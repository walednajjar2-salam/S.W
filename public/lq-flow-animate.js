/* Phase 5 — animated workflow on property/client/contract/invoice actions */
(function () {
  const STEP_LABELS = [
    "بناية",
    "شقة",
    "غرفة",
    "عميل",
    "عقد",
    "فاتورة",
    "تحصيل",
  ];
  const STEP_EMOJI = ["🏗️", "🏬", "🛏️", "👥", "📄", "🧾", "💰"];

  function snapshot() {
    const d = (window.Jawdah && Jawdah.data) || {};
    const props = d.properties || [];
    const buildings = new Set(props.map((p) => p.building_no).filter(Boolean)).size;
    return [
      buildings || props.length,
      props.filter((p) => p.apartment_no).length,
      props.filter((p) => p.room_no).length,
      (d.clients || []).length,
      (d.contracts || []).length,
      (d.invoices || []).length,
      (d.invoices || []).filter((i) => Number(i.paid_amount || 0) > 0).length,
    ];
  }

  function soundEnabled() {
    return localStorage.getItem("lq_flow_sound") !== "0";
  }

  function playChime() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!soundEnabled()) return;
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.setValueAtTime(440, ctx.currentTime);
      o.frequency.exponentialRampToValueAtTime(660, ctx.currentTime + 0.12);
      g.gain.setValueAtTime(0.07, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
      o.connect(g);
      g.connect(ctx.destination);
      o.start();
      o.stop(ctx.currentTime + 0.3);
      setTimeout(() => ctx.close(), 400);
    } catch (e) {}
  }

  function showToast(msg) {
    const el = document.getElementById("lqFlowToast");
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => el.classList.add("hidden"), 3200);
  }

  function spawnParticles(stepEl) {
    if (!stepEl || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const zone = document.getElementById("lqZoneFlow");
    if (!zone) return;
    const rect = stepEl.getBoundingClientRect();
    const zr = zone.getBoundingClientRect();
    for (let i = 0; i < 6; i++) {
      const p = document.createElement("span");
      p.className = "lq-flow-particle";
      p.style.left = rect.left - zr.left + rect.width / 2 + "px";
      p.style.top = rect.top - zr.top + rect.height / 2 + "px";
      p.style.setProperty("--px", (Math.random() * 40 - 20) + "px");
      p.style.setProperty("--py", (-20 - Math.random() * 30) + "px");
      zone.appendChild(p);
      setTimeout(() => p.remove(), 1100);
    }
  }

  function moveDotToStep(stepIdx) {
    const track = document.querySelector(".lq-flow-track");
    const step = document.querySelector(`.lq-flow-step[data-step="${stepIdx}"]`);
    const dot = document.getElementById("lqFlowEnergyDot");
    if (!track || !step || !dot) return;
    const tr = track.getBoundingClientRect();
    const sr = step.getBoundingClientRect();
    const x = sr.left + sr.width / 2 - tr.left - 7;
    dot.style.setProperty("--lq-dot-x", x + "px");
    dot.style.transform = `translateX(${x}px)`;
    dot.classList.add("lq-flow-dot-travel");
    setTimeout(() => dot.classList.remove("lq-flow-dot-travel"), 1800);
  }

  function celebrate(stepIdx, customMsg) {
    if (stepIdx < 0 || stepIdx > 6) return;
    const step = document.querySelector(`.lq-flow-step[data-step="${stepIdx}"]`);
    const arrow = document.querySelector(
      `.lq-flow-arrow[data-after="${stepIdx}"]`
    );
    document.querySelectorAll(".lq-flow-step").forEach((s) =>
      s.classList.remove("lq-flow-step--active")
    );
    if (step) {
      step.classList.add("lq-flow-step--burst", "lq-flow-step--active");
      spawnParticles(step);
      setTimeout(() => step.classList.remove("lq-flow-step--burst"), 1200);
    }
    if (arrow) {
      arrow.classList.add("lq-flow-arrow--pulse");
      setTimeout(() => arrow.classList.remove("lq-flow-arrow--pulse"), 1600);
    }
    moveDotToStep(stepIdx);
    playChime();
    const msg =
      customMsg ||
      `✓ تم تحديث المسار: ${STEP_EMOJI[stepIdx]} ${STEP_LABELS[stepIdx]}`;
    showToast(msg);
    if (typeof haptic === "function") haptic(10);
    if (typeof window.lqRenderWorkspace === "function") {
      window.lqRenderWorkspace();
      requestAnimationFrame(() => moveDotToStep(stepIdx));
    }
  }

  function stepFromSave(save) {
    if (!save) return -1;
    const t = save.table;
    const row = save.row || {};
    if (t === "clients") return 3;
    if (t === "contracts") return 4;
    if (t === "invoices") return 5;
    if (t === "properties") {
      if (row.room_no) return 2;
      if (row.apartment_no) return 1;
      return 0;
    }
    return -1;
  }

  function diffAndCelebrate(before, after, saveHint) {
    if (!before || !after) return;
    let step = stepFromSave(saveHint);
    if (step < 0) {
      for (let i = 0; i < 7; i++) {
        if (after[i] > before[i]) {
          step = i;
          break;
        }
      }
    }
    if (step >= 0 && after[step] >= before[step]) {
      celebrate(step);
    }
  }

  function ensureSoundToggle() {
    const head = document.querySelector("#lqZoneFlow .lq-zone-head");
    if (!head || document.getElementById("lqFlowSoundBtn")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "lqFlowSoundBtn";
    btn.className = "ghost lq-flow-sound-toggle";
    btn.textContent = soundEnabled() ? "🔊 صوت" : "🔇 صامت";
    btn.onclick = () => {
      const on = localStorage.getItem("lq_flow_sound") === "0";
      localStorage.setItem("lq_flow_sound", on ? "1" : "0");
      btn.textContent = on ? "🔊 صوت" : "🔇 صامت";
    };
    head.appendChild(btn);
  }

  function hookActions() {
    if (typeof saveNew === "function") {
      const orig = saveNew;
      window.saveNew = async function (table, row) {
        window.__lqFlowSaveHint = { table, row };
        return orig.apply(this, arguments);
      };
    }
    if (typeof loadAll === "function") {
      const origLoad = loadAll;
      window.loadAll = async function () {
        const before = snapshot();
        const hint = window.__lqFlowSaveHint;
        window.__lqFlowSaveHint = null;
        await origLoad.apply(this, arguments);
        if (hint) {
          const after = snapshot();
          diffAndCelebrate(before, after, hint);
        }
      };
    }
    if (typeof invoiceFromContract === "function") {
      const orig = invoiceFromContract;
      window.invoiceFromContract = async function (...args) {
        window.__lqFlowSaveHint = { table: "invoices" };
        return orig.apply(this, args);
      };
    }
    if (typeof submitPayment === "function") {
      const orig = submitPayment;
      window.submitPayment = async function () {
        window.__lqFlowSaveHint = { table: "payment" };
        const before = snapshot();
        try {
          await orig.apply(this, arguments);
          const after = snapshot();
          if (after[6] > before[6]) celebrate(6, "✓ تم التحصيل — المسار اكتمل 💰");
        } catch (e) {
          window.__lqFlowSaveHint = null;
        }
      };
    }
  }

  window.LQ_FLOW = {
    snapshot,
    celebrate,
    diffAndCelebrate,
    playChime,
  };

  function init() {
    hookActions();
    window.addEventListener("load", () => {
      setTimeout(ensureSoundToggle, 600);
    });
    document.addEventListener("DOMContentLoaded", () => {
      setTimeout(ensureSoundToggle, 800);
    });
  }

  init();
})();
