from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

try:
    import tiktoken
except ImportError:  # pragma: no cover - fallback for minimal environments
    tiktoken = None


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
RAG_ENV = REPO_ROOT / "rag" / ".env"
RESULTS = ROOT / "results"
RELEASE_NOTES_URL = (
    "https://raw.githubusercontent.com/kestra-io/docs/refs/heads/main/"
    "src/contents/blogs/release-1-1/index.md"
)

DEFAULT_TEXT = """\
Kestra is an open-source orchestration platform that allows you to define workflows declaratively in YAML. It enables both developers and non-developers to automate tasks through a no-code interface, while keeping everything versioned, governed, secure, and auditable. Kestra extends easily for custom use cases through plugins and custom scripts.

Kestra follows a "start simple and grow as needed" philosophy. You can schedule a basic workflow in a few minutes, then later add Python scripts, Docker containers, or complex branching logic if the situation requires it. This makes Kestra ideal for data engineering, ETL pipelines, business process automation, and more.

In LLM Zoomcamp, we learn how to build production-ready LLM applications using RAG, vector search, agents, and evaluation. In this bonus module, we're exploring how AI can accelerate workflow development through AI Copilot, RAG, and autonomous agents.
"""


@dataclass
class LlmResult:
    name: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    visible_output_tokens: int
    text: str


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def visible_token_count(text: str) -> int:
    if tiktoken is not None:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    return len(re.findall(r"\w+|[^\w\s]", text))


def ollama_native_url(openai_base_url: str) -> str:
    return re.sub(r"/v1/?$", "", openai_base_url.rstrip("/"))


def call_llm(
    ollama_url: str,
    model: str,
    name: str,
    messages: list[dict[str, str]],
    max_tokens: int = 700,
) -> LlmResult:
    response = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_predict": max_tokens,
            },
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    text = payload.get("message", {}).get("content", "")
    return LlmResult(
        name=name,
        model=model,
        prompt_tokens=payload.get("prompt_eval_count"),
        completion_tokens=payload.get("eval_count"),
        total_tokens=(
            payload.get("prompt_eval_count", 0) + payload.get("eval_count", 0)
            if payload.get("prompt_eval_count") is not None
            and payload.get("eval_count") is not None
            else None
        ),
        visible_output_tokens=visible_token_count(text),
        text=text,
    )


def summarize_messages(summary_length: str, text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": textwrap.dedent(
                f"""\
                You are a precise technical assistant.
                Produce a {summary_length} summary in en.
                Keep it factual, remove fluff, and avoid marketing language.
                If the input is empty or non-text, return a one-sentence explanation.

                Output format guidelines:
                - For 'short': 1-2 sentences
                - For 'medium': 2-5 sentences
                - For 'long': 1-3 paragraphs
                """
            ),
        },
        {"role": "user", "content": f"Summarize the following content: {text}"},
    ]


def english_brevity_messages(summary: str, sentences: int) -> list[dict[str, str]]:
    return [
        {
            "role": "user",
            "content": (
                f"Generate exactly {sentences} sentence"
                f"{'' if sentences == 1 else 's'} English summary of the following:\n"
                f'"{summary}"'
            ),
        }
    ]


def main() -> None:
    load_env_file(RAG_ENV)

    base_url = os.environ.get("OPENAI_BASE_URL", "http://100.114.202.116:11434/v1")
    model = os.environ.get("OPENAI_MODEL", "qwen3.5:4b")

    ollama_url = ollama_native_url(base_url)
    results: list[LlmResult] = []

    q2_prompt = (
        "Which features were released in Kestra 1.1?\n"
        "Please list at least 5 major features with brief descriptions."
    )
    results.append(
        call_llm(
            ollama_url,
            model,
            "q2_without_rag",
            [{"role": "user", "content": q2_prompt}],
        )
    )

    release_notes = requests.get(RELEASE_NOTES_URL, timeout=30).text
    rag_context = release_notes[:12000]
    results.append(
        call_llm(
            ollama_url,
            model,
            "q2_with_rag_context",
            [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that answers questions about Kestra. "
                        "Use the provided release-note context. If the information is not "
                        "in the context, say so.\n\n"
                        f"Context:\n{rag_context}"
                    ),
                },
                {"role": "user", "content": q2_prompt},
            ],
        )
    )

    short = call_llm(
        ollama_url,
        model,
        "q3_multilingual_agent_short",
        summarize_messages("short", DEFAULT_TEXT),
    )
    results.append(short)

    long = call_llm(
        ollama_url,
        model,
        "q4_multilingual_agent_long",
        summarize_messages("long", DEFAULT_TEXT),
        max_tokens=1000,
    )
    results.append(long)

    q5_one_sentence = call_llm(
        ollama_url,
        model,
        "q5_english_brevity_long_one_sentence",
        english_brevity_messages(long.text, 1),
    )
    results.append(q5_one_sentence)

    q5_three_sentences = call_llm(
        ollama_url,
        model,
        "q5_english_brevity_long_three_sentences",
        english_brevity_messages(long.text, 3),
    )
    results.append(q5_three_sentences)

    RESULTS.mkdir(exist_ok=True)
    payload = {
        "base_url": base_url,
        "model": model,
        "note": (
            "The script uses Ollama native /api/chat with think:false. "
            "completion_tokens is Ollama eval_count; visible_output_tokens is a "
            "cl100k_base estimate for the returned text."
        ),
        "results": [asdict(result) for result in results],
    }
    (RESULTS / "homework_ollama_results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )

    for result in results:
        print(f"\n## {result.name}")
        print(f"model={result.model}")
        print(
            "usage: "
            f"prompt={result.prompt_tokens}, "
            f"completion={result.completion_tokens}, "
            f"total={result.total_tokens}, "
            f"visible_output={result.visible_output_tokens}"
        )
        print(result.text)


if __name__ == "__main__":
    main()
