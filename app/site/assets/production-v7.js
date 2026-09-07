(() => {
  "use strict";

  const COPY_REPLACEMENTS = new Map([
    ["HajiriFlow Demo", "HajiriFlow"],
    ["Generated demo workspace", "Attendance operations online"],
    ["Live demo workspace", "Workforce operations"],
    [
      "Every figure below is calculated from the generated workforce dataset in this browser.",
      "Monitor attendance, leave, device health, and payroll activity across your organization.",
    ],
    ["Generated from daily evidence", "Calculated from attendance records"],
    [
      "A live workforce directory generated from the same state used by attendance and payroll.",
      "Manage employee profiles, assignments, attendance IDs, and employment status.",
    ],
    ["Across generated requests", "Across approved requests"],
    ["Current demo workflow", "Current leave workflow"],
    [
      "Generate exportable reports from the shared dynamic workforce state.",
      "Generate exportable reports from current workforce, attendance, leave, and payroll records.",
    ],
    ["Calculated from generated evidence", "Calculated from attendance records"],
    ["Across the generated history", "Across available attendance history"],
    ["Ready for client walkthrough", "Available report templates"],
    [
      "Review generated connectivity, registrations, and worker actions for each biometric reader.",
      "Review connectivity, registrations, and worker actions for each biometric reader.",
    ],
    ["Current generated health state", "Current reader health"],
    [
      "Generated payroll totals recalculate from attendance, salaries, deductions, and overtime.",
      "Payroll totals recalculate from attendance, salaries, deductions, and overtime.",
    ],
    ["Dynamic client workspace", "Data management"],
    [
      "This browser stores one coherent generated dataset. Regenerating replaces employees, attendance, leave, devices, payroll, and activity together.",
      "Export the current workforce snapshot for controlled backup or migration.",
    ],
    ["Generated browser provider", "Application data provider"],
    [
      "All screens share the window.HFData provider. A Supabase provider can replace persistence without rebuilding the presentation layer.",
      "Workforce modules share one application data provider and consistent permission boundary.",
    ],
    ["Signed-in demo user", "Signed-in user"],
    ["Changes saved to the dynamic demo", "Changes saved"],
    ["A new demo workspace was generated", "Workspace reset completed"],
  ]);

  const HIDDEN_ACTIONS = new Set([
    "regenerate-demo",
    "confirm-regenerate",
    "change-employee-photo",
    "remove-employee-photo",
  ]);

  function sanitizeText(root = document) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const replacement = COPY_REPLACEMENTS.get(node.nodeValue.trim());
      if (replacement) {
        node.nodeValue = node.nodeValue.replace(node.nodeValue.trim(), replacement);
      }
    });
  }

  function hideNonProductionControls(root = document) {
    root.querySelectorAll?.("[data-action], [data-command-action]").forEach((element) => {
      const action = element.dataset.action || element.dataset.commandAction;
      if (HIDDEN_ACTIONS.has(action)) element.remove();
    });

    root.querySelectorAll?.(".profile-photo-actions").forEach((element) => element.remove());
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
    if (
      state.workspace.name === "HajiriFlow"
      && state.workspace.organization !== "HajiriFlow Demo"
    ) return;

    window.HFData.mutate((draft) => {
      draft.workspace.name = "HajiriFlow";
      if (!draft.workspace.organization || /demo/i.test(draft.workspace.organization)) {
        draft.workspace.organization = "HajiriFlow Operations";
      }
    });
  }

  function polish(root = document) {
    sanitizeText(root);
    hideNonProductionControls(root);
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
