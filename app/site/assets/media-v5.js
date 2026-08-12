(() => {
  "use strict";

  const PHOTO_STORAGE_KEY = "hajiriflow_employee_photos_v1";
  const AVATAR_SELECTOR = ".person-avatar, .user-avatar, .avatar-button";
  const UNSPLASH_PARAMS = "auto=format&fit=crop&crop=faces&w=320&h=320&q=82";
  const PORTRAIT_IDS = [
    "photo-1494790108377-be9c29b29330",
    "photo-1500648767791-00dcc994a43e",
    "photo-1507003211169-0a1dd7228f2d",
    "photo-1534528741775-53994a69daeb",
    "photo-1506794778202-cad84cf45f1d",
    "photo-1527980965255-d3b416303d12",
    "photo-1438761681033-6461ffad8d80",
    "photo-1517841905240-472988babdf9",
    "photo-1531123897727-8f129e1688ce",
    "photo-1544005313-94ddf0286df2",
    "photo-1544725176-7c40e5a71c5e",
    "photo-1504593811423-6dd665756598",
    "photo-1560250097-0b93528c311a",
    "photo-1568602471122-7832951cc4c5",
    "photo-1573496359142-b8d87734a5a2",
    "photo-1580489944761-15a19d654956",
    "photo-1567532939604-b6b5b0db2604",
    "photo-1564564321837-a57b7070ac4f",
    "photo-1557804506-669a67965ba0",
    "photo-1566492031773-4f4e44671857",
    "photo-1547425260-76bcadfb4f2c",
    "photo-1531384441138-2736e62e0919",
    "photo-1531427186611-ecfd6d936c79",
    "photo-1542206395-9feb3edaa68d",
    "photo-1552374196-c4e7ffc6e7",
    "photo-1542103749-8ef59b94f47e",
    "photo-1488426862026-3ee34a7d66df",
    "photo-1551836022-d5d88e9218df",
    "photo-1508214751196-bcfd4ca60f91",
    "photo-1524504388940-b1c1722653e1",
    "photo-1525134479668-1bee5c7c6845",
    "photo-1522529599102-193c0d76b5b6",
    "photo-1519085360753-af0119f7cbe7",
    "photo-1502823403499-6ccfcf4fb453",
    "photo-1539571696357-5a69c17a67c6",
    "photo-1546961329-78bef0414d7c",
    "photo-1548142813-c348350df52b",
    "photo-1522075469751-3a6694fb2f61",
  ];

  function normalizeName(value) {
    return String(value || "HajiriFlow user").trim().replace(/\s+/g, " ");
  }

  function initials(value) {
    return normalizeName(value)
      .split(" ")
      .map((part) => part[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "HF";
  }

  function stableHash(value) {
    let hash = 2166136261;
    for (const character of normalizeName(value)) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function storageKey(name) {
    return normalizeName(name).toLocaleLowerCase("en-US");
  }

  function readPhotoMap() {
    try {
      return JSON.parse(window.localStorage.getItem(PHOTO_STORAGE_KEY) || "{}") || {};
    } catch {
      return {};
    }
  }

  function writePhotoMap(value) {
    window.localStorage.setItem(PHOTO_STORAGE_KEY, JSON.stringify(value));
  }

  function customPhoto(name) {
    return readPhotoMap()[storageKey(name)] || null;
  }

  function portraitUrl(name, offset = 0) {
    const index = (stableHash(name) + offset) % PORTRAIT_IDS.length;
    return `https://images.unsplash.com/${PORTRAIT_IDS[index]}?${UNSPLASH_PARAMS}`;
  }

  function personName(element) {
    if (element.dataset.avatarName) return normalizeName(element.dataset.avatarName);
    if (element.matches(".user-avatar, .avatar-button")) return "Nischhal Subba";

    const profile = element.closest(".profile-identity");
    if (profile) {
      const modalTitle = document.querySelector("#modal-title")?.textContent?.trim();
      if (modalTitle) return normalizeName(modalTitle);
    }

    const scopes = [
      element.closest(".person-cell"),
      element.closest(".detail-person"),
      element.closest(".mini-person"),
      element.closest(".mini-people button"),
      element.closest("article"),
      element.parentElement,
    ].filter(Boolean);

    for (const scope of scopes) {
      const candidate = scope.querySelector("strong, h2, h3, span:not(.person-avatar)");
      const value = candidate?.textContent?.trim();
      if (value && value.length > 1) return normalizeName(value);
    }

    return normalizeName(element.textContent || "HajiriFlow user");
  }

  function clearAvatar(element) {
    element.querySelectorAll("img").forEach((image) => image.remove());
    element.classList.remove("is-loading", "is-loaded", "is-error");
    delete element.dataset.openMedia;
  }

  function setPhoto(name, dataUrl) {
    const photos = readPhotoMap();
    photos[storageKey(name)] = dataUrl;
    writePhotoMap(photos);
    refreshName(name);
  }

  function removePhoto(name) {
    const photos = readPhotoMap();
    delete photos[storageKey(name)];
    writePhotoMap(photos);
    refreshName(name);
  }

  function refreshName(name) {
    const normalized = normalizeName(name);
    document.querySelectorAll(AVATAR_SELECTOR).forEach((element) => {
      if (personName(element) !== normalized) return;
      clearAvatar(element);
      enhanceAvatar(element);
    });
    window.dispatchEvent(new CustomEvent("hajiriflow:photo-updated", { detail: { name: normalized } }));
  }

  function enhanceAvatar(element) {
    if (!(element instanceof HTMLElement) || element.dataset.openMedia === "true") return;

    const name = personName(element);
    const fallback = initials(name);
    const image = new Image();
    let attempt = 0;

    element.dataset.openMedia = "true";
    element.dataset.avatarName = name;
    element.classList.add("open-avatar", "is-loading", "is-photographic");
    element.textContent = fallback;

    image.alt = "";
    image.loading = element.matches(".avatar-button, .user-avatar") ? "eager" : "lazy";
    image.decoding = "async";
    image.referrerPolicy = "no-referrer";
    image.width = 320;
    image.height = 320;

    image.addEventListener("load", () => {
      element.classList.remove("is-loading", "is-error");
      element.classList.add("is-loaded");
      window.dispatchEvent(new CustomEvent("hajiriflow:avatar-loaded", { detail: { element, image } }));
    });

    image.addEventListener("error", () => {
      attempt += 1;
      if (attempt === 1 && !customPhoto(name)) {
        image.src = portraitUrl(name, 11);
        return;
      }
      image.remove();
      element.classList.remove("is-loading");
      element.classList.add("is-error");
    });

    image.src = customPhoto(name) || portraitUrl(name);
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

  window.HFMedia = Object.freeze({
    getPhoto: customPhoto,
    setPhoto,
    removePhoto,
    refreshName,
    portraitFor: portraitUrl,
  });

  scan();
})();