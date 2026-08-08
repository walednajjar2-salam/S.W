(function () {
  "use strict";

  function esc(s) {
    if (typeof htmlEscape === "function") return htmlEscape(s);
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function guide() {
    return `
      <div class="card lq-enterprise-guide">
        <h3>🏛️ التوسع المؤسسي — جاهزية المنصة 100%</h3>
        <p class="mini">SQLite أساسي، تخزين دائم محلي، MFA soft، ومسارات اختيارية للسحابة وPostgreSQL.</p>
        <ul class="check-list">
          <li><strong>الفروع</strong> — ربط العقارات بمواقع/بنايات</li>
          <li><strong>التدقيق</strong> — كل إجراء مسجّل مع المستخدم والوقت</li>
          <li><strong>API</strong> — <a href="/docs.html" target="_blank" rel="noopener">Swagger UI</a> · <code>/api/openapi.json</code></li>
          <li><strong>الأمان</strong> — MFA soft + أجهزة موثوقة + تدوير كلمات المرور</li>
          <li><strong>PostgreSQL</strong> — ظلّي اختياري — SQLite يبقى الأساسي</li>
          <li><strong>التخزين</strong> — محلي دائم جاهز؛ Railway Bucket اختياري</li>
        </ul>
      </div>`;
  }

  function readinessPanel(status) {
    const pr = (status && status.platform_readiness) || {};
    const sec = (status && status.security) || (pr.components && pr.components.security) || {};
    const os = (status && status.object_storage) || {};
    const db = ((pr.components || {}).database) || ((status && status.database && status.database.platform) || {});
    const score = pr.platform_score != null ? pr.platform_score : "—";
    const ready = !!pr.platform_ready;
    return `
      <div class="card" style="margin-top:12px" id="platformReadyCard">
        <h4>جاهزية المنصة (v58)</h4>
        <p class="mini">درجة المنصة منفصلة عن بيانات الأعمال الفارغة (real-only).</p>
        <div class="status-line" style="margin:8px 0;flex-wrap:wrap;gap:6px">
          <span class="badge ${ready ? "paid" : "overdue"}">المنصة: ${ready ? "جاهزة" : "قيد الإكمال"} · ${esc(score)}%</span>
          <span class="badge">MFA: ${esc(sec.mfa_mode || "soft")} · ${sec.mfa_ready ? "جاهز" : "يحتاج SMTP"}</span>
          <span class="badge">تخزين: ${esc(os.mode || (os.cloud_ready ? "cloud" : "local-durable"))}</span>
          <span class="badge">Off-site: ${esc(((pr.components || {}).offsite || {}).mode || "local-volume")}</span>
          <span class="badge">DB: ${esc(db.primary_engine || "sqlite")} · ${db.ready || (db.sqlite && db.sqlite.production_ready) ? "جاهز" : "—"}</span>
          <span class="badge">TOTP: ${sec.totp_ready ? "جاهز" : "—"} · SMTP: ${sec.smtp_configured ? "مفعّل" : "اختياري"}</span>
        </div>
        <p class="mini">${esc((os.note || "") + (db.note ? " · " + db.note : ""))}</p>
      </div>`;
  }

  function storagePanel(status) {
    const os = (status && status.object_storage) || {};
    const cloudReady = !!(os.cloud_ready || os.ready);
    const localReady = os.local_durable_ready !== false;
    const configured = !!os.configured;
    const state = cloudReady
      ? "سحابي جاهز"
      : localReady
        ? "محلي دائم جاهز"
        : configured
          ? "غير جاهز"
          : "محلي (بدون Bucket)";
    const lastWrite = os.last_write
      ? (os.last_write.ok ? "آخر كتابة ناجحة" : "آخر كتابة فشلت") + " · " + (os.last_write.at || "")
      : "لا كتابة بعد";
    const off = (status && status.offsite) || {};
    const hint =
      os.setup_hint ||
      off.setup_hint ||
      "اختياري: Railway → Create → Bucket → Variable References → AWS SDK";
    const defaultOut = cloudReady
      ? "التخزين السحابي جاهز. اضغط فحص التخزين ثم مزامنة الملفات الحالية."
      : "التخزين المحلي الدائم جاهز للإنتاج.\nBucket اختياري للنسخ السحابي:\n1) Railway → Create → Bucket\n2) Variables → AWS SDK references\n3) Redeploy";
    return `
      <div class="card" style="margin-top:12px" id="objectStorageCard">
        <h4>التخزين الدائم + السحابة الاختيارية</h4>
        <p class="mini">الملفات تُحفظ محلياً دائماً. Railway Bucket اختياري للنسخ المزدوج.</p>
        <div class="status-line" style="margin:8px 0;flex-wrap:wrap;gap:6px">
          <span class="badge">التخزين: ${esc(state)}</span>
          <span class="badge">Off-site: ${off.enabled ? "مفعّل" : "اختياري"}</span>
          <span class="badge">الوضع: ${esc(os.mode || off.mode || "local-durable")}</span>
          <span class="badge">Provider: ${esc(os.provider || "—")}</span>
          <span class="badge">${esc(lastWrite)}</span>
        </div>
        <p class="mini"><b>Bucket (اختياري):</b> ${esc(hint)}</p>
        <div class="toolbar" style="flex-wrap:wrap;gap:8px;margin:10px 0">
          <button type="button" class="ghost" onclick="LQ_ENTERPRISE.storageProbe()">فحص التخزين</button>
          <button type="button" class="gold-btn" onclick="LQ_ENTERPRISE.storageSync()">مزامنة الملفات الحالية</button>
          <button type="button" class="ghost" onclick="showSection('backup')">صفحة التخزين</button>
        </div>
        <pre id="objectStorageOut" class="mini" style="white-space:pre-wrap;max-height:220px;overflow:auto;margin:0;background:rgba(0,0,0,.04);padding:10px;border-radius:8px">${esc(defaultOut)}</pre>
      </div>`;
  }

  function pgPanel(status) {
    const db = (status && status.database) || {};
    const plat = db.platform || {};
    const pg = plat.postgres || {};
    const probe = pg.probe || {};
    const verify = pg.shadow_verify || null;
    const sqlite = plat.sqlite || {};
    const probeLabel = !db.postgres_url_configured
      ? "اختياري / غير مُعرّف"
      : probe.ok
        ? "متصل"
        : db.postgres_driver
          ? "فشل الاتصال"
          : "بدون برنامج التشغيل";
    const verifyLabel = !verify
      ? "—"
      : verify.ok
        ? `مطابق (${verify.matches || 0})`
        : `غير مطابق (${(verify.mismatches || []).length} جداول)`;
    return `
      <div class="card" style="margin-top:12px" id="pgPathCard">
        <h4>مسار PostgreSQL — اختياري (ظلّي)</h4>
        <p class="mini">SQLite جاهز للإنتاج. Postgres ظلّي للتحقق فقط عند ضبط DATABASE_URL.</p>
        <div class="status-line" style="margin:8px 0;flex-wrap:wrap;gap:6px">
          <span class="badge">الأساسي: ${esc(plat.primary_engine || db.engine || "sqlite")}</span>
          <span class="badge">${plat.ready || sqlite.production_ready ? "SQLite جاهز" : "SQLite"}</span>
          <span class="badge">جداول SQLite: ${sqlite.tables || 0}</span>
          <span class="badge">صفوف ≈ ${sqlite.approx_rows || 0}</span>
          <span class="badge">Postgres URL: ${db.postgres_url_configured ? "مُعرّف" : "اختياري"}</span>
          <span class="badge">psycopg: ${db.postgres_driver ? "مثبّت" : "غير مثبّت"}</span>
          <span class="badge">الفحص: ${esc(probeLabel)}</span>
          <span class="badge">التحقق: ${esc(verifyLabel)}</span>
        </div>
        <div class="toolbar" style="flex-wrap:wrap;gap:8px;margin:10px 0">
          <button type="button" class="ghost" onclick="LQ_ENTERPRISE.pgProbe()">فحص الاتصال</button>
          <button type="button" class="ghost" onclick="LQ_ENTERPRISE.pgPreview()">معاينة النسخ</button>
          <button type="button" class="gold-btn" onclick="LQ_ENTERPRISE.pgShadow()">نسخ ظلّي</button>
          <button type="button" class="ghost" onclick="LQ_ENTERPRISE.pgVerify()">تحقق العدّ</button>
        </div>
        <pre id="pgPathOut" class="mini" style="white-space:pre-wrap;max-height:220px;overflow:auto;margin:0;background:rgba(0,0,0,.04);padding:10px;border-radius:8px">SQLite أساسي وجاهز. اضغط فحص الاتصال إذا أضفت DATABASE_URL.</pre>
      </div>`;
  }

  function branchForm() {
    return `
      <div class="card" style="margin-top:12px">
        <h4>إضافة فرع / موقع</h4>
        <div class="form">
          <input id="brCode" placeholder="رمز الفرع · HQ">
          <input id="brName" placeholder="اسم الفرع">
          <input id="brCity" placeholder="المدينة">
          <input id="brAddress" placeholder="العنوان">
          <input id="brManager" placeholder="المسؤول">
          <textarea id="brNotes" placeholder="ملاحظات"></textarea>
        </div>
        <button type="button" class="gold-btn" onclick="LQ_ENTERPRISE.saveBranch()">حفظ الفرع</button>
      </div>`;
  }

  function renderBranches(branches) {
    if (!branches || !branches.length) return "<p class=\"mini\">لا فروع — أضف فرعاً أو سيتم إنشاؤها من البنايات تلقائياً</p>";
    return `<div class="table-wrap"><table><thead><tr><th>الرمز</th><th>الاسم</th><th>المدينة</th><th>وحدات</th><th>إشغال</th><th>الحالة</th></tr></thead><tbody>${branches
      .map(
        (b) =>
          `<tr><td>${esc(b.code)}</td><td><b>${esc(b.name)}</b></td><td>${esc(b.city || "—")}</td><td>${b.properties || 0}</td><td>${b.occupancy || 0}%</td><td>${b.active ? "نشط" : "موقوف"}</td></tr>`
      )
      .join("")}</tbody></table></div>`;
  }

  function renderAudit(events) {
    if (!events || !events.length) return "<p class=\"mini\">لا أحداث في السجل</p>";
    return `<div class="saas-task-list">${events
      .map(
        (e) =>
          `<div class="saas-task-item"><div><b>${esc(e.action)}</b> · ${esc(e.entity)}<p class="mini">${esc(e.username || "—")} · ${esc(e.created_at || "")}</p><p>${esc(e.details || "")}</p></div><span class="badge">${esc(e.entity_id || "")}</span></div>`
      )
      .join("")}</div>`;
  }

  function render(host, status, auditRes) {
    if (!host) return;
    const off = status.offsite || {};
    const db = status.database || {};
    host.innerHTML =
      guide() +
      readinessPanel(status) +
      `<div class="status-line" style="margin:8px 0">
        <span class="badge">فروع: ${(status.branches || []).length}</span>
        <span class="badge">تدقيق اليوم: ${status.audit_today || 0}</span>
        <span class="badge">إجمالي التدقيق: ${status.audit_total || 0}</span>
        <span class="badge">${db.engine || "sqlite"}</span>
        <span class="badge">Off-site: ${off.enabled ? "مفعّل" : "اختياري"}</span>
        <span class="badge">تخزين: ${(status.object_storage && (status.object_storage.cloud_ready || status.object_storage.production_storage_ready)) ? (status.object_storage.cloud_ready ? "سحابي" : "محلي دائم") : "محلي"}</span>
      </div>` +
      `<div class="toolbar" style="flex-wrap:wrap;gap:8px;margin-bottom:12px">
        <button type="button" class="gold-btn" onclick="LQ_ENTERPRISE.refresh()">تحديث</button>
        <a class="ghost" href="/docs.html" target="_blank" rel="noopener">فتح Swagger API</a>
        <button type="button" class="ghost" onclick="showSection('backup')">النسخ الاحتياطي</button>
      </div>` +
      `<div class="layout">
        <div class="card"><h4>الفروع والمباني</h4>${renderBranches(status.branches)}${branchForm()}</div>
        <div class="card"><h4>سجل التدقيق</h4>
          <div class="toolbar" style="flex-wrap:wrap;gap:6px;margin-bottom:8px">
            <input id="auditFilterEntity" placeholder="entity: invoices" style="min-width:120px">
            <input id="auditFilterUser" placeholder="username">
            <button type="button" class="ghost" onclick="LQ_ENTERPRISE.loadAudit()">بحث</button>
          </div>
          ${renderAudit((auditRes && auditRes.events) || [])}
        </div>
      </div>` +
      `<div class="card" style="margin-top:12px"><h4>التكامل والنسخ</h4>
        <p class="mini">Off-site: ${off.last_push || "لم يُرسل بعد"} · ${off.last_status && off.last_status.ok ? "آخر دفع ناجح" : esc(off.last_status && off.last_status.error || "—")}</p>
        <p class="mini">PostgreSQL: ${db.postgres_url_configured ? "مُعرّف — استخدم لوحة المسار أدناه" : "SQLite أساسي جاهز (DATABASE_URL اختياري)"}</p>
        <p class="mini">التخزين: ${(status.object_storage && status.object_storage.cloud_ready) ? "سحابي جاهز" : "محلي دائم جاهز — Bucket اختياري"}</p>
      </div>` +
      storagePanel(status) +
      pgPanel(status);
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
  }

  function storageOut(text) {
    const el = document.getElementById("objectStorageOut");
    if (el) el.textContent = text;
  }

  async function storageProbe() {
    try {
      storageOut("جاري فحص التخزين السحابي…");
      const res = await api("storage/object_probe");
      const p = (res && res.probe) || {};
      storageOut(
        [
          p.ok ? "✓ التخزين السحابي متصل" : "✗ فشل الفحص",
          "latency_ms: " + (p.latency_ms ?? "—"),
          "bucket: " + (p.bucket_name || "—"),
          "endpoint: " + (p.endpoint_url || "AWS الافتراضي"),
          p.error ? "error: " + p.error : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      if (typeof toast === "function") toast(p.ok ? "التخزين السحابي متصل" : "فشل فحص التخزين");
    } catch (e) {
      storageOut(String((e && e.message) || e));
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function storageSync() {
    if (!window.confirm("مزامنة كل ملفات uploads المحلية إلى التخزين السحابي؟")) return;
    try {
      storageOut("جاري المزامنة… قد تستغرق وقتاً");
      const res = await api("storage/sync_uploads", {
        method: "POST",
        body: JSON.stringify({ confirm: "sync" }),
      });
      const r = (res && res.result) || {};
      storageOut(
        [
          r.ok ? "✓ اكتملت المزامنة" : "✗ اكتملت مع أخطاء",
          "ممسوح: " + (r.scanned ?? 0),
          "مرفوع: " + (r.uploaded ?? 0),
          "متخطى: " + (r.skipped ?? 0),
          (r.errors || []).length ? "أخطاء:\n" + (r.errors || []).slice(0, 15).join("\n") : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      if (typeof toast === "function") toast(r.ok ? "تمت مزامنة الملفات" : "مزامنة مع أخطاء");
      await refresh();
    } catch (e) {
      storageOut(String((e && e.message) || e));
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function pgOut(text) {
    const el = document.getElementById("pgPathOut");
    if (el) el.textContent = text;
  }

  async function pgProbe() {
    try {
      pgOut("جاري فحص PostgreSQL…");
      const res = await api("database/postgres_probe");
      const p = (res && res.probe) || {};
      pgOut(
        [
          p.ok ? "✓ الاتصال ناجح" : "✗ فشل الاتصال",
          "latency_ms: " + (p.latency_ms ?? "—"),
          "database: " + (p.database || "—"),
          "user: " + (p.user || "—"),
          "version: " + (p.server_version || "—"),
          p.error ? "error: " + p.error : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      if (typeof toast === "function") toast(p.ok ? "PostgreSQL متصل" : "فشل فحص PostgreSQL");
    } catch (e) {
      pgOut(String((e && e.message) || e));
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function pgPreview() {
    try {
      pgOut("جاري معاينة النسخ الظلّي…");
      const res = await api("database/migrate_preview", { method: "POST", body: "{}" });
      const r = (res && res.result) || {};
      pgOut(
        [
          r.ok ? "✓ المعاينة جاهزة (بدون كتابة)" : "✗ فشلت المعاينة",
          "جداول: " + (r.copied_tables ?? 0),
          "صفوف متوقعة: " + (r.copied_rows ?? 0),
          "المحرك الأساسي: " + (r.primary_engine || "sqlite"),
          (r.errors || []).length ? "أخطاء:\n" + (r.errors || []).join("\n") : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      if (typeof toast === "function") toast("تمت معاينة النسخ");
    } catch (e) {
      pgOut(String((e && e.message) || e));
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function pgShadow() {
    if (!window.confirm("نسخ ظلّي إلى PostgreSQL؟\nSQLite يبقى الأساسي. سيتم استبدال جداول الظل إن وُجدت.")) return;
    try {
      pgOut("جاري النسخ الظلّي… قد يستغرق وقتاً");
      const res = await api("database/migrate_shadow", {
        method: "POST",
        body: JSON.stringify({ confirm: "shadow" }),
      });
      const r = (res && res.result) || {};
      pgOut(
        [
          r.ok ? "✓ اكتمل النسخ الظلّي" : "✗ اكتمل مع أخطاء",
          "جداول منسوخة: " + (r.copied_tables ?? 0),
          "صفوف: " + (r.copied_rows ?? 0),
          (r.errors || []).length ? "أخطاء:\n" + (r.errors || []).slice(0, 20).join("\n") : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      if (typeof toast === "function") toast(r.ok ? "تم النسخ الظلّي" : "نسخ مع أخطاء — راجع التفاصيل");
      await refresh();
    } catch (e) {
      pgOut(String((e && e.message) || e));
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function pgVerify() {
    try {
      pgOut("جاري التحقق من أعداد الصفوف…");
      const res = await api("database/verify_shadow");
      const v = (res && res.verify) || {};
      const mism = (v.mismatches || [])
        .slice(0, 15)
        .map((m) => `${m.table}: sqlite=${m.sqlite} pg=${m.postgres}`)
        .join("\n");
      pgOut(
        [
          v.ok ? "✓ التعداد متطابق" : "✗ يوجد اختلاف",
          "مطابق: " + (v.matches ?? 0) + " / " + (v.table_count ?? 0),
          (v.missing_tables || []).length ? "جداول ناقصة: " + (v.missing_tables || []).join(", ") : "",
          mism ? "اختلافات:\n" + mism : "",
          v.error ? "error: " + v.error : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      if (typeof toast === "function") toast(v.ok ? "التحقق ناجح" : "التحقق أظهر فروقاً");
    } catch (e) {
      pgOut(String((e && e.message) || e));
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function loadAudit() {
    const entity = (document.getElementById("auditFilterEntity") || {}).value || "";
    const username = (document.getElementById("auditFilterUser") || {}).value || "";
    const q = new URLSearchParams({ limit: "120" });
    if (entity) q.set("entity", entity.trim());
    if (username) q.set("username", username.trim());
    return api("audit_feed?" + q.toString());
  }

  async function refresh() {
    const host = document.getElementById("enterpriseBox");
    if (host) host.innerHTML = "<p class=\"mini\">جاري تحميل التوسع المؤسسي…</p>";
    try {
      const status = await api("enterprise_status");
      const auditRes = await loadAudit();
      render(host, status, auditRes);
      return status;
    } catch (e) {
      if (host) host.innerHTML = guide() + "<p class=\"badge overdue\">تعذر التحميل</p>";
      if (typeof toastErr === "function") toastErr(e);
      throw e;
    }
  }

  async function saveBranch() {
    const code = (document.getElementById("brCode") || {}).value || "";
    const name = (document.getElementById("brName") || {}).value || "";
    if (!code.trim() || !name.trim()) {
      if (typeof toastNotice === "function") toastNotice("رمز الفرع والاسم مطلوبان");
      return;
    }
    try {
      await api("branches", {
        method: "POST",
        body: JSON.stringify({
          code: code.trim(),
          name: name.trim(),
          city: (document.getElementById("brCity") || {}).value || "",
          address: (document.getElementById("brAddress") || {}).value || "",
          manager: (document.getElementById("brManager") || {}).value || "",
          notes: (document.getElementById("brNotes") || {}).value || "",
          active: 1,
        }),
      });
      if (typeof toast === "function") toast("تم حفظ الفرع");
      await refresh();
      if (typeof loadAll === "function") await loadAll();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  window.LQ_ENTERPRISE = {
    refresh,
    loadAudit,
    saveBranch,
    render,
    storageProbe,
    storageSync,
    pgProbe,
    pgPreview,
    pgShadow,
    pgVerify,
  };
})();
