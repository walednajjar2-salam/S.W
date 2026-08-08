(function () {
  "use strict";

  let modalEl = null;
  let devicesHost = null;

  function deviceFingerprint() {
    try {
      const key = "lq_device_fp";
      let fp = localStorage.getItem(key);
      if (!fp) {
        fp =
          "lq-" +
          String(navigator.userAgent || "ua").slice(0, 40) +
          "-" +
          Math.random().toString(36).slice(2) +
          Date.now().toString(36);
        localStorage.setItem(key, fp);
      }
      return fp;
    } catch (_) {
      return "lq-anonymous";
    }
  }

  function deviceLabel() {
    const ua = navigator.userAgent || "";
    if (/Windows/i.test(ua)) return "Windows";
    if (/Mac OS/i.test(ua)) return "Mac";
    if (/Android/i.test(ua)) return "Android";
    if (/iPhone|iPad/i.test(ua)) return "iOS";
    return "متصفح";
  }

  function ensureModal() {
    if (modalEl) return modalEl;
    modalEl = document.createElement("div");
    modalEl.id = "lqSecurityModal";
    modalEl.className = "lq-security-modal";
    modalEl.innerHTML =
      '<div class="lq-security-card saas-glass">' +
      "<h3>🔐 أمان الحساب</h3>" +
      '<p class="mini" id="lqSecReason">يجب تحديث كلمة المرور للمتابعة (10 أحرف أو أكثر).</p>' +
      '<label id="lqSecOldWrap">الحالية<input id="lqSecOld" type="password" autocomplete="current-password"></label>' +
      '<label>الجديدة<input id="lqSecNew" type="password" autocomplete="new-password"></label>' +
      '<label>تأكيد<input id="lqSecConfirm" type="password" autocomplete="new-password"></label>' +
      '<button type="button" class="gold-btn" id="lqSecSubmit">حفظ كلمة المرور</button>' +
      "</div>";
    document.body.appendChild(modalEl);
    modalEl.querySelector("#lqSecSubmit").addEventListener("click", submitChange);
    return modalEl;
  }

  function mustChange() {
    return !!(window.Jawdah && Jawdah.user && Jawdah.user.must_change_password);
  }

  function show(force, reason) {
    const m = ensureModal();
    const oldWrap = m.querySelector("#lqSecOldWrap");
    if (oldWrap) oldWrap.style.display = force ? "none" : "grid";
    const reasonEl = m.querySelector("#lqSecReason");
    if (reasonEl && reason) reasonEl.textContent = reason;
    m.classList.add("open");
    document.body.classList.add("lq-security-lock");
  }

  function hide() {
    if (!modalEl) return;
    modalEl.classList.remove("open");
    document.body.classList.remove("lq-security-lock");
  }

  async function submitChange() {
    const newPwd = document.getElementById("lqSecNew").value;
    const confirm = document.getElementById("lqSecConfirm").value;
    if (newPwd !== confirm) {
      if (typeof toastNotice === "function") toastNotice("تأكيد كلمة المرور غير مطابق");
      return;
    }
    const body = { new_password: newPwd };
    const oldEl = document.getElementById("lqSecOld");
    if (oldEl && oldEl.parentElement.style.display !== "none") {
      body.old_password = oldEl.value;
    } else {
      body.force = true;
    }
    try {
      await api("change_password", { method: "POST", body: JSON.stringify(body) });
      if (Jawdah.user) Jawdah.user.must_change_password = false;
      hide();
      if (typeof toast === "function") toast("تم تحديث كلمة المرور");
      renderDevicesPanel();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  function gateAfterAuth() {
    if (mustChange()) {
      show(true, "انتهت صلاحية كلمة المرور أو يلزم تغييرها قبل الاستخدام.");
    }
  }

  async function completeMfaLogin(challengeId, username, code) {
    const res = await api("login/otp", {
      method: "POST",
      body: JSON.stringify({
        username,
        code,
        challenge_id: challengeId,
        remember_device: true,
        device_fingerprint: deviceFingerprint(),
        device_label: deviceLabel(),
      }),
    });
    return res;
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function renderDevicesPanel() {
    const host =
      document.getElementById("lqTrustedDevicesHost") ||
      document.getElementById("usersTable")?.parentElement;
    if (!host || !window.Jawdah || !Jawdah.token) return;
    let box = document.getElementById("lqTrustedDevicesCard");
    if (!box) {
      box = document.createElement("div");
      box.id = "lqTrustedDevicesCard";
      box.className = "card";
      host.parentElement
        ? host.parentElement.insertBefore(box, host.nextSibling)
        : host.appendChild(box);
    }
    devicesHost = box;
    box.innerHTML = "<h3>🛡️ الأجهزة الموثوقة</h3><p class='mini'>جاري التحميل...</p>";
    try {
      const res = await api("security/devices");
      const devices = (res.devices || []).filter((d) => Number(d.active) === 1);
      const sec = res.security || {};
      box.innerHTML =
        "<h3>🛡️ الأجهزة الموثوقة + MFA</h3>" +
        `<div class="status-line" style="margin:8px 0">
          <span class="badge">تدوير كل ${esc(sec.password_max_age_days || 90)} يوم</span>
          <span class="badge">MFA: ${esc(sec.mfa_enforce || "soft")}</span>
          <span class="badge">TOTP: ${sec.totp_enabled ? "مفعّل" : "غير مفعّل"}</span>
          <span class="badge">${sec.trusted_device ? "هذا الجهاز موثوق" : "هذا الجهاز غير موثوق بعد"}</span>
        </div>` +
        `<div class="toolbar" style="flex-wrap:wrap;gap:8px;margin:8px 0">
          <button type="button" class="gold-btn" onclick="LQ_SECURITY.setupTotp()">تفعيل تطبيق المصادقة</button>
          ${sec.totp_enabled ? '<button type="button" class="ghost" onclick="LQ_SECURITY.disableTotp()">تعطيل TOTP</button>' : ""}
        </div>` +
        '<pre id="lqTotpSetupOut" class="mini" style="white-space:pre-wrap;margin:0 0 10px"></pre>' +
        (devices.length
          ? `<div class="table-wrap"><table><thead><tr><th>الجهاز</th><th>آخر ظهور</th><th>موثوق حتى</th><th></th></tr></thead><tbody>${devices
              .map(
                (d) =>
                  `<tr><td>${esc(d.device_label || "جهاز")}<br><small class="mini">${esc(
                    (d.user_agent || "").slice(0, 60)
                  )}</small></td><td>${esc(d.last_seen_at || "")}</td><td>${esc(
                    d.trusted_until || ""
                  )}</td><td><button type="button" class="danger" data-revoke="${esc(
                    d.id
                  )}">إلغاء</button></td></tr>`
              )
              .join("")}</tbody></table></div>`
          : "<p class='mini'>لا توجد أجهزة موثوقة بعد. فعّل «تذكرني» عند الدخول أو أكمل MFA.</p>") +
        `<div class="toolbar" style="margin-top:10px">
          <button type="button" class="ghost" id="lqSecChangePwdBtn">تغيير كلمة المرور</button>
          <a class="ghost" href="/get-windows" target="_blank" rel="noopener">تطبيق ويندوز</a>
        </div>`;
      box.querySelectorAll("[data-revoke]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await api("security/devices", {
              method: "POST",
              body: JSON.stringify({ device_id: btn.getAttribute("data-revoke") }),
            });
            if (typeof toast === "function") toast("تم إلغاء ثقة الجهاز");
            renderDevicesPanel();
          } catch (e) {
            if (typeof toastErr === "function") toastErr(e);
          }
        });
      });
      const ch = box.querySelector("#lqSecChangePwdBtn");
      if (ch) ch.onclick = () => show(false, "غيّر كلمة المرور من هنا.");
    } catch (e) {
      box.innerHTML = "<h3>🛡️ الأجهزة الموثوقة</h3><p class='mini'>تعذر التحميل</p>";
    }
  }

  async function setupTotp() {
    const out = document.getElementById("lqTotpSetupOut");
    try {
      const res = await api("security/totp_setup", { method: "POST", body: "{}" });
      if (out) {
        out.textContent =
          "السر: " +
          (res.totp_secret || "") +
          "\nأضفه في Google Authenticator ثم أدخل الرمز أدناه للتأكيد.";
      }
      const code = window.prompt("أدخل رمز تطبيق المصادقة للتأكيد:");
      if (!code) return;
      await api("security/totp_confirm", {
        method: "POST",
        body: JSON.stringify({ code: String(code).trim(), totp_secret: res.totp_secret }),
      });
      if (typeof toast === "function") toast("تم تفعيل MFA عبر تطبيق المصادقة");
      renderDevicesPanel();
    } catch (e) {
      if (out) out.textContent = String((e && e.message) || e);
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  async function disableTotp() {
    const password = window.prompt("أدخل كلمة المرور لتعطيل TOTP:");
    if (!password) return;
    try {
      await api("security/totp_disable", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      if (typeof toast === "function") toast("تم تعطيل TOTP");
      renderDevicesPanel();
    } catch (e) {
      if (typeof toastErr === "function") toastErr(e);
    }
  }

  window.LQ_SECURITY = {
    mustChange,
    show,
    hide,
    gateAfterAuth,
    deviceFingerprint,
    deviceLabel,
    completeMfaLogin,
    renderDevicesPanel,
    setupTotp,
    disableTotp,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(renderDevicesPanel, 800));
  } else {
    setTimeout(renderDevicesPanel, 800);
  }
})();
