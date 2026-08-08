/* Login remember + autofill */
(function () {
  const KEY = "lq_saved_login";

  function loadSaved() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      const user = document.getElementById("loginUser");
      const pass = document.getElementById("loginPass");
      const remember = document.getElementById("lqRememberLogin");
      if (user && data.username) user.value = data.username;
      if (pass && data.password) pass.value = data.password;
      if (remember) remember.checked = true;
    } catch (e) {}
  }

  function saveIfRemembered(username, password) {
    const remember = document.getElementById("lqRememberLogin");
    if (!remember?.checked) {
      localStorage.removeItem(KEY);
      return;
    }
    localStorage.setItem(
      KEY,
      JSON.stringify({ username, password, savedAt: new Date().toISOString() })
    );
  }

  function ensureCheckbox() {
    const pane = document.getElementById("authPanePassword");
    if (!pane || document.getElementById("lqRememberLogin")) return;
    const row = document.createElement("label");
    row.className = "lq-remember-row";
    const caption =
      window.LQ_I18N && window.LQ_I18N.t
        ? window.LQ_I18N.t("saveCredentials")
        : "حفظ البيانات وتعبئة تلقائية عند الدخول";
    row.innerHTML =
      '<input type="checkbox" id="lqRememberLogin"> ' +
      '<span data-i18n="saveCredentials"></span>';
    row.querySelector("span").textContent = caption;
    const btn = document.getElementById("loginBtn");
    if (btn) pane.insertBefore(row, btn);
    else pane.appendChild(row);
  }

  window.addEventListener("load", () => {
    ensureCheckbox();
    loadSaved();
    if (typeof login === "function") {
      const orig = login;
      window.login = async function () {
        const username = document.getElementById("loginUser")?.value?.trim();
        const password = document.getElementById("loginPass")?.value;
        saveIfRemembered(username, password);
        return orig.apply(this, arguments);
      };
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    ensureCheckbox();
    loadSaved();
  });
})();
