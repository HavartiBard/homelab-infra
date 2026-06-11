from pathlib import Path

import pytest

from bench.references.model import ReferenceRecord
from bench.references.sources.frontier import FrontierFetcher

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTIER_YAML = REPO_ROOT / "benchmarks" / "references" / "frontier.yml"


def test_frontier_yaml_loads_to_records():
    fetcher = FrontierFetcher(FRONTIER_YAML)
    records = list(fetcher.fetch())
    assert len(records) >= 10
    assert all(isinstance(r, ReferenceRecord) for r in records)
    assert all(r.source == "frontier_curated" for r in records)


def test_frontier_yaml_has_known_models():
    fetcher = FrontierFetcher(FRONTIER_YAML)
    model_ids = {r.model_id for r in fetcher.fetch()}
    assert "anthropic/claude-sonnet-4" in model_ids
    assert "meta-llama/Llama-3.1-8B-Instruct" in model_ids


def test_frontier_fetcher_rejects_bad_score_id(tmp_path):
    bad = tmp_path / "frontier.yml"
    bad.write_text(
        "references:\n"
        "  - model_id: x/y\n"
        "    display_name: X\n"
        "    scores: {mmlu_pro: 0.5}\n"
        "    as_of: 2025-01-01\n"
    )
    fetcher = FrontierFetcher(bad)
    with pytest.raises(ValueError, match="unknown score ids"):
        list(fetcher.fetch())
