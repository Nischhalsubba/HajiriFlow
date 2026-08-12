# Security Policy

HajiriFlow handles workforce identity, biometric attendance evidence, leave decisions, and eventually payroll. Security reports are treated as product-integrity issues, not ordinary feature requests.

## Supported code

Security fixes target the latest commit on `main`. Older branches, deploy previews, local forks, and archived builds are not supported unless a maintainer explicitly says otherwise.

## Reporting a vulnerability

Do not publish credentials, employee data, biometric material, payroll information, exploit steps, or working proof-of-concept code in a public issue.

Preferred reporting path:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability** to create a private GitHub Security Advisory.
3. Include the affected commit or URL, impact, reproduction steps, and a minimal proof of concept.

If private vulnerability reporting is unavailable, open a public issue containing only a request for private contact. Do not include vulnerability details in that issue.

## Useful report details

- Affected route, module, worker, export, or device action
- Commit SHA and deployment URL
- Required permissions or account type
- Reproduction steps
- Expected and observed behavior
- Potential impact and data exposure
- Suggested mitigation, when known

## High-priority areas

- Authentication, sessions, CSRF, throttling, and account recovery
- Role, organization, employee, export, and object-scope authorization
- Biometric templates, device credentials, and device write operations
- Attendance correction, approval, period locking, and audit integrity
- Payroll calculation, approval, reversal, and financial exports
- SQL injection, stored or reflected XSS, SSRF, file upload, and path traversal
- Secret leakage through logs, audit payloads, browser storage, exports, or CI
- Backup, restore, migration, and deployment configuration

## Data-handling expectations

- Use synthetic data when testing.
- Never upload real employee, biometric, identity, banking, or salary records to an issue or pull request.
- Redact tokens, passwords, connection strings, private network addresses, and service-role keys.
- Do not test against an organization or device without explicit authorization.

## Disclosure

Please allow maintainers reasonable time to investigate and release a fix before public disclosure. Credit can be included in the advisory or release notes when requested and appropriate.
