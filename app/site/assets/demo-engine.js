(() => {
  "use strict";

  const STORAGE_KEY = "hajiriflow_dynamic_demo_v3";
  const VERSION = 3;
  const TIMEZONE = "Asia/Kathmandu";

  const vocabulary = {
    firstNames: [
      "Aarav", "Aarya", "Aayush", "Anisha", "Anup", "Asmita", "Bikash", "Bina",
      "Deepak", "Diya", "Elina", "Gaurav", "Ishan", "Kabir", "Karuna", "Kiran",
      "Manish", "Maya", "Nabin", "Nima", "Niruta", "Pooja", "Prakash", "Priya",
      "Rachana", "Rajan", "Ritesh", "Rojina", "Roshan", "Sabina", "Samir", "Sanjay",
      "Sarita", "Saugat", "Sita", "Suman", "Sushma", "Ujjwal", "Yubraj", "Zoya",
    ],
    lastNames: [
      "Adhikari", "Bhandari", "Gurung", "Karki", "Khadka", "Lama", "Maharjan",
      "Poudel", "Rai", "Shakya", "Sharma", "Sherpa", "Shrestha", "Subba", "Tamang",
      "Thapa", "Yadav", "Basnet", "Koirala", "Joshi",
    ],
    departmentNames: [
      "Administration", "Finance", "Human Resources", "Information Technology",
      "Operations", "Procurement", "Programs", "Customer Success", "Field Services",
    ],
    sections: [
      "People Operations", "Accounts", "Infrastructure", "Product", "Service Desk",
      "Planning", "Compliance", "East Region", "West Region", "Reception", "Logistics",
      "Quality Assurance", "Partnerships", "Communications",
    ],
    roles: [
      "Officer", "Senior Officer", "Coordinator", "Analyst", "Assistant", "Specialist",
      "Supervisor", "Manager", "Engineer", "Administrator", "Associate",
    ],
    deviceModels: [
      "SpeedFace V5L", "K40 Pro", "MB460", "iClock 680", "SilkBio 101TC", "UFace 302",
    ],
    locations: [
      "Main Gate", "Reception", "Office Floor", "East Wing", "Service Entrance", "Annex",
    ],
    leaveTypes: ["Home leave", "Sick leave", "Casual leave", "Unpaid leave", "Study leave"],
    activityVerbs: ["approved", "updated", "synchronized", "reviewed", "generated", "corrected"],
  };

  function hashSeed(input) {
    let h = 1779033703 ^ input.length;
    for (let index = 0; index < input.length; index += 1) {
      h = Math.imul(h ^ input.charCodeAt(index), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return () => {
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      return (h ^= h >>> 16) >>> 0;
    };
  }

  function createRandom(seed) {
    const seedFactory = hashSeed(seed);
    let value = seedFactory();
    return () => {
      value += 0x6d2b79f5;
      let t = value;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function newId(prefix = "id") {
    const token = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
    return `${prefix}_${token}`;
  }

  function pick(random, items) {
    return items[Math.floor(random() * items.length)];
  }

  function integer(random, minimum, maximum) {
    return Math.floor(random() * (maximum - minimum + 1)) + minimum;
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function isoDate(date) {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: TIMEZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(date);
  }

  function localDateFromIso(value) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(Date.UTC(year, month - 1, day, 12));
  }

  function addDays(value, offset) {
    const date = typeof value === "string" ? localDateFromIso(value) : new Date(value);
    date.setUTCDate(date.getUTCDate() + offset);
    return isoDate(date);
  }

  function formatMonthKey(date) {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: TIMEZONE,
      year: "numeric",
      month: "2-digit",
    }).format(date);
  }

  function currentMonthKey() {
    return formatMonthKey(new Date());
  }

  function monthLabel(key) {
    const [year, month] = key.split("-").map(Number);
    return new Intl.DateTimeFormat("en-NP", {
      timeZone: TIMEZONE,
      year: "numeric",
      month: "long",
    }).format(new Date(Date.UTC(year, month - 1, 15, 12)));
  }

  function previousMonthKey(offset) {
    const now = new Date();
    const date = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - offset, 15, 12));
    return formatMonthKey(date);
  }

  function minutesToClock(minutes) {
    const normalized = ((minutes % 1440) + 1440) % 1440;
    const hours = Math.floor(normalized / 60);
    const mins = normalized % 60;
    return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
  }

  function clockToMinutes(value) {
    if (!value || value === "—") return null;
    const [hours, minutes] = value.split(":").map(Number);
    return hours * 60 + minutes;
  }

  function isWeeklyOff(dateString) {
    return localDateFromIso(dateString).getUTCDay() === 6;
  }

  function workingDatesForMonth(monthKey) {
    const [year, month] = monthKey.split("-").map(Number);
    const lastDay = new Date(Date.UTC(year, month, 0, 12)).getUTCDate();
    return Array.from({ length: lastDay }, (_, index) => {
      const date = new Date(Date.UTC(year, month - 1, index + 1, 12));
      return isoDate(date);
    }).filter((date) => !isWeeklyOff(date));
  }

  function uniqueName(random, usedNames) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const name = `${pick(random, vocabulary.firstNames)} ${pick(random, vocabulary.lastNames)}`;
      if (!usedNames.has(name)) {
        usedNames.add(name);
        return name;
      }
    }
    const fallback = `Employee ${usedNames.size + 1}`;
    usedNames.add(fallback);
    return fallback;
  }

  function buildDepartments(random) {
    const pool = [...vocabulary.departmentNames].sort(() => random() - 0.5);
    const count = integer(random, 5, 7);
    return pool.slice(0, count).map((name, index) => ({
      id: newId("dept"),
      code: `D${String(index + 1).padStart(2, "0")}`,
      name,
      headEmployeeId: null,
      budgetCenter: `CC-${integer(random, 100, 999)}`,
      active: true,
    }));
  }

  function buildShifts(random) {
    const definitions = [
      { label: "General", start: 9 * 60, end: 17 * 60, grace: 10 },
      { label: "Early", start: 8 * 60, end: 16 * 60, grace: 8 },
      { label: "Late", start: 10 * 60, end: 18 * 60, grace: 10 },
      { label: "Field flexible", start: 8 * 60 + 30, end: 17 * 60 + 30, grace: 20 },
    ];
    return definitions.map((definition) => ({
      id: newId("shift"),
      ...definition,
      breakMinutes: integer(random, 45, 60),
      active: true,
    }));
  }

  function buildDevices(random, employeeTarget) {
    const count = integer(random, 4, 6);
    const locations = [...vocabulary.locations].sort(() => random() - 0.5).slice(0, count);
    return locations.map((location) => {
      const statusRoll = random();
      const status = statusRoll > 0.84 ? "Offline" : statusRoll > 0.72 ? "Attention" : "Online";
      const lastSyncMinutes = status === "Offline" ? integer(random, 80, 420) : integer(random, 1, 24);
      return {
        id: newId("device"),
        name: `${location} Reader`,
        location,
        vendor: "ZKTeco",
        model: pick(random, vocabulary.deviceModels),
        ip: `192.168.${integer(random, 10, 40)}.${integer(random, 20, 240)}`,
        port: 4370,
        status,
        lastSyncAt: new Date(Date.now() - lastSyncMinutes * 60000).toISOString(),
        registeredUsers: Math.max(0, employeeTarget + integer(random, -3, 4)),
        firmware: `${integer(random, 5, 8)}.${integer(random, 0, 9)}.${integer(random, 0, 9)}`,
        enabled: true,
      };
    });
  }

  function buildEmployees(random, departments, shifts, devices) {
    const count = integer(random, 42, 68);
    const usedNames = new Set();
    return Array.from({ length: count }, (_, index) => {
      const name = uniqueName(random, usedNames);
      const department = pick(random, departments);
      const shift = pick(random, shifts);
      const device = pick(random, devices);
      const status = random() > 0.06 ? "Active" : "Inactive";
      const joinedOffset = integer(random, 45, 2200);
      const firstName = name.split(" ")[0].toLowerCase();
      const lastName = name.split(" ").slice(-1)[0].toLowerCase();
      return {
        id: newId("emp"),
        attId: String(1001 + index),
        employeeCode: `HF-${String(index + 1).padStart(4, "0")}`,
        name,
        email: `${firstName}.${lastName}${index + 1}@demo.hajiriflow.app`,
        phone: `98${String(integer(random, 10000000, 99999999))}`,
        departmentId: department.id,
        section: pick(random, vocabulary.sections),
        role: pick(random, vocabulary.roles),
        shiftId: shift.id,
        deviceId: device.id,
        salary: integer(random, 36000, 145000),
        status,
        employmentType: random() > 0.16 ? "Permanent" : "Contract",
        joinedAt: addDays(isoDate(new Date()), -joinedOffset),
        avatarHue: integer(random, 180, 320),
      };
    });
  }

  function buildLeaveRequests(random, employees) {
    const activeEmployees = employees.filter((employee) => employee.status === "Active");
    const requests = [];
    const today = isoDate(new Date());
    const count = integer(random, 8, 16);
    for (let index = 0; index < count; index += 1) {
      const employee = pick(random, activeEmployees);
      const startOffset = integer(random, -18, 20);
      const duration = integer(random, 1, 4);
      const statusRoll = random();
      const status = statusRoll > 0.68 ? "Pending" : statusRoll > 0.18 ? "Approved" : "Rejected";
      const startDate = addDays(today, startOffset);
      requests.push({
        id: newId("leave"),
        employeeId: employee.id,
        type: pick(random, vocabulary.leaveTypes),
        startDate,
        endDate: addDays(startDate, duration - 1),
        days: duration,
        status,
        reason: status === "Rejected" ? "Policy documentation incomplete" : "Personal request",
        appliedAt: new Date(Date.now() - integer(random, 1, 18) * 86400000).toISOString(),
        reviewedAt: status === "Pending" ? null : new Date(Date.now() - integer(random, 1, 8) * 86400000).toISOString(),
      });
    }
    return requests;
  }

  function requestCoversDate(request, date) {
    return request.status === "Approved" && request.startDate <= date && request.endDate >= date;
  }

  function buildAttendanceRecord(random, employee, date, shift, device, leaveRequests, currentDate) {
    const leave = leaveRequests.find((request) => request.employeeId === employee.id && requestCoversDate(request, date));
    if (leave) {
      return {
        id: newId("attendance"), employeeId: employee.id, date, checkIn: null, checkOut: null,
        workedMinutes: 0, lateMinutes: 0, earlyMinutes: 0, status: "Leave",
        source: leave.type, deviceId: null,
      };
    }
    if (isWeeklyOff(date)) {
      return {
        id: newId("attendance"), employeeId: employee.id, date, checkIn: null, checkOut: null,
        workedMinutes: 0, lateMinutes: 0, earlyMinutes: 0, status: "Weekly off",
        source: "Calendar", deviceId: null,
      };
    }

    const roll = random();
    if (roll < 0.045) {
      return {
        id: newId("attendance"), employeeId: employee.id, date,
        checkIn: null, checkOut: null, workedMinutes: 0, lateMinutes: 0, earlyMinutes: 0,
        status: "Absent", source: "No punch", deviceId: null,
      };
    }
    if (roll < 0.085) {
      return {
        id: newId("attendance"), employeeId: employee.id, date,
        checkIn: null, checkOut: null, workedMinutes: shift.end - shift.start,
        lateMinutes: 0, earlyMinutes: 0, status: "Field duty", source: "Approved kaaj", deviceId: null,
      };
    }

    const arrivalRoll = random();
    const checkInOffset = arrivalRoll < 0.68
      ? integer(random, -18, 5)
      : arrivalRoll < 0.9
        ? integer(random, 6, 15)
        : integer(random, 16, 35);
    const overtime = integer(random, -22, 65);
    const checkInMinutes = shift.start + checkInOffset;
    const checkOutMinutes = shift.end + overtime;
    const lateMinutes = Math.max(0, checkInMinutes - shift.start - shift.grace);
    const earlyMinutes = Math.max(0, shift.end - checkOutMinutes);
    const isToday = date === currentDate;
    const nowParts = new Intl.DateTimeFormat("en-GB", {
      timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit", hour12: false,
    }).formatToParts(new Date());
    const nowMinutes = Number(nowParts.find((part) => part.type === "hour")?.value || 0) * 60
      + Number(nowParts.find((part) => part.type === "minute")?.value || 0);
    const checkedOut = !isToday || nowMinutes >= checkOutMinutes || random() > 0.35;
    const workedMinutes = checkedOut
      ? Math.max(0, checkOutMinutes - checkInMinutes - shift.breakMinutes)
      : Math.max(0, nowMinutes - checkInMinutes - Math.min(shift.breakMinutes, 45));
    return {
      id: newId("attendance"), employeeId: employee.id, date,
      checkIn: minutesToClock(checkInMinutes), checkOut: checkedOut ? minutesToClock(checkOutMinutes) : null,
      workedMinutes, lateMinutes, earlyMinutes, status: lateMinutes > 0 ? "Late" : "Present",
      source: device?.name || "Manual", deviceId: device?.id || null,
    };
  }

  function buildAttendance(random, employees, shifts, devices, leaveRequests) {
    const records = [];
    const currentDate = isoDate(new Date());
    for (let offset = -94; offset <= 0; offset += 1) {
      const date = addDays(currentDate, offset);
      for (const employee of employees.filter((item) => item.status === "Active")) {
        const shift = shifts.find((item) => item.id === employee.shiftId) || shifts[0];
        const device = devices.find((item) => item.id === employee.deviceId) || devices[0];
        records.push(buildAttendanceRecord(random, employee, date, shift, device, leaveRequests, currentDate));
      }
    }
    return records;
  }

  function buildPayrollPeriods() {
    return Array.from({ length: 3 }, (_, index) => {
      const key = previousMonthKey(index);
      return {
        id: newId("period"), key, label: monthLabel(key),
        status: index === 0 ? "Draft" : index === 1 ? "Approved" : "Paid",
        generatedAt: index === 0 ? null : new Date(Date.now() - (index * 27 + 4) * 86400000).toISOString(),
        locked: index > 0,
      };
    });
  }

  function buildActivities(random, employees, devices, leaveRequests) {
    const activities = [];
    for (let index = 0; index < 14; index += 1) {
      const employee = pick(random, employees);
      const device = pick(random, devices);
      const request = pick(random, leaveRequests);
      const subject = index % 3 === 0 ? device.name : index % 3 === 1 ? employee.name : `${request.type} request`;
      activities.push({
        id: newId("activity"), verb: pick(random, vocabulary.activityVerbs), subject,
        actor: index % 4 === 0 ? "System worker" : "Nischhal Subba",
        occurredAt: new Date(Date.now() - integer(random, 2, 3400) * 60000).toISOString(),
        type: index % 4 === 0 ? "device" : index % 4 === 1 ? "attendance" : index % 4 === 2 ? "leave" : "payroll",
      });
    }
    return activities.sort((a, b) => new Date(b.occurredAt) - new Date(a.occurredAt));
  }

  function generateState(seed = `${Date.now()}-${newId("seed")}`) {
    const random = createRandom(seed);
    const departments = buildDepartments(random);
    const shifts = buildShifts(random);
    const employeeTarget = integer(random, 48, 62);
    const devices = buildDevices(random, employeeTarget);
    const employees = buildEmployees(random, departments, shifts, devices);
    const leaveRequests = buildLeaveRequests(random, employees);
    const attendance = buildAttendance(random, employees, shifts, devices, leaveRequests);
    const payrollPeriods = buildPayrollPeriods();
    const activities = buildActivities(random, employees, devices, leaveRequests);

    departments.forEach((department) => {
      const candidates = employees.filter((employee) => employee.departmentId === department.id && employee.status === "Active");
      department.headEmployeeId = candidates[0]?.id || null;
    });

    return {
      version: VERSION, seed, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
      workspace: {
        name: "HajiriFlow Demo", organization: "HajiriFlow Client Workspace", timezone: TIMEZONE,
        locale: "en-NP", weeklyOffDay: 6, currency: "NPR", dataMode: "Generated demo data",
      },
      preferences: { density: "comfortable", theme: "light", dashboardRange: 14 },
      departments, shifts, devices, employees, leaveRequests, attendance, payrollPeriods, activities,
      notificationsReadAt: null,
    };
  }

  function loadState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (parsed?.version === VERSION && Array.isArray(parsed.employees)) return parsed;
    } catch (error) {
      console.warn("Unable to load demo state", error);
    }
    const next = generateState();
    saveState(next);
    return next;
  }

  function saveState(next) {
    next.updatedAt = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  let state = loadState();
  const listeners = new Set();

  function notify() { listeners.forEach((listener) => listener(state)); }
  function mutate(mutator) { const result = mutator(state); saveState(state); notify(); return result; }
  function replace(next) { state = next; saveState(state); notify(); return state; }
  function regenerate() { return replace(generateState()); }
  function getTodayRecords() { const today = isoDate(new Date()); return state.attendance.filter((record) => record.date === today); }
  function getEmployee(employeeId) { return state.employees.find((employee) => employee.id === employeeId) || null; }
  function getDepartment(departmentId) { return state.departments.find((department) => department.id === departmentId) || null; }
  function getShift(shiftId) { return state.shifts.find((shift) => shift.id === shiftId) || null; }

  function formatMoney(amount) {
    return new Intl.NumberFormat("en-NP", {
      style: "currency", currency: state.workspace.currency, maximumFractionDigits: 0,
    }).format(amount);
  }

  function payrollRows(periodKey) {
    const monthDates = new Set(workingDatesForMonth(periodKey));
    const workingDayCount = monthDates.size || 1;
    return state.employees.filter((employee) => employee.status === "Active").map((employee) => {
      const records = state.attendance.filter((record) => record.employeeId === employee.id && monthDates.has(record.date));
      const absent = records.filter((record) => record.status === "Absent").length;
      const lateMinutes = records.reduce((sum, record) => sum + record.lateMinutes, 0);
      const overtimeMinutes = records.reduce((sum, record) => {
        const shift = getShift(employee.shiftId);
        const planned = shift ? shift.end - shift.start - shift.breakMinutes : 480;
        return sum + Math.max(0, record.workedMinutes - planned);
      }, 0);
      const absenceDeduction = Math.round((employee.salary / workingDayCount) * absent);
      const lateDeduction = Math.round((employee.salary / workingDayCount / 480) * Math.max(0, lateMinutes - 30));
      const overtimePay = Math.round((employee.salary / workingDayCount / 480) * overtimeMinutes * 1.5);
      const providentFund = Math.round(employee.salary * 0.1);
      const tax = Math.round(Math.max(0, employee.salary + overtimePay - providentFund - 50000) * 0.1);
      const netPay = Math.max(0, employee.salary + overtimePay - absenceDeduction - lateDeduction - providentFund - tax);
      return { employeeId: employee.id, baseSalary: employee.salary, absent, lateMinutes, overtimeMinutes,
        overtimePay, absenceDeduction, lateDeduction, providentFund, tax, netPay };
    });
  }

  function dashboardSummary() {
    const activeEmployees = state.employees.filter((employee) => employee.status === "Active");
    const records = getTodayRecords();
    const presentStatuses = new Set(["Present", "Late", "Field duty"]);
    const present = records.filter((record) => presentStatuses.has(record.status)).length;
    const late = records.filter((record) => record.status === "Late").length;
    const absent = records.filter((record) => record.status === "Absent").length;
    const onLeave = records.filter((record) => record.status === "Leave").length;
    const onlineDevices = state.devices.filter((device) => device.status === "Online" && device.enabled).length;
    const pendingLeave = state.leaveRequests.filter((request) => request.status === "Pending").length;
    return {
      activeEmployees: activeEmployees.length, present,
      attendanceRate: activeEmployees.length ? Math.round((present / activeEmployees.length) * 100) : 0,
      late, absent, onLeave, onlineDevices, totalDevices: state.devices.filter((device) => device.enabled).length,
      pendingLeave, payrollReady: absent === 0 && pendingLeave === 0,
    };
  }

  function attendanceTrend(days = 14) {
    const today = isoDate(new Date());
    return Array.from({ length: days }, (_, index) => {
      const date = addDays(today, index - days + 1);
      const records = state.attendance.filter((record) => record.date === date);
      const expected = records.filter((record) => record.status !== "Weekly off").length;
      const present = records.filter((record) => ["Present", "Late", "Field duty"].includes(record.status)).length;
      return {
        date,
        label: new Intl.DateTimeFormat("en-NP", { month: "short", day: "numeric", timeZone: TIMEZONE }).format(localDateFromIso(date)),
        rate: expected ? Math.round((present / expected) * 100) : 100, present, expected,
      };
    });
  }

  function replaceAttendanceForDate(date) {
    return mutate((draft) => {
      const random = createRandom(`${draft.seed}-${date}-${Date.now()}`);
      draft.attendance = draft.attendance.filter((record) => record.date !== date);
      for (const employee of draft.employees.filter((item) => item.status === "Active")) {
        const shift = draft.shifts.find((item) => item.id === employee.shiftId) || draft.shifts[0];
        const device = draft.devices.find((item) => item.id === employee.deviceId) || draft.devices[0];
        draft.attendance.push(buildAttendanceRecord(random, employee, date, shift, device, draft.leaveRequests, isoDate(new Date())));
      }
      draft.activities.unshift({
        id: newId("activity"), verb: "reprocessed", subject: `attendance for ${date}`,
        actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "attendance",
      });
    });
  }

  function simulateDeviceAction(deviceId, action) {
    return mutate((draft) => {
      const device = draft.devices.find((item) => item.id === deviceId);
      if (!device) return null;
      if (action === "test") device.status = Math.random() > 0.12 ? "Online" : "Attention";
      if (action === "sync" || action === "pull") {
        device.status = "Online";
        device.lastSyncAt = new Date().toISOString();
        device.registeredUsers = draft.employees.filter((employee) => employee.status === "Active").length;
      }
      draft.activities.unshift({
        id: newId("activity"),
        verb: action === "test" ? "tested" : action === "sync" ? "synchronized" : "pulled records from",
        subject: device.name, actor: "Nischhal Subba", occurredAt: new Date().toISOString(), type: "device",
      });
      return device;
    });
  }

  function markNotificationsRead() { return mutate((draft) => { draft.notificationsReadAt = new Date().toISOString(); }); }
  function unreadNotificationCount() {
    if (!state.notificationsReadAt) return Math.min(9, state.activities.length);
    return state.activities.filter((activity) => activity.occurredAt > state.notificationsReadAt).length;
  }
  function subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }

  window.HFData = {
    TIMEZONE, VERSION, addDays, attendanceTrend, clamp, clockToMinutes, currentMonthKey,
    dashboardSummary, formatMoney, getDepartment, getEmployee, getShift, getState: () => state,
    isoDate, localDateFromIso, markNotificationsRead, monthLabel, mutate, newId, payrollRows,
    regenerate, replaceAttendanceForDate, save: () => saveState(state), simulateDeviceAction,
    subscribe, unreadNotificationCount, workingDatesForMonth,
  };
})();
