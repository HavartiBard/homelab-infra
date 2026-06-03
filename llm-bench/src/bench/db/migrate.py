from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from . import get_connection
from ..store import RunRecord, append_run

log = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    migrated: int
    skipped: int
    already_done: bool = False


def migrate_jsonl_to_duckdb(
    jsonl_path: Path, db_path: Path,
) -> MigrationResult:
    jsonl_path = Path(jsonl_path)
    db_path = Path(db_path)
    migrated_marker = jsonl_path.with_suffix(jsonl_path.suffix + ".migrated")

    if not jsonl_path.exists():
        if migrated_marker.exists():
            log.info("Migration already done (%s exists)", migrated_marker)
            return MigrationResult(0, 0, already_done=True)
        log.info("No JSONL at %s and no prior migration — nothing to do", jsonl_path)
        return MigrationResult(0, 0, already_done=True)

    db = get_connection(db_path)

    migrated = 0
    skipped = 0
    for lineno, line in enumerate(jsonl_path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = RunRecord.model_validate_json(line)
        except (ValueError, ValidationError) as exc:
            log.warning("Skipping line %d: %s", lineno, exc)
            skipped += 1
            continue
        append_run(db, record)
        migrated += 1

    jsonl_path.rename(migrated_marker)
    log.info(
        "Migrated %d runs from %s -> %s (skipped %d)",
        migrated, jsonl_path.name, db_path.name, skipped,
    )
    return MigrationResult(migrated=migrated, skipped=skipped)
