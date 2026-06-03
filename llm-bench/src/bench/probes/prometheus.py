"""Prometheus window probe — run PromQL queries against a Prometheus target."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from ..catalog import PrometheusProbe


def run_prometheus_window_probe(
    probe: PrometheusProbe,
    base_url: str,
    *,
    start: str,
    end: str,
    step: str = "15s",
    root: str | Path = ".",
) -> dict[str, float | None]:
    """Execute PromQL range queries and return {output_id: avg_value}.

    Each PromQL string may contain ``$duration`` which is replaced with
    the computed window duration (``end - start``) before sending to
    Prometheus.
    """
    base_url = base_url.rstrip("/")

    # Derive duration string from start/end ISO-8601 timestamps
    from datetime import datetime, timezone

    st = datetime.fromisoformat(start.replace("Z", "+00:00"))
    et = datetime.fromisoformat(end.replace("Z", "+00:00"))
    total_seconds = int((et - st).total_seconds())
    # Convert to a Prometheus-friendly duration like "1h30m"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    duration = "".join(parts)

    results: dict[str, float | None] = {}

    with httpx.Client(timeout=120) as client:
        for output_id, query in probe.queries.items():
            substituted = query.replace("$duration", duration)
            resp = client.get(
                f"{base_url}/api/v1/query_range",
                params={
                    "query": substituted,
                    "start": start,
                    "end": end,
                    "step": step,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Average all datapoints across all series in the response
            values: list[float] = []
            for series in data.get("data", []):
                for ts_val in series.get("values", []):
                    val_str: str = ts_val[1]
                    if val_str.lower() not in ("nan", "inf", "-inf", "null", ""):
                        values.append(float(val_str))

            results[output_id] = (
                round(sum(values) / len(values), 4) if values else None
            )

    return results
