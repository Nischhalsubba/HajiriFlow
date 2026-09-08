from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent


def _root(relative: str) -> str:
    return (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")


def _app(relative: str) -> str:
    return (APP_ROOT / relative).read_text(encoding="utf-8")


def test_codeowners_covers_governance_and_high_risk_paths() -> None:
    source = _root(".github/CODEOWNERS")
    assert "* @Nischhalsubba" in source
    assert "/.github/ @Nischhalsubba" in source
    assert "/netlify.toml @Nischhalsubba" in source
    for path in (
        "/app/src/hajiriflow/api/",
        "/app/src/hajiriflow/identity/",
        "/app/src/hajiriflow/attendance/",
        "/app/src/hajiriflow/payroll/",
        "/app/src/hajiriflow/device_platform/",
        "/app/alembic/",
    ):
        assert path in source


def test_root_security_policy_supports_private_reporting() -> None:
    source = _root("SECURITY.md")
    assert "Report a vulnerability" in source
    assert "private GitHub Security Advisory" in source
    assert "Never upload real employee" in source
    assert "biometric" in source.lower()
    assert "payroll" in source.lower()


def test_frontend_production_headers_include_hsts() -> None:
    source = _root("netlify.toml")
    assert 'Strict-Transport-Security = "max-age=31536000"' in source
    assert "frame-ancestors 'none'" in source
    assert 'X-Content-Type-Options = "nosniff"' in source
    assert 'X-Frame-Options = "DENY"' in source


def test_manual_production_smoke_checks_frontend_and_database_readiness() -> None:
    source = _root(".github/workflows/production-smoke.yml")
    assert "workflow_dispatch:" in source
    assert "permissions:\n  contents: read" in source
    assert "FRONTEND_URL" in source
    assert "API_URL" in source
    assert 'parsed.scheme != "https"' in source
    assert '"$api/health"' in source
    assert '"$api/ready"' in source
    assert '"$frontend/api/health"' in source
    assert '"operationalDataMode":"integration-required"' in source
    assert "strict-transport-security" in source.lower()
    assert "content-security-policy" in source.lower()
    assert 'health.get("environment") != "production"' in source


def test_release_requires_exact_main_and_repeats_integrity_gates() -> None:
    source = _root(".github/workflows/release-production.yml")
    assert "target_sha:" in source
    assert "api_url:" in source
    assert "^refs/heads/main" not in source
    assert "github.ref == 'refs/heads/main'" in source
    assert '[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]]' in source
    assert 'test "$TARGET_SHA" = "$(git rev-parse origin/main)"' in source
    assert "ruff check ." in source
    assert "pytest --cov=hajiriflow" in source
    assert "alembic upgrade head" in source
    assert "alembic current --check-heads" in source
    assert "test_postgresql_device_concurrency.py" in source
    assert '"$api/health"' in source
    assert '"$api/ready"' in source
    assert "[deploy]" in source


def test_runbook_covers_backup_restore_rollback_and_sensitive_boundaries() -> None:
    source = _app("docs/PRODUCTION_RUNBOOK.md")
    for required in (
        "pg_dump --format=custom",
        "pg_restore --list",
        "Restore rehearsal",
        "Frontend rollback",
        "API and worker rollback",
        "alembic upgrade head",
        "alembic current --check-heads",
        "GET /health",
        "GET /ready",
        "production smoke",
        "independent authorization",
    ):
        assert required in source
    warning = (
        "Do not run an Alembic downgrade in production merely to match "
        "an application rollback"
    )
    assert warning in source


def test_readiness_document_keeps_external_blockers_explicit() -> None:
    source = _app("docs/PRODUCTION_READINESS.md")
    assert "GitHub `main` was **not protected**" in source
    assert "HAJIRIFLOW_API_BASE_URL" in source
    assert "Independent authorization/tenant/object-scope test" in source
    assert "Independent biometric/privacy review" in source
    assert "Independent payroll-control review" in source
    assert "No license is added automatically" in source
    assert "Production readiness remains blocked" in source
