# Product Requirements Document

## Product

**Name:** NZ Regional Insights Assistant  
**Version:** 1.0  
**Scope:** Auckland population, housing, and transport open data  
**Type:** RAG and tool-using web application

## Product statement

Help residents, students, researchers, and journalists discover and understand Auckland open data
without requiring knowledge of government agencies, catalogue terminology, schemas, or APIs. Every
answer must identify its source, publisher, and update information. The product is an independent
student project, not a government service.

## Goals

- Discover relevant datasets from natural-language questions.
- Explain record purpose, publisher, formats, licence, and update date.
- Safely query selected structured resources through validated read-only tools.
- Return no answer instead of fabricating unsupported facts.
- Make ingestion, retrieval evaluation, answer evaluation, feedback, and monitoring reproducible.
- Run the complete user-facing system through Docker Compose.

## Non-goals

- National coverage across every agency and topic.
- Forecasting population, property prices, or transport demand.
- Legal, financial, housing, or policy advice.
- Unrestricted SQL or automatic analysis of arbitrary files.
- Writing to government systems.
- Claiming official status.

## Users and jobs

| User | Job |
|---|---|
| Resident | Find understandable information about local population, housing, or transport data |
| Student/researcher | Identify reusable datasets, formats, definitions, and source links |
| Journalist/analyst | Locate evidence and verify simple facts against original records |

## MVP requirements

1. One-command, repeatable metadata ingestion.
2. Lexical, vector, and hybrid retrieval.
3. Query rewriting and document reranking that can be evaluated separately.
4. Source-grounded answers with explicit no-answer behavior.
5. A browser interface and documented API.
6. A registry of supported resources and safe CKAN/ArcGIS query adapters.
7. Helpful/not-helpful feedback with optional comments.
8. A dashboard with at least five quality and operational charts.
9. Retrieval and answer comparison workflows.
10. Docker Compose, locked dependencies, tests, and complete setup instructions.

## Acceptance criteria

- Seeded application starts without external credentials.
- Live public catalogue ingestion does not require an API key.
- At least 60 labelled retrieval questions are checked in.
- Retrieval report compares at least three approaches and uses the best measured approach.
- Every generated answer contains source citations or explicitly states that no source was found.
- No number is presented as a data fact unless it came from a tool result or supplied evidence.
- Unknown resources and fields are rejected before any data query is sent.
- Feedback appears in the dashboard.
- Dashboard contains requests, latency, feedback, mode, errors, token use, and empty-result charts.
- API and UI start with `docker compose up --build`.
- Tests and lint checks pass from a clean environment.

## Success metrics

- Retrieval Hit Rate@5 >= 0.85.
- Retrieval MRR >= 0.70.
- Citation coverage = 100% for answered catalogue questions.
- High-severity fabricated numerical claims = 0 in the reviewed answer set.
- At least three test users complete five discovery tasks and provide feedback.

## Milestones

1. Validate catalogue schema and candidate datasets.
2. Deliver ingestion and baseline retrieval.
3. Compare retrieval approaches and add grounded answers.
4. Add validated data adapters.
5. Add UI, feedback, monitoring, tests, and containers.
6. Run human evaluation, capture screenshots, and prepare the final submission.

## Risks

| Risk | Mitigation |
|---|---|
| Heterogeneous resource formats | Restrict live queries to registered CKAN and ArcGIS resources |
| Broken upstream links | Seed metadata, cache schemas, use timeouts, and display clear failures |
| Conflicting definitions | Show publisher and limitations; never merge incompatible measures silently |
| Fabricated LLM values | Keep numbers tool-grounded and evaluate deterministic cases |
| Scope growth | Retain Auckland and three topics for the MVP |
| Changing datasets | Record update timestamps and re-review deterministic expected values |

