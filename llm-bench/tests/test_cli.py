import json
from click.testing import CliRunner
from bench.cli import cli
from bench.db import get_connection


def test_cli_shows_version():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "bench, version" in result.output


def test_cli_lists_subcommands():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for sub in ("run", "validate", "list", "db"):
        assert sub in result.output


def test_db_migrate_command(tmp_path, monkeypatch):
    """End-to-end smoke: migrate a small JSONL via the CLI."""
    get_connection.cache_clear()
    jsonl = tmp_path / "runs.jsonl"
    rec = {
        "run_uuid": "abc",
        "started_at": "2026-05-17T10:00:00Z",
        "ended_at": "2026-05-17T10:30:00Z",
        "endpoint_url": "http://x/v1",
        "model_id": "m",
        "runtime": "r",
        "suite_id": "tier1",
        "scores": {},
        "artifacts": {},
    }
    jsonl.write_text(json.dumps(rec) + "\n")
    db_path = tmp_path / "bench.duckdb"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "db", "migrate",
        "--jsonl-path", str(jsonl),
        "--db-path", str(db_path),
    ])
    assert result.exit_code == 0, result.output
    assert "migrated 1 runs" in result.output
    assert (tmp_path / "runs.jsonl.migrated").exists()
    get_connection.cache_clear()
