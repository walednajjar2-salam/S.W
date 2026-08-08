/**
 * Executive shell v2 — estate / hospitality / products / overview + contract timeline drawer
 */
(function () {
  "use strict";

  const VALID = new Set(["realestate", "hospitality", "products", "overview", "accounting"]);

  function t(k, vars) {
    return window.LQ_I18N ? window.LQ_I18N.t(k, vars) : k;
  }
  function money(n) {
    return window.LQ_I18N ? window.LQ_I18N.formatMoney(n) : "OMR " + Number(n || 0).toFixed(3);
  }
  function fmtDate(iso) {
    return window.LQ_I18N ? window.LQ_I18N.formatDate(iso) : String(iso || "—").slice(0, 10);
  }
  function esc(v) {
    return String(v ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function data(table) {
    return (window.Jawdah && Array.isArray(Jawdah.data?.[table]) && Jawdah.data[table]) || [];
  }
  function byId(table, id) {
    return data(table).find((r) => r.id === id) || null;
  }
  function propLabel(p) {
    if (!p) return "—";
    if (typeof window.propertyLabel === "function") return window.propertyLabel(p);
    return p.name || [p.building_no, p.apartment_no, p.room_no].filter(Boolean).join(" / ") || p.id;
  }
  function clientName(id) {
    return byId("clients", id)?.name || id || "—";
  }

  function enableExecTheme() {
    document.body.classList.add("lq-exec");
    document.body.classList.remove("lq-edition-terrifying");
  }

  function decorateLogin() {
    const card = document.querySelector("#loginScreen .login-glass-card, #loginScreen .ev-auth-card");
    if (!card) return;
    let mount = document.getElementById("loginLangMount");
    if (!mount) {
      mount = document.createElement("div");
      mount.id = "loginLangMount";
      mount.className = "login-topbar-lang";
      card.insertBefore(mount, card.firstChild);
    }
    if (window.LQ_I18N) {
      // Rebuilding the markup would tear down the very <select> whose change
      // event brought us here; bindSwitcher re-syncs the value on its own.
      if (!document.getElementById("loginLang")) {
        mount.innerHTML = window.LQ_I18N.langSwitcherHtml("loginLang");
      }
      window.LQ_I18N.bindSwitcher("loginLang");
    }
    const title = card.querySelector(".login-card-title");
    const sub = card.querySelector(".login-card-sub");
    const btn = document.getElementById("loginBtn");
    const user = document.getElementById("loginUser");
    const pass = document.getElementById("loginPass");
    if (title) title.setAttribute("data-i18n", "welcomeBack");
    if (sub) sub.setAttribute("data-i18n", "signInContinue");
    if (btn) btn.setAttribute("data-i18n", "signIn");
    if (user) user.setAttribute("data-i18n-placeholder", "username");
    if (pass) pass.setAttribute("data-i18n-placeholder", "password");
    window.LQ_I18N?.applyDocument();
  }

  function headActions(extra) {
    return `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      ${extra || ""}
      <button type="button" class="ghost" onclick="location.href='/portal-select.html'">${t("switchPortal")}</button>
      <span id="execLangMount"></span>
    </div>`;
  }

  function bindLang() {
    const langMount = document.getElementById("execLangMount");
    if (langMount && window.LQ_I18N) {
      langMount.innerHTML = window.LQ_I18N.langSwitcherHtml("execLang");
      window.LQ_I18N.bindSwitcher("execLang");
    }
  }

  function statusBadge(inv) {
    const bal = Number(inv.balance || 0);
    const st = String(inv.status || "").toLowerCase();
    if (st === "paid" || bal <= 0) return `<span class="lq-status ok">${t("completed")}</span>`;
    if (st === "overdue") return `<span class="lq-status bad">${t("overdueStatus")}</span>`;
    return `<span class="lq-status warn">${t("pending")}</span>`;
  }

  function monthlySeries(source, dateKey, amountKey) {
    const out = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date();
      d.setMonth(d.getMonth() - i);
      const key = d.toISOString().slice(0, 7);
      const sum = source
        .filter((x) => String(x[dateKey] || "").startsWith(key))
        .reduce((s, x) => s + Number(x[amountKey] || x.amount || 0), 0);
      out.push(sum);
    }
    return out;
  }

  function drawSpark(canvas, values, color) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = (canvas.width = canvas.clientWidth * 2 || 600);
    const h = (canvas.height = canvas.clientHeight * 2 || 220);
    ctx.clearRect(0, 0, w, h);
    if (!values.length) return;
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const pad = 24;
    ctx.strokeStyle = color || "#2f6fec";
    ctx.lineWidth = 4;
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = pad + (i / Math.max(values.length - 1, 1)) * (w - pad * 2);
      const y = h - pad - ((v - min) / Math.max(max - min, 1)) * (h - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    const lastX = pad + ((values.length - 1) / Math.max(values.length - 1, 1)) * (w - pad * 2);
    ctx.lineTo(lastX, h - pad);
    ctx.lineTo(pad, h - pad);
    ctx.closePath();
    ctx.fillStyle = "rgba(47,111,236,.12)";
    ctx.fill();
  }

  /* ---------- Contract / property timeline ---------- */
  function buildContractEvents(contractId) {
    const c = byId("contracts", contractId);
    if (!c) return [];
    const events = [];
    const client = byId("clients", c.client_id);
    const prop = byId("properties", c.property_id);
    if (client) {
      events.push({
        date: c.start_date || "",
        type: "client",
        title: t("client"),
        desc: client.name + (client.phone ? " · " + client.phone : ""),
        badge: "Client",
        tone: "blue",
      });
    }
    if (prop) {
      events.push({
        date: c.start_date || "",
        type: "unit",
        title: t("realestate"),
        desc: propLabel(prop),
        badge: "Unit",
        tone: "purple",
      });
    }
    events.push({
      date: c.start_date || c.approved_at || "",
      type: "contract",
      title: c.contract_no || c.id,
      desc: String(c.status || "") + " · " + money(c.rent_amount),
      badge: "Contract",
      tone: "blue",
      ref: { kind: "contract", id: c.id },
    });
    if (c.approved_at) {
      events.push({
        date: String(c.approved_at).slice(0, 10),
        type: "approved",
        title: t("completed"),
        desc: c.contract_no || c.id,
        badge: "Approved",
        tone: "green",
      });
    }
    data("invoices")
      .filter((i) => i.contract_id === c.id)
      .forEach((i) => {
        events.push({
          date: i.issue_date || "",
          type: "invoice",
          title: i.invoice_no || i.id,
          desc: money(i.amount) + " · " + String(i.status || ""),
          badge: "Invoice",
          tone: "blue",
          ref: { kind: "invoice", id: i.id },
        });
      });
    data("payments")
      .filter((p) => p.contract_id === c.id || data("invoices").some((i) => i.id === p.invoice_id && i.contract_id === c.id))
      .forEach((p) => {
        events.push({
          date: p.payment_date || "",
          type: "payment",
          title: money(p.amount),
          desc: String(p.method || "Payment"),
          badge: "Payment",
          tone: "green",
        });
      });
    data("maintenance")
      .filter((m) => m.property_id === c.property_id)
      .forEach((m) => {
        events.push({
          date: m.request_date || "",
          type: "maint",
          title: m.title || m.id,
          desc: String(m.status || ""),
          badge: "Task",
          tone: "amber",
        });
      });
    if (c.end_date) {
      events.push({
        date: c.end_date,
        type: "end",
        title: t("timeline"),
        desc: c.end_date,
        badge: "End",
        tone: "purple",
      });
    }
    return events
      .filter((e) => e.date)
      .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }

  function ensureDrawer() {
    let overlay = document.getElementById("lqExecDrawer");
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = "lqExecDrawer";
    overlay.className = "lq-drawer-overlay hidden";
    overlay.innerHTML = `<aside class="lq-drawer" role="dialog" aria-modal="true" aria-labelledby="lqDrawerTitle">
      <header class="lq-drawer-head">
        <div>
          <h2 id="lqDrawerTitle">${t("timeline")}</h2>
          <p class="mini" id="lqDrawerSub"></p>
        </div>
        <button type="button" class="ghost" id="lqDrawerClose" aria-label="Close">✕</button>
      </header>
      <div class="lq-drawer-tabs" id="lqDrawerTabs"></div>
      <div class="lq-drawer-body" id="lqDrawerBody"></div>
      <footer class="lq-drawer-foot" id="lqDrawerFoot"></footer>
    </aside>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeDrawer();
    });
    overlay.querySelector("#lqDrawerClose")?.addEventListener("click", closeDrawer);
    return overlay;
  }

  function closeDrawer() {
    document.getElementById("lqExecDrawer")?.classList.add("hidden");
  }

  function openContractTimeline(contractId) {
    const c = byId("contracts", contractId);
    if (!c) return;
    const overlay = ensureDrawer();
    const events = buildContractEvents(contractId);
    const prop = byId("properties", c.property_id);
    overlay.querySelector("#lqDrawerTitle").textContent = c.contract_no || c.id;
    overlay.querySelector("#lqDrawerSub").textContent =
      clientName(c.client_id) + " · " + propLabel(prop);
    overlay.querySelector("#lqDrawerTabs").innerHTML = `
      <button type="button" class="active" data-tab="all">All</button>
      <button type="button" data-tab="invoice">Invoices</button>
      <button type="button" data-tab="payment">Payments</button>
      <button type="button" data-tab="maint">Tasks</button>`;
    const body = overlay.querySelector("#lqDrawerBody");
    const paint = (filter) => {
      const list = filter === "all" ? events : events.filter((e) => e.type === filter || (filter === "invoice" && e.type === "invoice"));
      body.innerHTML = list.length
        ? `<div class="lq-full-timeline">${list
            .map(
              (e) => `<article class="lq-full-timeline-item tone-${e.tone}">
            <div class="when">${fmtDate(e.date)}</div>
            <div class="rail"><span class="bubble"></span></div>
            <div class="content">
              <div class="row"><b>${esc(e.title)}</b><span class="lq-status ${e.tone === "green" ? "ok" : e.tone === "amber" ? "warn" : "ok"}">${esc(e.badge)}</span></div>
              <p class="mini">${esc(e.desc)}</p>
            </div>
          </article>`
            )
            .join("")}</div>`
        : `<p class="mini">${t("empty")}</p>`;
    };
    paint("all");
    overlay.querySelectorAll("#lqDrawerTabs button").forEach((btn) => {
      btn.onclick = () => {
        overlay.querySelectorAll("#lqDrawerTabs button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        paint(btn.getAttribute("data-tab"));
      };
    });
    overlay.querySelector("#lqDrawerFoot").innerHTML = `
      <button type="button" class="ghost" onclick="showSection('contracts')">${t("realestate")}</button>
      <button type="button" class="gold-btn" onclick="typeof openContractDetail==='function'&&openContractDetail('${c.id}');LQ_EXEC.closeDrawer()">${t("enter")}</button>`;
    overlay.classList.remove("hidden");
  }

  /* ---------- KPI helpers ---------- */
  function computeEstateKpis() {
    const props = data("properties");
    const contracts = data("contracts");
    const invoices = data("invoices");
    const rented = props.filter((p) => /rent|مؤجر|مستأجر/i.test(String(p.status || ""))).length;
    const activeContracts = contracts.filter((c) => /active|نشط/i.test(String(c.status || ""))).length;
    const paid = invoices.reduce((s, i) => s + Number(i.paid_amount || 0), 0);
    const overdue = invoices
      .filter((i) => String(i.status || "").toLowerCase() === "overdue" || Number(i.balance || 0) > 0)
      .reduce((s, i) => s + Number(i.balance || i.amount || 0), 0);
    const occ = props.length ? Math.round((Math.max(rented, activeContracts) / props.length) * 100) : 0;
    return {
      revenue: paid || invoices.reduce((s, i) => s + Number(i.amount || 0), 0),
      activeUnits: Math.max(rented, activeContracts),
      occupancy: occ,
      overdue,
      props: props.length,
      contracts: contracts.length,
    };
  }

  function computeHospitalityKpis() {
    const events = data("hospitality_events");
    const bookings = data("hospitality_bookings");
    const revenue = events.reduce((s, e) => s + Number(e.paid_amount || e.total_amount || 0), 0);
    const upcoming = events.filter((e) => /reserved|confirmed|محجوز/i.test(String(e.status || ""))).length;
    const guests = events.reduce((s, e) => s + Number(e.guests || 0), 0);
    const balance = events.reduce((s, e) => s + Number(e.balance_amount || 0), 0);
    return { revenue, upcoming: upcoming || bookings.length, guests, balance, events: events.length };
  }

  function computeProductsKpis() {
    const items = data("inventory_items").length ? data("inventory_items") : data("inventory");
    const tx = data("inventory_transactions");
    const stock = items.reduce((s, i) => s + Number(i.qty || i.quantity || 0), 0);
    const low = items.filter((i) => Number(i.qty || i.quantity || 0) <= Number(i.min || i.min_qty || 0)).length;
    const value = items.reduce((s, i) => s + Number(i.qty || i.quantity || 0) * Number(i.cost || i.unit_cost || 0), 0);
    return { items: items.length, stock, low, value, tx: tx.length };
  }

  function recentInvoices(limit) {
    return data("invoices")
      .slice()
      .sort((a, b) => String(b.issue_date || "").localeCompare(String(a.issue_date || "")))
      .slice(0, limit || 6);
  }

  function contractPickerHtml() {
    const rows = data("contracts")
      .slice()
      .sort((a, b) => String(b.start_date || "").localeCompare(String(a.start_date || "")))
      .slice(0, 8);
    if (!rows.length) return `<p class="mini">${t("empty")}</p>`;
    return `<div class="lq-contract-list">${rows
      .map(
        (c) => `<button type="button" class="lq-contract-chip" data-contract="${esc(c.id)}">
        <b>${esc(c.contract_no || c.id)}</b>
        <span class="mini">${esc(clientName(c.client_id))} · ${esc(propLabel(byId("properties", c.property_id)))}</span>
      </button>`
      )
      .join("")}</div>`;
  }

  function bindContractChips(root) {
    root.querySelectorAll("[data-contract]").forEach((btn) => {
      btn.addEventListener("click", () => openContractTimeline(btn.getAttribute("data-contract")));
    });
  }

  /* ---------- Boards ---------- */
  function renderEstateBoard(host) {
    const k = computeEstateKpis();
    const name = Jawdah.user?.name || Jawdah.user?.username || "";
    const txs = recentInvoices(6);
    const monthly = monthlySeries(data("invoices"), "issue_date", "paid_amount");
    host.innerHTML = `
      <div class="lq-exec-board">
        <div class="lq-exec-head">
          <div><h2>${t("executiveOverview")} · ${t("realestate")}</h2><p>${t("goodMorning", { name })}</p></div>
          ${headActions(`<button type="button" class="ghost" onclick="showSection('contracts')">${t("timeline")}</button>`)}
        </div>
        <div class="lq-kpi-row">
          <article class="lq-kpi"><div class="label">${t("revenue")}</div><div class="value">${money(k.revenue)}</div></article>
          <article class="lq-kpi"><div class="label">${t("activeUnits")}</div><div class="value">${k.activeUnits}</div></article>
          <article class="lq-kpi"><div class="label">${t("occupancy")}</div><div class="value">${k.occupancy}%</div></article>
          <article class="lq-kpi"><div class="label">${t("overdue")}</div><div class="value">${money(k.overdue)}</div></article>
        </div>
        <div class="lq-exec-grid">
          <section class="lq-exec-panel"><h3>${t("revenueOverTime")}</h3><canvas class="lq-exec-chart" id="lqExecRevenueChart"></canvas></section>
          <section class="lq-exec-panel"><h3>${t("timeline")}</h3>${contractPickerHtml()}<p class="mini" style="margin-top:10px">اضغط عقداً لفتح المسار الزمني التفصيلي</p></section>
        </div>
        <section class="lq-exec-panel">
          <h3>${t("recentTx")}</h3>
          <div class="table-wrap"><table class="lq-tx-table">
            <thead><tr><th>${t("date")}</th><th>${t("client")}</th><th>${t("amount")}</th><th>${t("status")}</th></tr></thead>
            <tbody>${
              txs.length
                ? txs
                    .map(
                      (i) => `<tr>
                <td>${fmtDate(i.issue_date)}</td><td>${esc(clientName(i.client_id))}</td>
                <td>${money(i.amount)}</td><td>${statusBadge(i)}</td></tr>`
                    )
                    .join("")
                : `<tr><td colspan="4" class="mini">${t("empty")}</td></tr>`
            }</tbody>
          </table></div>
        </section>
      </div>`;
    bindLang();
    bindContractChips(host);
    requestAnimationFrame(() => drawSpark(document.getElementById("lqExecRevenueChart"), monthly));
  }

  function renderHospitalityBoard(host) {
    const k = computeHospitalityKpis();
    const events = data("hospitality_events")
      .slice()
      .sort((a, b) => String(b.event_date || "").localeCompare(String(a.event_date || "")))
      .slice(0, 8);
    const monthly = monthlySeries(data("hospitality_events"), "event_date", "paid_amount");
    host.innerHTML = `
      <div class="lq-exec-board">
        <div class="lq-exec-head">
          <div><h2>${t("hospitality")}</h2><p>${t("hospitalityDesc")}</p></div>
          ${headActions(`<button type="button" class="ghost" onclick="showSection('hospitality-platform')">${t("enter")}</button>`)}
        </div>
        <div class="lq-kpi-row">
          <article class="lq-kpi"><div class="label">${t("revenue")}</div><div class="value">${money(k.revenue)}</div></article>
          <article class="lq-kpi"><div class="label">${t("pending")}</div><div class="value">${k.upcoming}</div></article>
          <article class="lq-kpi"><div class="label">Guests</div><div class="value">${k.guests}</div></article>
          <article class="lq-kpi"><div class="label">${t("overdue")}</div><div class="value">${money(k.balance)}</div></article>
        </div>
        <div class="lq-exec-grid">
          <section class="lq-exec-panel"><h3>${t("revenueOverTime")}</h3><canvas class="lq-exec-chart" id="lqHospChart"></canvas></section>
          <section class="lq-exec-panel"><h3>${t("activity")}</h3>
            <div class="lq-timeline">${
              events.length
                ? events
                    .map(
                      (e) => `<div class="lq-timeline-item">
                  <div class="mini">${fmtDate(e.event_date)}</div><div class="dot"></div>
                  <div class="cardish"><b>${esc(e.package_name || e.client_name || e.id)}</b>
                  <div class="mini">${esc(e.venue_location || "")} · ${money(e.total_amount)} · ${esc(e.status || "")}</div></div></div>`
                    )
                    .join("")
                : `<p class="mini">${t("empty")}</p>`
            }</div>
          </section>
        </div>
      </div>`;
    bindLang();
    requestAnimationFrame(() => drawSpark(document.getElementById("lqHospChart"), monthly, "#1e4f8c"));
  }

  function renderProductsBoard(host) {
    const k = computeProductsKpis();
    const items = (data("inventory_items").length ? data("inventory_items") : data("inventory")).slice(0, 8);
    const tx = data("inventory_transactions")
      .slice()
      .sort((a, b) => String(b.entry_date || b.date || "").localeCompare(String(a.entry_date || a.date || "")))
      .slice(0, 8);
    host.innerHTML = `
      <div class="lq-exec-board">
        <div class="lq-exec-head">
          <div><h2>${t("products")}</h2><p>${t("productsDesc")}</p></div>
          ${headActions(`<button type="button" class="ghost" onclick="showSection('business-catalog')">${t("enter")}</button>
            <button type="button" class="ghost" onclick="showSection('inventory')">Inventory</button>`)}
        </div>
        <div class="lq-kpi-row">
          <article class="lq-kpi"><div class="label">${t("products")}</div><div class="value">${k.items}</div></article>
          <article class="lq-kpi"><div class="label">Stock</div><div class="value">${k.stock}</div></article>
          <article class="lq-kpi"><div class="label">Low stock</div><div class="value">${k.low}</div></article>
          <article class="lq-kpi"><div class="label">${t("amount")}</div><div class="value">${money(k.value)}</div></article>
        </div>
        <div class="lq-exec-grid">
          <section class="lq-exec-panel"><h3>${t("products")}</h3>
            <div class="table-wrap"><table class="lq-tx-table"><thead><tr><th>SKU</th><th>${t("products")}</th><th>Qty</th></tr></thead>
            <tbody>${
              items.length
                ? items
                    .map(
                      (i) =>
                        `<tr><td>${esc(i.sku || "—")}</td><td>${esc(i.name || i.id)}</td><td>${esc(i.qty ?? i.quantity ?? 0)}</td></tr>`
                    )
                    .join("")
                : `<tr><td colspan="3" class="mini">${t("empty")}</td></tr>`
            }</tbody></table></div>
          </section>
          <section class="lq-exec-panel"><h3>${t("activity")}</h3>
            <div class="lq-timeline">${
              tx.length
                ? tx
                    .map(
                      (x) => `<div class="lq-timeline-item">
                  <div class="mini">${fmtDate(x.entry_date || x.date)}</div><div class="dot"></div>
                  <div class="cardish"><b>${esc(x.type || "move")}</b>
                  <div class="mini">${esc(x.qty || x.quantity || "")} · ${esc(x.reference || x.ref || "")}</div></div></div>`
                    )
                    .join("")
                : `<p class="mini">${t("empty")}</p>`
            }</div>
          </section>
        </div>
      </div>`;
    bindLang();
  }

  function renderOverviewBoard(host) {
    const e = computeEstateKpis();
    const h = computeHospitalityKpis();
    const p = computeProductsKpis();
    const name = Jawdah.user?.name || Jawdah.user?.username || "";
    host.innerHTML = `
      <div class="lq-exec-board">
        <div class="lq-exec-head">
          <div><h2>${t("overview")}</h2><p>${t("goodMorning", { name })}</p></div>
          ${headActions()}
        </div>
        <div class="lq-kpi-row">
          <article class="lq-kpi"><div class="label">${t("realestate")} · ${t("revenue")}</div><div class="value">${money(e.revenue)}</div><div class="trend up">${e.occupancy}% ${t("occupancy")}</div></article>
          <article class="lq-kpi"><div class="label">${t("hospitality")} · ${t("revenue")}</div><div class="value">${money(h.revenue)}</div><div class="trend up">${h.upcoming} ${t("pending")}</div></article>
          <article class="lq-kpi"><div class="label">${t("products")}</div><div class="value">${p.items}</div><div class="trend ${p.low ? "down" : "up"}">${p.low} low</div></article>
          <article class="lq-kpi"><div class="label">${t("overdue")}</div><div class="value">${money(e.overdue + h.balance)}</div></article>
        </div>
        <div class="lq-exec-grid">
          <section class="lq-exec-panel">
            <h3>${t("realestate")}</h3>
            ${contractPickerHtml()}
            <div class="toolbar" style="margin-top:12px">
              <button type="button" class="ghost" onclick="choosePortal('realestate')">${t("enter")} ${t("realestate")}</button>
              <button type="button" class="ghost" onclick="choosePortal('hospitality')">${t("enter")} ${t("hospitality")}</button>
              <button type="button" class="ghost" onclick="choosePortal('products')">${t("enter")} ${t("products")}</button>
            </div>
          </section>
          <section class="lq-exec-panel">
            <h3>${t("activity")}</h3>
            <canvas class="lq-exec-chart" id="lqOverviewChart"></canvas>
          </section>
        </div>
      </div>`;
    bindLang();
    bindContractChips(host);
    const series = monthlySeries(data("invoices"), "issue_date", "paid_amount").map(
      (v, i) => v + (monthlySeries(data("hospitality_events"), "event_date", "paid_amount")[i] || 0)
    );
    requestAnimationFrame(() => drawSpark(document.getElementById("lqOverviewChart"), series, "#1f4ea5"));
  }

  function ensureBoardHost(portal) {
    let sectionId = "sec-dashboard";
    if (portal === "realestate") sectionId = "sec-estate-platform";
    if (portal === "hospitality") sectionId = "sec-hospitality-platform";
    if (portal === "products") sectionId = "sec-business-catalog";
    if (portal === "overview") sectionId = "sec-dashboard";
    const dash = document.getElementById(sectionId) || document.getElementById("sec-dashboard");
    if (!dash) return null;
    // reuse one host id per section
    const hostId = "lqExecBoard-" + portal;
    let host = document.getElementById(hostId);
    if (!host) {
      host = document.createElement("div");
      host.id = hostId;
      host.className = "lq-exec-board-host";
      dash.insertBefore(host, dash.firstChild);
    }
    return host;
  }

  function refreshBoard() {
    const portal = String(localStorage.getItem("jawdah_portal_choice") || "realestate").toLowerCase();
    if (!VALID.has(portal) || portal === "accounting") return;
    // منصة العقارات تستخدم تجربة نزوى المطوّرة (lq-estate-nizwa-ux) بدل لوحة exec
    if (portal === "realestate") {
      document.getElementById("lqExecBoard-realestate")?.remove();
      if (typeof window.renderEstatePlatform === "function") window.renderEstatePlatform();
      return;
    }
    const host = ensureBoardHost(portal === "overview" ? "overview" : portal);
    if (!host) return;
    if (portal === "hospitality") return renderHospitalityBoard(host);
    if (portal === "products") return renderProductsBoard(host);
    if (portal === "overview") return renderOverviewBoard(host);
    return renderEstateBoard(host);
  }

  function patchPortalHelpers() {
    if (typeof window.choosePortal === "function") {
      window.choosePortal = function (portal) {
        const choice = VALID.has(String(portal || "").toLowerCase())
          ? String(portal).toLowerCase()
          : "realestate";
        localStorage.setItem("jawdah_portal_choice", choice);
        if (typeof closePortalSwitch === "function") closePortalSwitch();
        if (typeof buildNav === "function") buildNav();
        if (choice === "hospitality") showSection("hospitality-platform");
        else if (choice === "accounting") showSection("accounting-platform");
        else if (choice === "products") showSection("business-catalog");
        else if (choice === "overview") showSection("dashboard");
        else showSection("estate-platform");
        setTimeout(refreshBoard, 60);
      };
    }
    if (typeof window.applySavedPortalChoice === "function") {
      const origApply = window.applySavedPortalChoice;
      window.applySavedPortalChoice = function () {
        const choice = localStorage.getItem("jawdah_portal_choice");
        if (!choice) return origApply();
        if (typeof buildNav === "function") buildNav();
        if (choice === "hospitality") showSection("hospitality-platform");
        else if (choice === "accounting") showSection("accounting-platform");
        else if (choice === "products") showSection("business-catalog");
        else if (choice === "overview") showSection("dashboard");
        else showSection("estate-platform");
        setTimeout(refreshBoard, 80);
      };
    }
    const _show = window.showSection;
    if (typeof _show === "function") {
      window.showSection = function (id) {
        const r = _show.apply(this, arguments);
        setTimeout(refreshBoard, 40);
        return r;
      };
    }
  }

  function boot() {
    enableExecTheme();
    decorateLogin();
    patchPortalHelpers();
    document.addEventListener("lq:langchange", () => {
      decorateLogin();
      refreshBoard();
    });
    const _loadAll = window.loadAll;
    if (typeof _loadAll === "function") {
      window.loadAll = async function () {
        const r = await _loadAll.apply(this, arguments);
        try {
          enableExecTheme();
          refreshBoard();
        } catch (_) {}
        return r;
      };
    }
    setTimeout(refreshBoard, 1000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  window.addEventListener("load", () => {
    enableExecTheme();
    decorateLogin();
    patchPortalHelpers();
    setTimeout(refreshBoard, 400);
  });

  window.LQ_EXEC = {
    refreshBoard,
    enableExecTheme,
    openContractTimeline,
    closeDrawer,
  };
})();
