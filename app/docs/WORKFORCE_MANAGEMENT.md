# Workforce management baseline

HajiriFlow keeps stable employee identity, effective organization/shift assignments, and optional HR/reporting metadata in separate database records so historical attendance and payroll references remain durable when current profile details change.

## Company report profile

Authorized organization administrators can maintain report/contact metadata independently from the legal company record:

- postal/display address
- contact email and phone
- report-header text

Changes are audited. The legal name, display name, timezone, and company lifecycle remain in `company_profiles`.

## Organization hierarchy

The hierarchy supports directorate, department, section, and unit nodes. Node codes are unique per organization. Parent changes are validated within the same organization and reject direct or indirect cycles. Nodes are archived rather than destructively deleted during ordinary operation.

## Employee master

The stable `employees` record owns:

- organization
- employee code
- display name
- join/left date
- lifecycle status

`employee_profiles` extends it with operational HR metadata:

- numeric attendance ID
- HR employee number
- employment type
- designation
- grade/level
- contact email and phone
- optional payroll reference

Attendance IDs and HR employee numbers are unique within an organization. Employee status changes remain soft lifecycle changes so historical records retain their references.

## Search, sorting, and exports

The workforce-management API supports server-side search, status/employment-type filters, bounded pagination, and deterministic sorting. Attendance IDs sort numerically, not lexicographically.

CSV and XLSX exports require the explicit `employee.export` permission and are scoped through the same organization authorization dependency as employee reads. The workforce and payroll administrator system roles receive this permission; global system administrators retain full access through the existing wildcard grant.

## Effective assignments and shifts

The existing workforce service remains the source of truth for effective-dated organization assignments and shifts. Primary organization assignments reject overlapping periods. Shift assignments target exactly one employee or organization node, reject overlaps for the same target, and employee-specific assignments override organization-node assignments for the same date.

## Audit and safety

Profile and hierarchy mutations create redacted administrative audit records with organization context. Sensitive credentials are not part of workforce profile models or exports. Cross-organization reads, writes, and exports are denied by the organization-scoped permission layer.
