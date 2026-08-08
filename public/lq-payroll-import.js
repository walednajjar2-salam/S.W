(function () {
  "use strict";

  const TYPES = {
    aglog: {
      icon: "🖐️",
      title: "سجل البصمة AGLog",
      hint: "ملف .txt من جهاز البصمة — No, Mchn, EnNo, Name, DateTime",
      accept: ".txt,.log,.csv",
    },
    payroll_sheet: {
      icon: "💰",
      title: "كشف الرواتب",
      hint: "CSV/Excel محفوظ كـ CSV — رقم الموظف، الاسم، الأساسي، البدلات، الخصومات، الصافي",
      accept: ".csv,.txt,.tsv",
    },
    attendance_detail: {
      icon: "📋",
      title: "تفاصيل البصمات و Day Off",
      hint: "جدول الحضور اليومي — دخول، خروج، بريك، غياب، عطلة",
      accept: ".csv,.txt,.tsv",
    },
    manual_adjustments: {
      icon: "✏️",
      title: "التعديلات اليدوية",
      hint: "سجل قبل/بعد — مضافة يدوياً، مسح، إلغاء تعديل",
      accept: ".csv,.txt,.tsv",
    },
  };

  const state = {
    importType: "aglog",
    preview: null,
    summary: null,
  };

  function esc(s) {
    if (typeof htmlEscape === "function") return htmlEscape(s);
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function money(v) {
    if (typeof window.money === "function") return window.money(v);
    return Number(v || 0).toLocaleString("en-US", { maximumFractionDigits: 3 }) + " OMR";
  }

  function fmt(v) {
    if (typeof window.fmt === "function") return window.fmt(v);
    return Number(v || 0).toLocaleString("en-US");
  }

  function toastOk(msg) {
    if (typeof toast === "function") toast(msg);
  }

  function toastErr(msg) {
    if (typeof toast === "function") toast(msg, true);
  }

  function typeCards() {
    return Object.entries(TYPES)
      .map(
        ([id, t]) => `
        <button type="button" class="lq-pi-type ${state.importType === id ? "active" : ""}" data-type="${id}">
          <span class="lq-pi-type-icon">${t.icon}</span>
          <strong>${esc(t.title)}</strong>
          <small>${esc(t.hint)}</small>
        </button>`
      )
      .join("");
  }

  function summaryCards(summary) {
    if (!summary) return "";
    const chips = [];
    if (summary.parsed_rows != null) chips.push(["السجلات", fmt(summary.parsed_rows)]);
    if (summary.employee_count != null) chips.push(["الموظفون", fmt(summary.employee_count)]);
    if (summary.total_net != null) chips.push(["إجمالي الصافي", money(summary.total_net)]);
    if (summary.date_from) chips.push(["من", summary.date_from]);
    if (summary.date_to) chips.push(["إلى", summary.date_to]);
    if (summary.extra_punches != null) chips.push(["بصمات زائدة", fmt(summary.extra_punches)]);
    if (summary.error_count) chips.push(["أخطاء", fmt(summary.error_count)]);
    if (summary.warning_count) chips.push(["تحذيرات", fmt(summary.warning_count)]);
    return chips.map(([k, v]) => `<span class="badge">${esc(k)}: ${esc(v)}</span>`).join("");
  }

  function previewTable(rows) {
    if (!rows || !rows.length) return `<p class="mini">لا توجد عينة للعرض</p>`;
    const keys = Object.keys(rows[0]).slice(0, 8);
    const head = keys.map((k) => `<th>${esc(k)}</th>`).join("");
    const body = rows
      .slice(0, 12)
      .map(
        (r) =>
          `<tr>${keys.map((k) => `<td>${esc(r[k])}</td>`).join("")}</tr>`
      )
      .join("");
    return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function shell() {
    const t = TYPES[state.importType] || TYPES.aglog;
    const monthDefault = new Date().toISOString().slice(0, 7);
    return `
      <div class="card lq-payroll-import-hero">
        <h3>📥 مركز استيراد الرواتب والحضور</h3>
        <p class="mini">ارفع ملفاتك باحترافية: معاينة → تحقق → تأكيد — AGLog، كشف رواتب، تفاصيل بصمات، وتعديلات يدوية.</p>
        <div class="lq-pi-steps">
          <span class="badge paid">1 · اختر النوع</span>
          <span class="badge">2 · ارفع الملف</span>
          <span class="badge">3 · معاينة</span>
          <span class="badge">4 · تأكيد</span>
        </div>
      </div>
      <div class="card">
        <h4>نوع الاستيراد</h4>
        <div class="lq-pi-types">${typeCards()}</div>
      </div>
      <div class="card">
        <h4>${esc(t.icon)} ${esc(t.title)}</h4>
        <div class="form lq-pi-form">
          <input type="file" id="lqPiFile" accept="${esc(t.accept)}" />
          <input type="month" id="lqPiMonth" value="${monthDefault}" placeholder="الشهر" />
          <input type="text" id="lqPiProject" placeholder="المشروع / كشف الرواتب — مشاريع..." />
        </div>
        <p class="mini">${esc(t.hint)}</p>
        <p class="mini">قوالب CSV فارغة الهيكل (اختيارية):
          <a href="/releases/payroll/sample-payroll-sheet.csv" download>كشف رواتب</a> ·
          <a href="/releases/payroll/sample-attendance-detail.csv" download>تفاصيل حضور</a> ·
          <a href="/releases/payroll/sample-manual-adjustments.csv" download>تعديلات يدوية</a>
        </p>
        <div class="toolbar">
          <button type="button" class="gold-btn" id="lqPiPreviewBtn">معاينة الاستيراد</button>
          <button type="button" class="ghost" id="lqPiResetBtn">إعادة ضبط</button>
        </div>
        <div id="lqPiStatus" class="status-line" style="margin-top:10px"></div>
      </div>
      <div class="card" id="lqPiPreviewCard" style="display:none">
        <h4>نتيجة المعاينة</h4>
        <div id="lqPiSummary" class="status-line"></div>
        <div id="lqPiSample"></div>
        <div class="toolbar" style="margin-top:12px">
          <button type="button" class="gold-btn" id="lqPiCommitBtn">✓ تأكيد وحفظ في النظام</button>
        </div>
      </div>
      <div class="card">
        <h4>سجل الدفعات والحضور</h4>
        <div id="lqPiBatches" class="mini">جاري التحميل...</div>
        <div id="lqPiAttendance" style="margin-top:12px"></div>
      </div>`;
  }

  function bindEvents(root) {
    root.querySelectorAll(".lq-pi-type").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.importType = btn.dataset.type || "aglog";
        state.preview = null;
        render();
      });
    });
    const fileInput = root.querySelector("#lqPiFile");
    const previewBtn = root.querySelector("#lqPiPreviewBtn");
    const commitBtn = root.querySelector("#lqPiCommitBtn");
    const resetBtn = root.querySelector("#lqPiResetBtn");
    if (previewBtn) {
      previewBtn.onclick = () => runPreview(root, fileInput);
    }
    if (commitBtn) {
      commitBtn.onclick = () => runCommit(root);
    }
    if (resetBtn) {
      resetBtn.onclick = () => {
        state.preview = null;
        if (fileInput) fileInput.value = "";
        render();
      };
    }
  }

  async function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("تعذر قراءة الملف"));
      reader.readAsText(file, "UTF-8");
    });
  }

  async function runPreview(root, fileInput) {
    const status = root.querySelector("#lqPiStatus");
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!file) {
      toastErr("اختر ملفاً أولاً");
      return;
    }
    status.innerHTML = `<span class="badge pending">جاري التحليل...</span>`;
    try {
      const content = await readFile(file);
      const payload = {
        import_type: state.importType,
        content,
        file_name: file.name,
        salary_month: (root.querySelector("#lqPiMonth") || {}).value || "",
        project_name: (root.querySelector("#lqPiProject") || {}).value || "",
      };
      const res = await api("payroll/import/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.preview = res.preview;
      state.summary = res.preview.summary || {};
      const card = root.querySelector("#lqPiPreviewCard");
      if (card) card.style.display = "block";
      root.querySelector("#lqPiSummary").innerHTML = summaryCards(state.summary);
      root.querySelector("#lqPiSample").innerHTML = previewTable(res.preview.sample_rows || []);
      status.innerHTML = `<span class="badge paid">جاهز للتأكيد — ${fmt(res.preview.row_count)} سجل</span>`;
      toastOk("تمت المعاينة بنجاح");
    } catch (e) {
      status.innerHTML = `<span class="badge overdue">${esc(e.message || "فشل")}</span>`;
      toastErr(e.message || "فشلت المعاينة");
    }
  }

  async function runCommit(root) {
    if (!state.preview || !state.preview.preview_id) {
      toastErr("قم بالمعاينة أولاً");
      return;
    }
    const status = root.querySelector("#lqPiStatus");
    status.innerHTML = `<span class="badge pending">جاري الحفظ...</span>`;
    try {
      const res = await api("payroll/import/commit", {
        method: "POST",
        body: JSON.stringify({ preview_id: state.preview.preview_id }),
      });
      state.preview = null;
      status.innerHTML = `<span class="badge paid">تم الحفظ — ${fmt(res.result.committed_rows)} سجل · ${esc(res.result.batch_id)}</span>`;
      toastOk("تم رفع البيانات للنظام");
      if (typeof loadAll === "function") await loadAll();
      if (typeof renderSalaries === "function") renderSalaries();
      await loadHistory(root);
      root.querySelector("#lqPiPreviewCard").style.display = "none";
    } catch (e) {
      status.innerHTML = `<span class="badge overdue">${esc(e.message || "فشل")}</span>`;
      toastErr(e.message || "فشل الحفظ");
    }
  }

  async function loadHistory(root) {
    const batchesBox = root.querySelector("#lqPiBatches");
    const attBox = root.querySelector("#lqPiAttendance");
    if (!batchesBox) return;
    // Mounted on DOMContentLoaded, so the login screen may still be up;
    // renderFinanceSuite re-mounts this panel once a session exists.
    const login = document.getElementById("loginScreen");
    if (login && !login.classList.contains("hidden")) return;
    try {
      const [batchesRes, attRes] = await Promise.all([
        api("payroll/import_batches?limit=12"),
        api("payroll/attendance_summary"),
      ]);
      const batches = batchesRes.batches || [];
      batchesBox.innerHTML = batches.length
        ? `<div class="table-wrap"><table><thead><tr><th>النوع</th><th>الملف</th><th>الشهر</th><th>السجلات</th><th>بواسطة</th><th>التاريخ</th></tr></thead><tbody>${batches
            .map(
              (b) =>
                `<tr><td>${esc(b.import_type)}</td><td>${esc(b.file_name || "—")}</td><td>${esc(b.salary_month || "—")}</td><td>${fmt(b.row_count)}</td><td>${esc(b.created_by || "")}</td><td>${esc(b.created_at || "")}</td></tr>`
            )
            .join("")}</tbody></table></div>`
        : `<p class="mini">لا توجد دفعات استيراد بعد — ارفع أول ملف من الأعلى.</p>`;
      const s = attRes.summary || {};
      attBox.innerHTML = `
        <div class="status-line">
          <span class="badge">بصمات AGLog: ${fmt(s.punch_count)}</span>
          <span class="badge">صفوف حضور: ${fmt(s.attendance_day_rows)}</span>
          <span class="badge">تعديلات: ${fmt(s.adjustment_count)}</span>
          <span class="badge">دفعات: ${fmt(s.batch_count)}</span>
        </div>`;
    } catch (e) {
      batchesBox.textContent = "تعذر تحميل السجل";
    }
  }

  function injectStyles() {
    if (document.getElementById("lqPiStyles")) return;
    const style = document.createElement("style");
    style.id = "lqPiStyles";
    style.textContent = `
      .lq-payroll-import-hero{border:1px solid rgba(216,177,91,.35);background:linear-gradient(135deg,rgba(216,177,91,.12),rgba(255,255,255,.04))}
      .lq-pi-steps{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
      .lq-pi-types{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
      .lq-pi-type{text-align:right;border:1px solid var(--line);background:rgba(255,255,255,.05);border-radius:18px;padding:14px;color:inherit;transition:.2s}
      .lq-pi-type:hover,.lq-pi-type.active{border-color:rgba(216,177,91,.75);background:rgba(216,177,91,.12);transform:translateY(-2px)}
      .lq-pi-type-icon{font-size:28px;display:block;margin-bottom:6px}
      .lq-pi-type small{display:block;color:var(--muted);margin-top:6px;line-height:1.5}
      .lq-pi-form input[type=file]{grid-column:1/-1;padding:12px;border:1px dashed rgba(216,177,91,.45);border-radius:14px;background:rgba(0,0,0,.15)}
    `;
    document.head.appendChild(style);
  }

  function render() {
    injectStyles();
    const host = document.getElementById("lqPayrollImportHost");
    if (!host) return;
    host.innerHTML = shell();
    bindEvents(host);
    loadHistory(host);
  }

  function mountPayrollImport() {
    const host = document.getElementById("lqPayrollImportHost");
    if (!host) return;
    render();
  }

  const oldRenderSalaries = window.renderSalaries;
  window.renderSalaries = function () {
    if (typeof oldRenderSalaries === "function") oldRenderSalaries();
    const rows = (window.Jawdah && window.Jawdah.data && window.Jawdah.data.salaries) || [];
    const table = document.getElementById("salariesTable");
    if (table && rows.length) {
      table.innerHTML =
        (typeof tableHtml === "function"
          ? tableHtml(
              [
                ["رقم الموظف", "employee_no"],
                ["الموظف", "employee_name"],
                ["المشروع", "project_name", (v) => v || "—"],
                ["الشهر", "salary_month"],
                ["أساسي", "basic_salary", (v) => money(v)],
                ["بدلات", "allowances", (v) => money(v)],
                ["استقطاعات", "deductions", (v) => money(v)],
                ["الصافي", "net_salary", (v) => money(v)],
                ["الحالة", "status", (v) => (typeof badge === "function" ? badge(v) : v)],
              ],
              rows
            )
          : table.innerHTML);
    }
  };

  const oldFinance = window.renderFinanceSuite;
  window.renderFinanceSuite = function () {
    if (typeof oldFinance === "function") oldFinance();
    mountPayrollImport();
  };

  window.LQ_PAYROLL_IMPORT = { render, mountPayrollImport };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountPayrollImport);
  } else {
    setTimeout(mountPayrollImport, 300);
  }
})();
