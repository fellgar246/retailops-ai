# AWS adapters

- **Scope:** Typed AWS configuration, S3 storage, Textract sheet translation, Bedrock reviewer, SageMaker registry
- **Decisions:** [ADR-010](../adr/ADR-010-aws-adapters-and-terraform.md)

Cloud adapters implement the same contracts the local stack already uses.
They stay off unless `AWS_ENABLED` is true *and* the matching feature flag
is set. Automated tests inject stubs; they never use account credentials.

```bash
# Local defaults — filesystem storage, mock reviewer, directory registry
make documents file=apps/api/tests/fixtures/supplier_documents/valid.csv supplier=SUP-BEVCO
make train
make review-eval
```

## Configuration

`Settings.aws_config()` builds an `AwsConfig` from environment variables.

| Variable | Default | Role |
|---|---|---|
| `AWS_ENABLED` | `false` | Master switch |
| `AWS_REGION` | `us-east-1` | Client region |
| `AWS_ACCOUNT_ID` | empty | ARN construction only |
| `AWS_ENVIRONMENT_NAME` | `local` | `{prefix}-{environment}-{suffix}` names |
| `AWS_RESOURCE_PREFIX` | `retailops` | Shared name prefix |
| `AWS_DOCUMENTS_BUCKET` | empty | Object-store bucket |
| `AWS_DOCUMENTS_PREFIX` | `supplier-documents` | Object key prefix |
| `AWS_BEDROCK_MODEL_ID` / `BEDROCK_MODEL_ID` | empty | Foundation-model id |
| `BEDROCK_INFERENCE_PROFILE_ID` | empty | Preferred Converse model id |
| `BEDROCK_MAX_TOKENS` | `1024` | Output bound |
| `BEDROCK_TEMPERATURE` | `0` | Sampling bound |
| `BEDROCK_TIMEOUT_SECONDS` | `30` | Client read timeout |
| `AWS_SAGEMAKER_MODEL_GROUP` | `category-forecast` | Model package group |
| `AWS_SAGEMAKER_ARTIFACT_PREFIX` | `models` | Declared artifact URI prefix |
| `AWS_USE_S3_STORAGE` | `false` | Use `S3DocumentStorage` |
| `AWS_USE_TEXTRACT` | `false` | Use `TextractDocumentAnalyzer` for PDF/image |
| `AWS_USE_BEDROCK` / `BEDROCK_ENABLED` | `false` | Use `BedrockAIReviewer` |
| `AWS_USE_SAGEMAKER_REGISTRY` | `false` | Use `SageMakerModelRegistry` |

A feature flag is ignored while `AWS_ENABLED` is false. Missing bucket or
model id values raise `AwsConfigError` only when the matching adapter is
actually selected.

## S3 document storage

`S3DocumentStorage` implements `DocumentStorage`: save, read, open, exists,
metadata, delete. Logical keys remain 32-hex identifiers stored in the
database. The object key is `{prefix}/{key}/source/payload`. Filename,
media type and SHA-256 live in object metadata. Live smoke uses prefix
`block13`. See [aws-ai-services.md](../runbooks/aws-ai-services.md).

The client is injected. Tests use an in-memory stub.

## Textract sheet translation

`TextractDocumentAnalyzer.analyze_response` maps AnalyzeDocument /
DetectDocumentText JSON onto `ParseResult`. TABLE cells become a grid;
FORMS are a fallback; LINE blocks fall back to the delimited-text
parser. Confidence and page references are retained when present.
`analyze` and `analyze_s3` call an injected client. CSV/XLSX stay on
the application parser. PDF/image use Textract only when
`document_analyzer_for` returns an analyzer. A versioned synthetic
corpus lives in `textract_corpus.py`.

## Bedrock reviewer

`BedrockAIReviewer` implements `AIReviewer.review`. It uses Bedrock
`Converse` with a JSON Schema tool, classifies provider errors
(throttled, timeout, validation, access denied, unavailable), retries
only the transient classes with bounded backoff/jitter, and validates
output with `parse_review_result`. Provider, model, prompt and schema
versions are stamped from the adapter. Usage metadata is kept on
`last_usage`, not on `ReviewResult`.

## SageMaker model registry

`SageMakerModelRegistry` implements `ModelRegistry`. Register writes
package metadata (metrics, fingerprint, approval). It does **not** upload
artifact files; it only records the `s3://` URI the package would point
at. Champion selection is explicit: customer metadata
`retailops_approval=champion`. Promoting a version demotes the previous
champion to `approved`. Latest-approved is not implied.

## Factory

`document_storage_for`, `document_analyzer_for`, `ai_reviewer_for` and
`model_registry_for` in `retailops_api.core.adapters` pick the local
implementation when AWS is disabled. Documents intake, demo review
bootstrap and `retailops-review-eval --provider mock` use those
factories, so local commands stay on the filesystem and mock reviewer.

Live clients are constructed only when a flag is on and no stub is
injected. That path needs the optional `aws` dependency group (`boto3`).

## Where the code lives

| Concern | Path |
|---|---|
| Typed config | `apps/api/src/retailops_api/core/aws.py` |
| Settings fields | `apps/api/src/retailops_api/core/config.py` |
| Factories | `apps/api/src/retailops_api/core/adapters.py` |
| S3 storage | `apps/api/src/retailops_api/documents/s3.py` |
| Textract translation | `apps/api/src/retailops_api/documents/textract.py` |
| Bedrock reviewer | `apps/api/src/retailops_api/review/bedrock.py` |
| SageMaker registry | `apps/api/src/retailops_api/forecasting/sagemaker_registry.py` |
| Review callback mapping | `apps/api/src/retailops_api/review/cloud_workflow.py` |
