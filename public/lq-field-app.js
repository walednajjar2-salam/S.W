(function () {
  "use strict";

  const CACHE_KEY = "lq_field_sync_cache";
  const SYNC_INTERVAL_MS = 3 * 60 * 1000;
  let syncTimer = null;
  let barEl = null;

  function loadCache() {
    try {
      return JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
    } catch (_e) {
      return null;
    }
  }

  function saveCache(sync) {
    if (!sync) return;
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(sync));
    } catch (_e) {}
  }

  function parseBootUrl() {
    const q = new URLSearchParams(location.search);
    if (q.get("field") === "1" && window.Jawdah) {
      Jawdah.fieldMode = true;
      localStorage.setItem("jawdah_field_mode", "1");
    }
    const section = (q.get("section") || "").trim();
    if (section) window.__lqBootSection = section;
  }

  function ensureBar() {
    if (barEl) return barEl;
    const host = document.getElementById("staffFieldPanel");
    if (!host) return null;
    barEl = document.createElement("div");
    barEl.id = "lqFieldBar";
    barEl.className = "lq-field-bar";
    host.parentNode.insertBefore(barEl, host);
    return barEl;
  }

  function updateBar(sync, offline) {
    const bar = ensureBar();
    if (!bar || !window.Jawdah || !Jawdah.fieldMode) {
      if (bar) bar.remove();
      barEl = null;
      return;
    }
    const user = Jawdah.user || {};
    const m = sync || loadCache();
    const synced = m && m.synced_at ? m.synced_at.slice(0, 16) : "—";
    const maint = (m && m.maintenance_open) ? m.maintenance_open.length : 0;
    const overdue = (m && m.overdue_invoices) ? m.overdue_invoices.length : 0;
    const approvals = (m && m.pending_approvals) ? m.pending_approvals : 0;
    bar.classList.toggle("lq-field-offline", !!offline);
    bar.innerHTML =
      '<div class="lq-field-bar-title">🧰 تطبيق الميدان</div>' +
      '<div class="lq-field-bar-meta">' +
      (user.name || user.username || "موظف") +
      " · v" +
      (m && m.app_version ? m.app_version : "2.0.0") +
      (offline ? " · بيانات محفوظة" : "") +
      "</div>" +
      '<div class="lq-field-bar-meta">مزامنة: ' +
      synced +
      " · صيانة " +
      maint +
      " · متأخرات " +
      overdue +
      (approvals ? " · اعتمادات " + approvals : "") +
      "</div>" +
      '<div class="lq-field-bar-actions">' +
      '<button type="button" class="gold-btn" onclick="LQ_FIELD_APP.syncNow()">مزامنة</button>' +
      '<button type="button" class="ghost" onclick="LQ_STAFF_FIELD.enableNotifications()">إشعارات</button>' +
      (window.LQ_PWA && LQ_PWA.canInstall && LQ_PWA.canInstall()
        ? '<button type="button" class="ghost" onclick="LQ_PWA.showInstallButton()">تثبيت</button>'
        : "") +
      '<button type="button" class="ghost" onclick="toggleFieldMode()">وضع كامل</button>' +
      "</div>";
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(bar);
  }

  function onFieldModeChange() {
    document.body.classList.toggle("lq-field-app-active", !!(window.Jawdah && Jawdah.fieldMode));
    if (!Jawdah || !Jawdah.fieldMode) {
      if (barEl) {
        barEl.remove();
        barEl = null;
      }
      stopPeriodicSync();
      return;
    }
    updateBar(loadCache(), false);
    startPeriodicSync();
  }

  function startPeriodicSync() {
    stopPeriodicSync();
    syncTimer = window.setInterval(function () {
      if (!Jawdah || !Jawdah.fieldMode) return;
      syncNow(true);
    }, SYNC_INTERVAL_MS);
  }

  function stopPeriodicSync() {
    if (syncTimer) {
      window.clearInterval(syncTimer);
      syncTimer = null;
    }
  }

  async function syncNow(silent) {
    try {
      const res = await api("staff/sync");
      saveCache(res.sync);
      updateBar(res.sync, false);
      if (window.LQ_STAFF_FIELD) window.LQ_STAFF_FIELD.renderPanel(res.sync);
      if (!silent && typeof toast === "function") toast("تمت مزامنة بيانات الميدان");
      if (window.LQ_STAFF_FIELD) window.LQ_STAFF_FIELD.maybeNotify(res.sync);
      if (typeof loadAll === "function" && !silent) await loadAll();
      return res.sync;
    } catch (e) {
      const cached = loadCache();
      if (cached) {
        updateBar(cached, true);
        if (window.LQ_STAFF_FIELD) window.LQ_STAFF_FIELD.renderPanel(cached);
        if (!silent && typeof toastNotice === "function") toastNotice("عرض آخر مزامنة — الشبكة غير متاحة");
      } else if (!silent && typeof toastErr === "function") toastErr(e);
      throw e;
    }
  }

  async function afterBoot() {
    if (!Jawdah || !Jawdah.fieldMode) return;
    document.body.classList.add("lq-field-app-active");
    onFieldModeChange();
    try {
      await syncNow(true);
    } catch (_e) {
      const cached = loadCache();
      if (cached && window.LQ_STAFF_FIELD) window.LQ_STAFF_FIELD.renderPanel(cached);
    }
    if (window.LQ_PWA && typeof LQ_PWA.showInstallButton === "function") {
      window.setTimeout(function () {
        if (LQ_PWA.canInstall && LQ_PWA.canInstall()) LQ_PWA.showInstallButton();
      }, 2500);
    }
  }

  window.LQ_FIELD_APP = {
    parseBootUrl,
    afterBoot,
    onFieldModeChange,
    syncNow,
    loadCache,
    saveCache,
  };

  document.addEventListener("DOMContentLoaded", parseBootUrl);
})();
