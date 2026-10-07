import json
import unittest

from backend.microsoft_learn_mcp import MicrosoftLearnMcpClient


class Response:
    def __init__(self, payload, *, headers=None, empty=False):
        self.headers = headers or {"Content-Type": "text/event-stream"}
        self.text = "" if empty else f"event: message\ndata: {json.dumps(payload)}\n\n"

    def raise_for_status(self):
        return None


class Session:
    def __init__(self):
        self.calls = []

    def post(self, url, *, json, headers, timeout):
        self.calls.append((url, json, headers, timeout))
        method = json["method"]
        if method == "initialize":
            return Response(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {"protocolVersion": "2025-03-26"},
                },
                headers={
                    "Content-Type": "text/event-stream",
                    "Mcp-Session-Id": "session-123",
                },
            )
        if method == "notifications/initialized":
            return Response({}, empty=True)
        if method == "tools/list":
            return Response(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "microsoft_docs_search",
                                "inputSchema": {"properties": {"query": {}}},
                            },
                            {
                                "name": "microsoft_docs_fetch",
                                "inputSchema": {"properties": {"url": {}}},
                            },
                        ]
                    },
                }
            )
        if json["params"]["name"] == "microsoft_docs_fetch":
            return Response(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "# Vector storage\n\nUse pgvector with relational data.",
                            }
                        ]
                    },
                }
            )
        return Response(
            {
                "jsonrpc": "2.0",
                "id": json["id"],
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json_module.dumps(
                                {
                                    "results": [
                                        {
                                            "title": "Agents",
                                            "contentUrl": (
                                                "https://learn.microsoft.com/"
                                                "azure/foundry/agents"
                                            ),
                                            "content": "Official content",
                                        }
                                    ]
                                }
                            ),
                        }
                    ]
                },
            }
        )


json_module = json


class MicrosoftLearnMcpTests(unittest.TestCase):
    def test_client_negotiates_session_and_normalizes_content_url(self):
        session = Session()
        client = MicrosoftLearnMcpClient(
            "https://learn.microsoft.com/api/mcp",
            session=session,
        )

        results = client.search("AI-103 agents", limit=2)

        self.assertEqual(
            results[0]["url"],
            "https://learn.microsoft.com/azure/foundry/agents",
        )
        self.assertEqual(
            session.calls[1][1]["method"],
            "notifications/initialized",
        )
        self.assertEqual(session.calls[1][2]["Mcp-Session-Id"], "session-123")

    def test_client_fetches_markdown_with_discovered_input_schema(self):
        client = MicrosoftLearnMcpClient(
            "https://learn.microsoft.com/api/mcp",
            session=Session(),
        )

        content = client.fetch("https://learn.microsoft.com/azure/postgresql")

        self.assertIn("Use pgvector with relational data.", content)


if __name__ == "__main__":
    unittest.main()
