# Module 5 homework: Monitoring

This directory contains a complete OpenTelemetry implementation for the 2026
LLM Zoomcamp monitoring homework. It emits `rag`, `search`, and `llm` spans,
records token/cost attributes, and can export either to the console or SQLite.

## Run

```bash
cd monitoring
uv sync
cp .env.example .env  # then add your key
uv run python homework.py --exporter console --runs 1
uv run python homework.py --exporter sqlite --runs 4 --reset-db
uv run pytest
```

The SQLite command prints span counts, total duration by child span, and all LLM
token/cost measurements. See `homework_solution.md` for the submitted choices.

