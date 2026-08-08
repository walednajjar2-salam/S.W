(function () {
  "use strict";

  let lastBoard = null;

  function esc(s) {
    if (typeof htmlEscape === "function") return htmlEscape(s);
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function levelCls(level) {
    if (level === "Critical" || level === "High") return "overdue";
    if (level === "Medium") return "pending";
    return "paid";
  }

  function renderKpis(kpis) {
    if (!kpis || !kpis.length) return "";
    return `<div class="status-line" style="margin:10px 0;flex-wrap:wrap;gap:8px">${kpis
      .map(
        (k) =>
          `<span class="badge"><b>${esc(k.label)}</b> · ${esc(k.display)}</span>`
      )
      .join("")}</div>`;
  }

  function renderPriorities(items) {
    if (!items || !items.length) {
      return `<p class="mini linked-ok">لا أولويات عاجلة لدورك اليوم ✅</p>`;
    }
    return `<div class="saas-task-list">${items
      .map((a) => {
        const go = a.action_section
          ? `<button type="button" class="ghost" onclick="showSection('${esc(a.action_section)}')">${esc(a.action_label || "فتح")}</button>`
          : "";
        return `<div class="saas-task-item"><div><span class="badge ${levelCls(a.level)}">${esc(a.level || "")}</span> <b>${esc(a.title || "")}</b><p class="mini">${esc(a.text || "")}</p></div>${go}</div>`;
      })
      .join("")}</div>`;
  }

  function renderActions(actions) {
    if (!actions || !actions.length) return "";
    return `<div class="toolbar" style="flex-wrap:wrap;gap:8px;margin-top:10px">${actions
      .map(
        (a) =>
          `<button type="button" class="ghost" onclick="showSection('${esc(a.section)}')">${esc(a.label)}</button>`
      )
      .join("")}<button type="button" class="gold-btn" onclick="showSection('messages')">كل التنبيهات</button></div>`;
  }

  function render(host, board) {
    if (!host || !board) return;
    lastBoard = board;
    const sum = board.summary || {};
    host.innerHTML = `
      <div class="card lq-role-board" style="margin-bottom:14px">
        <h3 style="margin:0 0 4px">${esc(board.title_ar || "لوحة دورك")}</h3>
        <p class="mini">${esc(board.subtitle_ar || "")} · ${esc(board.name || board.username || "")}</p>
        <div class="status-line" style="margin:8px 0;flex-wrap:wrap;gap:6px">
          <span class="badge overdue">عاجل: ${Number(sum.high || 0) + Number(sum.critical || 0)}</span>
          <span class="badge">إجمالي تنبيهات: ${Number(sum.total || 0)}</span>
          <span class="badge">اعتمادات: ${esc(String((board.kpis || []).find((k) => k.key === "pending_approvals")?.display || "0"))}</span>
        </div>
        ${renderKpis(board.kpis)}
        <h4 style="margin:12px 0 6px">أولويات اليوم</h4>
        ${renderPriorities(board.top_priorities || board.alerts)}
        ${renderActions(board.quick_actions)}
      </div>`;
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
  }

  async function refresh() {
    const host = document.getElementById("roleBoardBox");
    if (!host) return null;
    try {
      const res = await api("role_board");
      render(host, res.board);
      if (window.LQ_ALERT_CENTER && typeof LQ_ALERT_CENTER.updateBell === "function") {
        LQ_ALERT_CENTER.updateBell(res.board && res.board.summary);
      }
      return res.board;
    } catch (e) {
      host.innerHTML = `<p class="mini">تعذر تحميل لوحة الدور</p>`;
      return null;
    }
  }

  function hookDashboard() {
    const orig = window.renderDashboard;
    if (typeof orig !== "function" || orig.__lqRoleBoardHooked) return;
    const wrapped = function () {
      const out = orig.apply(this, arguments);
      refresh();
      return out;
    };
    wrapped.__lqRoleBoardHooked = true;
    window.renderDashboard = wrapped;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hookDashboard);
  } else {
    hookDashboard();
  }

  window.LQ_ROLE_BOARD = { refresh, render, get last() { return lastBoard; } };
})();
