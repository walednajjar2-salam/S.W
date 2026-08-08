/* WALEED — personal assistant persona */
(function () {
  function personalize() {
    const body = document.getElementById("visionAiBody");
    const headTitle = document.querySelector("#visionAiDock h4");
    if (headTitle) headTitle.textContent = "WALEED · المساعد الشخصي";

    const input = document.getElementById("visionAiInput");
    if (input) input.placeholder = "اسأل WALEED · تحدث معي…";

    if (!body || typeof displayUserName !== "function") return;
    const name = displayUserName(window.Jawdah?.user) || "زميلي";
    const role =
      typeof displayUserRole === "function"
        ? displayUserRole(window.Jawdah?.user)
        : window.Jawdah?.user?.role || "";
    const greet = `مرحباً ${name} — أنا WALEED، معك شخصياً. أطمئنك: العمل منظم والبيانات محدثة. دورك: ${role}. اسألني عن أي شيء.`;
    const first = body.querySelector(".vision-ai-msg");
    if (first) first.textContent = greet;
    else
      body.insertAdjacentHTML(
        "afterbegin",
        `<div class="vision-ai-msg pred">${greet}</div>`
      );
  }

  window.addEventListener("load", () => {
    if (typeof refreshVisionAi === "function") {
      const orig = refreshVisionAi;
      window.refreshVisionAi = function () {
        orig.apply(this, arguments);
        personalize();
      };
    }
    personalize();
  });
})();
