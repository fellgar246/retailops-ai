"""Sales → ingest → features → model → registry → forecast → API."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.forecasting.artifact import load_artifact
from retailops_api.forecasting.booster import HistGBMTrainerConfig
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.persist import persist_run
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND
from retailops_api.forecasting.registry import ApprovalStatus, LocalModelRegistry
from retailops_api.forecasting.sources import load_forecast_dataset
from retailops_api.forecasting.train import TrainSettings, run_training
from retailops_api.ingestion.catalog import ingest_catalog
from retailops_api.ingestion.sales import ingest_sales


def test_demand_pipeline_reaches_the_forecast_api(
    api_client: TestClient, session: Session, tmp_path: Path
) -> None:
    dataset, summary, frame = load_forecast_dataset(
        input_path=None,
        preset="tiny",
        start_date=date(2025, 1, 6),
        end_date=date(2025, 6, 29),
    )
    ingest_catalog(session, dataset.catalog)
    sales = ingest_sales(session, dataset.sales)
    assert sales.rows_accepted == sales.rows_read
    session.flush()

    registry = LocalModelRegistry(tmp_path / "registry")
    trained = run_training(
        dataset,
        frame,
        summary=summary,
        settings=TrainSettings(
            feature=FeatureConfig(min_history_weeks=8),
            trainer=HistGBMTrainerConfig(n_estimators=20, max_depth=3, min_samples_leaf=5),
            validation_periods=4,
            test_periods=4,
            model_name="category-forecast",
        ),
        output_dir=tmp_path / "out",
        registry=registry,
    )
    assert trained.version is not None
    assert trained.version.status is ApprovalStatus.candidate
    loaded = load_artifact(trained.artifact_dir)
    cutoff = trained.holdout.train_end
    points = loaded.predict(frame, cutoff=cutoff, horizon=4)
    assert points

    run = persist_run(
        session,
        model_id=trained.model.model_id,
        generated_at=trained.version.registered_at,
        cutoff=cutoff,
        horizon=4,
        problem_id=WEEKLY_CATEGORY_STORE_DEMAND.id,
        predictions=points,
        run_metadata={
            "model_version": trained.version.version,
            "overall_metrics": trained.decision.candidate.metrics.to_dict(),
        },
    )
    session.commit()

    listed = api_client.get("/forecasts")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    item = next(row for row in listed.json()["items"] if row["id"] == run.id)
    assert item["model_id"]
    assert "metrics" in item
    assert item["prediction_count"] == len(points)

    detail = api_client.get(f"/forecasts/{run.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["predictions"]
    assert body["horizon"] == 4
    assert set(body["predictions"][0]) >= {
        "store_code",
        "category_code",
        "period_start",
        "step",
        "predicted",
        "actual",
    }
