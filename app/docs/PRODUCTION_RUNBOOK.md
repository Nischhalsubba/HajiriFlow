# HajiriFlow production operations runbook

This runbook describes the production operating contract for HajiriFlow. It does not provision infrastructure and it does not replace provider-specific disaster-recovery procedures.

## 1. Production topology

A complete production deployment has four independently observable components:

1. **Frontend** — the static HajiriFlow site, currently configured for Netlify.
2. **API** — the FastAPI application serving identity, workforce, attendance, device, biometric, payroll, reporting, `/health`, and `/ready` routes.
3. **Worker** — the database-backed device pull scheduler. Reviewed vendor adapters must be registered before real hardware can sync.
4. **PostgreSQL** — the authoritative application database.

The frontend must use a same-origin `/api` proxy whose upstream is the reviewed HTTPS API. Production builds fail when `HAJIRIFLOW_API_BASE_URL` is missing.

The operational workspace remains `integration-required` until a reviewed API-backed frontend data provider replaces generated browser operational state.

## 2. Required production configuration

Keep values in the deployment provider's secret/environment store. Do not commit them.

API/worker configuration includes:

- `HAJIRIFLOW_ENVIRONMENT=production`
- `HAJIRIFLOW_DATABASE_URL`
- `HAJIRIFLOW_SESSION_SECRET`
- `HAJIRIFLOW_COOKIE_SECURE=true`
- explicit HTTPS `HAJIRIFLOW_ALLOWED_ORIGINS`
- device credential key material and active key ID when device credentials are used
- worker schedule settings appropriate to the deployed environment

Frontend configuration includes:

- `HAJIRIFLOW_API_BASE_URL` set to the reviewed HTTPS API origin in the Netlify production environment.

Never put passwords, database URLs, device credentials, bank data, biometric material, or service tokens into workflow inputs, commit messages, logs, or issue bodies.

## 3. Pre-release gate

Before authorizing a production release:

1. The target commit is the current `main` head.
2. CI and Security are green for that code.
3. Relevant browser E2E has passed when frontend/identity paths changed.
4. PostgreSQL migration roundtrip and device-concurrency tests are green.
5. The real production API `/health` and `/ready` endpoints are HTTPS-reachable.
6. The production database has a recent verified backup.
7. The release owner has a rollback target for frontend and API.
8. No unresolved security finding affects the release.

The repository's `Release Production` workflow repeats the code/migration checks and preflights the supplied production API before it authorizes the single `[deploy]` release commit.

## 4. Database migration order

For a normal compatible release:

1. Create and verify a backup.
2. Put the API/worker into the provider's normal controlled deployment procedure.
3. Run `alembic upgrade head` once against the production database from the exact release artifact/revision.
4. Confirm `alembic current --check-heads` succeeds.
5. Start/roll the API and worker revision that was validated with that migration head.
6. Verify `/health` and `/ready` before exposing the new application revision broadly.
7. Publish the frontend only after its API upstream is healthy and ready.
8. Run the manual `Production Smoke` workflow against the deployed frontend and API.

Do not run an Alembic downgrade in production merely to match an application rollback. Schema rollback is a separate change requiring explicit data-loss/compatibility review.

## 5. Health and readiness

- `GET /health` proves the API process is alive and reports service/version/environment metadata. It does **not** query the database.
- `GET /ready` executes a database round trip and returns HTTP 503 when PostgreSQL is unavailable.

Monitoring should alert on sustained non-2xx readiness responses, elevated 5xx rates, repeated worker failures, and abnormal device pull failure/latency. Request logs are intentionally privacy-minimized and use request IDs for correlation.

## 6. Frontend rollback

Netlify deployments are atomic. When a frontend release is bad and a known-good previous deploy is still available:

1. Stop additional releases.
2. In Netlify, select the last known-good successful deploy.
3. Publish that deploy as the production version rather than rebuilding identical old code.
4. Re-run frontend/API smoke checks.
5. Record the rollback target, reason, affected commit/deploy, and incident timeline.

If auto-publishing is ever enabled later, remember that a subsequent Git-triggered production deploy can overwrite a manually restored deploy. The current repository intentionally keeps deploys deliberate.

## 7. API and worker rollback

The repository does not assume a specific API hosting provider. Roll back by selecting the previous **validated immutable application revision/artifact** using the real provider's documented rollback mechanism.

Before rollback, verify database compatibility. If the database migration is forward-compatible with the previous application revision, roll back the API/worker and run `/health` + `/ready` + smoke checks. If not, stop and prepare a reviewed forward-fix or explicit database recovery plan.

Never invent or guess an API revision identifier during an incident.

## 8. PostgreSQL backup

Use the production provider's managed backups/PITR when available. In addition, a logical backup can be produced with PostgreSQL's `pg_dump` using a non-plain archive format suitable for `pg_restore`.

Example operator pattern (run from a trusted host; keep credentials outside shell history/log output):

```bash
pg_dump --format=custom --no-owner --no-privileges --file=hajiriflow-YYYYMMDD-HHMM.dump "$DATABASE_URL"
pg_restore --list hajiriflow-YYYYMMDD-HHMM.dump >/dev/null
```

Store backups in access-controlled encrypted storage with a defined retention policy. Do not commit backup files to GitHub or upload them to issue/PR attachments.

## 9. Restore rehearsal

A backup is not considered verified only because `pg_dump` exited successfully. On a recurring schedule and before high-risk releases:

1. Provision an isolated empty PostgreSQL database using the same supported major version.
2. Restore the selected archive with `pg_restore` using the provider-approved ownership/role strategy.
3. Run Alembic head verification.
4. Start an isolated application revision against the restored database.
5. Run health/readiness and non-destructive smoke checks using synthetic/test identities.
6. Record backup timestamp, archive identifier, restore duration, verification result, and operator.
7. Destroy the rehearsal environment and its data according to retention policy.

Never restore a production backup into a developer laptop or public test service merely for convenience.

## 10. Device operations

Real biometric/device traffic must stay on the reviewed private network path. Device credentials are encrypted at rest and must not appear in API responses or logs.

- A device pull is serialized per device by a PostgreSQL advisory lock.
- Each pull persistence attempt is atomic; partial valid prefixes of a failed batch are rolled back before retry.
- Retries are bounded.
- The latest successful cursor is the resume point.
- Failure of one device must not block unrelated devices.
- Unsupported adapters remain unsupported until actual hardware/vendor requirements are reviewed.

Do not open device management ports to the public internet as a shortcut.

## 11. Incident evidence

For security/integrity incidents, preserve:

- release commit/deploy/revision identifiers;
- request IDs and privacy-safe request logs;
- immutable business audit events;
- attendance/payroll domain history where relevant;
- device pull session identifiers and safe failure codes;
- migration head and database backup identifiers;
- production smoke results.

Do not copy sensitive payloads into incident chat, issues, or CI logs.

## 12. Release completion

A release is complete only when:

- frontend is serving the intended deploy;
- API `/health` is healthy;
- API `/ready` is ready;
- expected security headers are present;
- production smoke succeeds;
- no generated operational browser data is presented as authoritative production state;
- monitoring shows no new release-related error pattern.

## 13. Known external requirements

Repository automation cannot satisfy these by itself:

- provisioning the real FastAPI/worker/PostgreSQL production environment;
- supplying the real HTTPS API URL to Netlify;
- enabling repository branch/ruleset protection with appropriate bypass policy;
- executing and retaining evidence of a real backup/restore rehearsal;
- independent authorization, biometric/privacy, and payroll-control security testing;
- selecting and validating concrete hardware adapters;
- supplying authoritative payroll/tax/bank rules and formats;
- choosing the repository's legal license.
