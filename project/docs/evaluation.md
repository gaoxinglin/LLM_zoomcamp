# Evaluation Plan

## Retrieval evaluation

`evaluation/ground_truth.jsonl` contains 60 questions labelled with relevant catalogue IDs. It
includes paraphrases, publisher intent, formats, and closely related transport categories.

Run:

```bash
uv run nz-ingest --seed-only --replace
uv run nz-evaluate
```

The script compares a lexical baseline, lexical plus reranking, vector plus reranking, hybrid plus
reranking, and query rewriting plus hybrid retrieval and reranking. It reports:

- Hit Rate@5: fraction of questions with at least one relevant result;
- Recall@5: fraction of labelled relevant records found;
- MRR: average reciprocal rank of the first relevant record;
- NDCG@5: rank-sensitive gain, normalized by the ideal ranking.

The deployment target is Hit Rate@5 >= 0.85 and MRR >= 0.70. A result is not valid unless it records
the corpus version, ground-truth file, and code commit.

### Seed-corpus baseline

The verified run on 2026-07-16 produced:

| Mode | Hit Rate@5 | Recall@5 | MRR | NDCG@5 |
|---|---:|---:|---:|---:|
| Lexical | 1.0000 | 1.0000 | 0.6694 | 0.7557 |
| Vector | 0.9500 | 0.9500 | 0.8472 | 0.8740 |
| Hybrid | 0.9667 | 0.9667 | 0.8283 | 0.8642 |

The seed-only result is useful for deterministic regression testing, but the seed corpus is small and
transport-heavy. The final clean live ingestion contains 86 deduplicated records and 24 resources
that can be queried through the safe adapters. The complete variant comparison produced:

| Approach | Hit Rate@5 | Recall@5 | MRR | NDCG@5 |
|---|---:|---:|---:|---:|
| Lexical baseline | 0.8833 | 0.8833 | 0.6656 | 0.7199 |
| Lexical + rerank | 0.9000 | 0.9000 | 0.7278 | 0.7717 |
| Vector + rerank | 0.6500 | 0.6500 | 0.3589 | 0.4328 |
| Hybrid + rerank | 0.6500 | 0.6500 | 0.4094 | 0.4706 |
| Query rewrite + hybrid + rerank | 0.6333 | 0.6333 | 0.3417 | 0.4148 |

Lexical retrieval with reranking and no query rewriting is therefore the deployed default. The
dependency-free hashed vector signal does not separate the larger live corpus well enough, and the
small synonym expansion broadens queries too aggressively. These features remain available as
evaluated experiments. The comparison must be regenerated when the catalogue snapshot, embedding
model, or labelled set changes.

## Answer evaluation

`evaluation/answer_cases.json` provides initial answer cases and required evidence terms. Before the
final course submission it should be expanded with reviewed examples from the live corpus.

Compare at least:

1. extractive catalogue answer;
2. LLM synthesis with the grounding prompt.

Human reviewers score relevance, groundedness, citation correctness, limitation handling, and
clarity. Automatic gates require citations for every returned source and reject answers containing a
number that is absent from supplied evidence.

Run the deterministic extractive check with `uv run nz-evaluate-answers`. With an OpenAI key, run
`uv run nz-evaluate-answers --with-llm` to compare the baseline and grounded prompts. LLM comparisons
are intentionally not reported when no API credential is configured.

## Data-query evaluation

Each enabled live resource needs deterministic cases covering valid fields, invalid fields, equality
filters, ordering, row limits, empty results, and upstream errors. Expected values must record the
source update timestamp because government datasets can change.

## Monitoring feedback loop

Review low-rated queries and empty-result events weekly during testing. Add representative failures
to the ground truth before changing query rewriting or ranking. Regenerate the comparison report and
keep the change only if it improves aggregate metrics without breaking important slices.
