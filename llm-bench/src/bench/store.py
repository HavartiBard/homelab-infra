from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    """One benchmark run, written as one JSON line."""
    run_uuid: str
    started_at: str   # ISO 8601 UTC
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
    notes: str | None = None
    status: str = "ok"   # "ok" or "failed"
    error: str | None = None
    scores: dict[str, float | None] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)


def append_run(runs_path: Path, record: RunRecord) -> None:
    runs_path = Path(runs_path)
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    with runs_path.open("a") as f:
        f.write(record.model_dump_json() + "\n")


def read_runs(runs_path: Path) -> list[RunRecord]:
    runs_path = Path(runs_path)
    if not runs_path.exists():
        return []
    return [
        RunRecord.model_validate_json(line)
        for line in runs_path.read_text().splitlines()
        if line.strip()
    ]
