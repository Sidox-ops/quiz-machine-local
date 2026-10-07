import unittest
from unittest.mock import patch

from backend.config import DEFAULT_LLM_MODEL, GENERATION_CONTEXT_TOKENS
from backend.ollama_client import OllamaClient, _json_object, first_chat_model


class OllamaModelSelectionTests(unittest.TestCase):
    def test_json_parser_accepts_a_markdown_fence(self) -> None:
        self.assertEqual(_json_object('```json\n{"status": "ok"}\n```'), {"status": "ok"})

    def test_first_chat_model_skips_embedding_models(self) -> None:
        models = ["nomic-embed-text:latest", "deepseek-r1:14b", "qwen3:8b"]

        self.assertEqual(first_chat_model(models), "deepseek-r1:14b")

    def test_select_llm_model_uses_configured_default_not_inventory_order(self) -> None:
        client = OllamaClient()

        self.assertEqual(
            client.select_llm_model(["nomic-embed-text:latest", "deepseek-r1:14b"]),
            DEFAULT_LLM_MODEL,
        )
        self.assertEqual(DEFAULT_LLM_MODEL, "gemma4:e4b-mlx")

    def test_chat_uses_generation_context_window(self) -> None:
        client = OllamaClient()

        with (
            patch.object(client, "select_llm_model", return_value="gemma4:e4b-mlx"),
            patch("backend.ollama_client.requests.post") as post,
        ):
            post.return_value.json.return_value = {"message": {"content": "{}"}}
            client.chat_json("system", "user", {})

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["options"]["num_ctx"], GENERATION_CONTEXT_TOKENS)
        self.assertEqual(GENERATION_CONTEXT_TOKENS, 8192)
        self.assertEqual(payload["options"]["temperature"], 0)

    def test_validation_can_enable_thinking_without_persisting_it(self) -> None:
        client = OllamaClient()

        with patch("backend.ollama_client.requests.post") as post:
            post.return_value.json.return_value = {
                "message": {"content": "{}", "thinking": "private reasoning"}
            }
            result = client.chat_json("system", "user", {}, think=True)

        self.assertEqual(result, {})
        self.assertTrue(post.call_args.kwargs["json"]["think"])


if __name__ == "__main__":
    unittest.main()
