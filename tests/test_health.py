from fastapi.testclient import TestClient

from hajiriflow.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "hajiriflow-web"
    assert payload["environment"] == "test"


def test_readiness_endpoint() -> None:
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
