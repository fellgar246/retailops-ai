# Project closure

RetailOps AI is closed as a portfolio project. This records what was
built, what it proved, what it never reached, and how to bring the cloud
side back if that changes.

## What this was

A retail operations platform built to demonstrate engineering across a
realistic AI-assisted workflow rather than to run a business: category
demand forecasting, supplier document intake with deterministic
validation, three-way procurement reconciliation, and human review of
everything the models produced.

The principle throughout was **deterministic before AI**. Rules decide
what rules can decide; a model is asked only where judgement is genuinely
required; and no model output is treated as correct on its own.

## What was built

| Capability | State |
|---|---|
| Retail domain, migrations, synthetic history | Complete |
| Forecast evaluation and walk-forward backtesting | Complete |
| ML forecasting with champion/challenger promotion | Complete |
| Supplier document intake and validation | Complete |
| Procurement three-way reconciliation | Complete |
| AI review contracts, mock provider, evaluation harness | Complete |
| Human review, audit trail, feedback export | Complete |
| Operations console | Complete |
| Cloud adapters: S3, Textract, Bedrock, SageMaker registry | Complete |
| AWS foundation as Terraform | Applied and validated live |
| Authentication, roles, verified audit identity | Complete, validated live |
| Operator intake and asynchronous processing | Complete, validated live |
| Delivery pipeline | Built, never switched on |
| Deployed application | **Never reached** |

Roughly 990 automated checks cover it: 941 backend, 46 frontend, plus
static analysis and strict typing on both.

## What it proved

Four things were exercised against real AWS rather than described:

- **Document intake end to end** — an upload stored in S3, analysed by
  Textract, reviewed by Bedrock, routed by the existing policy.
- **Identity** — sign-in through a Cognito user pool, with the token's
  subject recorded on the decision and matching the pool exactly.
- **Asynchronous work** — a job announced on SQS, leased by a worker,
  and the message settled only after the outcome was recorded.
- **Cost discipline** — every environment sized against a stated budget
  before anything was applied.

## What it did not reach

No deployed application. The pipeline that would deploy one exists and is
wired, but was never enabled, because the environment it would deploy to
costs more per month than the project's entire budget.

That was the closing decision, and it is the honest one: the remaining
work was not engineering, it was a standing bill.

## What it cost

```text
August 2026      $0.00
September 2026   $0.00
```

The foundation that was applied — network without NAT, buckets, a
registry, a user pool, queues, roles — falls inside always-free
allowances. The expense was always in what came next: a load balancer, a
managed database and always-on compute, none of which were ever created.

## Why it stopped here

A staging environment sized as production would have cost around $300 a
month. Sized down as far as the architecture allows — no load balancer, no
NAT gateway, spare capacity, the smallest database — it still came to
about $24, against a $5 budget.

Two lines dominate and neither is the application: a load balancer and a
database, both charged for existing rather than for being used.

For a portfolio, paying that indefinitely buys very little. The
deployment was designed, costed and left un-applied, which is a more
useful thing to show than a running demo nobody visits.

## What remains

The repository. Everything is expressed as code: the application, its
tests, the infrastructure, the decisions behind both. Recreating the
cloud side is an apply, not a rewrite.

Fifteen architecture decision records explain why each significant choice
was made, including the ones that were later reversed.

## Bringing it back

```bash
cd infra/environments/dev
terraform init -backend-config=backend.hcl
terraform apply
```

Then follow the authentication runbook to create the user pool accounts,
and the deployment runbook to enable the pipeline.

The state bucket is kept deliberately. It holds the history of every
apply and costs a fraction of a cent, which is a poor reason to destroy
the ability to return.

## Known gaps, recorded rather than hidden

- A job whose queue message is lost sits queued and nothing notices. A
  sweeper re-announcing long-queued jobs was identified and not built.
- Staging places tasks in public subnets, because removing the NAT
  gateway leaves no other route to the registry. Production would not.
- The delivery pipeline has never run a real deployment or a rollback, so
  it is designed and reviewed but not proven.
- TLS, a custom domain, alarms and an operations notification destination
  were never built.
