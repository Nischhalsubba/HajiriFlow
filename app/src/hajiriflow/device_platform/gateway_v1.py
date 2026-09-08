import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    DeviceUserRecord,
    PullBatch,
    PunchRecord,
)


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None:
        raise ValueError("gateway timestamps must include a timezone")
    return result


class DeviceGatewayError(RuntimeError):
    pass


class HajiriFlowGatewayV1Adapter:
    """First-party HTTPS contract for LAN/device-specific gateway services.

    The gateway owns vendor protocol details. HajiriFlow receives normalized punches,
    user inventory, diagnostics, and optional encrypted-archive payloads without
    guessing a biometric device protocol in the web application.
    """

    adapter_key = "hajiriflow_gateway_v1"

    def __init__(
        self,
        *,
        endpoint_uri: str,
        token: str,
        timeout_seconds: float = 10.0,
        allow_http: bool = False,
    ) -> None:
        endpoint = endpoint_uri.strip().rstrip("/")
        parsed = urllib.parse.urlparse(endpoint)
        allowed_schemes = {"https"} | ({"http"} if allow_http else set())
        if parsed.scheme not in allowed_schemes or not parsed.hostname:
            raise ValueError("Device Gateway v1 requires a valid HTTPS endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Device Gateway endpoint must not contain credentials or query data")
        if not token.strip():
            raise ValueError("Device Gateway v1 requires a bearer token")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("gateway timeout must be between 0 and 60 seconds")
        self.endpoint_uri = endpoint
        self.token = token.strip()
        self.timeout_seconds = timeout_seconds

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.endpoint_uri}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "HajiriFlow-Device-Gateway/1",
        }
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(2_000_001)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DeviceGatewayError("Device Gateway request failed") from exc
        if len(raw) > 2_000_000:
            raise DeviceGatewayError("Device Gateway response exceeded the 2 MB safety limit")
        try:
            decoded = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise DeviceGatewayError("Device Gateway returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise DeviceGatewayError("Device Gateway response must be a JSON object")
        return decoded

    def capabilities(self) -> DeviceCapabilities:
        payload = self._request_json("GET", "/v1/diagnostics")
        capabilities = payload.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            raise DeviceGatewayError("Device Gateway capabilities must be an object")
        return DeviceCapabilities(
            pull_punches=bool(capabilities.get("pull_punches", True)),
            list_users=bool(capabilities.get("list_users", True)),
            push_users=bool(capabilities.get("push_users", False)),
            biometric_templates=bool(capabilities.get("biometric_templates", False)),
            realtime_events=bool(capabilities.get("realtime_events", False)),
        )

    def diagnostics(self) -> DeviceDiagnostics:
        payload = self._request_json("GET", "/v1/diagnostics")
        observed = payload.get("observed_at")
        observed_at = _parse_datetime(observed) if isinstance(observed, str) else datetime.now(UTC)
        device_time = payload.get("device_time")
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        safe_metadata = {
            str(key): value
            for key, value in metadata.items()
            if isinstance(value, (str, int, bool)) or value is None
        }
        return DeviceDiagnostics(
            reachable=bool(payload.get("reachable", True)),
            observed_at=observed_at,
            firmware_version=(
                str(payload["firmware_version"])
                if payload.get("firmware_version") is not None
                else None
            ),
            device_time=(
                _parse_datetime(device_time) if isinstance(device_time, str) else None
            ),
            message=str(payload["message"])[:400] if payload.get("message") else None,
            metadata=safe_metadata,
        )

    def pull_punches(
        self,
        *,
        cursor: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> PullBatch:
        query: dict[str, str] = {}
        if cursor:
            query["cursor"] = cursor
        if start_at:
            if start_at.tzinfo is None:
                raise ValueError("historical pull start must include a timezone")
            query["start_at"] = start_at.astimezone(UTC).isoformat()
        if end_at:
            if end_at.tzinfo is None:
                raise ValueError("historical pull end must include a timezone")
            query["end_at"] = end_at.astimezone(UTC).isoformat()
        if start_at and end_at and end_at < start_at:
            raise ValueError("historical pull end cannot be before start")
        payload = self._request_json("GET", "/v1/punches", query=query)
        rows = payload.get("punches") or []
        if not isinstance(rows, list) or len(rows) > 10_000:
            raise DeviceGatewayError("Device Gateway punch batch is invalid or too large")
        punches: list[PunchRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                raise DeviceGatewayError("Device Gateway punch rows must be objects")
            occurred_at = row.get("occurred_at")
            external_user_id = row.get("device_user_identifier")
            if not isinstance(occurred_at, str) or not isinstance(external_user_id, str):
                raise DeviceGatewayError("Device Gateway punch row is missing required fields")
            evidence = row.get("evidence") or {}
            if not isinstance(evidence, dict):
                raise DeviceGatewayError("Device Gateway punch evidence must be an object")
            punches.append(
                PunchRecord(
                    device_user_identifier=external_user_id,
                    occurred_at=_parse_datetime(occurred_at),
                    external_event_id=(
                        str(row["external_event_id"])
                        if row.get("external_event_id") is not None
                        else None
                    ),
                    punch_kind=str(row.get("punch_kind") or "unknown"),
                    verification_method=(
                        str(row["verification_method"])
                        if row.get("verification_method") is not None
                        else None
                    ),
                    evidence=evidence,
                )
            )
        next_cursor = payload.get("next_cursor")
        return PullBatch(
            punches=tuple(punches),
            next_cursor=str(next_cursor) if next_cursor is not None else None,
        )

    @staticmethod
    def _user_record(row: dict[str, Any]) -> DeviceUserRecord:
        external_user_id = row.get("external_user_id")
        if not isinstance(external_user_id, str) or not external_user_id.strip():
            raise DeviceGatewayError("Device Gateway user is missing external_user_id")
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        safe_metadata = {
            str(key): value
            for key, value in metadata.items()
            if isinstance(value, (str, int, bool)) or value is None
        }
        return DeviceUserRecord(
            external_user_id=external_user_id,
            display_name=(str(row["display_name"]) if row.get("display_name") else None),
            privilege=str(row["privilege"]) if row.get("privilege") else None,
            active=bool(row.get("active", True)),
            template_count=max(0, int(row.get("template_count", 0))),
            metadata=safe_metadata,
        )

    def list_users(self) -> tuple[DeviceUserRecord, ...]:
        payload = self._request_json("GET", "/v1/users")
        rows = payload.get("users") or []
        if not isinstance(rows, list) or len(rows) > 50_000:
            raise DeviceGatewayError("Device Gateway user inventory is invalid or too large")
        return tuple(self._user_record(row) for row in rows if isinstance(row, dict))

    def push_user(self, record: DeviceUserRecord, *, overwrite: bool = False) -> DeviceUserRecord:
        payload = self._request_json(
            "PUT",
            f"/v1/users/{urllib.parse.quote(record.external_user_id, safe='')}",
            payload={
                "display_name": record.display_name,
                "privilege": record.privilege,
                "active": record.active,
                "overwrite": overwrite,
            },
        )
        return self._user_record(payload.get("user") or {"external_user_id": record.external_user_id})

    def export_user_archive(self, external_user_id: str) -> bytes:
        payload = self._request_json(
            "GET",
            f"/v1/users/{urllib.parse.quote(external_user_id, safe='')}/archive",
        )
        encoded = payload.get("archive_base64")
        if not isinstance(encoded, str):
            raise DeviceGatewayError("Device Gateway archive response is missing archive_base64")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise DeviceGatewayError("Device Gateway archive is not valid base64") from exc
        if len(raw) > 10_000_000:
            raise DeviceGatewayError("Device Gateway user archive exceeds the 10 MB safety limit")
        return raw

    def import_user_archive(self, archive: bytes, *, overwrite: bool = False) -> DeviceUserRecord:
        if len(archive) > 10_000_000:
            raise ValueError("user archive exceeds the 10 MB safety limit")
        payload = self._request_json(
            "POST",
            "/v1/users/archive",
            payload={
                "archive_base64": base64.b64encode(archive).decode(),
                "overwrite": overwrite,
            },
        )
        user = payload.get("user")
        if not isinstance(user, dict):
            raise DeviceGatewayError("Device Gateway archive restore did not return a user")
        return self._user_record(user)
