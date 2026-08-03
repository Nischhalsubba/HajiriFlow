# Baseline Feature Matrix

Status values:

- `FOUNDATION`: supporting infrastructure exists.
- `PLANNED`: accepted baseline requirement, not yet implemented.
- `IN PROGRESS`: active implementation branch or pull request.
- `VERIFIED`: implemented, tested, documented, and accepted.

| ID | Capability | Baseline acceptance requirement | Status | Depends on |
|---|---|---|---|---|
| HF-001 | Secure authentication | Revocable sessions, password lifecycle, throttling, CSRF, audit | PLANNED | Database |
| HF-002 | Multi-role RBAC | Deny by default; page, API, export, job, and object checks | PLANNED | HF-001 |
| HF-003 | Web account administration | Create, edit, activate, deactivate, employee link, search | PLANNED | HF-001, HF-002 |
| HF-004 | Company profile | Configurable report identity and contact details | PLANNED | Database |
| HF-005 | Organization hierarchy | Directorate, department, section, unit CRUD with validation | PLANNED | HF-002 |
| HF-006 | Employee master | Full profile, status lifecycle, filters, export, soft restore | PLANNED | HF-005 |
| HF-007 | Shift definitions | Start/end, breaks, grace, overnight support | PLANNED | HF-005 |
| HF-008 | Effective shift assignments | Employee or org scope with effective date ranges | PLANNED | HF-006, HF-007 |
| HF-009 | Device registry | Vendor-neutral records, encrypted secret, status, diagnostics | PLANNED | HF-002 |
| HF-010 | Device adapter contract | Capability-based adapter interface independent of vendor | PLANNED | HF-009 |
| HF-011 | Connection diagnostics | Test connection and show actionable sanitized result | PLANNED | HF-010 |
| HF-012 | Pull scheduling | PostgreSQL schedule, worker execution, distributed lock | PLANNED | HF-009, worker |
| HF-013 | Immediate pull | Authorized command with job status and no web-process work | PLANNED | HF-012 |
| HF-014 | Pull session history | Per-device counts, timings, status, warnings, errors | PLANNED | HF-012 |
| HF-015 | Historical pull | Authorized date-range ingestion where device capability allows | PLANNED | HF-012 |
| HF-016 | Device users | Paginated device registration inventory | PLANNED | HF-010 |
| HF-017 | Employee-device mapping | Link many device registrations to one employee | PLANNED | HF-006, HF-016 |
| HF-018 | Device comparison and sync | Preview unknown/missing users and execute approved actions | PLANNED | HF-017 |
| HF-019 | Bulk device enrollment | Validate and push approved identities to selected devices | PLANNED | HF-018 |
| HF-020 | Device-to-device migration | Dry-run and audited compatible user migration | PLANNED | HF-018 |
| HF-021 | Encrypted device archive | Backup and restore supported identity/biometric payloads | PLANNED | HF-010, encryption |
| HF-022 | Immutable punch ingestion | Append-only events, idempotency, UTC, source metadata | PLANNED | HF-012, HF-017 |
| HF-023 | Unlinked punch review | Retain and map evidence without loss | PLANNED | HF-022 |
| HF-024 | Attendance event explorer | Filter, paginate, inspect, Excel, PDF | PLANNED | HF-022, HF-002 |
| HF-025 | Manual event entry | Additive correction with reason and approval metadata | PLANNED | HF-006, HF-022 |
| HF-026 | Spreadsheet attendance import | Template, preview, row validation, result report | PLANNED | HF-025 |
| HF-027 | Attendance day remarks | Non-destructive notes with audit | PLANNED | HF-006 |
| HF-028 | AD/BS date services | Bidirectional conversion and month boundaries | PLANNED | Foundation |
| HF-029 | Holiday types and calendar | Configurable categories, monthly calendar, working-day count | PLANNED | HF-028, HF-005 |
| HF-030 | Leave-type configuration | Entitlement, caps, carry, paid, color, half-day, eligibility | PLANNED | HF-005 |
| HF-031 | Leave balances | Opening, earned, carried, used, pending, available by BS year | PLANNED | HF-030, HF-006 |
| HF-032 | Leave allocation | Previewed, repeat-safe annual allocation | PLANNED | HF-031 |
| HF-033 | Leave application workflow | Apply, approve, reject, cancel, working-day calculation | PLANNED | HF-029, HF-031, HF-002 |
| HF-034 | Employee leave self-service | Own balances, requests, and statuses only | PLANNED | HF-033, HF-001 |
| HF-035 | Field duty / kaaj | Paid/unpaid records, approval, filters, exports | PLANNED | HF-006, HF-029 |
| HF-036 | Attendance calculation engine | Shift-aware deterministic day result with explanation trace | PLANNED | HF-008, HF-022, HF-029, HF-033, HF-035 |
| HF-037 | Duplicate-event policy | Configurable near-event grouping without raw deletion | PLANNED | HF-036 |
| HF-038 | Overnight attendance | Correct workday resolution across midnight | PLANNED | HF-036 |
| HF-039 | Daily status report | Present, absent, leave, field duty, drilldown, exports | PLANNED | HF-036 |
| HF-040 | Daily absence report | Expected workers minus valid statuses, non-workday handling | PLANNED | HF-036 |
| HF-041 | Department coverage | Summary, percentages, status drilldowns, exports | PLANNED | HF-036, HF-005 |
| HF-042 | Employee monthly detail | Daily plan/evidence/result table and print one/all | PLANNED | HF-036 |
| HF-043 | Monthly workforce summary | Per-employee totals and leave breakdown | PLANNED | HF-036 |
| HF-044 | Hajiri register | BS employee-day matrix, codes, totals, A3/Excel | PLANNED | HF-036, HF-028 |
| HF-045 | Attendance-to-salary worksheet | Attendance totals with approved compensation references | PLANNED | HF-036, HF-050 |
| HF-046 | Employee attendance self-service | Own daily and monthly attendance with punch drilldown | PLANNED | HF-036, HF-001 |
| HF-047 | Fiscal-year lifecycle | BS/AD dates and upcoming/active/closed/locked states | PLANNED | HF-028, HF-002 |
| HF-048 | Earning-head catalog | Fixed/percentage and payment frequency policy | PLANNED | HF-047 |
| HF-049 | Deduction catalog | Fixed/percentage, pretax, cap, enrollment | PLANNED | HF-047 |
| HF-050 | Employee compensation setup | Effective-dated heads, deductions, tax profile, OT policy | PLANNED | HF-006, HF-048, HF-049 |
| HF-051 | Holiday OT rules | Employee and org-scoped premium policy | PLANNED | HF-029, HF-050 |
| HF-052 | Tax slab sets | Fiscal-year versioning, taxpayer categories, confirmation | PLANNED | HF-047 |
| HF-053 | Payroll attendance review | Reconcile approved attendance before generation | PLANNED | HF-036, HF-047 |
| HF-054 | Payroll generation | Persist immutable identity, attendance, policy, and money snapshots | PLANNED | HF-050, HF-052, HF-053 |
| HF-055 | Payroll lifecycle | Preview, approve, post, reverse, close, lock | PLANNED | HF-054, HF-002 |
| HF-056 | Payslips | Individual and batch print/PDF with transparent calculation | PLANNED | HF-054 |
| HF-057 | Annual payroll summary | Employee annual totals and Excel export | PLANNED | HF-054 |
| HF-058 | Tax preview and projection | Explain projected tax and reconciliation | PLANNED | HF-052, HF-054 |
| HF-059 | Employee payroll self-service | Own payslips and annual totals only | PLANNED | HF-056, HF-001 |
| HF-060 | Administrative audit | Append-only, filterable, redacted before/after events | PLANNED | Database, HF-001 |
| HF-061 | Operational dashboard | Device, pull, attendance, exception, and job indicators | PLANNED | HF-014, HF-036 |
| HF-062 | Structured logs and metrics | Request/job correlation, alerts, no sensitive payloads | FOUNDATION | Foundation |
| HF-063 | Database migrations | Versioned, transactional, fail deployment on failure | PLANNED | Database |
| HF-064 | Backup and restore | Linux/Windows procedures and verified restore test | PLANNED | Database |
| HF-065 | Deployment and services | Docker local; documented Linux web/worker services | FOUNDATION | Foundation |
| HF-066 | CI quality gates | Compile, lint, tests, migration check, security checks | FOUNDATION | Foundation |

## Completion accounting

- Total baseline capabilities: 66
- Foundation capabilities at project bootstrap: 4
- Remaining capabilities require implementation and verification.

The matrix is updated in the same pull request that changes a feature's status. “Mostly works on my laptop” is not one of the status values, despite its historic popularity.
