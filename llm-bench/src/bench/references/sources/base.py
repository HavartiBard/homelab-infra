from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ..model import ReferenceRecord


@runtime_checkable
class SourceFetcher(Protocol):
    name: str

    def fetch(self) -> Iterable[ReferenceRecord]:
        """Yield ReferenceRecord instances. Must NOT touch the DB."""
        ...
