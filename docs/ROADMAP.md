# Roadmap

The complete accepted baseline is documented in [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) and tracked in [FEATURE_MATRIX.md](FEATURE_MATRIX.md). Delivery follows [IMPLEMENTATION_SEQUENCE.md](IMPLEMENTATION_SEQUENCE.md).

## Foundation: complete

- FastAPI web process and separate worker process.
- Configuration validation.
- PostgreSQL development environment.
- CI, linting, tests, health, and readiness checks.
- Architecture principles and production safety constraints.

## Current milestone: persistence, identity, and authorization

- Versioned database migrations.
- PostgreSQL pool and transaction lifecycle.
- Users, roles, permissions, scoped user-role assignments, sessions, and audit events.
- Login, logout, password change, account lifecycle, throttling, and CSRF.
- Deny-by-default page, API, export, object, and job authorization tests.

## Remaining baseline milestones

1. Organization, employees, shifts, and company settings.
2. BS calendar, holidays, leave, and field duty.
3. Device platform, scheduler, immutable raw evidence, and device identities.
4. Device sync, enrollment, migration, archive, and restore.
5. Manual corrections and the shared attendance engine.
6. Attendance reports and employee self-service.
7. Payroll policy, processing, payslips, and annual/tax outputs.
8. Production operations, monitoring, backup, restore, and security review.

## Release gate

Production deployment requires:

- a threat model and authorization review;
- tested backup restoration;
- permission tests for pages, APIs, exports, and worker actions;
- device integration tests against supported hardware;
- attendance reconciliation over a manually verified period;
- payroll reconciliation over a manually verified sample;
- migration, rollback, monitoring, and incident runbooks.
