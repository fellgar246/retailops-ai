# RetailOps AI — API

FastAPI backend for RetailOps AI.

```bash
uv sync --all-groups     # install dependencies
uv run uvicorn retailops_api.main:app --reload   # start on :8000
uv run pytest            # tests
uv run ruff check .      # lint
uv run mypy              # type check
uv run alembic upgrade head   # apply migrations
uv run retailops-demo         # one-command local dataset (migrate + seed + ingest + reviews)
uv run retailops-seed         # load development reference data (idempotent)
uv run retailops-synthetic    # generate, validate and ingest synthetic history
uv run retailops-forecast     # walk-forward demand baselines and write the benchmark
uv run retailops-train        # train the demand model, evaluate it and register a local candidate
uv run retailops-documents    # store, parse and validate a supplier sheet
uv run retailops-reconcile    # three-way match a purchase order or invoice
uv run retailops-review-eval  # score the mock reviewer and write an evaluation report
uv run retailops-review queue # list the human review queue
```

Endpoints:

- `GET /health` — liveness, returns `{"status": "ok"}`
- `GET /health/db` — database connectivity
- `GET /ops/overview` — operational counts from persisted facts
- `GET /forecasts` — forecast runs
- `GET /documents` — supplier documents and findings
- `GET /reconciliations` — three-way match runs and exceptions
- `GET /reviews` — human review queue
- `GET /reviews/metrics` — open cases and decision rates
- `GET /reviews/feedback` — decided cases as evaluation rows
- `GET /audit` — recent review audit events
- `GET /search` — lookup across documents, reviews, exceptions and forecasts
- `GET /docs` — interactive API documentation

Layout:

- `src/retailops_api/db/` — declarative base, naming conventions, session factory, seed data
- `src/retailops_api/domain/` — retail models and data-access helpers
- `src/retailops_api/dataset/` — portable CSV contract, validation and snapshots
- `src/retailops_api/synthetic/` — deterministic catalog, calendar and demand generators
- `src/retailops_api/ingestion/` — idempotent catalog upsert, batch sales upsert, run report
- `src/retailops_api/forecasting/` — weekly demand frame, features, baselines, histogram-GBM training, local and SageMaker model registries
- `src/retailops_api/documents/` — supplier-sheet intake, local and S3 storage, parsers, Textract translation and deterministic rules
- `src/retailops_api/procurement/` — purchase orders, receipts, invoices and deterministic three-way match
- `src/retailops_api/review/` — reviewer contract, structured results, mock and Bedrock providers, routing, evaluation, human-review cases and metrics
- `src/retailops_api/core/` — settings, typed AWS config and adapter factories
- `src/retailops_api/demo/` — one-command local dataset for development and demos
- `src/retailops_api/ops/` — overview counts and cross-entity search
- `migrations/` — Alembic revisions

The retail schema is documented in
[`docs/architecture/retail-domain-er-model.md`](../../docs/architecture/retail-domain-er-model.md).

Tests default to in-memory SQLite. PostgreSQL integration tests create their own
throwaway databases and skip when the server is unreachable; set
`RETAILOPS_SKIP_POSTGRES_TESTS=1` to skip them explicitly.
