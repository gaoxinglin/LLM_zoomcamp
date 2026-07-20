import argparse
import json
import re
from pathlib import Path
from statistics import mean

from .answering import BASELINE_PROMPT, SYSTEM_PROMPT, AnswerGenerator
from .config import get_settings
from .models import SearchRequest
from .retrieval import Retriever
from .storage import Storage

CITATION_RE = re.compile(r"\[\d+\]")


def score_answer(text: str, expected_terms: list[str], source_count: int) -> dict[str, float]:
    lowered = text.casefold()
    term_coverage = mean(float(term.casefold() in lowered) for term in expected_terms)
    citation_count = len(set(CITATION_RE.findall(text)))
    citation_coverage = min(citation_count / source_count, 1.0) if source_count else 1.0
    return {
        "expected_term_coverage": round(term_coverage, 4),
        "citation_coverage": round(citation_coverage, 4),
    }


def evaluate_variant(
    name: str,
    cases: list[dict],
    retriever: Retriever,
    generator: AnswerGenerator,
    *,
    use_llm: bool,
    system_prompt: str,
) -> dict:
    if use_llm and not generator.settings.openai_api_key:
        return {"approach": name, "status": "skipped: OPENAI_API_KEY is not configured"}
    scores = []
    for case in cases:
        results = retriever.search(SearchRequest(query=case["question"], limit=5))
        generated = generator.generate(
            case["question"], results, use_llm=use_llm, system_prompt=system_prompt
        )
        scores.append(score_answer(generated.text, case["expected_terms"], len(results)))
    return {
        "approach": name,
        "status": "completed",
        "cases": len(cases),
        "expected_term_coverage": round(mean(item["expected_term_coverage"] for item in scores), 4),
        "citation_coverage": round(mean(item["citation_coverage"] for item in scores), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare answer-generation approaches")
    parser.add_argument("--database", type=Path, default=Path("runtime/app.db"))
    parser.add_argument("--cases", type=Path, default=Path("evaluation/answer_cases.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/answers.json"))
    parser.add_argument("--with-llm", action="store_true")
    arguments = parser.parse_args()

    settings = get_settings()
    retriever = Retriever(Storage(arguments.database))
    generator = AnswerGenerator(settings)
    cases = json.loads(arguments.cases.read_text())
    variants = [
        evaluate_variant(
            "extractive",
            cases,
            retriever,
            generator,
            use_llm=False,
            system_prompt=SYSTEM_PROMPT,
        )
    ]
    if arguments.with_llm:
        variants.extend(
            [
                evaluate_variant(
                    "LLM baseline prompt",
                    cases,
                    retriever,
                    generator,
                    use_llm=True,
                    system_prompt=BASELINE_PROMPT,
                ),
                evaluate_variant(
                    "LLM grounded prompt",
                    cases,
                    retriever,
                    generator,
                    use_llm=True,
                    system_prompt=SYSTEM_PROMPT,
                ),
            ]
        )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(variants, indent=2) + "\n")
    print(json.dumps(variants, indent=2))


if __name__ == "__main__":
    main()
