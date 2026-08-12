function pagination(visible, total) {
  return `<div class="pagination"><span>Showing ${visible} of ${total}</span><div><button class="pagination-button" disabled aria-label="Previous page">‹</button><button class="pagination-button is-active">1</button><button class="pagination-button" disabled aria-label="Next page">›</button></div></div>`;
}

function emptyTableRow(columns, message) {
  return `<tr><td colspan="${columns}">${emptyState("search", "Nothing found", message)}</td></tr>`;
}

function emptyState(iconName, title, message) {
  return `<div class="empty-state"><span class="empty-icon">${icon(iconName)}</span><div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p></div></div>`;
}

function openSidebar() {
  document.body.classList.add("sidebar-open");
  document.querySelector("[data-open-sidebar]")?.setAttribute("aria-expanded", "true");
  sidebar.querySelector("a, button")?.focus();
}

function closeSidebar() {
  document.body.classList.remove("sidebar-open");
  document.querySelector("[data-open-sidebar]")?.setAttribute("aria-expanded", "false");
}

function updateNepalClock() {
  const now = new Date();
  const time = new Intl.DateTimeFormat("en-NP", { timeZone: "Asia/Kathmandu", hour: "2-digit", minute: "2-digit", hour12: true }).format(now);
  const date = new Intl.DateTimeFormat("en-NP", { timeZone: "Asia/Kathmandu", month: "short", day: "numeric" }).format(now);
  document.getElementById("nepal-time").textContent = time;
  document.getElementById("nepal-date").textContent = date;
}

function toast(message, tone = "success") {
  const region = document.getElementById("toast-region");
  const element = document.createElement("div");
  element.className = `toast is-${tone}`;
  element.innerHTML = `<span>${icon(tone === "success" ? "check" : tone === "danger" ? "alert" : "pulse")}</span><p>${escapeHtml(message)}</p>`;
  region.appendChild(element);
  requestAnimationFrame(() => element.classList.add("is-visible"));
  setTimeout(() => {
    element.classList.remove("is-visible");
    setTimeout(() => element.remove(), 220);
  }, 3500);
}

function openModal({ title, description = "", body, footer = "", size = "md" }) {
  ui.lastFocused = document.activeElement;
  modalLayer.hidden = false;
  modalLayer.innerHTML = `<div class="modal-backdrop" data-close-modal></div><section class="modal modal-${size}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">${escapeHtml(title)}</h2>${description ? `<p>${escapeHtml(description)}</p>` : ""}</div><button class="icon-button modal-close" data-close-modal aria-label="Close dialog">${icon("close")}</button></header><div class="modal-body">${body}</div>${footer ? `<footer class="modal-footer">${footer}</footer>` : ""}</section>`;
  document.body.classList.add("modal-open");
  modalLayer.querySelector("input, select, textarea, button")?.focus();
}

function closeModal() {
  modalLayer.hidden = true;
  modalLayer.innerHTML = "";
  document.body.classList.remove("modal-open");
  ui.lastFocused?.focus?.();
}

function downloadFile(filename, content, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function toCsv(rows) {
  return rows.map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
}

function openNotifications() {
  const items = [
    ["leave", "Two leave requests need approval", "Review the pending queue"],
    ["devices", "Reception device is delayed", "Last sync was one hour ago"],
    ["payroll", "Attendance is not locked", "Required before payroll generation"],
  ];
  openModal({
    title: "Notifications",
    description: "Operational items needing attention",
    body: `<div class="notification-list">${items.map(([type, title, detail]) => `<button class="notification-item" data-route-button="${type}"><span>${icon(type)}</span><div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div>${icon("chevron")}</button>`).join("")}</div>`,
  });
}

function openProfileMenu() {
  openModal({ title: "Nischhal Subba", description: "Project owner · Demo administrator", size: "sm", body: `<div class="profile-summary"><span class="large-avatar">NS</span><div><strong>Nischhal Subba</strong><small>Full demo access</small></div></div><div class="settings-actions"><button class="settings-action" data-route-button="settings">${icon("settings")}<span><strong>Workspace settings</strong><small>Preferences and demo controls</small></span>${icon("chevron")}</button><a class="settings-action" href="https://github.com/Nischhalsubba/HajiriFlow" target="_blank" rel="noreferrer">${icon("file")}<span><strong>Open repository</strong><small>View source and delivery progress</small></span>${icon("chevron")}</a></div>` });
}
