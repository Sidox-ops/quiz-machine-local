from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import (
    EMBEDDING_MODEL,
    GENERATION_CONTEXT_TOKENS,
    GENERATION_TEMPERATURE,
    LLM_MODEL,
    MODEL_PROBE_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
)
from .model_settings import ModelSettingsStore


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelProbeResult:
    status: str = "not_run"
    duration_ms: int | None = None
    error: str = ""


@dataclass(frozen=True)
class OllamaModelInfo:
    name: str
    digest: str = ""
    size: int = 0
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""
    capabilities: tuple[str, ...] = ()
    context_length: int | None = None
    license: str = ""
    compatible: bool = False
    compatibility_reason: str = ""
    probe_status: str = "not_run"
    probe_duration_ms: int | None = None
    probe_error: str = ""

    @property
    def estimated_memory_bytes(self) -> int:
        if self.size <= 0:
            return 0
        return int(self.size * 1.35 + 512 * 1024**2)

    def fits_memory(self, physical_memory_bytes: int | None) -> bool | None:
        if not physical_memory_bytes or not self.estimated_memory_bytes:
            return None
        return self.estimated_memory_bytes <= int(physical_memory_bytes * 0.70)

    def public_payload(
        self,
        *,
        selected: bool,
        recommended: bool,
        physical_memory_bytes: int | None = None,
    ) -> dict:
        return {
            "name": self.name,
            "digest": self.digest,
            "size": self.size,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
            "capabilities": list(self.capabilities),
            "context_length": self.context_length,
            "license": self.license,
            "compatible": self.compatible,
            "compatibility_reason": self.compatibility_reason,
            "estimated_memory_bytes": self.estimated_memory_bytes,
            "fits_memory": self.fits_memory(physical_memory_bytes),
            "probe_status": self.probe_status,
            "probe_duration_ms": self.probe_duration_ms,
            "probe_error": self.probe_error,
            "selected": selected,
            "recommended": recommended,
        }


def model_matches(required: str, available: str) -> bool:
    return available == required or available.startswith(f"{required}:")


def _parameter_count(value: str) -> float:
    match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmbt]?)\s*",
        value.lower(),
    )
    if not match:
        return 0
    multiplier = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
    return float(match.group(1)) * multiplier[match.group(2)]


def _quantization_bits(value: str) -> int:
    match = re.search(r"(?:^|_)q([0-9]+)", value.lower())
    return int(match.group(1)) if match else 0


class OllamaClient:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        settings: ModelSettingsStore | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.settings = settings or ModelSettingsStore()
        self._show_cache: dict[str, tuple[str, dict[str, Any]]] = {}
        self._probe_cache: dict[str, tuple[str, ModelProbeResult]] = {}

    def _model_payloads(self) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.base_url}/api/tags", timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            payload = response.json()
            values = payload.get("models", []) if isinstance(payload, dict) else []
            return [item for item in values if isinstance(item, dict)]
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.base_url}. Is `ollama serve` running?"
            ) from exc

    def list_models(self) -> list[str]:
        return [
            str(item.get("name") or item.get("model") or "")
            for item in self._model_payloads()
            if item.get("name") or item.get("model")
        ]

    def _show_model(self, name: str, digest: str | None = None) -> dict[str, Any]:
        cached = self._show_cache.get(name)
        if cached and (digest is None or cached[0] == digest):
            return cached[1]
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"model": name, "verbose": False},
                timeout=min(REQUEST_TIMEOUT_SECONDS, 10),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                payload = {}
        except (requests.RequestException, ValueError, TypeError):
            payload = {}
        self._show_cache[name] = (digest or "", payload)
        return payload

    def list_model_details(self) -> list[OllamaModelInfo]:
        result = []
        for item in self._model_payloads():
            name = str(item.get("name") or item.get("model") or "").strip()
            if not name:
                continue
            digest = str(item.get("digest") or "")
            shown = self._show_model(name, digest)
            item_details = item.get("details")
            shown_details = shown.get("details")
            details = dict(item_details) if isinstance(item_details, dict) else {}
            if isinstance(shown_details, dict):
                details.update(shown_details)
            raw_capabilities = shown.get("capabilities")
            capabilities = tuple(
                sorted(
                    str(value).casefold()
                    for value in (
                        raw_capabilities if isinstance(raw_capabilities, list) else []
                    )
                    if value
                )
            )
            raw_model_info = shown.get("model_info")
            model_info = raw_model_info if isinstance(raw_model_info, dict) else {}
            context_lengths = [
                int(value)
                for key, value in model_info.items()
                if str(key).endswith(".context_length")
                and isinstance(value, (int, float))
            ]
            context_length = max(context_lengths) if context_lengths else None
            family = str(details.get("family") or "")
            normalized = f"{name} {family}".casefold()
            tag = name.rsplit(":", 1)[-1].casefold()
            is_cloud = tag == "cloud" or tag.endswith("-cloud")
            is_embedding = (
                "embed" in normalized
                or ("embedding" in capabilities and "completion" not in capabilities)
            )
            if is_cloud:
                compatible = False
                reason = "Cloud-backed Ollama models are excluded from local inference."
            elif is_embedding:
                compatible = False
                reason = "Embedding models cannot generate quiz questions."
            elif capabilities and "completion" not in capabilities:
                compatible = False
                reason = "The model does not advertise text completion support."
            elif context_length and context_length < GENERATION_CONTEXT_TOKENS:
                compatible = False
                reason = (
                    f"The model context is {context_length} tokens; "
                    f"Quiz Machine requires {GENERATION_CONTEXT_TOKENS}."
                )
            else:
                compatible = True
                reason = (
                    "Compatible local chat model."
                    if capabilities
                    else "Compatibility inferred from local Ollama metadata."
                )
            license_text = str(shown.get("license") or "")
            license_name = next(
                (line.strip() for line in license_text.splitlines() if line.strip()),
                "",
            )[:160]
            cached_probe = self._probe_cache.get(name)
            probe = (
                cached_probe[1]
                if cached_probe and (not digest or cached_probe[0] == digest)
                else ModelProbeResult()
            )
            result.append(
                OllamaModelInfo(
                    name=name,
                    digest=digest,
                    size=int(item.get("size") or 0),
                    family=family,
                    parameter_size=str(details.get("parameter_size") or ""),
                    quantization_level=str(details.get("quantization_level") or ""),
                    capabilities=capabilities,
                    context_length=context_length,
                    license=license_name,
                    compatible=compatible,
                    compatibility_reason=reason,
                    probe_status=probe.status,
                    probe_duration_ms=probe.duration_ms,
                    probe_error=probe.error,
                )
            )
        return result

    @staticmethod
    def recommend_model(
        models: list[OllamaModelInfo],
        physical_memory_bytes: int | None = None,
    ) -> str | None:
        compatible = [
            model
            for model in models
            if model.compatible and model.probe_status != "failed"
        ]
        if not compatible:
            return None
        memory_fit = [
            model
            for model in compatible
            if model.fits_memory(physical_memory_bytes) is not False
        ]
        candidates = memory_fit or compatible
        return max(
            candidates,
            key=lambda model: (
                model.probe_status == "passed",
                _parameter_count(model.parameter_size),
                _quantization_bits(model.quantization_level),
                model.size,
                model.name.casefold(),
            ),
        ).name

    def probe_model(
        self,
        name: str,
        models: list[OllamaModelInfo] | None = None,
    ) -> ModelProbeResult:
        inventory = models if models is not None else self.list_model_details()
        selected = next((model for model in inventory if model.name == name), None)
        if selected is None:
            raise OllamaError(f"Ollama model is not installed: {name}")
        if not selected.compatible:
            raise OllamaError(selected.compatibility_reason)

        cached = self._probe_cache.get(selected.name)
        if cached and (not selected.digest or cached[0] == selected.digest):
            if cached[1].status == "passed":
                return cached[1]

        schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["ok"]}},
            "required": ["status"],
            "additionalProperties": False,
        }
        started = time.monotonic()
        try:
            request_payload: dict[str, Any] = {
                "model": selected.name,
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only the requested JSON object.",
                    },
                    {"role": "user", "content": "Confirm readiness with status ok."},
                ],
                "format": schema,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "num_ctx": min(
                        selected.context_length or GENERATION_CONTEXT_TOKENS,
                        GENERATION_CONTEXT_TOKENS,
                    ),
                    "num_predict": 24,
                    "temperature": 0,
                },
            }
            if "thinking" in selected.capabilities:
                request_payload["think"] = False
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_payload,
                timeout=MODEL_PROBE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("message", {}).get("content", "")
            parsed = _json_object(content)
            if parsed != {"status": "ok"}:
                raise ValueError("unexpected structured response")
        except (requests.RequestException, ValueError, TypeError) as exc:
            duration_ms = round((time.monotonic() - started) * 1000)
            result = ModelProbeResult(
                status="failed",
                duration_ms=duration_ms,
                error=(
                    "The model failed Quiz Machine's local structured-output test: "
                    f"{str(exc)[:300]}"
                ),
            )
            self._probe_cache[selected.name] = (selected.digest, result)
            raise OllamaError(result.error) from exc

        result = ModelProbeResult(
            status="passed",
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        self._probe_cache[selected.name] = (selected.digest, result)
        return result

    @property
    def selection_locked(self) -> bool:
        return bool(LLM_MODEL)

    def configured_model(self) -> str:
        return LLM_MODEL or self.settings.selected_model()

    @staticmethod
    def selected_model_info(
        selected: str,
        models: list[OllamaModelInfo],
    ) -> OllamaModelInfo | None:
        return next(
            (
                model
                for model in models
                if model.name == selected or model_matches(selected, model.name)
            ),
            None,
        )

    def set_selected_model(
        self,
        name: str,
        models: list[OllamaModelInfo] | None = None,
    ) -> str:
        if self.selection_locked:
            raise OllamaError(
                "The model is locked by QUIZ_MACHINE_LLM_MODEL. Change that "
                "environment variable before selecting a model in the app."
            )
        inventory = models if models is not None else self.list_model_details()
        selected = next((model for model in inventory if model.name == name), None)
        if selected is None:
            raise OllamaError(f"Ollama model is not installed: {name}")
        if not selected.compatible:
            raise OllamaError(selected.compatibility_reason)
        self.settings.select_model(selected.name)
        return selected.name

    def select_llm_model(self, models: list[str] | None = None) -> str:
        selected = self.configured_model()
        if not selected:
            raise OllamaError(
                "No local generation model is selected. Choose an installed "
                "Ollama model in Quiz Machine settings."
            )
        return selected

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
                "Missing Ollama model(s): "
                + ", ".join(missing)
                + ". Install them in Ollama, then check again. Quiz Machine does "
                "not download models automatically."
            )

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
            selected_model = self.select_llm_model()
            payload: dict[str, Any] = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "num_ctx": GENERATION_CONTEXT_TOKENS,
                    "temperature": (
                        GENERATION_TEMPERATURE
                        if temperature is None
                        else temperature
                    ),
                },
            }
            if think and "thinking" in self._capabilities_for_model(selected_model):
                payload["think"] = think
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
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

    def _capabilities_for_model(self, model: str) -> set[str]:
        payload = self._show_model(model)
        raw_capabilities = payload.get("capabilities")
        return {
            str(value).casefold()
            for value in (
                raw_capabilities if isinstance(raw_capabilities, list) else []
            )
            if value
        }


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
