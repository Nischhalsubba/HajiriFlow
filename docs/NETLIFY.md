# Netlify deployment

Netlify hosts the HajiriFlow browser frontend only.

## Why

The HajiriFlow backend is a FastAPI application with PostgreSQL persistence and a long-running worker that communicates with biometric devices. Static hosting cannot keep those Python processes alive or reach private device networks reliably.

The production architecture is therefore split into:

1. **Frontend** — static application assets on Netlify.
2. **Application API** — FastAPI on a service that supports persistent Python web processes.
3. **Worker** — a separate long-running service with network access to attendance devices.
4. **Database** — private PostgreSQL shared by the API and worker.

## Netlify configuration

`netlify.toml` publishes the `site/` directory and applies:

- a single-page fallback to `index.html`;
- restrictive browser security headers;
- long-lived caching for versioned assets.

The static frontend does not contain database credentials, device secrets, session secrets, biometric data, or payroll data.

## Current state

The deployed frontend is an application shell that communicates the actual implementation status. It does not pretend that unfinished attendance, device, leave, or payroll modules are operational.

When the FastAPI backend is deployed, its public base URL should be provided to the frontend through a non-secret build-time configuration value. Secrets must remain in the backend hosting environment.

## Deployment verification

After a production deploy:

1. Open the root site URL and confirm the HajiriFlow overview renders.
2. Test desktop and mobile navigation.
3. Confirm `/assets/styles.css`, `/assets/app.js`, and `/assets/favicon.svg` return successfully.
4. Confirm unknown frontend paths return the app shell rather than a blank page.
5. Check response headers for CSP, frame protection, content-type protection, and referrer policy.
