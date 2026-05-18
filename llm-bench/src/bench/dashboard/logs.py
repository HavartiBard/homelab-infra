"""Logs page — tails the active bench run log.

The orchestrator writes per-run output to ``LLM_BENCH_LOG_PATH`` (default
``/data/run.log``). This page shows the last N lines and offers manual or
auto-refresh.
"""

from __future__ import annotations

import os
import time
from pathlib import Path


DEFAULT_LOG_PATH = "/data/run.log"
DEFAULT_TAIL_LINES = 300


def read_log_tail(log_path: Path, n_lines: int) -> tuple[list[str], int]:
    """Return (last n_lines of log, total bytes) — empty list if file missing."""
    if not log_path.exists():
        return [], 0
    text = log_path.read_text(errors="replace")
    lines = text.splitlines()
    return lines[-n_lines:], len(text.encode("utf-8", errors="replace"))


def render():
    import streamlit as st

    log_path = Path(os.environ.get("LLM_BENCH_LOG_PATH", DEFAULT_LOG_PATH))
    st.title("Run log")
    st.caption(f"Tailing `{log_path}` — written by the active `bench run` process.")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        n_lines = st.number_input("Tail lines", min_value=50, max_value=5000,
                                  value=DEFAULT_TAIL_LINES, step=50)
    with col2:
        auto_refresh = st.toggle("Auto-refresh (5s)", value=False)
    with col3:
        if st.button("Refresh now", type="primary"):
            st.rerun()

    lines, total_bytes = read_log_tail(log_path, int(n_lines))

    if not lines:
        st.info(f"No log at `{log_path}`. Start a run with `docker exec llm-bench bench run …`.")
        if auto_refresh:
            time.sleep(5)
            st.rerun()
        return

    kb = total_bytes / 1024
    st.caption(f"showing last {len(lines)} of {total_bytes:,} bytes ({kb:,.1f} KiB) — newest at bottom")
    st.code("\n".join(lines), language="log")

    with st.expander("Download full log"):
        try:
            full_text = log_path.read_text(errors="replace")
            st.download_button(
                "Download run.log",
                data=full_text,
                file_name=log_path.name,
                mime="text/plain",
            )
        except OSError as exc:
            st.error(f"Could not read log: {exc}")

    if auto_refresh:
        time.sleep(5)
        st.rerun()
