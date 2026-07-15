from types import SimpleNamespace
import sqlite3

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from tracing import RAGTraced, SQLiteSpanExporter, calculate_cost


class FakeIndex:
    def search(self, query, num_results=5):
        return [{"filename": "lesson.md", "content": "Agent loop context"}]


class FakeResponses:
    def create(self, **kwargs):
        return SimpleNamespace(
            output_text="A test answer",
            usage=SimpleNamespace(input_tokens=7000, output_tokens=100),
        )


def test_rag_emits_three_nested_spans_and_metrics():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    client = SimpleNamespace(responses=FakeResponses())
    rag = RAGTraced(index=FakeIndex(), llm_client=client, tracer=tracer)

    assert rag.rag("question") == "A test answer"

    spans = exporter.get_finished_spans()
    assert {span.name for span in spans} == {"rag", "search", "llm"}
    assert len(spans) == 3
    by_name = {span.name: span for span in spans}
    assert by_name["search"].parent.span_id == by_name["rag"].context.span_id
    assert by_name["llm"].parent.span_id == by_name["rag"].context.span_id
    assert by_name["llm"].attributes["input_tokens"] == 7000
    assert by_name["llm"].attributes["output_tokens"] == 100
    assert by_name["llm"].attributes["cost"] == calculate_cost(7000, 100)


def test_sqlite_exporter_persists_four_complete_traces(tmp_path):
    db_path = tmp_path / "traces.db"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(SQLiteSpanExporter(db_path)))
    tracer = provider.get_tracer("test-sqlite")
    client = SimpleNamespace(responses=FakeResponses())
    rag = RAGTraced(index=FakeIndex(), llm_client=client, tracer=tracer)

    for _ in range(4):
        rag.rag("same question")
    provider.shutdown()

    with sqlite3.connect(db_path) as conn:
        counts = dict(
            conn.execute(
                "SELECT name, COUNT(*) FROM spans GROUP BY name"
            ).fetchall()
        )
        input_tokens = [
            row[0]
            for row in conn.execute(
                "SELECT input_tokens FROM spans WHERE name = 'llm'"
            ).fetchall()
        ]

    assert counts == {"llm": 4, "rag": 4, "search": 4}
    assert input_tokens == [7000, 7000, 7000, 7000]
