from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import requests
from gitsource import GithubRepositoryDataReader, chunk_documents
from minsearch import Index, VectorSearch


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
RAG_ENV = REPO_ROOT / "rag" / ".env"
GROUND_TRUTH_PATH = ROOT / "data" / "ground-truth.csv"
RESULTS_DIR = ROOT / "results"

sys.path.insert(0, str(REPO_ROOT / "vector"))
from embedder import Embedder  # noqa: E402


DATA_GEN_INSTRUCTIONS = """
You emulate a student who is taking our LLM course.
You are given one lesson page from the course.
Formulate 5 questions this student might ask that are answered by this page.

Rules:
- The page should contain the answer to each question.
- Make the questions complete and not too short.
- Use as few words as possible from the page; don't copy its phrasing.
- The questions should resemble how people actually ask things online:
  not too formal, not too short, not too long.
- Ask about the content of the lesson, not about its formatting or filename.

Return JSON only, with this shape:
{"questions": ["question 1", "question 2", "question 3", "question 4", "question 5"]}
""".strip()


@dataclass
class OllamaResult:
    questions: list[str]
    input_tokens: int
    output_tokens: int
    raw_text: str


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def ollama_base_url() -> str:
    load_env_file(RAG_ENV)
    base_url = os.environ.get("OPENAI_BASE_URL", "http://100.114.202.116:11434/v1")
    return re.sub(r"/v1/?$", "", base_url.rstrip("/"))


def ollama_model() -> str:
    load_env_file(RAG_ENV)
    return os.environ.get("OPENAI_MODEL", "qwen3.5:4b")


def extract_json_object(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def extract_questions(text: str) -> list[str]:
    try:
        parsed = extract_json_object(text)
        questions = parsed.get("questions", [])
        if isinstance(questions, list):
            return [str(question) for question in questions]
    except json.JSONDecodeError:
        pass

    return re.findall(r'"([^"\n]+\?)"', text)


def call_ollama_question_generation(document: dict, use_json_format: bool = True) -> dict:
    payload = {
        "filename": document["filename"],
        "content": document["content"],
    }
    request_payload = {
        "model": ollama_model(),
        "messages": [
            {"role": "system", "content": DATA_GEN_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": 700,
        },
    }
    if use_json_format:
        request_payload["format"] = "json"

    response = requests.post(
        f"{ollama_base_url()}/api/chat",
        json=request_payload,
        timeout=240,
    )
    response.raise_for_status()
    return response.json()


def generate_questions_with_ollama(document: dict) -> OllamaResult:
    data = call_ollama_question_generation(document, use_json_format=True)
    text = data.get("message", {}).get("content", "")
    if not text.strip():
        retry_data = call_ollama_question_generation(document, use_json_format=False)
        text = retry_data.get("message", {}).get("content", "")
        data = {
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count", 0) + retry_data.get("eval_count", 0),
            "message": {"content": text},
        }

    questions = extract_questions(text)
    return OllamaResult(
        questions=questions,
        input_tokens=int(data.get("prompt_eval_count", 0)),
        output_tokens=int(data.get("eval_count", 0)),
        raw_text=text,
    )


def load_documents() -> list[dict]:
    reader = GithubRepositoryDataReader(
        repo_owner="DataTalksClub",
        repo_name="llm-zoomcamp",
        commit_id="8c1834d",
        allowed_extensions={"md"},
        filename_filter=lambda path: "/lessons/" in path,
    )
    return [file.parse() for file in reader.read()]


def load_ground_truth() -> list[dict[str, str]]:
    with GROUND_TRUTH_PATH.open() as f:
        return list(csv.DictReader(f))


def build_indexes(chunks: list[dict]) -> tuple[Index, VectorSearch, Embedder]:
    model_path = REPO_ROOT / "vector" / "models" / "Xenova" / "all-MiniLM-L6-v2"
    embedder = Embedder(model_path)

    text_index = Index(
        text_fields=["content"],
        keyword_fields=["filename"],
        numeric_fields=["start"],
    )
    text_index.fit(chunks)

    embeddings = embedder.encode_batch([chunk["content"] for chunk in chunks])
    vector_index = VectorSearch(
        keyword_fields=["filename"],
        numeric_fields=["start"],
    )
    vector_index.fit(embeddings, chunks)

    return text_index, vector_index, embedder


def rrf(result_lists: list[list[dict]], k: int = 60, num_results: int = 5) -> list[dict]:
    scores = {}
    docs = {}

    for results in result_lists:
        for rank, doc in enumerate(results):
            key = (doc["filename"], doc["start"])
            scores[key] = scores.get(key, 0) + 1 / (k + rank)
            docs[key] = doc

    ranked = sorted(scores, key=scores.get, reverse=True)
    return [docs[key] for key in ranked[:num_results]]


def compute_relevance(record: dict[str, str], search_fn: Callable[[str], list[dict]]) -> list[int]:
    results = search_fn(record["question"])
    return [int(result["filename"] == record["filename"]) for result in results]


def hit_rate(relevance_total: list[list[int]]) -> float:
    return float(np.mean([any(relevance) for relevance in relevance_total]))


def mrr(relevance_total: list[list[int]]) -> float:
    score = 0.0
    for relevance in relevance_total:
        for rank, is_relevant in enumerate(relevance):
            if is_relevant:
                score += 1 / (rank + 1)
                break
    return score / len(relevance_total)


def evaluate(ground_truth: list[dict[str, str]], search_fn: Callable[[str], list[dict]]) -> dict[str, float]:
    relevance_total = [compute_relevance(record, search_fn) for record in ground_truth]
    return {
        "hit_rate": hit_rate(relevance_total),
        "mrr": mrr(relevance_total),
    }


def simplify_results(results: list[dict]) -> list[dict]:
    return [
        {
            "filename": result["filename"],
            "start": result.get("start"),
        }
        for result in results
    ]


def main() -> None:
    documents = load_documents()
    chunks = chunk_documents(documents, size=2000, step=1000)
    ground_truth = load_ground_truth()
    text_index, vector_index, embedder = build_indexes(chunks)

    def text_search(query: str, num_results: int = 5) -> list[dict]:
        return text_index.search(query, num_results=num_results)

    def vector_search(query: str, num_results: int = 5) -> list[dict]:
        query_vector = embedder.encode(query)
        return vector_index.search(query_vector, num_results=num_results)

    def hybrid_search(query: str, k: int = 60) -> list[dict]:
        text_results = text_search(query, num_results=10)
        vector_results = vector_search(query, num_results=10)
        return rrf([text_results, vector_results], k=k)

    q1_outputs = []
    for document in documents[:3]:
        generated = generate_questions_with_ollama(document)
        q1_outputs.append(
            {
                "filename": document["filename"],
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
                "questions": generated.questions,
                "raw_text": generated.raw_text,
            }
        )

    q1_average_input_tokens = float(
        np.mean([record["input_tokens"] for record in q1_outputs])
    )

    first_question = ground_truth[0]["question"]
    q2_text_results = text_search(first_question)
    q3_vector_results = vector_search(first_question)

    q4_text_metrics = evaluate(ground_truth, text_search)
    q5_vector_metrics = evaluate(ground_truth, vector_search)

    hybrid_metrics = {}
    for k in [1, 50, 100, 200]:
        hybrid_metrics[str(k)] = evaluate(
            ground_truth,
            lambda query, k=k: hybrid_search(query, k=k),
        )

    best_hybrid_k = min(
        hybrid_metrics,
        key=lambda key: (-hybrid_metrics[key]["mrr"], int(key)),
    )

    results = {
        "environment": {
            "ollama_base_url": ollama_base_url(),
            "ollama_model": ollama_model(),
        },
        "counts": {
            "documents": len(documents),
            "chunks": len(chunks),
            "ground_truth_questions": len(ground_truth),
        },
        "q1": {
            "average_input_tokens": q1_average_input_tokens,
            "calls": q1_outputs,
        },
        "q2": {
            "question": first_question,
            "first_text_result": q2_text_results[0]["filename"],
            "top_5": simplify_results(q2_text_results),
        },
        "q3": {
            "question": first_question,
            "first_vector_result": q3_vector_results[0]["filename"],
            "top_5": simplify_results(q3_vector_results),
        },
        "q4": q4_text_metrics,
        "q5": q5_vector_metrics,
        "q6": {
            "hybrid_metrics": hybrid_metrics,
            "best_k": int(best_hybrid_k),
        },
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "homework_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
