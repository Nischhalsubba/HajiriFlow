# HajiriFlow baseline release review

This review closes the repository-side release criteria for the HajiriFlow baseline. It does not
claim that an external hosting account, DNS zone, alert destination, backup scheduler, or GitHub
ruleset has been provisioned. Those environment-administration actions must be verified in the
target environment before a live production release.

## Release decision

A candidate commit is release-eligible only when all of the following are true:

1. CI passes on Python 3.12 and 3.14.
2. PostgreSQL migration roundtrip, device concurrency, and backup/restore rehearsal pass.
3. Security dependency audit, Bandit, repository hygiene, and CodeQL pass.
4. Real-browser identity/authorization E2E passes.
5. `python -m hajiriflow.operations.reconciliation` exits zero against the release database.
6. `scripts/release_smoke.py` exits zero against a production-like environment.
7. The operator records candidate SHA, migration head, reconciliation output, load-smoke output,
   backup checksum, and reviewer identity outside the application database.

A green merge is not itself permission to deploy.

## Threat model and mitigations

### Authentication and sessions

Threats: credential stuffing, stolen cookies, stale privileges, CSRF, temporary-password bypass.

Controls: Argon2 password hashing, throttled authentication attempts, revocable/versioned sessions,
forced password replacement, secure cookie policy, CSRF enforcement for cookie-authenticated
mutations, and browser E2E proving session invalidation and CSRF denial.

### Authorization and tenant isolation

Threats: IDOR, cross-organization reads/writes, role escalation, export leakage, privileged worker
or device actions from ordinary employee accounts.

Controls: deny-by-default permissions, organization-scoped grants, object-scope checks, explicit
export/device/worker permissions, system-administrator hierarchy protections, and positive/negative
role tests. Employee self-service permissions are deliberately separate from workforce, payroll,
device, audit, and operations permissions.

### Device and biometric boundary

Threats: credential disclosure, unsupported device behavior, replayed punches, destructive identity
writes, biometric payload exposure, concurrent pulls corrupting cursors.

Controls: encrypted device credentials, fail-closed adapter resolution, worker-only device I/O,
preview/approval before identity mutations, consent checks, immutable/idempotent punch evidence,
unlinked-evidence retention, PostgreSQL advisory locks, cursor/retry integration tests, and encrypted
identity archives. Logs and operational payloads exclude device credentials and biometric material.

### Attendance integrity

Threats: raw punch deletion, duplicate inflation, overnight misclassification, correction bypass,
locked-period mutation, stale derived records.

Controls: append-only raw evidence, deterministic Attendance Engine v2, duplicate grouping without
raw deletion, timezone-normalized overnight calculation, additive approved manual events, row-safe
imports, explicit period locks/reopen, and rejection of the legacy mutable correction path for v2
records. Release reconciliation requires every attendance record to have its v2 detail row.

### Payroll integrity and privacy

Threats: unapproved attendance feeding payroll, floating-point money drift, policy changes altering
history, self-approval, mutable posted payroll, another employee reading payslips, salary/tax leakage
into logs.

Controls: locked/approved attendance prerequisites, Decimal money arithmetic, effective-dated policy
and tax snapshots, maker/checker lifecycle, immutable posted snapshots, additive reversal, employee
self-service identity derived from the authenticated account, and sanitized operational metrics.
Release reconciliation verifies payroll arithmetic, snapshots, and terminal-run line presence.

### Audit and observability

Threats: tampering with audit history, secrets/PII in logs, unbounded administrative reads.

Controls: append-only audit events, shared redaction before persistence, bounded/filterable audit
reader, request/job correlation IDs, sanitized operations metrics, and repository tests proving audit
update/delete attempts fail.

### Database, backup, and recovery

Threats: failed migrations, unavailable database, corrupt/stale backup, accidental destructive
restore, backup credential disclosure.

Controls: Alembic upgrade/downgrade/re-upgrade CI, `/ready` database readiness, custom-format
PostgreSQL backup with SHA-256 sidecar, isolated restore rehearsal, production restore fail-closed
without an explicit acknowledgement, and scripts that never print database URLs.

## Permission review

The baseline permission review requires these separations to remain true:

- employee: own attendance/payroll self-service only; no exports, device pulls, operations, or admin;
- workforce administrator: workforce/attendance exports, device pulls, operations; no payroll manage;
- payroll administrator: payroll read/manage/approve/export and operations; no identity administration;
- system administrator: global administrative authority with hierarchy/self-lockout safeguards.

Any new protected page, API, export, object mutation, worker action, or device action must add both a
positive and a negative authorization test before release.

## Device integration review

The baseline supports the registered HajiriFlow gateway adapter contract. Device operations execute
outside FastAPI through `python -m hajiriflow.device_platform.worker_cli`. The release evidence must
include green PostgreSQL device-concurrency tests, supported-adapter contract tests, and worker tests.
Unsupported adapters remain fail-closed and must not be enabled by configuration alone.

## Attendance and payroll reconciliation

Run against a production-like copy first, then against the release database before enabling writes:

```text
python -m hajiriflow.operations.reconciliation
```

Optionally scope the report:

```text
python -m hajiriflow.operations.reconciliation --organization-id <uuid>
```

The command fails closed when any of these invariants fail:

- attendance record without a v2 detail row;
- payroll line where gross - deductions - tax does not equal net exactly;
- missing/non-object payroll calculation snapshot;
- posted/reversed payroll run with no payroll lines.

Store the JSON output with the release evidence. Do not repair a mismatch by deleting raw evidence or
historical payroll; investigate and use the documented additive correction/reversal workflows.

## Production-like health and bounded load smoke

Run only against an environment you are authorized to test:

```text
python scripts/release_smoke.py \
  --base-url https://staging.example.invalid \
  --requests 100 \
  --concurrency 10 \
  --p95-ms 1000 \
  --backup-path /var/backups/hajiriflow/latest.dump
```

The tool is intentionally bounded to at most 500 requests and concurrency 25. It checks `/health`,
`/ready`, a bounded health-endpoint load sample, optional backup age, and the backup checksum sidecar.
It never prints the supplied base URL or database credentials.

Release is blocked by any of these alert codes:

- `web_health_unavailable`
- `database_unavailable`
- `load_smoke_request_failures`
- `load_smoke_p95_exceeded`
- `backup_missing_or_empty`
- `backup_stale`
- `backup_checksum_missing`
- `backup_checksum_mismatch`

Alert delivery (pager, email, chat, monitoring platform) is infrastructure-specific. Schedule this
health contract or equivalent monitoring so non-zero results create an operator alert. A backup job
must likewise alert on non-zero exit and must never delete the newest restore-tested copy.

## Dependency, license, and security review

Before release, keep the direct runtime dependency ranges in `pyproject.toml` intentional and review
the resolved dependency inventory for license compatibility with the deployment. The automated
Security workflow is the executable vulnerability/static-analysis gate: `pip-audit`, Bandit,
repository secret hygiene, and CodeQL must all pass. A dependency upgrade that changes a license or
introduces an unreviewed transitive dependency requires a new release review; a vulnerability-free
result is not itself a license approval.

## Incident response and disaster recovery

For a worker failure, stale device, pull error, database outage, backup failure, authorization event,
or recovery exercise, record UTC time, request/job correlation ID, sanitized error category,
deployment SHA, migration head, affected organization/device identifiers where necessary, and backup
checksum where relevant. Never record credentials, biometric payloads, bank details, national
identity values, session/CSRF tokens, or raw request bodies.

Recovery order is: contain writes, preserve evidence, verify/restore to an isolated database, verify
migration head and a known business record, run reconciliation, run smoke checks, obtain operator
approval, then re-enable traffic/workers. Roll back application code only with schema compatibility
confirmed; do not downgrade a production schema destructively as an improvised rollback.

## External administration exception

GitHub `main` protection/ruleset work is tracked separately in issue #39. The connected remediation
integration cannot write repository-administration settings. Baseline coding can be complete while
#39 remains open, but production governance is not complete until GitHub reports the required ruleset
or branch protection as active.
