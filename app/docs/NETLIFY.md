# Netlify deployment

Netlify hosts the HajiriFlow browser frontend only. The browser is authenticated through a same-origin `/api/*` proxy that Netlify forwards to the separately hosted FastAPI service.

## Production architecture

1. **Frontend** — static application assets on Netlify.
2. **Same-origin browser API path** — `/api/*` on the frontend origin.
3. **Application API** — FastAPI on a service that supports persistent Python web processes.
4. **Worker** — a separate long-running service with network access to attendance devices.
5. **Database** — private PostgreSQL shared by the API and worker.

The browser never receives PostgreSQL credentials, session secrets, biometric-device credentials, worker credentials, or the API hosting service's internal secrets.

## Why the browser uses a same-origin API proxy

Calling an unrelated API origin directly from the Netlify browser app would complicate CSP, cookie SameSite behavior, and CSRF protection. HajiriFlow therefore keeps browser requests on the frontend origin:

`browser → https://<frontend>/api/v1/... → Netlify proxy → https://<api>/api/v1/...`

This preserves the restrictive `connect-src 'self'` policy and keeps session/CSRF cookies first-party from the browser's perspective.

## Required Netlify environment

Set the following non-secret build value in the production Netlify environment:

- `HAJIRIFLOW_API_BASE_URL` — the HTTPS origin/base of the deployed FastAPI service, without credentials, query parameters, or fragments.

Example shape:

`https://api.hajiriflow.example`

Do not place API keys, database credentials, device passwords, session secrets, or other secrets in frontend build configuration.

## Build-time configuration

`netlify.toml` runs:

`node scripts/generate-runtime-config.mjs`

The generator:

- refuses a production build when `HAJIRIFLOW_API_BASE_URL` is missing;
- refuses a non-HTTPS API base in production;
- rejects URLs containing embedded credentials, queries, or fragments;
- writes a non-secret browser runtime config using only `/api` as the browser API base path;
- writes `site/_redirects` with the `/api/*` upstream proxy before the SPA fallback.

The actual upstream API URL is therefore used by the Netlify proxy configuration rather than embedded in application JavaScript.

## Authentication boundary

The frontend initially keeps `#app-shell` inert and hidden behind the identity gate.

Startup flow:

1. request `GET /api/v1/auth/me`;
2. when authenticated, refresh the browser CSRF value through `GET /api/v1/auth/csrf`;
3. if authentication is missing, show the login form;
4. if `must_change_password` is true, keep the workspace locked and require a password change;
5. only after a valid non-temporary session is confirmed does the frontend remove the inert/hidden state.

Temporary-password users are also blocked server-side from permission-protected operations. The browser gate is therefore user experience, not the authorization control.

## Security headers

Netlify applies:

- `Content-Security-Policy` with `connect-src 'self'`;
- frame protection;
- content-type protection;
- a restrictive permissions policy;
- strict referrer policy.

The frontend must not broaden `connect-src` merely to accommodate an external API origin. Use the generated same-origin proxy instead.

## Deployment policy

- `main` is the only production-eligible branch.
- The existing `[deploy]` release gate remains authoritative.
- Feature/security PRs must not include `[deploy]` markers.
- Do not manually trigger an additional Netlify deployment after the Git-authorized release.

## Verification before production release

1. CI and Security workflows pass.
2. PostgreSQL migration roundtrip remains green.
3. The API production environment uses secure cookies and a strong session secret.
4. The Netlify production environment has the correct `HAJIRIFLOW_API_BASE_URL`.
5. The generated `_redirects` contains the API proxy rule before the SPA fallback.
6. An unauthenticated browser receives the HajiriFlow sign-in gate, not the workspace.
7. A valid user can sign in, reload, restore the session, and sign out.
8. A temporary-password user cannot access privileged operations before changing the password.
9. CSRF-protected mutations fail without the required token and succeed with a valid token.
10. Response headers retain CSP, frame, content-type, referrer, and permissions protections.

No production deployment is authorized merely by merging the identity integration work.
