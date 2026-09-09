import http.client
import json
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit

from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    DeviceUserRecord,
    PullBatch,
    PunchRecord,
)

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"gateway {field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"gateway {field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"gateway {field} must include a timezone")
    return parsed


def _primitive_mapping(value: object, *, field: str) -> dict[str, str | int | float | bool | None]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"gateway {field} must be an object")
    result: dict[str, str | int | float | bool | None] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, (str, int, float, bool, type(None))):
            raise ValueError(f"gateway {field} accepts primitive values only")
        result[key] = item
    return result


class HajiriFlowGatewayAdapter:
    """Supported adapter for the HajiriFlow Biometric Gateway HTTP v1 contract.

    The gateway runs on the same LAN as biometric hardware and exposes a narrow,
    vendor-neutral JSON surface to the worker. This keeps device networking out of
    the web process while allowing reviewed gateway implementations to support
    concrete hardware families without leaking biometric templates into HajiriFlow.
    """

    adapter_key = "hajiriflow_gateway_v1"

    def __init__(
        self,
        *,
        endpoint_uri: str,
        timeout_seconds: int = 10,
        bearer_token: str | None = None,
    ) -> None:
        parsed = urlsplit(endpoint_uri.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("gateway endpoint must use http or https with a hostname")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("gateway endpoint must not contain credentials, query, or fragment")
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise ValueError("gateway timeout must be between 1 and 120 seconds")
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port
        self._base_path = parsed.path.rstrip("/")
        self._timeout = timeout_seconds
        self._bearer_token = bearer_token.strip() if bearer_token else None

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            pull_punches=True,
            list_users=True,
            push_users=False,
            biometric_templates=False,
            realtime_events=False,
        )

    def _request(self, path: str, *, query: dict[str, str] | None = None) -> object:
        request_path = f"{self._base_path}{path}"
        if query:
            request_path = f"{request_path}?{urlencode(query)}"
        connection_class = (
            http.client.HTTPSConnection if self._scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_class(self._host, self._port, timeout=self._timeout)
        headers = {"Accept": "application/json", "User-Agent": "HajiriFlow-Worker/1"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        try:
            connection.request("GET", request_path, headers=headers)
            response = connection.getresponse()
            content_length = response.getheader("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise ValueError("gateway response exceeds the allowed size")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("gateway response exceeds the allowed size")
            if response.status < 200 or response.status >= 300:
                raise ConnectionError(f"gateway returned HTTP {response.status}")
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("gateway returned invalid JSON") from exc
        finally:
            connection.close()

    def diagnostics(self) -> DeviceDiagnostics:
        payload = self._request("/v1/diagnostics")
        if not isinstance(payload, dict):
            raise ValueError("gateway diagnostics response must be an object")
        observed_at = _timestamp(payload.get("observed_at"), field="observed_at")
        device_time_value = payload.get("device_time")
        device_time = (
            _timestamp(device_time_value, field="device_time")
            if device_time_value is not None
            else None
        )
        metadata = _primitive_mapping(payload.get("metadata"), field="metadata")
        return DeviceDiagnostics(
            reachable=bool(payload.get("reachable", False)),
            observed_at=observed_at.astimezone(UTC),
            firmware_version=(
                str(payload["firmware_version"]) if payload.get("firmware_version") else None
            ),
            device_time=device_time.astimezone(UTC) if device_time else None,
            message=str(payload["message"])[:500] if payload.get("message") else None,
            metadata=metadata,
        )

    def _pull(self, query: dict[str, str]) -> PullBatch:
        payload = self._request("/v1/punches", query=query)
        if not isinstance(payload, dict) or not isinstance(payload.get("punches"), list):
            raise ValueError("gateway punch response must contain a punches list")
        punches: list[PunchRecord] = []
        for raw in payload["punches"]:
            if not isinstance(raw, dict):
                raise ValueError("gateway punch entries must be objects")
            identifier = raw.get("device_user_identifier")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("gateway punch requires device_user_identifier")
            punches.append(
                PunchRecord(
                    device_user_identifier=identifier.strip(),
                    occurred_at=_timestamp(raw.get("occurred_at"), field="occurred_at"),
                    external_event_id=(
                        str(raw["external_event_id"])
                        if raw.get("external_event_id") is not None
                        else None
                    ),
                    punch_kind=str(raw.get("punch_kind", "unknown")),
                    verification_method=(
                        str(raw["verification_method"])
                        if raw.get("verification_method") is not None
                        else None
                    ),
                    evidence=_primitive_mapping(raw.get("evidence"), field="evidence"),
                )
            )
        next_cursor = payload.get("next_cursor")
        if next_cursor is not None and not isinstance(next_cursor, str):
            raise ValueError("gateway next_cursor must be a string or null")
        return PullBatch(punches=tuple(punches), next_cursor=next_cursor)

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        query = {"cursor": cursor} if cursor else {}
        return self._pull(query)

    def pull_punches_range(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        cursor: str | None = None,
    ) -> PullBatch:
        if start_at.tzinfo is None or end_at.tzinfo is None:
            raise ValueError("historical pull bounds must include a timezone")
        if end_at < start_at:
            raise ValueError("historical pull end cannot be before start")
        query = {
            "start_at": start_at.astimezone(UTC).isoformat(),
            "end_at": end_at.astimezone(UTC).isoformat(),
        }
        if cursor:
            query["cursor"] = cursor
        return self._pull(query)

    def list_users(self) -> tuple[DeviceUserRecord, ...]:
        payload = self._request("/v1/users")
        if not isinstance(payload, dict) or not isinstance(payload.get("users"), list):
            raise ValueError("gateway user response must contain a users list")
        users: list[DeviceUserRecord] = []
        for raw in payload["users"]:
            if not isinstance(raw, dict):
                raise ValueError("gateway user entries must be objects")
            external_user_id = raw.get("external_user_id")
            if not isinstance(external_user_id, str) or not external_user_id.strip():
                raise ValueError("gateway user requires external_user_id")
            users.append(
                DeviceUserRecord(
                    external_user_id=external_user_id.strip(),
                    display_name=(str(raw["display_name"]) if raw.get("display_name") else None),
                    privilege=(str(raw["privilege"]) if raw.get("privilege") else None),
                    active=bool(raw.get("active", True)),
                    template_count=max(0, int(raw.get("template_count", 0))),
                    metadata={
                        key: value
                        for key, value in _primitive_mapping(
                            raw.get("metadata"), field="metadata"
                        ).items()
                        if isinstance(value, (str, int, bool, type(None)))
                    },
                )
            )
        return tuple(users)
