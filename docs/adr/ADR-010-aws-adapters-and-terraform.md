# ADR-010 — AWS Adapters and Terraform Pre-Deployment

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Typed AWS config, cloud adapters behind existing contracts, Terraform modules, IAM intent

## Context

Storage, review and the model registry already sit behind protocols with
local implementations. Hosted object storage, document analysis, a
Bedrock reviewer, a SageMaker registry and AWS infrastructure can now be
expressed in code without creating or calling live resources.

Local development must keep working with AWS disabled. Tests must not
require account credentials.

## Decision

### Configuration is a typed boundary

`AwsConfig` holds region, account id, environment name, resource prefix,
document-bucket references, Bedrock model id, SageMaker group name and
feature flags. `AWS_ENABLED` defaults to false. A feature flag cannot
turn an adapter on by itself.

### Adapters implement existing contracts

| Contract | Cloud implementation | Test double |
|---|---|---|
| `DocumentStorage` | `S3DocumentStorage` | In-memory S3 stub |
| Sheet `ParseResult` | `TextractDocumentAnalyzer` | Captured Textract JSON |
| `AIReviewer` | `BedrockAIReviewer` | Injected Bedrock stub |
| `ModelRegistry` | `SageMakerModelRegistry` | Injected SageMaker stub |

Clients are injected. The SageMaker adapter records metadata and a
declared artifact URI; it does not upload files. Champion selection is
an explicit metadata value, not “latest approved”.

### Local review stays authoritative

`LocalCallbackWorkflow` maps start / decision / cancel / timeout onto
callback-token events (correlation id, idempotency key, task token).
Persisted transitions in `workflow.py` do not change.

### Terraform is validated, not applied

Modules cover networking, S3, ECR, ECS/Fargate, RDS PostgreSQL,
SQS/EventBridge, Step Functions, IAM, CloudWatch and the SageMaker
package group. Account id and AZs are variables so offline
`terraform validate` does not query AWS. Example tfvars contain no live
secrets.

The `dev` **foundation** (not the full platform) is applied against a
real account with remote state. Staging and prod remain unapplied
placeholders. See
[ADR-011](ADR-011-aws-foundation-and-remote-state.md).

### Least privilege is intent, not a proof

IAM statements name the bucket, queues, model, package group and
callback APIs. Assumptions that need a live account are listed in
[iam-security.md](../architecture/iam-security.md).

## Consequences

**Positive**

- Local `make demo` / `make dev` / `make test` stay on filesystem
  storage and the mock reviewer.
- A hosted adapter can replace a local one without changing callers.
- Infrastructure can be formatted and validated without an account.

**Negative**

- Declared SageMaker artifact URIs are not uploaded; a later job must
  place `model.tar.gz` before a live `CreateModelPackage` will succeed.
- Task-definition secrets (database URL) still need a Secrets Manager
  move before production traffic.

**Deferred**

- Wiring live SageMaker training / registry calls.
- VPC endpoints, TLS on the load balancer, and an SNS destination for
  alarms.

Live S3, Textract and Bedrock sit behind the existing adapter
contracts. Local `AWS_ENABLED=false` remains the default. See
[aws-ai-services.md](../runbooks/aws-ai-services.md).

Remote Terraform state and the first `dev` apply are recorded in
[ADR-011](ADR-011-aws-foundation-and-remote-state.md).
