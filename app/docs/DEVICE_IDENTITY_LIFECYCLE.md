# Device identity sync, enrollment, migration, and encrypted archive

HajiriFlow treats every device write as a reviewed operation. FastAPI never pushes users, migrates identities, or restores an archive directly. The API creates a deterministic preview, an authorized user approves that exact preview hash, and the dedicated worker performs the operation with a second device-side dry run before the write.

## Identity comparison

The comparison view uses the most recently synchronized device-user inventory and HajiriFlow employee mappings to show:

- device users already mapped to employees;
- unknown device registrations that need review;
- active employees missing from the selected device; and
- whether a missing employee has the numeric attendance ID required for deterministic enrollment.

Ordinary scheduled and immediate pulls refresh device-user inventory when the adapter advertises `list_users`.

## Preview and approval

Supported action types are:

- `push_users`: enroll selected employees on a target device;
- `migrate_users`: copy selected identities from one compatible device to another;
- `archive_export`: read selected identities and store an encrypted archive; and
- `archive_restore`: restore an encrypted archive to a compatible target device.

A preview performs row-level validation and records a SHA-256 hash of the reviewed action. Missing attendance IDs, existing target registrations, invalid source identities, and biometric-consent failures are blocking rows. An action with any blocking row cannot be approved. Approval must present the exact 64-character preview hash.

The worker rechecks target conflicts and biometric consent at execution time. This prevents a stale preview from silently overwriting a registration or moving biometric data after consent has changed.

## Gateway contract

`hajiriflow_gateway_v1` explicitly supports the identity lifecycle through two additional endpoints:

- `POST /v1/identity/push?dry_run=true|false` validates or writes one identity bundle; and
- `POST /v1/identity/export` returns one identity bundle for controlled migration/archive.

Each write is called first with `dry_run=true`. Only an accepted dry run is followed by `dry_run=false`. Unsupported adapters fail closed. Bulk jobs deliberately execute one identity at a time so one failure cannot abort or hide the results of other rows.

An identity bundle contains the external user ID, display name, privilege, active state, template count, primitive metadata, and an optional opaque biometric payload. The biometric payload is never written to ordinary application logs, audits, manifests, device-user inventory, or API responses.

## Biometric consent

If a source device user reports one or more biometric templates, HajiriFlow requires an active employee mapping and the employee's latest biometric consent decision to be `granted` before migration or archive export. Archive restore checks the archived employee reference and current consent again before execution. Unmapped biometric identities are blocked rather than guessed.

## Encrypted archives

Archive export holds the gateway identity bundle only in worker memory long enough to serialize and encrypt it. The same externally managed versioned Fernet keyring used for device credentials encrypts the archive payload. The database stores:

- key identifier;
- ciphertext;
- a non-sensitive manifest containing external user IDs, employee references, and template counts; and
- status/timestamps.

The API exposes only manifest metadata. It never returns archive ciphertext or decrypted biometric material. A restore decrypts the archive only inside the worker and performs a target-device dry run for every row before writing.

## Audit and results

Preview, approval, cancellation, and execution create administrative audit events. Audit payloads contain action type, device IDs, row counts, preview hash, final counts, archive ID, status, and sanitized error codes. They do not contain credentials, archive ciphertext, biometric payloads, or raw gateway error bodies.

Execution results are persisted per row as `succeeded` or `failed` with a short non-sensitive code. The aggregate action becomes `succeeded`, `partial`, or `failed`. Target external-ID conflicts are never overwritten automatically.
