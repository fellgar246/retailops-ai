# ADR-008 — AI Review Contracts, Mock Provider and Evaluation

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Reviewer interface, structured outputs, prompt versions, mock, routing, evaluation

## Context

Supplier intake and three-way matching already produce deterministic
findings and exceptions. Semantic help — classifying uncertain category
text, summarizing a sheet, explaining why a line does not match — should
be available without a live model, and without letting a model do the
arithmetic or silently change source rows.

A hosted model adapter must be able to implement the same calls and be
measured on the same cases.

## Decision

### Usage policy

A reviewer may classify uncertain category text, summarize findings,
explain reconciliation exceptions, suggest a next action and assign
semantic confidence.

A reviewer may not perform deterministic financial arithmetic, silently
mutate source records, bypass validation, or auto-resolve a high-risk
case without the routing policy.

### One interface

`AIReviewer.review(request) → ReviewResult`. The request carries a domain
DTO (`CategorySuggestionInput`, `SupplierSummaryInput` or
`ReconciliationExplanationInput`) plus prompt id and version. The result
is a validated object: review type, summary, findings, optional suggested
value, reasoning, confidence in `[0, 1]`, risk, recommended action,
provider/model metadata and prompt / schema versions.

`parse_review_result` is the only accepted parser. Malformed JSON, a
missing field, an unknown action or a confidence outside the unit
interval raises `ReviewSchemaError`. Callers must not read a partial
payload.

### Prompts are versioned records

Each prompt has an id, version, purpose, input schema version and output
schema version. Templates live in one registry. Callers look up a spec;
they do not embed prompt text.

### The mock is a test double

`MockAIReviewer` plays back fixtures for four behaviours: normal, low
confidence, malformed and provider failure. It does not infer from the
payload. A missing fixture uses the configured default behaviour.

### Workflows stay deterministic

`review_supplier_sheet` copies the existing findings unchanged and may
ask for category suggestions and a summary. `explain_exception` keeps
expected value, actual value and financial impact from the match. The
reviewer may only add prose, risk and a suggested action.

### Routing defaults to a human

Auto-eligibility requires a valid result, confidence at least 0.85, low
risk, absolute financial impact of zero, and an `accept` or `no_action`
recommendation. High risk, source validation errors, low confidence,
non-zero money, an escalate / hold-payment / correction action, and
provider or schema failures all stay with a person. Failures are
`ineligible` / `failed_safe` so a broken payload is never treated as a
suggestion.

### Evaluation is storage-neutral

Versioned JSONL cases cover category suggestions, supplier summaries,
reconciliation explanations and routing. Expected fields are structured
(suggested value, action, risk, eligibility), not only prose. The harness
runs any `AIReviewer` and records schema validity, classification
accuracy, recommended-action accuracy, confidence presence and provider
failure rate. Reports are JSON and Markdown.

## Consequences

**Positive**

- A hosted adapter can implement `review` and be scored without changing
  callers.
- Deterministic findings and match amounts remain the source of truth.
- Evaluation runs locally with `make review-eval`.

**Negative**

- The mock cannot be used as a stand-in for model quality; it only
  exercises the contract.
- Auto-eligibility is intentionally rare.

**Deferred**

- Invoking a live Bedrock model from the running API.

Human review cases, decisions, the audit log and the metrics HTTP API
are described in [ADR-009](ADR-009-human-review-audit-feedback.md).
