# Architecture

## Design principles

The system is built around four constraints: it must run without paid services, cite every catalogue
recommendation, fail safely when evidence is absent, and keep arbitrary model output away from live
data-query execution.

## Components

### Ingestion

`CatalogueClient` calls CKAN `package_search`, normalizes records into the `Dataset` model, removes
HTML, and preserves resources, publisher, licence, and update metadata. Topic filters require both an
Auckland signal and a population, housing, or transport signal. Upserts are idempotent.

The checked-in seed contains real catalogue IDs verified during initial development. It makes tests
and the first application start deterministic. Live ingestion enriches or replaces those records.

### Storage and retrieval

SQLite stores canonical JSON records, deterministic vectors, feedback, and events. FTS5 supplies a
BM25 lexical index. Vector retrieval uses a normalized feature-hashing representation; this avoids a
large model download and guarantees identical vectors across environments.

Hybrid mode combines lexical and vector ranks with reciprocal-rank fusion. Query rewriting adds a
small, transparent domain synonym set. Reranking boosts query overlap in title, tags, groups, and
publisher. Retrieval components can be evaluated independently.

### Answering

Extractive mode formats the highest-ranked records and explicitly labels them as catalogue
recommendations. When `OPENAI_API_KEY` is present, the same evidence is passed to a zero-temperature
generation call with instructions to cite sources, avoid unseen facts, and state limitations.

### Safe data tools

Data tools accept a Pydantic `DataQueryPlan`; they do not accept raw SQL. Execution checks that:

- the dataset is present in the local registry;
- the resource belongs to that dataset;
- every field exists in the live resource schema;
- filters use an enumerated operator;
- CKAN queries use supported equality filters;
- ArcGIS string values are escaped;
- requests are read-only and return at most 100 rows.

The tool endpoint is disabled by default. This avoids accidental external calls in an offline demo.

### Interface and observability

FastAPI owns application logic. Streamlit acts as an API client and provides the assistant, dataset
explorer, feedback controls, and monitoring dashboard. API and UI are separate Compose services.

SQLite's write-ahead log supports concurrent API requests and dashboard reads at project scale. A
larger deployment should migrate event and feedback tables to PostgreSQL.

## Trust boundaries

```text
User text (untrusted)
  -> validated request model
  -> retrieval over local records
  -> optional LLM output (display only)

Structured data plan (untrusted)
  -> Pydantic validation
  -> registered resource check
  -> live schema field allowlist
  -> adapter-generated read-only request
```

No LLM-generated string is executed as SQL or shell input.

