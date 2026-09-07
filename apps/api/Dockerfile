# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

ARG ENABLE_PADDLEOCR=false
ARG ENABLE_AWS=false

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev \
    $(if [ "$ENABLE_PADDLEOCR" = "true" ]; then echo --extra paddleocr; fi) \
    $(if [ "$ENABLE_AWS" = "true" ]; then echo --group aws; fi)

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev \
    $(if [ "$ENABLE_PADDLEOCR" = "true" ]; then echo --extra paddleocr; fi) \
    $(if [ "$ENABLE_AWS" = "true" ]; then echo --group aws; fi)


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1001 appuser \
    && mkdir -p /app/data/documents \
    && chown -R appuser:appuser /app/data

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser alembic.ini ./

USER appuser

EXPOSE 8000

CMD ["uvicorn", "retailops_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
