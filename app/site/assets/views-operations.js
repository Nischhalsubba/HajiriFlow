const reportCatalog = [
  { id: "daily", title: "Daily attendance", description: "Present, absent, leave, and field-duty status for one day.", icon: "calendar", format: "Excel · PDF" },
  { id: "absent", title: "Absent employees", description: "Employees without attendance evidence or approved leave.", icon: "alert", format: "Excel · PDF" },
  { id: "department", title: "Department coverage", description: "Present, absent, and leave counts by department.", icon: "building", format: "Excel · PDF" },
  { id: "monthly-detail", title: "Monthly employee detail", description: "Daily punches, hours, late time, overtime, and remarks.", icon: "file", format: "Excel · Print" },
  { id: "monthly-summary", title: "Monthly workforce summary", description: "Aggregated attendance totals for every employee.", icon: "reports", format: "Excel · PDF" },
  { id: "hajiri", title: "Hajiri register", description: "BS month cross-tab register with leave and holiday codes.", icon: "attendance", format: "A3 Print · Excel" },
];

function reportsView() {
  return `
    ${pageHeader("Reports library", "Generate attendance and workforce reports from one shared calculation model.", `<button class="button button-secondary" data-action="report-history">${icon("clock")} Export history</button>`)}
    <section class="report-grid">
      ${reportCatalog.map((report) => `<article class="report-card" data-search-row="${escapeHtml(`${report.title} ${report.description}`.toLowerCase())}"><span class="report-icon">${icon(report.icon)}</span><div><h3>${escapeHtml(report.title)}</h3><p>${escapeHtml(report.description)}</p><small>${escapeHtml(report.format)}</small></div><button class="button button-secondary button-sm" data-action="run-report" data-report="${report.id}">Generate ${icon("arrowRight")}</button></article>`).join("")}
    </section>
    <section class="panel report-preview">
      <div class="panel-header"><div><h3>Report principles</h3><p>Controls that keep exports accurate and accountable</p></div></div>
      <div class="principle-grid">
        ${principle("check", "One calculation engine", "Daily, department, monthly, and payroll totals use the same attendance rules.")}
        ${principle("lock", "Permission-aware exports", "Organizational scope is preserved when downloading or printing.")}
        ${principle("calendar", "AD and BS dates", "Every operational report carries both calendar references where useful.")}
        ${principle("file", "Traceable evidence", "Reports retain source context without changing immutable punch records.")}
      </div>
    </section>`;
}

function principle(iconName, title, description) {
  return `<div class="principle"><span>${icon(iconName)}</span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div></div>`;
}

function devicesView() {
  const online = state.devices.filter((device) => device.status === "Online").length;
  const users = state.devices.reduce((sum, device) => sum + Number(device.users), 0);
  return `
    ${pageHeader("Biometric devices", "Monitor connectivity, trigger safe pulls, and review device identity coverage.", `<button class="button button-secondary" data-action="pull-all">${icon("refresh")} Pull all</button><button class="button button-primary" data-action="add-device">${icon("plus")} Add device</button>`)}
    <section class="metric-grid">
      ${metricCard("devices", "", "Registered devices", state.devices.length, "Across configured locations")}
      ${metricCard("wifi", "is-blue", "Online now", online, `${state.devices.length - online} needs attention`)}
      ${metricCard("employees", "is-amber", "Device identities", users, "Registrations across devices")}
      ${metricCard("clock", "is-red", "Last full pull", "2 min", "Demo connection state")}
    </section>
    <section class="device-grid">${state.devices.map(deviceCard).join("")}</section>
    <section class="panel">
      <div class="panel-header"><div><h3>Recent pull activity</h3><p>Simulated worker runs for this frontend prototype</p></div><button class="button button-ghost button-sm" data-action="device-history">View history</button></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Device</th><th>Started</th><th>Duration</th><th>Records</th><th>Status</th></tr></thead><tbody>
        ${state.devices.map((device, index) => `<tr><td><strong>${escapeHtml(device.name)}</strong><small>${escapeHtml(device.ip)}</small></td><td>${index ? `${8 + index}:40 AM` : "10:48 AM"}</td><td>${6 + index * 2}s</td><td>${42 - index * 9}</td><td>${statusBadge(device.status === "Online" ? "Approved" : "Attention")}</td></tr>`).join("")}
      </tbody></table></div>
    </section>`;
}

function deviceCard(device) {
  return `<article class="device-card ${device.status !== "Online" ? "has-warning" : ""}" data-search-row="${escapeHtml(`${device.name} ${device.ip} ${device.model} ${device.location}`.toLowerCase())}">
    <div class="device-card-top"><span class="device-glyph">${icon("fingerprint")}</span>${statusBadge(device.status)}</div>
    <div class="device-copy"><h3>${escapeHtml(device.name)}</h3><p>${escapeHtml(device.model)} · ${escapeHtml(device.location)}</p></div>
    <dl class="device-details"><div><dt>IP address</dt><dd>${escapeHtml(device.ip)}</dd></div><div><dt>Protocol</dt><dd>${escapeHtml(device.protocol)}</dd></div><div><dt>Users</dt><dd>${device.users}</dd></div><div><dt>Last sync</dt><dd>${escapeHtml(device.lastSync)}</dd></div></dl>
    <div class="device-actions"><button class="button button-secondary button-sm" data-action="test-device" data-id="${device.id}">${icon("pulse")} Test</button><button class="button button-secondary button-sm" data-action="sync-device" data-id="${device.id}">${icon("refresh")} Sync</button><button class="table-action" data-action="edit-device" data-id="${device.id}" aria-label="Edit device">${icon("edit")}</button></div>
  </article>`;
}

function payrollView() {
  const current = state.payroll[0];
  const last = state.payroll.find((period) => period.status === "Posted");
  return `
    ${pageHeader("Payroll workspace", "Prepare payroll from approved and locked attendance snapshots.", `<button class="button button-secondary" data-action="payroll-settings">${icon("settings")} Payroll setup</button><button class="button button-primary" data-action="new-payroll">${icon("plus")} New payroll</button>`)}
    <div class="payroll-banner">
      <span class="payroll-banner-icon">${icon("lock")}</span>
      <div><p>Current payroll period</p><h2>${escapeHtml(current.period)}</h2><span>Attendance must be reviewed and locked before generation.</span></div>
      <div class="payroll-banner-actions">${statusBadge(current.attendance)}<button class="button button-light" data-action="review-attendance">Review attendance</button></div>
    </div>
    <section class="metric-grid">
      ${metricCard("employees", "", "Last payroll employees", last?.employees || 0, last?.period || "No posted period")}
      ${metricCard("money", "is-blue", "Gross payroll", formatCurrency(last?.gross || 0), "Last posted period")}
      ${metricCard("wallet", "is-amber", "Deductions", formatCurrency(last?.deductions || 0), "Tax and configured heads")}
      ${metricCard("check", "is-red", "Net payroll", formatCurrency(last?.net || 0), "Last posted period")}
    </section>
    <section class="panel">
      <div class="panel-header"><div><h3>Payroll periods</h3><p>Draft, approved, posted, and reversed runs</p></div><button class="button button-secondary button-sm" data-action="export-payroll">${icon("download")} Export</button></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Period</th><th>Employees</th><th>Gross</th><th>Deductions</th><th>Net pay</th><th>Attendance</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${state.payroll.map(payrollRow).join("")}</tbody></table></div>
    </section>`;
}

function payrollRow(period) {
  return `<tr><td><strong>${escapeHtml(period.period)}</strong><small>BS payroll month</small></td><td>${period.employees || "—"}</td><td>${period.gross ? formatCurrency(period.gross) : "—"}</td><td>${period.deductions ? formatCurrency(period.deductions) : "—"}</td><td><strong>${period.net ? formatCurrency(period.net) : "—"}</strong></td><td>${statusBadge(period.attendance)}</td><td>${statusBadge(period.status)}</td><td><button class="button button-secondary button-sm" data-action="view-payroll" data-id="${period.id}">${period.status === "Draft" ? "Continue" : "View"}</button></td></tr>`;
}

function organizationView() {
  const departments = [...new Set(state.employees.map((employee) => employee.department))].sort();
  return `
    ${pageHeader("Organization structure", "Manage departments, sections, and effective shift assignments.", `<button class="button button-primary" data-action="add-department">${icon("plus")} Add department</button>`)}
    <div class="organization-grid">
      <section class="panel span-two"><div class="panel-header"><div><h3>Department hierarchy</h3><p>${departments.length} departments in this demo workspace</p></div></div><div class="org-list">${departments.map((department, index) => organizationRow(department, index)).join("")}</div></section>
      <section class="panel"><div class="panel-header"><div><h3>Active shifts</h3><p>Effective work patterns</p></div><button class="button button-ghost button-sm" data-action="add-shift">Add shift</button></div><div class="shift-list">${["General 09:00–17:00", "Early 08:00–16:00", "Field Flexible"].map((shift, index) => `<div class="shift-item"><span class="shift-icon">${icon("clock")}</span><div><strong>${shift}</strong><small>${state.employees.filter((employee) => employee.shift === shift).length} employees assigned</small></div><button class="table-action" data-action="edit-shift" data-id="${index}">${icon("edit")}</button></div>`).join("")}</div></section>
    </div>`;
}

function organizationRow(department, index) {
  const members = state.employees.filter((employee) => employee.department === department);
  const sections = [...new Set(members.map((employee) => employee.section))];
  return `<div class="org-row"><span class="org-icon">${icon("building")}</span><div class="org-copy"><strong>${escapeHtml(department)}</strong><small>${sections.map(escapeHtml).join(" · ")}</small></div><span class="org-count">${members.length} people</span><button class="table-action" data-action="edit-department" data-id="${index}">${icon("edit")}</button></div>`;
}

function settingsView() {
  return `
    ${pageHeader("Workspace settings", "Configure presentation preferences and manage this interactive demo.", "")}
    <div class="settings-grid">
      <section class="panel settings-section"><div class="panel-header"><div><h3>Company profile</h3><p>Identity used throughout the workspace</p></div></div><form data-form="settings"><div class="form-grid"><label class="field"><span>Company name</span><input name="company" value="${escapeHtml(state.settings.company)}"></label><label class="field"><span>Business timezone</span><select name="timezone"><option selected>Asia/Kathmandu</option></select></label><label class="field"><span>Weekly off</span><select name="weekOff"><option ${state.settings.weekOff === "Saturday" ? "selected" : ""}>Saturday</option><option>Sunday</option></select></label><label class="field"><span>Date display</span><select name="dateFormat"><option ${state.settings.dateFormat === "BS + AD" ? "selected" : ""}>BS + AD</option><option>AD only</option></select></label></div><div class="form-actions"><button class="button button-primary" type="submit">Save settings</button></div></form></section>
      <section class="panel settings-section"><div class="panel-header"><div><h3>Demo data</h3><p>Browser-local state for interaction testing</p></div></div><div class="settings-actions"><button class="settings-action" data-action="export-demo">${icon("download")}<span><strong>Export demo data</strong><small>Download the current browser state as JSON</small></span>${icon("chevron")}</button><button class="settings-action" data-action="reset-demo">${icon("refresh")}<span><strong>Reset demo workspace</strong><small>Restore the original employees and records</small></span>${icon("chevron")}</button></div></section>
      <section class="panel settings-section"><div class="panel-header"><div><h3>Deployment boundary</h3><p>What is and is not running on Netlify</p></div></div><div class="boundary-list"><div><span class="status-dot is-online"></span><strong>Frontend prototype</strong><small>Live on Netlify</small></div><div><span class="status-dot"></span><strong>FastAPI backend</strong><small>Requires a separate application host</small></div><div><span class="status-dot"></span><strong>PostgreSQL</strong><small>Requires a protected database service</small></div><div><span class="status-dot"></span><strong>Device worker</strong><small>Requires private network access</small></div></div></section>
    </div>`;
}

const views = {
  overview: overviewView,
  attendance: attendanceView,
  employees: employeesView,
  leave: leaveView,
  reports: reportsView,
  devices: devicesView,
  payroll: payrollView,
  organization: organizationView,
  settings: settingsView,
};
