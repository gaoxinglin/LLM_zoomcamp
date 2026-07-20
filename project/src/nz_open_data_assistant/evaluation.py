import argparse
import json
import math
from pathlib import Path
from statistics import mean

from .models import SearchMode, SearchRequest
from .retrieval import Retriever
from .storage import Storage


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def reciprocal_rank(result_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, dataset_id in enumerate(result_ids, 1):
        if dataset_id in relevant_ids:
            return 1 / rank
    return 0.0


def ndcg_at_k(result_ids: list[str], relevant_ids: set[str], k: int = 5) -> float:
    dcg = sum(
        1 / math.log2(rank + 1)
        for rank, dataset_id in enumerate(result_ids[:k], 1)
        if dataset_id in relevant_ids
    )
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def evaluate(
    storage: Storage,
    cases: list[dict],
    mode: SearchMode,
    *,
    rewrite: bool,
    rerank: bool,
    label: str,
) -> dict[str, float | int | str | bool]:
    retriever = Retriever(storage)
    hits: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    for case in cases:
        relevant = set(case["relevant_dataset_ids"])
        results = retriever.search(
            SearchRequest(
                query=case["question"],
                mode=mode,
                limit=5,
                rewrite=rewrite,
                rerank=rerank,
            )
        )
        result_ids = [result.dataset.id for result in results]
        found = relevant & set(result_ids)
        hits.append(float(bool(found)))
        recalls.append(len(found) / len(relevant))
        reciprocal_ranks.append(reciprocal_rank(result_ids, relevant))
        ndcgs.append(ndcg_at_k(result_ids, relevant))
    return {
        "approach": label,
        "mode": mode.value,
        "rewrite": rewrite,
        "rerank": rerank,
        "cases": len(cases),
        "hit_rate_at_5": round(mean(hits), 4),
        "recall_at_5": round(mean(recalls), 4),
        "mrr": round(mean(reciprocal_ranks), 4),
        "ndcg_at_5": round(mean(ndcgs), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval approaches")
    parser.add_argument("--database", type=Path, default=Path("runtime/app.db"))
    parser.add_argument("--ground-truth", type=Path, default=Path("evaluation/ground_truth.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/retrieval.json"))
    arguments = parser.parse_args()
    storage = Storage(arguments.database)
    cases = load_cases(arguments.ground_truth)
    variants = [
        (SearchMode.LEXICAL, False, False, "lexical baseline"),
        (SearchMode.LEXICAL, False, True, "lexical + rerank"),
        (SearchMode.VECTOR, False, True, "vector + rerank"),
        (SearchMode.HYBRID, False, True, "hybrid + rerank"),
        (SearchMode.HYBRID, True, True, "query rewrite + hybrid + rerank"),
    ]
    results = [
        evaluate(storage, cases, mode, rewrite=rewrite, rerank=rerank, label=label)
        for mode, rewrite, rerank, label in variants
    ]
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
