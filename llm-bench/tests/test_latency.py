from __future__ import annotations

import json
from pathlib import Path
import pytest
import httpx

from bench.catalog import LatencyProbe
from bench.probes.latency import _load_fixture, run_probe


def _make_probe(sample_size: int = 50) -> LatencyProbe:
    return LatencyProbe(type="latency", fixture="test.jsonl", sample_size=sample_size)


# -- fixture loading -----------------------------------------------------------


def test_load_fixture_parses_jsonl(tmp_path: Path):
    f = tmp_path / "test.jsonl"
    f.write_text(
        json.dumps({"id": "p1", "prompt": "hello"})
        + "\n"
        + json.dumps({"id": "p2", "prompt": "world"})
        + "\n"
    )
    entries = _load_fixture(f)
    assert len(entries) == 2
    assert entries[0]["prompt"] == "hello"


def test_load_fixture_ignores_blank_lines(tmp_path: Path):
    f = tmp_path / "test.jsonl"
    f.write_text(
        json.dumps({"id": "p1", "prompt": "hello"})
        + "\n\n"
        + json.dumps({"id": "p2", "prompt": "world"})
        + "\n"
    )
    entries = _load_fixture(f)
    assert len(entries) == 2


# -- probe integration (mocked) ------------------------------------------------


def _build_sse_payload(prompt: str, delay_ms: float = 50.0) -> bytes:
    """Build a minimal SSE response that delivers one token after delay_ms."""
    data = json.dumps({"choices": [{"delta": {"content": "OK"}, "finish_reason": None}]})
    return f"data: {data}\n\n".encode()


def test_run_probe_returns_percentiles(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=3)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(
        "\n".join(
            json.dumps({"id": f"p{i}", "prompt": f"prompt-{i}"})
            for i in range(3)
        )
    )

    for _ in range(3):
        httpx_mock.add_response(
            method="POST",
            content=_build_sse_payload("x"),
            headers={"Content-Type": "text/event-stream"},
        )

    result = run_probe(probe, "https://llm.example.com", root=tmp_path)
    assert "ttft_p50_ms" in result
    assert "ttft_p95_ms" in result
    assert isinstance(result["ttft_p50_ms"], float)


def test_run_probe_uses_sample_size_limit(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=2)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(
        "\n".join(
            json.dumps({"id": f"p{i}", "prompt": f"prompt-{i}"})
            for i in range(10)
        )
    )

    for _ in range(2):
        httpx_mock.add_response(
            method="POST",
            content=_build_sse_payload("x"),
            headers={"Content-Type": "text/event-stream"},
        )

    run_probe(probe, "https://llm.example.com", root=tmp_path)
    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert str(requests[0].url) == "https://llm.example.com/chat/completions"


def test_run_probe_uses_api_key_header(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=1)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(json.dumps({"id": "p0", "prompt": "hi"}))

    httpx_mock.add_response(
        method="POST",
        content=_build_sse_payload("hi"),
        headers={"Content-Type": "text/event-stream"},
    )

    run_probe(probe, "https://llm.example.com", api_key="sk-test", root=tmp_path)
    req = httpx_mock.get_request()
    assert req.headers["Authorization"] == "Bearer sk-test"


def test_run_probe_4xx_raises(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=1)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(json.dumps({"id": "p0", "prompt": "hi"}))

    httpx_mock.add_response(method="POST", status_code=401, text="Unauthorized")

    with pytest.raises(httpx.HTTPStatusError):
        run_probe(probe, "https://llm.example.com", root=tmp_path)
