/* Launch Quality · Card record views (Model J) */
(function () {
  function grid(html) {
    return `<div class="lq-record-grid">${html}</div>`;
  }

  function patch(name, fn) {
    const orig = window[name];
    if (!orig) return;
    window[name] = function () {
      try {
        fn();
      } catch (e) {
        orig.apply(this, arguments);
      }
    };
  }

  patch("renderProperties", function () {
    const rows = filterRows("properties", [
      "building_no",
      "apartment_no",
      "room_no",
      "name",
      "status",
      "location",
      "notes",
    ]);
    const host = $("#propertiesTable");
    if (!host) return;
    if (!rows.length) {
      host.innerHTML = '<p class="lq-record-empty">لا توجد عقارات مسجلة</p>';
    } else {
      host.innerHTML = grid(
        rows
          .map(
            (p) => `
        <article class="lq-record-card lq-cine-tile lq-prop-card">
          ${typeof lqPropertyThumbHtml === "function" ? lqPropertyThumbHtml(p, { hero: true }) : `<span class="lq-record-icon">${typeof lqPropertyEmoji === "function" ? lqPropertyEmoji(p) : "🏢"}</span>`}
          <div class="lq-record-head">
            <div>
              <h4>${htmlEscape(propertyLabel(p))}</h4>
              <span class="lq-record-sub">${htmlEscape(p.location || "Oman")}</span>
            </div>
            ${statusBadge(p.status)}
          </div>
          <div class="lq-record-meta">
            <span>💵 ${money(p.price)}</span>
            <span>بناية ${htmlEscape(p.building_no || "—")}</span>
            <span>شقة ${htmlEscape(p.apartment_no || "—")}</span>
          </div>
          <div class="lq-record-actions">
            <button class="ghost" onclick="editRecord('properties','${p.id}')">تعديل</button>
            <button class="danger" onclick="delRecord('properties','${p.id}')">حذف</button>
          </div>
        </article>`
          )
          .join("")
      );
    }
    fillSelect("#propStatusFilter", ["", ...PROPERTY_STATUSES], false);
  });

  patch("renderClients", function () {
    const rows = filterRows("clients", [
      "name",
      "phone",
      "email",
      "national_id",
    ]);
    const host = $("#clientsTable");
    if (!host) return;
    if (!rows.length) {
      host.innerHTML = '<p class="lq-record-empty">لا يوجد عملاء</p>';
    } else {
      host.innerHTML = grid(
        rows
          .map(
            (c) => `
        <article class="lq-record-card lq-cine-tile">
          <div class="lq-record-head">
            <span class="lq-record-icon">👥</span>
            <div>
              <h4>${htmlEscape(c.name || "—")}</h4>
              <span class="lq-record-sub">${htmlEscape(c.phone || "بدون هاتف")}</span>
            </div>
          </div>
          <div class="lq-record-meta">
            <span>📧 ${htmlEscape(c.email || "—")}</span>
            <span>🪪 ${htmlEscape(c.national_id || "—")}</span>
            <span>💰 ${money(c.balance)}</span>
          </div>
          <div class="lq-record-actions">
            <button class="ghost" onclick="clientStatement('${c.id}')">كشف</button>
            <button class="ghost" onclick="editRecord('clients','${c.id}')">تعديل</button>
            <button class="danger" onclick="delRecord('clients','${c.id}')">حذف</button>
          </div>
        </article>`
          )
          .join("")
      );
    }
  });

  patch("renderContracts", function () {
    fillSelect(
      "#contractProperty",
      Jawdah.data.properties || [],
      true,
      "id",
      "name",
      propertyLabel
    );
    fillSelect("#contractClient", Jawdah.data.clients || [], true, "id", "name");
    const rows = filterRows("contracts", ["id", "status", "notes"]);
    const renewalHost = $("#renewalQueueBox");
    if (renewalHost) {
      const queue = renewalQueue();
      renewalHost.innerHTML = queue.length
        ? `<div class="renewal-panel"><h3>🔁 قرارات التجديد (${queue.length})</h3><p class="mini">عقود نشطة تقترب من تاريخ النهاية أو منتهية وتحتاج قرار تجديد قبل تحولها إلى شغور.</p>${queue
            .map(
              ({ contract: c, meta }) =>
                `<div class="renewal-row"><div><b>${c.contract_no || c.id}</b> · ${byId("clients", c.client_id).name || c.client_id}<br><span class="mini">${propertyLabel(byId("properties", c.property_id))} · ينتهي ${c.end_date}</span></div><span class="badge ${meta.tone}">${meta.label}</span><button class="gold-btn" onclick="renewContract('${c.id}')">تجديد</button></div>`
            )
            .join("")}</div>`
        : `<div class="renewal-panel renewal-ok"><h3>🔁 التجديد</h3><p class="mini">لا توجد عقود تحتاج قرار تجديد حالياً.</p></div>`;
    }
    const host = $("#contractsTable");
    if (!host) return;
    if (!rows.length) {
      host.innerHTML = '<p class="lq-record-empty">لا توجد عقود</p>';
      return;
    }
    host.innerHTML = grid(
      rows
        .map((r) => {
          const meta = contractRenewalMeta(r);
          const client = byId("clients", r.client_id);
          const prop = byId("properties", r.property_id);
          const renewBtn = meta.renewable
            ? `<button class="gold-btn" onclick="renewContract('${r.id}')">تجديد</button>`
            : "";
          const st = String(r.status || "").toLowerCase();
          const requestBtn = st === "draft"
            ? `<button class="gold-btn" onclick="requestContractApproval('${r.id}')">طلب اعتماد</button>`
            : "";
          const approveBtn = st === "approvalrequested" && canDecideApprovals()
            ? `<button class="gold-btn" onclick="approveContract('${r.id}')">اعتماد</button>`
            : "";
          const activateBtn = st === "approved" && (typeof canActivateContracts === "function" && canActivateContracts())
            ? `<button class="gold-btn" onclick="activateContract('${r.id}')">تفعيل</button>`
            : "";
          const invoiceBtn = (st === "active" || st === "activated")
            ? `<button class="ghost" onclick="invoiceFromContract('${r.id}')">فاتورة</button>`
            : "";
          return `
        <article class="lq-record-card lq-cine-tile">
          <div class="lq-record-head">
            <span class="lq-record-icon">📄</span>
            <div>
              <h4>${htmlEscape(r.contract_no || r.id)}</h4>
              <span class="lq-record-sub">${htmlEscape(client.name || "")}</span>
            </div>
            ${statusBadge(r.status)}
          </div>
          <div class="lq-record-meta">
            <span>🏢 ${htmlEscape(propertyLabel(prop))}</span>
            <span>📅 ${r.start_date || "—"} → ${r.end_date || "—"}</span>
            <span>💵 ${money(r.rent_amount)}</span>
            ${meta.label ? `<span class="badge ${meta.tone}">${meta.label}</span>` : ""}
          </div>
          <div class="lq-record-actions">
            ${renewBtn}
            ${requestBtn}
            ${approveBtn}
            ${activateBtn}
            <button class="ghost" onclick="contractDocument('${r.id}')">العقد</button>
            ${invoiceBtn}
            <button class="ghost" onclick="editRecord('contracts','${r.id}')">تعديل</button>
            <button class="danger" onclick="delRecord('contracts','${r.id}')">حذف</button>
          </div>
        </article>`;
        })
        .join("")
    );
  });

  patch("renderInvoices", function () {
    const rows = filterRows("invoices", [
      "invoice_no",
      "description",
      "status",
    ]);
    const host = $("#invoicesTable");
    if (!host) return;
    if (!rows.length) {
      host.innerHTML = '<p class="lq-record-empty">لا توجد فواتير</p>';
      return;
    }
    host.innerHTML = grid(
      rows
        .map((r) => {
          const rem = Math.max(
            0,
            Number(r.amount || 0) - Number(r.paid_amount || 0)
          );
          const voidBtn =
            String(r.status || "").toLowerCase() === "void"
              ? ""
              : `<button class="danger" onclick="voidInvoice('${r.id}')">إلغاء</button>`;
          return `
        <article class="lq-record-card lq-cine-tile">
          <div class="lq-record-head">
            <span class="lq-record-icon">🧾</span>
            <div>
              <h4>${htmlEscape(r.invoice_no || r.id)}</h4>
              <span class="lq-record-sub">${htmlEscape(byId("clients", r.client_id).name || "")}</span>
            </div>
            ${statusBadge(r.status || (rem > 0 ? "Pending" : "Paid"))}
          </div>
          <div class="lq-record-meta">
            <span>إجمالي ${money(r.amount)}</span>
            <span>مدفوع ${money(r.paid_amount)}</span>
            <span>متبقي ${money(rem)}</span>
            <span>استحقاق ${r.due_date || "—"}</span>
          </div>
          <div class="lq-record-actions">
            <button class="gold-btn" onclick="openPayment('${r.id}')">تحصيل</button>
            <button class="ghost" onclick="printInvoice('${r.id}')">طباعة</button>
            <button class="ghost" onclick="showInvoiceAudit('${r.id}')">سجل</button>
            ${voidBtn}
          </div>
        </article>`;
        })
        .join("")
    );
  });

  patch("renderAccounts", function () {
    const rows = filterRows("accounts", ["description", "category", "type"]);
    const host = $("#accountsTable");
    if (host) {
      if (!rows.length) {
        host.innerHTML = '<p class="lq-record-empty">لا توجد حركات</p>';
      } else {
        host.innerHTML = grid(
          rows
            .map(
              (r) => `
          <article class="lq-record-card lq-cine-tile">
            <div class="lq-record-head">
              <span class="lq-record-icon">${r.type === "income" ? "💰" : "📉"}</span>
              <div>
                <h4>${htmlEscape(r.description || r.category || "حركة")}</h4>
                <span class="lq-record-sub">${htmlEscape(r.entry_date || "")}</span>
              </div>
              ${statusBadge(r.type)}
            </div>
            <div class="lq-record-meta">
              <span>${money(r.amount)}</span>
              <span>${htmlEscape(r.category || "—")}</span>
            </div>
            <div class="lq-record-actions">
              <button class="ghost" onclick="editRecord('accounts','${r.id}')">تعديل</button>
              <button class="danger" onclick="delRecord('accounts','${r.id}')">حذف</button>
            </div>
          </article>`
            )
            .join("")
        );
      }
    }
    const income = rows
      .filter((x) => x.type === "income")
      .reduce((s, x) => s + Number(x.amount || 0), 0);
    const expense = rows
      .filter((x) => x.type === "expense")
      .reduce((s, x) => s + Number(x.amount || 0), 0);
    $("#accountSummary").innerHTML = `<span class="badge">إيرادات ${money(income)}</span><span class="badge">مصروفات ${money(expense)}</span><span class="badge">صافي ${money(income - expense)}</span>`;
  });

  patch("renderMaintenance", function () {
    fillSelect(
      "#maintProperty",
      Jawdah.data.properties || [],
      true,
      "id",
      "name",
      propertyLabel
    );
    const rows = filterRows("maintenance", [
      "title",
      "priority",
      "status",
      "notes",
    ]);
    const host = $("#maintenanceGrid");
    if (!host) return;
    if (!rows.length) {
      host.innerHTML =
        '<p class="lq-record-empty">لا توجد طلبات صيانة</p>';
      return;
    }
    host.innerHTML = rows
      .map(
        (m) => `
      <article class="lq-record-card lq-cine-tile card">
        <div class="lq-record-head">
          <span class="lq-record-icon">🔧</span>
          <div>
            <h4>${htmlEscape(m.title || "صيانة")}</h4>
            <span class="lq-record-sub">${htmlEscape(propertyLabel(byId("properties", m.property_id)) || m.property_id)}</span>
          </div>
          <span class="badge">${htmlEscape(m.priority || "")}</span>
        </div>
        <div class="lq-record-meta">
          <span>${htmlEscape(m.status || "")}</span>
          <span>💵 ${money(m.cost)}</span>
        </div>
        <div class="lq-record-actions">
          <button class="ghost" onclick="editRecord('maintenance','${m.id}')">متابعة</button>
          <button class="danger" onclick="delRecord('maintenance','${m.id}')">حذف</button>
        </div>
      </article>`
      )
      .join("");
  });

  patch("renderUsers", function () {
    if (typeof window.renderStaffMapping === "function") {
      window.renderStaffMapping();
    }
    if (
      !Jawdah.data.users &&
      !["admin", "owner"].includes(Jawdah.user?.role)
    ) {
      $("#usersTable").innerHTML =
        '<div class="card">هذا القسم للمدير فقط</div>';
      return;
    }
    if (!Jawdah.data.users) {
      $("#usersTable").innerHTML =
        '<div class="card mini">جاري تحميل المستخدمين...</div>';
      return;
    }
    const rows = Jawdah.data.users;
    const host = $("#usersTable");
    host.innerHTML = grid(
      rows
        .map(
          (r) => `
      <article class="lq-record-card lq-cine-tile">
        <div class="lq-record-head">
          <span class="lq-record-icon">🛡️</span>
          <div>
            <h4>${htmlEscape(r.name || r.username)}</h4>
            <span class="lq-record-sub">${htmlEscape(r.username)}</span>
          </div>
          <span class="badge">${r.active ? "نشط" : "موقوف"}</span>
        </div>
        <div class="lq-record-meta">
          <span>${htmlEscape(roleName(r.role))}</span>
          <span>آخر دخول ${htmlEscape(r.last_login || "—")}</span>
        </div>
        <div class="lq-record-actions">
          <button class="ghost" onclick="editRecord('users','${r.id}')">تعديل</button>
          <button class="danger" onclick="delRecord('users','${r.id}')">حذف</button>
        </div>
      </article>`
        )
        .join("")
    );
  });
})();
