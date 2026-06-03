from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator


ALLOWED_SCORE_IDS = frozenset({
    "arc_challenge_acc",
    "gsm8k_strict_match",
    "humaneval_pass1",
    "ifeval_strict_acc",
})

Source = Literal[
    "frontier_curated",
    "hf_open_llm_v1",
    "hf_open_llm_v2",
    "bigcode_humaneval",
]


class ReferenceRecord(BaseModel):
    model_id: str
    source: Source
    display_name: str
    num_params_b: float | None = None
    license: str | None = None
    scores: dict[str, float]
    citation_url: str | None = None
    as_of: date

    @field_validator("scores")
    @classmethod
    def only_known_scores(cls, v: dict[str, float]) -> dict[str, float]:
        unknown = set(v) - ALLOWED_SCORE_IDS
        if unknown:
            raise ValueError(f"unknown score ids: {sorted(unknown)}")
        return v
