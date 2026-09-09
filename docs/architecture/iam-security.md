# IAM and security intent

- **Scope:** Least-privilege roles for the API, document processing, model registry and review callbacks
- **Decisions:** [ADR-010](../adr/ADR-010-aws-adapters-and-terraform.md), [ADR-011](../adr/ADR-011-aws-foundation-and-remote-state.md)

Two IAM graphs exist. **`iam_foundation`** is applied in `dev` today.
**`modules/iam`** is the later full-stack intent used by the unapplied
`platform` module.

## Applied foundation roles (`iam_foundation`)

| Role | Trust | Intent |
|---|---|---|
| ECS execution | `ecs-tasks.amazonaws.com` | Pull images from the two ECR repos; write future `/ecs/{prefix}-*` log streams; `GetSecretValue` on the database and application secret ARNs |
| API task | `ecs-tasks.amazonaws.com` | Documents bucket objects and list; `GetSecretValue` on the two secret ARNs; `bedrock:InvokeModel` on Claude Haiku 4.5 and the US inference profile. No Textract, SQS or Step Functions |
| Document processor | `ecs-tasks.amazonaws.com` | Read/write `supplier-documents/*`, `block13/*` and `documents/*`; Textract analyze/detect. No secrets, no queues, no Bedrock |
| ML | `sagemaker.amazonaws.com` | Read/write `models/*` in the documents bucket. No training or package-group APIs yet |

A Step Functions callback role is not created until a state machine
exists.

## Later full-stack roles (`modules/iam`, not applied)

| Role | Trust | Intent |
|---|---|---|
| ECS execution | `ecs-tasks.amazonaws.com` | Pull images from the environment ECR repos; write API and web log streams |
| API task | `ecs-tasks.amazonaws.com` | Documents bucket objects; document and review SQS queues; Bedrock `InvokeModel` on the configured foundation model; Textract analyze/detect; SageMaker package register/list/describe/update on the model group; Step Functions task callbacks on the review state machine; API log streams |
| Document processor | `ecs-tasks.amazonaws.com` | Read/write document objects; receive from the documents queue; Textract only. No Bedrock, no registry, no workflow callbacks |
| Step Functions | `states.amazonaws.com` | `sqs:SendMessage` to the review callback queue |

## Storage and data

- The documents bucket blocks public access, enforces bucket-owner ownership, uses SSE-S3, denies non-TLS access and versions objects.
- Secrets Manager containers for `retailops-ai/{env}/database` and `…/application` exist without values. Terraform never writes `SecretString` or exports secret values.
- RDS is not applied. When it is, it stays in private subnets, encrypted at rest, not publicly accessible. The password must come from Secrets Manager, never from a committed tfvars file.
- SQS queues use SQS-managed encryption and a dead-letter queue.

## Assumptions that need live verification

These cannot be confirmed without an account and a plan against that account:

- Bedrock model access is granted on the chosen foundation-model id in the chosen region.
- Textract `AnalyzeDocument` with `TABLES` is available in that region.
- SageMaker `CreateModelPackage` accepts the declared `ModelDataUrl` only after artifacts are placed; the adapter does not upload them.
- `textract:*` on `Resource="*"` is required by the service (no per-document ARN). Confirm with IAM Access Analyzer after the first apply.
- `ecr:GetAuthorizationToken` must stay on `Resource="*"`.
- The review state-machine ARN interpolated from `name_prefix` matches the resource Terraform creates.
- Task-definition `DATABASE_URL` will be visible to anyone who can describe the task. Move it to Secrets Manager before production traffic.
- Security-group egress is currently open (`0.0.0.0/0`) so Fargate can pull images and call AWS APIs. Tighten after VPC endpoints are added.

## Logging

API, web and workflow log groups are created with environment-specific
retention (14 / 30 / 90 days). CPU alarms fire on the Fargate services.
No SNS topic is attached yet; alarm actions need an operations destination.
