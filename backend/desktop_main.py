from __future__ import annotations

import os

import uvicorn

from backend.api import app


def main() -> None:
    port = int(os.getenv("AI103_BACKEND_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
