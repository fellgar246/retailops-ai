# Local runtime

The product runs on a laptop without AWS. PostgreSQL is the only required
container. The API and the operations console start from the IDE.

## Recommended mode

PostgreSQL in Docker; FastAPI and Next.js on the host.

```bash
make setup      # once: .env, Python and Node dependencies
make ready      # PostgreSQL + Alembic head
make demo       # catalog, sales, forecast, sheets, matches, review cases
make dev        # API :8000 and web :3000
```

`make ready` is `env` + `db-up` + `migrate`. `make demo` is safe to re-run: it
upserts sales, skips sheets that are already stored, reuses an unchanged
three-way match, and returns existing review cases.

Open `http://localhost:3000` for the console and `http://localhost:8000/docs`
for the API. The browser calls `NEXT_PUBLIC_API_BASE_URL` (default
`http://localhost:8000`).

## Optional full Compose stack

```bash
make stack-up       # postgres + api + web
make stack-down
```

Compose starts only PostgreSQL unless the `full` profile is selected. The API
container mounts a local document volume (`retailops_document_data`). Use this
when you want the three processes in containers; day-to-day work still uses
`make ready` and `make dev`.

## Quality gate

```bash
make check-app      # format, lint, types, tests, frontend build, reviewer eval
make check          # check-app + live migrations + image builds
make perf           # wide wall-clock samples for generate / ingest / train / match
```

Backend tests use in-memory SQLite. PostgreSQL integration tests skip when the
database is down. `GET /health/db` reports `degraded` / `unavailable` in that
case so the console can show a recoverable failure.
