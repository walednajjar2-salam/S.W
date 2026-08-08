(function () {
  'use strict';

  var HIDDEN_AUTH = ['face', 'fingerprint', 'sso'];

  function hideFutureAuth() {
    document.querySelectorAll('.ev-auth-tab').forEach(function (tab) {
      var mode = tab.dataset.auth;
      if (HIDDEN_AUTH.indexOf(mode) !== -1) {
        tab.classList.add('lq-auth-hidden');
        tab.setAttribute('aria-hidden', 'true');
      }
    });
    var tabs = document.querySelector('.ev-auth-tabs');
    if (tabs && !tabs.querySelector('.ev-auth-note')) {
      var note = document.createElement('p');
      note.className = 'ev-auth-note';
      note.textContent =
        'الدخول المتاح: كلمة المرور و OTP. Face ID و SSO قريباً في التحديث المؤسسي.';
      tabs.insertAdjacentElement('afterend', note);
    }
  }

  function openSectionFromUrl() {
    var params = new URLSearchParams(location.search);
    var section = (params.get('section') || '').trim();
    if (!section || section === 'dashboard') return;
    var app = document.getElementById('app');
    if (!app || app.classList.contains('hidden')) return;
    if (typeof window.showSection === 'function') {
      window.showSection(section);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    hideFutureAuth();
    setTimeout(openSectionFromUrl, 400);
  });
})();
