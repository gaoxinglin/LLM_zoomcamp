from dataclasses import dataclass

from openai import OpenAI

from .config import Settings
from .models import Citation, SearchResult

SYSTEM_PROMPT = """You are the NZ Regional Insights Assistant, an independent student project.
Answer only from the supplied data.govt.nz catalogue records. Never invent figures or claim that
catalogue metadata proves a fact contained inside a dataset. Distinguish dataset discovery from
data analysis. Recommend the most relevant records, mention publisher and update date, and cite
sources using [1], [2], and so on. If the evidence is insufficient, say what cannot be established.
Keep the answer concise and use plain English."""

BASELINE_PROMPT = """Answer the user's question using only the supplied catalogue records.
Recommend relevant datasets and cite records as [1], [2], and so on."""


@dataclass
class Generation:
    text: str
    used_llm: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AnswerGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(
        self,
        query: str,
        results: list[SearchResult],
        use_llm: bool = True,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> Generation:
        if not results:
            return Generation(
                "I could not find a relevant Auckland open-data record. Try naming a topic, "
                "publisher, area, year, or desired file format.",
                False,
            )
        if not use_llm or not self.settings.openai_api_key:
            return Generation(self._extractive_answer(results), False)

        context = "\n\n".join(
            f"[{index}] Title: {result.dataset.title}\n"
            f"Publisher: {result.dataset.organization}\n"
            f"Updated: {result.dataset.metadata_modified or 'not stated'}\n"
            f"Formats: {', '.join(result.dataset.formats) or 'not stated'}\n"
            f"Description: {result.dataset.description[:1800]}\n"
            f"URL: {result.dataset.url}"
            for index, result in enumerate(results, 1)
        )
        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {query}\n\nCatalogue records:\n{context}"},
            ],
        )
        usage = response.usage
        return Generation(
            response.choices[0].message.content or self._extractive_answer(results),
            True,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

    @staticmethod
    def _extractive_answer(results: list[SearchResult]) -> str:
        lines = ["The most relevant catalogue records are:"]
        for index, result in enumerate(results[:5], 1):
            dataset = result.dataset
            description = dataset.description[:240].rsplit(" ", 1)[0]
            suffix = "…" if len(dataset.description) > 240 else ""
            updated = dataset.metadata_modified or "not stated"
            lines.append(
                f"\n{index}. **{dataset.title}** — {dataset.organization}. "
                f"{description}{suffix} Updated: {updated}. [{index}]"
            )
        lines.append(
            "\nThese are catalogue recommendations, not conclusions calculated from "
            "the underlying data."
        )
        return "".join(lines)


def citations_for(results: list[SearchResult]) -> list[Citation]:
    return [
        Citation(
            dataset_id=result.dataset.id,
            title=result.dataset.title,
            url=result.dataset.url,
            publisher=result.dataset.organization,
            updated=result.dataset.metadata_modified,
        )
        for result in results
    ]
