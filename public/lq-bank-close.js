(function () {
  "use strict";

  const token = () => (window.Jawdah && Jawdah.token) || localStorage.getItem("jawdah_cloud_token") || "";

  function openBankReport(extra = {}) {
    const qs = new URLSearchParams({ token: token(), ...extra });
    const url = "/api/report/bank_reconciliation?" + qs.toString();
    const w = window.open(url, "_blank", "noopener");
    if (w) return;
    fetch(url, { headers: { Authorization: "Bearer " + token() } })
      .then((r) => (r.ok ? r.text() : r.text().then((t) => Promise.reject(new Error(t)))))
      .then((html) => {
        if (typeof showHtmlPreview === "function") showHtmlPreview("تسوية بنكية", html, "bank-reconciliation.html");
      })
      .catch((e) => {
        if (typeof toastErr === "function") toastErr(e);
        else alert(e.message || "تعذر فتح التقرير");
      });
  }

  function printReconciliation(id) {
    if (!id) return;
    openBankReport({ reconciliation_id: id });
  }

  function printCurrentReconciliation() {
    const bank = document.getElementById("recBank")?.value || "";
    const period = document.getElementById("recPeriod")?.value || "";
    openBankReport({ bank_name: bank, period_name: period });
  }

  function renderPreviewBox(data) {
    const box = document.getElementById("bankReconciliationDetail");
    if (!box || !data) return;
    const unmatched = data.unmatched_transactions || [];
    const payGap = data.payments_without_bank || [];
    const alerts = data.alerts || [];
    const alertHtml = alerts.length
      ? alerts.map((a) => `<p><span class="badge overdue">${a.level || "Alert"}</span> ${a.text || ""}</p>`).join("")
      : '<p class="mini linked-ok">لا تنبيهات بنكية حرجة</p>';
    const unmatchedHtml = unmatched.length
      ? `<table class="data-table"><thead><tr><th>تاريخ</th><th>مرجع</th><th>نوع</th><th>مبلغ</th></tr></thead><tbody>${unmatched
          .map(
            (r) =>
              `<tr><td>${r.bank_date || ""}</td><td>${r.reference || ""}</td><td>${r.type || ""}</td><td>${typeof money === "function" ? money(r.amount) : r.amount}</td></tr>`
          )
          .join("")}</tbody></table>`
      : '<p class="mini">كل الحركات مطابقة في هذه الفترة</p>';
    box.innerHTML = `
      <div class="card lq-bank-close-detail">
        <h3>مطابقة بنكية — المرحلة 4</h3>
        <div class="status-line">
          <span class="badge">حركات: ${data.transaction_count || 0}</span>
          <span class="badge paid">مطابقة: ${data.matched_count || 0}</span>
          <span class="badge ${unmatched.length ? "overdue" : "paid"}">غير مطابقة: ${data.unmatched_count || 0}</span>
          <span class="badge">رصيد الدفاتر: ${typeof money === "function" ? money(data.book_balance) : data.book_balance}</span>
        </div>
        <h4>تنبيهات الفروقات</h4>${alertHtml}
        <h4>حركات غير مطابقة</h4>${unmatchedHtml}
        ${payGap.length ? `<h4>تحصيلات بنكية بدون حركة في كشف البنك (${payGap.length})</h4><p class="mini">استخدم «مطابقة تلقائية» أو أضف حركة بنك يدوياً</p>` : ""}
      </div>`;
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(box);
  }

  async function autoMatchBank() {
    try {
      const bank = document.getElementById("recBank")?.value || "";
      const period = document.getElementById("recPeriod")?.value || "";
      const res = await api("auto_match_bank", {
        method: "POST",
        body: JSON.stringify({ bank_name: bank, period_name: period }),
      });
      const m = res.match_result || {};
      if (typeof toast === "function") toast(`تمت مطابقة ${m.matched || 0} من ${m.scanned || 0} حركة`);
      renderPreviewBox(res.preview);
      if (typeof loadAll === "function") await loadAll();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function loadBankAlerts() {
    try {
      const res = await api("bank_reconciliation_alerts");
      const box = document.getElementById("bankAlertsBox");
      if (!box) return;
      const alerts = res.alerts || [];
      box.innerHTML = alerts.length
        ? alerts.map((a) => `<p><span class="badge overdue">${a.level}</span> ${a.text}</p>`).join("")
        : '<p class="mini linked-ok">لا تنبيهات بنكية</p>';
    } catch (e) {
      /* optional panel */
    }
  }

  async function closePeriod(periodId, force) {
    if (!periodId) return;
    if (!force && !confirm("إقفال الفترة المالية؟ تأكد من تسوية البنك أولاً.")) return;
    try {
      await api("close_financial_period", {
        method: "POST",
        body: JSON.stringify({ period_id: periodId, force: force || false }),
      });
      if (typeof toast === "function") toast("تم إقفال الفترة");
      if (typeof loadAll === "function") await loadAll();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function populatePeriodSelect(periods) {
    const sel = document.getElementById("recPeriodSelect");
    if (!sel || !periods) return;
    const current = sel.value;
    sel.innerHTML =
      '<option value="">— اختر فترة —</option>' +
      periods
        .map(
          (p) =>
            `<option value="${p.period_name}">${p.period_name} (${p.start_date} → ${p.end_date})</option>`
        )
        .join("");
    if (current) sel.value = current;
  }

  window.LQ_BANK_CLOSE = {
    renderPreviewBox,
    autoMatchBank,
    loadBankAlerts,
    closePeriod,
    printReconciliation,
    printCurrentReconciliation,
    populatePeriodSelect,
  };
  window.printBankReconciliation = printReconciliation;
  window.autoMatchBank = autoMatchBank;
  window.closeFinancialPeriod = closePeriod;
})();
