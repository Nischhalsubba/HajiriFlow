# Attendance, leave and payroll exception test matrix

## Applicability
The application lives under `app/`, using Python >=3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, `nepali-datetime`, pytest and Ruff according to `app/pyproject.toml`. This document is a **proposed verification contract** for implementations of attendance, leave, reporting and payroll; it does not assert each flow is already implemented.

## Deterministic fixtures
Use synthetic employee identifiers, isolated test tenants and controlled timestamps. Record explicit time zone (Nepal uses UTC+05:45), calendar conversion library version, local date and UTC timestamp. Never put production employee names, credentials, salary statements or attendance history in test output or PR screenshots.

## Exception matrix
| Case | Condition | Expected class of outcome |
| --- | --- | --- |
| Duplicate check-in | Same person/date/idempotency key | Reject duplicate or safely return existing record |
| Clock skew | Device time differs from trusted server | Server-controlled validation and explainable feedback |
| Overnight shift | Crosses local midnight | Shift-aware date attribution, not silent truncation |
| Calendar boundary | BS year/month and Gregorian rollover | Reproducible conversion in stored and displayed views |
| Leave overlapping attendance | Approved/denied/pending request | Consistent business rule and visible reason |
| Retroactive correction | Authorized correction after payroll freeze | Permission check, reason, audit trail, no silent rewrite |
| Multi-tenant record access | Actor queries a different employer | Deny and avoid side-channel disclosure |
| Role mismatch | Employee requests manager/admin action | Reject securely; log non-sensitive reason |
| Export/report | Empty or large timesheet, failed storage | Explicit error or complete result; no partial silent success |
| Payroll calculation | Leave, deductions, rounding, adjustments | Documented deterministic rule, decimal precision and review |
| Network retry | Repeated client request | Safe idempotency and consistent user-facing status |

These are scenarios for business-rule acceptance; do not treat suggested outcomes as proof of current domain implementation.

## Local verification workflow
```bash
cd app
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
```

Use an isolated virtual environment and configured test-only PostgreSQL services where required. Apply migrations to a disposable database and assert tenant isolation before integration checks. Never run a destructive fixture against live data.

## Review acceptance
- [ ] Scenario owner approves policy for leave, overtime, holidays, shifts and payroll periods.
- [ ] Time-zone and BS/AD conversion round trips have boundary assertions.
- [ ] Records record actor, action, timestamp and justification where required.
- [ ] Corrective actions use permission checks, concurrency control and auditable changes.
- [ ] Employee-facing messages show what happened and how to resolve it, without leaking sensitive data.
- [ ] Exports do not mix employers or retain hidden personal rows.
- [ ] Regression tests and migration safety reviewed.
- [ ] No real credentials or payroll values included in repository evidence.

## Test evidence
```text
PR and reviewed operation:
Synthetic fixture and policy reference:
Python, database and conversion-library versions:
Test command / result:
Cross-tenant / unauthorized checks:
BS/AD rollover and rounding cases:
Performance or concurrency note:
Open defects / owner / rollback:
```

## Release boundary
Automated unit tests alone do not establish compliance with labor law, contract terms, or payroll accuracy. Obtain appropriate domain and legal review of actual business rules before production payroll use.
