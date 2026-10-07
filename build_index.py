from backend.ollama_client import OllamaClient
from backend.rag import RagIndex


def main() -> None:
    client = OllamaClient()
    client.assert_required_models()
    index = RagIndex(client)
    count = index.build()
    print(f"\nDone. Indexed {count} chunks into storage/index.json")


if __name__ == "__main__":
    main()
