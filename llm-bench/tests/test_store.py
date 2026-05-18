import json
from pathlib import Path

import pytest

from bench.store import RunRecord, append_run, read_runs


def test_run_record_round_trip(tmp_path):
    runs_path = tmp_path / "runs.jsonl"
    rec = RunRecord(
        run_uuid="abc",
        started_at="2026-05-17T10:00:00Z",
        ended_at="2026-05-17T10:30:00Z",
        endpoint_url="http://goudai:8010/v1",
        model_id="qwen/qwen3.6-27b-mtp",
        runtime="llama.cpp",
        host="goudai",
        suite_id="tier1",
        quantization="bf16",
        ctx_length=65536,
        sampling_params={"temperature": 0.7, "top_p": 0.9, "top_k": 40, "max_tokens": 256},
        infra_git_sha="deadbeef",
        catalog_git_sha="cafebabe",
        notes="first run",
        status="ok",
        scores={"ttft_p95_ms": 320.0, "arc_challenge_acc": 0.42, "quality_avg": 0.55, "speed_score": 0.7},
        artifacts={"lm_eval_json": "/results/abc.json"},
    )
    append_run(runs_path, rec)
    append_run(runs_path, rec.model_copy(update={"run_uuid": "def"}))

    runs = read_runs(runs_path)
    assert [r.run_uuid for r in runs] == ["abc", "def"]
    assert runs[0].scores["ttft_p95_ms"] == 320.0


def test_read_runs_missing_file_returns_empty(tmp_path):
    assert read_runs(tmp_path / "nope.jsonl") == []
