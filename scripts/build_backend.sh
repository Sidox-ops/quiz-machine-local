#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-.venv/bin/python}"
if ! "$PYTHON" -c 'import PyInstaller' >/dev/null 2>&1; then
  printf 'Build dependencies are missing. Run:\n'
  printf '  %s -m pip install -r requirements-build.txt\n' "$PYTHON"
  exit 1
fi

rm -rf dist/backend build-backend
"$PYTHON" -m PyInstaller \
  --distpath dist/backend \
  --workpath build-backend \
  --noconfirm \
  packaging/quiz_backend.spec

"$PYTHON" -m piplicenses \
  --format=plain-vertical \
  --with-license-file \
  --output-file=dist/THIRD_PARTY_LICENSES.txt

printf 'Backend created in %s/dist/backend\n' "$ROOT_DIR"
