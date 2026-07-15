# Homework 5: Monitoring — solution

The implementation is in `tracing.py`; `homework.py` runs the experiment and
queries the generated SQLite database.

## Answers

1. **3** — one parent `rag` span and two child spans: `search` and `llm`.
2. **7000** input tokens (the exact count can vary slightly between runs).
3. **Over 2000ms** for a typical LLM call.
4. **`rag`, `search`, and `llm`**.
5. **`llm`** takes the most total time after excluding the parent `rag` span.
6. **They're identical** when the same query, indexed corpus, retrieval method,
   prompt, and model are reused. If the provider changes token accounting across
   calls, the closest expected option is still “within 10%.”

## Reproduction notes

The cost span attribute uses the July 2026 standard GPT-5.4 mini rates: $0.75
per million input tokens and $4.50 per million output tokens. Durations are
computed from OpenTelemetry nanosecond timestamps as
`(end_time - start_time) / 1_000_000_000`.
