from datetime import date
from pathlib import Path

from retailops_api.dataset.contract import Dataset
from retailops_api.forecasting.artifact import load_artifact
from retailops_api.forecasting.benchmark import DatasetSummary
from retailops_api.forecasting.booster import HistGBMTrainerConfig
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.frame import ForecastFrame
from retailops_api.forecasting.registry import ApprovalStatus, LocalModelRegistry
from retailops_api.forecasting.sources import load_forecast_dataset
from retailops_api.forecasting.train import TrainSettings, run_training
from retailops_api.forecasting.train_cli import main


def _tiny_inputs() -> tuple[Dataset, DatasetSummary, ForecastFrame]:
    return load_forecast_dataset(
        input_path=None,
        preset="tiny",
        start_date=date(2025, 1, 6),
        end_date=date(2025, 6, 29),
    )


def _settings() -> TrainSettings:
    return TrainSettings(
        feature=FeatureConfig(min_history_weeks=8),
        trainer=HistGBMTrainerConfig(n_estimators=20, max_depth=3, min_samples_leaf=5),
        validation_periods=4,
        test_periods=4,
        model_name="category-forecast",
    )


def test_training_registers_a_reloadable_candidate(tmp_path: Path) -> None:
    dataset, summary, frame = _tiny_inputs()
    registry = LocalModelRegistry(tmp_path / "registry")
    result = run_training(
        dataset,
        frame,
        summary=summary,
        settings=_settings(),
        output_dir=tmp_path / "out",
        registry=registry,
    )

    assert result.version is not None
    assert result.version.status is ApprovalStatus.candidate
    assert (tmp_path / "out" / "train_metrics.json").is_file()
    assert (tmp_path / "out" / "train_report.md").is_file()
    assert "Promotion policy" in (tmp_path / "out" / "train_report.md").read_text(encoding="utf-8")
    assert {score.model_id for score in result.decision.comparisons} >= {
        "naive",
        "seasonal_naive",
        "moving_average",
    }

    loaded = load_artifact(result.artifact_dir)
    original = result.model.predict(frame, cutoff=result.holdout.train_end, horizon=4)
    assert loaded.predict(frame, cutoff=result.holdout.train_end, horizon=4) == original


def test_approved_champion_is_the_model_used_for_inference(tmp_path: Path) -> None:
    dataset, summary, frame = _tiny_inputs()
    registry = LocalModelRegistry(tmp_path / "registry")
    result = run_training(
        dataset,
        frame,
        summary=summary,
        settings=_settings(),
        output_dir=tmp_path / "out",
        registry=registry,
    )
    assert result.version is not None
    registry.update_approval("category-forecast", result.version.version, ApprovalStatus.champion)
    champion = registry.get_champion("category-forecast")
    assert champion is not None

    model = load_artifact(champion.artifact_path)
    points = model.predict(frame, cutoff=result.holdout.train_end, horizon=4)
    baselines = {score.model_id: score.metrics for score in result.decision.comparisons}

    assert points
    assert "naive" in baselines
    assert result.decision.candidate.metrics.wape >= 0


def test_cli_writes_metrics_and_registers(tmp_path: Path) -> None:
    code = main(
        [
            "--preset",
            "tiny",
            "--start-date",
            "2025-01-06",
            "--end-date",
            "2025-06-29",
            "--n-estimators",
            "15",
            "--max-depth",
            "3",
            "--min-samples-leaf",
            "5",
            "--output",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "registry"),
        ]
    )

    assert code == 0
    assert (tmp_path / "out" / "train_metrics.json").is_file()
    assert (tmp_path / "out" / "forecast_frame.csv").is_file()
    assert (tmp_path / "registry" / "category-forecast" / "v001" / "model.joblib").is_file()
    assert (tmp_path / "registry" / "category-forecast" / "index.json").is_file()
