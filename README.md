# HajiriFlow

Attendance to payroll, with every record accounted for.

HajiriFlow is a Nepal-ready workforce attendance platform designed for biometric device integrations, attendance processing, leave, reporting, and payroll workflows. ZKTeco is treated as an integration adapter rather than the product identity.

## Current status

The project is in foundation development. The first milestone establishes a production-safe modular monolith with:

- a FastAPI web application;
- a separate worker process for device pulls;
- PostgreSQL as the only runtime source of truth;
- explicit Asia/Kathmandu business timezone handling;
- configuration validation that fails closed;
- health and readiness endpoints;
- automated tests and CI.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Web health check: `http://localhost:8000/health`

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn hajiriflow.main:app --reload
pytest
```

## Architecture principles

1. Raw biometric punches are immutable.
2. PostgreSQL is the sole source of runtime configuration.
3. Web and device-pull processes run separately.
4. Permissions are deny-by-default.
5. Unknown roles never inherit access.
6. Synthetic attendance is prohibited unless explicitly approved, attributed, and audited.
7. Payroll uses approved and locked attendance periods, never mutable live punches.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md).

## License

A license has not yet been selected. Until one is added, all rights are reserved.
