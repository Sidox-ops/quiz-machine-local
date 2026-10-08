from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _match(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Could not find the application version in {path}")
    return match.group(1)


def main() -> None:
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    values = {
        "Flutter package": _match(
            ROOT / "flutter_app" / "pubspec.yaml",
            r"^version:\s*([^+\s]+)",
        ),
        "Flutter runtime": _match(
            ROOT / "flutter_app" / "lib" / "core" / "version.dart",
            r"defaultValue:\s*'([^']+)'",
        ),
        "backend fallback": _match(
            ROOT / "backend" / "version.py",
            r'return\s+"([^"]+)"',
        ),
    }
    mismatches = [
        f"{label}={value}" for label, value in values.items() if value != expected
    ]
    if mismatches:
        raise RuntimeError(
            f"VERSION is {expected}, but " + ", ".join(mismatches)
        )
    print(f"Application version is consistent: {expected}")


if __name__ == "__main__":
    main()
