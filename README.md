# RetailOps AI

Retail operations intelligence platform. This repository currently contains:

- **The engineering foundation** — a FastAPI backend, a Next.js frontend, a local PostgreSQL database and the tooling needed to develop, test and containerize them.
- **The core retail domain** — the product catalog (categories, products, suppliers, supplier terms, stores) and the daily sales-history model, with migrations, data-access helpers, development seed data and a deterministic synthetic history generator.

Forecasting, document intelligence and AWS deployment are not implemented yet.

## Prerequisites

| Tool           | Version    | Notes                                     |
| -------------- | ---------- | ----------------------------------------- |
| Python         | 3.12       | Backend runtime                           |
| uv             | ≥ 0.5      | Python dependency manager                 |
| Node.js        | ≥ 20.11    | Frontend runtime                          |
| Docker         | ≥ 24       | PostgreSQL and image builds               |
| GNU Make       | any        | Developer command entry point             |

## Installation

```bash
git clone <repository-url> retailops
cd retailops
make setup      # creates .env, installs backend + frontend dependencies
```

## Environment setup

Configuration lives in environment variables. `make setup` copies
`.env.example` to `.env`; adjust it as needed. `.env` is never committed.

| Variable                   | Purpose                                     |
| -------------------------- | ------------------------------------------- |
| `POSTGRES_*`               | Database credentials and host port           |
| `DATABASE_URL`             | SQLAlchemy/Alembic connection string         |
| `CORS_ORIGINS`             | Comma-separated origins allowed by the API   |
| `NEXT_PUBLIC_API_BASE_URL` | API base URL used by the browser             |

PostgreSQL is published on host port **5435** by default so it never collides
with a locally installed PostgreSQL. Change `POSTGRES_PORT` if you prefer 5432.

## Repository structure

```text
retailops/
├── apps/
│   ├── api/          FastAPI backend (src layout, tests, Alembic migrations)
│   └── web/          Next.js frontend (App Router, TypeScript, Vitest)
├── ml/               Forecasting code and notebooks (not yet implemented)
├── infra/            Terraform modules and environments (not yet implemented)
├── data/             Local raw/processed/synthetic data (git-ignored)
├── docs/             Architecture notes and ADRs
├── scripts/          Developer scripts
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Local development

```bash
make db-up      # start PostgreSQL and wait until healthy
make migrate    # apply Alembic migrations
make seed       # load development reference data (safe to re-run)
make synthetic  # generate, validate and ingest a year of synthetic sales
make dev        # run API (:8000) and web (:3000) together
```

Individually:

```bash
make api        # http://localhost:8000  (docs at /docs)
make web        # http://localhost:3000
```

The landing page shows an API connectivity indicator backed by `GET /health`.

## Tests

```bash
make test       # backend (pytest) + frontend (Vitest)
make test-api
make test-web
```

Most backend tests run against in-memory SQLite and need nothing running. The
PostgreSQL integration tests — migrations, exact numeric scale, timezone-aware
timestamps — create and drop their own throwaway databases on the configured
server, so `make db-up` first to include them. They skip automatically when
PostgreSQL is unreachable, or when `RETAILOPS_SKIP_POSTGRES_TESTS` is set.

## Linting, formatting and types

```bash
make lint          # Ruff + ESLint
make format        # Ruff format + Prettier
make format-check  # verify formatting only
make typecheck     # mypy (strict) + tsc --noEmit
make build         # Next.js production build
```

## Database commands

```bash
make db-up                       # start PostgreSQL (healthy-wait)
make db-down                     # stop it, keeping the data volume
make db-logs                     # tail logs
make db-shell                    # psql session inside the container
make migrate                     # alembic upgrade head
make migration m="add products"  # create an empty revision
make autogenerate m="add x"      # create a revision from model changes
make seed                        # load reference data (idempotent)
make synthetic                   # regenerate and ingest synthetic history
make db-reset                    # rebuild the schema from scratch and re-seed
```

Data lives in the named volume `retailops_postgres_data` and survives restarts.

## Retail domain model

The catalog and sales schema is documented in
[the ER model note](docs/architecture/retail-domain-er-model.md), with the
modelling rationale in [ADR-002](docs/adr/ADR-002-core-retail-domain-model.md).

| Entity | Table | Purpose |
| ------ | ----- | ------- |
| Category | `categories` | Merchandise hierarchy (self-referencing tree) |
| Product | `products` | Sellable items, identified by SKU |
| Supplier | `suppliers` | Vendors the business buys from |
| SupplierProduct | `supplier_products` | Cost, case pack, minimum order and lead time per supplier/product pairing |
| Store | `stores` | Selling locations, grouped by region and type |
| SalesRecord | `sales_records` | One row per store, product and trading day |

`make seed` loads a deterministic development catalog. It is idempotent, so
running it repeatedly neither duplicates nor disturbs existing rows.

`make synthetic` is the one command that regenerates the development dataset:
it writes CSV files under `data/synthetic/`, validates them, and upserts the
catalog and daily sales into the configured database. Re-running it is safe.
The same seed and configuration always produce the same checksum. The file
contract (columns, keys, units, date and decimal formats) is documented in
[the synthetic dataset note](docs/architecture/synthetic-retail-dataset.md).

## Docker

```bash
make docker-build   # build retailops-api:local and retailops-web:local
make stack-up       # run db + api + web through Docker Compose
make stack-down     # stop the full stack
```

Both images use multi-stage builds and run as non-root users. Compose runs only
PostgreSQL by default; the `full` profile adds the API and web services.

## API endpoints

| Method | Path         | Description                     |
| ------ | ------------ | ------------------------------- |
| GET    | `/health`    | Liveness, returns `{"status": "ok"}` |
| GET    | `/health/db` | Database connectivity check     |
| GET    | `/docs`      | OpenAPI documentation           |

## Architecture decisions

- [ADR-001 — Monorepo and Local-First Development Strategy](docs/adr/ADR-001-monorepo-and-local-first-development.md)
- [ADR-002 — Core Retail Domain Model and Persistence Conventions](docs/adr/ADR-002-core-retail-domain-model.md)
- [ADR-003 — Synthetic Retail Dataset and Ingestion](docs/adr/ADR-003-synthetic-data-and-ingestion.md)

## Security baseline

Secrets are never committed. `.gitignore` excludes `.env` files, credentials,
private keys, Terraform state and local data directories. Application
configuration is read exclusively from environment variables.
