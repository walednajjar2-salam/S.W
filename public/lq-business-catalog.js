(function () {
  "use strict";

  function esc(s) {
    if (typeof htmlEscape === "function") return htmlEscape(s);
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function money(n) {
    if (typeof window.money === "function") return window.money(n);
    return Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 3 }) + " OMR";
  }

  function renderCompany(c) {
    const p = c.phones || {};
    const banks = ((c.bank || {}).accounts || [])
      .map(
        (a) =>
          `<div class="statement-row"><span>${esc(a.label_ar || a.label_en)}</span><b>${esc(a.number)}${a.phone ? " · " + esc(a.phone) : ""}</b></div>`
      )
      .join("");
    const deps = (c.departments || [])
      .map((d) => `<span class="badge">${esc(d.name_ar)}</span>`)
      .join(" ");
    return `
      <div class="card">
        <h3>🏢 ${esc(c.name_ar)}</h3>
        <p class="mini">${esc(c.name_en)} · س.ت ${esc(c.cr_no)}</p>
        <p>${esc(c.motto_ar || "")}</p>
        <p class="mini">${esc(c.activity_ar || "")}</p>
        <div class="status-line" style="flex-wrap:wrap;gap:6px;margin:8px 0">${deps}</div>
        <div class="statement-row"><span>العنوان</span><b>${esc(c.address_ar)}</b></div>
        <div class="statement-row"><span>ساعات العمل</span><b>${esc(c.hours)}</b></div>
        <div class="statement-row"><span>هاتف / واتساب</span><b>${esc(p.landline)} · ${esc(p.whatsapp)}</b></div>
        <div class="statement-row"><span>جوالات</span><b>${esc([p.mobile_1, p.mobile_2, p.mobile_3].filter(Boolean).join(" / "))}</b></div>
        <div class="statement-row"><span>البريد</span><b>${esc(c.email)} · ${esc(c.email_alt || "")}</b></div>
        <h4 style="margin-top:12px">حسابات بنك مسقط</h4>
        ${banks}
      </div>`;
  }

  function renderStaff(staff) {
    if (!staff || !staff.length) return "<p class='mini'>لا يوجد</p>";
    return `<div class="table-wrap"><table><thead><tr><th>الاسم</th><th>المسمى</th><th>القسم</th><th>الدور</th></tr></thead><tbody>${staff
      .map(
        (s) =>
          `<tr><td><b>${esc(s.name)}</b><br><small class="mini">${esc(s.username)}</small></td><td>${esc(s.title)}</td><td>${esc(s.department)}</td><td>${esc(s.role)}</td></tr>`
      )
      .join("")}</tbody></table></div>`;
  }

  function renderHousing(services) {
    return `<ul class="check-list">${(services || [])
      .map((s) => `<li>${esc(s.name_ar)}</li>`)
      .join("")}</ul>`;
  }

  function renderOfficePrices(rows, fee) {
    return `
      <div class="card">
        <h4>أسعار مكاتب الخدمات العقارية — الداخلية</h4>
        <p class="mini">سارية من 2023-01-01 · رسوم منصة الوزارة ${fee} ر.ع إضافية</p>
        <div class="toolbar" style="flex-wrap:wrap;gap:8px;margin:8px 0">
          <select id="bizFeeService">${(rows || [])
            .map((r) => `<option value="${esc(r.code)}">${esc(r.name_ar)}</option>`)
            .join("")}</select>
          <input id="bizFeeParties" type="number" min="1" value="2" style="width:90px" title="عدد الأطراف">
          <button type="button" class="gold-btn" onclick="LQ_BUSINESS.calcFee()">احسب الرسوم</button>
        </div>
        <pre id="bizFeeOut" class="mini" style="white-space:pre-wrap;background:rgba(0,0,0,.04);padding:10px;border-radius:8px">اختر الخدمة وعدد الأطراف ثم احسب.</pre>
        <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>المعاملة</th><th>الأطراف / السعر</th></tr></thead><tbody>
        ${(rows || [])
          .map(
            (r) =>
              `<tr><td>${esc(r.name_ar)}</td><td>${(r.tiers || [])
                .map((t) => `${esc(t.parties)} → ${money(t.price)}`)
                .join(" · ")}</td></tr>`
          )
          .join("")}
        </tbody></table></div>
      </div>`;
  }

  function renderLand(rows) {
    const byW = {};
    (rows || []).forEach((r) => {
      (byW[r.wilayat] = byW[r.wilayat] || []).push(r);
    });
    return `<div class="card"><h4>جدول أسعار الأراضي — محافظة الداخلية (ر.ع/م²)</h4>
      <div class="table-wrap"><table><thead><tr><th>الولاية</th><th>المنطقة</th><th>سكنية</th><th>سكني/تجاري</th><th>صناعية</th><th>زراعية</th><th>سياحية</th></tr></thead><tbody>
      ${Object.keys(byW)
        .map((w) =>
          byW[w]
            .map(
              (r, i) =>
                `<tr><td>${i === 0 ? `<b>${esc(w)}</b>` : ""}</td><td>${esc(r.zone)}</td><td>${r.residential}</td><td>${r.res_commercial}</td><td>${r.industrial}</td><td>${r.agricultural}</td><td>${r.tourism}</td></tr>`
            )
            .join("")
        )
        .join("")}
      </tbody></table></div></div>`;
  }

  function renderHospitality(pkgs, condolence, terms) {
    const prices = ((condolence && condolence.prices) || [])
      .map((p) => `<div class="statement-row"><span>${esc(p.zone)}</span><b>${money(p.price_omr)}</b></div>`)
      .join("");
    return `
      <div class="card">
        <h4>عروض ضيافة المجالس الخارجية</h4>
        <p class="mini">خدمة في مجالس خارجية — ليست غرفاً وليست مرتبطة بالعقارات.</p>
        <div class="toolbar" style="gap:8px;margin:8px 0">
          <input id="bizGuests" type="number" min="1" value="150" placeholder="عدد الضيوف" style="width:120px">
          <button type="button" class="gold-btn" onclick="LQ_BUSINESS.quoteHospitality()">عرض السعر</button>
        </div>
        <pre id="bizHospOut" class="mini" style="white-space:pre-wrap;background:rgba(0,0,0,.04);padding:10px;border-radius:8px">أدخل عدد الضيوف.</pre>
        <div class="table-wrap"><table><thead><tr><th>العرض</th><th>الضيوف</th><th>الطاقم</th><th>دلال</th><th>السعر</th></tr></thead><tbody>
        ${(pkgs || [])
          .map(
            (p) =>
              `<tr><td>${esc(p.name_ar)}</td><td>${p.guests_min}–${p.guests_max}</td><td>${p.waiters} + ${p.supervisors} مشرف</td><td>${esc(p.dallahs)}</td><td>${money(p.price_omr)}</td></tr>`
          )
          .join("")}
        </tbody></table></div>
        <p class="mini" style="margin-top:8px">${(terms || []).map(esc).join(" · ")}</p>
      </div>
      <div class="card" style="margin-top:12px">
        <h4>أسعار واجب العزاء (3 أيام)</h4>
        ${prices}
        <p class="mini">${((condolence && condolence.notes) || []).map(esc).join(" · ")}</p>
      </div>`;
  }

  function renderCancelForm() {
    return `
      <div class="card">
        <h4>نموذج طلب إلغاء عقد الإيجار</h4>
        <div class="form" style="grid-template-columns:repeat(2,minmax(0,1fr))">
          <input id="cancelApplicant" placeholder="اسم مقدم الطلب">
          <input id="cancelId" placeholder="رقم الهوية">
          <input id="cancelBuilding" placeholder="المبنى رقم">
          <input id="cancelApt" placeholder="الشقة رقم">
          <input id="cancelRoom" placeholder="الغرفة">
          <input id="cancelShop" placeholder="المحل">
          <input id="cancelEffective" type="date" placeholder="تاريخ الإلغاء">
          <select id="cancelKind"><option value="apartment">شقة / محل</option><option value="room">غرفة</option></select>
          <textarea id="cancelReasons" placeholder="الأسباب (سطر لكل سبب)" style="grid-column:1/-1"></textarea>
        </div>
        <button type="button" class="gold-btn" onclick="LQ_BUSINESS.printCancel()">طباعة الطلب</button>
      </div>`;
  }

  function render(host, data) {
    const cat = (data && data.catalog) || {};
    host.innerHTML =
      `<div class="card lq-enterprise-guide"><h3>📋 كتالوج العمل الحقيقي — جودة الانطلاقة</h3>
        <p class="mini">خدمات الإسكان · أسعار الأراضي · عروض الضيافة · الفريق · الحسابات البنكية — من مستندات المكتب.</p></div>` +
      renderCompany(cat.company || {}) +
      `<div class="layout" style="margin-top:12px">
        <div class="card"><h4>الإدارة مع فريق العمل</h4>${renderStaff(cat.staff)}</div>
        <div class="card"><h4>خدمات مكتب الإسكان المعتمد</h4>${renderHousing(cat.housing_services)}</div>
      </div>` +
      renderOfficePrices(cat.office_service_prices, cat.ministry_platform_fee_omr || 5) +
      renderLand(cat.land_prices) +
      renderHospitality(cat.hospitality_packages, cat.condolence, cat.hospitality_terms) +
      renderCancelForm();
    if (typeof ensureEnglishDigits === "function") ensureEnglishDigits(host);
  }

  async function refresh() {
    const host = document.getElementById("businessCatalogBox");
    if (!host) return;
    host.innerHTML = "<p class='mini'>جاري تحميل كتالوج العمل…</p>";
    try {
      const data = await api("business_catalog");
      render(host, data);
      return data;
    } catch (e) {
      host.innerHTML = "<p class='badge overdue'>تعذر التحميل</p>";
      if (typeof toastErr === "function") toastErr(e);
      throw e;
    }
  }

  async function calcFee() {
    const out = document.getElementById("bizFeeOut");
    try {
      const service_code = (document.getElementById("bizFeeService") || {}).value || "";
      const parties = Number((document.getElementById("bizFeeParties") || {}).value || 2);
      const res = await api("business_catalog/office_fee", {
        method: "POST",
        body: JSON.stringify({ service_code, parties }),
      });
      if (out) {
        out.textContent = [
          res.name_ar,
          "أطراف: " + res.parties,
          "رسوم المكتب: " + money(res.office_fee),
          "رسوم المنصة: " + money(res.ministry_platform_fee),
          "الإجمالي: " + money(res.total),
          res.note || "",
        ].join("\n");
      }
    } catch (e) {
      if (out) out.textContent = String((e && e.message) || e);
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function quoteHospitality() {
    const out = document.getElementById("bizHospOut");
    try {
      const guests = Number((document.getElementById("bizGuests") || {}).value || 0);
      const res = await api("business_catalog/hospitality_quote", {
        method: "POST",
        body: JSON.stringify({ guests }),
      });
      const p = res.package || {};
      if (out) {
        out.textContent = [
          'مجلس خارجي — مفصول عن العقارات',
          p.name_ar,
          "ضيوف: " + guests + ` (${p.guests_min}–${p.guests_max})`,
          "طاقم: " + p.waiters + " مضيف + " + p.supervisors + " مشرف",
          "دلال ذهبية: " + p.dallahs,
          "السعر: " + money(res.price_omr),
          "عربون 30%: " + money(res.deposit_omr),
        ].join("\n");
      }
    } catch (e) {
      if (out) out.textContent = String((e && e.message) || e);
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function printCancel() {
    try {
      const reasons = String((document.getElementById("cancelReasons") || {}).value || "")
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean);
      const res = await api("documents/lease_cancel", {
        method: "POST",
        body: JSON.stringify({
          applicant_name: (document.getElementById("cancelApplicant") || {}).value || "",
          id_no: (document.getElementById("cancelId") || {}).value || "",
          building_no: (document.getElementById("cancelBuilding") || {}).value || "",
          apartment_no: (document.getElementById("cancelApt") || {}).value || "",
          room_no: (document.getElementById("cancelRoom") || {}).value || "",
          shop_no: (document.getElementById("cancelShop") || {}).value || "",
          effective_date: (document.getElementById("cancelEffective") || {}).value || "",
          unit_kind: (document.getElementById("cancelKind") || {}).value || "apartment",
          reasons,
        }),
      });
      const w = window.open("", "_blank");
      if (!w) {
        if (typeof toastNotice === "function") toastNotice("اسمح بالنوافذ المنبثقة للطباعة");
        return;
      }
      w.document.write(res.html || "");
      w.document.close();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  window.LQ_BUSINESS = { refresh, calcFee, quoteHospitality, printCancel, render };
})();
