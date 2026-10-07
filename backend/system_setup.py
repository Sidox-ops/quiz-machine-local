from __future__ import annotations

import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

from requests import RequestException

from .config import DEFAULT_LLM_MODEL, EMBEDDING_MODEL, LLM_MODEL, STORAGE_DIR
from .ollama_client import OllamaClient, OllamaError, model_matches
from .rag import RagIndex


RECOMMENDED_FREE_BYTES = 8 * 1024**3


def find_ollama() -> str | None:
    executable = shutil.which("ollama")
    if executable:
        return executable
    if platform.system() == "Darwin":
        candidate = Path("/Applications/Ollama.app/Contents/Resources/ollama")
        if candidate.exists():
            return str(candidate)
    return None


def diagnostics(client: OllamaClient, rag: RagIndex) -> dict:
    executable = find_ollama()
    try:
        models = client.list_models()
        api_reachable = True
    except OllamaError:
        models = []
        api_reachable = False

    def has_model(required: str) -> bool:
        return any(model_matches(required, name) for name in models)

    selected_llm_model = client.select_llm_model(models) if api_reachable else (LLM_MODEL or DEFAULT_LLM_MODEL)

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(STORAGE_DIR).free
    return {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "ollama_installed": executable is not None,
        "ollama_reachable": api_reachable,
        "llm_model": selected_llm_model,
        "llm_ready": has_model(selected_llm_model),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_ready": (
            not rag.requires_local_embeddings or has_model(EMBEDDING_MODEL)
        ),
        "index_ready": rag.knowledge_ready,
        "indexed_chunks": rag.indexed_chunk_count,
        "knowledge_provider": rag.knowledge_provider,
        "knowledge_ready": rag.knowledge_ready,
        "free_disk_bytes": free_bytes,
        "recommended_free_bytes": RECOMMENDED_FREE_BYTES,
        "disk_ready": free_bytes >= RECOMMENDED_FREE_BYTES,
    }


class SetupManager:
    def __init__(self, client: OllamaClient, rag: RagIndex):
        self.client = client
        self.rag = rag
        self._lock = threading.Lock()
        self._state = {
            "status": "idle",
            "stage": "waiting",
            "message": "Environment check has not started.",
        }

    def state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def start(self) -> dict:
        with self._lock:
            if self._state["status"] == "running":
                return dict(self._state)
            self._state = {
                "status": "running",
                "stage": "starting",
                "message": "Preparing the local environment...",
            }
        threading.Thread(target=self._run, daemon=True).start()
        return self.state()

    def _update(self, status: str, stage: str, message: str) -> None:
        with self._lock:
            self._state = {"status": status, "stage": stage, "message": message}

    def _run(self) -> None:
        try:
            executable = find_ollama()
            if not executable:
                raise RuntimeError("Ollama is not installed.")

            try:
                self.client.list_models()
            except OllamaError:
                if platform.system() == "Darwin":
                    raise RuntimeError("Open the Ollama application, then check again.")
                self._update("running", "ollama", "Starting Ollama...")
                subprocess.Popen(
                    [executable, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                for _ in range(30):
                    time.sleep(1)
                    try:
                        self.client.list_models()
                        break
                    except OllamaError:
                        continue
                else:
                    raise RuntimeError("Ollama did not start within 30 seconds.")

            models = self.client.list_models()
            if (
                self.rag.requires_local_embeddings
                and not any(model_matches(EMBEDDING_MODEL, name) for name in models)
            ):
                self._update("running", "models", f"Downloading embedding model: {EMBEDDING_MODEL}")
                self.client.pull_model(EMBEDDING_MODEL)

            models = self.client.list_models()
            selected_llm = self.client.select_llm_model(models)
            llm_available = any(model_matches(selected_llm, name) for name in models)
            if not llm_available:
                self._update("running", "models", f"Downloading quiz model: {selected_llm}")
                self.client.pull_model(selected_llm)

            if self.rag.uses_microsoft_learn:
                self._update(
                    "running",
                    "knowledge",
                    "Connecting to the official Microsoft Learn courses...",
                )
                try:
                    self.rag.test_knowledge_provider()
                except (OSError, OllamaError, RequestException, RuntimeError):
                    if not self.rag.has_scoped_local_corpus:
                        raise
                    self._update(
                        "running",
                        "knowledge",
                        "Microsoft Learn is unavailable; preparing the local corpus...",
                    )
            if self.rag.requires_local_embeddings:
                self._update("running", "index", "Building the local search index...")
                self.rag.build()
            self._update("completed", "ready", "The quiz engine is ready.")
        except (OSError, OllamaError, RuntimeError) as exc:
            self._update("failed", "error", str(exc))
