"""Compare page — ad-hoc N runs × N references scorecard."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

import duckdb
import pandas as pd

from .compare_helpers import CAPABILITIES, load_merged_ref, quality_avg


def _load_run(
    db: duckdb.DuckDBPyConnection, run_uuid: str,
) -> tuple[str, dict[str, float | None]]:
    row = db.execute(
        "SELECT model_id, scores FROM runs WHERE run_uuid = ?", [run_uuid],
    ).fetchone()
    if row is None:
        return run_uuid, {}
    return row[0], json.loads(row[1]) if row[1] else {}


def build_multi_scorecard(
    db: duckdb.DuckDBPyConnection,
    *,
    run_uuids: Sequence[str],
    ref_model_ids: Sequence[str],
) -> pd.DataFrame:
    """Build an N runs × N refs scorecard.

    Rows: 4 capabilities + quality_avg.
    Columns: 'capability' + one column per run + one column per ref.
    No anchor / no delta column — that's the run-detail panel's job.
    """
    run_cols: list[tuple[str, dict[str, float | None]]] = []
    for uuid in run_uuids:
        model_id, scores = _load_run(db, uuid)
        run_cols.append((f"{model_id} @ {uuid}", scores))

    ref_cols: list[tuple[str, dict[str, float | None]]] = []
    for mid in ref_model_ids:
        display, scores = load_merged_ref(db, mid)
        ref_cols.append((display, scores))

    rows: list[dict] = []
    for cap in CAPABILITIES + ["quality_avg"]:
        row: dict = {"capability": cap}
        for label, scores in run_cols + ref_cols:
            if cap == "quality_avg":
                # Prefer stored quality_avg if present; otherwise compute.
                stored = scores.get("quality_avg")
                row[label] = stored if stored is not None else quality_avg(scores)
            else:
                row[label] = scores.get(cap)
        rows.append(row)
    return pd.DataFrame(rows)


def render():
    """Streamlit page entrypoint."""
    import streamlit as st
    from ..db import get_connection

    db = get_connection(Path(os.environ.get("LLM_BENCH_DB_PATH", "/data/bench.duckdb")))
    st.title("Compare")
    st.caption("Pick any combination of local runs and reference models for a side-by-side scorecard.")

    run_rows = db.execute(
        "SELECT run_uuid, model_id, started_at FROM runs ORDER BY started_at DESC"
    ).fetchall()
    run_options = {
        f"{r[1]} @ {r[2]} ({r[0][:8]})": r[0] for r in run_rows
    }
    selected_runs = st.multiselect("Runs", options=list(run_options.keys()))

    ref_rows = db.execute(
        "SELECT model_id, display_name FROM merged_refs_v ORDER BY display_name"
    ).fetchall()
    ref_options = {f"{name} ({mid})": mid for mid, name in ref_rows}
    selected_refs = st.multiselect("References", options=list(ref_options.keys()))

    if not (selected_runs or selected_refs):
        st.info("Select at least one run or reference.")
        return

    df = build_multi_scorecard(
        db,
        run_uuids=[run_options[s] for s in selected_runs],
        ref_model_ids=[ref_options[s] for s in selected_refs],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
