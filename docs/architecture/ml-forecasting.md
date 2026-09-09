# ML forecasting and the local model registry

- **Scope:** Feature contract, histogram-GBM training, promotion policy, artifacts, local registry
- **Decisions:** [ADR-005](../adr/ADR-005-ml-forecasting-and-model-registry.md)

```bash
make train
```

That generates (or loads) the weekly demand frame, builds the feature
matrix, fits the histogram GBM, scores the candidate against the baselines, writes
`data/forecasts/train_metrics.json` and `train_report.md`, and registers a
candidate under `artifacts/models/category-forecast/`.

```bash
uv run retailops-train --input data/synthetic --promote
```

`--promote` applies the two-gate policy and sets the champion only when
both gates pass.

## Feature contract

| Family | Names | Known at prediction time? | Leakage |
|---|---|---|---|
| Horizon | `horizon_step` | yes | none |
| Calendar | ISO week/year, month, week-of-month, month-boundary and mid-month flags, Christmas / New Year / Buen Fin / holiday day counts, mean demand multiplier | yes (date + holiday list) | none |
| Lags | `lag_1`, `lag_2`, `lag_4`, `lag_8` (configurable) | yes, from history ≤ cutoff | historical only |
| Rolling | mean, median, std of the last *n* weeks; optional min/max | yes, window is shifted | historical only |
| Price / discount / promo / stock | `*_lag_1` | last observed week ≤ cutoff | historical only |
| Identifiers | store, category, region, store type encodings | yes | none |
| Contemporaneous commercial | `avg_price`, `avg_discount`, `promo_rate`, `avg_stock`, `stockout_rate` of the **target** week | no | leaky if taken from that week's sales |

Rolling statistics never include the target week (they are shifted). A lag
whose lookback is after the cutoff is `0`.

## Training frame

Each supervised row is one `(store, category, origin, horizon step)`. The
label is the target week `origin + step`, and that week must lie on or
before `train_end` so validation labels cannot enter the fit. The frame
stores:

- dataset checksum
- feature names
- feature configuration
- holdout cutoffs
- identifier maps and the commercial snapshot

## Histogram gradient boosting

`HistGBMTrainerConfig` is the full set of knobs: `n_estimators`,
`learning_rate`, `max_depth`, `min_samples_leaf`, `max_leaf_nodes`,
`l2_regularization`, `random_state`. A fixed seed keeps two runs with the
same frame identical. Predictions are clipped at zero. The estimator is
scikit-learn's `HistGradientBoostingRegressor`, written with joblib.


## Promotion policy

Scored from `train_end` for the problem horizon, the same origin for every
model.

1. Candidate WAPE < WAPE of naive, seasonal naive, moving average, and the
   current champion when one exists.
2. Candidate MAE ≤ champion MAE, or ≤ the best baseline MAE when there is
   no champion.

Both must pass. Bias is diagnostic only.

## Artifact layout

```text
artifacts/models/category-forecast/
├── index.json
└── v001/
    ├── model.joblib
    ├── metadata.json
    ├── features.json
    ├── training_config.json
    ├── metrics.json
    ├── data_fingerprint.json
    ├── runtime.json
    ├── encodings.json
    └── observables.json
```

`load_artifact(path)` rebuilds the forecaster. Nothing is read from
notebook or in-memory Python state.

## Local registry

| Operation | Local behaviour |
|---|---|
| register | Copy the artifact into the next `vNNN`, status `candidate` |
| list versions | Read `index.json`, sorted by version number |
| retrieve version | Path plus metadata for that `vNNN` |
| update approval | `candidate` / `approved` / `champion` / `rejected` / `archived`. A new champion demotes the previous one to `approved` |
| retrieve champion | The version whose status is `champion`, or `None` |

## Mapping to SageMaker Model Registry

| Local | SageMaker |
|---|---|
| `LocalModelRegistry.register` | `CreateModelPackage` (or a new version of an existing group) |
| `v001`, `v002` | `ModelPackageVersion` |
| `artifacts/models/<name>/<version>/` | Model data in S3 referenced by the package |
| `metadata.json` / `runtime.json` | Package inference specification and customer metadata |
| `ApprovalStatus.candidate` | `PendingManualApproval` |
| `ApprovalStatus.approved` / `champion` | `Approved` (champion is the approved version the endpoint or batch job is configured to use) |
| `ApprovalStatus.rejected` | `Rejected` |
| `get_champion` | The approved package ARN wired to `CreateEndpoint` / a transform job |

Callers depend on `ModelRegistry`, not on the filesystem.
`SageMakerModelRegistry` implements the same operations with an injected
client. It records package metadata and a declared artifact URI; it does
not upload files. Champion selection is the version marked
`retailops_approval=champion`, not “latest approved”.
