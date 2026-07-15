"""Extract Logfire records and load their nested JSON into DuckDB with dlt."""

import argparse
import os
from pathlib import Path

import dlt
from dotenv import load_dotenv
from logfire.query_client import LogfireQueryClient

DEFAULT_SQL = "SELECT * FROM records ORDER BY start_timestamp"


@dlt.resource(name="records", write_disposition="replace")
def logfire_records(read_token: str, base_url: str, sql: str = DEFAULT_SQL):
    with LogfireQueryClient(read_token=read_token, base_url=base_url) as client:
        yield from client.query_json_rows(sql=sql)


def load_traces(db_path: Path, read_token: str, base_url: str):
    pipeline = dlt.pipeline(
        pipeline_name="logfire_to_duckdb",
        destination=dlt.destinations.duckdb(str(db_path)),
        dataset_name="agent_traces",
    )
    return pipeline.run(logfire_records(read_token, base_url))


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("logfire.duckdb"))
    args = parser.parse_args()

    read_token = os.getenv("LOGFIRE_READ_TOKEN")
    if not read_token:
        raise SystemExit("LOGFIRE_READ_TOKEN is required")
    base_url = os.getenv("LOGFIRE_API_URL", "https://logfire-api.pydantic.dev")

    print(load_traces(args.db, read_token, base_url))


if __name__ == "__main__":
    main()

