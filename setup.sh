#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

./scripts/doctor.sh

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Creating Python environment..."
  python3 -m venv .venv
fi

REQUIREMENTS_HASH="$(python3 -c '
import hashlib
from pathlib import Path
content = Path("requirements.txt").read_bytes() + Path("requirements.lock").read_bytes()
print(hashlib.sha256(content).hexdigest())
')"
STAMP_PATH=".venv/.requirements.sha256"
INSTALLED_HASH=""

if [[ -f "$STAMP_PATH" ]]; then
  INSTALLED_HASH="$(<"$STAMP_PATH")"
fi

if [[ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]]; then
  echo "Installing pinned Python dependencies..."
  .venv/bin/python -m pip install -r requirements.lock
  printf "%s" "$REQUIREMENTS_HASH" > "$STAMP_PATH"
else
  echo "Python dependencies are already up to date."
fi

echo "Local Python environment is ready."
