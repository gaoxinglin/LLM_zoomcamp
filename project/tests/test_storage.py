from nz_open_data_assistant.models import FeedbackRequest


def test_storage_indexes_and_fetches_datasets(storage) -> None:
    assert storage.count_datasets() == 12
    result = storage.get_dataset("68fa1cf2-fb90-40a4-8504-505c46457c6b")
    assert result is not None
    assert result.title == "Bus - Auckland Transport"


def test_lexical_search_finds_bus_dataset(storage) -> None:
    results = storage.lexical_search("bus routes public transport", limit=5)
    ids = [dataset_id for dataset_id, _ in results]
    assert "68fa1cf2-fb90-40a4-8504-505c46457c6b" in ids


def test_feedback_and_metrics(storage) -> None:
    storage.log_event(
        request_id="request-1",
        event_type="answer",
        query="bus data",
        mode="hybrid",
        latency_ms=12.5,
        result_count=3,
    )
    storage.save_feedback(FeedbackRequest(request_id="request-1", rating=1))
    metrics = storage.metrics()
    assert metrics["requests_by_day"][0]["value"] == 1
    assert metrics["feedback"][0]["label"] == "Helpful"


def test_clear_datasets_keeps_operational_tables(storage) -> None:
    storage.clear_datasets()
    assert storage.count_datasets() == 0
