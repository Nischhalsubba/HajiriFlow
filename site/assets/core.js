const STORAGE_KEY = "hajiriflow_demo_state_v2";
const NOTICE_KEY = "hajiriflow_demo_notice_dismissed";

const icons = {
  overview: '<path d="M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z"/>',
  attendance: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4m8-4v4M4 10h16m-12 4h3v3H8z"/>',
  employees: '<path d="M16 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2m6.5-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7.5 1a3 3 0 0 1 3 3v6m-4-17a4 4 0 0 1 0 7"/>',
  leave: '<path d="M7 3h10v18H7zM10 7h4m-4 4h4m-4 4h3"/>',
  reports: '<path d="M5 20V10m5 10V4m5 16v-7m5 7V7"/>',
  devices: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6m-6 10h6"/>',
  payroll: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M7 6V4h10v2m-6 5h5m-5 4h3"/>',
  organization: '<path d="M12 3v5m0 0H6v5m6-5h6v5M4 13h4v6H4zm8 0h4v6h-4zm8 0h-4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4M5 19h14"/>',
  upload: '<path d="M12 17V5m0 0 4 4m-4-4-4 4M5 21h14"/>',
  filter: '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v4m0 3h.01"/>',
  eye: '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>',
  edit: '<path d="m4 16-.8 4 4-.8L18 8.4 15.6 6 4 16Z"/><path d="m14 7 2.4 2.4"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  calendar: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4m8-4v4M4 10h16"/>',
  pulse: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m7-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8 0 2 2 4-4"/>',
  file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6m-6 4h6"/>',
  refresh: '<path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.5 10A7 7 0 0 0 6.2 6.2L4 8m2 6a7 7 0 0 0 12.3 3.8L20 16"/>',
  wifi: '<path d="M5 9a11 11 0 0 1 14 0M8 12a7 7 0 0 1 8 0m-5 4a1.4 1.4 0 1 1 2 0"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  wallet: '<path d="M4 6h14a2 2 0 0 1 2 2v11H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12"/><path d="M15 11h6v5h-6z"/>',
  building: '<path d="M4 21V5l8-3 8 3v16M8 8h1m3 0h1m3 0h1M8 12h1m3 0h1m3 0h1M8 16h1m3 0h1m3 0h1M10 21v-3h4v3"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 13h2"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  arrowRight: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  money: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M7 9H5v2m12 4h2v-2"/>',
  fingerprint: '<path d="M8 10a4 4 0 0 1 8 0v2m-10 1v-3a6 6 0 0 1 12 0v4m-9 2v-6a3 3 0 0 1 6 0v7m-9-1v-1m6 5c-2.5-1-3-3-3-5m6 5c2-2 2-4 2-7"/>',
};

const navGroups = [
  {
    label: "Workspace",
    items: [
      { route: "overview", label: "Overview", icon: "overview" },
      { route: "attendance", label: "Attendance", icon: "attendance" },
      { route: "employees", label: "Employees", icon: "employees" },
      { route: "leave", label: "Leave", icon: "leave", count: () => pendingLeaveCount() },
    ],
  },
  {
    label: "Operations",
    items: [
      { route: "reports", label: "Reports", icon: "reports" },
      { route: "devices", label: "Devices", icon: "devices", count: () => offlineDeviceCount() },
      { route: "payroll", label: "Payroll", icon: "payroll" },
    ],
  },
  {
    label: "Administration",
    items: [
      { route: "organization", label: "Organization", icon: "organization" },
      { route: "settings", label: "Settings", icon: "settings" },
    ],
  },
];

const routeMeta = {
  overview: { kicker: "Workspace", title: "Overview", description: "Today across your workforce" },
  attendance: { kicker: "Time & attendance", title: "Attendance", description: "Review daily records and punch evidence" },
  employees: { kicker: "People directory", title: "Employees", description: "Manage workforce profiles and assignments" },
  leave: { kicker: "Time away", title: "Leave", description: "Balances, requests, approvals, and field duty" },
  reports: { kicker: "Analysis", title: "Reports", description: "Generate operational attendance reports" },
  devices: { kicker: "Biometric network", title: "Devices", description: "Connectivity, synchronization, and pull health" },
  payroll: { kicker: "Compensation", title: "Payroll", description: "Review payroll periods and processing readiness" },
  organization: { kicker: "Administration", title: "Organization", description: "Company hierarchy, departments, and shifts" },
  settings: { kicker: "Administration", title: "Settings", description: "Workspace preferences and demo controls" },
};

const seedState = {
  employees: [
    { id: 1, attId: "101", name: "Aarav Shrestha", email: "aarav@hajiriflow.demo", department: "Administration", section: "Operations", shift: "General 09:00–17:00", status: "Active", device: "Main Gate", joined: "2024-02-15" },
    { id: 2, attId: "102", name: "Sushma Rai", email: "sushma@hajiriflow.demo", department: "Finance", section: "Accounts", shift: "General 09:00–17:00", status: "Active", device: "Main Gate", joined: "2023-11-03" },
    { id: 3, attId: "103", name: "Bikash Karki", email: "bikash@hajiriflow.demo", department: "Information Technology", section: "Infrastructure", shift: "Early 08:00–16:00", status: "Active", device: "Office Floor", joined: "2025-01-09" },
    { id: 4, attId: "104", name: "Nima Sherpa", email: "nima@hajiriflow.demo", department: "Human Resources", section: "People Operations", shift: "General 09:00–17:00", status: "Active", device: "Main Gate", joined: "2022-07-21" },
    { id: 5, attId: "105", name: "Priya Maharjan", email: "priya@hajiriflow.demo", department: "Finance", section: "Procurement", shift: "General 09:00–17:00", status: "Active", device: "Office Floor", joined: "2024-09-12" },
    { id: 6, attId: "106", name: "Roshan Thapa", email: "roshan@hajiriflow.demo", department: "Field Operations", section: "East Region", shift: "Field Flexible", status: "Active", device: "Main Gate", joined: "2023-04-18" },
    { id: 7, attId: "107", name: "Anisha Gurung", email: "anisha@hajiriflow.demo", department: "Administration", section: "Reception", shift: "Early 08:00–16:00", status: "Active", device: "Reception", joined: "2025-03-01" },
    { id: 8, attId: "108", name: "Kabir Lama", email: "kabir@hajiriflow.demo", department: "Information Technology", section: "Product", shift: "General 09:00–17:00", status: "Inactive", device: "Office Floor", joined: "2022-02-11" },
  ],
  attendance: [
    { id: 1, employeeId: 1, checkIn: "08:54", checkOut: "17:18", worked: "8h 24m", status: "Present", source: "Main Gate", late: "On time" },
    { id: 2, employeeId: 2, checkIn: "09:12", checkOut: "17:06", worked: "7h 54m", status: "Late", source: "Main Gate", late: "12 min late" },
    { id: 3, employeeId: 3, checkIn: "07:58", checkOut: "16:11", worked: "8h 13m", status: "Present", source: "Office Floor", late: "On time" },
    { id: 4, employeeId: 4, checkIn: "08:49", checkOut: "17:02", worked: "8h 13m", status: "Present", source: "Main Gate", late: "On time" },
    { id: 5, employeeId: 5, checkIn: "09:04", checkOut: "16:55", worked: "7h 51m", status: "Present", source: "Office Floor", late: "4 min late" },
    { id: 6, employeeId: 6, checkIn: "—", checkOut: "—", worked: "—", status: "Field duty", source: "Approved kaaj", late: "—" },
    { id: 7, employeeId: 7, checkIn: "08:01", checkOut: "16:08", worked: "8h 07m", status: "Present", source: "Reception", late: "1 min late" },
    { id: 8, employeeId: 8, checkIn: "—", checkOut: "—", worked: "—", status: "Absent", source: "No evidence", late: "—" },
  ],
  leaveRequests: [
    { id: 1, employeeId: 2, type: "Sick leave", from: "2026-08-05", to: "2026-08-05", days: 1, reason: "Medical appointment", status: "Pending" },
    { id: 2, employeeId: 4, type: "Home leave", from: "2026-08-10", to: "2026-08-12", days: 3, reason: "Family visit", status: "Pending" },
    { id: 3, employeeId: 7, type: "Casual leave", from: "2026-07-27", to: "2026-07-27", days: 1, reason: "Personal work", status: "Approved" },
    { id: 4, employeeId: 1, type: "Home leave", from: "2026-07-18", to: "2026-07-20", days: 3, reason: "Family event", status: "Approved" },
    { id: 5, employeeId: 3, type: "Sick leave", from: "2026-07-11", to: "2026-07-11", days: 1, reason: "Fever", status: "Rejected" },
  ],
  devices: [
    { id: 1, name: "Main Gate", ip: "192.168.10.21", model: "ZKTeco K40", users: 184, status: "Online", lastSync: "2 minutes ago", location: "Ground floor", protocol: "TCP" },
    { id: 2, name: "Office Floor", ip: "192.168.10.24", model: "ZKTeco F18", users: 96, status: "Online", lastSync: "8 minutes ago", location: "Second floor", protocol: "TCP" },
    { id: 3, name: "Reception", ip: "192.168.10.29", model: "ZKTeco LX50", users: 52, status: "Attention", lastSync: "1 hour ago", location: "Reception", protocol: "UDP" },
  ],
  payroll: [
    { id: 1, period: "Shrawan 2083", employees: 0, gross: 0, deductions: 0, net: 0, status: "Draft", attendance: "Not locked" },
    { id: 2, period: "Ashadh 2083", employees: 78, gross: 4820000, deductions: 638000, net: 4182000, status: "Posted", attendance: "Locked" },
    { id: 3, period: "Jestha 2083", employees: 77, gross: 4745000, deductions: 621000, net: 4124000, status: "Posted", attendance: "Locked" },
  ],
  activity: [
    { id: 1, type: "attendance", title: "Attendance pull completed", detail: "Main Gate · 42 new punches", time: "10:48" },
    { id: 2, type: "leave", title: "Leave request submitted", detail: "Sushma Rai · Sick leave", time: "10:22" },
    { id: 3, type: "employees", title: "Employee profile updated", detail: "Anisha Gurung · Shift assignment", time: "09:57" },
    { id: 4, type: "devices", title: "Device requires attention", detail: "Reception · Pull delayed", time: "09:11" },
  ],
  settings: {
    company: "HajiriFlow Demo",
    timezone: "Asia/Kathmandu",
    weekOff: "Saturday",
    dateFormat: "BS + AD",
  },
};

const ui = {
  route: "overview",
  search: "",
  attendanceTab: "daily",
  attendanceStatus: "all",
  employeeDepartment: "all",
  leaveStatus: "all",
  lastFocused: null,
};

let state = loadState();

const workspace = document.getElementById("workspace");
const nav = document.getElementById("primary-nav");
const pageTitle = document.getElementById("page-title");
const pageKicker = document.getElementById("page-kicker");
const globalSearch = document.getElementById("global-search");
const sidebar = document.getElementById("sidebar");
const modalLayer = document.getElementById("modal-layer");
const commandMenu = document.getElementById("command-menu");
const commandSearch = document.getElementById("command-search");
const commandResults = document.getElementById("command-results");
const demoNotice = document.getElementById("demo-notice");

function icon(name, label = "") {
  const content = icons[name] || icons.overview;
  const aria = label ? ` role="img" aria-label="${escapeHtml(label)}"` : ' aria-hidden="true"';
  return `<svg viewBox="0 0 24 24"${aria}>${content}</svg>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function loadState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return structuredClone(seedState);
    return { ...structuredClone(seedState), ...JSON.parse(saved) };
  } catch {
    return structuredClone(seedState);
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function initials(name) {
  return String(name)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function getEmployee(id) {
  return state.employees.find((employee) => employee.id === Number(id));
}

function activeEmployees() {
  return state.employees.filter((employee) => employee.status === "Active");
}

function pendingLeaveCount() {
  return state.leaveRequests.filter((request) => request.status === "Pending").length;
}

function offlineDeviceCount() {
  return state.devices.filter((device) => device.status !== "Online").length;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-NP", {
    style: "currency",
    currency: "NPR",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function formatDate(dateString, options = {}) {
  const date = new Date(`${dateString}T00:00:00+05:45`);
  if (Number.isNaN(date.getTime())) return dateString;
  return new Intl.DateTimeFormat("en-NP", {
    timeZone: "Asia/Kathmandu",
    month: options.short ? "short" : "long",
    day: "numeric",
    year: options.year === false ? undefined : "numeric",
  }).format(date);
}

function statusBadge(status) {
  const map = {
    Present: "is-success",
    Active: "is-success",
    Approved: "is-success",
    Online: "is-success",
    Posted: "is-success",
    Locked: "is-success",
    Late: "is-warning",
    Pending: "is-warning",
    Attention: "is-warning",
    Draft: "is-warning",
    "Field duty": "is-info",
    Absent: "is-danger",
    Rejected: "is-danger",
    Inactive: "is-neutral",
    "Not locked": "is-danger",
  };
  return `<span class="badge ${map[status] || "is-neutral"}">${escapeHtml(status)}</span>`;
}

function personAvatar(employee, index = 0) {
  const tones = ["", "is-blue", "is-amber", "is-red"];
  return `<span class="person-avatar ${tones[index % tones.length]}">${escapeHtml(initials(employee?.name || "Unknown"))}</span>`;
}

function renderNav() {
  nav.innerHTML = navGroups
    .map(
      (group) => `
        <section class="nav-group" aria-labelledby="nav-${group.label.toLowerCase().replaceAll(" ", "-")}">
          <h2 class="nav-group-title" id="nav-${group.label.toLowerCase().replaceAll(" ", "-")}">${escapeHtml(group.label)}</h2>
          ${group.items
            .map((item) => {
              const count = typeof item.count === "function" ? item.count() : 0;
              return `
                <a class="nav-item ${ui.route === item.route ? "is-active" : ""}" href="#${item.route}" data-route="${item.route}" ${ui.route === item.route ? 'aria-current="page"' : ""}>
                  ${icon(item.icon)}
                  <span>${escapeHtml(item.label)}</span>
                  ${count ? `<span class="nav-count">${count}</span>` : ""}
                </a>`;
            })
            .join("")}
        </section>`,
    )
    .join("");
}

function routeFromHash() {
  const candidate = location.hash.replace(/^#/, "") || "overview";
  return routeMeta[candidate] ? candidate : "overview";
}

function render() {
  ui.route = routeFromHash();
  ui.search = globalSearch.value.trim().toLowerCase();
  const meta = routeMeta[ui.route];
  pageTitle.textContent = meta.title;
  pageKicker.textContent = meta.kicker;
  document.title = `${meta.title} · HajiriFlow`;
  renderNav();

  const view = views[ui.route] || views.overview;
  workspace.innerHTML = `<div class="page-enter">${view()}</div>`;
  closeSidebar();
}

function pageHeader(title, description, actions = "") {
  return `
    <header class="page-header">
      <div class="page-header-copy">
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(description)}</p>
      </div>
      <div class="page-actions">${actions}</div>
    </header>`;
}

function metricCard(iconName, tone, label, value, caption, trend = "") {
  return `
    <article class="metric-card">
      <span class="metric-icon ${tone}">${icon(iconName)}</span>
      <div class="metric-card-copy">
        <span class="metric-label">${escapeHtml(label)}</span>
        <strong class="metric-value">${escapeHtml(value)}</strong>
        <span class="metric-caption">${escapeHtml(caption)}</span>
        ${trend ? `<span class="metric-trend">${icon("arrowRight")}${escapeHtml(trend)}</span>` : ""}
      </div>
    </article>`;
}

function attendanceSummary() {
  const records = state.attendance.filter((record) => getEmployee(record.employeeId)?.status === "Active");
  return records.reduce(
    (summary, record) => {
      summary.total += 1;
      if (record.status === "Present" || record.status === "Late") summary.present += 1;
      if (record.status === "Late") summary.late += 1;
      if (record.status === "Absent") summary.absent += 1;
      if (record.status === "Field duty") summary.field += 1;
      return summary;
    },
    { total: 0, present: 0, late: 0, absent: 0, field: 0 },
  );
}
