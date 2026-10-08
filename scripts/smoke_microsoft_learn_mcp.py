from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import MICROSOFT_LEARN_MCP_ENDPOINT
from backend.microsoft_learn_mcp import MicrosoftLearnMcpClient


def main() -> None:
    client = MicrosoftLearnMcpClient(MICROSOFT_LEARN_MCP_ENDPOINT, timeout=30)
    client.test_connection()
    results = client.search("Azure AI certification study guide", limit=1)
    if not results:
        raise RuntimeError("Microsoft Learn MCP returned no official search result")
    print(f"Microsoft Learn MCP is ready: {results[0]['url']}")


if __name__ == "__main__":
    main()
