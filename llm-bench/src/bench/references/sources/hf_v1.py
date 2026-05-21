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
        # Use streaming=True to avoid schema mismatch issues when loading large datasets
        ds = load_dataset(self.dataset_id, split="train", streaming=True)
        for row in ds:
            # HF V1 has nested structure: config_general + results dict
            model_id = row.get("config_general", {}).get("model_name")
            if not model_id:
                continue
            results = row.get("results", {})
            scores: dict[str, float] = {}
            # Look for arc:challenge in results (key format: harness|arc:challenge|N)
            arc_key = next((k for k in results.keys() if "arc:challenge" in k), None)
            if arc_key:
                arc_result = results[arc_key]
                if arc_result and isinstance(arc_result, dict):
                    scores["arc_challenge_acc"] = arc_result.get("acc", 0.0)
            # Look for gsm8k in results (key format: harness|gsm8k|N)
            gsm8k_key = next((k for k in results.keys() if "gsm8k" in k), None)
            if gsm8k_key:
                gsm8k_result = results[gsm8k_key]
                if gsm8k_result and isinstance(gsm8k_result, dict):
                    scores["gsm8k_strict_match"] = gsm8k_result.get("acc", 0.0)
            if not scores:
                continue
            try:
                yield ReferenceRecord(
                    model_id=model_id,
                    source=self.name,
                    display_name=model_id.split("/")[-1].replace("-", " "),
                    num_params_b=None,  # HF V1 doesn't expose params in this dataset
                    license=None,  # HF V1 doesn't expose license in this dataset
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
