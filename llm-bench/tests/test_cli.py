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
    for sub in ("run", "validate", "list", "db", "references"):
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


def test_references_refresh_calls_importer(tmp_path, monkeypatch):
    """`bench references refresh --source frontier` invokes the importer."""
    from unittest.mock import patch
    from bench.references.importer import ImportReport

    monkeypatch.setenv("LLM_BENCH_DB_PATH", str(tmp_path / "bench.duckdb"))
    get_connection.cache_clear()

    runner = CliRunner()
    with patch("bench.references.importer.refresh") as mock_refresh:
        mock_refresh.return_value = ImportReport(
            ok_sources={"frontier_curated": 12},
            failed_sources={},
        )
        result = runner.invoke(cli, ["references", "refresh", "--source", "frontier"])

    assert result.exit_code == 0, result.output
    assert "frontier_curated" in result.output
    assert "12" in result.output
    # confirm only ONE fetcher was passed (the frontier one)
    mock_refresh.assert_called_once()
    _, kwargs = mock_refresh.call_args
    assert len(kwargs["fetchers"]) == 1
    get_connection.cache_clear()


def test_references_refresh_all_sources(tmp_path, monkeypatch):
    """`bench references refresh --source all` passes all 4 fetchers."""
    from unittest.mock import patch
    from bench.references.importer import ImportReport

    monkeypatch.setenv("LLM_BENCH_DB_PATH", str(tmp_path / "bench.duckdb"))
    get_connection.cache_clear()

    runner = CliRunner()
    with patch("bench.references.importer.refresh") as mock_refresh:
        mock_refresh.return_value = ImportReport()
        result = runner.invoke(cli, ["references", "refresh"])

    assert result.exit_code == 0, result.output
    mock_refresh.assert_called_once()
    _, kwargs = mock_refresh.call_args
    assert len(kwargs["fetchers"]) == 4
    get_connection.cache_clear()


def test_references_list_empty_db(tmp_path, monkeypatch):
    """`bench references list` against an empty DB renders headers and exits ok."""
    monkeypatch.setenv("LLM_BENCH_DB_PATH", str(tmp_path / "bench.duckdb"))
    get_connection.cache_clear()
    runner = CliRunner()
    result = runner.invoke(cli, ["references", "list"])
    assert result.exit_code == 0, result.output
    # Headers present, no row data
    assert "model_id" in result.output
    get_connection.cache_clear()


def test_references_show_no_match(tmp_path, monkeypatch):
    """`bench references show` for an unknown model_id prints a friendly message."""
    monkeypatch.setenv("LLM_BENCH_DB_PATH", str(tmp_path / "bench.duckdb"))
    get_connection.cache_clear()
    runner = CliRunner()
    result = runner.invoke(cli, ["references", "show", "nonexistent"])
    assert result.exit_code == 0, result.output
    assert "No references found" in result.output
    get_connection.cache_clear()
