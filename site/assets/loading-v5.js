(() => {
  "use strict";

  const workspace = document.getElementById("workspace");
  const skeleton = document.getElementById("app-skeleton");
  if (!workspace || !skeleton) return;

  const INITIAL_MINIMUM_MS = 520;
  const ROUTE_MINIMUM_MS = 260;
  const STARTUP_FAILURE_MS = 8000;
  let loadingStartedAt = performance.now();
  let minimumDuration = INITIAL_MINIMUM_MS;
  let hideTimer = null;
  let failureTimer = null;
  let loadingComplete = false;

  function installIdempotentTitleGuard() {
    if (document.__hajiriFlowTitleGuard === true) return;

    let prototype = document;
    let descriptor = null;
    while (prototype && !descriptor) {
      prototype = Object.getPrototypeOf(prototype);
      descriptor = prototype ? Object.getOwnPropertyDescriptor(prototype, "title") : null;
    }

    if (!descriptor?.get || !descriptor?.set) return;

    Object.defineProperty(document, "title", {
      configurable: true,
      enumerable: descriptor.enumerable,
      get() {
        return descriptor.get.call(document);
      },
      set(value) {
        const nextTitle = String(value);
        if (descriptor.get.call(document) !== nextTitle) {
          descriptor.set.call(document, nextTitle);
        }
      },
    });
    Object.defineProperty(document, "__hajiriFlowTitleGuard", {
      configurable: false,
      value: true,
    });
  }

  function scheduleFailureFallback() {
    window.clearTimeout(failureTimer);
    failureTimer = window.setTimeout(() => {
      if (loadingComplete) return;
      if (workspace.childElementCount) {
        finishLoading(true);
        return;
      }
      showFailure("HajiriFlow could not finish loading this page.");
    }, STARTUP_FAILURE_MS);
  }

  function showLoading(kind = "route") {
    window.clearTimeout(hideTimer);
    loadingComplete = false;
    loadingStartedAt = performance.now();
    minimumDuration = kind === "initial" ? INITIAL_MINIMUM_MS : ROUTE_MINIMUM_MS;
    skeleton.dataset.loadingKind = kind;
    skeleton.hidden = false;
    document.body.classList.add("app-is-loading");
    workspace.setAttribute("aria-busy", "true");
    scheduleFailureFallback();
  }

  function finishLoading(force = false) {
    if (!workspace.childElementCount) return;

    const elapsed = performance.now() - loadingStartedAt;
    const wait = force ? 0 : Math.max(0, minimumDuration - elapsed);
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      loadingComplete = true;
      window.clearTimeout(failureTimer);
      skeleton.hidden = true;
      document.body.classList.remove("app-is-loading");
      workspace.setAttribute("aria-busy", "false");
      window.dispatchEvent(new CustomEvent("hajiriflow:content-ready", {
        detail: { route: location.hash.replace(/^#/, "") || "overview" },
      }));
    }, wait);
  }

  function showFailure(message) {
    if (!document.body.classList.contains("app-is-loading")) return;

    const panel = document.createElement("section");
    panel.className = "panel";
    panel.setAttribute("role", "alert");

    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "Unable to load workspace";

    const title = document.createElement("h2");
    title.textContent = "The page did not start correctly";

    const copy = document.createElement("p");
    copy.textContent = message;

    const button = document.createElement("button");
    button.className = "button button-primary";
    button.type = "button";
    button.textContent = "Reload HajiriFlow";
    button.addEventListener("click", () => window.location.reload());

    panel.append(eyebrow, title, copy, button);
    workspace.replaceChildren(panel);
    finishLoading(true);
  }

  installIdempotentTitleGuard();

  const observer = new MutationObserver(() => finishLoading());
  observer.observe(workspace, { childList: true, subtree: false });

  window.addEventListener("hashchange", () => showLoading("route"));
  window.addEventListener("hajiriflow:loading", (event) => showLoading(event.detail?.kind || "route"));
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) finishLoading(true);
  });
  window.addEventListener("error", (event) => {
    if (event.error) showFailure("A startup script failed. Reload the page to try again.");
  });
  window.addEventListener("unhandledrejection", () => {
    showFailure("A startup task failed. Reload the page to try again.");
  });

  showLoading("initial");
  if (workspace.childElementCount) finishLoading();
})();
