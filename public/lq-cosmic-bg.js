/* Launch Quality · animated starfield for cosmic glass theme */
(function () {
  const COUNT = 280;
  let canvas, ctx, stars, anim, w, h;

  function init() {
    canvas = document.getElementById("lqCosmicStars");
    if (!canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    ctx = canvas.getContext("2d");
    resize();
    window.addEventListener("resize", resize);
    draw();
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = Array.from({ length: COUNT }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.3 + 0.25,
      phase: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.018 + 0.004,
      gold: Math.random() < 0.12,
      drift: (Math.random() - 0.5) * 0.06,
    }));
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    stars.forEach((s) => {
      s.phase += s.speed;
      s.x += s.drift;
      if (s.x < 0) s.x = w;
      if (s.x > w) s.x = 0;
      const alpha = 0.25 + Math.sin(s.phase) * 0.35;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      if (s.gold) {
        ctx.fillStyle = `rgba(245, 215, 110, ${alpha})`;
      } else {
        ctx.fillStyle = `rgba(210, 230, 255, ${alpha * 0.9})`;
      }
      ctx.fill();
    });
    anim = requestAnimationFrame(draw);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
