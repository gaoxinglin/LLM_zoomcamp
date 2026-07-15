# dlt workshop homework

This solution instruments the Pydantic AI FAQ agent with Logfire, extracts the
complete Logfire `records` data through its read API, lets dlt normalize the
nested trace attributes into DuckDB, and computes the homework answers.

## Setup and run

```bash
cd dlt_workshop
uv sync
cp .env.example .env
# Fill OPENAI_API_KEY, LOGFIRE_TOKEN, and LOGFIRE_READ_TOKEN.

uv run python main.py --question "How do I run Ollama locally?"
uv run python load_traces.py --db logfire.duckdb
uv run python analyze.py --db logfire.duckdb
uv run pytest
```

`LOGFIRE_API_URL` defaults to Logfire's general API. Set it to the regional
host shown by your project if necessary, such as
`https://logfire-eu.pydantic.dev` or `https://logfire-us.pydantic.dev`.

