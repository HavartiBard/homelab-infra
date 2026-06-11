from __future__ import annotations

import logging
from datetime import date
from typing import Iterable

from datasets import load_dataset
from pydantic import ValidationError

from ..model import ReferenceRecord

log = logging.getLogger(__name__)

# HF v1 leaderboard archive was frozen on this date when v2 launched.
HF_V1_ARCHIVE_DATE = date(2024, 6, 26)


class HFOpenLLMV1Fetcher:
    name = "hf_open_llm_v1"
    dataset_id = "open-llm-leaderboard-old/results"

    def fetch(self) -> Iterable[ReferenceRecord]:
        ds = load_dataset(self.dataset_id, split="train")
        for row in ds:
            model_id = row.get("model")
            if not model_id:
                continue
            scores: dict[str, float] = {}
            if row.get("arc:challenge") is not None:
                scores["arc_challenge_acc"] = row["arc:challenge"] / 100.0
            if row.get("gsm8k") is not None:
                scores["gsm8k_strict_match"] = row["gsm8k"] / 100.0
            if not scores:
                continue
            try:
                yield ReferenceRecord(
                    model_id=model_id,
                    source=self.name,
                    display_name=model_id.split("/")[-1].replace("-", " "),
                    num_params_b=row.get("params"),
                    license=row.get("license"),
                    scores=scores,
                    citation_url=(
                        "https://huggingface.co/spaces/"
                        "open-llm-leaderboard-old/open_llm_leaderboard"
                    ),
                    as_of=HF_V1_ARCHIVE_DATE,
                )
            except ValidationError as exc:
                log.warning("Skipping v1 row for %s: %s", model_id, exc)
                continue
