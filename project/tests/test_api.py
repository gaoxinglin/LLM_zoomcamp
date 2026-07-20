from fastapi.testclient import TestClient

from nz_open_data_assistant.api import app
from nz_open_data_assistant.config import get_settings


def test_api_health_answer_feedback_and_metrics(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api.db"))
    get_settings.cache_clear()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["datasets"] == 12

        answer = client.post("/answer", json={"query": "Find Auckland bus datasets"})
        assert answer.status_code == 200
        payload = answer.json()
        assert payload["citations"]
        assert payload["used_llm"] is False

        feedback = client.post("/feedback", json={"request_id": payload["request_id"], "rating": 1})
        assert feedback.status_code == 204

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["feedback"][0]["value"] == 1
    get_settings.cache_clear()
