/** NAJJAR session storage — replaces legacy jawdah_/lq_ keys. */
(function (global) {
  const TOKEN_KEY = 'najjar_auth_token';
  const PORTAL_KEY = 'najjar_portal';
  const LEGACY_TOKEN_KEYS = ['jawdah_cloud_token', 'lq_cloud_token'];
  const LEGACY_PORTAL_KEYS = ['jawdah_portal_choice', 'lq_portal_choice'];
  const LEGACY_COOKIE = /(?:^|;\s*)lq_token=([^;]+)/;

  function readCookieToken() {
    try {
      const m = document.cookie.match(LEGACY_COOKIE);
      return m ? decodeURIComponent(m[1]).trim() : '';
    } catch (_) {
      return '';
    }
  }

  function getToken() {
    try {
      let t = (localStorage.getItem(TOKEN_KEY) || '').trim();
      if (t) return t;
      for (const k of LEGACY_TOKEN_KEYS) {
        t = (localStorage.getItem(k) || '').trim();
        if (t) {
          localStorage.setItem(TOKEN_KEY, t);
          localStorage.removeItem(k);
          return t;
        }
      }
      t = readCookieToken();
      if (t) {
        localStorage.setItem(TOKEN_KEY, t);
        return t;
      }
    } catch (_) {/* ignore */}
    return '';
  }

  function setToken(token) {
    const v = String(token || '').trim();
    try {
      if (v) localStorage.setItem(TOKEN_KEY, v);
      else localStorage.removeItem(TOKEN_KEY);
      LEGACY_TOKEN_KEYS.forEach((k) => localStorage.removeItem(k));
    } catch (_) {/* ignore */}
    return v;
  }

  function clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      LEGACY_TOKEN_KEYS.forEach((k) => localStorage.removeItem(k));
      LEGACY_PORTAL_KEYS.forEach((k) => localStorage.removeItem(k));
      document.cookie = 'najjar_token=; Path=/; Max-Age=0; SameSite=Lax';
      document.cookie = 'lq_token=; Path=/; Max-Age=0; SameSite=Lax';
    } catch (_) {/* ignore */}
  }

  function setPortal(value) {
    try {
      localStorage.setItem(PORTAL_KEY, String(value || 'autotrading'));
      LEGACY_PORTAL_KEYS.forEach((k) => localStorage.removeItem(k));
    } catch (_) {/* ignore */}
  }

  function purgeLegacyBrandStorage() {
    const wipePrefix = (prefix) => {
      try {
        const keys = [];
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k && k.startsWith(prefix)) keys.push(k);
        }
        keys.forEach((k) => localStorage.removeItem(k));
      } catch (_) {/* ignore */}
    };
    wipePrefix('lq_');
    wipePrefix('jawdah_');
    LEGACY_TOKEN_KEYS.forEach((k) => localStorage.removeItem(k));
    LEGACY_PORTAL_KEYS.forEach((k) => localStorage.removeItem(k));
  }

  global.NajjarAuth = {
    TOKEN_KEY,
    getToken,
    setToken,
    clearToken,
    setPortal,
    purgeLegacyBrandStorage,
  };
})(window);
