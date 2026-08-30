from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_health_returns_expected_body(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_database_health_reports_a_known_status(client: TestClient) -> None:
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
