# Production Deployment Policy

## Goal

Keep production releases deliberate, reproducible, and fail-closed while avoiding unnecessary Netlify builds.

## Rules

- `main` is the only branch eligible for production release.
- Pull requests, non-main branches, and ordinary merges do not publish production.
- Netlify only builds a `main` commit whose message contains `[deploy]`.
- Operators release through the repository's **Release Production** workflow; do not create ad-hoc `[deploy]` commits locally.
- A release requires the exact current 40-character `main` SHA and the real production HTTPS API origin.
- The release workflow repeats code, JavaScript, test, PostgreSQL migration, and device-concurrency validation before authorizing the empty `[deploy]` commit.
- The production API must return healthy `/health` and ready `/ready` responses before the frontend release is authorized.
- Netlify must independently have `HAJIRIFLOW_API_BASE_URL` configured to the same reviewed HTTPS upstream. The workflow input does not configure Netlify for you.
- Never trigger a second manual/API deploy after the Git-triggered release unless the first release failed and the incident procedure explicitly calls for it.
- After Netlify publishes the intended deploy, run **Production Smoke** against the real frontend and API origins.

## Branch/ruleset protection

The release workflow creates an **empty** `[deploy]` authorization commit on top of an already validated `main` SHA because Netlify's build-ignore contract keys off the commit message. Repository protection should therefore:

- require pull requests for code/configuration changes;
- require the normal CI and Security checks before merge;
- block force pushes and branch deletion;
- prevent ordinary actors from bypassing the rule;
- if protection blocks the release workflow's empty authorization commit, grant the narrowly scoped release integration/bot the minimum bypass needed for that empty commit only.

Do not grant a general human bypass merely to make releases convenient.

If a second independent maintainer is available, require approving review and consider Code Owner review for high-risk paths. Do not configure a self-review requirement that makes a single-maintainer repository impossible to operate.

## Recovery

Prefer rollback to an existing known-good deployment over rebuilding old frontend code. Netlify can republish a previous successful atomic deploy.

API/worker rollback must use the real hosting provider's previous validated immutable revision/artifact and must be checked for database-schema compatibility first.

Do not run a database downgrade automatically as part of application rollback.

See `app/docs/PRODUCTION_RUNBOOK.md` for backup, restore rehearsal, migration order, smoke checks, and incident evidence.
