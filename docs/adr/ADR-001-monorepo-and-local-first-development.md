# ADR-001 — Monorepo and Local-First Development Strategy

- **Status:** Accepted
- **Date:** 2026-08-29
- **Scope:** Block 0 — Development Environment & Repository Bootstrap

## Context

RetailOps AI will eventually span a FastAPI backend, a Next.js frontend, machine
learning code and AWS infrastructure. Block 0 must produce a foundation a
developer can clone and run end to end without any cloud account, while keeping
later blocks (forecasting, document intelligence, AWS deployment) unobstructed.

Two questions had to be settled before any code was written: how the components
share a repository, and what a developer needs installed to be productive.

## Decision

### Single monorepo

All components live in one repository under `apps/`, `ml/`, `infra/`, `data/`,
`docs/` and `scripts/`. Backend and frontend keep independent dependency
manifests (`apps/api/pyproject.toml`, `apps/web/package.json`) rather than being
merged into a workspace tool. A root `Makefile` is the single entry point so a
developer never needs to remember per-stack commands.

### Local-first stack

The whole environment runs locally: PostgreSQL through Docker Compose, the API
through uv/uvicorn and the frontend through the Next.js dev server. No AWS
service is required, referenced or mocked in Block 0.

### Tooling

- **uv** for Python dependency management, with a committed `uv.lock`.
- **Ruff** for backend linting and formatting, **mypy** in strict mode, **pytest** for tests.
- **ESLint** (flat config), **Prettier**, **Vitest** with React Testing Library, and TypeScript strict mode for the frontend.
- **Alembic** configured to read `DATABASE_URL` from application settings, with a single empty bootstrap revision so the migration path is proven before any domain model exists.

### Configuration and secrets

Configuration is read from environment variables via `pydantic-settings`.
`.env.example` documents every variable; `.env` and all credential-like files are
git-ignored. PostgreSQL is published on host port 5435 by default to avoid
colliding with locally installed database servers.

### Containers

Both applications have multi-stage Dockerfiles producing non-root runtime images
(the frontend uses Next.js standalone output). Docker Compose runs only
PostgreSQL by default; a `full` profile can run the entire stack. Containers are
built and validated in Block 0 but not deployed.

## Consequences

**Positive**

- One clone, one `make setup`, and the stack runs; onboarding cost is minimal.
- Cross-cutting changes (API contract plus frontend client) land in one commit.
- Quality gates are uniform and enforced identically for both stacks.
- Container images already exist when deployment work begins in a later block.

**Negative**

- The repository will grow large and mixes several toolchains, so contributors need both Python and Node installed.
- Independent manifests mean dependency upgrades happen per application rather than repository-wide.
- CI, once introduced, will need path filtering to avoid rebuilding everything on every change.

**Deferred**

- Deployment topology, AWS infrastructure and CI/CD pipelines are out of scope and will get their own ADRs.
