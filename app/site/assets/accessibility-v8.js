(() => {
  "use strict";

  const workspace = document.getElementById("workspace");
  const modalLayer = document.getElementById("modal-layer");
  const commandLayer = document.getElementById("command-layer");
  const pageTitle = document.getElementById("page-title");
  const focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  let lastOutsideFocus = null;

  function isVisible(element) {
    return element instanceof HTMLElement
      && !element.hidden
      && element.getAttribute("aria-hidden") !== "true"
      && element.getClientRects().length > 0;
  }

  function focusableWithin(container) {
    return [...container.querySelectorAll(focusableSelector)].filter(isVisible);
  }

  function activeDialogLayer() {
    if (modalLayer && !modalLayer.hidden) return modalLayer;
    if (commandLayer && !commandLayer.hidden) return commandLayer;
    return null;
  }

  function restoreOutsideFocus() {
    if (activeDialogLayer()) return;
    if (lastOutsideFocus instanceof HTMLElement && lastOutsideFocus.isConnected) {
      lastOutsideFocus.focus({ preventScroll: true });
    }
  }

  function ensureLayerFocus(layer) {
    if (layer.contains(document.activeElement)) return;
    const candidate = focusableWithin(layer)[0];
    candidate?.focus({ preventScroll: true });
  }

  function handleDialogKeydown(event) {
    const layer = activeDialogLayer();
    if (!layer) return;

    if (event.key === "Escape") {
      requestAnimationFrame(restoreOutsideFocus);
      return;
    }
    if (event.key !== "Tab") return;

    const items = focusableWithin(layer);
    if (!items.length) {
      event.preventDefault();
      return;
    }

    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function humanizeAction(value) {
    const words = String(value || "").replaceAll("-", " ").trim();
    return words ? `${words[0].toUpperCase()}${words.slice(1)}` : "Action";
  }

  function enhanceButtons(root) {
    root.querySelectorAll("button").forEach((button) => {
      if (button.hasAttribute("aria-label") || button.textContent.trim()) return;
      button.setAttribute("aria-label", humanizeAction(button.dataset.action));
    });
  }

  function tableLabel(container) {
    const panel = container.closest(".panel, .table-panel");
    const heading = panel?.querySelector("h2, h3")?.textContent?.trim();
    return heading ? `${heading} table` : `${pageTitle?.textContent?.trim() || "HajiriFlow"} table`;
  }

  function enhanceTables(root) {
    root.querySelectorAll(".table-scroll, .table-wrap").forEach((container) => {
      if (!container.hasAttribute("tabindex")) container.tabIndex = 0;
      container.setAttribute("role", "region");
      if (!container.hasAttribute("aria-label")) {
        container.setAttribute("aria-label", tableLabel(container));
      }

      container.querySelectorAll("th").forEach((header) => {
        if (!header.hasAttribute("scope")) header.setAttribute("scope", "col");
        if (!header.textContent.trim() && !header.hasAttribute("aria-label")) {
          header.setAttribute("aria-label", "Actions");
        }
      });
    });
  }

  function enhance(root = document) {
    enhanceButtons(root);
    enhanceTables(root);
  }

  document.addEventListener("focusin", (event) => {
    const layer = activeDialogLayer();
    if (!layer || !layer.contains(event.target)) {
      if (event.target instanceof HTMLElement) lastOutsideFocus = event.target;
    }
  });
  document.addEventListener("keydown", handleDialogKeydown);

  [modalLayer, commandLayer].filter(Boolean).forEach((layer) => {
    const observer = new MutationObserver(() => {
      if (layer.hidden) {
        requestAnimationFrame(restoreOutsideFocus);
      } else {
        enhance(layer);
        requestAnimationFrame(() => ensureLayerFocus(layer));
      }
    });
    observer.observe(layer, { attributes: true, childList: true, subtree: true });
  });

  if (workspace) {
    const observer = new MutationObserver(() => enhance(workspace));
    observer.observe(workspace, { childList: true, subtree: true });
  }

  enhance(document);
})();
