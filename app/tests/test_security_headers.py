from fastapi import FastAPI
from fastapi.testclient import TestClient

from hajiriflow.api.middleware import SecurityHeadersMiddleware


def make_client(*, protected_environment: bool) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        SecurityHeadersMiddleware,
        protected_environment=protected_environment,
    )

    @app.get("/api/v1/private")
    def private_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health")
    def public_health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_sensitive_api_responses_are_not_cacheable() -> None:
    response = make_client(protected_environment=False).get("/api/v1/private")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-permitted-cross-domain-policies"] == "none"
    assert "strict-transport-security" not in response.headers


def test_protected_environment_adds_https_and_document_hardening() -> None:
    response = make_client(protected_environment=True).get("/api/v1/private")

    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )


def test_public_health_response_is_not_forced_to_no_store() -> None:
    response = make_client(protected_environment=False).get("/health")

    assert "cache-control" not in response.headers
