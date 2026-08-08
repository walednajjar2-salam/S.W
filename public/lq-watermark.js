(function () {
  "use strict";

  function removeWatermark() {
    const el = document.getElementById("lqBrandWatermark");
    if (el && el.parentNode) {
      el.parentNode.removeChild(el);
    }
  }

  function sync() {
    removeWatermark();
  }

  document.addEventListener("DOMContentLoaded", sync);
  window.addEventListener("load", sync);

  const obs = new MutationObserver(sync);
  window.addEventListener("load", function () {
    const app = document.getElementById("app");
    if (app) obs.observe(app, { attributes: true, attributeFilter: ["class"] });
  });
})();
