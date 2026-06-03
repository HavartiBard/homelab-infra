import duckdb
import pytest
from bench.db import get_connection, apply_schema


def test_apply_schema_creates_runs_refs_tables_and_view():
    con = duckdb.connect(":memory:")
    apply_schema(con)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert {"runs", "refs"} <= tables
    views = {r[0] for r in con.execute(
        "SELECT view_name FROM duckdb_views() WHERE schema_name='main'"
    ).fetchall()}
    assert {"leaderboard_v", "merged_refs_v"} <= views


def test_get_connection_is_cached_per_path(tmp_path):
    p = tmp_path / "bench.duckdb"
    a = get_connection(p)
    b = get_connection(p)
    assert a is b
