/* عقود · فواتير · سندات — تصميم قريب من موقع النجار والسموم */
(function (global) {
  const LOGO = '/auto-trading/assets/logo-official-clear.png?v=at13';

  function esc(v) {
    return String(v ?? '').replace(/[&<>'"]/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[c]));
  }

  // The rial divides into 1000 baisa, so three places are shown even when round.
  function money(v) {
    const n = Number(v || 0).toLocaleString('en-US', {
      minimumFractionDigits: 3,
      maximumFractionDigits: 3,
    });
    return `<span dir="ltr">${n}</span> ر.ع`;
  }

  const AR_ONES = [
    '', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة', 'ستة', 'سبعة', 'ثمانية', 'تسعة',
    'عشرة', 'أحد عشر', 'اثنا عشر', 'ثلاثة عشر', 'أربعة عشر', 'خمسة عشر',
    'ستة عشر', 'سبعة عشر', 'ثمانية عشر', 'تسعة عشر',
  ];
  const AR_TENS = ['', '', 'عشرون', 'ثلاثون', 'أربعون', 'خمسون', 'ستون', 'سبعون', 'ثمانون', 'تسعون'];
  const AR_HUNDREDS = [
    '', 'مئة', 'مئتان', 'ثلاثمئة', 'أربعمئة', 'خمسمئة', 'ستمئة', 'سبعمئة', 'ثمانمئة', 'تسعمئة',
  ];
  // singular, dual, 3–10, and 11 upwards
  const AR_SCALES = [
    [1e9, ['مليار', 'ملياران', 'مليارات', 'مليار']],
    [1e6, ['مليون', 'مليونان', 'ملايين', 'مليون']],
    [1e3, ['ألف', 'ألفان', 'آلاف', 'ألف']],
  ];

  function arUnder1000(n) {
    const out = [];
    const h = Math.floor(n / 100);
    const rest = n % 100;
    if (h) out.push(AR_HUNDREDS[h]);
    if (rest < 20) {
      if (rest) out.push(AR_ONES[rest]);
    } else {
      const ones = rest % 10;
      const tens = AR_TENS[Math.floor(rest / 10)];
      out.push(ones ? `${AR_ONES[ones]} و${tens}` : tens);
    }
    return out.join(' و');
  }

  function arScaleWord(count, forms) {
    if (count === 1) return forms[0];
    if (count === 2) return forms[1];
    if (count <= 10) return forms[2];
    return forms[3];
  }

  function arInteger(n) {
    let rest = Math.floor(Math.abs(Number(n) || 0));
    if (!rest) return 'صفر';
    const out = [];
    AR_SCALES.forEach(([base, forms]) => {
      const count = Math.floor(rest / base);
      if (!count) return;
      const word = arScaleWord(count, forms);
      out.push(count <= 2 ? word : `${arUnder1000(count)} ${word}`);
      rest -= count * base;
    });
    if (rest) out.push(arUnder1000(rest));
    return out.join(' و');
  }

  /* The counted noun follows the last two digits: plural after 3–10, singular
     accusative after 11–99, and singular genitive after a round hundred or
     thousand — "ألف ريال عماني", not "ألف ريالاً". */
  function countedNoun(n, genitive, accusative, plural) {
    const tail = n % 100;
    if (tail === 0) return genitive;
    if (tail >= 3 && tail <= 10) return plural;
    return accusative;
  }

  /** Omani vouchers and contracts state the sum in words as well as figures. */
  function moneyWords(v) {
    const baisaTotal = Math.round((Number(v) || 0) * 1000);
    const rial = Math.floor(baisaTotal / 1000);
    const baisa = baisaTotal % 1000;
    const out = [];
    if (rial === 1) out.push('ريال عماني واحد');
    else if (rial === 2) out.push('ريالان عمانيان');
    else if (rial) {
      out.push(`${arInteger(rial)} ${countedNoun(rial, 'ريال عماني', 'ريالاً عمانياً', 'ريالات عمانية')}`);
    }
    if (baisa === 1) out.push('بيسة واحدة');
    else if (baisa === 2) out.push('بيستان');
    else if (baisa) out.push(`${arInteger(baisa)} ${countedNoun(baisa, 'بيسة', 'بيسة', 'بيسات')}`);
    if (!out.length) return 'فقط صفر ريال عماني لا غير';
    return `فقط ${out.join(' و')} لا غير`;
  }

  /** Amount in figures with the written sum underneath, as a voucher reads. */
  function amountRow(label, v) {
    return `<tr><th>${esc(label)}</th><td><b>${money(v)}</b>
      <div style="font-size:11.5px;color:var(--muted);margin-top:3px">${esc(moneyWords(v))}</div></td></tr>`;
  }

  function dmy(v) {
    if (!v) return '—';
    const p = String(v).slice(0, 10).split('-');
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : esc(v);
  }

  function docStyles() {
    return `
      @page { size: A4; margin: 12mm; }
      :root{
        --gold:#caa14a; --gold2:#f0d98a; --ink:#1a1408; --muted:#6b5a3a;
        --line:rgba(202,161,74,.55); --soft:#fffaf0; --bg:#fff;
      }
      *{box-sizing:border-box}
      body{
        margin:0; padding:0;
        font-family:Arial,Helvetica,"Segoe UI",sans-serif;
        font-size:12px; font-weight:700;
        color:var(--ink); background:#efe6d2;
        -webkit-print-color-adjust:exact; print-color-adjust:exact;
      }
      .sheet{
        width:210mm; min-height:297mm; margin:12px auto; padding:18mm 16mm;
        background:
          radial-gradient(circle at 12% 0%, rgba(240,217,138,.22), transparent 34%),
          linear-gradient(180deg,#fffef9 0%, #fff 48%, #fffaf0 100%);
        border:1px solid var(--line);
        box-shadow:0 18px 40px rgba(0,0,0,.18);
        position:relative;
      }
      .sheet:before{
        content:""; position:absolute; inset:8px; border:1px solid rgba(202,161,74,.28);
        pointer-events:none;
      }
      .brand{
        display:grid; grid-template-columns:110px 1fr 110px; gap:10px;
        align-items:center; border-bottom:3px solid var(--gold); padding-bottom:12px; margin-bottom:14px;
      }
      .brand img{width:96px; height:auto; object-fit:contain}
      .brand-center{text-align:center}
      .brand-center h1{
        margin:0; font-size:14px; letter-spacing:.04em; color:#111;
        font-family:Arial,Helvetica,sans-serif; font-weight:700;
      }
      .brand-center h2{margin:4px 0 0; font-size:14px; color:var(--gold); font-weight:700}
      .brand-center p{margin:4px 0 0; font-size:12px; color:var(--muted); font-weight:700}
      .badge{
        display:inline-block; margin-top:8px; padding:4px 12px; border-radius:999px;
        background:linear-gradient(135deg,#1a1408,#3a2a10); color:var(--gold2);
        font-size:12px; font-weight:800; border:1px solid var(--gold);
      }
      .meta-row{
        display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;
        margin:10px 0 14px; font-size:12px; color:var(--muted);
      }
      .meta-row strong{color:var(--ink)}
      h3.sec{
        margin:16px 0 8px; font-size:14px; color:#111; font-weight:700;
        border-right:4px solid var(--gold); padding-right:8px;
      }
      table{width:100%; border-collapse:collapse; margin:8px 0 12px}
      th,td{border:1px solid var(--line); padding:8px 10px; text-align:right; font-size:12px; vertical-align:top; font-weight:700}
      th{width:32%; background:linear-gradient(180deg,#fff6df,#f7ecd0); color:#3a2a10; font-weight:800}
      /* An itemised table heads its columns, so the label-column width does not apply. */
      table.items th{width:auto}
      table.items th:first-child{width:46%}
      table.items td:not(:first-child){white-space:nowrap}
      .box{
        border:1px solid var(--line); border-radius:12px; padding:12px 14px;
        background:var(--soft); margin:10px 0; font-size:12.5px; line-height:1.7;
      }
      .clauses{font-size:12.5px; line-height:1.85; margin:8px 0 0; padding-right:18px}
      .clauses li{margin:4px 0}
      .sign-grid{
        display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:28px;
      }
      .sign{
        border:1px dashed var(--line); border-radius:12px; padding:14px; min-height:120px;
        background:rgba(255,255,255,.7);
      }
      .sign b{display:block; margin-bottom:8px; color:#111}
      .sign .line{margin-top:42px; border-top:1px solid #cbb98a; padding-top:6px; font-size:11px; color:var(--muted)}
      .totals{
        margin-top:10px; border:2px solid var(--gold); border-radius:12px; overflow:hidden;
      }
      .totals table{margin:0}
      .totals th,.totals td{border:none; border-bottom:1px solid var(--line)}
      .totals tr:last-child th,.totals tr:last-child td{border-bottom:none; background:#1a1408; color:var(--gold2); font-size:14px}
      .foot{
        margin-top:22px; padding-top:10px; border-top:1px solid var(--line);
        text-align:center; font-size:11px; color:var(--muted);
      }
      .watermark{
        position:absolute; inset:0; display:grid; place-items:center; pointer-events:none; opacity:.045;
      }
      .watermark img{width:62%; max-width:420px}
      @media print{
        body{background:#fff}
        .sheet{margin:0; box-shadow:none; border:none; width:auto; min-height:auto}
        .no-print{display:none !important}
      }
    `;
  }

  function brandHeader(c, docTitleAr, docTitleEn, docNo, docDate) {
    const company = c || {};
    const reg = [
      company.cr_no ? `س.ت: <strong dir="ltr">${esc(company.cr_no)}</strong>` : '',
      company.vat_no ? `الرقم الضريبي: <strong dir="ltr">${esc(company.vat_no)}</strong>` : '',
    ].filter(Boolean).join(' · ');
    return `
      <div class="watermark"><img src="${LOGO}" alt=""></div>
      <div class="brand">
        <img src="${LOGO}" alt="NAJJAR & AL SAMOOM">
        <div class="brand-center">
          <h1>NAJJAR &amp; AL SAMOOM TRADING</h1>
          <h2>USED &amp; IMPORTED CARS</h2>
          <p>USED &amp; IMPORTED CARS · ${esc(company.address_ar || 'نزوى — الفلج')} · سلطنة عُمان</p>
          <div class="badge">${esc(docTitleAr)}${docTitleEn ? ' · ' + esc(docTitleEn) : ''}</div>
        </div>
        <div style="text-align:left;font-size:11px;color:var(--muted);line-height:1.6">
          <div dir="ltr">+968 71924089</div>
          <div dir="ltr">+968 93391994</div>
          <div dir="ltr">+968 77548482</div>
        </div>
      </div>
      <div class="meta-row">
        <span>رقم المستند: <strong dir="ltr">${esc(docNo || '—')}</strong></span>
        <span>التاريخ: <strong>${esc(docDate || '—')}</strong></span>
        <span>المكان: <strong>نزوى — سلطنة عُمان</strong></span>
      </div>
      ${reg ? `<div class="meta-row" style="margin-top:-6px">${reg}</div>` : ''}
    `;
  }

  function bankBox(c) {
    const bank = (c || {}).bank || {};
    // Arabic labels keep the line right-to-left; a Latin label such as "IBAN"
    // would be reordered to the far side of its own number.
    return `
      <div class="box">
        <b>بيانات التحويل البنكي · ${esc(bank.name_ar || 'بنك صحار الدولي')}</b><br>
        اسم الحساب: <span dir="ltr">${esc(bank.account_name_en || 'Al Najjar Trading')}</span><br>
        رقم الحساب الدولي: <span dir="ltr">${esc(bank.iban || '')}</span><br>
        رمز السويفت: <span dir="ltr">${esc(bank.swift || '')}</span>
      </div>`;
  }

  function vehicleTable(v) {
    return `
      <h3 class="sec">بيانات المركبة</h3>
      <table>
        <tr><th>الماركة / الطراز</th><td>${esc(v.make || '')} ${esc(v.model || '')} ${esc(v.variant || '')}</td></tr>
        <tr><th>السنة / اللون / النوع</th><td>${esc(v.year || '—')} · ${esc(v.color || '—')} · ${esc(v.vehicle_type || '—')}</td></tr>
        <tr><th>رقم المخزون</th><td dir="ltr">${esc(v.stock_no || '—')}</td></tr>
        <tr><th>رقم الهيكل (VIN)</th><td dir="ltr">${esc(v.vin || '—')}</td></tr>
        <tr><th>رقم المحرك</th><td dir="ltr">${esc(v.engine_no || '—')}${v.engine_cc ? ' · ' + esc(v.engine_cc) + ' cc' : ''}</td></tr>
        <tr><th>رقم اللوحة</th><td>${esc(v.plate_no || '—')}</td></tr>
        <tr><th>بلد المنشأ / مرجع الاستيراد</th><td>${esc(v.origin_country || '—')} · ${esc(v.import_ref || '—')}</td></tr>
      </table>`;
  }

  function signBlock(leftTitle, rightTitle) {
    return `
      <div class="sign-grid">
        <div class="sign"><b>${esc(leftTitle)}</b><div class="line">التوقيع / الختم</div></div>
        <div class="sign"><b>${esc(rightTitle)}</b><div class="line">التوقيع</div></div>
      </div>`;
  }

  /* Fire the print dialog only once the logo and the web font have landed —
     printing early yields an unbranded sheet in a fallback typeface. A timeout
     keeps a blocked font CDN from holding the document hostage. */
  function printWhenReady(w) {
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      try { w.print(); } catch (_) {}
    };
    try {
      const waits = [w.document.fonts ? w.document.fonts.ready : Promise.resolve()];
      w.document.querySelectorAll('img').forEach((img) => {
        if (img.complete) return;
        waits.push(new Promise((resolve) => { img.onload = img.onerror = resolve; }));
      });
      Promise.all(waits).then(() => setTimeout(go, 150));
    } catch (_) { /* fall through to the deadline below */ }
    setTimeout(go, 4000);
  }

  function openDoc(title, innerHtml, company) {
    const c = company || {};
    const w = window.open('', '_blank');
    if (!w) {
      if (typeof toast === 'function') toast('فعّل النوافذ المنبثقة للطباعة', 'error');
      return;
    }
    const footReg = [
      c.cr_no ? `C.R. ${esc(c.cr_no)}` : '',
      c.vat_no ? `VAT ${esc(c.vat_no)}` : '',
    ].filter(Boolean).join(' · ');
    w.document.write(`<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
      <title>${esc(title)}</title>
      <style>${docStyles()}</style></head>
      <body><div class="sheet">${innerHtml}
        <div class="foot">NAJJAR &amp; AL SAMOOM TRADING${footReg ? ' · ' + footReg : ''} · Nizwa Falaj · Sultanate of Oman<br>
        هذا المستند صادر إلكترونياً من نظام الشركة · للطباعة الرسمية ضع الختم والتوقيع</div>
      </div>
      <div class="no-print" style="text-align:center;margin:12px">
        <button onclick="window.print()" style="padding:10px 18px;border-radius:10px;border:1px solid #caa14a;background:#1a1408;color:#f0d98a;font-weight:800;cursor:pointer">طباعة / PDF</button>
      </div>
      </body></html>`);
    w.document.close();
    w.focus();
    printWhenReady(w);
  }

  /** عقد بيع مركبة — سلطنة عُمان */
  function printSaleContract(sale, vehicle, company) {
    const v = Object.assign({}, vehicle || {}, sale || {});
    const c = company || {};
    const price = Number(sale.sale_price || 0);
    const deposit = Number(sale.deposit_amount || 0);
    const remaining = Math.max(0, price - deposit);
    const body = `
      ${brandHeader(c, 'عقد بيع مركبة', 'Vehicle Sale Contract', sale.sale_no, dmy(sale.sale_date))}
      <div class="box">
        تم الاتفاق في سلطنة عُمان — ولاية نزوى، بين كل من:<br>
        <b>الطرف الأول (البائع):</b> النجار والسموم للتجارة — NAJJAR &amp; AL SAMOOM TRADING، مقرها ${esc(c.address_ar || 'نزوى — الفلج')}.<br>
        <b>الطرف الثاني (المشتري):</b> ${esc(sale.buyer_name || '—')}
        ${sale.buyer_id ? ' · رقم الهوية/البطاقة: <span dir="ltr">' + esc(sale.buyer_id) + '</span>' : ''}
        ${sale.buyer_phone ? ' · هاتف: <span dir="ltr">' + esc(sale.buyer_phone) + '</span>' : ''}.
      </div>
      ${vehicleTable(v)}
      <h3 class="sec">الثمن وطريقة السداد</h3>
      <div class="totals"><table>
        ${amountRow('سعر البيع المتفق عليه', price)}
        <tr><th>المبلغ المدفوع / العربون</th><td>${money(deposit)}</td></tr>
        <tr><th>المتبقي</th><td>${money(remaining)}</td></tr>
        <tr><th>طريقة الدفع</th><td>${esc(sale.payment_method || '—')}</td></tr>
      </table></div>
      ${bankBox(c)}
      <h3 class="sec">الشروط والأحكام (عُمان)</h3>
      <ol class="clauses">
        <li>يقر الطرف الأول بملكية المركبة وحقه في بيعها، ويسلّمها للطرف الثاني بالحالة المعاينة وقت البيع.</li>
        <li>يتحمّل الطرف الثاني رسوم نقل الملكية لدى شرطة عُمان السلطانية / المرور وأي رسوم حكومية لاحقة.</li>
        <li>بعد استلام كامل الثمن، تنتقل حيازة المركبة للمشتري، ولا يحق لأي طرف الرجوع إلا وفق اتفاق مكتوب أو حكم مختص.</li>
        <li>أي عيب ظاهر تمت معاينته من المشتري قبل الشراء يُعدّ مقبولاً، ما لم يُذكر خلافه في الملاحظات.</li>
        <li>يخضع هذا العقد لأنظمة سلطنة عُمان، ويكون الاختصاص لمحاكم نزوى عند النزاع.</li>
        ${sale.notes ? '<li>ملاحظات خاصة: ' + esc(sale.notes) + '</li>' : ''}
      </ol>
      ${signBlock('الطرف الأول — الشركة / الختم', 'الطرف الثاني — المشتري')}`;
    openDoc('عقد بيع — ' + (sale.sale_no || ''), body, c);
  }

  /** عقد شراء مركبة — الشركة تشتري من بائع */
  function printPurchaseContract(purchase, vehicle, company) {
    const v = Object.assign({}, vehicle || {}, purchase || {});
    const c = company || {};
    const price = Number(purchase.purchase_price || 0);
    const paid = Number(purchase.paid_amount != null ? purchase.paid_amount : price);
    const body = `
      ${brandHeader(c, 'عقد شراء مركبة', 'Vehicle Purchase Contract', purchase.purchase_no, dmy(purchase.purchase_date))}
      <div class="box">
        تم الاتفاق في سلطنة عُمان — ولاية نزوى، بين كل من:<br>
        <b>الطرف الأول (البائع / المالك السابق):</b> ${esc(purchase.seller_name || '—')}
        ${purchase.seller_id ? ' · الهوية/السجل: <span dir="ltr">' + esc(purchase.seller_id) + '</span>' : ''}
        ${purchase.seller_phone ? ' · هاتف: <span dir="ltr">' + esc(purchase.seller_phone) + '</span>' : ''}.<br>
        <b>الطرف الثاني (المشتري):</b> النجار والسموم للتجارة — NAJJAR &amp; AL SAMOOM TRADING.
      </div>
      ${vehicleTable(v)}
      <h3 class="sec">قيمة الشراء</h3>
      <div class="totals"><table>
        ${amountRow('سعر الشراء', price)}
        <tr><th>المبلغ المدفوع</th><td>${money(paid)}</td></tr>
        <tr><th>طريقة الدفع</th><td>${esc(purchase.payment_method || '—')}</td></tr>
        <tr><th>مصدر/بلد</th><td>${esc(purchase.source_country || v.origin_country || '—')}</td></tr>
      </table></div>
      <h3 class="sec">التعهدات</h3>
      <ol class="clauses">
        <li>يقر الطرف الأول أنه المالك الشرعي للمركبة وأنها غير مرهونة أو متنازع عليها، ما لم يُفصح عن خلاف ذلك كتابةً.</li>
        <li>يلتزم الطرف الأول بتسليم المركبة ومستنداتها المتاحة، والتعاون في إجراءات نقل الملكية.</li>
        <li>يدفع الطرف الثاني الثمن المتفق عليه وفق طريقة السداد الموضحة أعلاه.</li>
        <li>يخضع العقد لقوانين سلطنة عُمان واختصاص محاكم نزوى.</li>
        ${purchase.notes ? '<li>ملاحظات: ' + esc(purchase.notes) + '</li>' : ''}
      </ol>
      ${signBlock('الطرف الأول — البائع', 'الطرف الثاني — الشركة / الختم')}`;
    openDoc('عقد شراء — ' + (purchase.purchase_no || ''), body, c);
  }

  /** فاتورة بيع */
  function printSaleInvoice(sale, vehicle, company) {
    const v = Object.assign({}, vehicle || {}, sale || {});
    const c = company || {};
    const price = Number(sale.sale_price || 0);
    const deposit = Number(sale.deposit_amount || 0);
    const invNo = 'INV-' + String(sale.sale_no || '').replace(/^AT-S-/, '');
    // Only a VAT-registered seller may issue a tax invoice, and the agreed
    // retail price is treated as VAT-inclusive when one is due.
    const vatRate = c.vat_no ? Number(c.vat_rate || 0) : 0;
    const net = vatRate > 0 ? price / (1 + vatRate / 100) : price;
    const vat = price - net;
    const body = `
      ${brandHeader(
        c,
        vatRate > 0 ? 'فاتورة ضريبية' : 'فاتورة بيع',
        vatRate > 0 ? 'Tax Invoice' : 'Sales Invoice',
        invNo,
        dmy(sale.sale_date)
      )}
      <table>
        <tr><th>العميل / المشتري</th><td>${esc(sale.buyer_name || '—')}</td></tr>
        <tr><th>الهاتف</th><td dir="ltr">${esc(sale.buyer_phone || '—')}</td></tr>
        <tr><th>رقم الهوية</th><td dir="ltr">${esc(sale.buyer_id || '—')}</td></tr>
        <tr><th>مرجع البيع</th><td dir="ltr">${esc(sale.sale_no || '—')}</td></tr>
      </table>
      <h3 class="sec">تفاصيل الفاتورة</h3>
      <table class="items">
        <tr><th>البيان</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr>
        <tr>
          <td>${esc(v.make || '')} ${esc(v.model || '')} ${esc(v.variant || '')}<br>
            <span style="color:var(--muted);font-size:11px">رقم الهيكل: <span dir="ltr">${esc(v.vin || '—')}</span> · مخزون ${esc(v.stock_no || '—')}</span>
          </td>
          <td>1</td>
          <td>${money(net)}</td>
          <td><b>${money(net)}</b></td>
        </tr>
      </table>
      <div class="totals"><table>
        <tr><th>${vatRate > 0 ? 'الإجمالي قبل الضريبة' : 'الإجمالي'}</th><td>${money(net)}</td></tr>
        ${vatRate > 0 ? `<tr><th>ضريبة القيمة المضافة ${vatRate}%</th><td>${money(vat)}</td></tr>` : ''}
        <tr><th>المدفوع / العربون</th><td>${money(deposit)}</td></tr>
        ${amountRow('الإجمالي المستحق', price)}
      </table></div>
      <div class="box">المتبقي بعد الدفعات: <b>${money(Math.max(0, price - deposit))}</b></div>
      ${bankBox(c)}
      ${signBlock('المحاسب / البائع', 'العميل')}`;
    openDoc((vatRate > 0 ? 'فاتورة ضريبية — ' : 'فاتورة بيع — ') + invNo, body, c);
  }

  /** فاتورة شراء (داخلية) */
  function printPurchaseInvoice(purchase, vehicle, company) {
    const v = Object.assign({}, vehicle || {}, purchase || {});
    const c = company || {};
    const price = Number(purchase.purchase_price || 0);
    const invNo = 'PINV-' + String(purchase.purchase_no || '').replace(/^AT-P-/, '');
    const body = `
      ${brandHeader(c, 'فاتورة شراء', 'Purchase Invoice', invNo, dmy(purchase.purchase_date))}
      <table>
        <tr><th>المورد / البائع</th><td>${esc(purchase.seller_name || '—')}</td></tr>
        <tr><th>الهاتف</th><td dir="ltr">${esc(purchase.seller_phone || '—')}</td></tr>
        <tr><th>الهوية / السجل</th><td dir="ltr">${esc(purchase.seller_id || '—')}</td></tr>
        <tr><th>مرجع الشراء</th><td dir="ltr">${esc(purchase.purchase_no || '—')}</td></tr>
      </table>
      <table class="items">
        <tr><th>البيان</th><th>السعر</th></tr>
        <tr>
          <td>${esc(v.make || '')} ${esc(v.model || '')} · ${esc(v.stock_no || '—')}<br>
            <span style="font-size:11px;color:var(--muted)">رقم الهيكل: <span dir="ltr">${esc(v.vin || '—')}</span></span>
          </td>
          <td><b>${money(price)}</b></td>
        </tr>
      </table>
      <div class="totals"><table>
        <tr><th>طريقة الدفع</th><td>${esc(purchase.payment_method || '—')}</td></tr>
        ${amountRow('إجمالي فاتورة الشراء', price)}
      </table></div>
      ${signBlock('المستلم / المشتريات', 'اعتماد الإدارة')}`;
    openDoc('فاتورة شراء — ' + invNo, body, c);
  }

  /** سند قبض — استلام مبلغ من عميل */
  function printReceiptVoucher(sale, company) {
    const c = company || {};
    const amount = Number(sale.deposit_amount || sale.sale_price || 0);
    const no = 'RV-' + String(sale.sale_no || '').replace(/^AT-S-/, '');
    const body = `
      ${brandHeader(c, 'سند قبض', 'Receipt Voucher', no, dmy(sale.sale_date))}
      <div class="box">استلمنا من المكرم/ة: <b>${esc(sale.buyer_name || '—')}</b>
        ${sale.buyer_phone ? ' · <span dir="ltr">' + esc(sale.buyer_phone) + '</span>' : ''}</div>
      <div class="totals"><table>
        ${amountRow('مبلغ وقدره', amount)}
        <tr><th>وذلك عن</th><td>عربون/دفعة بيع مركبة ${esc(sale.stock_no || '')} · مرجع ${esc(sale.sale_no || '')}</td></tr>
        <tr><th>طريقة القبض</th><td>${esc(sale.payment_method || '—')}</td></tr>
      </table></div>
      ${bankBox(c)}
      ${signBlock('المحاسب المستلم', 'الدافع / العميل')}`;
    openDoc('سند قبض — ' + no, body, c);
  }

  /** سند صرف — صرف مبلغ (شراء أو مصروف) */
  function printPaymentVoucher(payload, company) {
    const c = company || {};
    const kind = payload.kind || 'purchase'; // purchase | expense
    const amount = Number(payload.amount || 0);
    const date = payload.date || payload.purchase_date || payload.expense_date;
    const ref = payload.ref_no || payload.purchase_no || payload.expense_no || '';
    const payee = payload.payee || payload.seller_name || '—';
    const reason = payload.reason
      || (kind === 'expense'
        ? `مصروف: ${payload.category || ''} ${payload.stock_no ? '· مركبة ' + payload.stock_no : ''}`
        : `شراء مركبة ${payload.stock_no || ''} · مرجع ${ref}`);
    const no = (kind === 'expense' ? 'PV-E-' : 'PV-P-') + String(ref).replace(/^AT-[PE]-/, '');
    const body = `
      ${brandHeader(c, 'سند صرف', 'Payment Voucher', no, dmy(date))}
      <div class="box">يُصرف للمكرم/ة: <b>${esc(payee)}</b></div>
      <div class="totals"><table>
        ${amountRow('مبلغ وقدره', amount)}
        <tr><th>وذلك عن</th><td>${esc(reason)}</td></tr>
        <tr><th>طريقة الصرف</th><td>${esc(payload.payment_method || '—')}</td></tr>
        <tr><th>المرجع</th><td dir="ltr">${esc(ref || '—')}</td></tr>
      </table></div>
      ${payload.notes ? '<div class="box">ملاحظات: ' + esc(payload.notes) + '</div>' : ''}
      ${signBlock('أمر الصرف / الإدارة', 'المستلم')}`;
    openDoc('سند صرف — ' + no, body, c);
  }

  global.NajjarPrintDocs = {
    moneyWords,
    printSaleContract,
    printPurchaseContract,
    printSaleInvoice,
    printPurchaseInvoice,
    printReceiptVoucher,
    printPaymentVoucher,
  };
})(window);
