from pathlib import Path

import pytest

from bench.db import get_connection
from bench.store import RunRecord, append_run
from bench.dashboard.leaderboard import runs_to_dataframe_rows
from bench.dashboard.logs import read_log_tail


def _make_record(uuid: str, model: str, scores: dict) -> RunRecord:
    return RunRecord(
        run_uuid=uuid,
        started_at="2026-05-17T10:00:00Z",
        ended_at="2026-05-17T10:30:00Z",
        endpoint_url="http://goudai:8010/v1",
        model_id=model,
        runtime="llama.cpp",
        host="goudai",
        suite_id="tier1",
        scores=scores,
    )


def test_runs_to_dataframe_picks_leaderboard_columns(tmp_path):
    get_connection.cache_clear()
    db = get_connection(tmp_path / "bench.duckdb")
    append_run(db, _make_record("a", "qwen3.6-27b-mtp", {
        "ttft_p95_ms": 320, "decode_tokens_per_sec": 40,
        "quality_avg": 0.55, "speed_score": 0.7,
        "vram_gb_peak": 21.5,
    }))
    append_run(db, _make_record("b", "qwen3-coder-next", {
        "ttft_p95_ms": 500, "decode_tokens_per_sec": 25,
        "quality_avg": 0.61, "speed_score": 0.45,
        "vram_gb_peak": 18.1,
    }))
    rows = runs_to_dataframe_rows(db)
    assert len(rows) == 2
    keys = set(rows[0].keys())
    for required in ("run_uuid", "model_id", "runtime", "host",
                     "quality_avg", "speed_score",
                     "ttft_p95_ms", "decode_tokens_per_sec",
                     "vram_gb_peak", "started_at"):
        assert required in keys


def test_runs_to_dataframe_renders_null_as_none(tmp_path):
    get_connection.cache_clear()
    db = get_connection(tmp_path / "bench.duckdb")
    append_run(db, _make_record("a", "m", {"ttft_p95_ms": None}))
    rows = runs_to_dataframe_rows(db)
    assert rows[0]["ttft_p95_ms"] is None


def test_read_log_tail_missing_file_returns_empty(tmp_path):
    lines, total = read_log_tail(tmp_path / "nope.log", 10)
    assert lines == []
    assert total == 0


def test_read_log_tail_returns_last_n_lines(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("\n".join(f"line {i}" for i in range(100)) + "\n")
    lines, total = read_log_tail(log, 10)
    assert lines == [f"line {i}" for i in range(90, 100)]
    assert total > 0


def test_read_log_tail_n_larger_than_file_returns_all(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("a\nb\nc\n")
    lines, _ = read_log_tail(log, 1000)
    assert lines == ["a", "b", "c"]
