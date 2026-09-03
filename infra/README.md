# RetailOps AI — Terraform

Typed AWS adapters live in the API package. This directory describes the
infrastructure those adapters would run on. Local development commands
never plan or apply. `make check-infra` only formats and validates.

Only the `dev` foundation is applied. It creates remote state, a VPC,
IAM roles, the documents bucket, ECR repositories, Secrets Manager
containers and a monthly budget. It does **not** create ECS services,
RDS, Step Functions, SageMaker model groups, or public application
traffic.

`staging` and `prod` remain full-stack placeholders and must not be
applied.

## Layout

```text
infra/
├── bootstrap/            Remote-state bucket (apply once, do not destroy)
├── modules/
│   ├── networking/       VPC, subnets, optional NAT, security groups
│   ├── s3/               Supplier-document bucket
│   ├── ecr/              API and web image repositories
│   ├── secrets/          Secrets Manager containers (no values)
│   ├── iam_foundation/   Execution, task, document and ML roles
│   ├── budget/           Monthly AWS Budget
│   ├── foundation/       Live `dev` composition (network, IAM, S3, ECR, secrets)
│   ├── ecs/              Fargate services (not applied)
│   ├── rds/              PostgreSQL (not applied)
│   ├── messaging/        SQS and EventBridge (not applied)
│   ├── step_functions/   Review wait-for-callback (not applied)
│   ├── iam/              Full-stack roles for later ECS/RDS apply
│   ├── cloudwatch/       Log groups (not applied)
│   ├── sagemaker/        Model package group (not applied)
│   └── platform/         Full composition used by staging/prod placeholders
└── environments/
    ├── dev/              Applied foundation only
    ├── staging/          Placeholder — do not apply
    └── prod/             Placeholder — do not apply
```

Naming is `{project}-{environment}-…`. Applied `dev` uses
`project = retailops-ai`. Tags always include `Project`, `Environment`,
`ManagedBy=terraform` and `Repository=retailops-ai`. Account id, region
and availability zones are variables so `terraform validate` does not
need live AWS data sources.

## Environments

Each environment has `terraform.tfvars.example`. Copy it to
`terraform.tfvars` (git-ignored) or export `TF_VAR_*`. Never commit a
real password, access key, session token or populated secret value.

`dev` and `bootstrap` also have `backend.hcl.example`. Copy to
`backend.hcl` (git-ignored) after the state bucket exists.

| Concern | Where it lives |
|---|---|
| Common names and tags | `modules/foundation` and `modules/platform` locals |
| Applied `dev` foundation | `environments/dev/main.tf` |
| Remote state | `bootstrap/`, then `environments/dev/backend.hcl` |
| Secret values | Out of band in Secrets Manager; never in tfvars |

## Apply `dev` (foundation only)

Review every plan before apply. Do not apply staging or prod.

```bash
# 1. Bootstrap remote state (first time only)
cd infra/bootstrap
cp terraform.tfvars.example terraform.tfvars   # set account id and bucket name
# Comment out `backend "s3" {}` in versions.tf until the bucket exists.
terraform init
terraform plan
terraform apply
cp backend.hcl.example backend.hcl             # set the real bucket name
# Restore `backend "s3" {}`, then migrate local state into the bucket.
terraform init -migrate-state -backend-config=backend.hcl

# 2. Apply the disposable foundation
cd ../environments/dev
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan
terraform apply
terraform plan    # expected: No changes
```

Destroy only the `dev` foundation, never the bootstrap bucket:

```bash
cd infra/environments/dev
terraform plan -destroy
terraform destroy
```

## Offline checks

```bash
make check-infra
```

That runs `terraform fmt -check -recursive` and `terraform validate`
in bootstrap and each environment after `terraform init -backend=false`.
It does not run plan or apply.
