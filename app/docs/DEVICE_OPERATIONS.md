# Device pull operations

## Scheduler behavior

Run the worker with `python -m hajiriflow.worker`. Each cycle reads active devices from PostgreSQL and selects only devices whose configured `pull_interval_seconds` has elapsed since the latest pull attempt. A pull result is stored per device, so an unreachable or unsupported device cannot block another device.

The worker polling cadence is controlled by `HAJIRIFLOW_WORKER_POLL_SECONDS` (default 30 seconds). Device retry attempts are bounded by `HAJIRIFLOW_DEVICE_PULL_MAX_ATTEMPTS` (default 3). Per-device PostgreSQL advisory locks in the pull coordinator prevent overlapping pulls across worker processes.

## Adapter availability

The open-source repository deliberately registers no concrete hardware adapter. Unknown/unconfigured devices are recorded as `skipped` with the non-sensitive code `adapter_unavailable`; they are not retried again until that device's configured pull interval elapses.

A production deployment must wire an explicitly supported adapter through the worker resolver. Do not infer protocols from vendor/model names or silently fall back to a generic device protocol. Each concrete adapter needs device-specific authentication, diagnostics, deletion/privacy behavior, rate-limit and failure tests before enablement.

## Credentials

Device credentials remain versioned encrypted records. Concrete adapters must obtain decrypted values only at the last responsible boundary, using externally managed encryption keys. Worker logs must never include credential values, provider errors that may contain credentials, raw biometric material, punch evidence bodies or device-user payloads.

## Safe worker logs

Scheduler logs contain aggregate status counts, opaque device IDs and exception *types* only. Adapter-resolution exception messages are deliberately discarded because vendor SDKs sometimes embed endpoint details or credentials in errors.

## Failure states

- `succeeded`: pull completed and any returned punches/users passed ingestion validation.
- `failed`: the supported adapter failed after bounded retries; stored details are generic.
- `skipped` / `device_locked`: another worker owns the advisory lock.
- `skipped` / `adapter_unavailable`: no reviewed adapter is configured for the registered device.

Operators should alert on repeated `failed` results, sustained `adapter_unavailable` for a device expected to be supported, and an unexpected absence of scheduled pull sessions.

## Production readiness

Scheduler integration does not itself prove real hardware compatibility. Production readiness for a device model requires a concrete reviewed adapter, test hardware or a vendor-supported simulator, credential-rotation verification, device-side biometric deletion verification when applicable, network access controls, and operational monitoring.
