# Local Development Architecture

Current local topology. AWS adapters stay disabled unless feature flags are
set. Startup commands and the recommended mode are in
[local runtime](local-runtime.md). The console walkthrough is in
[the local demo note](local-demo.md). Cloud adapter notes are in
[AWS adapters](aws-adapters.md).

```text
Browser
   |
   v
Next.js (App Router)          apps/web
localhost:3000
   |  fetch NEXT_PUBLIC_API_BASE_URL/health
   v
FastAPI                       apps/api
localhost:8000
   |  SQLAlchemy + psycopg (DATABASE_URL)
   v
PostgreSQL 16 (Docker)        docker-compose.yml
localhost:5435 -> container 5432
volume: retailops_postgres_data
```

## Components

| Component  | Location   | Runtime            | Entry point                        |
| ---------- | ---------- | ------------------ | ---------------------------------- |
| Web        | `apps/web` | Node ≥ 20.11       | `npm run dev` / `make web`         |
| API        | `apps/api` | Python 3.12 + uv   | `uvicorn retailops_api.main:app`   |
| Database   | Docker     | postgres:16-alpine | `make db-up`                       |
| Migrations | `apps/api/migrations` | Alembic | `make migrate`                     |

## Backend layout

```text
apps/api/src/retailops_api/
├── main.py            create_app() factory, CORS, router wiring
├── core/config.py     Settings loaded from environment
├── db/
│   ├── base.py        Declarative Base, naming convention, shared mixins
│   ├── session.py     Engine and session factory
│   └── seed.py        Deterministic development reference data
├── domain/
│   ├── models/        Retail catalog, sales, documents, procurement tables
│   └── repositories.py  Lookups by business code, bulk sales writes
├── dataset/           Portable CSV contract, validation, snapshots
├── synthetic/         Deterministic catalog, calendar and demand
├── ingestion/         Catalog and sales upsert
├── forecasting/       Weekly demand frame, baselines, walk-forward backtest
├── documents/         Supplier-sheet intake, local storage, deterministic rules
├── procurement/       Purchase orders, receipts, invoices, three-way match
├── review/            Reviewer contract, mock, routing, evaluation harness
└── api/
    ├── router.py      Aggregates feature routers
    └── routes/health.py
```

The `create_app()` factory keeps the application testable and lets tests build
isolated instances.

`db/base.py` owns the metadata that Alembic compares against, and
`domain/models/__init__.py` re-exports every model so importing it registers the
full schema. The domain layer stops at persistence; HTTP routes for these
entities do not exist yet.

See [the retail domain ER model](retail-domain-er-model.md) for the catalog
and sales schema, [forecast evaluation](forecasting-baselines.md) for the
weekly demand frame and baselines, [supplier document intake](supplier-document-intake.md)
for stored supplier sheets and deterministic findings,
[procurement and reconciliation](procurement-reconciliation.md) for purchase
orders, receipts, invoices and the three-way match, and
[AI review](ai-review.md) for the reviewer contract, mock and evaluation.

## Frontend layout

```text
apps/web/src/
├── app/               App Router: layout, landing page, global styles
├── components/        Client components (ApiHealthIndicator)
└── lib/               API base URL config and fetch client
```

All backend calls go through `lib/api-client.ts`, which centralizes the base
URL, timeouts and error normalization (`ApiError`).
