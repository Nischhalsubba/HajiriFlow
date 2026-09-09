(() => {
  "use strict";

  const FULL_ACCESS = "system.full_access";

  function can(permission) {
    const codes = new Set(
      (window.HFIdentity?.session?.permissions || []).map((item) => item.code),
    );
    return codes.has(FULL_ACCESS) || codes.has(permission);
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
    layer.replaceChildren();
  }

  function createField(labelText, input) {
    const label = document.createElement("label");
    const labelValue = document.createElement("span");
    labelValue.textContent = labelText;
    label.append(labelValue, input);
    return label;
  }

  function createAccountDialog(user) {
    const section = document.createElement("section");
    section.className = "account-panel account-edit-dialog";
    section.setAttribute("role", "dialog");
    section.setAttribute("aria-modal", "true");
    section.setAttribute("aria-labelledby", "account-edit-title");

    const heading = document.createElement("div");
    heading.className = "account-panel-heading";

    const headingCopy = document.createElement("div");
    const eyebrow = document.createElement("p");
    eyebrow.className = "account-eyebrow";
    eyebrow.textContent = "Account identity";
    const title = document.createElement("h2");
    title.id = "account-edit-title";
    title.textContent = `Edit ${user.display_name}`;
    headingCopy.append(eyebrow, title);

    const closeButton = document.createElement("button");
    closeButton.className = "account-button account-button-secondary";
    closeButton.type = "button";
    closeButton.dataset.accountEditClose = "";
    closeButton.textContent = "Close";
    heading.append(headingCopy, closeButton);

    const form = document.createElement("form");
    form.className = "account-form";
    form.dataset.accountEditForm = "";
    form.noValidate = true;

    const displayName = document.createElement("input");
    displayName.name = "display_name";
    displayName.maxLength = 200;
    displayName.required = true;
    displayName.value = user.display_name || "";

    const username = document.createElement("input");
    username.name = "username";
    username.minLength = 3;
    username.maxLength = 100;
    username.required = true;
    username.value = user.username || "";

    const employeeSearch = document.createElement("input");
    employeeSearch.name = "employee_search";
    employeeSearch.type = "search";
    employeeSearch.autocomplete = "off";
    employeeSearch.placeholder = "Search employee code or name";
    const employeeSearchField = createField("Find employee to link", employeeSearch);
    employeeSearchField.className = "account-form-wide";
    const employeeHint = document.createElement("small");
    employeeHint.textContent =
      "Linking or unlinking an employee invalidates the edited account's active sessions.";
    employeeSearchField.append(employeeHint);

    const employeeSelect = document.createElement("select");
    employeeSelect.name = "employee_id";
    employeeSelect.dataset.accountEmployeeSelect = "";
    employeeSelect.add(new Option("No employee link", ""));
    if (user.employee_id) {
      employeeSelect.add(
        new Option(`Current employee · ${user.employee_id}`, user.employee_id, true, true),
      );
    }
    const employeeSelectField = createField("Employee link", employeeSelect);
    employeeSelectField.className = "account-form-wide";

    const actions = document.createElement("div");
    actions.className = "account-form-actions";
    const saveButton = document.createElement("button");
    saveButton.className = "account-button account-button-primary";
    saveButton.type = "submit";
    saveButton.textContent = "Save account";
    actions.append(saveButton);

    const status = document.createElement("p");
    status.className = "account-form-status";
    status.dataset.accountEditStatus = "";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    form.append(
      createField("Display name", displayName),
      createField("Username", username),
      employeeSearchField,
      employeeSelectField,
      actions,
      status,
    );
    section.append(heading, form);
    return section;
  }

  async function openDialog(userId) {
    const layer = document.getElementById("modal-layer");
    if (!layer) return;
    const users = await window.HFIdentity.searchUsers({ limit: 200 });
    const user = users.find((item) => item.id === userId);
    if (!user) throw new Error("Account could not be loaded.");
    layer.replaceChildren(createAccountDialog(user));
    layer.hidden = false;
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
        const options = [new Option("No employee link", "")];
        for (const row of rows) {
          options.push(
            new Option(
              `${row.organization_name} · ${row.employee_code} · ${row.display_name}`,
              row.id,
            ),
          );
        }
        select.replaceChildren(...options);
        if ([...select.options].some((option) => option.value === current)) select.value = current;
      } catch {
        select.replaceChildren(new Option("Employee search unavailable", ""));
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
      status.textContent =
        "Account updated. Security-sensitive changes invalidated its prior sessions.";
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
      document
        .querySelector("[data-edit-account][aria-expanded='true']")
        ?.removeAttribute("aria-expanded");
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
