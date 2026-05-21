from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from datasets import load_dataset
from pydantic import ValidationError

from ..model import ReferenceRecord

log = logging.getLogger(__name__)


class HFOpenLLMV2Fetcher:
    name = "hf_open_llm_v2"
    dataset_id = "open-llm-leaderboard/contents"

    def fetch(self) -> Iterable[ReferenceRecord]:
        as_of = datetime.now(timezone.utc).date()
        ds = load_dataset(self.dataset_id)["train"]  # Load the train split
        for row in ds:
            # HF V2 doesn't have a "Maintainer's Choice" filter anymore
            model_id = row.get("fullname")
            ifeval = row.get("IFEval")
            if not model_id or ifeval is None:
                continue
            try:
                yield ReferenceRecord(
                    model_id=model_id,
                    source=self.name,
                    display_name=model_id.split("/")[-1].replace("-", " "),
                    num_params_b=row.get("#Params (B)"),
                    license=row.get("Hub License"),
                    scores={"ifeval_strict_acc": ifeval / 100.0},
                    citation_url=(
                        "https://huggingface.co/spaces/"
                        "open-llm-leaderboard/open_llm_leaderboard"
                    ),
                    as_of=as_of,
                )
            except ValidationError as exc:
                log.warning("Skipping v2 row for %s: %s", model_id, exc)
                continue
