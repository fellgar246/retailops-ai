# RetailOps AI — Block 0 Master Plan

## Block 0 — Development Environment & Repository Bootstrap

---

## 1. Objective

Establish the complete local development foundation for RetailOps AI.

At the end of Block 0, a developer should be able to clone the repository, install dependencies, start the development environment and run automated quality checks without requiring any AWS infrastructure.

Block 0 must not implement retail business functionality.

Its purpose is to create the engineering foundation on which subsequent blocks will be built.

---

## 2. Expected final state

The repository should contain a working monorepo with:

- FastAPI backend
- Next.js frontend
- PostgreSQL development database
- Docker Compose
- Python dependency management
- frontend dependency management
- database migration foundation
- testing infrastructure
- linting and formatting
- environment configuration
- Makefile developer commands
- documentation
- initial architecture decisions
- initial Git history

The complete local stack should be reproducible.

---

## 3. Local architecture

```text
Browser
   |
   v
Next.js
localhost:3000
   |
   v
FastAPI
localhost:8000
   |
   v
PostgreSQL
localhost:5432
```

AWS services are explicitly excluded from Block 0.

---

## 4. Repository target

```text
retailops-ai/
├── apps/
│   ├── api/
│   │   ├── src/
│   │   ├── tests/
│   │   ├── migrations/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── web/
│       ├── src/
│       ├── tests/
│       ├── package.json
│       └── Dockerfile
├── ml/
│   ├── forecasting/
│   └── notebooks/
├── infra/
│   ├── modules/
│   └── environments/
│       ├── dev/
│       ├── staging/
│       └── prod/
├── data/
│   ├── raw/
│   ├── processed/
│   └── synthetic/
├── docs/
│   ├── architecture/
│   └── adr/
├── scripts/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── Makefile
└── README.md
```

---

## 5. Engineering requirements

### Backend

FastAPI application must:

- start successfully
- expose `GET /health`
- return HTTP 200
- include automated tests

Example response:

```json
{
  "status": "ok"
}
```

The backend should use a maintainable application structure suitable for later growth.

### Frontend

Next.js application must:

- start successfully
- provide an initial landing page
- include a basic API connectivity strategy
- pass linting
- support automated tests

No final UI design is required.

### Database

PostgreSQL must run locally using Docker Compose.

Block 0 should configure:

- database container
- health check
- persistent local volume
- environment variables

No retail tables need to exist yet.

### Database migration foundation

Alembic must be configured and capable of connecting to the development database.

No domain migrations are required.

The migration framework simply needs to be functional.

---

## 6. Developer experience

The project should provide commands similar to:

```bash
make setup
make dev
make db-up
make db-down
make test
make lint
make format
make migrate
make clean
```

Exact implementation may vary, but the workflow should remain simple.

---

## 7. Environment configuration

Provide:

```text
.env.example
```

Never commit:

```text
.env
credentials
private keys
terraform state
AWS credentials
```

Application configuration should use environment variables.

---

## 8. Code quality

### Backend

Suggested tooling:

- Ruff
- mypy
- pytest

The backend should include:

- formatter
- linter
- type checking
- tests

### Frontend

Suggested tooling:

- ESLint
- Prettier
- Vitest
- TypeScript strict mode

---

## 9. Docker

Block 0 should provide Dockerfiles for:

- backend
- frontend

Docker Compose should at minimum support PostgreSQL.

Optionally it may support the entire local stack.

Development should still allow API and frontend to run directly from the IDE.

---

## 10. Documentation

Block 0 should produce:

- root `README.md`
- local setup instructions
- development commands
- repository structure
- architecture overview
- at least one ADR describing key bootstrap decisions

---

## 11. Security baseline

The repository should:

- avoid committed secrets
- use `.env.example`
- ignore Terraform state
- ignore generated local data where appropriate
- avoid hardcoded credentials
- prepare the project for later AWS credential isolation

---

## 12. Definition of Done

Block 0 is complete when all of the following are true:

- repository structure exists
- backend starts locally
- frontend starts locally
- PostgreSQL starts through Docker Compose
- backend `/health` returns HTTP 200
- backend tests pass
- frontend tests pass
- backend linting passes
- frontend linting passes
- type checking passes where configured
- Alembic is functional
- Makefile commands work
- `.env.example` exists
- `.gitignore` protects secrets and generated files
- Dockerfiles build successfully
- README explains how to run the project
- architecture decisions are documented
- working tree is clean after final commit

---

## 13. Explicitly out of scope

Do not implement during Block 0:

- retail domain entities
- suppliers
- products
- stores
- purchase orders
- invoices
- forecasting
- ML models
- Bedrock
- Textract
- SageMaker
- AWS infrastructure
- Terraform resources
- CI/CD deployment
- authentication
- production observability

These belong to later blocks.

---

## 14. Delivery approach

Block 0 will be implemented through a sequence of small specs.

Each spec should:

1. have one clear objective
2. have a narrow scope
3. produce a verifiable result
4. include validation criteria
5. avoid unrelated refactoring
6. leave the repository in a working state

The implementation order is defined in the Block 0 Specs Plan.
