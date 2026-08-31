from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_create_app_returns_fastapi_instance(app: FastAPI) -> None:
    assert isinstance(app, FastAPI)
    assert app.title


def test_openapi_schema_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
    assert "/reviews/metrics" in response.json()["paths"]
    assert "/ops/overview" in response.json()["paths"]
    assert "/forecasts" in response.json()["paths"]
    assert "/documents" in response.json()["paths"]
    assert "/reconciliations" in response.json()["paths"]
    assert "/audit" in response.json()["paths"]
