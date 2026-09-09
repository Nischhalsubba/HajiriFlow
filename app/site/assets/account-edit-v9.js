(() => {
  "use strict";

  const FULL_ACCESS = "system.full_access";

  function can(permission) {
    const codes = new Set(
      (window.HFIdentity?.session?.permissions || []).map((item) => item.code),
    );
    return codes.has(FULL_ACCESS) || codes.has(permission);
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

  function installEditButtons(root = document) {
    if (!can("identity.user.manage")) return;
    const currentId = window.HFIdentity?.session?.user?.id;
    root.querySelectorAll?.(".account-row[data-account-user]").forEach((row) => {
      if (row.dataset.accountUser === currentId) return;
      const actions = row.querySelector(".account-actions");
      if (!actions || actions.querySelector("[data-edit-account]")) return;
      const button = document.createElement("button");
      button.className = "account-button account-button-secondary";
      button.type = "button";
      button.dataset.editAccount = row.dataset.accountUser;
      button.textContent = "Edit account";
      actions.prepend(button);
    });
  }

  function closeDialog() {
    const layer = document.getElementById("modal-layer");
    if (!layer) return;
    layer.hidden = true;
    layer.innerHTML = "";
  }

  async function openDialog(userId) {
    const layer = document.getElementById("modal-layer");
    if (!layer) return;
    const users = await window.HFIdentity.searchUsers({ limit: 200 });
    const user = users.find((item) => item.id === userId);
    if (!user) throw new Error("Account could not be loaded.");
    layer.hidden = false;
    layer.innerHTML = `
      <section class="account-panel account-edit-dialog" role="dialog" aria-modal="true"
        aria-labelledby="account-edit-title">
        <div class="account-panel-heading">
          <div>
            <p class="account-eyebrow">Account identity</p>
            <h2 id="account-edit-title">Edit ${escapeHtml(user.display_name)}</h2>
          </div>
          <button class="account-button account-button-secondary" type="button" data-account-edit-close>Close</button>
        </div>
        <form class="account-form" data-account-edit-form novalidate>
          <label>
            <span>Display name</span>
            <input name="display_name" maxlength="200" required value="${escapeHtml(user.display_name)}">
          </label>
          <label>
            <span>Username</span>
            <input name="username" minlength="3" maxlength="100" required value="${escapeHtml(user.username)}">
          </label>
          <label class="account-form-wide">
            <span>Find employee to link</span>
            <input name="employee_search" type="search" autocomplete="off"
              placeholder="Search employee code or name">
            <small>Linking or unlinking an employee invalidates the edited account's active sessions.</small>
          </label>
          <label class="account-form-wide">
            <span>Employee link</span>
            <select name="employee_id" data-account-employee-select>
              <option value="">No employee link</option>
              ${user.employee_id ? `<option value="${escapeHtml(user.employee_id)}" selected>Current employee · ${escapeHtml(user.employee_id)}</option>` : ""}
            </select>
          </label>
          <div class="account-form-actions">
            <button class="account-button account-button-primary" type="submit">Save account</button>
          </div>
          <p class="account-form-status" data-account-edit-status role="status" aria-live="polite"></p>
        </form>
      </section>
    `;
    layer.querySelector("input[name='display_name']")?.focus();
  }

  let employeeSearchTimer = null;
  document.addEventListener("input", (event) => {
    const input = event.target.closest?.("[data-account-edit-form] input[name='employee_search']");
    if (!input) return;
    clearTimeout(employeeSearchTimer);
    employeeSearchTimer = setTimeout(async () => {
      const form = input.closest("form");
      const select = form?.querySelector("[data-account-employee-select]");
      if (!select) return;
      const current = select.value;
      try {
        const rows = await window.HFIdentity.searchEmployeeLinks({
          query: input.value.trim(),
          limit: 25,
        });
        select.innerHTML = '<option value="">No employee link</option>' + rows.map((row) => (
          `<option value="${escapeHtml(row.id)}">${escapeHtml(row.organization_name)} · ${escapeHtml(row.employee_code)} · ${escapeHtml(row.display_name)}</option>`
        )).join("");
        if ([...select.options].some((option) => option.value === current)) select.value = current;
      } catch {
        select.innerHTML = '<option value="">Employee search unavailable</option>';
      }
    }, 250);
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest?.("[data-account-edit-form]");
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    const status = form.querySelector("[data-account-edit-status]");
    const editButton = document.querySelector("[data-edit-account][aria-expanded='true']");
    const userId = editButton?.dataset.editAccount;
    if (!userId) return;
    const data = new FormData(form);
    const displayName = String(data.get("display_name") || "").trim();
    const username = String(data.get("username") || "").trim();
    if (!displayName || username.length < 3) {
      status.textContent = "Enter a display name and a username of at least 3 characters.";
      status.dataset.tone = "error";
      return;
    }
    button.disabled = true;
    status.textContent = "Saving account…";
    delete status.dataset.tone;
    try {
      await window.HFIdentity.updateUser(userId, {
        display_name: displayName,
        username,
        employee_id: String(data.get("employee_id") || "") || null,
      });
      status.dataset.tone = "success";
      status.textContent = "Account updated. Security-sensitive changes invalidated its prior sessions.";
      setTimeout(() => {
        editButton.removeAttribute("aria-expanded");
        closeDialog();
        document.querySelector("[data-refresh-accounts]")?.click();
      }, 300);
    } catch (error) {
      status.dataset.tone = "error";
      status.textContent = error.message || "Account could not be updated.";
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener("click", async (event) => {
    const close = event.target.closest?.("[data-account-edit-close]");
    if (close) {
      document.querySelector("[data-edit-account][aria-expanded='true']")?.removeAttribute("aria-expanded");
      closeDialog();
      return;
    }
    const button = event.target.closest?.("[data-edit-account]");
    if (!button) return;
    try {
      button.setAttribute("aria-expanded", "true");
      await openDialog(button.dataset.editAccount);
    } catch (error) {
      button.removeAttribute("aria-expanded");
      window.alert(error.message || "Account editor could not be opened.");
    }
  });

  const observer = new MutationObserver((records) => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (node instanceof Element) installEditButtons(node);
      }
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("hajiriflow:identity-ready", () => installEditButtons(document));
  installEditButtons(document);
})();
