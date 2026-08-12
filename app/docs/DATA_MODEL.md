# Baseline Domain Model

This is the conceptual model, not a promise that every concept becomes a separate table. Migrations may normalize or combine structures where constraints and query patterns justify it.

## Identity and access

- `UserAccount`: username, password hash, status, linked employee, password state.
- `Role`: named bundle of responsibilities.
- `Permission`: atomic action such as `attendance.read` or `payroll.run.generate`.
- `UserRole`: effective-dated role assignment with optional organization scope.
- `Session`: revocable login session and security metadata.
- `AuditEvent`: redacted append-only record of an administrative action.

## Organization and people

- `CompanyProfile`
- `OrganizationNode`: hierarchical node with type directorate, department, section, or unit.
- `Employee`: workforce identity and lifecycle.
- `EmployeeOrganizationAssignment`: effective-dated placement.
- `Shift`
- `ShiftAssignment`: effective-dated employee or organization policy assignment.

## Calendar, leave, and field duty

- `HolidayType`
- `Holiday`: date, scope, type, and optional working-rule override.
- `LeaveType`
- `LeaveBalance`: annual ledger summary supported by transactions.
- `LeaveLedgerEntry`: allocation, carry, usage, reversal, or correction.
- `LeaveRequest`: requested range, partial-day details, decision, and history.
- `FieldDutyRequest`: paid/unpaid official duty and approval history.

## Devices and ingestion

- `Device`: vendor-neutral connection and capability metadata.
- `DeviceSchedule`: database-backed pull schedule.
- `DeviceJob`: pull, sync, push, archive, restore, or migration operation.
- `DeviceUser`: normalized external registration observed on a device.
- `EmployeeDeviceIdentity`: mapping between employee and device registration.
- `BiometricEnvelope`: encrypted, access-controlled template payload when supported.
- `PunchEvent`: immutable raw attendance evidence.
- `IngestionIssue`: unlinked user, invalid time, duplicate candidate, or device warning.

## Attendance processing

- `ManualPunchRequest`: additive correction and approval state.
- `AttendanceRemark`: non-calculating day note.
- `AttendancePolicyVersion`: versioned rule inputs.
- `AttendanceDay`: calculated daily result and explanation trace.
- `AttendancePeriod`: review, approval, lock, correction, and reopen lifecycle.

## Payroll

- `FiscalYear`
- `EarningHead`
- `DeductionType`
- `TaxSlabSet` and `TaxSlabBand`
- `EmployeeCompensationAssignment`
- `HolidayOvertimeRule`
- `PayrollRun`: one period and lifecycle state.
- `PayrollItem`: employee identity and totals snapshot.
- `PayrollAttendanceSnapshot`
- `PayrollEarningLine`
- `PayrollDeductionLine`
- `PayrollTaxLine`
- `PayrollAdjustment`

## Core invariants

1. Punch events are append-only.
2. Manual corrections never overwrite device evidence.
3. Every external device identity maps to at most one active employee for a given effective time.
4. Organization and shift assignments cannot overlap inconsistently for the same scope.
5. Leave and field-duty decisions retain their history.
6. Locked attendance cannot change without a recorded reopen or correction workflow.
7. Posted payroll snapshots are immutable; reversal creates compensating records.
8. Sensitive secrets and biometrics are encrypted and never placed in ordinary audit JSON.
9. All instants are stored in UTC; business dates are derived using the configured Nepal timezone and stored only where indexing or historical stability requires it.
10. Monetary values use exact decimal types, never binary floating point.
