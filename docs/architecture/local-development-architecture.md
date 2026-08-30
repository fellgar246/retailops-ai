# Local Development Architecture

Block 0 target topology. No AWS services are involved.

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
├── db/session.py      Engine, session factory, declarative Base
└── api/
    ├── router.py      Aggregates feature routers
    └── routes/health.py
```

The `create_app()` factory keeps the application testable and lets tests build
isolated instances. Domain modules will be added as sibling packages under
`api/routes/` with matching service and model layers in later blocks.

## Frontend layout

```text
apps/web/src/
├── app/               App Router: layout, landing page, global styles
├── components/        Client components (ApiHealthIndicator)
└── lib/               API base URL config and fetch client
```

All backend calls go through `lib/api-client.ts`, which centralizes the base
URL, timeouts and error normalization (`ApiError`).
