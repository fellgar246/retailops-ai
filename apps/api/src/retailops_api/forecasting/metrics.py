"""Forecast accuracy metrics and their zero-demand behaviour.

MAE
    Mean absolute error: ``mean(|predicted - actual|)``.

RMSE
    Root mean squared error: ``sqrt(mean((predicted - actual) ** 2))``.

WAPE
    Weighted absolute percentage error:
    ``sum(|predicted - actual|) / sum(|actual|)``.
    When every actual is zero, the denominator is zero. In that case WAPE is
    ``0`` if every prediction is also zero (a perfect zero-demand forecast)
    and ``1`` if any prediction is non-zero (demand was invented where none
    occurred). This keeps the metric defined and bounded on all-zero weeks
    instead of returning infinity or NaN.

Forecast bias
    Mean signed error: ``mean(predicted - actual)``. Positive values mean the
    model over-forecasts. This remains defined when every actual is zero
    (it then equals the mean prediction).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from retailops_api.forecasting.models import ForecastPoint

METRIC_NAMES = ("mae", "rmse", "wape", "bias")

METRIC_DEFINITIONS_MARKDOWN = """\
### MAE

Mean absolute error: the average of `|predicted - actual|`.

### RMSE

Root mean squared error: the square root of the average squared error. Larger
misses weigh more than they do in MAE.

### WAPE

Weighted absolute percentage error: `sum(|predicted - actual|) / sum(|actual|)`.

When every actual is zero the denominator is zero. WAPE is then `0` if every
prediction is also zero, and `1` if any prediction is non-zero. That keeps the
metric defined on all-zero weeks instead of returning infinity.

### Forecast bias

Mean signed error: `mean(predicted - actual)`. Positive bias means the model
over-forecasts. The value is defined when every actual is zero - it equals the
mean prediction.
"""


@dataclass(frozen=True)
class ForecastMetrics:
    mae: float
    rmse: float
    wape: float
    bias: float

    def to_dict(self) -> dict[str, float]:
        return {
            "mae": self.mae,
            "rmse": self.rmse,
            "wape": self.wape,
            "bias": self.bias,
        }


def score_pairs(pairs: Sequence[tuple[float, float]]) -> ForecastMetrics:
    """Score ``(actual, predicted)`` pairs. Raises when the sample is empty."""
    if not pairs:
        raise ValueError("cannot compute metrics: no predicted/actual pairs")

    errors = [predicted - actual for actual, predicted in pairs]
    abs_errors = [abs(error) for error in errors]
    n = len(pairs)
    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(error * error for error in errors) / n)
    abs_actual = sum(abs(actual) for actual, _predicted in pairs)
    abs_predicted = sum(abs(predicted) for _actual, predicted in pairs)
    if abs_actual > 0:
        wape = sum(abs_errors) / abs_actual
    elif abs_predicted == 0:
        wape = 0.0
    else:
        wape = 1.0
    bias = sum(errors) / n
    return ForecastMetrics(mae=mae, rmse=rmse, wape=wape, bias=bias)


def score_points(points: Sequence[ForecastPoint]) -> ForecastMetrics:
    """Score points that carry an actual. Points without an actual are ignored."""
    pairs = [(point.actual, point.predicted) for point in points if point.actual is not None]
    return score_pairs(pairs)


def round_metrics(metrics: ForecastMetrics, digits: int = 6) -> dict[str, float]:
    return {name: round(getattr(metrics, name), digits) for name in METRIC_NAMES}
