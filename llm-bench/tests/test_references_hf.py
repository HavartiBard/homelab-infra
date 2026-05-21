from datetime import date
from unittest.mock import patch

import pytest

from bench.references.model import ReferenceRecord
from bench.references.sources.hf_v1 import HFOpenLLMV1Fetcher
from bench.references.sources.hf_v2 import HFOpenLLMV2Fetcher
from bench.references.sources.bigcode import BigCodeHumanEvalFetcher


SAMPLE_V1_ROWS = [
    {
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "arc:challenge": 81.2,
        "gsm8k": 84.6,
        "params": 8.0,
        "license": "llama3.1",
    },
    {
        "model": "deleted-org/missing",
        "arc:challenge": 50.0,
        "gsm8k": None,
        "params": 7.0,
        "license": None,
    },
]


def test_hf_v1_fetcher_normalizes_rows():
    with patch("bench.references.sources.hf_v1.load_dataset",
               side_effect=lambda _id: iter(SAMPLE_V1_ROWS)):
        records = list(HFOpenLLMV1Fetcher().fetch())

    assert len(records) == 2
    r0 = next(r for r in records if r.model_id == "meta-llama/Llama-3.1-8B-Instruct")
    assert r0.source == "hf_open_llm_v1"
    assert r0.scores["arc_challenge_acc"] == pytest.approx(0.812)
    assert r0.scores["gsm8k_strict_match"] == pytest.approx(0.846)
    assert r0.num_params_b == 8.0
    assert r0.as_of == date(2024, 6, 26)  # HF v1 archive cutoff


def test_hf_v1_fetcher_skips_rows_with_null_model():
    bad = [{"model": None, "arc:challenge": 50.0, "gsm8k": 60.0}]
    with patch("bench.references.sources.hf_v1.load_dataset",
               side_effect=lambda _id: iter(bad)):
        records = list(HFOpenLLMV1Fetcher().fetch())
    assert records == []


def test_hf_v1_fetcher_skips_rows_with_all_null_scores():
    bad = [{"model": "x/y", "arc:challenge": None, "gsm8k": None}]
    with patch("bench.references.sources.hf_v1.load_dataset",
               side_effect=lambda _id: iter(bad)):
        records = list(HFOpenLLMV1Fetcher().fetch())
    assert records == []


SAMPLE_V2_ROWS = [
    {
        "fullname": "Qwen/Qwen2.5-72B-Instruct",
        "IFEval": 86.6,
        "#Params (B)": 72.0,
        "Hub License": "qwen",
        "Maintainer's Choice": True,
    },
    {
        "fullname": "shady/merge-frankenstein",
        "IFEval": 99.9,
        "#Params (B)": 13.0,
        "Hub License": "other",
        "Maintainer's Choice": False,
    },
]


def test_hf_v2_fetcher_only_returns_maintainer_choice():
    with patch("bench.references.sources.hf_v2.load_dataset",
               side_effect=lambda _id: iter(SAMPLE_V2_ROWS)):
        records = list(HFOpenLLMV2Fetcher().fetch())
    assert len(records) == 1
    assert records[0].model_id == "Qwen/Qwen2.5-72B-Instruct"
    assert records[0].scores == {"ifeval_strict_acc": pytest.approx(0.866)}
    assert records[0].source == "hf_open_llm_v2"


def test_hf_v2_fetcher_skips_null_ifeval():
    row = [{"fullname": "x/y", "IFEval": None, "Maintainer's Choice": True}]
    with patch("bench.references.sources.hf_v2.load_dataset",
               side_effect=lambda _id: iter(row)):
        records = list(HFOpenLLMV2Fetcher().fetch())
    assert records == []


SAMPLE_BIGCODE_ROWS = [
    {"model": "Qwen/Qwen2.5-Coder-7B-Instruct", "humaneval-python": 88.4, "params": 7.0},
    {"model": None, "humaneval-python": 50.0, "params": 1.0},
    {"model": "x/y", "humaneval-python": None, "params": 7.0},
]


def test_bigcode_fetcher_normalizes_humaneval():
    with patch("bench.references.sources.bigcode.load_dataset",
               side_effect=lambda _id: iter(SAMPLE_BIGCODE_ROWS)):
        records = list(BigCodeHumanEvalFetcher().fetch())
    assert len(records) == 1
    r = records[0]
    assert r.source == "bigcode_humaneval"
    assert r.scores == {"humaneval_pass1": pytest.approx(0.884)}
    assert r.num_params_b == 7.0
