from datetime import date

import pytest
from pydantic import ValidationError

from bench.references.model import ReferenceRecord


def test_valid_record():
    r = ReferenceRecord(
        model_id="meta-llama/Llama-3.1-8B-Instruct",
        source="hf_open_llm_v1",
        display_name="Llama 3.1 8B Instruct",
        num_params_b=8.0,
        license="llama3.1",
        scores={"arc_challenge_acc": 0.812, "gsm8k_strict_match": 0.846},
        citation_url="https://huggingface.co/...",
        as_of=date(2024, 7, 23),
    )
    assert r.scores["arc_challenge_acc"] == 0.812


def test_unknown_score_id_rejected():
    with pytest.raises(ValidationError, match="unknown score ids"):
        ReferenceRecord(
            model_id="x/y",
            source="frontier_curated",
            display_name="X",
            scores={"mmlu_pro": 0.6},
            as_of=date(2025, 1, 1),
        )


def test_invalid_source_rejected():
    with pytest.raises(ValidationError):
        ReferenceRecord(
            model_id="x/y",
            source="some_other_source",
            display_name="X",
            scores={"arc_challenge_acc": 0.5},
            as_of=date(2025, 1, 1),
        )
