(function () {
  "use strict";

  const token = () => (window.Jawdah && Jawdah.token) || localStorage.getItem("jawdah_cloud_token") || "";

  function openAccountantReport(type, extra = {}) {
    const qs = new URLSearchParams({ token: token(), type, ...extra });
    const url = "/api/report/accountant?" + qs.toString();
    const w = window.open(url, "_blank", "noopener");
    if (w) return;
    fetch(url, { headers: { Authorization: "Bearer " + token() } })
      .then((r) => (r.ok ? r.text() : r.text().then((t) => Promise.reject(new Error(t)))))
      .then((html) => {
        if (typeof showHtmlPreview === "function") showHtmlPreview("تقرير محاسبي", html, `accountant-${type}.html`);
      })
      .catch((e) => {
        if (typeof toastErr === "function") toastErr(e);
        else alert(e.message || "تعذر فتح التقرير");
      });
  }

  function printClientStatement(clientId) {
    if (!clientId) return;
    openAccountantReport("client_statement", { client_id: clientId });
  }

  function printTrialBalance() {
    openAccountantReport("trial_balance");
  }

  function printOverdueReport() {
    openAccountantReport("overdue");
  }

  function printDepositsReport() {
    openAccountantReport("deposits");
  }

  function printMonthlyReport() {
    const month = prompt("الشهر YYYY-MM", new Date().toISOString().slice(0, 7));
    if (!month) return;
    openAccountantReport("monthly", { month });
  }

  function printAccountantSummary() {
    openAccountantReport("summary");
  }

  function accountantToolbarHtml() {
    return `<div class="card lq-accountant-reports">
      <h3>📊 تقارير المحاسب — المرحلة 3</h3>
      <p class="mini">تقارير جاهزة للطباعة / PDF — شعار الشركة وبيانات محدّثة</p>
      <div class="toolbar" style="flex-wrap:wrap;gap:8px">
        <button class="gold-btn" type="button" onclick="LQ_ACCOUNTANT_REPORTS.printSummary()">ملخص المحاسب PDF</button>
        <button class="gold-btn" type="button" onclick="LQ_ACCOUNTANT_REPORTS.printTrialBalance()">ميزان مراجعة PDF</button>
        <button class="gold-btn" type="button" onclick="LQ_ACCOUNTANT_REPORTS.printOverdue()">المتأخرات PDF</button>
        <button class="gold-btn" type="button" onclick="LQ_ACCOUNTANT_REPORTS.printDeposits()">تأمينات غير مستلمة PDF</button>
        <button class="gold-btn" type="button" onclick="LQ_ACCOUNTANT_REPORTS.printMonthly()">تقرير شهري PDF</button>
      </div>
    </div>`;
  }

  window.LQ_ACCOUNTANT_REPORTS = {
    open: openAccountantReport,
    printSummary: printAccountantSummary,
    printTrialBalance,
    printOverdue: printOverdueReport,
    printDeposits: printDepositsReport,
    printMonthly: printMonthlyReport,
    printClientStatement,
    toolbarHtml: accountantToolbarHtml,
  };
  window.printClientStatement = printClientStatement;
})();
