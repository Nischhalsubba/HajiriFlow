# Contributing to HajiriFlow

Thank you for helping build HajiriFlow. The project handles attendance evidence and will eventually influence payroll, so correctness, authorization, auditability, and privacy take priority over speed.

## Before starting

Read:

- [README](README.md)
- [Product scope](docs/PRODUCT_SCOPE.md)
- [Feature matrix](docs/FEATURE_MATRIX.md)
- [Implementation sequence](docs/IMPLEMENTATION_SEQUENCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Independent development policy](docs/INDEPENDENT_DEVELOPMENT.md)

Use an existing issue when possible. For new work, describe the user outcome, affected permissions, data changes, audit expectations, and acceptance criteria before implementation.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e '.[dev]'
cp .env.example .env
docker compose up -d db
alembic upgrade head
```

Run the API:

```bash
uvicorn hajiriflow.main:app --reload
```

Run the worker separately:

```bash
python -m hajiriflow.worker
```

## Branch naming

Use focused names:

- `feature/employee-import`
- `fix/session-revocation`
- `security/export-scope-check`
- `docs/payroll-runbook`
- `refactor/device-adapter-boundary`

## Pull request expectations

A pull request should contain one vertical slice or one infrastructure concern. Include:

1. User outcome and scope
2. Architecture or schema impact
3. Permission and organization-scope behavior
4. Audit behavior
5. Privacy and sensitive-data handling
6. Tests and validation evidence
7. Documentation updates
8. Migration and rollback notes when applicable

## Required validation

```bash
ruff check .
pytest --cov=hajiriflow --cov-report=term-missing
```

Validate changed JavaScript files with Node:

```bash
node --check site/assets/<changed-file>.js
```

GitHub Actions is the authoritative full-repository validation.

## Database changes

- Use Alembic for every schema change.
- Do not silently continue after migration failure.
- Add constraints for business invariants rather than relying only on UI validation.
- Include upgrade and downgrade behavior.
- Never put real employee, payroll, biometric, or device-secret data in migrations or fixtures.

## Authorization changes

- Permissions are deny-by-default.
- Unknown roles grant no access.
- Test allowed and denied cases.
- Test organization scope and object ownership.
- Apply the same rules to screens, APIs, exports, and background jobs.

## Attendance and payroll changes

- Raw biometric evidence is immutable.
- Corrections are additive and attributable.
- Attendance calculations must be deterministic and explainable.
- Locked periods require explicit correction and reapproval.
- Payroll calculations require fixed examples, boundary tests, and reconciliation to the smallest supported currency unit.

## Frontend changes

- Keep controls keyboard accessible.
- Preserve visible focus states.
- Support loading, empty, error, success, disabled, and responsive behavior.
- Respect `prefers-reduced-motion`.
- Do not hide operational consequences behind vague copy.
- Do not present simulated or browser-local behavior as authoritative server state.

## Independent implementation

Do not copy third-party code, templates, CSS, JavaScript, migrations, documentation wording, screenshots, logos, or assets without a compatible license and required attribution. Publicly observable product behavior may be translated into independently written requirements and original implementation.

## Security reports

Follow [SECURITY.md](SECURITY.md). Do not disclose sensitive vulnerabilities or real data in public issues.
