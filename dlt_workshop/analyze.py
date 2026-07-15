"""Answer Q2 and Q3 from the dlt-created DuckDB schema."""

import argparse
from pathlib import Path

import duckdb
import pandas as pd

DATASET = "agent_traces"
HOMEWORK_QUESTION = "How do I run Ollama locally?"


def count_tables(conn) -> int:
    return conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ?
        """,
        [DATASET],
    ).fetchone()[0]


def find_records_table(conn) -> str:
    tables = [
        row[0]
        for row in conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = ? AND NOT starts_with(table_name, '_dlt')
            ORDER BY table_name
            """,
            [DATASET],
        ).fetchall()
    ]
    if "records" in tables:
        return "records"
    if not tables:
        raise RuntimeError("No Logfire records table found")
    return tables[0]


def input_tokens_for_question(conn, question: str) -> tuple[str, int]:
    table = find_records_table(conn)
    frame = conn.execute(f'SELECT * FROM "{DATASET}"."{table}"').df()
    trace_column = next(
        (column for column in frame.columns if column.lower().endswith("trace_id")),
        None,
    )
    if trace_column is None:
        raise RuntimeError("No trace_id column found")

    contains_question = frame.astype(str).apply(
        lambda column: column.str.contains(question, case=False, regex=False)
    ).any(axis=1)
    matching = frame.loc[contains_question]
    if matching.empty:
        raise RuntimeError(f"No trace contains the question: {question}")
    trace_id = str(matching.iloc[-1][trace_column])

    token_columns = [
        column
        for column in frame.columns
        if "gen_ai" in column.lower()
        and "usage" in column.lower()
        and column.lower().endswith("input_tokens")
    ]
    if not token_columns:
        raise RuntimeError("No gen_ai.usage.input_tokens column found")

    trace_rows = frame.loc[frame[trace_column].astype(str) == trace_id]
    total = sum(
        pd.to_numeric(trace_rows[column], errors="coerce").fillna(0).sum()
        for column in token_columns
    )
    return trace_id, int(total)


def token_range(total: int) -> str:
    ranges = [
        (100, 500, "100 - 500"),
        (1500, 5000, "1500 - 5000"),
        (10000, 20000, "10000 - 20000"),
        (50000, 100000, "50000 - 100000"),
    ]
    for lower, upper, label in ranges:
        if lower <= total <= upper:
            return label
    return "outside the supplied ranges"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("logfire.duckdb"))
    parser.add_argument("--question", default=HOMEWORK_QUESTION)
    args = parser.parse_args()

    with duckdb.connect(str(args.db), read_only=True) as conn:
        print(f"Q2 table count: {count_tables(conn)}")
        trace_id, tokens = input_tokens_for_question(conn, args.question)
        print(f"Trace: {trace_id}")
        print(f"Q3 input tokens: {tokens} ({token_range(tokens)})")


if __name__ == "__main__":
    main()
