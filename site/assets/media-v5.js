(() => {
  "use strict";

  const AVATAR_ENDPOINT = "https://api.dicebear.com/10.x/notionists-neutral/svg";
  const AVATAR_SELECTOR = ".person-avatar, .user-avatar, .avatar-button";

  function initials(value) {
    return String(value || "HF")
      .trim()
      .split(/\s+/)
      .map((part) => part[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "HF";
  }

  function personName(element) {
    if (element.matches(".user-avatar, .avatar-button")) return "Nischhal Subba";

    const scopes = [
      element.closest(".person-cell"),
      element.closest(".profile-identity"),
      element.closest(".mini-person"),
      element.closest("article"),
      element.parentElement,
    ].filter(Boolean);

    for (const scope of scopes) {
      const candidate = scope.querySelector("h2, h3, strong");
      const value = candidate?.textContent?.trim();
      if (value && value.length > 1) return value;
    }

    return element.textContent?.trim() || "HajiriFlow user";
  }

  function avatarUrl(seed, simplified = false) {
    const params = new URLSearchParams({
      seed,
      size: "160",
      borderRadius: "50",
    });

    if (!simplified) {
      params.set("backgroundColor", "dbeafe,e0e7ff,ccfbf1,fef3c7,fce7f3");
      params.set("backgroundColorFill", "solid");
    }

    return `${AVATAR_ENDPOINT}?${params.toString()}`;
  }

  function enhanceAvatar(element) {
    if (!(element instanceof HTMLElement) || element.dataset.openMedia === "true") return;

    const name = personName(element);
    const fallback = initials(name);
    const image = new Image();
    let retried = false;

    element.dataset.openMedia = "true";
    element.dataset.avatarName = name;
    element.classList.add("open-avatar", "is-loading");
    element.textContent = fallback;

    image.alt = "";
    image.loading = element.matches(".avatar-button, .user-avatar") ? "eager" : "lazy";
    image.decoding = "async";
    image.referrerPolicy = "no-referrer";
    image.width = 160;
    image.height = 160;

    image.addEventListener("load", () => {
      element.classList.remove("is-loading", "is-error");
      element.classList.add("is-loaded");
      window.dispatchEvent(new CustomEvent("hajiriflow:avatar-loaded", { detail: { element, image } }));
    });

    image.addEventListener("error", () => {
      if (!retried) {
        retried = true;
        image.src = avatarUrl(name, true);
        return;
      }

      image.remove();
      element.classList.remove("is-loading");
      element.classList.add("is-error");
    });

    image.src = avatarUrl(name);
    element.append(image);
  }

  function scan(root = document) {
    if (root instanceof Element && root.matches(AVATAR_SELECTOR)) enhanceAvatar(root);
    root.querySelectorAll?.(AVATAR_SELECTOR).forEach(enhanceAvatar);
  }

  const observer = new MutationObserver((records) => {
    records.forEach((record) => record.addedNodes.forEach((node) => {
      if (node instanceof Element) scan(node);
    }));
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
