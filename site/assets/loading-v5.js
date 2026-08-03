(() => {
  "use strict";

  const workspace = document.getElementById("workspace");
  const skeleton = document.getElementById("app-skeleton");
  if (!workspace || !skeleton) return;

  const INITIAL_MINIMUM_MS = 520;
  const ROUTE_MINIMUM_MS = 260;
  let loadingStartedAt = performance.now();
  let minimumDuration = INITIAL_MINIMUM_MS;
  let hideTimer = null;

  function showLoading(kind = "route") {
    window.clearTimeout(hideTimer);
    loadingStartedAt = performance.now();
    minimumDuration = kind === "initial" ? INITIAL_MINIMUM_MS : ROUTE_MINIMUM_MS;
    skeleton.dataset.loadingKind = kind;
    skeleton.hidden = false;
    document.body.classList.add("app-is-loading");
    workspace.setAttribute("aria-busy", "true");
  }

  function finishLoading() {
    if (!workspace.childElementCount) return;

    const elapsed = performance.now() - loadingStartedAt;
    const wait = Math.max(0, minimumDuration - elapsed);
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      skeleton.hidden = true;
      document.body.classList.remove("app-is-loading");
      workspace.setAttribute("aria-busy", "false");
      window.dispatchEvent(new CustomEvent("hajiriflow:content-ready", {
        detail: { route: location.hash.replace(/^#/, "") || "overview" },
      }));
    }, wait);
  }

  const observer = new MutationObserver(() => finishLoading());
  observer.observe(workspace, { childList: true, subtree: false });

  window.addEventListener("hashchange", () => showLoading("route"));
  window.addEventListener("hajiriflow:loading", (event) => showLoading(event.detail?.kind || "route"));
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) finishLoading();
  });

  showLoading("initial");
  if (workspace.childElementCount) finishLoading();
})();
