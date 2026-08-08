(function () {
  var deferredPrompt = null;
  var installButton = null;

  function t(key, fallback) {
    return window.LQ_I18N && window.LQ_I18N.t ? window.LQ_I18N.t(key) : fallback;
  }

  function createInstallButton() {
    if (installButton || window.matchMedia("(display-mode: standalone)").matches) return;
    installButton = document.createElement("button");
    installButton.type = "button";
    installButton.id = "lqInstallAppBtn";
    installButton.setAttribute("data-i18n", "installApp");
    installButton.textContent = t("installApp", "تثبيت التطبيق");
    installButton.setAttribute("aria-label", installButton.textContent);
    installButton.style.cssText = [
      "position:fixed",
      "left:18px",
      "bottom:18px",
      "z-index:250",
      "border:1px solid rgba(47,220,196,.55)",
      "background:linear-gradient(135deg,rgba(5,18,28,.94),rgba(10,42,52,.92))",
      "color:#e8fffb",
      "border-radius:999px",
      "padding:11px 16px",
      "font:800 13px Tajawal,Segoe UI,Arial,sans-serif",
      "box-shadow:0 16px 40px rgba(0,0,0,.34),0 0 22px rgba(47,220,196,.18)",
      "cursor:pointer"
    ].join(";");
    installButton.addEventListener("click", installApp);
    document.body.appendChild(installButton);
  }

  function hideInstallButton() {
    if (installButton) {
      installButton.remove();
      installButton = null;
    }
  }

  async function installApp() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    try {
      await deferredPrompt.userChoice;
    } finally {
      deferredPrompt = null;
      hideInstallButton();
    }
  }

  // Nothing here is ever registered again. Registering /sw.js and then sweeping
  // every registration — as this did — unregistered the brand-new worker before
  // it could activate and purge, so the stale shell it was sent to remove stayed
  // put. Devices still carrying a worker pick up /sw.js on their next update
  // check and it deletes itself; this sweep clears the rest.
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.getRegistrations().then(function (regs) {
        return Promise.all((regs || []).map(function (reg) { return reg.unregister(); }));
      }).catch(function () {});
      if (window.caches && caches.keys) {
        caches.keys().then(function (keys) {
          return Promise.all((keys || []).map(function (k) { return caches.delete(k); }));
        }).catch(function () {});
      }
    });
  }

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferredPrompt = event;
    createInstallButton();
  });

  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    hideInstallButton();
  });

  window.LQ_PWA = {
    canInstall: function () { return !!deferredPrompt; },
    showInstallButton: createInstallButton
  };
})();
