# ADR-004 — Forecast Evaluation and Baselines

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Weekly demand frame, temporal splits, statistical baselines, walk-forward evaluation, forecast persistence

## Context

The catalog and daily sales history exist. Before any learned model is trained,
the project needs a demand problem that is stable, a frame that can be rebuilt
from sales, a split that cannot leak the future, three honest baselines, and a
place to store runs so a later model can be compared on the same folds.

The first problem is weekly category demand per store: it is coarse enough to
be dense on a year of synthetic history, fine enough to be useful for
replenishment, and it uses the category key the catalog already requires on
every product.

## Decision

### Problem

Daily `units_sold` is summed across products in a category, for each store,
on each complete ISO week (Monday–Sunday). Incomplete edge weeks are dropped.
A store–category week with no sales is stored as zero so the panel stays
balanced. The default horizon is four weeks. Parent categories are not rolled
up; the product's assigned category is the grain.

### Splits are temporal

Rows are never shuffled. Train ends at an inclusive cutoff; validation is the
weeks after that through a second cutoff; test is everything after. A holdout
helper locks the last eight weeks as test and the four before that as
validation so those dates can be written down.

### Baselines share one interface

`predict(history, cutoff, horizon)` is the contract a later model must
implement. The full frame may be passed in; implementations must ignore every
row after the cutoff.

- **Naive** repeats the last observed week.
- **Seasonal naive** uses the week `seasonal_lag` earlier (default 52). When
  that lookback is missing it falls back to naive, then to zero. On a single
  year of weekly data the 52-week lookback is almost never present.
- **Moving average** takes the mean of the last `window` weeks on or before
  the cutoff (default 4) and repeats that mean across the horizon.

### Metrics

MAE, RMSE, WAPE and mean signed bias. When every actual is zero, WAPE is 0 if
every prediction is also zero and 1 otherwise, so the metric stays defined on
all-zero weeks.

### Walk-forward evaluation

Origins advance one week at a time. The first origin leaves twelve weeks of
history; the last origin still has four observed weeks after it. Each fold
records cutoff, horizon, model, metrics and predictions. Overall metrics are
the micro-average of every scored pair.

### Persistence

`ForecastRun` is one model at one origin. `ForecastPrediction` is one store–
category week belonging to that run. Both are immutable facts (created_at
only). Predictions use store and category business codes rather than catalog
foreign keys so a run can be stored from a portable dataset. Deleting a run
cascades to its predictions; they have no meaning without it. The unique
constraint name is shortened to `uq_forecast_predictions_run_entity_week`
because the column-concatenated default exceeds PostgreSQL's 63-character
identifier limit.

## Consequences

**Positive**

- A later model can be scored on the same folds and the same metrics.
- Leakage is testable: the same `predict` call on the full frame and on the
  truncated frame must agree.
- The development benchmark is deterministic for a given generator seed.

**Negative**

- Seasonal naive with a 52-week lag is mostly the naive fallback until a
  second year of history exists. That is documented, not hidden.
- Predictions are not referentially tied to `stores` or `categories`, so a
  renamed business code will not cascade.

**Deferred**

- Learned models, feature stores and serving APIs are out of scope here.
- Filling `actual` on an already-persisted open-horizon run, once the week
  has occurred, is a later write path.
