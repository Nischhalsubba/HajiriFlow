(() => {
  "use strict";

  const rawConfig = window.__HAJIRIFLOW_CONFIG__ || {};
  const apiBasePath = String(rawConfig.apiBasePath || "/api").trim().replace(/\/+$/, "");
  let currentSession = null;
  let csrfToken = null;

  function isConfigured() {
    return apiBasePath.startsWith("/") && !apiBasePath.startsWith("//");
  }

  function endpoint(path) {
    return `${apiBasePath}/v1${path}`;
  }

  function createError(status, message) {
    const error = new Error(message);
    error.status = status;
    return error;
  }

  async function parseResponse(response) {
    if (response.status === 204) return null;
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      if (!response.ok) throw createError(response.status, "The HajiriFlow API returned an unexpected response.");
      return null;
    }
    const payload = await response.json();
    if (!response.ok) {
      const detail = typeof payload?.detail === "string" ? payload.detail : "The request could not be completed.";
      throw createError(response.status, detail);
    }
    return payload;
  }

  function rememberSession(session) {
    currentSession = session || null;
    csrfToken = session?.csrf_token || csrfToken || null;
    return currentSession;
  }

  async function request(path, { method = "GET", body, csrf = false } = {}) {
    if (!isConfigured()) throw createError(503, "HajiriFlow API proxy is not configured.");
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (csrf) {
      if (!csrfToken) throw createError(403, "The security token is unavailable. Refresh your session and try again.");
      headers["X-CSRF-Token"] = csrfToken;
    }

    let response;
    try {
      response = await fetch(endpoint(path), {
        method,
        headers,
        credentials: "same-origin",
        cache: "no-store",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw createError(503, "HajiriFlow could not reach the application API.");
    }
    return parseResponse(response);
  }

  async function refreshCsrf() {
    const result = await request("/auth/csrf");
    csrfToken = result?.csrf_token || null;
    if (!csrfToken) throw createError(500, "The application API did not provide a security token.");
    return csrfToken;
  }

  async function login(username, password) {
    const session = await request("/auth/login", {
      method: "POST",
      body: { username, password },
    });
    csrfToken = session?.csrf_token || null;
    return rememberSession(session);
  }

  async function me() {
    try {
      const session = await request("/auth/me");
      await refreshCsrf();
      return rememberSession({ ...session, csrf_token: csrfToken });
    } catch (error) {
      if (error.status === 401) {
        currentSession = null;
        csrfToken = null;
      }
      throw error;
    }
  }

  async function logout() {
    await request("/auth/logout", { method: "POST", csrf: true });
    currentSession = null;
    csrfToken = null;
  }

  async function changePassword(currentPassword, newPassword) {
    await request("/auth/change-password", {
      method: "POST",
      csrf: true,
      body: {
        current_password: currentPassword,
        new_password: newPassword,
      },
    });
    currentSession = null;
    csrfToken = null;
  }

  async function listUsers() {
    return request("/admin/users");
  }

  async function createUser(input) {
    return request("/admin/users", { method: "POST", csrf: true, body: input });
  }

  async function setUserStatus(userId, status) {
    return request(`/admin/users/${encodeURIComponent(userId)}/status`, {
      method: "PATCH",
      csrf: true,
      body: { status },
    });
  }

  async function listRoles() {
    return request("/admin/roles");
  }

  async function listRoleAssignments() {
    return request("/admin/role-assignments");
  }

  async function assignRole(userId, input) {
    return request(`/admin/users/${encodeURIComponent(userId)}/roles`, {
      method: "POST",
      csrf: true,
      body: input,
    });
  }

  async function revokeRoleAssignment(assignmentId) {
    return request(`/admin/role-assignments/${encodeURIComponent(assignmentId)}`, {
      method: "DELETE",
      csrf: true,
    });
  }

  window.HFIdentity = Object.freeze({
    assignRole,
    changePassword,
    createUser,
    get apiBasePath() { return apiBasePath; },
    get session() { return currentSession; },
    isConfigured,
    listRoleAssignments,
    listRoles,
    listUsers,
    login,
    logout,
    me,
    refreshCsrf,
    revokeRoleAssignment,
    setUserStatus,
  });
})();
