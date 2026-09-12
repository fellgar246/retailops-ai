# RetailOps AI

Retail operations intelligence platform.

> **Status: closed.** The project is complete as a portfolio piece and the
> cloud environment has been torn down. Everything runs locally with no AWS
> account and no cost — see [Local development](#local-development).
> What was built, what it proved and what it deliberately stopped short of
> are recorded in [the closure note](docs/project-closure.md).

This repository contains:

- **The engineering foundation** — a FastAPI backend, a Next.js frontend, a local PostgreSQL database and the tooling needed to develop, test and containerize them.
- **The core retail domain** — the product catalog (categories, products, suppliers, supplier terms, stores) and the daily sales-history model, with migrations, data-access helpers, development seed data and a deterministic synthetic history generator.
- **Forecast evaluation** — a weekly category-demand frame, time-based splits, naive / seasonal-naive / moving-average baselines, walk-forward backtesting, and persisted forecast runs.
- **ML forecasting** — calendar, lag and rolling features, a histogram gradient-boosted demand model, champion/challenger promotion, and a local filesystem model registry.
- **Supplier document intake** — store a CSV, XLSX or PDF, parse it onto a canonical offer sheet (Textract for scanned PDF/image when AWS is enabled), run deterministic validation against the catalog, and persist findings.
- **Procurement and reconciliation** — persist purchase orders, goods receipts and supplier invoices, then run a deterministic three-way match with explicit tolerances.
- **AI review contracts** — a provider-neutral reviewer, structured and validated outputs, a fixture mock, conservative routing to human review, and a versioned evaluation harness.
- **Human review** — persisted cases on document findings and reconciliation exceptions, an immutable AI snapshot, controlled decisions, an append-only audit log, a feedback export and a metrics API.
- **Authentication** — sign-in against a local development provider or a hosted user pool, two roles, and a verified subject on every review decision and audit event.
- **Operator intake** — upload a supplier sheet, reconcile an invoice or evaluate demand from the console; the work runs behind a queue and the page follows the job until it settles.
- **Operations web app** — a desktop-first shell for the overview, forecast runs, supplier documents, reconciliation exceptions, the human review queue, AI evaluation and the audit trail.

Cloud adapters (S3 storage, Textract sheet translation, Bedrock review,
SageMaker registry) implement the same contracts as the local stack and
stay disabled unless `AWS_ENABLED` and the matching feature flag are set.
`AWS_ENABLED=false` remains the local default.

**Portable replacements:** OpenAI API review and PaddleOCR document extraction
can run from the same backend locally or on AWS, independently of the AWS flags.
See [OpenAI + PaddleOCR setup](apps/api/PROVIDERS.md) for provider configuration,
optional OCR dependencies, Docker builds and AWS runtime requirements.

The `dev` AWS foundation (remote state, VPC, IAM, documents bucket, ECR
and Secrets Manager containers) can be applied from `infra/`. Local
developer commands never plan or apply. They never enable Bedrock,
Textract, SageMaker, ECS or RDS. Staging and prod stay placeholders.

## Prerequisites

| Tool           | Version    | Notes                                     |
| -------------- | ---------- | ----------------------------------------- |
| Python         | 3.12       | Backend runtime                           |
| uv             | ≥ 0.5      | Python dependency manager                 |
| Node.js        | ≥ 20.11    | Frontend runtime                          |
| Docker         | ≥ 24       | PostgreSQL and image builds               |
| GNU Make       | any        | Developer command entry point             |
| Terraform      | ≥ 1.6      | Offline `infra/` validation (`make check-infra`); 1.10+ for S3 state locking |

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
| `JOB_QUEUE_PROVIDER`       | `database` for local work, `sqs` for a hosted queue |
| `JOBS_QUEUE_URL`           | Queue the API announces work on when `sqs` is selected |
| `INSTANCE_COUNT`           | How many instances run; above 1 requires object storage |
| `AUTH_PROVIDER`            | `local` development tokens or `cognito` hosted sign-in |
| `AUTH_LOCAL_SECRET`        | Signing key shared by API and web for development tokens |
| `COGNITO_USER_POOL_ID`     | User pool backing hosted sign-in            |
| `COGNITO_CLIENT_ID`        | Application client id, validated as the token audience |
| `COGNITO_REGION`           | Region of the user pool (defaults to `AWS_REGION`) |
| `COGNITO_DOMAIN`           | Hosted sign-in domain used by the web application |
| `API_ORIGIN`               | Where the web application forwards API calls (server-side) |
| `APP_ORIGIN`               | Public origin of the web application, used for redirects |
| `DOCUMENT_STORAGE_ROOT`    | Local root for stored supplier files (optional; default `data/documents`) |
| `AWS_ENABLED`              | Master switch for cloud adapters (default `false`) |
| `AWS_REGION`               | Region used when a cloud adapter is enabled |
| `AWS_ACCOUNT_ID`           | Account id for ARN construction, and the account the live smoke checks it is pointing at (empty locally) |
| `AWS_ENVIRONMENT_NAME`     | Name segment for `{prefix}-{environment}-…` resources |
| `AWS_RESOURCE_PREFIX`      | Shared resource prefix (default `retailops`) |
| `AWS_DOCUMENTS_BUCKET`     | Object-store bucket when S3 storage is enabled |
| `AWS_DOCUMENTS_PREFIX`     | Object key prefix (default `supplier-documents`) |
| `AWS_BEDROCK_MODEL_ID`     | Bedrock foundation-model id when the hosted reviewer is enabled |
| `BEDROCK_INFERENCE_PROFILE_ID` | Preferred Converse model id (Haiku 4.5 US profile) |
| `BEDROCK_ENABLED`          | Alias of `AWS_USE_BEDROCK` |
| `BEDROCK_MAX_TOKENS`       | Max Bedrock output tokens (default `1024`) |
| `AWS_SAGEMAKER_MODEL_GROUP` | Model package group name |
| `AWS_USE_S3_STORAGE`       | Use S3 document storage (requires `AWS_ENABLED`) |
| `AWS_USE_TEXTRACT`         | Use Textract for PDF/image sheets (requires `AWS_ENABLED`) |
| `AWS_USE_BEDROCK`          | Use the Bedrock reviewer (requires `AWS_ENABLED`) |
| `AWS_USE_SAGEMAKER_REGISTRY` | Use the SageMaker registry (requires `AWS_ENABLED`) |

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
├── infra/            Terraform modules and environment compositions
├── data/             Local raw/processed/synthetic/document/review data (git-ignored)
├── scripts/          Developer scripts
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Local development

Recommended: PostgreSQL in Docker, API and web from the IDE.

```bash
make ready      # .env, PostgreSQL, migrations
make demo       # catalog, sales, forecast, sheets, matches, review cases
make dev        # API (:8000) and web (:3000)
make worker     # process queued uploads, reconciliations and forecasts
```

`make demo` is safe to re-run and does not require editing the database by
hand.

The optional full Compose stack (`make stack-up`) runs PostgreSQL, the API and
the web app in containers. Day-to-day work still uses `make ready` and
`make dev`.

Individual pipeline commands remain available:

```bash
make db-up      # start PostgreSQL and wait until healthy
make migrate    # apply Alembic migrations
make seed       # load development reference data (safe to re-run)
make synthetic  # generate, validate and ingest a year of synthetic sales
make forecast   # walk-forward the demand baselines and write the benchmark
make train      # train the demand model, evaluate it and register a local candidate
make documents file=apps/api/tests/fixtures/supplier_documents/valid.csv supplier=SUP-BEVCO
make reconcile supplier=SUP-BEVCO invoice=INV-1001
make review-eval # score the mock reviewer; writes data/reviews/
make reviews     # list the human review queue
make review-feedback # export decided reviews for evaluation
make dev        # run API (:8000) and web (:3000) together
```

Individually:

```bash
make api        # http://localhost:8000  (docs at /docs)
make web        # http://localhost:3000
```

The web app is the operations console. It reads live API data: no hardcoded
KPIs. Opening it redirects to `/signin`; with the default local identity
provider, enter any name and choose a role. Then open `http://localhost:3000`
for the overview, then use the sidebar to
reach forecasts, documents, reconciliations, reviews, AI evaluation, audit
and settings.

## Continuous integration

Every push and pull request runs the same gate as `make check-app` and
`make check-infra`, with PostgreSQL available so the integration tests run
rather than skip. Dependencies and images are scanned on every pull request
and weekly.

Workflows hold no credentials. Deployment authenticates through OpenID
Connect and runs only from `main` in this repository; the role's trust
policy matches the exact token subject, so a pull request — including one
from a fork — cannot reach it.

Deployment stays disabled until the deploy role is configured.

## Tests

```bash
make test       # backend (pytest) + frontend (Vitest)
make test-api
make test-web
make check-app  # format, lint, types, tests, frontend build, reviewer eval
make check      # check-app + live migrations + image builds + terraform validate
make check-infra # terraform fmt + validate (no apply)
make perf       # wide wall-clock samples for generate / ingest / train / match
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
make reconcile supplier=… invoice=…  # three-way match an invoice (or po=…)
make review-eval                 # score the mock reviewer; writes data/reviews/
make reviews                     # list the human review queue
make review-feedback             # export decided reviews for evaluation
make db-reset                    # rebuild the schema from scratch and re-seed
```

Data lives in the named volume `retailops_postgres_data` and survives restarts.

## Retail domain model

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
| PurchaseOrder | `purchase_orders` | An order placed with one supplier for one store |
| PurchaseOrderLine | `purchase_order_lines` | Ordered quantity, unit cost, tax and line total |
| GoodsReceipt | `goods_receipts` | A delivery, optionally against a purchase order |
| GoodsReceiptLine | `goods_receipt_lines` | Received quantity of one product |
| SupplierInvoice | `supplier_invoices` | A supplier bill, unique per supplier and number |
| SupplierInvoiceLine | `supplier_invoice_lines` | Invoiced quantity, unit cost, tax and line total |
| ReconciliationRun | `reconciliation_runs` | One deterministic three-way match (versioned by scope) |
| ReconciliationException | `reconciliation_exceptions` | What does not match, with signed financial impact |
| ReviewCase | `review_cases` | A human-oversight item on a finding or exception |
| ReviewAISnapshot | `review_ai_snapshots` | Immutable copy of the reviewer output that opened the case |
| ReviewDecisionRecord | `review_decisions` | The human approve / reject / correct close |
| ReviewAuditEvent | `review_audit_events` | Append-only history of status and assignment changes |

`make seed` loads a deterministic development catalog. It is idempotent, so
running it repeatedly neither duplicates nor disturbs existing rows.

`make synthetic` is the one command that regenerates the development dataset:
it writes CSV files under `data/synthetic/`, validates them, and upserts the
catalog and daily sales into the configured database. Re-running it is safe.
The same seed and configuration always produce the same checksum.

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
`data/forecasts/benchmark.md` and the weekly frame CSV.

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
`SageMakerModelRegistry` implements the same calls with an injected client
and does not upload artifacts.

## Supplier document intake

`make documents` stores the file under `data/documents/` (generated keys, no
path traversal), writes a `supplier_documents` row, parses CSV / XLSX / a
text-based PDF onto a canonical offer sheet, and runs deterministic rules:
required fields, EAN shape, cost and quantity bounds, configured VAT rates,
in-file duplicates, then catalog cross-checks (supplier SKU mapped elsewhere,
EAN already on a product, cost increase vs current term, category mismatch).
Findings are persisted; the document ends `review_ready` or `parse_failed`.
Storage is a contract — the local directory is one implementation;
`S3DocumentStorage` is the object-store adapter.

## Procurement and reconciliation

Purchase orders, goods receipts and supplier invoices are first-class rows.
`make reconcile` loads an invoice (or a purchase order), the other documents
that belong to that order, matches lines without guessing, compares ordered /
received / invoiced quantities and PO vs invoice cost, and persists a
versioned run plus exceptions. Tolerances default to zero. Re-running the
same documents and tolerances returns the existing run.

## AI review

Reviewers implement one method: `review(request) → ReviewResult`. Inputs are
domain DTOs (supplier findings, reconciliation exceptions). Outputs are
validated: review type, summary, findings, suggested value, reasoning,
confidence, risk, recommended action, provider metadata and prompt version.
Malformed output is rejected and must not be used.

The local implementation is `MockAIReviewer`, a fixture double for normal,
low-confidence, malformed and provider-failure behaviour. It does not
emulate a model. `BedrockAIReviewer` implements the same contract behind
an injected client and is scored the same way.

AI may classify uncertain category text, summarize findings, explain a
reconciliation exception, suggest a next action and assign confidence. It
may not do financial arithmetic, mutate source records, bypass validation
or auto-resolve high-risk cases. Amounts stay on the reconciliation run.
Deterministic findings stay the factual source of truth.

Routing defaults to human review. Auto-eligibility needs a valid result,
confidence ≥ 0.85, low risk, a zero financial impact and an `accept` or
`no_action` recommendation.

`make review-eval` runs the mock against the versioned JSONL cases and
writes `data/reviews/evaluation.json` and `evaluation.md`. Metrics:
schema validity, classification accuracy, recommended-action accuracy,
confidence presence and provider failure rate.

## Human review

Cases persist against a document finding or a reconciliation exception.
Each case carries priority, risk, confidence, financial impact, the
assigned reviewer and timestamps. When a reviewer result is attached, a
snapshot stores provider, model, prompt version, the original output,
confidence, the recommended action and an input hash. That snapshot is
not edited.

Status moves only through documented transitions: `open` → `in_review` →
`approved` / `rejected` / `corrected`, or `cancelled` from `open` or
`in_review`. Starting a case that someone else already holds is rejected.
Approve stores an optional comment and a reference to the accepted
snapshot. Reject requires a reason. Correct stores structured human
values next to the original AI recommendation. Every change appends an
audit event; history is not overwritten.

`GET /reviews` lists the queue (status, priority, subject type, supplier,
risk, date, stable order, pagination). `GET /reviews/metrics` returns
open-case count, acceptance / rejection / correction rates, and average
review duration when both timestamps exist. `GET /reviews/feedback`
and `make review-feedback` export decided rows for evaluation (input
reference, AI result, confidence, decision, correction, prompt and
model versions). Local reviewer identity is an explicit string; sign-in
is not implemented.

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
| GET    | `/ops/overview` | Forecast, document, reconciliation and review counts |
| GET    | `/forecasts` | Forecast runs (pagination) |
| GET    | `/forecasts/{id}` | Run detail, predictions and WAPE/bias |
| GET    | `/documents` | Supplier documents (filters + pagination) |
| GET    | `/documents/{id}` | Findings, related reviews and extracted rows |
| GET    | `/reconciliations` | Three-way match runs |
| GET    | `/reconciliations/{id}` | Exceptions with PO / receipt / invoice context |
| GET    | `/exceptions` | Flattened reconciliation exceptions |
| GET    | `/reviews`   | Human review queue (filters + pagination) |
| GET    | `/reviews/metrics` | Open cases, decision rates, average duration |
| GET    | `/reviews/feedback` | Decided cases as evaluation rows |
| GET    | `/audit`     | Recent review audit events |
| GET    | `/search`    | Cross-entity lookup for the operations shell |
| GET    | `/docs`      | OpenAPI documentation           |

## Security baseline

Secrets are never committed. `.gitignore` excludes `.env` files, credentials,
private keys, Terraform state and local data directories. Application
configuration is read exclusively from environment variables.
