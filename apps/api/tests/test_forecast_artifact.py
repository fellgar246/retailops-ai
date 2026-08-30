from datetime import UTC, date, datetime
from pathlib import Path

from retailops_api.forecasting.artifact import (
    ARTIFACT_FILES,
    ArtifactMetadata,
    DataFingerprint,
    load_artifact,
    write_artifact,
)
from retailops_api.forecasting.booster import HistGBMTrainerConfig, train_hist_gbm
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.feature_panel import build_supervised_frame
from retailops_api.forecasting.features import build_observables
from retailops_api.forecasting.frame import build_forecast_frame
from retailops_api.forecasting.metrics import ForecastMetrics
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset


def test_an_artifact_reloads_without_the_original_python_object(tmp_path: Path) -> None:
    dataset = generate_dataset(
        GeneratorConfig.from_preset(
            "tiny",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 29),
        )
    )
    frame = build_forecast_frame(dataset)
    train_end = frame.periods()[-(4 + 4 + 1)]
    supervised = build_supervised_frame(
        frame,
        config=FeatureConfig(min_history_weeks=8),
        train_end=train_end,
        horizon=4,
        observables=build_observables(dataset, frame.periods()),
        catalog=dataset.catalog,
        dataset_checksum="abc",
        source="synthetic:tiny",
    )
    model = train_hist_gbm(
        supervised,
        trainer=HistGBMTrainerConfig(n_estimators=15, max_depth=3, min_samples_leaf=5),
    )
    directory = tmp_path / "v001"
    write_artifact(
        directory,
        model,
        metadata=ArtifactMetadata(
            model_id="hist_gbm",
            model_name="category-forecast",
            problem_id="weekly_category_store_demand",
            created_at=datetime.now(UTC),
            feature_names=model.feature_names,
            horizon=4,
        ),
        metrics=ForecastMetrics(1.0, 1.0, 0.2, 0.0),
        fingerprint=DataFingerprint(
            dataset_checksum="abc",
            source="synthetic:tiny",
            train_end=train_end.isoformat(),
            validation_end=None,
            test_end=None,
            train_rows=len(supervised.rows),
            feature_names=model.feature_names,
        ),
    )

    for name in ARTIFACT_FILES:
        assert (directory / name).is_file()

    reloaded = load_artifact(directory)
    assert reloaded.feature_names == model.feature_names
    assert reloaded.trainer_config == model.trainer_config
    assert reloaded.predict(frame, cutoff=train_end, horizon=4) == model.predict(
        frame, cutoff=train_end, horizon=4
    )
