"""Baseline forecasters that share one prediction interface.

Every model implements ``predict(history, cutoff, horizon)``. Implementations
must ignore every row with ``period_start > cutoff``. The caller may pass the
full frame, including future targets; reading those targets is leakage.

Horizon steps are the next ``horizon`` ISO weeks after the week that contains
``cutoff``. The same predicted level is repeated across the horizon for these
baselines (they have no intra-horizon dynamics).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol

from retailops_api.forecasting.frame import ForecastEntity, ForecastFrame
from retailops_api.forecasting.problem import DEFAULT_MOVING_AVERAGE_WINDOW, DEFAULT_SEASONAL_LAG
from retailops_api.forecasting.weeks import add_weeks, iso_week_start


@dataclass(frozen=True)
class ForecastPoint:
    """One predicted week, optionally paired with the observed actual."""

    store_code: str
    category_code: str
    period_start: date
    step: int
    predicted: float
    actual: float | None = None

    @property
    def entity(self) -> ForecastEntity:
        return ForecastEntity(self.store_code, self.category_code)

    def with_actual(self, actual: float | None) -> ForecastPoint:
        return replace(self, actual=actual)


class Forecaster(Protocol):
    """The interface future models must implement."""

    @property
    def model_id(self) -> str: ...

    def predict(
        self,
        history: ForecastFrame,
        *,
        cutoff: date,
        horizon: int,
    ) -> tuple[ForecastPoint, ...]:
        """Forecast ``horizon`` weeks after the week that contains ``cutoff``.

        Rows after ``cutoff`` in ``history`` must not be read.
        """
        ...


def _require_horizon(horizon: int) -> None:
    if horizon < 1:
        raise ValueError("horizon must be at least 1")


def _horizon_periods(cutoff: date, horizon: int) -> tuple[date, ...]:
    origin = iso_week_start(cutoff)
    return tuple(add_weeks(origin, step) for step in range(1, horizon + 1))


def _history_index(history: ForecastFrame, cutoff: date) -> dict[tuple[str, str, date], float]:
    return {
        (row.store_code, row.category_code, row.period_start): row.target
        for row in history.rows
        if row.period_start <= cutoff
    }


def _entities_seen_by(index: dict[tuple[str, str, date], float]) -> tuple[ForecastEntity, ...]:
    seen: dict[ForecastEntity, None] = {}
    for store_code, category_code, _period in index:
        seen.setdefault(ForecastEntity(store_code, category_code), None)
    return tuple(seen)


def _last_value(index: dict[tuple[str, str, date], float], entity: ForecastEntity) -> float:
    latest: date | None = None
    for store_code, category_code, week in index:
        if (
            store_code == entity.store_code
            and category_code == entity.category_code
            and (latest is None or week > latest)
        ):
            latest = week
    if latest is None:
        return 0.0
    return index[(entity.store_code, entity.category_code, latest)]


def _points_for(
    entity: ForecastEntity,
    periods: tuple[date, ...],
    predicted: float,
) -> list[ForecastPoint]:
    return [
        ForecastPoint(
            store_code=entity.store_code,
            category_code=entity.category_code,
            period_start=period,
            step=step,
            predicted=predicted,
        )
        for step, period in enumerate(periods, start=1)
    ]


@dataclass(frozen=True)
class NaiveForecaster:
    """Previous-period forecast: each horizon step repeats the last observed week.

    An entity with no history on or before the cutoff predicts ``0``.
    """

    model_id: str = "naive"

    def predict(
        self,
        history: ForecastFrame,
        *,
        cutoff: date,
        horizon: int,
    ) -> tuple[ForecastPoint, ...]:
        _require_horizon(horizon)
        index = _history_index(history, cutoff)
        periods = _horizon_periods(cutoff, horizon)
        points: list[ForecastPoint] = []
        for entity in _entities_seen_by(index):
            points.extend(_points_for(entity, periods, _last_value(index, entity)))
        return tuple(points)


@dataclass(frozen=True)
class SeasonalNaiveForecaster:
    """Seasonal lag forecast with a documented fallback.

    For horizon step ``h``, the prediction is the observed target at
    ``origin + h - seasonal_lag`` weeks, provided that week exists in history
    on or before ``cutoff``.

    Fallback when that lookback is missing (the series is shorter than the
    lag, or the week was never in the frame): use the last observed week, the
    same value the naive baseline would use. If the entity has no history at
    all, predict ``0``.

    The default lag is 52 (the same ISO week a year earlier). On a one-year
    development history that lookback is almost never present, so the fallback
    dominates until a second year of sales exists.
    """

    seasonal_lag: int = DEFAULT_SEASONAL_LAG
    model_id: str = "seasonal_naive"

    def __post_init__(self) -> None:
        if self.seasonal_lag < 1:
            raise ValueError("seasonal_lag must be at least 1")

    def predict(
        self,
        history: ForecastFrame,
        *,
        cutoff: date,
        horizon: int,
    ) -> tuple[ForecastPoint, ...]:
        _require_horizon(horizon)
        index = _history_index(history, cutoff)
        periods = _horizon_periods(cutoff, horizon)
        points: list[ForecastPoint] = []
        for entity in _entities_seen_by(index):
            fallback = _last_value(index, entity)
            for step, period in enumerate(periods, start=1):
                lookback = add_weeks(period, -self.seasonal_lag)
                key = (entity.store_code, entity.category_code, lookback)
                predicted = index[key] if key in index and lookback <= cutoff else fallback
                points.append(
                    ForecastPoint(
                        store_code=entity.store_code,
                        category_code=entity.category_code,
                        period_start=period,
                        step=step,
                        predicted=predicted,
                    )
                )
        return tuple(points)


@dataclass(frozen=True)
class MovingAverageForecaster:
    """Mean of the last ``window`` weeks on or before the cutoff.

    The mean is computed once from history and repeated for every horizon
    step. Weeks after the cutoff are never read.

    If fewer than ``window`` weeks exist for an entity, the mean of the weeks
    that do exist is used. An entity with no history predicts ``0``.
    """

    window: int = DEFAULT_MOVING_AVERAGE_WINDOW
    model_id: str = "moving_average"

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError("window must be at least 1")

    def predict(
        self,
        history: ForecastFrame,
        *,
        cutoff: date,
        horizon: int,
    ) -> tuple[ForecastPoint, ...]:
        _require_horizon(horizon)
        index = _history_index(history, cutoff)
        periods = _horizon_periods(cutoff, horizon)
        points: list[ForecastPoint] = []
        for entity in _entities_seen_by(index):
            observed = sorted(
                week
                for store_code, category_code, week in index
                if store_code == entity.store_code and category_code == entity.category_code
            )
            trailing = observed[-self.window :]
            total = sum(index[(entity.store_code, entity.category_code, week)] for week in trailing)
            predicted = total / len(trailing)
            points.extend(_points_for(entity, periods, predicted))
        return tuple(points)


def default_baselines(
    *,
    seasonal_lag: int = DEFAULT_SEASONAL_LAG,
    window: int = DEFAULT_MOVING_AVERAGE_WINDOW,
) -> tuple[Forecaster, ...]:
    return (
        NaiveForecaster(),
        SeasonalNaiveForecaster(seasonal_lag=seasonal_lag),
        MovingAverageForecaster(window=window),
    )
