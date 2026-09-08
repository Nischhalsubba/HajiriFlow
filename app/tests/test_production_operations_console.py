from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
JS = (APP_ROOT / "site" / "assets" / "production-operations-v1.js").read_text(
    encoding="utf-8"
)
CSS = (APP_ROOT / "site" / "assets" / "production-operations-v1.css").read_text(
    encoding="utf-8"
)
GENERATOR = (APP_ROOT / "scripts" / "generate-runtime-config.mjs").read_text(
    encoding="utf-8"
)


def test_production_console_is_api_only_and_dom_safe() -> None:
    assert 'config.operationalDataMode !== "api"' in JS
    assert "window.HFData" not in JS
    assert "localStorage" not in JS
    assert "sessionStorage" not in JS
    assert "innerHTML" not in JS
    assert "insertAdjacentHTML" not in JS
    assert "document.write" not in JS
    assert 'credentials: "same-origin"' in JS
    assert 'headers.set("X-CSRF-Token", csrf)' in JS
    assert 'cache: "no-store"' in JS


def test_sensitive_views_are_permission_gated_in_the_browser() -> None:
    assert 'can("attendance.read")' in JS
    assert 'can("payroll.read")' in JS
    assert 'can("device.read")' in JS
    assert 'can("biometric.consent.read")' in JS
    assert 'can("biometric.consent.manage")' in JS
    assert 'can("biometric.deletion.manage")' in JS
    assert 'can("attendance.correction.approve")' in JS
    assert 'can("payroll.approve")' in JS


def test_attendance_correction_ux_explains_change_reason_and_actors() -> None:
    for phrase in (
        "Current record",
        "Requested correction",
        "Requested by",
        "Decision reason",
        "Approve correction",
        "Reject correction",
        "Immutable attendance history",
    ):
        assert phrase in JS
    assert "correction.reason" in JS
    assert "correction.requested_by" in JS
    assert "correction.decided_by" in JS
    assert "correction.decision_reason" in JS


def test_payroll_ux_explains_lifecycle_and_approvers() -> None:
    for status in (
        "draft",
        "pending_approval",
        "approved",
        "posted",
        "reversal_pending",
        "reversed",
    ):
        assert status in JS
    for field in (
        "run.created_by",
        "run.approved_by",
        "run.posted_by",
        "run.reversal_requested_by",
        "run.reversed_by",
    ):
        assert field in JS
    assert "Maker is still preparing the run." in JS
    assert "independent checker" in JS
    assert "additive reversal workflow" in JS
    assert "Immutable payroll history" in JS


def test_device_ux_exposes_safe_failure_evidence_without_secrets() -> None:
    assert "Safe error:" in JS
    assert "pull.error_code" in JS
    assert "pull.error_detail" in JS
    assert "pull.attempt_count" in JS
    assert "pull.ingested_count" in JS
    assert "pull.duplicate_count" in JS
    lowered = JS.lower()
    assert "credential_ciphertext" not in lowered
    assert "biometric_template" not in lowered
    assert "template_bytes" not in lowered


def test_biometric_ux_is_governance_only_and_receipt_hash_bounded() -> None:
    for phrase in (
        "Biometric privacy",
        "Latest consent decision",
        "Record consent",
        "Record decline",
        "Revoke consent",
        "Pending deletion queue",
        "64-character SHA-256 receipt hash",
    ):
        assert phrase in JS
    assert '/^[a-fA-F0-9]{64}$/' in JS
    assert "receipt_sha256" in JS
    assert "failure_code" in JS
    lowered = JS.lower()
    assert "biometric image" not in lowered
    assert "biometric scan" not in lowered
    assert "raw provider receipt" not in lowered


def test_manager_overview_prioritizes_sensitive_queues() -> None:
    assert "Manager approval queue" in JS
    assert "Payroll control queue" in JS
    assert "Device attention" in JS
    assert "Biometric deletion queue" in JS
    assert "pendingCorrections" in JS
    assert "pendingPayrollRuns" in JS
    assert "problemDevices" in JS


def test_console_meets_mobile_focus_and_motion_baselines() -> None:
    assert "min-height: 44px" in CSS
    assert "overflow-x: auto" in CSS
    assert "@media (max-width: 620px)" in CSS
    assert "@media (forced-colors: active)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "animation-duration: .01ms !important" in CSS
    assert "transition-duration: .01ms !important" in CSS


def test_production_assets_are_injected_before_identity_gate() -> None:
    assert "production-operations-v1.css" in GENERATOR
    assert "production-operations-v1.js" in GENERATOR
    assert "identity-gate.js" in GENERATOR
    assert "source.replace(identityGate" in GENERATOR
    assert 'operationalDataMode: isProduction ? "api" : "demo"' in GENERATOR
