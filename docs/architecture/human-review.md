# Human review

- **Scope:** Review cases, AI snapshots, decisions, audit log, queue, feedback, metrics
- **Migration:** `a9c4e18f7b21_human_review`
- **Decisions:** [ADR-009](../adr/ADR-009-human-review-audit-feedback.md)

```bash
make reviews
make review-feedback
```

```bash
uv run retailops-review queue
uv run retailops-review start 1 --reviewer alice
uv run retailops-review approve 1 --reviewer alice --comment ok
```

A case is one finding or one reconciliation exception waiting on a
person. Reviewer output, when present, is stored once and not edited.
Human closes are a separate row. History is appended.

## Status

```text
open  →  in_review  →  approved | rejected | corrected
  └──────────┴──────────→  cancelled
```

| From | To | How |
|---|---|---|
| `open` | `in_review` | start (or assign, which starts) |
| `open` | `cancelled` | cancel |
| `in_review` | `approved` | approve — optional comment, snapshot reference |
| `in_review` | `rejected` | reject — required reason, optional comment |
| `in_review` | `corrected` | correct — structured values |
| `in_review` | `cancelled` | cancel |
| `in_review` | `in_review` | assign a different reviewer |

Approved, rejected, corrected and cancelled do not leave those states.
Starting a case another reviewer already holds is a conflict. The same
reviewer may retry start.

## What is stored

| Entity | Table | Notes |
|---|---|---|
| Review case | `review_cases` | Priority, risk, confidence, financial impact, reviewer, timestamps |
| AI snapshot | `review_ai_snapshots` | Provider, model, prompt, original output, recommendation, input hash |
| Decision | `review_decisions` | Approve / reject / correct; correction JSON; accepted snapshot ref |
| Audit event | `review_audit_events` | created, opened, assigned, approved, rejected, corrected, status_changed |

Priority is derived from risk and absolute financial impact when the
caller does not set it. Document findings contribute zero impact;
exceptions use the signed amount on the match.

## Queue

`GET /reviews` and `retailops-review queue` filter by status, priority,
subject type, supplier, risk and created date. Order is urgent → high →
medium → low, then oldest `created_at`, then `id`. Pagination is
`limit` / `offset`.

## Feedback

Decided cases become evaluation rows: input reference, original AI
result, confidence, decision, correction, prompt id / version, provider
and model. `make review-feedback` writes `data/reviews/feedback.jsonl`.

## Metrics

`GET /reviews/metrics`:

| Field | Meaning |
|---|---|
| `open_cases` | Status `open` or `in_review` |
| `acceptance_rate` | Approved / decided |
| `rejection_rate` | Rejected / decided |
| `correction_rate` | Corrected / decided |
| `average_review_duration_seconds` | Mean `decided_at − opened_at` when both exist |

Decided means approved, rejected or corrected. Cancelled is counted
separately and is not in the rates.

## HTTP

| Method | Path | Purpose |
|---|---|---|
| GET | `/reviews` | Queue |
| POST | `/reviews` | Open a case |
| GET | `/reviews/{id}` | Case, snapshot and decision |
| GET | `/reviews/{id}/audit` | Event history |
| POST | `/reviews/{id}/start` | Open → in review |
| POST | `/reviews/{id}/assign` | Set reviewer |
| POST | `/reviews/{id}/approve` | Accept the recommendation |
| POST | `/reviews/{id}/reject` | Reject with a reason |
| POST | `/reviews/{id}/correct` | Store a structured correction |
| POST | `/reviews/{id}/cancel` | Cancel |
| GET | `/reviews/feedback` | Evaluation rows |
| GET | `/reviews/metrics` | Rates and open-case count |

Reviewer identity is a string on each write. Sign-in is not implemented.

## Where the code lives

| Concern | Path |
|---|---|
| Models | `apps/api/src/retailops_api/domain/models/review.py` |
| Transitions | `apps/api/src/retailops_api/review/cases.py` |
| Persist | `apps/api/src/retailops_api/review/persist.py` |
| Queue | `apps/api/src/retailops_api/review/queue.py` |
| Workflow | `apps/api/src/retailops_api/review/workflow.py` |
| Callback mapping | `apps/api/src/retailops_api/review/cloud_workflow.py` |
| Audit | `apps/api/src/retailops_api/review/audit.py` |
| Feedback | `apps/api/src/retailops_api/review/feedback.py` |
| Metrics | `apps/api/src/retailops_api/review/metrics.py` |
| HTTP | `apps/api/src/retailops_api/api/routes/reviews.py` |
| CLI | `apps/api/src/retailops_api/review/ops_cli.py` |
