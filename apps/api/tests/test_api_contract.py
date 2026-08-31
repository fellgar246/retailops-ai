"""Response shapes the operations console reads must stay stable."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.demo_support import load_demo

PAGE_KEYS = {"items", "total", "limit", "offset"}
FORECAST_SUMMARY_KEYS = {
    "id",
    "model_id",
    "model_version",
    "generated_at",
    "cutoff",
    "horizon",
    "problem_id",
    "status",
    "prediction_count",
    "metrics",
}
DOCUMENT_SUMMARY_KEYS = {
    "id",
    "supplier_id",
    "supplier_code",
    "filename",
    "status",
    "finding_count",
    "severity_summary",
    "created_at",
}
REVIEW_KEYS = {
    "id",
    "subject_type",
    "priority",
    "risk",
    "status",
    "financial_impact",
    "created_at",
}
OVERVIEW_KEYS = {
    "generated_at",
    "environment",
    "forecasts",
    "documents",
    "reconciliation",
    "reviews",
}


def test_frontend_endpoints_keep_their_response_contract(
    api_client: TestClient, session: Session, tmp_path: Path
) -> None:
    report = load_demo(session, tmp_path)
    session.commit()

    overview = api_client.get("/ops/overview")
    assert overview.status_code == 200
    assert set(overview.json()) >= OVERVIEW_KEYS
    assert {"run_count", "latest"} <= set(overview.json()["forecasts"])
    assert {"total", "awaiting_review", "parse_failed"} <= set(overview.json()["documents"])
    assert {"run_count", "open_exceptions", "total_financial_impact"} <= set(
        overview.json()["reconciliation"]
    )
    assert {"open_cases", "acceptance_rate"} <= set(overview.json()["reviews"])

    forecasts = api_client.get("/forecasts")
    assert forecasts.status_code == 200
    assert set(forecasts.json()) >= PAGE_KEYS
    assert forecasts.json()["items"]
    assert set(forecasts.json()["items"][0]) >= FORECAST_SUMMARY_KEYS

    forecast = api_client.get(f"/forecasts/{report.forecast_run_id}")
    assert forecast.status_code == 200
    assert "predictions" in forecast.json()
    assert forecast.json()["predictions"][0]["store_code"]

    documents = api_client.get("/documents")
    assert documents.status_code == 200
    assert set(documents.json()) >= PAGE_KEYS
    assert set(documents.json()["items"][0]) >= DOCUMENT_SUMMARY_KEYS

    document = api_client.get(f"/documents/{report.document_ids[0]}")
    assert document.status_code == 200
    body = document.json()
    assert {"findings", "rows", "rows_available", "review_cases"} <= set(body)
    if body["findings"]:
        assert body["findings"][0]["provenance"] == "rule"

    reconciliations = api_client.get("/reconciliations")
    assert reconciliations.status_code == 200
    assert set(reconciliations.json()) >= PAGE_KEYS
    run = api_client.get(f"/reconciliations/{report.reconciliation_run_ids[0]}")
    assert run.status_code == 200
    assert {"exceptions", "tolerances", "input_fingerprint"} <= set(run.json())
    if run.json()["exceptions"]:
        assert run.json()["exceptions"][0]["provenance"] == "rule"

    exceptions = api_client.get("/exceptions")
    assert exceptions.status_code == 200
    assert set(exceptions.json()) >= PAGE_KEYS

    reviews = api_client.get("/reviews")
    assert reviews.status_code == 200
    assert set(reviews.json()) >= PAGE_KEYS
    assert set(reviews.json()["items"][0]) >= REVIEW_KEYS

    review = api_client.get(f"/reviews/{report.review_case_ids[0]}")
    assert review.status_code == 200
    assert {"subject", "snapshot", "decision"} <= set(review.json())

    metrics = api_client.get("/reviews/metrics")
    assert metrics.status_code == 200
    assert {"open_cases", "acceptance_rate", "average_review_duration_seconds"} <= set(
        metrics.json()
    )

    feedback = api_client.get("/reviews/feedback")
    assert feedback.status_code == 200
    assert {"items", "count"} <= set(feedback.json())

    audit = api_client.get("/audit")
    assert audit.status_code == 200
    assert set(audit.json()) >= PAGE_KEYS

    search = api_client.get("/search", params={"q": "BEV"})
    assert search.status_code == 200
    assert {"query", "documents", "reviews", "exceptions", "forecasts"} <= set(search.json())


def test_openapi_lists_every_console_path(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/health",
        "/health/db",
        "/ops/overview",
        "/forecasts",
        "/forecasts/{run_id}",
        "/documents",
        "/documents/{document_id}",
        "/reconciliations",
        "/reconciliations/{run_id}",
        "/exceptions",
        "/reviews",
        "/reviews/metrics",
        "/reviews/feedback",
        "/audit",
        "/search",
    ):
        assert path in paths
