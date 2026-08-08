(function () {
  "use strict";

  const VERSION = "historic-2026.06.26";
  const UNIT_STATUSES = [
    ["شاغرة", "vacant"],
    ["محجوزة", "booked"],
    ["مؤجرة", "rented"],
    ["صيانة", "maintenance"],
  ];
  const HOSPITALITY_CATEGORIES = [
    "Housekeeping",
    "Linen",
    "Mini Bar",
    "Guest Supplies",
    "Maintenance",
    "Kitchen",
  ];

  const q = (selector, root = document) => root.querySelector(selector);
  const qa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const getState = () => (typeof Jawdah !== "undefined" ? Jawdah : window.Jawdah || null);
  const data = (table) => {
    const state = getState();
    return Array.isArray(state?.data?.[table]) ? state.data[table] : [];
  };
  const text = (value) => String(value ?? "");
  const amount = (value) => Number(value || 0);
  const safeMoney = (value) => (typeof money === "function" ? money(value) : `OMR ${Number(value || 0).toFixed(3)}`);
  const safeFmt = (value) => (typeof fmt === "function" ? fmt(value) : String(value ?? 0));
  const esc = (value) =>
    text(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

  function normalizeStatus(value) {
    const raw = text(value).trim().toLowerCase();
    if (["rented", "leased", "مستأجرة", "مؤجرة", "ماجره", "مأجرة"].includes(raw)) return "مؤجرة";
    if (["booked", "reserved", "محجوز", "محجوزة"].includes(raw)) return "محجوزة";
    if (["maintenance", "maint", "صيانة", "صيانه"].includes(raw)) return "صيانة";
    return "شاغرة";
  }

  function unitLabel(p) {
    const parts = [];
    if (p.building_no) parts.push(`بناية ${p.building_no}`);
    if (p.apartment_no) parts.push(`شقة ${p.apartment_no}`);
    if (p.room_no) parts.push(`غرفة ${p.room_no}`);
    return parts.join(" / ") || p.name || p.id || "وحدة";
  }

  function sectionLink(id, label) {
    return `<button type="button" onclick="showSection('${id}')">${label}</button>`;
  }

  function metricCard(label, value, hint, go) {
    return `
      <article class="lq-bridge-card" ${go ? `onclick="showSection('${go}')"` : ""}>
        <span>${label}</span>
        <strong>${value}</strong>
        <small>${hint || ""}</small>
      </article>
    `;
  }

  function ensureSection() {
    if (q("#sec-command-chain")) return;
    const dashboard = q("#sec-dashboard");
    if (!dashboard) return;
    dashboard.insertAdjacentHTML(
      "afterend",
      `<section id="sec-command-chain" class="section"><div id="lqCommandChainStage" class="lq-chain-stage"></div></section>`,
    );
  }

  function ensureNav() {
    const nav = q("#nav");
    if (!nav) return;
    const existingCommandButton = q('[data-section="command-chain"]', nav);
    if (existingCommandButton) {
      if (existingCommandButton.dataset.lqCommandBound) return;
      existingCommandButton.dataset.lqCommandBound = "1";
      existingCommandButton.addEventListener(
        "click",
        (event) => {
          event.preventDefault();
          event.stopImmediatePropagation();
          if (!showHistoricSection("command-chain") && typeof showSection === "function") showSection("command-chain");
        },
        true,
      );
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.section = "command-chain";
    button.dataset.lqCommandBound = "1";
    button.innerHTML = "<span>سلسلة التشغيل</span><b>↔</b>";
    button.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!showHistoricSection("command-chain") && typeof showSection === "function") showSection("command-chain");
      },
      true,
    );
    nav.insertBefore(button, nav.children[1] || null);
  }

  function renderBridge() {
    const dash = q("#sec-dashboard");
    if (!dash) return;
    let bridge = q("#lqHistoricBridge");
    if (!bridge) {
      bridge = document.createElement("div");
      bridge.id = "lqHistoricBridge";
      bridge.className = "lq-historic-bridge";
      const hub = q("#lqHubBoard");
      if (hub) hub.insertAdjacentElement("afterend", bridge);
      else dash.insertBefore(bridge, dash.firstElementChild);
    }

    const props = data("properties");
    const clients = data("clients");
    const contracts = data("contracts");
    const invoices = data("invoices");
    const accounts = data("accounts");
    const salaries = data("salaries");
    const inventory = data("inventory_items");
    const maintenance = data("maintenance");
    const activeContracts = contracts.filter((c) => ["active", "نشط"].includes(text(c.status).toLowerCase())).length;
    const unpaid = invoices.reduce((sum, inv) => sum + Math.max(0, amount(inv.amount) - amount(inv.paid_amount)), 0);
    const stockValue = inventory.reduce((sum, item) => sum + amount(item.quantity) * amount(item.unit_cost), 0);

    bridge.innerHTML = `
      <h3>جاهزية تشغيل Launch Quality ERP</h3>
      <p class="mini">مؤشرات مباشرة للعقود والفواتير والتحصيل والتخزين والنسخ الاحتياطي، محدثة من بيانات النظام.</p>
      <div class="lq-bridge-grid">
        ${metricCard("العقارات والوحدات", safeFmt(props.length), "بناية / شقة / غرفة", "properties")}
        ${metricCard("العملاء", safeFmt(clients.length), "ملفات مرتبطة بالعقود", "clients")}
        ${metricCard("العقود النشطة", safeFmt(activeContracts), "قابلة للتجديد والفوترة", "contracts")}
        ${metricCard("المبالغ غير المحصلة", safeMoney(unpaid), "فواتير مفتوحة", "invoices")}
        ${metricCard("حركات الحسابات", safeFmt(accounts.length), "إيرادات ومصروفات", "accounts")}
        ${metricCard("قيمة مخزن الضيافة", safeMoney(stockValue), `${safeFmt(salaries.length)} رواتب / ${safeFmt(maintenance.length)} صيانة`, "inventory")}
      </div>
      <div class="lq-flow-line">
        ${sectionLink("properties", "إضافة بناية / شقة / غرفة")}
        ${sectionLink("clients", "إضافة عميل")}
        ${sectionLink("contracts", "إنشاء عقد")}
        ${sectionLink("invoices", "تحصيل فاتورة")}
        ${sectionLink("accounts", "المحاسب والحسابات")}
        ${sectionLink("payroll", "الرواتب")}
        ${sectionLink("inventory", "مخزن الضيافة")}
        ${sectionLink("command-chain", "عرض سلسلة الربط")}
      </div>
    `;
  }

  function renderCommandChain() {
    const host = q("#lqCommandChainStage");
    if (!host) return;
    const props = data("properties");
    const contracts = data("contracts");
    const invoices = data("invoices");
    const accounts = data("accounts");
    const inventory = data("inventory_items");
    const brokenContracts = contracts.filter((c) => !data("properties").some((p) => p.id === c.property_id) || !data("clients").some((cl) => cl.id === c.client_id));
    const brokenInvoices = invoices.filter((inv) => !contracts.some((c) => c.id === inv.contract_id));
    const lowStock = inventory.filter((item) => amount(item.quantity) <= amount(item.min_quantity));

    host.innerHTML = `
      <h3>سلسلة التشغيل المترابطة</h3>
      <p class="mini">هذه الصفحة تعرض هل النظام يعمل كسلسلة واحدة أم كجداول منفصلة.</p>
      <div class="lq-chain-grid">
        <div class="lq-chain-card"><span>1. العقار</span><strong>${safeFmt(props.length)}</strong><small>بناية / شقة / غرفة بحالة تشغيلية واضحة</small></div>
        <div class="lq-chain-card"><span>2. العقد</span><strong>${safeFmt(contracts.length)}</strong><small>${brokenContracts.length ? "يوجد عقود تحتاج ربط" : "مرتبطة بالعملاء والعقارات"}</small></div>
        <div class="lq-chain-card"><span>3. الفاتورة</span><strong>${safeFmt(invoices.length)}</strong><small>${brokenInvoices.length ? "يوجد فواتير بلا عقد" : "مرتبطة بالعقود والتحصيل"}</small></div>
        <div class="lq-chain-card"><span>4. الحسابات</span><strong>${safeFmt(accounts.length)}</strong><small>تحصيل، مصروفات، رواتب، مخزن</small></div>
      </div>
      <div class="lq-status-grid">
        ${UNIT_STATUSES.map(([label, tone]) => {
          const count = props.filter((p) => normalizeStatus(p.status) === label).length;
          return `<div class="lq-status-card" data-tone="${tone}"><span>${label}</span><strong>${safeFmt(count)}</strong><small>وحدة</small></div>`;
        }).join("")}
      </div>
      <div class="lq-historic-bridge">
        <h3>فحص الربط</h3>
        <p>${brokenContracts.length ? `<span class="lq-linked-danger">عقود غير مكتملة الربط: ${brokenContracts.length}</span>` : `<span class="lq-linked-ok">العقود مربوطة بشكل صحيح</span>`}</p>
        <p>${brokenInvoices.length ? `<span class="lq-linked-danger">فواتير غير مرتبطة بعقد: ${brokenInvoices.length}</span>` : `<span class="lq-linked-ok">الفواتير مربوطة بالعقود</span>`}</p>
        <p>${lowStock.length ? `<span class="lq-linked-warn">أصناف ضيافة تحتاج إعادة طلب: ${lowStock.length}</span>` : `<span class="lq-linked-ok">المخزن ضمن الحدود</span>`}</p>
      </div>
    `;
  }

  function enhancePropertyForm() {
    const sec = q("#sec-properties");
    const form = q("#sec-properties .form");
    if (!sec || !form || q("#lqUnitAtelier")) return;

    form.insertAdjacentHTML(
      "beforebegin",
      `
      <div id="lqUnitAtelier" class="lq-unit-atelier">
        <h3>إضافة وحدة عقارية دقيقة</h3>
        <p class="mini">اختر البناية والشقة والغرفة من قوائم منظمة، ثم حدد الحالة التشغيلية: محجوزة، مؤجرة، شاغرة، صيانة.</p>
        <div class="lq-unit-grid">
          <input id="lqBuildingPreset" list="lqBuildings" placeholder="اختر/اكتب البناية">
          <input id="lqApartmentPreset" list="lqApartments" placeholder="اختر/اكتب الشقة">
          <input id="lqRoomPreset" list="lqRooms" placeholder="اختر/اكتب الغرفة">
        </div>
        <datalist id="lqBuildings"></datalist>
        <datalist id="lqApartments"></datalist>
        <datalist id="lqRooms"></datalist>
        <div class="lq-unit-toolbar">
          ${UNIT_STATUSES.map(([label]) => `<button type="button" class="lq-chip-button" data-unit-status="${label}">${label}</button>`).join("")}
          <button type="button" class="lq-chip-button" id="lqApplyUnit">تعبئة النموذج</button>
        </div>
      </div>
      `,
    );

    q("#lqApplyUnit")?.addEventListener("click", applyUnitPreset);
    qa("[data-unit-status]").forEach((btn) => btn.addEventListener("click", () => setValue("pStatus", btn.dataset.unitStatus)));
    ["lqBuildingPreset", "lqApartmentPreset", "lqRoomPreset"].forEach((id) => q(`#${id}`)?.addEventListener("input", applyUnitPreset));
  }

  function setValue(id, value) {
    const el = q(`#${id}`);
    if (el) el.value = value;
  }

  function applyUnitPreset() {
    setValue("pBuilding", q("#lqBuildingPreset")?.value || q("#pBuilding")?.value || "");
    setValue("pApartment", q("#lqApartmentPreset")?.value || q("#pApartment")?.value || "");
    setValue("pRoom", q("#lqRoomPreset")?.value || q("#pRoom")?.value || "");
  }

  function refreshUnitDatalists() {
    const props = data("properties");
    const put = (id, values) => {
      const el = q(`#${id}`);
      if (!el) return;
      el.innerHTML = [...new Set(values.filter(Boolean).map(String))]
        .sort((a, b) => a.localeCompare(b, "ar"))
        .map((value) => `<option value="${esc(value)}"></option>`)
        .join("");
    };
    put("lqBuildings", props.map((p) => p.building_no));
    put("lqApartments", props.map((p) => p.apartment_no));
    put("lqRooms", props.map((p) => p.room_no));

    const status = q("#pStatus");
    if (status) {
      status.innerHTML = UNIT_STATUSES.map(([label]) => `<option value="${label}">${label}</option>`).join("");
    }
  }

  function renderPropertyStatusStrip() {
    const sec = q("#sec-properties");
    if (!sec) return;
    let strip = q("#lqPropertyStatusStrip");
    if (!strip) {
      strip = document.createElement("div");
      strip.id = "lqPropertyStatusStrip";
      strip.className = "lq-status-grid";
      const tableCard = q("#propertiesTable")?.closest(".card");
      sec.insertBefore(strip, tableCard || sec.firstChild);
    }
    const props = data("properties");
    strip.innerHTML = UNIT_STATUSES.map(([label, tone]) => {
      const count = props.filter((p) => normalizeStatus(p.status) === label).length;
      return `<div class="lq-status-card" data-tone="${tone}"><span>${label}</span><strong>${safeFmt(count)}</strong><small>${label === "شاغرة" ? "جاهزة للتأجير" : "حالة تشغيلية"}</small></div>`;
    }).join("");
  }

  function enhanceAccountant() {
    const sec = q("#sec-accounts");
    if (!sec || q("#lqAccountantStrip")) return;
    sec.insertAdjacentHTML(
      "afterbegin",
      `
      <div id="lqAccountantStrip" class="lq-accountant-strip">
        <h3>مكتب المحاسب</h3>
        <p class="mini">كل عملية مالية يجب أن ترتبط بعميل أو عقار أو فاتورة أو راتب أو مخزون ضيافة.</p>
        <div class="lq-accountant-grid">
          <button type="button" class="lq-accountant-card" onclick="showSection('payroll')"><strong>الرواتب</strong><span>تسجيل راتب وبدلات واستقطاعات</span></button>
          <button type="button" class="lq-accountant-card" onclick="showSection('purchases')"><strong>المشتريات</strong><span>فواتير موردين مرتبطة بالعقار</span></button>
          <button type="button" class="lq-accountant-card" onclick="showSection('statements')"><strong>القوائم المالية</strong><span>دخل، ميزانية، مخزون، بنك</span></button>
        </div>
      </div>
      `,
    );
  }

  function enhanceHospitalityInventory() {
    const sec = q("#sec-inventory");
    if (!sec || q("#lqHospitalityIssue")) return;
    sec.insertAdjacentHTML(
      "afterbegin",
      `
      <div id="lqHospitalityIssue" class="lq-hospitality-issue">
        <h3>مخزن الضيافة المرتبط بالمصروفات</h3>
        <p class="mini">صرف صنف للضيافة ينشئ حركة مخزون خروج، ويمكن ربطه كمرجع تشغيلي مع المصروفات والصيانة.</p>
        <div class="lq-hospitality-form">
          <select id="lqHospItem"></select>
          <input id="lqHospQty" type="number" min="1" step="1" placeholder="الكمية">
          <select id="lqHospCategory">${HOSPITALITY_CATEGORIES.map((x) => `<option>${x}</option>`).join("")}</select>
          <input id="lqHospRef" placeholder="مرجع الصرف / الغرفة">
        </div>
        <div class="lq-unit-toolbar">
          <button type="button" class="gold-btn" id="lqIssueStock">صرف من المخزن</button>
          <button type="button" class="ghost" onclick="showSection('admin-expenses')">تسجيل المصروف الإداري</button>
          <button type="button" class="ghost" onclick="showSection('maintenance')">فتح طلب صيانة</button>
        </div>
      </div>
      `,
    );
    q("#lqIssueStock")?.addEventListener("click", issueHospitalityStock);
  }

  function refreshHospitalitySelect() {
    const select = q("#lqHospItem");
    if (!select) return;
    select.innerHTML =
      data("inventory_items")
        .map((item) => `<option value="${esc(item.id)}">${esc(item.sku || item.id)} - ${esc(item.name)} (${safeFmt(item.quantity || 0)})</option>`)
        .join("") || '<option value="">لا توجد أصناف</option>';
  }

  async function issueHospitalityStock() {
    try {
      const itemId = q("#lqHospItem")?.value;
      const qty = amount(q("#lqHospQty")?.value || 0);
      if (!itemId || qty <= 0) {
        if (typeof toast === "function") toast("اختر الصنف والكمية", true);
        return;
      }
      const item = data("inventory_items").find((x) => x.id === itemId) || {};
      await api("inventory_transactions", {
        method: "POST",
        body: JSON.stringify({
          item_id: itemId,
          tx_date: typeof today === "function" ? today() : new Date().toISOString().slice(0, 10),
          tx_type: "out",
          quantity: qty,
          unit_cost: amount(item.unit_cost),
        reference: q("#lqHospRef")?.value || q("#lqHospCategory")?.value || "Hospitality issue",
          notes: `Hospitality category: ${q("#lqHospCategory")?.value || ""}`,
        }),
      });
      if (typeof toast === "function") toast("تم صرف صنف الضيافة وربطه بسجل المخزون");
      if (typeof loadAll === "function") await loadAll();
    } catch (error) {
      if (typeof toastErr === "function") toastErr(error);
      else console.error(error);
    }
  }

  function installCreatePropertyOverride() {
    if (window.__lqHistoricCreateProperty) return;
    window.__lqHistoricCreateProperty = window.createProperty;
    window.createProperty = async function () {
      applyUnitPreset();
      const building = q("#pBuilding")?.value?.trim() || "";
      const apartment = q("#pApartment")?.value?.trim() || "";
      const room = q("#pRoom")?.value?.trim() || "";
      const status = normalizeStatus(q("#pStatus")?.value);
      const row = {
        building_no: building,
        apartment_no: apartment,
        room_no: room,
        status,
        price: amount(q("#pPrice")?.value),
        location: q("#pLocation")?.value?.trim() || "Nizwa, Oman",
        notes: q("#pNotes")?.value?.trim() || "",
        image: "🏢",
        type: room ? "Room" : apartment ? "Apartment" : "Building",
        name: unitLabel({ building_no: building, apartment_no: apartment, room_no: room }),
        last_update: typeof today === "function" ? today() : new Date().toISOString().slice(0, 10),
      };
      try {
        await api("properties", { method: "POST", body: JSON.stringify(row) });
        if (typeof toast === "function") toast("تم حفظ الوحدة وربطها بمحفظة العقار");
        if (typeof loadAll === "function") await loadAll();
      } catch (error) {
        if (typeof toastErr === "function") toastErr(error);
        else throw error;
      }
    };
  }

  function installQaOverride() {
    if (window.__lqHistoricRunQA) return;
    window.__lqHistoricRunQA = window.runQA;
    window.runQA = async function () {
      if (typeof window.__lqHistoricRunQA === "function") await window.__lqHistoricRunQA();
      const box = q("#qaBox");
      if (!box) return;
      const props = data("properties");
      const inventory = data("inventory_items");
      const salaries = data("salaries");
      const missingUnit = props.filter((p) => !p.building_no && !p.apartment_no && !p.room_no).length;
      const lowStock = inventory.filter((i) => amount(i.quantity) <= amount(i.min_quantity)).length;
      const hasAccountant = data("users").some((u) => text(u.role).toLowerCase() === "accountant");
      const score = Math.max(0, 100 - missingUnit * 4 - lowStock * 5 - (hasAccountant ? 0 : 10));
      box.insertAdjacentHTML(
        "beforeend",
        `
        <div class="lq-historic-bridge">
          <h3>فحص جاهزية الربط</h3>
          <p><span class="${missingUnit ? "lq-linked-warn" : "lq-linked-ok"}">وحدات بلا بناية/شقة/غرفة: ${safeFmt(missingUnit)}</span></p>
          <p><span class="${lowStock ? "lq-linked-warn" : "lq-linked-ok"}">أصناف ضيافة تحت الحد الأدنى: ${safeFmt(lowStock)}</span></p>
          <p><span class="${hasAccountant ? "lq-linked-ok" : "lq-linked-danger"}">دور المحاسب: ${hasAccountant ? "موجود" : "غير موجود"}</span></p>
          <p><span class="${salaries.length ? "lq-linked-ok" : "lq-linked-warn"}">سجلات الرواتب: ${safeFmt(salaries.length)}</span></p>
          <div class="kpi"><span>جاهزية ERP المترابط</span><strong>${safeFmt(score)}%</strong></div>
        </div>
        `,
      );
    };
  }

  function fieldValue(id) {
    return text(q(`#${id}`)?.value).trim();
  }

  function fieldNumber(id) {
    return Number(fieldValue(id) || 0);
  }

  function parseDate(value) {
    const dateValue = new Date(`${text(value).slice(0, 10)}T00:00:00`);
    return Number.isNaN(dateValue.getTime()) ? null : dateValue;
  }

  function contractDuration(c) {
    const start = parseDate(c.start_date);
    const end = parseDate(c.end_date);
    if (!start || !end || end < start) return { days: 0, months: 0, label: "غير محدد" };
    const days = Math.floor((end - start) / 86400000) + 1;
    const months = Math.max(1, Math.round(days / 30));
    return { days, months, label: `${safeFmt(months)} شهر / ${safeFmt(days)} يوم` };
  }

  function contractDaysLeftLocal(c) {
    const end = parseDate(c.end_date);
    if (!end) return null;
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return Math.floor((end - now) / 86400000);
  }

  function contractStatusMeta(c) {
    const raw = text(c.status || "Draft").toLowerCase();
    const days = contractDaysLeftLocal(c);
    const notice = Number(c.renewal_notice_days || 30);
    if (["cancelled", "canceled", "ملغي"].includes(raw)) return { key: "Cancelled", label: "ملغي", tone: "danger" };
    if (["renewed"].includes(raw)) return { key: "Renewed", label: "مجدد", tone: "neutral" };
    if (["draft", "مسودة"].includes(raw)) return { key: "Draft", label: "مسودة", tone: "draft" };
    if (["expired", "closed", "منتهي"].includes(raw) || (days !== null && days < 0)) return { key: "Expired", label: "منتهي", tone: "overdue" };
    if (days !== null && days <= notice) return { key: "Expiring", label: "قريب الانتهاء", tone: "pending" };
    return { key: "Active", label: "ساري", tone: "active" };
  }

  function contractAttachments(c) {
    try {
      const list = JSON.parse(c.attachments || "[]");
      return Array.isArray(list) ? list : [];
    } catch (error) {
      return [];
    }
  }

  function readContractFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () =>
        resolve({
          name: file.name,
          type: file.type || "application/octet-stream",
          size: file.size,
          data: reader.result,
          uploaded_at: new Date().toISOString(),
        });
      reader.onerror = () => reject(reader.error || new Error("File read failed"));
      reader.readAsDataURL(file);
    });
  }

  async function collectContractFiles(input) {
    const files = Array.from(input?.files || []);
    if (!files.length) return [];
    const accepted = files.filter((file) => file.size <= 5 * 1024 * 1024).slice(0, 6);
    return Promise.all(accepted.map(readContractFile));
  }

  function contractPropertyLabel(id) {
    const prop = data("properties").find((p) => p.id === id) || {};
    if (typeof propertyLabel === "function") return propertyLabel(prop);
    return unitLabel(prop);
  }

  function contractClientName(id) {
    return data("clients").find((client) => client.id === id)?.name || id || "";
  }

  function contractInvoices(id) {
    return data("invoices").filter((invoice) => invoice.contract_id === id);
  }

  function contractPayments(id) {
    const invoiceIds = new Set(contractInvoices(id).map((invoice) => invoice.id));
    return data("payments").filter((payment) => payment.contract_id === id || invoiceIds.has(payment.invoice_id));
  }

  function installContractOverrides() {
    if (window.__lqContractsEnhanced) return;
    window.__lqContractsEnhanced = true;
    window.__lqOriginalCreateContract = window.createContract;
    window.createContract = async function () {
      try {
        const attachments = await collectContractFiles(q("#contractAttachments"));
        await api("contracts", {
          method: "POST",
          body: JSON.stringify({
            contract_type: fieldValue("contractType") || "Residential",
            property_id: fieldValue("contractProperty"),
            client_id: fieldValue("contractClient"),
            tenant_nationality: fieldValue("tenantNationality"),
            tenant_id_no: fieldValue("tenantIdNo"),
            unit_details: fieldValue("unitDetails"),
            start_date: fieldValue("contractStart") || today(),
            end_date: fieldValue("contractEnd") || today(),
            rent_amount: fieldNumber("contractRent"),
            deposit_amount: 0,
            late_fee: fieldNumber("contractLateFee"),
            grace_days: fieldNumber("contractGraceDays") || 5,
            renewal_notice_days: fieldNumber("contractRenewalDays") || 30,
            status: "Draft",
            payment_cycle: "monthly",
            legal_terms: fieldValue("contractLegalTerms"),
            attachments: JSON.stringify(attachments),
            notes: fieldValue("contractNotes"),
          }),
        });
        const fileInput = q("#contractAttachments");
        if (fileInput) fileInput.value = "";
        if (typeof toast === "function") toast("تم حفظ مسودة العقد");
        if (typeof loadAll === "function") await loadAll();
        if (typeof showSection === "function") showSection("contracts");
      } catch (error) {
        if (typeof toastErr === "function") toastErr(error);
        else if (typeof toast === "function") toast(error.message || "تعذر حفظ العقد", true);
      }
    };
  }

  function ensureContractDesk() {
    const tableHost = q("#contractsTable");
    if (!tableHost || q("#lqContractDesk")) return;
    tableHost.insertAdjacentHTML(
      "beforebegin",
      `<div id="lqContractDesk" class="lq-contract-desk">
        <div id="lqContractSummary" class="lq-contract-summary"></div>
        <div class="lq-contract-toolbar">
          <input id="lqContractSearch" placeholder="بحث في العقود والعملاء والوحدات">
          <select id="lqContractStatus">
            <option value="">كل الحالات</option>
            <option value="Draft">مسودة</option>
            <option value="Active">ساري</option>
            <option value="Expiring">قريب الانتهاء</option>
            <option value="Expired">منتهي</option>
            <option value="Cancelled">ملغي</option>
            <option value="Renewed">مجدد</option>
          </select>
          <select id="lqContractClient"><option value="">كل العملاء</option></select>
          <select id="lqContractProperty"><option value="">كل العقارات</option></select>
        </div>
      </div>`,
    );
    ["lqContractSearch", "lqContractStatus", "lqContractClient", "lqContractProperty"].forEach((id) => {
      q(`#${id}`)?.addEventListener("input", renderContractsAdvanced);
      q(`#${id}`)?.addEventListener("change", renderContractsAdvanced);
    });
  }

  function syncContractFilterOptions() {
    const client = q("#lqContractClient");
    const prop = q("#lqContractProperty");
    if (client) {
      const old = client.value;
      client.innerHTML = `<option value="">كل العملاء</option>${data("clients")
        .map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`)
        .join("")}`;
      client.value = old;
    }
    if (prop) {
      const old = prop.value;
      prop.innerHTML = `<option value="">كل العقارات</option>${data("properties")
        .map((p) => `<option value="${esc(p.id)}">${esc(contractPropertyLabel(p.id))}</option>`)
        .join("")}`;
      prop.value = old;
    }
  }

  function filteredContracts() {
    const query = text(q("#lqContractSearch")?.value).trim().toLowerCase();
    const status = text(q("#lqContractStatus")?.value);
    const client = text(q("#lqContractClient")?.value);
    const prop = text(q("#lqContractProperty")?.value);
    return data("contracts")
      .filter((c) => !status || contractStatusMeta(c).key === status)
      .filter((c) => !client || c.client_id === client)
      .filter((c) => !prop || c.property_id === prop)
      .filter((c) => {
        if (!query) return true;
        return [
          c.contract_no,
          c.id,
          c.status,
          c.notes,
          c.unit_details,
          contractClientName(c.client_id),
          contractPropertyLabel(c.property_id),
        ]
          .map((value) => text(value).toLowerCase())
          .some((value) => value.includes(query));
      });
  }

  function renderContractSummary() {
    const summaryHost = q("#lqContractSummary");
    if (!summaryHost) return;
    const contracts = data("contracts");
    const counts = contracts.reduce(
      (acc, c) => {
        acc[contractStatusMeta(c).key] = (acc[contractStatusMeta(c).key] || 0) + 1;
        acc.attachments += contractAttachments(c).length;
        return acc;
      },
      { Draft: 0, Active: 0, Expiring: 0, Expired: 0, Cancelled: 0, Renewed: 0, attachments: 0 },
    );
    const billed = data("invoices").reduce((sum, invoice) => sum + amount(invoice.amount), 0);
    summaryHost.innerHTML = [
      ["العقود", contracts.length, "إجمالي السجلات"],
      ["سارية", counts.Active || 0, "عقود نشطة"],
      ["قرب الانتهاء", counts.Expiring || 0, "تحتاج قرار"],
      ["مرفقات", counts.attachments || 0, "ملفات محفوظة"],
      ["فوترة مرتبطة", safeMoney(billed), "من العقود"],
    ]
      .map(([label, value, hint]) => `<article><span>${label}</span><strong>${value}</strong><small>${hint}</small></article>`)
      .join("");
  }

  function renderContractsAdvanced() {
    const host = q("#contractsTable");
    if (!host) return;
    renderContractSummary();
    const rows = filteredContracts();
    host.innerHTML = `<div class="table-wrap lq-contract-table"><table>
      <thead><tr>
        <th>العقد</th><th>العميل</th><th>العقار</th><th>المدة</th><th>الإيجار</th><th>الفواتير</th><th>المرفقات</th><th>الحالة</th><th>إجراءات</th>
      </tr></thead>
      <tbody>${rows
        .map((c) => {
          const status = contractStatusMeta(c);
          const invoices = contractInvoices(c.id);
          const paid = invoices.reduce((sum, invoice) => sum + amount(invoice.paid_amount), 0);
          const total = invoices.reduce((sum, invoice) => sum + amount(invoice.amount), 0);
          const attachments = contractAttachments(c);
          return `<tr>
            <td><b>${esc(c.contract_no || c.id)}</b><br><small>${esc(c.contract_type || "Residential")}</small></td>
            <td>${esc(contractClientName(c.client_id))}</td>
            <td>${esc(contractPropertyLabel(c.property_id))}</td>
            <td>${esc(contractDuration(c).label)}<br><small>${esc(c.start_date)} - ${esc(c.end_date)}</small></td>
            <td>${safeMoney(c.rent_amount)}</td>
            <td>${safeMoney(total)}<br><small>محصل ${safeMoney(paid)}</small></td>
            <td><span class="badge">${safeFmt(attachments.length)}</span></td>
            <td><span class="badge ${status.tone}">${status.label}</span></td>
            <td class="lq-action-cell">
              <button class="gold-btn" onclick="openContractDetails('${esc(c.id)}')">تفاصيل</button>
              <button class="ghost" onclick="contractDocument('${esc(c.id)}')">معاينة PDF</button>
              <button class="ghost" onclick="approveContract('${esc(c.id)}')">اعتماد</button>
              <button class="ghost" onclick="invoiceFromContract('${esc(c.id)}')">فاتورة</button>
              <button class="ghost" onclick="renewContract('${esc(c.id)}')">تجديد</button>
              <button class="danger" onclick="openEndContractModal('${esc(c.id)}')">إنهاء</button>
            </td>
          </tr>`;
        })
        .join("") || `<tr><td colspan="9">لا توجد عقود مطابقة</td></tr>`}</tbody>
    </table></div>`;
  }

  window.openContractDetails = function (id) {
    const c = data("contracts").find((item) => item.id === id);
    if (!c) return;
    const invoices = contractInvoices(id);
    const payments = contractPayments(id);
    const status = contractStatusMeta(c);
    const attachmentList = contractAttachments(c);
    const invoiceRows = invoices
      .map((invoice) => `<tr><td>${esc(invoice.invoice_no)}</td><td>${safeMoney(invoice.amount)}</td><td>${safeMoney(invoice.paid_amount)}</td><td>${esc(invoice.status)}</td></tr>`)
      .join("") || `<tr><td colspan="4">لا توجد فواتير مرتبطة</td></tr>`;
    const paymentRows = payments
      .map((payment) => `<tr><td>${esc(payment.payment_date)}</td><td>${safeMoney(payment.amount)}</td><td>${esc(payment.method)}</td><td>${esc(payment.note)}</td></tr>`)
      .join("") || `<tr><td colspan="4">لا توجد دفعات</td></tr>`;
    const attachments = attachmentList
      .map((file) => {
        const link = file.data ? `<a class="ghost" href="${esc(file.data)}" download="${esc(file.name || "contract-file")}">تحميل</a>` : "";
        return `<li><span>${esc(file.name || "Attachment")}</span><small>${safeFmt(Math.round(amount(file.size) / 1024))} KB</small>${link}</li>`;
      })
      .join("") || `<li><span>لا توجد مرفقات محفوظة</span></li>`;
    q("#genericModalBody").innerHTML = `<div class="lq-contract-detail">
      <div class="lq-detail-head">
        <div><h2>${esc(c.contract_no || c.id)}</h2><p>${esc(contractClientName(c.client_id))} - ${esc(contractPropertyLabel(c.property_id))}</p></div>
        <span class="badge ${status.tone}">${status.label}</span>
      </div>
      <div class="lq-detail-grid">
        <article><span>المدة</span><strong>${esc(contractDuration(c).label)}</strong></article>
        <article><span>الإيجار</span><strong>${safeMoney(c.rent_amount)}</strong></article>
        <article><span>الفواتير</span><strong>${safeFmt(invoices.length)}</strong></article>
        <article><span>الدفعات</span><strong>${safeFmt(payments.length)}</strong></article>
      </div>
      <div class="lq-detail-actions">
        <button class="gold-btn" onclick="contractDocument('${esc(id)}')">معاينة قبل الطباعة / PDF</button>
        <button class="ghost" onclick="editRecord('contracts','${esc(id)}')">تعديل العقد</button>
        <button class="ghost" onclick="invoiceFromContract('${esc(id)}')">إنشاء فاتورة</button>
        <button class="danger" onclick="openEndContractModal('${esc(id)}')">إنهاء العقد</button>
      </div>
      <section><h3>الفواتير المرتبطة</h3><div class="table-wrap"><table><thead><tr><th>رقم</th><th>الإجمالي</th><th>المدفوع</th><th>الحالة</th></tr></thead><tbody>${invoiceRows}</tbody></table></div></section>
      <section><h3>الدفعات</h3><div class="table-wrap"><table><thead><tr><th>التاريخ</th><th>المبلغ</th><th>الطريقة</th><th>ملاحظة</th></tr></thead><tbody>${paymentRows}</tbody></table></div></section>
      <section><h3>مرفقات العقد</h3><ul class="lq-attachment-list">${attachments}</ul><div class="lq-upload-row"><input id="lqContractDetailFiles" type="file" multiple accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"><button class="gold-btn" onclick="saveContractAttachments('${esc(id)}')">حفظ المرفقات</button></div></section>
    </div>`;
    if (typeof openModal === "function") openModal("genericModal");
  };

  window.saveContractAttachments = async function (id) {
    try {
      const c = data("contracts").find((item) => item.id === id);
      if (!c) return;
      const next = await collectContractFiles(q("#lqContractDetailFiles"));
      const merged = contractAttachments(c).concat(next);
      await api(`contracts/${id}`, { method: "PUT", body: JSON.stringify({ attachments: JSON.stringify(merged) }) });
      if (typeof toast === "function") toast("تم حفظ مرفقات العقد");
      if (typeof loadAll === "function") await loadAll();
      window.openContractDetails(id);
    } catch (error) {
      if (typeof toastErr === "function") toastErr(error);
      else if (typeof toast === "function") toast(error.message || "تعذر حفظ المرفقات", true);
    }
  };

  window.openEndContractModal = function (id) {
    const c = data("contracts").find((item) => item.id === id);
    if (!c) return;
    q("#genericModalBody").innerHTML = `<div class="lq-contract-detail">
      <div class="lq-detail-head"><div><h2>إنهاء العقد</h2><p>${esc(c.contract_no || c.id)} - ${esc(contractClientName(c.client_id))}</p></div></div>
      <div class="form edit-form">
        <label>تاريخ الإنهاء<input id="lqEndContractDate" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
        <label>الحالة<select id="lqEndContractStatus"><option value="Cancelled">ملغي</option><option value="Expired">منتهي</option></select></label>
        <label>السبب<textarea id="lqEndContractReason" rows="4" placeholder="سبب الإنهاء أو ملاحظة داخلية"></textarea></label>
      </div>
      <div class="toolbar"><button class="danger" onclick="submitEndContract('${esc(id)}')">تأكيد الإنهاء</button><button class="ghost" onclick="closeModal('genericModal')">إلغاء</button></div>
    </div>`;
    if (typeof openModal === "function") openModal("genericModal");
  };

  window.submitEndContract = async function (id) {
    try {
      await api("end_contract", {
        method: "POST",
        body: JSON.stringify({
          contract_id: id,
          ended_at: fieldValue("lqEndContractDate") || today(),
          status: fieldValue("lqEndContractStatus") || "Cancelled",
          reason: fieldValue("lqEndContractReason"),
        }),
      });
      if (typeof closeModal === "function") closeModal("genericModal");
      if (typeof toast === "function") toast("تم إنهاء العقد");
      if (typeof loadAll === "function") await loadAll();
      if (typeof showSection === "function") showSection("contracts");
    } catch (error) {
      if (typeof toastErr === "function") toastErr(error);
      else if (typeof toast === "function") toast(error.message || "تعذر إنهاء العقد", true);
    }
  };

  function enhanceContracts() {
    installContractOverrides();
    ensureContractDesk();
    syncContractFilterOptions();
    window.renderContractsAdvanced = renderContractsAdvanced;
    renderContractsAdvanced();
  }

  function invoiceRemaining(invoice) {
    return Math.max(0, amount(invoice.amount) - amount(invoice.paid_amount));
  }

  function invoiceStatusMeta(invoice) {
    const raw = text(invoice.status || "Pending").toLowerCase();
    if (raw === "paid" || invoiceRemaining(invoice) <= 0) return { key: "Paid", label: "مدفوعة", tone: "paid" };
    if (invoice.due_date && invoice.due_date < new Date().toISOString().slice(0, 10)) return { key: "Overdue", label: "متأخرة", tone: "overdue" };
    if (raw === "partial" || amount(invoice.paid_amount) > 0) return { key: "Partial", label: "جزئية", tone: "partial" };
    return { key: "Pending", label: "معلقة", tone: "pending" };
  }

  function invoicePayments(invoiceId) {
    return data("payments").filter((payment) => payment.invoice_id === invoiceId);
  }

  function invoiceContractLabel(id) {
    const contract = data("contracts").find((c) => c.id === id) || {};
    return contract.contract_no || contract.id || id || "";
  }

  function ensureInvoiceDesk() {
    const host = q("#invoicesTable");
    if (!host || q("#lqInvoiceDesk")) return;
    host.insertAdjacentHTML(
      "beforebegin",
      `<div id="lqInvoiceDesk" class="lq-invoice-desk">
        <div id="lqInvoiceSummary" class="lq-contract-summary"></div>
        <div class="lq-contract-toolbar">
          <input id="lqInvoiceSearch" placeholder="بحث في الفواتير والعملاء والعقود">
          <select id="lqInvoiceStatus">
            <option value="">كل الحالات</option>
            <option value="Pending">معلقة</option>
            <option value="Partial">جزئية</option>
            <option value="Paid">مدفوعة</option>
            <option value="Overdue">متأخرة</option>
          </select>
          <select id="lqInvoiceClient"><option value="">كل العملاء</option></select>
          <button type="button" class="gold-btn" onclick="openInvoiceComposer()">فاتورة يدوية</button>
        </div>
      </div>`,
    );
    ["lqInvoiceSearch", "lqInvoiceStatus", "lqInvoiceClient"].forEach((id) => {
      q(`#${id}`)?.addEventListener("input", renderInvoicesAdvanced);
      q(`#${id}`)?.addEventListener("change", renderInvoicesAdvanced);
    });
  }

  function syncInvoiceFilterOptions() {
    const client = q("#lqInvoiceClient");
    if (!client) return;
    const old = client.value;
    client.innerHTML = `<option value="">كل العملاء</option>${data("clients")
      .map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`)
      .join("")}`;
    client.value = old;
  }

  function filteredInvoices() {
    const query = text(q("#lqInvoiceSearch")?.value).trim().toLowerCase();
    const status = text(q("#lqInvoiceStatus")?.value);
    const client = text(q("#lqInvoiceClient")?.value);
    return data("invoices")
      .filter((invoice) => !status || invoiceStatusMeta(invoice).key === status)
      .filter((invoice) => !client || invoice.client_id === client)
      .filter((invoice) => {
        if (!query) return true;
        return [
          invoice.invoice_no,
          invoice.description,
          invoice.status,
          contractClientName(invoice.client_id),
          contractPropertyLabel(invoice.property_id),
          invoiceContractLabel(invoice.contract_id),
        ]
          .map((value) => text(value).toLowerCase())
          .some((value) => value.includes(query));
      });
  }

  function renderInvoiceSummary() {
    const invoices = data("invoices");
    const total = invoices.reduce((sum, invoice) => sum + amount(invoice.amount), 0);
    const paid = invoices.reduce((sum, invoice) => sum + amount(invoice.paid_amount), 0);
    const overdue = invoices
      .filter((invoice) => invoiceStatusMeta(invoice).key === "Overdue")
      .reduce((sum, invoice) => sum + invoiceRemaining(invoice), 0);
    const payments = data("payments").reduce((sum, payment) => sum + amount(payment.amount), 0);
    q("#lqInvoiceSummary").innerHTML = [
      ["الفواتير", invoices.length, "إجمالي"],
      ["المصدر", safeMoney(total), "مبالغ مصدرة"],
      ["المحصل", safeMoney(paid), "من الدفعات"],
      ["المتبقي", safeMoney(Math.max(0, total - paid)), "رصيد مفتوح"],
      ["المتأخر", safeMoney(overdue), `${safeFmt(data("payments").length)} دفعة`],
    ]
      .map(([label, value, hint]) => `<article><span>${label}</span><strong>${value}</strong><small>${hint}</small></article>`)
      .join("");
  }

  function renderInvoicesAdvanced() {
    const host = q("#invoicesTable");
    if (!host) return;
    renderInvoiceSummary();
    const rows = filteredInvoices();
    host.innerHTML = `<div class="table-wrap lq-invoice-table"><table>
      <thead><tr>
        <th>الفاتورة</th><th>العميل</th><th>العقد/العقار</th><th>التواريخ</th><th>الإجمالي</th><th>المدفوع</th><th>المتبقي</th><th>الدفعات</th><th>الحالة</th><th>إجراءات</th>
      </tr></thead>
      <tbody>${rows
        .map((invoice) => {
          const status = invoiceStatusMeta(invoice);
          const payments = invoicePayments(invoice.id);
          return `<tr>
            <td><b>${esc(invoice.invoice_no)}</b><br><small>${esc(invoice.description)}</small></td>
            <td>${esc(contractClientName(invoice.client_id))}</td>
            <td>${esc(invoiceContractLabel(invoice.contract_id))}<br><small>${esc(contractPropertyLabel(invoice.property_id))}</small></td>
            <td>إصدار ${esc(invoice.issue_date)}<br><small>استحقاق ${esc(invoice.due_date)}</small></td>
            <td>${safeMoney(invoice.amount)}</td>
            <td>${safeMoney(invoice.paid_amount)}</td>
            <td>${safeMoney(invoiceRemaining(invoice))}</td>
            <td><span class="badge">${safeFmt(payments.length)}</span></td>
            <td><span class="badge ${status.tone}">${status.label}</span></td>
            <td class="lq-action-cell">
              <button class="gold-btn" onclick="openInvoiceDetails('${esc(invoice.id)}')">تفاصيل</button>
              <button class="ghost" onclick="openPayment('${esc(invoice.id)}')">دفعة</button>
              <button class="ghost" onclick="printInvoice('${esc(invoice.id)}')">PDF</button>
              <button class="ghost" onclick="printReceipt('${esc(invoice.id)}')">إيصال</button>
              <button class="ghost" onclick="reissueInvoice('${esc(invoice.id)}')">إعادة إصدار</button>
            </td>
          </tr>`;
        })
        .join("") || `<tr><td colspan="10">لا توجد فواتير مطابقة</td></tr>`}</tbody>
    </table></div>`;
  }

  function contractOptionsHtml(selected = "") {
    return data("contracts")
      .map((c) => {
        const label = `${c.contract_no || c.id} - ${contractClientName(c.client_id)} - ${contractPropertyLabel(c.property_id)}`;
        return `<option value="${esc(c.id)}" ${c.id === selected ? "selected" : ""}>${esc(label)}</option>`;
      })
      .join("");
  }

  window.openInvoiceComposer = function (contractId = "") {
    const c = data("contracts").find((item) => item.id === contractId) || data("contracts")[0] || {};
    q("#genericModalBody").innerHTML = `<div class="lq-contract-detail">
      <div class="lq-detail-head"><div><h2>إنشاء فاتورة</h2><p>فاتورة مخصصة مرتبطة بعقد قائم للحفاظ على الترابط المالي.</p></div></div>
      <div class="form edit-form">
        <label>العقد<select id="lqInvoiceContract" onchange="syncInvoiceComposerFromContract()">${contractOptionsHtml(c.id)}</select></label>
        <label>تاريخ الإصدار<input id="lqInvoiceIssue" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
        <label>تاريخ الاستحقاق<input id="lqInvoiceDue" type="date" value="${new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)}"></label>
        <label>المبلغ<input id="lqInvoiceAmount" type="number" step="0.001" value="${esc(c.rent_amount || "")}"></label>
        <label>الوصف<textarea id="lqInvoiceDesc" rows="3">Rent invoice</textarea></label>
      </div>
      <div class="toolbar"><button class="gold-btn" onclick="submitManualInvoice()">إنشاء الفاتورة</button><button class="ghost" onclick="closeModal('genericModal')">إلغاء</button></div>
    </div>`;
    if (typeof openModal === "function") openModal("genericModal");
  };

  window.syncInvoiceComposerFromContract = function () {
    const c = data("contracts").find((item) => item.id === fieldValue("lqInvoiceContract"));
    if (!c) return;
    const amountInput = q("#lqInvoiceAmount");
    const descInput = q("#lqInvoiceDesc");
    if (amountInput && !amountInput.value) amountInput.value = c.rent_amount || "";
    if (descInput) descInput.value = `Rent invoice for ${c.contract_no || c.id}`;
  };

  window.submitManualInvoice = async function () {
    try {
      const res = await api("manual_invoice", {
        method: "POST",
        body: JSON.stringify({
          contract_id: fieldValue("lqInvoiceContract"),
          issue_date: fieldValue("lqInvoiceIssue") || today(),
          due_date: fieldValue("lqInvoiceDue") || today(),
          amount: fieldNumber("lqInvoiceAmount"),
          description: fieldValue("lqInvoiceDesc") || "Manual invoice",
        }),
      });
      if (typeof closeModal === "function") closeModal("genericModal");
      if (typeof toast === "function") toast(`تم إنشاء الفاتورة ${res.item?.invoice_no || ""}`);
      if (typeof loadAll === "function") await loadAll();
      if (typeof showSection === "function") showSection("invoices");
    } catch (error) {
      if (typeof toastErr === "function") toastErr(error);
      else if (typeof toast === "function") toast(error.message || "تعذر إنشاء الفاتورة", true);
    }
  };

  window.invoiceFromContract = function (contractId) {
    window.openInvoiceComposer(contractId);
  };

  window.reissueInvoice = async function (id) {
    const invoice = data("invoices").find((item) => item.id === id);
    if (!invoice) return;
    if (!confirm(`إعادة إصدار ${invoice.invoice_no} برقم جديد؟`)) return;
    try {
      const res = await api("reissue_invoice", { method: "POST", body: JSON.stringify({ invoice_id: id }) });
      if (typeof toast === "function") toast(`تمت إعادة الإصدار ${res.item?.invoice_no || ""}`);
      if (typeof loadAll === "function") await loadAll();
      if (typeof showSection === "function") showSection("invoices");
    } catch (error) {
      if (typeof toastErr === "function") toastErr(error);
      else if (typeof toast === "function") toast(error.message || "تعذر إعادة الإصدار", true);
    }
  };

  window.openInvoiceDetails = function (id) {
    const invoice = data("invoices").find((item) => item.id === id);
    if (!invoice) return;
    const payments = invoicePayments(id);
    const status = invoiceStatusMeta(invoice);
    const rows = payments
      .map((payment) => `<tr><td>${esc(payment.payment_date)}</td><td>${safeMoney(payment.amount)}</td><td>${esc(payment.method)}</td><td>${esc(payment.note)}</td><td><button class="ghost" onclick="printReceipt('${esc(id)}','${esc(payment.id)}')">إيصال</button></td></tr>`)
      .join("") || `<tr><td colspan="5">لا توجد دفعات بعد</td></tr>`;
    q("#genericModalBody").innerHTML = `<div class="lq-contract-detail">
      <div class="lq-detail-head"><div><h2>${esc(invoice.invoice_no)}</h2><p>${esc(contractClientName(invoice.client_id))} - ${esc(invoiceContractLabel(invoice.contract_id))}</p></div><span class="badge ${status.tone}">${status.label}</span></div>
      <div class="lq-detail-grid">
        <article><span>الإجمالي</span><strong>${safeMoney(invoice.amount)}</strong></article>
        <article><span>المدفوع</span><strong>${safeMoney(invoice.paid_amount)}</strong></article>
        <article><span>المتبقي</span><strong>${safeMoney(invoiceRemaining(invoice))}</strong></article>
        <article><span>الدفعات</span><strong>${safeFmt(payments.length)}</strong></article>
      </div>
      <div class="lq-detail-actions">
        <button class="gold-btn" onclick="openPayment('${esc(id)}')">تسجيل دفعة</button>
        <button class="ghost" onclick="printInvoice('${esc(id)}')">معاينة PDF</button>
        <button class="ghost" onclick="printReceipt('${esc(id)}')">إيصال قبض</button>
        <button class="ghost" onclick="reissueInvoice('${esc(id)}')">إعادة إصدار</button>
      </div>
      <section><h3>الدفعات المتعددة</h3><div class="table-wrap"><table><thead><tr><th>التاريخ</th><th>المبلغ</th><th>الطريقة</th><th>ملاحظة</th><th>إجراء</th></tr></thead><tbody>${rows}</tbody></table></div></section>
    </div>`;
    if (typeof openModal === "function") openModal("genericModal");
  };

  function focusPrintModal() {
    q("#genericModal")?.classList.remove("show");
    q("#paymentModal")?.classList.remove("show");
  }

  window.printInvoice = function (id) {
    const invoice = data("invoices").find((item) => item.id === id);
    if (!invoice) return;
    window.Jawdah = window.Jawdah || {};
    window.Jawdah.invoiceForPrint = invoice;
    focusPrintModal();
    if (window.LQ_PRINT?.buildTaxInvoiceHtml) {
      q("#invoicePreview").innerHTML = window.LQ_PRINT.buildTaxInvoiceHtml(invoice);
    } else {
      const status = invoiceStatusMeta(invoice);
      q("#invoicePreview").innerHTML = `<div class="invoice-paper lq-print-paper"><p>${esc(invoice.invoice_no)} — ${status.label}</p></div>`;
    }
    if (typeof openModal === "function") openModal("invoiceModal");
  };

  window.printReceipt = function (invoiceId, paymentId = "") {
    const invoice = data("invoices").find((item) => item.id === invoiceId);
    if (!invoice) return;
    const payments = invoicePayments(invoiceId);
    const payment =
      payments.find((item) => item.id === paymentId) ||
      payments[payments.length - 1] ||
      (amount(invoice.paid_amount) > 0
        ? {
            id: `${invoice.invoice_no}-RECORDED`,
            payment_date: invoice.issue_date,
            method: "Recorded payment",
            amount: invoice.paid_amount,
            note: "Recorded invoice collection",
          }
        : null);
    if (!payment) {
      if (typeof toast === "function") toast("لا توجد دفعات لإصدار إيصال", true);
      return;
    }
    focusPrintModal();
    if (window.LQ_PRINT?.buildReceiptHtml) {
      q("#invoicePreview").innerHTML = window.LQ_PRINT.buildReceiptHtml(invoice, payment);
    } else {
      q("#invoicePreview").innerHTML = `<div class="invoice-paper lq-print-paper"><p>Receipt ${esc(payment.id)}</p></div>`;
    }
    if (typeof openModal === "function") openModal("invoiceModal");
  };

  function enhanceInvoices() {
    ensureInvoiceDesk();
    syncInvoiceFilterOptions();
    renderInvoicesAdvanced();
  }

  function refreshAll() {
    ensureSection();
    ensureNav();
    enhanceContracts();
    enhanceInvoices();
    enhancePropertyForm();
    enhanceAccountant();
    enhanceHospitalityInventory();
    tuneFloatingAiDock();
    refreshUnitDatalists();
    refreshHospitalitySelect();
    renderBridge();
    renderCommandChain();
    renderPropertyStatusStrip();
    installCreatePropertyOverride();
    installQaOverride();
    document.body.dataset.historicUpgrade = VERSION;
  }

  function tuneFloatingAiDock() {
    const dock = q("#visionAiDock");
    if (!dock) return;
    dock.classList.add("hidden");
    dock.setAttribute("hidden", "");
    dock.style.display = "none";
  }

  function showHistoricSection(id) {
    if (id !== "command-chain") return false;
    ensureSection();
    renderCommandChain();
    const section = q("#sec-command-chain");
    if (!section) return false;
    qa(".section").forEach((sec) => sec.classList.remove("active", "section-fade-out", "section-fade-in"));
    section.classList.add("active", "section-fade-in");
    section.dataset.rendered = "1";
    qa("#nav button").forEach((button) => button.classList.toggle("active", button.dataset.section === id));
    const state = getState();
    if (state) state.activeSection = id;
    const title = q("#sectionTitle");
    if (title) title.textContent = "سلسلة التشغيل";
    document.body.classList.remove("dash-pro-active");
    window.scrollTo({ top: 0, behavior: "smooth" });
    setTimeout(() => section.classList.remove("section-fade-in"), 320);
    setTimeout(refreshAll, 0);
    return true;
  }

  function hookRenderAll() {
    if (window.__lqHistoricRenderHooked) return;
    window.__lqHistoricRenderHooked = true;
    const oldRenderAll = window.renderAll;
    if (typeof oldRenderAll === "function") {
      window.renderAll = function () {
        const result = oldRenderAll.apply(this, arguments);
        setTimeout(refreshAll, 0);
        return result;
      };
    }
    const oldShowSection = window.showSection;
    if (typeof oldShowSection === "function") {
      window.showSection = function (id) {
        if (showHistoricSection(id)) return;
        const result = oldShowSection.apply(this, arguments);
        setTimeout(refreshAll, 0);
        return result;
      };
    }
  }

  window.LAUNCH_QUALITY_HISTORIC_UPGRADE = () => ({
    version: VERSION,
    linkedTables: {
      properties: data("properties").length,
      clients: data("clients").length,
      contracts: data("contracts").length,
      invoices: data("invoices").length,
      accounts: data("accounts").length,
      salaries: data("salaries").length,
      inventory_items: data("inventory_items").length,
      inventory_transactions: data("inventory_transactions").length,
    },
  });

  window.addEventListener("load", () => {
    hookRenderAll();
    setTimeout(refreshAll, 400);
    setInterval(refreshAll, 4000);
  });
})();
