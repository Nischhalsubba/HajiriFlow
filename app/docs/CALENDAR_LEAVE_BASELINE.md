# Calendar, leave, and field-duty baseline

HajiriFlow uses one calendar decision service for holidays, weekends, leave, field duty, attendance, reporting, and later payroll reconciliation. Leave entitlement periods are keyed by Bikram Sambat (BS) year; AD dates remain the storage and interoperability representation for individual events.

## BS dates and organization calendar

- AD/BS conversion and BS month boundaries use `BsDateService`.
- Organization weekends are configurable as weekday numbers.
- Holidays support public, organization, and optional categories plus active/cancelled lifecycle state.
- The organization BS-month endpoint returns every BS/AD day pair, its shared working-day decision, holiday name when applicable, and the month working-day count.
- Working-day calculations exclude configured weekends and active non-optional holidays.

## Leave policy rules

A leave policy owns its code, display name, paid/unpaid flag, half-day allowance, annual entitlement, and active state. Baseline policy rules add:

- carry-forward enablement
- optional carry-forward cap
- `#RRGGBB` display color
- optional employment-type eligibility (`permanent`, `contract`, `temporary`, `intern`, `consultant`)

An empty eligibility list means all employment types are eligible. Policy-rule mutations are authorized and audited.

## BS-year balances

`leave_allocations.period_year` is interpreted as a BS year. Each allocation can expose:

- opening days
- earned days
- carried days
- adjustment days
- approved/used days
- pending days
- available days

Existing allocations without a detail row remain backward-compatible: their existing `allocated_days` value is treated as earned entitlement until a breakdown is explicitly saved.

Leave requests must remain inside one BS allocation year. Their working-day count uses the same organization calendar service, so weekends and active holidays are excluded consistently. Half-day requests are limited to a single working day when the policy allows them.

## Annual allocation

Annual allocation is always previewable before apply. The plan shows each active employee, employment type, eligibility decision, prior-year carry, annual entitlement, adjustment, existing allocation ID, and whether applying would create, update, skip, or make no change.

Applying the same annual allocation repeatedly is idempotent because the employee/policy/BS-year allocation key is unique and the apply path upserts to the deterministic target values. Carry is calculated from positive prior-year available balance, excludes pending requests, and is capped when configured.

## Leave workflow and self-service

Employees can view only their own balances and requests through organization-scoped employee permissions. Authorized managers can create/decide/list requests. Pending or approved leave can be cancelled; cancellation releases pending/used entitlement because cancelled requests are excluded from balance aggregation. Employees cannot decide their own leave under the existing approval contract.

## Field duty / kaaj

Field-duty requests support paid/unpaid state, request/approval/rejection/cancellation, employee self-service, optional location/evidence references, filters, and CSV/XLSX exports. Field duty and leave reject overlapping pending/approved periods so the shared workday service receives one unambiguous absence/presence decision.

Exports and managed reads remain organization-scoped. Detail, cancellation, policy, allocation, and holiday mutations create redacted audit events.
