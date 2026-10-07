from __future__ import annotations

from typing import Any

import json
import requests

from .config import (
    DEFAULT_LLM_MODEL,
    EMBEDDING_MODEL,
    GENERATION_CONTEXT_TOKENS,
    GENERATION_TEMPERATURE,
    LLM_MODEL,
    OLLAMA_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
)


class OllamaError(RuntimeError):
    pass


def model_matches(required: str, available: str) -> bool:
    return available == required or available.startswith(f"{required}:")


def first_chat_model(models: list[str]) -> str | None:
    for name in models:
        normalized = name.lower()
        if not name:
            continue
        if model_matches(EMBEDDING_MODEL, name):
            continue
        if "embed" in normalized:
            continue
        return name
    return None


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def list_models(self) -> list[str]:
        try:
            response = requests.get(
                f"{self.base_url}/api/tags", timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            payload = response.json()
            return [m.get("name", "") for m in payload.get("models", [])]
        except requests.RequestException as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.base_url}. Is `ollama serve` running?"
            ) from exc

    def select_llm_model(self, models: list[str] | None = None) -> str:
        # The default is deliberate: model ordering in `/api/tags` must not silently
        # switch the quiz pipeline to an unrelated locally installed model.
        return LLM_MODEL or DEFAULT_LLM_MODEL

    def assert_required_models(self, *, require_embedding: bool = True) -> None:
        models = self.list_models()
        missing = []
        required_models = [self.select_llm_model(models)]
        if require_embedding:
            required_models.insert(0, EMBEDDING_MODEL)
        for required in required_models:
            if not any(model_matches(required, name) for name in models):
                missing.append(required)
        if missing:
            raise OllamaError(
                "Missing Ollama model(s): " + ", ".join(missing) + ". Pull them first."
            )

    def pull_model(self, model: str) -> None:
        """Ask the already-running local Ollama service to install a model."""
        try:
            with requests.post(
                f"{self.base_url}/api/pull",
                json={"model": model, "stream": False},
                timeout=3600,
                stream=False,
            ) as response:
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "success":
                    raise OllamaError(
                        f"Ollama could not install {model}: {payload.get('error') or payload}"
                    )
        except requests.RequestException as exc:
            raise OllamaError(f"Model download failed for {model}: {exc}") from exc

    def embed(self, inputs: str | list[str]) -> list[list[float]]:
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": EMBEDDING_MODEL,
                    "input": inputs,
                    "truncate": True,
                    "keep_alive": "10m",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            embeddings = payload.get("embeddings")
            if not embeddings:
                raise OllamaError("Ollama returned no embeddings.")
            return embeddings
        except requests.RequestException as exc:
            raise OllamaError(f"Embedding request failed: {exc}") from exc

    def chat_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        think: bool | str = False,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.select_llm_model(),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": schema,
                    "stream": False,
                    "think": think,
                    "keep_alive": "10m",
                    "options": {
                        "num_ctx": GENERATION_CONTEXT_TOKENS,
                        "temperature": (
                            GENERATION_TEMPERATURE
                            if temperature is None
                            else temperature
                        ),
                    },
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("message", {}).get("content", "")
            if not content:
                raise OllamaError("Ollama returned an empty chat response.")
            try:
                return _json_object(content)
            except ValueError as exc:
                raise OllamaError(f"Model did not return valid JSON: {content[:500]}") from exc
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            detail = response.text.strip()[:1000] if response is not None else ""
            suffix = f" Response: {detail}" if detail else ""
            raise OllamaError(f"Chat request failed: {exc}.{suffix}") from exc


def _json_object(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(content[start:])
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object.")
    return value
