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
  return quantity ? Math.min(100, Math.round((delivered / quantity) * 100)) : 0;
}

function statusBadge(status) {
  const map = {
    processing: "قيد التسليم",
    completed: "مكتمل",
    pending: "انتظار",
  };
  return `<span class="badge badge-${status}">${map[status] || status}</span>`;
}

function platformBadge(platform) {
  const p = (platform || "").toLowerCase();
  const labels = { instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube" };
  return `<span class="badge badge-platform badge-${p}">${labels[p] || platform}</span>`;
}

function platformIcon(platform) {
  const icons = { instagram: "📸", tiktok: "🎵", youtube: "▶️" };
  return icons[(platform || "").toLowerCase()] || "📦";
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "/login";
    return false;
  }
  return true;
}

function logout() {
  setToken(null);
  setUser(null);
  window.location.href = "/login";
}

function showToast(message, type = "success") {
  const container = document.getElementById("toasts");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.3s";
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

function toggleSidebar(open) {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  if (!sidebar) return;
  const isOpen = open ?? !sidebar.classList.contains("open");
  sidebar.classList.toggle("open", isOpen);
  overlay?.classList.toggle("open", isOpen);
}

function setActiveNav(tab) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  const titles = {
    order: "طلب جديد",
    orders: "طلباتي",
    wallet: "المحفظة",
    accounts: "ربط الحسابات",
    admin: "لوحة الإدارة",
  };
  const titleEl = document.getElementById("pageTitle");
  if (titleEl) titleEl.textContent = titles[tab] || "لوحة التحكم";
}

function renderEmptyState(icon, text) {
  return `<div class="empty-state"><div class="empty-state-icon">${icon}</div><p>${text}</p></div>`;
}

function actionLabel(action) {
  const map = { follow: "متابعة", like: "لايك", view: "مشاهدة", subscribe: "اشتراك" };
  return map[action] || action;
}

function engagementSummary(o) {
  const e = o.engagement || {};
  const label = e.action_label || actionLabel(e.action);
  const n = Number(e.assigned || 0);
  return `<div class="engagement-line">
    👆 ${n.toLocaleString()} حساب ضغطوا <strong>${label}</strong> على الرابط المطلوب
    <button type="button" class="btn btn-ghost btn-sm" style="margin-right:8px;" onclick="loadOrderEngagement(${o.id})">عرض من ضغط</button>
  </div>
  <div id="engagement-${o.id}" class="engagement-details hidden"></div>`;
}

async function loadOrderEngagement(orderId) {
  const box = document.getElementById(`engagement-${orderId}`);
  try {
    const data = await api(`/orders/${orderId}/engagement`);
    const names = (data.actors || [])
      .map((a) => `@${a.username || a.name || "حساب"}`)
      .join("، ");
    const html = `<div><strong>${Number(data.assigned || 0).toLocaleString()}</strong> حساب نفّذوا ${data.action_label} على <span dir="ltr">${data.target_url}</span></div>
      <div style="margin-top:6px;">${names || "لم يُسند أي حساب بعد — سيبدأ العامل عند التحديث التالي."}</div>`;
    if (box) {
      box.innerHTML = html;
      box.classList.remove("hidden");
    } else {
      showToast(`${data.assigned} حساب نفّذوا ${data.action_label}`, "success");
    }
  } catch (err) {
    showToast(err.message || "تعذّر تحميل من ضغطوا", "error");
  }
}

function renderOrderCards(rows, admin = false) {
  if (!rows.length) return renderEmptyState("📭", "لا توجد طلبات بعد");
  return rows.map((o) => {
    const pct = formatProgress(o.delivered, o.quantity);
    return `<div class="order-card">
      <div class="order-card-header">
        <span class="order-card-id">#${o.id}</span>
        ${statusBadge(o.status)}
      </div>
      <div class="order-card-meta">
        ${admin ? `<div><strong>المستخدم:</strong> ${o.user_email || "—"}</div>` : ""}
        <div><strong>الخدمة:</strong> ${o.service_name}</div>
        <div><strong>المبلغ:</strong> ${formatMoney(o.amount)}</div>
        <div style="grid-column:1/-1;"><strong>الرابط:</strong> ${o.target_url}</div>
      </div>
      <div>${o.delivered.toLocaleString()} / ${o.quantity.toLocaleString()} (${pct}%)</div>
      <div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>
      ${engagementSummary(o)}
    </div>`;
  }).join("");
}

function renderOrdersTable(rows, admin = false) {
  if (!rows.length) return renderEmptyState("📭", "لا توجد طلبات بعد");
  return `<div class="table-wrap"><table>
    <tr>
      <th>#</th>
      ${admin ? "<th>المستخدم</th>" : ""}
      <th>الخدمة</th>
      <th>الرابط</th>
      <th>التقدم</th>
      <th>الحالة</th>
      <th>المبلغ</th>
    </tr>
    ${rows.map((o) => {
      const pct = formatProgress(o.delivered, o.quantity);
      return `<tr>
        <td><strong style="color:var(--primary-light)">#${o.id}</strong></td>
        ${admin ? `<td>${o.user_email || ""}</td>` : ""}
        <td>${o.service_name}</td>
        <td style="max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${o.target_url}</td>
        <td style="min-width:140px;">
          <div style="font-size:0.82rem; color:var(--text-secondary);">${o.delivered}/${o.quantity} (${pct}%)</div>
          <div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>
          <div class="engagement-line">${Number((o.engagement && o.engagement.assigned) || 0).toLocaleString()} × ${(o.engagement && o.engagement.action_label) || "ضغط"}</div>
        </td>
        <td>${statusBadge(o.status)}</td>
        <td><strong>${formatMoney(o.amount)}</strong></td>
      </tr>`;
    }).join("")}
  </table></div>`;
}

function renderOrders(rows, containerId, admin = false) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <div class="desktop-table">${renderOrdersTable(rows, admin)}</div>
    <div class="mobile-cards">${renderOrderCards(rows, admin)}</div>`;
}

function userInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return parts.length >= 2
    ? (parts[0][0] + parts[1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}
