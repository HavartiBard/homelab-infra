#!/usr/bin/env bash
# Run gedcom_sync.py from a temporary container on the webtrees Docker network,
# so it reaches webtrees-db:3306 without the DB being published. Run ON Unraid.
# Required env: PB_ADMIN_EMAIL PB_ADMIN_PASSWORD WT_DB_PASSWORD
# Any extra args (e.g. --dry-run) are forwarded to gedcom_sync.py.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker run --rm --network webtrees -v "$DIR":/app -w /app \
  -e PB_URL="${PB_URL:-http://192.168.20.14:8094}" \
  -e PB_ADMIN_EMAIL -e PB_ADMIN_PASSWORD \
  -e WT_DB_HOST="${WT_DB_HOST:-webtrees-db}" \
  -e WT_DB_NAME="${WT_DB_NAME:-webtrees}" \
  -e WT_DB_USER="${WT_DB_USER:-webtrees}" \
  -e WT_DB_PASSWORD \
  python:3.12-slim sh -c "pip install -q -r requirements.txt && python gedcom_sync.py $*"
