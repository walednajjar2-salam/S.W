/* Launch Quality · Hub Command Center (Model B) */
(function () {
  const $ = (s) => document.querySelector(s);

  function initBody() {
    document.body.classList.add("lq-hub-mode", "lq-card-mode", "lq-cinematic-bi", "lq-hub-expanded");
    // Always show full dashboard functions (ignore stale localStorage cache)
    localStorage.setItem("lq_hub_expanded", "1");
  }

  function hubTiles(k) {
    const tiles = [
      {
        id: "properties",
        icon: "🏢",
        label: "العقارات",
        value: () => fmt(k.properties),
        sub: "محفظة الوحدات",
      },
      {
        id: "clients",
        icon: "👥",
        label: "العملاء",
        value: () => fmt((Jawdah.data.clients || []).length),
        sub: "سجل العملاء",
      },
      {
        id: "contracts",
        icon: "📄",
        label: "العقود",
        value: () =>
          fmt(
            (Jawdah.data.contracts || []).filter(
              (c) => String(c.status || "").toLowerCase() === "active"
            ).length
          ),
        sub: "عقود نشطة",
      },
      {
        id: "invoices",
        icon: "🧾",
        label: "الفواتير",
        value: () => money(k.overdue || 0),
        sub: "ذمم متأخرة",
        alert: Number(k.overdue || 0) > 0,
      },
      {
        id: "receivables",
        icon: "💸",
        label: "التحصيل الذكي",
        value: () => money(k.overdue || 0),
        sub: "أعمار وتذكير",
        alert: Number(k.overdue || 0) > 0,
      },
      {
        id: "maintenance",
        icon: "🔧",
        label: "الصيانة",
        value: () => fmt(k.maintenance || 0),
        sub: "طلبات مفتوحة",
      },
      {
        id: "reports",
        icon: "📊",
        label: "التقارير",
        value: () => "BI",
        sub: "تنفيذي + مالي",
        tone: "violet",
      },
      {
        id: "messages",
        icon: "📨",
        label: "الرسائل",
        value: () => fmt((Jawdah.data.messages || []).length),
        sub: "تنبيهات ومراسلة",
      },
      {
        id: "backup",
        icon: "☁️",
        label: "نسخ احتياطي",
        value: () => "☁",
        sub: "حماية البيانات",
      },
    ];
    if (typeof canManageUsersSection === "function" ? canManageUsersSection() : false) {
      tiles.push({
        id: "users",
        icon: "🛡️",
        label: "المستخدمين",
        value: () => fmt((Jawdah.data.users || []).length),
        sub: "صلاحيات ودخول",
      });
    }
    return tiles.filter((t) => {
      if (typeof canAccessSection === "function" && !canAccessSection(t.id)) return false;
      return uiAllowedSection(t.id);
    });
  }

  function renderHubBoard(k) {
    const host = $("#lqHubBoard");
    if (!host) return;
    const name = displayUserName(Jawdah.user) || DISPLAY_OWNER_NAME;
    const greeting = dashGreeting();
    const coll = k.billed
      ? Math.round((Number(k.paid || 0) / Number(k.billed || 1)) * 100)
      : 0;
    const expanded = document.body.classList.contains("lq-hub-expanded");

    host.innerHTML = `
      <div class="lq-hub-hero lq-cine-scan">
        <div class="lq-hub-hero-inner">
          <span class="lq-hub-pill">🌟 Data Insights · Command Hub</span>
          <h2>${greeting}، ${htmlEscape(name)}</h2>
          <p>مركز القيادة — اختر منطقة العمل أو افتح التحليلات الكاملة</p>
        </div>
        <div class="lq-hub-hero-kpis">
          <div class="lq-hub-kpi"><b class="lq-kpi-pulse">${fmt(k.occupancy || 0)}%</b><span>إشغال</span></div>
          <div class="lq-hub-kpi"><b class="lq-kpi-pulse">${fmt(coll)}%</b><span>تحصيل</span></div>
          <div class="lq-hub-kpi"><b class="lq-kpi-pulse">${money(k.net || 0)}</b><span>صافي</span></div>
          <div class="lq-hub-kpi"><b class="lq-kpi-pulse">${fmt(k.health || 0)}%</b><span>جاهزية</span></div>
        </div>
      </div>
      <div class="lq-hub-grid">
        ${hubTiles(k)
          .map(
            (t, i) => `
          <button type="button" class="lq-hub-tile lq-cine-tile${t.alert ? " is-alert" : ""}" data-tone="${t.tone || "cyan"}" style="--lq-i:${i}" onclick="showSection('${t.id}')">
            <span class="lq-hub-tile-scan" aria-hidden="true"></span>
            <span class="lq-hub-tile-icon">${t.icon}</span>
            <span class="lq-hub-tile-val lq-kpi-pulse">${t.value()}</span>
            <strong>${htmlEscape(t.label)}</strong>
            <small>${htmlEscape(t.sub)}</small>
          </button>`
          )
          .join("")}
      </div>
      <div class="lq-hub-actions">
        <button type="button" class="lq-hub-expand-btn gold-btn" id="lqHubExpandBtn">${expanded ? "⬆ إخفاء التحليلات الكاملة" : "📊 Data Insights الكاملة"}</button>
      </div>`;

    const btn = $("#lqHubExpandBtn");
    if (btn) btn.onclick = toggleHubExpand;
  }

  function toggleHubExpand() {
    const expanded = !document.body.classList.contains("lq-hub-expanded");
    document.body.classList.toggle("lq-hub-expanded", expanded);
    localStorage.setItem("lq_hub_expanded", expanded ? "1" : "0");
    const btn = $("#lqHubExpandBtn");
    if (btn) {
      btn.textContent = expanded
        ? "⬆ إخفاء التحليلات الكاملة"
        : "📊 Data Insights الكاملة";
    }
    if (expanded) {
      setTimeout(() => scheduleDrawCharts(), 120);
      const wrap = $("#lqCockpitWrap");
      if (wrap) wrap.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  window.lqRenderHubBoard = renderHubBoard;
  window.lqToggleHubExpand = toggleHubExpand;

  function hookDashboard() {
    initBody();
    const orig = window.renderDashboard;
    if (!orig) return;
    window.renderDashboard = function () {
      orig.apply(this, arguments);
      try {
        renderHubBoard(dashKpis());
      } catch (e) {}
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hookDashboard);
  } else {
    hookDashboard();
  }
})();
