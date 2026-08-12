(() => {
  "use strict";

  const { animate, stagger } = window.Motion || {};
  if (!animate || !stagger) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const workspace = document.getElementById("workspace");
  const modalLayer = document.getElementById("modal-layer");
  const commandLayer = document.getElementById("command-layer");
  const primaryNav = document.getElementById("primary-nav");

  function canAnimate() {
    return !reducedMotion.matches;
  }

  function revealWorkspace() {
    if (!canAnimate() || !workspace) return;

    const candidates = [...workspace.querySelectorAll([
      ".welcome-row",
      ".page-intro",
      ".metric-card",
      ".summary-strip",
      ".panel",
      ".report-card",
      ".device-card",
      ".payroll-summary",
      ".table-panel",
    ].join(","))].filter((element) => element.dataset.motionReady !== "true");

    if (!candidates.length) return;
    candidates.forEach((element) => { element.dataset.motionReady = "true"; });

    animate(candidates, {
      opacity: [0, 1],
      y: [14, 0],
      scale: [0.992, 1],
    }, {
      duration: 0.48,
      delay: stagger(0.035, { startDelay: 0.02 }),
      ease: [0.22, 1, 0.36, 1],
    });
  }

  function animateLayer(layer) {
    if (!canAnimate() || !layer || layer.hidden) return;
    const panel = layer.querySelector(".modal, .command-panel");
    if (!panel) return;

    animate(layer, { opacity: [0, 1] }, { duration: 0.18, ease: "easeOut" });
    animate(panel, {
      opacity: [0, 1],
      y: [18, 0],
      scale: [0.975, 1],
    }, {
      duration: 0.34,
      ease: [0.22, 1, 0.36, 1],
    });
  }

  function animateActiveNavigation() {
    if (!canAnimate() || !primaryNav) return;
    const active = primaryNav.querySelector(".nav-link.is-active");
    if (!active || active.dataset.activeMotion === "true") return;

    primaryNav.querySelectorAll(".nav-link").forEach((link) => delete link.dataset.activeMotion);
    active.dataset.activeMotion = "true";
    animate(active, { x: [-5, 0], opacity: [0.72, 1] }, {
      duration: 0.3,
      ease: [0.22, 1, 0.36, 1],
    });
  }

  window.addEventListener("hajiriflow:content-ready", revealWorkspace);
  window.addEventListener("hajiriflow:avatar-loaded", (event) => {
    if (!canAnimate()) return;
    animate(event.detail.image, { opacity: [0, 1], scale: [1.08, 1] }, {
      duration: 0.42,
      ease: [0.22, 1, 0.36, 1],
    });
  });

  document.addEventListener("pointerdown", (event) => {
    if (!canAnimate()) return;
    const target = event.target.closest(".button, .icon-button, .nav-link, .search-trigger, .user-card");
    if (target) animate(target, { scale: 0.975 }, { duration: 0.1, ease: "easeOut" });
  });

  document.addEventListener("pointerup", (event) => {
    if (!canAnimate()) return;
    const target = event.target.closest(".button, .icon-button, .nav-link, .search-trigger, .user-card");
    if (target) animate(target, { scale: 1 }, { duration: 0.18, ease: [0.22, 1, 0.36, 1] });
  });

  document.addEventListener("pointercancel", (event) => {
    const target = event.target.closest?.(".button, .icon-button, .nav-link, .search-trigger, .user-card");
    if (target && canAnimate()) animate(target, { scale: 1 }, { duration: 0.12 });
  });

  if (workspace) {
    new MutationObserver(() => requestAnimationFrame(revealWorkspace))
      .observe(workspace, { childList: true });
  }

  [modalLayer, commandLayer].filter(Boolean).forEach((layer) => {
    new MutationObserver(() => requestAnimationFrame(() => animateLayer(layer)))
      .observe(layer, { childList: true, attributes: true, attributeFilter: ["hidden"] });
  });

  if (primaryNav) {
    new MutationObserver(() => requestAnimationFrame(animateActiveNavigation))
      .observe(primaryNav, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  }

  revealWorkspace();
  animateActiveNavigation();
})();
