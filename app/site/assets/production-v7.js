(() => {
  "use strict";

  const config = window.__HAJIRIFLOW_CONFIG__ || {};
  const isProduction = config.environment === "production";
  const operationalDataMode = String(config.operationalDataMode || "demo");
  const HIDDEN_ACTIONS = new Set([
    "regenerate-demo",
    "confirm-regenerate",
    "change-employee-photo",
    "remove-employee-photo",
  ]);

  function hideNonProductionControls(root = document) {
    root.querySelectorAll?.("[data-action], [data-command-action]").forEach((element) => {
      const action = element.dataset.action || element.dataset.commandAction;
      if (HIDDEN_ACTIONS.has(action)) element.remove();
    });
    root.querySelectorAll?.(".profile-photo-actions").forEach((element) => element.remove());
    root.querySelectorAll?.(".provider-card.muted").forEach((element) => element.remove());
  }

  function statusRow(label, value, tone) {
    const row = document.createElement("div");
    row.className = "production-boundary-status";

    const marker = document.createElement("span");
    marker.className = `production-boundary-dot is-${tone}`;
    marker.setAttribute("aria-hidden", "true");

    const copy = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = label;
    const small = document.createElement("small");
    small.textContent = value;
    copy.append(strong, small);
    row.append(marker, copy);
    return row;
  }

  function createIntegrationBoundary(session) {
    const section = document.createElement("section");
    section.id = "production-data-boundary";
    section.className = "production-data-boundary";
    section.setAttribute("role", "status");
    section.setAttribute("aria-labelledby", "production-data-boundary-title");

    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "Production safety";

    const title = document.createElement("h2");
    title.id = "production-data-boundary-title";
    title.textContent = "Operational data connection required";

    const intro = document.createElement("p");
    intro.className = "production-boundary-intro";
    intro.textContent = "Your identity is verified, but this frontend release has not yet enabled an authoritative API-backed provider for workforce, attendance, device, reporting, and payroll records. Those views are locked rather than showing generated browser data as if it were live.";

    const statuses = document.createElement("div");
    statuses.className = "production-boundary-statuses";
    statuses.append(
      statusRow("Identity and access", `Verified as ${session?.user?.display_name || session?.user?.username || "authenticated user"}`, "ready"),
      statusRow("Operational records", "Locked until the API-backed data provider is enabled", "blocked"),
      statusRow("Generated demo records", "Never presented as authoritative production data", "blocked"),
    );

    const guidance = document.createElement("p");
    guidance.className = "production-boundary-guidance";
    guidance.textContent = "Deployment owners must connect the reviewed FastAPI/PostgreSQL application stack and complete production smoke evidence before enabling operational views.";

    const actions = document.createElement("div");
    actions.className = "production-boundary-actions";
    const signOut = document.createElement("button");
    signOut.className = "button button-secondary";
    signOut.type = "button";
    signOut.dataset.identityLogout = "";
    signOut.textContent = "Sign out";
    actions.append(signOut);

    section.append(eyebrow, title, intro, statuses, guidance, actions);
    return section;
  }

  function disableGeneratedWorkspace(session) {
    if (!isProduction || operationalDataMode !== "integration-required") return;

    document.documentElement.dataset.environment = "production";
    document.body.classList.add("production-data-blocked");

    const appMain = document.querySelector(".app-main");
    const workspace = document.getElementById("workspace");
    const skeleton = document.getElementById("app-skeleton");
    const existing = document.getElementById("production-data-boundary");
    if (workspace) {
      workspace.setAttribute("inert", "");
      workspace.setAttribute("aria-hidden", "true");
    }
    if (skeleton) skeleton.setAttribute("aria-hidden", "true");

    if (!existing && appMain) {
      const boundary = createIntegrationBoundary(session);
      appMain.append(boundary);
      boundary.querySelector("button")?.focus();
    }

    const kicker = document.getElementById("page-kicker");
    const title = document.getElementById("page-title");
    if (kicker) kicker.textContent = "Production safety";
    if (title) title.textContent = "Integration required";

    document.querySelectorAll("#primary-nav a, #primary-nav button, [data-action='open-command-menu']")
      .forEach((control) => {
        control.setAttribute("aria-disabled", "true");
        control.setAttribute("tabindex", "-1");
      });
  }

  function polish(root = document) {
    if (!isProduction) return;
    hideNonProductionControls(root);
    document.title = "HajiriFlow | Workforce Operations";
    document.documentElement.dataset.environment = "production";
  }

  if (isProduction) {
    const observer = new MutationObserver((records) => {
      records.forEach((record) => record.addedNodes.forEach((node) => {
        if (node instanceof Element) hideNonProductionControls(node);
      }));
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });

    window.addEventListener("hajiriflow:identity-ready", (event) => {
      polish(document);
      disableGeneratedWorkspace(event.detail?.session || window.HFIdentity?.session);
    });
    window.addEventListener("load", () => polish(document), { once: true });
    polish(document);
  }
})();
