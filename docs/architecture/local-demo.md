# Local demo walkthrough

A 5–10 minute pass through the operations console after `make demo` and
`make dev`. Every number on screen comes from the API.

## Before you start

```bash
make ready
make demo
make dev
```

Sign-in is not implemented. Set the reviewer name under **Configuración**
(default `alice`). That string is what the API stores on decisions.

## 1. Category demand forecast (~1 min)

Open **Pronósticos**. The demo persists one naive weekly run tagged as the
local dataset (`run_metadata.source = local-demo`).

- The list shows model, cutoff, horizon and WAPE when actuals exist.
- Open the run. The series is weekly category demand per store.
- Filters for store and category stay on the same payload.

`make train` is separate: it fits the histogram-GBM, writes an artifact under
`artifacts/models/` and can persist a later run. The console reads whatever
`ForecastRun` rows are in the database.

## 2. Supplier anomaly (~1 min)

Open **Documentos de proveedor**. The demo ingested three BevCo sheets:

| File | What it shows |
| ---- | ------------- |
| `demo-cost-increase.csv` | Known SKU at a higher cost than the catalog |
| `demo-new-items.csv` | Unknown supplier SKUs |
| `demo-malformed.csv` | A cost that is not a number |

Open the cost-increase file. Findings are labelled as deterministic rules.
Extracted rows, when storage is reachable, are labelled as extracted. Related
review cases appear on the same page.

## 3. Purchase-order exception (~1 min)

Open **Conciliaciones**. Two scopes are already matched:

- `PO-DEMO-OVER` — invoiced quantity 12 against ordered/received 10
- `PO-DEMO-COST` — invoiced unit cost 8.00 against PO cost 7.45

Open a run. Expected and actual values and the signed impact come from the
match engine, not from the reviewer. Provenance stays `rule`.

## 4. Human review (~3 min)

Open **Revisiones**. Cases exist for material document findings and for the
open exceptions. The mock reviewer attached an immutable snapshot.

On a case:

1. **Tomar caso** moves `open` → `in_review`.
2. The left column is deterministic facts; the AI proposal is labelled as
   interpretation.
3. **Aprobar recomendación**, **Rechazar propuesta** (reason required) or
   **Confirmar corrección**.
4. The audit list at the bottom appends the transition. A 409 conflict keeps
   the page and asks you to reload.

The approve control is reachable with the keyboard. At 1280 px and 200 % zoom
the workspace stacks into a single column.

## 5. Audit and evaluation (~1 min)

- **Auditoría** lists recent review events across cases.
- **Evaluación de IA** shows acceptance / rejection / correction rates and the
  decided-case feedback export. `make review-eval` scores the mock on the
  versioned fixture set and writes `data/reviews/`.

Search from the top bar looks up documents, reviews, exceptions and forecast
runs.

## Current limitations

- No AWS, hosted object storage, Bedrock adapter or cloud deployment.
- The reviewer in this dataset is the fixture mock. It does not call a live
  model and it does not invent findings.
- Reviewer identity is a local string. There is no authentication.
- The demo forecast is a naive baseline so `make demo` stays fast. Train the
  gradient-boosted model with `make train` when you want a registered artifact.
- Document bytes live on the local disk (`DOCUMENT_STORAGE_ROOT` or
  `data/documents`).
- `GET /health/db` is how an unreachable database shows up; bring PostgreSQL
  back with `make db-up` and refresh.
