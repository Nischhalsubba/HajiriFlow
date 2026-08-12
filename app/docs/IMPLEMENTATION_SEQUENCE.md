# Implementation Sequence

The baseline is delivered through dependency-ordered vertical slices. Each milestone ends with runnable software, migrations, permission tests, API or UI coverage, and user documentation.

## Milestone 1: Persistence, identity, and authorization

- Alembic migrations and PostgreSQL connection lifecycle.
- User, role, permission, user-role, session, and audit-event tables.
- Login, logout, password change, account activation, and throttling.
- Deny-by-default authorization helpers and object-scope foundation.
- CSRF protection and security headers.

**Exit test:** unknown roles cannot access any protected page, API, export, or job action.

## Milestone 2: Organization, employees, shifts, and company settings

- Company profile.
- Directorate, department, section, and unit hierarchy.
- Employee lifecycle and account linking.
- Shift definitions and effective assignments.
- Search, pagination, exports, and soft restoration.

**Exit test:** an employee's organization and shift can be resolved correctly for any effective date.

## Milestone 3: Calendar, BS dates, holidays, leave, and field duty

- AD/BS conversion service and month metadata.
- Holiday categories and calendar.
- Leave policy, balance, allocation, request, and approval.
- Half-day handling and working-day calculation.
- Paid/unpaid field duty workflow.
- Employee self-service for leave.

**Exit test:** the same date produces the same workday decision in leave, attendance, and report services.

## Milestone 4: Device platform and raw evidence

- Vendor-neutral adapter contract.
- Device registry, secret encryption, diagnostics, and capabilities.
- Worker schedule, immediate pull, distributed lock, retry, and pull sessions.
- Immutable idempotent punch ingestion.
- Device user inventory and employee mapping.

**Exit test:** repeating a pull produces no duplicate evidence and one failing device does not block another.

## Milestone 5: Device identity operations

- Compare device users with employee mappings.
- Import review queue and push operations.
- Bulk enrollment.
- Compatible device-to-device migration.
- Encrypted archive and controlled restore.

**Exit test:** every write to a device has a preview, authorization check, result record, and audit event.

## Milestone 6: Manual corrections and attendance engine

- Manual event entry and spreadsheet preview/import.
- Non-destructive corrections and day remarks.
- Duplicate policy, shift resolution, overnight workdays, leave, holiday, and field-duty integration.
- Daily outcome explanation trace.
- Open-period recomputation and locked-period correction rules.

**Exit test:** a fixed test calendar produces deterministic attendance outcomes and explanations across repeated runs.

## Milestone 7: Attendance reporting and self-service

- Event explorer.
- Daily status, absence, and department coverage.
- Employee monthly detail and monthly workforce summary.
- Hajiri register and attendance-to-salary worksheet.
- Employee attendance self-service.
- PDF, print, and Excel permission coverage.

**Exit test:** report totals reconcile to the shared engine and exports match the on-screen filtered scope.

## Milestone 8: Payroll policy and processing

- Fiscal years, earning heads, deductions, tax slabs, compensation assignments, and holiday OT.
- Attendance review and period approval/lock.
- Payroll generation with immutable snapshots.
- Approval, posting, reversal, closing, and locking.
- Payslips, annual summary, tax preview/projection, and employee self-service.

**Exit test:** a manually verified employee sample reconciles attendance, earnings, deductions, tax, and net pay to the paisa.

## Milestone 9: Production operations

- Operational dashboard, metrics, alerts, and sanitized diagnostics.
- Backup automation, restore verification, retention, and migration runbook.
- Linux web and worker services.
- Security review, dependency review, load test, and disaster-recovery exercise.

**Exit test:** a blank environment can be installed, restored from backup, verified, and safely rolled back using documentation alone.

## Pull request rules

- One vertical slice or one infrastructure concern per pull request.
- Every schema change uses a migration.
- Every permission change includes positive and negative tests.
- Every financial calculation includes fixed examples and boundary tests.
- Every export is checked for data-scope leakage.
- No feature is marked verified without documentation and acceptance evidence.
