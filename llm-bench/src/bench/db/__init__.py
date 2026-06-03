"""DuckDB connection + schema helpers."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb

_SCHEMA = Path(__file__).parent / "schema.sql"


def apply_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Apply (idempotent) schema DDL to ``con``."""
    con.execute(_SCHEMA.read_text())


@lru_cache(maxsize=8)
def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Open (or reuse) a DuckDB connection at ``db_path`` with schema applied."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    apply_schema(con)
    return con
