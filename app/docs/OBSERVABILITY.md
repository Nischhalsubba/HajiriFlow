# Observability and incident correlation

HajiriFlow observability must make failures diagnosable without turning logs into a second copy of workforce, biometric, attendance, payroll, or authentication data.

## Runtime probes

- `GET /health` is the liveness endpoint. It reports service/version/environment metadata and does not query application data.
- `GET /ready` is the readiness endpoint. It performs a minimal database connectivity check and returns `503` when PostgreSQL is unavailable.
- Neither endpoint is an authorization bypass or a place for secret/configuration dumps.

## Request correlation

Every HTTP response includes `X-Request-ID`.

A caller-supplied value is reused only when it matches the conservative request-ID grammar and is at most 100 characters. Otherwise HajiriFlow generates a new identifier. The active request ID is also attached automatically to newly inserted `AuditEvent` records, so an operational request can be correlated with a protected domain action without copying the domain payload into the request log.

Request logs are structured JSON and contain only:

- `event`
- `request_id`
- HTTP method
- route template/path
- status code
- duration in milliseconds
- exception type for an unhandled server error

They must **not** contain query strings, request/response bodies, cookies, authorization headers, CSRF values, usernames, employee identifiers, salaries, bank data, national identifiers, biometric/template values, device credentials, document payloads, session tokens, or reset secrets.

## Audit versus operational logs

Operational request logs answer: *which request failed, where, and how long did it take?*

The append-only audit subsystem answers: *who performed which protected action, against what object, why, and what approved state transition occurred?*

Do not solve an audit requirement by adding sensitive business data to application logs.

## Minimum production alert signals

A production deployment should alert on sustained or unusual changes in:

- readiness failures;
- HTTP 5xx rate and latency;
- authentication failures and lockout/throttling activity;
- authorization denials across organization boundaries;
- biometric device pull failures/retry exhaustion;
- attendance correction approval/rejection anomalies;
- payroll approval, posting, reversal, and export failures;
- database migration or worker failures.

Alert destinations and thresholds are deployment-specific and should be configured in the hosting/monitoring platform rather than hard-coded into the repository.

## Incident use

Start with the request ID. Correlate the structured request record with immutable audit history and the relevant worker/device session. Never copy sensitive payloads into an incident ticket unless the incident-response process explicitly requires and protects them.
