"""Gradient-boosted weekly demand model (histogram GBM).

Hyperparameters are explicit on ``HistGBMTrainerConfig``. Training writes a
joblib snapshot of the estimator plus the feature contract; inference
rebuilds the same matrix and does not depend on notebook state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from retailops_api.forecasting.coerce import as_float, as_int
from retailops_api.forecasting.feature_contract import (
    CATEGORICAL_FEATURE_NAMES,
    FeatureConfig,
)
from retailops_api.forecasting.feature_panel import FeatureFrame, FeatureRow, build_inference_rows
from retailops_api.forecasting.features import IdentifierMaps, WeeklyObservables
from retailops_api.forecasting.frame import ForecastFrame
from retailops_api.forecasting.models import ForecastPoint
from retailops_api.forecasting.weeks import iso_week_start

DEFAULT_N_ESTIMATORS = 200
DEFAULT_LEARNING_RATE = 0.05
DEFAULT_MAX_DEPTH = 6
DEFAULT_MIN_SAMPLES_LEAF = 20
DEFAULT_MAX_LEAF_NODES = 31
DEFAULT_L2 = 1.0
DEFAULT_RANDOM_STATE = 42


@dataclass(frozen=True)
class HistGBMTrainerConfig:
    """Every knob that changes the fitted booster."""

    n_estimators: int = DEFAULT_N_ESTIMATORS
    learning_rate: float = DEFAULT_LEARNING_RATE
    max_depth: int = DEFAULT_MAX_DEPTH
    min_samples_leaf: int = DEFAULT_MIN_SAMPLES_LEAF
    max_leaf_nodes: int = DEFAULT_MAX_LEAF_NODES
    l2_regularization: float = DEFAULT_L2
    random_state: int = DEFAULT_RANDOM_STATE

    def __post_init__(self) -> None:
        if self.n_estimators < 1:
            raise ValueError("n_estimators must be at least 1")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if self.max_depth < 1:
            raise ValueError("max_depth must be at least 1")
        if self.min_samples_leaf < 1:
            raise ValueError("min_samples_leaf must be at least 1")
        if self.max_leaf_nodes < 2:
            raise ValueError("max_leaf_nodes must be at least 2")
        if self.l2_regularization < 0:
            raise ValueError("l2_regularization must be non-negative")

    def to_dict(self) -> dict[str, float | int]:
        return {
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
            "max_leaf_nodes": self.max_leaf_nodes,
            "l2_regularization": self.l2_regularization,
            "random_state": self.random_state,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> HistGBMTrainerConfig:
        return cls(
            n_estimators=as_int(payload.get("n_estimators"), DEFAULT_N_ESTIMATORS),
            learning_rate=as_float(payload.get("learning_rate"), DEFAULT_LEARNING_RATE),
            max_depth=as_int(payload.get("max_depth"), DEFAULT_MAX_DEPTH),
            min_samples_leaf=as_int(payload.get("min_samples_leaf"), DEFAULT_MIN_SAMPLES_LEAF),
            max_leaf_nodes=as_int(payload.get("max_leaf_nodes"), DEFAULT_MAX_LEAF_NODES),
            l2_regularization=as_float(payload.get("l2_regularization"), DEFAULT_L2),
            random_state=as_int(payload.get("random_state"), DEFAULT_RANDOM_STATE),
        )


class HistGBMForecaster:
    """Fitted histogram GBM that implements ``predict(history, cutoff, horizon)``.

    Rows after ``cutoff`` in ``history`` are not read. Commercial lags come
    from the observables snapshot stored at fit time, filtered by the cutoff.
    Predictions are clipped at zero.
    """

    def __init__(
        self,
        *,
        estimator: Any,
        feature_config: FeatureConfig,
        trainer_config: HistGBMTrainerConfig,
        feature_names: tuple[str, ...],
        identifier_maps: IdentifierMaps,
        observables: tuple[WeeklyObservables, ...] = (),
        model_id: str = "hist_gbm",
    ) -> None:
        self.model_id = model_id
        self._estimator = estimator
        self.feature_config = feature_config
        self.trainer_config = trainer_config
        self.feature_names = feature_names
        self.identifier_maps = identifier_maps
        self.observables = observables

    @property
    def estimator(self) -> Any:
        return self._estimator

    def predict(
        self,
        history: ForecastFrame,
        *,
        cutoff: date,
        horizon: int,
    ) -> tuple[ForecastPoint, ...]:
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        origin = iso_week_start(cutoff)
        rows = build_inference_rows(
            history,
            cutoff=origin,
            horizon=horizon,
            config=self.feature_config,
            identifier_maps=self.identifier_maps,
            observables=self.observables,
        )
        if not rows:
            return ()
        predicted = self._predict_rows(rows)
        return tuple(
            ForecastPoint(
                store_code=row.store_code,
                category_code=row.category_code,
                period_start=row.period_start,
                step=row.horizon_step,
                predicted=max(0.0, float(value)),
            )
            for row, value in zip(rows, predicted, strict=True)
        )

    def _predict_rows(self, rows: tuple[FeatureRow, ...]) -> np.ndarray:
        matrix = feature_matrix(rows)
        raw = np.asarray(self._estimator.predict(matrix), dtype=float)
        return np.atleast_1d(raw)


def feature_matrix(rows: Sequence[FeatureRow]) -> np.ndarray:
    if not rows:
        return np.empty((0, 0), dtype=np.float64)
    return np.asarray([row.values for row in rows], dtype=np.float64)


def label_vector(rows: Sequence[FeatureRow]) -> np.ndarray:
    missing = [row for row in rows if row.target is None]
    if missing:
        raise ValueError("cannot train: a supervised row is missing its target")
    return np.asarray([row.target for row in rows], dtype=np.float64)


def train_hist_gbm(
    train: FeatureFrame,
    *,
    trainer: HistGBMTrainerConfig | None = None,
    identifier_maps: IdentifierMaps | None = None,
    observables: tuple[WeeklyObservables, ...] | None = None,
) -> HistGBMForecaster:
    """Fit one booster on ``train``. Configuration is taken from ``trainer``."""
    if not train.rows:
        raise ValueError("cannot train: the supervised frame is empty")
    chosen = trainer or HistGBMTrainerConfig()
    maps = identifier_maps or train.identifier_maps
    if maps is None:
        raise ValueError("identifier maps are required to train")
    names = train.feature_names
    matrix = feature_matrix(train.rows)
    labels = label_vector(train.rows)
    categorical = [index for index, name in enumerate(names) if name in CATEGORICAL_FEATURE_NAMES]
    estimator = _fit_estimator(matrix, labels, categorical, chosen)
    return HistGBMForecaster(
        estimator=estimator,
        feature_config=train.config,
        trainer_config=chosen,
        feature_names=names,
        identifier_maps=maps,
        observables=observables if observables is not None else train.observables,
    )


def _fit_estimator(
    matrix: np.ndarray,
    labels: np.ndarray,
    categorical: list[int],
    trainer: HistGBMTrainerConfig,
) -> Any:
    from sklearn.ensemble import HistGradientBoostingRegressor

    estimator = HistGradientBoostingRegressor(
        max_iter=trainer.n_estimators,
        learning_rate=trainer.learning_rate,
        max_depth=trainer.max_depth,
        min_samples_leaf=trainer.min_samples_leaf,
        max_leaf_nodes=trainer.max_leaf_nodes,
        l2_regularization=trainer.l2_regularization,
        random_state=trainer.random_state,
        categorical_features=categorical or None,
    )
    estimator.fit(matrix, labels)
    return estimator
