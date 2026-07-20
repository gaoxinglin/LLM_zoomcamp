from collections import defaultdict

from .models import SearchMode, SearchRequest, SearchResult
from .storage import Storage
from .text import rewrite_query, tokens


class Retriever:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def search(self, request: SearchRequest) -> list[SearchResult]:
        query = rewrite_query(request.query) if request.rewrite else request.query
        candidate_limit = max(request.limit * 4, 20)
        lexical = self.storage.lexical_search(query, candidate_limit)
        vector = self.storage.vector_search(query, candidate_limit)

        if request.mode == SearchMode.LEXICAL:
            fused = [(dataset_id, score, ["lexical"]) for dataset_id, score in lexical]
        elif request.mode == SearchMode.VECTOR:
            fused = [(dataset_id, score, ["vector"]) for dataset_id, score in vector]
        else:
            fused = self._reciprocal_rank_fusion(lexical, vector)

        query_terms = set(tokens(request.query))
        results: list[SearchResult] = []
        for dataset_id, score, matched_by in fused:
            dataset = self.storage.get_dataset(dataset_id)
            if dataset is None:
                continue
            if request.rerank:
                title_overlap = len(query_terms & set(tokens(dataset.title)))
                tag_overlap = len(
                    query_terms & set(tokens(" ".join(dataset.tags + dataset.groups)))
                )
                publisher_overlap = len(query_terms & set(tokens(dataset.organization)))
                score += 0.025 * title_overlap + 0.012 * tag_overlap + 0.008 * publisher_overlap
            results.append(
                SearchResult(dataset=dataset, score=score, rank=0, matched_by=matched_by)
            )

        results.sort(key=lambda item: item.score, reverse=True)
        selected = results[: request.limit]
        for rank, result in enumerate(selected, 1):
            result.rank = rank
        return selected

    @staticmethod
    def _reciprocal_rank_fusion(
        lexical: list[tuple[str, float]], vector: list[tuple[str, float]], constant: int = 60
    ) -> list[tuple[str, float, list[str]]]:
        scores: defaultdict[str, float] = defaultdict(float)
        methods: defaultdict[str, list[str]] = defaultdict(list)
        # Semantic ranking is the stronger signal on the labelled set; lexical evidence
        # remains a smaller, independent signal and recovers exact catalogue terms.
        weights = {"lexical": 1.0, "vector": 8.0}
        for method, ranking in (("lexical", lexical), ("vector", vector)):
            for rank, (dataset_id, _) in enumerate(ranking, 1):
                scores[dataset_id] += weights[method] / (constant + rank)
                methods[dataset_id].append(method)
        return sorted(
            [(dataset_id, score * 10, methods[dataset_id]) for dataset_id, score in scores.items()],
            key=lambda item: item[1],
            reverse=True,
        )
