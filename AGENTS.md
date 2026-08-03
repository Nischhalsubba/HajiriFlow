# HajiriFlow Agent Guide

This file defines repository rules for coding assistants, automation, and agent-driven pull requests.

## Product boundary

HajiriFlow is a Nepal-ready workforce platform covering identity, employees, organization structure, biometric devices, attendance evidence, leave, kaaj, reporting, self-service, audit, and payroll.

Read the product source of truth before changing code:

- `docs/PRODUCT_SCOPE.md`
- `docs/FEATURE_MATRIX.md`
- `docs/IMPLEMENTATION_SEQUENCE.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/INDEPENDENT_DEVELOPMENT.md`

## Non-negotiable invariants

1. Raw biometric punches are append-only.
2. Corrections are additive, attributable, and auditable.
3. PostgreSQL is the runtime source of device, schedule, employee, and policy configuration.
4. Device work runs outside the web request process.
5. Permissions are deny-by-default.
6. Unknown roles grant no access.
7. Screens, APIs, exports, and jobs enforce the same scope.
8. Audit payloads exclude or mask credentials, biometrics, identity numbers, bank details, and tokens.
9. Payroll consumes approved and locked attendance snapshots.
10. Device-specific behavior stays behind capability-based adapters.
11. Business-local dates use `Asia/Kathmandu`; instants are stored consistently.
12. Schema changes use Alembic and deployment fails on required migration failure.

## Independent development

Do not copy source code, templates, styles, documentation wording, tests, migrations, screenshots, assets, or distinctive internal structure from third-party projects without a compatible license and required attribution.

General capabilities and publicly observable behavior may be converted into independently written requirements and original implementation. Record third-party dependencies and media attribution.

## Change process

- Create a focused branch.
- Implement one vertical slice or infrastructure concern.
- Add positive, negative, boundary, and failure-path tests.
- Update documentation and the feature matrix when capability status changes.
- Open a pull request with user outcome, security, privacy, migration, audit, and validation notes.
- Do not merge failing CI.

## Backend guidance

- Keep domain logic outside route handlers.
- Use typed services and repositories at module boundaries.
- Avoid broad exception swallowing.
- Use transactions deliberately and savepoints where partial batch failure is acceptable.
- Never log secrets or full sensitive records.
- Validate organization and object scope before data access or mutation.

## Frontend guidance

- The public Netlify site is a frontend layer, not the authoritative database or biometric worker.
- Preserve keyboard access, focus treatment, responsive behavior, reduced motion, loading, empty, error, and retry states.
- Operational records should come from the data-provider boundary rather than HTML constants.
- Do not label browser-local or simulated actions as production-complete.
- External images and animation libraries must fail without breaking core workflows.

## Device guidance

- Isolate failures per device.
- Use distributed locks for pulls.
- Make ingestion idempotent.
- Sanitize device errors.
- Require preview, permission, result record, and audit for device writes, enrollment, migration, archive, and restore.

## Payroll guidance

- Store monetary values without floating-point ambiguity.
- Version policy and tax inputs.
- Persist calculation snapshots and explanations.
- Require attendance review and lock before generation.
- Add fixed reconciliation fixtures and boundary tests.

## Validation

Run:

```bash
ruff check .
pytest --cov=hajiriflow --cov-report=term-missing
```

Run `node --check` for changed files in `site/assets/`. GitHub Actions validates the complete repository.
