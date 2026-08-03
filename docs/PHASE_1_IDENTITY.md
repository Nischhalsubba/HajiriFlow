# Phase 1: Identity, authentication, and authorization

Phase 1 turns the existing identity schema into an enforceable API boundary. It is designed to run against local PostgreSQL now and a dedicated Supabase PostgreSQL project once an organization slot is available.

## Delivered in the first slice

- Argon2 password hashing and upgrade detection
- Username normalization and duplicate prevention
- Login with generic failure responses
- Database-backed failed-attempt throttling by username and client IP hash
- Revocable, expiring sessions stored only as HMAC hashes
- Immediate invalidation through per-user session versioning
- HttpOnly session cookies and signed double-submit CSRF tokens
- Logout and password-change flows
- Deny-by-default permission dependencies
- Global and organization-scoped role grants
- User listing, creation, activation, deactivation, and role assignment APIs
- Idempotent system role and permission seeding
- First-administrator CLI workflow
- Redacted audit events for identity mutations
- CORS and security-header middleware

## API surface

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Public, throttled |
| `GET` | `/api/v1/auth/me` | Authenticated session |
| `POST` | `/api/v1/auth/logout` | Authenticated + CSRF |
| `POST` | `/api/v1/auth/change-password` | Authenticated + CSRF |
| `GET` | `/api/v1/admin/users` | `identity.user.read` |
| `POST` | `/api/v1/admin/users` | `identity.user.create` + CSRF |
| `PATCH` | `/api/v1/admin/users/{id}/status` | `identity.user.manage` + CSRF |
| `POST` | `/api/v1/admin/users/{id}/roles` | `identity.role.assign` + CSRF |

## Bootstrap

Run migrations, seed the identity catalog, and create the first administrator:

```bash
alembic upgrade head
hajiriflow seed-identity
hajiriflow create-admin --username admin --display-name "System Administrator"
```

The CLI prompts for the initial password without echoing it. The account is marked to change that password after the first login.

## Browser security model

The browser receives:

- an HttpOnly session cookie;
- a signed CSRF cookie readable by the frontend;
- the same CSRF value in the login response so a cross-origin frontend can retain it in memory.

State-changing cookie-authenticated requests must send `X-CSRF-Token`. Bearer-authenticated API requests do not require CSRF because browsers do not attach bearer credentials automatically.

Production deployments must use secure cookies. `SameSite=None` is rejected unless secure cookies are enabled.

## Supabase connection boundary

A dedicated HajiriFlow Supabase project is still required. The current organization has no free project slot. Once a slot exists:

1. create the project in `ap-south-1`;
2. use the pooled PostgreSQL connection string as `HAJIRIFLOW_DATABASE_URL`;
3. run Alembic migrations;
4. seed roles and permissions;
5. configure the API host and Netlify origin;
6. decide whether Supabase Auth replaces the database session provider or remains an external identity provider mapped to `user_accounts`;
7. add RLS policies only after the authoritative access path is chosen and tested.

Do not enable RLS blindly while the FastAPI service uses a privileged database connection. That produces either ineffective policies or a beautifully inaccessible application.

## Remaining Phase 1 work

- frontend login, logout, forced-password-change, and session-expiry screens;
- account and role administration screens backed by these APIs;
- password reset and recovery workflow;
- session-management UI and administrator session revocation;
- optional MFA policy;
- dedicated Supabase project and production secrets;
- production RLS decision and policy tests;
- end-to-end browser tests against the deployed API.
