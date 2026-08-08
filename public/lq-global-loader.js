/* Global loading spinner */
(function () {
  function ensureLoader() {
    if (document.getElementById("lqGlobalLoader")) return;
    const el = document.createElement("div");
    el.id = "lqGlobalLoader";
    el.className = "lq-global-loader hidden";
    el.setAttribute("aria-hidden", "true");
    el.innerHTML = "<div><div class=\"lq-loader-orbit\"></div><span>جاري التحميل…</span></div>";
    document.body.appendChild(el);
  }

  function show() {
    ensureLoader();
    const el = document.getElementById("lqGlobalLoader");
    if (el) {
      el.classList.remove("hidden");
      el.setAttribute("aria-hidden", "false");
    }
  }

  function hide() {
    const el = document.getElementById("lqGlobalLoader");
    if (el) {
      el.classList.add("hidden");
      el.setAttribute("aria-hidden", "true");
    }
  }

  window.lqLoaderShow = show;
  window.lqLoaderHide = hide;

  window.addEventListener("load", () => {
    if (typeof loadAll === "function") {
      const orig = loadAll;
      window.loadAll = async function () {
        show();
        try {
          return await orig.apply(this, arguments);
        } finally {
          hide();
        }
      };
    }
    if (typeof showSection === "function") {
      const origSec = showSection;
      window.showSection = function (id) {
        show();
        const done = () => setTimeout(hide, 280);
        try {
          const r = origSec.apply(this, arguments);
          done();
          return r;
        } catch (e) {
          hide();
          throw e;
        }
      };
    }
  });
})();
