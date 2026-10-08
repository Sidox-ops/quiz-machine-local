import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.ollama_client import OllamaModelInfo
from backend.rag import RagIndex
from backend.system_setup import SetupManager


class _Client:
    def __init__(self, selected: str = "qwen3:8b"):
        self.selected = selected
        self.list_calls = 0
        self.probe_calls: list[str] = []

    def list_models(self) -> list[str]:
        self.list_calls += 1
        return ["qwen3:8b"]

    def list_model_details(self) -> list[OllamaModelInfo]:
        return [
            OllamaModelInfo(
                name="qwen3:8b",
                compatible=True,
                compatibility_reason="Compatible local chat model.",
            )
        ]

    def configured_model(self) -> str:
        return self.selected

    def probe_model(
        self,
        name: str,
        models: list[OllamaModelInfo],
    ) -> None:
        self.probe_calls.append(name)

    def selected_model_info(
        self,
        selected: str,
        models: list[OllamaModelInfo],
    ) -> OllamaModelInfo | None:
        return next((model for model in models if model.name == selected), None)


class _Rag:
    requires_local_embeddings = False
    uses_microsoft_learn = True
    has_scoped_local_corpus = False

    def __init__(self):
        self.test_calls = 0
        self.build_calls = 0

    def test_knowledge_provider(self) -> None:
        self.test_calls += 1

    def build(self) -> None:
        self.build_calls += 1


class SetupManagerTests(unittest.TestCase):
    def test_microsoft_learn_cache_does_not_replace_the_connection_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rag = RagIndex(
                _Client(),
                path=root / "index.json",
                knowledge_provider="microsoft_learn_mcp",
                microsoft_corpus_path=root / "microsoft.json",
            )

            self.assertFalse(rag.knowledge_check_completed)
            with patch.object(rag.microsoft_learn, "test_connection") as check:
                rag.test_knowledge_provider()

            check.assert_called_once_with()
            self.assertTrue(rag.knowledge_check_completed)

    @patch("backend.system_setup.find_ollama", return_value="/usr/local/bin/ollama")
    def test_setup_checks_installed_model_and_mcp_without_downloading(
        self,
        _find_ollama,
    ) -> None:
        client = _Client()
        rag = _Rag()
        manager = SetupManager(client, rag)

        manager._run()

        self.assertEqual(manager.state()["status"], "completed")
        self.assertEqual(client.list_calls, 1)
        self.assertEqual(client.probe_calls, ["qwen3:8b"])
        self.assertEqual(rag.test_calls, 1)
        self.assertEqual(rag.build_calls, 0)
        self.assertFalse(hasattr(client, "pull_model"))

    @patch("backend.system_setup.find_ollama", return_value="/usr/local/bin/ollama")
    def test_setup_requires_an_explicit_installed_model_selection(
        self,
        _find_ollama,
    ) -> None:
        manager = SetupManager(_Client(selected=""), _Rag())

        manager._run()

        state = manager.state()
        self.assertEqual(state["status"], "failed")
        self.assertIn("Choose one of the installed", state["message"])


if __name__ == "__main__":
    unittest.main()
