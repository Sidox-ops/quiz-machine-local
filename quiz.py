from __future__ import annotations

from backend.ollama_client import OllamaClient
from backend.progress import ProgressStore
from backend.question_store import QuestionStore
from backend.quiz_engine import QuizEngine
from backend.rag import RagIndex


def main() -> None:
    client = OllamaClient()
    rag = RagIndex(client)
    client.assert_required_models(require_embedding=not rag.uses_microsoft_learn)
    if not rag.uses_microsoft_learn and not rag.items:
        raise SystemExit("Index missing. Run `python build_index.py` first.")

    progress = ProgressStore()
    engine = QuizEngine(client, rag, progress, QuestionStore())

    print(f"\nAI-103 LOCAL QUIZ — {client.select_llm_model()} + nomic-embed-text")
    print("Shuffle mode is ON: random chapters + random difficulty + balanced answer positions.")
    print("Type A/B/C/D, `p` for progress, or `q` to quit.\n")

    while True:
        question = engine.generate(mode="shuffle", difficulty="random")
        print("=" * 78)
        print(f"[{question.domain}]  {question.topic}  •  {question.difficulty}")
        print(f"Sources: {', '.join(question.supporting_source_ids)}\n")
        print(question.question)
        for index, option in enumerate(question.options):
            print(f"  {chr(65 + index)}. {option.text}")

        while True:
            answer = input("\nYour answer: ").strip().upper()
            if answer == "Q":
                return
            if answer == "P":
                print(progress.load())
                continue
            if answer in {"A", "B", "C", "D"}:
                break
            print("Enter A, B, C, D, p or q.")

        selected_option_id = question.options[ord(answer) - ord("A")].id
        result = engine.answer(question.question_id, selected_option_id)
        icon = "✓" if result["correct"] else "✗"
        correct_index = next(
            index
            for index, option in enumerate(question.options)
            if option.id == result["correct_option_id"]
        )
        print(f"\n{icon} Correct answer: {chr(65 + correct_index)}")
        print(result["explanation"])
        print("\nOption review:")
        labels = {
            option.id: chr(65 + index)
            for index, option in enumerate(question.options)
        }
        for item in result["option_explanations"]:
            print(f"  {labels[item['option_id']]}: {item['explanation']}")
        stats = result["progress"]
        print(f"\nScore: {stats['correct']}/{stats['asked']} ({stats['accuracy']:.0%})\n")
        input("Press Enter for the next shuffled question...")


if __name__ == "__main__":
    main()
