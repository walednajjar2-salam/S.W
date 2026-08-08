(function () {
  "use strict";

  const THRESHOLD = () =>
    Number((window.Jawdah && Jawdah.dashboard && Jawdah.dashboard.kpis && Jawdah.dashboard.kpis.approval_threshold) || 3000);

  function canDecide() {
    const r = window.Jawdah && Jawdah.user && Jawdah.user.role;
    return r === "admin" || r === "owner" || r === "accountant";
  }

  function canRequest() {
    const r = window.Jawdah && Jawdah.user && Jawdah.user.role;
    return r === "operations" || canDecide();
  }

  function typeLabel(t) {
    return (
      {
        contract: "اعتماد عقد",
        manual_invoice: "فاتورة يدوية كبيرة",
        payment: "تحصيل كبير",
        invoice: "فاتورة",
      }[t] || t
    );
  }

  function entityLabel(row) {
    const data = (window.Jawdah && Jawdah.data) || {};
    if (row.entity === "contracts") {
      const c = (data.contracts || []).find((x) => x.id === row.entity_id);
      return c ? (c.contract_no || c.id) : row.entity_id;
    }
    if (row.entity === "invoices") {
      const i = (data.invoices || []).find((x) => x.id === row.entity_id);
      return i ? (i.invoice_no || i.id) : row.entity_id;
    }
    return row.entity_id;
  }

  function explainHtml() {
    const th = THRESHOLD();
    const m = typeof money === "function" ? money(th) : th;
    return `
      <div class="card lq-approvals-guide">
        <h3>📋 شرح سير الاعتمادات — المرحلة 5</h3>
        <p class="mini"><strong>ببساطة:</strong> بعض العمليات المالية لا تُنفَّذ مباشرة — تمر على المدير أو المحاسب أولاً.</p>
        <ol class="check-list" style="margin:12px 0">
          <li><strong>عقد جديد:</strong> العمليات يجهّز العقد → يطلب اعتماد → المدير يوافق → يصبح العقد نشط وتُولَّد الفواتير.</li>
          <li><strong>فاتورة كبيرة</strong> (فوق ${m}): لا تُصدر مباشرة → طلب اعتماد → بعد الموافقة تُنشأ الفاتورة.</li>
          <li><strong>تحصيل كبير</strong> (فوق ${m}): لا يُسجَّل مباشرة → طلب اعتماد → بعد الموافقة يُسجَّل التحصيل والبنك.</li>
        </ol>
        <p class="mini linked-ok">كل خطوة تُسجَّل: من طلب، من وافق، ومتى.</p>
      </div>`;
  }

  function renderTable() {
    const host = document.getElementById("approvalsTable");
    if (!host) return;
    const rows = ((window.Jawdah && Jawdah.data && Jawdah.data.approvals) || []).slice();
    const pending = rows.filter((r) => String(r.status || "").toLowerCase() === "pending");
    const history = rows.filter((r) => String(r.status || "").toLowerCase() !== "pending").slice(0, 30);
    const pendingHtml = pending.length
      ? pending
          .map((r) => {
            const acts = canDecide()
              ? `<button class="gold-btn" type="button" onclick="LQ_APPROVALS.decide('${r.id}',true)">موافقة</button> <button class="ghost" type="button" onclick="LQ_APPROVALS.decide('${r.id}',false)">رفض</button>`
              : "";
            return `<tr><td>${typeLabel(r.request_type)}</td><td>${entityLabel(r)}</td><td>${r.requested_by || ""}</td><td>${r.requested_at || ""}</td><td><span class="badge overdue">Pending</span></td><td>${acts}</td></tr>`;
          })
          .join("")
      : "<tr><td colspan='6'>لا طلبات معلقة — كل شيء واضح ✅</td></tr>";
    const histHtml = history
      .map(
        (r) =>
          `<tr><td>${typeLabel(r.request_type)}</td><td>${entityLabel(r)}</td><td>${r.requested_by || ""}</td><td>${r.approved_by || "—"}</td><td>${r.approved_at || ""}</td><td>${r.status || ""}</td></tr>`
      )
      .join("");
    host.innerHTML = `
      <h4>⏳ بانتظار الاعتماد (${pending.length})</h4>
      <table class="data-table"><thead><tr><th>النوع</th><th>المرجع</th><th>طلب بواسطة</th><th>التاريخ</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>${pendingHtml}</tbody></table>
      <h4 style="margin-top:20px">📜 سجل الاعتمادات</h4>
      <table class="data-table"><thead><tr><th>النوع</th><th>المرجع</th><th>طلب</th><th>وافق</th><th>التاريخ</th><th>الحالة</th></tr></thead><tbody>${histHtml || "<tr><td colspan='6'>لا سجل بعد</td></tr>"}</tbody></table>`;
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
  }

  async function decide(approvalId, approve) {
    if (!approvalId) return;
    const word = approve ? "الموافقة" : "الرفض";
    if (!confirm(`تأكيد ${word} على هذا الطلب؟`)) return;
    try {
      await api("decide_approval", {
        method: "POST",
        body: JSON.stringify({
          approval_id: approvalId,
          decision: approve ? "approve" : "reject",
        }),
      });
      if (typeof toast === "function") toast(approve ? "تمت الموافقة" : "تم الرفض");
      if (typeof loadAll === "function") await loadAll();
      renderTable();
      updateBell();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function requestContract(contractId) {
    if (!contractId) return;
    try {
      await api("request_approval", {
        method: "POST",
        body: JSON.stringify({
          entity: "contracts",
          entity_id: contractId,
          request_type: "contract",
          notes: "طلب اعتماد عقد للتفعيل",
        }),
      });
      if (typeof toast === "function") toast("تم إرسال العقد لمركز الاعتمادات");
      if (typeof loadAll === "function") await loadAll();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function updateBell() {
    const bell = document.getElementById("bellDot");
    if (!bell) return;
    const n = Number((Jawdah.dashboard && Jawdah.dashboard.kpis && Jawdah.dashboard.kpis.pending_approvals) || 0);
    const overdue = Number((Jawdah.dashboard && Jawdah.dashboard.kpis && Jawdah.dashboard.kpis.overdue) || 0);
    const exp = Number((Jawdah.dashboard && Jawdah.dashboard.kpis && Jawdah.dashboard.kpis.expiring) || 0);
    bell.classList.toggle("hidden", !(n > 0 || overdue > 0 || exp > 0));
  }

  window.LQ_APPROVALS = {
    explainHtml,
    renderTable,
    decide,
    requestContract,
    updateBell,
    threshold: THRESHOLD,
    canDecide,
    canRequest,
  };
  window.requestContractApproval = requestContract;
})();
