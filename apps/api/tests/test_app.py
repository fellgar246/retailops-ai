from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_create_app_returns_fastapi_instance(app: FastAPI) -> None:
    assert isinstance(app, FastAPI)
    assert app.title


def test_openapi_schema_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
