/* NAJJAR & AL SAMOOM TRADING — Car showroom: photos · prices · specs */
(function (global) {
  const esc = (v) => String(v ?? '').replace(/[&<>'"]/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[c]));

  // Approximate pegged rates for display (1 OMR)
  const FX = { USD: 2.6, SAR: 9.76, AED: 9.55 };
  const LOGO_MARK = '/auto-trading/assets/logo-mark.png?v=at27';

  function accentOf(v) {
    const make = String(v.make || '');
    const model = String(v.model || '');
    const variant = String(v.variant || '');
    if (make.includes('Land')) return 'lr';
    if (model.includes('GLE')) return 'gle';
    if (model.includes('G-Class') || variant.includes('G63')) return 'g63';
    if (make.includes('BMW')) return 'bmw';
    return 'def';
  }

  function fmtNum(n, digits) {
    return Number(n || 0).toLocaleString('en-US', {
      maximumFractionDigits: digits != null ? digits : 0,
      minimumFractionDigits: 0,
    });
  }

  function money(v) {
    return Number(v || 0) > 0 ? `${fmtNum(v, 3)} ر.ع` : 'حسب الاتفاق';
  }

  function priceOMR(v) {
    const omr = Number(v.list_price || 0);
    if (omr > 0) return omr;
    const usd = Number(v.price_usd || 0);
    return usd > 0 ? usd / FX.USD : 0;
  }

  function priceBlock(v, opts = {}) {
    const omr = v.price_on_request ? 0 : priceOMR(v);
    if (!(omr > 0)) {
      const label = v.status === 'قيد الاستيراد' ? 'السعر عند الوصول' : 'حسب الاتفاق';
      return `<div class="nt-price-block"><strong class="nt-show-price">${label}</strong></div>`;
    }
    const usd = Number(v.price_usd || 0) > 0 ? Number(v.price_usd) : omr * FX.USD;
    const sar = omr * FX.SAR;
    const aed = omr * FX.AED;
    // Each amount keeps its own left-to-right run, otherwise the Arabic page
    // reorders the row and a figure ends up read against another currency.
    const pairs = [['USD', usd], ['SAR', sar], ['AED', aed]];
    const compact = opts.compact
      ? `<span class="nt-price-fx">${pairs
          .map(([code, value]) => `<b dir="ltr">${fmtNum(value)} ${code}</b>`)
          .join('<i aria-hidden="true">·</i>')}</span>`
      : `<ul class="nt-price-fx-list">
          ${pairs.map(([code, value]) => `
          <li><span>${code}</span><b dir="ltr">${fmtNum(value)}</b></li>`).join('')}
        </ul>`;
    return `
      <div class="nt-price-block">
        <strong class="nt-show-price">${fmtNum(omr, 3)} ر.ع</strong>
        ${compact}
      </div>`;
  }

  function statusClass(s) {
    if (s === 'متاحة') return 'available';
    if (s === 'قيد الاستيراد') return 'importing';
    if (s === 'محجوزة') return 'reserved';
    if (s === 'مباعة') return 'sold';
    return 'draft';
  }

  function photosOf(v) {
    let photos = v.photos || v.images || [];
    if (typeof photos === 'string') {
      try { photos = JSON.parse(photos); } catch (_) { photos = photos ? [photos] : []; }
    }
    if (!Array.isArray(photos)) photos = [];
    if (!photos.length && v.photo_url) photos = [v.photo_url];
    return photos.filter(Boolean);
  }

  function particlesHtml(n) {
    let out = '';
    for (let i = 0; i < n; i += 1) {
      const x = (8 + (i * 17) % 84);
      const y = (12 + (i * 29) % 70);
      const d = ((i * 0.55) % 6).toFixed(2);
      const s = (1.5 + (i % 4) * 0.7).toFixed(1);
      out += `<span class="car3d-spark" style="--sx:${x}%;--sy:${y}%;--sd:${d}s;--ss:${s}px"></span>`;
    }
    return out;
  }

  function firstWithPhoto(vehicles) {
    return (vehicles || []).find((v) => photosOf(v).length > 0);
  }

  function renderGlassLogo(opts = {}) {
    const size = opts.size || 'hero';
    const src = opts.src || '/auto-trading/assets/logo-official-clear.png?v=at13';
    const alt = opts.alt || 'NAJJAR & AL SAMOOM TRADING';
    return `
      <div class="nt-glass-logo-float nt-glass-logo-float--${esc(size)}" role="img" aria-label="${esc(alt)}">
        <div class="nt-glass-logo-glow"></div>
        <div class="nt-glass-logo-ring"></div>
        <div class="nt-glass-logo-pane">
          <img src="${esc(src)}" alt="${esc(alt)}" loading="eager">
        </div>
        <div class="nt-glass-logo-shine"></div>
      </div>`;
  }

  function renderCar3D(v, opts = {}) {
    const accent = opts.accent || accentOf(v);
    const delay = opts.delay != null ? opts.delay : (Math.random() * 3).toFixed(1);
    const label = `${v.make || ''} ${v.model || ''}`.trim();
    const cinema = opts.cinema ? ' car3d-scene--cinema' : '';
    const hero = opts.hero ? ' car3d-scene--hero' : '';
    return `
      <div class="car3d-scene car3d-scene--${accent}${cinema}${hero}" style="--car-delay:${delay}s" aria-hidden="true">
        <div class="car3d-glow"></div>
        <div class="car3d-beams"></div>
        <div class="car3d-particles">${particlesHtml(opts.hero || opts.cinema ? 18 : 10)}</div>
        <div class="car3d-stage">
          <div class="car3d-orbit">
            <div class="car3d-car car3d-car--${accent}">
              <div class="car3d-shadow"></div>
              <div class="car3d-chassis">
                <div class="car3d-bumper car3d-bumper--f"></div>
                <div class="car3d-body"></div>
                <div class="car3d-side-line"></div>
                <div class="car3d-cabin"></div>
                <div class="car3d-roof"></div>
                <div class="car3d-hood"></div>
                <div class="car3d-grille"></div>
                <div class="car3d-light car3d-light--l"></div>
                <div class="car3d-light car3d-light--r"></div>
                <div class="car3d-fog car3d-fog--l"></div>
                <div class="car3d-fog car3d-fog--r"></div>
                <div class="car3d-mirror car3d-mirror--l"></div>
                <div class="car3d-mirror car3d-mirror--r"></div>
                <div class="car3d-spoiler"></div>
                <div class="car3d-bumper car3d-bumper--r"></div>
                <div class="car3d-wheel car3d-wheel--fl"><i></i><b></b></div>
                <div class="car3d-wheel car3d-wheel--fr"><i></i><b></b></div>
                <div class="car3d-wheel car3d-wheel--rl"><i></i><b></b></div>
                <div class="car3d-wheel car3d-wheel--rr"><i></i><b></b></div>
              </div>
            </div>
          </div>
          <div class="car3d-floor"></div>
          <div class="car3d-ring"></div>
          <div class="car3d-reflection"></div>
        </div>
        <div class="car3d-vignette"></div>
        <div class="car3d-caption">${esc(label)}</div>
        ${opts.badge ? `<div class="car3d-live">${esc(opts.badge)}</div>` : ''}
      </div>`;
  }

  function renderNoPhoto(v, opts = {}) {
    const label = `${v.make || ''} ${v.model || ''}`.trim();
    const hero = opts.hero ? ' nt-nophoto--hero' : '';
    return `
      <div class="nt-nophoto${hero}" role="img" aria-label="لا توجد صورة لهذه السيارة بعد">
        <img class="nt-nophoto-mark" src="${LOGO_MARK}" alt="">
        <strong>${esc(label)}</strong>
        <span>الصور قريباً — تواصل معنا للاستفسار</span>
        ${opts.badge ? `<div class="nt-photo-badge">${esc(opts.badge)}</div>` : ''}
      </div>`;
  }

  function renderPhotoMedia(v, opts = {}) {
    const photos = photosOf(v);
    const src = photos[opts.photoIndex || 0] || photos[0];
    if (!src) {
      // A stylised drawing in place of a product photo misleads a buyer.
      return renderNoPhoto(v, opts);
    }
    const label = `${v.make || ''} ${v.model || ''}`.trim();
    const hero = opts.hero ? ' nt-photo-media--hero' : '';
    const thumbs = opts.gallery && photos.length > 1
      ? `<div class="nt-photo-thumbs">${photos.map((p, i) => `
          <button type="button" class="nt-photo-thumb${i === (opts.photoIndex || 0) ? ' active' : ''}" data-photo-index="${i}">
            <img src="${esc(p)}" alt="">
          </button>`).join('')}</div>`
      : '';
    return `
      <div class="nt-photo-media${hero}" data-photo-root>
        <img class="nt-photo-main" src="${esc(src)}" alt="${esc(label)}" loading="${opts.eager ? 'eager' : 'lazy'}">
        <div class="nt-photo-caption">${esc(label)}</div>
        ${opts.badge ? `<div class="nt-photo-badge">${esc(opts.badge)}</div>` : ''}
        ${thumbs}
      </div>`;
  }

  function waHref(v) {
    const omr = v.price_on_request ? 0 : priceOMR(v);
    const priceLine = omr > 0 ? `السعر: ${fmtNum(omr, 3)} ر.ع` : 'السعر: عند الطلب';
    return `https://wa.me/96871924089?text=${encodeURIComponent([
      'مرحباً NAJJAR & AL SAMOOM TRADING',
      'أرغب بالاستفسار عن السيارة التالية:',
      `${v.make} ${v.model} ${v.variant || ''}`.trim(),
      v.year ? `السنة: ${v.year}` : '',
      v.color ? `اللون: ${v.color}` : '',
      `رقم المخزون: ${v.stock_no || ''}`,
      v.vin ? `VIN: ${v.vin}` : '',
      v.plate_no ? `اللوحة: ${v.plate_no}` : '',
      priceLine,
    ].filter(Boolean).join('\n'))}`;
  }

  function pill(status) {
    return `<span class="pill ${statusClass(status)}">${esc(status || '')}</span>`;
  }

  function specRows(v, limit) {
    const rows = [
      v.vin ? ['VIN', v.vin, true] : null,
      v.plate_no ? ['اللوحة', v.plate_no, false] : null,
      v.engine_cc ? ['المحرك', `${v.engine_cc} cc`, false] : null,
      v.year ? ['السنة', String(v.year), false] : null,
      v.vehicle_type ? ['النوع', v.vehicle_type, false] : null,
      v.origin_country ? ['المنشأ', v.origin_country, false] : null,
      v.import_ref ? ['الشحن / المرجع', v.import_ref, false] : null,
      v.seats ? ['المقاعد', String(v.seats), false] : null,
      v.insurance_company ? ['التأمين', v.insurance_company, false] : null,
    ].filter(Boolean);
    const list = typeof limit === 'number' ? rows.slice(0, limit) : rows;
    return list.map(([label, value, ltr]) => `
      <li>
        <span>${esc(label)}</span>
        <strong${ltr ? ' dir="ltr"' : ''}>${esc(value)}</strong>
      </li>`).join('');
  }

  function sortVehicles(list, sort) {
    const rows = (list || []).slice();
    const key = sort || 'showroom';
    // Cars quoted on request have no number to compare, so they trail either ordering.
    const quoted = (v) => (v.price_on_request ? 0 : priceOMR(v));
    rows.sort((a, b) => {
      if (key === 'price-asc' || key === 'price-desc') {
        const pa = quoted(a);
        const pb = quoted(b);
        if (!pa !== !pb) return pa ? -1 : 1;
        const diff = key === 'price-asc' ? pa - pb : pb - pa;
        return diff || (a.sort_order || 999) - (b.sort_order || 999);
      }
      if (key === 'year-desc') return Number(b.year || 0) - Number(a.year || 0) || (a.sort_order || 999) - (b.sort_order || 999);
      if (key === 'name') {
        const an = `${a.make || ''} ${a.model || ''}`.localeCompare(`${b.make || ''} ${b.model || ''}`, 'ar');
        return an || (a.sort_order || 999) - (b.sort_order || 999);
      }
      // default: showroom order
      return (a.sort_order || 999) - (b.sort_order || 999) || String(a.stock_no || '').localeCompare(String(b.stock_no || ''));
    });
    return rows;
  }

  function renderSort(active) {
    const options = [
      ['showroom', 'ترتيب المعرض'],
      ['price-asc', 'السعر: الأقل'],
      ['price-desc', 'السعر: الأعلى'],
      ['year-desc', 'الأحدث سنة'],
      ['name', 'الاسم أ–ي'],
    ];
    return `
      <label class="nt-show-sort">
        <span>ترتيب</span>
        <select data-sort aria-label="ترتيب السيارات">
          ${options.map(([id, label]) => `
            <option value="${esc(id)}"${active === id ? ' selected' : ''}>${esc(label)}</option>`).join('')}
        </select>
      </label>`;
  }

  function renderShowroomCard(v, opts = {}) {
    const accent = accentOf(v);
    const idAttr = v.id != null ? ` data-vehicle-id="${esc(v.id)}"` : '';
    const idx = opts.index != null ? ` data-index="${opts.index}"` : '';
    const stock = v.stock_no || `CAR-${(opts.index || 0) + 1}`;
    return `
      <article class="nt-vcard nt-show-card nt-vcard--${accent}"${idAttr}${idx} role="button" tabindex="0">
        <div class="nt-show-media">
          ${renderPhotoMedia(v, { accent, delay: opts.delay, badge: v.year || 'NAJJAR' })}
          <div class="nt-show-media-badge">${esc(v.status || '')}</div>
        </div>
        <div class="nt-vcard-top">
          <span class="nt-vcard-stock">${esc(stock)}</span>
          ${pill(v.status)}
        </div>
        <h3>${esc(v.make)} ${esc(v.model)}</h3>
        <p class="nt-vcard-var">${esc(v.variant || '')} · ${esc(v.year || '—')} · ${esc(v.color || '')}</p>
        <ul class="nt-vcard-meta">
          ${specRows(v, 4)}
        </ul>
        <div class="nt-vcard-foot nt-vcard-foot--stack">
          ${priceBlock(v, { compact: true })}
          <div class="nt-show-actions">
            <a class="nt-btn primary nt-show-wa" href="${waHref(v)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">واتساب</a>
            <span class="nt-show-more">التفاصيل</span>
          </div>
        </div>
      </article>`;
  }

  function renderFilters(vehicles, active) {
    const counts = { all: vehicles.length, متاحة: 0, 'قيد الاستيراد': 0, محجوزة: 0 };
    vehicles.forEach((v) => {
      if (counts[v.status] != null) counts[v.status] += 1;
    });
    const chips = [
      ['all', 'الكل', counts.all],
      ['متاحة', 'متاحة للبيع', counts.متاحة],
      ['قيد الاستيراد', 'قيد الاستيراد', counts['قيد الاستيراد']],
      ['محجوزة', 'محجوزة', counts.محجوزة],
    ];
    return `
      <div class="nt-show-filters" role="group" aria-label="تصفية السيارات">
        ${chips.map(([id, label, n]) => `
          <button type="button" class="nt-show-chip${active === id ? ' active' : ''}" data-filter="${esc(id)}">
            ${esc(label)} <em>${n}</em>
          </button>`).join('')}
      </div>`;
  }

  function visibleVehicles(list, filter, sort) {
    const sorted = sortVehicles(list || [], sort || 'showroom');
    return !filter || filter === 'all' ? sorted : sorted.filter((v) => v.status === filter);
  }

  function renderShowroom(vehicles, opts = {}) {
    const list = vehicles || [];
    const filter = opts.filter || 'all';
    const sort = opts.sort || 'showroom';
    const sorted = sortVehicles(list, sort);
    const filtered = visibleVehicles(list, filter, sort);
    return `
      <div class="nt-showroom-shell">
        ${opts.hero !== false ? renderHero(sorted) : ''}
        <section class="nt-cust-intro">
          <div>
            <h2>Available now</h2>
            <p>صور حقيقية · أسعار واضحة · تواصل واتساب مباشر</p>
          </div>
          <div class="nt-show-controls">
            ${renderFilters(list, filter)}
            ${renderSort(sort)}
          </div>
        </section>
        <div class="nt-showroom" data-showroom>
          ${filtered.length
            ? filtered.map((v, i) => renderShowroomCard(v, {
              ...opts,
              delay: (i * 0.9).toFixed(1),
              index: i,
            })).join('')
            : '<p class="empty-state">لا توجد سيارات في هذا التصنيف</p>'}
        </div>
      </div>
      <div id="ntVehicleSheet" class="nt-vehicle-sheet" hidden></div>`;
  }

  function renderHero(vehicles) {
    const v = firstWithPhoto(vehicles);
    const stage = v
      ? renderPhotoMedia(v, { hero: true, eager: true, badge: v.year || v.stock_no || '' })
      : renderGlassLogo({ size: 'hero' });
    return `
      <section class="nt-cinema-hero nt-show-hero">
        <div class="nt-cinema-stage">
          ${stage}
        </div>
        <div class="nt-cinema-copy">
          <p class="nt-kicker">NAJJAR &amp; AL SAMOOM TRADING</p>
          <h2>Imported & carefully selected</h2>
          <p>تصفّح بالصور والأسعار، وتواصل معنا مباشرة للحجز أو الاستفسار.</p>
          <div class="nt-cinema-actions">
            <a class="nt-btn primary" href="#custRoot">استكشف التشكيلة</a>
            <a class="nt-btn ghost" href="https://wa.me/96871924089" target="_blank" rel="noopener">واتساب المعرض</a>
          </div>
        </div>
      </section>`;
  }

  function ensureOverlay(id, cls) {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      el.className = cls;
      el.hidden = true;
      document.body.appendChild(el);
    }
    return el;
  }

  function openVehicleSheet(vehicles, startIndex) {
    const list = vehicles || [];
    if (!list.length) return;
    let i = Math.max(0, Math.min(startIndex || 0, list.length - 1));
    let photoIndex = 0;
    const overlay = ensureOverlay('ntVehicleSheet', 'nt-vehicle-sheet');

    function paint() {
      const v = list[i];
      const accent = accentOf(v);
      const photos = photosOf(v);
      if (photoIndex >= photos.length) photoIndex = 0;
      overlay.hidden = false;
      document.body.classList.add('nt-lock');
      overlay.innerHTML = `
        <div class="nt-vehicle-sheet-panel nt-vehicle-sheet-panel--${accent}" role="dialog" aria-modal="true" aria-label="تفاصيل السيارة">
          <button type="button" class="nt-story-close" aria-label="إغلاق">✕</button>
          <div class="nt-vehicle-sheet-media">
            ${renderPhotoMedia(v, {
              accent, cinema: true, hero: true, eager: true, gallery: true,
              photoIndex, badge: v.stock_no || 'NAJJAR',
            })}
          </div>
          <div class="nt-vehicle-sheet-body">
            <div class="nt-vcard-top">
              <span class="nt-vcard-stock">${esc(v.stock_no || '')}</span>
              ${pill(v.status)}
            </div>
            <h3>${esc(v.make)} ${esc(v.model)} <em>${esc(v.variant || '')}</em></h3>
            <p class="nt-vcard-var">${esc(v.color || '')} · ${esc(v.vehicle_type || '')} · ${esc(v.year || '—')}</p>
            <ul class="nt-vcard-meta nt-vcard-meta--sheet">
              ${specRows(v)}
              ${v.license_doc_no ? `<li><span>رقم الوثيقة</span><strong>${esc(v.license_doc_no)}</strong></li>` : ''}
              ${v.notes ? `<li class="nt-sheet-notes"><span>ملاحظات</span><strong>${esc(v.notes)}</strong></li>` : ''}
            </ul>
            <div class="nt-vehicle-sheet-foot">
              ${priceBlock(v)}
              <div class="nt-show-actions">
                <button type="button" class="nt-btn ghost" data-sheet-prev ${i <= 0 ? 'disabled' : ''}>السابق</button>
                <button type="button" class="nt-btn ghost" data-sheet-next ${i >= list.length - 1 ? 'disabled' : ''}>التالي</button>
                <a class="nt-btn primary" href="${waHref(v)}" target="_blank" rel="noopener">استفسار واتساب</a>
              </div>
            </div>
          </div>
        </div>`;
      overlay.querySelector('.nt-story-close').onclick = close;
      const prev = overlay.querySelector('[data-sheet-prev]');
      const next = overlay.querySelector('[data-sheet-next]');
      if (prev) prev.onclick = () => { i -= 1; photoIndex = 0; paint(); };
      if (next) next.onclick = () => { i += 1; photoIndex = 0; paint(); };
      overlay.querySelectorAll('[data-photo-index]').forEach((btn) => {
        btn.onclick = (ev) => {
          ev.stopPropagation();
          photoIndex = Number(btn.getAttribute('data-photo-index') || 0);
          paint();
        };
      });
    }

    function close() {
      overlay.hidden = true;
      overlay.innerHTML = '';
      document.body.classList.remove('nt-lock');
    }

    overlay.onclick = (ev) => { if (ev.target === overlay) close(); };
    paint();
  }

  function bindShowroom(root, vehicles, opts = {}) {
    if (!root) return;
    const list = vehicles || [];
    // The detail sheet walks the cards the visitor can actually see, in their order.
    const activeChip = root.querySelector('.nt-show-chip.active');
    const filter = opts.filter || (activeChip && activeChip.getAttribute('data-filter')) || 'all';
    const sortSelect = root.querySelector('[data-sort]');
    const sort = opts.sort || (sortSelect && sortSelect.value) || 'showroom';
    const visible = visibleVehicles(list, filter, sort);
    root.querySelectorAll('[data-filter]').forEach((btn) => {
      btn.onclick = () => {
        if (typeof opts.onFilter === 'function') opts.onFilter(btn.getAttribute('data-filter'));
      };
    });
    const sortEl = root.querySelector('[data-sort]');
    if (sortEl) {
      sortEl.onchange = () => {
        if (typeof opts.onSort === 'function') opts.onSort(sortEl.value);
      };
    }
    root.querySelectorAll('.nt-show-card[data-index], .nt-show-card[data-vehicle-id]').forEach((el) => {
      const open = (ev) => {
        if (ev.target.closest('a,button,select,label')) return;
        const index = Number(el.getAttribute('data-index') || 0);
        openVehicleSheet(visible, index);
        if (typeof opts.onVehicle === 'function') {
          opts.onVehicle(Number(el.getAttribute('data-vehicle-id')), index);
        }
      };
      el.onclick = open;
      el.onkeydown = (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          open(ev);
        }
      };
    });
  }

  /* Legacy aliases */
  function renderIgPost(v, opts) { return renderShowroomCard(v, opts); }
  function renderReel(v, opts) { return renderShowroomCard(v, opts); }
  function renderStories() { return ''; }
  function renderFeed(vehicles, opts) { return renderShowroom(vehicles, opts); }
  function openStoryViewer(vehicles, startIndex) { return openVehicleSheet(vehicles, startIndex); }
  function openCinema(vehicles, startIndex) { return openVehicleSheet(vehicles, startIndex); }
  function bindGallery(root, vehicles, opts) { return bindShowroom(root, vehicles, opts); }
  function setMode() {}

  global.NajjarCar3D = {
    accentOf,
    photosOf,
    firstWithPhoto,
    renderCar3D,
    renderGlassLogo,
    renderPhotoMedia,
    renderNoPhoto,
    renderShowroomCard,
    renderShowroom,
    renderIgPost,
    renderReel,
    renderStories,
    renderFeed,
    renderHero,
    openVehicleSheet,
    openStoryViewer,
    openCinema,
    bindShowroom,
    bindGallery,
    setMode,
    sortVehicles,
    visibleVehicles,
    photosOf,
    priceBlock,
    money,
    esc,
    waHref,
  };
})(typeof window !== 'undefined' ? window : globalThis);
