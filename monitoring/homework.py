"""Run the instrumented RAG and print the measurements used in Q1-Q6."""

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from starter import build_index
from tracing import RAGTraced, SQLiteSpanExporter

QUERY = "How does the agentic loop keep calling the model until it stops?"


def configure_tracing(exporter):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("llm-zoomcamp"), provider


def summarize(db_path):
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        spans = pd.read_sql_query(
            """
            SELECT *, (end_time - start_time) / 1000000000.0 AS duration_seconds
            FROM spans
            """,
            conn,
        )

    print("\nSpan counts:")
    print(spans.groupby("name").size().to_string())
    print("\nTotal child-span duration (seconds):")
    print(
        spans.loc[spans.name != "rag"]
        .groupby("name")["duration_seconds"]
        .sum()
        .sort_values(ascending=False)
        .to_string()
    )
    print("\nLLM token and cost measurements:")
    print(
        spans.loc[
            spans.name == "llm",
            ["input_tokens", "output_tokens", "cost", "duration_seconds"],
        ].to_string(index=False)
    )


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--exporter", choices=["console", "sqlite"], default="sqlite")
    parser.add_argument("--db", default="traces.db")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--reset-db", action="store_true")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.exporter == "sqlite" and args.reset_db:
        db_path.unlink(missing_ok=True)

    exporter = (
        ConsoleSpanExporter()
        if args.exporter == "console"
        else SQLiteSpanExporter(db_path)
    )
    tracer, provider = configure_tracing(exporter)

    from openai import OpenAI

    rag = RAGTraced(
        index=build_index(),
        llm_client=OpenAI(),
        tracer=tracer,
        model=args.model,
    )
    for run in range(1, args.runs + 1):
        answer = rag.rag(QUERY)
        print(f"Run {run}: {answer}")

    provider.force_flush()
    if args.exporter == "sqlite":
        summarize(db_path)
    provider.shutdown()


if __name__ == "__main__":
    main()
