from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ..db import get_connection
from ..store import read_runs


LEADERBOARD_COLUMNS = [
    "run_uuid", "model_id", "source", "runtime", "host",
    "quality_avg", "speed_score", "ttft_p95_ms",
    "decode_tokens_per_sec", "vram_gb_peak", "num_params_b",
    "started_at",
]


def has_reference_source(db: duckdb.DuckDBPyConnection, source: str) -> bool:
    """Return whether at least one reference row exists for the given source."""
    row = db.execute(
        "SELECT 1 FROM refs WHERE source = ? LIMIT 1",
        [source],
    ).fetchone()
    return row is not None


def query_leaderboard(
    db: duckdb.DuckDBPyConnection,
    *,
    show_local: bool = True,
    show_frontier: bool = False,
    show_open: bool = False,
    search: str = "",
    min_params: float | None = None,
    max_params: float | None = None,
) -> pd.DataFrame:
    """Query the leaderboard_v view with filters applied."""
    sources: list[str] = []
    if show_local:
        sources.append("'local'")
    if show_frontier:
        sources.append("'frontier_curated'")
    if show_open:
        sources.extend([
            "'hf_open_llm_v1'", "'hf_open_llm_v2'", "'bigcode_humaneval'",
        ])
    if not sources:
        return pd.DataFrame(columns=LEADERBOARD_COLUMNS)

    where = [f"source IN ({','.join(sources)})"]
    params: list = []
    if search:
        where.append("model_id ILIKE ?")
        params.append(f"%{search}%")
    if min_params is not None:
        where.append("(num_params_b IS NOT NULL AND num_params_b >= ?)")
        params.append(min_params)
    if max_params is not None:
        where.append("(num_params_b IS NOT NULL AND num_params_b <= ?)")
        params.append(max_params)

    sql = f"""
        SELECT {', '.join(LEADERBOARD_COLUMNS)}
        FROM leaderboard_v
        WHERE {' AND '.join(where)}
        ORDER BY quality_avg DESC NULLS LAST, started_at DESC
    """
    return db.execute(sql, params).df()


# Backward-compatible helper used by older tests / callers.
def runs_to_dataframe_rows(db: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Flatten RunRecord into one dict per row (legacy shape).

    Kept for the existing `test_dashboard.py` tests that haven't been migrated.
    New code should use `query_leaderboard()` directly.
    """
    rows: list[dict[str, Any]] = []
    for rec in read_runs(db):
        row: dict[str, Any] = {
            "run_uuid":   rec.run_uuid,
            "model_id":   rec.model_id,
            "runtime":    rec.runtime,
            "host":       rec.host,
            "started_at": rec.started_at,
        }
        for k in ("quality_avg", "speed_score", "ttft_p95_ms",
                  "decode_tokens_per_sec", "vram_gb_peak"):
            row[k] = rec.scores.get(k)
        rows.append(row)
    return rows


def render():
    """Streamlit page entrypoint — called from app.py via st.navigation."""
    import streamlit as st

    db_path = Path(os.environ.get("LLM_BENCH_DB_PATH", "/data/bench.duckdb"))
    db = get_connection(db_path)
    frontier_default = has_reference_source(db, "frontier_curated")
    st.title("Leaderboard")

    col1, col2, col3 = st.columns(3)
    show_local    = col1.checkbox("Local runs", value=True)
    show_frontier = col2.checkbox("Frontier (curated)", value=frontier_default)
    show_open     = col3.checkbox("Open weights (HF/BigCode)", value=False)

    search = st.text_input("Search model_id", value="")
    col_a, col_b = st.columns(2)
    min_p = col_a.number_input("Min params (B)", min_value=0.0, value=0.0,
                               help="Applies only to reference rows.")
    max_p = col_b.number_input("Max params (B)", min_value=0.0, value=0.0,
                               help="0 = no upper bound.")
    min_params = min_p if min_p > 0 else None
    max_params = max_p if max_p > 0 else None

    df = query_leaderboard(
        db,
        show_local=show_local,
        show_frontier=show_frontier,
        show_open=show_open,
        search=search,
        min_params=min_params,
        max_params=max_params,
    )
    if df.empty:
        st.info("No rows match the current filters.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)

    local_uuids = df.loc[df["source"] == "local", "run_uuid"].dropna().tolist()
    if local_uuids:
        selected = st.selectbox("Inspect a local run", local_uuids)
        if selected:
            st.session_state["selected_run"] = selected
            st.switch_page("Run detail")
