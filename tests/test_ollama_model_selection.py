import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.config import GENERATION_CONTEXT_TOKENS
from backend.model_settings import ModelSettingsStore
from backend.ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaModelInfo,
    _json_object,
)


def _model(
    name: str,
    *,
    parameters: str = "",
    quantization: str = "",
    size: int = 0,
    compatible: bool = True,
) -> OllamaModelInfo:
    return OllamaModelInfo(
        name=name,
        parameter_size=parameters,
        quantization_level=quantization,
        size=size,
        compatible=compatible,
        compatibility_reason=(
            "Compatible local chat model."
            if compatible
            else "Not a local generation model."
        ),
    )


def _response(payload: dict) -> Mock:
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class OllamaModelSelectionTests(unittest.TestCase):
    def test_json_parser_accepts_a_markdown_fence(self) -> None:
        self.assertEqual(
            _json_object('```json\n{"status": "ok"}\n```'),
            {"status": "ok"},
        )

    def test_inventory_filters_non_local_and_non_generation_models(self) -> None:
        tags = {
            "models": [
                {
                    "name": "qwen3:8b",
                    "digest": "qwen-digest",
                    "size": 5_000,
                    "details": {
                        "family": "qwen3",
                        "parameter_size": "8B",
                        "quantization_level": "Q4_K_M",
                    },
                },
                {
                    "name": "llama3.2:3b",
                    "digest": "llama-digest",
                    "size": 2_000,
                    "details": {"family": "llama", "parameter_size": "3B"},
                },
                {"name": "nomic-embed-text:latest", "size": 1_000},
                {"name": "gpt-oss:cloud", "size": 0},
                {"name": "tiny:latest", "size": 500},
            ]
        }
        shows = {
            "qwen3:8b": {
                "capabilities": ["completion", "thinking"],
                "model_info": {"qwen3.context_length": 32_768},
            },
            "llama3.2:3b": {
                "capabilities": ["completion"],
                "model_info": {"llama.context_length": 16_384},
            },
            "nomic-embed-text:latest": {"capabilities": ["embedding"]},
            "gpt-oss:cloud": {"capabilities": ["completion"]},
            "tiny:latest": {
                "capabilities": ["completion"],
                "model_info": {"tiny.context_length": 4_096},
            },
        }
        client = OllamaClient(settings=ModelSettingsStore(Path("unused")))

        with (
            patch("backend.ollama_client.requests.get", return_value=_response(tags)),
            patch(
                "backend.ollama_client.requests.post",
                side_effect=lambda *args, **kwargs: _response(
                    shows[kwargs["json"]["model"]]
                ),
            ),
        ):
            inventory = client.list_model_details()

        by_name = {model.name: model for model in inventory}
        self.assertTrue(by_name["qwen3:8b"].compatible)
        self.assertTrue(by_name["llama3.2:3b"].compatible)
        self.assertFalse(by_name["nomic-embed-text:latest"].compatible)
        self.assertFalse(by_name["gpt-oss:cloud"].compatible)
        self.assertFalse(by_name["tiny:latest"].compatible)
        self.assertEqual(client.recommend_model(inventory), "qwen3:8b")

    def test_recommendation_prefers_largest_compatible_installed_model(self) -> None:
        models = [
            _model("llama3.2:3b", parameters="3B", size=2_000),
            _model("qwen3:8b", parameters="8B", size=5_000),
            _model("embed:latest", parameters="12B", compatible=False),
        ]

        self.assertEqual(OllamaClient.recommend_model(models), "qwen3:8b")

    def test_recommendation_uses_the_largest_model_that_fits_memory(self) -> None:
        models = [
            _model("llama3.2:3b", parameters="3B", size=2 * 1024**3),
            _model("qwen3:8b", parameters="8B", size=6 * 1024**3),
            _model("deepseek-r1:14b", parameters="14B", size=10 * 1024**3),
        ]

        self.assertEqual(
            OllamaClient.recommend_model(models, physical_memory_bytes=16 * 1024**3),
            "qwen3:8b",
        )

    def test_probe_requires_valid_structured_output(self) -> None:
        client = OllamaClient(settings=ModelSettingsStore(Path("unused")))
        model = _model("qwen3:8b", parameters="8B", size=5_000)

        with patch(
            "backend.ollama_client.requests.post",
            return_value=_response({"message": {"content": '{"status":"ok"}'}}),
        ) as post:
            result = client.probe_model("qwen3:8b", [model])

        self.assertEqual(result.status, "passed")
        self.assertGreaterEqual(result.duration_ms or 0, 0)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen3:8b")
        self.assertEqual(payload["format"]["required"], ["status"])
        self.assertNotIn("think", payload)

    def test_failed_probe_excludes_model_from_recommendation(self) -> None:
        client = OllamaClient(settings=ModelSettingsStore(Path("unused")))
        large = _model("qwen3:8b", parameters="8B", size=5_000)
        small = _model("llama3.2:3b", parameters="3B", size=2_000)

        with patch(
            "backend.ollama_client.requests.post",
            return_value=_response({"message": {"content": '{"status":"wrong"}'}}),
        ):
            with self.assertRaisesRegex(OllamaError, "structured-output test"):
                client.probe_model("qwen3:8b", [large, small])

        inventory = [
            OllamaModelInfo(
                **{
                    **large.__dict__,
                    "probe_status": "failed",
                    "probe_error": "invalid output",
                }
            ),
            small,
        ]
        self.assertEqual(OllamaClient.recommend_model(inventory), "llama3.2:3b")

    def test_selected_model_is_persisted_without_downloading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = ModelSettingsStore(Path(directory) / "settings.json")
            client = OllamaClient(settings=settings)
            inventory = [_model("llama3.2:3b"), _model("qwen3:8b")]

            selected = client.set_selected_model("qwen3:8b", inventory)

            self.assertEqual(selected, "qwen3:8b")
            self.assertEqual(client.select_llm_model(), "qwen3:8b")
            self.assertEqual(
                ModelSettingsStore(settings.path).selected_model(),
                "qwen3:8b",
            )

    def test_selection_rejects_missing_or_incompatible_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = OllamaClient(
                settings=ModelSettingsStore(Path(directory) / "settings.json")
            )
            inventory = [_model("nomic-embed-text", compatible=False)]

            with self.assertRaisesRegex(OllamaError, "not installed"):
                client.set_selected_model("missing:latest", inventory)
            with self.assertRaisesRegex(OllamaError, "Not a local generation"):
                client.set_selected_model("nomic-embed-text", inventory)

    def test_environment_override_locks_selection_and_accepts_a_base_name(self) -> None:
        inventory = [_model("qwen3:8b")]
        with patch("backend.ollama_client.LLM_MODEL", "qwen3"):
            client = OllamaClient(settings=ModelSettingsStore(Path("unused")))

            self.assertTrue(client.selection_locked)
            self.assertEqual(client.configured_model(), "qwen3")
            self.assertEqual(client.selected_model_info("qwen3", inventory), inventory[0])
            with self.assertRaisesRegex(OllamaError, "locked"):
                client.set_selected_model("qwen3:8b", inventory)

    def test_chat_uses_selected_model_and_generation_context_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = ModelSettingsStore(Path(directory) / "settings.json")
            settings.select_model("llama3.2:3b")
            client = OllamaClient(settings=settings)

            with (
                patch.object(client, "_capabilities_for_model", return_value=set()),
                patch(
                    "backend.ollama_client.requests.post",
                    return_value=_response({"message": {"content": "{}"}}),
                ) as post,
            ):
                client.chat_json("system", "user", {}, think=True)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "llama3.2:3b")
        self.assertEqual(payload["options"]["num_ctx"], GENERATION_CONTEXT_TOKENS)
        self.assertEqual(GENERATION_CONTEXT_TOKENS, 8192)
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertNotIn("think", payload)

    def test_thinking_is_requested_only_when_the_model_advertises_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = ModelSettingsStore(Path(directory) / "settings.json")
            settings.select_model("qwen3:8b")
            client = OllamaClient(settings=settings)

            with (
                patch.object(
                    client,
                    "_capabilities_for_model",
                    return_value={"completion", "thinking"},
                ),
                patch(
                    "backend.ollama_client.requests.post",
                    return_value=_response(
                        {
                            "message": {
                                "content": "{}",
                                "thinking": "private reasoning",
                            }
                        }
                    ),
                ) as post,
            ):
                result = client.chat_json("system", "user", {}, think=True)

        self.assertEqual(result, {})
        self.assertTrue(post.call_args.kwargs["json"]["think"])

    def test_no_selection_has_an_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch(
            "backend.ollama_client.LLM_MODEL", ""
        ):
            client = OllamaClient(
                settings=ModelSettingsStore(Path(directory) / "settings.json")
            )

            with self.assertRaisesRegex(OllamaError, "No local generation model"):
                client.select_llm_model()


if __name__ == "__main__":
    unittest.main()
