"""Latency probe — TTFT (time to first token) + decode/prompt throughput."""

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


def run_latency_probe(
    probe: LatencyProbe,
    base_url: str,
    *,
    api_key: str = "",
    model: str = "default",
    root: str | Path = ".",
) -> dict[str, float]:
    """Execute a latency probe and return TTFT + throughput outputs.

    For each of ``probe.sample_size`` streaming chat completions, measures:

    - **TTFT**: time from request start to first content chunk
    - **decode rate**: output tokens / (last chunk - first chunk)
    - **prompt eval rate**: prompt tokens / TTFT

    Requests are sent with ``stream_options.include_usage=True`` so the final
    chunk carries ``prompt_tokens`` / ``completion_tokens``. Falls back to
    whitespace-split heuristics if the endpoint doesn't emit usage.

    Returns:
        {ttft_p50_ms, ttft_p95_ms, decode_tokens_per_sec, prompt_eval_tokens_per_sec}
    """
    fixture_path = Path(root) / probe.fixture
    prompts = _load_fixture(fixture_path)
    batch = prompts[: probe.sample_size]

    ttfts: list[float] = []
    decode_rates: list[float] = []
    prompt_rates: list[float] = []

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
                "max_tokens": 64,
                "stream_options": {"include_usage": True},
            }
            start = time.perf_counter()
            first_chunk_at: float | None = None
            output_tokens = 0
            prompt_tokens: int | None = None

            with client.stream("POST", endpoint, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                for raw in resp.iter_lines():
                    if not raw or not raw.startswith("data: "):
                        continue
                    body = raw[len("data: ") :]
                    if body.strip() == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(body)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content") or ""
                        if content:
                            if first_chunk_at is None:
                                first_chunk_at = time.perf_counter()
                            output_tokens += max(1, len(content.split()))

                    usage = chunk.get("usage")
                    if usage:
                        if usage.get("prompt_tokens") is not None:
                            prompt_tokens = usage["prompt_tokens"]
                        if usage.get("completion_tokens") is not None:
                            output_tokens = usage["completion_tokens"]

            end = time.perf_counter()

            if first_chunk_at is None:
                continue

            ttfts.append((first_chunk_at - start) * 1000)

            decode_window = end - first_chunk_at
            if decode_window > 0 and output_tokens > 0:
                decode_rates.append(output_tokens / decode_window)

            if prompt_tokens is None:
                prompt_tokens = max(1, len(entry["prompt"].split()))
            ttft_seconds = first_chunk_at - start
            if ttft_seconds > 0:
                prompt_rates.append(prompt_tokens / ttft_seconds)

    if not ttfts:
        raise RuntimeError(
            "Latency probe: no TTFT samples collected (no responses produced content). "
            "Check endpoint reachability and that the model is loaded."
        )

    sorted_latencies = sorted(ttfts)
    n = len(sorted_latencies)
    p50 = sorted_latencies[int(n * 0.50)]
    p95 = sorted_latencies[min(int(n * 0.95), n - 1)]

    return {
        "ttft_p50_ms": round(p50, 2),
        "ttft_p95_ms": round(p95, 2),
        "decode_tokens_per_sec": (
            round(sum(decode_rates) / len(decode_rates), 2) if decode_rates else 0.0
        ),
        "prompt_eval_tokens_per_sec": (
            round(sum(prompt_rates) / len(prompt_rates), 2) if prompt_rates else 0.0
        ),
    }
