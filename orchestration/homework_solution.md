# Homework 3: AI Orchestration with Kestra

This folder contains the official Module 3 orchestration flows plus a local
Ollama-based reproduction script:

```bash
uv run python orchestration/scripts/run_homework_ollama.py
```

The script reads the existing `rag/.env` config:

```text
OPENAI_BASE_URL=http://100.114.202.116:11434/v1
OPENAI_MODEL=qwen3.5:4b
```

It calls Ollama native `/api/chat` with `think:false`, because the OpenAI-compatible
endpoint counted hidden thinking tokens and returned empty visible text for Qwen.
Raw results are saved in `orchestration/results/homework_ollama_results.json`.

## Answers

1. **AI Copilot has access to current Kestra plugin documentation**

   The key difference is context: Kestra AI Copilot is grounded in Kestra-specific
   plugin docs and flow syntax, so it can generate more accurate Kestra YAML than a
   generic chat prompt.

2. **Vague, generic, or fabricated — the model guesses from training data**

   In the no-RAG run, the model listed plausible but incorrect or unsupported
   features such as Kubernetes Secrets, Cron expressions, generic monitoring
   upgrades, and Pydantic integration. With release-note context, it listed actual
   Kestra 1.1 features such as new filters, no-code dashboard editor, Human Task,
   multi-agent AI systems, enhanced file detection triggers, custom app branding,
   and air-gapped support.

3. **5-15 tokens / 60-100 tokens / 200-400 tokens / 500+ tokens**

   Selected answer: **60-100 tokens**.

   Ollama `qwen3.5:4b` produced 122 output tokens for the `short` summary, which is
   closest to this option.

4. **About the same (within 20%)**

   Ollama `qwen3.5:4b` produced:

   - `short`: 122 output tokens
   - `long`: 177 output tokens
   - ratio: `177 / 122 = 1.45x`

   This is not quite within 20%, but it is much closer to "about the same" than to
   the `2-5x` bucket for this local model run.

5. **2-4x more**

   With `summary_length = long`, the original one-sentence `english_brevity` prompt
   produced 44 output tokens. After changing the prompt to exactly 3 sentences, it
   produced 103 output tokens.

   Ratio: `103 / 44 = 2.34x`, so the closest answer is **2-4x more**.

   The homework change has been applied in `flows/4_simple_agent.yaml`:

   ```yaml
   Generate exactly 3 sentences English summary of the following:
   ```

6. **Use traditional task-based workflows for predictability and auditability**

   For deterministic, repeatable, compliance-sensitive workflows, fixed
   task-based orchestration is more appropriate than autonomous agents because it
   is easier to audit, test, reproduce, and control.
