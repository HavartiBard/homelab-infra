from __future__ import annotations

from pathlib import Path
from typing import Any

from ..store import read_runs


LEADERBOARD_COLUMNS = [
    "run_uuid", "model_id", "runtime", "host",
    "quality_avg", "speed_score",
    "ttft_p95_ms", "decode_tokens_per_sec",
    "vram_gb_peak", "started_at",
]


def runs_to_dataframe_rows(runs_path: Path) -> list[dict[str, Any]]:
    """Flatten RunRecord into one dict per row, selecting leaderboard columns."""
    rows: list[dict[str, Any]] = []
    for rec in read_runs(runs_path):
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
    import pandas as pd
    import os

    runs_path = Path(os.environ.get("LLM_BENCH_RUNS_PATH", "/data/runs.jsonl"))
    st.title("Leaderboard")
    rows = runs_to_dataframe_rows(runs_path)
    if not rows:
        st.info(f"No runs yet. Trigger a run from the orchestrator CLI. (Expected at {runs_path}.)")
        return
    df = pd.DataFrame(rows, columns=LEADERBOARD_COLUMNS)
    df = df.sort_values("quality_avg", ascending=False, na_position="last")
    st.dataframe(df, use_container_width=True, hide_index=True)
    selected = st.selectbox("Inspect a run", df["run_uuid"].tolist())
    if selected:
        st.session_state["selected_run"] = selected
        st.switch_page("Run detail")
