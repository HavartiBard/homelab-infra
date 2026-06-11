"""About page — explains aggregates and shows reference-source freshness."""
from __future__ import annotations

import os
from pathlib import Path

import duckdb


def _refs_freshness_rows(db: duckdb.DuckDBPyConnection) -> list[dict]:
    """Return per-source (source, last_refresh, row_count) summary rows."""
    fetched = db.execute("""
        SELECT source, MAX(imported_at) AS last_refresh, COUNT(*) AS row_count
        FROM refs
        GROUP BY source
        ORDER BY source
    """).fetchall()
    return [
        {"source": r[0], "last_refresh": r[1], "row_count": r[2]}
        for r in fetched
    ]


def render():
    import streamlit as st
    import pandas as pd
    from ..db import get_connection

    st.title("About llm-bench")
    db = get_connection(Path(os.environ.get("LLM_BENCH_DB_PATH", "/data/bench.duckdb")))

    st.markdown(
        """
        Local benchmark runs and published reference scores are stored together
        in `/data/bench.duckdb`. Reference data is refreshed via:

        ```
        bench references refresh --source all
        ```

        ### Aggregates

        - **`quality_avg`** — mean of `arc_challenge_acc`, `gsm8k_strict_match`,
          `humaneval_pass1`, `ifeval_strict_acc`. For reference rows, at least
          **2 non-null scores** are required to compute the average.
        - **`speed_score`** — `0.5 × cliff_inverse(ttft_p95_ms, 5000)` +
          `0.5 × cliff_normalize(decode_tokens_per_sec, 100)`. Computed only
          for local runs.

        ### Reference sources

        Each source is refreshed independently. The `source` column on the
        leaderboard tags rows so you can tell where each score came from.
        Note that the HF v1 archive is frozen (cutoff 2024-06-26) and will
        never change — only HF v2 and BigCode produce new data on refresh.

        - `frontier_curated` — hand-curated frontier + open-weights scores
          (`benchmarks/references/frontier.yml`)
        - `hf_open_llm_v1` — ARC + GSM8K from the archived HuggingFace
          Open LLM Leaderboard v1
        - `hf_open_llm_v2` — IFEval from current HF Open LLM Leaderboard v2
          (Maintainer's Choice only)
        - `bigcode_humaneval` — HumanEval pass@1 from BigCode leaderboard
        """
    )

    st.subheader("Source freshness")
    freshness = _refs_freshness_rows(db)
    if not freshness:
        st.info(
            "No references loaded yet. Run "
            "`bench references refresh --source all` to populate."
        )
        return
    df = pd.DataFrame(freshness, columns=["source", "last_refresh", "row_count"])
    st.dataframe(df, use_container_width=True, hide_index=True)
