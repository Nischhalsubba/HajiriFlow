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

  function render(options = {}) {
    const current = routes[route()] ? route() : "overview";
    document.documentElement.dataset.theme = S().preferences.theme;
    document.documentElement.dataset.density = S().preferences.density;
    $("#page-kicker").textContent = meta[current][0];
    $("#page-title").textContent = meta[current][1];
    renderNav();
    workspace.innerHTML = routes[current]();
    shell.classList.remove("sidebar-is-open");
    if (options.focusWorkspace === true) {
      workspace.focus({ preventScroll: true });
    }
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
    return `<div class="trend-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Attendance rate trend"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2563eb" stop-opacity=".24"/><stop offset="1" stop-color="#2563eb" stop-opacity="0"/></linearGradient></defs><path class="chart-area" d="M${coords[0][0]},${height - pad} L${coords.map(([x, y]) => `${x},${y}`).join(" L")} L${coords.at(-1)[0]},${height - pad} Z" fill="url(#chart-fill)"/><polyline class="chart-line" points="${line}" fill="none"/><g>${coords.filter((_, index) => index % Math.max(1, Math.floor(coords.length / 6)) === 0 || index === coords.length - 1).map(([x, y, point]) => `<circle cx="${x}" cy="${y}" r="3.5"><title>${formatDate(point.date)} · ${point.rate}% attendance</title></circle>`).join("")}</g></svg><div class="chart-caption"><span>${formatDate(points[0].date)}</span><span>${formatDate(points.at(-1).date)}</span></div></div>`;
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
      count: S().employees.filter((person) => person.departmentId === item.id).length,
      present: records.filter((record) => employee(record.employeeId)?.departmentId === item.id && ["Present", "Late"].includes(record.status)).length,
    }));
    return `<div class="page-stack"><section class="page-intro"><div><p>Monitor today's workforce, exceptions, and system health from one operational view.</p></div><div class="page-actions">${button("Record attendance", "manual-attendance", { ico: "attendance" })}${button("Add employee", "add-employee", { kind: "primary", ico: "plus" })}</div></section><section class="metric-grid">${metric("Attendance today", `${summary.attendanceRate}%`, `${summary.present} present · ${summary.late} late`, "blue", "attendance")}${metric("Active workforce", String(summary.totalActive), `${summary.absent} absent · ${summary.onLeave} on leave`, "teal", "employees")}${metric("Open approvals", String(summary.pendingLeave), "Leave requests waiting", summary.pendingLeave ? "amber" : "green", "leave")}${metric("Device health", `${summary.onlineDevices}/${S().devices.length}`, `${summary.offlineDevices} need attention`, summary.offlineDevices ? "red" : "green", "devices")}</section><section class="dashboard-grid"><article class="panel panel-wide">${panelHeader("30-day signal", "Attendance trend", `<a class="text-link" href="#reports">Open reports</a>`)}${trendChart(D.attendanceTrend(30))}</article><article class="panel">${panelHeader("Exceptions", "Needs attention", `<a class="text-link" href="#attendance">Open attendance</a>`)}<div class="exception-list">${exceptions.map((record) => { const person = employee(record.employeeId); return `<button class="exception-item" data-action="view-attendance" data-id="${record.id}">${avatar(person)}<span><strong>${esc(person?.name)}</strong><small>${esc(department(person?.departmentId)?.name || "Unassigned")} · ${record.status}</small></span>${pill(record.status)}</button>`; }).join("") || empty("No exceptions", "Everyone is accounted for in the selected workday.")}</div></article><article class="panel panel-wide">${panelHeader("Coverage", "Department presence")}<div class="department-coverage">${departmentCounts.map((item) => `<div><span><strong>${esc(item.name)}</strong><small>${item.present}/${item.count} accounted for</small></span><div class="coverage-track"><i style="width:${item.count ? Math.round(item.present / item.count * 100) : 0}%"></i></div><b>${item.count ? Math.round(item.present / item.count * 100) : 0}%</b></div>`).join("")}</div></article><article class="panel">${panelHeader("Activity", "Recent changes")} ${activityList(S().activities.slice(0, 7))}</article></section></div>`;
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

  function reportDefinitions() {
    return [
      ["daily", "Daily attendance register", "Employee-by-employee status, first in, last out, and worked time.", "attendance"],
      ["monthly", "Monthly workforce summary", "Employee-level attendance rates, late minutes, absence, and overtime.", "reports"],
      ["department", "Department coverage", "Compare daily coverage and exceptions across organization units.", "building"],
      ["payroll", "Payroll reconciliation", "Trace compensation inputs back to attendance and leave records.", "money"],
    ];
  }

  function renderReports() {
    const definitions = reportDefinitions();
    const trend = D.attendanceTrend(30);
    const average = Math.round(trend.reduce((sum, point) => sum + point.rate, 0) / trend.length);
    return `<div class="page-stack"><section class="page-intro"><div><p>Generate exportable reports from the shared dynamic workforce state.</p></div><div class="page-actions">${button("Export activity log", "export-activity", { ico: "download" })}</div></section><section class="metric-grid compact">${metric("30-day attendance", `${average}%`, "Calculated from generated evidence", "blue", "reports")}${metric("Attendance records", S().attendance.length.toLocaleString(), "Across the generated history", "teal", "attendance")}${metric("Active workforce", String(S().employees.filter((item) => item.status === "Active").length), "Included in reporting", "green", "employees")}${metric("Report types", String(definitions.length), "Ready for client walkthrough", "amber", "file")}</section><section class="report-grid">${definitions.map(([id, title, copy, symbol]) => `<article class="report-card"><span class="report-icon">${icon(symbol)}</span><div><h2>${title}</h2><p>${copy}</p></div><div class="report-card-footer"><span>CSV export · live calculations</span>${button("Generate", "generate-report", { kind: "primary", key: id })}</div></article>`).join("")}</section></div>`;
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
    return `<div class="page-stack"><section class="settings-grid"><article class="panel">${panelHeader("Workspace", "Organization settings")}<div class="form-stack"><label class="field"><span>Workspace name</span><input id="setting-workspace-name" value="${esc(state.workspace.name)}"></label><label class="field"><span>Organization name</span><input id="setting-organization" value="${esc(state.workspace.organization)}"></label><label class="field"><span>Currency</span><select id="setting-currency"><option ${state.workspace.currency === "NPR" ? "selected" : ""}>NPR</option><option ${state.workspace.currency === "USD" ? "selected" : ""}>USD</option></select></label>${button("Save workspace", "save-settings", { kind: "primary" })}</div></article><article class="panel">${panelHeader("Appearance", "Interface preferences")}<div class="form-stack"><label class="field"><span>Theme</span><select id="setting-theme"><option value="light" ${state.preferences.theme === "light" ? "selected" : ""}>Light</option><option value="dark" ${state.preferences.theme === "dark" ? "selected" : ""}>Dark</option></select></label><label class="field"><span>Density</span><select id="setting-density"><option value="comfortable" ${state.preferences.density === "comfortable" ? "selected" : ""}>Comfortable</option><option value="compact" ${state.preferences.density === "compact" ? "selected" : ""}>Compact</option></select></label><label class="field"><span>Dashboard range</span><select id="setting-range">${[7, 14, 30].map((value) => `<option value="${value}" ${state.preferences.dashboardRange === value ? "selected" : ""}>${value} days</option>`).join("")}</select></label>${button("Save preferences", "save-settings", { kind: "primary" })}</div></article><article class="panel panel-danger">${panelHeader("Demo controls", "Dynamic client workspace")}<p>This browser stores one coherent generated dataset. Regenerating replaces employees, attendance, leave, devices, payroll, and activity together.</p><div class="stacked-actions">${button("Export state snapshot", "export-snapshot", { ico: "download" })}${button("Regenerate demo workspace", "regenerate-demo", { kind: "danger", ico: "refresh" })}</div><dl class="data-facts"><div><dt>Generated</dt><dd>${formatDateTime(state.createdAt)}</dd></div><div><dt>Last changed</dt><dd>${timeAgo(state.updatedAt)}</dd></div><div><dt>Dataset seed</dt><dd class="tabular">${esc(state.seed.slice(0, 18))}…</dd></div></dl></article><article class="panel">${panelHeader("Data provider", "Integration readiness")}<div class="provider-card"><span>${icon("check")}</span><div><strong>Generated browser provider</strong><p>All screens share the window.HFData provider. A reviewed API-backed provider must replace generated operational state before production views are enabled.</p></div>${pill("Demo only")}</div><div class="provider-card muted"><span>${icon("building")}</span><div><strong>Authoritative API provider</strong><p>Production stays locked until organization-scoped workforce, attendance, device, reporting, and payroll data is loaded from the reviewed server APIs.</p></div>${pill("Integration required")}</div></article></section></div>`;
  }

  const routes = { overview: renderOverview, attendance: renderAttendance, employees: renderEmployees, leave: renderLeave, reports: renderReports, devices: renderDevices, payroll: renderPayroll, organization: renderOrganization, settings: renderSettings };

  function modal(title, body, options = {}) {
    modalLayer.innerHTML = `<div class="modal-backdrop" data-action="close-modal"></div><section class="modal ${options.wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><p>${esc(options.eyebrow || "HajiriFlow")}</p><h2 id="modal-title">${esc(title)}</h2></div><button type="button" class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon("close")}</button></header><div class="modal-body">${body}</div>${options.footer ? `<footer class="modal-footer">${options.footer}</footer>` : ""}</section>`;
    modalLayer.hidden = false;
    requestAnimationFrame(() => modalLayer.querySelector("input, select, textarea, button")?.focus());
  }

  function closeModal() { modalLayer.hidden = true; modalLayer.innerHTML = ""; }
  function toast(message, kind = "info") {
    const item = document.createElement("div");
    item.className = `toast toast-${kind}`;
    const text = document.createElement("span");
    text.textContent = String(message ?? "");
    item.append(text);
    toastRegion.append(item);
    requestAnimationFrame(() => item.classList.add("is-visible"));
    setTimeout(() => { item.classList.remove("is-visible"); setTimeout(() => item.remove(), 220); }, 3200);
  }

  function employeeForm(item = null) {
    const current = item || { name: "", email: "", attId: "", departmentId: S().departments[0]?.id, shiftId: S().shifts[0]?.id, role: "Associate", section: "", employmentType: "Permanent", salary: 50000, status: "Active" };
    return `<form class="form-stack" data-form="employee" data-id="${current.id || ""}"><div class="form-grid two"><label class="field"><span>Full name</span><input name="name" required value="${esc(current.name)}"></label><label class="field"><span>Email</span><input name="email" type="email" required value="${esc(current.email)}"></label><label class="field"><span>Attendance ID</span><input name="attId" required value="${esc(current.attId)}"></label><label class="field"><span>Role</span><input name="role" required value="${esc(current.role)}"></label><label class="field"><span>Department</span><select name="departmentId">${S().departments.map((item) => `<option value="${item.id}" ${item.id === current.departmentId ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label><label class="field"><span>Shift</span><select name="shiftId">${S().shifts.map((item) => `<option value="${item.id}" ${item.id === current.shiftId ? "selected" : ""}>${esc(item.label)}</option>`).join("")}</select></label><label class="field"><span>Section</span><input name="section" value="${esc(current.section)}"></label><label class="field"><span>Employment</span><select name="employmentType">${["Permanent", "Contract", "Part-time"].map((value) => `<option ${value === current.employmentType ? "selected" : ""}>${value}</option>`).join("")}</select></label><label class="field"><span>Base salary</span><input name="salary" type="number" min="0" step="500" value="${current.salary}"></label><label class="field"><span>Status</span><select name="status"><option ${current.status === "Active" ? "selected" : ""}>Active</option><option ${current.status === "Inactive" ? "selected" : ""}>Inactive</option></select></label></div><footer class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">${item ? "Save changes" : "Create employee"}</button></footer></form>`;
  }

  function attendanceForm(item = null) {
    const current = item || { employeeId: S().employees[0]?.id, date: ui.date, status: "Present", checkIn: "09:00", checkOut: "17:30", source: "Manual correction" };
    return `<form class="form-stack" data-form="attendance" data-id="${current.id || ""}"><div class="form-grid two"><label class="field"><span>Employee</span><select name="employeeId">${S().employees.filter((item) => item.status === "Active").map((person) => `<option value="${person.id}" ${person.id === current.employeeId ? "selected" : ""}>${esc(person.name)} · ${esc(person.attId)}</option>`).join("")}</select></label><label class="field"><span>Date</span><input type="date" name="date" value="${current.date}"></label><label class="field"><span>Status</span><select name="status">${["Present", "Late", "Absent", "Leave", "Field duty"].map((value) => `<option ${value === current.status ? "selected" : ""}>${value}</option>`).join("")}</select></label><label class="field"><span>Source</span><select name="source"><option ${current.source === "Manual correction" ? "selected" : ""}>Manual correction</option><option ${current.source === "Administrator entry" ? "selected" : ""}>Administrator entry</option></select></label><label class="field"><span>Check in</span><input type="time" name="checkIn" value="${current.checkIn || ""}"></label><label class="field"><span>Check out</span><input type="time" name="checkOut" value="${current.checkOut || ""}"></label></div><footer class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">Save attendance</button></footer></form>`;
  }

  function leaveForm(kind = "leave") {
    const today = D.isoDate(new Date());
    return `<form class="form-stack" data-form="leave"><div class="form-grid two"><label class="field"><span>Employee</span><select name="employeeId">${S().employees.filter((item) => item.status === "Active").map((person) => `<option value="${person.id}">${esc(person.name)} · ${esc(person.employeeCode)}</option>`).join("")}</select></label><label class="field"><span>Type</span><select name="type"><option>${kind === "field" ? "Field duty" : "Annual leave"}</option><option>Sick leave</option><option>Casual leave</option><option>Unpaid leave</option><option>Field duty</option></select></label><label class="field"><span>Start date</span><input type="date" name="startDate" value="${today}" required></label><label class="field"><span>End date</span><input type="date" name="endDate" value="${today}" required></label><label class="field field-wide"><span>Reason</span><textarea name="reason" rows="3" required placeholder="Add a clear reason for audit history"></textarea></label><label class="field"><span>Status</span><select name="status"><option>Pending</option><option>Approved</option></select></label></div><footer class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">Save request</button></footer></form>`;
  }

  function deviceForm() {
    return `<form class="form-stack" data-form="device"><div class="form-grid two"><label class="field"><span>Device name</span><input name="name" required placeholder="Main Gate Reader"></label><label class="field"><span>Location</span><input name="location" required placeholder="Head Office"></label><label class="field"><span>Model</span><input name="model" required placeholder="ZKTeco K40"></label><label class="field"><span>IP address</span><input name="ip" required placeholder="192.168.1.201"></label><label class="field"><span>Port</span><input name="port" type="number" value="4370" required></label></div><footer class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">Add device</button></footer></form>`;
  }

  function departmentForm() {
    return `<form class="form-stack" data-form="department"><div class="form-grid two"><label class="field"><span>Name</span><input name="name" required placeholder="Customer Success"></label><label class="field"><span>Code</span><input name="code" required placeholder="CS"></label><label class="field"><span>Cost center</span><input name="budgetCenter" required placeholder="CC-700"></label></div><footer class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">Add department</button></footer></form>`;
  }

  function shiftForm() {
    return `<form class="form-stack" data-form="shift"><div class="form-grid two"><label class="field"><span>Shift name</span><input name="label" required placeholder="Standard shift"></label><label class="field"><span>Start time</span><input name="start" type="time" value="09:00" required></label><label class="field"><span>End time</span><input name="end" type="time" value="17:30" required></label><label class="field"><span>Grace minutes</span><input name="grace" type="number" min="0" value="10"></label><label class="field"><span>Break minutes</span><input name="breakMinutes" type="number" min="0" value="60"></label></div><footer class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">Add shift</button></footer></form>`;
  }

  function viewEmployee(id) {
    const person = employee(id);
    if (!person) return;
    const records = S().attendance.filter((item) => item.employeeId === id).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);
    modal(person.name, `<div class="employee-detail"><header>${avatar(person, "large")}<div><p>${esc(person.employeeCode)} · Attendance ${esc(person.attId)}</p><h3>${esc(person.role)}</h3><span>${esc(department(person.departmentId)?.name || "Unassigned")} · ${esc(person.section)}</span></div></header><dl class="detail-list"><div><dt>Email</dt><dd>${esc(person.email)}</dd></div><div><dt>Phone</dt><dd>${esc(person.phone)}</dd></div><div><dt>Shift</dt><dd>${esc(shift(person.shiftId)?.label || "Unassigned")}</dd></div><div><dt>Employment</dt><dd>${esc(person.employmentType)}</dd></div><div><dt>Base salary</dt><dd>${D.formatMoney(person.salary)}</dd></div><div><dt>Status</dt><dd>${pill(person.status)}</dd></div></dl><section><h3>Recent attendance</h3>${records.length ? `<div class="mini-records">${records.map((item) => `<div><span>${formatDate(item.date)}</span>${pill(item.status)}<small>${item.checkIn || "—"} · ${worked(item.workedMinutes)}</small></div>`).join("")}</div>` : empty("No attendance", "This person has no records in the generated history.")}</section></div>`, { eyebrow: "Employee record", wide: true });
  }

  function viewAttendance(id) {
    const record = S().attendance.find((item) => item.id === id);
    if (!record) return;
    const person = employee(record.employeeId);
    modal("Attendance evidence", `<div class="detail-stack"><div class="evidence-header">${avatar(person, "medium")}<div><h3>${esc(person?.name)}</h3><p>${formatDate(record.date)} · ${esc(person?.employeeCode)}</p></div>${pill(record.status)}</div><dl class="detail-list"><div><dt>Check in</dt><dd>${record.checkIn || "—"}</dd></div><div><dt>Check out</dt><dd>${record.checkOut || "—"}</dd></div><div><dt>Worked</dt><dd>${worked(record.workedMinutes)}</dd></div><div><dt>Late</dt><dd>${record.lateMinutes} min</dd></div><div><dt>Source</dt><dd>${esc(record.source)}</dd></div><div><dt>Device</dt><dd>${esc(device(record.deviceId)?.name || "Manual")}</dd></div></dl></div>`, { eyebrow: "Record evidence", footer: `<button type="button" class="button button-primary" data-action="edit-attendance" data-id="${record.id}">Add correction</button>` });
  }

  function viewLeave(id) {
    const item = S().leaveRequests.find((request) => request.id === id);
    const person = employee(item?.employeeId);
    if (!item) return;
    modal("Leave request", `<div class="detail-stack"><div class="evidence-header">${avatar(person, "medium")}<div><h3>${esc(person?.name)}</h3><p>${esc(item.type)} · ${item.days} days</p></div>${pill(item.status)}</div><dl class="detail-list"><div><dt>Dates</dt><dd>${formatDate(item.startDate)} – ${formatDate(item.endDate)}</dd></div><div><dt>Reason</dt><dd>${esc(item.reason)}</dd></div><div><dt>Submitted</dt><dd>${formatDateTime(item.appliedAt)}</dd></div><div><dt>Reviewed</dt><dd>${item.reviewedAt ? formatDateTime(item.reviewedAt) : "Pending"}</dd></div></dl></div>`, { eyebrow: "Approval record" });
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
  window.addEventListener("hashchange", () => render({ focusWorkspace: true }));
  window.addEventListener("resize", () => { if (innerWidth > 980) shell.classList.remove("sidebar-is-open"); });
  D.subscribe(() => renderNav());
  updateClock();
  setInterval(updateClock, 1000);
  render({ focusWorkspace: true });
})();
