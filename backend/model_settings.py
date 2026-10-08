from __future__ import annotations

import json
from pathlib import Path
import threading

from .config import MODEL_SETTINGS_PATH


class ModelSettingsStore:
    """Persist the user's local generation-model choice atomically."""

    def __init__(self, path: Path = MODEL_SETTINGS_PATH):
        self.path = path
        self._lock = threading.Lock()

    def selected_model(self) -> str:
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return ""
            if not isinstance(payload, dict):
                return ""
            return str(payload.get("generation_model") or "").strip()

    def select_model(self, model: str) -> None:
        selected = model.strip()
        if not selected:
            raise ValueError("A generation model must be selected.")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generation_model": selected,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)
