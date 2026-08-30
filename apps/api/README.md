# RetailOps AI — API

FastAPI backend for RetailOps AI.

```bash
uv sync --all-groups     # install dependencies
uv run uvicorn retailops_api.main:app --reload   # start on :8000
uv run pytest            # tests
uv run ruff check .      # lint
uv run mypy              # type check
```

Endpoints:

- `GET /health` — liveness, returns `{"status": "ok"}`
- `GET /health/db` — database connectivity
- `GET /docs` — interactive API documentation
