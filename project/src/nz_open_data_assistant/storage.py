import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import Dataset, FeedbackRequest
from .text import cosine, hash_embedding, tokens


class Storage:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    searchable_text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS dataset_fts USING fts5(
                    dataset_id UNINDEXED,
                    title,
                    organization,
                    tags,
                    description,
                    tokenize='porter unicode61'
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT,
                    event_type TEXT NOT NULL,
                    query TEXT,
                    mode TEXT,
                    latency_ms REAL,
                    result_count INTEGER,
                    used_llm INTEGER DEFAULT 0,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    estimated_cost_usd REAL DEFAULT 0,
                    error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def upsert_dataset(self, dataset: Dataset) -> None:
        embedding = hash_embedding(dataset.searchable_text)
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO datasets(id, payload, searchable_text, embedding)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     payload=excluded.payload,
                     searchable_text=excluded.searchable_text,
                     embedding=excluded.embedding,
                     updated_at=CURRENT_TIMESTAMP""",
                (
                    dataset.id,
                    dataset.model_dump_json(),
                    dataset.searchable_text,
                    json.dumps(embedding),
                ),
            )
            connection.execute("DELETE FROM dataset_fts WHERE dataset_id = ?", (dataset.id,))
            connection.execute(
                "INSERT INTO dataset_fts VALUES (?, ?, ?, ?, ?)",
                (
                    dataset.id,
                    dataset.title,
                    dataset.organization,
                    " ".join(dataset.tags + dataset.groups),
                    dataset.description,
                ),
            )

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM datasets WHERE id = ?", (dataset_id,)
            ).fetchone()
        return Dataset.model_validate_json(row["payload"]) if row else None

    def all_datasets(self) -> list[Dataset]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload FROM datasets ORDER BY id").fetchall()
        return [Dataset.model_validate_json(row["payload"]) for row in rows]

    def count_datasets(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0])

    def clear_datasets(self) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM dataset_fts")
            connection.execute("DELETE FROM datasets")

    def lexical_search(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        terms = list(dict.fromkeys(tokens(query)))[:20]
        if not terms:
            return []
        match_query = " OR ".join(f'"{term}"' for term in terms)
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT dataset_id, -bm25(dataset_fts, 0, 8, 3, 2, 1) AS score
                   FROM dataset_fts WHERE dataset_fts MATCH ?
                   ORDER BY bm25(dataset_fts, 0, 8, 3, 2, 1) LIMIT ?""",
                (match_query, limit),
            ).fetchall()
        return [(row["dataset_id"], float(row["score"])) for row in rows]

    def vector_search(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        query_vector = hash_embedding(query)
        with self.connect() as connection:
            rows = connection.execute("SELECT id, embedding FROM datasets").fetchall()
        scored = [(row["id"], cosine(query_vector, json.loads(row["embedding"]))) for row in rows]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]

    def log_event(self, **values: Any) -> None:
        fields = [
            "request_id",
            "event_type",
            "query",
            "mode",
            "latency_ms",
            "result_count",
            "used_llm",
            "prompt_tokens",
            "completion_tokens",
            "estimated_cost_usd",
            "error",
        ]
        with self.connect() as connection:
            placeholders = ", ".join("?" for _ in fields)
            statement = f"INSERT INTO events ({', '.join(fields)}) VALUES ({placeholders})"
            connection.execute(
                statement,
                tuple(values.get(field) for field in fields),
            )

    def save_feedback(self, feedback: FeedbackRequest) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO feedback(request_id, rating, comment) VALUES (?, ?, ?)",
                (feedback.request_id, feedback.rating, feedback.comment),
            )

    def metrics(self) -> dict[str, list[dict[str, Any]]]:
        queries = {
            "requests_by_day": """SELECT date(created_at) day, COUNT(*) value FROM events
                WHERE event_type='answer' GROUP BY day ORDER BY day""",
            "latency_by_day": """SELECT date(created_at) day, ROUND(AVG(latency_ms), 2) value
                FROM events WHERE event_type='answer' GROUP BY day ORDER BY day""",
            "feedback": """SELECT CASE rating WHEN 1 THEN 'Helpful' ELSE 'Not helpful' END label,
                COUNT(*) value FROM feedback GROUP BY rating""",
            "search_modes": """SELECT COALESCE(mode, 'unknown') label, COUNT(*) value FROM events
                WHERE event_type IN ('search','answer') GROUP BY mode""",
            "errors_by_day": """SELECT date(created_at) day, COUNT(*) value FROM events
                WHERE error IS NOT NULL GROUP BY day ORDER BY day""",
            "llm_usage": """
                SELECT date(created_at) day, SUM(prompt_tokens + completion_tokens) value
                FROM events GROUP BY day ORDER BY day
            """,
            "empty_results": """
                SELECT CASE WHEN result_count=0 THEN 'No results' ELSE 'Results' END label,
                       COUNT(*) value
                FROM events WHERE event_type IN ('search','answer') GROUP BY label
            """,
        }
        with self.connect() as connection:
            return {
                name: [dict(row) for row in connection.execute(sql).fetchall()]
                for name, sql in queries.items()
            }
