import json

from hajiriflow.device_platform.adapters import DeviceIdentityBundle
from hajiriflow.device_platform.gateway_adapter import HajiriFlowGatewayAdapter


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.status = 200
        self.payload = json.dumps(payload).encode()

    def getheader(self, _name: str) -> str | None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.payload


class FakeConnection:
    calls: list[tuple[str, str, bytes | None, dict[str, str]]] = []

    def __init__(self, _host: str, _port: int | None, *, timeout: int) -> None:
        assert timeout == 9
        self.method = ""
        self.path = ""
        self.body: bytes | None = None
        self.headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.method = method
        self.path = path
        self.body = body
        self.headers = headers or {}
        self.calls.append((method, path, body, self.headers))

    def getresponse(self) -> FakeResponse:
        if self.path.startswith("/gateway/v1/identity/push"):
            return FakeResponse({"accepted": True, "code": "accepted"})
        if self.path == "/gateway/v1/identity/export":
            return FakeResponse(
                {
                    "external_user_id": "101",
                    "display_name": "Employee One",
                    "template_count": 1,
                    "biometric_payload": "opaque-template",
                    "metadata": {"source": "device"},
                }
            )
        raise AssertionError(f"unexpected gateway path: {self.path}")

    def close(self) -> None:
        return None


def test_gateway_identity_write_requires_explicit_dry_run(monkeypatch) -> None:
    FakeConnection.calls = []
    monkeypatch.setattr(
        "hajiriflow.device_platform.gateway_adapter.http.client.HTTPConnection",
        FakeConnection,
    )
    adapter = HajiriFlowGatewayAdapter(
        endpoint_uri="http://gateway.internal:9080/gateway",
        timeout_seconds=9,
        bearer_token="gateway-token",
    )
    bundle = DeviceIdentityBundle(
        external_user_id="101",
        display_name="Employee One",
        template_count=1,
        biometric_payload="opaque-template",
    )

    assert adapter.capabilities().push_users is True
    assert adapter.capabilities().archive_users is True
    assert adapter.capabilities().restore_users is True
    assert adapter.push_identity(bundle, dry_run=True).accepted is True
    assert adapter.push_identity(bundle, dry_run=False).accepted is True
    exported = adapter.export_identity("101")
    assert exported.biometric_payload == "opaque-template"

    paths = [path for _, path, _, _ in FakeConnection.calls]
    assert "/gateway/v1/identity/push?dry_run=true" in paths
    assert "/gateway/v1/identity/push?dry_run=false" in paths
    assert "/gateway/v1/identity/export" in paths
    for method, _path, body, headers in FakeConnection.calls:
        assert method == "POST"
        assert body is not None
        assert headers["Authorization"] == "Bearer gateway-token"
        assert headers["Content-Type"] == "application/json"
