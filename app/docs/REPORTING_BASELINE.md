# Attendance reporting, exports, and employee self-service

HajiriFlow reports are read-only views over persisted `attendance-v2` results. Report GET routes do not recalculate attendance and do not reproduce attendance business rules independently.

## Shared status model

Daily, monthly, department, employee-detail, and Hajiri reports read `AttendanceRecordDetail.day_status` when a v2 result exists. The shared statuses are `present`, `partial`, `absent`, `leave`, `field_duty`, `holiday`, and `weekly_off`. When no calculated record exists, the reporting service can still classify approved leave, approved field duty, organization holidays, and configured weekly-off days without converting those non-working states into absences; otherwise the row is `uncalculated`.

The daily absence report contains only employees whose resolved day status is `absent`. Approved leave, field duty, holidays, weekly off, and uncalculated rows are excluded from absence counts.

## Evidence and drilldown

The attendance event explorer merges immutable device punches with manual attendance evidence. The response is deliberately privacy-minimized: it includes identifiers needed to trace a result, timestamps, source, event type, verification method, source fingerprint, and manual-event lifecycle status, but not device-user identifiers or raw evidence payloads.

Employee-day drilldown is employee-scoped and includes both device and manual evidence around the target workday, including the next local day so overnight attendance remains explainable.

## Report surfaces

The baseline includes:

- daily workforce status and dedicated daily absence
- department coverage counts, percentages, status breakdowns, and employee drilldown identifiers
- employee date-range detail with attendance-v2 metrics and explanation traces
- monthly workforce summary with leave/non-working status totals
- legacy AD-range Hajiri compatibility plus canonical BS-year/BS-month Hajiri matrices and codes
- the existing attendance-to-salary worksheet over immutable payroll-line snapshots
- employee self-service for the signed-in employee's own attendance and punch drilldown only

Employee self-service is authorized by `attendance.self.read`; it never accepts an arbitrary employee identifier. Organization report exports require `attendance.export`. The migration and identity bootstrap both provision these permissions for existing and fresh installations.

## Exports

Daily, absence, department, employee, monthly, Hajiri, and event-explorer exports use the same reporting services as their screen/API views. Supported formats are XLSX, printable HTML, and PDF. Export rows are bounded to 50,000, event pages to 1,000 rows with a bounded offset, employee report pages to 1,000 employees, and matrix/report date ranges are bounded. Hajiri PDF/print output uses A3 landscape.

XLSX and HTML preserve Unicode text. The dependency-free baseline PDF uses the built-in Helvetica font and replaces characters outside Latin-1; deployments that require native Devanagari PDF glyphs should install and review an embeddable Unicode font renderer rather than silently shipping font assets.

## Verification

Automated coverage proves that:

- present, leave, and absent states reconcile across daily, monthly, summary, and Hajiri reports
- non-working states do not appear in the daily absence report
- device and manual evidence are both visible through the event explorer without raw evidence leakage
- XLSX, PDF, and printable HTML exports use the same daily report data
- the BS Hajiri register maps the same attendance result to the expected day code
- employee-role users can read only their linked employee attendance and cannot open workforce reports or exports
- large report ranges and event offsets are rejected by explicit bounds

The pull request is merged only after CI, migration roundtrip, PostgreSQL device concurrency, Security/CodeQL, and browser authorization gates pass on the exact head.
