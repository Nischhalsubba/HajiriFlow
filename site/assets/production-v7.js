(() => {
  "use strict";

  const COPY_REPLACEMENTS = new Map([
    ["HajiriFlow Demo", "HajiriFlow"],
    ["Generated demo workspace", "Attendance operations online"],
    ["Live demo workspace", "Workforce operations"],
    ["Every figure below is calculated from the generated workforce dataset in this browser.", "Monitor attendance, leave, device health, and payroll activity across your organization."],
    ["Generated from daily evidence", "Calculated from attendance records"],
    ["A live workforce directory generated from the same state used by attendance and payroll.", "Manage employee profiles, assignments, attendance IDs, and employment status."],
    ["Across generated requests", "Across approved requests"],
    ["Current demo workflow", "Current leave workflow"],
    ["Generate exportable reports from the shared dynamic workforce state.", "Generate exportable reports from current workforce, attendance, leave, and payroll records."],
    ["Calculated from generated evidence", "Calculated from attendance records"],
    ["Across the generated history", "Across available attendance history"],
    ["Ready for client walkthrough", "Available report templates"],
    ["Review generated connectivity, registrations, and worker actions for each biometric reader.", "Review connectivity, registrations, and worker actions for each biometric reader."],
    ["Current generated health state", "Current reader health"],
    ["Generated payroll totals recalculate from attendance, salaries, deductions, and overtime.", "Payroll totals recalculate from attendance, salaries, deductions, and overtime."],
    ["Dynamic client workspace", "Data management"],
    ["This browser stores one coherent generated dataset. Regenerating replaces employees, attendance, leave, devices, payroll, and activity together.", "Export the current workforce snapshot for controlled backup or migration."],
    ["Generated browser provider", "Application data provider"],
    ["All screens share the window.HFData provider. A Supabase provider can replace persistence without rebuilding the presentation layer.", "Workforce modules share one application data provider and consistent permission boundary."],
    ["Signed-in demo user", "Signed-in user"],
    ["Changes saved to the dynamic demo", "Changes saved"],
    ["A new demo workspace was generated", "Workspace reset completed"],
  ]);

  const HIDDEN_ACTIONS = new Set(["regenerate-demo", "confirm-regenerate"]);
  const MAX_PHOTO_BYTES = 3 * 1024 * 1024;
  const TARGET_PHOTO_SIZE = 480;

  function sanitizeText(root = document) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const replacement = COPY_REPLACEMENTS.get(node.nodeValue.trim());
      if (replacement) node.nodeValue = node.nodeValue.replace(node.nodeValue.trim(), replacement);
    });
  }

  function hideNonProductionControls(root = document) {
    root.querySelectorAll?.("[data-action], [data-command-action]").forEach((element) => {
      const action = element.dataset.action || element.dataset.commandAction;
      if (HIDDEN_ACTIONS.has(action)) element.remove();
    });

    root.querySelectorAll?.(".provider-card.muted").forEach((element) => element.remove());

    root.querySelectorAll?.(".data-facts > div").forEach((row) => {
      const label = row.querySelector("dt")?.textContent?.trim().toLowerCase();
      if (label === "dataset seed" || label === "generated") row.remove();
    });
  }

  function normalizeWorkspaceIdentity() {
    if (!window.HFData?.mutate) return;
    const state = window.HFData.getState?.();
    if (!state?.workspace) return;
    if (state.workspace.name === "HajiriFlow" && state.workspace.organization !== "HajiriFlow Demo") return;

    window.HFData.mutate((draft) => {
      draft.workspace.name = "HajiriFlow";
      if (!draft.workspace.organization || /demo/i.test(draft.workspace.organization)) {
        draft.workspace.organization = "HajiriFlow Operations";
      }
    });
  }

  function toast(message, kind = "success") {
    const region = document.querySelector("#toast-region");
    if (!region) return;
    const item = document.createElement("div");
    item.className = `toast toast-${kind}`;
    item.innerHTML = `<span aria-hidden="true">${kind === "danger" ? "!" : "✓"}</span><span>${message}</span>`;
    region.append(item);
    requestAnimationFrame(() => item.classList.add("is-visible"));
    window.setTimeout(() => {
      item.classList.remove("is-visible");
      window.setTimeout(() => item.remove(), 180);
    }, 3000);
  }

  function cropPhoto(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.addEventListener("error", () => reject(new Error("Unable to read the selected photo.")), { once: true });
      reader.addEventListener("load", () => {
        const image = new Image();
        image.addEventListener("error", () => reject(new Error("The selected file is not a valid image.")), { once: true });
        image.addEventListener("load", () => {
          const canvas = document.createElement("canvas");
          canvas.width = TARGET_PHOTO_SIZE;
          canvas.height = TARGET_PHOTO_SIZE;
          const context = canvas.getContext("2d", { alpha: false });
          if (!context) {
            reject(new Error("Photo processing is unavailable in this browser."));
            return;
          }

          const sourceSize = Math.min(image.naturalWidth, image.naturalHeight);
          const sourceX = Math.max(0, (image.naturalWidth - sourceSize) / 2);
          const sourceY = Math.max(0, (image.naturalHeight - sourceSize) / 2);
          context.fillStyle = "#ffffff";
          context.fillRect(0, 0, TARGET_PHOTO_SIZE, TARGET_PHOTO_SIZE);
          context.drawImage(
            image,
            sourceX,
            sourceY,
            sourceSize,
            sourceSize,
            0,
            0,
            TARGET_PHOTO_SIZE,
            TARGET_PHOTO_SIZE,
          );
          resolve(canvas.toDataURL("image/jpeg", 0.86));
        }, { once: true });
        image.src = String(reader.result);
      }, { once: true });
      reader.readAsDataURL(file);
    });
  }

  async function handlePhotoSelection(name, input) {
    const file = input.files?.[0];
    if (!file) return;
    if (!/^image\/(jpeg|png|webp)$/i.test(file.type)) {
      toast("Choose a JPG, PNG, or WebP photo.", "danger");
      input.value = "";
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      toast("Employee photos must be 3 MB or smaller.", "danger");
      input.value = "";
      return;
    }

    try {
      const dataUrl = await cropPhoto(file);
      window.HFMedia?.setPhoto(name, dataUrl);
      toast("Employee photo updated.");
      enhanceProfilePhotoControls();
    } catch (error) {
      toast(error.message || "Could not update the employee photo.", "danger");
    } finally {
      input.value = "";
    }
  }

  function enhanceProfilePhotoControls() {
    const modal = document.querySelector("#modal-layer:not([hidden]) .modal");
    const profile = modal?.querySelector(".profile-sheet");
    const title = modal?.querySelector("#modal-title")?.textContent?.trim();
    if (!modal || !profile || !title || profile.querySelector(".profile-photo-actions")) return;

    const controls = document.createElement("div");
    controls.className = "profile-photo-actions";
    controls.innerHTML = `
      <input class="visually-hidden" id="employee-photo-input" type="file" accept="image/jpeg,image/png,image/webp">
      <label class="button button-secondary" for="employee-photo-input"><span>Change photo</span></label>
      <button class="button button-ghost" type="button" data-remove-employee-photo><span>Use licensed portrait</span></button>
    `;

    const identity = profile.querySelector(".profile-identity");
    identity?.append(controls);

    const input = controls.querySelector("#employee-photo-input");
    input?.addEventListener("change", () => handlePhotoSelection(title, input));
    controls.querySelector("[data-remove-employee-photo]")?.addEventListener("click", () => {
      window.HFMedia?.removePhoto(title);
      toast("Licensed portrait restored.");
    });
  }

  function polish(root = document) {
    sanitizeText(root);
    hideNonProductionControls(root);
    enhanceProfilePhotoControls();
    document.title = "HajiriFlow | Workforce Operations";
    document.documentElement.dataset.environment = "production";
  }

  const observer = new MutationObserver((records) => {
    records.forEach((record) => record.addedNodes.forEach((node) => {
      if (node instanceof Element) polish(node);
    }));
    polish(document);
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("load", () => {
    normalizeWorkspaceIdentity();
    polish(document);
  }, { once: true });
  polish(document);
})();