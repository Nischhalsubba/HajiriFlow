# Milestone 10 acceptance evidence

HajiriFlow milestone #10 implements HF-025 through HF-027 and HF-036 through HF-038.

## Manual attendance

- Manual attendance events are additive records; raw biometric punches are never edited or deleted.
- Manual events require a reason and preserve requester/decision metadata.
- Approval is independent when configured, and approved events can be revoked without deleting history.
- XLSX imports are previewed before apply, retain row-level validation errors, and do not partially apply invalid strict imports.
- Day remarks are append-only notes with actor and timestamp metadata.

## Deterministic engine

- `AttendanceEngineService` is the authoritative calculator for both the v2 API and the legacy `/attendance/calculate` compatibility route.
- Effective employee/org shift assignment, weekly-off configuration, holidays, approved leave, and approved field duty are resolved for the work date.
- Overnight shifts use a bounded cross-midnight event window.
- Near-duplicate events are grouped by a configurable policy without deleting raw evidence.
- The engine stores worked, late, early-arrival, early-departure, late-departure, regular-OT and holiday-OT metrics plus a deterministic explanation trace.
- An input fingerprint makes repeat calculations with unchanged inputs repeat-safe.
- Locked attendance periods reject recalculation until an audited reopen action occurs.

## Automated proof

`test_attendance_engine_v2.py` covers overnight workdays, duplicate suppression, deterministic reruns, leave/holiday priority, manual approval/revocation, spreadsheet preview/apply isolation, period lock/reopen, and append-only remarks. Existing API tests verify the legacy calculation route now records `attendance-v2`.

The pull request must pass the repository CI matrix, migration roundtrip, PostgreSQL device-concurrency regression, Security/CodeQL, and identity browser authorization before merge.
