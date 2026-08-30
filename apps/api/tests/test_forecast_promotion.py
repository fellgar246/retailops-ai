from retailops_api.forecasting.metrics import ForecastMetrics
from retailops_api.forecasting.promotion import (
    ModelScore,
    evaluate_promotion,
)


def _score(model_id: str, *, mae: float, wape: float) -> ModelScore:
    return ModelScore(
        model_id=model_id,
        metrics=ForecastMetrics(mae=mae, rmse=mae, wape=wape, bias=0.0),
        predictions=(),
    )


def test_a_wape_win_alone_is_not_enough() -> None:
    candidate = _score("hist_gbm", mae=5.0, wape=0.10)
    naive = _score("naive", mae=2.0, wape=0.20)
    decision = evaluate_promotion(candidate, (naive,))

    assert decision.promote is False
    assert any("mae" in reason for reason in decision.reasons)


def test_both_gates_must_beat_every_baseline() -> None:
    candidate = _score("hist_gbm", mae=1.0, wape=0.10)
    naive = _score("naive", mae=2.0, wape=0.20)
    seasonal = _score("seasonal_naive", mae=2.5, wape=0.22)
    moving = _score("moving_average", mae=1.8, wape=0.18)
    decision = evaluate_promotion(candidate, (naive, seasonal, moving))

    assert decision.promote is True
    assert any("both gates passed" in reason for reason in decision.reasons)


def test_equal_wape_does_not_promote() -> None:
    candidate = _score("hist_gbm", mae=1.0, wape=0.20)
    naive = _score("naive", mae=2.0, wape=0.20)
    decision = evaluate_promotion(candidate, (naive,))

    assert decision.promote is False


def test_champion_mae_regression_blocks_promotion() -> None:
    candidate = _score("hist_gbm", mae=3.0, wape=0.10)
    naive = _score("naive", mae=4.0, wape=0.30)
    champion = _score("champion_v001", mae=1.5, wape=0.15)
    decision = evaluate_promotion(
        candidate,
        (naive, champion),
        champion_id="champion_v001",
    )

    assert decision.promote is False
    assert any("champion" in reason for reason in decision.reasons)


def test_policy_documents_that_one_metric_is_not_enough() -> None:
    candidate = _score("hist_gbm", mae=1.0, wape=0.10)
    naive = _score("naive", mae=2.0, wape=0.20)
    decision = evaluate_promotion(candidate, (naive,))

    assert "single-metric" in decision.policy.to_dict()["rule"]
