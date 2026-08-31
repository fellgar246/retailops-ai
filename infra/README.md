# RetailOps AI — Terraform

Typed AWS adapters live in the API package. This directory describes the
infrastructure those adapters would run on. Nothing here is applied by
local development commands. `make check-infra` only formats and
validates the configuration.

## Layout

```text
infra/
├── modules/
│   ├── networking/       VPC, subnets, NAT, security groups
│   ├── s3/               Supplier-document bucket
│   ├── ecr/              API and web image repositories
│   ├── ecs/              Fargate services and the public load balancer
│   ├── rds/              PostgreSQL
│   ├── messaging/        SQS queues and the operations EventBridge bus
│   ├── step_functions/   Human-review wait-for-callback state machine
│   ├── iam/              Task, execution, document-processing and workflow roles
│   ├── cloudwatch/       Log groups and CPU alarms
│   ├── sagemaker/        Model package group
│   └── platform/         Composes the modules above
└── environments/
    ├── dev/              Full composition, smaller instances
    ├── staging/          Same graph, placeholder values
    └── prod/             Same graph, multi-AZ and longer retention
```

Naming is `{project}-{environment}-…`. Tags always include `Project`,
`Environment` and `ManagedBy=terraform`. Account id, region and
availability zones are variables so `terraform validate` does not need
live AWS data sources.

## Environments

Each environment has `terraform.tfvars.example`. Copy it to
`terraform.tfvars` (git-ignored) or export `TF_VAR_*`. Never commit a
real password, access key or session token.

| Concern | Where it lives |
|---|---|
| Common names and tags | `modules/platform` locals |
| Environment sizing | `environments/<name>/main.tf` |
| Secret references | `TF_VAR_master_password`, Secrets Manager after first apply |

## Offline checks

```bash
make check-infra
```

That runs `terraform fmt -check -recursive` and `terraform validate`
in each environment after `terraform init -backend=false`. It does not
run plan or apply.

## Related notes

- [Cloud readiness](../docs/runbooks/cloud-readiness.md)
- [IAM and security](../docs/architecture/iam-security.md)
- [AWS adapters](../docs/architecture/aws-adapters.md)
