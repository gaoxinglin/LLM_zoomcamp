import argparse
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from gitsource import GithubRepositoryDataReader, chunk_documents
from minsearch import Index
from openai import OpenAI
from pydantic_ai import Agent


QUERY = "How does the agentic loop keep calling the model until it stops?"
AGENT_QUERY = "How does the agentic loop work, and how is it different from plain RAG?"
MODEL = "gpt-5.4-mini"


def load_lesson_documents() -> list[dict[str, str]]:
    reader = GithubRepositoryDataReader(
        repo_owner="DataTalksClub",
        repo_name="llm-zoomcamp",
        commit_id="8c1834d",
        allowed_extensions={"md"},
        filename_filter=lambda path: "/lessons/" in path,
    )
    return [file.parse() for file in reader.read()]


def build_index(documents: list[dict[str, str]]) -> Index:
    return Index(
        text_fields=["content"],
        keyword_fields=["filename"],
    ).fit(documents)


def search(index: Index, query: str, num_results: int = 5) -> list[dict]:
    return index.search(query, num_results=num_results)


def build_context(results: list[dict]) -> str:
    return "\n\n".join(
        f"Filename: {document['filename']}\n"
        f"Content:\n{document['content']}"
        for document in results
    )


@dataclass
class RagResult:
    answer: str
    input_tokens: int


def rag(index: Index, query: str) -> RagResult:
    context = build_context(search(index, query))
    prompt = f"""Answer the QUESTION using only the CONTEXT.

QUESTION:
{query}

CONTEXT:
{context}
"""

    response = OpenAI().responses.create(
        model=MODEL,
        input=prompt,
    )
    return RagResult(
        answer=response.output_text,
        input_tokens=response.usage.input_tokens,
    )


def run_agent(chunk_index: Index) -> tuple[str, int]:
    call_count = 0

    def search_lessons(query: str) -> list[dict]:
        """Search course lessons for information relevant to the query."""
        nonlocal call_count
        call_count += 1
        return search(chunk_index, query)

    agent = Agent(
        f"openai:{MODEL}",
        instructions=(
            "You're a course teaching assistant. Answer the student's question "
            "using the search tool. Make multiple searches with different "
            "keywords before answering."
        ),
        tools=[search_lessons],
    )
    result = agent.run_sync(AGENT_QUERY)
    return result.output, call_count


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Zoomcamp homework 1")
    parser.add_argument(
        "question",
        choices=["q1", "q2", "q3", "q4", "q5", "q6", "all"],
        nargs="?",
        default="all",
    )
    args = parser.parse_args()

    load_dotenv()
    documents = load_lesson_documents()
    document_index = build_index(documents)

    if args.question in {"q1", "all"}:
        print(f"Q1 lesson pages: {len(documents)}")

    if args.question in {"q2", "all"}:
        first_result = search(document_index, QUERY, num_results=1)[0]
        print(f"Q2 first result: {first_result['filename']}")

    full_result = None
    if args.question in {"q3", "q5", "all"}:
        require_openai_key()
        full_result = rag(document_index, QUERY)

    if args.question in {"q3", "all"}:
        print(f"Q3 input tokens: {full_result.input_tokens}")
        print(f"Q3 answer: {full_result.answer}")

    chunks = chunk_documents(documents, size=2000, step=1000)

    if args.question in {"q4", "all"}:
        print(f"Q4 chunks: {len(chunks)}")

    chunk_index = None
    if args.question in {"q5", "q6", "all"}:
        chunk_index = build_index(chunks)

    if args.question in {"q5", "all"}:
        chunk_result = rag(chunk_index, QUERY)
        ratio = full_result.input_tokens / chunk_result.input_tokens
        print(f"Q5 chunked input tokens: {chunk_result.input_tokens}")
        print(f"Q5 reduction: {ratio:.1f}x fewer input tokens")
        print(f"Q5 answer: {chunk_result.answer}")

    if args.question in {"q6", "all"}:
        require_openai_key()
        answer, call_count = run_agent(chunk_index)
        print(f"Q6 search calls: {call_count}")
        print(f"Q6 answer: {answer}")


def require_openai_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is required for Q3, Q5, and Q6. "
            "Put it in rag/.env or export it in your shell."
        )


if __name__ == "__main__":
    main()
