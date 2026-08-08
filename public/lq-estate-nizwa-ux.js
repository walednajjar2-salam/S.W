/**
 * منصة العقارات — مبدأ نزوى المطوّر (estate_* tables)
 * يبقي عقارات نزوى (quick-estate / qe_*) منصة مستقلة.
 */
(function () {
  "use strict";

  const LS_PROP = "lq_estate_nx_prop";
  const LS_BLD = "lq_estate_nx_bld";
  const LS_MOD = "lq_estate_nx_mod";

  const state = {
    propertyId: localStorage.getItem(LS_PROP) || "",
    buildingId: localStorage.getItem(LS_BLD) || "",
    module: localStorage.getItem(LS_MOD) || "units",
    statusFilter: "",
    search: "",
    budgetMax: "",
    drawer: null, // { entityType, entityId, tab }
    mounted: false,
  };

  function esc(v) {
    if (typeof htmlEscape === "function") return htmlEscape(String(v ?? ""));
    return String(v ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function rows(k) {
    return Array.isArray(Jawdah?.data?.[k]) ? Jawdah.data[k] : [];
  }
  function byRow(table, id) {
    return rows(table).find((x) => x.id === id) || {};
  }
  function moneyVal(n) {
    return typeof money === "function" ? money(n) : Number(n || 0).toFixed(3);
  }
  function fmtVal(n) {
    return typeof fmt === "function" ? fmt(n) : String(Number(n || 0));
  }
  function todayStr() {
    return typeof today === "function" ? today() : new Date().toISOString().slice(0, 10);
  }
  function toastOk(m) {
    if (typeof toast === "function") toast(m);
  }
  function toastBad(e) {
    if (typeof toastErr === "function") toastErr(e);
    else alert(String(e?.message || e));
  }

  function unitStatusAr(s) {
    const v = String(s || "").toLowerCase();
    if (v === "draft") return "مسودة";
    if (v === "reserved") return "محجوزة";
    if (v === "occupied" || v === "rented") return "مؤجرة";
    if (v === "maintenance") return "صيانة";
    if (v === "suspended") return "موقوفة";
    return "شاغرة";
  }
  function unitStatusTone(s) {
    const v = String(s || "").toLowerCase();
    if (v === "occupied" || v === "rented") return "ok";
    if (v === "reserved") return "warn";
    if (v === "maintenance" || v === "suspended") return "bad";
    return "idle";
  }
  function contractStatusAr(s) {
    const v = String(s || "").toLowerCase();
    if (v === "draft") return "مسودة";
    if (v === "approvalrequested") return "بانتظار الاعتماد";
    if (v === "approved") return "معتمد";
    if (v === "active") return "نشط";
    if (v === "ended") return "منتهٍ";
    if (v === "cancelled") return "مرفوض/ملغى";
    return s || "—";
  }
  function maintStatusAr(s) {
    const v = String(s || "").toLowerCase();
    if (v.includes("closed") || v === "done" || v === "completed") return "مغلقة";
    if (v.includes("progress") || v === "inprogress") return "قيد التنفيذ";
    return "مفتوحة";
  }

  function clientOptions(selected) {
    const list = rows("clients");
    return (
      `<option value="">— اختر العميل —</option>` +
      list
        .map(
          (c) =>
            `<option value="${esc(c.id)}" ${String(c.id) === String(selected || "") ? "selected" : ""}>${esc(c.name || c.id)}${c.phone ? " · " + esc(c.phone) : ""}</option>`
        )
        .join("")
    );
  }

  function imageUrl(row, kind) {
    if (typeof estateImageUrl === "function") return estateImageUrl(row, kind);
    const direct = String(row?.image || "").trim();
    if (direct) return direct;
    return "";
  }
  function thumbSrc(row, kind) {
    let url = imageUrl(row, kind) || "";
    if (url.startsWith("/uploads/") && Jawdah.token) {
      const sep = url.includes("?") ? "&" : "?";
      url = `${url}${sep}token=${encodeURIComponent(Jawdah.token)}`;
    }
    return url;
  }

  function unifyUnits(propertyId, buildingId) {
    const props = rows("estate_properties");
    const blds = rows("estate_buildings");
    const apts = rows("estate_apartments");
    const rooms = rows("estate_rooms");
    const out = [];
    apts.forEach((r) => {
      if (propertyId && r.property_id !== propertyId) return;
      if (buildingId && r.building_id !== buildingId) return;
      out.push({
        entityType: "apartment",
        entityId: r.id,
        table: "estate_apartments",
        kindLabel: "شقة",
        name: r.name || r.id,
        status: String(r.status || "vacant").toLowerCase(),
        rent: Number(r.rent_price || 0),
        floor: r.floor_no,
        area: r.area_sqm,
        propertyId: r.property_id,
        buildingId: r.building_id,
        propertyName: (props.find((p) => p.id === r.property_id) || {}).name || "—",
        buildingName: (blds.find((b) => b.id === r.building_id) || {}).name || "—",
        tenantId: r.tenant_client_id || r.booked_client_id || "",
        tenantPhone: r.tenant_phone || r.booked_client_phone || "",
        image: thumbSrc(r, "apartment"),
        raw: r,
      });
    });
    rooms.forEach((r) => {
      if (propertyId && r.property_id !== propertyId) return;
      if (buildingId && r.building_id !== buildingId) return;
      out.push({
        entityType: "room",
        entityId: r.id,
        table: "estate_rooms",
        kindLabel: "غرفة",
        name: r.name || r.id,
        status: String(r.status || "vacant").toLowerCase(),
        rent: Number(r.rent_price || 0),
        floor: r.floor_no,
        area: r.area_sqm,
        propertyId: r.property_id,
        buildingId: r.building_id,
        propertyName: (props.find((p) => p.id === r.property_id) || {}).name || "—",
        buildingName: (blds.find((b) => b.id === r.building_id) || {}).name || "—",
        tenantId: r.tenant_client_id || r.booked_client_id || "",
        tenantPhone: r.tenant_phone || r.booked_client_phone || "",
        image: thumbSrc(r, "room"),
        raw: r,
      });
    });
    out.sort((a, b) => String(a.name).localeCompare(String(b.name), "ar"));
    return out;
  }

  function scopedBuildings(propertyId) {
    const all = rows("estate_buildings");
    if (!propertyId) return all;
    return all.filter((b) => b.property_id === propertyId);
  }

  function ensureSelection() {
    const props = rows("estate_properties");
    if (!props.length) {
      state.propertyId = "";
      state.buildingId = "";
      return;
    }
    if (!state.propertyId || !props.some((p) => p.id === state.propertyId)) {
      state.propertyId = props[0].id;
    }
    const blds = scopedBuildings(state.propertyId);
    if (!blds.length) {
      state.buildingId = "";
      return;
    }
    if (!state.buildingId || !blds.some((b) => b.id === state.buildingId)) {
      state.buildingId = blds[0].id;
    }
    localStorage.setItem(LS_PROP, state.propertyId);
    localStorage.setItem(LS_BLD, state.buildingId);
    localStorage.setItem(LS_MOD, state.module);
  }

  function computeStats(units) {
    const total = units.length;
    const vacant = units.filter((u) => u.status === "vacant" || u.status === "available").length;
    const occupied = units.filter((u) => u.status === "occupied" || u.status === "rented").length;
    const reserved = units.filter((u) => u.status === "reserved").length;
    const maintUnits = units.filter((u) => u.status === "maintenance").length;
    const occPct = total ? Math.round((occupied / total) * 1000) / 10 : 0;
    const today = todayStr();
    const unitKeys = new Set(units.map((u) => `${u.entityType}::${u.entityId}`));
    const overdueInv = rows("estate_contract_invoices").filter((inv) => {
      if (String(inv.status || "").toLowerCase() === "paid") return false;
      if (!(String(inv.due_date || "") < today)) return false;
      const c = byRow("estate_contracts", inv.contract_id);
      const key = `${String(c.entity_type || "").toLowerCase()}::${c.entity_id}`;
      return unitKeys.has(key) || !state.buildingId;
    }).length;
    const openMaint = rows("estate_maintenance").filter((m) => {
      if (String(m.status || "").toLowerCase().includes("closed")) return false;
      if (state.propertyId && m.property_id && m.property_id !== state.propertyId) return false;
      if (state.buildingId && m.building_id && m.building_id !== state.buildingId) return false;
      return true;
    }).length;
    return { total, vacant, occupied, reserved, maintUnits, occPct, overdueInv, openMaint };
  }

  function shellHtml() {
    return `
<div class="lq-estate-nx" id="lqEstateNx">
  <header class="lq-estate-nx-head">
    <div>
      <h3>منصة العقارات</h3>
      <p class="mini">بنايات ← وحدات ← عقود ← صيانة · نفس مبدأ نزوى بطبقة مطوّرة</p>
    </div>
    <div class="lq-estate-nx-filters">
      <label class="mini">العقار / المحفظة
        <select id="lqNxProperty"></select>
      </label>
      <button type="button" class="ghost" id="lqNxCopyNizwa" title="نسخ من عقارات نزوى دون حذف الأصلية">نسخ بيانات نزوى</button>
    </div>
  </header>
  <nav class="lq-estate-nx-modules" id="lqNxModules" aria-label="وحدات العمل">
    <button type="button" data-mod="units">الوحدات</button>
    <button type="button" data-mod="contracts">العقود</button>
    <button type="button" data-mod="maint">الصيانة</button>
  </nav>

  <div class="lq-estate-nx-toolbar" id="lqNxToolbar"></div>
  <div class="lq-estate-nx-stats" id="lqNxStats"></div>
  <div class="lq-estate-nx-buildings" id="lqNxBuildings"></div>
  <div class="lq-estate-nx-body" id="lqNxBody"></div>
</div>

<div id="lqNxDrawerOverlay" class="lq-drawer-overlay hidden" aria-hidden="true">
  <aside class="lq-drawer lq-estate-nx-drawer" role="dialog" aria-modal="true">
    <header class="lq-drawer-head">
      <div>
        <h2 id="lqNxDrawerTitle">تفاصيل الوحدة</h2>
        <p class="mini" id="lqNxDrawerSub"></p>
      </div>
      <button type="button" class="ghost" id="lqNxDrawerClose" aria-label="إغلاق">✕</button>
    </header>
    <div class="lq-drawer-tabs" id="lqNxDrawerTabs"></div>
    <div class="lq-drawer-body" id="lqNxDrawerBody"></div>
    <footer class="lq-drawer-foot" id="lqNxDrawerFoot"></footer>
  </aside>
</div>`;
  }

  function mountShell() {
    const sec = document.getElementById("sec-estate-platform");
    if (!sec) return false;
    if (!state.mounted || !document.getElementById("lqEstateNx")) {
      sec.innerHTML = shellHtml();
      state.mounted = true;
      bindShell();
    }
    return true;
  }

  function bindShell() {
    const prop = document.getElementById("lqNxProperty");
    prop?.addEventListener("change", () => {
      state.propertyId = prop.value;
      state.buildingId = "";
      localStorage.setItem(LS_PROP, state.propertyId);
      render();
    });
    document.getElementById("lqNxCopyNizwa")?.addEventListener("click", copyNizwaData);
    document.getElementById("lqNxModules")?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-mod]");
      if (!btn) return;
      state.module = btn.getAttribute("data-mod");
      localStorage.setItem(LS_MOD, state.module);
      render();
    });
    document.getElementById("lqNxBuildings")?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-bld]");
      if (!btn) return;
      state.buildingId = btn.getAttribute("data-bld");
      localStorage.setItem(LS_BLD, state.buildingId);
      render();
    });
    document.getElementById("lqNxDrawerClose")?.addEventListener("click", closeDrawer);
    document.getElementById("lqNxDrawerOverlay")?.addEventListener("click", (e) => {
      if (e.target.id === "lqNxDrawerOverlay") closeDrawer();
    });
  }

  function renderPropertySelect() {
    const sel = document.getElementById("lqNxProperty");
    if (!sel) return;
    const props = rows("estate_properties");
    if (!props.length) {
      sel.innerHTML = `<option value="">لا توجد عقارات</option>`;
      return;
    }
    sel.innerHTML = props
      .map(
        (p) =>
          `<option value="${esc(p.id)}" ${p.id === state.propertyId ? "selected" : ""}>${esc(p.name || p.id)}${p.location ? " · " + esc(p.location) : ""}</option>`
      )
      .join("");
  }

  function renderStats(units) {
    const host = document.getElementById("lqNxStats");
    if (!host) return;
    const s = computeStats(units);
    host.innerHTML = `
      <button type="button" class="lq-estate-nx-stat" data-stat="all"><span>إجمالي الوحدات</span><strong>${fmtVal(s.total)}</strong></button>
      <button type="button" class="lq-estate-nx-stat" data-stat="vacant"><span>شاغرة</span><strong>${fmtVal(s.vacant)}</strong></button>
      <button type="button" class="lq-estate-nx-stat" data-stat="occupied"><span>مؤجرة</span><strong>${fmtVal(s.occupied)}</strong></button>
      <button type="button" class="lq-estate-nx-stat" data-stat="reserved"><span>محجوزة</span><strong>${fmtVal(s.reserved)}</strong></button>
      <button type="button" class="lq-estate-nx-stat"><span>نسبة الإشغال</span><strong>${fmtVal(s.occPct)}%</strong></button>
      <button type="button" class="lq-estate-nx-stat" data-mod-jump="contracts"><span>متأخرات عقود</span><strong>${fmtVal(s.overdueInv)}</strong></button>
      <button type="button" class="lq-estate-nx-stat" data-mod-jump="maint"><span>صيانة مفتوحة</span><strong>${fmtVal(s.openMaint)}</strong></button>
    `;
    host.querySelectorAll("[data-stat]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const st = btn.getAttribute("data-stat");
        state.module = "units";
        state.statusFilter = st === "all" ? "" : st;
        state.budgetMax = "";
        render();
      });
    });
    host.querySelectorAll("[data-mod-jump]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.module = btn.getAttribute("data-mod-jump");
        render();
      });
    });
  }

  function renderModules() {
    document.querySelectorAll("#lqNxModules [data-mod]").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-mod") === state.module);
    });
  }

  function renderBuildings() {
    const host = document.getElementById("lqNxBuildings");
    if (!host) return;
    const blds = scopedBuildings(state.propertyId);
    if (!blds.length) {
      host.innerHTML = `<p class="mini">لا توجد بنايات لهذا العقار. أضف بناية من قائمة العقارات أو عبر الإضافة السريعة.</p>`;
      return;
    }
    host.innerHTML = blds
      .map((b) => {
        const units = unifyUnits(state.propertyId, b.id);
        const occ = units.filter((u) => u.status === "occupied" || u.status === "rented").length;
        const vac = units.filter((u) => u.status === "vacant" || u.status === "available").length;
        return `<button type="button" class="lq-estate-nx-bld ${b.id === state.buildingId ? "active" : ""}" data-bld="${esc(b.id)}">
          <b>${esc(b.name || b.id)}</b>
          <small>${fmtVal(units.length)} وحدة · مؤجر ${fmtVal(occ)} · شاغر ${fmtVal(vac)}</small>
        </button>`;
      })
      .join("");
  }

  function renderToolbar() {
    const host = document.getElementById("lqNxToolbar");
    if (!host) return;
    if (state.module === "units") {
      host.innerHTML = `
        <input id="lqNxSearch" type="search" placeholder="بحث اسم الوحدة / الهاتف…" value="${esc(state.search)}">
        <select id="lqNxStatus">
          <option value="">كل الحالات</option>
          <option value="vacant" ${state.statusFilter === "vacant" ? "selected" : ""}>شاغرة</option>
          <option value="occupied" ${state.statusFilter === "occupied" ? "selected" : ""}>مؤجرة</option>
          <option value="reserved" ${state.statusFilter === "reserved" ? "selected" : ""}>محجوزة</option>
          <option value="maintenance" ${state.statusFilter === "maintenance" ? "selected" : ""}>صيانة</option>
        </select>
        <label class="lq-estate-nx-budget mini">حد إيجار الشواغر (OMR)
          <input id="lqNxBudget" type="number" min="0" step="0.001" placeholder="مثل 180" value="${esc(state.budgetMax)}">
        </label>
        <button type="button" class="ghost" id="lqNxBudgetGo">بحث الشواغر</button>
        <button type="button" class="gold-btn" id="lqNxAddApt">+ شقة</button>
        <button type="button" class="ghost" id="lqNxAddRoom">+ غرفة</button>
      `;
      const sync = () => {
        state.search = document.getElementById("lqNxSearch")?.value || "";
        state.statusFilter = document.getElementById("lqNxStatus")?.value || "";
        state.budgetMax = document.getElementById("lqNxBudget")?.value || "";
        renderBody();
      };
      document.getElementById("lqNxSearch")?.addEventListener("input", sync);
      document.getElementById("lqNxStatus")?.addEventListener("change", sync);
      document.getElementById("lqNxBudget")?.addEventListener("change", sync);
      document.getElementById("lqNxBudgetGo")?.addEventListener("click", () => {
        state.statusFilter = "vacant";
        state.budgetMax = document.getElementById("lqNxBudget")?.value || "";
        const st = document.getElementById("lqNxStatus");
        if (st) st.value = "vacant";
        renderBody();
      });
      document.getElementById("lqNxAddApt")?.addEventListener("click", () => createUnitPrompt("apartment"));
      document.getElementById("lqNxAddRoom")?.addEventListener("click", () => createUnitPrompt("room"));
      return;
    }
    if (state.module === "contracts") {
      host.innerHTML = `<p class="mini">دورة العقد: مسودة → طلب اعتماد → اعتماد → تفعيل. الرفض يُلغي المسودة قيد الاعتماد.</p>`;
      return;
    }
    host.innerHTML = `
      <button type="button" class="gold-btn" id="lqNxAddMaint">+ طلب صيانة</button>
      <span class="mini">من جدول estate_maintenance للبناية/العقار الحالي</span>
    `;
    document.getElementById("lqNxAddMaint")?.addEventListener("click", createMaintPrompt);
  }

  function filterUnits(units) {
    let list = units.slice();
    const st = String(state.statusFilter || "").toLowerCase();
    if (st === "vacant") list = list.filter((u) => u.status === "vacant" || u.status === "available");
    else if (st === "occupied") list = list.filter((u) => u.status === "occupied" || u.status === "rented");
    else if (st) list = list.filter((u) => u.status === st);
    const q = String(state.search || "").trim().toLowerCase();
    if (q) {
      list = list.filter((u) => {
        const tenant = byRow("clients", u.tenantId);
        const blob = `${u.name} ${u.kindLabel} ${u.tenantPhone} ${tenant.name || ""} ${tenant.phone || ""}`.toLowerCase();
        return blob.includes(q);
      });
    }
    const budget = Number(state.budgetMax || 0);
    if (budget > 0) {
      list = list.filter((u) => {
        const vacant = u.status === "vacant" || u.status === "available";
        return vacant && u.rent > 0 && u.rent <= budget;
      });
    }
    return list;
  }

  function renderUnitsTable(units) {
    const list = filterUnits(units);
    if (!list.length) {
      return `<div class="card"><p class="mini">لا توجد وحدات مطابقة للفلاتر الحالية.</p></div>`;
    }
    const body = list
      .map((u) => {
        const tenant = byRow("clients", u.tenantId);
        const tenantLabel = tenant.name || u.raw.booked_client_name || "—";
        const img = u.image
          ? `<img class="lq-estate-nx-thumb" src="${esc(u.image)}" alt="">`
          : `<span class="lq-estate-nx-thumb ph">${u.kindLabel === "شقة" ? "ش" : "غ"}</span>`;
        return `<tr data-open-unit="${esc(u.entityType)}:${esc(u.entityId)}">
          <td>${img}</td>
          <td><b>${esc(u.name)}</b><div class="mini">${esc(u.kindLabel)}</div></td>
          <td><span class="lq-status ${unitStatusTone(u.status)}">${esc(unitStatusAr(u.status))}</span></td>
          <td>${moneyVal(u.rent)}</td>
          <td>${u.floor != null && u.floor !== "" ? esc(u.floor) : "—"}</td>
          <td>${esc(tenantLabel)}<div class="mini">${esc(u.tenantPhone || tenant.phone || "")}</div></td>
          <td><button type="button" class="gold-btn" data-open-unit="${esc(u.entityType)}:${esc(u.entityId)}">فتح</button></td>
        </tr>`;
      })
      .join("");
    return `<div class="lq-estate-nx-table-wrap"><table class="lq-estate-nx-table">
      <thead><tr><th></th><th>الوحدة</th><th>الحالة</th><th>الإيجار</th><th>الطابق</th><th>المستأجر</th><th></th></tr></thead>
      <tbody>${body}</tbody>
    </table></div>`;
  }

  function renderContractsPanel(units) {
    const keys = new Set(units.map((u) => `${u.entityType}::${u.entityId}`));
    let contracts = rows("estate_contracts");
    if (state.buildingId || state.propertyId) {
      contracts = contracts.filter((c) => keys.has(`${String(c.entity_type || "").toLowerCase()}::${c.entity_id}`));
    }
    contracts = contracts.slice().sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    if (!contracts.length) {
      return `<div class="card"><p class="mini">لا توجد عقود لهذه البناية. افتح وحدة وأنشئ مسودة عقد من درج التفاصيل.</p></div>`;
    }
    return `<div class="lq-estate-nx-table-wrap"><table class="lq-estate-nx-table">
      <thead><tr><th>العقد</th><th>الوحدة</th><th>العميل</th><th>الفترة</th><th>الإيجار</th><th>الحالة</th><th>إجراءات</th></tr></thead>
      <tbody>${contracts
        .map((c) => {
          const st = String(c.status || "").toLowerCase();
          const unit =
            String(c.entity_type || "").toLowerCase() === "room"
              ? byRow("estate_rooms", c.entity_id)
              : byRow("estate_apartments", c.entity_id);
          const actions = [];
          if (st === "draft") {
            actions.push(`<button type="button" class="gold-btn" data-c-act="request" data-cid="${esc(c.id)}">طلب اعتماد</button>`);
          }
          if (st === "approvalrequested" && typeof canDecideApprovals === "function" && canDecideApprovals()) {
            actions.push(`<button type="button" class="gold-btn" data-c-act="approve" data-cid="${esc(c.id)}">اعتماد</button>`);
            actions.push(`<button type="button" class="danger" data-c-act="reject" data-cid="${esc(c.id)}">رفض</button>`);
          }
          if (st === "approved") {
            actions.push(`<button type="button" class="gold-btn" data-c-act="activate" data-cid="${esc(c.id)}">تفعيل</button>`);
          }
          if (st === "active") {
            actions.push(`<button type="button" class="ghost" data-c-act="close" data-cid="${esc(c.id)}">إنهاء</button>`);
          }
          actions.push(
            `<button type="button" class="ghost" data-open-unit="${esc(String(c.entity_type || "apartment").toLowerCase())}:${esc(c.entity_id)}">الوحدة</button>`
          );
          return `<tr>
            <td><b>${esc(c.contract_no || c.id)}</b></td>
            <td>${esc(unit.name || c.entity_id)} <span class="mini">${esc(c.entity_type === "room" ? "غرفة" : "شقة")}</span></td>
            <td>${esc(byRow("clients", c.client_id).name || c.client_id)}</td>
            <td>${esc(c.start_date || "—")} → ${esc(c.end_date || "—")}</td>
            <td>${moneyVal(c.rent_amount)}</td>
            <td><span class="badge">${esc(contractStatusAr(st))}</span></td>
            <td class="lq-estate-nx-acts">${actions.join(" ")}</td>
          </tr>`;
        })
        .join("")}</tbody>
    </table></div>`;
  }

  function renderMaintPanel() {
    let list = rows("estate_maintenance").slice();
    if (state.propertyId) list = list.filter((m) => !m.property_id || m.property_id === state.propertyId);
    if (state.buildingId) list = list.filter((m) => !m.building_id || m.building_id === state.buildingId);
    list.sort((a, b) => String(b.maintenance_date || "").localeCompare(String(a.maintenance_date || "")));
    if (!list.length) {
      return `<div class="card"><p class="mini">لا توجد طلبات صيانة. أضف طلباً من الزر أعلاه.</p></div>`;
    }
    return `<div class="lq-estate-nx-table-wrap"><table class="lq-estate-nx-table">
      <thead><tr><th>التاريخ</th><th>العنوان</th><th>الوحدة</th><th>الأولوية</th><th>التكلفة</th><th>الحالة</th><th></th></tr></thead>
      <tbody>${list
        .map((m) => {
          const unitName = m.room_id
            ? byRow("estate_rooms", m.room_id).name
            : m.apartment_id
              ? byRow("estate_apartments", m.apartment_id).name
              : "—";
          const openKey = m.room_id
            ? `room:${m.room_id}`
            : m.apartment_id
              ? `apartment:${m.apartment_id}`
              : "";
          return `<tr>
            <td>${esc(m.maintenance_date || "—")}</td>
            <td><b>${esc(m.title || m.id)}</b><div class="mini">${esc(m.responsible_name || "")}</div></td>
            <td>${esc(unitName || "—")}</td>
            <td>${esc(m.priority || "—")}</td>
            <td>${moneyVal(m.total_cost || Number(m.parts_cost || 0) + Number(m.labor_cost || 0))}</td>
            <td><span class="badge">${esc(maintStatusAr(m.status))}</span></td>
            <td>${
              openKey
                ? `<button type="button" class="ghost" data-open-unit="${esc(openKey)}">الوحدة</button>`
                : ""
            }
            <button type="button" class="ghost" data-m-edit="${esc(m.id)}">تعديل</button></td>
          </tr>`;
        })
        .join("")}</tbody>
    </table></div>`;
  }

  function renderBody() {
    const body = document.getElementById("lqNxBody");
    if (!body) return;
    const units = unifyUnits(state.propertyId, state.buildingId);
    if (state.module === "units") body.innerHTML = renderUnitsTable(units);
    else if (state.module === "contracts") body.innerHTML = renderContractsPanel(units);
    else body.innerHTML = renderMaintPanel();

    body.querySelectorAll("[data-open-unit]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const [etype, eid] = String(el.getAttribute("data-open-unit") || "").split(":");
        if (etype && eid) openUnitDrawer(etype, eid);
      });
    });
    body.querySelectorAll("[data-c-act]").forEach((btn) => {
      btn.addEventListener("click", () => handleContractAction(btn.getAttribute("data-c-act"), btn.getAttribute("data-cid")));
    });
    body.querySelectorAll("[data-m-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (typeof editRecord === "function") editRecord("estate_maintenance", btn.getAttribute("data-m-edit"));
      });
    });
  }

  async function handleContractAction(act, id) {
    try {
      if (act === "request" && typeof requestEstateContractApproval === "function") {
        return requestEstateContractApproval(id);
      }
      if (act === "approve" && typeof approveEstateContract === "function") {
        return approveEstateContract(id);
      }
      if (act === "activate" && typeof activateEstateContract === "function") {
        return activateEstateContract(id);
      }
      if (act === "close" && typeof closeEstateContractById === "function") {
        return closeEstateContractById(id);
      }
      if (act === "reject") {
        if (typeof canDecideApprovals === "function" && !canDecideApprovals()) {
          return toastBad("لا تملك صلاحية رفض الاعتماد");
        }
        if (!confirm("رفض طلب الاعتماد وإلغاء العقد؟")) return;
        await api(`estate_contracts/${id}`, {
          method: "PUT",
          body: JSON.stringify({ status: "Cancelled", notes: "رفض الاعتماد من منصة العقارات" }),
        });
        toastOk("تم رفض/إلغاء العقد");
        await loadAll();
        render();
      }
    } catch (e) {
      toastBad(e);
    }
  }

  function closeDrawer() {
    state.drawer = null;
    document.getElementById("lqNxDrawerOverlay")?.classList.add("hidden");
  }

  function openUnitDrawer(entityType, entityId, tab) {
    state.drawer = { entityType, entityId, tab: tab || "details" };
    const overlay = document.getElementById("lqNxDrawerOverlay");
    if (!overlay) return;
    overlay.classList.remove("hidden");
    paintDrawer();
  }

  function unitContracts(entityType, entityId) {
    return rows("estate_contracts").filter(
      (c) => String(c.entity_type || "").toLowerCase() === entityType && String(c.entity_id) === String(entityId)
    );
  }

  function unitInvoices(entityType, entityId) {
    const ids = new Set(unitContracts(entityType, entityId).map((c) => c.id));
    return rows("estate_contract_invoices").filter((i) => ids.has(i.contract_id));
  }

  function paintDrawer() {
    if (!state.drawer) return;
    const { entityType, entityId, tab } = state.drawer;
    const table = entityType === "room" ? "estate_rooms" : "estate_apartments";
    const row = byRow(table, entityId);
    if (!row.id) {
      closeDrawer();
      return;
    }
    const kind = entityType === "room" ? "غرفة" : "شقة";
    document.getElementById("lqNxDrawerTitle").textContent = `${kind}: ${row.name || row.id}`;
    document.getElementById("lqNxDrawerSub").textContent = `${unitStatusAr(row.status)} · ${moneyVal(row.rent_price)} · ${byRow("estate_buildings", row.building_id).name || ""}`;

    const tabs = document.getElementById("lqNxDrawerTabs");
    tabs.innerHTML = `
      <button type="button" data-dtab="details" class="${tab === "details" ? "active" : ""}">التفاصيل</button>
      <button type="button" data-dtab="contracts" class="${tab === "contracts" ? "active" : ""}">العقود</button>
      <button type="button" data-dtab="finance" class="${tab === "finance" ? "active" : ""}">فواتير</button>
    `;
    tabs.querySelectorAll("[data-dtab]").forEach((b) => {
      b.addEventListener("click", () => {
        state.drawer.tab = b.getAttribute("data-dtab");
        paintDrawer();
      });
    });

    const body = document.getElementById("lqNxDrawerBody");
    const foot = document.getElementById("lqNxDrawerFoot");
    if (tab === "details") {
      const img = thumbSrc(row, entityType === "room" ? "room" : "apartment");
      body.innerHTML = `
        ${img ? `<img class="lq-estate-nx-hero" src="${esc(img)}" alt="">` : ""}
        <div class="form lq-estate-nx-form">
          <label>الاسم<input id="nxUName" value="${esc(row.name || "")}"></label>
          <label>الحالة
            <select id="nxUStatus">
              ${["vacant", "reserved", "occupied", "maintenance", "suspended"]
                .map(
                  (s) =>
                    `<option value="${s}" ${String(row.status || "").toLowerCase() === s ? "selected" : ""}>${unitStatusAr(s)}</option>`
                )
                .join("")}
            </select>
          </label>
          <label>الإيجار (OMR)<input id="nxURent" type="number" min="0" step="0.001" value="${esc(row.rent_price || 0)}"></label>
          <label>عربون الحجز<input id="nxUDeposit" type="number" min="0" step="0.001" value="${esc(row.booking_deposit || 0)}"></label>
          <label>الطابق<input id="nxUFloor" type="number" value="${esc(row.floor_no ?? "")}"></label>
          <label>المساحة م²<input id="nxUArea" type="number" min="0" step="0.01" value="${esc(row.area_sqm || 0)}"></label>
          <label>المستأجر (عملاء النظام)<select id="nxUTenant">${clientOptions(row.tenant_client_id || row.booked_client_id)}</select></label>
          <label>هاتف المستأجر<input id="nxUPhone" value="${esc(row.tenant_phone || row.booked_client_phone || "")}"></label>
          <label>المسؤول<input id="nxUManager" value="${esc(row.manager_name || "")}"></label>
          <label>ملاحظات<textarea id="nxUNotes" rows="3">${esc(row.notes || "")}</textarea></label>
        </div>`;
      foot.innerHTML = `
        <button type="button" class="ghost" id="nxUClose">إغلاق</button>
        ${
          String(row.status || "").toLowerCase() === "reserved" && typeof canEstateConvertReservation === "function" && canEstateConvertReservation()
            ? `<button type="button" class="ghost" id="nxUConvert">تحويل الحجز</button>`
            : ""
        }
        ${
          typeof canEstateCreateContract === "function" && canEstateCreateContract() && !["maintenance", "suspended"].includes(String(row.status || "").toLowerCase())
            ? `<button type="button" class="ghost" id="nxUNewContract">مسودة عقد</button>`
            : ""
        }
        <button type="button" class="gold-btn" id="nxUSave">حفظ</button>`;
      document.getElementById("nxUClose")?.addEventListener("click", closeDrawer);
      document.getElementById("nxUSave")?.addEventListener("click", () => saveUnit(entityType, entityId));
      document.getElementById("nxUConvert")?.addEventListener("click", () => {
        if (typeof convertEstateReservation === "function") convertEstateReservation(entityType, entityId);
      });
      document.getElementById("nxUNewContract")?.addEventListener("click", () => createContractForUnit(entityType, entityId, row));
      document.getElementById("nxUTenant")?.addEventListener("change", (e) => {
        const c = byRow("clients", e.target.value);
        const phone = document.getElementById("nxUPhone");
        if (c.phone && phone && !phone.value) phone.value = c.phone;
      });
      return;
    }

    if (tab === "contracts") {
      const contracts = unitContracts(entityType, entityId);
      body.innerHTML =
        contracts
          .map((c) => {
            const st = String(c.status || "").toLowerCase();
            let acts = "";
            if (st === "draft") acts += `<button type="button" class="gold-btn" data-c-act="request" data-cid="${esc(c.id)}">طلب اعتماد</button> `;
            if (st === "approvalrequested" && typeof canDecideApprovals === "function" && canDecideApprovals()) {
              acts += `<button type="button" class="gold-btn" data-c-act="approve" data-cid="${esc(c.id)}">اعتماد</button> `;
              acts += `<button type="button" class="danger" data-c-act="reject" data-cid="${esc(c.id)}">رفض</button> `;
            }
            if (st === "approved") acts += `<button type="button" class="gold-btn" data-c-act="activate" data-cid="${esc(c.id)}">تفعيل</button> `;
            if (st === "active") acts += `<button type="button" class="ghost" data-c-act="close" data-cid="${esc(c.id)}">إنهاء</button> `;
            return `<div class="statement-row"><span><b>${esc(c.contract_no || c.id)}</b><br><small>${esc(c.start_date)} → ${esc(c.end_date)} · ${moneyVal(c.rent_amount)}</small></span><b>${esc(contractStatusAr(st))}</b></div><div class="toolbar" style="margin-bottom:10px">${acts}</div>`;
          })
          .join("") || `<p class="mini">لا عقود بعد لهذه الوحدة.</p>`;
      body.querySelectorAll("[data-c-act]").forEach((btn) => {
        btn.addEventListener("click", () => handleContractAction(btn.getAttribute("data-c-act"), btn.getAttribute("data-cid")));
      });
      foot.innerHTML = `
        <button type="button" class="ghost" id="nxUClose">إغلاق</button>
        ${
          typeof canEstateCreateContract === "function" && canEstateCreateContract()
            ? `<button type="button" class="gold-btn" id="nxUNewContract">مسودة عقد جديدة</button>`
            : ""
        }`;
      document.getElementById("nxUClose")?.addEventListener("click", closeDrawer);
      document.getElementById("nxUNewContract")?.addEventListener("click", () => createContractForUnit(entityType, entityId, row));
      return;
    }

    const inv = unitInvoices(entityType, entityId);
    body.innerHTML =
      inv
        .map((i) => {
          const due = Math.max(0, Number(i.amount || 0) - Number(i.paid_amount || 0));
          return `<div class="statement-row"><span>${esc(i.invoice_no || i.id)}<br><small>استحقاق ${esc(i.due_date || "—")}</small></span><b>${moneyVal(due)} · ${esc(i.status || "")}</b></div>`;
        })
        .join("") || `<p class="mini">لا فواتير عقد بعد. فعّل العقد لتوليد الجدول.</p>`;
    const openInv = inv.filter((i) => String(i.status || "").toLowerCase() !== "paid");
    foot.innerHTML = `
      <button type="button" class="ghost" id="nxUClose">إغلاق</button>
      ${
        openInv.length
          ? `<button type="button" class="gold-btn" id="nxUPay">تحصيل فاتورة</button>`
          : ""
      }`;
    document.getElementById("nxUClose")?.addEventListener("click", closeDrawer);
    document.getElementById("nxUPay")?.addEventListener("click", async () => {
      const invId = openInv[0]?.id;
      if (!invId) return;
      const amount = prompt("مبلغ التحصيل", String(Math.max(0, Number(openInv[0].amount || 0) - Number(openInv[0].paid_amount || 0))));
      if (amount === null) return;
      try {
        await api("estate_contract_pay_invoice", {
          method: "POST",
          body: JSON.stringify({ invoice_id: invId, amount: Number(amount || 0), payment_date: todayStr() }),
        });
        toastOk("تم التحصيل");
        await loadAll();
        paintDrawer();
        render();
      } catch (e) {
        toastBad(e);
      }
    });
  }

  async function saveUnit(entityType, entityId) {
    const table = entityType === "room" ? "estate_rooms" : "estate_apartments";
    const row = byRow(table, entityId);
    const tenantId = document.getElementById("nxUTenant")?.value || "";
    const tenant = byRow("clients", tenantId);
    const status = String(document.getElementById("nxUStatus")?.value || "vacant").toLowerCase();
    const payload = {
      ...row,
      name: document.getElementById("nxUName")?.value || row.name,
      status,
      rent_price: Number(document.getElementById("nxURent")?.value || 0),
      booking_deposit: Number(document.getElementById("nxUDeposit")?.value || 0),
      floor_no: document.getElementById("nxUFloor")?.value || null,
      area_sqm: Number(document.getElementById("nxUArea")?.value || 0),
      tenant_client_id: tenantId || null,
      tenant_phone: document.getElementById("nxUPhone")?.value || tenant.phone || "",
      manager_name: document.getElementById("nxUManager")?.value || "",
      notes: document.getElementById("nxUNotes")?.value || "",
      last_update: todayStr(),
    };
    if (
      typeof canEstatePricingEdit === "function" &&
      !canEstatePricingEdit() &&
      (Number(payload.rent_price) !== Number(row.rent_price || 0) ||
        Number(payload.booking_deposit) !== Number(row.booking_deposit || 0))
    ) {
      return toastBad("لا تملك صلاحية تعديل التسعير العقاري");
    }
    try {
      await api(`${table}/${entityId}`, { method: "PUT", body: JSON.stringify(payload) });
      toastOk("تم حفظ الوحدة");
      await loadAll();
      render();
      openUnitDrawer(entityType, entityId, "details");
    } catch (e) {
      toastBad(e);
    }
  }

  async function createContractForUnit(entityType, entityId, row) {
    if (typeof canEstateCreateContract === "function" && !canEstateCreateContract()) {
      return toastBad("لا تملك صلاحية إنشاء العقود");
    }
    const clientId = row.tenant_client_id || row.booked_client_id || "";
    if (!clientId) return toastBad("اربط مستأجراً من العملاء أولاً ثم أنشئ العقد");
    const start = prompt("تاريخ بداية العقد", row.reservation_start_date || todayStr());
    if (start === null) return;
    const end = prompt("تاريخ نهاية العقد", row.reservation_end_date || "");
    if (end === null) return;
    const rent = prompt("قيمة الإيجار", String(row.rent_price || 0));
    if (rent === null) return;
    try {
      await api("estate_convert_to_contract", {
        method: "POST",
        body: JSON.stringify({
          entity_type: entityType,
          entity_id: entityId,
          tenant_client_id: clientId,
          start_date: start,
          end_date: end,
          rent_amount: Number(rent || 0),
          payment_cycle: "monthly",
          notes: "",
        }),
      });
      toastOk("تم إنشاء مسودة العقد");
      await loadAll();
      state.module = "contracts";
      openUnitDrawer(entityType, entityId, "contracts");
      render();
    } catch (e) {
      toastBad(e);
    }
  }

  async function createUnitPrompt(kind) {
    if (!state.propertyId || !state.buildingId) return toastBad("اختر عقاراً وبناية أولاً");
    const name = prompt(kind === "room" ? "اسم الغرفة" : "اسم الشقة");
    if (!name) return;
    const rent = Number(prompt("الإيجار (OMR)", "0") || 0);
    const table = kind === "room" ? "estate_rooms" : "estate_apartments";
    const payload =
      kind === "room"
        ? {
            property_id: state.propertyId,
            building_id: state.buildingId,
            name,
            unit_kind: "غرفة مستقلة",
            room_type: "غرفة مستقلة",
            status: "vacant",
            rent_price: rent,
            last_update: todayStr(),
          }
        : {
            property_id: state.propertyId,
            building_id: state.buildingId,
            name,
            unit_kind: "شقة كاملة",
            status: "vacant",
            rent_price: rent,
            last_update: todayStr(),
          };
    try {
      await api(table, { method: "POST", body: JSON.stringify(payload) });
      toastOk("تمت إضافة الوحدة");
      await loadAll();
      render();
    } catch (e) {
      toastBad(e);
    }
  }

  async function copyNizwaData() {
    if (!confirm("نسخ بيانات عقارات نزوى إلى منصة العقارات؟\n(نسخ فقط — لن تُحذف بيانات نزوى)")) return;
    try {
      const res = await api("estate_copy_from_nizwa", { method: "POST", body: "{}" });
      const c = res.created || {};
      toastOk(
        `تم النسخ: ${c.apartments || 0} شقة · ${c.buildings || 0} بناية · ${c.clients || 0} عميل · ${c.contracts || 0} عقد`
      );
      await loadAll();
      render();
    } catch (e) {
      toastBad(e);
    }
  }

  async function createMaintPrompt() {
    const title = prompt("عنوان طلب الصيانة");
    if (!title) return;
    try {
      await api("estate_maintenance", {
        method: "POST",
        body: JSON.stringify({
          property_id: state.propertyId || null,
          building_id: state.buildingId || null,
          title,
          status: "Open",
          priority: "Medium",
          maintenance_date: todayStr(),
          parts_cost: 0,
          labor_cost: 0,
          total_cost: 0,
        }),
      });
      toastOk("تم تسجيل طلب الصيانة");
      await loadAll();
      state.module = "maint";
      render();
    } catch (e) {
      toastBad(e);
    }
  }

  function suppressLegacyChrome() {
    document.getElementById("lqForceEstateDock")?.setAttribute("hidden", "true");
    const fd = document.getElementById("lqForceEstateDock");
    if (fd) fd.style.display = "none";
    // لوحة exec القديمة كانت تُحقَن فوق المنصة — نخفيها لصالح تجربة نزوى
    const exec = document.getElementById("lqExecBoard-realestate");
    if (exec) exec.remove();
  }

  function render() {
    if (!mountShell()) return;
    suppressLegacyChrome();
    ensureSelection();
    const unitsAllProp = unifyUnits(state.propertyId, "");
    const unitsBld = unifyUnits(state.propertyId, state.buildingId);
    renderPropertySelect();
    renderStats(state.buildingId ? unitsBld : unitsAllProp);
    renderModules();
    renderBuildings();
    renderToolbar();
    renderBody();
    if (state.drawer) paintDrawer();
    if (typeof ensureEnglishDigits === "function") {
      ensureEnglishDigits(document.getElementById("sec-estate-platform"));
    }
  }

  window.showEstatePanel = function (panel) {
    const map = { maint: "maint", booking: "contracts", finance: "contracts", tables: "units", overview: "units", add: "units", media: "units", ops: "units" };
    state.module = map[panel] || "units";
    localStorage.setItem(LS_MOD, state.module);
    try {
      localStorage.setItem("jawdah_estate_panel", panel || "overview");
    } catch (_) {}
    if (document.getElementById("sec-estate-platform")?.classList.contains("active")) render();
  };

  /** إخفاء dock اللوحات القديمة حتى لا يتشتت الموظف */
  window.ensureForceEstateDock = function () {
    const host = document.getElementById("lqForceEstateDock");
    if (host) {
      host.style.display = "none";
      host.setAttribute("hidden", "true");
      host.innerHTML = "";
    }
  };

  window.renderEstatePlatform = render;
  window.openEstateUnitDrawer = openUnitDrawer;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      if (document.getElementById("sec-estate-platform")?.classList.contains("active")) render();
    });
  }
})();
