(() => {
  "use strict";

  const D = window.HFData;
  if (!D) throw new Error("HajiriFlow data engine unavailable");

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const workspace = $("#workspace");
  const nav = $("#primary-nav");
  const shell = $("#app-shell");
  const modalLayer = $("#modal-layer");
  const commandLayer = $("#command-layer");
  const commandInput = $("#command-input");
  const commandResults = $("#command-results");
  const toastRegion = $("#toast-region");

  const ui = {
    date: D.isoDate(new Date()),
    search: "",
    department: "all",
    attendanceStatus: "all",
    employeeStatus: "Active",
    leaveStatus: "all",
    payrollPeriod: D.currentMonthKey(),
    tab: "requests",
  };

  const icons = {
    overview: '<path d="M4 4h7v7H4zM14 4h6v4h-6zM14 11h6v9h-6zM4 14h7v6H4z"/>',
    attendance: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4m8-4v4M4 10h16m-9 4h3v3h-3z"/>',
    employees: '<path d="M16 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2m5.5-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8.5 1a3 3 0 0 1 3 3v6m-4-17a4 4 0 0 1 0 7"/>',
    leave: '<path d="M7 3h10v18H7zM10 7h4m-4 4h4m-4 4h3"/>',
    reports: '<path d="M4 20V10m5 10V4m5 16v-7m5 7V7"/>',
    devices: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6m-6 10h6"/>',
    payroll: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M7 6V4h10v2m-6 5h5m-5 4h3"/>',
    organization: '<path d="M12 3v5m0 0H6v5m6-5h6v5M4 13h4v6H4zm8 0h4v6h-4zm8 0h-4"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4M5 19h14"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    alert: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v4m0 3h.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    edit: '<path d="m4 16-.8 4 4-.8L18 8.4 15.6 6 4 16Z"/><path d="m14 7 2.4 2.4"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    refresh: '<path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.5 10A7 7 0 0 0 6.2 6.2L4 8m2 6a7 7 0 0 0 12.3 3.8L20 16"/>',
    eye: '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>',
    wifi: '<path d="M5 9a11 11 0 0 1 14 0M8 12a7 7 0 0 1 8 0m-5 4a1.4 1.4 0 1 1 2 0"/>',
    money: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="12" cy="12" r="3"/>',
    file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6m-6 4h6"/>',
    building: '<path d="M4 21V5l8-3 8 3v16M8 8h1m3 0h1m3 0h1M8 12h1m3 0h1m3 0h1M8 16h1m3 0h1m3 0h1M10 21v-3h4v3"/>',
  };

  const groups = [
    ["Workspace", [["overview", "Overview"], ["attendance", "Attendance"], ["employees", "Employees"], ["leave", "Leave & kaaj"]]],
    ["Operations", [["reports", "Reports"], ["devices", "Devices"], ["payroll", "Payroll"]]],
    ["Administration", [["organization", "Organization"], ["settings", "Settings"]]],
  ];

  const meta = {
    overview: ["Workspace", "Overview"],
    attendance: ["Time & attendance", "Attendance"],
    employees: ["People directory", "Employees"],
    leave: ["Time away", "Leave & kaaj"],
    reports: ["Analysis", "Reports"],
    devices: ["Biometric network", "Devices"],
    payroll: ["Compensation", "Payroll"],
    organization: ["Administration", "Organization"],
    settings: ["Administration", "Settings"],
  };

  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
  const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
  const S = () => D.getState();
  const employee = (id) => D.getEmployee(id);
  const department = (id) => D.getDepartment(id);
  const shift = (id) => D.getShift(id);
  const device = (id) => S().devices.find((item) => item.id === id);
  const route = () => location.hash.replace(/^#/, "") || "overview";
  const formatDate = (value) => new Intl.DateTimeFormat("en-NP", { timeZone: D.TIMEZONE, month: "short", day: "numeric", year: "numeric" }).format(D.localDateFromIso(value));
  const formatDateTime = (value) => new Intl.DateTimeFormat("en-NP", { timeZone: D.TIMEZONE, month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
  const timeAgo = (value) => {
    const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
    if (minutes < 2) return "just now";
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.round(hours / 24)}d ago`;
  };
  const worked = (minutes) => minutes ? `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m` : "—";
  const statusClass = (status) => {
    const normalized = String(status).toLowerCase();
    if (["online", "active", "present", "approved", "paid", "ready"].some((word) => normalized.includes(word))) return "status-success";
    if (["late", "pending", "draft", "attention", "leave", "field"].some((word) => normalized.includes(word))) return "status-warning";
    if (["offline", "inactive", "absent", "rejected", "failed"].some((word) => normalized.includes(word))) return "status-danger";
    return "status-neutral";
  };
  const pill = (status) => `<span class="status-pill ${statusClass(status)}">${esc(status)}</span>`;
  const avatar = (item, size = "") => `<span class="person-avatar ${size}" style="--avatar-hue:${item?.avatarHue || 210}">${esc((item?.name || "?").split(" ").map((part) => part[0]).slice(0, 2).join(""))}</span>`;
  const button = (label, action, options = {}) => `<button type="button" class="button button-${options.kind || "secondary"}" data-action="${action}"${options.id ? ` data-id="${options.id}"` : ""}${options.key ? ` data-key="${options.key}"` : ""}>${options.ico ? icon(options.ico) : ""}<span>${esc(label)}</span></button>`;
  const empty = (title, copy) => `<div class="empty-state">${icon("file")}<h3>${esc(title)}</h3><p>${esc(copy)}</p></div>`;
  const panelHeader = (eyebrow, title, action = "") => `<header class="panel-header"><div><p class="eyebrow">${esc(eyebrow)}</p><h2>${esc(title)}</h2></div>${action}</header>`;

  function renderNav() {
    const current = route();
    nav.innerHTML = groups.map(([label, items]) => `<section class="nav-group"><p>${label}</p>${items.map(([key, name]) => {
      let count = "";
      if (key === "leave") count = S().leaveRequests.filter((request) => request.status === "Pending").length;
      if (key === "devices") count = S().devices.filter((item) => item.status !== "Online").length;
      return `<a class="nav-link ${current === key ? "is-active" : ""}" href="#${key}" ${current === key ? 'aria-current="page"' : ""}>${icon(key)}<span>${name}</span>${count ? `<b>${count}</b>` : ""}</a>`;
    }).join("")}</section>`).join("");
    const state = S();
    $("#workspace-card").innerHTML = `<span class="workspace-monogram">HF</span><span><strong>${esc(state.workspace.name)}</strong><small>${state.employees.filter((item) => item.status === "Active").length} active people</small></span>`;
    const online = state.devices.filter((item) => item.enabled && item.status === "Online").length;
    $("#connection-card").innerHTML = `<span class="connection-dot ${online === state.devices.length ? "is-online" : "is-warning"}"></span><span><strong>${online}/${state.devices.length} readers online</strong><small>Generated demo workspace</small></span>`;
    $("#notification-count").textContent = D.unreadNotificationCount();
  }

  function render() {
    const current = routes[route()] ? route() : "overview";
    document.documentElement.dataset.theme = S().preferences.theme;
    document.documentElement.dataset.density = S().preferences.density;
    $("#page-kicker").textContent = meta[current][0];
    $("#page-title").textContent = meta[current][1];
    renderNav();
    workspace.innerHTML = routes[current]();
    shell.classList.remove("sidebar-is-open");
    workspace.focus({ preventScroll: true });
  }

  function metric(label, value, detail, tone = "blue", symbol = "overview") {
    return `<article class="metric-card"><div class="metric-icon tone-${tone}">${icon(symbol)}</div><div><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></div></article>`;
  }

  function trendChart(points) {
    const width = 640;
    const height = 190;
    const pad = 20;
    const values = points.map((point) => point.rate);
    const min = Math.max(0, Math.min(...values) - 5);
    const max = Math.min(100, Math.max(...values) + 3);
    const coords = points.map((point, index) => {
      const x = pad + (index / Math.max(1, points.length - 1)) * (width - pad * 2);
      const y = height - pad - ((point.rate - min) / Math.max(1, max - min)) * (height - pad * 2);
      return [x, y, point];
    });
    const line = coords.map(([x, y]) => `${x},${y}`).join(" ");
    return `<div class="trend-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Attendance rate trend"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2563eb" stop-opacity=".24"/><stop offset="1" stop-color="#2563eb" stop-opacity="0"/></linearGradient></defs><path class="chart-area" d="M${coords[0][0]},${height - pad} L${line.replaceAll(" ", " L")} L${coords.at(-1)[0]},${height - pad} Z"/><polyline class="chart-line" points="${line}"/>${coords.map(([x, y, point]) => `<circle cx="${x}" cy="${y}" r="3"><title>${point.label}: ${point.rate}%</title></circle>`).join("")}</svg><div class="chart-labels">${points.filter((_, index) => index % Math.max(1, Math.floor(points.length / 6)) === 0).map((point) => `<span>${point.label}</span>`).join("")}</div></div>`;
  }

  function activityList(items) {
    if (!items.length) return empty("No recent activity", "Workspace changes will appear here.");
    return `<div class="activity-list">${items.map((item) => `<article><span class="activity-mark">${icon(item.type === "device" ? "devices" : item.type === "leave" ? "leave" : item.type === "payroll" ? "payroll" : item.type === "report" ? "reports" : "attendance")}</span><div><p><strong>${esc(item.actor)}</strong> ${esc(item.verb)} <b>${esc(item.subject)}</b></p><small>${timeAgo(item.occurredAt)}</small></div></article>`).join("")}</div>`;
  }

  function renderOverview() {
    const summary = D.dashboardSummary();
    const records = S().attendance.filter((record) => record.date === D.isoDate(new Date()));
    const exceptions = records.filter((record) => ["Late", "Absent", "Leave"].includes(record.status)).slice(0, 6);
    const departmentCounts = S().departments.map((item) => ({
      name: item.name,
      value: S().employees.filter((person) => person.departmentId === item.id && person.status === "Active").length,
    })).sort((a, b) => b.value - a.value);
    const maxDepartment = Math.max(1, ...departmentCounts.map((item) => item.value));
    return `<div class="page-stack"><section class="welcome-row"><div><p class="eyebrow">Live demo workspace</p><h2>Good ${new Intl.DateTimeFormat("en-GB", { timeZone: D.TIMEZONE, hour: "numeric", hour12: false }).format(new Date()) < 12 ? "morning" : "afternoon"}, Nischhal.</h2><p>Every figure below is calculated from the generated workforce dataset in this browser.</p></div><div class="page-actions">${button("Reprocess today", "reprocess-today", { ico: "refresh" })}${button("Add employee", "add-employee", { kind: "primary", ico: "plus" })}</div></section><section class="metric-grid">${metric("Attendance rate", `${summary.attendanceRate}%`, `${summary.present} of ${summary.activeEmployees} active people`, "blue", "attendance")}${metric("Needs review", String(summary.late + summary.absent), `${summary.late} late · ${summary.absent} absent`, "amber", "alert")}${metric("Leave approvals", String(summary.pendingLeave), "Pending manager decisions", summary.pendingLeave ? "amber" : "green", "leave")}${metric("Reader health", `${summary.onlineDevices}/${summary.totalDevices}`, "Biometric readers online", summary.onlineDevices === summary.totalDevices ? "green" : "red", "devices")}</section><section class="dashboard-grid"><article class="panel panel-wide">${panelHeader("Attendance intelligence", `${S().preferences.dashboardRange}-day attendance rate`, `<span class="data-source">Generated from daily evidence</span>`)}${trendChart(D.attendanceTrend(S().preferences.dashboardRange))}</article><article class="panel">${panelHeader("Today", "Exceptions requiring attention", button("View attendance", "go-attendance", { kind: "ghost" }))}${exceptions.length ? `<div class="exception-list">${exceptions.map((record) => { const person = employee(record.employeeId); return `<button data-action="view-attendance" data-id="${record.id}">${avatar(person)}<span><strong>${esc(person?.name)}</strong><small>${record.status}${record.lateMinutes ? ` · ${record.lateMinutes} min late` : ""}</small></span>${pill(record.status)}</button>`; }).join("")}</div>` : empty("No exceptions today", "The generated workforce has no unresolved attendance exceptions.")}</article><article class="panel">${panelHeader("Workforce", "People by department")}<div class="bar-list">${departmentCounts.map((item) => `<div class="bar-row"><div><span>${esc(item.name)}</span><strong>${item.value}</strong></div><progress max="${maxDepartment}" value="${item.value}"></progress></div>`).join("")}</div></article><article class="panel">${panelHeader("Audit stream", "Recent workspace activity", button("Export", "export-activity", { kind: "ghost", ico: "download" }))}${activityList(S().activities.slice(0, 7))}</article></section></div>`;
  }

  function filteredAttendance() {
    return S().attendance.filter((record) => {
      const person = employee(record.employeeId);
      return record.date === ui.date
        && (ui.attendanceStatus === "all" || record.status === ui.attendanceStatus)
        && (ui.department === "all" || person?.departmentId === ui.department)
        && (!ui.search || `${person?.name} ${person?.attId} ${record.status}`.toLowerCase().includes(ui.search.toLowerCase()));
    });
  }

  function renderAttendance() {
    const rows = filteredAttendance();
    const statuses = ["Present", "Late", "Absent", "Leave", "Field duty"];
    return `<div class="page-stack"><section class="page-intro"><div><p>Review calculated workday results and the evidence that produced them.</p></div><div class="page-actions">${button("Export CSV", "export-attendance", { ico: "download" })}${button("Add correction", "manual-attendance", { kind: "primary", ico: "plus" })}</div></section><section class="summary-strip">${statuses.map((status) => `<div><span>${status}</span><strong>${rows.filter((record) => record.status === status).length}</strong></div>`).join("")}</section><section class="panel table-panel"><div class="table-toolbar"><div class="filters"><label><span>Date</span><input type="date" value="${ui.date}" data-filter="date"></label><label><span>Status</span><select data-filter="attendance-status"><option value="all">All statuses</option>${statuses.map((status) => `<option ${ui.attendanceStatus === status ? "selected" : ""}>${status}</option>`).join("")}</select></label><label><span>Department</span><select data-filter="department"><option value="all">All departments</option>${S().departments.map((item) => `<option value="${item.id}" ${ui.department === item.id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label></div><label class="table-search">${icon("search")}<input type="search" placeholder="Search name or ID" value="${esc(ui.search)}" data-filter="search"></label></div><div class="table-scroll"><table><thead><tr><th>Employee</th><th>Department</th><th>Status</th><th>Check in</th><th>Check out</th><th>Worked</th><th>Evidence</th><th></th></tr></thead><tbody>${rows.map((record) => { const person = employee(record.employeeId); return `<tr><td><button class="person-cell" data-action="view-employee" data-id="${person?.id}">${avatar(person)}<span><strong>${esc(person?.name)}</strong><small>${esc(person?.attId)}</small></span></button></td><td>${esc(department(person?.departmentId)?.name || "Unassigned")}</td><td>${pill(record.status)}</td><td class="tabular">${record.checkIn || "—"}</td><td class="tabular">${record.checkOut || "—"}</td><td class="tabular">${worked(record.workedMinutes)}</td><td><span class="evidence-source">${esc(record.source)}</span></td><td><button class="icon-button table-action" data-action="view-attendance" data-id="${record.id}" aria-label="View record">${icon("eye")}</button></td></tr>`; }).join("")}</tbody></table>${rows.length ? "" : empty("No records match", "Change the date or filters to review another workday.")}</div></section></div>`;
  }

  function filteredEmployees() {
    return S().employees.filter((person) => (ui.employeeStatus === "all" || person.status === ui.employeeStatus)
      && (ui.department === "all" || person.departmentId === ui.department)
      && (!ui.search || `${person.name} ${person.employeeCode} ${person.attId} ${person.role}`.toLowerCase().includes(ui.search.toLowerCase())));
  }

  function renderEmployees() {
    const rows = filteredEmployees();
    return `<div class="page-stack"><section class="page-intro"><div><p>A live workforce directory generated from the same state used by attendance and payroll.</p></div><div class="page-actions">${button("Export directory", "export-employees", { ico: "download" })}${button("Add employee", "add-employee", { kind: "primary", ico: "plus" })}</div></section><section class="metric-grid compact">${metric("Total people", String(S().employees.length), "All workforce profiles", "blue", "employees")}${metric("Active", String(S().employees.filter((item) => item.status === "Active").length), "Included in daily attendance", "green", "check")}${metric("Departments", String(S().departments.length), "Active organization units", "teal", "building")}${metric("Contracts", String(S().employees.filter((item) => item.employmentType === "Contract").length), "Non-permanent profiles", "amber", "file")}</section><section class="panel table-panel"><div class="table-toolbar"><div class="filters"><label><span>Status</span><select data-filter="employee-status"><option value="all">All people</option><option ${ui.employeeStatus === "Active" ? "selected" : ""}>Active</option><option ${ui.employeeStatus === "Inactive" ? "selected" : ""}>Inactive</option></select></label><label><span>Department</span><select data-filter="department"><option value="all">All departments</option>${S().departments.map((item) => `<option value="${item.id}" ${ui.department === item.id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label></div><label class="table-search">${icon("search")}<input type="search" placeholder="Search employees" value="${esc(ui.search)}" data-filter="search"></label></div><div class="table-scroll"><table><thead><tr><th>Employee</th><th>Role</th><th>Department</th><th>Shift</th><th>Employment</th><th>Status</th><th></th></tr></thead><tbody>${rows.map((person) => `<tr><td><button class="person-cell" data-action="view-employee" data-id="${person.id}">${avatar(person)}<span><strong>${esc(person.name)}</strong><small>${esc(person.employeeCode)} · Att. ${esc(person.attId)}</small></span></button></td><td>${esc(person.role)}</td><td>${esc(department(person.departmentId)?.name || "Unassigned")}<small class="cell-subtext">${esc(person.section)}</small></td><td>${esc(shift(person.shiftId)?.label || "Unassigned")}</td><td>${esc(person.employmentType)}</td><td>${pill(person.status)}</td><td><button class="icon-button table-action" data-action="edit-employee" data-id="${person.id}" aria-label="Edit employee">${icon("edit")}</button></td></tr>`).join("")}</tbody></table>${rows.length ? "" : empty("No employees found", "Try another search or status filter.")}</div></section></div>`;
  }

  function renderLeave() {
    const requests = S().leaveRequests.filter((request) => (ui.leaveStatus === "all" || request.status === ui.leaveStatus)
      && (!ui.search || `${employee(request.employeeId)?.name} ${request.type}`.toLowerCase().includes(ui.search.toLowerCase()))).sort((a, b) => new Date(b.appliedAt) - new Date(a.appliedAt));
    const pending = S().leaveRequests.filter((request) => request.status === "Pending").length;
    const approvedDays = S().leaveRequests.filter((request) => request.status === "Approved").reduce((sum, request) => sum + request.days, 0);
    return `<div class="page-stack"><section class="page-intro"><div><p>Manage time-away decisions and field-duty records from one approval queue.</p></div><div class="page-actions">${button("Record field duty", "record-field-duty", { ico: "plus" })}${button("Request leave", "request-leave", { kind: "primary", ico: "plus" })}</div></section><section class="metric-grid compact">${metric("Pending approvals", String(pending), "Awaiting a decision", pending ? "amber" : "green", "leave")}${metric("Approved days", String(approvedDays), "Across generated requests", "blue", "calendar")}${metric("Active requests", String(S().leaveRequests.filter((request) => request.status !== "Rejected").length), "Current demo workflow", "teal", "file")}${metric("Average balance", `${Math.max(0, 24 - Math.round(approvedDays / Math.max(1, S().employees.length)))} days`, "Estimated annual balance", "green", "check")}</section><section class="panel table-panel"><div class="table-toolbar"><div class="filters"><label><span>Status</span><select data-filter="leave-status"><option value="all">All requests</option>${["Pending", "Approved", "Rejected"].map((status) => `<option ${ui.leaveStatus === status ? "selected" : ""}>${status}</option>`).join("")}</select></label></div><label class="table-search">${icon("search")}<input type="search" placeholder="Search requests" value="${esc(ui.search)}" data-filter="search"></label></div><div class="table-scroll"><table><thead><tr><th>Employee</th><th>Leave type</th><th>Dates</th><th>Days</th><th>Applied</th><th>Status</th><th>Action</th></tr></thead><tbody>${requests.map((request) => { const person = employee(request.employeeId); return `<tr><td><div class="person-cell static">${avatar(person)}<span><strong>${esc(person?.name)}</strong><small>${esc(department(person?.departmentId)?.name || "")}</small></span></div></td><td>${esc(request.type)}</td><td>${formatDate(request.startDate)} – ${formatDate(request.endDate)}</td><td class="tabular">${request.days}</td><td>${timeAgo(request.appliedAt)}</td><td>${pill(request.status)}</td><td><div class="row-actions">${request.status === "Pending" ? `<button class="text-action success" data-action="approve-leave" data-id="${request.id}">Approve</button><button class="text-action danger" data-action="reject-leave" data-id="${request.id}">Reject</button>` : `<button class="text-action" data-action="view-leave" data-id="${request.id}">View</button>`}</div></td></tr>`; }).join("")}</tbody></table></div></section></div>`;
  }

  const reportDefinitions = [
    ["daily", "Daily attendance", "Present, late, absent, leave, and field-duty evidence for a selected date.", "attendance"],
    ["monthly", "Monthly workforce summary", "Employee-level attendance rates, late minutes, absence, and overtime.", "reports"],
    ["department", "Department coverage", "Compare daily coverage and exceptions across organization units.", "building"],
    ["payroll", "Payroll reconciliation", "Trace compensation inputs back to attendance and leave records.", "money"],
  ];

  function renderReports() {
    const trend = D.attendanceTrend(30);
    const average = Math.round(trend.reduce((sum, point) => sum + point.rate, 0) / trend.length);
    return `<div class="page-stack"><section class="page-intro"><div><p>Generate exportable reports from the shared dynamic workforce state.</p></div><div class="page-actions">${button("Export activity log", "export-activity", { ico: "download" })}</div></section><section class="metric-grid compact">${metric("30-day attendance", `${average}%`, "Calculated from generated evidence", "blue", "reports")}${metric("Attendance records", S().attendance.length.toLocaleString(), "Across the generated history", "teal", "attendance")}${metric("Active workforce", String(S().employees.filter((item) => item.status === "Active").length), "Included in reporting", "green", "employees")}${metric("Report types", String(reportDefinitions.length), "Ready for client walkthrough", "amber", "file")}</section><section class="report-grid">${reportDefinitions.map(([id, title, copy, symbol]) => `<article class="report-card"><span class="report-icon">${icon(symbol)}</span><div><h2>${title}</h2><p>${copy}</p></div><div class="report-card-footer"><span>CSV export · live calculations</span>${button("Generate", "generate-report", { kind: "primary", key: id })}</div></article>`).join("")}</section></div>`;
  }

  function renderDevices() {
    const online = S().devices.filter((item) => item.status === "Online").length;
    const registered = S().devices.reduce((sum, item) => sum + item.registeredUsers, 0);
    return `<div class="page-stack"><section class="page-intro"><div><p>Review generated connectivity, registrations, and worker actions for each biometric reader.</p></div><div class="page-actions">${button("Pull all devices", "pull-all-devices", { ico: "refresh" })}${button("Add device", "add-device", { kind: "primary", ico: "plus" })}</div></section><section class="metric-grid compact">${metric("Readers online", `${online}/${S().devices.length}`, "Current generated health state", online === S().devices.length ? "green" : "amber", "devices")}${metric("Registered users", registered.toLocaleString(), "Across all reader inventories", "blue", "employees")}${metric("Last worker run", timeAgo(S().devices.map((item) => item.lastSyncAt).sort().at(-1)), "Most recent device activity", "teal", "clock")}${metric("Needs attention", String(S().devices.length - online), "Offline or warning readers", S().devices.length === online ? "green" : "red", "alert")}</section><section class="device-grid">${S().devices.map((item) => `<article class="device-card"><header><span class="device-symbol">${icon("devices")}</span><div><h2>${esc(item.name)}</h2><p>${esc(item.location)} · ${esc(item.model)}</p></div>${pill(item.status)}</header><dl><div><dt>Network</dt><dd class="tabular">${esc(item.ip)}:${item.port}</dd></div><div><dt>Registered</dt><dd>${item.registeredUsers} users</dd></div><div><dt>Last sync</dt><dd>${timeAgo(item.lastSyncAt)}</dd></div><div><dt>Firmware</dt><dd>${esc(item.firmware)}</dd></div></dl><footer>${button("Test", "test-device", { id: item.id })}${button("Sync users", "sync-device", { id: item.id })}${button("Pull records", "pull-device", { kind: "primary", id: item.id })}</footer></article>`).join("")}</section></div>`;
  }

  function renderPayroll() {
    const periods = S().payrollPeriods;
    if (!periods.some((item) => item.key === ui.payrollPeriod)) ui.payrollPeriod = periods[0].key;
    const period = periods.find((item) => item.key === ui.payrollPeriod) || periods[0];
    const rows = D.payrollRows(period.key);
    const totalGross = rows.reduce((sum, row) => sum + row.baseSalary + row.overtimePay, 0);
    const totalDeductions = rows.reduce((sum, row) => sum + row.absenceDeduction + row.lateDeduction + row.providentFund + row.tax, 0);
    const totalNet = rows.reduce((sum, row) => sum + row.netPay, 0);
    return `<div class="page-stack"><section class="page-intro"><div><p>Generated payroll totals recalculate from attendance, salaries, deductions, and overtime.</p></div><div class="page-actions"><label class="inline-select"><span>Period</span><select data-filter="payroll-period">${periods.map((item) => `<option value="${item.key}" ${item.key === period.key ? "selected" : ""}>${esc(item.label)}</option>`).join("")}</select></label>${button("Export payroll", "export-payroll", { ico: "download", key: period.key })}${button(period.generatedAt ? "Regenerate draft" : "Generate draft", "generate-payroll", { kind: "primary", ico: "refresh", key: period.key })}</div></section><section class="payroll-summary"><article><span>Gross payroll</span><strong>${D.formatMoney(totalGross)}</strong><small>Base salary plus overtime</small></article><article><span>Deductions</span><strong>${D.formatMoney(totalDeductions)}</strong><small>Absence, late, PF, and tax</small></article><article><span>Net payable</span><strong>${D.formatMoney(totalNet)}</strong><small>${rows.length} active employees</small></article><article><span>Period status</span><strong>${esc(period.status)}</strong><small>${period.generatedAt ? `Generated ${timeAgo(period.generatedAt)}` : "Not generated yet"}</small></article></section><section class="panel table-panel">${panelHeader("Payroll register", period.label, `<div class="page-actions">${period.status === "Draft" ? button("Approve", "approve-payroll", { kind: "success", key: period.key }) : ""}${period.status === "Approved" ? button("Mark paid", "pay-payroll", { kind: "primary", key: period.key }) : ""}</div>`)}<div class="table-scroll"><table><thead><tr><th>Employee</th><th>Base</th><th>Overtime</th><th>Absence</th><th>Late</th><th>PF</th><th>Tax</th><th>Net pay</th></tr></thead><tbody>${rows.map((row) => { const person = employee(row.employeeId); return `<tr><td><div class="person-cell static">${avatar(person)}<span><strong>${esc(person?.name)}</strong><small>${esc(person?.employeeCode)}</small></span></div></td><td class="tabular">${D.formatMoney(row.baseSalary)}</td><td class="tabular positive">+${D.formatMoney(row.overtimePay)}</td><td class="tabular negative">−${D.formatMoney(row.absenceDeduction)}</td><td class="tabular negative">−${D.formatMoney(row.lateDeduction)}</td><td class="tabular">${D.formatMoney(row.providentFund)}</td><td class="tabular">${D.formatMoney(row.tax)}</td><td class="tabular strong">${D.formatMoney(row.netPay)}</td></tr>`; }).join("")}</tbody></table></div></section></div>`;
  }

  function renderOrganization() {
    return `<div class="page-stack"><section class="page-intro"><div><p>Organization units and shift assignments are live inputs to every employee record.</p></div><div class="page-actions">${button("Add shift", "add-shift", { ico: "plus" })}${button("Add department", "add-department", { kind: "primary", ico: "plus" })}</div></section><section class="organization-grid"><article class="panel">${panelHeader("Organization structure", "Departments")}<div class="org-list">${S().departments.map((item) => { const people = S().employees.filter((person) => person.departmentId === item.id); const head = employee(item.headEmployeeId); return `<button data-action="view-department" data-id="${item.id}"><span class="org-icon">${icon("building")}</span><span><strong>${esc(item.name)}</strong><small>${people.length} people · ${head ? `Head: ${esc(head.name)}` : "No head assigned"}</small></span><b>${esc(item.code)}</b></button>`; }).join("")}</div></article><article class="panel">${panelHeader("Time policy", "Shift definitions")}<div class="shift-list">${S().shifts.map((item) => `<article><div><strong>${esc(item.label)}</strong><small>${minutesToLabel(item.start)} – ${minutesToLabel(item.end)}</small></div><dl><div><dt>Grace</dt><dd>${item.grace} min</dd></div><div><dt>Break</dt><dd>${item.breakMinutes} min</dd></div><div><dt>Assigned</dt><dd>${S().employees.filter((person) => person.shiftId === item.id).length}</dd></div></dl></article>`).join("")}</div></article></section></div>`;
  }

  function renderSettings() {
    const state = S();
    return `<div class="page-stack"><section class="settings-grid"><article class="panel">${panelHeader("Workspace", "Organization settings")}<div class="form-stack"><label class="field"><span>Workspace name</span><input id="setting-workspace-name" value="${esc(state.workspace.name)}"></label><label class="field"><span>Organization name</span><input id="setting-organization" value="${esc(state.workspace.organization)}"></label><label class="field"><span>Currency</span><select id="setting-currency"><option ${state.workspace.currency === "NPR" ? "selected" : ""}>NPR</option><option ${state.workspace.currency === "USD" ? "selected" : ""}>USD</option></select></label>${button("Save workspace", "save-settings", { kind: "primary" })}</div></article><article class="panel">${panelHeader("Appearance", "Interface preferences")}<div class="form-stack"><label class="field"><span>Theme</span><select id="setting-theme"><option value="light" ${state.preferences.theme === "light" ? "selected" : ""}>Light</option><option value="dark" ${state.preferences.theme === "dark" ? "selected" : ""}>Dark</option></select></label><label class="field"><span>Density</span><select id="setting-density"><option value="comfortable" ${state.preferences.density === "comfortable" ? "selected" : ""}>Comfortable</option><option value="compact" ${state.preferences.density === "compact" ? "selected" : ""}>Compact</option></select></label><label class="field"><span>Dashboard range</span><select id="setting-range">${[7, 14, 30].map((value) => `<option value="${value}" ${state.preferences.dashboardRange === value ? "selected" : ""}>${value} days</option>`).join("")}</select></label>${button("Save preferences", "save-settings", { kind: "primary" })}</div></article><article class="panel panel-danger">${panelHeader("Demo controls", "Dynamic client workspace")}<p>This browser stores one coherent generated dataset. Regenerating replaces employees, attendance, leave, devices, payroll, and activity together.</p><div class="stacked-actions">${button("Export state snapshot", "export-snapshot", { ico: "download" })}${button("Regenerate demo workspace", "regenerate-demo", { kind: "danger", ico: "refresh" })}</div><dl class="data-facts"><div><dt>Generated</dt><dd>${formatDateTime(state.createdAt)}</dd></div><div><dt>Last changed</dt><dd>${timeAgo(state.updatedAt)}</dd></div><div><dt>Dataset seed</dt><dd class="tabular">${esc(state.seed.slice(0, 18))}…</dd></div></dl></article><article class="panel">${panelHeader("Data provider", "Integration readiness")}<div class="provider-card"><span>${icon("check")}</span><div><strong>Generated browser provider</strong><p>All screens share `window.HFData`. A Supabase provider can replace persistence without rebuilding the presentation layer.</p></div>${pill("Active")}</div><div class="provider-card muted"><span>${icon("building")}</span><div><strong>Supabase provider</strong><p>Project creation, authentication, RLS, and production tables are the next backend milestone.</p></div>${pill("Not connected")}</div></article></section></div>`;
  }

  const routes = {
    overview: renderOverview,
    attendance: renderAttendance,
    employees: renderEmployees,
    leave: renderLeave,
    reports: renderReports,
    devices: renderDevices,
    payroll: renderPayroll,
    organization: renderOrganization,
    settings: renderSettings,
  };

  function minutesToLabel(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours % 12 || 12}:${String(mins).padStart(2, "0")} ${hours >= 12 ? "PM" : "AM"}`;
  }

  function modal(title, body, options = {}) {
    modalLayer.hidden = false;
    modalLayer.innerHTML = `<button class="modal-backdrop" data-action="close-modal" aria-label="Close dialog"></button><section class="modal ${options.wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header><div><p class="eyebrow">${esc(options.eyebrow || "HajiriFlow")}</p><h2 id="modal-title">${esc(title)}</h2></div><button class="icon-button" data-action="close-modal" aria-label="Close">${icon("close")}</button></header><div class="modal-body">${body}</div>${options.footer ? `<footer>${options.footer}</footer>` : ""}</section>`;
    $("input, select, button", modalLayer)?.focus();
  }

  function closeModal() { modalLayer.hidden = true; modalLayer.innerHTML = ""; }
  function toast(message, kind = "success") {
    const item = document.createElement("div");
    item.className = `toast toast-${kind}`;
    item.innerHTML = `${icon(kind === "danger" ? "alert" : "check")}<span>${esc(message)}</span>`;
    toastRegion.append(item);
    requestAnimationFrame(() => item.classList.add("is-visible"));
    setTimeout(() => { item.classList.remove("is-visible"); setTimeout(() => item.remove(), 180); }, 3200);
  }

  function employeeForm(person = null) {
    const nextAttId = String(Math.max(...S().employees.map((item) => Number(item.attId))) + 1);
    modal(person ? "Edit employee" : "Add employee", `<form class="form-grid" data-form="employee" data-id="${person?.id || ""}"><label class="field field-wide"><span>Full name</span><input name="name" required value="${esc(person?.name || "")}"></label><label class="field field-wide"><span>Email</span><input name="email" type="email" required value="${esc(person?.email || "")}"></label><label class="field"><span>Attendance ID</span><input name="attId" required value="${esc(person?.attId || nextAttId)}"></label><label class="field"><span>Status</span><select name="status"><option ${person?.status !== "Inactive" ? "selected" : ""}>Active</option><option ${person?.status === "Inactive" ? "selected" : ""}>Inactive</option></select></label><label class="field"><span>Department</span><select name="departmentId">${S().departments.map((item) => `<option value="${item.id}" ${person?.departmentId === item.id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label><label class="field"><span>Shift</span><select name="shiftId">${S().shifts.map((item) => `<option value="${item.id}" ${person?.shiftId === item.id ? "selected" : ""}>${esc(item.label)}</option>`).join("")}</select></label><label class="field"><span>Role</span><input name="role" required value="${esc(person?.role || "Officer")}"></label><label class="field"><span>Section</span><input name="section" required value="${esc(person?.section || "Operations")}"></label><label class="field"><span>Employment type</span><select name="employmentType"><option ${person?.employmentType !== "Contract" ? "selected" : ""}>Permanent</option><option ${person?.employmentType === "Contract" ? "selected" : ""}>Contract</option></select></label><label class="field"><span>Base salary</span><input name="salary" type="number" min="0" required value="${person?.salary || 55000}"></label><div class="form-actions field-wide">${button("Cancel", "close-modal", { kind: "ghost" })}<button class="button button-primary" type="submit">Save employee</button></div></form>`, { eyebrow: "People directory" });
  }

  function attendanceForm(record = null) {
    modal(record ? "Attendance evidence" : "Add attendance correction", `<form class="form-grid" data-form="attendance" data-id="${record?.id || ""}"><label class="field field-wide"><span>Employee</span><select name="employeeId">${S().employees.filter((item) => item.status === "Active").map((item) => `<option value="${item.id}" ${record?.employeeId === item.id ? "selected" : ""}>${esc(item.name)} · ${esc(item.attId)}</option>`).join("")}</select></label><label class="field"><span>Date</span><input name="date" type="date" required value="${record?.date || ui.date}"></label><label class="field"><span>Status</span><select name="status">${["Present", "Late", "Absent", "Leave", "Field duty"].map((status) => `<option ${record?.status === status ? "selected" : ""}>${status}</option>`).join("")}</select></label><label class="field"><span>Check in</span><input name="checkIn" type="time" value="${record?.checkIn || "09:00"}"></label><label class="field"><span>Check out</span><input name="checkOut" type="time" value="${record?.checkOut || "17:00"}"></label><label class="field field-wide"><span>Evidence or reason</span><input name="source" required value="${esc(record?.source || "Manual correction")}"></label><div class="form-actions field-wide">${button("Cancel", "close-modal", { kind: "ghost" })}<button class="button button-primary" type="submit">Save correction</button></div></form>`, { eyebrow: "Attendance evidence" });
  }

  function leaveForm(fieldDuty = false) {
    modal(fieldDuty ? "Record field duty" : "Request leave", `<form class="form-grid" data-form="leave"><label class="field field-wide"><span>Employee</span><select name="employeeId">${S().employees.filter((item) => item.status === "Active").map((item) => `<option value="${item.id}">${esc(item.name)}</option>`).join("")}</select></label><label class="field"><span>Type</span><select name="type">${(fieldDuty ? ["Field duty"] : ["Home leave", "Sick leave", "Casual leave", "Unpaid leave", "Study leave"]).map((type) => `<option>${type}</option>`).join("")}</select></label><label class="field"><span>Status</span><select name="status"><option>Pending</option><option>Approved</option></select></label><label class="field"><span>Start</span><input name="startDate" type="date" value="${D.isoDate(new Date())}"></label><label class="field"><span>End</span><input name="endDate" type="date" value="${D.isoDate(new Date())}"></label><label class="field field-wide"><span>Reason</span><textarea name="reason" required></textarea></label><div class="form-actions field-wide">${button("Cancel", "close-modal", { kind: "ghost" })}<button class="button button-primary" type="submit">Save request</button></div></form>`, { eyebrow: fieldDuty ? "Kaaj workflow" : "Leave workflow" });
  }

  function employeeDetails(id) {
    const person = employee(id);
    if (!person) return;
    const records = S().attendance.filter((record) => record.employeeId === id && record.status !== "Weekly off");
    const present = records.filter((record) => ["Present", "Late", "Field duty"].includes(record.status)).length;
    modal(person.name, `<div class="profile-sheet"><div class="profile-identity">${avatar(person, "large")}<div><h3>${esc(person.role)}</h3><p>${esc(department(person.departmentId)?.name || "Unassigned")} · ${esc(person.section)}</p>${pill(person.status)}</div></div><div class="profile-stats"><div><span>Attendance rate</span><strong>${records.length ? Math.round((present / records.length) * 100) : 100}%</strong></div><div><span>Base salary</span><strong>${D.formatMoney(person.salary)}</strong></div><div><span>Shift</span><strong>${esc(shift(person.shiftId)?.label || "—")}</strong></div></div><dl class="profile-details"><div><dt>Employee code</dt><dd>${esc(person.employeeCode)}</dd></div><div><dt>Attendance ID</dt><dd>${esc(person.attId)}</dd></div><div><dt>Email</dt><dd>${esc(person.email)}</dd></div><div><dt>Phone</dt><dd>${esc(person.phone)}</dd></div><div><dt>Employment</dt><dd>${esc(person.employmentType)}</dd></div><div><dt>Device</dt><dd>${esc(device(person.deviceId)?.name || "Unassigned")}</dd></div></dl></div>`, { wide: true, eyebrow: person.employeeCode, footer: button("Edit profile", "edit-employee", { kind: "primary", ico: "edit", id: person.id }) });
  }

  function requestDetails(id) {
    const request = S().leaveRequests.find((item) => item.id === id);
    const person = employee(request?.employeeId);
    if (!request) return;
    modal(`${request.type} request`, `<div class="detail-stack"><div class="detail-person">${avatar(person, "medium")}<div><strong>${esc(person?.name)}</strong><small>${esc(department(person?.departmentId)?.name || "")}</small></div>${pill(request.status)}</div><dl class="detail-list"><div><dt>Dates</dt><dd>${formatDate(request.startDate)} to ${formatDate(request.endDate)}</dd></div><div><dt>Duration</dt><dd>${request.days} days</dd></div><div><dt>Reason</dt><dd>${esc(request.reason)}</dd></div></dl></div>`);
  }

  function simpleForm(type, title, fields) {
    modal(title, `<form class="form-grid" data-form="${type}">${fields}<div class="form-actions field-wide">${button("Cancel", "close-modal", { kind: "ghost" })}<button class="button button-primary" type="submit">Save</button></div></form>`);
  }

  function setLeave(id, status) {
    D.mutate((state) => {
      const request = state.leaveRequests.find((item) => item.id === id);
      if (!request) return;
      request.status = status;
      request.reviewedAt = new Date().toISOString();
      state.activities.unshift({ id: D.newId("activity"), verb: status.toLowerCase(), subject: `${request.type} request`, actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "leave" });
    });
    closeModal();
    toast(`Request ${status.toLowerCase()}`);
    render();
  }

  function payrollAction(key, action) {
    D.mutate((state) => {
      const period = state.payrollPeriods.find((item) => item.key === key);
      if (!period) return;
      if (action === "generate-payroll") { period.generatedAt = new Date().toISOString(); period.status = "Draft"; period.locked = false; }
      if (action === "approve-payroll") period.status = "Approved";
      if (action === "pay-payroll") { period.status = "Paid"; period.locked = true; }
      state.activities.unshift({ id: D.newId("activity"), verb: action.replace("-payroll", ""), subject: `${period.label} payroll`, actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "payroll" });
    });
    toast("Payroll status updated");
    render();
  }

  function generateReport(key) {
    D.mutate((state) => state.activities.unshift({ id: D.newId("activity"), verb: "generated", subject: `${key} report`, actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "report" }));
    if (key === "daily") exportAttendance();
    else if (key === "payroll") exportPayroll(ui.payrollPeriod);
    else exportEmployees(`${key}-report`);
    toast("Report generated");
    render();
  }

  function action(name, target) {
    const id = target.dataset.id;
    const key = target.dataset.key;
    switch (name) {
      case "add-employee": employeeForm(); break;
      case "edit-employee": employeeForm(employee(id)); break;
      case "view-employee": employeeDetails(id); break;
      case "manual-attendance": attendanceForm(); break;
      case "view-attendance": attendanceForm(S().attendance.find((record) => record.id === id)); break;
      case "request-leave": leaveForm(false); break;
      case "record-field-duty": leaveForm(true); break;
      case "view-leave": requestDetails(id); break;
      case "approve-leave": setLeave(id, "Approved"); break;
      case "reject-leave": setLeave(id, "Rejected"); break;
      case "add-device": simpleForm("device", "Add biometric reader", `<label class="field field-wide"><span>Reader name</span><input name="name" required></label><label class="field"><span>Location</span><input name="location" required></label><label class="field"><span>Model</span><input name="model" required value="SpeedFace V5L"></label><label class="field"><span>IP address</span><input name="ip" required value="192.168.20.100"></label><label class="field"><span>Port</span><input name="port" type="number" value="4370"></label>`); break;
      case "add-department": simpleForm("department", "Add department", `<label class="field field-wide"><span>Name</span><input name="name" required></label><label class="field"><span>Code</span><input name="code" required></label><label class="field"><span>Cost center</span><input name="budgetCenter" required></label>`); break;
      case "add-shift": simpleForm("shift", "Add shift", `<label class="field field-wide"><span>Shift name</span><input name="label" required></label><label class="field"><span>Start</span><input name="start" type="time" value="09:00"></label><label class="field"><span>End</span><input name="end" type="time" value="17:00"></label><label class="field"><span>Grace minutes</span><input name="grace" type="number" value="10"></label><label class="field"><span>Break minutes</span><input name="breakMinutes" type="number" value="60"></label>`); break;
      case "test-device": D.simulateDeviceAction(id, "test"); toast("Connection test completed"); render(); break;
      case "sync-device": D.simulateDeviceAction(id, "sync"); toast("Device users synchronized"); render(); break;
      case "pull-device": D.simulateDeviceAction(id, "pull"); toast("Attendance pull completed"); render(); break;
      case "pull-all-devices": S().devices.forEach((item) => D.simulateDeviceAction(item.id, "pull")); toast("All readers pulled successfully"); render(); break;
      case "reprocess-today": D.replaceAttendanceForDate(D.isoDate(new Date())); toast("Today's attendance recalculated"); render(); break;
      case "go-attendance": location.hash = "attendance"; break;
      case "generate-report": generateReport(key); break;
      case "generate-payroll": case "approve-payroll": case "pay-payroll": payrollAction(key, name); break;
      case "export-attendance": exportAttendance(); break;
      case "export-employees": exportEmployees(); break;
      case "export-payroll": exportPayroll(key || ui.payrollPeriod); break;
      case "export-activity": exportActivity(); break;
      case "export-snapshot": download("hajiriflow-demo-snapshot.json", JSON.stringify(S(), null, 2), "application/json"); break;
      case "regenerate-demo": modal("Regenerate demo workspace", `<p>This replaces every generated employee, record, request, device, payroll input, and activity in this browser.</p>`, { eyebrow: "Destructive demo action", footer: `${button("Cancel", "close-modal", { kind: "ghost" })}${button("Regenerate everything", "confirm-regenerate", { kind: "danger", ico: "refresh" })}` }); break;
      case "confirm-regenerate": D.regenerate(); closeModal(); toast("A new demo workspace was generated"); render(); break;
      case "save-settings": saveSettings(); break;
      case "notifications": openNotifications(); break;
      case "profile-menu": openProfile(); break;
      case "open-command-menu": openCommands(); break;
      case "close-modal": closeModal(); break;
      case "view-department": viewDepartment(id); break;
      default: break;
    }
  }

  function saveSettings() {
    D.mutate((state) => {
      state.workspace.name = $("#setting-workspace-name")?.value.trim() || state.workspace.name;
      state.workspace.organization = $("#setting-organization")?.value.trim() || state.workspace.organization;
      state.workspace.currency = $("#setting-currency")?.value || state.workspace.currency;
      state.preferences.theme = $("#setting-theme")?.value || state.preferences.theme;
      state.preferences.density = $("#setting-density")?.value || state.preferences.density;
      state.preferences.dashboardRange = Number($("#setting-range")?.value || state.preferences.dashboardRange);
    });
    toast("Settings saved");
    render();
  }

  function viewDepartment(id) {
    const item = department(id);
    if (!item) return;
    const people = S().employees.filter((person) => person.departmentId === id);
    modal(item.name, `<div class="detail-stack"><dl class="detail-list"><div><dt>Code</dt><dd>${esc(item.code)}</dd></div><div><dt>Cost center</dt><dd>${esc(item.budgetCenter)}</dd></div><div><dt>Head</dt><dd>${esc(employee(item.headEmployeeId)?.name || "Unassigned")}</dd></div><div><dt>People</dt><dd>${people.length}</dd></div></dl><div class="mini-people">${people.slice(0, 8).map((person) => `<button data-action="view-employee" data-id="${person.id}">${avatar(person)}<span>${esc(person.name)}</span></button>`).join("")}</div></div>`, { eyebrow: "Organization unit" });
  }

  function openNotifications() {
    D.markNotificationsRead();
    modal("Notifications", activityList(S().activities.slice(0, 10)), { wide: true, eyebrow: "Workspace activity" });
    renderNav();
  }

  function openProfile() {
    modal("Nischhal Subba", `<div class="profile-menu-card"><span class="user-avatar large">NS</span><div><strong>Workspace administrator</strong><p>${esc(S().workspace.organization)}</p></div></div><div class="stacked-actions">${button("Open settings", "go-settings", { kind: "primary" })}${button("Export state snapshot", "export-snapshot")}</div>`, { eyebrow: "Signed-in demo user" });
  }

  function submit(form) {
    const values = Object.fromEntries(new FormData(form));
    const type = form.dataset.form;
    if (type === "employee") {
      D.mutate((state) => {
        const existing = state.employees.find((item) => item.id === form.dataset.id);
        const payload = { name: values.name, email: values.email, attId: values.attId, departmentId: values.departmentId, shiftId: values.shiftId, role: values.role, section: values.section, employmentType: values.employmentType, salary: Number(values.salary), status: values.status };
        if (existing) Object.assign(existing, payload);
        else state.employees.push({ id: D.newId("emp"), employeeCode: `HF-${String(state.employees.length + 1).padStart(4, "0")}`, phone: `98${String(Math.floor(10000000 + Math.random() * 89999999))}`, deviceId: state.devices[0]?.id || null, joinedAt: D.isoDate(new Date()), avatarHue: Math.floor(180 + Math.random() * 140), ...payload });
        state.activities.unshift({ id: D.newId("activity"), verb: existing ? "updated" : "created", subject: values.name, actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "employee" });
      });
    }
    if (type === "attendance") {
      D.mutate((state) => {
        const existing = state.attendance.find((item) => item.id === form.dataset.id);
        const start = D.clockToMinutes(values.checkIn);
        const end = D.clockToMinutes(values.checkOut);
        const payload = { employeeId: values.employeeId, date: values.date, status: values.status, checkIn: values.checkIn || null, checkOut: values.checkOut || null, workedMinutes: start !== null && end !== null ? Math.max(0, end - start - 60) : 0, lateMinutes: values.status === "Late" ? Math.max(1, (start || 540) - 550) : 0, earlyMinutes: 0, source: values.source, deviceId: null };
        if (existing) Object.assign(existing, payload);
        else state.attendance.push({ id: D.newId("attendance"), ...payload });
        state.activities.unshift({ id: D.newId("activity"), verb: existing ? "corrected" : "added", subject: "manual attendance evidence", actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "attendance" });
      });
    }
    if (type === "leave") {
      const start = D.localDateFromIso(values.startDate);
      const end = D.localDateFromIso(values.endDate);
      const days = Math.max(1, Math.round((end - start) / 86400000) + 1);
      D.mutate((state) => state.leaveRequests.push({ id: D.newId("leave"), employeeId: values.employeeId, type: values.type, startDate: values.startDate, endDate: values.endDate, days, status: values.status, reason: values.reason, appliedAt: new Date().toISOString(), reviewedAt: values.status === "Pending" ? null : new Date().toISOString() }));
    }
    if (type === "device") D.mutate((state) => state.devices.push({ id: D.newId("device"), name: values.name, location: values.location, vendor: "ZKTeco", model: values.model, ip: values.ip, port: Number(values.port), status: "Attention", lastSyncAt: new Date(0).toISOString(), registeredUsers: 0, firmware: "Unknown", enabled: true }));
    if (type === "department") D.mutate((state) => state.departments.push({ id: D.newId("dept"), name: values.name, code: values.code, budgetCenter: values.budgetCenter, headEmployeeId: null, active: true }));
    if (type === "shift") D.mutate((state) => state.shifts.push({ id: D.newId("shift"), label: values.label, start: D.clockToMinutes(values.start), end: D.clockToMinutes(values.end), grace: Number(values.grace), breakMinutes: Number(values.breakMinutes), active: true }));
    closeModal();
    toast("Changes saved to the dynamic demo");
    render();
  }

  function csv(rows) {
    if (!rows.length) return "";
    const headers = Object.keys(rows[0]);
    const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    return [headers.map(quote).join(","), ...rows.map((row) => headers.map((header) => quote(row[header])).join(","))].join("\n");
  }

  function download(filename, content, type = "text/csv;charset=utf-8") {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([content], { type }));
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function exportAttendance() {
    const rows = S().attendance.filter((record) => record.date === ui.date).map((record) => { const person = employee(record.employeeId); return { date: record.date, attendance_id: person?.attId, employee: person?.name, department: department(person?.departmentId)?.name, status: record.status, check_in: record.checkIn, check_out: record.checkOut, worked_minutes: record.workedMinutes, late_minutes: record.lateMinutes, source: record.source }; });
    download(`hajiriflow-attendance-${ui.date}.csv`, csv(rows));
  }
  function exportEmployees(prefix = "employee-directory") { download(`hajiriflow-${prefix}.csv`, csv(S().employees.map((person) => ({ employee_code: person.employeeCode, attendance_id: person.attId, name: person.name, email: person.email, department: department(person.departmentId)?.name, section: person.section, role: person.role, shift: shift(person.shiftId)?.label, employment_type: person.employmentType, base_salary: person.salary, status: person.status })))); }
  function exportPayroll(key) { download(`hajiriflow-payroll-${key}.csv`, csv(D.payrollRows(key).map((row) => { const person = employee(row.employeeId); return { period: key, employee_code: person?.employeeCode, employee: person?.name, base_salary: row.baseSalary, overtime_pay: row.overtimePay, absence_deduction: row.absenceDeduction, late_deduction: row.lateDeduction, provident_fund: row.providentFund, tax: row.tax, net_pay: row.netPay }; }))); }
  function exportActivity() { download("hajiriflow-activity.csv", csv(S().activities.map((item) => ({ timestamp: item.occurredAt, actor: item.actor, action: item.verb, subject: item.subject, type: item.type })))); }

  function openCommands() { commandLayer.hidden = false; commandInput.value = ""; commandSearch(""); commandInput.focus(); }
  function commandSearch(query) {
    const needle = query.toLowerCase();
    const pages = groups.flatMap((group) => group[1]).map(([key, label]) => ({ label, detail: meta[key][0], route: key, symbol: key }));
    const actions = [
      { label: "Add employee", detail: "Create a workforce profile", action: "add-employee", symbol: "plus" },
      { label: "Record attendance", detail: "Add a manual correction", action: "manual-attendance", symbol: "attendance" },
      { label: "Request leave", detail: "Create a leave request", action: "request-leave", symbol: "leave" },
      { label: "Regenerate demo", detail: "Create a new dynamic workspace", action: "regenerate-demo", symbol: "refresh" },
    ];
    const people = S().employees.map((person) => ({ label: person.name, detail: `${person.employeeCode} · ${department(person.departmentId)?.name}`, action: "view-employee", id: person.id, symbol: "employees" }));
    const items = [...pages, ...actions, ...people].filter((item) => !needle || `${item.label} ${item.detail}`.toLowerCase().includes(needle)).slice(0, 12);
    commandResults.innerHTML = items.length ? items.map((item) => `<button data-command-route="${item.route || ""}" data-command-action="${item.action || ""}" data-command-id="${item.id || ""}"><span>${icon(item.symbol)}</span><span><strong>${esc(item.label)}</strong><small>${esc(item.detail)}</small></span></button>`).join("") : empty("No results", "Try another employee, page, or action.");
  }

  function updateClock() {
    const now = new Date();
    $("#nepal-time").textContent = new Intl.DateTimeFormat("en-NP", { timeZone: D.TIMEZONE, hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).format(now);
    $("#nepal-date").textContent = new Intl.DateTimeFormat("en-NP", { timeZone: D.TIMEZONE, weekday: "short", month: "short", day: "numeric" }).format(now);
  }

  function filter(target) {
    const key = target.dataset.filter;
    if (key === "date") ui.date = target.value;
    if (key === "attendance-status") ui.attendanceStatus = target.value;
    if (key === "employee-status") ui.employeeStatus = target.value;
    if (key === "leave-status") ui.leaveStatus = target.value;
    if (key === "department") ui.department = target.value;
    if (key === "search") ui.search = target.value;
    if (key === "payroll-period") ui.payrollPeriod = target.value;
    render();
  }

  document.addEventListener("click", (event) => {
    const actionTarget = event.target.closest("[data-action]");
    if (actionTarget) action(actionTarget.dataset.action, actionTarget);
    const command = event.target.closest("[data-command-route], [data-command-action]");
    if (command) {
      commandLayer.hidden = true;
      if (command.dataset.commandRoute) location.hash = command.dataset.commandRoute;
      if (command.dataset.commandAction) action(command.dataset.commandAction, { dataset: { id: command.dataset.commandId || "" } });
    }
    if (event.target.closest("[data-open-sidebar]")) shell.classList.add("sidebar-is-open");
    if (event.target.closest("[data-close-sidebar]")) shell.classList.remove("sidebar-is-open");
  });
  document.addEventListener("submit", (event) => { if (event.target.matches("[data-form]")) { event.preventDefault(); submit(event.target); } });
  document.addEventListener("input", (event) => { if (event.target === commandInput) commandSearch(event.target.value); if (event.target.matches('[data-filter="search"]')) filter(event.target); });
  document.addEventListener("change", (event) => { if (event.target.matches("[data-filter]:not([type=search])")) filter(event.target); });
  document.addEventListener("keydown", (event) => {
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") || (event.key === "/" && !typing)) { event.preventDefault(); openCommands(); }
    if (event.key === "Escape") { commandLayer.hidden = true; closeModal(); shell.classList.remove("sidebar-is-open"); }
  });
  window.addEventListener("hashchange", render);
  window.addEventListener("resize", () => { if (innerWidth > 980) shell.classList.remove("sidebar-is-open"); });
  D.subscribe(() => renderNav());
  updateClock();
  setInterval(updateClock, 1000);
  render();
})();
