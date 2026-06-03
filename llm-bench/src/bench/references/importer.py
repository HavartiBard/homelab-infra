from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

import duckdb
from pydantic import BaseModel, Field

from .sources.base import SourceFetcher

log = logging.getLogger(__name__)


class ImportReport(BaseModel):
    ok_sources: dict[str, int] = Field(default_factory=dict)
    failed_sources: dict[str, str] = Field(default_factory=dict)


_INSERT = """
INSERT OR REPLACE INTO refs (
  model_id, source, display_name, num_params_b, license,
  arc_challenge_acc, gsm8k_strict_match, humaneval_pass1, ifeval_strict_acc,
  citation_url, as_of, imported_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def refresh(
    db: duckdb.DuckDBPyConnection,
    fetchers: Sequence[SourceFetcher],
) -> ImportReport:
    """Run each fetcher in its own transaction with per-source isolation.

    Each fetcher's records replace ALL existing rows for its source in a
    single transaction. A failure in one fetcher does not affect the
    others — its transaction is rolled back and the next fetcher proceeds.

    Returns an ImportReport with per-source row counts (ok_sources) and
    per-source error messages (failed_sources).
    """
    report = ImportReport()
    imported_at = datetime.now(timezone.utc)

    for fetcher in fetchers:
        try:
            db.execute("BEGIN TRANSACTION")
            db.execute("DELETE FROM refs WHERE source = ?", [fetcher.name])
            count = 0
            for rec in fetcher.fetch():
                if rec.source != fetcher.name:
                    raise ValueError(
                        f"Fetcher {fetcher.name!r} yielded record with "
                        f"source={rec.source!r} (must match fetcher name)"
                    )
                db.execute(_INSERT, [
                    rec.model_id, rec.source, rec.display_name,
                    rec.num_params_b, rec.license,
                    rec.scores.get("arc_challenge_acc"),
                    rec.scores.get("gsm8k_strict_match"),
                    rec.scores.get("humaneval_pass1"),
                    rec.scores.get("ifeval_strict_acc"),
                    rec.citation_url, rec.as_of, imported_at,
                ])
                count += 1
            db.execute("COMMIT")
            report.ok_sources[fetcher.name] = count
            log.info("[ok] %s: %d records", fetcher.name, count)
        except Exception as exc:
            db.execute("ROLLBACK")
            report.failed_sources[fetcher.name] = str(exc)
            log.warning("[fail] %s: %s", fetcher.name, exc)

    return report
