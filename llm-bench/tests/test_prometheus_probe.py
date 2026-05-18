from __future__ import annotations

import pytest

from bench.catalog import PrometheusProbe
from bench.probes.prometheus import run_prometheus_window_probe


def _make_response(data: list[dict]) -> dict:
    return {"status": "success", "data": data}


def test_prometheus_probe_returns_mapped_scores(monkeypatch):
    probe = PrometheusProbe(
        type="prometheus_window",
        queries={
            "ttft_p50_ms": "histogram_quantile(0.5, sum_rate(ttft_bucket[$duration]))",
            "decode_tps": "avg_rate(decode_tokens_total[$duration])",
        },
    )

    call_log: list[dict] = []

    class FakeResponse:
        def __init__(self, data: list[dict]):
            self._data = data
            self.status_code = 200

        def json(self):
            return _make_response(self._data)

        def raise_for_status(self):
            pass

    responses = [
        FakeResponse([
            {
                "metric": {},
                "values": [[1700000000, "120.5"], [1700000060, "130.2"]],
            },
        ]),
        FakeResponse([
            {
                "metric": {},
                "values": [[1700000000, "45.1"], [1700000060, "48.7"]],
            },
        ]),
    ]
    resp_iter = iter(responses)

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, url, params=None):
            call_log.append({"url": url, "params": dict(params) if params else {}})
            return next(resp_iter)

    monkeypatch.setattr("httpx.Client", FakeClient)

    result = run_prometheus_window_probe(
        probe,
        base_url="http://prometheus:9090",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T01:00:00Z",
        step="60s",
    )

    assert result["ttft_p50_ms"] == pytest.approx(125.35)
    assert result["decode_tps"] == pytest.approx(46.9)

    # Verify $duration was substituted with "1h" (1 hour window)
    for call in call_log:
        params = call["params"]
        assert "$duration" not in params["query"]
        assert "1h" in params["query"]


def test_prometheus_probe_handles_empty_series(monkeypatch):
    probe = PrometheusProbe(
        type="prometheus_window",
        queries={"cpu_idle": "node_cpu_seconds_total{mode='idle'}"},
    )

    class FakeResponse:
        status_code = 200

        def json(self):
            return _make_response([{"metric": {}, "values": []}])

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr("httpx.Client", FakeClient)

    result = run_prometheus_window_probe(
        probe,
        base_url="http://prometheus:9090",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T01:00:00Z",
        step="60s",
    )

    assert result["cpu_idle"] is None
