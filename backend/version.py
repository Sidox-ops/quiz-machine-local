from __future__ import annotations

import sys
from pathlib import Path


def _load_version() -> str:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.1.0"


APP_VERSION = _load_version()
