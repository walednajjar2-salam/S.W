(function () {
  "use strict";

  let lastSync = null;

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function isFieldRole() {
    const r = window.Jawdah && Jawdah.user && Jawdah.user.role;
    return r === "maintenance" || r === "operations" || r === "viewer";
  }

  function isMobile() {
    return window.matchMedia("(max-width: 900px)").matches || /Android|iPhone|iPad/i.test(navigator.userAgent);
  }

  function canQuickMaint() {
    if (typeof canWriteSection === "function") return canWriteSection("maintenance");
    const role = Jawdah && Jawdah.user && Jawdah.user.role;
    return role === "admin" || role === "maintenance" || role === "operations";
  }

  function explainHtml() {
    return `
      <div class="card lq-staff-guide">
        <h3>📱 تطبيق الميدان — المرحلة 10</h3>
        <p class="mini">وضع الميدان يربط الجوال مع السيرفر: صيانة سريعة، عقود، اعتمادات، ومزامنة مع تخزين مؤقت عند انقطاع الشبكة.</p>
        <ul class="check-list">
          <li><strong>مزامنة</strong> — API مباشر + نسخة محفوظة offline</li>
          <li><strong>طلب صيانة</strong> — إنشاء من الميدان بدون نموذج كامل</li>
          <li><strong>روابط PWA</strong> — <code>?field=1&section=maintenance</code></li>
        </ul>
        <div class="toolbar" style="flex-wrap:wrap;gap:8px;margin-top:10px">
          <button type="button" class="gold-btn" onclick="LQ_STAFF_FIELD.syncNow()">مزامنة الآن</button>
          <button type="button" class="ghost" onclick="LQ_STAFF_FIELD.enableNotifications()">تفعيل الإشعارات</button>
          <a class="ghost" href="/download.html" target="_blank" rel="noopener">تحميل APK / Windows</a>
        </div>
      </div>`;
  }

  function quickMaintFormHtml(sync) {
    if (!canQuickMaint()) return "";
    const props = (sync && sync.field_properties) || [];
    const opts = props
      .map(
        (p) =>
          '<option value="' +
          esc(p.id) +
          '">' +
          esc(p.name || p.id) +
          (p.building_no ? " · " + esc(p.building_no) : "") +
          "</option>"
      )
      .join("");
    if (!opts) return '<p class="mini">لا عقارات للاختيار — أضف مشروعاً أولاً</p>';
    return (
      '<div class="lq-field-quick-form">' +
      '<label>عقار<select id="lqQuickMaintProp">' +
      opts +
      "</select></label>" +
      '<label>الوصف<input id="lqQuickMaintTitle" type="text" placeholder="مثال: تكييف لا يعمل"></label>' +
      '<label>الأولوية<select id="lqQuickMaintPri"><option>High</option><option selected>Medium</option><option>Low</option></select></label>' +
      '<label>ملاحظات<textarea id="lqQuickMaintNotes" rows="2" placeholder="تفاصيل من الميدان"></textarea></label>' +
      '<button type="button" class="gold-btn" onclick="LQ_STAFF_FIELD.submitQuickMaint()">إرسال طلب صيانة</button>' +
      "</div>"
    );
  }

  function renderPanel(sync) {
    const host = document.getElementById("staffFieldPanel");
    if (!host) return;
    if (!window.Jawdah || !Jawdah.fieldMode) {
      host.innerHTML = "";
      return;
    }
    const m = sync || lastSync || (window.LQ_FIELD_APP && LQ_FIELD_APP.loadCache && LQ_FIELD_APP.loadCache());
    if (!m) {
      host.innerHTML = explainHtml() + '<p class="mini">اضغط «مزامنة الآن» لتحميل بيانات الميدان</p>';
      return;
    }
    lastSync = m;
    const maint = m.maintenance_open || [];
    const overdue = m.overdue_invoices || [];
    const contracts = m.contracts_watch || [];
    const maintHtml = maint
      .slice(0, 8)
      .map(function (x) {
        return (
          '<div class="saas-task-item"><div><b>' +
          esc(x.title || "صيانة") +
          "</b><p>" +
          esc(x.property_name || x.property_id) +
          " · " +
          esc(x.priority) +
          "</p></div>" +
          '<button type="button" class="ghost" onclick="LQ_STAFF_FIELD.closeMaint(\'' +
          esc(x.id) +
          "')\">إغلاق</button>" +
          '<button type="button" class="ghost" onclick="LQ_STAFF_FIELD.progressMaint(\'' +
          esc(x.id) +
          "')\">قيد التنفيذ</button></div>"
        );
      })
      .join("");
    const invHtml = overdue
      .slice(0, 6)
      .map(function (x) {
        const rem = typeof money === "function" ? money(x.remaining) : x.remaining;
        return (
          '<div class="saas-task-item"><div><b>' +
          esc(x.invoice_no) +
          "</b><p>" +
          esc(x.client_name || "") +
          " · " +
          rem +
          "</p></div>" +
          '<button type="button" class="ghost" onclick="showSection(\'invoices\')">فتح</button></div>'
        );
      })
      .join("");
    const contractHtml = contracts
      .slice(0, 6)
      .map(function (x) {
        return (
          '<div class="saas-task-item lq-field-contracts"><div><b>' +
          esc(x.contract_no || x.id) +
          "</b><p>" +
          esc(x.client_id || "") +
          " · انتهاء " +
          esc((x.end_date || "").slice(0, 10)) +
          "</p><small>" +
          esc(x.status || "") +
          "</small></div>" +
          '<button type="button" class="ghost" onclick="showSection(\'contracts\')">عقود</button></div>'
        );
      })
      .join("");
    const appr = m.pending_approvals || 0;
    host.innerHTML =
      explainHtml() +
      '<div class="status-line"><span class="badge">v' +
      esc(m.app_version || "2.0.0") +
      "</span><span class=\"badge\">مزامنة: " +
      esc((m.synced_at || "").slice(0, 16)) +
      "</span><span class=\"badge overdue\">صيانة: " +
      maint.length +
      "</span><span class=\"badge\">متأخرات: " +
      overdue.length +
      "</span>" +
      (appr ? '<span class="badge">اعتمادات: ' + appr + "</span>" : "") +
      "</div>" +
      '<div class="card" style="margin-top:12px"><h4>➕ طلب صيانة سريع</h4>' +
      quickMaintFormHtml(m) +
      "</div>" +
      '<div class="card" style="margin-top:12px"><h4>🔧 صيانة مفتوحة</h4>' +
      (maintHtml || '<p class="mini">لا طلبات</p>') +
      "</div>" +
      '<div class="card" style="margin-top:12px"><h4>🧾 فواتير متأخرة</h4>' +
      (invHtml || '<p class="mini">لا متأخرات</p>') +
      "</div>" +
      '<div class="card" style="margin-top:12px"><h4>📄 عقود للمتابعة</h4>' +
      (contractHtml || '<p class="mini">لا عقود نشطة</p>') +
      "</div>";
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
  }

  async function syncNow() {
    if (window.LQ_FIELD_APP && typeof LQ_FIELD_APP.syncNow === "function") {
      return LQ_FIELD_APP.syncNow(false);
    }
    try {
      const res = await api("staff/sync");
      lastSync = res.sync;
      if (window.LQ_FIELD_APP && LQ_FIELD_APP.saveCache) LQ_FIELD_APP.saveCache(lastSync);
      renderPanel(lastSync);
      if (typeof toast === "function") toast("تمت مزامنة بيانات الميدان");
      maybeNotify(lastSync);
      if (typeof loadAll === "function") await loadAll();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function maybeNotify(sync) {
    if (!sync || !("Notification" in window) || Notification.permission !== "granted") return;
    const n = (sync.overdue_invoices || []).length;
    const m = (sync.maintenance_open || []).length;
    if (n > 0) {
      try {
        new Notification("Launch Quality — متأخرات", { body: n + " فاتورة متأخرة", tag: "lq-overdue" });
      } catch (_e) {}
    }
    if (m > 0) {
      try {
        new Notification("Launch Quality — صيانة", { body: m + " طلب صيانة مفتوح", tag: "lq-maint" });
      } catch (_e) {}
    }
  }

  async function enableNotifications() {
    if (!("Notification" in window)) {
      if (typeof toastNotice === "function") toastNotice("المتصفح لا يدعم الإشعارات");
      return;
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") {
      if (typeof toastNotice === "function") toastNotice("لم يتم منح إذن الإشعارات");
      return;
    }
    try {
      await api("staff/push_register", {
        method: "POST",
        body: JSON.stringify({
          platform: /android/i.test(navigator.userAgent) ? "android" : "web",
          push_token: (Jawdah.user && Jawdah.user.id) + "-" + Date.now(),
          device_label: navigator.userAgent.slice(0, 160),
        }),
      });
      if (typeof toast === "function") toast("تم تفعيل الإشعارات وتسجيل الجهاز");
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function updateMaint(id, status) {
    if (!id) return;
    try {
      await api("staff/maintenance_update", {
        method: "POST",
        body: JSON.stringify({ maintenance_id: id, status }),
      });
      if (typeof toast === "function") toast("تم تحديث الصيانة");
      await syncNow();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function submitQuickMaint() {
    const prop = document.getElementById("lqQuickMaintProp");
    const titleEl = document.getElementById("lqQuickMaintTitle");
    const priEl = document.getElementById("lqQuickMaintPri");
    const notesEl = document.getElementById("lqQuickMaintNotes");
    if (!prop || !prop.value) {
      if (typeof toastNotice === "function") toastNotice("اختر عقاراً");
      return;
    }
    try {
      await api("staff/quick_maintenance", {
        method: "POST",
        body: JSON.stringify({
          property_id: prop.value,
          title: (titleEl && titleEl.value) || "طلب صيانة من الميدان",
          priority: (priEl && priEl.value) || "Medium",
          notes: (notesEl && notesEl.value) || "من تطبيق الميدان",
        }),
      });
      if (typeof toast === "function") toast("تم إنشاء طلب الصيانة");
      if (titleEl) titleEl.value = "";
      if (notesEl) notesEl.value = "";
      await syncNow();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function closeMaint(id) {
    updateMaint(id, "Closed");
  }
  function progressMaint(id) {
    updateMaint(id, "In Progress");
  }

  function enhanceFieldGrid() {
    const host = document.getElementById("fieldModeGrid");
    if (!host || !Jawdah.fieldMode) return;
    const extra = [
      { icon: "📲", label: "مزامنة", go: "", fn: "LQ_FIELD_APP.syncNow()" },
      { icon: "➕", label: "طلب صيانة", go: "maintenance", fn: "" },
      { icon: "📥", label: "تحميل", go: "", fn: "window.open('/download.html','_blank')" },
      { icon: "📄", label: "عقود", go: "contracts", fn: "" },
      { icon: "✅", label: "اعتمادات", go: "approvals", fn: "" },
      { icon: "🔔", label: "تنبيهات", go: "messages", fn: "" },
    ];
    extra.forEach(function (x) {
      if (x.go && typeof canAccessSection === "function" && !canAccessSection(x.go)) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "field-mode-card saas-glass";
      if (x.fn) btn.setAttribute("onclick", x.fn);
      else btn.onclick = function () {
        showSection(x.go);
      };
      btn.innerHTML = "<span>" + x.icon + "</span><b>" + x.label + "</b>";
      host.appendChild(btn);
    });
  }

  function bootFromUrl() {
    if (window.LQ_FIELD_APP && LQ_FIELD_APP.parseBootUrl) {
      LQ_FIELD_APP.parseBootUrl();
      return;
    }
    const q = new URLSearchParams(location.search);
    if (q.get("field") === "1" && window.Jawdah) {
      Jawdah.fieldMode = true;
      localStorage.setItem("jawdah_field_mode", "1");
    }
  }

  function autoFieldForRole() {
    if (!window.Jawdah || !Jawdah.user) return;
    if (isFieldRole() && isMobile() && localStorage.getItem("jawdah_field_mode") !== "0") {
      Jawdah.fieldMode = true;
      localStorage.setItem("jawdah_field_mode", "1");
    }
  }

  window.LQ_STAFF_FIELD = {
    explainHtml,
    renderPanel,
    syncNow,
    enableNotifications,
    submitQuickMaint,
    closeMaint,
    progressMaint,
    enhanceFieldGrid,
    bootFromUrl,
    autoFieldForRole,
    maybeNotify,
  };

  document.addEventListener("DOMContentLoaded", function () {
    bootFromUrl();
  });
})();
