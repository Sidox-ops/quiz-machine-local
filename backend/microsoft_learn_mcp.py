from __future__ import annotations

import json
from typing import Any

import requests

_PROTOCOL_VERSION = "2025-03-26"


class MicrosoftLearnMcpClient:
    """Small Streamable HTTP client for the public Microsoft Learn MCP server."""

    def __init__(
        self,
        endpoint: str,
        timeout: int = 60,
        session: requests.Session | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self._http = session or requests.Session()
        self._id = 0
        self._session_id: str | None = None
        self._tools: dict[str, dict[str, Any]] = {}

    def search(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        self._initialize()
        tool = self._tools.get("microsoft_docs_search")
        if tool is None:
            raise RuntimeError("Microsoft Learn MCP document search is unavailable")
        arguments: dict[str, Any] = {"query": query}
        properties = tool.get("inputSchema", {}).get("properties", {})
        if "max_results" in properties:
            arguments["max_results"] = min(limit, 10)
        rows = _rows(
            self._request(
                "tools/call",
                {"name": "microsoft_docs_search", "arguments": arguments},
            ).get("content", [])
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            url = (
                row.get("url")
                or row.get("contentUrl")
                or row.get("source_url")
                or row.get("sourceUrl")
            )
            if not isinstance(url, str) or not url.startswith(
                "https://learn.microsoft.com/"
            ):
                continue
            results.append({**row, "url": url})
        return results[:limit]

    def fetch(self, url: str) -> str | None:
        """Fetch a full Learn page when the dynamically advertised tool supports it."""
        self._initialize()
        tool = self._tools.get("microsoft_docs_fetch")
        if tool is None:
            return None
        properties = tool.get("inputSchema", {}).get("properties", {})
        url_key = next(
            (key for key in ("url", "uri") if key in properties),
            None,
        )
        if url_key is None:
            return None
        result = self._request(
            "tools/call",
            {"name": "microsoft_docs_fetch", "arguments": {url_key: url}},
        )
        return _document_text(result.get("content", []))

    def test_connection(self) -> None:
        self._initialize()
        if "microsoft_docs_search" not in self._tools:
            raise RuntimeError("Microsoft Learn MCP document search is unavailable")

    def _initialize(self) -> None:
        if self._tools:
            return
        initialized = self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "quiz-machine-local",
                    "version": "1",
                },
            },
        )
        if initialized.get("protocolVersion") != _PROTOCOL_VERSION:
            raise RuntimeError("Microsoft Learn MCP protocol negotiation failed")
        self._notification("notifications/initialized", {})
        self._tools = {
            str(tool["name"]): tool
            for tool in self._request("tools/list", {}).get("tools", [])
            if isinstance(tool, dict) and tool.get("name")
        }

    def _notification(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        request_id = self._id
        messages = self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        message = next(
            (item for item in messages if item.get("id") == request_id),
            None,
        )
        if message is None:
            raise RuntimeError("Microsoft Learn MCP returned no response")
        if "error" in message:
            raise RuntimeError(str(message["error"]))
        result = message.get("result", {})
        if not isinstance(result, dict):
            raise RuntimeError("Microsoft Learn MCP returned an invalid result")
        return result

    def _send(self, payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": _PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        response = self._http.post(
            self.endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id
        return _decode_payloads(response.text, response.headers.get("Content-Type", ""))


def _decode_payloads(raw: str, content_type: str) -> tuple[dict[str, Any], ...]:
    if not raw.strip():
        return ()
    values: list[Any] = []
    if "text/event-stream" in content_type:
        data_lines: list[str] = []
        for line in raw.splitlines():
            if not line.strip() and data_lines:
                values.append(json.loads("\n".join(data_lines)))
                data_lines = []
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            values.append(json.loads("\n".join(data_lines)))
    else:
        values.append(json.loads(raw))
    return tuple(item for item in values if isinstance(item, dict))


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and value.get("type") == "text":
        try:
            return _rows(json.loads(str(value.get("text", ""))))
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        for key in ("results", "items", "documents"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
        return [value]
    if isinstance(value, list):
        rows: list[dict[str, Any]] = []
        for item in value:
            rows.extend(_rows(item))
        return rows
    return []


def _document_text(value: Any) -> str | None:
    if isinstance(value, dict) and value.get("type") == "text":
        raw = str(value.get("text", "")).strip()
        if not raw:
            return None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        return _document_text(decoded)
    if isinstance(value, dict):
        for key in ("content", "markdown", "text", "body"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
        for key in ("result", "document", "page"):
            nested = _document_text(value.get(key))
            if nested:
                return nested
        return None
    if isinstance(value, list):
        blocks = [text for item in value if (text := _document_text(item))]
        return "\n\n".join(blocks) or None
    if isinstance(value, str):
        return value.strip() or None
    return None
