# Device platform and immutable attendance evidence

HajiriFlow keeps biometric-device networking outside the web application. The web API stores authorized requests in PostgreSQL; the dedicated worker resolves a reviewed adapter and performs device communication. Unsupported adapter keys are skipped rather than guessed.

## Supported adapter boundary

The baseline includes `hajiriflow_gateway_v1`, a vendor-neutral HTTP adapter intended for a HajiriFlow Biometric Gateway running on the same network as physical devices. The gateway contract exposes only diagnostics, attendance punches, and user inventory. HajiriFlow does not request or expose biometric templates through this adapter.

A registered gateway endpoint must be an HTTP or HTTPS origin/path without embedded credentials, query strings, or fragments. Optional bearer credentials are encrypted in `device_credentials`. Deployments configure a versioned Fernet keyring through `HAJIRIFLOW_DEVICE_SECRET_ACTIVE_KEY_ID` and `HAJIRIFLOW_DEVICE_SECRET_KEYS_JSON`; key material is never stored in device rows or returned by APIs.

The worker fails closed when the adapter key is unknown, the keyring is unavailable, the active credential cannot be decrypted, or a credential contains unsupported fields.

## Gateway HTTP v1 contract

The worker uses the following read-only gateway calls:

- `GET /v1/diagnostics` returns reachability, observed time, optional firmware/device time, a sanitized message, and primitive metadata.
- `GET /v1/punches?cursor=...` returns a bounded page of punches and an optional next cursor.
- `GET /v1/punches?start_at=...&end_at=...&cursor=...` is the historical date-range form.
- `GET /v1/users` returns device identity inventory without biometric templates.

Responses larger than 4 MiB are rejected. Punch timestamps must be timezone-aware ISO-8601 values. Evidence and metadata accept primitive values only, and sensitive evidence names such as template, biometric, fingerprint image, password, secret, and token are rejected or redacted before persistence/logging.

## Scheduling and commands

Scheduled pulls use the PostgreSQL `devices.pull_interval_seconds` value. A PostgreSQL advisory lock prevents overlapping pulls for the same device, and every attempt is isolated so one failing device cannot stop another.

Diagnostics, **Pull now**, and historical date-range pulls are never executed by FastAPI request handlers. The API writes a `device_operations` row with `pending` status and returns `202 Accepted`. The worker claims pending operations and records `running`, `succeeded`, `failed`, or `skipped` outcomes. Historical pulls are limited to 366 days and 100 pagination batches, reject cursor cycles, and use bounded retries.

`device_pull_sessions` retain attempt counts, ingestion counts, duplicate counts, cursor progress, sanitized error codes/details, and start/end times. Runtime configuration stores site, protocol preference, timeout, last diagnostics, and last successful pull in PostgreSQL.

## Immutable evidence

Raw punches are append-only. A deterministic source fingerprint makes repeated ingestion idempotent, while SQLAlchemy update/delete guards reject ordinary mutation of `raw_punches`. Device evidence stores the UTC instant and the API derives Nepal-local AD and Bikram Sambat dates for review without changing the original instant.

Unlinked punches remain in the evidence table. The unlinked review endpoint surfaces punches whose device identity has no active employee mapping. Mapping a device user to an employee adds relationship metadata; it never edits or deletes the underlying raw punch.

## Authorization

Device reads require `device.read`. Registry/runtime/credential changes require `device.manage`. Pull and diagnostics commands require `device.pull`. Employee-device links require `device.mapping.manage`. Every protected action is organization-scoped, mutating browser requests require CSRF, and credential values are never returned after write.

## Operational verification

The baseline is covered by automated tests for credential encryption, repeat-safe ingestion, raw-evidence immutability, per-device failure isolation, the gateway JSON contract, adapter fail-closed behavior, queued worker execution, historical cursor failure handling, tenant authorization, and PostgreSQL migration roundtrips.
