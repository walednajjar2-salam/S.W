const API = "/api";

function getToken() {
  return localStorage.getItem("smm_token");
}

function setToken(token) {
  if (token) localStorage.setItem("smm_token", token);
  else localStorage.removeItem("smm_token");
}

function getUser() {
  const raw = localStorage.getItem("smm_user");
  return raw ? JSON.parse(raw) : null;
}

function setUser(user) {
  if (user) localStorage.setItem("smm_user", JSON.stringify(user));
  else localStorage.removeItem("smm_user");
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API}${path}`, { ...options, headers });
  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = { detail: text }; }
  }

  if (!res.ok) {
    const msg = data?.detail || data?.message || "حدث خطأ";
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function formatMoney(n) {
  return `$${Number(n).toFixed(2)}`;
}

function formatProgress(delivered, quantity) {
  const pct = quantity ? Math.min(100, Math.round((delivered / quantity) * 100)) : 0;
  return pct;
}

function statusBadge(status) {
  const map = {
    processing: "قيد التسليم",
    completed: "مكتمل",
    pending: "انتظار",
  };
  const cls = `badge badge-${status}`;
  return `<span class="${cls}">${map[status] || status}</span>`;
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "/assets/login.html";
    return false;
  }
  return true;
}

function logout() {
  setToken(null);
  setUser(null);
  window.location.href = "/assets/login.html";
}
