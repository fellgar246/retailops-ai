# AI review

- **Scope:** Reviewer contract, structured results, prompt versions, mock, routing, evaluation
- **Decisions:** [ADR-008](../adr/ADR-008-ai-review-contracts.md)

```bash
make review-eval
```

```bash
uv run retailops-review-eval --output data/reviews
```

That loads the versioned cases, runs `MockAIReviewer`, and writes
`evaluation.json` plus `evaluation.md`. Any implementation of `AIReviewer`
can be scored the same way. `BedrockAIReviewer` implements the contract
through Bedrock Converse. `retailops-review-eval --provider bedrock`
selects it when AWS is enabled; `--compare` writes mock and live reports
without overwriting prior prompt versions.

## What a reviewer may do

| Allowed | Forbidden |
|---|---|
| Classify uncertain category text | Deterministic financial arithmetic |
| Summarize findings | Silently mutate source records |
| Explain a reconciliation exception | Bypass validation |
| Suggest a next action | Auto-resolve high-risk cases without policy |
| Assign semantic confidence | |

Deterministic sheet findings stay the factual source of truth. Ordered,
received and invoiced amounts stay on the reconciliation run.

## Contract

```text
AIReviewer
├── MockAIReviewer
└── BedrockAIReviewer
```

`review(request) → ReviewResult`. Inputs are domain DTOs. The result must
parse through `parse_review_result`. Malformed output raises
`ReviewSchemaError` and is discarded.

| Field | Notes |
|---|---|
| `review_type` | `category_suggestion`, `supplier_summary`, `reconciliation_explanation` |
| `summary` | Short prose |
| `findings` | Optional structured notes (`code`, `message`, `suggested_value`) |
| `suggested_value` | e.g. a catalog code |
| `reasoning_summary` | Why the suggestion was made |
| `confidence` | `0`–`1` |
| `risk` | `low` / `medium` / `high` |
| `recommended_action` | `accept`, `request_correction`, `escalate`, `hold_payment`, `no_action`, `human_review` |
| `provider`, `model` | Who produced the payload |
| `prompt_id`, `prompt_version` | Registry coordinates |
| `input_schema_version`, `output_schema_version` | Currently `"1"` |

## Prompts

| Id | Purpose |
|---|---|
| `supplier.category_suggestion` | Classify uncertain category text |
| `supplier.summary` | Summarize deterministic findings |
| `reconciliation.explanation` | Explain one exception |

Each record stores version, purpose and the input / output schema
versions. Templates are not scattered through callers.

## Mock behaviours

| Behaviour | Result |
|---|---|
| `normal` | Valid fixture payload |
| `low_confidence` | Valid payload, confidence `0.22` |
| `malformed` | Invalid payload → schema error |
| `provider_failure` | `ReviewerError` |

The mock looks up a fixture by `case_id`. It does not infer from the
input.

## Workflows

```text
deterministic findings  →  review_supplier_sheet(reviewer?)  →  route
reconciliation exception →  explain_exception(reviewer)      →  route
```

Category suggestions and a sheet summary are optional. Findings are never
edited. An explanation copies `expected_value`, `actual_value` and
`financial_impact` from the exception.

## Routing

Default: human review.

Auto-eligible only when all of these hold:

- the result validated
- confidence ≥ `0.85`
- risk is `low`
- absolute financial impact is `0`
- recommended action is `accept` or `no_action`
- the source sheet has no deterministic errors

High risk, money, low confidence, a hold / escalate / correction action,
and provider or schema failures stay with a person. A broken call is
`ineligible` / `failed_safe`.

## Evaluation

Cases live in `apps/api/src/retailops_api/review/datasets/v001/cases.jsonl`.
Each row has structured `expected` attributes (suggested value, action,
risk, eligibility, outcome), not only prose.

| Metric | Definition |
|---|---|
| Schema validity | Valid parses among cases that were expected to return a payload |
| Classification accuracy | Suggested value, eligibility or classification label matches |
| Recommended-action accuracy | Action matches when an expected action is present |
| Confidence presence | Valid `ok` review results include confidence |
| Provider failure rate | Review cases that raised a provider error |

## Where the code lives

| Concern | Path |
|---|---|
| Policy | `apps/api/src/retailops_api/review/policy.py` |
| Contract | `apps/api/src/retailops_api/review/contract.py` |
| Schemas | `apps/api/src/retailops_api/review/schemas.py` |
| Prompts | `apps/api/src/retailops_api/review/prompts.py` |
| Mock | `apps/api/src/retailops_api/review/mock.py` |
| Bedrock | `apps/api/src/retailops_api/review/bedrock.py` |
| Supplier review | `apps/api/src/retailops_api/review/supplier.py` |
| Reconciliation explanation | `apps/api/src/retailops_api/review/reconciliation.py` |
| Routing | `apps/api/src/retailops_api/review/routing.py` |
| Dataset / harness | `apps/api/src/retailops_api/review/dataset.py`, `evaluate.py` |
| CLI | `apps/api/src/retailops_api/review/cli.py` |

Human decisions, the audit log and the metrics API are documented in
[human-review.md](human-review.md).
