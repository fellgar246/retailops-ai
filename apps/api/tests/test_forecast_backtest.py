from datetime import date

import pytest

from retailops_api.forecasting.backtest import rolling_origins, walk_forward
from retailops_api.forecasting.models import ForecastPoint, NaiveForecaster
from tests.forecast_support import series_frame, week


class _LeakyMean:
    """A model that averages every target in the frame, including the future."""

    model_id = "leaky"

    def predict(
        self,
        history: object,
        *,
        cutoff: date,
        horizon: int,
    ) -> tuple[ForecastPoint, ...]:
        from retailops_api.forecasting.frame import ForecastFrame
        from retailops_api.forecasting.weeks import add_weeks, iso_week_start

        assert isinstance(history, ForecastFrame)
        mean = sum(row.target for row in history.rows) / len(history.rows)
        origin = iso_week_start(cutoff)
        return tuple(
            ForecastPoint("ST-001", "BEV-SOFT", add_weeks(origin, step), step, mean)
            for step in range(1, horizon + 1)
        )


def test_rolling_origins_leave_history_and_a_scorable_horizon() -> None:
    frame = series_frame(list(range(20)))
    origins = rolling_origins(frame, horizon=4, min_train_periods=8, step_weeks=1)

    assert origins[0] == week(7)
    assert origins[-1] == week(15)
    assert origins == tuple(week(index) for index in range(7, 16))


def test_walk_forward_attaches_actuals_and_never_scores_the_cutoff_week() -> None:
    values = [10.0] * 12 + [20.0] * 8
    frame = series_frame(values)
    result = walk_forward(
        frame,
        NaiveForecaster(),
        horizon=4,
        min_train_periods=8,
        step_weeks=4,
    )

    assert result.model_id == "naive"
    assert result.horizon == 4
    assert len(result.folds) == 3
    first = result.folds[0]
    assert first.cutoff == week(7)
    assert [point.period_start for point in first.predictions] == [
        week(8),
        week(9),
        week(10),
        week(11),
    ]
    assert all(point.actual == 10.0 for point in first.predictions)
    assert all(point.predicted == 10.0 for point in first.predictions)
    assert first.metrics.mae == 0


def test_walk_forward_overall_metrics_concatenate_every_fold() -> None:
    frame = series_frame([float(index) for index in range(16)])
    result = walk_forward(
        frame,
        NaiveForecaster(),
        horizon=4,
        min_train_periods=8,
        step_weeks=4,
    )

    # Origins at week 7 and week 11. Naive at week 7 predicts 7 for weeks 8-11
    # (actuals 8-11). Naive at week 11 predicts 11 for weeks 12-15 (actuals 12-15).
    assert len(result.folds) == 2
    # predicted 7 vs 8,9,10,11 and 11 vs 12,13,14,15: errors -1,-2,-3,-4 twice
    assert result.overall.mae == 2.5
    assert result.overall.bias == -2.5


def test_a_leaky_model_would_see_future_targets_the_baselines_do_not() -> None:
    frame = series_frame([10.0] * 12 + [999.0] * 4)
    cutoff_origin = week(11)
    honest = NaiveForecaster().predict(frame, cutoff=cutoff_origin, horizon=4)
    leaky = _LeakyMean().predict(frame, cutoff=cutoff_origin, horizon=4)

    assert all(point.predicted == 10.0 for point in honest)
    assert leaky[0].predicted > 10.0


def test_walk_forward_refuses_a_frame_that_cannot_cover_the_horizon() -> None:
    frame = series_frame(list(range(10)))
    with pytest.raises(ValueError, match="rolling backtest"):
        walk_forward(frame, NaiveForecaster(), horizon=4, min_train_periods=8)
