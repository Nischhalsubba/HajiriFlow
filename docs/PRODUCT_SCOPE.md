# HajiriFlow Baseline Product Scope

This document defines the complete baseline product that HajiriFlow will deliver before optimization and advanced enhancements begin. The scope is intentionally broader than a biometric downloader: it covers workforce identity, device operations, attendance policy, leave, reporting, employee self-service, payroll, auditing, and operational recovery.

## Product goals

HajiriFlow must let a Nepal-based organization reliably answer five questions:

1. Who is employed and where do they belong in the organization?
2. What attendance evidence was received from each device or approved manual source?
3. How did policy convert that evidence into present, absent, leave, field-duty, late, early, and overtime outcomes?
4. Which outcomes were reviewed, corrected, approved, and locked?
5. How did approved attendance contribute to payroll and employee-facing records?

## Roles

The baseline supports multiple roles per account.

- **System administrator:** platform configuration, access control, integrations, audit, and recovery.
- **Attendance administrator:** devices, employees, attendance corrections, schedules, leave, holidays, and reports.
- **Attendance operator:** routine pulls, review queues, imports, and non-destructive attendance operations.
- **Leave approver:** leave and field-duty decisions for assigned organizational scope.
- **Payroll administrator:** fiscal years, compensation policies, payroll runs, approvals, and exports.
- **Report viewer:** read-only access to authorized organization-wide reports.
- **Employee:** own attendance, leave, field duty, profile, and payslips.

Unknown roles and unassigned permissions are denied.

## 1. Authentication, accounts, and access control

- Login and logout with secure server-side or revocable sessions.
- Password change, forced password change, account activation, and account deactivation.
- Login throttling and failed-login audit events.
- Multiple roles per user and organization-scoped permissions.
- Employee accounts linked to one employee profile.
- Administrator account management, search, filtering, and status changes.
- Permission checks on pages, APIs, exports, background jobs, and object-level access.
- No credentials or sensitive fields in audit payloads.

## 2. Dashboard and operational overview

- Current device reachability and last successful communication.
- Today's unique attendees and total received punches.
- Employees presently missing an expected punch or awaiting review.
- Recent pull jobs, failures, warnings, and duplicate-event counts.
- Recent attendance activity displayed in Nepal time with AD and BS dates.
- Quick links to pull now, review exceptions, and open reports, subject to permission.

## 3. Organization and employee master data

- Company identity, address, contact information, and report-header configuration.
- Hierarchy: directorate, department, section, and unit.
- Employee master profile with attendance ID, HR employee number, name, employment type, employment status, designation, grade/level, join date, contact details, and optional payroll identifiers.
- Organization, shift, and account assignment.
- Search, filters, server-side pagination, numeric attendance-ID sorting, CSV/Excel export, and print view.
- Soft deactivation and restoration; destructive deletion is exceptional and audited.
- Mapping of one employee to registrations on multiple physical devices.
- Identification and review of device users not yet linked to an employee profile.

## 4. Shift and attendance policy configuration

- Shift definitions with planned start, planned end, break duration, and cross-midnight support.
- Grace periods for late arrival and early departure.
- Effective-dated shift assignments to employees or organizational scopes.
- Weekly-off rules, including Saturday defaults and configurable exceptions.
- Attendance event labels such as entry, exit, break, overtime, and unknown.
- Duplicate-punch window configurable by policy.
- Default organization timezone fixed to `Asia/Kathmandu`, with UTC storage for instants.

## 5. Device registry and diagnostics

- Vendor-neutral device records with adapter type, network address, port, encrypted communication secret, protocol preference, timeout, site, and active status.
- Add, edit, deactivate, and remove devices under explicit permissions.
- Connection test with actionable diagnostics.
- Adapter capability display, such as user read/write, fingerprint export/import, event retrieval, and device-time operations.
- Last seen, last successful pull, firmware/model metadata where available.
- Per-device failure isolation so one device cannot block others.

## 6. Pull worker and scheduling

- Dedicated worker process separate from the web application.
- Configurable schedules stored only in PostgreSQL.
- Immediate pull command from the UI.
- Distributed lock preventing overlapping pulls for the same device.
- Idempotent ingestion with a deterministic uniqueness key.
- Pull-session history containing device, trigger, start/end, status, counts, warnings, and sanitized error details.
- Retry policy with bounded backoff and no infinite retry loops.
- Historical date-range pull for devices that retain older records.
- Structured application logs and health signals for monitoring.

## 7. Device user operations

- List users registered on each device.
- Compare device registrations with HajiriFlow employee mappings.
- Import an unknown device user into a review queue.
- Push an approved employee identity to selected devices.
- Bulk enrollment or bulk push across devices.
- Copy a supported user registration between compatible devices.
- Export an encrypted device archive of supported user data and biometric templates.
- Restore or migrate data only with explicit authorization, dry-run preview, and audit.
- Fingerprint and biometric payloads are encrypted and never displayed in logs or ordinary exports.

## 8. Raw attendance evidence

- Append-only punch events from devices.
- UTC event time plus derived Nepal-local AD and BS dates.
- Device, external user ID, mapped employee, event type, verification method, and ingestion metadata.
- Original raw value retained where useful for diagnostics.
- Duplicate detection without deleting evidence.
- Unlinked punches retained and surfaced for mapping.
- Search by date range, employee, attendance ID, device, source, and event type.
- Authorized Excel and PDF exports.

## 9. Manual attendance and correction workflow

- Add a missing attendance event with employee, date/time, event type, reason, and evidence note.
- Bulk import approved events from a documented spreadsheet template.
- Preview and validate imports before writing.
- Reject unknown employees, impossible dates, invalid ordering, and duplicate rows with row-level feedback.
- Corrections are additive; raw device evidence is never edited.
- Approval workflow for manual changes when policy requires it.
- Full audit history showing requester, approver, reason, previous calculated outcome, and resulting outcome.
- Day-level remarks that do not alter the underlying evidence.

## 10. Bikram Sambat and holiday calendar

- Bidirectional AD/BS conversion services and date-picker support.
- BS month metadata including valid days and AD boundaries.
- Configurable holiday categories, display codes, colors, and ordering.
- Monthly BS calendar view with working-day count.
- Add, edit, and deactivate holidays with optional organization scope.
- Public, festival, national, optional, company, and custom holiday categories.
- Holiday and weekly-off rules consistently applied to leave, attendance, reports, and payroll.

## 11. Leave management

- Configurable leave types with code, display label, color, annual entitlement, paid status, carry-forward rule, accumulation cap, half-day support, and employee eligibility.
- Employee opening balance, carried balance, earned amount, used amount, pending amount, and available balance by BS year.
- Annual allocation in bulk with preview and idempotency.
- Employee leave request with BS/AD date support, partial day, reason, and attachment metadata.
- Working-day calculation excluding configured weekly offs and holidays.
- Approval, rejection, cancellation, and deletion rules with scope-based permissions.
- Employee self-service list and current balance summary.
- Attendance reports display approved leave consistently.

## 12. Kaaj and field duty

- Record paid or unpaid official field duty independently from ordinary leave.
- Employee, date or date range, reason, location, approver, and evidence metadata.
- Approval workflow and organizational filtering.
- Field duty contributes to attendance and payroll according to configured policy.
- Dedicated list, filters, exports, and audit history.

## 13. Attendance calculation engine

- Normalize device and approved manual events into a single timeline per employee and workday.
- Deduplicate near-simultaneous events without removing raw records.
- Resolve effective shift, weekly off, holiday, approved leave, and field duty.
- Calculate first in, last out, worked minutes, planned minutes, break minutes, late arrival, early departure, early arrival, late departure, regular overtime, and holiday overtime.
- Handle overnight shifts and punches crossing midnight.
- Produce deterministic day status with a documented priority model.
- Preserve an explanation trace showing which rules produced each result.
- Recompute open periods safely; locked periods require an explicit correction and reapproval workflow.
- Optional persisted daily calculation cache for large installations.

## 14. Attendance reports

Every report uses the same attendance engine and permission scope.

### Attendance event explorer

- Filterable event list with AD/BS dates, device, source, employee, and event label.
- Excel and PDF export.

### Daily workforce status

- Present, absent, approved leave, field duty, and unresolved employees for one date.
- First in, last out, worked time, and punch-count drilldown.
- Department and name filters.
- Print, PDF, and multi-sheet Excel export.

### Daily absence register

- Employees expected to work but without attendance, approved leave, or field duty.
- Suppressed or clearly marked on non-working days.
- Search, print, PDF, and Excel export.

### Department coverage report

- Present, leave, field duty, absent, total, and attendance percentage per department.
- Expandable employee drilldown for each status.
- Print, PDF, and Excel export.

### Employee monthly detail

- One employee's daily planned time, observed punches, work duration, late/early values, overtime, leave, holiday, field duty, status, and notes.
- Cross-device punch consolidation and configurable duplicate window.
- Organization and employee filters.
- Print one employee or all selected employees.

### Monthly workforce summary

- Per-employee totals for working days, present days, absence, weekly off, holidays, leave by type, field duty, overtime, late arrival, and early departure.
- A4 landscape print, PDF, and Excel export.

### Hajiri register

- Employee-by-day matrix for a BS month using organization-configured short codes.
- Summary totals and overtime columns.
- Filters by organization, employment type, status, and employee.
- A3 landscape print and Excel export.

### Attendance-to-salary worksheet

- Attendance summary combined with approved compensation reference fields.
- Intended for review and reconciliation, not as the payroll ledger.
- Print, PDF, and Excel export.

## 15. Payroll configuration

- BS fiscal years with AD boundaries and lifecycle: upcoming, active, closed, locked.
- Earning-head catalog with fixed, percentage, monthly, annual, festival, or one-time behavior.
- Deduction catalog with fixed or percentage calculation, pretax flag, caps, and employee enrollment.
- Per-employee earning and deduction assignments with effective dates.
- Compensation policy fields including expected daily hours, overtime multiplier, marital/tax profile, and permitted adjustments.
- Holiday overtime rules scoped by employee or organization.
- Versioned tax slab sets by fiscal year and taxpayer category.
- Tax slab confirmation required before generation.
- All monetary rules stored as data, never hidden constants.

## 16. Payroll processing and outputs

- Pre-generation attendance review for a BS month.
- Generate a payroll run for eligible employees using a locked or approved attendance period.
- Persist employee identity, attendance, earning, deduction, tax, and policy snapshots.
- Itemized gross earnings, taxable income, deductions, tax, and net pay.
- Transparent calculation explanation per employee.
- Controlled adjustment, approval, posting, reversal, closing, and locking workflow.
- Individual payslip, batch payslip print/PDF, and employee self-service access.
- Annual employee summary and tax projection.
- Excel exports for attendance summary, annual summary, and tax projection.
- Bank-payment export is a later baseline subfeature after bank formats are confirmed.

## 17. Audit and accountability

- Append-only administrative audit events for configuration, identity, employee, leave, calendar, corrections, and payroll changes.
- Actor, action, object, timestamp, request ID, client metadata, reason, and redacted before/after changes.
- Filters by module, action, actor, object, and date.
- Dedicated pull-session and import-session records for bulk operations.
- Sensitive values, biometric templates, password hashes, communication secrets, bank numbers, and identity numbers are excluded or masked.
- Retention and access policies are configurable and documented.

## 18. Backup, migration, and operations

- PostgreSQL backup and restore scripts for Linux and Windows.
- Scheduled backup guidance and retention policy.
- Restore verification runbook.
- Application migration checklist for a new server.
- Docker-based local setup plus documented Linux service deployment.
- Worker and web health/readiness endpoints.
- Structured logs, metrics, alerts, and troubleshooting guidance.
- Database migrations are versioned and never silently skipped.

## Baseline completion rule

The baseline is complete only when every capability in this document is either:

- implemented with automated tests and user documentation; or
- explicitly marked as excluded by a recorded product decision.

A page shell, placeholder route, or untested button does not count as implementation. Software has enough decorative doors that open into drywall.
