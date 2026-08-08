/* Launch Quality · draggable Walid AI dock */
(function () {
  const KEY = "lq_walid_pos";
  const dock = document.getElementById("visionAiDock");
  if (!dock) return;

  dock.classList.add("lq-walid-free");

  const dragBar = document.createElement("div");
  dragBar.className = "lq-walid-drag-bar";
  dragBar.title = "اسحب لنقل WALEED";
  dragBar.textContent = "⋯ اسحب للنقل ⋯";
  dock.insertBefore(dragBar, dock.firstChild);

  const head = dock.querySelector(".vision-ai-head");
  if (!head) return;

  let dragging = false;
  let offsetX = 0;
  let offsetY = 0;

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function applyPos(x, y) {
    const maxX = window.innerWidth - dock.offsetWidth - 8;
    const maxY = window.innerHeight - dock.offsetHeight - 8;
    const px = clamp(x, 8, maxX);
    const py = clamp(y, 8, maxY);
    dock.style.left = px + "px";
    dock.style.top = py + "px";
    dock.style.right = "auto";
    dock.style.bottom = "auto";
    dock.style.insetInlineStart = "auto";
    return { x: px, y: py };
  }

  function loadPos() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) {
        applyPos(window.innerWidth - dock.offsetWidth - 24, window.innerHeight - dock.offsetHeight - 100);
        return;
      }
      const { x, y } = JSON.parse(raw);
      applyPos(x, y);
    } catch (e) {
      applyPos(24, window.innerHeight - dock.offsetHeight - 100);
    }
  }

  function savePos() {
    const x = parseInt(dock.style.left, 10);
    const y = parseInt(dock.style.top, 10);
    if (!Number.isNaN(x) && !Number.isNaN(y)) {
      localStorage.setItem(KEY, JSON.stringify({ x, y }));
    }
  }

  function onPointerDown(e) {
    if (!e.target.closest(".lq-walid-drag-bar")) return;
    dragging = true;
    dock.classList.add("lq-walid-dragging");
    const rect = dock.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;
    dragBar.setPointerCapture?.(e.pointerId);
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!dragging) return;
    applyPos(e.clientX - offsetX, e.clientY - offsetY);
  }

  function onPointerUp(e) {
    if (!dragging) return;
    dragging = false;
    dock.classList.remove("lq-walid-dragging");
    dragBar.releasePointerCapture?.(e.pointerId);
    savePos();
    haptic(6);
  }

  dragBar.addEventListener("pointerdown", onPointerDown);
  dock.addEventListener("pointermove", onPointerMove);
  dock.addEventListener("pointerup", onPointerUp);
  dock.addEventListener("pointercancel", onPointerUp);

  window.addEventListener("resize", () => {
    const x = parseInt(dock.style.left, 10) || 24;
    const y = parseInt(dock.style.top, 10) || 24;
    applyPos(x, y);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(loadPos, 400));
  } else {
    setTimeout(loadPos, 400);
  }
})();
