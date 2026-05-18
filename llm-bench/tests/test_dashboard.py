from pathlib import Path

import pytest

from bench.store import RunRecord, append_run
from bench.dashboard.leaderboard import runs_to_dataframe_rows


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
    runs_path = tmp_path / "runs.jsonl"
    append_run(runs_path, _make_record("a", "qwen3.6-27b-mtp", {
        "ttft_p95_ms": 320, "decode_tokens_per_sec": 40,
        "quality_avg": 0.55, "speed_score": 0.7,
        "vram_gb_peak": 21.5,
    }))
    append_run(runs_path, _make_record("b", "qwen3-coder-next", {
        "ttft_p95_ms": 500, "decode_tokens_per_sec": 25,
        "quality_avg": 0.61, "speed_score": 0.45,
        "vram_gb_peak": 18.1,
    }))
    rows = runs_to_dataframe_rows(runs_path)
    assert len(rows) == 2
    keys = set(rows[0].keys())
    for required in ("run_uuid", "model_id", "runtime", "host",
                     "quality_avg", "speed_score",
                     "ttft_p95_ms", "decode_tokens_per_sec",
                     "vram_gb_peak", "started_at"):
        assert required in keys


def test_runs_to_dataframe_renders_null_as_none(tmp_path):
    runs_path = tmp_path / "runs.jsonl"
    append_run(runs_path, _make_record("a", "m", {"ttft_p95_ms": None}))
    rows = runs_to_dataframe_rows(runs_path)
    assert rows[0]["ttft_p95_ms"] is None
