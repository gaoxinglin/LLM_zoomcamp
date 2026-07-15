"""Run the instrumented FAQ agent for Question 1."""

import argparse

from dotenv import load_dotenv

load_dotenv()

from observability import configure_observability

configure_observability()

HOMEWORK_QUESTION = "How do I run Ollama locally?"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=HOMEWORK_QUESTION)
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()

    from agent import SearchDeps, faq_agent
    from ingest import build_index, load_faq_data

    deps = SearchDeps(index=build_index(load_faq_data()))
    for run in range(1, args.runs + 1):
        result = faq_agent.run_sync(args.question, deps=deps)
        print(f"Run {run}: {result.output}")

    import logfire

    logfire.force_flush()


if __name__ == "__main__":
    main()
