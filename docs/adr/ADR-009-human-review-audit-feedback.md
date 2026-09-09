# ADR-009 — Human Review, Audit and Feedback

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Review cases, AI snapshots, decisions, audit log, queue, feedback, metrics API

## Context

Routing already sends most reviewer output to a person. Those items need a
durable queue: who is looking, what the model said, what the person decided,
and a history that can train the next evaluation pass. Sign-in is not
required yet. A callback-token mapping exists; a live Step Functions
execution is not started.

## Decision

### One case per subject

A `ReviewCase` links to exactly one `document_finding` or one
`reconciliation_exception`. Re-opening the same subject returns the
existing row. The case stores priority, risk, confidence, financial
impact, the assigned reviewer and timestamps. Subject foreign keys are
`ON DELETE RESTRICT` so a reviewed finding cannot disappear.

### Status is a closed set

`open` → `in_review` → `approved` / `rejected` / `corrected`. `cancelled`
is allowed from `open` or `in_review`. Terminal statuses do not leave
those states. Start is idempotent for the same reviewer and conflicts
when another reviewer already holds the case.

### The AI snapshot is a fact

`ReviewAISnapshot` stores provider, model, prompt id and version, the
original JSON output, confidence, the recommended action, an input hash
and a readable reference key. There is no `updated_at`. A second create
does not rewrite those bytes.

### Decisions are a separate row

Approve records the reviewer, timestamp, optional comment and a
reference to the accepted snapshot. Reject requires a reason. Correct
stores structured values (`suggested_value`, `recommended_action`,
`risk`, `summary`, `fields`) beside the original snapshot. One decision
per case.

### Audit is append-only

`ReviewAuditEvent` records created, opened, assigned, approved,
rejected, corrected and status_changed. Existing events are not updated.

### Queue, feedback and metrics

The queue filters by status, priority, subject type, supplier, risk and
created date, and pages with a stable order: priority, then
`created_at`, then `id`. Feedback rows export input reference, AI
result, confidence, decision, correction and prompt / model versions.
`GET /reviews/metrics` returns open-case count (open + in review),
acceptance / rejection / correction rates among decided cases, and
average `decided_at - opened_at` when both exist.

Local reviewer identity is an explicit string on each command.

## Consequences

**Positive**

- Human oversight works without a hosted model or an operations UI.
- Evaluation can consume decided rows without reading live cases.

**Negative**

- Reviewer identity is not authenticated.
- A document cannot be deleted while a finding still has a case.

**Deferred**

- Starting a live wait-for-callback execution from `start_review`.
- Authenticated reviewer identity.
