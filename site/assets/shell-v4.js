(() => {
  "use strict";

  const shell = document.getElementById("app-shell");
  const sidebar = document.getElementById("sidebar");
  const menuButton = document.querySelector("[data-open-sidebar]");
  const nav = document.getElementById("primary-nav");
  const desktopQuery = window.matchMedia("(min-width: 1101px)");
  const STORAGE_KEY = "hajiriflow_sidebar_collapsed_v4";

  if (!shell || !sidebar || !menuButton) return;

  function storedCollapsed() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  }

  function storeCollapsed(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
      // Storage can be unavailable in private or restricted browser contexts.
    }
  }

  function isDesktop() {
    return desktopQuery.matches;
  }

  function setMobileOpen(open) {
    shell.classList.toggle("sidebar-is-open", open);
    document.body.classList.toggle("nav-lock", open);
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  }

  function setDesktopCollapsed(collapsed, persist = true) {
    shell.classList.toggle("sidebar-is-collapsed", collapsed);
    shell.classList.remove("sidebar-is-open");
    document.body.classList.remove("nav-lock");
    menuButton.setAttribute("aria-expanded", String(!collapsed));
    menuButton.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
    menuButton.title = collapsed ? "Expand navigation" : "Collapse navigation";
    if (persist) storeCollapsed(collapsed);
  }

  function syncForViewport() {
    menuButton.setAttribute("aria-controls", "sidebar");
    if (isDesktop()) {
      setDesktopCollapsed(storedCollapsed(), false);
    } else {
      shell.classList.remove("sidebar-is-collapsed");
      setMobileOpen(false);
      menuButton.title = "Open navigation";
    }
  }

  function annotateNavigation() {
    nav?.querySelectorAll(".nav-link").forEach((link) => {
      const label = link.querySelector("span")?.textContent?.trim();
      if (label) link.title = label;
    });
  }

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open-sidebar]");
    if (opener) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (isDesktop()) {
        setDesktopCollapsed(!shell.classList.contains("sidebar-is-collapsed"));
      } else {
        setMobileOpen(!shell.classList.contains("sidebar-is-open"));
      }
      return;
    }

    const closer = event.target.closest("[data-close-sidebar]");
    if (closer) {
      event.preventDefault();
      event.stopImmediatePropagation();
      setMobileOpen(false);
      return;
    }

    if (!isDesktop() && event.target.closest(".nav-link")) {
      setMobileOpen(false);
    }
  }, true);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && shell.classList.contains("sidebar-is-open")) {
      setMobileOpen(false);
      menuButton.focus();
    }
  }, true);

  desktopQuery.addEventListener?.("change", syncForViewport);
  window.addEventListener("resize", syncForViewport, { passive: true });

  if (nav) {
    new MutationObserver(annotateNavigation).observe(nav, { childList: true, subtree: true });
  }

  syncForViewport();
  annotateNavigation();
})();
