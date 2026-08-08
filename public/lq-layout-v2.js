/* Launch Quality · Layout V2 — floating center nav card */
(function () {
  const $ = (s) => document.querySelector(s);

  function ensureFloatNav() {
    if ($("#lqNavFloat")) return;
    const wrap = document.createElement("div");
    wrap.id = "lqNavFloat";
    wrap.className = "lq-nav-float";
    wrap.setAttribute("aria-label", "قائمة التنقل");
    wrap.innerHTML = `
      <div id="lqNavFloatCard" class="lq-nav-float-card" role="dialog" aria-modal="true" aria-label="قائمة النظام">
        <div class="lq-nav-float-head">
          <div class="lq-nav-float-brand">
            <div><strong>مشاريع الانطلاقة</strong><small>Launch Quality · ERP</small></div>
          </div>
          <button type="button" id="lqNavFloatClose" class="ghost lq-nav-float-close" aria-label="إغلاق">✕</button>
        </div>
        <nav id="lqNavFloatNav" class="lq-nav-float-grid"></nav>
      </div>
      <button type="button" id="lqNavFloatFab" class="lq-nav-float-fab" title="القائمة · Menu">◆</button>
    `;
    document.body.appendChild(wrap);

    $("#lqNavFloatFab")?.addEventListener("click", () => {
      wrap.classList.toggle("open");
      haptic(8);
    });
    $("#lqNavFloatClose")?.addEventListener("click", () => wrap.classList.remove("open"));
    document.addEventListener("click", (e) => {
      if (!wrap.classList.contains("open")) return;
      if (wrap.contains(e.target)) return;
      wrap.classList.remove("open");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") wrap.classList.remove("open");
    });
  }

  function syncFloatNav() {
    const src = $("#nav");
    const dst = $("#lqNavFloatNav");
    if (!src || !dst) return;
    dst.innerHTML = "";
    src.querySelectorAll(".nav-group-label, button").forEach((node) => {
      if (node.classList.contains("nav-group-label")) {
        const g = document.createElement("div");
        g.className = "nav-group-label";
        g.textContent = node.textContent;
        dst.appendChild(g);
        return;
      }
      const btn = node.cloneNode(true);
      btn.addEventListener("click", () => {
        $("#lqNavFloat")?.classList.remove("open");
      });
      dst.appendChild(btn);
    });
  }

  function hookMenuBtn() {
    const apply = () => {
      const menuBtn = $("#menuBtn");
      if (!menuBtn) return;
      menuBtn.onclick = () => $("#lqNavFloat")?.classList.toggle("open");
    };
    window.addEventListener("load", apply);
    apply();
  }

  function init() {
    document.body.classList.add("lq-layout-v2");
    // Executive shell uses a docked sidebar — skip floating center nav.
    if (document.body.classList.contains("lq-exec")) {
      const menuBtn = $("#menuBtn");
      if (menuBtn) {
        menuBtn.onclick = () => $("#sidebar")?.classList.toggle("open");
      }
      return;
    }
    ensureFloatNav();
    hookMenuBtn();

    const origBuild = window.buildNav;
    if (origBuild) {
      window.buildNav = function () {
        origBuild.apply(this, arguments);
        syncFloatNav();
      };
    }

    if ($("#nav")?.children.length) syncFloatNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.lqSyncFloatNav = syncFloatNav;
})();
