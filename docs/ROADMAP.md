# Roadmap

## Phase 0: Foundation

- Application and worker processes
- Configuration validation
- PostgreSQL development environment
- CI, linting, tests, and health checks
- Architecture and security documentation

## Phase 1: Identity and organisation

- Database migrations
- Administrators, managers, viewers, employees
- Deny-by-default permission matrix
- Organisation hierarchy and employee records
- Secure sessions, CSRF protection, login throttling, audit events

## Phase 2: Devices and raw attendance

- Device registry stored in PostgreSQL
- ZKTeco adapter behind a vendor-neutral interface
- Test connection and diagnostics
- Idempotent, distributed-locked pull jobs
- Immutable raw punch storage and pull-session audit

## Phase 3: Attendance engine

- Nepal timezone boundaries
- Shift and grace rules
- Punch deduplication
- Daily settlement and correction workflow
- Holidays, weekends, leave, and kaaj integration

## Phase 4: Reports

- Daily attendance
- Monthly attendance
- Absent and department reports
- Hajiri register
- Excel/PDF exports with permission checks

## Phase 5: Payroll

- Locked attendance periods
- Versioned earning and deduction rules
- Payroll preview, approval, posting, and reversal
- Payslips and bank exports

## Release gate

Production deployment requires threat modelling, backup restore testing, permission tests, device integration tests, and payroll reconciliation against a manually verified sample period.
