/* Launch Quality · 4-zone workspace (commands, org, flow, today) */
(function () {
  const $ = (s) => document.querySelector(s);
  function signedIn() {
    const login = document.getElementById("loginScreen");
    return !login || login.classList.contains("hidden");
  }
  const SECTION_LABELS = {
    dashboard: "لوحة التحكم",
    properties: "العقارات",
    clients: "العملاء",
    contracts: "العقود",
    invoices: "الفواتير",
    maintenance: "الصيانة",
    reports: "التقارير",
    accounts: "الحسابات",
    users: "المستخدمين",
    backup: "نسخ احتياطي",
    walid: "WALEED",
    messages: "الرسائل",
    payroll: "الرواتب",
    inventory: "المخزن",
    statements: "قوائم مالية",
    approvals: "الاعتمادات",
    enterprise: "المؤسسة",
  };

  const ROLE_TOOLS = {
    owner: ["dashboard", "reports", "users", "backup", "enterprise", "invoices"],
    admin: ["properties", "contracts", "invoices", "clients", "users", "reports"],
    operations: ["properties", "clients", "contracts", "maintenance"],
    accountant: ["invoices", "accounts", "reports", "statements"],
    maintenance: ["maintenance", "properties"],
    viewer: ["dashboard", "reports", "messages"],
  };

  const ROLE_ICON = {
    owner: "👑",
    admin: "🛡️",
    accountant: "📊",
    operations: "🏢",
    maintenance: "🔧",
    viewer: "👁️",
  };

  function esc(s) {
    return typeof htmlEscape === "function" ? htmlEscape(s) : String(s || "");
  }

  function propertyVisual(p) {
    const s = String(p.status || "");
    if (s.includes("صيان")) return "🔧";
    if (s.includes("شاغ")) return "🏠";
    if (s.includes("محج")) return "📋";
    if (s.includes("مستأ")) return "✅";
    if (p.room_no) return "🛏️";
    if (p.apartment_no) return "🏬";
    if (p.building_no) return "🏗️";
    return "🏢";
  }

  window.lqPropertyEmoji = propertyVisual;

  function ensureWorkspace() {
    const dash = $("#sec-dashboard");
    if (!dash || $("#lqWorkspace")) return;
    const ws = document.createElement("div");
    ws.id = "lqWorkspace";
    ws.className = "lq-workspace-grid";
    ws.innerHTML = `
      <article class="lq-zone lq-zone-1" id="lqZoneCommands">
        <div class="lq-zone-head"><h3>① لوحة التحكم والأوامر</h3><span>Commands</span></div>
        <div id="lqZoneCommandsBody"></div>
      </article>
      <article class="lq-zone lq-zone-2" id="lqZoneFlow">
        <div class="lq-zone-head"><h3>② مسار العمل التوضيحي</h3><span>يتحدث مع كل إضافة</span></div>
        <div id="lqZoneFlowBody"></div>
      </article>
      <article class="lq-zone lq-zone-3" id="lqZoneToday">
        <div class="lq-zone-head"><h3>③ أعمال اليوم</h3><span>محفوظ على الخادم</span></div>
        <div id="lqZoneTodayBody"></div>
      </article>
      <article class="lq-zone lq-zone-4" id="lqZoneOrg">
        <div class="lq-zone-head"><h3>④ الهيكل الوظيفي</h3><span>اضغط اسم الموظف</span></div>
        <div id="lqZoneOrgBody"></div>
        <div id="lqZoneOrgTools" class="lq-org-tools"></div>
      </article>`;
    const hub = $("#lqHubBoard");
    if (hub) dash.insertBefore(ws, hub);
    else dash.prepend(ws);
    bindTodayForm();
  }

  function renderCommandsZone(k) {
    const host = $("#lqZoneCommandsBody");
    if (!host) return;
    const cmds = (window.DASH_EXEC_COMMANDS || [])
      .filter((c) => typeof canAccessSection === "function" && canAccessSection(c.section))
      .slice(0, 6);
    host.innerHTML = `
      <div class="lq-zone-kpis">
        <div class="lq-zone-kpi"><b>${fmt(k.health || 0)}%</b><small>جاهزية</small></div>
        <div class="lq-zone-kpi"><b>${fmt(k.occupancy || 0)}%</b><small>إشغال</small></div>
        <div class="lq-zone-kpi"><b>${money(k.net || 0)}</b><small>صافي</small></div>
        <div class="lq-zone-kpi"><b>${money(k.overdue || 0)}</b><small>متأخر</small></div>
      </div>
      <div class="lq-cmd-grid">
        ${cmds
          .map(
            (c) =>
              `<button type="button" class="lq-cmd-btn" data-sec="${c.section}" data-act="${c.action || ""}"><i>${c.icon}</i>${esc(c.label)}</button>`
          )
          .join("")}
        <button type="button" class="lq-cmd-btn" onclick="lqToggleHubExpand && lqToggleHubExpand()"><i>📊</i>تحليلات كاملة</button>
      </div>`;
    host.querySelectorAll(".lq-cmd-btn[data-sec]").forEach((btn) => {
      btn.onclick = () => {
        const sec = btn.dataset.sec;
        const act = btn.dataset.act;
        if (typeof dashCommandClick === "function") dashCommandClick(sec, act);
        else if (typeof showSection === "function") showSection(sec);
      };
    });
  }

  function renderOrgZone() {
    const host = $("#lqZoneOrgBody");
    if (!host) return;
    const users = (Jawdah.data && Jawdah.data.users) || [];
    if (!users.length) {
      host.innerHTML = "<p class=\"mini\">جاري تحميل الموظفين…</p>";
      return;
    }
    host.innerHTML = `<div class="lq-org-grid">${users
      .filter((u) => u.active)
      .map((u) => {
        const ic = ROLE_ICON[u.role] || "👤";
        const initial = (u.name || u.username || "?").trim()[0] || "?";
        return `<button type="button" class="lq-org-card" data-uid="${esc(u.id)}" data-role="${esc(u.role)}">
          <div class="avatar-mini">${ic || initial}</div>
          <b>${esc(u.name || u.username)}</b>
          <small>${esc(typeof roleName === "function" ? roleName(u.role) : u.role)}</small>
        </button>`;
      })
      .join("")}</div>`;
    host.querySelectorAll(".lq-org-card").forEach((card) => {
      card.onclick = () => showStaffTools(card.dataset.uid, card.dataset.role, card);
    });
  }

  function showStaffTools(uid, role, cardEl) {
    document.querySelectorAll(".lq-org-card").forEach((c) => c.classList.remove("active"));
    cardEl?.classList.add("active");
    const tools = ROLE_TOOLS[role] || ["dashboard"];
    const host = $("#lqZoneOrgTools");
    if (!host) return;
    const u = (Jawdah.data.users || []).find((x) => x.id === uid);
    host.innerHTML = `<span class="mini" style="margin-right:6px">${esc(u?.name || "")}:</span>${tools
      .map(
        (sec) =>
          `<button type="button" class="ghost" onclick="showSection('${sec}')">${SECTION_LABELS[sec] || sec}</button>`
      )
      .join("")}`;
  }

  function renderFlowZone() {
    const host = $("#lqZoneFlowBody");
    if (!host) return;
    const d = Jawdah.data || {};
    const buildings = new Set((d.properties || []).map((p) => p.building_no).filter(Boolean)).size;
    const apartments = (d.properties || []).filter((p) => p.apartment_no).length;
    const rooms = (d.properties || []).filter((p) => p.room_no).length;
    const clients = (d.clients || []).length;
    const contracts = (d.contracts || []).length;
    const invoices = (d.invoices || []).length;
    const paid = (d.invoices || []).filter((i) => Number(i.paid_amount || 0) > 0).length;

    const steps = [
      { emoji: "🏗️", label: "بناية", val: buildings || (d.properties || []).length },
      { emoji: "🏬", label: "شقة", val: apartments },
      { emoji: "🛏️", label: "غرفة", val: rooms },
      { emoji: "👥", label: "عميل", val: clients },
      { emoji: "📄", label: "عقد", val: contracts },
      { emoji: "🧾", label: "فاتورة", val: invoices },
      { emoji: "💰", label: "تحصيل", val: paid },
    ];

    host.innerHTML = `
      <div class="lq-flow-pipeline" id="lqFlowPipeline">
        <div class="lq-flow-energy"><span class="lq-flow-energy-dot" id="lqFlowEnergyDot"></span></div>
        <div class="lq-flow-track">${steps
      .map((s, i) => {
        const arrow =
          i < steps.length - 1
            ? `<span class="lq-flow-arrow" data-after="${i}">→</span>`
            : "";
        return `<div class="lq-flow-step" data-step="${i}"><i>${s.emoji}</i><b>${fmt(s.val)}</b><small>${s.label}</small></div>${arrow}`;
      })
      .join("")}</div>
      </div>
      <div id="lqFlowToast" class="lq-flow-toast hidden" role="status"></div>
      <p class="mini">آخر العقارات: ${(d.properties || [])
        .slice(-4)
        .map((p) => `${propertyVisual(p)} ${esc(propertyLabel(p))}`)
        .join(" · ") || "—"}</p>`;
  }

  let todayItemsCache = [];
  let todayMigrated = false;

  function todayKey() {
    const uid = Jawdah.user?.id || Jawdah.user?.username || "guest";
    return `lq_today_${uid}_${today()}`;
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("تعذر قراءة الملف"));
      reader.readAsDataURL(file);
    });
  }

  async function collectTodayFiles(input) {
    const files = [];
    if (!input?.files?.length) return files;
    for (const f of input.files) {
      if (f.size > 600000) {
        toastOk?.("تخطي ملف كبير: " + f.name);
        continue;
      }
      try {
        const image = await readFileAsDataUrl(f);
        files.push({ name: f.name, type: f.type, image });
      } catch (e) {
        toastErr?.(e);
      }
    }
    return files;
  }

  async function fetchTodayEntries() {
    const res = await api("work_journal/today");
    todayItemsCache = res.items || [];
    return todayItemsCache;
  }

  async function migrateLocalTodayOnce() {
    if (todayMigrated) return;
    todayMigrated = true;
    const key = todayKey();
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const items = JSON.parse(raw);
      if (!Array.isArray(items) || !items.length) {
        localStorage.removeItem(key);
        return;
      }
      const existing = await fetchTodayEntries();
      if (existing.length) {
        localStorage.removeItem(key);
        return;
      }
      for (const item of items) {
        const files = (item.files || [])
          .map((f) => {
            if (f?.preview) return { name: f.name, type: f.type, image: f.preview };
            return null;
          })
          .filter(Boolean);
        await api("work_journal", {
          method: "POST",
          body: JSON.stringify({ text: item.text, work_date: today(), files }),
        });
      }
      localStorage.removeItem(key);
      toast?.("تم نقل أعمال اليوم من الجهاز إلى الخادم");
    } catch (e) {
      /* migration is best-effort */
    }
  }

  function todayAttachmentsHtml(files) {
    if (!files?.length) return "";
    return `<div class="lq-today-attachments">${files
      .map((f) => {
        const url = f.url || (f.preview && String(f.preview).startsWith("data:") ? f.preview : "");
        if (f.type?.startsWith("image/") && url) {
          return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer"><img src="${esc(url)}" alt="${esc(f.name || "")}"></a>`;
        }
        if (url) {
          return `<a class="mini" href="${esc(url)}" target="_blank" rel="noopener noreferrer">📎 ${esc(f.name || "ملف")}</a>`;
        }
        return `<small>${esc(f.name || "ملف")}</small>`;
      })
      .join("")}</div>`;
  }

  function renderTodayList() {
    const list = $("#lqTodayList");
    if (!list) return;
    const items = todayItemsCache;
    list.innerHTML = items.length
      ? items
          .map(
            (x) =>
              `<div class="lq-today-item"><div class="lq-today-item-top"><b>${esc(x.text)}</b><button type="button" class="ghost lq-today-del" data-id="${esc(x.id)}">حذف</button></div>${todayAttachmentsHtml(x.attachments)}<small class="mini">${esc((x.created_at || "").slice(11, 16) || "")}</small></div>`
          )
          .join("")
      : "<p class=\"mini\">لا مهام مسجلة اليوم — اكتب ما أنجزته أدناه</p>";
    list.querySelectorAll(".lq-today-del").forEach((btn) => {
      btn.onclick = () => deleteTodayEntry(btn.dataset.id);
    });
  }

  async function refreshTodayList() {
    // Mounted on DOMContentLoaded, so the login screen may still be up; the
    // dashboard render after sign-in calls back in with a usable session.
    if (!signedIn()) return;
    const sync = $("#lqTodaySync");
    if (sync) sync.textContent = "جاري التحميل…";
    try {
      await migrateLocalTodayOnce();
      await fetchTodayEntries();
      renderTodayList();
      if (sync) sync.textContent = "☁️ متزامن مع الخادم";
    } catch (e) {
      if (sync) sync.textContent = "تعذر التحميل";
      toastErr?.(e);
    }
  }

  async function deleteTodayEntry(id) {
    if (!id || !confirm("حذف هذا السجل من أعمال اليوم؟")) return;
    try {
      await api(`work_journal/${id}`, { method: "DELETE" });
      todayItemsCache = todayItemsCache.filter((x) => x.id !== id);
      renderTodayList();
      toast?.("تم الحذف");
    } catch (e) {
      toastErr?.(e);
    }
  }

  function bindTodayForm() {
    const host = $("#lqZoneTodayBody");
    if (!host || host.dataset.bound) return;
    host.dataset.bound = "1";
    host.innerHTML = `
      <div class="lq-today-form">
        <p id="lqTodaySync" class="mini">☁️ أعمال اليوم على الخادم</p>
        <textarea id="lqTodayText" placeholder="ما أنجزته اليوم…"></textarea>
        <input id="lqTodayFiles" type="file" accept="image/*,.pdf,.doc,.docx" multiple>
        <button type="button" class="gold-btn" id="lqTodaySave">حفظ أعمال اليوم</button>
        <div id="lqTodayPreview" class="lq-today-files"></div>
        <div id="lqTodayList" class="lq-today-list"></div>
      </div>`;
    $("#lqTodaySave").onclick = async () => {
      const text = $("#lqTodayText").value.trim();
      if (!text) return;
      const input = $("#lqTodayFiles");
      const btn = $("#lqTodaySave");
      btn.disabled = true;
      try {
        const files = await collectTodayFiles(input);
        await api("work_journal", {
          method: "POST",
          body: JSON.stringify({ text, work_date: today(), files }),
        });
        $("#lqTodayText").value = "";
        if (input) input.value = "";
        $("#lqTodayPreview").innerHTML = "";
        await refreshTodayList();
        toast?.("تم حفظ أعمال اليوم على الخادم");
        pulseFlowStep(6);
      } catch (e) {
        toastErr?.(e);
      } finally {
        btn.disabled = false;
      }
    };
    $("#lqTodayFiles")?.addEventListener("change", (e) => {
      const prev = $("#lqTodayPreview");
      if (!prev) return;
      prev.innerHTML = Array.from(e.target.files || [])
        .map((f) => `<div class="lq-today-file">${f.type.startsWith("image/") ? "🖼" : "📎"}<br>${esc(f.name.slice(0, 8))}</div>`)
        .join("");
    });
    refreshTodayList();
  }

  function pulseFlowStep(idx) {
    const step = document.querySelector(`.lq-flow-step[data-step="${idx}"]`);
    if (step) {
      step.classList.add("pulse");
      setTimeout(() => step.classList.remove("pulse"), 1400);
    }
  }

  window.lqPulseWorkflow = pulseFlowStep;

  function renderWorkspace() {
    ensureWorkspace();
    if (typeof dashKpis !== "function") return;
    const k = dashKpis();
    renderCommandsZone(k);
    renderOrgZone();
    renderFlowZone();
    if (todayItemsCache.length || $("#lqTodayList")) refreshTodayList();
  }

  function init() {
    document.body.classList.add("lq-workspace-mode");
    ensureWorkspace();

    const origRender = window.renderDashboard;
    if (origRender) {
      window.renderDashboard = function () {
        origRender.apply(this, arguments);
        renderWorkspace();
      };
    }

    const origRenderAll = window.renderAll;
    // renderAll doesn't exist as window - it's function renderAll in app.js
    // Hook after load via renderDashboard

    if ($("#sec-dashboard")?.classList.contains("active")) {
      setTimeout(renderWorkspace, 100);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.lqRenderWorkspace = renderWorkspace;
})();
