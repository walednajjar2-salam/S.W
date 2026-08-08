(function () {
  "use strict";

  let centerData = null;

  function levelBadge(level) {
    const cls =
      level === "Critical" || level === "High"
        ? "overdue"
        : level === "Medium"
          ? "pending"
          : "paid";
    return `<span class="badge ${cls}">${level || "Alert"}</span>`;
  }

  function explainHtml(role) {
    return `
      <div class="card lq-alerts-guide">
        <h3>🔔 مركز التنبيهات — حسب دورك</h3>
        <p class="mini">تنبيهات استباقية مفلترة لدورك${role ? " (" + role + ")" : ""}: عقود، فواتير، اعتمادات، بنك، مخزون، صيانة.</p>
        <ul class="check-list">
          <li><strong>أولويات اليوم</strong> — أهم 3 تنبيهات تحتاج إجراء</li>
          <li><strong>30 / 60 / 90 يوم</strong> — عقود قريبة الانتهاء</li>
          <li><strong>متأخرات</strong> — فواتير لم تُحصّل</li>
          <li><strong>بريد</strong> — إرسال ملخص (إن وُجد SMTP)</li>
        </ul>
      </div>`;
  }

  function renderSummary(summary) {
    if (!summary) return "";
    return `<div class="status-line" style="margin:12px 0">
      <span class="badge overdue">عاجل: ${(summary.high || 0) + (summary.critical || 0)}</span>
      <span class="badge">حرج: ${summary.critical || 0}</span>
      <span class="badge">إجمالي: ${summary.total || 0}</span>
      <span class="badge">عقود: ${summary.contracts || 0}</span>
      <span class="badge">مالية: ${summary.finance || 0}</span>
      <span class="badge">تشغيل: ${summary.operations || 0}</span>
    </div>`;
  }

  function renderTop(top) {
    if (!top || !top.length) return "";
    return `<div class="card" style="margin:10px 0"><h4>أولويات اليوم</h4><div class="saas-task-list">${top
      .map(
        (a) =>
          `<div class="saas-task-item"><div>${levelBadge(a.level)} <b>${a.title || ""}</b><p>${a.text || ""}</p></div>${
            a.action_section
              ? `<button type="button" class="ghost" onclick="LQ_ALERT_CENTER.go('${a.action_section}','${a.entity_id || ""}')">${a.action_label || "فتح"}</button>`
              : ""
          }</div>`
      )
      .join("")}</div></div>`;
  }

  function renderAlerts(alerts) {
    if (!alerts || !alerts.length) {
      return '<p class="mini linked-ok">لا تنبيهات نشطة — كل شيء تحت المراقبة ✅</p>';
    }
    return `<div class="saas-task-list">${alerts
      .map((a) => {
        const act = a.action_section
          ? `<button type="button" class="ghost" onclick="LQ_ALERT_CENTER.go('${a.action_section}','${a.entity_id || ""}')">${a.action_label || "فتح"}</button>`
          : "";
        const dismiss = `<button type="button" class="ghost" onclick="LQ_ALERT_CENTER.dismiss('${a.id}')">تجاهل</button>`;
        return `<div class="saas-task-item"><div>${levelBadge(a.level)} <b>${a.title || ""}</b><p>${a.text || ""}</p></div>${act} ${dismiss}</div>`;
      })
      .join("")}</div>`;
  }

  function render(host, data) {
    if (!host) return;
    centerData = data;
    const summary = data && data.summary;
    const alerts = (data && data.alerts) || [];
    const channels = (data && data.channels) || {};
    const emailBtn =
      channels.email
        ? `<button type="button" class="gold-btn" onclick="LQ_ALERT_CENTER.sendEmail()">إرسال ملخص بريد</button>`
        : `<span class="mini">البريد: فعّل LQ_SMTP_HOST على السيرفر للإرسال التلقائي</span>`;
    host.innerHTML =
      explainHtml(data && data.role) +
      renderSummary(summary) +
      renderTop((data && data.top_priorities) || []) +
      `<div class="toolbar" style="flex-wrap:wrap;gap:8px;margin-bottom:12px">
        <button type="button" class="ghost" onclick="LQ_ALERT_CENTER.refresh()">تحديث</button>
        ${emailBtn}
      </div>` +
      renderAlerts(alerts);
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
    updateBell(summary);
  }

  async function refresh() {
    try {
      const res = await api("alert_center");
      const box = document.getElementById("messagesPageBox");
      render(box, res.center);
      if (typeof toast === "function") toast("تم تحديث التنبيهات");
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function dismiss(alertKey) {
    if (!alertKey) return;
    try {
      const res = await api("alert_dismiss", {
        method: "POST",
        body: JSON.stringify({ alert_key: alertKey }),
      });
      const box = document.getElementById("messagesPageBox");
      render(box, res.center);
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function go(section, entityId) {
    if (typeof showSection === "function") showSection(section);
    if (entityId && section === "contracts" && typeof renewContract === "function") {
      /* user lands on contracts list */
    }
  }

  async function sendEmail() {
    const email = prompt("بريد المستلم", "info@alamal.info");
    if (!email) return;
    try {
      const res = await api("alert_notify", {
        method: "POST",
        body: JSON.stringify({ channel: "email", recipient: email }),
      });
      if (typeof toast === "function") {
        toast(
          res.status === "sent"
            ? "تم إرسال ملخص التنبيهات بالبريد"
            : `البريد: ${res.status} — ${res.detail || ""}`
        );
      }
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function updateBell(summary) {
    const bell = document.getElementById("bellDot");
    if (!bell) return;
    const n = Number((summary && summary.total) || 0);
    const k = (window.Jawdah && Jawdah.dashboard && Jawdah.dashboard.kpis) || {};
    const urgent = Number(k.overdue || 0) > 0 || Number(k.expiring || 0) > 0 || n > 0;
    bell.classList.toggle("hidden", !urgent);
  }

  window.LQ_ALERT_CENTER = {
    explainHtml,
    render,
    refresh,
    dismiss,
    go,
    sendEmail,
    updateBell,
  };
})();
