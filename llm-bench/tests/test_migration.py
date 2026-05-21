import json
from pathlib import Path

import pytest

from bench.db import get_connection
from bench.db.migrate import migrate_jsonl_to_duckdb, MigrationResult
from bench.store import read_runs


def _record(uuid: str, **overrides) -> dict:
    base = {
        "run_uuid": uuid,
        "started_at": "2026-05-17T10:00:00Z",
        "ended_at": "2026-05-17T10:30:00Z",
        "endpoint_url": "http://goudai:8010/v1",
        "model_id": "qwen/qwen3.6-27b-mtp",
        "runtime": "llama.cpp",
        "host": "goudai",
        "suite_id": "tier1",
        "scores": {"quality_avg": 0.55},
        "artifacts": {},
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _clear_cache():
    get_connection.cache_clear()
    yield
    get_connection.cache_clear()


def test_migration_imports_all_records(tmp_path):
    jsonl = tmp_path / "runs.jsonl"
    jsonl.write_text(
        json.dumps(_record("a")) + "\n" +
        json.dumps(_record("b", status="failed", error="boom")) + "\n" +
        json.dumps(_record("c", notes="… unicode")) + "\n"
    )
    db_path = tmp_path / "bench.duckdb"

    result = migrate_jsonl_to_duckdb(jsonl, db_path)

    assert result.migrated == 3
    assert result.skipped == 0
    db = get_connection(db_path)
    runs = read_runs(db)
    assert {r.run_uuid for r in runs} == {"a", "b", "c"}
    assert (tmp_path / "runs.jsonl.migrated").exists()
    assert not jsonl.exists()


def test_migration_is_idempotent(tmp_path):
    jsonl = tmp_path / "runs.jsonl"
    jsonl.write_text(json.dumps(_record("a")) + "\n")
    db_path = tmp_path / "bench.duckdb"

    first = migrate_jsonl_to_duckdb(jsonl, db_path)
    assert first.migrated == 1

    second = migrate_jsonl_to_duckdb(jsonl, db_path)
    assert second.migrated == 0
    assert second.already_done is True


def test_migration_skips_invalid_lines(tmp_path):
    jsonl = tmp_path / "runs.jsonl"
    jsonl.write_text(
        json.dumps(_record("a")) + "\n" +
        "{not-valid-json\n" +
        json.dumps(_record("c")) + "\n"
    )
    db_path = tmp_path / "bench.duckdb"

    result = migrate_jsonl_to_duckdb(jsonl, db_path)
    assert result.migrated == 2
    assert result.skipped == 1
