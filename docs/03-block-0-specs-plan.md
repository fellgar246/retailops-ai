# RetailOps AI — Block 0 Specs Plan

## Development Environment & Repository Bootstrap

This document decomposes Block 0 into small implementation specs intended to be executed sequentially from an IDE coding agent.

Total specs: **14**

---

# Spec 01 — Repository Foundation

## Objective

Create the initial monorepo structure and root-level project files.

## Scope

Create:

- `apps/api`
- `apps/web`
- `ml/forecasting`
- `ml/notebooks`
- `infra/modules`
- `infra/environments/dev`
- `infra/environments/staging`
- `infra/environments/prod`
- `data/raw`
- `data/processed`
- `data/synthetic`
- `docs/architecture`
- `docs/adr`
- `scripts`

Create initial:

- `README.md`
- `.gitignore`
- `.env.example`

## Validation

- Repository structure matches the master plan.
- No generated or secret files are committed.
- Git working tree is clean after commit.

---

# Spec 02 — Python Backend Dependency Foundation

## Objective

Initialize the backend Python project.

## Scope

Configure:

- Python 3.12
- `pyproject.toml`
- dependency management
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- Alembic
- pytest
- Ruff
- mypy

Recommended package manager:

- `uv`

## Validation

- dependencies install successfully
- Python project imports correctly
- lint/test commands are callable

---

# Spec 03 — FastAPI Application Bootstrap

## Objective

Create the initial FastAPI application.

## Scope

Create a maintainable application structure under:

```text
apps/api/src/
```

Include:

- application entry point
- application configuration
- routing foundation
- `GET /health`

Expected response:

```json
{
  "status": "ok"
}
```

## Validation

- application starts locally
- `/health` returns HTTP 200
- API docs load successfully

---

# Spec 04 — Backend Test Foundation

## Objective

Establish backend automated testing.

## Scope

Configure pytest and implement initial tests for:

- application creation
- `/health`
- expected status code
- expected response body

## Validation

```bash
pytest
```

must pass with zero failures.

---

# Spec 05 — Backend Code Quality

## Objective

Establish backend linting, formatting and type checking.

## Scope

Configure:

- Ruff linting
- Ruff formatting
- mypy

Define commands for:

- lint
- format
- format check
- typecheck

## Validation

All quality checks pass against the current backend.

---

# Spec 06 — PostgreSQL Local Development Service

## Objective

Provide a reproducible local PostgreSQL instance.

## Scope

Create or extend:

```text
docker-compose.yml
```

Configure:

- PostgreSQL
- environment variables
- named volume
- health check
- host port mapping

No domain tables are required.

## Validation

- container starts successfully
- health check becomes healthy
- database accepts connections
- data persists across container restart

---

# Spec 07 — Backend Database Configuration

## Objective

Allow FastAPI to configure a PostgreSQL connection without introducing domain models.

## Scope

Add:

- database URL configuration
- SQLAlchemy engine foundation
- session foundation
- safe startup configuration

Do not create retail tables.

## Validation

- backend starts with database configuration
- database connection can be established
- tests remain passing

---

# Spec 08 — Alembic Migration Foundation

## Objective

Configure database migrations.

## Scope

Initialize and configure Alembic to use application settings.

Do not introduce business-domain migrations.

## Validation

- Alembic loads configuration correctly
- current migration state can be inspected
- an empty or bootstrap migration can execute if required
- database upgrade command works

---

# Spec 09 — Next.js Frontend Bootstrap

## Objective

Create the initial web application.

## Scope

Initialize:

- Next.js
- TypeScript
- React
- App Router

Configure:

- strict TypeScript
- environment configuration
- initial landing page

The page should identify the application as:

**RetailOps AI**

## Validation

- frontend starts successfully
- page loads at `localhost:3000`
- production build succeeds

---

# Spec 10 — Frontend Quality and Testing Foundation

## Objective

Establish frontend engineering quality gates.

## Scope

Configure:

- ESLint
- Prettier
- Vitest
- React Testing Library where appropriate

Add at least one meaningful initial UI test.

## Validation

- lint passes
- formatting check passes
- tests pass
- TypeScript check passes
- production build passes

---

# Spec 11 — Frontend/API Connectivity Foundation

## Objective

Prepare the frontend to communicate with FastAPI.

## Scope

Add:

- public API base URL environment variable
- lightweight API client abstraction
- health request integration or connectivity indicator

Avoid introducing retail functionality.

## Validation

When both applications are running:

- frontend can request backend `/health`
- connectivity errors are handled gracefully

---

# Spec 12 — Dockerfiles and Container Build Validation

## Objective

Make both applications containerizable.

## Scope

Create:

```text
apps/api/Dockerfile
apps/web/Dockerfile
```

Use reasonable production-oriented multi-stage builds where applicable.

Do not deploy them.

## Validation

Both images build successfully.

Optional:

- entire stack can run through Docker Compose

---

# Spec 13 — Developer Workflow and Makefile

## Objective

Provide a simple and consistent local developer experience.

## Scope

Create a root `Makefile` with commands such as:

```bash
make setup
make dev
make api
make web
make db-up
make db-down
make migrate
make test
make lint
make format
make typecheck
make build
make clean
```

Exact targets may be adapted to the final tooling.

## Validation

Each documented target works or delegates correctly.

---

# Spec 14 — Documentation, ADR and Block 0 Final Validation

## Objective

Finalize and validate the engineering foundation.

## Scope

Update `README.md` with:

- project summary
- prerequisites
- installation
- environment setup
- repository structure
- local development
- tests
- linting
- Docker usage
- database commands

Create at least one ADR covering major bootstrap decisions, for example:

```text
ADR-001 — Monorepo and Local-First Development Strategy
```

Run complete validation.

## Final validation checklist

Backend:

- FastAPI starts
- `/health` = 200
- tests pass
- lint passes
- format check passes
- type checking passes

Frontend:

- Next.js starts
- tests pass
- lint passes
- format check passes
- TypeScript passes
- production build passes

Database:

- PostgreSQL starts
- health check passes
- persistence works
- Alembic works

Containers:

- API image builds
- Web image builds

Repository:

- documentation is current
- `.env.example` is current
- no secrets are tracked
- working tree is clean

## Completion criterion

When Spec 14 is complete, **Block 0 — Development Environment & Repository Bootstrap** is considered finished and the project is ready for Block 1.
