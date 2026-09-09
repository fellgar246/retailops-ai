# ADR-011 — AWS Foundation and Remote Terraform State

- **Status:** Accepted
- **Date:** 2026-09-01
- **Scope:** Live `dev` AWS foundation, remote Terraform state, naming and cost guardrails
- **Supersedes in part:** the “Terraform is validated, not applied” clause of [ADR-010](ADR-010-aws-adapters-and-terraform.md)

## Context

AWS infrastructure was expressed as Terraform modules with every adapter
held behind `AWS_ENABLED=false`, and no live resources had been created.
Attaching S3, Textract and Bedrock needs a real account, a remote state
backend and a disposable `dev` foundation, so that names and IAM are not
invented in the console when the adapters are switched on.

The full `platform` composition still includes ECS, RDS, Step Functions
and a SageMaker model package group. Those remain out of scope.

## Decision

### Only `dev` is live

`infra/environments/dev` applies `modules/foundation`. `staging` and
`prod` keep the full `platform` graph as placeholders and are not
applied.

### Remote state is bootstrapped separately

`infra/bootstrap` creates an encrypted, versioned, publicly blocked S3
bucket used only for Terraform state. Locking uses the Terraform 1.10+
S3 lock file (`use_lockfile = true`), not DynamoDB. Bootstrap state is
migrated into the same bucket at `retailops-ai/bootstrap/terraform.tfstate`.
Platform state lives at `retailops-ai/dev/terraform.tfstate`. The
documents bucket is never used for state.

The state bucket has `prevent_destroy`. Destroying `dev` must not delete
it.

### Foundation resources only

The applied graph is:

- VPC, two public and two private subnets, internet gateway, route tables
- Security-group placeholders with no public ingress
- Documents S3 bucket
- ECR repositories `retailops-ai-dev-api` and `retailops-ai-dev-web`
- Secrets Manager containers for database and application secrets
- IAM roles for ECS execution, API task, document processing and ML
- A monthly AWS Budget

NAT Gateway is off. Public ALB ingress is off. No ECS service, RDS
instance, Step Functions state machine, SageMaker package group, or
Bedrock/Textract workload is created.

### Naming and tags

```text
Project      = retailops-ai
Environment  = dev | bootstrap
ManagedBy    = terraform
Repository   = retailops-ai
```

Resource names use `{project}-{environment}-…`. The provider is pinned
to the selected account with `allowed_account_ids`.

### Secrets stay empty in Git

Terraform creates secret containers and exports ARNs only. Values are
set out of band before ECS or RDS exist.

### Local operation does not change

`AWS_ENABLED=false` remains the default. Applying the foundation does
not cut the application over to AWS.

## Consequences

**Positive**

- `dev` can be planned, applied, inspected, destroyed and recreated.
- Later work receives stable names, role ARNs and a documents bucket.
- State is remote, encrypted and isolated from application objects.

**Negative**

- Private subnets have no NAT, so Fargate tasks cannot pull images or
  call AWS APIs until NAT or VPC endpoints are added.
- Secret containers have no versions until an operator writes values.
- A $50 account-wide budget is a signal, not a hard spend cap.

**Deferred**

- Live S3 / Textract / Bedrock adapter cutover
- ECS, RDS, TLS, CI/CD, staging and prod
