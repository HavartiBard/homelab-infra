# gedcom_sync — Webtrees → PocketBase

Reads the Webtrees MariaDB and upserts into the reunion PocketBase
`persons`/`couples` collections. Idempotent (keyed on `gedcom_id`),
fill-blanks-only (never overwrites edits made in the reunion SPA), redacts
living people, supports `--dry-run`.

## One-time admin workflow

1. Import the ancestry.com `.ged` via the Webtrees UI (`https://webtrees.klsll.com`).
2. Copy this directory to Unraid, e.g. `/mnt/user/appdata/gedcom_sync/`.
3. Export secrets, dry-run, then apply (run **on Unraid**, where the `webtrees`
   Docker network exists):

```bash
export PB_ADMIN_EMAIL="james@klsll.com"
export PB_ADMIN_PASSWORD="<pocketbase admin pw>"      # 1Password: AI Wedge / pocketbase
export WT_DB_PASSWORD="<webtrees db pw>"              # vault_webtrees_db_password

./run.sh --dry-run     # report only, no writes
./run.sh               # apply
```

`run.sh` launches a throwaway `python:3.12-slim` container on the `webtrees`
network so it can reach `webtrees-db:3306` without the DB being published, and
talks to PocketBase at `http://192.168.20.14:8094`.

## Behaviour

- **Idempotent:** matches existing people by `persons.gedcom_id` (the Webtrees
  xref, e.g. `@I123@`). Re-running only adds new people / fills empty fields.
- **Fill-blanks-only:** never overwrites a field that already has a value in
  PocketBase, so anything edited in the SPA wins. (`gender="unknown"` counts as
  blank and will be filled by a known GEDCOM gender.)
- **Living-person redaction:** anyone with no death date and a birth year within
  100 years is marked `living=true` with `birth_date`/`bio` cleared.
- **Relationships:** `father`/`mother` set from each family's HUSB/WIFE; a
  `couples` row is created per family with both partners.

## Local unit tests

```bash
pip install -r requirements.txt   # or just: pip install pytest
python -m pytest test_gedcom_sync.py -q
```
