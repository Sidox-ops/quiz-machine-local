#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Python environment missing. Run ./setup.sh or ./start.sh first."
  exit 1
fi

exec .venv/bin/python -m uvicorn backend.api:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
