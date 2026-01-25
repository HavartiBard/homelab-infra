#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$ROOT/stacks/platform/homepage/config"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to validate homepage config" >&2
  exit 1
fi

errors=0
for file in "$CONFIG_DIR"/*.yaml; do
  [ -e "$file" ] || continue
  if ! python3 - "$file" <<'PY'
import sys, yaml
from pathlib import Path
f = Path(sys.argv[1])
try:
    yaml.safe_load(f.read_text())
except Exception as e:
    print(f"{f}: {e}", file=sys.stderr)
    sys.exit(1)
PY
  then
    errors=$((errors+1))
  fi
done

if [ "$errors" -gt 0 ]; then
  echo "Homepage config validation failed." >&2
  exit 1
fi

echo "Homepage config validation passed."
