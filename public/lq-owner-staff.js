(function () {
  "use strict";

  let cache = null;
  let filterUser = "";
  let filterDays = 14;

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function roleLabel(r) {
    const m = {
      owner: "مالك",
      admin: "مدير",
      accountant: "محاسب",
      operations: "تشغيل",
      maintenance: "صيانة",
      viewer: "عرض",
    };
    return m[r] || r || "—";
  }

  function canView() {
    if (typeof isPrimaryOwnerUser === "function") return isPrimaryOwnerUser();
    const uname = String(Jawdah.user?.username || "").trim().toLowerCase();
    return ["yaqoub", "yaqoub.khasibi", "waleed", "waleed.najjar"].includes(uname);
  }

  async function load() {
    const res = await api("owner/staff_activity?days=" + encodeURIComponent(filterDays));
    cache = res.activity;
    return cache;
  }

  function renderStaffCards(data) {
    const staff = (data.staff || []).filter(function (u) {
      return !filterUser || u.username === filterUser || u.id === filterUser;
    });
    return staff
      .map(function (u) {
        return (
          '<article class="lq-owner-staff-card">' +
          "<h4>" +
          esc(u.name || u.username) +
          "</h4>" +
          '<p class="mini">' +
          esc(u.username) +
          " · " +
          esc(roleLabel(u.role)) +
          "</p>" +
          '<div class="stats">' +
          '<span class="badge">يوميات: ' +
          (u.journal_entries || 0) +
          "</span>" +
          '<span class="badge">إجراءات: ' +
          (u.audit_actions || 0) +
          "</span>" +
          '<span class="badge">آخر دخول: ' +
          esc((u.last_login || "—").slice(0, 16)) +
          "</span>" +
          "</div></article>"
        );
      })
      .join("");
  }

  function renderJournalFeed(data) {
    const items = (data.journals || []).filter(function (j) {
      return !filterUser || j.user_id === filterUser || j.username === filterUser;
    });
    if (!items.length) return '<p class="mini">لا يوجد عمل مسجّل في الفترة المحددة</p>';
    return (
      '<div class="lq-owner-feed">' +
      items
        .slice(0, 80)
        .map(function (j) {
          const files = (j.attachments || []).length;
          return (
            '<div class="lq-owner-feed-item">' +
            '<div class="head"><b>' +
            esc(j.user_name || j.username) +
            "</b><span>" +
            esc(j.work_date) +
            " · " +
            esc((j.created_at || "").slice(11, 16)) +
            "</span></div>" +
            "<p>" +
            esc(j.text) +
            "</p>" +
            (files
              ? '<div class="tags"><span class="tag">📎 ' + files + " مرفق</span></div>"
              : "") +
            "</div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderAuditFeed(data) {
    const items = (data.audits || []).filter(function (a) {
      return !filterUser || a.username === filterUser;
    });
    if (!items.length) return '<p class="mini">لا إجراءات في السجل</p>';
    return (
      '<div class="lq-owner-feed">' +
      items
        .slice(0, 60)
        .map(function (a) {
          return (
            '<div class="lq-owner-feed-item">' +
            '<div class="head"><b>' +
            esc(a.username) +
            "</b><span>" +
            esc((a.created_at || "").slice(0, 16)) +
            "</span></div>" +
            "<p>" +
            esc(a.action) +
            " · " +
            esc(a.entity) +
            (a.details ? " — " + esc(a.details) : "") +
            "</p></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderPage(data) {
    const host = document.getElementById("ownerStaffBox");
    if (!host) return;
    if (!canView()) {
      host.innerHTML = '<p class="mini">هذه الصفحة للمالك فقط</p>';
      return;
    }
    const k = data.summary || {};
    const staffOpts = (data.staff || [])
      .map(function (u) {
        return (
          '<option value="' +
          esc(u.username) +
          '">' +
          esc(u.name || u.username) +
          "</option>"
        );
      })
      .join("");
    host.innerHTML =
      '<div class="lq-owner-staff-page">' +
      '<div class="lq-owner-hero">' +
      "<h3>👑 لوحة المالك — متابعة عمل الموظفين</h3>" +
      '<p class="mini">عرض كامل: يوميات العمل، الإجراءات على النظام، وآخر نشاط لكل موظف</p>' +
      '<div class="lq-owner-kpi-row" style="margin-top:14px">' +
      '<div class="lq-owner-kpi"><b>' +
      (k.staff_count || 0) +
      "</b><span>موظف نشط</span></div>" +
      '<div class="lq-owner-kpi"><b>' +
      (k.journal_today || 0) +
      "</b><span>يوميات اليوم</span></div>" +
      '<div class="lq-owner-kpi"><b>' +
      (k.audit_today || 0) +
      "</b><span>إجراءات اليوم</span></div>" +
      '<div class="lq-owner-kpi"><b>' +
      (k.active_today || 0) +
      "</b><span>موظفون نشطون اليوم</span></div>" +
      "</div></div>" +
      '<div class="lq-owner-toolbar">' +
      '<label>الموظف <select id="lqOwnerFilterUser"><option value="">الكل</option>' +
      staffOpts +
      "</select></label>" +
      '<label>الفترة <select id="lqOwnerFilterDays"><option value="7">7 أيام</option><option value="14" selected>14 يوم</option><option value="30">30 يوم</option></select></label>' +
      '<button type="button" class="gold-btn" onclick="LQ_OWNER_STAFF.refresh()">تحديث</button>' +
      "</div>" +
      '<div class="card"><h4>👥 ملخص الموظفين</h4><div class="lq-owner-staff-grid">' +
      renderStaffCards(data) +
      "</div></div>" +
      '<div class="card"><h4>📝 عمل اليوم / اليوميات</h4>' +
      renderJournalFeed(data) +
      "</div>" +
      '<div class="card"><h4>📋 سجل الإجراءات</h4>' +
      renderAuditFeed(data) +
      "</div></div>";

    const uSel = document.getElementById("lqOwnerFilterUser");
    const dSel = document.getElementById("lqOwnerFilterDays");
    if (uSel) {
      uSel.value = filterUser;
      uSel.onchange = function () {
        filterUser = uSel.value;
        if (cache) renderPage(cache);
      };
    }
    if (dSel) {
      dSel.value = String(filterDays);
      dSel.onchange = function () {
        filterDays = parseInt(dSel.value, 10) || 14;
        refresh();
      };
    }
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
  }

  async function refresh() {
    const host = document.getElementById("ownerStaffBox");
    if (host) host.innerHTML = '<p class="mini">جاري التحميل…</p>';
    try {
      const data = await load();
      renderPage(data);
      if (typeof toast === "function") toast("تم تحديث متابعة الموظفين");
    } catch (e) {
      if (host) host.innerHTML = '<p class="mini">تعذر التحميل</p>';
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function render() {
    if (!canView()) return;
    if (cache) {
      renderPage(cache);
      return;
    }
    await refresh();
  }

  window.LQ_OWNER_STAFF = { render, refresh, canView };
})();
