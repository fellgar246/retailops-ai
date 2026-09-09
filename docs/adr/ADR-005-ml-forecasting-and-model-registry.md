# ADR-005 — ML Forecasting and Local Model Registry

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Feature contract, histogram-GBM training, champion/challenger promotion, artifact format, local registry

## Context

Baselines, a weekly demand frame and walk-forward evaluation already exist.
The next step is a learned model that can be trained as application code,
compared fairly against those baselines, packaged so it reloads in a fresh
process, and versioned behind an interface that does not assume a cloud
vendor.

## Decision

### Features known at the origin

The default matrix uses:

- the calendar of the *target* week (ISO week, month flags, Christmas, New
  Year, Buen Fin, holidays)
- configurable lags of the target
- shifted rolling mean / median / std (optional min/max)
- lagged price, discount, promotion rate and stock
- integer encodings of store, category, region and store type
- `horizon_step`

Lag and rolling features read only weeks strictly before the target and on
or before the cutoff. Contemporaneous price, promotion and stock of the
target week are listed on the contract and excluded: those values come from
the week's own sales and would leak the label.

### One gradient-boosted tree

The first learned model is scikit-learn's histogram gradient boosting
(`HistGradientBoostingRegressor`). Every hyperparameter lives on
`HistGBMTrainerConfig` (tree count, learning rate, max depth, min samples
per leaf, max leaf nodes, L2, seed). Training is deterministic for a given
config and frame. The fitted object implements the same
`predict(history, cutoff, horizon)` contract as the baselines.

A native LightGBM or XGBoost wheel needs a system OpenMP runtime on macOS
(``libomp``). Histogram GBM installs with ``uv sync`` alone, so training
stays a single application command.

### Promotion needs two gates

A candidate is scored from the locked train-end origin against naive,
seasonal naive, moving average and the current champion when one exists.

- **Accuracy:** WAPE must be strictly below every comparison model.
- **Secondary:** MAE must be at most the champion MAE, or at most the best
  baseline MAE when there is no champion.

A win on one metric is never enough. Bias is reported, not gated.

### Artifacts are directories, not notebooks

A version directory holds the native booster, metadata, the feature list and
contract, training config, metrics, the dataset fingerprint, runtime
versions, identifier encodings and the lagged commercial snapshot. `load_artifact`
rebuilds the forecaster with no interpreter state.

### Registry is a contract

`ModelRegistry` exposes register, list versions, get version, update
approval and get champion. `LocalModelRegistry` stores
`artifacts/models/<name>/v001`. Approval values are candidate, approved,
champion, rejected and archived. Promoting a version to champion demotes the
previous champion to approved.

The same operations map onto SageMaker Model Registry without changing
callers: register → `CreateModelPackage` / a new `ModelPackageVersion`;
approval → `ModelApprovalStatus`; champion → the approved package an
endpoint or batch transform loads; artifact files → the S3 model data the
package points at.

## Consequences

**Positive**

- Training is a `make train` command, not a notebook.
- Leakage is testable: the same `predict` on the full frame and the
  truncated frame must agree, and lag/rolling builders ignore poison after
  the cutoff.
- A later hosted registry can implement the same protocol.

**Negative**

- Commercial lags at inference come from the snapshot stored at fit time.
  A brand-new sales history needs a retraining (or a rebuilt snapshot).
- The first promotion bar is conservative; a useful model may stay a
  candidate until it beats every baseline on both WAPE and MAE.

**Deferred**

- Serving the champion over HTTP.
- Automatic refits on a schedule.
- A second tree library. Histogram GBM is the only booster for now.
