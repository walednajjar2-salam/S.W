/* Phase 8 — WALEED optional voice: speak replies + microphone input */
(function () {
  const VOICE_ON_KEY = "lq_waleed_voice";
  const voicesReady = { done: false };

  function voiceOn() {
    return localStorage.getItem(VOICE_ON_KEY) === "1";
  }

  function setVoiceOn(on) {
    localStorage.setItem(VOICE_ON_KEY, on ? "1" : "0");
    syncToggleUi();
  }

  function stripForSpeech(text) {
    return String(text || "")
      .replace(/<[^>]+>/g, " ")
      .replace(/&[a-z]+;/gi, " ")
      .replace(/^(WALEED|Walid)\s*\([^)]*\)\s*:\s*/i, "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 600);
  }

  function pickVoice() {
    if (!window.speechSynthesis) return null;
    const voices = speechSynthesis.getVoices();
    return (
      voices.find((v) => v.lang && v.lang.startsWith("ar")) ||
      voices.find((v) => v.lang && v.lang.startsWith("en")) ||
      voices[0] ||
      null
    );
  }

  function ensureVoices() {
    if (!window.speechSynthesis) return;
    if (speechSynthesis.getVoices().length) {
      voicesReady.done = true;
      return;
    }
    speechSynthesis.addEventListener("voiceschanged", () => {
      voicesReady.done = true;
    });
  }

  function speak(text) {
    if (!voiceOn() || !window.speechSynthesis) return;
    const say = stripForSpeech(text);
    if (!say) return;
    try {
      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(say);
      utter.lang = "ar-SA";
      const voice = pickVoice();
      if (voice) utter.voice = voice;
      utter.rate = 0.95;
      utter.pitch = 1;
      speechSynthesis.speak(utter);
    } catch (e) {
      /* ignore TTS errors */
    }
  }

  window.lqWaleedSpeak = speak;

  function injectControls() {
    const compose = document.querySelector("#visionAiDock .vision-ai-compose");
    if (!compose || document.getElementById("visionAiMic")) return;

    const mic = document.createElement("button");
    mic.type = "button";
    mic.id = "visionAiMic";
    mic.className = "ghost lq-voice-btn";
    mic.title = "تحدث مع WALEED";
    mic.setAttribute("aria-label", "تحدث مع WALEED");
    mic.textContent = "🎤";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = "visionAiSpeakToggle";
    toggle.className = "ghost lq-voice-btn";
    toggle.title = "تفعيل / إيقاف صوت WALEED";
    toggle.setAttribute("aria-label", "صوت WALEED");
    toggle.textContent = "🔇";

    const send = document.getElementById("visionAiSend");
    if (send) compose.insertBefore(mic, send);
    compose.insertBefore(toggle, send || null);

    const hint = document.createElement("p");
    hint.id = "lqVoiceHint";
    hint.className = "lq-voice-hint mini hidden";
    compose.parentElement?.insertBefore(hint, compose.nextSibling);

    toggle.onclick = () => {
      setVoiceOn(!voiceOn());
      if (voiceOn()) {
        speak("صوت WALEED مفعّل — اسألني أي شيء");
        if (typeof haptic === "function") haptic(6);
      }
    };

    bindMic(mic, hint);
    syncToggleUi();
  }

  function syncToggleUi() {
    const toggle = document.getElementById("visionAiSpeakToggle");
    if (!toggle) return;
    const on = voiceOn();
    toggle.textContent = on ? "🔊" : "🔇";
    toggle.classList.toggle("active", on);
    toggle.title = on ? "إيقاف صوت WALEED" : "تفعيل صوت WALEED";
  }

  function bindMic(btn, hint) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      btn.disabled = true;
      btn.title = "الإدخال الصوتي غير متاح في هذا المتصفح";
      return;
    }

    const rec = new SR();
    rec.lang = "ar-SA";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    let listening = false;

    function setListening(on) {
      listening = on;
      btn.classList.toggle("listening", on);
      btn.textContent = on ? "⏹" : "🎤";
      if (hint) {
        hint.classList.toggle("hidden", !on);
        hint.textContent = on ? "استمع… تحدث الآن ثم اضغط مرة أخرى للإيقاف" : "";
      }
    }

    btn.onclick = () => {
      if (listening) {
        try {
          rec.stop();
        } catch (e) {
          setListening(false);
        }
        return;
      }
      try {
        rec.start();
        setListening(true);
        if (typeof haptic === "function") haptic(4);
      } catch (e) {
        setListening(false);
        if (typeof toastNotice === "function") toastNotice("تعذر تشغيل الميكروفون");
      }
    };

    rec.onresult = (ev) => {
      const text = ev.results?.[0]?.[0]?.transcript || "";
      const input = document.getElementById("visionAiInput");
      if (input && text) input.value = text.trim();
      setListening(false);
      if (text.trim()) {
        const send = document.getElementById("visionAiSend");
        if (send) send.click();
      }
    };

    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
  }

  function patchAsk() {
    if (window.LQ_WALID_INTEL && typeof window.LQ_WALID_INTEL.ask === "function" && !window.LQ_WALID_INTEL.__voicePatched) {
      const orig = window.LQ_WALID_INTEL.ask;
      window.LQ_WALID_INTEL.ask = async function (question) {
        await orig.apply(this, arguments);
        const body = document.getElementById("visionAiBody");
        const last = body?.querySelector(".vision-ai-msg.pred:last-of-type");
        if (last) speak(last.textContent);
      };
      window.LQ_WALID_INTEL.__voicePatched = true;
    }

    if (typeof window.submitVisionAi === "function" && !window.submitVisionAi.__voicePatched) {
      const origSubmit = window.submitVisionAi;
      window.submitVisionAi = async function (question) {
        await origSubmit.apply(this, arguments);
        const body = document.getElementById("visionAiBody");
        const msgs = body?.querySelectorAll(".vision-ai-msg.pred");
        const last = msgs?.[msgs.length - 1];
        if (last) speak(last.textContent);
      };
      window.submitVisionAi.__voicePatched = true;
    }
  }

  function init() {
    ensureVoices();
    injectControls();
    patchAsk();

    if (typeof initAiDock === "function") {
      const orig = initAiDock;
      window.initAiDock = function () {
        orig.apply(this, arguments);
        injectControls();
        syncToggleUi();
      };
    }

    document.addEventListener("visibilitychange", () => {
      if (document.hidden && window.speechSynthesis) speechSynthesis.cancel();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.addEventListener("load", () => {
    setTimeout(patchAsk, 300);
    injectControls();
  });
})();
