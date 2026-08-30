"""Walk-forward (rolling-origin) evaluation.

At each origin the model may read history through that cutoff, inclusive, and
must forecast the next ``horizon`` weeks. Origins advance by ``step_weeks``.
The first origin is the week that first leaves ``min_train_periods`` weeks of
history; the last origin is the week that still has ``horizon`` observed weeks
after it, so every fold can be scored.

Each fold records the cutoff, the horizon, the model id, the metrics and the
predictions (with actuals attached from the frame).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retailops_api.forecasting.frame import ForecastFrame, require_periods
from retailops_api.forecasting.metrics import ForecastMetrics, score_points
from retailops_api.forecasting.models import Forecaster, ForecastPoint
from retailops_api.forecasting.problem import DEFAULT_MIN_TRAIN_PERIODS, DEFAULT_STEP_WEEKS
from retailops_api.forecasting.weeks import add_weeks


@dataclass(frozen=True)
class BacktestFold:
    cutoff: date
    horizon: int
    model_id: str
    metrics: ForecastMetrics
    predictions: tuple[ForecastPoint, ...]


@dataclass(frozen=True)
class BacktestResult:
    model_id: str
    horizon: int
    folds: tuple[BacktestFold, ...]
    overall: ForecastMetrics

    @property
    def first_cutoff(self) -> date:
        return self.folds[0].cutoff

    @property
    def last_cutoff(self) -> date:
        return self.folds[-1].cutoff


def rolling_origins(
    frame: ForecastFrame,
    *,
    horizon: int,
    min_train_periods: int = DEFAULT_MIN_TRAIN_PERIODS,
    step_weeks: int = DEFAULT_STEP_WEEKS,
) -> tuple[date, ...]:
    """Cutoffs at which a walk-forward fold can be scored."""
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    if min_train_periods < 1:
        raise ValueError("min_train_periods must be at least 1")
    if step_weeks < 1:
        raise ValueError("step_weeks must be at least 1")
    periods = require_periods(
        frame,
        min_train_periods + horizon,
        what="a rolling backtest",
    )
    last_index = len(periods) - horizon - 1
    first_index = min_train_periods - 1
    return tuple(periods[index] for index in range(first_index, last_index + 1, step_weeks))


def attach_actuals(
    predictions: tuple[ForecastPoint, ...],
    frame: ForecastFrame,
) -> tuple[ForecastPoint, ...]:
    """Copy observed targets onto predictions when the week exists in ``frame``."""
    return tuple(
        point.with_actual(frame.target_at(point.entity, point.period_start))
        for point in predictions
    )


def walk_forward(
    frame: ForecastFrame,
    model: Forecaster,
    *,
    horizon: int,
    min_train_periods: int = DEFAULT_MIN_TRAIN_PERIODS,
    step_weeks: int = DEFAULT_STEP_WEEKS,
) -> BacktestResult:
    """Evaluate ``model`` at every rolling origin.

    The full frame is passed to ``predict`` so a leaky model would see future
    targets; honest models ignore rows after the cutoff. Actuals used for
    scoring come from the frame after the cutoff.
    """
    origins = rolling_origins(
        frame,
        horizon=horizon,
        min_train_periods=min_train_periods,
        step_weeks=step_weeks,
    )
    folds: list[BacktestFold] = []
    all_points: list[ForecastPoint] = []
    for cutoff in origins:
        expected_last = add_weeks(cutoff, horizon)
        if expected_last not in set(frame.periods()):
            raise ValueError(
                f"fold at {cutoff.isoformat()} is missing the horizon week "
                f"{expected_last.isoformat()}"
            )
        raw = model.predict(frame, cutoff=cutoff, horizon=horizon)
        scored = attach_actuals(raw, frame)
        fold = BacktestFold(
            cutoff=cutoff,
            horizon=horizon,
            model_id=model.model_id,
            metrics=score_points(scored),
            predictions=scored,
        )
        folds.append(fold)
        all_points.extend(scored)
    if not folds:
        raise ValueError("rolling backtest produced no folds")
    return BacktestResult(
        model_id=model.model_id,
        horizon=horizon,
        folds=tuple(folds),
        overall=score_points(all_points),
    )
