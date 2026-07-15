# dlt workshop homework — solution

## Answers

1. **5 spans** (the exact number can vary when the model chooses a different
   number of searches).
2. **24 tables** in the `agent_traces` DuckDB schema.
3. **1500 - 5000 input tokens**, summed across the LLM calls in the trace.

## Evidence and reproduction

- `main.py` instruments Pydantic AI with Logfire and runs the exact Q1 query.
- `load_traces.py` queries all Logfire records and loads them with dlt into the
  `agent_traces` DuckDB schema. Nested attributes and messages are normalized
  into child tables automatically.
- `analyze.py` runs the Q2 table-count query, locates the trace containing the
  homework question, and sums every normalized
  `gen_ai.usage.input_tokens` column for that trace.

Live values require `LOGFIRE_TOKEN` and `LOGFIRE_READ_TOKEN`. These credentials
are intentionally not committed.
