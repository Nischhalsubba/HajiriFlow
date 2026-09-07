# Application attack-surface review

This review records the controls present in the current HajiriFlow codebase and the regression evidence that protects them. It is not a substitute for an independent production penetration test.

## SQL injection

**Current exposure:** database-backed API and identity flows.

**Controls:** application queries use SQLAlchemy expressions and bound parameters. Authentication normalizes input and compares it as data rather than composing SQL strings. `test_sql_injection_payload_is_treated_as_literal_identity_input` sends a classic boolean-injection username and requires authentication failure.

## Stored and reflected XSS

**Current exposure:** the static authenticated workspace renders data in the browser.

**Controls:** production JavaScript is guarded against direct raw-HTML execution sinks (`innerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, and `new Function`). Protected API responses also receive a restrictive CSP. The CI contract scans every production JavaScript asset so a newly introduced sink requires an explicit security review rather than silently landing.

This guard does not mean arbitrary future DOM code is automatically safe; user-controlled values must continue to be assigned through text/value APIs or otherwise escaped for their rendering context.

## CSRF

**Current exposure:** cookie-authenticated state-changing API calls.

**Controls:** state-changing routes depend on `require_csrf`. Bearer-token API clients are not forced through browser-cookie CSRF validation. Existing identity API tests prove cookie-authenticated writes without the matching CSRF header are rejected.

## SSRF

**Current exposure:** none in the current application API.

The runtime backend has no generic URL-fetch endpoint and no runtime HTTP client integration used to fetch user-selected URLs. A CI contract scans application source for common generic HTTP-fetch call sites. Device endpoints are registered configuration, not arbitrary browser-submitted fetch targets; concrete future vendor adapters require a dedicated network policy review before production use.

## Broken access control and IDOR/BOLA

**Current exposure:** organization-owned workforce, leave, attendance, device, biometric and payroll resources.

**Controls:** organization-owned routes derive the trusted organization scope from the path and use `require_organization_permission`; query-string scope injection is explicitly rejected by the identity tests. Existing cross-tenant tests verify organization-scoped administrators cannot act on another tenant. Resource services additionally constrain resource identifiers by organization where the resource is loaded.

Any new organization-owned endpoint must use the organization-scoped dependency rather than a global permission dependency.

## Mass assignment

**Current exposure:** JSON request bodies.

**Controls:** FastAPI/Pydantic request models enumerate accepted fields and service methods assign authoritative fields explicitly. Organization IDs, audit actors, lifecycle state, calculation versions and approval identities are not copied wholesale from untrusted request dictionaries. New APIs must not call ORM constructors with arbitrary `payload.model_dump()` data unless every accepted field has been deliberately reviewed.

## File upload attacks and path traversal

**Current exposure:** none. HajiriFlow currently exposes no `UploadFile`, multipart upload, filesystem-download, or browser file-input flow.

Do not add placeholder upload code. If document/file functionality is introduced, it must receive its own threat review covering MIME verification, file signatures, size limits, malware/content scanning, generated storage names, private object authorization, path normalization, download headers and retention/deletion.

## Password-reset abuse

**Current exposure:** none. The current identity API supports authenticated password change but has no unauthenticated forgot/reset flow.

When account recovery is introduced, it must add single-use expiring recovery tokens, enumeration-resistant responses, rate limiting, session invalidation, audit events and tests before release.

## Rate limiting

**Current exposure:** authentication attempts.

**Controls:** failed authentication attempts are stored as protected hashes and bounded by the configured login window and maximum attempts. Existing service tests verify the threshold produces `AuthenticationRateLimited`; the API maps it to HTTP 429 with `Retry-After`.

Rate limiting for future high-cost or externally-triggered endpoints must be assessed separately according to abuse cost and user impact.

## Session fixation

**Current exposure:** login/session creation.

**Controls:** every successful authentication creates a new cryptographically random raw token and a new server-side session row. The attack-surface test verifies two fresh authentications cannot reuse the same token or session ID. Password changes and user disablement invalidate existing sessions through session version/revocation controls.

## Open redirects

**Current exposure:** none. The API currently has no `RedirectResponse` endpoint and accepts no return URL for authentication. CI prevents a redirect endpoint from appearing unnoticed in the API surface.

If redirects are added, destinations must be same-origin or selected from a fixed allow-list; arbitrary absolute return URLs must not be trusted.

## CORS

**Current exposure:** browser API access.

**Controls:** configured origins are explicit. Staging/production configuration rejects non-HTTPS, loopback, path-bearing and otherwise non-canonical origins. The middleware does not use a wildcard with credentials. A CI regression test proves an attacker origin receives no `Access-Control-Allow-Origin` grant.

## Biometric and sensitive-data leakage

Raw punch/device metadata rejects keys that imply biometric templates, faces, fingerprints, images, passwords, secrets or tokens. Audit payload redaction covers sensitive nested fields, and request observability logs route metadata rather than query strings, request bodies or authorization headers. The biometric privacy policy separately defines consent/deletion and export/logging restrictions.

## Independent validation still required

Before calling HajiriFlow production-ready, use a security reviewer who is independent of the implementation work to test authorization boundaries, biometric-device operational handling and payroll controls against the deployed production-equivalent system. Record findings and remediation evidence; do not convert this internal review into an "independent" assessment claim.
