"""Benchmark runner — orchestrates catalog, probes, store, and OTel tracing."""

from __future__ import annotations

import logging
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .aggregates import compute_aggregates
from .catalog import (
    Capability,
    LatencyProbe,
    LmEvalProbe,
    PrometheusProbe,
    Probe,
    Suite,
    load_catalog,
    load_suite,
)
from .llama_swap import LlamaSwapClient
from .otel import init_tracing, log_run_to_phoenix
from .store import RunRecord, append_run

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------

def _discover_model(base_url: str, api_key: str = "") -> str:
    """Query the /v1/models endpoint and return the first available model id.

    Raises RuntimeError if the endpoint is unreachable or returns no models.
    """
    url = str(base_url.rstrip("/") + "/models")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Model discovery failed: {exc}") from exc

    data = resp.json()
    models = data.get("data", [])
    if not models:
        raise RuntimeError(
            f"Model discovery returned zero models from {url}. "
            "Ensure the endpoint is running and models are loaded."
        )
    return models[0]["id"]


# ---------------------------------------------------------------------------
# Probe dispatch (unified signature)
# ---------------------------------------------------------------------------

def _dispatch_probe(
    probe_obj: Probe,
    base_url: str,
    *,
    model: str,
    api_key: str = "",
    root: Path,
    run_dir: Path,
    prom_start: str | None,
    prom_end: str | None,
) -> tuple[dict[str, float | None], dict[str, str]]:
    """Dispatch a single probe by type and return (scores, artifacts).

    Uses the unified Phase 3 signature: ``func(probe, base_url, *, kwargs)``.
    Returns a ``(scores, artifacts)`` tuple. ``artifacts`` maps a descriptive
    key (e.g. ``"lm_eval_arc_challenge"``) to the on-disk path of any file the
    probe wrote. Currently only ``lm_eval`` produces artifacts; other probes
    return an empty artifact dict.
    """
    if isinstance(probe_obj, LatencyProbe):
        from .probes.latency import run_latency_probe

        scores = run_latency_probe(
            probe_obj,
            base_url,
            api_key=api_key,
            model=model,
            root=root,
        )
        return scores, {}

    if isinstance(probe_obj, LmEvalProbe):
        from .probes.lm_eval import run_lm_eval_probe

        output_path = run_dir / f"lm_eval_{probe_obj.task}.json"
        scores = run_lm_eval_probe(
            probe_obj,
            base_url,
            api_key=api_key,
            model=model,
            output_path=output_path,
        )
        return scores, {f"lm_eval_{probe_obj.task}": str(output_path)}

    if isinstance(probe_obj, PrometheusProbe):
        from .probes.prometheus import run_prometheus_window_probe

        if prom_start is None or prom_end is None:
            log.warning("Prometheus probe skipped: prom_start/prom_end not provided")
            return {}, {}

        scores = run_prometheus_window_probe(
            probe_obj,
            base_url,
            start=prom_start,
            end=prom_end,
        )
        return scores, {}

    raise ValueError(f"Unknown probe type: {type(probe_obj)}")


# ---------------------------------------------------------------------------
# Git SHA capture
# ---------------------------------------------------------------------------

def _read_git_sha(path: str | Path) -> str | None:
    """Return the HEAD commit SHA of the git repo containing ``path``.

    Returns ``None`` if ``path`` is not in a git checkout or ``git`` is not
    available. Never raises — failure to read the SHA must not fail a run.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired, OSError):
        return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_suite(
    *,
    base_url: str,
    catalog_root: Path,
    suite_id: str,
    api_key: str = "",
    model: str | None = None,
    runtime: str = "unknown",
    prom_start: str | None = None,
    prom_end: str | None = None,
    runs_path: Path | None = None,
    otlp_endpoint: str | None = None,
    quantization: str | None = None,
    ctx_length: int | None = None,
    sampling_params: dict[str, Any] | None = None,
    notes: str | None = None,
    pre_warm: bool = False,
) -> RunRecord:
    """Run a full benchmark suite and persist the result.

    Flow:
    1. Initialize OTel tracing (Phoenix) — *failures are logged and skipped*
    2. Discover model (unless ``model`` is given) — *failures abort the run*
    3. Load catalog + suite from YAML
    4. Execute probes sequentially (latency, lm_eval, prometheus)
       — *individual probe failures are caught, scored null, run continues*
    5. Compute aggregates from the suite definition
    6. Append result to JSONL store
    7. Emit run span to Phoenix — *failures are logged and skipped*

    Returns the ``RunRecord`` on success.
    Raises ``RuntimeError`` on model-discovery failure or catalog/suite load error.
    """
    base_url = base_url.rstrip("/")
    run_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()

    # 1. Init OTel tracing (best-effort)
    if otlp_endpoint:
        try:
            init_tracing(otlp_endpoint=otlp_endpoint)
            log.info("OTel tracing initialized → %s", otlp_endpoint)
        except Exception:
            log.warning("OTel tracing init failed, continuing without tracing: %s",
                        _exc_msg())

    # 2. Discover model (hard failure)
    if model is None:
        try:
            model = _discover_model(base_url, api_key=api_key)
            log.info("Discovered model: %s", model)
        except RuntimeError as exc:
            # Record a failed run before aborting
            record = _failed_record(
                run_id=run_id,
                started_at=started_at,
                base_url=base_url,
                suite_id=suite_id,
                error=str(exc),
                runtime=runtime,
                runs_path=runs_path,
                quantization=quantization,
                ctx_length=ctx_length,
                sampling_params=sampling_params,
                notes=notes,
            )
            append_run(runs_path, record)
            raise RuntimeError(f"Benchmark run aborted: {exc}") from exc

    # 2b. Pre-warm the model via llama-swap (best-effort).
    # If the endpoint is a llama-swap proxy and we want clean TTFT numbers,
    # send a 1-token request first so the model loads BEFORE the first probe.
    # The load time is captured as a metadata field for provenance.
    warm_time_sec: float | None = None
    if pre_warm:
        try:
            swap = LlamaSwapClient(base_url, api_key=api_key)
            warm_time_sec = swap.pre_warm(model)
            log.info("Pre-warmed %s in %.1fs", model, warm_time_sec)
        except Exception as exc:
            log.warning("Pre-warm failed (continuing — first probe will absorb load): %s", exc)

    # 3. Load catalog + suite
    catalog = load_catalog(catalog_root)
    suite = _load_suite_for_id(catalog_root, suite_id, catalog)

    # 4. Execute probes sequentially
    scores: dict[str, float | None] = {}
    artifacts: dict[str, str] = {}
    run_dir = Path("results") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    for cap_id in suite.capabilities:
        cap = catalog.get(cap_id)
        if cap is None:
            msg = f"Capability '{cap_id}' referenced in suite not found in catalog"
            log.error(msg)
            errors.append(msg)
            continue

        log.info("Running probe for capability %s (%s)", cap_id, cap.probe.type)
        try:
            probe_scores, probe_artifacts = _dispatch_probe(
                cap.probe,
                base_url,
                model=model,
                api_key=api_key,
                root=catalog_root,
                run_dir=run_dir,
                prom_start=prom_start,
                prom_end=prom_end,
            )
            scores.update(probe_scores)
            artifacts.update(probe_artifacts)
            log.info("Probe %s scores: %s", cap_id, probe_scores)
        except Exception as exc:
            # Telemetry probes (Prometheus) are best-effort: their failure
            # nulls the queried scores but does NOT mark the run as failed.
            # Scoring probes (latency, lm_eval) propagate failure.
            is_telemetry = isinstance(cap.probe, PrometheusProbe)
            level = "telemetry" if is_telemetry else "scoring"
            msg = f"Probe {cap_id} ({cap.probe.type}, {level}) failed: {exc}"
            for output in cap.outputs:
                scores[output.id] = None
            if is_telemetry:
                log.warning("%s — run continues with null %s scores",
                            msg, cap_id)
            else:
                log.warning(msg)
                errors.append(msg)

    # 5. Compute aggregates
    try:
        aggregates = compute_aggregates(scores, suite)
        scores.update(aggregates)
    except Exception as exc:
        msg = f"Aggregate computation failed: {exc}"
        log.error(msg)
        errors.append(msg)

    ended_at = datetime.now(timezone.utc).isoformat()
    status = "ok" if not errors else "failed"
    error_detail = "; ".join(errors) if errors else None

    # Best-effort git SHA capture for provenance.
    infra_git_sha = _read_git_sha(Path(__file__).parent)
    catalog_git_sha = _read_git_sha(catalog_root)

    # 6. Build and persist record
    record = RunRecord(
        run_uuid=run_id,
        started_at=started_at,
        ended_at=ended_at,
        endpoint_url=base_url,
        model_id=model,
        runtime=runtime,
        host=platform.node(),
        suite_id=suite_id,
        quantization=quantization,
        ctx_length=ctx_length,
        sampling_params=sampling_params or {},
        infra_git_sha=infra_git_sha,
        catalog_git_sha=catalog_git_sha,
        warm_time_sec=warm_time_sec,
        notes=notes,
        status=status,
        error=error_detail,
        scores=scores,
        artifacts=artifacts,
    )

    if runs_path:
        append_run(runs_path, record)
        log.info("Run record appended to %s", runs_path)

    # 7. Emit to Phoenix (best-effort)
    if otlp_endpoint:
        try:
            log_run_to_phoenix(record)
            log.info("Run span emitted to Phoenix")
        except Exception:
            log.warning("Phoenix span emission failed: %s", _exc_msg())

    return record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_suite_for_id(
    catalog_root: Path,
    suite_id: str,
    catalog: dict[str, Capability],
) -> Suite:
    """Find and load the suite YAML by iterating suites/*.yml."""
    suites_dir = Path(catalog_root) / "suites"
    if not suites_dir.is_dir():
        raise FileNotFoundError(
            f"Suites directory not found: {suites_dir}. "
            f"Expected suites/ subdirectory inside {catalog_root}."
        )

    for yml_path in sorted(suites_dir.glob("*.yml")):
        suite = load_suite(yml_path)
        if suite.id == suite_id:
            return suite

    available = ", ".join(sorted(s.id for s in (load_suite(p) for p in suites_dir.glob("*.yml"))))
    raise FileNotFoundError(
        f"Suite '{suite_id}' not found. Available suites: {available}"
    )


def _failed_record(
    *,
    run_id: str,
    started_at: str,
    base_url: str,
    suite_id: str,
    error: str,
    runtime: str = "unknown",
    runs_path: Path | None = None,
    quantization: str | None = None,
    ctx_length: int | None = None,
    sampling_params: dict[str, Any] | None = None,
    notes: str | None = None,
) -> RunRecord:
    """Build a RunRecord for a failed discovery attempt."""
    ended_at = datetime.now(timezone.utc).isoformat()
    return RunRecord(
        run_uuid=run_id,
        started_at=started_at,
        ended_at=ended_at,
        endpoint_url=base_url,
        model_id="",
        runtime=runtime,
        host=platform.node(),
        suite_id=suite_id,
        quantization=quantization,
        ctx_length=ctx_length,
        sampling_params=sampling_params or {},
        notes=notes,
        status="failed",
        error=error,
    )


def _exc_msg() -> str:
    """Extract a clean exception message from the current exception."""
    import sys
    exc_info = sys.exc_info()
    if exc_info[1]:
        return str(exc_info[1])
    return "unknown"
