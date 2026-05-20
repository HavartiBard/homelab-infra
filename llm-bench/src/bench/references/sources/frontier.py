from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from ..model import ReferenceRecord


class FrontierFetcher:
    name = "frontier_curated"

    def __init__(self, yaml_path: Path):
        self.yaml_path = Path(yaml_path)

    def fetch(self) -> Iterable[ReferenceRecord]:
        data = yaml.safe_load(self.yaml_path.read_text())
        for entry in data.get("references", []):
            yield ReferenceRecord(source=self.name, **entry)
