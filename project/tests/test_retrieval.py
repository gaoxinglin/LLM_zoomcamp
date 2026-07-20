from nz_open_data_assistant.models import SearchMode, SearchRequest
from nz_open_data_assistant.retrieval import Retriever


def test_hybrid_retrieval_ranks_specific_dataset_first(storage) -> None:
    results = Retriever(storage).search(
        SearchRequest(
            query="Auckland bus stop routes",
            mode=SearchMode.HYBRID,
            limit=5,
            rewrite=True,
        )
    )
    assert results[0].dataset.id == "68fa1cf2-fb90-40a4-8504-505c46457c6b"
    assert set(results[0].matched_by) == {"lexical", "vector"}


def test_retrieval_modes_return_results(storage) -> None:
    retriever = Retriever(storage)
    for mode in SearchMode:
        results = retriever.search(SearchRequest(query="Auckland population", mode=mode))
        assert results
        assert [result.rank for result in results] == list(range(1, len(results) + 1))
