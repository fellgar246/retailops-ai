import math

import pytest

from retailops_api.forecasting.metrics import score_pairs, score_points
from retailops_api.forecasting.models import ForecastPoint
from tests.forecast_support import MONDAY


def test_perfect_forecast_is_zero_everywhere() -> None:
    metrics = score_pairs([(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)])

    assert metrics.mae == 0
    assert metrics.rmse == 0
    assert metrics.wape == 0
    assert metrics.bias == 0


def test_known_errors_match_the_closed_form() -> None:
    metrics = score_pairs([(1.0, 2.0), (3.0, 2.0)])

    assert metrics.mae == 1.0
    assert metrics.rmse == 1.0
    assert metrics.wape == 0.5
    assert metrics.bias == 0.0


def test_rmse_penalises_large_misses() -> None:
    metrics = score_pairs([(0.0, 3.0), (0.0, 4.0)])

    assert metrics.mae == 3.5
    assert metrics.rmse == math.sqrt(12.5)
    assert metrics.bias == 3.5


def test_all_zero_actuals_and_predictions_have_zero_wape() -> None:
    metrics = score_pairs([(0.0, 0.0), (0.0, 0.0)])

    assert metrics.wape == 0.0
    assert metrics.mae == 0.0
    assert metrics.bias == 0.0


def test_all_zero_actuals_with_a_false_alarm_have_unit_wape() -> None:
    metrics = score_pairs([(0.0, 1.0), (0.0, 1.0)])

    assert metrics.wape == 1.0
    assert metrics.mae == 1.0
    assert metrics.bias == 1.0


def test_mixed_zero_demand_uses_the_non_zero_actuals_as_the_weight() -> None:
    metrics = score_pairs([(0.0, 0.0), (2.0, 0.0)])

    assert metrics.wape == 1.0
    assert metrics.bias == -1.0


def test_points_without_actuals_are_ignored() -> None:
    metrics = score_points(
        [
            ForecastPoint("ST-001", "BEV-SOFT", MONDAY, 1, 2.0, actual=1.0),
            ForecastPoint("ST-001", "BEV-SOFT", MONDAY, 2, 99.0, actual=None),
        ]
    )

    assert metrics.mae == 1.0


def test_an_empty_sample_is_an_error() -> None:
    with pytest.raises(ValueError, match="no predicted/actual"):
        score_pairs([])
