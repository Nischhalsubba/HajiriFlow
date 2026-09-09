# Deterministic attendance engine v2

The v2 attendance engine is HajiriFlow's authoritative calculation contract for new reporting and payroll work. It merges immutable device punches with approved additive manual evidence, resolves the effective workforce/calendar context, and persists both a compact attendance record and an explanation-rich detail record.

The legacy attendance correction endpoints remain available for backward compatibility, but new missing-punch workflows should use manual attendance evidence so recalculation is driven by an auditable event timeline rather than by editing raw device data.

## Inputs

A calculation is identified by organization, employee, and work date. The engine resolves:

- the effective employee shift for that date, falling back to the employee's primary organization-node shift;
- organization attendance policy, including duplicate tolerance and pre/post-shift capture windows;
- immutable mapped device punches with `in` or `out` labels;
- approved manual attendance events;
- configured weekends and active non-optional holidays;
- approved leave and field duty; and
- whether the requested work date is in a locked attendance period.

Raw device punches are never updated or deleted. Manual evidence is additive and has a lifecycle of `pending`, `approved`, `rejected`, or `revoked`.

## Workday and overnight resolution

For a normal shift, the capture window starts before scheduled start and ends after scheduled end using organization-configured margins. If shift end is less than or equal to shift start, the scheduled end belongs to the following local calendar day. This keeps an overnight shift as one HajiriFlow workday instead of splitting it at midnight.

Without an effective shift, the capture window is the Nepal-local calendar day and shift-derived metrics are zero.

All instants are compared as timezone-aware values and persisted in UTC. Local schedule calculations use the organization's timezone, which defaults to `Asia/Kathmandu`.

## Duplicate policy

Device and approved manual events are sorted into one timeline. Events of the same type that occur within `duplicate_window_seconds` are grouped for calculation, with device evidence taking precedence when device and manual evidence occur at the same instant. Grouping never removes the source rows. The detail record stores `duplicate_event_count` so the decision is visible to operators and reports.

## First-in / last-out and metrics

The first retained `in` event becomes check-in and the last retained `out` event becomes check-out. An out event before the selected in event is not used as a valid pair and is recorded in the explanation trace.

When a valid pair exists, worked minutes equal elapsed minutes minus the configured shift break, floored at zero. The engine also calculates:

- planned minutes;
- late arrival after shift grace;
- early arrival;
- early departure before end minus grace;
- late departure after scheduled end;
- regular overtime as worked minutes above planned minutes on a normal workday; and
- holiday overtime as all worked minutes on a holiday or configured weekly off.

## Status priority

The base evidence status is `present`, `partial`, or `absent`. The final day status uses this deterministic priority:

1. approved field duty;
2. approved full-day leave;
3. active non-optional holiday;
4. configured weekly off;
5. evidence status.

An approved half-day leave is included in the explanation trace. When no attendance evidence exists on that half-day, the day is `partial` rather than fully absent.

The engine still computes observed punch metrics on holiday/leave/field-duty days, so evidence is never hidden by the status decision.

## Explanation and deterministic fingerprint

Every calculated detail contains an explanation trace with shift resolution, normalized event count, duplicate count, first-in/last-out decision, applicable leave/field-duty/holiday/weekly-off rules, and the final status-priority decision.

The input fingerprint is SHA-256 over the engine version, employee/date, effective shift values, attendance-policy values, normalized source event identifiers/times/types, and calendar/leave/field-duty references. A second calculation with the same fingerprint and engine version returns the existing result without incrementing the source revision. This makes the same evidence and policy inputs repeat-safe.

## Manual evidence approval and reversal

Manual events require a reason and timezone-aware timestamp. By default they require independent approval: the requester cannot approve their own event. Organizations may explicitly disable that requirement in attendance policy. Approved manual evidence can be revoked with a reason; revocation changes only the manual evidence status and leaves every device punch untouched.

Manual evidence cannot be added, approved, or revoked inside a locked period until that period is explicitly reopened.

## Spreadsheet import

The template endpoint returns `hajiriflow-manual-attendance.xlsx` with these columns:

- `employee_code`
- `event_time`
- `event_type`
- `reason`
- `evidence_note`

`event_time` may be an Excel date/time cell or Nepal-local `YYYY-MM-DD HH:MM` text. Preview accepts at most 2 MiB and 5,000 non-empty rows. It validates unknown employees, invalid event types/times, blank reasons, locked periods, out-of-order rows for the same employee, duplicates within the workbook, and existing matching pending/approved manual evidence.

Preview writes no attendance evidence. It stores a content hash plus row-level normalized data and validation errors. Re-uploading identical content for the same organization returns the existing preview rather than creating a second import.

Strict imports cannot be applied while any row is invalid. Non-strict imports apply only valid rows. Applying an import requires attendance approval permission and, when independent approval is enabled, a different user from the preview requester. Every applied row becomes an approved manual attendance event linked to its import session and row number.

## Day remarks

Attendance day remarks are append-only contextual notes. They do not alter evidence or calculation inputs. SQLAlchemy guards reject update and delete attempts so history is preserved.

## Locked periods

An attendance approver may lock a date range with a reason. Active lock ranges cannot overlap. The engine rejects ordinary recalculation while a date is locked, and manual evidence approval/revocation is blocked. Reopening requires a second reason and records the actor and timestamp. This gives payroll/review workflows an explicit boundary instead of silently recalculating closed attendance.

## Reporting and payroll contract

New attendance reports and payroll generation should read `attendance_record_details` (or the v2 engine API) for day status, planned/break/early/overtime metrics, explanation trace, and deterministic fingerprint rather than reimplementing policy rules independently.
