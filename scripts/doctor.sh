#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

missing=0

require_command() {
  if command -v "$1" >/dev/null 2>&1; then
    printf "[ok] %s: %s\n" "$1" "$(command -v "$1")"
  else
    printf "[missing] %s\n" "$1"
    missing=1
  fi
}

require_command python3
require_command ollama
require_command flutter
require_command curl

if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    printf "[ok] Python %s\n" "$(python3 -c 'import platform; print(platform.python_version())')"
  else
    printf "[unsupported] Python 3.10 or newer is required\n"
    missing=1
  fi
fi

case "$(uname -s)" in
  Darwin)
    printf "[ok] Platform: macOS (tested)\n"
    ;;
  Linux)
    printf "[warning] Platform: Linux (community-tested only)\n"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    printf "[warning] Platform: Windows through Bash (experimental)\n"
    ;;
  *)
    printf "[unsupported] Platform: %s\n" "$(uname -s)"
    missing=1
    ;;
esac

if [[ "$missing" -ne 0 ]]; then
  printf "\nInstall the missing prerequisites, then run this command again.\n"
  exit 1
fi

printf "\nLocal prerequisites are ready.\n"
