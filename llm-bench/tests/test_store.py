import pytest

from bench.db import get_connection
from bench.store import RunRecord, append_run, read_runs


def _make_record(uuid: str = "abc") -> RunRecord:
    return RunRecord(
        run_uuid=uuid,
        started_at="2026-05-17T10:00:00Z",
        ended_at="2026-05-17T10:30:00Z",
        endpoint_url="http://goudai:8010/v1",
        model_id="qwen/qwen3.6-27b-mtp",
        runtime="llama.cpp",
        host="goudai",
        suite_id="tier1",
        quantization="bf16",
        ctx_length=65536,
        sampling_params={"temperature": 0.7, "top_p": 0.9},
        infra_git_sha="deadbeef",
        catalog_git_sha="cafebabe",
        notes="first run — unicode em-dash",
        status="ok",
        scores={"ttft_p95_ms": 320.0, "quality_avg": 0.55},
        artifacts={"lm_eval_json": "/results/abc.json"},
    )


@pytest.fixture
def db(tmp_path):
    get_connection.cache_clear()
    con = get_connection(tmp_path / "bench.duckdb")
    yield con
    get_connection.cache_clear()


def test_round_trip(db):
    rec = _make_record()
    append_run(db, rec)
    append_run(db, rec.model_copy(update={"run_uuid": "def"}))

    runs = read_runs(db)
    assert [r.run_uuid for r in runs] == ["abc", "def"]
    assert runs[0].notes == "first run — unicode em-dash"
    assert runs[0].scores["ttft_p95_ms"] == 320.0
    assert runs[0].sampling_params == {"temperature": 0.7, "top_p": 0.9}


def test_read_runs_empty(db):
    assert read_runs(db) == []


def test_mirror_jsonl_when_marker_present(db, tmp_path, monkeypatch):
    marker = tmp_path / ".mirror_jsonl_enabled"
    marker.touch()
    jsonl = tmp_path / "runs.jsonl"
    monkeypatch.setenv("LLM_BENCH_MIRROR_JSONL_PATH", str(jsonl))
    monkeypatch.setenv("LLM_BENCH_MIRROR_MARKER_PATH", str(marker))

    append_run(db, _make_record())
    assert jsonl.exists()
    assert "abc" in jsonl.read_text()


def test_no_mirror_when_marker_absent(db, tmp_path, monkeypatch):
    jsonl = tmp_path / "runs.jsonl"
    monkeypatch.setenv("LLM_BENCH_MIRROR_JSONL_PATH", str(jsonl))
    monkeypatch.setenv("LLM_BENCH_MIRROR_MARKER_PATH", str(tmp_path / ".absent"))

    append_run(db, _make_record())
    assert not jsonl.exists()
