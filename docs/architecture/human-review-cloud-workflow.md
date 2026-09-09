# Human review callback workflow

- **Scope:** Mapping from local `ReviewCase` transitions to a wait-for-callback orchestrator
- **Decisions:** [ADR-009](../adr/ADR-009-human-review-audit-feedback.md), [ADR-010](../adr/ADR-010-aws-adapters-and-terraform.md)

The persisted functions in `review/workflow.py` remain the implementation.
`LocalCallbackWorkflow` records the events a hosted state machine would
emit. It does not start a remote execution.

## Local to callback events

| Local action | Callback event |
|---|---|
| `start_review` (open → in_review) | Workflow **start** and a **task token** |
| `approve_review` / `reject_review` / `correct_review` | **Success** callback with the decision |
| `cancel_review` | **Failure** callback |
| Wait exceeds `timeout_seconds` | **Timeout** |

## Identifiers

| Field | Value |
|---|---|
| Correlation id | `review-case:{case_id}` |
| Idempotency key | `{subject_reference}:{case_id}` e.g. `document_finding:12:44` |
| Task token | Issued at start; consumed by the first terminal callback |

Starting the same open case again returns the existing token. A second
success or failure on that token is a conflict. Timeout is only legal
after `expires_at`.

## Hosted shape

The Terraform state machine `*-review` sends the token to the review
callback SQS queue (`arn:aws:states:::sqs:sendMessage.waitForTaskToken`)
and waits. The API task role is allowed `states:SendTaskSuccess`,
`SendTaskFailure` and `SendTaskHeartbeat`. Default timeout is seven days.

Until that execution path is wired, operators use `retailops-review` and
the `/reviews` HTTP API against the local status machine.

## Where the code lives

| Concern | Path |
|---|---|
| Local transitions | `apps/api/src/retailops_api/review/workflow.py` |
| Callback mapping | `apps/api/src/retailops_api/review/cloud_workflow.py` |
| State machine | `infra/modules/step_functions` |
