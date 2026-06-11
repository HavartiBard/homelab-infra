"""Helpers shared between run-detail compare panel (#153) and /compare page (#154)."""
from __future__ import annotations

import json
from typing import Sequence

import duckdb
import pandas as pd


CAPABILITIES = [
    "arc_challenge_acc",
    "gsm8k_strict_match",
    "humaneval_pass1",
    "ifeval_strict_acc",
]


def _load_run_scores(db: duckdb.DuckDBPyConnection, run_uuid: str) -> dict[str, float | None]:
    row = db.execute(
        "SELECT scores FROM runs WHERE run_uuid = ?", [run_uuid],
    ).fetchone()
    if row is None:
        return {}
    return json.loads(row[0]) if row[0] else {}


def load_merged_ref(
    db: duckdb.DuckDBPyConnection, model_id: str,
) -> tuple[str, dict[str, float | None]]:
    """Return (display_name, scores_dict) for a model_id, using merged_refs_v."""
    row = db.execute("""
        SELECT display_name, arc_challenge_acc, gsm8k_strict_match,
               humaneval_pass1, ifeval_strict_acc
        FROM merged_refs_v WHERE model_id = ?
    """, [model_id]).fetchone()
    if row is None:
        return model_id, {c: None for c in CAPABILITIES}
    return row[0], {
        "arc_challenge_acc":  row[1],
        "gsm8k_strict_match": row[2],
        "humaneval_pass1":    row[3],
        "ifeval_strict_acc":  row[4],
    }


def quality_avg(scores: dict[str, float | None]) -> float | None:
    """Mean of non-null capability scores; None if fewer than 2 are present."""
    present = [scores[c] for c in CAPABILITIES if scores.get(c) is not None]
    if len(present) < 2:
        return None
    return sum(present) / len(present)


def build_scorecard(
    db: duckdb.DuckDBPyConnection,
    *,
    run_uuid: str,
    ref_model_ids: Sequence[str],
) -> pd.DataFrame:
    """Build a side-by-side scorecard: rows = capabilities, columns = run + each ref.

    The leftmost reference column (if any) drives a `Δ vs <display>` column.
    """
    run_scores = _load_run_scores(db, run_uuid)
    ref_columns: list[tuple[str, dict[str, float | None]]] = []
    for mid in ref_model_ids:
        display, scores = load_merged_ref(db, mid)
        ref_columns.append((display, scores))

    delta_target = ref_columns[0] if ref_columns else None

    rows: list[dict] = []
    for cap in CAPABILITIES + ["quality_avg"]:
        if cap == "quality_avg":
            run_val = run_scores.get("quality_avg")
            if run_val is None:
                run_val = quality_avg(run_scores)
        else:
            run_val = run_scores.get(cap)

        row: dict = {"capability": cap, "This run": run_val}
        for display, scores in ref_columns:
            row[display] = (
                quality_avg(scores) if cap == "quality_avg" else scores.get(cap)
            )
        if delta_target:
            display, scores = delta_target
            ref_val = (
                quality_avg(scores) if cap == "quality_avg" else scores.get(cap)
            )
            row[f"Δ vs {display}"] = (
                (run_val - ref_val)
                if (run_val is not None and ref_val is not None)
                else None
            )
        rows.append(row)
    return pd.DataFrame(rows)
