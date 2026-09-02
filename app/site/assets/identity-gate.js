(() => {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeText(value) {
    return String(value ?? "");
  }

  function initials(name) {
    const parts = escapeText(name).trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "HF";
    return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "HF";
  }

  function permissionLabel(session) {
    const permissions = new Set((session?.permissions || []).map((item) => item.code));
    if (permissions.has("system.full_access")) return "System administrator";
    if (permissions.has("identity.user.manage") || permissions.has("identity.role.assign")) {
      return "Identity administrator";
    }
    return "Authenticated user";
  }

  function identityElements() {
    return {
      gate: byId("identity-gate"),
      content: byId("identity-content"),
      shell: byId("app-shell"),
    };
  }

  function lockApplication() {
    const { shell } = identityElements();
    document.body.classList.add("identity-locked");
    if (shell) {
      shell.setAttribute("inert", "");
      shell.setAttribute("aria-hidden", "true");
    }
  }

  function updateUserSurfaces(session) {
    const displayName = escapeText(session?.user?.display_name || session?.user?.username || "Signed-in user");
    const role = permissionLabel(session);
    const shortName = initials(displayName);

    document.querySelectorAll("[data-current-user-name]").forEach((element) => {
      element.textContent = displayName;
    });
    document.querySelectorAll("[data-current-user-role]").forEach((element) => {
      element.textContent = role;
    });
    document.querySelectorAll("[data-current-user-initials]").forEach((element) => {
      element.textContent = shortName;
    });
  }

  function unlockApplication(session) {
    const { gate, shell } = identityElements();
    updateUserSurfaces(session);
    document.body.classList.remove("identity-locked");
    if (shell) {
      shell.removeAttribute("inert");
      shell.removeAttribute("aria-hidden");
    }
    if (gate) gate.hidden = true;
    window.dispatchEvent(new CustomEvent("hajiriflow:identity-ready", { detail: { session } }));
  }

  function setContent(html) {
    const { gate, content } = identityElements();
    if (!gate || !content) return null;
    gate.hidden = false;
    content.innerHTML = html;
    return content;
  }

  function renderChecking(message = "Verifying your session with the HajiriFlow API.") {
    setContent(`
      <h1>Connecting securely</h1>
      <p class="identity-intro">${message}</p>
      <p class="identity-status" role="status" aria-live="polite">Please keep this page open while the session check completes.</p>
    `);
  }

  function renderConfigurationError() {
    const content = setContent(`
      <h1>Application API required</h1>
      <p class="identity-intro">This frontend is intentionally locked because no HajiriFlow API endpoint is configured.</p>
      <p class="identity-status" data-tone="error" role="alert">Production access cannot fall back to browser demo identity or local data.</p>
      <p class="identity-support-copy">Configure the non-secret <code>HAJIRIFLOW_API_BASE_URL</code> build value with the HTTPS FastAPI endpoint, then rebuild through the controlled release process.</p>
    `);
    content?.querySelector("code")?.setAttribute("translate", "no");
  }

  function renderUnavailable(message) {
    const content = setContent(`
      <h1>API unavailable</h1>
      <p class="identity-intro">HajiriFlow could not verify the current session.</p>
      <p class="identity-status" data-tone="error" role="alert"></p>
      <button class="identity-button" type="button" data-identity-retry>Retry connection</button>
    `);
    const status = content?.querySelector(".identity-status");
    if (status) status.textContent = message || "The application API could not be reached.";
    content?.querySelector("[data-identity-retry]")?.addEventListener("click", boot);
  }

  function renderLogin(message = "") {
    const content = setContent(`
      <h1>Sign in</h1>
      <p class="identity-intro">Use your HajiriFlow account to continue to the protected workspace.</p>
      <form class="identity-form" data-identity-login novalidate>
        <div class="identity-field">
          <label for="identity-username">Username</label>
          <input id="identity-username" name="username" type="text" autocomplete="username" minlength="3" maxlength="100" required>
        </div>
        <div class="identity-field">
          <label for="identity-password">Password</label>
          <input id="identity-password" name="password" type="password" autocomplete="current-password" maxlength="500" required>
        </div>
        <button class="identity-button" type="submit">Sign in</button>
      </form>
      <p class="identity-status" role="status" aria-live="polite"></p>
    `);
    if (!content) return;
    const form = content.querySelector("[data-identity-login]");
    const status = content.querySelector(".identity-status");
    if (status && message) status.textContent = message;
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = form.querySelector("button[type='submit']");
      const data = new FormData(form);
      const username = escapeText(data.get("username")).trim();
      const password = escapeText(data.get("password"));
      if (!username || !password) {
        if (status) {
          status.dataset.tone = "error";
          status.textContent = "Enter both your username and password.";
        }
        return;
      }
      if (submit) submit.disabled = true;
      if (status) {
        delete status.dataset.tone;
        status.textContent = "Signing in securely…";
      }
      try {
        const session = await window.HFIdentity.login(username, password);
        if (session?.user?.must_change_password) {
          renderPasswordChange(session);
          return;
        }
        unlockApplication(session);
      } catch (error) {
        if (submit) submit.disabled = false;
        if (status) {
          status.dataset.tone = "error";
          status.textContent = error.status === 429
            ? "Too many failed attempts. Wait for the server retry window before trying again."
            : error.message || "Sign-in failed.";
        }
      }
    });
    queueMicrotask(() => byId("identity-username")?.focus());
  }

  function renderPasswordChange(session) {
    const content = setContent(`
      <h1>Change temporary password</h1>
      <p class="identity-intro">Your account requires a new password before privileged HajiriFlow actions are allowed.</p>
      <form class="identity-form" data-password-change novalidate>
        <div class="identity-field">
          <label for="current-password">Current password</label>
          <input id="current-password" name="currentPassword" type="password" autocomplete="current-password" maxlength="500" required>
        </div>
        <div class="identity-field">
          <label for="new-password">New password</label>
          <input id="new-password" name="newPassword" type="password" autocomplete="new-password" minlength="12" maxlength="500" required aria-describedby="new-password-help">
          <span id="new-password-help" class="identity-support-copy">Use at least 12 characters and do not reuse the temporary password.</span>
        </div>
        <div class="identity-field">
          <label for="confirm-password">Confirm new password</label>
          <input id="confirm-password" name="confirmPassword" type="password" autocomplete="new-password" minlength="12" maxlength="500" required>
        </div>
        <button class="identity-button" type="submit">Change password</button>
      </form>
      <p class="identity-status" role="status" aria-live="polite"></p>
    `);
    if (!content) return;
    updateUserSurfaces(session);
    const form = content.querySelector("[data-password-change]");
    const status = content.querySelector(".identity-status");
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = form.querySelector("button[type='submit']");
      const data = new FormData(form);
      const currentPassword = escapeText(data.get("currentPassword"));
      const newPassword = escapeText(data.get("newPassword"));
      const confirmPassword = escapeText(data.get("confirmPassword"));
      if (newPassword.length < 12) {
        status.dataset.tone = "error";
        status.textContent = "The new password must contain at least 12 characters.";
        byId("new-password")?.focus();
        return;
      }
      if (newPassword !== confirmPassword) {
        status.dataset.tone = "error";
        status.textContent = "The new passwords do not match.";
        byId("confirm-password")?.focus();
        return;
      }
      if (submit) submit.disabled = true;
      delete status.dataset.tone;
      status.textContent = "Changing password and revoking existing sessions…";
      try {
        await window.HFIdentity.changePassword(currentPassword, newPassword);
        renderLogin("Password changed. Sign in again with your new password.");
      } catch (error) {
        if (submit) submit.disabled = false;
        status.dataset.tone = "error";
        status.textContent = error.message || "Password change failed.";
      }
    });
    queueMicrotask(() => byId("current-password")?.focus());
  }

  async function signOut() {
    lockApplication();
    renderChecking("Signing out and revoking this session.");
    try {
      await window.HFIdentity.logout();
      renderLogin("Signed out securely.");
    } catch (error) {
      renderUnavailable(error.message || "The session could not be revoked. Retry before leaving this device unattended.");
    }
  }

  async function boot() {
    lockApplication();
    renderChecking();
    if (!window.HFIdentity?.isConfigured?.()) {
      renderConfigurationError();
      return;
    }
    try {
      const session = await window.HFIdentity.me();
      if (session?.user?.must_change_password) {
        renderPasswordChange(session);
        return;
      }
      unlockApplication(session);
    } catch (error) {
      if (error.status === 401) {
        renderLogin();
        return;
      }
      renderUnavailable(error.message || "The application API could not be reached.");
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-identity-logout]");
    if (!button) return;
    event.preventDefault();
    signOut();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
