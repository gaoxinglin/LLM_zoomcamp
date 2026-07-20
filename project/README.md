# NZ Regional Insights Assistant

An end-to-end RAG and tool-using application for discovering and querying Auckland population,
housing, and transport open data. It indexes records from the New Zealand Government Data
Catalogue, compares lexical and vector retrieval, produces source-grounded answers, collects user
feedback, and exposes an operations dashboard.

> **Independent student project:** this application is not an official New Zealand Government
> service. Verify important conclusions against the linked source datasets.

## Problem

New Zealand publishes a large open-data catalogue, but users often do not know the responsible
agency, the catalogue terminology, or the format they need. Finding a record is only the first step:
users must still interpret metadata, inspect resources, and safely query heterogeneous services.

This project addresses two jobs:

1. **Dataset discovery:** find and explain relevant Auckland records from a plain-English question.
2. **Controlled data access:** query a registered CKAN DataStore or ArcGIS resource through a
   validated, read-only query plan.

The MVP deliberately focuses on Auckland population, housing, and transport. It does not attempt to
answer every question in the national catalogue.

## What is implemented

- Repeatable CKAN metadata ingestion with retries, pagination-ready parameters, cleaning, deduping,
  topic filtering, and an offline seed fallback.
- SQLite FTS5 BM25 retrieval.
- Deterministic feature-hashing vector retrieval that requires no model download or API key.
- Reciprocal-rank hybrid fusion, query expansion, and lightweight metadata reranking.
- Source-grounded extractive answers that work without an LLM key.
- Optional OpenAI answer synthesis with a strict catalogue-grounding prompt.
- Safe CKAN DataStore and ArcGIS FeatureServer adapters with resource/field allowlists, structured
  filters, read-only requests, row limits, and timeouts.
- FastAPI endpoints, interactive API documentation, and health checks.
- Streamlit assistant, dataset explorer, source cards, feedback controls, and seven monitoring charts.
- Sixty labelled retrieval cases and a script comparing lexical, vector, and hybrid approaches.
- Unit tests, exact dependency locking, Dockerfile, and Docker Compose services for the API, UI, and
  ingestion job.

## Architecture

```text
data.govt.nz Catalogue API                 Optional OpenAI API
             |                                      |
             v                                      v
      ingestion + cleaning                  grounded synthesis
             |                                      ^
             v                                      |
  SQLite metadata + FTS + vectors --> hybrid retrieval + reranking
             |                                      |
             +------------ FastAPI -----------------+
                              |
                       Streamlit UI
                   feedback + monitoring

  Registered CKAN/ArcGIS resource --> validated query plan --> read-only adapter
```

See [Architecture](docs/architecture.md), [Evaluation](docs/evaluation.md), and the
[Product Requirements Document](docs/PRD.md) for details.

## Quick start with Docker

Requirements: Docker with Compose v2.

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Application: <http://localhost:8501>
- API documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

The API seeds 12 verified catalogue records on first start, so the application works without network
access or an API key. To replace/enrich the seed with live catalogue metadata:

```bash
docker compose --profile tools run --rm ingest
```

## Local development

Requirements: Python 3.11+ and `uv`.

```bash
cp .env.example .env
uv sync --extra dev
uv run nz-ingest --seed-only
uv run uvicorn nz_open_data_assistant.api:app --reload
```

In another terminal:

```bash
uv run streamlit run app/streamlit_app.py
```

Run the full live ingestion when internet access is available:

```bash
uv run nz-ingest --max-per-topic 200 --replace
```

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` | empty | Enables optional LLM answer synthesis |
| `OPENAI_MODEL` | `gpt-4o-mini` | Generation model |
| `DATABASE_PATH` | `runtime/app.db` | SQLite database and index |
| `CATALOGUE_BASE_URL` | data.govt.nz catalogue | CKAN base URL |
| `API_URL` | `http://localhost:8000` | API used by the Streamlit UI |
| `REQUEST_TIMEOUT_SECONDS` | `20` | External-request timeout |
| `MAX_SEARCH_RESULTS` | `5` | Default answer result count |
| `ENABLE_DATA_TOOLS` | `false` | Enables explicit live data-query requests |

No data.govt.nz API key is required for public read access. Individual publishers may apply their
own terms or authentication to externally hosted resources.

## API examples

Search the local index:

```bash
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Auckland bus route data","mode":"hybrid","limit":5}'
```

Generate a grounded answer:

```bash
curl -X POST http://localhost:8000/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"Where can I find Auckland population data by local board?"}'
```

Submit feedback:

```bash
curl -X POST http://localhost:8000/feedback \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"REQUEST_ID","rating":1,"comment":"The sources were useful."}'
```

Data queries are disabled by default because they make live calls. After ingesting full resource
metadata, set `ENABLE_DATA_TOOLS=true` and submit a plan containing a dataset ID, one of that
dataset's resource IDs, an adapter, allowed fields, filters, and a maximum of 100 rows. The service
fetches the live schema and rejects unknown fields or resources.

## Evaluation

Seed the index and compare all retrieval modes:

```bash
uv run nz-ingest --seed-only --replace
uv run nz-evaluate
uv run nz-evaluate-answers
```

Metrics include Hit Rate@5, Recall@5, MRR, and NDCG@5. The labelled set contains 60 user-style
questions. Results are written to `evaluation/results/retrieval.json` and must be regenerated after
changing the corpus, embedding method, query rewriting, or reranking.

On the final live-ingested development corpus, lexical retrieval plus metadata reranking is the
measured default (Hit Rate@5 0.90, MRR 0.7278). Hybrid search and query rewriting remain selectable,
but did not outperform the lexical approach with the dependency-free hashed vectors. See the
evaluation document for the complete comparison and limitations.

With `OPENAI_API_KEY` configured, compare a baseline prompt against the stricter grounded prompt:

```bash
uv run nz-evaluate-answers --with-llm
```

```bash
uv run pytest --cov=nz_open_data_assistant
uv run ruff check .
uv run ruff format --check .
```

## Monitoring

Anonymous local events capture request type, retrieval mode, latency, result count, LLM token use,
and errors. Feedback stores request ID, rating, and an optional comment. The UI reports:

1. requests by day;
2. average latency;
3. helpful/not-helpful feedback;
4. retrieval mode usage;
5. errors by day;
6. LLM tokens by day; and
7. empty-result rate.

The project does not request names or email addresses. Do not place secrets or personal information
in feedback comments.

## Limitations

- Catalogue metadata describes datasets; it does not establish facts inside the underlying data.
- The dependency-free vector representation is reproducible and inexpensive, but a domain embedding
  model may improve semantic recall.
- Auckland resources use several platforms and schemas. Live querying is therefore restricted to
  registered CKAN DataStore and ArcGIS FeatureServer resources.
- Seed records guarantee an offline demo but contain fewer resource details than live ingestion.
- Dataset availability, definitions, accuracy, licence, and update frequency remain the publisher's
  responsibility.
- The assistant does not provide legal, financial, housing, or policy advice.

## Repository layout

```text
app/                         Streamlit application
data/                        Offline seed catalogue
docs/                        PRD, architecture, and evaluation notes
evaluation/                  Ground truth and generated results
scripts/                     Bootstrap helpers
src/nz_open_data_assistant/  Application package
tests/                       Unit tests
Dockerfile                   Reproducible image
docker-compose.yml           API, UI, and ingestion services
```

## Data attribution

Catalogue metadata is obtained from [data.govt.nz](https://www.data.govt.nz/). Each record retains
its original publisher, licence, update information, and source link. Users must follow the licence
and terms attached to each dataset.
