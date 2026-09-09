# Attendance engine v2 review checklist

Review this milestone against issue #10 and HF-025 through HF-027/HF-036 through HF-038.

- [ ] Raw device punches remain immutable.
- [ ] Manual events are additive, reasoned, approval-aware, and reversible.
- [ ] Spreadsheet imports preview and isolate invalid rows before apply.
- [ ] Remarks are non-destructive and attributable.
- [ ] Effective shifts, weekly off, holidays, approved leave, and field duty feed one deterministic engine.
- [ ] Duplicate suppression never deletes source evidence.
- [ ] Overnight shifts resolve events across midnight.
- [ ] Explanation trace and calculation metrics are persisted.
- [ ] Locked periods reject recalculation until reopened.
- [ ] Legacy `/attendance/calculate` delegates to `AttendanceEngineService`.
- [ ] CI, migration roundtrip, PostgreSQL device concurrency, Security/CodeQL, and browser authorization are green on the exact PR head.
