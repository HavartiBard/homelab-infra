from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    run_uuid: str
    started_at: str
    ended_at: str
    endpoint_url: str
    model_id: str
    runtime: str
    host: str | None = None
    suite_id: str
    quantization: str | None = None
    ctx_length: int | None = None
    sampling_params: dict[str, Any] = Field(default_factory=dict)
    infra_git_sha: str | None = None
    catalog_git_sha: str | None = None
    warm_time_sec: float | None = None
    notes: str | None = None
    status: str = "ok"
    error: str | None = None
    scores: dict[str, float | None] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)


_INSERT_SQL = """
INSERT OR REPLACE INTO runs (
  run_uuid, started_at, ended_at, endpoint_url, model_id, runtime, host,
  suite_id, quantization, ctx_length, sampling_params, infra_git_sha,
  catalog_git_sha, warm_time_sec, notes, status, error, scores, artifacts, source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local')
"""


def _maybe_mirror_jsonl(record: RunRecord) -> None:
    marker = Path(os.environ.get(
        "LLM_BENCH_MIRROR_MARKER_PATH", "/data/.mirror_jsonl_enabled"
    ))
    if not marker.exists():
        return
    jsonl = Path(os.environ.get(
        "LLM_BENCH_MIRROR_JSONL_PATH", "/data/runs.jsonl"
    ))
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with jsonl.open("a") as f:
        f.write(record.model_dump_json() + "\n")


def append_run(db: duckdb.DuckDBPyConnection, record: RunRecord) -> None:
    db.execute(_INSERT_SQL, [
        record.run_uuid,
        record.started_at,
        record.ended_at,
        record.endpoint_url,
        record.model_id,
        record.runtime,
        record.host,
        record.suite_id,
        record.quantization,
        record.ctx_length,
        json.dumps(record.sampling_params),
        record.infra_git_sha,
        record.catalog_git_sha,
        record.warm_time_sec,
        record.notes,
        record.status,
        record.error,
        json.dumps(record.scores),
        json.dumps(record.artifacts),
    ])
    _maybe_mirror_jsonl(record)


def read_runs(db: duckdb.DuckDBPyConnection) -> list[RunRecord]:
    rows = db.execute("""
        SELECT run_uuid, started_at, ended_at, endpoint_url, model_id, runtime,
               host, suite_id, quantization, ctx_length, sampling_params,
               infra_git_sha, catalog_git_sha, warm_time_sec, notes, status,
               error, scores, artifacts
        FROM runs
        ORDER BY started_at ASC
    """).fetchall()
    out: list[RunRecord] = []
    for r in rows:
        out.append(RunRecord(
            run_uuid=r[0],
            started_at=r[1].isoformat() if isinstance(r[1], datetime) else r[1],
            ended_at=r[2].isoformat() if isinstance(r[2], datetime) else r[2],
            endpoint_url=r[3], model_id=r[4], runtime=r[5], host=r[6],
            suite_id=r[7], quantization=r[8], ctx_length=r[9],
            sampling_params=json.loads(r[10]) if r[10] else {},
            infra_git_sha=r[11], catalog_git_sha=r[12], warm_time_sec=r[13],
            notes=r[14], status=r[15], error=r[16],
            scores=json.loads(r[17]) if r[17] else {},
            artifacts=json.loads(r[18]) if r[18] else {},
        ))
    return out
