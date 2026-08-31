"""HTTP forecast-run list and detail."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.forecasting.models import ForecastPoint
from retailops_api.forecasting.persist import persist_run


def test_list_and_detail_forecast_runs(api_client: TestClient, session: Session) -> None:
    run = persist_run(
        session,
        model_id="naive",
        generated_at=datetime(2026, 8, 30, 13, 32, tzinfo=UTC),
        cutoff=date(2025, 6, 2),
        horizon=2,
        problem_id="weekly_category_store_demand",
        predictions=(
            ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 9), 1, 10.0, actual=9.0),
            ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 16), 2, 11.0, actual=None),
        ),
        run_metadata={"overall_metrics": {"mae": 1.0, "rmse": 1.0, "wape": 0.11, "bias": 1.0}},
    )
    session.commit()

    listed = api_client.get("/forecasts")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    item = listed.json()["items"][0]
    assert item["id"] == run.id
    assert item["model_id"] == "naive"
    assert item["metrics"]["wape"] == 0.11
    assert item["status"] == "evaluated"

    detail = api_client.get(f"/forecasts/{run.id}")
    assert detail.status_code == 200
    assert len(detail.json()["predictions"]) == 2
    assert detail.json()["horizon"] == 2


def test_unknown_forecast_is_not_found(api_client: TestClient) -> None:
    assert api_client.get("/forecasts/9999").status_code == 404
