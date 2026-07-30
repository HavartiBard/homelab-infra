# ComfyUI observability (spraycheese + goudai)

Centralized logs, metrics, dashboards, and alerts for the two ComfyUI hosts,
built entirely on the existing Grafana/Prometheus/Loki/Alertmanager stack on
Unraid. Nothing here is exposed outside the LAN.

## Architecture

```
spraycheese (Windows/Docker Desktop, NVIDIA)     goudai (Linux, AMD/ROCm)
┌───────────────────────────────────┐            ┌───────────────────────────────────┐
│ comfyui            :8188          │            │ comfyui               :8188        │
│ comfyui-exporter    :9840  ───┐   │            │ comfyui-exporter        :9840 ──┐  │
│ nvidia-gpu-exporter :9835  ───┤   │            │ (reads /sys for AMD GPU)         │  │
│ node_exporter       :9100  ───┤   │            │ node_exporter (existing) :9100 ──┤  │
│ cadvisor            :8081  ───┤   │            │ cadvisor (existing)      :8081 ──┤  │
│ promtail            :9080  ───┘   │            │ promtail (existing)      :9080 ──┘  │
└───────────────────────────────────┘            └───────────────────────────────────┘
              │  scraped/shipped over LAN                    │
              ▼                                               ▼
                    Unraid (192.168.20.14): Prometheus :9090, Loki :3100
                    Grafana :3030 → 5 "ComfyUI" dashboards, Alertmanager :9093 → Slack
```

`comfyui-exporter` is the same script/image on both hosts - it only talks to
ComfyUI's own local HTTP API (`/queue`, `/history`, `/system_stats`), which is
GPU-agnostic. On goudai it additionally reads AMD GPU sysfs directly
(`/sys` is bind-mounted read-only into that one container); on spraycheese
GPU metrics instead come from the separate `nvidia-gpu-exporter` container.

goudai already had node_exporter/cadvisor/promtail deployed
(`ansible/playbooks/observability/deploy-observability-agents.yml`) - this
work only added `comfyui-exporter` there. spraycheese previously had none of
the three (Windows/PowerShell SSH isn't compatible with the `raw`+`become`
tasks those roles use), so all four new services there
(`comfyui-exporter`, `nvidia-gpu-exporter`, `node_exporter`, `cadvisor`,
`promtail`) were added as plain compose services in
`ansible/playbooks/ai/deploy-comfyui.yml`, reusing the same container images
as every other host.

## Services and ports (LAN-only, nothing proxied through NPM)

| Service | Host(s) | Port | Notes |
|---|---|---|---|
| comfyui-exporter | spraycheese, goudai | 9840 | `/metrics` - ComfyUI-specific Prometheus metrics |
| nvidia-gpu-exporter | spraycheese | 9835 | `utkuozdemir/nvidia_gpu_exporter`, nvidia-smi based |
| node_exporter | spraycheese, goudai | 9100 | Host CPU/RAM/disk |
| cadvisor | spraycheese, goudai | 8081 | Per-container CPU/RAM/health |
| promtail | spraycheese, goudai | 9080 | Ships Docker container logs to Loki |
| Prometheus | Unraid | 9090 | internal |
| Loki | Unraid | 3100 | internal |
| Grafana | Unraid | 3030 | `grafana.klsll.com` |
| Alertmanager | Unraid | 9093 | internal, → Slack `#homelab-alerts` |

## Configuration files

| What | Path |
|---|---|
| ComfyUI exporter script (shared) | `ansible/files/comfyui-exporter/comfyui_exporter.py` |
| spraycheese compose | `ansible/files/spraycheese/comfyui/docker-compose.yml` |
| spraycheese deploy playbook | `ansible/playbooks/ai/deploy-comfyui.yml` |
| goudai compose | `ansible/files/goudai/comfyui-ltx/docker-compose.yml.j2` |
| goudai deploy playbook | `ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml` |
| Prometheus scrape config | `ansible/files/observability/prometheus/prometheus.yml` |
| Alert rules | `ansible/files/observability/prometheus/rules/alerts.yml` (`comfyui.rules` group) |
| Promtail pipeline stages | `ansible/roles/promtail/templates/promtail-config.yml.j2` (the `docker` job's `match` stages) |
| Dashboards | `ansible/files/observability/grafana/provisioning/dashboards/json/comfyui-*.json` |

## Deploying

```bash
cd ansible
# goudai
ansible-playbook playbooks/ai/deploy-comfyui-ltx-goudai.yml --syntax-check
ansible-playbook playbooks/ai/deploy-comfyui-ltx-goudai.yml --check --diff --limit goudai
ansible-playbook playbooks/ai/deploy-comfyui-ltx-goudai.yml --limit goudai

# spraycheese
ansible-playbook playbooks/ai/deploy-comfyui.yml --syntax-check
ansible-playbook playbooks/ai/deploy-comfyui.yml --check --diff --limit spraycheese
ansible-playbook playbooks/ai/deploy-comfyui.yml --limit unraid,spraycheese

# Push the updated Prometheus/Promtail/dashboard config to Unraid
./scripts/run-playbook.sh observability playbooks/observability/deploy-observability.yml --limit unraid --check --diff
./scripts/run-playbook.sh observability playbooks/observability/deploy-observability.yml --limit unraid
./scripts/run-playbook.sh observability playbooks/observability/deploy-observability-agents.yml --limit goudai --check --diff
./scripts/run-playbook.sh observability playbooks/observability/deploy-observability-agents.yml --limit goudai
```

`deploy-observability.yml` reloads Prometheus and re-copies dashboard JSON on
every run - it's safe to re-run any time config changes.

## Viewing logs

```bash
# Tail raw ComfyUI logs directly
docker logs -f comfyui           # on either host

# Via Loki (from Unraid, or any host that can reach it)
curl -s -G http://192.168.20.14:3100/loki/api/v1/query_range \
  --data-urlencode 'query={container="comfyui"}' \
  --data-urlencode 'limit=50' | jq

# Only errors, either host
curl -s -G http://192.168.20.14:3100/loki/api/v1/query_range \
  --data-urlencode 'query={container="comfyui", level="error"}' | jq
```

Or use the "Recent ComfyUI Error Logs" panel on the **ComfyUI Overview**
dashboard, or Grafana Explore with the `Loki` datasource.

Note: `prompt_id` is **not** a Loki label (it's unique per job and would
fragment the log index) - it's available instead via the exporter's
Prometheus metrics.

## Restarting collectors safely

None of these restarts touch the `comfyui` container or interrupt a
running/queued generation job:

```bash
cd /opt/comfyui          # goudai: /opt/comfyui, spraycheese: C:\opt\comfyui
docker compose restart comfyui-exporter
docker compose restart promtail
docker compose restart node_exporter cadvisor        # spraycheese only
docker compose restart nvidia-gpu-exporter            # spraycheese only
```

To restart Promtail on every homelab host at once (e.g. after a config
change to the shared template), re-run
`playbooks/observability/deploy-observability-agents.yml` - it's idempotent
and only touches the promtail/node_exporter/cadvisor containers.

## Inspecting and releasing goudai ComfyUI memory

ComfyUI's API exposes device and PyTorch allocator memory, but it does not
provide a guaranteed authoritative list of every resident model. The helper
reports both memory layers, queue state, and model names found in the last 20
workflow records:

```bash
scripts/goudai-comfyui-gpu.sh status
```

After image or video generation, release ComfyUI's cached models without
restarting the service:

```bash
scripts/goudai-comfyui-gpu.sh free
```

If the allocator still retains GPU memory, restart ComfyUI. This interrupts
active work and is intentionally a separate command:

```bash
scripts/goudai-comfyui-gpu.sh restart
```

These cleanup actions do not affect llama-swap or other goudai services.

## Validating both hosts are reporting

```bash
# 1. Every new job should show up=1 for both instances
curl -s http://192.168.20.14:9090/api/v1/targets | \
  jq '.data.activeTargets[] | select(.labels.job | test("comfyui_exporter|nvidia_gpu_exporter|node_exporter|cadvisor|promtail")) | {job: .labels.job, instance: .labels.instance, health}'

# 2. The exporter is actually talking to ComfyUI (no connection-refused)
docker logs comfyui-exporter --tail 50    # on either host

# 3. Trigger one real generation on each host, then confirm:
#    - a log line lands in Loki (see "Viewing logs" above)
#    - the completion counter incremented:
curl -s 'http://192.168.20.14:9090/api/v1/query?query=comfyui_prompts_completed_total' | jq

# 4. Open each dashboard in Grafana and confirm panels aren't "No data":
#    ComfyUI Overview, ComfyUI Generation Jobs, ComfyUI GPU and VRAM,
#    ComfyUI Errors and Restarts, ComfyUI: spraycheese vs goudai
```

## Known limitations

- **spraycheese host metrics (CPU/RAM/disk) reflect the Docker Desktop WSL2
  VM, not raw Windows perfmon counters.** CPU/RAM are a reasonably close
  proxy (WSL2 shares cores/memory dynamically with the host); disk usage
  reflects the VM's virtual disk, not the real `C:\` drive. A native
  `windows_exporter` service would be more accurate but was intentionally not
  used, to avoid introducing a new Windows-native deployment mechanism into
  this repo for now.
- **NVIDIA vs AMD metric parity isn't 1:1.** `nvidia-gpu-exporter` reports
  encoder/decoder utilization; there's no equivalent readily available for
  the AMD APU via sysfs, so that panel on the GPU & VRAM dashboard is
  NVIDIA-only.
- **`workflow_type` is a heuristic, not a true workflow name.** ComfyUI
  doesn't track a friendly workflow identifier server-side. The exporter
  guesses `image` vs `video-ltx` by scanning node `class_type`s in the prompt
  graph for known video-related nodes (`LTX2_SM_*`, `VHS_*`).
  `comfyui_model_prompt_total` (checkpoint usage) is similarly best-effort -
  it counts prompts referencing a checkpoint, not true model load/unload
  events (ComfyUI caches models, so "used in a prompt" ≠ "just loaded").
- **The Loki `job_status`/`level` labels depend on ComfyUI's exact log
  strings** (`got prompt`, `Prompt executed in ... seconds`,
  `Exception during processing`), taken from ComfyUI's known source but not
  verified against a live deployment. If job_status/level don't show up in
  Loki after rollout, check `docker logs comfyui` for the actual strings and
  adjust the `match` stages in
  `ansible/roles/promtail/templates/promtail-config.yml.j2`.
- **`nvidia-gpu-exporter`'s metric names** (`nvidia_smi_utilization_gpu_ratio`,
  `nvidia_smi_memory_used_bytes`, etc., used in the dashboards and the VRAM
  alert) are the exporter's documented names - verify against its actual
  `/metrics` output after first deploy in case the pinned version's schema
  differs.
- **Container-restart detection** reuses the existing generic
  `ContainerRestartLoop` alert (any container, any host) rather than a
  ComfyUI-specific alert rule - the Errors and Restarts dashboard has a
  ComfyUI-scoped panel, but the alert itself is not scoped to `container=comfyui`.
