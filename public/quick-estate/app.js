/* عقارات نزوى — UI ported from My program (Starting_Quality_Program_v1_51) */
const API_BASE = '/api/quick-estate';
const content = document.getElementById('content');
const drawer = document.getElementById('drawer');
const drawerContent = document.getElementById('drawerContent');
const modal = document.getElementById('modal');
const modalContent = document.getElementById('modalContent');
const topbarSectionLogo = document.getElementById('topbarSectionLogo');
const sidebarSectionLogo = document.getElementById('sidebarSectionLogo');

let currentSection = 'dashboard';
let realEstateSubsection = sessionStorage.getItem('qeRealEstateSubsection') || 'units';
let currentUnit = null;
let unitsCache = [];
let selectedBuilding = sessionStorage.getItem('qeSelectedBuilding') || '';
let role = 'operations';

function readToken() {
  try {
    const qs = new URLSearchParams(location.search || '');
    const qTok = (qs.get('token') || '').trim();
    if (qTok) {
      localStorage.setItem('jawdah_cloud_token', qTok);
      qs.delete('token');
      history.replaceState({}, '', location.pathname + (qs.toString() ? '?' + qs.toString() : ''));
      return qTok;
    }
  } catch (_) {}
  return (localStorage.getItem('jawdah_cloud_token') || '').trim();
}

function goToPlatforms(event) {
  if (event) event.preventDefault();
  const token = readToken();
  let url = '/portal-select.html?from=nizwaestate&t=' + Date.now();
  if (token) url += '&token=' + encodeURIComponent(token);
  location.href = url;
}
document.querySelectorAll('[data-back-platforms]').forEach((link) => {
  link.addEventListener('click', goToPlatforms);
});

const e = (v) => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const money = (v) => `${Number(v || 0).toFixed(3)} ر.ع`;
const dmy = (v) => {
  if (!v) return '—';
  const p = String(v).slice(0,10).split('-');
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : e(v);
};
const actionLabel = {
  unit_updated:'تحديث بيانات وحدة', contract_created:'إنشاء عقد', contract_submitted:'إرسال عقد للاعتماد',
  contract_approved:'اعتماد عقد', contract_rejected:'رفض عقد'
};

async function api(url, options={}) {
  const token = readToken();
  if (!token) { location.replace('/app.html?v=need-login'); return; }
  const opts = {...options};
  opts.headers = {
    'Content-Type':'application/json',
    'Authorization': 'Bearer ' + token,
    ...(opts.headers||{})
  };
  if (opts.body && typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
  const res = await fetch(url.startsWith('/api/') ? url : (API_BASE + url), opts);
  const data = await res.json().catch(() => ({ok:false,error:'تعذر قراءة رد الخادم'}));
  if (res.status === 401) { location.replace('/app.html?v=need-login'); return; }
  if (!res.ok || data.ok === false) throw new Error(data.error || 'حدث خطأ');
  return data;
}

function toast(message, type='success') {
  const el = document.getElementById('toast');
  el.textContent = message; el.className = `toast ${type} show`;
  clearTimeout(el._timer); el._timer = setTimeout(()=>el.classList.remove('show'), 3100);
}
function statusClass(s) {
  return ({'مؤجرة':'occupied','شاغرة':'vacant','محجوزة':'reserved','صيانة':'maintenance',approved:'approved',pending:'pending',draft:'draft',rejected:'rejected',cancelled:'rejected'})[s] || 'draft';
}
function pill(s,label=s){ return `<span class="pill ${statusClass(s)}">${e(label)}</span>`; }
function contextualPageTitle(title) {
  if (currentSection === 'real_estate') {
    const sub = (title === 'العقارات' || title === 'عقارات نزوى') ? 'الوحدات' : title;
    return `عقارات نزوى — ${sub}`;
  }
  if (currentSection === 'dashboard') return 'لوحة التحكم';
  return title;
}
function setTitle(title, subtitle='') {
  document.getElementById('pageTitle').textContent = contextualPageTitle(title);
  document.getElementById('pageSubtitle').textContent = subtitle;
}
function openDrawer(html){ drawerContent.innerHTML=html; drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false'); }
function closeDrawer(){ drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); currentUnit=null; }
function openModal(html){ modalContent.innerHTML=html; modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); }
function closeModal(){ modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); }

document.getElementById('drawerClose').onclick=closeDrawer;
document.getElementById('modalClose').onclick=closeModal;
drawer.addEventListener('click',ev=>{ if(ev.target===drawer) closeDrawer(); });
modal.addEventListener('click',ev=>{ if(ev.target===modal) closeModal(); });
document.getElementById('refreshPage').onclick=()=>loadSection(currentSection);
document.getElementById('mobileMenu').onclick=()=>document.querySelector('.sidebar').classList.toggle('open');

function enforceSidebarTabStyle(){
  document.querySelectorAll('.sidebar .nav-item').forEach(btn=>{
    const active=btn.classList.contains('active');
    const label=btn.querySelector('.nav-label');
    const icon=btn.querySelector('.nav-icon');
    [btn,btn.querySelector('.nav-inner'),label,icon].filter(Boolean).forEach(el=>{
      el.style.setProperty('color','#ffffff','important');
      el.style.setProperty('-webkit-text-fill-color','#ffffff','important');
    });
    if(label) label.style.setProperty('font-size',active?'15.2px':'11.7px','important');
    if(icon) icon.style.setProperty('font-size',active?'14.2px':'13px','important');
  });
}

for (const btn of document.querySelectorAll('.nav-item')) {
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    enforceSidebarTabStyle();
    document.querySelector('.sidebar').classList.remove('open');
    loadSection(btn.dataset.section);
  });
}

function applySectionBrand() {
  const logo = '/quick-estate/assets/logo_real_estate_transparent.png';
  if (topbarSectionLogo) topbarSectionLogo.src = logo;
  if (sidebarSectionLogo) sidebarSectionLogo.src = logo;
  content.classList.add('brand-realestate');
  document.body.classList.add('theme-realestate');
}

async function loadSection(section) {
  currentSection=section;
  applySectionBrand();
  document.body.classList.add('section-dashboard');
  content.classList.add('dashboard-page','section-updating');
  try {
    if(section==='dashboard') return await loadDashboard();
    if(section==='real_estate') return await loadRealEstateModule(realEstateSubsection);
  } catch(err) {
    content.innerHTML=`<div class="alert error">${e(err.message)}</div>`;
  } finally {
    requestAnimationFrame(()=>content.classList.remove('section-updating'));
  }
}

async function loadRealEstateModule(subsection='units') {
  realEstateSubsection = ['units','contracts','maintenance'].includes(subsection) ? subsection : 'units';
  sessionStorage.setItem('qeRealEstateSubsection', realEstateSubsection);
  if(realEstateSubsection==='units') await loadUnits();
  else if(realEstateSubsection==='contracts') await loadContracts();
  else loadMaintenance();
  prependRealEstateTabs(realEstateSubsection);
}

function prependRealEstateTabs(active) {
  const wrap=document.createElement('div');
  wrap.className='module-tabs realestate-module-tabs';
  wrap.innerHTML=`<button class="module-tab ${active==='units'?'active':''}" data-realestate-tab="units">الوحدات</button><button class="module-tab ${active==='contracts'?'active':''}" data-realestate-tab="contracts">العقود</button><button class="module-tab ${active==='maintenance'?'active':''}" data-realestate-tab="maintenance">الصيانة</button>`;
  content.prepend(wrap);
  wrap.querySelectorAll('[data-realestate-tab]').forEach(btn=>btn.onclick=()=>loadRealEstateModule(btn.dataset.realestateTab));
}

function loadMaintenance(){
  setTitle('الصيانة','قسم الصيانة داخل العقارات');
  content.innerHTML=`<div class="card coming-soon"><div class="icon">⌁</div><h2>طلبات الصيانة</h2><p>الصيانة موجودة داخل قسم العقارات، وسيتم بناء تفاصيل الطلبات والتنبيهات اليومية ضمن هذه الصفحة.</p></div>`;
}

async function loadDashboard(){
  setTitle('لوحة التحكم','ملخص واضح لأهم ما يحدث في العقارات');
  const data=await api('/dashboard');
  const s=data.stats;
  content.innerHTML=`
    <div class="stats-grid">
      ${stat('إجمالي الوحدات',s.total_units)}${stat('المؤجرة',s.occupied,'highlight')}${stat('الشاغرة',s.vacant)}
      ${stat('المحجوزة',s.reserved)}${stat('الصيانة',s.maintenance)}${stat('عقود تنتظر الاعتماد',s.pending_contracts,'highlight')}
    </div>
    <div class="split-grid">
      <section class="card"><div class="card-header"><h3>نظرة سريعة</h3></div><div class="card-body">
        <div class="detail-list">
          <div class="detail-row"><span>نسبة الإشغال</span><strong>${s.total_units ? Math.round(s.occupied/s.total_units*100) : 0}%</strong></div>
          <div class="detail-row"><span>الوحدات المتاحة</span><strong>${s.vacant}</strong></div>
          <div class="detail-row"><span>العقود المطلوب اعتمادها</span><strong>${s.pending_contracts}</strong></div>
        </div>
      </div></section>
      <section class="card"><div class="card-header"><h3>آخر الحركات</h3></div><div class="card-body audit-list">
        ${data.recent.length?data.recent.map(a=>`<div class="contract-card"><strong>${e(actionLabel[a.action]||a.action)}</strong><div class="meta"><span>${e(a.display_name||'النظام')}</span><span>${e(new Date(a.created_at).toLocaleString('ar-OM'))}</span></div></div>`).join(''):'<div class="empty-state">لا توجد حركات بعد</div>'}
      </div></section>
    </div>`;
}
function stat(label,value,cls=''){ return `<div class="stat-card ${cls}"><span class="label">${e(label)}</span><strong>${e(value)}</strong></div>`; }

async function loadUnits(){
  setTitle('عقارات نزوى','كل بناية في صفحة مستقلة بدون سحب أفقي');
  const data=await api('/units'); unitsCache=data.units;
  const buildings=data.buildings.map(String);
  if(!selectedBuilding || !buildings.includes(String(selectedBuilding))) selectedBuilding=buildings[0]||'';
  sessionStorage.setItem('qeSelectedBuilding',selectedBuilding);
  content.innerHTML=`
    <div class="page-head"><div><h2>الوحدات السكنية</h2><p>اختر البناية، وستظهر وحداتها فقط في صفحة واحدة واضحة.</p></div></div>
    <section class="vacant-budget-search" aria-label="بحث الغرف الشاغرة حسب متوسط الإيجار">
      <div class="vacant-budget-copy"><strong>بحث الغرف الشاغرة حسب الميزانية</strong><span>يشمل جميع البنايات، ويعرض متوسط الإيجار المساوي للرقم المكتوب أو الأقل منه.</span></div>
      <label class="vacant-budget-field"><span>الحد الأعلى لمتوسط الإيجار</span><input id="maxAverageRent" type="number" min="0" step="0.001" inputmode="decimal" placeholder="مثال: 50"></label>
      <button class="btn secondary" id="clearBudgetFilter" type="button">مسح</button>
    </section>
    <div class="building-tabs" id="buildingTabs">
      ${buildings.map(b=>`<button class="building-tab ${String(b)===String(selectedBuilding)?'active':''}" data-building="${e(b)}">بناية ${e(b)}</button>`).join('')}
    </div>
    <div class="building-summary"><div><span>البناية الحالية</span><strong id="currentBuildingLabel">بناية ${e(selectedBuilding)}</strong></div><div><span id="currentBuildingCountLabel">عدد الوحدات</span><strong id="currentBuildingCount">0</strong></div></div>
    <div class="filters units-filters">
      <input id="unitSearch" placeholder="بحث بالاسم أو الهاتف أو الهوية أو رقم الشقة">
      <select id="statusFilter"><option value="">كل الحالات</option>${['شاغرة','مؤجرة','محجوزة','صيانة'].map(s=>`<option>${s}</option>`).join('')}</select>
      <button class="btn secondary" id="clearFilters">مسح البحث</button>
    </div>
    <div id="budgetSearchState" class="budget-search-state hidden"></div>
    <div class="table-wrap units-table-wrap"><table class="data-table units-table"><thead><tr>
      <th class="col-apartment">الشقة</th><th class="col-rooms">عدد الغرف</th><th class="col-status">الحالة</th><th class="col-tenant">المستأجر</th><th class="col-phone">الهاتف</th><th class="col-average">متوسط الإيجار</th><th class="col-rent">مبلغ الإيجار</th><th class="col-period">مدة العقد</th><th class="col-action">التفاصيل</th>
    </tr></thead><tbody id="unitsBody"></tbody></table></div>`;
  document.querySelectorAll('[data-building]').forEach(btn=>btn.onclick=()=>{
    selectedBuilding=btn.dataset.building;
    sessionStorage.setItem('qeSelectedBuilding',selectedBuilding);
    document.querySelectorAll('[data-building]').forEach(x=>x.classList.toggle('active',x===btn));
    document.getElementById('maxAverageRent').value='';
    document.getElementById('unitSearch').value='';
    document.getElementById('statusFilter').disabled=false;
    document.getElementById('statusFilter').value='';
    renderSelectedBuilding();
  });
  document.getElementById('unitSearch').addEventListener('input',renderSelectedBuilding);
  document.getElementById('statusFilter').addEventListener('change',renderSelectedBuilding);
  document.getElementById('maxAverageRent').addEventListener('input',renderSelectedBuilding);
  document.getElementById('clearBudgetFilter').onclick=()=>{document.getElementById('maxAverageRent').value='';document.getElementById('statusFilter').disabled=false;document.getElementById('statusFilter').value='';renderSelectedBuilding();};
  document.getElementById('clearFilters').onclick=()=>{document.getElementById('unitSearch').value='';document.getElementById('statusFilter').disabled=false;document.getElementById('statusFilter').value='';document.getElementById('maxAverageRent').value='';renderSelectedBuilding();};
  renderSelectedBuilding();
}
function renderUnitRows(rows,globalBudget=false){
  if(!rows.length) return `<tr><td colspan="9"><div class="empty-state">${globalBudget?'لا توجد غرف شاغرة ضمن هذا الحد':'لا توجد نتائج في هذه البناية'}</div></td></tr>`;
  return rows.map(u=>`<tr data-unit-id="${u.id}">
    <td class="cell-apartment"><strong>${e(u.apartment_no)}</strong>${globalBudget?`<small class="building-ref">بناية ${e(u.building_no)}</small>`:''}</td>
    <td class="cell-rooms"><strong>${e(u.rooms_count)}</strong></td><td class="cell-status">${pill(u.status)}</td>
    <td class="cell-tenant">${e(u.tenant_name||'—')}</td><td class="cell-phone"><span class="number">${e(u.phone||'—')}</span></td>
    <td class="cell-average"><span class="money">${money(u.average_rent)}</span></td>
    <td class="cell-rent"><span class="money">${money(u.rent_amount)}</span></td>
    <td class="cell-period"><span><small>من</small> ${dmy(u.contract_start)}</span><span><small>إلى</small> ${dmy(u.contract_end)}</span></td>
    <td class="cell-action"><button class="btn small ghost">فتح</button></td>
  </tr>`).join('');
}
function bindUnitRows(){ document.querySelectorAll('[data-unit-id]').forEach(r=>r.onclick=()=>openUnit(Number(r.dataset.unitId))); }
function renderSelectedBuilding(){
  const searchInput=document.getElementById('unitSearch');
  const statusFilter=document.getElementById('statusFilter');
  const budgetInput=document.getElementById('maxAverageRent');
  const state=document.getElementById('budgetSearchState');
  const q=searchInput.value.trim().toLowerCase();
  const rawMax=budgetInput.value.trim();
  const maxRent=rawMax===''?null:Number(rawMax);
  const budgetActive=maxRent!==null&&Number.isFinite(maxRent)&&maxRent>=0;
  const wasBudgetLocked=statusFilter.disabled;
  let rows=[];
  if(budgetActive){
    statusFilter.value='شاغرة';
    statusFilter.disabled=true;
    rows=unitsCache.filter(u=>u.status==='شاغرة'&&Number(u.average_rent)<=maxRent&&(!q||[u.tenant_name,u.phone,u.identity_no,u.apartment_no,u.building_no].some(v=>String(v||'').toLowerCase().includes(q))));
    rows.sort((a,b)=>Number(a.average_rent)-Number(b.average_rent)||Number(a.building_no)-Number(b.building_no)||String(a.apartment_no).localeCompare(String(b.apartment_no),'ar',{numeric:true}));
    document.querySelectorAll('[data-building]').forEach(btn=>btn.classList.remove('active'));
    document.getElementById('currentBuildingLabel').textContent='كل البنايات';
    document.getElementById('currentBuildingCountLabel').textContent='عدد النتائج';
    document.getElementById('currentBuildingCount').textContent=rows.length;
    state.textContent=`النتائج تشمل كل البنايات وكل الوحدات الشاغرة بمتوسط إيجار ${money(maxRent)} أو أقل.`;
    state.classList.remove('hidden');
  }else{
    if(wasBudgetLocked) statusFilter.value='';
    statusFilter.disabled=false;
    const s=statusFilter.value;
    const buildingRows=unitsCache.filter(u=>String(u.building_no)===String(selectedBuilding));
    rows=buildingRows.filter(u=>(!s||u.status===s)&&(!q||[u.tenant_name,u.phone,u.identity_no,u.apartment_no].some(v=>String(v||'').toLowerCase().includes(q))));
    document.querySelectorAll('[data-building]').forEach(btn=>btn.classList.toggle('active',String(btn.dataset.building)===String(selectedBuilding)));
    document.getElementById('currentBuildingLabel').textContent=`بناية ${selectedBuilding}`;
    document.getElementById('currentBuildingCountLabel').textContent='عدد الوحدات';
    document.getElementById('currentBuildingCount').textContent=buildingRows.length;
    state.classList.add('hidden');
    state.textContent='';
  }
  document.getElementById('unitsBody').innerHTML=renderUnitRows(rows,budgetActive);
  bindUnitRows();
}

async function openUnit(id){
  const data=await api(`/units/${id}`); currentUnit=data.unit;
  openDrawer(unitDrawerHtml(data.unit,data.contracts)); bindUnitDrawer(data.unit,data.contracts);
}
function unitDrawerHtml(u,contracts){
  return `<div class="drawer-title"><h2>بناية ${e(u.building_no)} — شقة ${e(u.apartment_no)}</h2><p>${pill(u.status)} ${u.location_url?`<a href="${e(u.location_url)}" target="_blank" rel="noopener">فتح الموقع</a>`:''}</p></div>
  <div class="tabs"><button class="tab active" data-tab="unit">بيانات الوحدة</button><button class="tab" data-tab="contracts">العقود (${contracts.length})</button></div>
  <section id="tab-unit">${unitForm(u)}</section><section id="tab-contracts" class="hidden">${contractsPane(u,contracts)}</section>`;
}
function unitForm(u){
  return `<form id="unitForm"><div class="form-grid">
    ${lockedField('رقم البناية',u.building_no)}${lockedField('رقم الشقة',u.apartment_no)}
    <div class="field"><label>حالة الشقة<select name="status">${['شاغرة','مؤجرة','محجوزة','صيانة'].map(s=>`<option ${u.status===s?'selected':''}>${s}</option>`).join('')}</select></label></div>
    ${lockedField('حالة الحمام',u.bathroom)}${lockedField('عدد الغرف',u.rooms_count)}
    <div class="field"><label>اسم المستأجر<input name="tenant_name" value="${e(u.tenant_name)}"></label></div>
    <div class="field"><label>رقم الهاتف<input name="phone" value="${e(u.phone)}"></label></div>
    ${lockedField('متوسط الإيجار',money(u.average_rent))}
    <div class="field"><label>مبلغ الإيجار<input name="rent_amount" type="number" step="0.001" min="0" value="${e(u.rent_amount)}"></label></div>
    <div class="field"><label>بداية العقد<input name="contract_start" type="date" value="${e(String(u.contract_start||'').slice(0,10))}"></label></div>
    <div class="field"><label>نهاية العقد<input name="contract_end" type="date" value="${e(String(u.contract_end||'').slice(0,10))}"></label></div>
    <div class="field"><label>رقم الهوية<input name="identity_no" value="${e(u.identity_no)}"></label></div>
    ${lockedField('الخدمات',u.services)}
  </div><div class="form-actions"><button class="btn primary" type="submit">حفظ التعديلات</button><button class="btn secondary" type="button" id="newContract">إنشاء عقد</button></div></form>`;
}
function lockedField(label,value){ return `<div class="field"><label>${e(label)}<input disabled value="${e(value)}"></label></div>`; }
function contractsPane(u,contracts){
  return `<div class="actions-row" style="margin-bottom:14px"><button class="btn primary" id="newContract2">إنشاء عقد جديد</button></div><div id="unitContracts">${contracts.length?contracts.map(contractCard).join(''):'<div class="empty-state"><div class="icon">▤</div>لا توجد عقود لهذه الوحدة</div>'}</div>`;
}
function canApprove(){
  return ['owner','admin','deputy','manager'].includes(String(role||'').toLowerCase());
}
function contractCard(c){
  const label=({'draft':'مسودة','pending':'بانتظار الاعتماد','approved':'معتمد','rejected':'مرفوض','cancelled':'ملغي'})[c.status]||c.status;
  const approveButtons = canApprove() ? (c.status==='pending'?`<button class="btn small success" data-contract-action="approve" data-id="${c.id}">اعتماد</button><button class="btn small danger" data-contract-action="reject" data-id="${c.id}">رفض</button>`:'') : '';
  return `<div class="contract-card"><div class="contract-card-head"><h4>${e(c.contract_no)}</h4>${pill(c.status,label)}</div>
    <div class="meta"><span>${e(c.tenant_name)}</span><span>${money(c.rent_amount)}</span><span>${dmy(c.start_date)} ← ${dmy(c.end_date)}</span></div>
    ${c.rejection_reason?`<div class="alert error">سبب الرفض: ${e(c.rejection_reason)}</div>`:''}
    <div class="contract-actions">
      ${c.status==='draft'?`<button class="btn small primary" data-contract-action="submit" data-id="${c.id}">إرسال للاعتماد</button>`:''}
      ${approveButtons}
    </div></div>`;
}
function bindUnitDrawer(u,contracts){
  document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active')); t.classList.add('active');
    document.getElementById('tab-unit').classList.toggle('hidden',t.dataset.tab!=='unit');
    document.getElementById('tab-contracts').classList.toggle('hidden',t.dataset.tab!=='contracts');
  });
  document.getElementById('unitForm').onsubmit=saveUnit;
  document.getElementById('newContract').onclick=()=>newContractModal(currentUnit);
  document.getElementById('newContract2')?.addEventListener('click',()=>newContractModal(currentUnit));
  bindContractActions();
}
async function saveUnit(ev){
  ev.preventDefault(); const fd=new FormData(ev.target); const body=Object.fromEntries(fd.entries());
  try{
    const data=await api(`/units/${currentUnit.id}`,{method:'POST',body}); currentUnit=data.unit;
    const idx=unitsCache.findIndex(x=>x.id===currentUnit.id); if(idx>=0) unitsCache[idx]=currentUnit;
    updateUnitRow(currentUnit); toast(data.message);
  }catch(err){toast(err.message,'error');}
}
function updateUnitRow(u){
  const row=document.querySelector(`tr[data-unit-id="${u.id}"]`); if(!row)return;
  row.querySelector('.cell-status').innerHTML=pill(u.status); row.querySelector('.cell-tenant').textContent=u.tenant_name||'—';
  row.querySelector('.cell-phone').innerHTML=`<span class="number">${e(u.phone||'—')}</span>`; row.querySelector('.cell-rent').innerHTML=`<span class="money">${money(u.rent_amount)}</span>`;
  row.querySelector('.cell-period').innerHTML=`<span><small>من</small> ${dmy(u.contract_start)}</span><span><small>إلى</small> ${dmy(u.contract_end)}</span>`;
}
function newContractModal(u){
  openModal(`<div class="drawer-title"><h2>إنشاء عقد جديد</h2><p>بناية ${e(u.building_no)} — شقة ${e(u.apartment_no)}</p></div>
  <form id="contractForm"><div class="form-grid">
    ${lockedField('رقم البناية',u.building_no)}${lockedField('رقم الشقة',u.apartment_no)}
    ${lockedField('حالة الحمام',u.bathroom)}${lockedField('عدد الغرف',u.rooms_count)}
    ${lockedField('متوسط الإيجار',money(u.average_rent))}
    ${lockedField('الخدمات',u.services)}
    <div class="field"><label>اسم المستأجر<input name="tenant_name" required value="${e(u.tenant_name)}"></label></div>
    <div class="field"><label>رقم الهاتف<input name="phone" value="${e(u.phone)}"></label></div>
    <div class="field"><label>رقم الهوية<input name="identity_no" value="${e(u.identity_no)}"></label></div>
    <div class="field"><label>مبلغ الإيجار<input name="rent_amount" type="number" step="0.001" min="0" required value="${e(u.rent_amount)}"></label></div>
    <div class="field"><label>بداية العقد<input name="start_date" type="date" value="${e(String(u.contract_start||'').slice(0,10))}"></label></div>
    <div class="field"><label>نهاية العقد<input name="end_date" type="date" value="${e(String(u.contract_end||'').slice(0,10))}"></label></div>
    <div class="field full"><label>ملاحظات<textarea name="notes" rows="3"></textarea></label></div>
  </div><div class="form-actions"><button class="btn primary" type="submit">حفظ كمسودة</button><button class="btn ghost" type="button" id="cancelContractModal">إلغاء</button></div></form>`);
  document.getElementById('cancelContractModal').onclick=closeModal;
  document.getElementById('contractForm').onsubmit=async ev=>{
    ev.preventDefault(); const body={unit_id:u.id,...Object.fromEntries(new FormData(ev.target).entries())};
    try{const data=await api('/contracts/create',{method:'POST',body});toast(data.message);closeModal();await openUnit(u.id);}catch(err){toast(err.message,'error');}
  };
}
function bindContractActions(){
  document.querySelectorAll('[data-contract-action]').forEach(btn=>btn.onclick=async ev=>{
    ev.stopPropagation(); const id=btn.dataset.id, action=btn.dataset.contractAction; let body={};
    if(action==='reject'){ const reason=prompt('اكتب سبب رفض العقد:'); if(!reason)return; body.reason=reason; }
    try{const data=await api(`/contracts/${id}/${action}`,{method:'POST',body});toast(data.message); if(currentUnit) await openUnit(currentUnit.id); else if(currentSection==='real_estate') await loadRealEstateModule('contracts'); else await loadContracts();}catch(err){toast(err.message,'error');}
  });
}

async function loadContracts(){
  setTitle('العقود','مسودة ← إرسال للاعتماد ← اعتماد أو رفض');
  const data=await api('/contracts');
  content.innerHTML=`<div class="page-head"><div><h2>عقود الإيجار</h2><p>لا يصبح أي عقد فعالًا إلا بعد موافقة الإدارة.</p></div></div>
    <div class="filters" style="grid-template-columns:1fr auto"><select id="contractStatus"><option value="">كل الحالات</option>${Object.entries(data.labels).map(([k,v])=>`<option value="${k}">${e(v)}</option>`).join('')}</select><button class="btn secondary" id="contractClear">مسح الفلتر</button></div>
    <div id="contractsGrid">${renderContracts(data.contracts)}</div>`;
  document.getElementById('contractStatus').onchange=async ev=>{const d=await api(`/contracts?status=${encodeURIComponent(ev.target.value)}`);document.getElementById('contractsGrid').innerHTML=renderContracts(d.contracts);bindContractActions();};
  document.getElementById('contractClear').onclick=()=>{document.getElementById('contractStatus').value='';document.getElementById('contractStatus').dispatchEvent(new Event('change'));};
  bindContractActions();
}
function renderContracts(rows){
  if(!rows.length)return '<div class="card empty-state"><div class="icon">▤</div>لا توجد عقود بهذه الحالة</div>';
  return `<div class="card"><div class="card-body">${rows.map(c=>`<div class="contract-card"><div class="contract-card-head"><h4>${e(c.contract_no)} — بناية ${e(c.building_no)} / شقة ${e(c.apartment_no)}</h4>${pill(c.status,({'draft':'مسودة','pending':'بانتظار الاعتماد','approved':'معتمد','rejected':'مرفوض','cancelled':'ملغي'})[c.status])}</div><div class="meta"><span>${e(c.tenant_name)}</span><span>${money(c.rent_amount)}</span></div><div class="contract-actions">${c.status==='draft'?`<button class="btn small primary" data-contract-action="submit" data-id="${c.id}">إرسال للاعتماد</button>`:''}${canApprove()&&c.status==='pending'?`<button class="btn small success" data-contract-action="approve" data-id="${c.id}">اعتماد</button><button class="btn small danger" data-contract-action="reject" data-id="${c.id}">رفض</button>`:''}</div></div>`).join('')}</div></div>`;
}

async function boot() {
  const token = readToken();
  if (!token) {
    location.replace('/app.html?v=need-login');
    return;
  }
  try {
    const me = await api('/me');
    window.APP_USER = me.user || {};
    role = String(window.APP_USER.role || 'operations');
    const chip = document.getElementById('userChip');
    if (chip) chip.textContent = window.APP_USER.display_name || window.APP_USER.username || 'مستخدم';
  } catch (_) {
    location.replace('/app.html?v=need-login');
    return;
  }
  const firstNav=document.querySelector('.nav-item');
  if(firstNav){firstNav.classList.add('active');enforceSidebarTabStyle();loadSection(firstNav.dataset.section);}
}
boot();
