# RetailOps AI

Retail operations intelligence platform. This repository currently contains:

- **The engineering foundation** — a FastAPI backend, a Next.js frontend, a local PostgreSQL database and the tooling needed to develop, test and containerize them.
- **The core retail domain** — the product catalog (categories, products, suppliers, supplier terms, stores) and the daily sales-history model, with migrations, data-access helpers, development seed data and a deterministic synthetic history generator.
- **Forecast evaluation** — a weekly category-demand frame, time-based splits, naive / seasonal-naive / moving-average baselines, walk-forward backtesting, and persisted forecast runs.
- **ML forecasting** — calendar, lag and rolling features, a histogram gradient-boosted demand model, champion/challenger promotion, and a local filesystem model registry.
- **Supplier document intake** — store a CSV, XLSX or text PDF locally, parse it onto a canonical offer sheet, run deterministic validation against the catalog, and persist findings.

AI review, hosted object storage, document-analysis APIs and AWS deployment are not implemented yet.

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
| `DOCUMENT_STORAGE_ROOT`    | Local root for stored supplier files (optional; default `data/documents`) |

PostgreSQL is published on host port **5435** by default so it never collides
with a locally installed PostgreSQL. Change `POSTGRES_PORT` if you prefer 5432.

## Repository structure

```text
retailops/
├── apps/
│   ├── api/          FastAPI backend (src layout, tests, Alembic migrations)
│   └── web/          Next.js frontend (App Router, TypeScript, Vitest)
├── ml/               Optional notebooks (training lives in the API package)
├── artifacts/        Local model registry versions (git-ignored)
├── infra/            Terraform modules and environments (not yet implemented)
├── data/             Local raw/processed/synthetic/document data (git-ignored)
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
make forecast   # walk-forward the demand baselines and write the benchmark
make train      # train the demand model, evaluate it and register a local candidate
make documents file=apps/api/tests/fixtures/supplier_documents/valid.csv supplier=SUP-BEVCO
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
make forecast                    # walk-forward baselines; writes data/forecasts/
make train                       # train the demand model; writes data/forecasts/ and artifacts/models/
make documents file=… supplier=… # store, parse and validate a supplier sheet
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
| ForecastRun | `forecast_runs` | One baseline forecast at one origin (model, cutoff, horizon) |
| ForecastPrediction | `forecast_predictions` | One predicted week per store and category, with actual when known |
| SupplierDocument | `supplier_documents` | A stored supplier file (key, checksum, type, status) |
| DocumentFinding | `document_findings` | One deterministic observation about that file |

`make seed` loads a deterministic development catalog. It is idempotent, so
running it repeatedly neither duplicates nor disturbs existing rows.

`make synthetic` is the one command that regenerates the development dataset:
it writes CSV files under `data/synthetic/`, validates them, and upserts the
catalog and daily sales into the configured database. Re-running it is safe.
The same seed and configuration always produce the same checksum. The file
contract (columns, keys, units, date and decimal formats) is documented in
[the synthetic dataset note](docs/architecture/synthetic-retail-dataset.md).

## Forecast evaluation

The first demand problem is **weekly category demand per store**: daily
`units_sold` summed across the products in a category, for each store, on
each complete ISO week (Monday–Sunday). Incomplete edge weeks are dropped;
a store–category week with no sales is stored as zero. The default horizon
is four weeks.

Splits are time-based only. A later week never appears in an earlier slice.
Evaluation is walk-forward (rolling-origin): at each cutoff the model may
read history through that week and must forecast the next four. Three
baselines share one prediction interface so a later model can be compared
on the same folds:

| Model | Rule |
| --- | --- |
| `naive` | Repeat the last observed week |
| `seasonal_naive` | Same week a configurable lag ago (default 52); falls back to naive when that week is missing |
| `moving_average` | Mean of the last *n* weeks (default 4), never reading past the cutoff |

Metrics are MAE, RMSE, WAPE and mean forecast bias. When every actual is
zero, WAPE is `0` if every prediction is also zero and `1` otherwise.

`make forecast` rebuilds the development history in memory, walks the three
baselines forward, and writes `data/forecasts/benchmark.json`,
`data/forecasts/benchmark.md` and the weekly frame CSV. Metric definitions
and the backtest rules are also in
[the forecasting note](docs/architecture/forecasting-baselines.md).

Pass `--persist` to store each fold as a `ForecastRun` with its predictions.

## ML forecasting and the local registry

Features available at an origin are the calendar of the target week, lags and
shifted rolling statistics of history on or before the cutoff, lagged price /
discount / promotion / stock, and store or category identifiers. The target
week's own sales measures are excluded: using them would leak the label.

`make train` builds that matrix, fits one histogram gradient-boosted model
with an explicit config, scores the candidate against the three baselines
(and the current champion, when one exists) from the locked train-end
origin, writes a reloadable artifact, and registers it under
`artifacts/models/category-forecast/v001`. Promotion requires a strict WAPE
win against every comparison model **and** no MAE regression versus the
champion (or the best baseline when there is no champion). A single-metric
win is not enough. Pass `--promote` to apply that policy and set the
champion when both gates pass.

Reload a version with the same `predict(history, cutoff, horizon)` interface
the baselines use. The on-disk package includes the booster, feature list,
training config, metrics, data fingerprint and runtime versions, so it does
not depend on notebook state.

The registry operations (register, list, get, update approval, get champion)
are storage-neutral. The local implementation is a directory of versions;
the same calls map onto SageMaker Model Registry (`CreateModelPackage`,
`ModelPackageVersion`, `ModelApprovalStatus`, the approved package an
endpoint loads). Details are in
[the ML forecasting note](docs/architecture/ml-forecasting.md).

## Supplier document intake

`make documents` stores the file under `data/documents/` (generated keys, no
path traversal), writes a `supplier_documents` row, parses CSV / XLSX / a
text-based PDF onto a canonical offer sheet, and runs deterministic rules:
required fields, EAN shape, cost and quantity bounds, configured VAT rates,
in-file duplicates, then catalog cross-checks (supplier SKU mapped elsewhere,
EAN already on a product, cost increase vs current term, category mismatch).
Findings are persisted; the document ends `review_ready` or `parse_failed`.
Storage is a contract — the local directory is one implementation. Details
are in [the intake note](docs/architecture/supplier-document-intake.md).

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
- [ADR-004 — Forecast Evaluation and Baselines](docs/adr/ADR-004-forecast-evaluation.md)
- [ADR-005 — ML Forecasting and Local Model Registry](docs/adr/ADR-005-ml-forecasting-and-model-registry.md)
- [ADR-006 — Supplier Document Intake and Deterministic Validation](docs/adr/ADR-006-supplier-document-intake.md)

## Security baseline

Secrets are never committed. `.gitignore` excludes `.env` files, credentials,
private keys, Terraform state and local data directories. Application
configuration is read exclusively from environment variables.
