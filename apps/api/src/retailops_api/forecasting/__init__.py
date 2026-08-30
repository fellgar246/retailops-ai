"""Weekly category-demand baselines, temporal splits and walk-forward evaluation."""

from retailops_api.forecasting.backtest import BacktestFold, BacktestResult, walk_forward
from retailops_api.forecasting.frame import ForecastFrame, ForecastRow, build_forecast_frame
from retailops_api.forecasting.metrics import ForecastMetrics, score_pairs, score_points
from retailops_api.forecasting.models import (
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
    default_baselines,
)
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND, ForecastProblem
from retailops_api.forecasting.split import TemporalSplit, split_holdout, split_temporal

__all__ = [
    "WEEKLY_CATEGORY_STORE_DEMAND",
    "BacktestFold",
    "BacktestResult",
    "ForecastFrame",
    "ForecastMetrics",
    "ForecastProblem",
    "ForecastRow",
    "MovingAverageForecaster",
    "NaiveForecaster",
    "SeasonalNaiveForecaster",
    "TemporalSplit",
    "build_forecast_frame",
    "default_baselines",
    "score_pairs",
    "score_points",
    "split_holdout",
    "split_temporal",
    "walk_forward",
]
