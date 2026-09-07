# OpenAI + PaddleOCR, locally and on AWS

RetailOps supports `AI_REVIEW_PROVIDER=openai` and
`DOCUMENT_OCR_PROVIDER=paddleocr` independently of `AWS_ENABLED`.
Both implement the existing reviewer and sheet-analyzer contracts. CSV/XLSX
parsing, business rules, reconciliation and human decisions remain unchanged.

## Configuration

Set these values in the root `.env` for local development, or inject them into
the backend container environment on AWS:

```dotenv
AI_REVIEW_PROVIDER=openai
DOCUMENT_OCR_PROVIDER=paddleocr
OPENAI_API_KEY=your-project-api-key
OPENAI_MODEL=your-structured-output-model-id
OPENAI_MAX_OUTPUT_TOKENS=2048
OPENAI_TIMEOUT_SECONDS=60
PADDLEOCR_DEVICE=cpu
PADDLEOCR_MAX_PAGES=10
AWS_USE_BEDROCK=false
BEDROCK_ENABLED=false
AWS_USE_TEXTRACT=false
```

Choose an available OpenAI model supporting Responses and Structured Outputs.
`OPENAI_MODEL` intentionally has no default: configuring a key alone must not
select a billable model. Keys belong only in backend runtime configuration,
never frontend variables, image layers, Terraform values or version control.
The OpenAI API is billed separately from AWS credits.

Explicit provider names override legacy flags. `mock` and `local` are the
offline configuration in `.env.example`; `auto` preserves legacy flag routing
for existing installations. No provider silently falls back to a mock on error.

## Native local development

```sh
cd apps/api
uv sync --frozen --extra paddleocr
uv run --extra paddleocr uvicorn retailops_api.main:app --reload --port 8000
```

The OCR extra is optional so normal development does not need its model runtime.
Keep `--extra paddleocr` on `uv run` commands that need OCR; otherwise uv may
remove optional packages while synchronizing. For example:

```sh
uv run --extra paddleocr retailops-documents --file /absolute/path/sheet.pdf --supplier SUP-BEVCO
```

PaddleOCR downloads model weights on first inference and reuses the PaddleX
cache. Allow network access for initialization and enough disk/RAM for these
models. Native support depends on PaddlePaddle wheels for your OS/architecture;
use the Linux container when native dependencies are unavailable.

## Docker locally

After setting the root `.env`:

```sh
ENABLE_PADDLEOCR=true docker compose --profile full up --build -d
```

Compose uses Linux x86_64 by default, including emulation on Apple Silicon,
because the locked PaddlePaddle release has no Linux ARM wheel. It passes the
key at runtime and mounts a persistent PaddleX cache.
The API uses one process by default; OCR inference is serialized per process
because the model pipeline is shared. PDFs are bounded before inference;
multi-frame TIFFs are processed frame by frame.

## AWS container deployment

Build the same backend image with both optional capabilities:

```sh
docker build --platform linux/amd64 \
  --build-arg ENABLE_PADDLEOCR=true --build-arg ENABLE_AWS=true \
  -t retailops-api:openai-paddleocr apps/api
```

Run it on a matching x86 Linux EC2 host or ECS task. Inject the configuration
above, the deployed `DATABASE_URL`, and your frontend origin. Inject
`OPENAI_API_KEY` from Secrets Manager through the deployment configuration.
The process needs outbound HTTPS to OpenAI and, initially, the model download
hosts. Keep `/home/appuser/.paddlex` writable and persistent, or prewarm the
models as part of your image release process. Size CPU, memory and request
timeouts using a representative document; a small free-tier instance is not
assumed sufficient for PP-StructureV3.

For S3 storage also set:

```dotenv
AWS_ENABLED=true
AWS_USE_S3_STORAGE=true
AWS_REGION=us-east-1
AWS_DOCUMENTS_BUCKET=your-existing-bucket
```

Use the instance/task role for S3 credentials. With local storage, leave
`AWS_ENABLED=false` and mount a persistent `DOCUMENT_STORAGE_ROOT`. Deployment
location does not determine the AI or OCR provider.

The current Terraform only provisions the existing AWS foundation; this change
does not provision an ECS service, database, secret value or deploy an image.

## Behavior and verification

OpenAI receives the existing review DTO with strict JSON Schema output;
application-owned provenance is stamped locally. Responses use `store=false`,
a timeout, and two SDK retries for retryable errors. Refusals, incomplete output
and schema failures enter the existing review error path. Token usage is recorded.

PaddleOCR uses PP-StructureV3's `table_res_list[].pred_html` output. All tables
and pages are considered, preserving page provenance. Each table currently
needs a recognizable supplier header. Merged cells, missing tables and
unreadable tables produce explicit issues; no missing numbers are inferred.
OCR scores are not represented as field-level confidence because they do not
establish that the reconstructed row is correct. Validate accuracy on actual
supplier sheets, especially Spanish text, merged headers and table continuations.

Run contract tests without API calls or model downloads:

```sh
cd apps/api
uv run pytest tests/test_portable_providers.py
```

These tests cover provider precedence in both environments, output schema,
refusals, limits, temporary-file cleanup and multi-page table conversion.
They do not establish OCR accuracy, model review quality or AWS deployment health.

Once the key and model are configured, run a billed evaluation against the
existing fixture corpus explicitly:

```sh
uv run retailops-review-eval --provider openai --compare
```

Sources:

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [PaddleOCR PP-StructureV3](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PP-StructureV3.html)
