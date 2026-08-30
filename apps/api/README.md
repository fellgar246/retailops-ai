# RetailOps AI — API

FastAPI backend for RetailOps AI.

```bash
uv sync --all-groups     # install dependencies
uv run uvicorn retailops_api.main:app --reload   # start on :8000
uv run pytest            # tests
uv run ruff check .      # lint
uv run mypy              # type check
uv run alembic upgrade head   # apply migrations
uv run retailops-seed         # load development reference data (idempotent)
uv run retailops-synthetic    # generate, validate and ingest synthetic history
uv run retailops-forecast     # walk-forward demand baselines and write the benchmark
uv run retailops-train        # train the demand model, evaluate it and register a local candidate
```

Endpoints:

- `GET /health` — liveness, returns `{"status": "ok"}`
- `GET /health/db` — database connectivity
- `GET /docs` — interactive API documentation

Layout:

- `src/retailops_api/db/` — declarative base, naming conventions, session factory, seed data
- `src/retailops_api/domain/` — retail models and data-access helpers
- `src/retailops_api/dataset/` — portable CSV contract, validation and snapshots
- `src/retailops_api/synthetic/` — deterministic catalog, calendar and demand generators
- `src/retailops_api/ingestion/` — idempotent catalog upsert, batch sales upsert, run report
- `src/retailops_api/forecasting/` — weekly demand frame, features, baselines, histogram-GBM training, local model registry
- `migrations/` — Alembic revisions

The retail schema is documented in
[`docs/architecture/retail-domain-er-model.md`](../../docs/architecture/retail-domain-er-model.md).

Tests default to in-memory SQLite. PostgreSQL integration tests create their own
throwaway databases and skip when the server is unreachable; set
`RETAILOPS_SKIP_POSTGRES_TESTS=1` to skip them explicitly.
