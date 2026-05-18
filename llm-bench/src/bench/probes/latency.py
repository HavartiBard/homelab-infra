"""Latency probe — measure Time to First Token (TTFT) via streaming requests."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from ..catalog import LatencyProbe


def _load_fixture(fixture_path: str | Path) -> list[dict[str, Any]]:
    """Load prompts from a JSONL fixture file."""
    prompts: list[dict[str, Any]] = []
    for line in Path(fixture_path).read_text().strip().splitlines():
        if line.strip():
            prompts.append(json.loads(line))
    return prompts


def run_probe(
    probe: LatencyProbe,
    base_url: str,
    *,
    api_key: str = "",
    model: str = "default",
    root: str | Path = ".",
) -> dict[str, float]:
    """Execute a latency probe and return {output_id: value}.

    Sends ``probe.sample_size`` streaming requests to an OpenAI-compatible
    endpoint and returns TTFT percentiles (p50, p95) in milliseconds.
    """
    fixture_path = Path(root) / probe.fixture
    prompts = _load_fixture(fixture_path)
    batch = prompts[: probe.sample_size]

    ttfts: list[float] = []
    endpoint = str(base_url.rstrip("/") + "/chat/completions")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(timeout=120) as client:
        for entry in batch:
            payload: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": entry["prompt"]}],
                "stream": True,
                "max_tokens": 1,
            }
            start = time.perf_counter()
            with client.stream("POST", endpoint, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                for _line in resp.iter_lines():
                    ttfts.append((time.perf_counter() - start) * 1000)
                    break

    sorted_latencies = sorted(ttfts)
    n = len(sorted_latencies)
    p50 = sorted_latencies[int(n * 0.50)]
    p95 = sorted_latencies[min(int(n * 0.95), n - 1)]

    return {"ttft_p50_ms": round(p50, 2), "ttft_p95_ms": round(p95, 2)}
