# Homework 4: Evaluation

This folder contains the official homework statement, ground-truth data, helper
code, and a reproducible script for the answers:

```bash
uv run python -B evaluation/scripts/run_homework.py
```

The script uses the LAN Ollama endpoint from `rag/.env`:

```text
OPENAI_BASE_URL=http://100.114.202.116:11434/v1
OPENAI_MODEL=qwen3.5:4b
```

For Q1, it calls Ollama native `/api/chat` with `think:false` and records
`prompt_eval_count` as input tokens. For Q2-Q6, it rebuilds the same homework 2
text, vector, and hybrid search indexes over the 295 chunks.

Raw results are saved in `evaluation/results/homework_results.json`.

## Answers

1. **1400**

   The first three LLM calls used these input token counts:

   - `01-agentic-rag/lessons/01-intro.md`: 1044
   - `01-agentic-rag/lessons/02-environment.md`: 1322
   - `01-agentic-rag/lessons/03-rag.md`: 1793

   Average: `1386.33`, closest to **1400**.

2. **`01-agentic-rag/lessons/03-rag.md`**

   The first ground-truth question was:

   > What exactly is a retrieval-augmented generation system, and why does it help with answers that the model wouldn't know on its own?

   Text search returned `01-agentic-rag/lessons/03-rag.md` first.

3. **`01-agentic-rag/lessons/01-intro.md`**

   Vector search returned `01-agentic-rag/lessons/01-intro.md` first for the
   same question.

4. **0.76**

   Text search metrics:

   - Hit Rate: `0.7583333333333333`
   - MRR: `0.5942592592592594`

   Closest option: **0.76**.

5. **0.55**

   Vector search metrics:

   - Hit Rate: `0.725`
   - MRR: `0.5486111111111112`

   Closest option: **0.55**.

6. **1**

   Hybrid search MRR by RRF `k`:

   - `k=1`: `0.6481944444444449`
   - `k=50`: `0.637916666666667`
   - `k=100`: `0.637916666666667`
   - `k=200`: `0.637916666666667`

   Best MRR is with **k = 1**.
