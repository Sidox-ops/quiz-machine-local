#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

OLLAMA_PID=""
BACKEND_PID=""

cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${OLLAMA_PID}" ]] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
    kill "$OLLAMA_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

./setup.sh

mkdir -p storage

# Start Ollama only if its local API is not already reachable.
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve > storage/ollama.log 2>&1 &
  OLLAMA_PID=$!
  for _ in {1..30}; do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Could not reach Ollama at http://127.0.0.1:11434"
  exit 1
fi

ensure_model() {
  local model="$1"
  if ! ollama show "$model" >/dev/null 2>&1; then
    echo "Pulling Ollama model: $model"
    ollama pull "$model"
  fi
}

EMBEDDING_MODEL="${AI103_EMBEDDING_MODEL:-nomic-embed-text}"
DEFAULT_LLM_MODEL="${AI103_DEFAULT_LLM_MODEL:-gemma4:e4b-mlx}"
LLM_MODEL="${AI103_LLM_MODEL:-$DEFAULT_LLM_MODEL}"
KNOWLEDGE_PROVIDER="${AI103_KNOWLEDGE_PROVIDER:-microsoft_learn_mcp}"
export AI103_KNOWLEDGE_PROVIDER="$KNOWLEDGE_PROVIDER"

if [[ "$KNOWLEDGE_PROVIDER" != "microsoft_learn_mcp" ]]; then
  ensure_model "$EMBEDDING_MODEL"
fi

ensure_model "$LLM_MODEL"
echo "Using Ollama quiz model: $LLM_MODEL"
export AI103_LLM_MODEL="$LLM_MODEL"

if [[ "$KNOWLEDGE_PROVIDER" == "microsoft_learn_mcp" ]]; then
  echo "Using official Microsoft Learn courses for quiz grounding."
else
  # Build embeddings when the local index is missing or stale.
  INDEX_CURRENT="false"
  if [[ -f "storage/index.json" ]] && .venv/bin/python -c \
    'from backend.ollama_client import OllamaClient; from backend.rag import RagIndex; raise SystemExit(0 if RagIndex(OllamaClient()).catalog()["coverage"]["complete"] else 1)'
  then
    INDEX_CURRENT="true"
  fi

  if [[ "$INDEX_CURRENT" != "true" ]]; then
    echo "Building the local RAG index for all corpus sources..."
    .venv/bin/python build_index.py
  fi
fi

# Generate native Flutter project files once, while preserving our app source.
if [[ ! -d "flutter_app/macos" ]]; then
  echo "Preparing Flutter desktop files..."
  (
    cd flutter_app
    ./bootstrap.sh
  )
else
  (
    cd flutter_app
    flutter pub get >/dev/null
  )
fi

# Flutter macOS runs in an App Sandbox. Grant outgoing network access so the
# desktop UI can reach the local FastAPI backend at 127.0.0.1:8000. This is
# intentionally run on every launch so existing generated macOS projects are
# repaired too.
(
  cd flutter_app
  ./enable_macos_network.sh
)

# Start FastAPI in the background.
echo "Starting Microsoft certification backend..."
.venv/bin/python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 > storage/backend.log 2>&1 &
BACKEND_PID=$!

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend stopped unexpectedly. See storage/backend.log"
    exit 1
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "Backend did not become ready. See storage/backend.log"
  exit 1
fi

case "$(uname -s)" in
  Darwin) DEVICE="macos" ;;
  Linux)  DEVICE="linux" ;;
  MINGW*|MSYS*|CYGWIN*) DEVICE="windows" ;;
  *)
    echo "Unsupported desktop platform: $(uname -s)"
    exit 1
    ;;
esac

echo "Launching Microsoft Certification Quiz Machine..."
cd flutter_app
flutter run -d "$DEVICE"
