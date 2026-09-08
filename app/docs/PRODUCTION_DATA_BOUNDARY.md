# Production operational-data boundary

HajiriFlow currently has two distinct frontend capabilities:

1. API-backed identity and account administration.
2. A legacy browser-generated operational workspace used for design and interaction development.

Those two capabilities must not be conflated. Generated attendance, workforce, device, report, or payroll records are not authoritative production records.

## Production rule

A production build is generated with:

- `environment: "production"`
- `operationalDataMode: "integration-required"`

The identity gate still requires the configured HTTPS FastAPI upstream and authenticates through the same-origin `/api` proxy. After successful authentication, the legacy operational workspace is made inert and hidden. The user receives an explicit integration-required state instead of generated operational figures.

The production presentation layer must not rename demo/generated content to make it sound live. This is enforced by regression tests.

## What is allowed while integration is pending

- API-backed sign-in, session validation, password change, sign-out, and reviewed identity/account administration paths may remain available where the user has permission.
- The operational workspace may not present generated employee, attendance, leave, device, reporting, or payroll state as production data.
- Browser-generated operational mutations, simulated device pulls, locally calculated payroll, and generated reports are not production substitutes.

## Enabling operational views later

Changing the production mode away from `integration-required` requires a reviewed API-backed operational data provider. The integration must preserve:

- organization scope derived from trusted session grants;
- permission-aware data loading and actions;
- CSRF protection for cookie-authenticated mutations;
- server-authoritative attendance, correction, payroll, device, biometric, and reporting rules;
- no salary/payroll exposure to attendance-only roles;
- no biometric template/image/scan material in the browser;
- loading, empty, denied, stale, and failure states that do not fall back to generated data;
- accessibility and keyboard behavior for the resulting sensitive workflows;
- production smoke evidence against the deployed frontend and API.

## Deployment implication

The current Netlify production site must not be upgraded merely because the repository is green. A current production build also requires a real `HAJIRIFLOW_API_BASE_URL` build value pointing to the reviewed HTTPS FastAPI deployment. As of the repository review, that infrastructure value was not configured in the connected Netlify project.

Do not invent a placeholder backend, tax policy, bank format, device adapter, or production credential to bypass this boundary.

## Readiness language

This fail-closed boundary is a safety control, not completion of production integration. HajiriFlow should not be described as production-ready until the authoritative operational provider, production infrastructure, release/smoke evidence, and independent authorization/biometric/payroll security testing are complete.
