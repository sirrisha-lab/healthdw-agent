"""
Interactive CLI — run this to ask the warehouse questions in plain English.
Shows the generated SQL alongside the answer, which is what makes this a good
interview demo: nothing is hidden, you can point at exactly what it did.
"""

from .agent import ask

EXAMPLE_QUESTIONS = [
    "Which province had the longest 90th-percentile wait for knee replacement in 2024?",
    "What percentage of ED visits in Ontario resulted in hospital admission?",
    "Compare median length of stay for admitted patients across all provinces.",
    "How many total ED visits were there nationally in fiscal year 2024-2025?",
]


def main():
    print("HealthDW Q&A Agent — ask a question about ED visits or wait times.")
    print("Type 'examples' to see sample questions, or 'quit' to exit.\n")

    while True:
        question = input("Question: ").strip()
        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            break
        if question.lower() == "examples":
            for q in EXAMPLE_QUESTIONS:
                print(f"  - {q}")
            print()
            continue

        result = ask(question)

        print("\n--- SQL generated ---")
        print(result["sql"])

        if "error" in result:
            print(f"\n--- Error ---\n{result['error']}\n")
        else:
            print(f"\n--- Answer ({result['row_count']} rows returned) ---")
            print(result["answer"])
        print()


if __name__ == "__main__":
    main()
