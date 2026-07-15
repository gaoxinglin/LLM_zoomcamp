"""OpenTelemetry instrumentation and SQLite exporter for the RAG pipeline."""

import sqlite3

from opentelemetry import trace
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from rag_helper import RAGBase

# GPT-5.4 mini standard text-token prices, USD per 1M tokens (July 2026).
INPUT_PRICE_PER_MILLION = 0.75
OUTPUT_PRICE_PER_MILLION = 4.50


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * INPUT_PRICE_PER_MILLION
        + output_tokens * OUTPUT_PRICE_PER_MILLION
    ) / 1_000_000


class RAGTraced(RAGBase):
    """RAGBase with a parent span and one span for each expensive child step."""

    def __init__(self, *args, tracer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracer = tracer or trace.get_tracer("llm-zoomcamp")

    def search(self, query, num_results=5):
        with self.tracer.start_as_current_span("search"):
            return super().search(query, num_results=num_results)

    def llm(self, prompt):
        with self.tracer.start_as_current_span("llm") as span:
            response = super().llm(prompt)
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            span.set_attribute("input_tokens", input_tokens)
            span.set_attribute("output_tokens", output_tokens)
            span.set_attribute("cost", calculate_cost(input_tokens, output_tokens))
            return response

    def rag(self, query):
        with self.tracer.start_as_current_span("rag"):
            return super().rag(query)


class SQLiteSpanExporter(SpanExporter):
    def __init__(self, db_path="traces.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                name TEXT,
                start_time INTEGER,
                end_time INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost REAL
            )
            """
        )
        self.conn.commit()

    def export(self, spans):
        for span in spans:
            attrs = dict(span.attributes or {})
            self.conn.execute(
                "INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?)",
                (
                    span.name,
                    span.start_time,
                    span.end_time,
                    attrs.get("input_tokens"),
                    attrs.get("output_tokens"),
                    attrs.get("cost"),
                ),
            )
        self.conn.commit()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self.conn.close()

    def force_flush(self, timeout_millis=30_000):
        return True

