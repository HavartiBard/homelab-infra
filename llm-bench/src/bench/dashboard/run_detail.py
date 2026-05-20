from __future__ import annotations

import os
from pathlib import Path

import duckdb

from ..db import get_connection
from ..store import read_runs


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
