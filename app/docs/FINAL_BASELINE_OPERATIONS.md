# Final baseline operations

This document is the coding and operator contract for HF-060 through HF-066. It does not claim that a particular external hosting account has been provisioned. It defines the repository artifacts and verification gates required before a live environment may be called production-ready.

## Administrative audit

`GET /api/v1/admin/audit-events` is a read-only, globally privileged audit reader guarded by `identity.audit.read`. The reader is bounded to 200 rows per request and supports exact/prefix action filters, object type/id, actor, request ID, organization context, time range, and pagination.

`AuditEvent` rows remain append-only. Application code rejects updates and deletes. Stored before/after/context data is passed through the shared redaction contract before persistence, and request correlation comes from `X-Request-ID`/request context.

## Operational dashboard and metrics

Authorized organization operators can poll:

- `/api/v1/organizations/{organization_id}/operations/dashboard`
- `/api/v1/organizations/{organization_id}/operations/metrics`

The contract exposes aggregate device state, stale-device count, 24-hour pull/job state, attendance status/exception counts, payroll approval indicators, and alert codes. It deliberately excludes device endpoints, credentials, biometric material, employee identity, bank data, salary values, HTTP bodies, cookies, and tokens.

Alert codes currently include:

- `stale_devices`
- `pull_failures_24h`
- `worker_job_failures_24h`
- `attendance_exceptions`
- `payroll_approval_pending`

A production monitoring service can poll `/ready` for database readiness and the organization metrics endpoint for domain health. Alert delivery destinations remain an infrastructure choice; the repository defines the signals and sanitized payload.

## Background worker

The production worker entrypoint is:

```text
python -m hajiriflow.device_platform.worker_cli
```

Each bounded cycle:

1. claims queued device operations;
2. executes approved device-identity lifecycle actions;
3. resolves supported adapters through the encrypted credential resolver;
4. performs due scheduled pulls with the existing PostgreSQL advisory device locks;
5. commits the cycle atomically or rolls it back on an unhandled application failure.

`--once` executes one cycle and exits for smoke tests and supervised jobs. Unsupported adapters continue to fail closed.

## Linux services

Repository templates:

- `ops/systemd/hajiriflow-web.service`
- `ops/systemd/hajiriflow-worker.service`

Recommended layout:

```text
/opt/hajiriflow/app          application checkout
/opt/hajiriflow/venv         Python virtual environment
/etc/hajiriflow/hajiriflow.env   root-owned runtime environment
```

Install the package into the virtual environment, copy the templates to `/etc/systemd/system`, create a non-login `hajiriflow` service user, make the environment file readable only by root and the service group, then run `systemctl daemon-reload` and enable the two units. The web unit binds only to loopback and expects a reviewed HTTPS reverse proxy in front of it. Both units use restrictive systemd sandboxing and `UMask=0077`.

The worker requires only the device integrations and keyring that are actually supported in that environment. Do not invent credentials or enable unsupported adapters.

## PostgreSQL backup

Linux:

```text
HAJIRIFLOW_BACKUP_DATABASE_URL=postgresql://... \
HAJIRIFLOW_BACKUP_PATH=/var/backups/hajiriflow/2026-09-09.dump \
bash scripts/backup-postgres.sh
```

Windows PowerShell:

```text
$env:HAJIRIFLOW_BACKUP_DATABASE_URL = "postgresql://..."
$env:HAJIRIFLOW_BACKUP_PATH = "D:\\HajiriFlowBackups\\2026-09-09.dump"
.\scripts\backup-postgres.ps1
```

Backups use PostgreSQL custom format, omit ownership/ACL portability noise, are written through a temporary file, and receive a SHA-256 sidecar. The scripts never print the database URL.

Retention should be implemented by the operator's scheduler/storage lifecycle policy after a restore rehearsal proves the backup usable. A retention job must never delete the newest known-good restore-tested copy.

## PostgreSQL restore

Always restore into an isolated target first.

Linux:

```text
HAJIRIFLOW_RESTORE_TARGET_URL=postgresql://.../hajiriflow_restore \
HAJIRIFLOW_RESTORE_BACKUP_PATH=/var/backups/hajiriflow/2026-09-09.dump \
HAJIRIFLOW_RESTORE_CONFIRM=I_UNDERSTAND_THIS_REPLACES_THE_TARGET \
bash scripts/restore-postgres.sh
```

Windows uses the equivalent `restore-postgres.ps1` variables.

The restore command verifies the checksum when present and uses `pg_restore --clean --if-exists --no-owner --no-acl`. Production targets are blocked by default. A production restore additionally requires `HAJIRIFLOW_ALLOW_PRODUCTION_RESTORE=yes`; this is an emergency operator acknowledgement, not an automated deployment behavior.

After restore:

1. point `HAJIRIFLOW_DATABASE_URL` at the restored isolated database;
2. run `alembic current --check-heads`;
3. query a known sentinel/business record;
4. run application smoke tests;
5. record the restore date, backup checksum, migration head, operator, and result outside the database being restored.

CI performs this entire source-backup → isolated-target-restore → migration-head → sentinel verification against PostgreSQL 17 on every relevant pull request.

## Migration and CI release gates

Every schema change must have an Alembic revision. CI verifies:

- Python 3.12 and 3.14 lint/tests;
- frontend JavaScript syntax;
- production runtime/proxy fail-closed behavior;
- backup/service script syntax and worker CLI importability;
- PostgreSQL `upgrade head → downgrade base → upgrade head → current --check-heads`;
- PostgreSQL backup/restore rehearsal;
- PostgreSQL device advisory-lock/retry/cursor integration;
- dependency/static analysis, repository hygiene, and CodeQL in the Security workflow;
- real browser authorization against PostgreSQL in the browser workflow.

A green repository merge is not itself permission to release production. External hosting credentials, DNS/provider state, branch/ruleset administration, and live backup scheduling remain environment administration tasks.

## Incident and recovery evidence

For worker failure, stale devices, pull errors, database unavailability, or backup failure, preserve:

- request/job correlation identifier;
- UTC timestamp;
- sanitized error code/category;
- affected organization/device identifiers when needed;
- relevant deployment SHA and migration head;
- backup checksum for recovery incidents.

Never add credentials, biometric payloads, bank details, national identity values, session/csrf tokens, or raw HTTP request bodies to incident logs.
