function overviewView() {
  const summary = attendanceSummary();
  const rate = summary.total ? Math.round((summary.present / summary.total) * 100) : 0;
  const pending = state.leaveRequests.filter((request) => request.status === "Pending");
  return `
    ${pageHeader(
      "Good morning, Nischhal",
      "Review today's attendance, approvals, and device health from one workspace.",
      `<button class="button button-secondary" data-action="manual-attendance">${icon("clock")} Add attendance</button>
       <button class="button button-primary" data-action="add-employee">${icon("plus")} Add employee</button>`,
    )}
    <section class="metric-grid" aria-label="Today summary">
      ${metricCard("users", "", "Active employees", activeEmployees().length, `${state.employees.length} total profiles`)}
      ${metricCard("check", "is-blue", "Present today", summary.present, `${rate}% attendance rate`)}
      ${metricCard("leave", "is-amber", "Pending approvals", pending.length, "Leave requests waiting")}
      ${metricCard("devices", offlineDeviceCount() ? "is-red" : "", "Device health", `${state.devices.length - offlineDeviceCount()}/${state.devices.length}`, offlineDeviceCount() ? "Attention required" : "All devices online")}
    </section>
    <div class="dashboard-grid">
      <section class="panel span-two">
        <div class="panel-header">
          <div><h3>Today's attendance</h3><p>Daily status across active employees</p></div>
          <button class="button button-ghost button-sm" data-route-button="attendance">View all ${icon("chevron")}</button>
        </div>
        <div class="attendance-summary">
          <div class="donut" style="--progress:${rate * 3.6}deg"><div><strong>${rate}%</strong><span>attendance</span></div></div>
          <div class="summary-list">
            <div><span><i class="dot success"></i>Present</span><strong>${summary.present}</strong></div>
            <div><span><i class="dot warning"></i>Late</span><strong>${summary.late}</strong></div>
            <div><span><i class="dot info"></i>Field duty</span><strong>${summary.field}</strong></div>
            <div><span><i class="dot danger"></i>Absent</span><strong>${summary.absent}</strong></div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Employee</th><th>Check in</th><th>Status</th><th>Worked</th></tr></thead>
            <tbody>${state.attendance.slice(0, 6).map((record, index) => attendanceRow(record, index, false)).join("")}</tbody>
          </table>
        </div>
      </section>
      <div class="dashboard-stack">
        <section class="panel">
          <div class="panel-header"><div><h3>Approval queue</h3><p>${pending.length} items need a decision</p></div><button class="button button-ghost button-sm" data-route-button="leave">View all</button></div>
          <div class="approval-list">${pending.length ? pending.slice(0, 3).map(approvalItem).join("") : emptyState("check", "Queue is clear", "No pending approvals right now.")}</div>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Quick actions</h3><p>Frequent administrative tasks</p></div></div>
          <div class="quick-actions">
            ${quickAction("clock", "Manual attendance", "manual-attendance")}
            ${quickAction("employees", "Add employee", "add-employee")}
            ${quickAction("leave", "Request leave", "request-leave")}
            ${quickAction("devices", "Connect device", "add-device")}
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Recent activity</h3><p>Latest workspace events</p></div></div>
          <div class="activity-list">${state.activity.slice(0, 4).map(activityItem).join("")}</div>
        </section>
      </div>
    </div>`;
}

function quickAction(iconName, label, action) {
  return `<button class="quick-action" data-action="${action}">${icon(iconName)}<span>${escapeHtml(label)}</span></button>`;
}

function activityItem(item) {
  return `<div class="activity-item"><span class="activity-icon">${icon(item.type in icons ? item.type : "pulse")}</span><div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.detail)}</small></div><time>${escapeHtml(item.time)}</time></div>`;
}

function approvalItem(request, index) {
  const employee = getEmployee(request.employeeId);
  return `<div class="approval-item">${personAvatar(employee, index)}<div><strong>${escapeHtml(employee?.name || "Unknown")}</strong><small>${escapeHtml(request.type)} · ${request.days} day${request.days === 1 ? "" : "s"}</small></div><button class="button button-secondary button-sm" data-action="review-leave" data-id="${request.id}">Review</button></div>`;
}

function attendanceRow(record, index, actions = true) {
  const employee = getEmployee(record.employeeId);
  if (!employee) return "";
  return `<tr data-search-row="${escapeHtml(`${employee.name} ${employee.attId} ${employee.department} ${record.status}`.toLowerCase())}">
    <td><div class="table-primary">${personAvatar(employee, index)}<div><strong>${escapeHtml(employee.name)}</strong><small>Att. ID ${escapeHtml(employee.attId)} · ${escapeHtml(employee.department)}</small></div></div></td>
    <td><strong>${escapeHtml(record.checkIn)}</strong><small>${escapeHtml(record.late)}</small></td>
    <td>${statusBadge(record.status)}</td><td>${escapeHtml(record.worked)}</td>
    ${actions ? `<td><div class="table-actions"><button class="table-action" data-action="view-attendance" data-id="${record.id}" aria-label="View record">${icon("eye")}</button><button class="table-action" data-action="edit-attendance" data-id="${record.id}" aria-label="Edit record">${icon("edit")}</button></div></td>` : ""}
  </tr>`;
}

function attendanceView() {
  const summary = attendanceSummary();
  const filtered = filteredAttendance();
  return `
    ${pageHeader("Attendance workspace", "Review daily records, raw punch evidence, and approved corrections.", `<button class="button button-secondary" data-action="export-attendance">${icon("download")} Export CSV</button><button class="button button-primary" data-action="manual-attendance">${icon("plus")} Add attendance</button>`)}
    <section class="metric-grid">
      ${metricCard("check", "", "Present", summary.present, "Includes late arrivals")}
      ${metricCard("clock", "is-amber", "Late", summary.late, "After assigned shift start")}
      ${metricCard("leave", "is-blue", "Field duty", summary.field, "Approved external assignment")}
      ${metricCard("alert", "is-red", "Absent", summary.absent, "No attendance evidence")}
    </section>
    <div class="tabs" role="tablist">
      ${[["daily", "Daily attendance"], ["logs", "Punch logs"], ["monthly", "Monthly summary"]].map(([id, label]) => `<button class="tab ${ui.attendanceTab === id ? "is-active" : ""}" data-attendance-tab="${id}" role="tab" aria-selected="${ui.attendanceTab === id}">${label}</button>`).join("")}
    </div>
    ${attendanceTabContent(filtered)}`;
}

function attendanceToolbar() {
  return `<div class="toolbar"><div class="toolbar-start"><label class="search-field">${icon("search")}<input type="search" data-page-search placeholder="Search employee or department" value="${escapeHtml(ui.search)}"></label><input class="filter-control" type="date" value="2026-08-03" aria-label="Attendance date"><select class="filter-control" data-filter="attendance-status">${["all", "Present", "Late", "Field duty", "Absent"].map((value) => `<option value="${value}" ${ui.attendanceStatus === value ? "selected" : ""}>${value === "all" ? "All statuses" : value}</option>`).join("")}</select></div></div>`;
}

function attendanceTabContent(filtered) {
  if (ui.attendanceTab === "logs") {
    const logs = state.attendance.flatMap((record) => {
      const employee = getEmployee(record.employeeId);
      if (!employee || record.checkIn === "—") return [];
      return [{ employee, time: record.checkIn, type: "Check in", device: record.source }, ...(record.checkOut !== "—" ? [{ employee, time: record.checkOut, type: "Check out", device: record.source }] : [])];
    });
    return `<section class="panel">${attendanceToolbar()}<div class="table-wrap"><table class="data-table"><thead><tr><th>Employee</th><th>Time</th><th>Punch type</th><th>Device</th><th>Evidence</th></tr></thead><tbody>${logs.map((log, index) => `<tr data-search-row="${escapeHtml(`${log.employee.name} ${log.device}`.toLowerCase())}"><td><div class="table-primary">${personAvatar(log.employee, index)}<div><strong>${escapeHtml(log.employee.name)}</strong><small>Att. ID ${escapeHtml(log.employee.attId)}</small></div></div></td><td><strong>${escapeHtml(log.time)}</strong></td><td>${statusBadge(log.type)}</td><td>${escapeHtml(log.device)}</td><td><span class="badge is-success">Raw punch</span></td></tr>`).join("")}</tbody></table></div></section>`;
  }
  if (ui.attendanceTab === "monthly") {
    return `<section class="panel"><div class="panel-header"><div><h3>Shrawan 2083 summary</h3><p>Generated from the shared attendance model</p></div><button class="button button-secondary button-sm" data-action="run-report" data-report="monthly-summary">${icon("file")} Generate</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Employee</th><th>Working days</th><th>Present</th><th>Absent</th><th>Leave</th><th>Late</th><th>Hours</th></tr></thead><tbody>${activeEmployees().map((employee, index) => `<tr><td><div class="table-primary">${personAvatar(employee, index)}<div><strong>${escapeHtml(employee.name)}</strong><small>${escapeHtml(employee.department)}</small></div></div></td><td>22</td><td>${18 + index % 4}</td><td>${index % 3}</td><td>${index % 2}</td><td>${index % 4}</td><td>${168 - index * 3}h</td></tr>`).join("")}</tbody></table></div></section>`;
  }
  return `<section class="panel">${attendanceToolbar()}<div class="table-wrap"><table class="data-table"><thead><tr><th>Employee</th><th>Check in</th><th>Status</th><th>Worked</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${filtered.length ? filtered.map((record, index) => attendanceRow(record, index)).join("") : emptyTableRow(5, "No attendance records match these filters.")}</tbody></table></div>${pagination(filtered.length, state.attendance.length)}</section>`;
}

function filteredAttendance() {
  return state.attendance.filter((record) => {
    const employee = getEmployee(record.employeeId);
    const text = `${employee?.name || ""} ${employee?.attId || ""} ${employee?.department || ""} ${record.status} ${record.source}`.toLowerCase();
    return (!ui.search || text.includes(ui.search)) && (ui.attendanceStatus === "all" || record.status === ui.attendanceStatus);
  });
}

function employeesView() {
  const departments = [...new Set(state.employees.map((employee) => employee.department))].sort();
  const filtered = state.employees.filter((employee) => {
    const text = `${employee.name} ${employee.email} ${employee.attId} ${employee.department} ${employee.section} ${employee.shift}`.toLowerCase();
    return (!ui.search || text.includes(ui.search)) && (ui.employeeDepartment === "all" || employee.department === ui.employeeDepartment);
  });
  return `
    ${pageHeader("Employee directory", "Manage identities, assignments, shifts, and device mappings.", `<button class="button button-secondary" data-action="export-employees">${icon("download")} Export CSV</button><button class="button button-primary" data-action="add-employee">${icon("plus")} Add employee</button>`)}
    <section class="metric-grid">
      ${metricCard("employees", "", "Total employees", state.employees.length, `${activeEmployees().length} active profiles`)}
      ${metricCard("building", "is-blue", "Departments", departments.length, "Across the organization")}
      ${metricCard("fingerprint", "is-amber", "Device mapped", state.employees.filter((employee) => employee.device).length, "Biometric identity links")}
      ${metricCard("clock", "is-red", "Shift patterns", new Set(state.employees.map((employee) => employee.shift)).size, "Effective assignments")}
    </section>
    <section class="panel"><div class="toolbar"><div class="toolbar-start"><label class="search-field">${icon("search")}<input type="search" data-page-search placeholder="Search name, ID, email, or team" value="${escapeHtml(ui.search)}"></label><select class="filter-control" data-filter="employee-department"><option value="all">All departments</option>${departments.map((department) => `<option value="${escapeHtml(department)}" ${ui.employeeDepartment === department ? "selected" : ""}>${escapeHtml(department)}</option>`).join("")}</select></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Employee</th><th>Att. ID</th><th>Organization</th><th>Shift</th><th>Device</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${filtered.length ? filtered.map(employeeRow).join("") : emptyTableRow(7, "No employee matches this search.")}</tbody></table></div>${pagination(filtered.length, state.employees.length)}</section>`;
}

function employeeRow(employee, index) {
  return `<tr data-search-row="${escapeHtml(`${employee.name} ${employee.attId} ${employee.department}`.toLowerCase())}"><td><div class="table-primary">${personAvatar(employee, index)}<div><strong>${escapeHtml(employee.name)}</strong><small>${escapeHtml(employee.email)}</small></div></div></td><td><strong>${escapeHtml(employee.attId)}</strong></td><td>${escapeHtml(employee.department)}<small>${escapeHtml(employee.section)}</small></td><td>${escapeHtml(employee.shift)}</td><td>${escapeHtml(employee.device)}</td><td>${statusBadge(employee.status)}</td><td><div class="table-actions"><button class="table-action" data-action="view-employee" data-id="${employee.id}" aria-label="View employee">${icon("eye")}</button><button class="table-action" data-action="edit-employee" data-id="${employee.id}" aria-label="Edit employee">${icon("edit")}</button></div></td></tr>`;
}

function leaveView() {
  const requests = state.leaveRequests.filter((request) => {
    const employee = getEmployee(request.employeeId);
    const text = `${employee?.name || ""} ${request.type} ${request.status}`.toLowerCase();
    return (!ui.search || text.includes(ui.search)) && (ui.leaveStatus === "all" || request.status === ui.leaveStatus);
  });
  const used = state.leaveRequests.filter((request) => request.status === "Approved").reduce((sum, request) => sum + Number(request.days), 0);
  return `
    ${pageHeader("Leave management", "Review requests, monitor balances, and record field duty.", `<button class="button button-secondary" data-action="add-field-duty">${icon("building")} Add field duty</button><button class="button button-primary" data-action="request-leave">${icon("plus")} New request</button>`)}
    <section class="metric-grid">
      ${metricCard("leave", "", "Pending requests", pendingLeaveCount(), "Need an approval decision")}
      ${metricCard("check", "is-blue", "Approved days", used, "Across visible requests")}
      ${metricCard("clock", "is-amber", "On leave today", 0, "No approved absence today")}
      ${metricCard("building", "is-red", "Field duty today", 1, "Approved kaaj assignment")}
    </section>
    <section class="panel"><div class="toolbar"><div class="toolbar-start"><label class="search-field">${icon("search")}<input type="search" data-page-search placeholder="Search employee or leave type" value="${escapeHtml(ui.search)}"></label><select class="filter-control" data-filter="leave-status">${["all", "Pending", "Approved", "Rejected"].map((status) => `<option value="${status}" ${ui.leaveStatus === status ? "selected" : ""}>${status === "all" ? "All requests" : status}</option>`).join("")}</select></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Employee</th><th>Leave type</th><th>Dates</th><th>Days</th><th>Reason</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${requests.length ? requests.map(leaveRow).join("") : emptyTableRow(7, "No leave request matches these filters.")}</tbody></table></div>${pagination(requests.length, state.leaveRequests.length)}</section>`;
}

function leaveRow(request, index) {
  const employee = getEmployee(request.employeeId);
  const actions = request.status === "Pending" ? `<button class="button button-secondary button-sm" data-action="review-leave" data-id="${request.id}">Review</button>` : `<button class="table-action" data-action="view-leave" data-id="${request.id}" aria-label="View leave request">${icon("eye")}</button>`;
  return `<tr data-search-row="${escapeHtml(`${employee?.name || ""} ${request.type} ${request.status}`.toLowerCase())}"><td><div class="table-primary">${personAvatar(employee, index)}<div><strong>${escapeHtml(employee?.name || "Unknown")}</strong><small>${escapeHtml(employee?.department || "")}</small></div></div></td><td>${escapeHtml(request.type)}</td><td><strong>${formatDate(request.from, { short: true })}</strong><small>${request.from === request.to ? "Single day" : `to ${formatDate(request.to, { short: true })}`}</small></td><td>${request.days}</td><td>${escapeHtml(request.reason)}</td><td>${statusBadge(request.status)}</td><td>${actions}</td></tr>`;
}
