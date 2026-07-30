#!/usr/bin/env python3
"""Prometheus exporter for a local ComfyUI instance.

Polls ComfyUI's own HTTP API (/queue, /history, /system_stats) on a fixed
interval and serves the derived metrics on /metrics. Talks only to ComfyUI on
the shared "comfyui" Docker network - no GPU vendor tooling required, so the
same script/image runs unmodified on both the NVIDIA (spraycheese) and AMD
(goudai) hosts.

Env vars:
  COMFYUI_URL      base URL of the ComfyUI instance (default http://comfyui:8188)
  POLL_INTERVAL     seconds between polls (default 10)
  METRICS_PORT      port to serve /metrics on (default 9840)
  HISTORY_MAX_SEEN  bounds memory for the dedupe set (default 2000)
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://comfyui:8188").rstrip("/")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "10"))
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9840"))
HISTORY_MAX_SEEN = int(os.environ.get("HISTORY_MAX_SEEN", "2000"))

# Node class_type substrings used to guess whether a prompt graph is an image
# or video workflow. Best-effort only - ComfyUI does not track a friendly
# workflow name server-side.
VIDEO_NODE_HINTS = ("LTX2_SM", "VHS_", "LTXV", "VideoCombine")
CHECKPOINT_NODE_HINTS = ("CheckpointLoader", "UNETLoader", "DiffusionModelLoader")
OOM_PATTERNS = re.compile(r"out of memory|CUDA error|HIP error", re.IGNORECASE)

def read_amd_gpu_sysfs():
    """Best-effort AMD GPU read via kernel sysfs (amdgpu driver).

    No-op (returns {}) unless /sys is bind-mounted into this container AND an
    amdgpu card is present - i.e. only produces data on goudai. NVIDIA's
    driver doesn't populate gpu_busy_percent under sysfs, so this is
    naturally a no-op on spraycheese even if /sys were mounted there.
    """
    drm = "/sys/class/drm"
    if not os.path.isdir(drm):
        return {}
    base = None
    for entry in sorted(os.listdir(drm)):
        busy_path = os.path.join(drm, entry, "device", "gpu_busy_percent")
        if entry.startswith("card") and os.path.exists(busy_path):
            base = os.path.join(drm, entry, "device")
            break
    if base is None:
        return {}

    result = {}
    for key, filename in [
        ("vram_used", "mem_info_vram_used"),
        ("vram_total", "mem_info_vram_total"),
        ("busy_percent", "gpu_busy_percent"),
    ]:
        try:
            with open(os.path.join(base, filename)) as f:
                result[key] = int(f.read().strip())
        except (OSError, ValueError):
            pass

    hwmon_dir = os.path.join(base, "hwmon")
    if os.path.isdir(hwmon_dir):
        for hw in sorted(os.listdir(hwmon_dir)):
            sensor = os.path.join(hwmon_dir, hw)
            try:
                with open(os.path.join(sensor, "name")) as f:
                    if f.read().strip() != "amdgpu":
                        continue
            except OSError:
                continue
            try:
                with open(os.path.join(sensor, "temp1_input")) as f:
                    result["temp_celsius"] = int(f.read().strip()) / 1000.0
            except (OSError, ValueError):
                pass
            try:
                with open(os.path.join(sensor, "power1_average")) as f:
                    result["power_watts"] = int(f.read().strip()) / 1_000_000.0
            except (OSError, ValueError):
                pass
            break
    return result


_lock = threading.Lock()
_state = {
    "up": 0,
    "amd_gpu": {},
    "scrape_timestamp": 0,
    "scrape_errors_total": 0,
    "queue_running": 0,
    "queue_pending": 0,
    "prompts_completed_total": {},  # workflow_type -> count
    "prompts_errored_total": {},  # workflow_type -> count
    "oom_errors_total": 0,
    "node_errors_total": {},  # node_type -> count
    "last_prompt_duration_seconds": {},  # workflow_type -> last value
    "prompt_duration_seconds_sum": {},  # workflow_type -> cumulative sum
    "prompt_duration_seconds_count": {},  # workflow_type -> cumulative count
    "model_prompt_total": {},  # model name -> count
    "vram": [],  # list of {device, vram_total, vram_free}
}
_seen_prompt_ids = set()
_seen_order = []


def escape_label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_metric(name, value, labels=None):
    labels = labels or {}
    if labels:
        rendered = ",".join(f'{k}="{escape_label(v)}"' for k, v in sorted(labels.items()))
        return f"{name}{{{rendered}}} {value}"
    return f"{name} {value}"


def get_json(path, timeout=5):
    with urllib.request.urlopen(f"{COMFYUI_URL}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def classify_workflow(prompt_graph):
    for node in (prompt_graph or {}).values():
        class_type = node.get("class_type", "") if isinstance(node, dict) else ""
        if any(hint in class_type for hint in VIDEO_NODE_HINTS):
            return "video-ltx"
    return "image" if prompt_graph else "unknown"


def checkpoint_names(prompt_graph):
    names = []
    for node in (prompt_graph or {}).values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type", "")
        if any(hint in class_type for hint in CHECKPOINT_NODE_HINTS):
            inputs = node.get("inputs", {})
            for key in ("ckpt_name", "unet_name", "model_name"):
                if key in inputs and isinstance(inputs[key], str):
                    names.append(inputs[key])
    return names


def remember_prompt_id(prompt_id):
    _seen_prompt_ids.add(prompt_id)
    _seen_order.append(prompt_id)
    if len(_seen_order) > HISTORY_MAX_SEEN:
        oldest = _seen_order.pop(0)
        _seen_prompt_ids.discard(oldest)


def poll_once():
    try:
        queue = get_json("/queue")
        history = get_json("/history")
        system_stats = get_json("/system_stats")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError):
        with _lock:
            _state["up"] = 0
            _state["scrape_errors_total"] += 1
        return

    amd_gpu = read_amd_gpu_sysfs()

    with _lock:
        _state["up"] = 1
        _state["scrape_timestamp"] = int(time.time())
        _state["amd_gpu"] = amd_gpu
        _state["queue_running"] = len(queue.get("queue_running", []))
        _state["queue_pending"] = len(queue.get("queue_pending", []))

        _state["vram"] = []
        for device in system_stats.get("devices", []):
            _state["vram"].append(
                {
                    "device": device.get("name", "unknown"),
                    "vram_total": device.get("vram_total", 0),
                    "vram_free": device.get("vram_free", 0),
                    "torch_vram_total": device.get("torch_vram_total", 0),
                    "torch_vram_free": device.get("torch_vram_free", 0),
                }
            )

        for prompt_id, entry in history.items():
            if prompt_id in _seen_prompt_ids:
                continue
            remember_prompt_id(prompt_id)

            prompt_graph = (entry.get("prompt") or [None, None, {}])[2]
            workflow_type = classify_workflow(prompt_graph)
            status = entry.get("status", {})
            status_str = status.get("status_str", "unknown")
            messages = dict(status.get("messages", []))

            start_ts = messages.get("execution_start", {}).get("timestamp")
            end_ts = None
            for event in ("execution_success", "execution_error", "execution_interrupted"):
                if event in messages:
                    end_ts = messages[event].get("timestamp")
                    break
            if start_ts and end_ts and end_ts >= start_ts:
                duration = (end_ts - start_ts) / 1000.0
                _state["last_prompt_duration_seconds"][workflow_type] = duration
                _state["prompt_duration_seconds_sum"][workflow_type] = (
                    _state["prompt_duration_seconds_sum"].get(workflow_type, 0) + duration
                )
                _state["prompt_duration_seconds_count"][workflow_type] = (
                    _state["prompt_duration_seconds_count"].get(workflow_type, 0) + 1
                )

            if status_str == "success":
                _state["prompts_completed_total"][workflow_type] = (
                    _state["prompts_completed_total"].get(workflow_type, 0) + 1
                )
            elif status_str == "error":
                _state["prompts_errored_total"][workflow_type] = (
                    _state["prompts_errored_total"].get(workflow_type, 0) + 1
                )
                error_event = messages.get("execution_error", {})
                node_type = error_event.get("node_type", "unknown")
                exception_message = error_event.get("exception_message", "")
                _state["node_errors_total"][node_type] = (
                    _state["node_errors_total"].get(node_type, 0) + 1
                )
                if OOM_PATTERNS.search(exception_message):
                    _state["oom_errors_total"] += 1

            for model in checkpoint_names(prompt_graph):
                _state["model_prompt_total"][model] = _state["model_prompt_total"].get(model, 0) + 1


def poll_loop():
    while True:
        poll_once()
        time.sleep(POLL_INTERVAL)


def render_metrics():
    with _lock:
        state = json.loads(json.dumps(_state))  # cheap deep copy

    lines = [
        "# HELP comfyui_up Whether the ComfyUI HTTP API responded on the last scrape.",
        "# TYPE comfyui_up gauge",
        render_metric("comfyui_up", state["up"]),
        "# HELP comfyui_scrape_timestamp_seconds Unix timestamp of the last successful scrape.",
        "# TYPE comfyui_scrape_timestamp_seconds gauge",
        render_metric("comfyui_scrape_timestamp_seconds", state["scrape_timestamp"]),
        "# HELP comfyui_exporter_scrape_errors_total Count of failed polls against the ComfyUI API.",
        "# TYPE comfyui_exporter_scrape_errors_total counter",
        render_metric("comfyui_exporter_scrape_errors_total", state["scrape_errors_total"]),
        "# HELP comfyui_queue_running Number of prompts currently executing.",
        "# TYPE comfyui_queue_running gauge",
        render_metric("comfyui_queue_running", state["queue_running"]),
        "# HELP comfyui_queue_pending Number of prompts waiting in the queue.",
        "# TYPE comfyui_queue_pending gauge",
        render_metric("comfyui_queue_pending", state["queue_pending"]),
    ]

    lines.append("# HELP comfyui_prompts_completed_total Prompts that finished successfully.")
    lines.append("# TYPE comfyui_prompts_completed_total counter")
    for workflow_type, count in state["prompts_completed_total"].items():
        lines.append(render_metric("comfyui_prompts_completed_total", count, {"workflow_type": workflow_type}))

    lines.append("# HELP comfyui_prompts_errored_total Prompts that finished with an error.")
    lines.append("# TYPE comfyui_prompts_errored_total counter")
    for workflow_type, count in state["prompts_errored_total"].items():
        lines.append(render_metric("comfyui_prompts_errored_total", count, {"workflow_type": workflow_type}))

    lines.append("# HELP comfyui_oom_errors_total Errored prompts whose exception message looked like a GPU OOM (CUDA/HIP).")
    lines.append("# TYPE comfyui_oom_errors_total counter")
    lines.append(render_metric("comfyui_oom_errors_total", state["oom_errors_total"]))

    lines.append("# HELP comfyui_node_errors_total Errored prompts by the node type that raised the exception.")
    lines.append("# TYPE comfyui_node_errors_total counter")
    for node_type, count in state["node_errors_total"].items():
        lines.append(render_metric("comfyui_node_errors_total", count, {"node_type": node_type}))

    lines.append("# HELP comfyui_last_prompt_duration_seconds Duration of the most recently finished prompt.")
    lines.append("# TYPE comfyui_last_prompt_duration_seconds gauge")
    for workflow_type, duration in state["last_prompt_duration_seconds"].items():
        lines.append(render_metric("comfyui_last_prompt_duration_seconds", duration, {"workflow_type": workflow_type}))

    lines.append("# HELP comfyui_prompt_duration_seconds_sum Cumulative sum of prompt durations (divide by _count for an average).")
    lines.append("# TYPE comfyui_prompt_duration_seconds_sum counter")
    for workflow_type, total in state["prompt_duration_seconds_sum"].items():
        lines.append(render_metric("comfyui_prompt_duration_seconds_sum", total, {"workflow_type": workflow_type}))

    lines.append("# HELP comfyui_prompt_duration_seconds_count Count of prompts included in _sum.")
    lines.append("# TYPE comfyui_prompt_duration_seconds_count counter")
    for workflow_type, count in state["prompt_duration_seconds_count"].items():
        lines.append(render_metric("comfyui_prompt_duration_seconds_count", count, {"workflow_type": workflow_type}))

    lines.append("# HELP comfyui_model_prompt_total Prompts seen using a given checkpoint/model (best-effort, not a true load event).")
    lines.append("# TYPE comfyui_model_prompt_total counter")
    for model, count in state["model_prompt_total"].items():
        lines.append(render_metric("comfyui_model_prompt_total", count, {"model": model}))

    lines.append("# HELP comfyui_vram_total_bytes Total VRAM on the device, as reported by ComfyUI itself.")
    lines.append("# TYPE comfyui_vram_total_bytes gauge")
    lines.append("# HELP comfyui_vram_free_bytes Free VRAM on the device, as reported by ComfyUI itself.")
    lines.append("# TYPE comfyui_vram_free_bytes gauge")
    for device in state["vram"]:
        labels = {"device": device["device"]}
        lines.append(render_metric("comfyui_vram_total_bytes", device["vram_total"], labels))
        lines.append(render_metric("comfyui_vram_free_bytes", device["vram_free"], labels))
        lines.append(render_metric("comfyui_torch_vram_total_bytes", device["torch_vram_total"], labels))
        lines.append(render_metric("comfyui_torch_vram_free_bytes", device["torch_vram_free"], labels))

    amd_gpu = state["amd_gpu"]
    if amd_gpu:
        lines.append("# HELP comfyui_amd_gpu_busy_percent AMD GPU busy percentage (amdgpu sysfs).")
        lines.append("# TYPE comfyui_amd_gpu_busy_percent gauge")
        if "busy_percent" in amd_gpu:
            lines.append(render_metric("comfyui_amd_gpu_busy_percent", amd_gpu["busy_percent"]))
        lines.append("# HELP comfyui_amd_gpu_vram_used_bytes AMD GPU VRAM used (amdgpu sysfs).")
        lines.append("# TYPE comfyui_amd_gpu_vram_used_bytes gauge")
        if "vram_used" in amd_gpu:
            lines.append(render_metric("comfyui_amd_gpu_vram_used_bytes", amd_gpu["vram_used"]))
        lines.append("# HELP comfyui_amd_gpu_vram_total_bytes AMD GPU total VRAM (amdgpu sysfs).")
        lines.append("# TYPE comfyui_amd_gpu_vram_total_bytes gauge")
        if "vram_total" in amd_gpu:
            lines.append(render_metric("comfyui_amd_gpu_vram_total_bytes", amd_gpu["vram_total"]))
        if "temp_celsius" in amd_gpu:
            lines.append("# HELP comfyui_amd_gpu_temperature_celsius AMD GPU edge temperature (amdgpu hwmon).")
            lines.append("# TYPE comfyui_amd_gpu_temperature_celsius gauge")
            lines.append(render_metric("comfyui_amd_gpu_temperature_celsius", amd_gpu["temp_celsius"]))
        if "power_watts" in amd_gpu:
            lines.append("# HELP comfyui_amd_gpu_power_watts AMD GPU average package power (amdgpu hwmon).")
            lines.append("# TYPE comfyui_amd_gpu_power_watts gauge")
            lines.append(render_metric("comfyui_amd_gpu_power_watts", amd_gpu["power_watts"]))

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = render_metrics().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # keep container logs quiet - this is polled every few seconds


def main():
    threading.Thread(target=poll_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", METRICS_PORT), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
