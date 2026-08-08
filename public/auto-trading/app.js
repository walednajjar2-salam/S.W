/* النجار والسموم — تجارة واستيراد السيارات */
const NAJJAR_WEB = (typeof window !== 'undefined' && window.NAJJAR_BASE) || '/najjar-al-samoom-used-imported-cars';
const API_BASE = '/api/auto-trading';
const content = document.getElementById('content');
const drawer = document.getElementById('drawer');
const drawerContent = document.getElementById('drawerContent');
const modal = document.getElementById('modal');
const modalContent = document.getElementById('modalContent');

let currentSection = 'dashboard';
let vehiclesCache = [];
let selectedVehicleId = null;
let vehicleSearchQ = '';
let statusFilter = '';
let makeFilter = '';
let companyProfile = null;

const LOGO_URL = '/auto-trading/assets/logo-official-clear.png?v=at13';
const LOGO_MARK = '/auto-trading/assets/logo-mark.png?v=at13';
const LOGO_CARD = '/auto-trading/assets/logo-official.png?v=at13';
const ICO = (name) => (window.NajjarIcons ? NajjarIcons.get(name, { wrap: false }) : '');

function waLink(phone) {
  const p = String(phone || '').replace(/\D/g, '');
  const full = p.startsWith('968') ? p : ('968' + p);
  return `https://wa.me/${full}`;
}

function vehicleWhatsAppText(v, c) {
  const co = c || companyProfile || {};
  const priceLine = Number(v.list_price) > 0 ? `السعر: ${money(v.list_price)}` : 'السعر: حسب الاتفاق';
  return [
    'NAJJAR & AL SAMOOM TRADING — USED & IMPORTED CARS',
    `${v.make} ${v.model} ${v.variant || ''}`.trim(),
    v.vehicle_type ? `النوع: ${v.vehicle_type}` : '',
    `السنة: ${v.year || '—'} · اللون: ${v.color || '—'}`,
    priceLine,
    `مخزون: ${v.stock_no}`,
    v.vin ? `VIN: ${v.vin}` : '',
    v.engine_no ? `المحرك: ${v.engine_no}${v.engine_cc ? ' · ' + v.engine_cc + ' cc' : ''}` : '',
    v.first_registration ? `أول تسجيل: ${dmy(v.first_registration)}` : '',
    v.license_valid_until ? `صلاحية الرخصة: ${dmy(v.license_valid_until)}` : '',
    v.license_doc_no ? `رقم الوثيقة: ${v.license_doc_no}` : '',
    v.insurance_company ? `التأمين: ${v.insurance_type || 'شامل'} — ${v.insurance_company}` : '',
    v.insurance_policy ? `وثيقة التأمين: ${v.insurance_policy}` : '',
    co.address_ar || 'نزوى — الفلج',
    'للاستفسار: +968 71924089 · +968 93391994',
  ].filter(Boolean).join('\n');
}

function uploadUrl(url) {
  const u = String(url || '').trim();
  if (!u || !u.startsWith('/uploads/')) return u;
  const token = readToken();
  if (!token) return u;
  const sep = u.includes('?') ? '&' : '?';
  return u + sep + 'token=' + encodeURIComponent(token);
}

function vehicleDocLink(v) {
  if (!v.license_source) return '';
  let href = String(v.license_source).startsWith('/') ? v.license_source : '/' + v.license_source;
  // Paperwork is served to signed-in staff only, so carry the session on the link.
  const token = readToken();
  if (token && href.startsWith('/auto-trading/documents/')) {
    href += (href.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
  }
  const label = href.includes('bill-of-sale') ? 'عرض Bill of Sale'
    : href.includes('port-shipment') ? 'عرض بيانات الشحن'
    : href.includes('license') ? 'عرض رخصة المركبة'
    : 'عرض الوثيقة';
  return `<a class="btn secondary" href="${e(href)}" target="_blank" rel="noopener" style="margin-top:12px;display:inline-block">${label}</a>`;
}

function licenseDetailRows(v) {
  return `
    <div class="detail-row"><span>سعة المحرك</span><strong>${e(v.engine_cc ? v.engine_cc + ' cc' : '—')}</strong></div>
    <div class="detail-row"><span>المقاعد / المحاور</span><strong>${e(v.seats || '—')} · ${e(v.axles || '—')}</strong></div>
    <div class="detail-row"><span>أول تسجيل</span><strong>${dmy(v.first_registration)}</strong></div>
    <div class="detail-row"><span>صلاحية الرخصة</span><strong>${dmy(v.license_valid_until)}</strong></div>
    <div class="detail-row"><span>رقم الوثيقة</span><strong class="number">${e(v.license_doc_no || '—')}</strong></div>
    <div class="detail-row"><span>نوع التأمين</span><strong>${e(v.insurance_type || '—')}</strong></div>
    <div class="detail-row"><span>شركة التأمين</span><strong>${e(v.insurance_company || '—')}</strong></div>
    <div class="detail-row"><span>وثيقة التأمين</span><strong class="number">${e(v.insurance_policy || '—')}</strong></div>
    <div class="detail-row"><span>الرهن</span><strong>${e(v.mortgage || '—')}</strong></div>`;
}

function openPrintWindow(title, bodyHtml) {
  const w = window.open('', '_blank');
  if (!w) { toast('فعّل النوافذ المنبثقة للطباعة', 'error'); return; }
  w.document.write(`<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>${e(title)}</title>
    <style>
      body{font-family:Tahoma,Arial,sans-serif;padding:24px;color:#111}
      .head{text-align:center;border-bottom:3px solid #d4af37;padding-bottom:14px;margin-bottom:18px}
      .head h1{margin:0;color:#111;letter-spacing:2px}
      .head p{margin:6px 0 0;color:#666;font-size:13px}
      table{width:100%;border-collapse:collapse;margin:14px 0}
      th,td{border:1px solid #ddd;padding:8px;text-align:right;font-size:13px}
      th{background:#f7f7f7}
      .bank{margin-top:18px;padding:12px;border:1px solid #d4af37;border-radius:8px;background:#fffaf0}
      .foot{margin-top:24px;font-size:12px;color:#666;text-align:center}
      @media print{body{padding:0}}
    </style></head><body>${bodyHtml}</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 350);
}

async function printVehicleOffer(v) {
  const c = await ensureCompany();
  const bank = c.bank || {};
  const priceCell = Number(v.list_price) > 0 ? `<b>${money(v.list_price)}</b>` : 'حسب الاتفاق';
  openPrintWindow('عرض سيارة — NAJJAR & AL SAMOOM TRADING', `
    <div class="head">
      <h1>NAJJAR & AL SAMOOM TRADING</h1>
      <p>USED & IMPORTED CARS · ${e(c.address_ar || '')}</p>
      <p>${e(c.address_en || '')}</p>
    </div>
    <h2>Vehicle — ${e(v.stock_no)}</h2>
    <table>
      <tr><th>الماركة / الطراز</th><td>${e(v.make)} ${e(v.model)} ${e(v.variant || '')}</td></tr>
      <tr><th>السنة / اللون</th><td>${e(v.year || '—')} · ${e(v.color || '—')}</td></tr>
      <tr><th>النوع</th><td>${e(v.vehicle_type || '—')}</td></tr>
      <tr><th>رقم الهيكل</th><td dir="ltr">${e(v.vin || '—')}</td></tr>
      <tr><th>رقم المحرك</th><td dir="ltr">${e(v.engine_no || '—')}${v.engine_cc ? ' · ' + e(v.engine_cc) + ' cc' : ''}</td></tr>
      <tr><th>المقاعد / المحاور</th><td>${e(v.seats || '—')} · ${e(v.axles || '—')}</td></tr>
      <tr><th>بلد المنشأ</th><td>${e(v.origin_country || '—')}</td></tr>
      <tr><th>سعر البيع</th><td>${priceCell}</td></tr>
    </table>
    <h3 style="margin-top:18px">بيانات الرخصة والتأمين</h3>
    <table>
      <tr><th>أول تسجيل</th><td>${dmy(v.first_registration)}</td></tr>
      <tr><th>صلاحية الرخصة</th><td>${dmy(v.license_valid_until)}</td></tr>
      <tr><th>رقم الوثيقة</th><td dir="ltr">${e(v.license_doc_no || '—')}</td></tr>
      <tr><th>اللوحة</th><td>${e(v.plate_no || '—')}</td></tr>
      <tr><th>التأمين</th><td>${e(v.insurance_type || '—')} — ${e(v.insurance_company || '—')}</td></tr>
      <tr><th>وثيقة التأمين</th><td dir="ltr">${e(v.insurance_policy || '—')}</td></tr>
      <tr><th>الرهن</th><td>${e(v.mortgage || '—')}</td></tr>
    </table>
    <div class="bank">
      <b>للتحويل البنكي — ${e(bank.name_ar || '')}</b><br>
      <span dir="ltr">${e(bank.account_name_en || '')}</span><br>
      رقم الحساب الدولي: <span dir="ltr">${e(bank.iban || '')}</span><br>
      رمز السويفت: <span dir="ltr">${e(bank.swift || '')}</span>
    </div>
    <p>واتساب: <span dir="ltr">+968 71924089</span> · <span dir="ltr">+968 93391994</span></p>
    <div class="foot">NAJJAR & AL SAMOOM TRADING · Nizwa · Falaj · ${e(v.license_source ? 'بيانات الرخصة: ' + v.license_source : '')}</div>`);
}

function printSaleReceipt(sale, c) {
  if (window.NajjarPrintDocs) {
    NajjarPrintDocs.printReceiptVoucher(sale, c);
    return;
  }
  openPrintWindow('سند قبض — ' + (sale.sale_no || ''), `<h2>سند قبض ${e(sale.sale_no || '')}</h2><p>${e(sale.buyer_name)} · ${money(sale.deposit_amount || sale.sale_price)}</p>`);
}

function saleDocActions(indexAttr) {
  return `
    <div class="actions-row" style="gap:6px;flex-wrap:wrap">
      <button type="button" class="btn secondary small" data-doc-sale-contract="${indexAttr}">عقد بيع</button>
      <button type="button" class="btn secondary small" data-doc-sale-invoice="${indexAttr}">فاتورة</button>
      <button type="button" class="btn secondary small" data-doc-sale-receipt="${indexAttr}">سند قبض</button>
    </div>`;
}

function purchaseDocActions(indexAttr) {
  return `
    <div class="actions-row" style="gap:6px;flex-wrap:wrap">
      <button type="button" class="btn secondary small" data-doc-buy-contract="${indexAttr}">عقد شراء</button>
      <button type="button" class="btn secondary small" data-doc-buy-invoice="${indexAttr}">فاتورة</button>
      <button type="button" class="btn secondary small" data-doc-buy-voucher="${indexAttr}">سند صرف</button>
    </div>`;
}

async function bindSaleDocButtons(root, rows) {
  const c = await ensureCompany();
  const docs = window.NajjarPrintDocs;
  if (!docs) return;
  root.querySelectorAll('[data-doc-sale-contract]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-sale-contract'))];
      docs.printSaleContract(r, r, c);
    };
  });
  root.querySelectorAll('[data-doc-sale-invoice]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-sale-invoice'))];
      docs.printSaleInvoice(r, r, c);
    };
  });
  root.querySelectorAll('[data-doc-sale-receipt]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-sale-receipt'))];
      docs.printReceiptVoucher(r, c);
    };
  });
}

async function bindPurchaseDocButtons(root, rows) {
  const c = await ensureCompany();
  const docs = window.NajjarPrintDocs;
  if (!docs) return;
  root.querySelectorAll('[data-doc-buy-contract]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-buy-contract'))];
      docs.printPurchaseContract(r, r, c);
    };
  });
  root.querySelectorAll('[data-doc-buy-invoice]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-buy-invoice'))];
      docs.printPurchaseInvoice(r, r, c);
    };
  });
  root.querySelectorAll('[data-doc-buy-voucher]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-buy-voucher'))];
      docs.printPaymentVoucher({
        kind: 'purchase',
        amount: r.purchase_price,
        purchase_date: r.purchase_date,
        purchase_no: r.purchase_no,
        seller_name: r.seller_name,
        stock_no: r.stock_no,
        payment_method: r.payment_method,
        notes: r.notes,
      }, c);
    };
  });
}

function readToken() {
  if (window.NajjarAuth) {
    try {
      const qs = new URLSearchParams(location.search || '');
      const qTok = (qs.get('token') || '').trim();
      if (qTok) {
        NajjarAuth.setToken(qTok);
        qs.delete('token');
        history.replaceState({}, '', location.pathname + (qs.toString() ? '?' + qs.toString() : ''));
        return qTok;
      }
    } catch (_) {}
    return NajjarAuth.getToken();
  }
  try {
    const qs = new URLSearchParams(location.search || '');
    const qTok = (qs.get('token') || '').trim();
    if (qTok) return qTok;
  } catch (_) {}
  return '';
}

const PLATFORM_LABELS = {
  america: '🇺🇸 USA — مزادات Copart / IAAI',
  salam: '🚗 SALAM TRADING',
  oman: '🇴🇲 عُمان — مخزون السيارات',
  dubai: '🇦🇪 دبي',
  jordan: '🇯🇴 الأردن',
  iran: '🇮🇷 إيران',
  india: '🇮🇳 الهند',
  saudi: '🇸🇦 السعودية',
};

function currentPlatform() {
  try {
    const qs = new URLSearchParams(location.search || '');
    return (qs.get('platform') || localStorage.getItem('najjar_platform') || 'oman').trim();
  } catch (_) {
    return 'oman';
  }
}

function goToPlatforms(event) {
  if (event) event.preventDefault();
  const token = readToken();
  let url = NAJJAR_WEB + '/platforms.html?from=dashboard&t=' + Date.now();
  if (token) url += '&token=' + encodeURIComponent(token);
  location.href = url;
}
document.querySelectorAll('[data-back-platforms]').forEach((link) => {
  link.addEventListener('click', goToPlatforms);
});

const e = (v) => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const money = (v) => `${Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 3 })} ر.ع`;
const dmy = (v) => {
  if (!v) return '—';
  const p = String(v).slice(0, 10).split('-');
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : e(v);
};

const actionLabel = {
  vehicle_created: 'إضافة مركبة',
  vehicle_updated: 'تحديث مركبة',
  sale_created: 'تسجيل بيع',
  purchase_created: 'تسجيل شراء',
  expense_created: 'تسجيل مصروف',
  import_created: 'طلب استيراد',
  import_updated: 'تحديث استيراد',
  capital_entry: 'حركة رأس مال',
  capital_distribution: 'توزيع أرباح',
  capital_distribution_status: 'تحديث توزيع',
};

const statusClass = {
  'متاحة': 'available',
  'محجوزة': 'reserved',
  'مباعة': 'sold',
  'قيد الاستيراد': 'importing',
  'صيانة': 'service',
};

async function api(url, options = {}) {
  const token = readToken();
  if (!token) { location.replace(NAJJAR_WEB + '/login.html'); return; }
  const opts = { ...options };
  opts.headers = {
    'Content-Type': 'application/json',
    Authorization: 'Bearer ' + token,
    ...(opts.headers || {}),
  };
  if (opts.body && typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
  const res = await fetch(url.startsWith('/api/') ? url : (API_BASE + url), opts);
  const data = await res.json().catch(() => ({ ok: false, error: 'تعذر قراءة رد الخادم' }));
  if (res.status === 401) {
    if (window.NajjarAuth) NajjarAuth.clearToken();
    location.replace(NAJJAR_WEB + '/login.html');
    return;
  }
  if (!res.ok || data.ok === false) throw new Error(data.error || 'حدث خطأ');
  return data;
}

function toast(message, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = `toast ${type} show`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('show'), 3100);
}

function pill(s, label = s) {
  return `<span class="pill ${statusClass[s] || 'draft'}">${e(label)}</span>`;
}

function setTitle(title, subtitle = '') {
  document.getElementById('pageTitle').textContent = title;
  document.getElementById('pageSubtitle').textContent = subtitle || 'النجار والسموم — تجارة واستيراد السيارات';
}

function openDrawer(html) {
  drawerContent.innerHTML = html;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
}

function closeDrawer() {
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
}

function openModal(html) {
  modalContent.innerHTML = html;
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
}

function closeModal() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}

document.getElementById('drawerClose').onclick = closeDrawer;
document.getElementById('modalClose').onclick = closeModal;
drawer.addEventListener('click', ev => { if (ev.target === drawer) closeDrawer(); });
modal.addEventListener('click', ev => { if (ev.target === modal) closeModal(); });
document.getElementById('refreshPage').onclick = () => loadSection(currentSection);
function closeMobileSidebar() {
  document.querySelector('.sidebar')?.classList.remove('open');
  document.getElementById('sidebarBackdrop')?.classList.remove('open');
  document.body.classList.remove('nt-sidebar-open');
}

function openMobileSidebar() {
  document.querySelector('.sidebar')?.classList.add('open');
  document.getElementById('sidebarBackdrop')?.classList.add('open');
  document.body.classList.add('nt-sidebar-open');
}

function toggleMobileSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (sidebar?.classList.contains('open')) closeMobileSidebar();
  else openMobileSidebar();
}

document.getElementById('mobileMenu').onclick = toggleMobileSidebar;
document.getElementById('sidebarBackdrop')?.addEventListener('click', closeMobileSidebar);

for (const btn of document.querySelectorAll('.nav-item')) {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
    btn.classList.add('active');
    closeMobileSidebar();
    loadSection(btn.dataset.section);
  });
}

if (window.matchMedia('(max-width: 820px)').matches) {
  closeMobileSidebar();
}

function stat(label, value, cls = '') {
  return `<div class="stat-card ${cls}"><span class="label">${e(label)}</span><strong>${e(value)}</strong></div>`;
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => toast('تم النسخ')).catch(() => toast('تعذر النسخ', 'error'));
}

function renderCompanyCard(c) {
  if (!c) return '';
  const bank = c.bank || {};
  const contacts = c.contacts || [];
  return `
    <div class="company-hero-wide">
      <img class="sign-banner" src="${e(c.logo_card_url || LOGO_CARD)}" alt="${e(c.name_en || 'NAJJAR & AL SAMOOM TRADING')}">
      <div>
        <h2 style="margin:0;color:var(--navy)">${e(c.name_en || 'NAJJAR & AL SAMOOM TRADING')}</h2>
        <p class="mini" style="letter-spacing:1px">${e(c.tagline_en || 'USED & IMPORTED CARS')}</p>
        <p class="mini">${e(c.name_ar || '')}</p>
        <p class="mini">${e(c.address_ar || '')} · ${e(c.address_en || '')}</p>
      </div>
    </div>
    <div class="split-grid">
      <section class="card">
        <div class="card-header"><h3>Contact</h3></div>
        <div class="card-body contact-grid">
          ${contacts.map(x => `
            <div class="contact-card">
              <strong>${e(x.label_ar)}</strong>
              ${x.whatsapp ? `<span class="wa-badge">WhatsApp</span>` : ''}
              <a href="${x.whatsapp ? waLink(x.phone) : ('tel:' + e(String(x.phone).replace(/\s/g, '')))}" ${x.whatsapp ? 'target="_blank" rel="noopener"' : ''}>${e(x.note || x.phone)}</a>
            </div>`).join('')}
        </div>
      </section>
      <section class="card">
        <div class="card-header"><h3>Bank account — ${e(bank.name_ar || '')}</h3></div>
        <div class="card-body">
          <div class="detail-list">
            <div class="detail-row"><span>اسم صاحب الحساب</span><strong>${e(bank.account_name_en || '')}</strong></div>
            <div class="detail-row copy-row"><span>رقم الحساب</span><span><strong class="number">${e(bank.account_number || '')}</strong> <button type="button" class="btn secondary copy" data-copy="${e(bank.account_number || '')}">نسخ</button></span></div>
            <div class="detail-row copy-row"><span>IBAN</span><span><strong class="number">${e(bank.iban || '')}</strong> <button type="button" class="btn secondary copy" data-copy="${e(bank.iban || '')}">نسخ</button></span></div>
            <div class="detail-row copy-row"><span>SWIFT</span><span><strong class="number">${e(bank.swift || '')}</strong> <button type="button" class="btn secondary copy" data-copy="${e(bank.swift || '')}">نسخ</button></span></div>
            <div class="detail-row"><span>البنك</span><strong>${e(bank.name_ar || '')} · ${e(bank.name_en || '')}</strong></div>
          </div>
        </div>
      </section>
    </div>
    <p class="mini" style="margin-top:12px">الشعار مطابق للافتة الخارجية — NAJJAR & AL SAMOOM TRADING · Nizwa · Falaj</p>`;
}

function bindCopyButtons(root) {
  (root || document).querySelectorAll('[data-copy]').forEach(btn => {
    btn.onclick = () => copyText(btn.getAttribute('data-copy') || '');
  });
}

async function ensureCompany() {
  if (companyProfile) return companyProfile;
  const data = await api('/company');
  companyProfile = data.company || {};
  return companyProfile;
}

async function loadCompany() {
  setTitle('Company', 'Contact & bank details — NAJJAR & AL SAMOOM TRADING');
  const c = await ensureCompany();
  content.innerHTML = renderCompanyCard(c);
  bindCopyButtons(content);
}

async function loadSection(section) {
  currentSection = section;
  content.classList.add('section-updating');
  try {
    if (section === 'dashboard') return await loadDashboard();
    if (section === 'vehicles') return await loadVehicles();
    if (section === 'purchases') return await loadPurchases();
    if (section === 'sales') return await loadSales();
    if (section === 'expenses') return await loadExpenses();
    if (section === 'capital') return await loadCapital();
    if (section === 'transactions') return await loadTransactions();
    if (section === 'imports') return await loadImports();
    if (section === 'staff') return await loadStaff();
    if (section === 'company') return await loadCompany();
  } catch (err) {
    content.innerHTML = `<div class="alert error">${e(err.message)}</div>`;
  } finally {
    requestAnimationFrame(() => content.classList.remove('section-updating'));
  }
}

async function loadStaff() {
  setTitle('Staff', 'NAJJAR & AL SAMOOM TRADING team — access roles');
  const c = await ensureCompany();
  const staff = c.staff || [];
  content.innerHTML = `
    <div class="nt-dash-banner nt-dash-banner--logo">
      <img src="${e(c.logo_url || LOGO_URL)}" alt="NAJJAR & AL SAMOOM TRADING">
      <div>
        <h2>Team</h2>
        <p>Board · Operations · Sales · Accounting — passwords 1–5</p>
      </div>
    </div>
    <div class="nt-staff-grid">
      ${staff.map(s => `
        <article class="nt-staff-card">
          <span class="nt-staff-role ${e(s.role)}">${e(s.role_ar || s.role)}</span>
          <strong>${e(s.name_ar)}</strong>
          <div class="mini">User: <span dir="ltr">${e(s.username)}</span></div>
          ${s.password_hint ? `<div class="mini">Password: <strong dir="ltr">${e(s.password_hint)}</strong></div>` : ''}
          ${s.phone ? `<div class="mini" dir="ltr">+968 ${e(s.phone)}</div>` : ''}
        </article>`).join('')}
    </div>
    <section class="card" style="margin-top:16px">
      <div class="card-header"><h3>Permissions</h3></div>
      <div class="card-body detail-list">
        <div class="detail-row"><span>Board (1–2)</span><strong>waleed.najjar · hamad.sumoom — full access + capital</strong></div>
        <div class="detail-row"><span>Operations (3)</span><strong>sara — stock, purchases, sales, expenses, imports</strong></div>
        <div class="detail-row"><span>Sales (4)</span><strong>sales — stock, sales, imports</strong></div>
        <div class="detail-row"><span>Accounting (5)</span><strong>accounting — purchases, sales, expenses, capital, ledger</strong></div>
      </div>
    </section>`;
}

function allowedSections() {
  const fromApi = window.NAJJAR_SECTIONS;
  if (Array.isArray(fromApi) && fromApi.length) return new Set(fromApi);
  const role = String((window.APP_USER && window.APP_USER.role) || 'viewer').toLower();
  const map = {
    owner: ['dashboard', 'vehicles', 'purchases', 'sales', 'expenses', 'capital', 'transactions', 'imports', 'staff', 'company'],
    admin: ['dashboard', 'vehicles', 'purchases', 'sales', 'expenses', 'capital', 'transactions', 'imports', 'staff', 'company'],
    operations: ['dashboard', 'vehicles', 'purchases', 'sales', 'expenses', 'transactions', 'imports', 'staff', 'company'],
    sales: ['dashboard', 'vehicles', 'sales', 'imports', 'staff', 'company'],
    accountant: ['dashboard', 'vehicles', 'purchases', 'sales', 'expenses', 'capital', 'transactions', 'staff', 'company'],
    viewer: ['dashboard', 'vehicles', 'sales', 'staff', 'company'],
  };
  return new Set(map[role] || map.viewer);
}

function applyNavPermissions() {
  const allowed = allowedSections();
  document.querySelectorAll('.nav-item[data-section]').forEach((btn) => {
    const section = btn.dataset.section;
    const ok = allowed.has(section);
    btn.hidden = !ok;
    btn.disabled = !ok;
    if (!ok) btn.classList.remove('active');
  });
}

function goToSection(name) {
  const allowed = allowedSections();
  const target = allowed.has(name) ? name : (allowed.has('dashboard') ? 'dashboard' : [...allowed][0]);
  document.querySelectorAll('.nav-item').forEach(x => x.classList.toggle('active', x.dataset.section === target));
  loadSection(target);
}

function kpi(icon, label, value, cls = '') {
  return `<div class="stat-card ${cls}">
    <div class="actions-row" style="justify-content:space-between;align-items:flex-start">
      <span class="label">${e(label)}</span>
      <span class="nt-kpi-icon" aria-hidden="true">${icon}</span>
    </div>
    <strong>${value}</strong>
  </div>`;
}

async function loadDashboard() {
  setTitle('Dashboard', 'Staff console — sales · expenses · partner capital');
  const data = await api('/dashboard');
  const c = data.company || {};
  companyProfile = c;
  const s = data.stats;
  const staff = c.staff || [];
  const partners = s.partners || (data.capital || {}).partners || [];
  const netCls = Number(s.net_profit) >= 0 ? 'highlight' : '';
  content.innerHTML = `
    <div class="nt-dash-banner nt-dash-banner--logo">
      <img src="${e(c.logo_url || LOGO_URL)}" alt="NAJJAR & AL SAMOOM TRADING">
      <div>
        <span class="nt-dash-kicker">NAJJAR & AL SAMOOM · USED & IMPORTED CARS</span>
        <h2>Dashboard</h2>
        <p>${e(c.address_ar || 'نزوى — الفلج')} · شريكان: وليد النجار · حمد السموم</p>
      </div>
    </div>
    <div class="stats-grid">
      ${kpi(ICO('car'), 'إجمالي المركبات', s.total_vehicles)}
      ${kpi(ICO('ok'), 'متاحة للبيع', s.available, 'highlight')}
      ${kpi(ICO('sale'), 'إجمالي المبيعات', money(s.sales_total))}
      ${kpi(ICO('buy'), 'تكلفة المبيعات', money(s.cost_of_sales || 0))}
      ${kpi(ICO('exp'), 'إجمالي المصاريف', money(s.expenses_total))}
      ${kpi(ICO('chart'), 'صافي الربح', money(s.net_profit), netCls)}
    </div>
    <p class="mini" style="margin-top:8px">صافي الربح = المبيعات − تكلفة السيارات المباعة ومصاريفها − المصاريف العامة. تكلفة السيارات التي لم تُبع بعد تبقى في قيمة المخزون.</p>
    <div class="stats-grid" style="margin-top:14px">
      ${kpi(ICO('chart'), 'رأس المال الحالي', money(s.total_capital || 0), 'highlight')}
      ${kpi(ICO('sale'), 'توزيعات معتمدة', money(s.total_distributed || 0))}
      ${kpi(ICO('ok'), 'قابل للتوزيع (تقديري)', money(s.distributable_estimate || 0))}
      ${partners.map(p => kpi(ICO('staff'), e(p.name_ar) + ' · ' + Number(p.ownership_pct||0) + '%', money(p.capital_balance || 0))).join('')}
    </div>
    <div class="stats-grid" style="margin-top:14px">
      ${stat('محجوزة', s.reserved)}
      ${stat('مباعة', s.sold)}
      ${stat('قيد الاستيراد', s.importing)}
      ${stat('قيمة المخزون بسعر البيع', money(s.stock_value))}
      ${stat('قيمة المخزون بالتكلفة', money(s.inventory_cost || 0))}
      ${stat('إجمالي المشتريات', money(s.purchases_total))}
      ${stat('حركات اليوم', (Number(s.today_purchases) + Number(s.today_sales) + Number(s.today_expenses)))}
      ${stat('طلبات استيراد نشطة', s.pending_imports)}
    </div>
    <div class="split-grid" style="margin-top:16px">
      <section class="card">
        <div class="card-header"><h3>Quick access</h3></div>
        <div class="card-body">
          <div class="actions-row">
            <button class="btn primary" type="button" id="dashGoVehicles">المخزون</button>
            <button class="btn secondary" type="button" id="dashGoPurchases">تسجيل شراء</button>
            <button class="btn secondary" type="button" id="dashGoSales">المبيعات</button>
            <button class="btn secondary" type="button" id="dashGoExpenses">تسجيل مصروف</button>
            <button class="btn secondary" type="button" id="dashGoCapital">رأس المال والتوزيعات</button>
            <button class="btn secondary" type="button" id="dashGoTransactions">الحركة اليومية</button>
          </div>
        </div>
      </section>
      <section class="card">
        <div class="card-header"><h3>Recent activity</h3></div>
        <div class="card-body audit-list">
          ${data.recent.length ? data.recent.map(a => `
            <div class="contract-card">
              <strong>${e(actionLabel[a.action] || a.action)}</strong>
              <div class="meta">
                <span>${e(a.display_name || 'النظام')}</span>
                <span>${e(new Date(a.created_at).toLocaleString('ar-OM'))}</span>
              </div>
            </div>`).join('') : '<div class="empty-state">لا توجد حركات بعد</div>'}
        </div>
      </section>
    </div>
    <section class="card" style="margin-top:16px">
      <div class="card-header"><h3>NAJJAR & AL SAMOOM TRADING team</h3></div>
      <div class="card-body">
        <div class="nt-staff-grid">
          ${staff.map(x => `
            <div class="nt-staff-card">
              <span class="nt-staff-role ${e(x.role)}">${e(x.role_ar || x.role)}</span>
              <strong>${e(x.name_ar)}</strong>
              <div class="mini" dir="ltr">${e(x.username)}${x.phone ? ' · +968 ' + e(x.phone) : ''}</div>
            </div>`).join('')}
        </div>
      </div>
    </section>
    <section class="card" style="margin-top:16px">
      <div class="card-header"><h3>Contact & banking</h3></div>
      <div class="card-body">
        <div class="contact-grid" style="margin-bottom:14px">
          ${(c.contacts || []).slice(0, 3).map(x => `
            <div class="contact-card">
              <strong>${e(x.label_ar)}</strong>
              ${x.whatsapp ? '<span class="wa-badge">WhatsApp</span>' : ''}
              <a href="${x.whatsapp ? waLink(x.phone) : ('tel:+968' + e(String(x.phone).replace(/\D/g, '')))}" ${x.whatsapp ? 'target="_blank" rel="noopener"' : ''}>${e(x.note || x.phone)}</a>
            </div>`).join('')}
        </div>
        <div class="detail-list">
          <div class="detail-row copy-row"><span>IBAN — ${e((c.bank || {}).name_ar || 'صحار')}</span>
            <span><strong class="number">${e((c.bank || {}).iban || '')}</strong>
            <button type="button" class="btn secondary copy" data-copy="${e((c.bank || {}).iban || '')}">نسخ</button></span>
          </div>
        </div>
        <p class="mini" style="margin-top:10px">${e(c.motto_ar || '')}</p>
      </div>
    </section>`;
  bindCopyButtons(content);
  const allowed = allowedSections();
  const wireDash = (id, section) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (!allowed.has(section)) { el.hidden = true; return; }
    el.onclick = () => goToSection(section);
  };
  wireDash('dashGoVehicles', 'vehicles');
  wireDash('dashGoPurchases', 'purchases');
  wireDash('dashGoSales', 'sales');
  wireDash('dashGoExpenses', 'expenses');
  wireDash('dashGoCapital', 'capital');
  wireDash('dashGoTransactions', 'transactions');
}

const CAPITAL_TYPE_LABEL = {
  opening: 'مساهمة افتتاحية',
  contribution: 'زيادة رأس مال',
  withdrawal: 'سحب من رأس المال',
  distribution: 'توزيع أرباح',
  adjustment: 'تسوية',
};

/* A partner asked to accept a profit figure has to be able to subtract his way
   back to the sale price, so the deductions are laid out in order rather than
   scattered across separate cards. */
function profitChain(s) {
  const row = (label, value, cls = '') =>
    `<tr class="${cls}"><th scope="row">${e(label)}</th><td>${value}</td></tr>`;
  return `<section class="card nt-profit-chain" style="margin-top:14px">
    <div class="card-header"><h3>Profit basis</h3></div>
    <div class="card-body">
      <table class="nt-chain-table">
        <tbody>
          ${row('المبيعات', money(s.sales_total || 0))}
          ${row('− تكلفة شراء السيارات المباعة', money(s.cost_of_sales || 0))}
          ${row('− مصاريف السيارات المباعة', money(s.expenses_on_sold || 0))}
          ${row('= الربح الإجمالي', money(s.gross_profit || 0), 'nt-chain-sum')}
          ${row('− المصاريف العامة', money(s.overhead || 0))}
          ${row('= صافي الربح', money(s.net_profit || 0), 'nt-chain-total')}
        </tbody>
      </table>
      <p class="mini" style="margin-top:10px">المخزون بالتكلفة <strong>${money(s.inventory_cost || 0)}</strong> — سيارات لم تُبع بعد، تكلفتها تبقى في المخزون ولا تُخصم من الربح حتى تُباع.</p>
    </div>
  </section>`;
}

async function loadCapital() {
  setTitle('Capital & Distributions', 'Walid Najjar · Hamad Al Samoom — contributions · draws · profit share');
  const data = await api('/capital');
  const summary = data.summary || {};
  const partners = summary.partners || [];
  const entries = data.entries || [];
  const dists = data.distributions || [];
  const partnerOptions = partners.map(p => `<option value="${e(p.id)}">${e(p.name_ar)} · ${Number(p.ownership_pct||0)}%</option>`).join('');
  content.innerHTML = `
    <div class="nt-dash-banner">
      <div>
        <h2>Partner capital accounting</h2>
        <p>وليد النجار 50% · حمد السموم 50% — تسجيل المساهمات والسحوبات وتوزيع الأرباح</p>
      </div>
    </div>
    <div class="stats-grid">
      ${kpi(ICO('chart'), 'إجمالي رأس المال', money(summary.total_capital || 0), 'highlight')}
      ${kpi(ICO('buy'), 'إجمالي المساهمات', money(summary.total_contributions || 0))}
      ${kpi(ICO('exp'), 'إجمالي السحوبات', money(summary.total_withdrawals || 0))}
      ${kpi(ICO('sale'), 'توزيعات معتمدة', money(summary.total_distributed || 0))}
      ${kpi(ICO('ok'), 'صافي الربح', money(summary.net_profit || 0))}
      ${kpi(ICO('ledger'), 'قابل للتوزيع', money(summary.distributable_estimate || 0))}
    </div>
    ${profitChain(summary)}
    <div class="nt-staff-grid" style="margin-top:14px">
      ${partners.map(p => `
        <article class="nt-staff-card">
          <span class="nt-staff-role owner">${Number(p.ownership_pct||0)}%</span>
          <strong>${e(p.name_ar)}</strong>
          <div class="mini">رصيد رأس المال: <strong>${money(p.capital_balance || 0)}</strong></div>
          <div class="mini">توزيعات مستلمة: <strong>${money(p.distributions_total || 0)}</strong></div>
          ${p.phone ? `<div class="mini" dir="ltr">+968 ${e(p.phone)}</div>` : ''}
        </article>`).join('')}
    </div>
    <div class="split-grid" style="margin-top:16px">
      <section class="card">
        <div class="card-header"><h3>Record capital movement</h3></div>
        <div class="card-body">
          <div class="form-grid">
            <label class="field"><span>الشريك</span><select id="capPartner">${partnerOptions}</select></label>
            <label class="field"><span>النوع</span><select id="capType">
              <option value="opening">مساهمة افتتاحية</option>
              <option value="contribution" selected>زيادة رأس مال</option>
              <option value="withdrawal">سحب من رأس المال</option>
              <option value="adjustment">تسوية</option>
            </select></label>
            <label class="field"><span>المبلغ (OMR)</span><input id="capAmount" type="number" min="0" step="0.001" placeholder="0.000"></label>
            <label class="field"><span>التاريخ</span><input id="capDate" type="date"></label>
            <label class="field"><span>طريقة الدفع</span><select id="capMethod"><option>تحويل بنكي</option><option>نقد</option><option>شيك</option></select></label>
            <label class="field"><span>مرجع / إيصال</span><input id="capRef" placeholder="رقم التحويل أو الإيصال"></label>
            <label class="field full"><span>ملاحظات</span><input id="capNotes" placeholder="اختياري"></label>
          </div>
          <div class="actions-row" style="margin-top:12px">
            <button class="btn primary" type="button" id="capSaveEntry">حفظ الحركة</button>
          </div>
        </div>
      </section>
      <section class="card">
        <div class="card-header"><h3>Distribute profit to partners</h3></div>
        <div class="card-body">
          <div class="form-grid">
            <label class="field"><span>إجمالي التوزيع (OMR)</span><input id="distAmount" type="number" min="0" step="0.001" placeholder="0.000"></label>
            <label class="field"><span>تاريخ التوزيع</span><input id="distDate" type="date"></label>
            <label class="field"><span>الفترة / البيان</span><input id="distPeriod" placeholder="مثال: أرباح الربع الأول 2026"></label>
            <label class="field"><span>الحالة</span><select id="distStatus"><option value="معتمد">معتمد</option><option value="مدفوع">مدفوع</option><option value="مسودة">مسودة</option></select></label>
            <label class="field full"><span>ملاحظات</span><input id="distNotes" placeholder="اختياري"></label>
          </div>
          <p class="mini" style="margin-top:8px">يُقسَّم تلقائياً 50% لوليد النجار و 50% لحمد السموم حسب نسبة الملكية.</p>
          <div class="actions-row" style="margin-top:12px">
            <button class="btn primary" type="button" id="distSave">تنفيذ التوزيع</button>
          </div>
        </div>
      </section>
    </div>
    <section class="card" style="margin-top:16px">
      <div class="card-header"><h3>Capital movement log</h3></div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead><tr><th>الرقم</th><th>التاريخ</th><th>الشريك</th><th>النوع</th><th>المبلغ</th><th>الطريقة</th><th>ملاحظات</th></tr></thead>
          <tbody>
            ${entries.length ? entries.map(r => `
              <tr>
                <td dir="ltr">${e(r.entry_no)}</td>
                <td>${e(r.entry_date || '')}</td>
                <td>${e(r.partner_name || '')}</td>
                <td>${e(CAPITAL_TYPE_LABEL[r.entry_type] || r.entry_type)}</td>
                <td>${money(r.amount)}</td>
                <td>${e(r.method || '—')}</td>
                <td>${e(r.notes || '—')}</td>
              </tr>`).join('') : '<tr><td colspan="7" class="empty-state">لا حركات رأس مال بعد</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
    <section class="card" style="margin-top:16px">
      <div class="card-header"><h3>Distribution log</h3></div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead><tr><th>الرقم</th><th>الفترة</th><th>التاريخ</th><th>الإجمالي</th><th>الحالة</th><th>إجراء</th></tr></thead>
          <tbody>
            ${dists.length ? dists.map(r => `
              <tr>
                <td dir="ltr">${e(r.dist_no)}</td>
                <td>${e(r.period_label || '—')}</td>
                <td>${e(r.dist_date || '')}</td>
                <td>${money(r.total_amount)}</td>
                <td>${pill(r.status, r.status)}</td>
                <td>${r.status === 'مسودة' ? `<button class="btn secondary" type="button" data-approve-dist="${r.id}">اعتماد</button>` : (r.status === 'معتمد' ? `<button class="btn secondary" type="button" data-pay-dist="${r.id}">تعليم مدفوع</button>` : '—')}</td>
              </tr>`).join('') : '<tr><td colspan="6" class="empty-state">لا توزيعات بعد</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>`;
  const today = new Date().toISOString().slice(0, 10);
  const capDate = document.getElementById('capDate');
  const distDate = document.getElementById('distDate');
  if (capDate) capDate.value = today;
  if (distDate) distDate.value = today;
  document.getElementById('capSaveEntry').onclick = async () => {
    try {
      const amount = Number(document.getElementById('capAmount').value || 0);
      if (!(amount > 0)) return toast('أدخل مبلغاً صحيحاً', 'error');
      await api('/capital', {
        method: 'POST',
        body: {
          partner_id: Number(document.getElementById('capPartner').value),
          entry_type: document.getElementById('capType').value,
          amount,
          entry_date: document.getElementById('capDate').value || today,
          method: document.getElementById('capMethod').value,
          reference_no: document.getElementById('capRef').value,
          notes: document.getElementById('capNotes').value,
        },
      });
      toast('تم حفظ حركة رأس المال');
      await loadCapital();
    } catch (err) { toast(err.message, 'error'); }
  };
  document.getElementById('distSave').onclick = async () => {
    try {
      const total_amount = Number(document.getElementById('distAmount').value || 0);
      if (!(total_amount > 0)) return toast('أدخل مبلغ التوزيع', 'error');
      const res = await api('/distributions', {
        method: 'POST',
        body: {
          total_amount,
          dist_date: document.getElementById('distDate').value || today,
          period_label: document.getElementById('distPeriod').value,
          status: document.getElementById('distStatus').value,
          notes: document.getElementById('distNotes').value,
        },
      });
      const splits = (res.splits || []).map(s => `${s.partner_name}: ${money(s.amount)}`).join(' · ');
      toast('تم التوزيع — ' + splits);
      await loadCapital();
    } catch (err) { toast(err.message, 'error'); }
  };
  content.querySelectorAll('[data-approve-dist]').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api('/distributions/' + btn.dataset.approveDist, { method: 'POST', body: { status: 'معتمد' } });
        toast('تم اعتماد التوزيع');
        await loadCapital();
      } catch (err) { toast(err.message, 'error'); }
    };
  });
  content.querySelectorAll('[data-pay-dist]').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api('/distributions/' + btn.dataset.payDist, { method: 'POST', body: { status: 'مدفوع' } });
        toast('تم تعليم التوزيع كمدفوع');
        await loadCapital();
      } catch (err) { toast(err.message, 'error'); }
    };
  });
}

async function loadVehicles() {
  setTitle('Vehicle Inventory', 'Vehicles · purchase, sale & licensing details');
  await ensureCompany().catch(() => null);
  const qs = new URLSearchParams();
  if (statusFilter) qs.set('status', statusFilter);
  if (makeFilter) qs.set('make', makeFilter);
  if (vehicleSearchQ) qs.set('q', vehicleSearchQ);
  const data = await api('/vehicles' + (qs.toString() ? '?' + qs.toString() : ''));
  vehiclesCache = data.vehicles || [];
  const makes = data.makes || [];
  content.innerHTML = `
    <div class="page-head">
      <div>
        <h2>Vehicle inventory</h2>
        <p>${vehiclesCache.length} مركبة</p>
      </div>
      <div class="actions-row vehicle-crud-bar">
        <a class="btn ghost" href="${NAJJAR_WEB}/customer.html" target="_blank" rel="noopener">بوابة الزبائن</a>
        <button class="btn primary" type="button" id="btnAddVehicle">إضافة</button>
        <button class="btn secondary" type="button" id="btnEditSelected" disabled>تعديل</button>
        <button class="btn danger" type="button" id="btnDeleteSelected" disabled>حذف</button>
        <button class="btn ghost" type="button" id="btnCancelSelection">إلغاء</button>
      </div>
    </div>
    <div class="filters">
      <label class="field nt-search-field">
        <span>بحث</span>
        <input type="search" id="vehicleSearch" placeholder="مخزون · ماركة · VIN · لوحة..." value="${e(vehicleSearchQ)}">
      </label>
      <select id="filterStatus">
        <option value="">كل الحالات</option>
        ${['متاحة', 'محجوزة', 'مباعة', 'قيد الاستيراد', 'صيانة'].map(s => `<option value="${s}" ${statusFilter === s ? 'selected' : ''}>${s}</option>`).join('')}
      </select>
      <select id="filterMake">
        <option value="">كل الماركات</option>
        ${makes.map(m => `<option value="${e(m)}" ${makeFilter === m ? 'selected' : ''}>${e(m)}</option>`).join('')}
      </select>
      <button class="btn secondary" type="button" id="btnApplyFilter">تصفية</button>
    </div>
    <div id="vehiclesShowcase">
      ${vehiclesCache.length ? `<div class="vehicle-grid">${vehiclesCache.map(v => vehicleCard(v)).join('')}</div>` : '<div class="empty-state">لا توجد مركبات — أضف مركبة جديدة</div>'}
    </div>`;
  document.getElementById('vehiclesShowcase').querySelectorAll('[data-vehicle-id]').forEach((card) => {
    card.onclick = (ev) => {
      if (ev.target.closest('[data-edit-id], [data-delete-id]')) return;
      selectVehicle(card.getAttribute('data-vehicle-id'));
      openVehicleDetail(card.getAttribute('data-vehicle-id'));
    };
  });
  document.getElementById('vehiclesShowcase').querySelectorAll('[data-edit-id]').forEach((btn) => {
    btn.onclick = (ev) => {
      ev.stopPropagation();
      selectVehicle(btn.getAttribute('data-edit-id'));
      editVehicleById(btn.getAttribute('data-edit-id'));
    };
  });
  document.getElementById('vehiclesShowcase').querySelectorAll('[data-delete-id]').forEach((btn) => {
    btn.onclick = (ev) => {
      ev.stopPropagation();
      selectVehicle(btn.getAttribute('data-delete-id'));
      deleteVehicleById(btn.getAttribute('data-delete-id'));
    };
  });
  document.getElementById('btnAddVehicle').onclick = showAddVehicleForm;
  document.getElementById('btnEditSelected').onclick = () => {
    if (!selectedVehicleId) return toast('اختر مركبة أولاً', 'error');
    editVehicleById(selectedVehicleId);
  };
  document.getElementById('btnDeleteSelected').onclick = () => {
    if (!selectedVehicleId) return toast('اختر مركبة أولاً', 'error');
    deleteVehicleById(selectedVehicleId);
  };
  document.getElementById('btnCancelSelection').onclick = () => {
    clearVehicleSelection();
    closeDrawer();
    closeModal();
  };
  document.getElementById('btnApplyFilter').onclick = () => {
    statusFilter = document.getElementById('filterStatus').value;
    makeFilter = document.getElementById('filterMake').value;
    vehicleSearchQ = document.getElementById('vehicleSearch').value.trim();
    loadVehicles();
  };
  const searchInput = document.getElementById('vehicleSearch');
  if (searchInput) {
    searchInput.onkeydown = (ev) => {
      if (ev.key === 'Enter') document.getElementById('btnApplyFilter').click();
    };
  }
}

function vehiclePhotos(v) {
  let photos = v.photos || [];
  if (typeof photos === 'string') {
    try { photos = JSON.parse(photos); } catch (_) { photos = photos ? [photos] : []; }
  }
  return Array.isArray(photos) ? photos.filter(Boolean) : [];
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result || ''));
    r.onerror = () => reject(new Error('تعذر قراءة الملف'));
    r.readAsDataURL(file);
  });
}

async function uploadVehiclePhotos(vehicleId, files) {
  const list = Array.from(files || []).filter(Boolean);
  if (!list.length) return [];
  const urls = [];
  for (const file of list) {
    const image = await readFileAsDataUrl(file);
    const res = await api('/vehicles/' + vehicleId + '/photos', {
      method: 'POST',
      body: { image, content_type: file.type || 'image/jpeg', name: file.name },
    });
    if (res.url) urls.push(res.url);
  }
  return urls;
}

function renderPhotoGallery(photos, idPrefix = 'veh') {
  if (!photos.length) return '<p class="mini">لا توجد صور — حمّل صوراً من الأسفل</p>';
  return `<div class="nt-photo-thumbs">${photos.map((p, i) => `
    <div class="nt-photo-thumb${i === 0 ? ' active' : ''}"><img src="${e(uploadUrl(p))}" alt="صورة ${i + 1}" loading="lazy"></div>
  `).join('')}</div>`;
}

function renderEditablePhotoGallery(photos, vehicleId) {
  if (!photos.length) return '<p class="mini">لا توجد صور بعد</p>';
  return `<div class="nt-photo-thumbs nt-photo-thumbs--edit">${photos.map((p, i) => `
    <div class="nt-photo-thumb nt-photo-thumb--edit">
      <img src="${e(uploadUrl(p))}" alt="صورة ${i + 1}" loading="lazy">
      <button type="button" class="btn small danger nt-photo-del" data-photo-url="${e(p)}" data-vehicle-id="${vehicleId}" title="حذف الصورة">×</button>
    </div>
  `).join('')}</div>`;
}

async function deleteVehiclePhoto(vehicleId, url) {
  if (!confirm('حذف هذه الصورة من المركبة؟')) return;
  try {
    await api('/vehicles/' + vehicleId + '/photos', { method: 'DELETE', body: { url } });
    toast('تم حذف الصورة');
    return true;
  } catch (err) {
    toast(err.message, 'error');
    return false;
  }
}

function bindPhotoDeleteButtons(root, onDone) {
  (root || document).querySelectorAll('.nt-photo-del').forEach((btn) => {
    btn.onclick = async (ev) => {
      ev.stopPropagation();
      const vid = btn.getAttribute('data-vehicle-id');
      const url = btn.getAttribute('data-photo-url');
      if (await deleteVehiclePhoto(vid, url)) {
        if (typeof onDone === 'function') onDone(vid);
      }
    };
  });
}

function photoUploadField(idPrefix, label = 'تحميل صور') {
  return `
    <label class="field full">
      <span>${label}</span>
      <input type="file" id="${idPrefix}Photos" accept="image/*" multiple>
      <p class="mini">JPG · PNG · WebP — حتى 5MB لكل صورة</p>
    </label>
    <div id="${idPrefix}PhotoPreview" class="nt-photo-thumbs hidden"></div>`;
}

function bindPhotoPreview(inputId, previewId) {
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  if (!input || !preview) return;
  input.onchange = () => {
    const files = Array.from(input.files || []);
    if (!files.length) {
      preview.innerHTML = '';
      preview.classList.add('hidden');
      return;
    }
    preview.classList.remove('hidden');
    preview.innerHTML = files.map((f) => {
      const url = URL.createObjectURL(f);
      return `<div class="nt-photo-thumb"><img src="${url}" alt="${e(f.name)}"></div>`;
    }).join('');
  };
}

function clearVehicleSelection() {
  selectedVehicleId = null;
  document.querySelectorAll('.vehicle-card.selected').forEach((el) => el.classList.remove('selected'));
  const editBtn = document.getElementById('btnEditSelected');
  const delBtn = document.getElementById('btnDeleteSelected');
  if (editBtn) editBtn.disabled = true;
  if (delBtn) delBtn.disabled = true;
}

function selectVehicle(id) {
  selectedVehicleId = String(id);
  document.querySelectorAll('.vehicle-card').forEach((el) => {
    el.classList.toggle('selected', el.getAttribute('data-vehicle-id') === selectedVehicleId);
  });
  const editBtn = document.getElementById('btnEditSelected');
  const delBtn = document.getElementById('btnDeleteSelected');
  if (editBtn) editBtn.disabled = false;
  if (delBtn) delBtn.disabled = false;
}

async function deleteVehicleById(id) {
  const v = vehiclesCache.find((row) => String(row.id) === String(id));
  const label = v ? `${v.make} ${v.model} (${v.stock_no})` : 'هذه المركبة';
  if (!confirm(`حذف ${label}؟ لا يمكن التراجع.`)) return;
  try {
    await api('/vehicles/' + id, { method: 'DELETE' });
    toast('تم حذف المركبة');
    clearVehicleSelection();
    loadVehicles();
  } catch (err) { toast(err.message, 'error'); }
}

async function editVehicleById(id) {
  const data = await api('/vehicles/' + id);
  showEditVehicleForm(data.vehicle);
}

function vehicleCard(v) {
  const price = Number(v.list_price) > 0 ? money(v.list_price) : 'حسب الاتفاق';
  const photos = vehiclePhotos(v);
  const media = photos[0]
    ? `<div class="nt-show-media"><img class="nt-photo-main" src="${e(uploadUrl(photos[0]))}" alt="${e(v.make)} ${e(v.model)}" loading="lazy"></div>`
    : '';
  const usd = Number(v.price_usd || 0) > 0
    ? `<span class="nt-price-fx" dir="ltr">${Number(v.price_usd).toLocaleString('en-US')} USD</span>`
    : '';
  return `
    <article class="vehicle-card nt-vcard nt-show-card${String(selectedVehicleId) === String(v.id) ? ' selected' : ''}" data-vehicle-id="${v.id}" role="button" tabindex="0">
      ${media}
      <div class="nt-vcard-top">
        <span class="nt-vcard-stock">${e(v.stock_no)}</span>
        ${pill(v.status)}
      </div>
      <h4>${e(v.make)} ${e(v.model)}</h4>
      <p class="nt-vcard-var">${e(v.variant || '')} · ${e(v.year || '—')} · ${e(v.color || '')}</p>
      <ul class="nt-vcard-meta">
        ${v.vin ? `<li><span>VIN</span><strong dir="ltr">${e(v.vin)}</strong></li>` : ''}
        ${v.plate_no ? `<li><span>اللوحة</span><strong>${e(v.plate_no)}</strong></li>` : ''}
        ${v.engine_cc ? `<li><span>المحرك</span><strong>${e(v.engine_cc)} cc</strong></li>` : ''}
        ${v.seller_name ? `<li><span>البائع</span><strong>${e(v.seller_name)}</strong></li>` : ''}
        ${v.buyer_name ? `<li><span>المشتري</span><strong>${e(v.buyer_name)}</strong></li>` : ''}
        ${v.origin_country ? `<li><span>المنشأ</span><strong>${e(v.origin_country)}</strong></li>` : ''}
      </ul>
      <div class="nt-vcard-foot nt-vcard-foot--stack">
        <div class="nt-price-block"><strong class="nt-show-price">${price}</strong>${usd}</div>
        <div class="nt-vcard-actions">
          <button type="button" class="btn small secondary" data-edit-id="${v.id}">تعديل</button>
          <button type="button" class="btn small danger" data-delete-id="${v.id}">حذف</button>
        </div>
      </div>
    </article>`;
}

function purchaseInfoRows(v) {
  if (!v.seller_name && !Number(v.purchase_cost)) return '';
  return `
    <div class="detail-row"><span>اسم البائع (اشتريت منه)</span><strong>${e(v.seller_name || '—')}</strong></div>
    <div class="detail-row"><span>هاتف البائع</span><strong>${e(v.seller_phone || '—')}</strong></div>
    <div class="detail-row"><span>رقم بطاقة/سجل البائع</span><strong class="number">${e(v.seller_id || '—')}</strong></div>
    <div class="detail-row"><span>تاريخ الشراء</span><strong>${dmy(v.purchase_date)}</strong></div>`;
}

function saleInfoRows(v, sales) {
  if (!sales || !sales.length) return '';
  const s = sales[0];
  return `
    <div class="detail-row"><span>اسم المشتري (بيعت له)</span><strong>${e(s.buyer_name || '—')}</strong></div>
    <div class="detail-row"><span>هاتف المشتري</span><strong>${e(s.buyer_phone || '—')}</strong></div>
    <div class="detail-row"><span>تاريخ البيع</span><strong>${dmy(s.sale_date)}</strong></div>
    <div class="detail-row"><span>سعر البيع الفعلي</span><strong>${money(s.sale_price)}</strong></div>
    <div class="detail-row"><span>رقم البيع</span><strong class="number">${e(s.sale_no || '—')}</strong></div>`;
}

async function openVehicleDetail(id) {
  const data = await api('/vehicles/' + id);
  const v = data.vehicle;
  const sales = data.sales || [];
  const priceDisplay = Number(v.list_price) > 0 ? money(v.list_price) : 'حسب الاتفاق';
  const licenseLink = vehicleDocLink(v);
  const purchaseRows = purchaseInfoRows(v);
  const saleRows = saleInfoRows(v, sales);
  const photos = vehiclePhotos(v);
  openDrawer(`
    <div class="drawer-title"><h2>${e(v.make)} ${e(v.model)}</h2><p>${e(v.stock_no)} · ${pill(v.status)}</p></div>
    ${photos.length ? `<div style="margin:12px 0">${renderPhotoGallery(photos)}</div>` : ''}
    <div class="detail-list" style="margin:16px 0">
      <div class="detail-row"><span>الطراز</span><strong>${e(v.variant || '—')}</strong></div>
      <div class="detail-row"><span>النوع</span><strong>${e(v.vehicle_type || '—')}</strong></div>
      <div class="detail-row"><span>اللون / السنة</span><strong>${e(v.color || '—')} · ${e(v.year || '—')}</strong></div>
      <div class="detail-row"><span>رقم الهيكل</span><strong class="number">${e(v.vin || '—')}</strong></div>
      <div class="detail-row"><span>رقم المحرك</span><strong class="number">${e(v.engine_no || '—')}</strong></div>
      ${licenseDetailRows(v)}
      <div class="detail-row"><span>سعر الشراء</span><strong>${Number(v.purchase_cost) > 0 ? money(v.purchase_cost) : '—'}</strong></div>
      <div class="detail-row"><span>سعر البيع المطلوب</span><strong>${priceDisplay}</strong></div>
      <div class="detail-row"><span>بلد المنشأ</span><strong>${e(v.origin_country || '—')}</strong></div>
      <div class="detail-row"><span>مرجع الاستيراد</span><strong>${e(v.import_ref || '—')}</strong></div>
      <div class="detail-row"><span>اللوحة</span><strong>${e(v.plate_no || '—')}</strong></div>
      ${v.notes ? `<div class="detail-row"><span>ملاحظات</span><strong>${e(v.notes)}</strong></div>` : ''}
    </div>
    ${purchaseRows ? `<h3 style="margin:14px 0 6px">معلومات الشراء — من البائع</h3><div class="detail-list">${purchaseRows}</div>` : ''}
    ${saleRows ? `<h3 style="margin:14px 0 6px">معلومات البيع — للمشتري</h3><div class="detail-list">${saleRows}</div>` : ''}
    ${licenseLink}
    <div class="photo-upload-block" style="margin:14px 0">
      <h3 style="margin:0 0 8px">صور المركبة</h3>
      ${renderEditablePhotoGallery(photos, v.id)}
      ${photoUploadField('drawerUpload', 'تحميل صور جديدة')}
      <button class="btn secondary" type="button" id="btnUploadDrawerPhotos">رفع الصور</button>
    </div>
    <div class="form-actions">
      ${v.status !== 'مباعة' ? `<button class="btn success" type="button" id="btnSellVehicle">تسجيل بيع</button>` : ''}
      ${v.status === 'متاحة' ? `<button class="btn secondary" type="button" id="btnReserveVehicle">حجز</button>` : ''}
      <button class="btn secondary" type="button" id="btnWaVehicle">واتساب</button>
      <button class="btn ghost" type="button" id="btnPrintVehicle">طباعة عرض</button>
      <button class="btn secondary" type="button" id="btnEditVehicle">تعديل</button>
      ${v.status !== 'مباعة' ? `<button class="btn danger" type="button" id="btnDeleteVehicle">حذف</button>` : ''}
      <button class="btn ghost" type="button" id="btnCancelDrawer">إلغاء</button>
    </div>`);
  const sellBtn = document.getElementById('btnSellVehicle');
  if (sellBtn) sellBtn.onclick = () => showSaleForm(v);
  document.getElementById('btnWaVehicle').onclick = async () => {
    const c = await ensureCompany();
    const msg = encodeURIComponent(vehicleWhatsAppText(v, c));
    window.open(waLink('71924089') + '?text=' + msg, '_blank', 'noopener');
  };
  document.getElementById('btnPrintVehicle').onclick = () => printVehicleOffer(v);
  const reserveBtn = document.getElementById('btnReserveVehicle');
  if (reserveBtn) reserveBtn.onclick = () => showReserveForm(v);
  document.getElementById('btnEditVehicle').onclick = () => showEditVehicleForm(v);
  document.getElementById('btnCancelDrawer').onclick = closeDrawer;
  bindPhotoPreview('drawerUploadPhotos', 'drawerUploadPhotoPreview');
  bindPhotoDeleteButtons(document.getElementById('drawerContent'), (vid) => openVehicleDetail(vid));
  document.getElementById('btnUploadDrawerPhotos').onclick = async () => {
    const input = document.getElementById('drawerUploadPhotos');
    const files = input?.files;
    if (!files?.length) return toast('اختر صوراً للرفع', 'error');
    try {
      await uploadVehiclePhotos(v.id, files);
      toast('تم رفع الصور');
      openVehicleDetail(v.id);
    } catch (err) { toast(err.message, 'error'); }
  };
  const deleteBtn = document.getElementById('btnDeleteVehicle');
  if (deleteBtn) deleteBtn.onclick = () => { closeDrawer(); deleteVehicleById(v.id); };
}

function showReserveForm(v) {
  closeDrawer();
  openModal(`
    <h2>Reserve vehicle — ${e(v.make)} ${e(v.model)}</h2>
    <div class="form-grid">
      <label class="field"><span>اسم العميل *</span><input id="rName"></label>
      <label class="field"><span>الهاتف</span><input id="rPhone"></label>
      <label class="field full"><span>ملاحظات</span><textarea id="rNotes" rows="2"></textarea></label>
    </div>
    <div class="form-actions">
      <button class="btn primary" type="button" id="btnConfirmReserve">تأكيد الحجز</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
    </div>`);
  document.getElementById('btnConfirmReserve').onclick = async () => {
    const name = document.getElementById('rName').value.trim();
    if (!name) return toast('اسم العميل مطلوب', 'error');
    try {
      await api('/vehicles/' + v.id, {
        method: 'POST',
        body: {
          status: 'محجوزة',
          reserved_by: name,
          buyer_name: name,
          buyer_phone: document.getElementById('rPhone').value.trim(),
          notes: (v.notes ? v.notes + '\n' : '') + 'حجز: ' + (document.getElementById('rNotes').value.trim() || name),
        },
      });
      closeModal();
      toast('تم حجز المركبة');
      loadVehicles();
    } catch (err) { toast(err.message, 'error'); }
  };
}

function showAddVehicleForm() {
  openModal(`
    <h2>Add new vehicle</h2>
    <div class="form-grid">
      <label class="field"><span>رقم المخزون *</span><input id="fStockNo" placeholder="NT-LR-002"></label>
      <label class="field"><span>الماركة *</span><input id="fMake" placeholder="Toyota"></label>
      <label class="field"><span>الطراز *</span><input id="fModel" placeholder="Camry"></label>
      <label class="field"><span>الفئة</span><input id="fVariant" placeholder="LE"></label>
      <label class="field"><span>نوع المركبة</span><input id="fType" placeholder="Sedan"></label>
      <label class="field"><span>اللون</span><input id="fColor"></label>
      <label class="field"><span>سنة الصنع</span><input id="fYear" type="number" min="1990" max="2030"></label>
      <label class="field"><span>رقم الهيكل VIN</span><input id="fVin"></label>
      <label class="field"><span>بلد المنشأ</span><input id="fOrigin"></label>
      <label class="field"><span>سعر البيع المطلوب</span><input id="fList" type="number" step="0.001"></label>
    </div>
    <h3 style="margin:16px 0 6px">معلومات الشراء — من اشتريت المركبة منه</h3>
    <div class="form-grid">
      <label class="field"><span>اسم البائع</span><input id="fSellerName" placeholder="اسم البائع / المالك السابق"></label>
      <label class="field"><span>هاتف البائع</span><input id="fSellerPhone"></label>
      <label class="field"><span>رقم بطاقة/سجل البائع</span><input id="fSellerId"></label>
      <label class="field"><span>سعر الشراء</span><input id="fPurchase" type="number" step="0.001"></label>
      <label class="field"><span>تاريخ الشراء</span><input id="fPurchaseDate" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
    </div>
    <div class="form-grid" style="margin-top:6px">
      <label class="field full"><span>ملاحظات</span><textarea id="fNotes" rows="2"></textarea></label>
    </div>
    <h3 style="margin:16px 0 6px">صور المركبة</h3>
    ${photoUploadField('fNew', 'تحميل صور')}
    <div class="form-actions">
      <button class="btn primary" type="button" id="btnSaveVehicle">حفظ</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
    </div>`);
  bindPhotoPreview('fNewPhotos', 'fNewPhotoPreview');
  document.getElementById('btnSaveVehicle').onclick = async () => {
    try {
      const res = await api('/vehicles', {
        method: 'POST',
        body: {
          stock_no: document.getElementById('fStockNo').value.trim(),
          make: document.getElementById('fMake').value.trim(),
          model: document.getElementById('fModel').value.trim(),
          variant: document.getElementById('fVariant').value.trim(),
          vehicle_type: document.getElementById('fType').value.trim(),
          color: document.getElementById('fColor').value.trim(),
          year: Number(document.getElementById('fYear').value) || null,
          vin: document.getElementById('fVin').value.trim(),
          purchase_cost: Number(document.getElementById('fPurchase').value) || 0,
          list_price: Number(document.getElementById('fList').value) || 0,
          origin_country: document.getElementById('fOrigin').value.trim(),
          seller_name: document.getElementById('fSellerName').value.trim(),
          seller_phone: document.getElementById('fSellerPhone').value.trim(),
          seller_id: document.getElementById('fSellerId').value.trim(),
          purchase_date: document.getElementById('fPurchaseDate').value,
          notes: document.getElementById('fNotes').value.trim(),
        },
      });
      const photoInput = document.getElementById('fNewPhotos');
      if (photoInput?.files?.length && res.vehicle?.id) {
        await uploadVehiclePhotos(res.vehicle.id, photoInput.files);
      }
      closeModal();
      toast('تمت إضافة المركبة');
      loadVehicles();
    } catch (err) { toast(err.message, 'error'); }
  };
}

function showEditVehicleForm(v) {
  closeDrawer();
  const photos = vehiclePhotos(v);
  openModal(`
    <h2>Edit ${e(v.make)} ${e(v.model)}</h2>
    <div id="editPhotoGallery" style="margin-bottom:12px">${renderEditablePhotoGallery(photos, v.id)}</div>
    <div class="form-grid">
      <label class="field"><span>الحالة</span>
        <select id="eStatus">${['متاحة', 'محجوزة', 'مباعة', 'قيد الاستيراد', 'صيانة'].map(s => `<option value="${s}" ${v.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select>
      </label>
      <label class="field"><span>سعر الشراء</span><input id="ePurchase" type="number" step="0.001" value="${v.purchase_cost || 0}"></label>
      <label class="field"><span>سعر البيع</span><input id="eList" type="number" step="0.001" value="${v.list_price || 0}"></label>
      <label class="field"><span>رقم اللوحة</span><input id="ePlate" value="${e(v.plate_no || '')}"></label>
      <label class="field"><span>صلاحية الرخصة</span><input id="eLicense" type="date" value="${e(v.license_valid_until || '')}"></label>
      <label class="field"><span>شركة التأمين</span><input id="eInsurance" value="${e(v.insurance_company || '')}"></label>
      <label class="field"><span>وثيقة التأمين</span><input id="ePolicy" value="${e(v.insurance_policy || '')}"></label>
      <label class="field"><span>نوع التأمين</span><input id="eInsType" value="${e(v.insurance_type || '')}"></label>
      <label class="field"><span>اسم البائع (اشتريت منه)</span><input id="eSellerName" value="${e(v.seller_name || '')}"></label>
      <label class="field"><span>هاتف البائع</span><input id="eSellerPhone" value="${e(v.seller_phone || '')}"></label>
      <label class="field"><span>رقم بطاقة/سجل البائع</span><input id="eSellerId" value="${e(v.seller_id || '')}"></label>
      <label class="field"><span>تاريخ الشراء</span><input id="ePurchaseDate" type="date" value="${e(v.purchase_date || '')}"></label>
      <label class="field full"><span>ملاحظات</span><textarea id="eNotes" rows="2">${e(v.notes || '')}</textarea></label>
    </div>
    <h3 style="margin:16px 0 6px">صور المركبة</h3>
    ${photoUploadField('fEdit', 'تحميل صور إضافية')}
    <div class="form-actions">
      <button class="btn primary" type="button" id="btnUpdateVehicle">حفظ التعديل</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
      ${v.status !== 'مباعة' ? `<button class="btn danger" type="button" id="btnDeleteInEdit">حذف</button>` : ''}
    </div>`);
  bindPhotoPreview('fEditPhotos', 'fEditPhotoPreview');
  bindPhotoDeleteButtons(document.getElementById('modalContent'), (vid) => {
    const fresh = vehiclesCache.find((row) => String(row.id) === String(vid));
    if (fresh) showEditVehicleForm(fresh);
    else showEditVehicleForm(v);
  });
  document.getElementById('btnUpdateVehicle').onclick = async () => {
    try {
      await api('/vehicles/' + v.id, {
        method: 'POST',
        body: {
          status: document.getElementById('eStatus').value,
          purchase_cost: Number(document.getElementById('ePurchase').value) || 0,
          list_price: Number(document.getElementById('eList').value) || 0,
          plate_no: document.getElementById('ePlate').value.trim(),
          license_valid_until: document.getElementById('eLicense').value,
          insurance_company: document.getElementById('eInsurance').value.trim(),
          insurance_policy: document.getElementById('ePolicy').value.trim(),
          insurance_type: document.getElementById('eInsType').value.trim(),
          seller_name: document.getElementById('eSellerName').value.trim(),
          seller_phone: document.getElementById('eSellerPhone').value.trim(),
          seller_id: document.getElementById('eSellerId').value.trim(),
          purchase_date: document.getElementById('ePurchaseDate').value,
          notes: document.getElementById('eNotes').value.trim(),
        },
      });
      const photoInput = document.getElementById('fEditPhotos');
      if (photoInput?.files?.length) {
        await uploadVehiclePhotos(v.id, photoInput.files);
      }
      closeModal();
      toast('تم حفظ التعديل');
      loadVehicles();
    } catch (err) { toast(err.message, 'error'); }
  };
  const delInEdit = document.getElementById('btnDeleteInEdit');
  if (delInEdit) delInEdit.onclick = () => { closeModal(); deleteVehicleById(v.id); };
}

function showSaleForm(v) {
  closeDrawer();
  openModal(`
    <h2>Record sale — ${e(v.make)} ${e(v.model)}</h2>
    <p class="mini">مخزون: ${e(v.stock_no)} · السعر: ${money(v.list_price)}</p>
    <div class="form-grid">
      <label class="field"><span>اسم المشتري *</span><input id="sBuyer"></label>
      <label class="field"><span>الهاتف</span><input id="sPhone"></label>
      <label class="field"><span>رقم الهوية / البطاقة</span><input id="sBuyerId" placeholder="للعقد والفاتورة"></label>
      <label class="field"><span>سعر البيع</span><input id="sPrice" type="number" step="0.001" value="${v.list_price || 0}"></label>
      <label class="field"><span>العربون / المدفوع</span><input id="sDeposit" type="number" step="0.001" value="0"></label>
      <label class="field"><span>طريقة الدفع</span>
        <select id="sMethod"><option>نقد</option><option>تحويل بنكي</option><option>شيك</option><option>تمويل</option></select>
      </label>
      <label class="field"><span>تاريخ البيع</span><input id="sDate" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
      <label class="field full"><span>ملاحظات</span><textarea id="sNotes" rows="2"></textarea></label>
    </div>
    <div class="form-actions">
      <button class="btn success" type="button" id="btnConfirmSale">تأكيد البيع</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
    </div>`);
  document.getElementById('btnConfirmSale').onclick = async () => {
    try {
      const res = await api('/sales', {
        method: 'POST',
        body: {
          vehicle_id: v.id,
          buyer_name: document.getElementById('sBuyer').value.trim(),
          buyer_phone: document.getElementById('sPhone').value.trim(),
          buyer_id: document.getElementById('sBuyerId').value.trim(),
          sale_price: Number(document.getElementById('sPrice').value) || 0,
          deposit_amount: Number(document.getElementById('sDeposit').value) || 0,
          payment_method: document.getElementById('sMethod').value,
          sale_date: document.getElementById('sDate').value,
          notes: document.getElementById('sNotes').value.trim(),
        },
      });
      closeModal();
      toast('تم تسجيل البيع — ' + (res.sale?.sale_no || ''));
      const saleRow = res.sale || {};
      const c = await ensureCompany();
      if (window.NajjarPrintDocs && confirm('طباعة عقد البيع العُماني؟')) {
        NajjarPrintDocs.printSaleContract(saleRow, saleRow, c);
      } else if (confirm('طباعة سند القبض؟')) {
        printSaleReceipt(saleRow, c);
      }
      loadVehicles();
    } catch (err) { toast(err.message, 'error'); }
  };
}

async function loadSales() {
  setTitle('Sales', 'Sale contracts · invoices · receipts — Sultanate of Oman');
  const data = await api('/sales');
  const rows = data.sales || [];
  content.innerHTML = `
    <div class="page-head"><div><h2>Sales & documents</h2><p>${rows.length} عملية بيع · اطبع عقد بيع أو فاتورة أو سند قبض</p></div></div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>رقم البيع</th><th>المركبة</th><th>المشتري</th><th>السعر</th><th>التاريخ</th><th>الحالة</th><th>مستندات عُمانية</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map((r, i) => `
            <tr>
              <td><b>${e(r.sale_no)}</b></td>
              <td>${e(r.make || '')} ${e(r.model || '')} <span class="mini">${e(r.stock_no)}</span></td>
              <td>${e(r.buyer_name)}<br><span class="mini">${e(r.buyer_phone || '')}</span></td>
              <td class="money">${money(r.sale_price)}</td>
              <td>${dmy(r.sale_date)}</td>
              <td>${pill(r.status)}</td>
              <td>${saleDocActions(i)}</td>
            </tr>`).join('') : '<tr><td colspan="7" class="empty-state">لا مبيعات بعد</td></tr>'}
        </tbody>
      </table>
    </div>`;
  await bindSaleDocButtons(content, rows);
}

async function loadPurchases() {
  setTitle('Purchases', 'Purchase contracts · invoices · payments — Sultanate of Oman');
  const [purchData, vehData] = await Promise.all([api('/purchases'), api('/vehicles')]);
  const rows = purchData.purchases || [];
  const vehicles = vehData.vehicles || [];
  const total = rows.reduce((sum, r) => sum + Number(r.purchase_price || 0), 0);
  content.innerHTML = `
    <div class="page-head">
      <div><h2>Purchases & documents</h2><p>${rows.length} عملية شراء · إجمالي ${money(total)} · عقد شراء / فاتورة / سند صرف</p></div>
      <div class="actions-row">
        <button class="btn primary" type="button" id="btnAddPurchase">+ تسجيل شراء</button>
      </div>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>رقم الشراء</th><th>المركبة</th><th>البائع</th><th>هاتف البائع</th><th>السعر</th><th>التاريخ</th><th>مستندات عُمانية</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map((r, i) => `
            <tr>
              <td><b>${e(r.purchase_no)}</b></td>
              <td>${e(r.make || '')} ${e(r.model || '')} <span class="mini">${e(r.stock_no || '')}</span></td>
              <td>${e(r.seller_name)}</td>
              <td dir="ltr">${e(r.seller_phone || '—')}</td>
              <td class="money">${money(r.purchase_price)}</td>
              <td>${dmy(r.purchase_date)}</td>
              <td>${purchaseDocActions(i)}</td>
            </tr>`).join('') : '<tr><td colspan="7" class="empty-state">لا مشتريات مسجلة بعد</td></tr>'}
        </tbody>
      </table>
    </div>`;
  document.getElementById('btnAddPurchase').onclick = () => showAddPurchaseForm(vehicles);
  await bindPurchaseDocButtons(content, rows);
}

function showAddPurchaseForm(vehicles) {
  openModal(`
    <h2>Record vehicle purchase</h2>
    <div class="form-grid">
      <label class="field full"><span>المركبة (اختياري)</span>
        <select id="pVehicle">
          <option value="">— بدون ربط بمركبة —</option>
          ${vehicles.map(v => `<option value="${v.id}">${e(v.stock_no)} — ${e(v.make)} ${e(v.model)}</option>`).join('')}
        </select>
      </label>
      <label class="field"><span>اسم البائع *</span><input id="pSellerName" placeholder="اسم البائع / المالك السابق"></label>
      <label class="field"><span>هاتف البائع</span><input id="pSellerPhone"></label>
      <label class="field"><span>رقم بطاقة/سجل البائع</span><input id="pSellerId"></label>
      <label class="field"><span>بلد/مصدر الشراء</span><input id="pSourceCountry"></label>
      <label class="field"><span>سعر الشراء *</span><input id="pPrice" type="number" step="0.001"></label>
      <label class="field"><span>المبلغ المدفوع</span><input id="pPaid" type="number" step="0.001"></label>
      <label class="field"><span>طريقة الدفع</span>
        <select id="pMethod"><option>نقد</option><option>تحويل بنكي</option><option>شيك</option><option>تمويل</option></select>
      </label>
      <label class="field"><span>تاريخ الشراء</span><input id="pDate" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
      <label class="field full"><span>ملاحظات</span><textarea id="pNotes" rows="2"></textarea></label>
    </div>
    <div class="form-actions">
      <button class="btn primary" type="button" id="btnConfirmPurchase">حفظ عملية الشراء</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
    </div>`);
  document.getElementById('btnConfirmPurchase').onclick = async () => {
    const sellerName = document.getElementById('pSellerName').value.trim();
    if (!sellerName) return toast('اسم البائع مطلوب', 'error');
    const price = Number(document.getElementById('pPrice').value) || 0;
    if (price <= 0) return toast('سعر الشراء مطلوب', 'error');
    try {
      const res = await api('/purchases', {
        method: 'POST',
        body: {
          vehicle_id: Number(document.getElementById('pVehicle').value) || null,
          seller_name: sellerName,
          seller_phone: document.getElementById('pSellerPhone').value.trim(),
          seller_id: document.getElementById('pSellerId').value.trim(),
          source_country: document.getElementById('pSourceCountry').value.trim(),
          purchase_price: price,
          paid_amount: Number(document.getElementById('pPaid').value) || price,
          payment_method: document.getElementById('pMethod').value,
          purchase_date: document.getElementById('pDate').value,
          notes: document.getElementById('pNotes').value.trim(),
        },
      });
      closeModal();
      toast('تم تسجيل الشراء — ' + (res.purchase?.purchase_no || ''));
      const c = await ensureCompany();
      const row = res.purchase || {};
      if (window.NajjarPrintDocs && confirm('طباعة عقد الشراء العُماني؟')) {
        NajjarPrintDocs.printPurchaseContract(row, row, c);
      } else if (window.NajjarPrintDocs && confirm('طباعة سند الصرف؟')) {
        NajjarPrintDocs.printPaymentVoucher({
          kind: 'purchase',
          amount: row.purchase_price,
          purchase_date: row.purchase_date,
          purchase_no: row.purchase_no,
          seller_name: row.seller_name,
          stock_no: row.stock_no,
          payment_method: row.payment_method,
          notes: row.notes,
        }, c);
      }
      loadPurchases();
    } catch (err) { toast(err.message, 'error'); }
  };
}

async function loadExpenses() {
  setTitle('Expenses', 'Expense entries & payment vouchers — shipping · customs · maintenance · rent');
  const [expData, vehData] = await Promise.all([api('/expenses'), api('/vehicles')]);
  const rows = expData.expenses || [];
  const categories = expData.categories || [];
  const vehicles = vehData.vehicles || [];
  const total = rows.reduce((sum, r) => sum + Number(r.amount || 0), 0);
  content.innerHTML = `
    <div class="page-head">
      <div><h2>Expenses & payment vouchers</h2><p>${rows.length} مصروف · إجمالي ${money(total)}</p></div>
      <div class="actions-row">
        <button class="btn primary" type="button" id="btnAddExpense">+ تسجيل مصروف</button>
      </div>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>رقم المصروف</th><th>البند</th><th>المركبة</th><th>المستفيد</th><th>القيمة</th><th>التاريخ</th><th>سند</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map((r, i) => `
            <tr>
              <td><b>${e(r.expense_no)}</b></td>
              <td>${e(r.category)}</td>
              <td>${r.stock_no ? e(r.stock_no) + ' — ' + e(r.make || '') + ' ' + e(r.model || '') : '—'}</td>
              <td>${e(r.payee || '—')}</td>
              <td class="money">${money(r.amount)}</td>
              <td>${dmy(r.expense_date)}</td>
              <td><button type="button" class="btn secondary small" data-doc-exp-voucher="${i}">سند صرف</button></td>
            </tr>`).join('') : '<tr><td colspan="7" class="empty-state">لا مصاريف مسجلة بعد</td></tr>'}
        </tbody>
      </table>
    </div>`;
  document.getElementById('btnAddExpense').onclick = () => showAddExpenseForm(categories, vehicles);
  const c = await ensureCompany();
  content.querySelectorAll('[data-doc-exp-voucher]').forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute('data-doc-exp-voucher'))];
      if (!window.NajjarPrintDocs) return toast('وحدة الطباعة غير محمّلة', 'error');
      NajjarPrintDocs.printPaymentVoucher({
        kind: 'expense',
        amount: r.amount,
        expense_date: r.expense_date,
        expense_no: r.expense_no,
        payee: r.payee,
        category: r.category,
        stock_no: r.stock_no,
        payment_method: r.payment_method,
        notes: r.notes,
      }, c);
    };
  });
}

function showAddExpenseForm(categories, vehicles) {
  openModal(`
    <h2>Record new expense</h2>
    <div class="form-grid">
      <label class="field"><span>البند *</span>
        <select id="xCategory">${categories.map(c => `<option value="${e(c)}">${e(c)}</option>`).join('')}</select>
      </label>
      <label class="field"><span>القيمة *</span><input id="xAmount" type="number" step="0.001"></label>
      <label class="field"><span>المستفيد / الجهة</span><input id="xPayee"></label>
      <label class="field"><span>طريقة الدفع</span>
        <select id="xMethod"><option>نقد</option><option>تحويل بنكي</option><option>شيك</option></select>
      </label>
      <label class="field"><span>تاريخ المصروف</span><input id="xDate" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
      <label class="field full"><span>مركبة مرتبطة (اختياري)</span>
        <select id="xVehicle">
          <option value="">— مصروف عام —</option>
          ${vehicles.map(v => `<option value="${v.id}">${e(v.stock_no)} — ${e(v.make)} ${e(v.model)}</option>`).join('')}
        </select>
      </label>
      <label class="field full"><span>ملاحظات</span><textarea id="xNotes" rows="2"></textarea></label>
    </div>
    <div class="form-actions">
      <button class="btn primary" type="button" id="btnConfirmExpense">حفظ المصروف</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
    </div>`);
  document.getElementById('btnConfirmExpense').onclick = async () => {
    const amount = Number(document.getElementById('xAmount').value) || 0;
    if (amount <= 0) return toast('قيمة المصروف مطلوبة', 'error');
    try {
      const res = await api('/expenses', {
        method: 'POST',
        body: {
          category: document.getElementById('xCategory').value,
          amount,
          payee: document.getElementById('xPayee').value.trim(),
          payment_method: document.getElementById('xMethod').value,
          expense_date: document.getElementById('xDate').value,
          vehicle_id: Number(document.getElementById('xVehicle').value) || null,
          notes: document.getElementById('xNotes').value.trim(),
        },
      });
      closeModal();
      toast('تم تسجيل المصروف — ' + (res.expense?.expense_no || ''));
      const c = await ensureCompany();
      const row = res.expense || {};
      if (window.NajjarPrintDocs && confirm('طباعة سند الصرف؟')) {
        NajjarPrintDocs.printPaymentVoucher({
          kind: 'expense',
          amount: row.amount,
          expense_date: row.expense_date,
          expense_no: row.expense_no,
          payee: row.payee,
          category: row.category,
          stock_no: row.stock_no,
          payment_method: row.payment_method,
          notes: row.notes,
        }, c);
      }
      loadExpenses();
    } catch (err) { toast(err.message, 'error'); }
  };
}

const txKindClass = { 'شراء': 'importing', 'بيع': 'available', 'مصروف': 'service', 'رأس مال': 'capital' };

function kindPill(kind) {
  return `<span class="pill ${txKindClass[kind] || 'draft'}">${e(kind)}</span>`;
}

async function loadTransactions() {
  setTitle('Daily Ledger', 'Cash book — inflows & outflows by date');
  const data = await api('/transactions');
  const rows = data.transactions || [];
  const labels = data.entry_types || {};
  // This ledger tracks cash, not profit: buying a car that is still on the lot
  // is money out but no loss. Profit is on the dashboard, on a cost-of-sales
  // basis, so the two figures are labelled apart rather than confused.
  const totals = rows.reduce((acc, r) => {
    const amount = Number(r.amount || 0);
    if (r.flow === 'in') acc.cashIn += amount;
    else acc.cashOut += amount;
    if (r.kind === 'شراء') acc.purchases += amount;
    if (r.kind === 'بيع') acc.sales += amount;
    if (r.kind === 'مصروف') acc.expenses += amount;
    return acc;
  }, { cashIn: 0, cashOut: 0, purchases: 0, sales: 0, expenses: 0 });
  const netCash = totals.cashIn - totals.cashOut;
  content.innerHTML = `
    <div class="page-head"><div><h2>Daily ledger</h2><p>${rows.length} حركة مسجلة</p></div></div>
    <div class="stats-grid">
      ${stat('نقد داخل', money(totals.cashIn), 'highlight')}
      ${stat('نقد خارج', money(totals.cashOut))}
      ${stat('صافي الحركة النقدية', money(netCash))}
      ${stat('إجمالي المبيعات', money(totals.sales))}
      ${stat('إجمالي المشتريات', money(totals.purchases))}
      ${stat('إجمالي المصاريف', money(totals.expenses))}
    </div>
    <p class="mini" style="margin:10px 2px 0">
      هذه الصفحة تتابع حركة النقد لا الربح — شراء سيارة لم تُبع بعد هو نقد خارج وليس خسارة.
      الربح محسوب على أساس تكلفة المبيعات في لوحة التحكم.
    </p>
    <div class="table-wrap" style="margin-top:14px">
      <table class="data-table">
        <thead><tr>
          <th>التاريخ</th><th>النوع</th><th>المرجع</th><th>الطرف</th><th>المركبة</th><th>الاتجاه</th><th>القيمة</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map(r => `
            <tr>
              <td>${dmy(r.tx_date)}</td>
              <td>${kindPill(r.kind)}${r.kind === 'رأس مال' && r.detail ? `<br><span class="mini">${e(labels[r.detail] || r.detail)}</span>` : ''}</td>
              <td><b>${e(r.ref_no)}</b></td>
              <td>${e(r.party || '—')}</td>
              <td>${e(r.stock_no || '—')}</td>
              <td><span class="pill ${r.flow === 'in' ? 'cash-in' : 'cash-out'}">${r.flow === 'in' ? 'داخل' : 'خارج'}</span></td>
              <td class="money">${money(r.amount)}</td>
            </tr>`).join('') : '<tr><td colspan="7" class="empty-state">لا حركات مسجلة بعد</td></tr>'}
        </tbody>
      </table>
    </div>`;
}

async function loadImports() {
  setTitle('Imports', 'Vehicle import requests');
  const data = await api('/imports');
  const rows = data.imports || [];
  content.innerHTML = `
    <div class="page-head">
      <div><h2>Import requests</h2><p>${rows.length} طلب</p></div>
      <div class="actions-row">
        <button class="btn primary" type="button" id="btnAddImport">+ طلب استيراد</button>
      </div>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>رقم الطلب</th><th>بلد المنشأ</th><th>المورد</th><th>عدد</th><th>التكلفة</th><th>الحالة</th><th>ETA</th><th>تحديث</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map(r => `
            <tr>
              <td><b>${e(r.order_no)}</b></td>
              <td>${e(r.origin_country)}</td>
              <td>${e(r.supplier || '—')}</td>
              <td>${e(r.vehicle_count)}</td>
              <td class="money">${money(r.total_cost)}</td>
              <td>${pill(r.status, r.status)}</td>
              <td>${dmy(r.eta_date)}</td>
              <td>
                <select data-import-id="${r.id}" class="import-status-select">
                  ${['قيد الشحن', 'في الميناء', 'قيد التخليص', 'مستلم', 'ملغي'].map(s =>
                    `<option value="${s}" ${r.status === s ? 'selected' : ''}>${s}</option>`).join('')}
                </select>
              </td>
            </tr>`).join('') : '<tr><td colspan="8" class="empty-state">لا طلبات استيراد — أضف طلباً جديداً</td></tr>'}
        </tbody>
      </table>
    </div>`;
  document.getElementById('btnAddImport').onclick = showAddImportForm;
  content.querySelectorAll('.import-status-select').forEach(sel => {
    sel.onchange = async () => {
      const id = sel.getAttribute('data-import-id');
      try {
        await api('/imports/' + id, { method: 'POST', body: { status: sel.value } });
        toast('تم تحديث حالة الاستيراد');
      } catch (err) {
        toast(err.message, 'error');
        loadImports();
      }
    };
  });
}

function showAddImportForm() {
  openModal(`
    <h2>New import request</h2>
    <div class="form-grid">
      <label class="field"><span>بلد المنشأ *</span><input id="iOrigin" placeholder="اليابان"></label>
      <label class="field"><span>المورد</span><input id="iSupplier"></label>
      <label class="field"><span>عدد المركبات</span><input id="iCount" type="number" min="1" value="1"></label>
      <label class="field"><span>التكلفة الإجمالية</span><input id="iCost" type="number" step="0.001"></label>
      <label class="field"><span>تاريخ الوصول المتوقع</span><input id="iEta" type="date"></label>
      <label class="field full"><span>ملاحظات</span><textarea id="iNotes" rows="2"></textarea></label>
    </div>
    <div class="form-actions">
      <button class="btn primary" type="button" id="btnSaveImport">حفظ الطلب</button>
      <button class="btn ghost" type="button" onclick="closeModal()">إلغاء</button>
    </div>`);
  document.getElementById('btnSaveImport').onclick = async () => {
    try {
      const res = await api('/imports', {
        method: 'POST',
        body: {
          origin_country: document.getElementById('iOrigin').value.trim(),
          supplier: document.getElementById('iSupplier').value.trim(),
          vehicle_count: Number(document.getElementById('iCount').value) || 1,
          total_cost: Number(document.getElementById('iCost').value) || 0,
          eta_date: document.getElementById('iEta').value,
          notes: document.getElementById('iNotes').value.trim(),
        },
      });
      closeModal();
      toast('تم إنشاء طلب الاستيراد — ' + (res.import?.order_no || ''));
      loadImports();
    } catch (err) { toast(err.message, 'error'); }
  };
}

async function boot() {
  const token = readToken();
  if (!token) { location.replace(NAJJAR_WEB + '/login.html'); return; }
  try {
    const me = await fetch('/api/me', { headers: { Authorization: 'Bearer ' + token } }).then(r => r.json());
    const user = me.user || me;
    const roleLabel = me.role_label_ar || user.role || '';
    document.getElementById('userChip').textContent = (user.name || user.username || '—') + (roleLabel ? ` · ${roleLabel}` : '');
    window.APP_USER = user;
    window.NAJJAR_SECTIONS = me.najjar_sections || [];
  } catch (_) {}
  applyNavPermissions();
  const qs = new URLSearchParams(location.search || '');
  const view = (qs.get('view') || '').trim();
  const allowed = allowedSections();
  const start = allowed.has(view) ? view : (allowed.has('dashboard') ? 'dashboard' : [...allowed][0] || 'dashboard');
  document.querySelectorAll('.nav-item').forEach(x => x.classList.toggle('active', x.dataset.section === start));
  loadSection(start);
}

boot();
