"""Weekly category-demand baselines, features, histogram-GBM training and a local registry."""

from retailops_api.forecasting.backtest import BacktestFold, BacktestResult, walk_forward
from retailops_api.forecasting.booster import HistGBMForecaster, HistGBMTrainerConfig
from retailops_api.forecasting.feature_contract import FEATURE_CONTRACT, FeatureConfig, FeatureSpec
from retailops_api.forecasting.feature_panel import FeatureFrame, FeatureRow, build_supervised_frame
from retailops_api.forecasting.frame import ForecastFrame, ForecastRow, build_forecast_frame
from retailops_api.forecasting.metrics import ForecastMetrics, score_pairs, score_points
from retailops_api.forecasting.models import (
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
    default_baselines,
)
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND, ForecastProblem
from retailops_api.forecasting.registry import (
    ApprovalStatus,
    LocalModelRegistry,
    ModelRegistry,
    ModelVersion,
)
from retailops_api.forecasting.split import TemporalSplit, split_holdout, split_temporal

__all__ = [
    "FEATURE_CONTRACT",
    "WEEKLY_CATEGORY_STORE_DEMAND",
    "ApprovalStatus",
    "BacktestFold",
    "BacktestResult",
    "FeatureConfig",
    "FeatureFrame",
    "FeatureRow",
    "FeatureSpec",
    "ForecastFrame",
    "ForecastMetrics",
    "ForecastProblem",
    "ForecastRow",
    "HistGBMForecaster",
    "HistGBMTrainerConfig",
    "LocalModelRegistry",
    "ModelRegistry",
    "ModelVersion",
    "MovingAverageForecaster",
    "NaiveForecaster",
    "SeasonalNaiveForecaster",
    "TemporalSplit",
    "build_forecast_frame",
    "build_supervised_frame",
    "default_baselines",
    "score_pairs",
    "score_points",
    "split_holdout",
    "split_temporal",
    "walk_forward",
]
