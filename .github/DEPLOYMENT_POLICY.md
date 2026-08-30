# Production Deployment Policy

## Goal
Preserve Netlify free-tier usage by making production deploys deliberate, batched, and predictable.

## Rules
- `main` is the only branch eligible for production deployment.
- Pull requests and non-main branches are ignored before the real build runs.
- Normal commits and merges to `main` are also ignored.
- Production deploys only when the latest `main` commit message contains `[deploy]`.
- Batch and validate changes before releasing.
- Never trigger a second manual/API deploy after a Git-triggered release.

## Release
```bash
git commit --allow-empty -m "release: production [deploy]"
git push origin main
```

The release commit publishes the full accumulated `main` state.

## Recovery
Prefer rollback to an existing deployment over rebuilding. Use a new `[deploy]` release only when new code must be published.
