# Payroll baseline

HajiriFlow payroll is a configurable calculation and approval system. It does not hard-code a tax schedule. A payroll administrator records the applicable fiscal-year policy, and a separate authorized approver confirms it before payroll can use it.

## Authority chain

1. Create a Bikram Sambat fiscal year with its exact AD date boundaries.
2. A different authorized actor activates the fiscal year.
3. Configure earning heads, deduction types, effective employee compensation, and holiday-overtime rules.
4. Create a versioned tax slab set and have a different authorized actor confirm it.
5. Create a payroll period inside the active fiscal year.
6. Calculate attendance with `attendance-v2`, prepare the employee payroll-attendance review, and approve the snapshot.
7. Lock the payroll period through the existing maker/checker lifecycle.
8. Preview or generate payroll. Generation fails closed when the fiscal year, tax policy, compensation, attendance review, or period lock is missing.
9. Draft runs may receive reasoned adjustments. Existing submit, independent approval, posting, additive reversal, period close, and immutable history controls remain authoritative.
10. Payslips and annual summaries are rendered from posted payroll-line snapshots rather than current mutable policy tables.

## Calculation contract

Money uses `Decimal` and is rounded to NPR paisa with `ROUND_HALF_UP` at monetary boundaries.

For the baseline monthly calculation:

- base salary is the effective compensation profile's monthly base;
- fixed components use their configured amount;
- percentage components apply their configured percentage to base salary;
- deduction caps are applied after the component calculation;
- pretax deductions reduce taxable period income;
- holiday overtime uses the effective employee-specific rule first, then the organization rule, and multiplies the minute rate by approved `attendance-v2` holiday-overtime minutes;
- period taxable income is projected across 12 monthly periods for tax projection;
- progressive tax uses the confirmed versioned slab set and its standard deduction;
- the projected annual tax is divided across 12 periods and rounded to paisa for the period;
- net pay is `gross - deductions - tax`.

No statutory values are embedded in code. Administrators are responsible for entering and confirming the policy that applies to the organization and fiscal year.

## Snapshot integrity

Each generated payroll line stores:

- employee identity snapshot;
- approved attendance snapshot, including attendance engine version and input fingerprints;
- effective compensation and earnings snapshot;
- deduction and confirmed tax-policy snapshot;
- overtime-policy reference;
- calculation explanation and projected-tax values.

Changing a current earning head, compensation profile, or tax policy therefore does not rewrite a historical posted payslip.

## Self-service boundary

The employee role receives `payroll.self.read`. Self-service endpoints never accept an arbitrary employee identity. The server derives `employee_id` from the authenticated account link and verifies that it belongs to the organization before returning posted payslips or annual totals.

## Export bounds

Individual and batch payslips use the shared bounded PDF renderer. Annual payroll summaries use the shared bounded XLSX renderer. Organization-wide reads and exports remain permission-gated; employee self-service does not inherit those administrator permissions.

## Release evidence

The payroll baseline is not accepted unless ordinary CI, both supported Python versions, PostgreSQL migration roundtrip, PostgreSQL device-concurrency regression, Security/CodeQL, and real-browser authorization gates pass on the exact pull-request head. Payroll tests include an exact synthetic reconciliation fixture to the paisa; it is a test policy, not a claim about a current statutory Nepal tax schedule.
