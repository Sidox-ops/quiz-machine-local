from __future__ import annotations

import platform
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from requests import RequestException

from .config import EMBEDDING_MODEL, STORAGE_DIR
from .ollama_client import OllamaClient, OllamaError, model_matches
from .rag import RagIndex


RECOMMENDED_FREE_BYTES = 8 * 1024**3


def physical_memory_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return int(pages * page_size)
    except (AttributeError, OSError, ValueError):
        pass
    if platform.system() == "Windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.total_physical)
        except (AttributeError, OSError, ValueError):
            pass
    return None


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
        inventory = client.list_model_details()
        api_reachable = True
    except OllamaError:
        inventory = []
        api_reachable = False

    models = [model.name for model in inventory]

    def has_model(required: str) -> bool:
        return any(model_matches(required, name) for name in models)

    selected_llm_model = client.configured_model()
    memory_bytes = physical_memory_bytes()
    recommended_llm_model = client.recommend_model(inventory, memory_bytes)
    selected_info = client.selected_model_info(selected_llm_model, inventory)

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(STORAGE_DIR).free
    return {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "ollama_installed": executable is not None,
        "ollama_reachable": api_reachable,
        "llm_model": selected_llm_model,
        "llm_model_selected": bool(selected_llm_model),
        "llm_ready": bool(selected_info and selected_info.compatible),
        "recommended_llm_model": recommended_llm_model or "",
        "model_selection_locked": client.selection_locked,
        "physical_memory_bytes": memory_bytes or 0,
        "model_recommendation_reason": (
            "Best compatible installed model estimated to fit within 70% of "
            "system memory. The selected model is verified with a local JSON probe."
            if memory_bytes
            else "Best compatible installed model. The selected model is verified "
            "with a local JSON probe."
        ),
        "ollama_models": [
            model.public_payload(
                selected=model == selected_info,
                recommended=model.name == recommended_llm_model,
                physical_memory_bytes=memory_bytes,
            )
            for model in inventory
        ],
        "embedding_model": EMBEDDING_MODEL,
        "embedding_ready": (
            not rag.requires_local_embeddings or has_model(EMBEDDING_MODEL)
        ),
        "index_ready": rag.knowledge_ready,
        "indexed_chunks": rag.indexed_chunk_count,
        "knowledge_provider": rag.knowledge_provider,
        "knowledge_ready": rag.knowledge_ready,
        "knowledge_check_completed": rag.knowledge_check_completed,
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

            inventory = self.client.list_model_details()
            models = [model.name for model in inventory]
            if (
                self.rag.requires_local_embeddings
                and not any(model_matches(EMBEDDING_MODEL, name) for name in models)
            ):
                raise RuntimeError(
                    f"The local corpus requires the installed embedding model "
                    f"{EMBEDDING_MODEL}. Install it in Ollama, then check again. "
                    "Quiz Machine does not download models automatically."
                )

            selected_llm = self.client.configured_model()
            if not selected_llm:
                raise RuntimeError(
                    "Choose one of the installed local Ollama models before "
                    "verifying the environment."
                )
            selected_info = self.client.selected_model_info(selected_llm, inventory)
            if selected_info is None:
                raise RuntimeError(
                    f"The selected Ollama model is no longer installed: {selected_llm}"
                )
            if not selected_info.compatible:
                raise RuntimeError(selected_info.compatibility_reason)

            self._update(
                "running",
                "model",
                f"Testing structured output with {selected_info.name}...",
            )
            self.client.probe_model(selected_info.name, inventory)

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
