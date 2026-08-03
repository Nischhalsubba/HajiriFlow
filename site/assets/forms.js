function employeeOptions(selected = "") {
  return activeEmployees().map((employee) => `<option value="${employee.id}" ${Number(selected) === employee.id ? "selected" : ""}>${escapeHtml(employee.attId)} · ${escapeHtml(employee.name)}</option>`).join("");
}

function employeeForm(employee = {}) {
  return `<form class="form-stack" data-form="employee" data-id="${employee.id || ""}">
    <div class="form-grid two-columns">
      <label class="field"><span>Full name</span><input name="name" required value="${escapeHtml(employee.name || "")}" placeholder="Employee name"></label>
      <label class="field"><span>Attendance ID</span><input name="attId" required inputmode="numeric" value="${escapeHtml(employee.attId || "")}" placeholder="e.g. 109"></label>
      <label class="field"><span>Email</span><input name="email" type="email" required value="${escapeHtml(employee.email || "")}" placeholder="name@company.com"></label>
      <label class="field"><span>Status</span><select name="status"><option ${employee.status !== "Inactive" ? "selected" : ""}>Active</option><option ${employee.status === "Inactive" ? "selected" : ""}>Inactive</option></select></label>
      <label class="field"><span>Department</span><input name="department" required value="${escapeHtml(employee.department || "")}" placeholder="Department"></label>
      <label class="field"><span>Section</span><input name="section" required value="${escapeHtml(employee.section || "")}" placeholder="Section or unit"></label>
      <label class="field"><span>Shift</span><select name="shift">${["General 09:00–17:00", "Early 08:00–16:00", "Field Flexible"].map((shift) => `<option ${employee.shift === shift ? "selected" : ""}>${shift}</option>`).join("")}</select></label>
      <label class="field"><span>Device mapping</span><select name="device">${state.devices.map((device) => `<option ${employee.device === device.name ? "selected" : ""}>${escapeHtml(device.name)}</option>`).join("")}</select></label>
    </div>
    <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">${employee.id ? "Save changes" : "Add employee"}</button></div>
  </form>`;
}

function openEmployeeForm(id = null) {
  const employee = id ? getEmployee(id) : null;
  openModal({
    title: employee ? "Edit employee" : "Add employee",
    description: employee ? "Update profile and effective assignment details." : "Create a new workforce identity for this demo workspace.",
    body: employeeForm(employee || {}),
    size: "lg",
  });
}

function viewEmployee(id) {
  const employee = getEmployee(id);
  if (!employee) return;
  const attendance = state.attendance.find((record) => record.employeeId === employee.id);
  const leave = state.leaveRequests.filter((request) => request.employeeId === employee.id);
  openModal({
    title: employee.name,
    description: `Attendance ID ${employee.attId} · ${employee.status}`,
    size: "lg",
    body: `<div class="profile-hero">${personAvatar(employee, 1)}<div><h3>${escapeHtml(employee.name)}</h3><p>${escapeHtml(employee.email)}</p>${statusBadge(employee.status)}</div></div>
      <dl class="detail-grid"><div><dt>Department</dt><dd>${escapeHtml(employee.department)}</dd></div><div><dt>Section</dt><dd>${escapeHtml(employee.section)}</dd></div><div><dt>Shift</dt><dd>${escapeHtml(employee.shift)}</dd></div><div><dt>Device</dt><dd>${escapeHtml(employee.device)}</dd></div><div><dt>Joined</dt><dd>${formatDate(employee.joined, { short: true })}</dd></div><div><dt>Today's status</dt><dd>${attendance ? statusBadge(attendance.status) : "—"}</dd></div></dl>
      <div class="modal-section"><h3>Recent leave</h3>${leave.length ? `<div class="compact-list">${leave.slice(0, 3).map((request) => `<div><span>${escapeHtml(request.type)}</span><strong>${request.days} day${request.days === 1 ? "" : "s"}</strong>${statusBadge(request.status)}</div>`).join("")}</div>` : `<p class="muted">No leave history in demo data.</p>`}</div>`,
    footer: `<button class="button button-secondary" data-close-modal>Close</button><button class="button button-primary" data-action="edit-employee" data-id="${employee.id}">${icon("edit")} Edit employee</button>`,
  });
}

function attendanceForm(record = {}) {
  return `<form class="form-stack" data-form="attendance" data-id="${record.id || ""}">
    <div class="notice-card">${icon("alert")}<p>This creates or updates an <strong>approved correction</strong>. Raw biometric punch evidence remains unchanged.</p></div>
    <div class="form-grid two-columns">
      <label class="field"><span>Employee</span><select name="employeeId" required>${employeeOptions(record.employeeId)}</select></label>
      <label class="field"><span>Status</span><select name="status">${["Present", "Late", "Field duty", "Absent"].map((status) => `<option ${record.status === status ? "selected" : ""}>${status}</option>`).join("")}</select></label>
      <label class="field"><span>Check in</span><input name="checkIn" type="time" value="${record.checkIn && record.checkIn !== "—" ? record.checkIn : "09:00"}"></label>
      <label class="field"><span>Check out</span><input name="checkOut" type="time" value="${record.checkOut && record.checkOut !== "—" ? record.checkOut : "17:00"}"></label>
      <label class="field full-width"><span>Reason and approval note</span><textarea name="reason" required placeholder="Explain why this correction is required">${record.source?.includes("Manual") ? "Approved attendance correction" : ""}</textarea></label>
    </div>
    <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">Save correction</button></div>
  </form>`;
}

function openAttendanceForm(id = null) {
  const record = id ? state.attendance.find((item) => item.id === Number(id)) : null;
  openModal({ title: record ? "Edit attendance correction" : "Add manual attendance", description: "Record an attributable adjustment without editing raw evidence.", body: attendanceForm(record || {}), size: "lg" });
}

function viewAttendance(id) {
  const record = state.attendance.find((item) => item.id === Number(id));
  if (!record) return;
  const employee = getEmployee(record.employeeId);
  openModal({
    title: "Attendance record",
    description: `${employee?.name || "Unknown"} · 3 August 2026`,
    body: `<div class="evidence-timeline"><div class="evidence-item"><span>${icon("clock")}</span><div><strong>Check in · ${escapeHtml(record.checkIn)}</strong><p>${escapeHtml(record.source)} · Raw or approved source</p></div></div><div class="evidence-item"><span>${icon("clock")}</span><div><strong>Check out · ${escapeHtml(record.checkOut)}</strong><p>${escapeHtml(record.source)} · Raw or approved source</p></div></div></div><dl class="detail-grid"><div><dt>Status</dt><dd>${statusBadge(record.status)}</dd></div><div><dt>Worked</dt><dd>${escapeHtml(record.worked)}</dd></div><div><dt>Arrival</dt><dd>${escapeHtml(record.late)}</dd></div><div><dt>Source</dt><dd>${escapeHtml(record.source)}</dd></div></dl>`,
    footer: `<button class="button button-secondary" data-close-modal>Close</button><button class="button button-primary" data-action="edit-attendance" data-id="${record.id}">${icon("edit")} Add correction</button>`,
  });
}

function leaveForm(fieldDuty = false) {
  return `<form class="form-stack" data-form="leave" data-field-duty="${fieldDuty}">
    <div class="form-grid two-columns">
      <label class="field"><span>Employee</span><select name="employeeId" required>${employeeOptions()}</select></label>
      <label class="field"><span>${fieldDuty ? "Duty type" : "Leave type"}</span><select name="type">${(fieldDuty ? ["Kaaj — Paid", "Kaaj — Unpaid"] : ["Home leave", "Sick leave", "Casual leave", "Maternity leave", "Paternity leave", "Unpaid leave"]).map((type) => `<option>${type}</option>`).join("")}</select></label>
      <label class="field"><span>From</span><input name="from" type="date" required value="2026-08-04"></label>
      <label class="field"><span>To</span><input name="to" type="date" required value="2026-08-04"></label>
      <label class="field full-width"><span>${fieldDuty ? "Purpose and destination" : "Reason"}</span><textarea name="reason" required placeholder="Provide enough detail for the approver"></textarea></label>
    </div>
    <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">Submit request</button></div>
  </form>`;
}

function openLeaveForm(fieldDuty = false) {
  openModal({ title: fieldDuty ? "Add field duty" : "New leave request", description: fieldDuty ? "Record paid or unpaid external duty." : "Submit a request into the approval workflow.", body: leaveForm(fieldDuty), size: "lg" });
}

function reviewLeave(id) {
  const request = state.leaveRequests.find((item) => item.id === Number(id));
  if (!request) return;
  const employee = getEmployee(request.employeeId);
  openModal({
    title: "Review leave request",
    description: `${employee?.name || "Unknown"} · ${request.days} day${request.days === 1 ? "" : "s"}`,
    body: `<div class="profile-hero">${personAvatar(employee, 2)}<div><h3>${escapeHtml(employee?.name || "Unknown")}</h3><p>${escapeHtml(employee?.department || "")}</p>${statusBadge(request.status)}</div></div><dl class="detail-grid"><div><dt>Leave type</dt><dd>${escapeHtml(request.type)}</dd></div><div><dt>Dates</dt><dd>${formatDate(request.from, { short: true })}${request.from !== request.to ? ` – ${formatDate(request.to, { short: true })}` : ""}</dd></div><div><dt>Working days</dt><dd>${request.days}</dd></div><div><dt>Available balance</dt><dd>9 days</dd></div></dl><div class="reason-box"><span>Employee reason</span><p>${escapeHtml(request.reason)}</p></div>`,
    footer: request.status === "Pending" ? `<button class="button button-danger" data-action="reject-leave" data-id="${request.id}">Reject</button><button class="button button-primary" data-action="approve-leave" data-id="${request.id}">${icon("check")} Approve</button>` : `<button class="button button-secondary" data-close-modal>Close</button>`,
  });
}

function deviceForm(device = {}) {
  return `<form class="form-stack" data-form="device" data-id="${device.id || ""}"><div class="form-grid two-columns"><label class="field"><span>Device name</span><input name="name" required value="${escapeHtml(device.name || "")}" placeholder="e.g. Main Gate"></label><label class="field"><span>IP address</span><input name="ip" required value="${escapeHtml(device.ip || "")}" placeholder="192.168.1.201"></label><label class="field"><span>Model</span><input name="model" required value="${escapeHtml(device.model || "ZKTeco")}"></label><label class="field"><span>Location</span><input name="location" required value="${escapeHtml(device.location || "")}" placeholder="Building or floor"></label><label class="field"><span>Protocol</span><select name="protocol"><option ${device.protocol !== "UDP" ? "selected" : ""}>TCP</option><option ${device.protocol === "UDP" ? "selected" : ""}>UDP</option></select></label><label class="field"><span>Connection state</span><select name="status"><option ${device.status !== "Attention" ? "selected" : ""}>Online</option><option ${device.status === "Attention" ? "selected" : ""}>Attention</option></select></label></div><div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">${device.id ? "Save device" : "Add device"}</button></div></form>`;
}

function openDeviceForm(id = null) {
  const device = id ? state.devices.find((item) => item.id === Number(id)) : null;
  openModal({ title: device ? "Edit device" : "Add biometric device", description: "Demo configuration only. The protected worker will perform real network operations.", body: deviceForm(device || {}), size: "lg" });
}

function runReport(id) {
  const report = reportCatalog.find((item) => item.id === id) || reportCatalog[0];
  openModal({ title: report.title, description: "Choose the reporting period and output format.", body: `<form class="form-stack" data-form="report" data-report="${report.id}"><div class="form-grid two-columns"><label class="field"><span>From date</span><input name="from" type="date" value="2026-08-01"></label><label class="field"><span>To date</span><input name="to" type="date" value="2026-08-03"></label><label class="field"><span>Department</span><select name="department"><option>All departments</option>${[...new Set(state.employees.map((employee) => employee.department))].map((department) => `<option>${escapeHtml(department)}</option>`).join("")}</select></label><label class="field"><span>Format</span><select name="format"><option>CSV</option><option>PDF preview</option><option>Print view</option></select></label></div><div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">${icon("file")} Generate report</button></div></form>` });
}

function newPayrollModal() {
  openModal({ title: "Prepare payroll", description: "A posted payroll must be based on locked attendance and versioned policy.", body: `<div class="checklist"><div class="checklist-item is-complete">${icon("check")}<div><strong>Employee compensation assigned</strong><small>Demo profiles are ready</small></div></div><div class="checklist-item is-warning">${icon("alert")}<div><strong>Attendance period not locked</strong><small>Review attendance before generation</small></div></div><div class="checklist-item">${icon("lock")}<div><strong>Tax policy confirmation</strong><small>Required in the backend payroll workflow</small></div></div></div>`, footer: `<button class="button button-secondary" data-close-modal>Cancel</button><button class="button button-primary" data-action="create-payroll-draft">Create draft only</button>` });
}

function openCommandMenu() {
  commandMenu.hidden = false;
  document.body.classList.add("command-open");
  commandSearch.value = "";
  renderCommandResults();
  requestAnimationFrame(() => commandSearch.focus());
}

function closeCommandMenu() {
  commandMenu.hidden = true;
  document.body.classList.remove("command-open");
}

function renderCommandResults() {
  const query = commandSearch.value.trim().toLowerCase();
  const routes = Object.entries(routeMeta).map(([route, meta]) => ({ route, label: meta.title, detail: meta.description, icon: route in icons ? route : "overview" }));
  const actions = [{ action: "add-employee", label: "Add employee", detail: "Create a workforce profile", icon: "plus" }, { action: "manual-attendance", label: "Add attendance", detail: "Record an approved correction", icon: "clock" }, { action: "request-leave", label: "New leave request", detail: "Open the leave form", icon: "leave" }, { action: "add-device", label: "Add device", detail: "Configure a biometric endpoint", icon: "devices" }];
  const results = [...routes, ...actions].filter((item) => `${item.label} ${item.detail}`.toLowerCase().includes(query));
  commandResults.innerHTML = results.length ? results.map((item) => `<button class="command-result" ${item.route ? `data-route-button="${item.route}"` : `data-action="${item.action}"`}><span>${icon(item.icon)}</span><div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.detail)}</small></div><kbd>↵</kbd></button>`).join("") : emptyState("search", "No command found", "Try a page name or common action.");
}
