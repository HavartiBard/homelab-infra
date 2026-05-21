from datetime import date
from unittest.mock import patch

import pytest

from bench.references.model import ReferenceRecord
from bench.references.sources.hf_v1 import HFOpenLLMV1Fetcher
from bench.references.sources.hf_v2 import HFOpenLLMV2Fetcher
from bench.references.sources.bigcode import BigCodeHumanEvalFetcher


SAMPLE_V1_ROWS = [
    {
        "config_general": {"model_name": "meta-llama/Llama-3.1-8B-Instruct"},
        "results": {
            "harness|arc:challenge|25": {"acc": 0.812},
            "harness|gsm8k|5": {"acc": 0.846},
        },
    },
    {
        "config_general": {"model_name": "deleted-org/missing"},
        "results": {
            "harness|arc:challenge|25": {"acc": 0.5},
            "harness|gsm8k|5": None,
        },
    },
]


def test_hf_v1_fetcher_normalizes_rows():
    with patch("bench.references.sources.hf_v1.load_dataset",
               side_effect=lambda _id, **kw: iter(SAMPLE_V1_ROWS)):
        records = list(HFOpenLLMV1Fetcher().fetch())

    assert len(records) == 2
    r0 = next(r for r in records if r.model_id == "meta-llama/Llama-3.1-8B-Instruct")
    assert r0.source == "hf_open_llm_v1"
    assert r0.scores["arc_challenge_acc"] == pytest.approx(0.812)
    assert r0.scores["gsm8k_strict_match"] == pytest.approx(0.846)
    assert r0.num_params_b is None  # HF V1 dataset doesn't expose params
    assert r0.as_of == date(2024, 6, 26)  # HF v1 archive cutoff


def test_hf_v1_fetcher_skips_rows_with_null_model():
    bad = [{"config_general": {"model_name": None}, "results": {}}]
    with patch("bench.references.sources.hf_v1.load_dataset",
               side_effect=lambda _id, **kw: iter(bad)):
        records = list(HFOpenLLMV1Fetcher().fetch())
    assert records == []


def test_hf_v1_fetcher_skips_rows_with_all_null_scores():
    bad = [{"config_general": {"model_name": "x/y"}, "results": {}}]
    with patch("bench.references.sources.hf_v1.load_dataset",
               side_effect=lambda _id, **kw: iter(bad)):
        records = list(HFOpenLLMV1Fetcher().fetch())
    assert records == []


SAMPLE_V2_ROWS = [
    {
        "fullname": "Qwen/Qwen2.5-72B-Instruct",
        "IFEval": 86.6,
        "#Params (B)": 72.0,
        "Hub License": "qwen",
    },
    {
        "fullname": "shady/merge-frankenstein",
        "IFEval": 99.9,
        "#Params (B)": 13.0,
        "Hub License": "other",
    },
]


def test_hf_v2_fetcher_returns_all_rows_with_ifeval():
    with patch("bench.references.sources.hf_v2.load_dataset",
               side_effect=lambda _id, **kw: {"train": iter(SAMPLE_V2_ROWS)}):
        records = list(HFOpenLLMV2Fetcher().fetch())
    assert len(records) == 2
    r0 = next(r for r in records if r.model_id == "Qwen/Qwen2.5-72B-Instruct")
    assert r0.scores == {"ifeval_strict_acc": pytest.approx(0.866)}
    assert r0.source == "hf_open_llm_v2"
    r1 = next(r for r in records if r.model_id == "shady/merge-frankenstein")
    assert r1.scores == {"ifeval_strict_acc": pytest.approx(0.999)}


def test_hf_v2_fetcher_skips_null_ifeval():
    row = [{"fullname": "x/y", "IFEval": None}]
    with patch("bench.references.sources.hf_v2.load_dataset",
               side_effect=lambda _id, **kw: {"train": iter(row)}):
        records = list(HFOpenLLMV2Fetcher().fetch())
    assert records == []


def test_bigcode_fetcher_returns_empty_when_dataset_unavailable():
    # Dataset bigcode/bigcode-models-leaderboard-data no longer exists
    with patch("bench.references.sources.bigcode.load_dataset") as mock_load:
        mock_load.side_effect = Exception("Dataset not found")
        records = list(BigCodeHumanEvalFetcher().fetch())
    assert records == []
