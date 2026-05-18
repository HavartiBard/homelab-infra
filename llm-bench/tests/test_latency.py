from __future__ import annotations

import json
from pathlib import Path
import pytest
import httpx

from bench.catalog import LatencyProbe
from bench.probes.latency import _load_fixture, run_latency_probe


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


def _content_sse_payload() -> bytes:
    """SSE response with one content chunk (no usage)."""
    data = json.dumps({"choices": [{"delta": {"content": "OK"}, "finish_reason": None}]})
    return f"data: {data}\n\n".encode()


def _content_with_usage_payload(
    prompt_tokens: int = 10, completion_tokens: int = 5
) -> bytes:
    """SSE response with one content chunk + a final usage chunk."""
    content = json.dumps(
        {"choices": [{"delta": {"content": "hello world"}, "finish_reason": None}]}
    )
    usage = json.dumps(
        {
            "choices": [],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }
    )
    return f"data: {content}\n\ndata: {usage}\n\ndata: [DONE]\n\n".encode()


def test_run_probe_returns_all_four_outputs(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=3)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(
        "\n".join(
            json.dumps({"id": f"p{i}", "prompt": f"prompt-{i}"}) for i in range(3)
        )
    )

    for _ in range(3):
        httpx_mock.add_response(
            method="POST",
            content=_content_sse_payload(),
            headers={"Content-Type": "text/event-stream"},
        )

    result = run_latency_probe(probe, "https://llm.example.com", root=tmp_path)
    # All four output IDs declared by the ttft + throughput capabilities must be present.
    assert set(result) == {
        "ttft_p50_ms",
        "ttft_p95_ms",
        "decode_tokens_per_sec",
        "prompt_eval_tokens_per_sec",
    }
    assert isinstance(result["ttft_p50_ms"], float)


def test_run_probe_uses_usage_chunk_when_present(tmp_path: Path, httpx_mock):
    """When the endpoint emits a final usage chunk, the probe should not crash
    and should produce non-negative throughput rates."""
    probe = _make_probe(sample_size=1)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(json.dumps({"id": "p", "prompt": "hello world"}))

    httpx_mock.add_response(
        method="POST",
        content=_content_with_usage_payload(prompt_tokens=42, completion_tokens=10),
        headers={"Content-Type": "text/event-stream"},
    )

    result = run_latency_probe(probe, "https://llm.example.com", root=tmp_path)
    assert result["decode_tokens_per_sec"] >= 0.0
    assert result["prompt_eval_tokens_per_sec"] >= 0.0


def test_run_probe_uses_sample_size_limit(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=2)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(
        "\n".join(
            json.dumps({"id": f"p{i}", "prompt": f"prompt-{i}"}) for i in range(10)
        )
    )

    for _ in range(2):
        httpx_mock.add_response(
            method="POST",
            content=_content_sse_payload(),
            headers={"Content-Type": "text/event-stream"},
        )

    run_latency_probe(probe, "https://llm.example.com", root=tmp_path)
    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert str(requests[0].url) == "https://llm.example.com/chat/completions"


def test_run_probe_uses_api_key_header(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=1)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(json.dumps({"id": "p0", "prompt": "hi"}))

    httpx_mock.add_response(
        method="POST",
        content=_content_sse_payload(),
        headers={"Content-Type": "text/event-stream"},
    )

    run_latency_probe(
        probe, "https://llm.example.com", api_key="sk-test", root=tmp_path
    )
    req = httpx_mock.get_request()
    assert req.headers["Authorization"] == "Bearer sk-test"


def test_run_probe_4xx_raises(tmp_path: Path, httpx_mock):
    probe = _make_probe(sample_size=1)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(json.dumps({"id": "p0", "prompt": "hi"}))

    httpx_mock.add_response(method="POST", status_code=401, text="Unauthorized")

    with pytest.raises(httpx.HTTPStatusError):
        run_latency_probe(probe, "https://llm.example.com", root=tmp_path)


def test_run_probe_raises_when_no_samples_collected(tmp_path: Path, httpx_mock):
    """If every response yields only [DONE] with no content, the percentile
    calculation would IndexError without a guard. We raise instead."""
    probe = _make_probe(sample_size=2)
    fixture = tmp_path / "test.jsonl"
    fixture.write_text(
        "\n".join(
            json.dumps({"id": f"p{i}", "prompt": f"prompt-{i}"}) for i in range(2)
        )
    )

    for _ in range(2):
        httpx_mock.add_response(
            method="POST",
            content=b"data: [DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )

    with pytest.raises(RuntimeError, match="no TTFT samples collected"):
        run_latency_probe(probe, "https://llm.example.com", root=tmp_path)
