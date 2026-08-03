function addActivity(type, title, detail) {
  state.activity.unshift({ id: Date.now(), type, title, detail, time: new Intl.DateTimeFormat("en-NP", { timeZone: "Asia/Kathmandu", hour: "2-digit", minute: "2-digit" }).format(new Date()) });
  state.activity = state.activity.slice(0, 12);
}

function exportEmployees() {
  const rows = [["Attendance ID", "Name", "Email", "Department", "Section", "Shift", "Device", "Status"], ...state.employees.map((employee) => [employee.attId, employee.name, employee.email, employee.department, employee.section, employee.shift, employee.device, employee.status])];
  downloadFile("hajiriflow-employees.csv", toCsv(rows), "text/csv");
  toast("Employee CSV downloaded.");
}

function exportAttendance() {
  const rows = [["Attendance ID", "Employee", "Department", "Check in", "Check out", "Worked", "Status", "Source"], ...state.attendance.map((record) => { const employee = getEmployee(record.employeeId); return [employee?.attId, employee?.name, employee?.department, record.checkIn, record.checkOut, record.worked, record.status, record.source]; })];
  downloadFile("hajiriflow-attendance.csv", toCsv(rows), "text/csv");
  toast("Attendance CSV downloaded.");
}

function handleAction(action, element) {
  const id = element.dataset.id;
  switch (action) {
    case "add-employee": openEmployeeForm(); break;
    case "edit-employee": closeModal(); setTimeout(() => openEmployeeForm(id), 0); break;
    case "view-employee": viewEmployee(id); break;
    case "employee-more": viewEmployee(id); break;
    case "manual-attendance": openAttendanceForm(); break;
    case "edit-attendance": closeModal(); setTimeout(() => openAttendanceForm(id), 0); break;
    case "view-attendance": viewAttendance(id); break;
    case "request-leave": openLeaveForm(false); break;
    case "add-field-duty": openLeaveForm(true); break;
    case "review-leave": case "view-leave": reviewLeave(id); break;
    case "approve-leave": updateLeaveStatus(id, "Approved"); break;
    case "reject-leave": updateLeaveStatus(id, "Rejected"); break;
    case "add-device": openDeviceForm(); break;
    case "edit-device": openDeviceForm(id); break;
    case "test-device": simulateDeviceAction(id, "Connection test passed", false); break;
    case "sync-device": simulateDeviceAction(id, "Device synchronization completed", true); break;
    case "pull-all": pullAllDevices(); break;
    case "export-employees": exportEmployees(); break;
    case "export-attendance": exportAttendance(); break;
    case "export-payroll": exportPayroll(); break;
    case "run-report": runReport(element.dataset.report); break;
    case "new-payroll": newPayrollModal(); break;
    case "create-payroll-draft": createPayrollDraft(); break;
    case "review-attendance": location.hash = "attendance"; closeModal(); break;
    case "notifications": openNotifications(); break;
    case "profile-menu": case "workspace-menu": openProfileMenu(); break;
    case "dismiss-demo-notice": dismissDemoNotice(); break;
    case "export-demo": downloadFile("hajiriflow-demo-state.json", JSON.stringify(state, null, 2), "application/json"); toast("Demo state downloaded."); break;
    case "reset-demo": resetDemo(); break;
    case "report-history": toast("No generated report history yet.", "info"); break;
    case "device-history": toast("Pull-session history will be connected to the worker API.", "info"); break;
    case "attendance-filters": toast("Status, date, and search filters are available above the table.", "info"); break;
    case "payroll-settings": toast("Payroll policy configuration is part of the payroll milestone.", "info"); break;
    case "add-department": promptDepartment(); break;
    case "edit-department": toast("Department editing will use effective-dated assignments in the backend.", "info"); break;
    case "add-shift": promptShift(); break;
    case "edit-shift": toast("Shift editing preview opened in the future backend workflow.", "info"); break;
    default: toast("This action is represented in the prototype and awaits its backend workflow.", "info");
  }
}

function updateLeaveStatus(id, status) {
  const request = state.leaveRequests.find((item) => item.id === Number(id));
  if (!request) return;
  request.status = status;
  const employee = getEmployee(request.employeeId);
  addActivity("leave", `Leave request ${status.toLowerCase()}`, `${employee?.name || "Employee"} · ${request.type}`);
  saveState();
  closeModal();
  render();
  toast(`Leave request ${status.toLowerCase()}.`, status === "Approved" ? "success" : "danger");
}

function simulateDeviceAction(id, message, sync) {
  const device = state.devices.find((item) => item.id === Number(id));
  if (!device) return;
  const original = event?.target?.closest("button");
  if (original) original.disabled = true;
  toast(`${device.name}: operation started.`, "info");
  setTimeout(() => {
    device.status = "Online";
    if (sync) device.lastSync = "just now";
    addActivity("devices", message, device.name);
    saveState();
    render();
    toast(`${device.name}: ${message.toLowerCase()}.`);
  }, 650);
}

function pullAllDevices() {
  toast("Pulling all reachable devices…", "info");
  setTimeout(() => {
    state.devices.forEach((device) => { device.lastSync = "just now"; if (device.status !== "Online") device.status = "Online"; });
    addActivity("attendance", "Attendance pull completed", `${state.devices.length} devices · demo run`);
    saveState();
    render();
    toast("Device pull completed in the prototype.");
  }, 850);
}

function createPayrollDraft() {
  const draft = state.payroll[0];
  draft.employees = activeEmployees().length;
  draft.gross = draft.employees * 58000;
  draft.deductions = Math.round(draft.gross * 0.12);
  draft.net = draft.gross - draft.deductions;
  addActivity("payroll", "Payroll draft prepared", draft.period);
  saveState();
  closeModal();
  render();
  toast("Payroll draft calculated from demo values.");
}

function exportPayroll() {
  const rows = [["Period", "Employees", "Gross", "Deductions", "Net", "Attendance", "Status"], ...state.payroll.map((period) => [period.period, period.employees, period.gross, period.deductions, period.net, period.attendance, period.status])];
  downloadFile("hajiriflow-payroll.csv", toCsv(rows), "text/csv");
  toast("Payroll CSV downloaded.");
}

function dismissDemoNotice() {
  demoNotice.hidden = true;
  localStorage.setItem(NOTICE_KEY, "1");
}

function resetDemo() {
  if (!window.confirm("Reset all browser-local demo changes?")) return;
  state = structuredClone(seedState);
  saveState();
  render();
  toast("Demo workspace reset.");
}

function promptDepartment() {
  openModal({ title: "Add department", description: "Create a presentation-only department in this prototype.", body: `<form class="form-stack" data-form="department"><label class="field"><span>Department name</span><input name="name" required placeholder="e.g. Quality Assurance"></label><label class="field"><span>Parent directorate</span><input name="parent" value="Corporate Services"></label><div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">Add department</button></div></form>` });
}

function promptShift() {
  openModal({ title: "Add shift", description: "Define a work pattern for future employee assignments.", body: `<form class="form-stack" data-form="shift"><label class="field"><span>Shift name</span><input name="name" required placeholder="e.g. Evening"></label><div class="form-grid two-columns"><label class="field"><span>Start</span><input name="start" type="time" value="09:00"></label><label class="field"><span>End</span><input name="end" type="time" value="17:00"></label></div><div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancel</button><button class="button button-primary" type="submit">Add shift</button></div></form>` });
}

function minutesBetween(start, end) {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  let minutes = eh * 60 + em - (sh * 60 + sm);
  if (minutes < 0) minutes += 24 * 60;
  return minutes;
}

function workedLabel(start, end) {
  if (!start || !end) return "—";
  const minutes = minutesBetween(start, end);
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

function calculateDays(from, to) {
  const start = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return 1;
  return Math.round((end - start) / 86400000) + 1;
}

function handleFormSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const type = form.dataset.form;
  if (type === "employee") {
    const id = Number(form.dataset.id || 0);
    const duplicate = state.employees.some((employee) => employee.attId === data.attId && employee.id !== id);
    if (duplicate) return toast("Attendance ID must be unique.", "danger");
    const existing = id ? getEmployee(id) : null;
    const employee = { id: existing?.id || Math.max(0, ...state.employees.map((item) => item.id)) + 1, attId: data.attId.trim(), name: data.name.trim(), email: data.email.trim(), department: data.department.trim(), section: data.section.trim(), shift: data.shift, status: data.status, device: data.device, joined: existing?.joined || "2026-08-03" };
    if (existing) Object.assign(existing, employee); else state.employees.unshift(employee);
    addActivity("employees", existing ? "Employee profile updated" : "Employee added", `${employee.name} · ${employee.department}`);
    saveState(); closeModal(); render(); toast(existing ? "Employee updated." : "Employee added.");
    return;
  }
  if (type === "attendance") {
    const id = Number(form.dataset.id || 0);
    const existing = id ? state.attendance.find((item) => item.id === id) : null;
    const record = { id: existing?.id || Math.max(0, ...state.attendance.map((item) => item.id)) + 1, employeeId: Number(data.employeeId), checkIn: ["Absent", "Field duty"].includes(data.status) ? "—" : data.checkIn, checkOut: ["Absent", "Field duty"].includes(data.status) ? "—" : data.checkOut, worked: ["Absent", "Field duty"].includes(data.status) ? "—" : workedLabel(data.checkIn, data.checkOut), status: data.status, source: `Manual correction · ${data.reason.trim()}`, late: data.status === "Late" ? "Approved late arrival" : "On time" };
    if (existing) Object.assign(existing, record); else state.attendance.unshift(record);
    addActivity("attendance", "Attendance correction saved", getEmployee(record.employeeId)?.name || "Employee");
    saveState(); closeModal(); render(); toast("Attendance correction saved.");
    return;
  }
  if (type === "leave") {
    const request = { id: Math.max(0, ...state.leaveRequests.map((item) => item.id)) + 1, employeeId: Number(data.employeeId), type: data.type, from: data.from, to: data.to, days: calculateDays(data.from, data.to), reason: data.reason.trim(), status: form.dataset.fieldDuty === "true" ? "Approved" : "Pending" };
    state.leaveRequests.unshift(request);
    addActivity("leave", form.dataset.fieldDuty === "true" ? "Field duty recorded" : "Leave request submitted", `${getEmployee(request.employeeId)?.name || "Employee"} · ${request.type}`);
    saveState(); closeModal(); render(); toast(form.dataset.fieldDuty === "true" ? "Field duty recorded." : "Leave request submitted.");
    return;
  }
  if (type === "device") {
    const id = Number(form.dataset.id || 0);
    const existing = id ? state.devices.find((item) => item.id === id) : null;
    const device = { id: existing?.id || Math.max(0, ...state.devices.map((item) => item.id)) + 1, name: data.name.trim(), ip: data.ip.trim(), model: data.model.trim(), users: existing?.users || 0, status: data.status, lastSync: existing?.lastSync || "Never", location: data.location.trim(), protocol: data.protocol };
    if (existing) Object.assign(existing, device); else state.devices.push(device);
    addActivity("devices", existing ? "Device configuration updated" : "Device registered", device.name);
    saveState(); closeModal(); render(); toast(existing ? "Device updated." : "Device added.");
    return;
  }
  if (type === "report") {
    const report = reportCatalog.find((item) => item.id === form.dataset.report) || reportCatalog[0];
    const rows = [["Report", "From", "To", "Department"], [report.title, data.from, data.to, data.department], [], ["Employee", "Department", "Status"], ...activeEmployees().map((employee) => [employee.name, employee.department, state.attendance.find((record) => record.employeeId === employee.id)?.status || "No record"])];
    downloadFile(`hajiriflow-${report.id}.csv`, toCsv(rows), "text/csv"); closeModal(); toast(`${report.title} generated.`);
    return;
  }
  if (type === "settings") {
    state.settings = { ...state.settings, company: data.company.trim(), timezone: data.timezone, weekOff: data.weekOff, dateFormat: data.dateFormat };
    saveState(); toast("Workspace settings saved.");
    return;
  }
  if (type === "department" || type === "shift") {
    closeModal(); toast(`${type === "department" ? "Department" : "Shift"} added to the prototype.`);
  }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("button, a");
  if (!target) return;
  if (target.matches("[data-open-sidebar]")) return openSidebar();
  if (target.matches("[data-close-sidebar]")) return closeSidebar();
  if (target.matches("[data-close-modal]")) return closeModal();
  if (target.dataset.routeButton) { location.hash = target.dataset.routeButton; closeModal(); closeCommandMenu(); return; }
  if (target.dataset.action) { handleAction(target.dataset.action, target); closeCommandMenu(); }
  if (target.dataset.attendanceTab) { ui.attendanceTab = target.dataset.attendanceTab; render(); }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  handleFormSubmit(form);
});

document.addEventListener("input", (event) => {
  if (event.target.matches("[data-page-search]")) { globalSearch.value = event.target.value; ui.search = event.target.value.trim().toLowerCase(); render(); document.querySelector("[data-page-search]")?.focus(); }
});

document.addEventListener("change", (event) => {
  if (event.target.dataset.filter === "attendance-status") { ui.attendanceStatus = event.target.value; render(); }
  if (event.target.dataset.filter === "employee-department") { ui.employeeDepartment = event.target.value; render(); }
  if (event.target.dataset.filter === "leave-status") { ui.leaveStatus = event.target.value; render(); }
});

globalSearch.addEventListener("input", () => render());
commandSearch.addEventListener("input", renderCommandResults);
window.addEventListener("hashchange", () => { globalSearch.value = ""; ui.search = ""; render(); workspace.focus({ preventScroll: true }); });
window.addEventListener("resize", () => { if (window.innerWidth > 960) closeSidebar(); });

document.addEventListener("keydown", (event) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  if ((event.key === "/" && !typing) || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")) { event.preventDefault(); openCommandMenu(); }
  if (event.key === "Escape") { if (!commandMenu.hidden) closeCommandMenu(); else if (!modalLayer.hidden) closeModal(); else closeSidebar(); }
});

if (localStorage.getItem(NOTICE_KEY) === "1") demoNotice.hidden = true;
document.querySelector("[data-open-sidebar]")?.setAttribute("aria-expanded", "false");
updateNepalClock();
setInterval(updateNepalClock, 30000);
render();
