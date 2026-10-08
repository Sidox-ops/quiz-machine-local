from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA_DIR = ROOT_DIR / "data"
REFERENCE_DATA_DIR = Path(
    os.getenv("QUIZ_MACHINE_REFERENCE_DATA_DIR", DATA_DIR / "reference")
)
USER_DATA_DIR = Path(os.getenv("QUIZ_MACHINE_USER_DATA_DIR", DATA_DIR / "local"))
STORAGE_DIR = Path(os.getenv("QUIZ_MACHINE_STORAGE_DIR", ROOT_DIR / "storage"))
INDEX_PATH = STORAGE_DIR / "index.json"
PROGRESS_PATH = STORAGE_DIR / "progress.json"
QUESTIONS_PATH = STORAGE_DIR / "questions.json"
MODEL_SETTINGS_PATH = STORAGE_DIR / "settings.json"
MICROSOFT_LEARN_CORPUS_PATH = STORAGE_DIR / "microsoft_learn_corpus.json"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
API_TOKEN = os.getenv("QUIZ_MACHINE_API_TOKEN", "")
LLM_MODEL = os.getenv("QUIZ_MACHINE_LLM_MODEL", "").strip()
EMBEDDING_MODEL = os.getenv("QUIZ_MACHINE_EMBEDDING_MODEL", "nomic-embed-text")

TOP_K = max(1, min(int(os.getenv("QUIZ_MACHINE_TOP_K", "3")), 3))
GENERATION_TEMPERATURE = float(os.getenv("QUIZ_MACHINE_TEMPERATURE", "0"))
GENERATION_CONTEXT_TOKENS = int(os.getenv("QUIZ_MACHINE_NUM_CTX", "8192"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("QUIZ_MACHINE_TIMEOUT", "180"))
MODEL_PROBE_TIMEOUT_SECONDS = int(
    os.getenv("QUIZ_MACHINE_MODEL_PROBE_TIMEOUT", "120")
)
MICROSOFT_LEARN_CORPUS_REFRESH_HOURS = int(
    os.getenv("QUIZ_MACHINE_LEARN_CORPUS_REFRESH_HOURS", "24")
)
KNOWLEDGE_PROVIDER = os.getenv(
    "QUIZ_MACHINE_KNOWLEDGE_PROVIDER", "microsoft_learn_mcp"
).strip().lower()
MICROSOFT_LEARN_MCP_ENDPOINT = os.getenv(
    "MICROSOFT_LEARN_MCP_ENDPOINT", "https://learn.microsoft.com/api/mcp"
)
