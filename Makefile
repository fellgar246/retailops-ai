API_DIR := apps/api
WEB_DIR := apps/web
UV := uv --directory $(API_DIR)
NPM := npm --prefix $(WEB_DIR)

.DEFAULT_GOAL := help
.PHONY: help setup env ready demo check check-app check-infra ml-smoke perf \
        dev api web db-up db-down db-logs db-shell migrate migration \
        autogenerate db-reset seed synthetic forecast train documents reconcile \
        review-eval reviews review-feedback aws-smoke \
        test test-api test-web lint lint-api lint-web format format-check typecheck \
        tf-fmt-check tf-validate secrets-scan \
        build docker-build stack-up stack-down clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example when missing
	@[ -f .env ] || (cp .env.example .env && echo "Created .env from .env.example")

setup: env ## Install backend and frontend dependencies
	cd $(API_DIR) && uv sync --all-groups
	$(NPM) install

ready: env db-up migrate ## Recommended start: PostgreSQL in Docker, schema current
	@echo "Database is ready. Next: make demo && make dev"

demo: ready ## Load catalog, sales, forecast, supplier sheets, matches and review cases
	cd $(API_DIR) && uv run retailops-demo --preset development --skip-migrate

dev: ## Run API and web from the IDE (Ctrl-C stops both)
	@$(MAKE) -j2 api web

api: ## Run the FastAPI dev server on :8000
	cd $(API_DIR) && uv run uvicorn retailops_api.main:app --reload --host 0.0.0.0 --port 8000

web: ## Run the Next.js dev server on :3000
	$(NPM) run dev

db-up: env ## Start PostgreSQL and wait until healthy
	docker compose up -d --wait postgres

db-down: ## Stop PostgreSQL (keeps the data volume)
	docker compose down

db-logs: ## Tail PostgreSQL logs
	docker compose logs -f postgres

db-shell: ## Open psql inside the PostgreSQL container
	docker compose exec postgres psql -U $${POSTGRES_USER:-retailops} -d $${POSTGRES_DB:-retailops}

migrate: ## Apply all pending Alembic migrations
	cd $(API_DIR) && uv run alembic upgrade head

migration: ## Create a migration: make migration m="message"
	cd $(API_DIR) && uv run alembic revision -m "$(m)"

autogenerate: ## Autogenerate a migration from the models: make autogenerate m="message"
	cd $(API_DIR) && uv run alembic revision --autogenerate -m "$(m)"

db-reset: ## Drop the schema, re-apply every migration and re-seed
	cd $(API_DIR) && uv run alembic downgrade base && uv run alembic upgrade head
	@$(MAKE) seed

seed: ## Load deterministic development reference data (idempotent)
	cd $(API_DIR) && uv run retailops-seed

synthetic: ## Generate, validate and ingest the development synthetic dataset
	cd $(API_DIR) && uv run retailops-synthetic --output "$(CURDIR)/data/synthetic"

forecast: ## Walk-forward the demand baselines and write the benchmark
	cd $(API_DIR) && uv run retailops-forecast --output "$(CURDIR)/data/forecasts"

train: ## Train the demand model, evaluate it and register a local candidate
	cd $(API_DIR) && uv run retailops-train --output "$(CURDIR)/data/forecasts" --registry "$(CURDIR)/artifacts/models"

documents: ## Ingest a supplier sheet: make documents file=path supplier=SUP-BEVCO
	cd $(API_DIR) && uv run retailops-documents --file "$(file)" --supplier "$(supplier)" --storage "$(CURDIR)/data/documents"

reconcile: ## Three-way match: make reconcile supplier=SUP-BEVCO invoice=INV-1001
	cd $(API_DIR) && uv run retailops-reconcile --supplier "$(supplier)" $(if $(invoice),--invoice "$(invoice)") $(if $(po),--po "$(po)")

review-eval: ## Score the mock reviewer on the versioned evaluation cases
	cd $(API_DIR) && uv run retailops-review-eval --output "$(CURDIR)/data/reviews"

reviews: ## List the human review queue
	cd $(API_DIR) && uv run retailops-review queue

review-feedback: ## Export decided reviews as evaluation rows
	cd $(API_DIR) && uv run retailops-review feedback --output "$(CURDIR)/data/reviews"

perf: ## Time generate, ingest, train, reconciliation and the review queue (tiny scale)
	cd $(API_DIR) && uv run retailops-demo measure --skip-migrate

ml-smoke: ## Score the mock reviewer on the versioned evaluation cases
	@$(MAKE) review-eval

aws-smoke: ## Opt-in live S3/Textract/Bedrock smoke (not part of check-app)
	cd $(API_DIR) && uv run retailops-aws-smoke preflight

check-app: format-check lint typecheck test build ml-smoke ## App quality without images

check-infra: tf-fmt-check tf-validate ## Terraform format and static validation (no apply)

check: check-app check-infra ## Full local quality gate, including schema, images and Terraform
	@$(MAKE) db-up
	@$(MAKE) migrate
	@$(MAKE) docker-build

test: test-api test-web ## Run all tests

test-api: ## Run backend tests
	cd $(API_DIR) && uv run pytest

test-web: ## Run frontend tests
	$(NPM) test

lint: lint-api lint-web ## Lint everything

lint-api: ## Lint the backend
	cd $(API_DIR) && uv run ruff check .

lint-web: ## Lint the frontend
	$(NPM) run lint

format: ## Format backend and frontend sources
	cd $(API_DIR) && uv run ruff format .
	$(NPM) run format

format-check: ## Verify formatting without writing
	cd $(API_DIR) && uv run ruff format --check .
	$(NPM) run format:check

typecheck: ## Type check backend and frontend
	cd $(API_DIR) && uv run mypy
	$(NPM) run typecheck

build: ## Build the frontend production bundle
	$(NPM) run build

tf-fmt-check: ## Verify Terraform formatting
	terraform fmt -check -recursive infra

tf-validate: ## Init (local backend) and validate bootstrap plus every environment
	@echo "terraform validate infra/bootstrap"; \
	terraform -chdir=infra/bootstrap init -backend=false -input=false >/dev/null; \
	terraform -chdir=infra/bootstrap validate; \
	for env in dev staging prod; do \
		echo "terraform validate infra/environments/$$env"; \
		terraform -chdir=infra/environments/$$env init -backend=false -input=false >/dev/null; \
		terraform -chdir=infra/environments/$$env validate; \
	done

secrets-scan: ## Fail if example or Terraform files look like they contain live secrets
	cd $(API_DIR) && uv run pytest tests/test_secret_scan.py

docker-build: ## Build both container images
	docker build -t retailops-api:local $(API_DIR)
	docker build -t retailops-web:local $(WEB_DIR)

stack-up: env ## Run the full stack (db + api + web) in Docker
	docker compose --profile full up -d --build

stack-down: ## Stop the full Docker stack
	docker compose --profile full down

clean: ## Remove build artifacts, caches and installed dependencies
	rm -rf $(WEB_DIR)/node_modules $(WEB_DIR)/.next $(WEB_DIR)/coverage
	rm -rf $(API_DIR)/.venv $(API_DIR)/.pytest_cache $(API_DIR)/.mypy_cache $(API_DIR)/.ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
