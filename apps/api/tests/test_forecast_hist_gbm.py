from datetime import date

from retailops_api.forecasting.booster import (
    HistGBMForecaster,
    HistGBMTrainerConfig,
    train_hist_gbm,
)
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.feature_panel import build_supervised_frame
from retailops_api.forecasting.features import build_observables
from retailops_api.forecasting.frame import ForecastFrame, build_forecast_frame
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset


def _trained() -> tuple[ForecastFrame, date, HistGBMForecaster]:
    dataset = generate_dataset(
        GeneratorConfig.from_preset(
            "tiny",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 29),
        )
    )
    frame = build_forecast_frame(dataset)
    train_end = frame.periods()[-(4 + 4 + 1)]
    config = FeatureConfig(min_history_weeks=8)
    supervised = build_supervised_frame(
        frame,
        config=config,
        train_end=train_end,
        horizon=4,
        observables=build_observables(dataset, frame.periods()),
        catalog=dataset.catalog,
    )
    trainer = HistGBMTrainerConfig(n_estimators=20, max_depth=3, min_samples_leaf=5)
    model = train_hist_gbm(supervised, trainer=trainer)
    return frame, train_end, model


def test_the_same_config_and_data_reproduce_the_booster() -> None:
    frame, cutoff, first = _trained()
    second = _trained()[2]

    assert first.predict(frame, cutoff=cutoff, horizon=4) == second.predict(
        frame, cutoff=cutoff, horizon=4
    )


def test_predictions_ignore_targets_after_the_cutoff() -> None:
    frame, cutoff, model = _trained()
    full = model.predict(frame, cutoff=cutoff, horizon=4)
    truncated = model.predict(frame.up_to(cutoff), cutoff=cutoff, horizon=4)

    assert full == truncated
    assert all(point.predicted >= 0 for point in full)
    assert [point.step for point in full[:4]] == [1, 2, 3, 4]


def test_trainer_config_is_explicit_and_round_trips() -> None:
    config = HistGBMTrainerConfig(n_estimators=40, learning_rate=0.1, random_state=7)
    restored = HistGBMTrainerConfig.from_dict(config.to_dict())

    assert restored == config
    assert config.n_estimators == 40
    assert config.random_state == 7
