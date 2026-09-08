# HajiriFlow production readiness

Last repository reconciliation: **2026-09-08**.

This document separates repository controls from external production evidence. A checked box here is not permission to describe HajiriFlow as production-ready unless every required external item is also satisfied.

## Repository controls implemented

- [x] Production authentication/session APIs with CSRF and scoped permissions.
- [x] Organization-scoped workforce, attendance, payroll, device, biometric, and reporting APIs.
- [x] Append-only attendance/payroll/business audit history with high-risk audit completeness requirements.
- [x] Maker/checker payroll approvals and additive reversal workflow.
- [x] Device credentials encrypted at rest and never returned by management APIs.
- [x] Biometric template/image/scan ingestion rejected; consent and deletion governance recorded separately.
- [x] Device pull scheduler with bounded retry, per-device PostgreSQL advisory lock, atomic attempt persistence, and cursor continuity.
- [x] Real PostgreSQL migration roundtrip and device-concurrency/atomicity CI jobs.
- [x] Privacy-safe request observability and request/audit correlation IDs.
- [x] Internal attack-surface review contracts.
- [x] Production frontend fails closed rather than presenting generated operational state as live data.
- [x] Salary/payroll authorization isolation is executable in tests.
- [x] WCAG 2.2 AA interaction regression layer with real Chromium keyboard/focus evidence.
- [x] Root security policy and CODEOWNERS.
- [x] Manual production smoke workflow.
- [x] Production operations/backup/restore/rollback runbook.
- [x] Frontend CSP, frame denial, MIME-sniffing protection, referrer policy, permissions policy, and HSTS configuration.
- [x] Release workflow validates exact current `main`, code/tests, PostgreSQL migration/device integrity, production runtime generation, and API health/readiness before authorizing a frontend deploy.

## Observed external state on 2026-09-08

The connected services showed the following state during this review:

- GitHub `main` was **not protected**.
- The connected Netlify project existed and served `hajiriflow.netlify.app`.
- The published Netlify production deploy was from **2026-08-17**, commit `044bb7a026b77c8fb789c22c2375644408792a92`, so it did not contain the current remediation work.
- The connected Netlify project returned **no configured environment variables**, so the required production `HAJIRIFLOW_API_BASE_URL` was not present.

Treat this as an audit snapshot, not a permanent truth. Re-check the external systems before every launch/release decision.

## External/manual blockers before a production-readiness claim

### 1. Real production application stack

- [ ] Deploy the reviewed FastAPI application to the real production provider.
- [ ] Deploy the worker from the same reviewed release lineage.
- [ ] Provision/configure supported PostgreSQL with encrypted transport and provider access controls.
- [ ] Configure real secrets/environment values outside source control.
- [ ] Verify `/health` reports `environment=production` and `/ready` returns ready.

### 2. Frontend production integration

- [ ] Configure Netlify `HAJIRIFLOW_API_BASE_URL` to the real reviewed HTTPS API origin.
- [ ] Complete the authoritative API-backed operational frontend provider; generated operational data must remain locked until that integration exists.
- [ ] Release the current validated `main` through `Release Production`.
- [ ] Confirm the intended Netlify deploy is live.
- [ ] Run `Production Smoke` against the real frontend/API origins and retain the successful run as release evidence.

### 3. Repository protection

- [ ] Enable a GitHub branch protection rule or ruleset for `main`.
- [ ] Require pull requests for code/configuration changes.
- [ ] Require the general CI and Security checks before merge.
- [ ] Block force pushes and deletion.
- [ ] Restrict bypasses. If the empty `[deploy]` release authorization commit is blocked, grant only the release integration the minimum required bypass.
- [ ] When a second independent maintainer exists, require an approving review and consider Code Owner review for high-risk paths.

CODEOWNERS now documents ownership, but CODEOWNERS alone does not enforce review.

### 4. Backup and recovery evidence

- [ ] Enable/verify the production database provider's managed backup/PITR policy.
- [ ] Create a current logical PostgreSQL archive where policy requires it.
- [ ] Perform a restore rehearsal into an isolated non-production database.
- [ ] Run migration-head, health/readiness, and non-destructive validation against the restored copy.
- [ ] Record restore duration, backup identifier, result, and operator.
- [ ] Verify the actual API hosting provider's application rollback procedure and a previous immutable revision/artifact.
- [ ] Verify the Netlify previous-deploy rollback path.

### 5. Independent security validation

- [ ] Independent authorization/tenant/object-scope test.
- [ ] Independent biometric/privacy review, including deletion and vendor boundary.
- [ ] Independent payroll-control review, including maker/checker, locked periods, exports, reversals, and audit evidence.
- [ ] Remediate findings and repeat affected tests.

Internal self-review and CI cannot satisfy the word **independent**.

### 6. Real hardware and payroll policy inputs

Only required when these capabilities are intentionally activated:

- [ ] Select actual supported attendance/biometric hardware.
- [ ] Review and implement the real vendor adapter against the documented adapter boundary.
- [ ] Validate network segmentation, device credential rotation, failure recovery, and deletion behavior on real hardware.
- [ ] Supply authoritative Nepal payroll/tax policy inputs before claiming tax calculation correctness.
- [ ] Supply the actual bank/payment export specification before implementing bank files.

Do not invent these inputs to satisfy a checklist.

### 7. Legal/repository administration

- [ ] Repository owner chooses the appropriate software license, if public licensing is intended.

No license is added automatically because licensing is an owner/legal decision.

## Launch decision

HajiriFlow's internally actionable repository remediation can be considered complete only when the repository checklist and open-PR sweep are clean. **Production readiness remains blocked** until the required external infrastructure, live integration, branch protection, recovery evidence, and independent security validation above are complete.
