(function () {
  "use strict";

  let intelCache = null;
  let usageCache = null;

  function esc(s) {
    if (typeof htmlEscape === "function") return htmlEscape(s);
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function moneyFmt(n) {
    if (typeof money === "function") return money(n);
    return Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  function prioBadge(p) {
    const cls = p === "high" ? "overdue" : p === "medium" ? "pending" : "paid";
    return `<span class="badge ${cls}">${esc(p)}</span>`;
  }

  function guideHtml() {
    return `
      <div class="card lq-walid-guide">
        <h3>🤖 وليد · الذكاء التشغيلي — المرحلة 9</h3>
        <p class="mini">مساعد تشغيلي يجيب من بياناتك الحقيقية: متأخرات، عقود، تأمينات، صيانة، وتوصيات تنفيذية.</p>
        <p class="mini">🎤 تحدث مع WALEED · 🔊 صوت الردود (اختياري من لوحة WALEED).</p>
        <ul class="check-list">
          <li><strong>أسئلة مباشرة</strong> — من لم يدفع؟ ما العقود التي تنتهي؟</li>
          <li><strong>توصيات</strong> — تحصيل، تجديد، صيانة، اعتمادات</li>
          <li><strong>LLM</strong> — فعّل <code>OPENAI_API_KEY</code> على Railway للردود الذكية</li>
          <li><strong>حد الاستخدام</strong> — ${usageCache ? usageCache.limit : "50"} سؤال/يوم لكل مستخدم</li>
        </ul>
      </div>`;
  }

  function usageHtml() {
    const u = usageCache || {};
    const llm = u.llm_enabled ? "LLM مفعّل" : "قواعد + بيانات (بدون LLM)";
    return `<div class="status-line" style="margin:8px 0">
      <span class="badge">استخدام: ${u.count || 0}/${u.limit || 50}</span>
      <span class="badge">${llm}</span>
      <button type="button" class="ghost" onclick="window.open('/api/report/executive','_blank')">تقرير تنفيذي PDF</button>
    </div>`;
  }

  function briefCard(intel) {
    return `<div class="card saas-glass" style="margin-top:12px">
      <h4>📋 ملخص تنفيذي تلقائي</h4>
      <p class="exec-brief-text">${esc(intel.brief || "—")}</p>
    </div>`;
  }

  function recommendationsHtml(recs) {
    if (!recs || !recs.length) {
      return '<p class="mini linked-ok">لا توصيات حرجة — التشغيل مستقر ✅</p>';
    }
    return `<div class="saas-task-list">${recs
      .map(
        (r) =>
          `<div class="saas-task-item"><div>${prioBadge(r.priority)} <b>${esc(r.title)}</b><p>${esc(r.text)}</p></div>
          <button type="button" class="ghost" onclick="showSection('${r.section || "dashboard"}')">${esc(r.action_label || "فتح")}</button></div>`
      )
      .join("")}</div>`;
  }

  function debtorsTable(rows) {
    if (!rows || !rows.length) return '<p class="mini">لا متأخرات</p>';
    return `<div class="table-wrap"><table><thead><tr><th>العميل</th><th>المتأخر</th><th>فواتير</th><th>أقدم استحقاق</th></tr></thead><tbody>${rows
      .slice(0, 10)
      .map(
        (d) =>
          `<tr><td>${esc(d.name)}</td><td>${moneyFmt(d.total)}</td><td>${d.invoice_count || 0}</td><td>${esc(d.oldest_due || "—")}</td></tr>`
      )
      .join("")}</tbody></table></div>`;
  }

  function contractsTable(rows) {
    if (!rows || !rows.length) return '<p class="mini">لا عقود قريبة</p>';
    return `<div class="table-wrap"><table><thead><tr><th>العقد</th><th>العميل</th><th>الوحدة</th><th>الانتهاء</th><th>الأيام</th></tr></thead><tbody>${rows
      .slice(0, 10)
      .map((c) => {
        const days =
          c.days_left < 0
            ? `<span class="badge overdue">منتهي ${Math.abs(c.days_left)}</span>`
            : esc(c.days_left);
        return `<tr><td>${esc(c.contract_no)}</td><td>${esc(c.client_name)}</td><td>${esc(c.property_name)}</td><td>${esc(c.end_date || "—")}</td><td>${days}</td></tr>`;
      })
      .join("")}</tbody></table></div>`;
  }

  function promptsHtml(questions) {
    const qs = questions || [];
    return `<div class="lq-walid-prompts">${qs
      .map(
        (q, i) =>
          `<button type="button" class="ghost lq-walid-chip" data-walid-q="${i}">${esc(q)}</button>`
      )
      .join("")}</div>`;
  }

  function bindPrompts(root, handler) {
    if (!root) return;
    const qs = (intelCache && intelCache.suggested_questions) || [];
    root.querySelectorAll("[data-walid-q]").forEach((btn) => {
      btn.onclick = () => {
        const i = Number(btn.getAttribute("data-walid-q"));
        if (qs[i]) handler(qs[i]);
      };
    });
  }

  function renderPage(host, intel) {
    if (!host) return;
    intelCache = intel;
    host.innerHTML =
      guideHtml() +
      usageHtml() +
      briefCard(intel) +
      `<div class="toolbar" style="flex-wrap:wrap;gap:8px;margin:12px 0">
        <button type="button" class="gold-btn" onclick="LQ_WALID_INTEL.refresh()">تحديث الذكاء</button>
        <button type="button" class="ghost" onclick="LQ_WALID_INTEL.ask('ملخص تنفيذي اليوم')">ملخص اليوم</button>
      </div>` +
      `<div class="card"><h4>💡 أسئلة سريعة</h4>${promptsHtml(intel.suggested_questions)}</div>` +
      `<div class="layout" style="margin-top:12px">
        <div class="card"><h4>🎯 توصيات Walid</h4>${recommendationsHtml(intel.recommendations)}</div>
        <div class="card"><h4>💳 من لم يدفع؟</h4>${debtorsTable(intel.overdue_debtors)}</div>
      </div>` +
      `<div class="layout" style="margin-top:12px">
        <div class="card"><h4>📄 عقود تنتهي قريباً</h4>${contractsTable(intel.expiring_contracts)}</div>
        <div class="card"><h4>🔧 صيانة مفتوحة</h4>${maintList(intel.urgent_maintenance)}</div>
      </div>`;
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
    bindPrompts(host, ask);
    updateDockBadge();
  }

  function maintList(rows) {
    if (!rows || !rows.length) return '<p class="mini">لا طلبات مفتوحة</p>';
    return `<div class="saas-task-list">${rows
      .slice(0, 8)
      .map(
        (m) =>
          `<div class="saas-task-item"><div><b>${esc(m.title)}</b><p>${esc(m.property_name)} · ${esc(m.priority)}</p></div></div>`
      )
      .join("")}</div>`;
  }

  function updateDockBadge() {
    const head = document.querySelector("#visionAiDock .vision-ai-head span");
    const u = usageCache || {};
    if (head) {
      head.textContent = u.llm_enabled ? `LLM · ${u.remaining || 0} left` : `Live · ${u.remaining || 0} left`;
    }
    const prompts = document.getElementById("walidDockPrompts");
    if (prompts && intelCache) {
      prompts.innerHTML = promptsHtml(intelCache.suggested_questions);
      bindPrompts(prompts, ask);
    }
  }

  async function refresh() {
    const host = document.getElementById("walidIntelBox");
    if (host) host.innerHTML = '<p class="mini">جاري تحميل الذكاء التشغيلي…</p>';
    try {
      const res = await api("operational_intel");
      intelCache = res.intel || {};
      usageCache = res.usage || {};
      if (host) renderPage(host, intelCache);
      if (typeof refreshVisionAi === "function") refreshVisionAi();
      return res;
    } catch (e) {
      if (host) host.innerHTML = guideHtml() + '<p class="badge overdue">تعذر التحميل</p>';
      if (typeof toastErr === "function") toastErr(e);
      throw e;
    }
  }

  async function ask(question) {
    const q = String(question || "").trim();
    if (!q) return;
    const body = document.getElementById("visionAiBody");
    if (body) {
      body.insertAdjacentHTML("beforeend", `<div class="vision-ai-msg">${esc(q)}</div>`);
    }
    try {
      const res = await api("ai/ask", { method: "POST", body: JSON.stringify({ question: q }) });
      usageCache = res.usage || usageCache;
      const mode = res.mode === "llm" ? "LLM" : "Rules";
      const reply = `${res.assistant || "Walid"} (${mode}): ${res.reply || ""}`;
      if (body) {
        body.insertAdjacentHTML("beforeend", `<div class="vision-ai-msg pred">${esc(reply)}</div>`);
        const actions = (res.actions || [])
          .map(
            (a) =>
              `<button type="button" data-action="${a.action || "navigate"}" data-section="${a.section}">${esc(a.label)}</button>`
          )
          .join("");
        if (actions) {
          body.insertAdjacentHTML("beforeend", `<div class="vision-ai-actions">${actions}</div>`);
        }
        if (typeof initAiDock === "function") initAiDock();
      }
      updateDockBadge();
      if (typeof haptic === "function") haptic(8);
    } catch (e) {
      if (body) {
        body.insertAdjacentHTML(
          "beforeend",
          `<div class="vision-ai-msg">${esc(e.message || "تعذر الاتصال بـ Walid")}</div>`
        );
      }
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  window.LQ_WALID_INTEL = { refresh, ask, renderPage };
  window.LQ_WALID_DOCK_ask = function (q) {
    ask(q);
    const dock = document.getElementById("visionAiDock");
    if (dock) dock.classList.remove("collapsed");
  };

  document.addEventListener("DOMContentLoaded", function () {
    const style = document.createElement("style");
    style.textContent =
      ".lq-walid-prompts{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.lq-walid-chip{font-size:12px;padding:6px 10px;border-radius:999px}";
    document.head.appendChild(style);
  });
})();
