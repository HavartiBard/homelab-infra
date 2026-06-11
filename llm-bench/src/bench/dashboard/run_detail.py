from __future__ import annotations

import os
from pathlib import Path

import duckdb

from ..db import get_connection
from ..store import read_runs
from .compare_helpers import build_scorecard


def render():
    import streamlit as st

    db = get_connection(Path(os.environ.get("LLM_BENCH_DB_PATH", "/data/bench.duckdb")))
    runs = {r.run_uuid: r for r in read_runs(db)}
    uuid = st.session_state.get("selected_run") or next(iter(runs), None)

    if not uuid or uuid not in runs:
        st.warning("No run selected.")
        return
    rec = runs[uuid]

    st.title(f"Run {uuid}")
    st.caption(f"{rec.started_at} → {rec.ended_at} • {rec.status}")
    st.subheader("Target")
    st.json({
        "endpoint_url": rec.endpoint_url,
        "model_id": rec.model_id,
        "runtime": rec.runtime,
        "host": rec.host,
        "quantization": rec.quantization,
        "ctx_length": rec.ctx_length,
        "sampling_params": rec.sampling_params,
    })
    st.subheader("Scores")
    st.json(rec.scores)
    if rec.artifacts:
        st.subheader("Artifacts")
        for k, v in rec.artifacts.items():
            st.code(f"{k}: {v}")
    if rec.notes:
        st.subheader("Notes")
        st.write(rec.notes)

    st.subheader("Compare against references")
    refs = db.execute(
        "SELECT model_id, display_name FROM merged_refs_v ORDER BY display_name"
    ).fetchall()
    if not refs:
        st.info("No references loaded yet. Run `bench references refresh --source all`.")
        return
    options = {f"{name} ({mid})": mid for mid, name in refs}
    selected = st.multiselect(
        "Add reference models",
        options=list(options.keys()),
    )
    if selected:
        ref_ids = [options[s] for s in selected]
        df = build_scorecard(db, run_uuid=uuid, ref_model_ids=ref_ids)
        st.dataframe(df, use_container_width=True, hide_index=True)
