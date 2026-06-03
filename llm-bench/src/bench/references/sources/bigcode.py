from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from datasets import load_dataset
from pydantic import ValidationError

from ..model import ReferenceRecord

log = logging.getLogger(__name__)


class BigCodeHumanEvalFetcher:
    name = "bigcode_humaneval"
    dataset_id = "bigcode/bigcode-models-leaderboard-data"

    def fetch(self) -> Iterable[ReferenceRecord]:
        as_of = datetime.now(timezone.utc).date()
        ds = load_dataset(self.dataset_id, split="train")
        for row in ds:
            model_id = row.get("model")
            hev = row.get("humaneval-python")
            if not model_id or hev is None:
                continue
            try:
                yield ReferenceRecord(
                    model_id=model_id,
                    source=self.name,
                    display_name=model_id.split("/")[-1].replace("-", " "),
                    num_params_b=row.get("params"),
                    license=row.get("license"),
                    scores={"humaneval_pass1": hev / 100.0},
                    citation_url="https://huggingface.co/spaces/bigcode/bigcode-models-leaderboard",
                    as_of=as_of,
                )
            except ValidationError as exc:
                log.warning("Skipping bigcode row for %s: %s", model_id, exc)
                continue
