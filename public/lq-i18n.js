/**
 * Launch Quality — central i18n (ar, en, hi, bn, ur)
 */
(function () {
  "use strict";

  const STORAGE_KEY = "lq_lang";
  const RTL = new Set(["ar", "ur"]);

  const DICT = {
    ar: {
      appName: "جودة الانطلاقة",
      welcomeBack: "مرحباً بك",
      signInContinue: "سجّل الدخول للوصول إلى حسابك",
      username: "اسم المستخدم",
      password: "كلمة المرور",
      rememberMe: "تذكرني على هذا الجهاز",
      forgotPassword: "نسيت كلمة المرور؟",
      signIn: "دخول",
      support: "الدعم الفني",
      continueGoogle: "المتابعة عبر Google",
      contactSupport: "ليس لديك حساب؟ تواصل مع الدعم",
      choosePlatform: "اختر قسم العمل",
      choosePlatformSub: "سبع منصات متكاملة — اختر مسار عملك",
      realestate: "العقارات",
      realestateDesc: "الوحدات، العملاء، العقود، الفواتير، والصيانة",
      nizwaestate: "عقارات نزوى",
      nizwaestateDesc: "وحدات وعقود نزوى من My program — منصة مستقلة بعد الدخول",
      quickestate: "عقارات نزوى",
      quickestateDesc: "وحدات وعقود نزوى من My program — منصة مستقلة بعد الدخول",
      hospitality: "الضيافة",
      hospitalityDesc: "المجالس، الحجوزات، الخدمات، والمخزن",
      products: "منتجاتنا",
      productsDesc: "المنتجات، الأسعار، المخزون، والمبيعات",
      autotrading: "NAJJAR & AL SAMOOM TRADING",
      autotradingDesc: "سيارات مستعملة ومستوردة — نزوى الفلج",
      overview: "نظرة شاملة",
      overviewDesc: "مؤشرات العقارات والضيافة للإدارة",
      accounting: "المحاسبة",
      accountingDesc: "الفواتير، التحصيل، القيود، والتقارير المالية",
      enter: "دخول",
      language: "اللغة",
      showPassword: "إظهار",
      capsLockOn: "يبدو أن زر Caps Lock مفعّل",
      hidePassword: "إخفاء",
      passwordVisibility: "إظهار أو إخفاء كلمة المرور",
      saveCredentials: "حفظ البيانات وتعبئة تلقائية عند الدخول",
      installApp: "تثبيت التطبيق",
      executiveOverview: "نظرة تنفيذية",
      goodMorning: "مرحباً {name}. هذا ملخص أعمالك اليوم.",
      revenue: "الإيرادات",
      activeUnits: "وحدات مؤجرة",
      occupancy: "الإشغال",
      overdue: "المتأخرات",
      revenueOverTime: "الإيرادات عبر الزمن",
      byChannel: "توزيع الوحدات",
      recentTx: "أحدث المعاملات",
      activity: "النشاط",
      search: "بحث…",
      notifications: "الإشعارات",
      filters: "تصفية",
      timeline: "المسار الزمني",
      loading: "جاري التحميل…",
      empty: "لا توجد بيانات حالياً",
      error: "تعذر التحميل",
      logout: "خروج",
      switchPortal: "تبديل القسم",
      date: "التاريخ",
      client: "العميل",
      amount: "المبلغ",
      status: "الحالة",
      completed: "مكتمل",
      pending: "قيد الانتظار",
      overdueStatus: "متأخر",
    },
    en: {
      appName: "Launch Quality",
      welcomeBack: "Welcome",
      signInContinue: "Sign in to access your account",
      username: "Username",
      password: "Password",
      rememberMe: "Remember me on this device",
      forgotPassword: "Forgot password?",
      signIn: "Sign in",
      support: "Support",
      continueGoogle: "Continue with Google",
      contactSupport: "Don't have an account? Contact support",
      choosePlatform: "Choose your workspace",
      choosePlatformSub: "Seven integrated platforms — choose your path",
      realestate: "Real Estate",
      realestateDesc: "Units, clients, contracts, invoices, and maintenance",
      nizwaestate: "Nizwa Real Estate",
      nizwaestateDesc: "Nizwa units and contracts from My program",
      quickestate: "Nizwa Real Estate",
      quickestateDesc: "Nizwa units and contracts from My program",
      hospitality: "Hospitality",
      hospitalityDesc: "Majlis, bookings, services, and inventory",
      products: "Our Products",
      productsDesc: "Products, pricing, stock, and sales",
      autotrading: "NAJJAR & AL SAMOOM TRADING",
      autotradingDesc: "Used & imported cars — Nizwa Falaj",
      overview: "Executive Overview",
      overviewDesc: "Combined real-estate and hospitality insights",
      accounting: "Accounting",
      accountingDesc: "Invoices, collection, ledgers, and finance reports",
      enter: "Enter",
      language: "Language",
      showPassword: "Show",
      capsLockOn: "Caps Lock appears to be on",
      hidePassword: "Hide",
      passwordVisibility: "Show or hide the password",
      saveCredentials: "Save my details and fill them in next time",
      installApp: "Install app",
      executiveOverview: "Executive Overview",
      goodMorning: "Hello {name}. Here's what's happening today.",
      revenue: "Revenue",
      activeUnits: "Rented units",
      occupancy: "Occupancy",
      overdue: "Overdue",
      revenueOverTime: "Revenue over time",
      byChannel: "Unit mix",
      recentTx: "Recent transactions",
      activity: "Activity",
      search: "Search…",
      notifications: "Notifications",
      filters: "Filters",
      timeline: "Timeline",
      loading: "Loading…",
      empty: "No data yet",
      error: "Could not load",
      logout: "Sign out",
      switchPortal: "Switch section",
      date: "Date",
      client: "Client",
      amount: "Amount",
      status: "Status",
      completed: "Completed",
      pending: "Pending",
      overdueStatus: "Overdue",
    },
    hi: {
      appName: "लॉन्च क्वालिटी",
      welcomeBack: "वापसी पर स्वागत है",
      signInContinue: "अपने खाते में जारी रखने के लिए साइन इन करें",
      username: "उपयोगकर्ता नाम",
      password: "पासवर्ड",
      rememberMe: "मुझे याद रखें",
      forgotPassword: "पासवर्ड भूल गए?",
      signIn: "साइन इन",
      support: "सहायता",
      continueGoogle: "Google से जारी रखें",
      contactSupport: "खाता नहीं है? सहायता से संपर्क करें",
      choosePlatform: "कार्यक्षेत्र चुनें",
      choosePlatformSub: "अपनी भूमिका के अनुसार अनुभाग चुनें",
      realestate: "रियल एस्टेट",
      realestateDesc: "यूनिट, ग्राहक, अनुबंध, चालान और रखरखाव",
      nizwaestate: "निज़वा रियल एस्टेट",
      nizwaestateDesc: "My program से निज़वा यूनिट और अनुबंध",
      quickestate: "निज़वा रियल एस्टेट",
      quickestateDesc: "My program से निज़वा यूनिट और अनुबंध",
      hospitality: "आतिथ्य",
      hospitalityDesc: "मजलिस, बुकिंग, सेवाएँ और इन्वेंटरी",
      products: "हमारे उत्पाद",
      productsDesc: "उत्पाद, मूल्य, स्टॉक और बिक्री",
      autotrading: "NAJJAR & AL SAMOOM TRADING",
      autotradingDesc: "Used & imported cars — Nizwa Falaj",
      overview: "कार्यकारी अवलोकन",
      overviewDesc: "रियल एस्टेट और आतिथ्य का संयुक्त सारांश",
      accounting: "लेखांकन",
      accountingDesc: "चालान, संग्रह, खाते और वित्तीय रिपोर्ट",
      enter: "प्रवेश",
      language: "भाषा",
      showPassword: "दिखाएँ",
      capsLockOn: "लगता है Caps Lock चालू है",
      hidePassword: "छिपाएँ",
      passwordVisibility: "पासवर्ड दिखाएँ या छिपाएँ",
      saveCredentials: "मेरा विवरण सहेजें और अगली बार भर दें",
      installApp: "ऐप इंस्टॉल करें",
      executiveOverview: "कार्यकारी अवलोकन",
      goodMorning: "नमस्ते {name}. आज का सारांश यहाँ है.",
      revenue: "राजस्व",
      activeUnits: "किराए की इकाइयाँ",
      occupancy: "अधिभोग",
      overdue: "बकाया",
      revenueOverTime: "समय के साथ राजस्व",
      byChannel: "यूनिट वितरण",
      recentTx: "हाल के लेनदेन",
      activity: "गतिविधि",
      search: "खोजें…",
      notifications: "सूचनाएँ",
      filters: "फ़िल्टर",
      timeline: "समयरेखा",
      loading: "लोड हो रहा है…",
      empty: "अभी कोई डेटा नहीं",
      error: "लोड नहीं हो सका",
      logout: "साइन आउट",
      switchPortal: "अनुभाग बदलें",
      date: "तारीख",
      client: "ग्राहक",
      amount: "राशि",
      status: "स्थिति",
      completed: "पूर्ण",
      pending: "लंबित",
      overdueStatus: "बकाया",
    },
    bn: {
      appName: "লঞ্চ কোয়ালিটি",
      welcomeBack: "ফিরে আসার জন্য স্বাগতম",
      signInContinue: "আপনার অ্যাকাউন্টে চালিয়ে যেতে সাইন ইন করুন",
      username: "ব্যবহারকারীর নাম",
      password: "পাসওয়ার্ড",
      rememberMe: "মনে রাখুন",
      forgotPassword: "পাসওয়ার্ড ভুলে গেছেন?",
      signIn: "সাইন ইন",
      support: "সহায়তা",
      continueGoogle: "Google দিয়ে চালিয়ে যান",
      contactSupport: "অ্যাকাউন্ট নেই? সহায়তায় যোগাযোগ করুন",
      choosePlatform: "কর্মক্ষেত্র বেছে নিন",
      choosePlatformSub: "আপনার ভূমিকা অনুযায়ী বিভাগ নির্বাচন করুন",
      realestate: "রিয়েল এস্টেট",
      realestateDesc: "ইউনিট, ক্লায়েন্ট, চুক্তি, চালান ও রক্ষণাবেক্ষণ",
      nizwaestate: "নিজওয়া রিয়েল এস্টেট",
      nizwaestateDesc: "My program থেকে নিজওয়া ইউনিট ও চুক্তি",
      quickestate: "নিজওয়া রিয়েল এস্টেট",
      quickestateDesc: "My program থেকে নিজওয়া ইউনিট ও চুক্তি",
      hospitality: "আতিথেয়তা",
      hospitalityDesc: "মজলিস, বুকিং, সেবা ও ইনভেন্টরি",
      products: "আমাদের পণ্য",
      productsDesc: "পণ্য, মূল্য, স্টক ও বিক্রয়",
      autotrading: "NAJJAR & AL SAMOOM TRADING",
      autotradingDesc: "Used & imported cars — Nizwa Falaj",
      overview: "নির্বাহী সংক্ষিপ্তসার",
      overviewDesc: "রিয়েল এস্টেট ও আতিথেয়তার সম্মিলিত দৃশ্য",
      accounting: "হিসাবরক্ষণ",
      accountingDesc: "চালান, আদায়, খাতা ও আর্থিক প্রতিবেদন",
      enter: "প্রবেশ",
      language: "ভাষা",
      showPassword: "দেখান",
      capsLockOn: "মনে হচ্ছে Caps Lock চালু আছে",
      hidePassword: "লুকান",
      passwordVisibility: "পাসওয়ার্ড দেখান বা লুকান",
      saveCredentials: "আমার তথ্য সংরক্ষণ করে পরেরবার বসিয়ে দিন",
      installApp: "অ্যাপ ইনস্টল করুন",
      executiveOverview: "নির্বাহী সংক্ষিপ্তসার",
      goodMorning: "হ্যালো {name}. আজকের সারাংশ এখানে.",
      revenue: "আয়",
      activeUnits: "ভাড়া ইউনিট",
      occupancy: "দখল",
      overdue: "বকেয়া",
      revenueOverTime: "সময় অনুযায়ী আয়",
      byChannel: "ইউনিট বিন্যাস",
      recentTx: "সাম্প্রতিক লেনদেন",
      activity: "কার্যকলাপ",
      search: "অনুসন্ধান…",
      notifications: "বিজ্ঞপ্তি",
      filters: "ফিল্টার",
      timeline: "টাইমলাইন",
      loading: "লোড হচ্ছে…",
      empty: "এখনো কোনো তথ্য নেই",
      error: "লোড করা যায়নি",
      logout: "সাইন আউট",
      switchPortal: "বিভাগ পরিবর্তন",
      date: "তারিখ",
      client: "ক্লায়েন্ট",
      amount: "পরিমাণ",
      status: "অবস্থা",
      completed: "সম্পন্ন",
      pending: "মুলতবি",
      overdueStatus: "বকেয়া",
    },
    ur: {
      appName: "جودة الانطلاقة",
      welcomeBack: "خوش آمدید",
      signInContinue: "اپنے اکاؤنٹ میں جاری رکھنے کے لیے سائن ان کریں",
      username: "صارف نام",
      password: "پاس ورڈ",
      rememberMe: "مجھے یاد رکھیں",
      forgotPassword: "پاس ورڈ بھول گئے؟",
      signIn: "سائن ان",
      support: "سپورٹ",
      continueGoogle: "Google کے ساتھ جاری رکھیں",
      contactSupport: "اکاؤنٹ نہیں ہے؟ سپورٹ سے رابطہ کریں",
      choosePlatform: "کام کا شعبہ منتخب کریں",
      choosePlatformSub: "اپنے کردار کے مطابق سیکشن منتخب کریں",
      realestate: "ریئل اسٹیٹ",
      realestateDesc: "یونٹس، کلائنٹس، معاہدے، بل اور مرمت",
      nizwaestate: "نزویٰ ریئل اسٹیٹ",
      nizwaestateDesc: "My program سے نزویٰ یونٹس اور معاہدے",
      quickestate: "نزویٰ ریئل اسٹیٹ",
      quickestateDesc: "My program سے نزویٰ یونٹس اور معاہدے",
      hospitality: "مہمان نوازی",
      hospitalityDesc: "مجالس، بکنگ، خدمات اور اسٹاک",
      products: "ہماری مصنوعات",
      productsDesc: "مصنوعات، قیمتیں، اسٹاک اور فروخت",
      autotrading: "NAJJAR & AL SAMOOM TRADING",
      autotradingDesc: "Used & imported cars — Nizwa Falaj",
      overview: "انتظامی جائزہ",
      overviewDesc: "ریئل اسٹیٹ اور مہمان نوازی کا مجموعی منظر",
      accounting: "اکاؤنٹنگ",
      accountingDesc: "بل، وصولی، کھاتہ اور مالیاتی رپورٹس",
      enter: "داخلہ",
      language: "زبان",
      showPassword: "دکھائیں",
      capsLockOn: "ایسا لگتا ہے Caps Lock آن ہے",
      hidePassword: "چھپائیں",
      passwordVisibility: "پاس ورڈ دکھائیں یا چھپائیں",
      saveCredentials: "میری تفصیلات محفوظ کر کے اگلی بار بھر دیں",
      installApp: "ایپ انسٹال کریں",
      executiveOverview: "انتظامی جائزہ",
      goodMorning: "ہیلو {name}. آج کا خلاصہ یہ ہے.",
      revenue: "آمدنی",
      activeUnits: "کرائے کی یونٹس",
      occupancy: "قبضہ",
      overdue: "واجب الادا",
      revenueOverTime: "وقت کے ساتھ آمدنی",
      byChannel: "یونٹ تقسیم",
      recentTx: "حالیہ لین دین",
      activity: "سرگرمی",
      search: "تلاش…",
      notifications: "اطلاعات",
      filters: "فلٹر",
      timeline: "ٹائم لائن",
      loading: "لوڈ ہو رہا ہے…",
      empty: "ابھی کوئی ڈیٹا نہیں",
      error: "لوڈ نہیں ہو سکا",
      logout: "سائن آؤٹ",
      switchPortal: "سیکشن بدلیں",
      date: "تاریخ",
      client: "کلائنٹ",
      amount: "رقم",
      status: "حالت",
      completed: "مکمل",
      pending: "زیر التواء",
      overdueStatus: "واجب الادا",
    },
  };

  function savedLang() {
    try {
      const stored = (localStorage.getItem(STORAGE_KEY) || "").trim().toLowerCase();
      if (DICT[stored]) return stored;
    } catch (_) {/* storage can be unavailable */}
    // The cookie copy is the one that survives a site-data wipe. Without it an
    // Arabic-speaking office would be handed an English interface the first time
    // a device is cleaned, because the fallback below reads the machine's locale.
    try {
      const m = document.cookie.match(/(?:^|;\s*)lq_lang=([^;]+)/);
      const fromCookie = m ? decodeURIComponent(m[1]).trim().toLowerCase() : "";
      if (DICT[fromCookie]) return fromCookie;
    } catch (_) {/* ignore */}
    return "";
  }

  function detectLang() {
    const saved = savedLang();
    if (DICT[saved]) return saved;
    const nav = String(navigator.language || "ar").toLowerCase();
    if (nav.startsWith("ar")) return "ar";
    if (nav.startsWith("ur")) return "ur";
    if (nav.startsWith("hi")) return "hi";
    if (nav.startsWith("bn")) return "bn";
    if (nav.startsWith("en")) return "en";
    return "ar";
  }

  let lang = detectLang();

  function t(key, vars) {
    const pack = DICT[lang] || DICT.ar;
    let s = pack[key] || DICT.en[key] || DICT.ar[key] || key;
    if (vars && typeof vars === "object") {
      Object.keys(vars).forEach((k) => {
        s = s.replace(new RegExp("\\{" + k + "\\}", "g"), String(vars[k] ?? ""));
      });
    }
    return s;
  }

  const LOCALES = { ar: "ar-OM", en: "en-OM", hi: "hi-IN", bn: "bn-BD", ur: "ur-PK" };
  /* Digits appropriate to each language script */
  const NUM_SYS = { ar: "arab", en: "latn", hi: "latn", bn: "beng", ur: "arab" };

  function translatePass() {
    const html = document.documentElement;
    html.lang = lang;
    html.dir = RTL.has(lang) ? "rtl" : "ltr";
    document.body?.setAttribute("data-lq-lang", lang);
    html.setAttribute("data-lq-num", NUM_SYS[lang] || "latn");
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      const val = t(key);
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
        el.setAttribute("placeholder", val);
      } else {
        el.textContent = val;
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
    });
    return html.dir;
  }

  /* Several screens rebuild their own markup on "lq:langchange" and then ask for
     another pass, so an unguarded dispatch here recurses until the stack blows.
     A re-entrant call is collapsed into a single extra pass that translates the
     freshly injected markup without announcing the change a second time. */
  let applying = false;
  let passQueued = false;

  function applyDocument() {
    if (applying) {
      passQueued = true;
      return;
    }
    applying = true;
    try {
      const dir = translatePass();
      document.dispatchEvent(new CustomEvent("lq:langchange", { detail: { lang, dir, num: NUM_SYS[lang] || "latn" } }));
      if (passQueued) translatePass();
    } finally {
      passQueued = false;
      applying = false;
    }
  }

  function setLang(next) {
    const n = String(next || "").toLowerCase();
    if (!DICT[n]) return lang;
    lang = n;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch (_) {/* storage can be unavailable */}
    try {
      document.cookie =
        STORAGE_KEY + "=" + encodeURIComponent(lang) +
        "; Path=/; Max-Age=31536000; SameSite=Lax";
    } catch (_) {/* ignore */}
    applyDocument();
    return lang;
  }

  function formatNumber(n, opts) {
    try {
      return new Intl.NumberFormat(LOCALES[lang] || "en-OM", {
        numberingSystem: NUM_SYS[lang] || "latn",
        maximumFractionDigits: 3,
        ...(opts || {}),
      }).format(Number(n || 0));
    } catch (_) {
      return String(Number(n || 0));
    }
  }

  function formatMoney(n, currency) {
    try {
      return new Intl.NumberFormat(LOCALES[lang] || "en-OM", {
        style: "currency",
        currency: currency || "OMR",
        numberingSystem: NUM_SYS[lang] || "latn",
        maximumFractionDigits: 3,
      }).format(Number(n || 0));
    } catch (_) {
      return "OMR " + formatNumber(n);
    }
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      return new Intl.DateTimeFormat(LOCALES[lang] || "en-GB", {
        year: "numeric",
        month: "short",
        day: "numeric",
        numberingSystem: NUM_SYS[lang] || "latn",
      }).format(new Date(String(iso).slice(0, 10) + "T00:00:00"));
    } catch (_) {
      return String(iso).slice(0, 10);
    }
  }

  function langSwitcherHtml(id) {
    const opts = [
      ["ar", "العربية"],
      ["en", "English"],
      ["hi", "हिन्दी"],
      ["bn", "বাংলা"],
      ["ur", "اردو"],
    ];
    /* The switcher outlives a language change — rebuilding it would destroy the
       <select> mid-event — so its own caption is tagged for the next pass. */
    return `<label class="lq-lang-switch" for="${id}"><span data-i18n="language">${t("language")}</span>
      <select id="${id}" data-i18n-aria="language" aria-label="${t("language")}">
        ${opts.map(([c, l]) => `<option value="${c}" ${c === lang ? "selected" : ""}>${l}</option>`).join("")}
      </select></label>`;
  }

  function bindSwitcher(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = lang;
    el.onchange = () => setLang(el.value);
  }

  window.LQ_I18N = {
    t,
    setLang,
    getLang: () => lang,
    isRtl: () => RTL.has(lang),
    applyDocument,
    formatNumber,
    formatMoney,
    formatDate,
    langSwitcherHtml,
    bindSwitcher,
    DICT,
    NUM_SYS,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyDocument);
  } else {
    applyDocument();
  }
})();
