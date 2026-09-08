(() => {
  "use strict";

  const config = window.__HAJIRIFLOW_CONFIG__ || {};
  if (config.environment !== "production" || config.operationalDataMode !== "api") return;

  document.body.classList.add("production-api-active");

  const apiBase = String(config.apiBasePath || "/api").replace(/\/$/, "");
  const state = {
    session: null,
    organizations: [],
    organizationId: "",
    view: "overview",
    employees: [],
    operators: [],
    attendanceRecords: [],
    corrections: [],
    payrollPeriods: [],
    payrollRuns: [],
    devices: [],
    pullsByDevice: new Map(),
    biometricDeletions: [],
    consentEmployeeId: "",
    consent: null,
    loading: false,
    error: "",
  };

  let root;
  let main;
  let nav;
  let organizationSelect;
  let liveRegion;

  function node(tag, options = {}, children = []) {
    const element = document.createElement(tag);
    if (options.className) element.className = options.className;
    if (options.text !== undefined) element.textContent = String(options.text);
    if (options.type) element.type = options.type;
    if (options.name) element.name = options.name;
    if (options.value !== undefined) element.value = String(options.value);
    if (options.placeholder) element.placeholder = options.placeholder;
    if (options.id) element.id = options.id;
    if (options.role) element.setAttribute("role", options.role);
    if (options.ariaLabel) element.setAttribute("aria-label", options.ariaLabel);
    if (options.ariaCurrent) element.setAttribute("aria-current", options.ariaCurrent);
    if (options.disabled) element.disabled = true;
    if (options.tabIndex !== undefined) element.tabIndex = options.tabIndex;
    if (options.dataset) {
      Object.entries(options.dataset).forEach(([key, value]) => {
        element.dataset[key] = String(value);
      });
    }
    for (const child of Array.isArray(children) ? children : [children]) {
      if (child instanceof Node) element.append(child);
      else if (child !== null && child !== undefined) element.append(document.createTextNode(String(child)));
    }
    return element;
  }

  function button(label, action, options = {}) {
    return node("button", {
      className: `production-api-button${options.primary ? " is-primary" : ""}${options.danger ? " is-danger" : ""}`,
      text: label,
      type: "button",
      disabled: options.disabled,
      dataset: { action, ...(options.dataset || {}) },
    });
  }

  function statusPill(value) {
    const normalized = String(value || "unknown").toLowerCase();
    let tone = "is-info";
    if (["active", "approved", "posted", "completed", "succeeded", "granted", "present", "ready"].some((item) => normalized.includes(item))) tone = "is-success";
    if (["pending", "draft", "locked", "reversal_pending", "partial", "running", "declined"].some((item) => normalized.includes(item))) tone = "is-warning";
    if (["failed", "disabled", "rejected", "revoked", "reversed", "absent", "error"].some((item) => normalized.includes(item))) tone = "is-danger";
    return node("span", { className: `production-api-status ${tone}`, text: value || "unknown" });
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat("en-NP", {
      timeZone: "Asia/Kathmandu",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function shortId(value) {
    const text = String(value || "");
    return text.length > 12 ? `${text.slice(0, 8)}…${text.slice(-4)}` : text || "—";
  }

  function employeeName(id) {
    const item = state.employees.find((employee) => employee.id === id);
    return item ? `${item.display_name} (${item.employee_code})` : shortId(id);
  }

  function operatorName(id) {
    if (!id) return "—";
    const item = state.operators.find((operator) => operator.id === id);
    return item ? item.display_name : `User ${shortId(id)}`;
  }

  function can(permission, organizationId = state.organizationId) {
    const grants = state.session?.permissions || [];
    return grants.some((grant) => {
      if (![permission, "system.full_access"].includes(grant.code)) return false;
      if (grant.scope_type === "global") return true;
      return grant.scope_type === "organization" && grant.scope_id === organizationId;
    });
  }

  async function request(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    const headers = new Headers({ Accept: "application/json" });
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      const csrf = state.session?.csrf_token;
      if (!csrf) throw new Error("Your secure session is missing a CSRF token. Sign in again.");
      headers.set("X-CSRF-Token", csrf);
    }
    const response = await fetch(`${apiBase}${path}`, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (response.status === 204) return null;
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const detail = payload?.detail;
      throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
    }
    return payload;
  }

  function announce(message) {
    if (liveRegion) liveRegion.textContent = message;
  }

  function empty(message) {
    return node("div", { className: "production-api-empty", text: message });
  }

  function errorBox(message) {
    return node("div", { className: "production-api-error", role: "alert", text: message });
  }

  function card(title, description, body, options = {}) {
    const heading = node("h2", { text: title });
    const copy = description ? node("p", { text: description }) : null;
    const header = node("div", { className: "production-api-card-header" }, [
      node("div", {}, [heading, copy]),
      options.action || null,
    ].filter(Boolean));
    return node("section", {
      className: `production-api-card${options.full ? " is-full" : ""}${options.third ? " is-third" : ""}`,
    }, [header, body]);
  }

  function metricCard(label, value, detail) {
    return node("section", { className: "production-api-card is-third" }, [
      node("div", { className: "production-api-metric" }, [
        node("span", { className: "production-api-muted", text: label }),
        node("strong", { text: value }),
        node("small", { className: "production-api-muted", text: detail }),
      ]),
    ]);
  }

  function detailList(entries) {
    const list = node("dl", { className: "production-api-detail-list" });
    entries.forEach(([label, value]) => {
      list.append(node("div", {}, [node("dt", { text: label }), node("dd", { text: value ?? "—" })]));
    });
    return list;
  }

  function currentOrganization() {
    return state.organizations.find((item) => item.id === state.organizationId) || null;
  }

  function pendingCorrections() {
    return state.corrections.filter((item) => item.status === "pending")
      .sort((a, b) => new Date(a.requested_at) - new Date(b.requested_at));
  }

  function pendingPayrollRuns() {
    return state.payrollRuns.filter((item) => ["pending_approval", "reversal_pending"].includes(item.status));
  }

  function problemDevices() {
    return state.devices.filter((device) => {
      const latest = state.pullsByDevice.get(device.id)?.[0];
      return device.status !== "active" || latest?.status === "failed";
    });
  }

  function renderNavigation() {
    if (!nav) return;
    nav.replaceChildren();
    const definitions = [
      ["overview", "Overview", pendingCorrections().length + pendingPayrollRuns().length + state.biometricDeletions.length + problemDevices().length, true],
      ["attendance", "Attendance", pendingCorrections().length, can("attendance.read")],
      ["payroll", "Payroll", pendingPayrollRuns().length, can("payroll.read")],
      ["devices", "Devices", problemDevices().length, can("device.read")],
      ["biometrics", "Biometric privacy", state.biometricDeletions.length, can("biometric.consent.read") || can("biometric.deletion.manage")],
    ];
    definitions.filter(([, , , visible]) => visible).forEach(([key, label, count]) => {
      const children = [node("span", { text: label })];
      if (count) children.push(node("span", { className: "production-api-nav-count", text: count }));
      nav.append(node("button", {
        type: "button",
        ariaCurrent: state.view === key ? "page" : null,
        dataset: { view: key },
      }, children));
    });
  }

  function heading(title, description, actions = []) {
    const titleNode = node("h1", { text: title, tabIndex: -1 });
    const wrap = node("header", { className: "production-api-heading" }, [
      node("div", {}, [
        node("p", { className: "production-api-kicker", text: "Authoritative API data" }),
        titleNode,
        node("p", { text: description }),
      ]),
      node("div", { className: "production-api-actions" }, actions),
    ]);
    requestAnimationFrame(() => titleNode.focus({ preventScroll: true }));
    return wrap;
  }

  function queueList(items, formatter) {
    if (!items.length) return empty("Nothing is waiting in this queue.");
    const list = node("ul", { className: "production-api-list" });
    items.forEach((item) => list.append(formatter(item)));
    return list;
  }

  function renderOverview() {
    const org = currentOrganization();
    const corrections = pendingCorrections();
    const payroll = pendingPayrollRuns();
    const devices = problemDevices();
    const deletions = state.biometricDeletions;
    const content = node("div", {}, [
      heading(
        org ? `${org.display_name} operations` : "Operations",
        "Prioritized approval and integrity queues from the production FastAPI/PostgreSQL application. Generated browser records are not used here.",
        [button("Refresh", "refresh")],
      ),
      node("div", { className: "production-api-grid" }, [
        metricCard("Attendance corrections", corrections.length, "Oldest pending requests first"),
        metricCard("Payroll approvals", payroll.length, "Pending approval or reversal review"),
        metricCard("Device attention", devices.length, "Disabled devices or latest failed pull"),
        metricCard("Biometric deletions", deletions.length, "Pending device-side deletion work"),
        card("Manager approval queue", "Attendance requests requiring a checker decision.", queueList(corrections.slice(0, 6), (item) => {
          const record = state.attendanceRecords.find((entry) => entry.id === item.attendance_record_id);
          return node("li", { className: "production-api-list-item" }, [
            node("div", { className: "production-api-list-row" }, [
              node("strong", { text: record ? employeeName(record.employee_id) : `Record ${shortId(item.attendance_record_id)}` }),
              statusPill(item.status),
            ]),
            node("small", { text: `${formatDateTime(item.requested_at)} · Requested by ${operatorName(item.requested_by)}` }),
            node("span", { text: item.reason }),
          ]);
        })),
        card("Payroll control queue", "Runs waiting for independent approval or reversal review.", queueList(payroll.slice(0, 6), (run) => node("li", { className: "production-api-list-item" }, [
          node("div", { className: "production-api-list-row" }, [
            node("strong", { text: `${periodLabel(run.period_id)} · Run ${run.sequence}` }),
            statusPill(run.status),
          ]),
          node("small", { text: `Created by ${operatorName(run.created_by)} · ${formatDateTime(run.created_at)}` }),
          run.approved_by ? node("span", { text: `Approved by ${operatorName(run.approved_by)} at ${formatDateTime(run.approved_at)}` }) : node("span", { text: "No approval recorded yet." }),
        ]))),
        card("Device attention", "Safe operational status and pull failures; no credential ciphertext or biometric material.", queueList(devices.slice(0, 6), renderDeviceListItem)),
        card("Biometric deletion queue", "Device-side deletion requests use hashed completion receipts only.", queueList(deletions.slice(0, 6), renderDeletionListItem)),
      ]),
    ]);
    main.replaceChildren(content);
  }

  function periodLabel(id) {
    const period = state.payrollPeriods.find((item) => item.id === id);
    return period?.label || `Period ${shortId(id)}`;
  }

  function recordComparison(correction) {
    const record = state.attendanceRecords.find((item) => item.id === correction.attendance_record_id);
    const current = node("div", {}, [node("strong", { text: "Current record" }), detailList([
      ["Employee", record ? employeeName(record.employee_id) : "Unknown record"],
      ["Work date", record?.work_date || "—"],
      ["Status", record?.status || "—"],
      ["Check in", formatDateTime(record?.check_in_at)],
      ["Check out", formatDateTime(record?.check_out_at)],
      ["Revision", record?.source_revision ?? "—"],
    ])]);
    const proposed = node("div", {}, [node("strong", { text: "Requested correction" }), detailList([
      ["Status", correction.proposed_status ?? "No change"],
      ["Check in", correction.proposed_check_in_at ? formatDateTime(correction.proposed_check_in_at) : "No change"],
      ["Check out", correction.proposed_check_out_at ? formatDateTime(correction.proposed_check_out_at) : "No change"],
      ["Requested by", operatorName(correction.requested_by)],
      ["Requested", formatDateTime(correction.requested_at)],
      ["Reason", correction.reason],
    ])]);
    return node("div", { className: "production-api-comparison" }, [current, proposed]);
  }

  function correctionActions(correction) {
    if (correction.status !== "pending" || !can("attendance.correction.approve")) {
      return node("div", {}, [
        correction.decided_by ? node("p", { text: `Decision by ${operatorName(correction.decided_by)} · ${formatDateTime(correction.decided_at)}` }) : null,
        correction.decision_reason ? node("p", { className: "production-api-muted", text: correction.decision_reason }) : null,
      ].filter(Boolean));
    }
    const textarea = node("textarea", { name: "reason", placeholder: "Decision reason (minimum 5 characters)" });
    textarea.setAttribute("aria-label", "Correction decision reason");
    const form = node("div", { className: "production-api-form" }, [
      node("label", {}, [node("span", { text: "Decision reason" }), textarea]),
      node("div", { className: "production-api-actions" }, [
        button("Approve correction", "correction-decision", { primary: true, dataset: { id: correction.id, approve: "true" } }),
        button("Reject correction", "correction-decision", { danger: true, dataset: { id: correction.id, approve: "false" } }),
        button("View immutable history", "attendance-history", { dataset: { recordId: correction.attendance_record_id } }),
      ]),
    ]);
    form.dataset.correctionForm = correction.id;
    return form;
  }

  function renderAttendance() {
    const all = [...state.corrections].sort((a, b) => new Date(b.requested_at) - new Date(a.requested_at));
    const container = node("div", {}, [
      heading("Attendance corrections", "Review what changed, why it was requested, who requested it, who decided it, and the immutable record history.", [button("Refresh", "refresh")]),
      node("div", { className: "production-api-grid" }),
    ]);
    const grid = container.lastChild;
    if (!all.length) grid.append(card("Corrections", "No correction requests are recorded for this organization.", empty("No attendance corrections found."), { full: true }));
    all.forEach((correction) => {
      const body = node("div", {}, [
        node("div", { className: "production-api-list-row" }, [
          node("strong", { text: `Correction ${shortId(correction.id)}` }),
          statusPill(correction.status),
        ]),
        recordComparison(correction),
        correctionActions(correction),
        node("div", { dataset: { historyTarget: correction.attendance_record_id } }),
      ]);
      grid.append(card(
        state.attendanceRecords.find((item) => item.id === correction.attendance_record_id)
          ? employeeName(state.attendanceRecords.find((item) => item.id === correction.attendance_record_id).employee_id)
          : "Attendance record",
        correction.status === "pending" ? "Checker decision required." : "Decision recorded.",
        body,
        { full: true },
      ));
    });
    main.replaceChildren(container);
  }

  function payrollStatusMeaning(status) {
    return ({
      draft: "Maker is still preparing the run.",
      pending_approval: "Run is frozen for an independent checker decision.",
      approved: "Checker approved; posting is the next irreversible lifecycle step.",
      posted: "Posted run is final; corrections require an additive reversal workflow.",
      reversal_pending: "A reversal was requested and requires a different checker.",
      reversed: "Original run remains preserved and is offset by its reversal run.",
    })[status] || "Server-controlled payroll lifecycle state.";
  }

  function payrollRunActions(run) {
    const actions = [];
    if (run.status === "draft" && can("payroll.manage")) actions.push(button("Submit for approval", "payroll-transition", { dataset: { id: run.id, transition: "submit" } }));
    if (run.status === "pending_approval" && can("payroll.approve")) actions.push(button("Approve run", "payroll-transition", { primary: true, dataset: { id: run.id, transition: "approve" } }));
    if (run.status === "approved" && can("payroll.approve")) actions.push(button("Post run", "payroll-transition", { primary: true, dataset: { id: run.id, transition: "post" } }));
    actions.push(button("View payroll history", "payroll-history", { dataset: { id: run.id } }));
    return node("div", { className: "production-api-actions" }, actions);
  }

  function renderPayroll() {
    const container = node("div", {}, [
      heading("Payroll lifecycle", "Statuses and approval identities come directly from the controlled payroll service. Attendance-only roles cannot enter this view.", [button("Refresh", "refresh")]),
      node("div", { className: "production-api-grid" }),
    ]);
    const grid = container.lastChild;
    grid.append(card("Payroll periods", "Open → locked → closed. Locking freezes the attendance calculation version used by payroll.", payrollPeriodTable(), { full: true }));
    const runs = [...state.payrollRuns].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (!runs.length) grid.append(card("Payroll runs", "No payroll runs exist yet.", empty("No payroll runs found."), { full: true }));
    runs.forEach((run) => {
      const body = node("div", {}, [
        node("div", { className: "production-api-list-row" }, [statusPill(run.status), node("span", { className: "production-api-muted", text: payrollStatusMeaning(run.status) })]),
        detailList([
          ["Period", periodLabel(run.period_id)],
          ["Run", String(run.sequence)],
          ["Calculation version", run.calculation_version],
          ["Created by", operatorName(run.created_by)],
          ["Created", formatDateTime(run.created_at)],
          ["Approved by", operatorName(run.approved_by)],
          ["Approved", formatDateTime(run.approved_at)],
          ["Posted by", operatorName(run.posted_by)],
          ["Posted", formatDateTime(run.posted_at)],
          ["Reversal requested by", operatorName(run.reversal_requested_by)],
          ["Reversal reason", run.reversal_reason || "—"],
          ["Reversed by", operatorName(run.reversed_by)],
        ]),
        payrollRunActions(run),
        node("div", { dataset: { payrollHistoryTarget: run.id } }),
      ]);
      grid.append(card(`${periodLabel(run.period_id)} · Run ${run.sequence}`, "Maker/checker and reversal evidence", body, { full: true }));
    });
    main.replaceChildren(container);
  }

  function payrollPeriodTable() {
    if (!state.payrollPeriods.length) return empty("No payroll periods found.");
    const region = node("div", { className: "production-api-table-region", role: "region", ariaLabel: "Payroll periods" });
    region.tabIndex = 0;
    const table = node("table", { className: "production-api-table" });
    const head = node("thead", {}, [node("tr", {}, ["Period", "Dates", "Status", "Attendance version", "Locked by", "Closed by"].map((label) => {
      const th = node("th", { text: label }); th.scope = "col"; return th;
    }))]);
    const body = node("tbody");
    state.payrollPeriods.forEach((period) => {
      body.append(node("tr", {}, [
        node("td", { text: `${period.label} (${period.code})` }),
        node("td", { text: `${period.starts_on} – ${period.ends_on}` }),
        node("td", {}, [statusPill(period.status)]),
        node("td", { text: period.attendance_calculation_version }),
        node("td", { text: period.locked_by ? `${operatorName(period.locked_by)} · ${formatDateTime(period.locked_at)}` : "—" }),
        node("td", { text: period.closed_by ? `${operatorName(period.closed_by)} · ${formatDateTime(period.closed_at)}` : "—" }),
      ]));
    });
    table.append(head, body); region.append(table); return region;
  }

  function latestPull(deviceId) {
    return state.pullsByDevice.get(deviceId)?.[0] || null;
  }

  function renderDeviceListItem(device) {
    const pull = latestPull(device.id);
    const subtitle = pull
      ? `Latest pull ${pull.status} · ${formatDateTime(pull.started_at)} · ${pull.attempt_count} attempt(s)`
      : "No pull history recorded.";
    return node("li", { className: "production-api-list-item" }, [
      node("div", { className: "production-api-list-row" }, [node("strong", { text: `${device.name} · ${device.code}` }), statusPill(device.status)]),
      node("small", { text: `${device.vendor} · ${device.adapter_key} · ${subtitle}` }),
      pull?.error_code ? node("span", { text: `Safe error: ${pull.error_code}${pull.error_detail ? ` — ${pull.error_detail}` : ""}` }) : null,
    ].filter(Boolean));
  }

  function renderDevices() {
    const container = node("div", {}, [
      heading("Device operations", "Connectivity and pull evidence from the server. Credential ciphertext, templates, biometric images, and raw scans are never rendered.", [button("Refresh", "refresh")]),
      node("div", { className: "production-api-grid" }),
    ]);
    const grid = container.lastChild;
    if (!state.devices.length) grid.append(card("Devices", "No registered attendance devices.", empty("No devices found."), { full: true }));
    state.devices.forEach((device) => {
      const pulls = state.pullsByDevice.get(device.id) || [];
      const list = node("ul", { className: "production-api-list" });
      pulls.slice(0, 8).forEach((pull) => list.append(node("li", { className: "production-api-list-item" }, [
        node("div", { className: "production-api-list-row" }, [statusPill(pull.status), node("span", { text: formatDateTime(pull.started_at) })]),
        node("small", { text: `${pull.attempt_count} attempt(s) · ${pull.ingested_count} ingested · ${pull.duplicate_count} duplicate` }),
        pull.error_code ? node("span", { text: `Safe error: ${pull.error_code}${pull.error_detail ? ` — ${pull.error_detail}` : ""}` }) : null,
      ].filter(Boolean))));
      grid.append(card(`${device.name} · ${device.code}`, `${device.vendor} / ${device.adapter_key}`, node("div", {}, [
        detailList([
          ["Status", device.status],
          ["Endpoint", device.endpoint_uri],
          ["Pull interval", `${device.pull_interval_seconds} seconds`],
          ["Last seen", formatDateTime(device.last_seen_at)],
          ["Capabilities", Object.keys(device.capabilities || {}).filter((key) => device.capabilities[key]).join(", ") || "—"],
        ]),
        node("h3", { text: "Recent pulls" }),
        pulls.length ? list : empty("No device pull sessions recorded."),
      ]), { full: true }));
    });
    main.replaceChildren(container);
  }

  function renderDeletionListItem(item) {
    return node("li", { className: "production-api-list-item" }, [
      node("div", { className: "production-api-list-row" }, [node("strong", { text: `Deletion ${shortId(item.id)}` }), statusPill(item.status)]),
      node("small", { text: `Device user ${shortId(item.device_user_id)} · Requested by ${operatorName(item.requested_by)} · ${formatDateTime(item.requested_at)}` }),
      item.failure_code ? node("span", { text: `Safe failure code: ${item.failure_code}` }) : null,
    ].filter(Boolean));
  }

  function consentPanel() {
    if (!can("biometric.consent.read")) return empty("Your role cannot read biometric consent governance.");
    if (!state.employees.length) return empty("No employees are available for consent review.");
    const select = node("select", { name: "employee" });
    state.employees.forEach((employee) => {
      const option = node("option", { value: employee.id, text: `${employee.display_name} (${employee.employee_code})` });
      if (employee.id === state.consentEmployeeId) option.selected = true;
      select.append(option);
    });
    select.dataset.consentEmployee = "";
    const form = node("div", { className: "production-api-form" }, [
      node("label", {}, [node("span", { text: "Employee" }), select]),
      state.consent
        ? node("div", { className: "production-api-note" }, [
            node("div", { className: "production-api-list-row" }, [node("strong", { text: "Latest consent decision" }), statusPill(state.consent.decision)]),
            detailList([
              ["Policy version", state.consent.policy_version],
              ["Purpose", state.consent.purpose],
              ["Recorded by", operatorName(state.consent.recorded_by)],
              ["Recorded", formatDateTime(state.consent.recorded_at)],
            ]),
          ])
        : node("div", { className: "production-api-note", text: "No biometric consent decision is recorded for this employee." }),
    ]);
    if (can("biometric.consent.manage")) {
      const policy = node("input", { name: "policy", placeholder: "Policy version, e.g. biometric-v1" });
      const purpose = node("textarea", { name: "purpose", placeholder: "Specific attendance-verification purpose" });
      policy.dataset.consentPolicy = "";
      purpose.dataset.consentPurpose = "";
      form.append(
        node("label", {}, [node("span", { text: "Policy version" }), policy]),
        node("label", {}, [node("span", { text: "Purpose" }), purpose]),
        node("div", { className: "production-api-actions" }, [
          button("Record consent", "consent-decision", { primary: true, dataset: { decision: "granted" } }),
          button("Record decline", "consent-decision", { dataset: { decision: "declined" } }),
          button("Revoke consent", "consent-decision", { danger: true, dataset: { decision: "revoked" } }),
        ]),
      );
    }
    return form;
  }

  function deletionQueue() {
    if (!state.biometricDeletions.length) return empty("No biometric deletion requests are pending.");
    const list = node("ul", { className: "production-api-list" });
    state.biometricDeletions.forEach((item) => {
      const children = [renderDeletionListItem(item)];
      if (can("biometric.deletion.manage") && item.status === "pending") {
        const receipt = node("input", { placeholder: "64-character SHA-256 receipt hash" });
        receipt.dataset.deletionReceipt = item.id;
        const failure = node("input", { placeholder: "Safe failure code" });
        failure.dataset.deletionFailure = item.id;
        children.push(node("div", { className: "production-api-actions" }, [
          receipt,
          button("Mark complete", "deletion-complete", { primary: true, dataset: { id: item.id } }),
          failure,
          button("Mark failed", "deletion-fail", { danger: true, dataset: { id: item.id } }),
        ]));
      }
      list.append(node("li", {}, children));
    });
    return list;
  }

  function renderBiometrics() {
    const container = node("div", {}, [
      heading("Biometric privacy", "Consent, revocation, and device-side deletion governance only. HajiriFlow never ingests biometric templates, images, or scans.", [button("Refresh", "refresh")]),
      node("div", { className: "production-api-grid" }, [
        card("Employee consent", "Review the latest append-only decision and record a new grant, decline, or revocation when authorized.", consentPanel(), { full: true }),
        card("Pending deletion queue", "Completion stores only a SHA-256 receipt hash; raw provider receipts are not accepted.", deletionQueue(), { full: true }),
      ]),
    ]);
    main.replaceChildren(container);
  }

  function renderCurrentView() {
    renderNavigation();
    if (!main) return;
    if (state.loading) {
      main.replaceChildren(node("div", { className: "production-api-loading", role: "status", text: "Loading authoritative operational data…" }));
      return;
    }
    if (state.error) {
      main.replaceChildren(errorBox(state.error), button("Retry", "refresh", { primary: true }));
      return;
    }
    if (!state.organizationId) {
      main.replaceChildren(empty("No organization is available to this signed-in identity."));
      return;
    }
    if (state.view === "attendance" && can("attendance.read")) return renderAttendance();
    if (state.view === "payroll" && can("payroll.read")) return renderPayroll();
    if (state.view === "devices" && can("device.read")) return renderDevices();
    if (state.view === "biometrics" && (can("biometric.consent.read") || can("biometric.deletion.manage"))) return renderBiometrics();
    state.view = "overview";
    return renderOverview();
  }

  async function loadConsent() {
    state.consent = null;
    if (!state.consentEmployeeId || !can("biometric.consent.read")) return;
    state.consent = await request(`/v1/organizations/${state.organizationId}/biometric/consent/employees/${state.consentEmployeeId}`);
  }

  async function loadOrganizationData(options = {}) {
    if (!state.organizationId) return;
    state.loading = true;
    state.error = "";
    renderCurrentView();
    const base = `/v1/organizations/${state.organizationId}`;
    try {
      const jobs = [
        request(`${base}/operators`).then((value) => { state.operators = value; }),
      ];
      if (can("employee.read")) jobs.push(request(`${base}/employees?limit=200`).then((value) => { state.employees = value; }));
      else state.employees = [];
      if (can("attendance.read")) {
        jobs.push(request(`${base}/attendance/records?limit=500`).then((value) => { state.attendanceRecords = value; }));
        jobs.push(request(`${base}/attendance/corrections`).then((value) => { state.corrections = value; }));
      } else {
        state.attendanceRecords = [];
        state.corrections = [];
      }
      if (can("payroll.read")) {
        jobs.push(request(`${base}/payroll/periods`).then((value) => { state.payrollPeriods = value; }));
        jobs.push(request(`${base}/payroll/runs`).then((value) => { state.payrollRuns = value; }));
      } else {
        state.payrollPeriods = [];
        state.payrollRuns = [];
      }
      if (can("device.read")) jobs.push(request(`${base}/devices`).then((value) => { state.devices = value; }));
      else state.devices = [];
      if (can("biometric.deletion.manage")) jobs.push(request(`${base}/biometric/deletions/pending`).then((value) => { state.biometricDeletions = value; }));
      else state.biometricDeletions = [];

      await Promise.all(jobs);
      state.pullsByDevice = new Map();
      if (can("device.read") && state.devices.length) {
        await Promise.all(state.devices.map(async (device) => {
          const pulls = await request(`${base}/devices/${device.id}/pulls`);
          state.pullsByDevice.set(device.id, pulls);
        }));
      }
      if (!state.consentEmployeeId || !state.employees.some((item) => item.id === state.consentEmployeeId)) {
        state.consentEmployeeId = state.employees[0]?.id || "";
      }
      if (state.view === "biometrics" || options.loadConsent) await loadConsent();
    } catch (error) {
      state.error = error instanceof Error ? error.message : "Unable to load production data.";
    } finally {
      state.loading = false;
      renderCurrentView();
      announce(state.error || "Authoritative operational data refreshed.");
    }
  }

  async function initialize(session) {
    state.session = session;
    state.loading = true;
    renderCurrentView();
    try {
      state.organizations = await request("/v1/organizations");
      if (!state.organizationId || !state.organizations.some((item) => item.id === state.organizationId)) {
        state.organizationId = state.organizations[0]?.id || "";
      }
      syncOrganizationOptions();
      await loadOrganizationData();
    } catch (error) {
      state.loading = false;
      state.error = error instanceof Error ? error.message : "Unable to initialize production operations.";
      renderCurrentView();
    }
  }

  function syncOrganizationOptions() {
    if (!organizationSelect) return;
    organizationSelect.replaceChildren();
    state.organizations.forEach((item) => {
      const option = node("option", { value: item.id, text: item.display_name });
      if (item.id === state.organizationId) option.selected = true;
      organizationSelect.append(option);
    });
    organizationSelect.disabled = state.organizations.length < 2;
  }

  async function decideCorrection(target) {
    const id = target.dataset.id;
    const form = document.querySelector(`[data-correction-form="${CSS.escape(id)}"]`);
    const reason = form?.querySelector("textarea[name='reason']")?.value.trim() || "";
    if (reason.length < 5) {
      announce("Add a decision reason of at least five characters.");
      form?.querySelector("textarea")?.focus();
      return;
    }
    target.disabled = true;
    try {
      await request(`/v1/organizations/${state.organizationId}/attendance/corrections/${id}/decision`, {
        method: "POST",
        body: { approve: target.dataset.approve === "true", reason },
      });
      announce("Attendance correction decision recorded.");
      await loadOrganizationData();
    } catch (error) {
      announce(error instanceof Error ? error.message : "Correction decision failed.");
      target.disabled = false;
    }
  }

  async function loadAttendanceHistory(target) {
    const recordId = target.dataset.recordId;
    const destination = document.querySelector(`[data-history-target="${CSS.escape(recordId)}"]`);
    if (!destination) return;
    target.disabled = true;
    try {
      const history = await request(`/v1/organizations/${state.organizationId}/attendance/records/${recordId}/history`);
      const list = node("ul", { className: "production-api-list" });
      history.forEach((item) => list.append(node("li", { className: "production-api-list-item" }, [
        node("div", { className: "production-api-list-row" }, [node("strong", { text: item.event_type }), node("span", { text: formatDateTime(item.occurred_at) })]),
        node("small", { text: `Actor: ${item.actor_user_id ? operatorName(item.actor_user_id) : "System"}` }),
        item.reason ? node("span", { text: item.reason }) : null,
      ].filter(Boolean))));
      destination.replaceChildren(node("h3", { text: "Immutable attendance history" }), list);
    } catch (error) {
      destination.replaceChildren(errorBox(error instanceof Error ? error.message : "History could not be loaded."));
    } finally {
      target.disabled = false;
    }
  }

  async function payrollTransition(target) {
    const transition = target.dataset.transition;
    const id = target.dataset.id;
    if (!new Set(["submit", "approve", "post"]).has(transition)) return;
    target.disabled = true;
    try {
      await request(`/v1/organizations/${state.organizationId}/payroll/runs/${id}/${transition}`, { method: "POST" });
      announce(`Payroll run ${transition} completed.`);
      await loadOrganizationData();
    } catch (error) {
      announce(error instanceof Error ? error.message : "Payroll transition failed.");
      target.disabled = false;
    }
  }

  async function loadPayrollHistory(target) {
    const id = target.dataset.id;
    const destination = document.querySelector(`[data-payroll-history-target="${CSS.escape(id)}"]`);
    if (!destination) return;
    target.disabled = true;
    try {
      const history = await request(`/v1/organizations/${state.organizationId}/payroll/runs/${id}/history`);
      const list = node("ul", { className: "production-api-list" });
      history.forEach((item) => list.append(node("li", { className: "production-api-list-item" }, [
        node("div", { className: "production-api-list-row" }, [node("strong", { text: item.action }), node("span", { text: formatDateTime(item.occurred_at) })]),
        node("small", { text: `Actor: ${operatorName(item.actor_user_id)}` }),
        item.reason ? node("span", { text: item.reason }) : null,
      ].filter(Boolean))));
      destination.replaceChildren(node("h3", { text: "Immutable payroll history" }), list);
    } catch (error) {
      destination.replaceChildren(errorBox(error instanceof Error ? error.message : "History could not be loaded."));
    } finally {
      target.disabled = false;
    }
  }

  async function saveConsent(target) {
    const policy = document.querySelector("[data-consent-policy]")?.value.trim() || "";
    const purpose = document.querySelector("[data-consent-purpose]")?.value.trim() || "";
    if (!state.consentEmployeeId || !policy || !purpose) {
      announce("Choose an employee and enter both policy version and purpose.");
      return;
    }
    target.disabled = true;
    try {
      await request(`/v1/organizations/${state.organizationId}/biometric/consent/employees/${state.consentEmployeeId}`, {
        method: "POST",
        body: { decision: target.dataset.decision, policy_version: policy, purpose },
      });
      await loadConsent();
      renderBiometrics();
      announce(`Biometric consent decision recorded as ${target.dataset.decision}.`);
    } catch (error) {
      announce(error instanceof Error ? error.message : "Consent update failed.");
      target.disabled = false;
    }
  }

  async function completeDeletion(target) {
    const id = target.dataset.id;
    const input = document.querySelector(`[data-deletion-receipt="${CSS.escape(id)}"]`);
    const hash = input?.value.trim() || "";
    if (!/^[a-fA-F0-9]{64}$/.test(hash)) {
      announce("Completion requires a 64-character SHA-256 receipt hash.");
      input?.focus();
      return;
    }
    target.disabled = true;
    try {
      await request(`/v1/organizations/${state.organizationId}/biometric/deletions/${id}/complete`, { method: "POST", body: { receipt_sha256: hash.toLowerCase() } });
      await loadOrganizationData({ loadConsent: true });
      announce("Biometric deletion marked complete using the hashed receipt only.");
    } catch (error) {
      announce(error instanceof Error ? error.message : "Deletion completion failed.");
      target.disabled = false;
    }
  }

  async function failDeletion(target) {
    const id = target.dataset.id;
    const input = document.querySelector(`[data-deletion-failure="${CSS.escape(id)}"]`);
    const code = input?.value.trim() || "";
    if (!code) {
      announce("Enter a safe failure code without sensitive payload details.");
      input?.focus();
      return;
    }
    target.disabled = true;
    try {
      await request(`/v1/organizations/${state.organizationId}/biometric/deletions/${id}/fail`, { method: "POST", body: { failure_code: code } });
      await loadOrganizationData({ loadConsent: true });
      announce("Biometric deletion failure recorded with a safe code.");
    } catch (error) {
      announce(error instanceof Error ? error.message : "Deletion failure update failed.");
      target.disabled = false;
    }
  }

  function buildShell() {
    root = node("div", { className: "production-api-console", id: "production-api-console" });
    const brand = node("div", { className: "production-api-brand" }, [
      node("span", { className: "production-api-brand-mark", text: "HF", ariaLabel: "HajiriFlow" }),
      node("span", {}, [node("strong", { text: "HajiriFlow" }), node("small", { text: "Production operations" })]),
    ]);
    organizationSelect = node("select", { ariaLabel: "Organization" });
    const organizationControl = node("div", { className: "production-api-org" }, [
      node("label", {}, [node("span", { text: "Organization" }), organizationSelect]),
    ]);
    const userCopy = node("div", { className: "production-api-user-copy" }, [
      node("strong", { text: "Signed-in user", dataset: { apiUserName: "" } }),
      node("small", { text: "Server-authorized session" }),
    ]);
    const user = node("div", { className: "production-api-user" }, [
      userCopy,
      node("button", { className: "production-api-button", text: "Sign out", type: "button", dataset: { identityLogout: "" } }),
    ]);
    const header = node("header", { className: "production-api-header" }, [brand, organizationControl, user]);
    nav = node("nav", { className: "production-api-nav", ariaLabel: "Production operations" });
    main = node("main", { className: "production-api-main", id: "production-api-main", tabIndex: -1 });
    liveRegion = node("div", { className: "production-api-live", role: "status" });
    liveRegion.setAttribute("aria-live", "polite");
    root.append(header, node("div", { className: "production-api-layout" }, [nav, main]), liveRegion);
    document.getElementById("app-shell")?.append(root);
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest?.("[data-action]");
    if (!target || !root?.contains(target)) return;
    const action = target.dataset.action;
    if (action === "refresh") void loadOrganizationData({ loadConsent: state.view === "biometrics" });
    if (action === "correction-decision") void decideCorrection(target);
    if (action === "attendance-history") void loadAttendanceHistory(target);
    if (action === "payroll-transition") void payrollTransition(target);
    if (action === "payroll-history") void loadPayrollHistory(target);
    if (action === "consent-decision") void saveConsent(target);
    if (action === "deletion-complete") void completeDeletion(target);
    if (action === "deletion-fail") void failDeletion(target);
  });

  document.addEventListener("click", (event) => {
    const target = event.target.closest?.("[data-view]");
    if (!target || !nav?.contains(target)) return;
    state.view = target.dataset.view;
    if (state.view === "biometrics" && state.consentEmployeeId && can("biometric.consent.read")) {
      state.loading = true;
      renderCurrentView();
      void loadConsent().then(() => {
        state.loading = false;
        renderCurrentView();
      }).catch((error) => {
        state.loading = false;
        state.error = error instanceof Error ? error.message : "Consent data could not be loaded.";
        renderCurrentView();
      });
      return;
    }
    renderCurrentView();
  });

  document.addEventListener("change", (event) => {
    if (event.target === organizationSelect) {
      state.organizationId = organizationSelect.value;
      state.view = "overview";
      void loadOrganizationData();
      return;
    }
    if (event.target?.matches?.("[data-consent-employee]")) {
      state.consentEmployeeId = event.target.value;
      state.loading = true;
      renderCurrentView();
      void loadConsent().then(() => {
        state.loading = false;
        renderCurrentView();
      }).catch((error) => {
        state.loading = false;
        state.error = error instanceof Error ? error.message : "Consent data could not be loaded.";
        renderCurrentView();
      });
    }
  });

  buildShell();
  renderCurrentView();

  window.addEventListener("hajiriflow:identity-ready", (event) => {
    const session = event.detail?.session || window.HFIdentity?.session;
    const userName = root.querySelector("[data-api-user-name]");
    if (userName) userName.textContent = session?.user?.display_name || session?.user?.username || "Authenticated user";
    if (!session) {
      state.error = "A verified session is required for production operations.";
      renderCurrentView();
      return;
    }
    void initialize(session);
  });
})();
