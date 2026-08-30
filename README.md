# RetailOps AI

Retail operations intelligence platform. This repository currently contains the
**Block 0** engineering foundation: a FastAPI backend, a Next.js frontend, a
local PostgreSQL database and the tooling needed to develop, test and containerize
them. No retail domain functionality is implemented yet.

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
├── ml/               Forecasting code and notebooks (later blocks)
├── infra/            Terraform modules and environments (later blocks)
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
make migration m="add products"  # create a new revision
```

Data lives in the named volume `retailops_postgres_data` and survives restarts.

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

## Security baseline

Secrets are never committed. `.gitignore` excludes `.env` files, credentials,
private keys, Terraform state and local data directories. Application
configuration is read exclusively from environment variables.
