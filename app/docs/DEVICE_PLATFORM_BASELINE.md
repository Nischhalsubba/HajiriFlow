# Device platform baseline

HajiriFlow keeps vendor/device protocol traffic out of the web process. The web API validates permissions, stores encrypted credentials, creates previews, and enqueues durable jobs. The dedicated worker owns diagnostics, pulls, inventory synchronization, enrollment, migration, archive, and restore network work.

## Supported adapter: HajiriFlow Device Gateway v1

The first supported production adapter is `hajiriflow_gateway_v1`. It is a small HTTPS JSON contract intended for a separately deployed gateway process that understands the actual biometric hardware/vendor protocol. This keeps vendor SDKs, LAN-specific drivers, and biometric payload handling out of the web application and provides one reviewed normalization boundary.

The gateway contract exposes:

- `GET /v1/diagnostics` — reachability, firmware/device time, capabilities, sanitized metadata
- `GET /v1/punches` — bounded normalized punch batches with optional cursor/start/end parameters
- `GET /v1/users` — normalized device registration inventory
- `PUT /v1/users/{external_user_id}` — non-overwriting enrollment when `push_users` is supported
- `GET /v1/users/{external_user_id}/archive` — optional archive export when biometric templates are supported
- `POST /v1/users/archive` — optional non-overwriting archive restore

Gateway responses are bounded before parsing. Punch timestamps must include an explicit timezone. Ordinary gateway metadata accepts only scalar operational values; credentials/templates are not copied into logs, diagnostics, or job results.

Production gateway endpoints must use HTTPS. HTTP is accepted only in development/test environments for isolated fixtures.

## Encrypted device credentials

Device credentials are versioned in `device_credentials`. Ordinary device rows contain endpoint/capability metadata only. Credential rotation encrypts the bearer token before commit and retires the previous version.

The API/worker require the same device-secret keyring configuration:

- `HAJIRIFLOW_DEVICE_SECRET_ACTIVE_KEY_ID`
- `HAJIRIFLOW_DEVICE_SECRET_KEYS_JSON` — JSON object mapping key IDs to Fernet keys

Key IDs are stored with ciphertext so key rotation remains possible. Secret values are never returned by device APIs.

## Durable worker jobs

`device_jobs` is the command queue for network operations:

- diagnostics
- immediate pull
- historical pull
- inventory sync
- user enrollment
- device-to-device identity migration
- encrypted user archive
- archive restore

The web process only enqueues these commands. Worker instances claim queued jobs and use the existing PostgreSQL advisory device lock, so independent workers do not operate on one device concurrently. Migration also takes a target-device lock; a conflicting target never gets overwritten silently.

Job errors expose a sanitized code/message. Sensitive adapter exception text is not persisted as a job result.

## Scheduling and pull history

The existing PostgreSQL-backed scheduler uses each active device's `pull_interval_seconds` plus the most recent pull completion time to decide when a device is due. Scheduled and immediate pulls use the same `DevicePullCoordinator`, retry/backoff policy, advisory lock, pull-session history, normalized user inventory, and idempotent punch ingestion.

Historical pull jobs accept a timezone-aware range of at most 366 days. They ingest through the same raw-punch fingerprint/idempotency contract as scheduled pulls.

## Immutable punch evidence and review

Raw punches remain append-only application evidence. They are unique by organization/device/source fingerprint, retain the original device identifier and normalized event evidence, and are not deleted when a user mapping changes.

The unlinked-punch review endpoint lists raw punches whose device identifier is not currently mapped to an employee. Mapping the corresponding `DeviceUser` to an employee resolves future review without rewriting the raw event.

## Device identities, preview, and sync

Inventory sync updates normalized `device_users`. The API provides bounded/paginated inventory plus a comparison preview:

- unknown/unmapped device users
- active employees missing a mapped registration
- inactive device registrations

Bulk enrollment always has a preview. Employee external IDs use the numeric attendance ID when configured; otherwise the stable employee code is used. Apply only enqueues missing registrations and the worker re-checks adapter capability.

Device-to-device migration requires an explicit preview. Apply is rejected when a source user is missing or the target already contains that external ID. No overwrite flag is exposed by the baseline API.

## Encrypted user/biometric archive

Adapters advertising `biometric_templates` may export a gateway-defined user archive. HajiriFlow immediately encrypts the opaque bytes with the device secret keyring and stores only ciphertext plus a SHA-256 integrity digest. The clear archive is never returned through the API or written to job/audit payloads.

Restore verifies organization ownership and the SHA-256 digest before sending the decrypted opaque archive to a compatible adapter. Restore is non-overwriting.

## Authorization and audit

- `device.read` — registry, inventory, jobs, diagnostics, comparisons, unlinked punches
- `device.manage` — credential rotation, diagnostics request, sync/enrollment/migration/archive/restore
- `device.pull` — immediate/historical pull commands
- `device.mapping.manage` — employee-device mapping

Every queued job and job outcome is audited with actor, device, organization, command type, sanitized counts/IDs, and sanitized error code. Device network calls remain a worker responsibility.
