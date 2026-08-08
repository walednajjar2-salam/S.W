/* Phase 9 — role-based UI: sections, KPIs, write actions */
(function () {
  const ROLE_LABEL = {
    owner: "مالك",
    admin: "مدير",
    accountant: "محاسب",
    operations: "تشغيل",
    maintenance: "صيانة",
    viewer: "عرض فقط",
  };

  function writeSections() {
    return Jawdah.uiPermissions?.write_sections || [];
  }

  function isReadOnly() {
    return Boolean(Jawdah.uiPermissions?.read_only) || Jawdah.user?.role === "viewer";
  }

  function canWriteSection(id) {
    if (!Jawdah.user) return false;
    if (isReadOnly()) return false;
    const w = writeSections();
    if (!w.length) return Jawdah.user.role !== "viewer";
    if (w.includes("*")) return true;
    return w.includes(id);
  }

  window.canWriteSection = canWriteSection;

  function injectRoleBadge() {
    const topbar = document.querySelector(".topbar");
    if (!topbar || document.getElementById("lqRoleBadge")) return;
    const role = Jawdah.user?.role || "viewer";
    const badge = document.createElement("span");
    badge.id = "lqRoleBadge";
    badge.className = "lq-role-badge" + (role === "viewer" ? " viewer" : "");
    badge.textContent = ROLE_LABEL[role] || role;
    badge.title = isReadOnly()
      ? "وضع العرض — لا يمكنك التعديل أو الحذف"
      : "صلاحياتك: " + (ROLE_LABEL[role] || role);
    const userbox = document.querySelector(".userbox-pro, .userbox");
    if (userbox) topbar.insertBefore(badge, userbox);
    else topbar.appendChild(badge);
  }

  function applySectionVisibility() {
    document.querySelectorAll(".section[id^='sec-']").forEach((sec) => {
      const id = sec.id.replace(/^sec-/, "");
      if (typeof canAccessSection === "function" && !canAccessSection(id)) {
        sec.classList.add("lq-role-hidden");
      } else {
        sec.classList.remove("lq-role-hidden");
      }
    });

    document.querySelectorAll("[data-lq-section]").forEach((el) => {
      const sec = el.getAttribute("data-lq-section");
      if (sec && typeof canAccessSection === "function") {
        el.classList.toggle("lq-role-hidden", !canAccessSection(sec));
      }
    });

    const dock = document.getElementById("visionAiDock");
    if (dock && typeof canAccessSection === "function") {
      const showWalid = canAccessSection("walid");
      if (!showWalid && !dock.classList.contains("hidden")) {
        dock.classList.add("lq-role-hidden");
      } else {
        dock.classList.remove("lq-role-hidden");
      }
    }
  }

  function applyReadOnlyUi() {
    document.body.classList.toggle("lq-readonly", isReadOnly());
    const roles = ["owner", "admin", "accountant", "operations", "maintenance", "viewer"];
    roles.forEach((r) => document.body.classList.remove("lq-role-" + r));
    const role = Jawdah.user?.role || "viewer";
    document.body.classList.add("lq-role-" + role);
  }

  function patchMutations() {
    if (typeof window.saveNew === "function" && !window.saveNew.__rolePatched) {
      const orig = window.saveNew;
      const tableSection = {
        properties: "properties",
        clients: "clients",
        contracts: "contracts",
        invoices: "invoices",
        maintenance: "maintenance",
        accounts: "accounts",
        users: "users",
        purchase_invoices: "purchases",
        revenues: "revenues",
        admin_expenses: "admin-expenses",
        salaries: "payroll",
        inventory_items: "inventory",
        bank_transactions: "bank",
        chart_accounts: "chart-accounts",
        financial_periods: "financial-periods",
        bank_reconciliations: "bank-reconciliation",
      };
      window.saveNew = async function (table, row) {
        const sec = tableSection[table] || table;
        if (!canWriteSection(sec)) {
          toastNotice("عرض فقط — لا تملك صلاحية إضافة أو تعديل هذه البيانات");
          return;
        }
        return orig.apply(this, arguments);
      };
      window.saveNew.__rolePatched = true;
    }

    if (typeof window.delRecord === "function" && !window.delRecord.__rolePatched) {
      const origDel = window.delRecord;
      window.delRecord = async function (table, id) {
        const sec =
          table === "purchase_invoices"
            ? "purchases"
            : table === "admin_expenses"
              ? "admin-expenses"
              : table === "bank_reconciliations"
                ? "bank-reconciliation"
                : table === "financial_periods"
                  ? "financial-periods"
                  : table === "chart_accounts"
                    ? "chart-accounts"
                    : table;
        if (!canWriteSection(sec)) {
          toastNotice("عرض فقط — لا تملك صلاحية الحذف");
          return;
        }
        return origDel.apply(this, arguments);
      };
      window.delRecord.__rolePatched = true;
    }
  }

  function applyRoleUi() {
    if (!Jawdah.user) return;
    applyReadOnlyUi();
    injectRoleBadge();
    applySectionVisibility();
    patchMutations();
  }

  window.lqApplyRoleUi = applyRoleUi;

  window.addEventListener("load", () => {
    patchMutations();
    if (typeof window.renderAll === "function" && !window.renderAll.__roleHook) {
      const orig = window.renderAll;
      window.renderAll = function () {
        orig.apply(this, arguments);
        applySectionVisibility();
      };
      window.renderAll.__roleHook = true;
    }
    setTimeout(applyRoleUi, 50);
  });
})();
