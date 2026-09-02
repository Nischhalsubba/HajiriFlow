(() => {
  "use strict";

  const FULL_ACCESS = "system.full_access";
  const state = {
    users: [],
    search: "",
    busy: false,
  };

  const permissions = () => new Set(
    (window.HFIdentity?.session?.permissions || []).map((item) => item.code),
  );

  function can(permission) {
    const grants = permissions();
    return grants.has(FULL_ACCESS) || grants.has(permission);
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function accountRouteActive() {
    return location.hash.replace(/^#/, "") === "accounts";
  }

  function setPageHeading() {
    const kicker = document.getElementById("page-kicker");
    const title = document.getElementById("page-title");
    if (kicker) kicker.textContent = "Administration";
    if (title) title.textContent = "Access & accounts";
  }

  function installNavigation() {
    const nav = document.getElementById("primary-nav");
    if (!nav || !can("identity.user.read")) return;
    if (nav.querySelector('[data-identity-accounts-link]')) return;

    const groups = [...nav.querySelectorAll(".nav-group")];
    const administration = groups.find((group) => (
      group.querySelector("p")?.textContent?.trim() === "Administration"
    ));
    if (!administration) return;

    const link = document.createElement("a");
    link.className = `nav-link ${accountRouteActive() ? "is-active" : ""}`;
    link.href = "#accounts";
    link.dataset.identityAccountsLink = "";
    if (accountRouteActive()) link.setAttribute("aria-current", "page");
    link.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M19 8v6M16 11h6"/>
      </svg>
      <span>Access & accounts</span>
    `;
    administration.appendChild(link);
  }

  function statusPill(user) {
    const active = user.status === "active";
    return `<span class="account-status ${active ? "is-active" : "is-disabled"}">
      <span aria-hidden="true"></span>${active ? "Active" : "Disabled"}
    </span>`;
  }

  function roleOptions() {
    const options = [
      ["employee", "Employee"],
      ["identity_administrator", "Identity administrator"],
    ];
    if (can(FULL_ACCESS)) options.push(["system_administrator", "System administrator"]);
    return options.map(([value, label]) => (
      `<option value="${value}">${label}</option>`
    )).join("");
  }

  function userActions(user) {
    const currentUserId = window.HFIdentity?.session?.user?.id;
    const canManage = can("identity.user.manage") && user.id !== currentUserId;
    const canAssign = can("identity.role.assign");
    const nextStatus = user.status === "active" ? "disabled" : "active";
    const statusLabel = nextStatus === "disabled" ? "Disable" : "Enable";

    return `
      <div class="account-actions">
        ${canManage ? `
          <button class="account-button account-button-secondary" type="button"
            data-account-status="${nextStatus}" data-user-id="${escapeHtml(user.id)}"
            data-user-name="${escapeHtml(user.display_name)}">
            ${statusLabel}
          </button>
        ` : ""}
        ${canAssign ? `
          <div class="account-role-action">
            <label>
              <span class="sr-only">Role for ${escapeHtml(user.display_name)}</span>
              <select data-role-select="${escapeHtml(user.id)}" aria-label="Role for ${escapeHtml(user.display_name)}">
                ${roleOptions()}
              </select>
            </label>
            <button class="account-button account-button-secondary" type="button"
              data-assign-role="${escapeHtml(user.id)}">Assign role</button>
          </div>
        ` : ""}
      </div>
    `;
  }

  function filteredUsers() {
    const query = state.search.trim().toLowerCase();
    if (!query) return state.users;
    return state.users.filter((user) => [user.display_name, user.username, user.status]
      .some((value) => String(value || "").toLowerCase().includes(query)));
  }

  function renderUserList(root) {
    const list = root.querySelector("[data-account-list]");
    if (!list) return;
    const users = filteredUsers();
    if (!users.length) {
      list.innerHTML = `
        <div class="account-empty">
          <strong>No accounts match this search.</strong>
          <p>Clear the search or create a new account if your permissions allow it.</p>
        </div>
      `;
      return;
    }

    list.innerHTML = users.map((user) => `
      <article class="account-row" data-account-user="${escapeHtml(user.id)}">
        <div class="account-identity">
          <span class="account-avatar" aria-hidden="true">${escapeHtml(
            String(user.display_name || user.username || "?").trim().split(/\s+/)
              .slice(0, 2).map((part) => part[0] || "").join("").toUpperCase(),
          )}</span>
          <div>
            <strong>${escapeHtml(user.display_name)}</strong>
            <span>@${escapeHtml(user.username)}</span>
          </div>
        </div>
        <div class="account-meta">
          ${statusPill(user)}
          ${user.must_change_password ? "<span class=\"account-note\">Password change required</span>" : ""}
        </div>
        ${userActions(user)}
      </article>
    `).join("");
  }

  function createForm() {
    if (!can("identity.user.create")) return "";
    return `
      <section class="account-panel account-create-panel" aria-labelledby="account-create-title">
        <div class="account-panel-heading">
          <div>
            <p class="account-eyebrow">New identity</p>
            <h2 id="account-create-title">Create account</h2>
          </div>
        </div>
        <form class="account-form" data-create-account novalidate>
          <label>
            <span>Display name</span>
            <input name="display_name" autocomplete="off" maxlength="200" required>
          </label>
          <label>
            <span>Username</span>
            <input name="username" autocomplete="off" minlength="3" maxlength="100" required>
          </label>
          <label class="account-form-wide">
            <span>Temporary password</span>
            <input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="500" required
              aria-describedby="account-password-help">
            <small id="account-password-help">At least 12 characters. HajiriFlow does not store this password in the browser.</small>
          </label>
          ${can("identity.role.assign") ? `
            <label>
              <span>Initial role</span>
              <select name="role_code">${roleOptions()}</select>
            </label>
          ` : ""}
          <label class="account-checkbox">
            <input name="must_change_password" type="checkbox" checked>
            <span>Require password change at first sign-in</span>
          </label>
          <div class="account-form-actions">
            <button class="account-button account-button-primary" type="submit">Create account</button>
          </div>
          <p class="account-form-status" data-create-status role="status" aria-live="polite"></p>
        </form>
      </section>
    `;
  }

  function renderShell(root) {
    root.innerHTML = `
      <div class="account-management" id="account-management-root">
        <section class="account-intro" aria-labelledby="account-heading">
          <div>
            <p class="account-eyebrow">Identity & authorization</p>
            <h1 id="account-heading">Access & accounts</h1>
            <p>Manage authenticated HajiriFlow accounts. Permissions remain enforced by the FastAPI backend; this screen never grants access by hiding or showing controls alone.</p>
          </div>
          <button class="account-button account-button-secondary" type="button" data-refresh-accounts>Refresh</button>
        </section>
        <div class="account-alert" data-account-alert role="status" aria-live="polite" hidden></div>
        ${createForm()}
        <section class="account-panel" aria-labelledby="account-list-title">
          <div class="account-panel-heading">
            <div><p class="account-eyebrow">Directory</p><h2 id="account-list-title">User accounts</h2></div>
            <label class="account-search">
              <span class="sr-only">Search accounts</span>
              <input type="search" data-account-search placeholder="Search name, username, or status" autocomplete="off">
            </label>
          </div>
          <div class="account-list" data-account-list aria-busy="true">
            <div class="account-loading" role="status">Loading protected account directory…</div>
          </div>
        </section>
      </div>
    `;
  }

  function setAlert(root, message, tone = "info") {
    const alert = root.querySelector("[data-account-alert]");
    if (!alert) return;
    alert.hidden = !message;
    alert.dataset.tone = tone;
    alert.textContent = message || "";
  }

  async function loadUsers(root, { announce = false } = {}) {
    const list = root.querySelector("[data-account-list]");
    if (list) list.setAttribute("aria-busy", "true");
    try {
      state.users = await window.HFIdentity.listUsers();
      renderUserList(root);
      if (announce) setAlert(root, "Account directory refreshed.", "success");
    } catch (error) {
      if (list) {
        list.innerHTML = `
          <div class="account-error" role="alert">
            <strong>Account directory unavailable.</strong>
            <p>${escapeHtml(error.message || "The request could not be completed.")}</p>
            <button class="account-button account-button-secondary" type="button" data-refresh-accounts>Retry</button>
          </div>
        `;
      }
    } finally {
      if (list) list.setAttribute("aria-busy", "false");
    }
  }

  async function createAccount(root, form) {
    if (state.busy) return;
    const status = form.querySelector("[data-create-status]");
    const submit = form.querySelector("button[type='submit']");
    const data = new FormData(form);
    const input = {
      display_name: String(data.get("display_name") || "").trim(),
      username: String(data.get("username") || "").trim(),
      password: String(data.get("password") || ""),
      must_change_password: data.get("must_change_password") === "on",
    };
    if (!input.display_name || input.username.length < 3 || input.password.length < 12) {
      status.dataset.tone = "error";
      status.textContent = "Enter a display name, a username of at least 3 characters, and a password of at least 12 characters.";
      return;
    }

    state.busy = true;
    submit.disabled = true;
    delete status.dataset.tone;
    status.textContent = "Creating account…";
    try {
      const created = await window.HFIdentity.createUser(input);
      const roleCode = can("identity.role.assign") ? String(data.get("role_code") || "") : "";
      let roleAssigned = false;
      if (roleCode) {
        try {
          await window.HFIdentity.assignRole(created.id, {
            role_code: roleCode,
            scope_type: "global",
            scope_id: null,
          });
          roleAssigned = true;
        } catch (roleError) {
          status.dataset.tone = "error";
          status.textContent = `Account created, but role assignment failed: ${roleError.message || "unknown error"}.`;
        }
      }
      form.reset();
      const passwordField = form.querySelector("input[name='password']");
      if (passwordField) passwordField.value = "";
      await loadUsers(root);
      if (!status.dataset.tone) {
        status.dataset.tone = "success";
        status.textContent = roleCode && roleAssigned
          ? "Account created and initial role assigned."
          : "Account created. It has no application role until one is assigned.";
      }
    } catch (error) {
      status.dataset.tone = "error";
      status.textContent = error.message || "Account creation failed.";
    } finally {
      state.busy = false;
      submit.disabled = false;
    }
  }

  async function changeStatus(root, button) {
    if (!can("identity.user.manage") || state.busy) return;
    const userId = button.dataset.userId;
    const nextStatus = button.dataset.accountStatus;
    const userName = button.dataset.userName || "this user";
    if (nextStatus === "disabled" && !window.confirm(`Disable ${userName}? Existing sessions will no longer be valid.`)) {
      return;
    }
    state.busy = true;
    button.disabled = true;
    setAlert(root, `${nextStatus === "disabled" ? "Disabling" : "Enabling"} ${userName}…`);
    try {
      await window.HFIdentity.setUserStatus(userId, nextStatus);
      await loadUsers(root);
      setAlert(root, `${userName} is now ${nextStatus}.`, "success");
    } catch (error) {
      setAlert(root, error.message || "Account status could not be changed.", "error");
    } finally {
      state.busy = false;
      button.disabled = false;
    }
  }

  async function assignRole(root, button) {
    if (!can("identity.role.assign") || state.busy) return;
    const userId = button.dataset.assignRole;
    const select = root.querySelector(`[data-role-select="${CSS.escape(userId)}"]`);
    const roleCode = select?.value;
    if (!roleCode) return;
    if (roleCode === "system_administrator" && !can(FULL_ACCESS)) {
      setAlert(root, "Only a system administrator can grant the system administrator role.", "error");
      return;
    }

    state.busy = true;
    button.disabled = true;
    setAlert(root, "Assigning role…");
    try {
      await window.HFIdentity.assignRole(userId, {
        role_code: roleCode,
        scope_type: "global",
        scope_id: null,
      });
      setAlert(root, "Role assigned. Server-side permission checks apply immediately to new requests.", "success");
    } catch (error) {
      setAlert(root, error.message || "Role assignment failed.", "error");
    } finally {
      state.busy = false;
      button.disabled = false;
    }
  }

  async function renderAccounts() {
    if (!accountRouteActive()) return;
    const workspace = document.getElementById("workspace");
    if (!workspace) return;
    setPageHeading();
    installNavigation();

    if (!can("identity.user.read")) {
      workspace.innerHTML = `
        <section class="account-denied" id="account-management-root" role="alert">
          <h1>Access restricted</h1>
          <p>Your authenticated account does not have permission to read the account directory.</p>
          <a class="account-button account-button-secondary" href="#overview">Return to overview</a>
        </section>
      `;
      return;
    }

    renderShell(workspace);
    await loadUsers(workspace);
  }

  function ensureRoute() {
    installNavigation();
    if (accountRouteActive() && !document.getElementById("account-management-root")) {
      renderAccounts();
    }
  }

  document.addEventListener("input", (event) => {
    const search = event.target.closest?.("[data-account-search]");
    if (!search) return;
    state.search = search.value;
    const root = document.getElementById("workspace");
    if (root) renderUserList(root);
  });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest?.("[data-create-account]");
    if (!form) return;
    event.preventDefault();
    const root = document.getElementById("workspace");
    if (root) createAccount(root, form);
  });

  document.addEventListener("click", (event) => {
    const root = document.getElementById("workspace");
    if (!root || !accountRouteActive()) return;
    const refresh = event.target.closest?.("[data-refresh-accounts]");
    if (refresh) {
      loadUsers(root, { announce: true });
      return;
    }
    const statusButton = event.target.closest?.("[data-account-status]");
    if (statusButton) {
      changeStatus(root, statusButton);
      return;
    }
    const roleButton = event.target.closest?.("[data-assign-role]");
    if (roleButton) assignRole(root, roleButton);
  });

  window.addEventListener("hajiriflow:identity-ready", () => {
    installNavigation();
    ensureRoute();
  });
  window.addEventListener("hashchange", () => queueMicrotask(ensureRoute));

  const nav = document.getElementById("primary-nav");
  if (nav) {
    new MutationObserver(() => queueMicrotask(installNavigation)).observe(nav, {
      childList: true,
      subtree: true,
    });
  }

  const workspace = document.getElementById("workspace");
  if (workspace) {
    new MutationObserver(() => queueMicrotask(ensureRoute)).observe(workspace, {
      childList: true,
    });
  }

  if (window.HFIdentity?.session) ensureRoute();
})();
