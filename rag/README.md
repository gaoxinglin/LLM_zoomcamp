# LLM Zoomcamp 2026 - Homework 1

Run the deterministic questions:

```bash
uv run python ingest.py q1
uv run python ingest.py q2
uv run python ingest.py q4
```

For the LLM and agent questions, create `.env`:

```text
OPENAI_API_KEY=your-key
```

Then run:

```bash
uv run python ingest.py q3
uv run python ingest.py q5
uv run python ingest.py q6
```

Run every question with:

```bash
uv run python ingest.py all
```

The script uses the homework's pinned commit (`8c1834d`), the
`gpt-5.4-mini` model, five search results, and 2000-character chunks with a
1000-character step.
