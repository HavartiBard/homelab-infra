from pathlib import Path

import pytest

from bench.db import get_connection
from bench.store import RunRecord, append_run
from bench.dashboard.leaderboard import (
    has_reference_source,
    query_leaderboard,
    runs_to_dataframe_rows,
)
from bench.dashboard.logs import read_log_tail


def _make_record(uuid: str, model: str, scores: dict) -> RunRecord:
    return RunRecord(
        run_uuid=uuid,
        started_at="2026-05-17T10:00:00Z",
        ended_at="2026-05-17T10:30:00Z",
        endpoint_url="http://goudai:8010/v1",
        model_id=model,
        runtime="llama.cpp",
        host="goudai",
        suite_id="tier1",
        scores=scores,
    )


def test_runs_to_dataframe_picks_leaderboard_columns(tmp_path):
    get_connection.cache_clear()
    db = get_connection(tmp_path / "bench.duckdb")
    append_run(db, _make_record("a", "qwen3.6-27b-mtp", {
        "ttft_p95_ms": 320, "decode_tokens_per_sec": 40,
        "quality_avg": 0.55, "speed_score": 0.7,
        "vram_gb_peak": 21.5,
    }))
    append_run(db, _make_record("b", "qwen3-coder-next", {
        "ttft_p95_ms": 500, "decode_tokens_per_sec": 25,
        "quality_avg": 0.61, "speed_score": 0.45,
        "vram_gb_peak": 18.1,
    }))
    rows = runs_to_dataframe_rows(db)
    assert len(rows) == 2
    keys = set(rows[0].keys())
    for required in ("run_uuid", "model_id", "runtime", "host",
                     "quality_avg", "speed_score",
                     "ttft_p95_ms", "decode_tokens_per_sec",
                     "vram_gb_peak", "started_at"):
        assert required in keys


def test_runs_to_dataframe_renders_null_as_none(tmp_path):
    get_connection.cache_clear()
    db = get_connection(tmp_path / "bench.duckdb")
    append_run(db, _make_record("a", "m", {"ttft_p95_ms": None}))
    rows = runs_to_dataframe_rows(db)
    assert rows[0]["ttft_p95_ms"] is None


def test_read_log_tail_missing_file_returns_empty(tmp_path):
    lines, total = read_log_tail(tmp_path / "nope.log", 10)
    assert lines == []
    assert total == 0


def test_read_log_tail_returns_last_n_lines(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("\n".join(f"line {i}" for i in range(100)) + "\n")
    lines, total = read_log_tail(log, 10)
    assert lines == [f"line {i}" for i in range(90, 100)]
    assert total > 0


def test_read_log_tail_n_larger_than_file_returns_all(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("a\nb\nc\n")
    lines, _ = read_log_tail(log, 1000)
    assert lines == ["a", "b", "c"]


from bench.dashboard.about import _refs_freshness_rows


def _seed_db(db, *, runs=0, frontier=0, hf=0):
    for i in range(runs):
        db.execute("""
            INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url,
                              model_id, runtime, suite_id, status, scores, artifacts)
            VALUES (?, '2026-05-19T10:00:00Z', '2026-05-19T10:30:00Z',
                    'http://x/v1', ?, 'llama.cpp', 'tier1', 'ok',
                    '{"quality_avg": 0.5}', '{}')
        """, [f"run-{i}", f"local/model-{i}"])
    for i in range(frontier):
        db.execute("""
            INSERT INTO refs (model_id, source, display_name,
                              num_params_b,
                              arc_challenge_acc, gsm8k_strict_match,
                              as_of, imported_at)
            VALUES (?, 'frontier_curated', ?, ?, 0.8, 0.8,
                    '2025-01-01', '2025-01-01T00:00:00')
        """, [f"anthropic/m-{i}", f"M{i}", float(10 + i)])
    for i in range(hf):
        db.execute("""
            INSERT INTO refs (model_id, source, display_name,
                              num_params_b,
                              arc_challenge_acc, gsm8k_strict_match,
                              as_of, imported_at)
            VALUES (?, 'hf_open_llm_v1', ?, ?, 0.7, 0.7,
                    '2024-06-26', '2024-06-26T00:00:00')
        """, [f"meta/m-{i}", f"M{i}", float(70 + i)])


@pytest.fixture(autouse=True)
def _clear_cache():
    get_connection.cache_clear()
    yield
    get_connection.cache_clear()


def test_filter_local_only(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    _seed_db(db, runs=2, frontier=1, hf=1)
    df = query_leaderboard(
        db, show_local=True, show_frontier=False, show_open=False,
    )
    assert set(df["source"]) == {"local"}
    assert len(df) == 2


def test_filter_all_sources(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    _seed_db(db, runs=1, frontier=2, hf=3)
    df = query_leaderboard(
        db, show_local=True, show_frontier=True, show_open=True,
    )
    assert len(df) == 6
    assert set(df["source"]) == {"local", "frontier_curated", "hf_open_llm_v1"}


def test_empty_filter_returns_empty_df(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    _seed_db(db, runs=2, frontier=2, hf=2)
    df = query_leaderboard(
        db, show_local=False, show_frontier=False, show_open=False,
    )
    assert df.empty


def test_has_reference_source_detects_frontier_rows(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    _seed_db(db, runs=0, frontier=1, hf=0)
    assert has_reference_source(db, "frontier_curated") is True
    assert has_reference_source(db, "hf_open_llm_v2") is False


def test_search_filters_by_model_id(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    _seed_db(db, runs=2, frontier=2, hf=0)
    df = query_leaderboard(
        db, show_local=True, show_frontier=True, show_open=False,
        search="anthropic",
    )
    # 2 frontier rows match, 0 local
    assert len(df) == 2
    assert all("anthropic" in m for m in df["model_id"])


def test_param_range_filters_only_refs(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    _seed_db(db, runs=2, frontier=3, hf=0)  # frontier params: 10, 11, 12
    df = query_leaderboard(
        db, show_local=True, show_frontier=True, show_open=False,
        min_params=11.0,
    )
    # local rows have NULL params and are filtered out by min_params guard
    # frontier rows: 11.0 and 12.0 pass; 10.0 fails
    assert len(df) == 2
    assert all(p >= 11.0 for p in df["num_params_b"])


import pandas as pd
from bench.dashboard.compare_helpers import build_scorecard


def test_build_scorecard_with_one_ref(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
        INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url,
                          model_id, runtime, suite_id, status, scores, artifacts)
        VALUES ('R1', '2026-05-19T10:00:00Z', '2026-05-19T10:30:00Z',
                'http://x/v1', 'qwen/test', 'llama.cpp', 'tier1', 'ok',
                '{"arc_challenge_acc":0.82,"gsm8k_strict_match":0.69,"humaneval_pass1":0.55,"ifeval_strict_acc":0.67,"quality_avg":0.68}',
                '{}')
    """)
    db.execute("""
        INSERT INTO refs (model_id, source, display_name,
                          arc_challenge_acc, gsm8k_strict_match,
                          humaneval_pass1, ifeval_strict_acc,
                          as_of, imported_at)
        VALUES ('meta-llama/Llama-3.1-8B-Instruct', 'frontier_curated',
                'Llama 3.1 8B Instruct', 0.812, 0.846, 0.728, 0.789,
                '2024-07-23', '2024-07-23T00:00:00')
    """)

    df = build_scorecard(
        db, run_uuid="R1",
        ref_model_ids=["meta-llama/Llama-3.1-8B-Instruct"],
    )
    assert list(df["capability"]) == [
        "arc_challenge_acc", "gsm8k_strict_match",
        "humaneval_pass1", "ifeval_strict_acc", "quality_avg",
    ]
    # delta vs Llama on humaneval: 0.55 - 0.728 = -0.178
    delta_he = df.loc[df["capability"] == "humaneval_pass1",
                      "Δ vs Llama 3.1 8B Instruct"].iloc[0]
    assert abs(delta_he - (-0.178)) < 1e-3


def test_build_scorecard_handles_missing_ref_metric(tmp_path):
    """If the reference is missing a metric, the delta cell renders as None/NaN."""
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
        INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url,
                          model_id, runtime, suite_id, status, scores, artifacts)
        VALUES ('R2', '2026-05-19T10:00:00Z', '2026-05-19T10:30:00Z',
                'http://x/v1', 'm', 'r', 'tier1', 'ok',
                '{"arc_challenge_acc":0.8}', '{}')
    """)
    db.execute("""
        INSERT INTO refs (model_id, source, display_name,
                          arc_challenge_acc, gsm8k_strict_match,
                          as_of, imported_at)
        VALUES ('ref/x', 'frontier_curated', 'ref x', 0.7, 0.7,
                '2025-01-01', '2025-01-01T00:00:00')
    """)
    df = build_scorecard(db, run_uuid="R2", ref_model_ids=["ref/x"])
    # ref/x has no humaneval — the ref column should be None
    he_ref = df.loc[df["capability"] == "humaneval_pass1", "ref x"].iloc[0]
    assert he_ref is None or (isinstance(he_ref, float) and pd.isna(he_ref))


def test_build_scorecard_no_refs_just_renders_run(tmp_path):
    """With zero refs, the scorecard still shows the 'This run' column."""
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
        INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url,
                          model_id, runtime, suite_id, status, scores, artifacts)
        VALUES ('R3', '2026-05-19T10:00:00Z', '2026-05-19T10:30:00Z',
                'http://x/v1', 'm', 'r', 'tier1', 'ok',
                '{"arc_challenge_acc":0.9,"gsm8k_strict_match":0.85}', '{}')
    """)
    df = build_scorecard(db, run_uuid="R3", ref_model_ids=[])
    assert "This run" in df.columns
    assert len(df) == 5  # 4 caps + quality_avg


def test_refs_freshness_rows_empty(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    rows = _refs_freshness_rows(db)
    assert rows == []


def test_refs_freshness_rows_groups_by_source(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
        INSERT INTO refs (model_id, source, display_name, arc_challenge_acc,
                          as_of, imported_at)
        VALUES ('a/b', 'frontier_curated', 'a b', 0.8,
                '2025-01-01', '2025-01-01T00:00:00')
    """)
    db.execute("""
        INSERT INTO refs (model_id, source, display_name, arc_challenge_acc,
                          as_of, imported_at)
        VALUES ('c/d', 'frontier_curated', 'c d', 0.7,
                '2025-01-01', '2025-01-02T00:00:00')
    """)
    db.execute("""
        INSERT INTO refs (model_id, source, display_name, ifeval_strict_acc,
                          as_of, imported_at)
        VALUES ('e/f', 'hf_open_llm_v2', 'e f', 0.6,
                '2025-01-01', '2025-01-03T00:00:00')
    """)
    rows = _refs_freshness_rows(db)
    # ORDER BY source — frontier_curated < hf_open_llm_v2 alphabetically
    assert len(rows) == 2
    frontier = next(r for r in rows if r["source"] == "frontier_curated")
    assert frontier["row_count"] == 2
    # last_refresh should be the MAX imported_at within the source
    assert "2025-01-02" in str(frontier["last_refresh"])


from bench.dashboard.compare import build_multi_scorecard


def test_multi_scorecard_n_runs_n_refs(tmp_path):
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
      INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url, model_id,
                        runtime, suite_id, status, scores, artifacts)
      VALUES ('R1', '2026-05-19T10:00:00Z', '2026-05-19T10:30:00Z', 'http://x/v1',
              'qwen/27b', 'llama.cpp', 'tier1', 'ok',
              '{"arc_challenge_acc":0.82,"gsm8k_strict_match":0.69}', '{}')
    """)
    db.execute("""
      INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url, model_id,
                        runtime, suite_id, status, scores, artifacts)
      VALUES ('R2', '2026-05-19T11:00:00Z', '2026-05-19T11:30:00Z', 'http://x/v1',
              'gemma/27b', 'llama.cpp', 'tier1', 'ok',
              '{"arc_challenge_acc":0.71,"gsm8k_strict_match":0.75}', '{}')
    """)
    db.execute("""
      INSERT INTO refs (model_id, source, display_name, arc_challenge_acc,
                        gsm8k_strict_match, as_of, imported_at)
      VALUES ('anthropic/claude-sonnet-4', 'frontier_curated', 'Claude Sonnet 4',
              0.949, 0.965, '2025-05-22', '2025-05-22T00:00:00')
    """)
    df = build_multi_scorecard(
        db, run_uuids=["R1", "R2"],
        ref_model_ids=["anthropic/claude-sonnet-4"],
    )
    assert "qwen/27b @ R1" in df.columns
    assert "gemma/27b @ R2" in df.columns
    assert "Claude Sonnet 4" in df.columns
    assert list(df["capability"]) == [
        "arc_challenge_acc", "gsm8k_strict_match",
        "humaneval_pass1", "ifeval_strict_acc", "quality_avg",
    ]


def test_multi_scorecard_runs_only(tmp_path):
    """No refs is a valid state — just N run columns."""
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
      INSERT INTO runs (run_uuid, started_at, ended_at, endpoint_url, model_id,
                        runtime, suite_id, status, scores, artifacts)
      VALUES ('R1', '2026-05-19T10:00:00Z', '2026-05-19T10:30:00Z', 'http://x/v1',
              'qwen/27b', 'llama.cpp', 'tier1', 'ok',
              '{"arc_challenge_acc":0.82}', '{}')
    """)
    df = build_multi_scorecard(db, run_uuids=["R1"], ref_model_ids=[])
    assert "qwen/27b @ R1" in df.columns
    assert len(df) == 5  # 4 caps + quality_avg


def test_multi_scorecard_refs_only(tmp_path):
    """No runs is a valid state — just N ref columns."""
    db = get_connection(tmp_path / "bench.duckdb")
    db.execute("""
      INSERT INTO refs (model_id, source, display_name, arc_challenge_acc,
                        gsm8k_strict_match, as_of, imported_at)
      VALUES ('anthropic/claude-sonnet-4', 'frontier_curated', 'Claude Sonnet 4',
              0.949, 0.965, '2025-05-22', '2025-05-22T00:00:00')
    """)
    df = build_multi_scorecard(db, run_uuids=[], ref_model_ids=["anthropic/claude-sonnet-4"])
    assert "Claude Sonnet 4" in df.columns
    assert "capability" in df.columns
