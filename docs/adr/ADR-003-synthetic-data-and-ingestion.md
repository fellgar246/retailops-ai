# ADR-003 — Synthetic Retail Dataset and Ingestion

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Synthetic catalog and sales history, portable files, ingestion

## Context

Local development and forecasting experiments need a year-scale sales history
that is realistic enough to be interesting and stable enough to be shared.
The database already has a catalog schema and a daily sales fact; what was
missing is a way to produce that history and load it without one-row ORM
inserts or irreproducible random draws.

The generator must not make forecasting trivial: a constant, a pure weekday
dummy or a straight line would let a model "succeed" without learning
anything. Promotions, prices, stockouts and calendar events have to interact.

## Decision

### Portable files, then ingest

The generator writes CSV files under `data/synthetic/` using business codes
(`sku`, `store_code`, …), not surrogate ids. Ingestion resolves those codes
in bulk. Files can be checksummed, diffed and re-ingested without a live
database.

### Deterministic configuration

A frozen `GeneratorConfig` (seed, date range, entity counts, promotion and
stockout probabilities, holidays) fully determines the output. Named scales
`tiny`, `development` and `benchmark` are the usual starting points. Catalog
and demand use separate RNG streams derived from the seed so a date-range
change does not reshuffle the catalog.

### Demand is a product of several effects

Unconstrained demand multiplies popularity, category and store factors, a
seasonal sine, a Q4 lift, the calendar multiplier, promotional lift and
log-normal noise. Stock then censors the sold quantity. Calendar flags
(weekend, month boundary, Christmas, New Year, Buen Fin, holidays) are also
written to `calendar.csv` so modelling jobs can reuse them as features.

### Duplicate strategy is upsert

Sales identity is `(store_id, product_id, business_date)`. Re-ingesting a
file replaces measures and keeps `created_at`. Duplicates inside a file are
rejected. Catalog identity is the business code; a second run updates in
place and does not bump `updated_at` when nothing changed.

### Transaction boundaries

Neither ingest function commits. Catalog failure raises so the caller can
roll the whole catalog write back. Sales validation rejects are data-quality
events: they are listed on the run report and the accepted rows are still
written. Unexpected database errors raise and the caller rolls back.

### Run report

Every ingest emits structured metadata: source, run id, start and end, rows
read / accepted / rejected, duplicate count, validation errors, optional
catalog counts and checksum.

## Consequences

**Positive**

- `make synthetic` is a single, repeatable local workflow.
- The same seed always yields the same checksum, so accidental generator
  drift is visible.
- Forecasting has interacting effects and censored demand rather than a
  single obvious pattern.
- Ingestion is safe to re-run against a database that already has data.

**Negative**

- A million-row benchmark materialises the sales tuple in memory. That is
  acceptable for local use; a streaming write can be added if it becomes a
  problem.
- Ingesting a synthetic catalog after `make seed` upserts any overlapping
  business codes (for example `ST-001`).

**Deferred**

- Reading real POS exports through the same contract.
- Persisting calendar rows in the database; they stay a file of features.
