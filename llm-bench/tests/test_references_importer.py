from datetime import date
from unittest.mock import MagicMock

import pytest

from bench.db import get_connection
from bench.references.importer import ImportReport, refresh
from bench.references.model import ReferenceRecord


def _rec(model_id: str, source: str) -> ReferenceRecord:
    return ReferenceRecord(
        model_id=model_id,
        source=source,
        display_name=model_id,
        scores={"arc_challenge_acc": 0.5, "gsm8k_strict_match": 0.7},
        as_of=date(2025, 1, 1),
    )


@pytest.fixture(autouse=True)
def _clear():
    get_connection.cache_clear()
    yield
    get_connection.cache_clear()


def test_refresh_inserts_records(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    f1 = MagicMock()
    f1.name = "frontier_curated"
    f1.fetch.return_value = [
        _rec("a/b", "frontier_curated"),
        _rec("c/d", "frontier_curated"),
    ]

    report = refresh(db, fetchers=[f1])
    assert isinstance(report, ImportReport)
    assert report.ok_sources == {"frontier_curated": 2}
    assert report.failed_sources == {}
    rows = db.execute(
        "SELECT model_id, source FROM refs ORDER BY model_id"
    ).fetchall()
    assert rows == [("a/b", "frontier_curated"), ("c/d", "frontier_curated")]


def test_refresh_continues_when_one_fetcher_fails(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    f1 = MagicMock()
    f1.name = "frontier_curated"
    f1.fetch.return_value = [_rec("a/b", "frontier_curated")]
    f2 = MagicMock()
    f2.name = "bigcode_humaneval"
    f2.fetch.side_effect = RuntimeError("network down")

    report = refresh(db, fetchers=[f1, f2])
    assert report.ok_sources == {"frontier_curated": 1}
    assert "bigcode_humaneval" in report.failed_sources
    assert "network down" in report.failed_sources["bigcode_humaneval"]
    rows = db.execute("SELECT model_id FROM refs").fetchall()
    assert rows == [("a/b",)]


def test_refresh_replaces_existing_rows_for_same_source(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    f1 = MagicMock()
    f1.name = "frontier_curated"
    f1.fetch.return_value = [
        _rec("a/b", "frontier_curated"),
        _rec("c/d", "frontier_curated"),
    ]
    refresh(db, fetchers=[f1])

    # Re-run with fewer records — the orphan should be removed
    f1.fetch.return_value = [_rec("a/b", "frontier_curated")]
    refresh(db, fetchers=[f1])

    rows = db.execute(
        "SELECT model_id FROM refs ORDER BY model_id"
    ).fetchall()
    assert rows == [("a/b",)]


def test_refresh_rejects_mismatched_source(tmp_path):
    """Fetcher claiming name X but yielding records with source=Y is a bug."""
    db = get_connection(tmp_path / "bench.duckdb")
    f1 = MagicMock()
    f1.name = "frontier_curated"
    f1.fetch.return_value = [_rec("a/b", "hf_open_llm_v1")]  # wrong source

    report = refresh(db, fetchers=[f1])
    assert "frontier_curated" in report.failed_sources
    rows = db.execute("SELECT model_id FROM refs").fetchall()
    assert rows == []  # transaction rolled back
