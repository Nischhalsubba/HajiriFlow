import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService

APP_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
ADMIN_USERNAME = "browser.admin"
ADMIN_TEMP_PASSWORD = "browser-temp-password-123"
ADMIN_NEW_PASSWORD = "browser-new-password-456"
EMPLOYEE_USERNAME = "browser.employee"
EMPLOYEE_PASSWORD = "browser-employee-password-123"


@pytest.fixture(scope="module")
def seeded_identity() -> None:
    session = get_session_factory()()
    try:
        seed_identity_catalog(session)
        service = IdentityService(session, get_settings())
        admin = service.create_user(
            username=ADMIN_USERNAME,
            display_name="Browser Admin",
            password=ADMIN_TEMP_PASSWORD,
            must_change_password=True,
        )
        service.assign_role(
            user_id=admin.id,
            role_code="system_administrator",
            actor_user_id=admin.id,
            scope_type=ScopeType.GLOBAL,
        )
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="module")
def live_server(seeded_identity: None) -> Iterator[str]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.browser_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--log-level",
            "warning",
        ],
        cwd=APP_ROOT,
    )
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"browser test server exited with code {process.returncode}")
            try:
                with urlopen(f"{BASE_URL}/ready", timeout=1) as response:  # noqa: S310
                    if response.status == 200:
                        break
            except URLError:
                time.sleep(0.25)
        else:
            raise RuntimeError("browser test server did not become ready")
        yield BASE_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def sign_in(page: Page, username: str, password: str) -> None:
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def expect_unlocked(page: Page, display_name: str) -> None:
    expect(page.locator("#identity-gate")).to_be_hidden()
    expect(page.locator("#app-shell")).not_to_have_attribute("inert", "")
    expect(page.locator("[data-current-user-name]").first).to_have_text(display_name)


def create_employee_from_account_ui(page: Page) -> None:
    page.goto(f"{BASE_URL}/#accounts")
    expect(page.get_by_role("heading", name="User accounts")).to_be_visible()
    form = page.locator("[data-create-account]")
    form.get_by_label("Display name").fill("Browser Employee")
    form.get_by_label("Username", exact=True).fill(EMPLOYEE_USERNAME)
    form.get_by_label("Temporary password").fill(EMPLOYEE_PASSWORD)
    form.get_by_label("Initial role").select_option("employee")
    form.get_by_label("Require password change at first sign-in").uncheck()
    form.get_by_role("button", name="Create account").click()
    expect(form.get_by_text("Account created and initial role assigned.")).to_be_visible()
    expect(page.locator("[data-account-user]", has_text="Browser Employee")).to_be_visible()


def test_real_browser_identity_and_authorization_flow(live_server: str) -> None:
    assert live_server == BASE_URL
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        try:
            admin_context = browser.new_context()
            admin_page = admin_context.new_page()
            admin_page.goto(BASE_URL)

            sign_in(admin_page, ADMIN_USERNAME, ADMIN_TEMP_PASSWORD)
            expect(
                admin_page.get_by_role("heading", name="Change temporary password")
            ).to_be_visible()
            admin_page.get_by_label("Current password").fill(ADMIN_TEMP_PASSWORD)
            admin_page.get_by_label("New password", exact=True).fill(ADMIN_NEW_PASSWORD)
            admin_page.get_by_label("Confirm new password").fill(ADMIN_NEW_PASSWORD)
            admin_page.get_by_role("button", name="Change password").click()
            expect(admin_page.get_by_text("Password changed. Sign in again")).to_be_visible()

            sign_in(admin_page, ADMIN_USERNAME, ADMIN_NEW_PASSWORD)
            expect_unlocked(admin_page, "Browser Admin")

            admin_page.reload()
            expect_unlocked(admin_page, "Browser Admin")

            csrf_status = admin_page.evaluate(
                """async () => {
                  const response = await fetch('/api/v1/admin/users', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                      username: 'csrf.probe',
                      display_name: 'CSRF Probe',
                      password: 'csrf-probe-password-123',
                      must_change_password: false
                    })
                  });
                  return response.status;
                }"""
            )
            assert csrf_status == 403

            create_employee_from_account_ui(admin_page)

            employee_context = browser.new_context()
            employee_page = employee_context.new_page()
            employee_page.goto(f"{BASE_URL}/#accounts")
            sign_in(employee_page, EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD)
            expect(employee_page.get_by_role("heading", name="Access restricted")).to_be_visible()

            employee_row = admin_page.locator(
                "[data-account-user]", has_text="Browser Employee"
            )
            admin_page.once("dialog", lambda dialog: dialog.accept())
            employee_row.get_by_role("button", name="Disable").click()
            expect(admin_page.get_by_text("Browser Employee is now disabled.")).to_be_visible()

            employee_page.reload()
            expect(employee_page.get_by_role("heading", name="Sign in")).to_be_visible()

            admin_page.get_by_role("button", name="Sign out").first.click()
            expect(admin_page.get_by_role("heading", name="Sign in")).to_be_visible()

            employee_context.close()
            admin_context.close()
        finally:
            browser.close()
