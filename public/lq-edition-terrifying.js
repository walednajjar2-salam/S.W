/*!
 * جودة الانطلاقة — Launch Quality ERP base edition runtime
 * Default foundation layer: identity, effectiveness heal, health probe.
 */
(function () {
  "use strict";

  var EDITION = {
    code: "terrifying-dev",
    labelAr: "جودة الانطلاقة",
    labelEn: "Launch Quality",
    uiVersion: "2026.3-TD",
    storageKey: "lq_ui_edition",
  };

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function applyEditionIdentity() {
    try {
      localStorage.setItem(EDITION.storageKey, EDITION.code);
    } catch (_) {}
    document.documentElement.setAttribute("data-lq-edition", EDITION.code);
    document.documentElement.setAttribute("data-lq-edition-label", EDITION.labelAr);
    document.body.classList.add("lq-edition-terrifying");
    document.body.setAttribute("data-edition", EDITION.code);
    if (!document.body.classList.contains("login-ultra")) {
      document.body.classList.add("saas-luxury", "app-ready");
    }
  }

  function ensureEditionBadge() {
    /* Development edition badge is intentionally not shown in the live UI. */
    var badge = qs("#lqEditionBadge");
    if (badge && badge.parentNode) badge.parentNode.removeChild(badge);
  }

  function healLayout() {
    document.body.classList.add("lq-hub-mode", "lq-hub-expanded", "lq-card-mode");
    document.body.classList.remove("lq-workspace-collapsed");
    try {
      localStorage.setItem("lq_hub_expanded", "1");
      localStorage.removeItem("lq_workspace_collapsed");
    } catch (_) {}

    var login = qs("#loginScreen");
    var app = qs("#app");
    if (app && !app.classList.contains("hidden") && login) {
      login.classList.add("hidden");
      login.setAttribute("aria-hidden", "true");
      login.style.cssText =
        "display:none!important;height:0!important;min-height:0!important;overflow:hidden!important;visibility:hidden!important;pointer-events:none!important";
    }

    var ops = qs("#opsQuickBar");
    if (ops && !ops.querySelector("button")) ops.style.display = "none";

    var cockpit = qs("#lqCockpitWrap");
    if (cockpit) {
      cockpit.style.display = "block";
      cockpit.style.visibility = "visible";
      cockpit.style.opacity = "1";
    }

    var sections = document.querySelectorAll(".section.active");
    if (app && !app.classList.contains("hidden") && sections.length === 0) {
      var dash = qs("#sec-dashboard");
      if (dash) dash.classList.add("active");
    }

    // Kill removed assistants / elevator if any remnant injects them
    ["#visionAiDock", "#saasFabDock", "#saasScrollTop"].forEach(function (id) {
      var el = qs(id);
      if (el) {
        el.style.display = "none";
        el.setAttribute("hidden", "");
      }
    });
  }

  function healHeader() {
    var org = qs("#headerOrgName");
    if (org && !String(org.textContent || "").trim()) {
      org.textContent = "مشاريع جودة الانطلاقة";
    }
    var greet = qs("#headerGreeting");
    if (greet && greet.parentNode) greet.parentNode.removeChild(greet);
    var welcome = qs(".lq-header-welcome");
    if (welcome && welcome.parentNode) welcome.parentNode.removeChild(welcome);
    if (typeof window.syncHeaderClock === "function") {
      try {
        window.syncHeaderClock();
      } catch (_) {}
    }
  }

  function probeHealth() {
    return fetch("/api/health", { cache: "no-store" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        window.__LQ_HEALTH__ = data || {};
        var badge = qs("#lqEditionBadge");
        if (badge && data && data.ok) {
          badge.classList.add("is-healthy");
          badge.setAttribute(
            "data-health",
            String(data.version || "") + " · " + String(data.edition_label || EDITION.labelAr)
          );
        }
        return data;
      })
      .catch(function () {
        window.__LQ_HEALTH__ = { ok: false };
        return null;
      });
  }

  function effectivenessReport() {
    var app = qs("#app");
    var login = qs("#loginScreen");
    var dash = qs("#sec-dashboard");
    var nav = qs("#nav");
    var header = qs(".app-header");
    var health = window.__LQ_HEALTH__ || {};
    var checks = {
      edition: EDITION.code,
      label: EDITION.labelAr,
      appVisible: !!(app && !app.classList.contains("hidden")),
      loginHidden: !!(login && login.classList.contains("hidden")),
      dashboardPresent: !!dash,
      navButtons: nav ? nav.querySelectorAll("button").length : 0,
      headerPresent: !!header,
      hubExpanded: document.body.classList.contains("lq-hub-expanded"),
      apiHealthy: health.ok === true,
      token: !!(localStorage.getItem("jawdah_cloud_token") || "").trim(),
      portal: localStorage.getItem("jawdah_portal_choice") || null,
    };
    var score = 0;
    var total = 8;
    if (checks.edition) score++;
    if (checks.headerPresent) score++;
    if (checks.dashboardPresent) score++;
    if (checks.hubExpanded) score++;
    if (checks.apiHealthy) score++;
    if (checks.appVisible || !checks.token) score++;
    if (checks.loginHidden || !checks.token) score++;
    if (checks.navButtons > 0 || !checks.appVisible) score++;
    checks.score = Math.round((score / total) * 100);
    checks.status = checks.score >= 80 ? "excellent" : checks.score >= 60 ? "ok" : "needs-heal";
    return checks;
  }

  function runCycle() {
    applyEditionIdentity();
    ensureEditionBadge();
    healLayout();
    healHeader();
  }

  function boot() {
    runCycle();
    probeHealth().then(function () {
      runCycle();
      window.__LQ_TERRIFYING__ = {
        edition: EDITION,
        health: function () {
          return window.__LQ_HEALTH__;
        },
        check: effectivenessReport,
        heal: runCycle,
      };
      window.LQ_TERRIFYING_CHECK = effectivenessReport;
      var old = window.LAUNCH_QUALITY_CHECK;
      window.LAUNCH_QUALITY_CHECK = function () {
        var base = typeof old === "function" ? old() : {};
        return Object.assign({}, base, {
          edition: EDITION.code,
          edition_label: EDITION.labelAr,
          ui_version: EDITION.uiVersion,
          terrifying: effectivenessReport(),
          command_chain: typeof window.LQ_COMMAND_CHAIN_READY === "function" ? window.LQ_COMMAND_CHAIN_READY() : null,
        });
      };
    });
    setInterval(function () {
      if (document.body.classList.contains("app-ready")) {
        healLayout();
        ensureEditionBadge();
      }
    }, 4000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
  window.addEventListener("load", function () {
    setTimeout(runCycle, 200);
    setTimeout(runCycle, 1200);
  });
})();
