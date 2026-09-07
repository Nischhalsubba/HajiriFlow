import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hajiriflow.api.middleware import RequestContextMiddleware


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/api/v1/items/{item_id}")
    def read_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @app.post("/api/v1/payroll-preview")
    def payroll_preview(payload: dict[str, str]) -> dict[str, str]:
        return {"status": "accepted", "employee": payload.get("employee", "")}

    return TestClient(app)


def _request_payload(caplog) -> dict[str, object]:
    records = [
        record
        for record in caplog.records
        if record.name == "hajiriflow.request"
    ]
    assert len(records) == 1
    return json.loads(records[0].getMessage())


def test_safe_request_id_is_echoed_and_route_is_structured(caplog) -> None:
    caplog.set_level(logging.INFO, logger="hajiriflow.request")
    response = make_client().get(
        "/api/v1/items/employee-123?token=do-not-log-this",
        headers={"X-Request-ID": "request-2026.09:abc"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-2026.09:abc"
    payload = _request_payload(caplog)
    assert payload["request_id"] == "request-2026.09:abc"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/items/{item_id}"
    assert payload["status_code"] == 200
    assert isinstance(payload["duration_ms"], int)

    serialized = json.dumps(payload)
    assert "employee-123" not in serialized
    assert "do-not-log-this" not in serialized
    assert "token" not in serialized


def test_invalid_request_id_is_replaced(caplog) -> None:
    caplog.set_level(logging.INFO, logger="hajiriflow.request")
    response = make_client().get(
        "/api/v1/items/1",
        headers={"X-Request-ID": "not safe because it has spaces"},
    )

    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32
    assert request_id.isalnum()
    assert _request_payload(caplog)["request_id"] == request_id


def test_request_bodies_are_never_logged(caplog) -> None:
    caplog.set_level(logging.INFO, logger="hajiriflow.request")
    response = make_client().post(
        "/api/v1/payroll-preview",
        json={
            "employee": "Sensitive Employee",
            "salary": "999999.99",
            "bank_account": "NP00SECRET",
        },
    )

    assert response.status_code == 200
    payload = _request_payload(caplog)
    serialized = json.dumps(payload)
    assert payload["path"] == "/api/v1/payroll-preview"
    assert "Sensitive Employee" not in serialized
    assert "999999.99" not in serialized
    assert "NP00SECRET" not in serialized
    assert "salary" not in serialized
    assert "bank_account" not in serialized
