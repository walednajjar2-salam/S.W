#!/usr/bin/env python3
"""
NAJJAR & AL SAMOOM TRADING
Used & imported cars — web platform backend.
Run: python server.py
"""
from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lq_expand.offsite import offsite_config, push_offsite_backup
from lq_expand import object_storage as lq_object_storage
import lq_payroll_import
import lq_postgres
import lq_business_catalog
import lq_quick_estate
import lq_auto_trading
from lq_expand.openapi import build_openapi_spec
from lq_expand.security import (
    device_trust_days,
    generate_totp_secret,
    mfa_enforce_mode,
    normalize_device_fingerprint,
    otp_login_enabled,
    password_needs_rotation,
    pending_login_ttl_seconds,
    resolve_bootstrap_password,
    resolve_user_email,
    role_requires_mfa,
    security_platform_status,
    security_status_payload,
    smtp_configured,
    totp_provisioning_uri,
    validate_new_password,
    verify_totp,
)

try:
    from fido2.server import Fido2Server
    from fido2.webauthn import (
        AttestationObject,
        AttestedCredentialData,
        AuthenticatorData,
        PublicKeyCredentialRpEntity,
    )
    try:
        from fido2.client import CollectedClientData
    except Exception:
        from fido2.webauthn import CollectedClientData  # type: ignore
    FIDO2_AVAILABLE = True
except Exception:
    Fido2Server = None  # type: ignore
    AttestationObject = None  # type: ignore
    AttestedCredentialData = None  # type: ignore
    AuthenticatorData = None  # type: ignore
    PublicKeyCredentialRpEntity = None  # type: ignore
    CollectedClientData = None  # type: ignore
    FIDO2_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = Path(os.environ.get("JAWDAH_DATA_DIR", str(BASE_DIR / "data"))).resolve()
DB_PATH = Path(os.environ.get("JAWDAH_DB_PATH", str(DATA_DIR / "jawdah.sqlite3"))).resolve()
UPLOAD_DIR = Path(os.environ.get("JAWDAH_UPLOAD_DIR", str(DATA_DIR / "uploads"))).resolve()
PROPERTY_PHOTO_DIR = UPLOAD_DIR / "properties"
WORK_JOURNAL_DIR = UPLOAD_DIR / "work_journal"
CLIENT_CARD_DIR = UPLOAD_DIR / "client_cards"
PAYMENT_PROOF_DIR = UPLOAD_DIR / "payment_proofs"
CONTRACT_ATTACHMENT_DIR = UPLOAD_DIR / "contracts"
MAX_PROPERTY_PHOTO_BYTES = int(os.environ.get("JQ_MAX_PROPERTY_PHOTO_BYTES", "5242880") or "5242880")
MAX_JOURNAL_FILE_BYTES = int(os.environ.get("LQ_MAX_JOURNAL_FILE_BYTES", "2097152") or "2097152")
MAX_CLIENT_CARD_BYTES = int(os.environ.get("LQ_MAX_CLIENT_CARD_BYTES", "5242880") or "5242880")
MAX_PAYMENT_PROOF_BYTES = int(os.environ.get("LQ_MAX_PAYMENT_PROOF_BYTES", "5242880") or "5242880")
MAX_JOURNAL_FILES_PER_ENTRY = 5
HOST = os.environ.get("JAWDAH_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT") or os.environ.get("JAWDAH_PORT", "8765"))
CORS_ORIGIN = os.environ.get("JAWDAH_CORS_ORIGIN", "*").strip()
LIVE_STREAM_INTERVAL_SEC = max(1, int(os.environ.get("LQ_LIVE_STREAM_INTERVAL_SEC", "2") or "2"))
APP_VERSION = "Launch-Quality-LLC-v71.0-stock-integrity"
# Production baseline family: v71.0 = live showroom feed, protected stock records,
# cost-of-sales profit. v72 retires the Launch Quality ERP shell — NAJJAR is the
# only staff-facing product; old /app.html entry points redirect here.
RELEASE_CHANNEL = "stable"
STABLE_RELEASE = True
STABLE_TAG = "v71.0-stock-integrity"
# A device that installed an earlier build keeps serving that build from its own
# service worker cache, so shipping a release never reaches it — the old shell
# answers before the network does. Bumping this generation makes the next page
# load from each device hand back Clear-Site-Data once, which is the only lever
# that deletes a worker the page's own scripts can no longer reach. The marker
# cookie is what keeps it to once: Clear-Site-Data "storage" spares cookies, so
# the very response that purges the device also records that it was purged.
CLIENT_PURGE_GENERATION = os.environ.get("LQ_CLIENT_PURGE", "v81-najjar-no-lq").strip()
CLIENT_PURGE_COOKIE = "najjar_purge"
# "cookies" is deliberately absent, for two reasons: it would take the marker
# cookie with it and re-purge on every navigation, and it would drop lq_token,
# which is what carries a signed-in user across the purge.
# "executionContexts" is absent because Chrome does not implement it — measured,
# not assumed: adding it changed nothing about when the fresh build appeared, and
# a directive that only takes effect in some other browser is a reload risk with
# no benefit here.
CLIENT_PURGE_DIRECTIVES = '"cache", "storage"'
# When off, the ERP shell and legacy entry points stay hidden. NAJJAR can still be
# published on its own base path (see NAJJAR_PUBLISHED). Set LQ_SITE_PUBLISHED=1 on
# Railway to turn the full public site face back on.
SITE_PUBLISHED = os.environ.get("LQ_SITE_PUBLISHED", "0").strip().lower() in ("1", "true", "yes", "on")
SITE_CLOSED_URL = "/closed"
# NAJJAR lives under its own URL prefix — not / and not /auto-trading/*.html.
NAJJAR_BASE = (
    os.environ.get("LQ_NAJJAR_BASE", "/najjar-al-samoom-used-imported-cars").strip().rstrip("/")
    or "/najjar-al-samoom-used-imported-cars"
)
# Older short prefix — 301 to NAJJAR_BASE so bookmarks keep working.
NAJJAR_LEGACY_BASES = (
    "/najjar",
    "/najjar-al-samoom",
)
NAJJAR_PUBLISHED = os.environ.get("LQ_NAJJAR_PUBLISHED", "1").strip().lower() in ("1", "true", "yes", "on")
# Launch Quality ERP is retired — NAJJAR is the only live product. Set LQ_ERP_PUBLISHED=1
# only for emergency maintenance of legacy data (never on public Railway).
ERP_PUBLISHED = os.environ.get("LQ_ERP_PUBLISHED", "0").strip().lower() in ("1", "true", "yes", "on")
NAJJAR_HOME = f"{NAJJAR_BASE}/customer.html"
NAJJAR_LOGIN = f"{NAJJAR_BASE}/login.html"
NAJJAR_PLATFORMS = f"{NAJJAR_BASE}/platforms.html"
NAJJAR_STAFF = f"{NAJJAR_BASE}/staff.html"
COMPANY_NAME = "NAJJAR & AL SAMOOM TRADING"
COMPANY_NAME_AR = "نجار & سموم للتجارة"
SESSION_COOKIE = "najjar_token"
LEGACY_SESSION_COOKIE = "lq_token"
NAJJAR_API_ROOTS = frozenset({"auto-trading", "login", "me", "logout", "biometric"})
NAJJAR_TEAM_USERNAMES = frozenset({
    "waleed.najjar", "hamad.sumoom", "sara", "sales", "accounting",
})
# Easy local/team passwords (1–5). Env LQ_USER_PASSWORD_<USER> still overrides.
NAJJAR_TEAM_BOOTSTRAP = (
    ("waleed.najjar", "Walid Najjar", "owner", "1"),
    ("hamad.sumoom", "Hamad Al Samoom", "owner", "2"),
    ("sara", "Sara", "operations", "3"),
    ("sales", "Sales", "sales", "4"),
    ("accounting", "Accounting", "accountant", "5"),
)
# Legacy ERP HTML — never served when ERP_PUBLISHED=0.
_RETIRED_ERP_PAGES = frozenset({
    "/app.html", "/app", "/app/", "/app/app.html",
    "/portal-select.html", "/portal-select",
    "/Launch_Quality_LLC.html", "/Launch Quality LLC.html",
    "/install.html", "/download.html", "/docs.html",
    "/quick-estate.html", "/index.html", "/go.html", "/start.html",
    "/erp", "/erp.html",
    "/auto-trading.html",
})
# Download hubs stay public while NAJJAR is live (even if old ERP face is closed).
_NAJJAR_DOWNLOAD_PAGES = frozenset({
    "/get-windows.html", "/get-android.html",
    "/get-windows", "/get-android",
    "/تحميل-ويندوز", "/تحميل-اندرويد",
    "/download-windows", "/download-android",
    "/windows-setup", "/android-apk",
})


def _najjar_legacy_redirect(path: str) -> Optional[str]:
    """Map legacy /najjar/* URLs to the canonical English NAJJAR_BASE."""
    for legacy in NAJJAR_LEGACY_BASES:
        if path == legacy or path == legacy + "/":
            return NAJJAR_HOME
        if path.startswith(legacy + "/"):
            suffix = path[len(legacy):]
            if suffix in ("/login", "/platforms", "/staff"):
                suffix += ".html"
            return NAJJAR_BASE + suffix
    return None


def _najjar_page_file(path: str) -> Optional[str]:
    """Map a public NAJJAR URL to a file under public/."""
    mapping = {
        NAJJAR_BASE: "auto-trading/customer.html",
        NAJJAR_BASE + "/": "auto-trading/customer.html",
        NAJJAR_BASE + "/customer.html": "auto-trading/customer.html",
        NAJJAR_BASE + "/login.html": "auto-trading/login.html",
        NAJJAR_BASE + "/login": "auto-trading/login.html",
        NAJJAR_BASE + "/platforms.html": "auto-trading/platforms.html",
        NAJJAR_BASE + "/platforms": "auto-trading/platforms.html",
        NAJJAR_STAFF: "auto-trading.html",
        NAJJAR_BASE + "/staff": "auto-trading.html",
        "/najjar-login": "auto-trading/login.html",
        "/دخول-النجار": "auto-trading/login.html",
        "/النجار": "auto-trading/customer.html",
        "/سيارات": "auto-trading/customer.html",
    }
    if path in mapping:
        return mapping[path]
    if path.rstrip("/") == NAJJAR_BASE:
        return "auto-trading/customer.html"
    return None


def _is_najjar_public_path(path: str) -> bool:
    return _najjar_page_file(path) is not None or path in (NAJJAR_BASE, NAJJAR_BASE + "/")


def _is_auto_trading_asset(safe: str) -> bool:
    if not safe.startswith("auto-trading/"):
        return False
    leaf = safe.rsplit("/", 1)[-1]
    return not leaf.endswith(".html")


def _is_najjar_brand_asset(safe: str) -> bool:
    """Allow /assets/* brand media while the old ERP site face stays closed."""
    if not safe.startswith("assets/"):
        return False
    leaf = safe.rsplit("/", 1)[-1].lower()
    return leaf.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".gif"))


def _is_najjar_download_asset(path: str, safe: str) -> bool:
    """Windows/Android installers and release files for staff devices."""
    if path in _NAJJAR_DOWNLOAD_PAGES:
        return True
    if safe in (
        "get-windows.html", "get-android.html",
        "NAJJAR-Trading.exe", "NAJJAR-Trading-Windows.zip",
        "LaunchQuality.exe", "lq-portable.zip",
        "lq-setup.exe", "windows-setup.exe",
    ):
        return True
    if safe.startswith("releases/windows/") or safe.startswith("releases/android/"):
        return True
    leaf = safe.rsplit("/", 1)[-1].lower()
    return leaf.endswith((".exe", ".zip", ".apk", ".ps1", ".bat", ".vbs", ".json", ".ico", ".url", ".txt")) and (
        safe.startswith("releases/") or safe.startswith("downloads/")
    )


def _najjar_api_allowed(parts: list) -> bool:
    return bool(parts) and parts[0] in NAJJAR_API_ROOTS
# DB seed policy stays "official" by default (no sample seed in production).
APP_EDITION = os.environ.get("LQ_EDITION", "official").strip().lower() or "official"
# Product base edition — التطوير المؤسسي is the default foundation for UI + health.
APP_BASE_EDITION = os.environ.get("LQ_BASE_EDITION", "terrifying-dev").strip().lower() or "terrifying-dev"
APP_EDITION_LABEL = os.environ.get("LQ_EDITION_LABEL", "التطوير المؤسسي").strip() or "التطوير المؤسسي"
APP_ENV_MODE = os.environ.get("LQ_ENV_MODE", "official" if APP_EDITION == "official" else "trial").strip().lower() or "official"
APP_ENV_LABEL_AR = "نسخة رسمية" if APP_ENV_MODE in ("official", "production", "prod") else "نسخة تجريبية"
BACKUP_DIR = Path(os.environ.get("JAWDAH_BACKUP_DIR", str(DATA_DIR / "backups"))).resolve()
AUTO_BACKUP_ENABLED = os.environ.get("JAWDAH_AUTO_BACKUP", "1").strip().lower() not in ("0", "false", "no", "off")
BACKUP_INTERVAL_HOURS = max(1, int(os.environ.get("JAWDAH_BACKUP_INTERVAL_HOURS", "24") or "24"))
BACKUP_RETENTION = max(1, int(os.environ.get("JAWDAH_BACKUP_RETENTION", "30") or "30"))
BACKUP_LOCK = threading.Lock()
LAST_AUTO_BACKUP_AT: Optional[str] = None
STORAGE_WARN_GB = float(os.environ.get("JAWDAH_STORAGE_WARN_GB", "2") or "2")
CONTRACT_ACTIVE_STATUSES = {"active", "approved", "activated"}
CONTRACT_EDIT_LOCK_STATUSES = {"approved", "active", "activated"}
CONTRACT_CORE_FIELDS = {
    "contract_type",
    "property_id",
    "client_id",
    "unit_details",
    "start_date",
    "end_date",
    "rent_amount",
    "payment_cycle",
}
ESTATE_UNIT_ACTIVE_STATUSES = {"active"}
ESTATE_CONTRACT_FLOW_STATUSES = {"draft", "approvalrequested", "approved", "active", "ended", "cancelled"}
CORE_USERNAMES = set(NAJJAR_TEAM_USERNAMES)

# Fallback assets: Railway can still open the app even if the public folder is misplaced.
FALLBACK_INDEX_HTML = "<!doctype html>\n<html lang=\"ar\" dir=\"ltr\">\n<head>\n  <meta charset=\"utf-8\">\n  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n  <title>Launch Quality LLC</title>\n  <link rel=\"stylesheet\" href=\"app.css\">\n</head>\n<body>\n  <main id=\"loginScreen\" class=\"login hidden\">\n    <section class=\"login-card\">\n      <img src=\"assets/brand-logo-gold.png\" alt=\"Jawdah logo\">\n      <h1>Launch Quality LLC</h1>\n      <p class=\"mini\">Real Estate & Hospitality Management System</p>\n      <input id=\"loginUser\" placeholder=\"اسم المستخدم\" autocomplete=\"username\">\n      <input id=\"loginPass\" placeholder=\"كلمة المرور\" type=\"password\" autocomplete=\"current-password\">\n      <button id=\"loginBtn\" class=\"gold-btn\" style=\"width:100%;margin-top:10px\">تسجيل الدخول</button>\n      <p class=\"mini\">Use the authorized administrator account.</p>\n    </section>\n  </main>\n\n  <main id=\"app\" class=\"app hidden\">\n    <aside id=\"sidebar\" class=\"sidebar\">\n      <div class=\"brand\">\n        <img src=\"assets/brand-logo-gold.png\" alt=\"logo\">\n        <div><h1>Launch Quality LLC</h1><small>Real Estate & Hospitality Management</small></div>\n      </div>\n      <nav id=\"nav\" class=\"nav\"></nav>\n    </aside>\n    <section class=\"content\">\n      <header class=\"topbar\">\n        <button id=\"menuBtn\" class=\"ghost mobile-nav\">☰</button>\n        <div class=\"search\"><input id=\"globalSearch\" placeholder=\"بحث سريع Ctrl + K\"></div>\n        <button class=\"gold-btn\" onclick=\"showSection('properties')\">+ إضافة</button>\n        <div id=\"clock\" class=\"top-pill\">00:00:00</div>\n        <div class=\"userbox\"><div id=\"avatar\" class=\"avatar\">J</div><div><b id=\"userName\">User</b><br><small id=\"userRole\" class=\"mini\">Role</small></div></div>\n        <button id=\"logoutBtn\" class=\"ghost\">خروج</button>\n      </header>\n      <h2 id=\"sectionTitle\">لوحة التحكم التنفيذية</h2>\n\n      <section id=\"sec-dashboard\" class=\"section active\">\n        <div class=\"hero\"><h2>مركز القيادة التنفيذي للعقارات والضيافة</h2><p>نظام إدارة عقارية وضيافة يربط التشغيل المالي والإداري مباشرة: العقار ← العميل ← العقد ← الفاتورة ← التحصيل ← الحسابات.</p><div id=\"heroStats\" class=\"status-line\" style=\"margin-top:14px\"></div></div>\n        <div id=\"kpiGrid\" class=\"grid kpis\"></div>\n        <div class=\"layout\">\n          <div class=\"card\"><h3>الإيرادات والمصروفات</h3><div class=\"canvas-wrap\"><canvas id=\"incomeChart\"></canvas></div></div>\n          <div class=\"card\"><h3>خريطة GIS تشغيلية</h3><div class=\"gis\"><div id=\"gisPins\"></div></div></div>\n        </div>\n        <div class=\"layout\">\n          <div class=\"card\"><h3>قرارات الآن</h3><div id=\"decisionList\"></div></div>\n          <div class=\"card\"><h3>الإشغال</h3><div class=\"canvas-wrap\"><canvas id=\"occupancyChart\"></canvas></div></div>\n        </div>\n        <div class=\"card\"><h3>إجراءات سريعة</h3><div id=\"quickActions\" class=\"quick\"></div></div>\n      </section>\n\n      <section id=\"sec-properties\" class=\"section\">\n        <div class=\"card\"><h3>إضافة عقار</h3><div class=\"form\"><input id=\"pImage\" placeholder=\"إيموجي/رمز\" value=\"🏠\"><input id=\"pName\" placeholder=\"اسم العقار\"><input id=\"pType\" placeholder=\"النوع\"><select id=\"pStatus\"><option>Rented</option><option>Vacant</option><option>Maintenance</option></select><input id=\"pPrice\" placeholder=\"السعر\"><input id=\"pLocation\" placeholder=\"الموقع\"><textarea id=\"pNotes\" placeholder=\"ملاحظات\"></textarea></div><button class=\"gold-btn\" onclick=\"createProperty()\">حفظ العقار</button></div>\n        <div class=\"card\"><div class=\"toolbar\"><select id=\"propStatusFilter\" onchange=\"renderProperties()\"></select><button class=\"ghost\" onclick=\"exportCsv('properties')\">تصدير CSV</button></div><div id=\"propertiesTable\"></div></div>\n      </section>\n\n      <section id=\"sec-clients\" class=\"section\">\n        <div class=\"card\"><h3>إضافة عميل</h3><div class=\"form\"><input id=\"cName\" placeholder=\"اسم العميل\"><input id=\"cPhone\" placeholder=\"الهاتف\"><input id=\"cEmail\" placeholder=\"البريد\"><input id=\"cNational\" placeholder=\"الهوية/السجل\"><textarea id=\"cNotes\" placeholder=\"ملاحظات\"></textarea></div><button class=\"gold-btn\" onclick=\"createClient()\">حفظ العميل</button></div>\n        <div class=\"card\"><div class=\"toolbar\"><button class=\"ghost\" onclick=\"exportCsv('clients')\">تصدير CSV</button></div><div id=\"clientsTable\"></div></div>\n      </section>\n\n      <section id=\"sec-contracts\" class=\"section\">\n        <div class=\"card\"><h3>إنشاء عقد</h3><div class=\"form\"><select id=\"contractProperty\"></select><select id=\"contractClient\"></select><input id=\"contractStart\" type=\"date\"><input id=\"contractEnd\" type=\"date\"><input id=\"contractRent\" placeholder=\"قيمة الإيجار\"><textarea id=\"contractNotes\" placeholder=\"ملاحظات العقد\"></textarea></div><button class=\"gold-btn\" onclick=\"createContract()\">حفظ العقد</button></div>\n        <div class=\"card\"><div class=\"toolbar\"><button class=\"ghost\" onclick=\"exportCsv('contracts')\">تصدير CSV</button></div><div id=\"contractsTable\"></div></div>\n      </section>\n\n      <section id=\"sec-invoices\" class=\"section\">\n        <div class=\"card\"><h3>الفواتير والتحصيل</h3><p class=\"mini\">يتم إنشاء الفاتورة من العقد فقط لضمان الربط الصحيح.</p><div id=\"invoicesTable\"></div></div>\n      </section>\n\n      <section id=\"sec-accounts\" class=\"section\">\n        <div class=\"card\"><h3>إضافة حركة مالية</h3><div class=\"form\"><input id=\"accDate\" type=\"date\"><select id=\"accType\"><option value=\"income\">income</option><option value=\"expense\">expense</option></select><input id=\"accCategory\" placeholder=\"التصنيف\"><input id=\"accDesc\" placeholder=\"الوصف\"><input id=\"accAmount\" placeholder=\"المبلغ\"></div><button class=\"gold-btn\" onclick=\"createAccount()\">حفظ الحركة</button></div>\n        <div class=\"card\"><h3>ملخص الحسابات</h3><div id=\"accountSummary\" class=\"status-line\"></div><div class=\"canvas-wrap\"><canvas id=\"expenseChart\"></canvas></div></div>\n        <div class=\"card\"><div class=\"toolbar\"><button class=\"ghost\" onclick=\"exportCsv('accounts')\">تصدير CSV</button></div><div id=\"accountsTable\"></div></div>\n      </section>\n\n      <section id=\"sec-maintenance\" class=\"section\">\n        <div class=\"card\"><h3>طلب صيانة</h3><div class=\"form\"><select id=\"maintProperty\"></select><input id=\"maintTitle\" placeholder=\"عنوان الطلب\"><select id=\"maintPriority\"><option>High</option><option>Medium</option><option>Low</option></select><input id=\"maintCost\" placeholder=\"التكلفة المتوقعة\"><textarea id=\"maintNotes\" placeholder=\"تفاصيل\"></textarea></div><button class=\"gold-btn\" onclick=\"createMaintenance()\">حفظ الطلب</button></div>\n        <div class=\"grid\" id=\"maintenanceGrid\" style=\"grid-template-columns:repeat(auto-fit,minmax(260px,1fr))\"></div>\n      </section>\n\n      <section id=\"sec-reports\" class=\"section\">\n        <div id=\"reportsBox\"></div>\n        <div class=\"card\"><button class=\"gold-btn\" onclick=\"renderReports()\">تحديث التقرير</button> <button class=\"ghost\" onclick=\"downloadBackup()\">تنزيل Backup</button></div>\n      </section>\n\n      <section id=\"sec-users\" class=\"section\">\n        <div class=\"card\"><h3>إضافة مستخدم</h3><div class=\"form\"><input id=\"uUsername\" placeholder=\"اسم المستخدم\"><input id=\"uName\" placeholder=\"الاسم\"><select id=\"uRole\"><option value=\"admin\">admin</option><option value=\"accountant\">accountant</option><option value=\"operations\">operations</option><option value=\"maintenance\">maintenance</option><option value=\"viewer\">viewer</option></select><input id=\"uPassword\" placeholder=\"كلمة المرور\"></div><button class=\"gold-btn\" onclick=\"createUser()\">حفظ المستخدم</button></div>\n        <div class=\"card\"><div id=\"usersTable\"></div></div>\n      </section>\n\n      <section id=\"sec-backup\" class=\"section\">\n        <div class=\"card\"><h3>مركز التخزين والنسخ الاحتياطي</h3><div id=\"backupStatus\" class=\"status-line\"></div><div class=\"toolbar\" style=\"margin-top:16px\"><button class=\"gold-btn\" onclick=\"downloadBackup()\">تنزيل Backup JSON</button><button class=\"ghost\" onclick=\"exportCsv('properties')\">عقارات CSV</button><button class=\"ghost\" onclick=\"exportCsv('clients')\">عملاء CSV</button><button class=\"ghost\" onclick=\"exportCsv('contracts')\">عقود CSV</button><button class=\"ghost\" onclick=\"exportCsv('invoices')\">فواتير CSV</button><button class=\"ghost\" onclick=\"exportCsv('accounts')\">حسابات CSV</button></div></div>\n      </section>\n\n      <section id=\"sec-qa\" class=\"section\">\n        <div class=\"card\"><h3>اختبار التشغيل</h3><button class=\"gold-btn\" onclick=\"runQA()\">تشغيل الاختبار الآن</button><div id=\"qaBox\" style=\"margin-top:15px\"></div></div>\n      </section>\n    </section>\n  </main>\n\n  <div id=\"paymentModal\" class=\"modal\"><div class=\"modal-box\"><h2>تحصيل فاتورة</h2><p id=\"payInfo\"></p><input id=\"payInvoiceId\" type=\"hidden\"><div class=\"form\"><input id=\"payAmount\" placeholder=\"المبلغ\"><select id=\"payMethod\"><option>Cash</option><option>Bank Transfer</option><option>Card</option></select><input id=\"payNote\" placeholder=\"ملاحظة\"></div><button class=\"gold-btn\" onclick=\"submitPayment()\">تأكيد التحصيل</button> <button class=\"ghost\" onclick=\"closeModal('paymentModal')\">إغلاق</button></div></div>\n  <div id=\"invoiceModal\" class=\"modal\"><div class=\"modal-box\"><div id=\"invoicePreview\"></div><div class=\"toolbar\"><button class=\"gold-btn\" onclick=\"window.print()\">طباعة A4</button><button class=\"ghost\" onclick=\"downloadInvoice()\">تنزيل HTML</button><button class=\"ghost\" onclick=\"closeModal('invoiceModal')\">إغلاق</button></div></div></div>\n  <div id=\"genericModal\" class=\"modal\"><div class=\"modal-box\"><div id=\"genericModalBody\"></div><button class=\"ghost\" onclick=\"closeModal('genericModal')\">إغلاق</button></div></div>\n  <script src=\"app.js\"></script>\n</body>\n</html>\n"
FALLBACK_CSS = ":root{\n  --bg:#030712;\n  --navy:#07111f;\n  --navy2:#0b1728;\n  --navy3:#111f34;\n  --panel:rgba(11,23,40,.82);\n  --panel2:rgba(17,31,52,.72);\n  --glass:rgba(255,255,255,.075);\n  --text:#f8f5ec;\n  --muted:#aeb8c9;\n  --gold:#d8b15b;\n  --gold2:#fff0b8;\n  --gold3:#9c6d21;\n  --silver:#dce3ef;\n  --silver2:#93a4ba;\n  --blue:#4ea1ff;\n  --red:#ff6666;\n  --line:rgba(255,255,255,.13);\n  --line-gold:rgba(216,177,91,.42);\n  --shadow:0 28px 85px rgba(0,0,0,.42);\n  --soft:0 16px 45px rgba(0,0,0,.22);\n  --radius:24px;\n  --side:300px;\n}\n*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:\"Tajawal\",\"Segoe UI\",Arial,sans-serif;background:radial-gradient(circle at 14% 10%,rgba(216,177,91,.22),transparent 27%),radial-gradient(circle at 82% 0%,rgba(78,161,255,.14),transparent 30%),linear-gradient(135deg,#030712 0%,#07111f 44%,#0b1220 100%);color:var(--text);min-height:100vh;overflow-x:hidden}body:before{content:\"\";position:fixed;inset:0;pointer-events:none;background:linear-gradient(90deg,rgba(216,177,91,.07),transparent 18%,transparent 82%,rgba(216,177,91,.06)),radial-gradient(circle at 50% 110%,rgba(216,177,91,.14),transparent 38%);z-index:-1}button,input,select,textarea{font:inherit}button{cursor:pointer}.hidden{display:none!important}.app{min-height:100vh;display:grid;grid-template-columns:var(--side) 1fr}.sidebar{position:sticky;top:0;height:100vh;padding:22px;background:linear-gradient(180deg,rgba(15,25,42,.95),rgba(5,11,22,.97));border-left:1px solid var(--line-gold);box-shadow:var(--shadow);overflow-y:auto}.sidebar::-webkit-scrollbar{width:6px}.sidebar::-webkit-scrollbar-thumb{background:rgba(216,177,91,.45);border-radius:20px}.brand{display:flex;align-items:center;gap:14px;margin-bottom:24px;border:1px solid rgba(216,177,91,.25);border-radius:26px;padding:12px;background:linear-gradient(135deg,rgba(255,255,255,.08),rgba(216,177,91,.08))}.brand img{width:64px;height:64px;border-radius:22px;object-fit:cover;border:2px solid rgba(216,177,91,.95);box-shadow:0 0 38px rgba(216,177,91,.38)}.brand h1{font-size:19px;margin:0;color:var(--gold2)}.brand small{color:var(--muted)}.nav{display:grid;gap:10px}.nav button{border:1px solid var(--line);background:linear-gradient(135deg,rgba(255,255,255,.055),rgba(255,255,255,.025));color:var(--text);padding:13px 14px;border-radius:18px;display:flex;justify-content:space-between;align-items:center;transition:.22s;box-shadow:0 10px 22px rgba(0,0,0,.12)}.nav button:hover,.nav button.active{background:linear-gradient(135deg,rgba(216,177,91,.28),rgba(255,255,255,.08));border-color:rgba(216,177,91,.78);transform:translateX(-4px);box-shadow:0 14px 34px rgba(216,177,91,.16), inset 0 1px 0 rgba(255,255,255,.16)}.content{padding:22px 24px 34px;min-width:0}.topbar{display:flex;align-items:center;gap:12px;margin-bottom:20px;position:sticky;top:10px;z-index:10;background:linear-gradient(180deg,rgba(8,18,32,.86),rgba(8,18,32,.62));backdrop-filter:blur(18px);padding:10px;border:1px solid rgba(216,177,91,.25);border-radius:26px;box-shadow:0 18px 48px rgba(0,0,0,.26)}.search{flex:1;position:relative}.search input{width:100%;border:1px solid var(--line);background:rgba(255,255,255,.055);color:var(--text);padding:14px 18px;border-radius:18px;outline:none}.search input:focus{border-color:rgba(216,177,91,.72);box-shadow:0 0 0 4px rgba(216,177,91,.1)}.top-pill{border:1px solid rgba(216,177,91,.55);background:linear-gradient(135deg,rgba(216,177,91,.24),rgba(255,255,255,.07));color:var(--gold2);padding:12px 15px;border-radius:18px;white-space:nowrap;font-weight:800}.gold-btn,.primary{border:0;background:linear-gradient(135deg,#9a681e,#f4d77f 48%,#b88328);color:#101010;border-radius:17px;padding:12px 18px;font-weight:900;box-shadow:0 18px 42px rgba(216,177,91,.27), inset 0 1px 0 rgba(255,255,255,.5)}.gold-btn:hover{filter:brightness(1.08);transform:translateY(-1px)}.ghost{border:1px solid var(--line);background:linear-gradient(135deg,rgba(255,255,255,.075),rgba(255,255,255,.035));color:var(--text);border-radius:15px;padding:10px 13px}.ghost:hover{border-color:rgba(216,177,91,.45);background:rgba(216,177,91,.08)}.danger{border:0;background:linear-gradient(135deg,#7f1d1d,#ff7474);color:#fff;border-radius:15px;padding:10px 13px;font-weight:900}.userbox{display:flex;align-items:center;gap:10px}.avatar{width:48px;height:48px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#fff1b8,#b8862e);color:#111;border:2px solid var(--gold2);font-weight:900}.content>h2{font-size:24px;margin:8px 0 18px;color:var(--gold2);letter-spacing:.2px}.hero{position:relative;overflow:hidden;border:1px solid rgba(216,177,91,.32);border-radius:34px;background:linear-gradient(135deg,rgba(255,255,255,.11),rgba(255,255,255,.035)),radial-gradient(circle at 12% 15%,rgba(216,177,91,.28),transparent 32%),radial-gradient(circle at 85% 25%,rgba(78,161,255,.14),transparent 30%),linear-gradient(135deg,#0a1627,#111d31);padding:30px;margin-bottom:20px;box-shadow:var(--shadow)}.hero:before{content:\"Jawdah Command Center\";position:absolute;left:28px;bottom:10px;font-size:56px;font-weight:900;color:rgba(255,255,255,.035);letter-spacing:1px;white-space:nowrap}.hero:after{content:\"\";position:absolute;inset:auto -110px -160px auto;width:420px;height:420px;background:radial-gradient(circle,rgba(216,177,91,.36),transparent 62%);filter:blur(12px)}.hero h2{font-size:36px;margin:0 0 10px;color:var(--gold2)}.hero p{margin:0;color:var(--muted);max-width:920px;line-height:1.9}.grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(4,minmax(0,1fr))}.kpi{border:1px solid rgba(216,177,91,.18);border-radius:26px;background:linear-gradient(145deg,rgba(255,255,255,.105),rgba(255,255,255,.035));padding:18px;box-shadow:0 18px 52px rgba(0,0,0,.24);position:relative;overflow:hidden;transition:.22s;min-height:142px}.kpi:hover{transform:translateY(-3px);border-color:rgba(216,177,91,.55);box-shadow:0 24px 68px rgba(0,0,0,.32),0 0 26px rgba(216,177,91,.12)}.kpi:before{content:\"\";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,transparent,var(--gold),var(--gold2),transparent)}.kpi:after{content:\"\";position:absolute;left:-25%;bottom:-55%;width:180px;height:180px;background:radial-gradient(circle,rgba(216,177,91,.18),transparent 62%)}.kpi .icon{font-size:31px;filter:drop-shadow(0 8px 18px rgba(216,177,91,.28))}.kpi strong{display:block;font-size:31px;margin:10px 0 4px;color:#fff}.kpi span{color:var(--muted)}.layout{display:grid;grid-template-columns:1.18fr .82fr;gap:16px;margin-top:16px}.card{border:1px solid rgba(216,177,91,.16);border-radius:26px;background:linear-gradient(145deg,rgba(255,255,255,.095),rgba(255,255,255,.032));padding:18px;box-shadow:0 18px 48px rgba(0,0,0,.22);min-width:0}.card h3{margin:0 0 14px;color:var(--gold2)}.canvas-wrap{height:280px}.canvas-wrap canvas{width:100%;height:100%}.gis{height:330px;border-radius:24px;background:radial-gradient(circle at 40% 35%,rgba(216,177,91,.14),transparent 30%),linear-gradient(135deg,#10233a,#0b1628);position:relative;overflow:hidden;border:1px solid rgba(216,177,91,.18)}.gis:before{content:\"\";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.06) 1px,transparent 1px);background-size:35px 35px;opacity:.35}.gis:after{content:\"\";position:absolute;inset:15%;border:1px solid rgba(216,177,91,.18);border-radius:50%;filter:blur(.2px)}.pin{position:absolute;width:18px;height:18px;border-radius:50%;box-shadow:0 0 0 8px rgba(255,255,255,.08),0 0 25px currentColor;border:2px solid rgba(255,255,255,.75)}.pin.gold{color:#f6d77f;background:#f6d77f}.pin.blue{color:#60a5fa;background:#60a5fa}.pin.red{color:#ff6b6b;background:#ff6b6b}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}.toolbar input,.toolbar select,.form input,.form select,.form textarea{border:1px solid var(--line);background:rgba(255,255,255,.065);color:var(--text);border-radius:15px;padding:11px 12px;outline:none}.toolbar option,.form option{background:#0b1728;color:#fff}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:rgba(2,6,23,.18)}table{width:100%;border-collapse:collapse;min-width:880px}th,td{padding:13px;border-bottom:1px solid rgba(255,255,255,.075);text-align:right;vertical-align:middle}th{color:var(--gold2);background:rgba(216,177,91,.09);position:sticky;top:0}td{color:#edf2fa}.badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.07);border:1px solid var(--line);font-size:13px;color:var(--silver)}.paid,.active,.rented{color:#1b1302;background:linear-gradient(135deg,#b9882c,#ffe49a);border-color:rgba(216,177,91,.8);font-weight:800}.partial,.pending{color:#261a02;background:linear-gradient(135deg,#b68b39,#e8d9ac);border-color:rgba(216,177,91,.65);font-weight:800}.overdue,.maintenance,.open{color:#fff;background:linear-gradient(135deg,#7f1d1d,#e15b5b);border-color:rgba(255,115,115,.65);font-weight:800}.vacant{color:#06172c;background:linear-gradient(135deg,#79b7ff,#dceaff);border-color:rgba(96,165,250,.65);font-weight:800}.section{display:none}.section.active{display:block}.form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:15px}.form textarea{grid-column:1/-1;min-height:90px}.modal{position:fixed;inset:0;background:rgba(0,0,0,.68);display:none;align-items:center;justify-content:center;z-index:30;padding:16px}.modal.show{display:flex}.modal-box{width:min(880px,100%);max-height:90vh;overflow:auto;border:1px solid rgba(216,177,91,.38);border-radius:28px;background:#081426;color:var(--text);padding:22px;box-shadow:0 30px 90px rgba(0,0,0,.55)}.invoice-paper{background:#fff;color:#111;border-radius:18px;padding:30px;direction:ltr}.invoice-paper .head{display:flex;justify-content:space-between;border-bottom:4px solid #d8b15b;padding-bottom:16px;margin-bottom:18px}.invoice-paper table{min-width:0;color:#111}.invoice-paper th{background:#071426;color:#fff}.invoice-paper td{color:#111;border-color:#ddd}.login{min-height:100vh;display:grid;place-items:center;padding:20px}.login-card{width:min(460px,100%);border:1px solid rgba(216,177,91,.35);border-radius:32px;background:linear-gradient(145deg,rgba(255,255,255,.12),rgba(255,255,255,.04));padding:32px;box-shadow:var(--shadow);text-align:center}.login-card img{width:96px;height:96px;border-radius:30px;border:2px solid var(--gold);object-fit:cover}.login-card input{width:100%;margin:9px 0;border:1px solid var(--line);background:rgba(255,255,255,.08);color:#fff;padding:14px;border-radius:16px;outline:none}.toast{position:fixed;bottom:22px;left:22px;background:#101d30;border:1px solid rgba(216,177,91,.45);padding:14px 18px;border-radius:18px;box-shadow:var(--shadow);z-index:50}.toast.err{border-color:#ef4444}.mobile-nav{display:none}.mini{font-size:13px;color:var(--muted)}.status-line{display:flex;gap:10px;flex-wrap:wrap}.quick{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.quick button{text-align:right;padding:18px;border-radius:22px}.executive-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}.executive-chip{border:1px solid rgba(216,177,91,.2);background:rgba(255,255,255,.055);border-radius:20px;padding:14px}.executive-chip b{color:var(--gold2)}@media(max-width:1100px){.app{grid-template-columns:1fr}.sidebar{position:fixed;right:-320px;width:290px;z-index:40;transition:.25s}.sidebar.open{right:0}.content{padding:14px}.kpis{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.form{grid-template-columns:1fr}.mobile-nav{display:inline-flex}.topbar{flex-wrap:wrap}.quick{grid-template-columns:repeat(2,1fr)}.executive-strip{grid-template-columns:1fr}}@media(max-width:650px){.kpis{grid-template-columns:1fr}.hero h2{font-size:25px}.hero:before{font-size:34px}.userbox{width:100%;justify-content:space-between}.top-pill{font-size:13px}.quick{grid-template-columns:1fr}}@media print{body{background:#fff;color:#000}.app,.modal .ghost,.modal .gold-btn{display:none!important}.modal{display:block!important;position:static;background:#fff;padding:0}.modal-box{box-shadow:none;border:0;max-height:none;width:100%;padding:0}.invoice-paper{border-radius:0;padding:0}}\n"
FALLBACK_JS = 'const Jawdah = {\n  token: localStorage.getItem(\'jawdah_cloud_token\') || \'\',\n  user: null,\n  data: {},\n  dashboard: null,\n  activeSection: \'dashboard\',\n  charts: {},\n  invoiceForPrint: null\n};\nconst $ = s => document.querySelector(s);\nconst $$ = s => Array.from(document.querySelectorAll(s));\nconst api = async (path, opts={}) => {\n  const headers = {\'Content-Type\':\'application/json\'};\n  if(Jawdah.token) headers.Authorization = \'Bearer \' + Jawdah.token;\n  const res = await fetch(\'/api/\' + path.replace(/^\\//,\'\'), {...opts, headers:{...headers, ...(opts.headers||{})}});\n  const text = await res.text();\n  let data;\n  try{ data = text ? JSON.parse(text) : {}; }catch(e){ data = {ok:false,error:text || \'Invalid response\'}; }\n  if(!res.ok || data.ok === false) throw new Error(data.error || data.detail || \'Request failed\');\n  return data;\n};\nconst fmt = n => Number(n||0).toLocaleString(\'en-US\',{maximumFractionDigits:2});\nconst money = n => fmt(n) + \' OMR\';\nconst today = () => new Date().toISOString().slice(0,10);\nconst byId = (table,id) => (Jawdah.data[table]||[]).find(x=>x.id===id) || {};\nconst roleName = r => ({admin:\'مدير النظام\',accountant:\'محاسب\',operations:\'تشغيل\',maintenance:\'صيانة\',viewer:\'مشاهد\'}[r]||r);\nfunction toast(msg, err=false){ const t=document.createElement(\'div\'); t.className=\'toast\'+(err?\' err\':\'\'); t.textContent=msg; document.body.appendChild(t); setTimeout(()=>t.remove(),3200); }\nfunction ensureEnglishDigits(root=document.body){\n  const rx=/[\\u0660-\\u0669\\u06F0-\\u06F9]/g;\n  const convert=s=>String(s).replace(rx,ch=>String(ch.charCodeAt(0)-((ch.charCodeAt(0)>=0x06F0)?0x06F0:0x0660)));\n  const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);\n  let n; while(n=walk.nextNode()){ if(rx.test(n.nodeValue)) n.nodeValue=convert(n.nodeValue); }\n  $$(\'input,textarea\').forEach(el=>{ if(rx.test(el.value)) el.value=convert(el.value); });\n}\nasync function login(){\n  try{\n    const username=$(\'#loginUser\').value.trim(); const password=$(\'#loginPass\').value;\n    const res=await api(\'login\',{method:\'POST\',body:JSON.stringify({username,password})});\n    Jawdah.token=res.token; Jawdah.user=res.user; localStorage.setItem(\'jawdah_cloud_token\',res.token);\n    $(\'#loginScreen\').classList.add(\'hidden\'); $(\'#app\').classList.remove(\'hidden\'); await loadAll(); toast(\'تم تسجيل الدخول\');\n  }catch(e){toast(e.message,true)}\n}\nasync function logout(){ try{await api(\'logout\',{method:\'POST\'});}catch(e){} localStorage.removeItem(\'jawdah_cloud_token\'); location.reload(); }\nasync function checkSession(){\n  if(!Jawdah.token){ $(\'#loginScreen\').classList.remove(\'hidden\'); return; }\n  try{ const me=await api(\'me\'); Jawdah.user=me.user; $(\'#loginScreen\').classList.add(\'hidden\'); $(\'#app\').classList.remove(\'hidden\'); await loadAll(); }\n  catch(e){ localStorage.removeItem(\'jawdah_cloud_token\'); $(\'#loginScreen\').classList.remove(\'hidden\'); }\n}\nasync function loadAll(){\n  const res=await api(\'bootstrap\'); Jawdah.data=res.data; Jawdah.dashboard=res.dashboard; Jawdah.user=res.user;\n  $(\'#userName\').textContent=Jawdah.user.name; $(\'#userRole\').textContent=roleName(Jawdah.user.role); $(\'#avatar\').textContent=(Jawdah.user.name||\'J\').slice(0,1).toUpperCase();\n  buildNav(); renderAll(); showSection(Jawdah.activeSection||\'dashboard\'); ensureEnglishDigits();\n}\nfunction buildNav(){\n  const items=[[\'dashboard\',\'لوحة التحكم\',\'🏛️\'],[\'properties\',\'العقارات\',\'🏠\'],[\'clients\',\'العملاء\',\'👥\'],[\'contracts\',\'العقود\',\'📑\'],[\'invoices\',\'الفواتير\',\'🧾\'],[\'accounts\',\'الحسابات\',\'💰\'],[\'maintenance\',\'الصيانة\',\'🔧\'],[\'reports\',\'التقارير\',\'📊\'],[\'users\',\'المستخدمين\',\'🛡️\'],[\'backup\',\'التخزين والنسخ\',\'💾\'],[\'qa\',\'اختبار التشغيل\',\'✅\']];\n  const nav=$(\'#nav\'); nav.innerHTML=\'\';\n  items.forEach(([id,label,icon])=>{\n    if(id===\'users\' && Jawdah.user.role!==\'admin\') return;\n    const b=document.createElement(\'button\'); b.dataset.section=id; b.innerHTML=`<span>${icon} ${label}</span><small>›</small>`; b.onclick=()=>showSection(id); nav.appendChild(b);\n  });\n}\nfunction showSection(id){\n  Jawdah.activeSection=id; $$(\'.section\').forEach(s=>s.classList.remove(\'active\')); const s=$(\'#sec-\'+id); if(s) s.classList.add(\'active\');\n  $$(\'#nav button\').forEach(b=>b.classList.toggle(\'active\',b.dataset.section===id));\n  $(\'#sectionTitle\').textContent = ({dashboard:\'لوحة التحكم التنفيذية\',properties:\'العقارات\',clients:\'العملاء\',contracts:\'العقود\',invoices:\'الفواتير\',accounts:\'الحسابات\',maintenance:\'الصيانة\',reports:\'التقارير المالية\',users:\'المستخدمين والصلاحيات\',backup:\'التخزين والنسخ الاحتياطي\',qa:\'اختبار التشغيل\'}[id]||\'Jawdah\');\n  if(innerWidth<1100) $(\'#sidebar\').classList.remove(\'open\'); setTimeout(drawCharts,50); ensureEnglishDigits();\n}\nfunction renderAll(){ renderDashboard(); renderProperties(); renderClients(); renderContracts(); renderInvoices(); renderAccounts(); renderMaintenance(); renderUsers(); renderBackup(); renderQA(); }\nfunction renderDashboard(){\n  const k=Jawdah.dashboard.kpis;\n  const collectionRate = k.billed ? Math.round((Number(k.paid||0)/Number(k.billed||1))*100) : 0;\n  $(\'#heroStats\').innerHTML=`<span class="badge paid">جاهزية النظام ${fmt(k.health)}%</span><span class="badge">الإشغال ${fmt(k.occupancy)}%</span><span class="badge">التحصيل ${fmt(collectionRate)}%</span><span class="badge">صافي الدخل ${money(k.net)}</span>`;\n  const kpis=[[\'🏛️\',\'إجمالي العقارات\',k.properties,\'properties\'],[\'🔑\',\'العقارات المؤجرة\',k.rented,\'properties\'],[\'🏠\',\'العقارات الشاغرة\',k.vacant,\'properties\'],[\'🧾\',\'إجمالي الفوترة\',k.billed,\'invoices\',\'money\'],[\'💳\',\'إجمالي التحصيل\',k.paid,\'accounts\',\'money\'],[\'⏰\',\'المبالغ المتأخرة\',k.overdue,\'invoices\',\'money\'],[\'🔧\',\'طلبات الصيانة المفتوحة\',k.maintenance,\'maintenance\'],[\'📈\',\'صافي الربح\',k.net,\'accounts\',\'money\']];\n  $(\'#kpiGrid\').innerHTML=kpis.map(x=>`<div class="kpi" onclick="showSection(\'${x[3]}\')"><div class="icon">${x[0]}</div><span>${x[1]}</span><strong>${x[4]?money(x[2]):fmt(x[2])}</strong><small class="mini">فتح التفاصيل</small></div>`).join(\'\');\n  $(\'#decisionList\').innerHTML=`<div class="executive-strip"><div class="executive-chip"><b>مؤشر التحصيل</b><br><span class="mini">${fmt(collectionRate)}% من إجمالي الفواتير</span></div><div class="executive-chip"><b>مؤشر الإشغال</b><br><span class="mini">${fmt(k.occupancy)}% من الوحدات</span></div><div class="executive-chip"><b>القرار التالي</b><br><span class="mini">راجع المتأخرات والصيانة أولاً</span></div></div>` + Jawdah.dashboard.decisions.map(d=>`<div class="card" style="padding:13px;margin-bottom:10px"><span class="badge">${d.level}</span><p>${d.text}</p></div>`).join(\'\');\n  const props=Jawdah.data.properties||[];\n  $(\'#gisPins\').innerHTML=props.map((p,i)=>{ const cls=(p.status||\'\').toLowerCase().includes(\'maintenance\')?\'red\':((p.status||\'\').toLowerCase().includes(\'vacant\')?\'blue\':\'gold\'); const left=[18,43,68,28,78,52,36][i%7], top=[24,42,58,70,32,22,64][i%7]; return `<button class="pin ${cls}" title="${p.name}" style="left:${left}%;top:${top}%" onclick="toast(\'${p.name} - ${p.status}\')"></button>` }).join(\'\');\n  $(\'#quickActions\').innerHTML=[[\'إضافة عقار\',\'properties\',\'🏠\'],[\'إضافة عميل\',\'clients\',\'👥\'],[\'إنشاء عقد\',\'contracts\',\'📑\'],[\'فاتورة من عقد\',\'invoices\',\'🧾\'],[\'تحصيل دفعة\',\'invoices\',\'💳\'],[\'Backup فوري\',\'backup\',\'💾\'],[\'تقرير مالي\',\'reports\',\'📊\'],[\'اختبار التشغيل\',\'qa\',\'✅\']].map(q=>`<button class="ghost" onclick="showSection(\'${q[1]}\')"><b>${q[2]} ${q[0]}</b><br><small class="mini">أمر تنفيذي سريع</small></button>`).join(\'\');\n}\nfunction tableHtml(cols, rows, actions){\n  return `<div class="table-wrap"><table><thead><tr>${cols.map(c=>`<th>${c[0]}</th>`).join(\'\')}${actions?\'<th>إجراء</th>\':\'\'}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${c[2]?c[2](r[c[1]],r):(r[c[1]]??\'\')}</td>`).join(\'\')}${actions?`<td>${actions(r)}</td>`:\'\'}</tr>`).join(\'\')||`<tr><td colspan="${cols.length+1}">لا توجد بيانات</td></tr>`}</tbody></table></div>`;\n}\nfunction renderProperties(){\n  const rows=filterRows(\'properties\',[\'name\',\'type\',\'status\',\'location\']);\n  $(\'#propertiesTable\').innerHTML=tableHtml([[\'الصورة\',\'image\'],[\'الاسم\',\'name\'],[\'النوع\',\'type\'],[\'الحالة\',\'status\',(v)=>badge(v)],[\'السعر\',\'price\',(v)=>money(v)],[\'الموقع\',\'location\'],[\'آخر تحديث\',\'last_update\']],rows,r=>`<button class="ghost" onclick="editRecord(\'properties\',\'${r.id}\')">تعديل</button> <button class="danger" onclick="delRecord(\'properties\',\'${r.id}\')">حذف</button>`);\n  fillSelect(\'#propStatusFilter\',[\'\',\'Rented\',\'Vacant\',\'Maintenance\'],false);\n}\nfunction renderClients(){\n  const rows=filterRows(\'clients\',[\'name\',\'phone\',\'email\',\'national_id\']);\n  $(\'#clientsTable\').innerHTML=tableHtml([[\'الاسم\',\'name\'],[\'الهاتف\',\'phone\'],[\'البريد\',\'email\'],[\'الهوية/السجل\',\'national_id\'],[\'الرصيد\',\'balance\',(v)=>money(v)],[\'ملاحظات\',\'notes\']],rows,r=>`<button class="ghost" onclick="clientStatement(\'${r.id}\')">كشف</button> <button class="ghost" onclick="editRecord(\'clients\',\'${r.id}\')">تعديل</button> <button class="danger" onclick="delRecord(\'clients\',\'${r.id}\')">حذف</button>`);\n}\nfunction renderContracts(){\n  fillSelect(\'#contractProperty\',Jawdah.data.properties||[],true,\'id\',\'name\'); fillSelect(\'#contractClient\',Jawdah.data.clients||[],true,\'id\',\'name\');\n  const rows=filterRows(\'contracts\',[\'id\',\'status\',\'notes\']);\n  $(\'#contractsTable\').innerHTML=tableHtml([[\'العقد\',\'id\'],[\'العقار\',\'property_id\',(v)=>byId(\'properties\',v).name||v],[\'العميل\',\'client_id\',(v)=>byId(\'clients\',v).name||v],[\'البداية\',\'start_date\'],[\'النهاية\',\'end_date\'],[\'الإيجار\',\'rent_amount\',(v)=>money(v)],[\'الحالة\',\'status\',(v)=>badge(v)]],rows,r=>`<button class="gold-btn" onclick="invoiceFromContract(\'${r.id}\')">فاتورة</button> <button class="ghost" onclick="editRecord(\'contracts\',\'${r.id}\')">تعديل</button> <button class="danger" onclick="delRecord(\'contracts\',\'${r.id}\')">حذف</button>`);\n}\nfunction renderInvoices(){\n  const rows=filterRows(\'invoices\',[\'invoice_no\',\'description\',\'status\']);\n  $(\'#invoicesTable\').innerHTML=tableHtml([[\'رقم\',\'invoice_no\'],[\'العميل\',\'client_id\',(v)=>byId(\'clients\',v).name||v],[\'العقار\',\'property_id\',(v)=>byId(\'properties\',v).name||v],[\'الإصدار\',\'issue_date\'],[\'الاستحقاق\',\'due_date\'],[\'الإجمالي\',\'amount\',(v)=>money(v)],[\'المدفوع\',\'paid_amount\',(v)=>money(v)],[\'المتبقي\',\'amount\',(v,r)=>money(Number(r.amount)-Number(r.paid_amount))],[\'الحالة\',\'status\',(v)=>badge(v)]],rows,r=>`<button class="gold-btn" onclick="openPayment(\'${r.id}\')">تحصيل</button> <button class="ghost" onclick="printInvoice(\'${r.id}\')">طباعة</button> <button class="danger" onclick="delRecord(\'invoices\',\'${r.id}\')">حذف</button>`);\n}\nfunction renderAccounts(){\n  const rows=filterRows(\'accounts\',[\'description\',\'category\',\'type\']);\n  $(\'#accountsTable\').innerHTML=tableHtml([[\'التاريخ\',\'entry_date\'],[\'النوع\',\'type\',(v)=>badge(v)],[\'التصنيف\',\'category\'],[\'الوصف\',\'description\'],[\'العميل\',\'client_id\',(v)=>v?(byId(\'clients\',v).name||v):\'\'],[\'العقار\',\'property_id\',(v)=>v?(byId(\'properties\',v).name||v):\'\'],[\'الفاتورة\',\'invoice_id\',(v)=>v?(byId(\'invoices\',v).invoice_no||v):\'\'],[\'المبلغ\',\'amount\',(v)=>money(v)]],rows,r=>`<button class="ghost" onclick="editRecord(\'accounts\',\'${r.id}\')">تعديل</button> <button class="danger" onclick="delRecord(\'accounts\',\'${r.id}\')">حذف</button>`);\n  const income=rows.filter(x=>x.type===\'income\').reduce((s,x)=>s+Number(x.amount||0),0), expense=rows.filter(x=>x.type===\'expense\').reduce((s,x)=>s+Number(x.amount||0),0);\n  $(\'#accountSummary\').innerHTML=`<span class="badge">إيرادات ${money(income)}</span><span class="badge">مصروفات ${money(expense)}</span><span class="badge">صافي ${money(income-expense)}</span>`;\n}\nfunction renderMaintenance(){\n  fillSelect(\'#maintProperty\',Jawdah.data.properties||[],true,\'id\',\'name\');\n  const rows=filterRows(\'maintenance\',[\'title\',\'priority\',\'status\',\'notes\']);\n  $(\'#maintenanceGrid\').innerHTML=rows.map(m=>`<div class="card"><h3>${m.title}</h3><p>${byId(\'properties\',m.property_id).name||m.property_id}</p><span class="badge">${m.priority}</span> <span class="badge">${m.status}</span><p>التكلفة: ${money(m.cost)}</p><button class="ghost" onclick="editRecord(\'maintenance\',\'${m.id}\')">متابعة</button> <button class="danger" onclick="delRecord(\'maintenance\',\'${m.id}\')">حذف</button></div>`).join(\'\')||\'<div class="card">لا توجد طلبات صيانة</div>\';\n}\nfunction renderUsers(){\n  if(!Jawdah.data.users){ $(\'#usersTable\').innerHTML=\'<div class="card">هذا القسم للمدير فقط</div>\'; return; }\n  $(\'#usersTable\').innerHTML=tableHtml([[\'المستخدم\',\'username\'],[\'الاسم\',\'name\'],[\'الدور\',\'role\',(v)=>roleName(v)],[\'نشط\',\'active\',(v)=>v?\'نعم\':\'لا\'],[\'آخر دخول\',\'last_login\']],Jawdah.data.users,r=>`<button class="ghost" onclick="editRecord(\'users\',\'${r.id}\')">تعديل</button> <button class="danger" onclick="delRecord(\'users\',\'${r.id}\')">حذف</button>`);\n}\nfunction renderBackup(){\n  const counts=Object.fromEntries(Object.entries(Jawdah.data).map(([k,v])=>[k,(v||[]).length]));\n  $(\'#backupStatus\').innerHTML=Object.entries(counts).map(([k,v])=>`<span class="badge">${k}: ${fmt(v)}</span>`).join(\' \');\n}\nfunction renderQA(){\n  $(\'#qaBox\').innerHTML=\'<p>اضغط تشغيل الاختبار لفحص الترابط والتخزين والفواتير والحسابات.</p>\';\n}\nfunction filterRows(table, fields){\n  let rows=[...(Jawdah.data[table]||[])]; const q=($(\'#globalSearch\')?.value||\'\').toLowerCase().trim();\n  if(q) rows=rows.filter(r=>fields.some(f=>String(r[f]??\'\').toLowerCase().includes(q)));\n  if(table===\'properties\'){ const s=$(\'#propStatusFilter\')?.value; if(s) rows=rows.filter(r=>r.status===s); }\n  return rows;\n}\nfunction badge(v){ const cls=String(v||\'\').toLowerCase(); return `<span class="badge ${cls}">${v||\'\'}</span>`; }\nfunction fillSelect(sel, data, objects=false, valueKey=\'id\', textKey=\'name\'){\n  const el=$(sel); if(!el) return; const old=el.value; let html=\'<option value="">اختر</option>\';\n  if(objects) html+=data.map(x=>`<option value="${x[valueKey]}">${x[textKey]}</option>`).join(\'\'); else html+=data.map(x=>`<option value="${x}">${x||\'الكل\'}</option>`).join(\'\');\n  el.innerHTML=html; if([...el.options].some(o=>o.value===old)) el.value=old;\n}\nasync function createProperty(){ await saveNew(\'properties\',{name:val(\'pName\'),type:val(\'pType\'),status:val(\'pStatus\'),price:num(\'pPrice\'),location:val(\'pLocation\'),image:val(\'pImage\')||\'🏠\',last_update:today(),notes:val(\'pNotes\')}); }\nasync function createClient(){ await saveNew(\'clients\',{name:val(\'cName\'),phone:val(\'cPhone\'),email:val(\'cEmail\'),national_id:val(\'cNational\'),balance:0,notes:val(\'cNotes\')}); }\nasync function createContract(){ await saveNew(\'contracts\',{property_id:val(\'contractProperty\'),client_id:val(\'contractClient\'),start_date:val(\'contractStart\')||today(),end_date:val(\'contractEnd\')||today(),rent_amount:num(\'contractRent\'),status:\'Active\',payment_cycle:\'monthly\',notes:val(\'contractNotes\')}); }\nasync function createAccount(){ await saveNew(\'accounts\',{entry_date:val(\'accDate\')||today(),type:val(\'accType\'),category:val(\'accCategory\'),description:val(\'accDesc\'),client_id:val(\'accClient\')||null,property_id:val(\'accProperty\')||null,invoice_id:null,amount:num(\'accAmount\')}); }\nasync function createMaintenance(){ await saveNew(\'maintenance\',{property_id:val(\'maintProperty\'),title:val(\'maintTitle\'),priority:val(\'maintPriority\'),status:\'Open\',request_date:today(),cost:num(\'maintCost\'),notes:val(\'maintNotes\')}); }\nasync function createUser(){ await saveNew(\'users\',{username:val(\'uUsername\'),name:val(\'uName\'),role:val(\'uRole\'),password:val(\'uPassword\'),active:true}); }\nasync function saveNew(table,row){ try{ await api(table,{method:\'POST\',body:JSON.stringify(row)}); toast(\'تم الحفظ\'); await loadAll(); }catch(e){toast(e.message,true)} }\nfunction val(id){ return ($(\'#\'+id)?.value||\'\').trim(); } function num(id){ return Number(val(id)||0); }\nasync function delRecord(table,id){ if(!confirm(\'تأكيد الحذف؟\')) return; try{ await api(`${table}/${id}`,{method:\'DELETE\'}); toast(\'تم الحذف\'); await loadAll(); }catch(e){toast(e.message,true)} }\nfunction escapeHtml(v){ return String(v ?? \'\').replace(/[&<>"\']/g, ch => ({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[ch])); }\nfunction editOptions(field, row){\n  const opts = {\n    status: [\'Rented\',\'Vacant\',\'Maintenance\',\'Active\',\'Closed\',\'Open\',\'In Progress\',\'Completed\',\'Pending\'],\n    type: [\'Villa\',\'Apartment\',\'Office\',\'Compound\',\'income\',\'expense\'],\n    role: [\'admin\',\'accountant\',\'operations\',\'maintenance\',\'viewer\'],\n    priority: [\'Low\',\'Medium\',\'High\',\'Urgent\'],\n    payment_cycle: [\'monthly\',\'quarterly\',\'yearly\'],\n    active: [\'1\',\'0\']\n  };\n  if(field === \'property_id\') return (Jawdah.data.properties||[]).map(x=>[x.id,x.name]);\n  if(field === \'client_id\') return (Jawdah.data.clients||[]).map(x=>[x.id,x.name]);\n  if(field === \'invoice_id\') return [[\'\',\'بدون فاتورة\'], ...(Jawdah.data.invoices||[]).map(x=>[x.id,x.invoice_no])];\n  if(opts[field]) return opts[field].map(x=>[x, field===\'role\'?roleName(x):(x===\'1\'?\'نعم\':x===\'0\'?\'لا\':x)]);\n  return null;\n}\nconst EDIT_CONFIG = {\n  properties: {title:\'تعديل عقار\', fields:[[\'name\',\'اسم العقار\',\'text\'],[\'type\',\'النوع\',\'select\'],[\'status\',\'الحالة\',\'select\'],[\'price\',\'السعر\',\'number\'],[\'location\',\'الموقع\',\'text\'],[\'image\',\'رمز/صورة\',\'text\'],[\'notes\',\'ملاحظات\',\'textarea\']]},\n  clients: {title:\'تعديل عميل\', fields:[[\'name\',\'اسم العميل\',\'text\'],[\'phone\',\'الهاتف\',\'text\'],[\'email\',\'البريد\',\'text\'],[\'national_id\',\'الهوية/السجل\',\'text\'],[\'balance\',\'الرصيد الافتتاحي\',\'number\'],[\'notes\',\'ملاحظات\',\'textarea\']]},\n  contracts: {title:\'تعديل عقد\', fields:[[\'property_id\',\'العقار\',\'select\'],[\'client_id\',\'العميل\',\'select\'],[\'start_date\',\'تاريخ البداية\',\'date\'],[\'end_date\',\'تاريخ النهاية\',\'date\'],[\'rent_amount\',\'قيمة الإيجار\',\'number\'],[\'status\',\'الحالة\',\'select\'],[\'payment_cycle\',\'دورة الدفع\',\'select\'],[\'notes\',\'ملاحظات\',\'textarea\']]},\n  accounts: {title:\'تعديل حركة مالية\', fields:[[\'entry_date\',\'التاريخ\',\'date\'],[\'type\',\'النوع\',\'select\'],[\'category\',\'التصنيف\',\'text\'],[\'description\',\'الوصف\',\'text\'],[\'client_id\',\'العميل\',\'select\'],[\'property_id\',\'العقار\',\'select\'],[\'invoice_id\',\'الفاتورة\',\'select\'],[\'amount\',\'المبلغ\',\'number\']]},\n  maintenance: {title:\'تعديل طلب صيانة\', fields:[[\'property_id\',\'العقار\',\'select\'],[\'title\',\'عنوان الطلب\',\'text\'],[\'priority\',\'الأولوية\',\'select\'],[\'status\',\'الحالة\',\'select\'],[\'request_date\',\'تاريخ الطلب\',\'date\'],[\'cost\',\'التكلفة\',\'number\'],[\'notes\',\'ملاحظات\',\'textarea\']]},\n  users: {title:\'تعديل مستخدم\', fields:[[\'username\',\'اسم المستخدم\',\'text\'],[\'name\',\'الاسم\',\'text\'],[\'role\',\'الدور\',\'select\'],[\'active\',\'نشط\',\'select\'],[\'password\',\'كلمة مرور جديدة - اختياري\',\'password\']]}\n};\nfunction editRecord(table,id){\n  const cfg = EDIT_CONFIG[table];\n  const row = byId(table,id);\n  if(!cfg || !row.id){ toast(\'لم يتم العثور على السجل\', true); return; }\n  const fields = cfg.fields.map(([key,label,type])=>{\n    const value = key === \'password\' ? \'\' : (row[key] ?? \'\');\n    const options = editOptions(key,row);\n    if(type === \'textarea\') return `<label>${label}<textarea data-edit-field="${key}" rows="3">${escapeHtml(value)}</textarea></label>`;\n    if(options) return `<label>${label}<select data-edit-field="${key}">${options.map(([v,t])=>`<option value="${escapeHtml(v)}" ${String(value)===String(v)?\'selected\':\'\'}>${escapeHtml(t)}</option>`).join(\'\')}</select></label>`;\n    return `<label>${label}<input data-edit-field="${key}" type="${type}" value="${escapeHtml(value)}" ${type===\'number\'?\'step="0.001"\':\'\'}></label>`;\n  }).join(\'\');\n  $(\'#genericModalBody\').innerHTML = `<h2>${cfg.title}</h2><p class="mini">تعديل مباشر محفوظ في قاعدة البيانات عبر API.</p><div class="form edit-form">${fields}</div><div class="toolbar"><button class="gold-btn" onclick="submitEditRecord(\'${table}\',\'${id}\')">حفظ التعديل</button><button class="ghost" onclick="closeModal(\'genericModal\')">إلغاء</button></div>`;\n  openModal(\'genericModal\');\n}\nasync function submitEditRecord(table,id){\n  try{\n    const data = {};\n    $$(\'#genericModalBody [data-edit-field]\').forEach(el=>{\n      let v = el.value;\n      if(el.type === \'number\') v = Number(v || 0);\n      if(el.dataset.editField === \'active\') v = v === \'1\';\n      if(el.dataset.editField === \'password\' && !v) return;\n      if(v === \'\' && [\'client_id\',\'property_id\',\'invoice_id\'].includes(el.dataset.editField)) v = null;\n      data[el.dataset.editField] = v;\n    });\n    await api(`${table}/${id}`, {method:\'PUT\', body:JSON.stringify(data)});\n    closeModal(\'genericModal\');\n    toast(\'تم حفظ التعديل\');\n    await loadAll();\n  }catch(e){ toast(e.message, true); }\n}\nasync function invoiceFromContract(contractId){ try{ const due=prompt(\'تاريخ الاستحقاق YYYY-MM-DD\', today()); const desc=prompt(\'وصف الفاتورة\',\'Rent invoice\'); const res=await api(\'invoice_from_contract\',{method:\'POST\',body:JSON.stringify({contract_id:contractId,due_date:due||today(),description:desc||\'Rent invoice\'})}); toast(\'تم إنشاء الفاتورة \'+res.item.invoice_no); await loadAll(); showSection(\'invoices\'); }catch(e){toast(e.message,true)} }\nfunction openPayment(id){ const inv=byId(\'invoices\',id); const remaining=Number(inv.amount)-Number(inv.paid_amount); $(\'#payInvoiceId\').value=id; $(\'#payAmount\').value=remaining.toFixed(2); $(\'#payInfo\').textContent=`${inv.invoice_no} - المتبقي ${money(remaining)}`; openModal(\'paymentModal\'); }\nasync function submitPayment(){ try{ await api(\'pay_invoice\',{method:\'POST\',body:JSON.stringify({invoice_id:val(\'payInvoiceId\'),amount:num(\'payAmount\'),method:val(\'payMethod\'),note:val(\'payNote\')})}); closeModal(\'paymentModal\'); toast(\'تم التحصيل وتحديث الحسابات\'); await loadAll(); }catch(e){toast(e.message,true)} }\nfunction printInvoice(id){ const inv=byId(\'invoices\',id), client=byId(\'clients\',inv.client_id), prop=byId(\'properties\',inv.property_id), contract=byId(\'contracts\',inv.contract_id); Jawdah.invoiceForPrint=inv; const rem=Number(inv.amount)-Number(inv.paid_amount);\n  $(\'#invoicePreview\').innerHTML=`<div class="invoice-paper"><div class="head"><div><h1>INVOICE</h1><h2>Quality of Launch</h2><p>Real Estate & Hospitality Services<br>GSM: 96203068 / 92120205<br>C.R: 1466316 | Postal Code: 611 | Sultanate of Oman</p></div><div><h2>${inv.invoice_no}</h2><p>Issue: ${inv.issue_date}<br>Due: ${inv.due_date}<br>Status: ${inv.status}</p></div></div><div class="grid" style="grid-template-columns:1fr 1fr"><div><h3>Client</h3><p>${client.name||\'\'}<br>${client.phone||\'\'}<br>${client.email||\'\'}</p></div><div><h3>Contract / Property</h3><p>${contract.id||\'\'}<br>${prop.name||\'\'}<br>${prop.location||\'\'}</p></div></div><table><thead><tr><th>Description</th><th>Amount</th></tr></thead><tbody><tr><td>${inv.description}</td><td>${money(inv.amount)}</td></tr></tbody></table><h3>Total: ${money(inv.amount)}</h3><h3>Paid: ${money(inv.paid_amount)}</h3><h3>Remaining: ${money(rem)}</h3><div style="margin-top:40px;display:flex;justify-content:space-between"><p>Prepared By: __________</p><p>Client Signature: __________</p><p>Company Stamp: __________</p></div></div>`; openModal(\'invoiceModal\'); }\nfunction downloadInvoice(){ const html=\'<!doctype html><meta charset="utf-8">\'+$(\'#invoicePreview\').innerHTML; downloadFile(`invoice-${Jawdah.invoiceForPrint?.invoice_no||\'file\'}.html`,html,\'text/html\'); }\nfunction clientStatement(id){ const c=byId(\'clients\',id); const inv=(Jawdah.data.invoices||[]).filter(x=>x.client_id===id); const acc=(Jawdah.data.accounts||[]).filter(x=>x.client_id===id); const total=inv.reduce((s,x)=>s+Number(x.amount||0),0), paid=inv.reduce((s,x)=>s+Number(x.paid_amount||0),0); $(\'#genericModalBody\').innerHTML=`<h2>كشف حساب ${c.name}</h2><p>إجمالي الفواتير: ${money(total)} | المدفوع: ${money(paid)} | المتبقي: ${money(total-paid)}</p>${tableHtml([[\'رقم\',\'invoice_no\'],[\'تاريخ\',\'issue_date\'],[\'إجمالي\',\'amount\',(v)=>money(v)],[\'مدفوع\',\'paid_amount\',(v)=>money(v)],[\'حالة\',\'status\',(v)=>badge(v)]],inv)}<h3>الحركات</h3>${tableHtml([[\'تاريخ\',\'entry_date\'],[\'نوع\',\'type\'],[\'وصف\',\'description\'],[\'مبلغ\',\'amount\',(v)=>money(v)]],acc)}`; openModal(\'genericModal\'); }\nfunction openModal(id){ $(\'#\'+id).classList.add(\'show\'); ensureEnglishDigits($(\'#\'+id)); } function closeModal(id){ $(\'#\'+id).classList.remove(\'show\'); }\nasync function downloadBackup(){ try{ const res=await api(\'backup\'); downloadFile(\'jawdah-cloud-backup.json\', JSON.stringify(res.backup,null,2), \'application/json\'); }catch(e){toast(e.message,true)} }\nfunction downloadFile(name,content,type=\'text/plain\'){ const a=document.createElement(\'a\'); a.href=URL.createObjectURL(new Blob([content],{type})); a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1000); }\nasync function exportCsv(table){ try{ const res=await fetch(\'/api/export/\'+table,{headers:{Authorization:\'Bearer \'+Jawdah.token}}); if(!res.ok) throw new Error(\'Export failed\'); const blob=await res.blob(); const a=document.createElement(\'a\'); a.href=URL.createObjectURL(blob); a.download=\'jawdah-\'+table+\'.csv\'; a.click(); }catch(e){toast(e.message,true)} }\nfunction renderReports(){\n  const k=Jawdah.dashboard.kpis; $(\'#reportsBox\').innerHTML=`<div class="kpis grid"><div class="kpi"><span>الإيرادات</span><strong>${money(k.income)}</strong></div><div class="kpi"><span>المصروفات</span><strong>${money(k.expense)}</strong></div><div class="kpi"><span>الصافي</span><strong>${money(k.net)}</strong></div><div class="kpi"><span>المتأخرات</span><strong>${money(k.overdue)}</strong></div></div><div class="card"><h3>قرارات تنفيذية</h3>${Jawdah.dashboard.decisions.map(d=>`<p><span class="badge">${d.level}</span> ${d.text}</p>`).join(\'\')}</div>`;\n}\nfunction runQA(){\n  const problems=[]; const data=Jawdah.data;\n  (data.contracts||[]).forEach(c=>{ if(!byId(\'properties\',c.property_id).id) problems.push(\'عقد بدون عقار: \'+c.id); if(!byId(\'clients\',c.client_id).id) problems.push(\'عقد بدون عميل: \'+c.id); });\n  (data.invoices||[]).forEach(i=>{ if(!byId(\'contracts\',i.contract_id).id) problems.push(\'فاتورة بدون عقد: \'+i.invoice_no); if(Number(i.paid_amount)>Number(i.amount)) problems.push(\'فاتورة مدفوعة أكثر من الإجمالي: \'+i.invoice_no); });\n  const score=Math.max(0,100-problems.length*10);\n  $(\'#qaBox\').innerHTML=`<div class="kpi"><span>نتيجة الجاهزية</span><strong>${fmt(score)}%</strong></div>${problems.length?problems.map(p=>`<p class="badge overdue">${p}</p>`).join(\'\'):\'<p class="badge paid">كل الفحوصات الأساسية ناجحة</p>\'}`;\n}\nfunction drawCharts(){ if(!Jawdah.dashboard) return; drawLine(\'incomeChart\',Jawdah.dashboard.series.map(x=>x.income),Jawdah.dashboard.series.map(x=>x.expense)); drawDonut(\'occupancyChart\',Jawdah.dashboard.kpis.occupancy); drawBar(\'expenseChart\',Jawdah.dashboard.series.map(x=>x.expense)); }\nfunction ctx(id){ const c=$(\'#\'+id); return c?c.getContext(\'2d\'):null; }\nfunction prepCanvas(c){ const r=c.getBoundingClientRect(); c.width=r.width*devicePixelRatio; c.height=r.height*devicePixelRatio; const g=c.getContext(\'2d\'); g.scale(devicePixelRatio,devicePixelRatio); return [g,r.width,r.height]; }\nfunction drawLine(id,a,b){ const c=$(\'#\'+id); if(!c) return; const [g,w,h]=prepCanvas(c); g.clearRect(0,0,w,h); const vals=[...a,...b,1], max=Math.max(...vals)*1.22; const area=(arr,color1,color2)=>{ g.beginPath(); arr.forEach((v,i)=>{ const x=32+i*(w-64)/(arr.length-1||1), y=h-34-(v/max)*(h-70); i?g.lineTo(x,y):g.moveTo(x,y); }); g.lineTo(w-32,h-34); g.lineTo(32,h-34); g.closePath(); const gr=g.createLinearGradient(0,28,0,h-34); gr.addColorStop(0,color1); gr.addColorStop(1,color2); g.fillStyle=gr; g.fill(); }; const plot=(arr,color)=>{ g.beginPath(); arr.forEach((v,i)=>{ const x=32+i*(w-64)/(arr.length-1||1), y=h-34-(v/max)*(h-70); i?g.lineTo(x,y):g.moveTo(x,y); }); g.strokeStyle=color; g.lineWidth=4; g.shadowBlur=16; g.shadowColor=color; g.stroke(); arr.forEach((v,i)=>{ const x=32+i*(w-64)/(arr.length-1||1), y=h-34-(v/max)*(h-70); g.beginPath(); g.fillStyle=color; g.arc(x,y,4,0,Math.PI*2); g.fill(); }); g.shadowBlur=0; }; g.strokeStyle=\'rgba(255,255,255,.12)\'; for(let i=0;i<5;i++){let y=24+i*(h-58)/4;g.beginPath();g.moveTo(24,y);g.lineTo(w-24,y);g.stroke();} area(a,\'rgba(246,215,127,.28)\',\'rgba(246,215,127,0)\'); plot(a,\'#f6d77f\'); plot(b,\'#8fbfff\'); }\nfunction drawDonut(id,p){ const c=$(\'#\'+id); if(!c) return; const [g,w,h]=prepCanvas(c); g.clearRect(0,0,w,h); const x=w/2,y=h/2,r=Math.min(w,h)/3; g.lineWidth=26; g.lineCap=\'round\'; g.strokeStyle=\'rgba(255,255,255,.12)\'; g.beginPath(); g.arc(x,y,r,0,Math.PI*2); g.stroke(); const gr=g.createLinearGradient(x-r,y-r,x+r,y+r); gr.addColorStop(0,\'#fff0b8\'); gr.addColorStop(.5,\'#d8b15b\'); gr.addColorStop(1,\'#8f631b\'); g.strokeStyle=gr; g.shadowBlur=20; g.shadowColor=\'rgba(216,177,91,.4)\'; g.beginPath(); g.arc(x,y,r,-Math.PI/2,-Math.PI/2+Math.PI*2*p/100); g.stroke(); g.shadowBlur=0; g.fillStyle=\'#fff\'; g.font=\'800 30px Segoe UI\'; g.textAlign=\'center\'; g.fillText(fmt(p)+\'%\',x,y+6); g.font=\'13px Segoe UI\'; g.fillStyle=\'rgba(255,255,255,.7)\'; g.fillText(\'Occupancy\',x,y+28); }\nfunction drawBar(id,arr){ const c=$(\'#\'+id); if(!c) return; const [g,w,h]=prepCanvas(c); g.clearRect(0,0,w,h); const max=Math.max(...arr,1)*1.2, bw=(w-60)/arr.length*.65; arr.forEach((v,i)=>{const x=30+i*(w-60)/arr.length+10, bh=(v/max)*(h-50); const grd=g.createLinearGradient(0,h-25-bh,0,h-25); grd.addColorStop(0,\'#f6d77f\'); grd.addColorStop(1,\'#8f631b\'); g.fillStyle=grd; g.shadowBlur=16; g.shadowColor=\'rgba(216,177,91,.38)\'; g.fillRect(x,h-25-bh,bw,bh);}); g.shadowBlur=0; }\nfunction initClock(){ setInterval(()=>{ const d=new Date(); $(\'#clock\').textContent=d.toLocaleTimeString(\'en-US\',{hour12:false}); },1000); }\nfunction bind(){\n  $(\'#loginBtn\').onclick=login; $(\'#logoutBtn\').onclick=logout; $(\'#menuBtn\').onclick=()=>$(\'#sidebar\').classList.toggle(\'open\'); $(\'#globalSearch\').oninput=()=>renderAll();\n  document.addEventListener(\'input\',e=>ensureEnglishDigits(e.target));\n  document.addEventListener(\'keydown\',e=>{ if(e.ctrlKey&&e.key.toLowerCase()===\'k\'){ e.preventDefault(); $(\'#globalSearch\').focus(); } if(e.key===\'/\' && document.activeElement.tagName!==\'INPUT\'){e.preventDefault();$(\'#globalSearch\').focus();} });\n}\nwindow.JAWDAH_CLOUD_CHECK=()=>({status:\'v40-executive-dashboard\',user:Jawdah.user?.username||null,tables:Object.fromEntries(Object.entries(Jawdah.data).map(([k,v])=>[k,v.length])),dashboard:Jawdah.dashboard});\nwindow.addEventListener(\'load\',()=>{ bind(); initClock(); checkSession(); setInterval(()=>ensureEnglishDigits(),3000); });\n'

# Keep fallback assets synchronized with the real public files.
# This protects Railway deployments even if static routing uses the fallback branch.
def _load_public_asset(name: str, fallback: str) -> str:
    try:
        path = PUBLIC_DIR / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return fallback

FALLBACK_APP_HTML = _load_public_asset("app.html", FALLBACK_INDEX_HTML)
FALLBACK_INDEX_HTML = _load_public_asset("index.html", FALLBACK_INDEX_HTML)
FALLBACK_CSS = _load_public_asset("app.css", FALLBACK_CSS)
FALLBACK_JS = _load_public_asset("app.js", FALLBACK_JS)


ROLE_PERMISSIONS = {
    "owner": {"all"},
    "admin": {"all"},
    "deputy": {"all"},
    "accountant": {"dashboard", "properties:read", "clients:read", "contracts", "invoices", "accounts", "purchase_invoices", "revenues", "salaries", "admin_expenses", "inventory_items", "inventory_transactions", "hospitality_rooms:read", "hospitality_bookings", "hospitality_events", "hospitality_season_rates", "hospitality_folios:read", "bank_transactions", "chart_accounts", "financial_periods", "approvals", "bank_reconciliations", "reports", "backup:export", "branches:read", "audit:read", "estate_properties:read", "estate_buildings:read", "estate_apartments:read", "estate_rooms:read", "estate_accessories:read", "estate_maintenance", "accounting_budgets"},
    "operations": {"dashboard", "properties", "clients", "contracts", "invoices", "accounts", "maintenance", "inventory_items", "inventory_transactions", "hospitality_rooms", "hospitality_bookings", "hospitality_events", "hospitality_season_rates", "hospitality_folios:read", "reports:read", "approvals:request", "branches", "estate_properties", "estate_buildings", "estate_apartments", "estate_rooms", "estate_accessories", "estate_maintenance", "accounting_budgets:read"},
    # NAJJAR sales desk — stock, sales, imports (no capital / company admin).
    "sales": {
        "dashboard", "properties", "clients", "contracts:read", "invoices:read",
        "inventory_items", "inventory_transactions", "reports:read", "branches:read",
        "estate_properties:read", "estate_buildings:read", "estate_apartments:read",
        "estate_rooms:read", "estate_accessories:read",
    },
    "reception": {"dashboard", "properties:read", "clients", "contracts:read", "invoices:read", "hospitality_events", "hospitality_bookings:read", "reports:read", "estate_properties:read", "estate_buildings:read", "estate_apartments:read", "estate_rooms:read", "messages"},
    "maintenance": {"dashboard", "properties:read", "maintenance", "inventory_items", "inventory_transactions", "hospitality_rooms:read", "hospitality_bookings:read", "hospitality_events:read", "hospitality_season_rates:read", "hospitality_folios:read", "purchase_invoices:read", "reports:read", "branches:read", "estate_properties:read", "estate_buildings:read", "estate_apartments:read", "estate_rooms:read", "estate_accessories:read", "estate_maintenance", "accounting_budgets:read"},
    "viewer": {"dashboard", "properties:read", "clients:read", "contracts:read", "invoices:read", "accounts:read", "purchase_invoices:read", "revenues:read", "salaries:read", "admin_expenses:read", "inventory_items:read", "hospitality_rooms:read", "hospitality_bookings:read", "hospitality_events:read", "hospitality_season_rates:read", "hospitality_folios:read", "bank_transactions:read", "chart_accounts:read", "financial_periods:read", "approvals:read", "bank_reconciliations:read", "maintenance:read", "reports:read", "backup:export", "branches:read", "audit:read", "estate_properties:read", "estate_buildings:read", "estate_apartments:read", "estate_rooms:read", "estate_accessories:read", "estate_maintenance:read", "accounting_budgets:read"},
}
ROLE_PERMISSIONS["operations"].update({"estate_actions_convert", "estate_actions_contract_create"})
ROLE_PERMISSIONS["accountant"].update({"estate_actions_contract_close", "estate_actions_month_close", "estate_actions_pricing_edit"})
ROLE_PERMISSIONS["reception"].update({"estate_actions_convert"})
ROLE_PERMISSIONS["sales"].update({"estate_actions_convert"})
ROLE_LABELS_AR = {
    "owner": "مجلس إدارة",
    "admin": "مدير النظام",
    "deputy": "نائب المدير",
    "accountant": "محاسبة",
    "operations": "تشغيل",
    "sales": "مبيعات",
    "reception": "استقبال",
    "maintenance": "صيانة",
    "viewer": "مشاهدة فقط",
}
# NAJJAR staff console sections each role may open.
NAJJAR_SECTION_ACCESS = {
    "owner": {"dashboard", "vehicles", "purchases", "sales", "expenses", "capital", "transactions", "imports", "staff", "company"},
    "admin": {"dashboard", "vehicles", "purchases", "sales", "expenses", "capital", "transactions", "imports", "staff", "company"},
    "operations": {"dashboard", "vehicles", "purchases", "sales", "expenses", "transactions", "imports", "staff", "company"},
    "sales": {"dashboard", "vehicles", "sales", "imports", "staff", "company"},
    "accountant": {"dashboard", "vehicles", "purchases", "sales", "expenses", "capital", "transactions", "staff", "company"},
    "viewer": {"dashboard", "vehicles", "sales", "staff", "company"},
}

TABLES = {
    "branches": ["id", "code", "name", "city", "address", "manager", "active", "notes", "created_at"],
    "properties": ["id", "name", "type", "status", "price", "location", "building_no", "apartment_no", "room_no", "latitude", "longitude", "image", "last_update", "notes", "branch_id"],
    "clients": ["id", "name", "phone", "email", "national_id", "id_card_image", "balance", "notes"],
    "contracts": ["id", "contract_no", "contract_type", "property_id", "client_id", "tenant_nationality", "tenant_id_no", "unit_details", "start_date", "end_date", "rent_amount", "deposit_amount", "deposit_received", "deposit_received_at", "deposit_received_amount", "late_fee", "grace_days", "renewal_notice_days", "status", "payment_cycle", "legal_terms", "company_signatory", "approved_at", "ended_at", "attachments", "notes"],
    "invoices": ["id", "invoice_no", "contract_id", "client_id", "property_id", "issue_date", "due_date", "description", "invoice_type", "subtotal", "vat_rate", "vat_amount", "grand_total", "amount", "paid_amount", "status", "is_void", "void_reason", "voided_at", "sequence_year", "sequence_no", "reissued_from"],
    "payments": ["id", "invoice_id", "client_id", "property_id", "contract_id", "payment_date", "amount", "method", "note", "payment_proof_image"],
    "accounts": ["id", "entry_date", "type", "category", "description", "client_id", "property_id", "invoice_id", "amount"],
    "purchase_invoices": ["id", "purchase_no", "supplier", "invoice_date", "due_date", "category", "description", "amount", "paid_amount", "status", "property_id", "account_id"],
    "revenues": ["id", "revenue_no", "revenue_date", "source", "category", "description", "amount", "client_id", "property_id", "account_id"],
    "salaries": ["id", "employee_no", "employee_name", "salary_month", "project_name", "basic_salary", "allowances", "deductions", "net_salary", "status", "payment_date", "account_id", "import_batch_id"],
    "payroll_import_batches": ["id", "import_type", "file_name", "project_name", "salary_month", "status", "row_count", "summary_json", "created_by", "created_at"],
    "admin_expenses": ["id", "expense_date", "category", "description", "amount", "supplier", "property_id", "account_id"],
    "inventory_items": ["id", "sku", "name", "category", "unit", "quantity", "min_quantity", "unit_cost", "location", "property_id", "notes"],
    "inventory_transactions": ["id", "item_id", "tx_date", "tx_type", "quantity", "unit_cost", "reference", "notes"],
    "hospitality_rooms": ["id", "property_id", "room_code", "room_type", "capacity", "rate_per_night", "status", "notes"],
    "hospitality_bookings": ["id", "room_id", "client_id", "guest_name", "guest_phone", "checkin_date", "checkout_date", "nights", "rate_per_night", "total_amount", "paid_amount", "balance_amount", "status", "booking_source", "property_id", "notes", "created_at"],
    "hospitality_events": [
        "id", "service_kind", "package_code", "package_name", "client_id", "client_name", "phone",
        "event_date", "guests", "location_zone", "venue_location", "waiters", "supervisors", "dallahs",
        "total_amount", "deposit_required", "paid_amount", "balance_amount", "status",
        "outside_nizwa", "notes", "created_by", "created_at",
    ],
    "hospitality_season_rates": ["id", "property_id", "room_type", "season_name", "start_date", "end_date", "nightly_rate", "active", "notes"],
    "hospitality_folios": ["id", "booking_id", "folio_no", "issue_date", "total_amount", "paid_amount", "balance_amount", "status", "notes"],
    "bank_transactions": ["id", "bank_date", "bank_name", "reference", "type", "description", "amount", "matched_account_id", "matched_invoice_id", "matched_payment_id", "status"],
    "chart_accounts": ["id", "code", "name", "type", "parent_code", "active", "notes"],
    "financial_periods": ["id", "period_name", "start_date", "end_date", "status", "closed_by", "closed_at", "notes"],
    "accounting_budgets": ["id", "month_key", "revenue_target", "expense_budget", "collection_target", "cash_reserve_target", "notes", "created_at", "updated_at"],
    "approvals": ["id", "entity", "entity_id", "request_type", "status", "requested_by", "approved_by", "requested_at", "approved_at", "notes"],
    "bank_reconciliations": ["id", "bank_name", "period_name", "book_balance", "bank_balance", "difference", "status", "reconciled_by", "reconciled_at", "notes", "matched_count", "unmatched_count", "period_start", "period_end"],
    "maintenance": ["id", "property_id", "title", "priority", "status", "request_date", "cost", "notes"],
    "estate_properties": ["id", "name", "status", "location", "building_count", "apartment_count", "room_count", "base_rent_price", "service_charge", "attachments", "manager_name", "tenant_client_id", "tenant_phone", "notes", "image", "last_update"],
    "estate_buildings": ["id", "property_id", "name", "status", "location", "unit_count", "apartment_count", "room_count", "base_rent_price", "service_charge", "attachments", "manager_name", "tenant_client_id", "tenant_phone", "description", "notes", "image", "last_update"],
    "estate_apartments": ["id", "property_id", "building_id", "name", "unit_kind", "status", "room_count", "floor_no", "area_sqm", "rent_price", "booking_deposit", "prepaid_amount", "reservation_start_date", "reservation_end_date", "booked_client_name", "booked_client_phone", "booked_client_id", "booked_by_employee", "maintenance_notes", "maintenance_cost", "attachments", "manager_name", "tenant_client_id", "tenant_phone", "notes", "image", "last_update"],
    "estate_rooms": ["id", "property_id", "building_id", "apartment_id", "name", "unit_kind", "room_type", "status", "floor_no", "area_sqm", "rent_price", "booking_deposit", "prepaid_amount", "reservation_start_date", "reservation_end_date", "booked_client_name", "booked_client_phone", "booked_client_id", "booked_by_employee", "maintenance_notes", "maintenance_cost", "attachments", "manager_name", "tenant_client_id", "tenant_phone", "notes", "image", "last_update"],
    "estate_accessories": ["id", "property_id", "building_id", "apartment_id", "room_id", "name", "category", "status", "qty", "unit_cost", "supplier", "invoice_no", "responsible_name", "notes", "last_update"],
    "estate_maintenance": ["id", "property_id", "building_id", "apartment_id", "room_id", "title", "status", "priority", "responsible_name", "assigned_team", "parts_details", "parts_cost", "labor_cost", "invoice_no", "invoice_date", "vendor_name", "total_cost", "approved_by", "maintenance_date", "next_followup_date", "closed_at", "notes"],
    "estate_contracts": ["id", "contract_no", "entity_type", "entity_id", "property_id", "building_id", "apartment_id", "room_id", "client_id", "start_date", "end_date", "rent_amount", "payment_cycle", "status", "created_by", "created_at", "approved_by", "approved_at", "activated_by", "activated_at", "closed_at", "close_note", "attachments", "notes"],
    "estate_contract_invoices": ["id", "invoice_no", "contract_id", "due_date", "amount", "paid_amount", "status", "issued_at", "note"],
    "estate_contract_settlements": ["id", "contract_id", "close_date", "total_scheduled", "total_paid", "outstanding_due", "future_cancelled", "closed_by", "note", "created_at"],
    "estate_month_closes": ["id", "month_key", "status", "total_invoiced", "total_collected", "outstanding_due", "closed_by", "closed_at", "note"],
    "estate_status_history": ["id", "entity_type", "entity_id", "property_id", "building_id", "apartment_id", "room_id", "old_status", "new_status", "changed_by", "changed_at", "note"],
    "estate_reservation_invoices": ["id", "invoice_no", "entity_type", "entity_id", "property_id", "building_id", "apartment_id", "room_id", "client_id", "client_name", "issued_by", "issue_date", "due_date", "rent_price", "deposit_amount", "prepaid_amount", "total_amount", "status", "note"],
    "users": ["id", "username", "name", "role", "active", "email", "must_change_password", "password_changed_at", "created_at", "last_login"],
    "audit_log": ["id", "created_at", "username", "action", "entity", "entity_id", "details"],
}

FULL_ACCESS_USERNAMES = frozenset({"waleed.najjar", "hamad.sumoom"})
PRIMARY_OWNER_USERNAMES = FULL_ACCESS_USERNAMES
DAILY_OPS_MANAGER_USERNAMES = frozenset(NAJJAR_TEAM_USERNAMES)
RESTRICTED_ADMIN_USERNAMES: frozenset[str] = frozenset()

WRITE_ROLES = {"owner", "admin", "deputy", "accountant", "operations", "sales", "reception", "maintenance"}

OTP_CODES: Dict[str, Tuple[str, float]] = {}
OTP_TTL_SECONDS = 300
PENDING_LOGINS: Dict[str, Dict[str, Any]] = {}


def ensure_security_runtime_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS security_otp_codes (
            username TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            exp REAL NOT NULL,
            purpose TEXT NOT NULL DEFAULT 'login',
            tries INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS security_pending_logins (
            challenge_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            remember INTEGER NOT NULL DEFAULT 0,
            device_fingerprint TEXT NOT NULL DEFAULT '',
            device_label TEXT NOT NULL DEFAULT '',
            user_agent TEXT NOT NULL DEFAULT '',
            expires_ts REAL NOT NULL,
            method TEXT NOT NULL DEFAULT 'email',
            totp_secret TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )
    try:
        cols = {r[1] for r in db.execute("PRAGMA table_info(security_pending_logins)").fetchall()}
        if "method" not in cols:
            db.execute("ALTER TABLE security_pending_logins ADD COLUMN method TEXT NOT NULL DEFAULT 'email'")
        if "totp_secret" not in cols:
            db.execute("ALTER TABLE security_pending_logins ADD COLUMN totp_secret TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass


def store_otp_code(db: Optional[sqlite3.Connection], username: str, code: str, purpose: str = "login") -> None:
    exp = time.time() + OTP_TTL_SECONDS
    OTP_CODES[username] = (code, exp)
    if db is None:
        return
    ensure_security_runtime_tables(db)
    db.execute(
        """
        INSERT INTO security_otp_codes(username, code, exp, purpose, tries, created_at)
        VALUES(?,?,?,?,0,?)
        ON CONFLICT(username) DO UPDATE SET
            code=excluded.code,
            exp=excluded.exp,
            purpose=excluded.purpose,
            tries=0,
            created_at=excluded.created_at
        """,
        (username, code, exp, purpose, now_iso()),
    )


def load_otp_code(db: Optional[sqlite3.Connection], username: str) -> Optional[Tuple[str, float]]:
    now_ts = time.time()
    mem = OTP_CODES.get(username)
    if mem and now_ts <= float(mem[1]):
        return mem
    if mem:
        OTP_CODES.pop(username, None)
    if db is None:
        return None
    ensure_security_runtime_tables(db)
    row = db.execute(
        "SELECT code, exp FROM security_otp_codes WHERE username=?",
        (username,),
    ).fetchone()
    if not row:
        return None
    if now_ts > float(row["exp"]):
        db.execute("DELETE FROM security_otp_codes WHERE username=?", (username,))
        return None
    pair = (str(row["code"]), float(row["exp"]))
    OTP_CODES[username] = pair
    return pair


def clear_otp_code(db: Optional[sqlite3.Connection], username: str) -> None:
    OTP_CODES.pop(username, None)
    if db is None:
        return
    ensure_security_runtime_tables(db)
    db.execute("DELETE FROM security_otp_codes WHERE username=?", (username,))


def store_pending_login(db: sqlite3.Connection, challenge_id: str, payload: Dict[str, Any]) -> None:
    ensure_security_runtime_tables(db)
    PENDING_LOGINS[challenge_id] = dict(payload)
    db.execute(
        """
        INSERT INTO security_pending_logins(
            challenge_id, user_id, username, remember, device_fingerprint,
            device_label, user_agent, expires_ts, method, totp_secret, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(challenge_id) DO UPDATE SET
            user_id=excluded.user_id,
            username=excluded.username,
            remember=excluded.remember,
            device_fingerprint=excluded.device_fingerprint,
            device_label=excluded.device_label,
            user_agent=excluded.user_agent,
            expires_ts=excluded.expires_ts,
            method=excluded.method,
            totp_secret=excluded.totp_secret,
            created_at=excluded.created_at
        """,
        (
            challenge_id,
            payload.get("user_id"),
            payload.get("username"),
            1 if payload.get("remember") else 0,
            payload.get("device_fingerprint") or "",
            payload.get("device_label") or "",
            payload.get("user_agent") or "",
            float(payload.get("expires_ts") or 0),
            payload.get("method") or "email",
            payload.get("totp_secret") or "",
            now_iso(),
        ),
    )


def load_pending_login(db: sqlite3.Connection, challenge_id: str) -> Optional[Dict[str, Any]]:
    now_ts = time.time()
    mem = PENDING_LOGINS.get(challenge_id)
    if mem and now_ts <= float(mem.get("expires_ts") or 0):
        return dict(mem)
    if mem:
        PENDING_LOGINS.pop(challenge_id, None)
    ensure_security_runtime_tables(db)
    row = db.execute(
        "SELECT * FROM security_pending_logins WHERE challenge_id=?",
        (challenge_id,),
    ).fetchone()
    if not row:
        return None
    if now_ts > float(row["expires_ts"]):
        db.execute("DELETE FROM security_pending_logins WHERE challenge_id=?", (challenge_id,))
        return None
    keys = row.keys()
    payload = {
        "user_id": row["user_id"],
        "username": row["username"],
        "remember": bool(row["remember"]),
        "device_fingerprint": row["device_fingerprint"] or "",
        "device_label": row["device_label"] or "",
        "user_agent": row["user_agent"] or "",
        "expires_ts": float(row["expires_ts"]),
        "method": (row["method"] if "method" in keys else "email") or "email",
        "totp_secret": (row["totp_secret"] if "totp_secret" in keys else "") or "",
    }
    PENDING_LOGINS[challenge_id] = dict(payload)
    return payload


def clear_pending_login(db: sqlite3.Connection, challenge_id: str) -> None:
    PENDING_LOGINS.pop(challenge_id, None)
    ensure_security_runtime_tables(db)
    db.execute("DELETE FROM security_pending_logins WHERE challenge_id=?", (challenge_id,))


def build_platform_readiness(db: sqlite3.Connection) -> Dict[str, Any]:
    missing_email = int(
        db.execute(
            "SELECT COUNT(*) FROM users WHERE active=1 AND (email IS NULL OR trim(email)='')"
        ).fetchone()[0]
        or 0
    )
    try:
        totp_users = int(
            db.execute(
                "SELECT COUNT(*) FROM users WHERE active=1 AND COALESCE(totp_enabled,0)=1"
            ).fetchone()[0]
            or 0
        )
    except Exception:
        totp_users = 0
    security = security_platform_status(users_missing_email=missing_email, totp_users=totp_users)
    storage = lq_object_storage.object_storage_status()
    database = lq_postgres.build_database_platform_status(db, TABLES)
    disk = storage_status()
    offsite = offsite_config()
    components = {
        "security": security,
        "storage": storage,
        "database": database,
        "offsite": offsite,
        "disk": {
            "path": disk.get("path"),
            "free_gb": disk.get("free_gb"),
            "warning": disk.get("warning"),
            "ready": not bool(disk.get("warning")),
        },
    }
    ready_flags = [
        bool(security.get("ready")),
        bool(storage.get("production_storage_ready", storage.get("ready"))),
        bool(database.get("ready", database.get("primary_ready"))),
        bool(offsite.get("enabled")),
        bool(components["disk"]["ready"]),
    ]
    score = round(sum(1 for x in ready_flags if x) / len(ready_flags) * 100, 1)
    return {
        "ok": True,
        "version": APP_VERSION,
        "platform_score": score,
        "platform_ready": all(ready_flags),
        "components": components,
        "notes": [
            "SQLite هو المحرك الأساسي للإنتاج",
            "التخزين المحلي الدائم + مرآة Volume جاهزان",
            "MFA عبر TOTP (تطبيق المصادقة) جاهز بدون SMTP",
            "PostgreSQL ظلّي اختياري عند ضبط DATABASE_URL",
            "Railway Bucket اختياري للنسخ السحابي الإضافي",
        ],
    }
MODULE_FIX_PREVIEW_TTL_SECONDS = max(300, int(os.environ.get("LQ_MODULE_FIX_PREVIEW_TTL", "1800") or "1800"))
MODULE_FIX_MIN_ATTEMPTS_FOR_ALERT = max(1, int(os.environ.get("LQ_MODULE_FIX_MIN_ATTEMPTS_ALERT", "5") or "5"))
MODULE_FIX_MIN_SUCCESS_RATE = float(os.environ.get("LQ_MODULE_FIX_MIN_SUCCESS_RATE", "85") or "85")
MODULE_FIX_MAX_REJECTED = max(0, int(os.environ.get("LQ_MODULE_FIX_MAX_REJECTED", "3") or "3"))
MODULE_FIX_MIN_APPLY_EFFECTIVENESS = float(os.environ.get("LQ_MODULE_FIX_MIN_APPLY_EFFECTIVENESS", "65") or "65")
MODULE_FIX_PREVIEWS: Dict[str, Dict[str, Any]] = {}
BIOMETRIC_CHALLENGE_TTL_SECONDS = 180
BIOMETRIC_CHALLENGES: Dict[str, Dict[str, Any]] = {}
BIOMETRIC_FLOW_STATES: Dict[str, Dict[str, Any]] = {}
SUPPORT_PHONE = os.environ.get("LQ_SUPPORT_PHONE", "+96898203088")
SUPPORT_EMAIL = os.environ.get("LQ_SUPPORT_EMAIL", "jiwdat@gmail.com")
VAT_RATE = float(os.environ.get("LQ_VAT_RATE", "0.05") or "0.05")
COMPANY_VAT_NO = os.environ.get("LQ_VAT_NO", "OM-VAT-PENDING").strip()
AI_ASSISTANT_NAME = "WALEED"
OPENAI_API_KEY = (os.environ.get("OPENAI_API_KEY") or os.environ.get("LQ_OPENAI_API_KEY") or "").strip()
AI_MODEL = os.environ.get("LQ_AI_MODEL", "gpt-4o-mini").strip()
AI_DAILY_LIMIT = max(1, int(os.environ.get("LQ_AI_DAILY_LIMIT", "50") or "50"))
APPROVAL_THRESHOLD = float(os.environ.get("LQ_APPROVAL_THRESHOLD", "3000") or "3000")
WORKFLOW_POLICY_DEFAULTS: Dict[str, Any] = {
    # If enabled, only owner/admin can activate contracts from API.
    "contract_activation_owner_admin_only": True,
    # Dynamic thresholds used by workflow approvals engine.
    "manual_invoice_approval_threshold": APPROVAL_THRESHOLD,
    "payment_approval_threshold": APPROVAL_THRESHOLD,
    # How far invoice due date can be backdated/future-dated by non-admin users.
    "invoice_backdate_limit_days": 7,
    "invoice_future_limit_days": 180,
}
STAFF_APP_VERSION = os.environ.get("LQ_STAFF_APP_VERSION", "70.4.0").strip()
PRODUCTION_URL = os.environ.get("LQ_PRODUCTION_URL", "https://web-production-08d73.up.railway.app").strip()
STAFF_DOWNLOAD_APK = os.environ.get(
    "LQ_STAFF_APK_URL",
    f"{PRODUCTION_URL.rstrip('/')}/releases/android/Launch-Quality-Staff.apk",
).strip()
STAFF_DOWNLOAD_ZIP = os.environ.get(
    "LQ_STAFF_ZIP_URL",
    f"{PRODUCTION_URL.rstrip('/')}/lq-portable.zip",
).strip()
LQ_DATABASE_URL = (os.environ.get("LQ_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()

APPROVAL_DECIDE_ROLES = {
    "contract": {"admin", "owner"},
    "manual_invoice": {"admin", "owner", "accountant"},
    "invoice": {"admin", "owner", "accountant"},
    "payment": {"admin", "owner", "accountant"},
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def today() -> str:
    return date.today().isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(raw: str) -> bytes:
    cleaned = str(raw or "").strip()
    if not cleaned:
        return b""
    padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def rp_id_from_origin(origin_url: str) -> str:
    host = urllib.parse.urlparse(origin_url or "").hostname or ""
    return host or "localhost"


def cleanup_biometric_challenges() -> None:
    now_ts = time.time()
    expired = [key for key, item in BIOMETRIC_CHALLENGES.items() if now_ts > float(item.get("expires", 0))]
    for key in expired:
        BIOMETRIC_CHALLENGES.pop(key, None)
    expired_states = [key for key, item in BIOMETRIC_FLOW_STATES.items() if now_ts > float(item.get("expires", 0))]
    for key in expired_states:
        BIOMETRIC_FLOW_STATES.pop(key, None)


def cleanup_module_fix_previews() -> None:
    now_ts = time.time()
    expired = [key for key, item in MODULE_FIX_PREVIEWS.items() if now_ts > float(item.get("expires_ts", 0))]
    for key in expired:
        MODULE_FIX_PREVIEWS.pop(key, None)


def module_fix_preview_key(username: str, preview_id: str) -> str:
    return f"{str(username or '').strip().lower()}::{str(preview_id or '').strip()}"


def _coerce_workflow_policy_value(key: str, value: Any) -> Any:
    if key not in WORKFLOW_POLICY_DEFAULTS:
        raise ValueError(f"Unsupported workflow policy: {key}")
    default = WORKFLOW_POLICY_DEFAULTS[key]
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            if token in ("1", "true", "yes", "on"):
                return True
            if token in ("0", "false", "no", "off"):
                return False
        raise ValueError(f"{key} must be boolean")
    if isinstance(default, int):
        iv = int(value)
        if iv < 0:
            raise ValueError(f"{key} must be >= 0")
        return iv
    if isinstance(default, float):
        fv = float(value)
        if fv <= 0:
            raise ValueError(f"{key} must be > 0")
        return fv
    return value


def _workflow_policy_float(policies: Dict[str, Any], key: str) -> float:
    try:
        return float(policies.get(key, WORKFLOW_POLICY_DEFAULTS[key]))
    except Exception:
        return float(WORKFLOW_POLICY_DEFAULTS[key])


def _workflow_policy_int(policies: Dict[str, Any], key: str) -> int:
    try:
        return int(policies.get(key, WORKFLOW_POLICY_DEFAULTS[key]))
    except Exception:
        return int(WORKFLOW_POLICY_DEFAULTS[key])


def _workflow_policy_bool(policies: Dict[str, Any], key: str) -> bool:
    raw = policies.get(key, WORKFLOW_POLICY_DEFAULTS[key])
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(raw)


def load_workflow_policies(db: sqlite3.Connection) -> Dict[str, Any]:
    out = dict(WORKFLOW_POLICY_DEFAULTS)
    rows = db.execute("SELECT key, value_json FROM workflow_policies").fetchall()
    for row in rows:
        key = str(row["key"] or "").strip()
        if key not in WORKFLOW_POLICY_DEFAULTS:
            continue
        try:
            out[key] = json.loads(row["value_json"])
        except Exception:
            out[key] = WORKFLOW_POLICY_DEFAULTS[key]
    return out


def validate_invoice_due_date_by_policy(
    due_date_raw: Any,
    user: Dict[str, Any],
    policies: Dict[str, Any],
) -> Optional[str]:
    due_s = str(due_date_raw or "").strip()
    if not due_s:
        return None
    try:
        due_d = datetime.fromisoformat(due_s).date()
    except Exception:
        return "Invoice due_date format must be YYYY-MM-DD"
    role = str(user.get("role") or "").strip().lower()
    if role in ("admin", "owner"):
        return None
    max_back_days = _workflow_policy_int(policies, "invoice_backdate_limit_days")
    max_future_days = _workflow_policy_int(policies, "invoice_future_limit_days")
    delta_days = (due_d - date.today()).days
    if delta_days < -max_back_days:
        return f"Backdate over policy limit ({max_back_days} days)"
    if delta_days > max_future_days:
        return f"Future due date over policy limit ({max_future_days} days)"
    return None


def log_module_fix_run(
    db: sqlite3.Connection,
    *,
    username: str,
    mode: str,
    status: str,
    preview_id: str = "",
    modules: Optional[List[str]] = None,
    max_rows: int = 0,
    candidates: int = 0,
    applied: int = 0,
    score_before: Optional[float] = None,
    score_after: Optional[float] = None,
    issues_before: Optional[int] = None,
    issues_after: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        insert(
            db,
            "module_fix_runs",
            {
                "id": uid("MFX"),
                "created_at": now_iso(),
                "username": str(username or "unknown"),
                "mode": str(mode or ""),
                "status": str(status or ""),
                "preview_id": str(preview_id or ""),
                "modules": json.dumps(modules or [], ensure_ascii=False),
                "max_rows": int(max_rows or 0),
                "candidates": int(candidates or 0),
                "applied": int(applied or 0),
                "score_before": score_before,
                "score_after": score_after,
                "issues_before": issues_before,
                "issues_after": issues_after,
                "details_json": json.dumps(details or {}, ensure_ascii=False),
            },
        )
    except Exception:
        # Never block main API behavior if history logging fails.
        pass


def create_biometric_challenge(user_id: str, action: str) -> Dict[str, str]:
    cleanup_biometric_challenges()
    state = uid("BCH")
    challenge = b64url_encode(secrets.token_bytes(32))
    BIOMETRIC_CHALLENGES[state] = {
        "user_id": user_id,
        "action": action,
        "challenge": challenge,
        "expires": time.time() + BIOMETRIC_CHALLENGE_TTL_SECONDS,
    }
    return {"state": state, "challenge": challenge}


def consume_biometric_challenge(state: str, user_id: str, action: str) -> Optional[str]:
    cleanup_biometric_challenges()
    item = BIOMETRIC_CHALLENGES.pop(state, None)
    if not item:
        return None
    if item.get("user_id") != user_id or item.get("action") != action:
        return None
    return str(item.get("challenge") or "")


def store_biometric_flow_state(user_id: str, action: str, payload: Dict[str, Any]) -> str:
    cleanup_biometric_challenges()
    state = uid("BFS")
    BIOMETRIC_FLOW_STATES[state] = {
        "user_id": user_id,
        "action": action,
        "payload": payload,
        "expires": time.time() + BIOMETRIC_CHALLENGE_TTL_SECONDS,
    }
    return state


def consume_biometric_flow_state(state: str, user_id: str, action: str) -> Optional[Dict[str, Any]]:
    cleanup_biometric_challenges()
    item = BIOMETRIC_FLOW_STATES.pop(state, None)
    if not item:
        return None
    if item.get("user_id") != user_id or item.get("action") != action:
        return None
    payload = item.get("payload")
    return payload if isinstance(payload, dict) else None


def webauthn_to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return b64url_encode(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): webauthn_to_jsonable(v) for k, v in value.items()}
    if hasattr(value, "items"):
        try:
            return {str(k): webauthn_to_jsonable(v) for k, v in dict(value).items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        return [webauthn_to_jsonable(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return webauthn_to_jsonable(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return webauthn_to_jsonable(vars(value))
        except Exception:
            pass
    return str(value)


def password_hash(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, salt, digest = encoded.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        candidate = password_hash(password, salt).split("$", 2)[2]
        return hmac.compare_digest(candidate, digest)
    except Exception:
        return False


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


def build_backup_payload(db: sqlite3.Connection) -> Dict[str, Any]:
    payload = {"status": "production", "exported_at": now_iso(), "tables": {}}
    for table, cols in TABLES.items():
        payload["tables"][table] = rows_to_dicts(db.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall())
    return payload


def list_automatic_backups() -> List[Dict[str, Any]]:
    backups: List[Dict[str, Any]] = []
    for json_path in sorted(BACKUP_DIR.glob("jawdah-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        stamp = json_path.stem.replace("jawdah-", "")
        sqlite_path = BACKUP_DIR / f"jawdah-{stamp}.sqlite3"
        backups.append({
            "timestamp": stamp,
            "json_file": json_path.name,
            "sqlite_file": sqlite_path.name if sqlite_path.exists() else None,
            "json_bytes": json_path.stat().st_size,
            "sqlite_bytes": sqlite_path.stat().st_size if sqlite_path.exists() else 0,
            "created_at": datetime.fromtimestamp(json_path.stat().st_mtime).replace(microsecond=0).isoformat(sep=" "),
        })
    return backups


def storage_status() -> Dict[str, Any]:
    usage = shutil.disk_usage(str(DATA_DIR))
    free_gb = round(usage.free / (1024 ** 3), 2)
    total_gb = round(usage.total / (1024 ** 3), 2)
    used_gb = round((usage.total - usage.free) / (1024 ** 3), 2)
    warning = free_gb <= STORAGE_WARN_GB
    return {
        "path": str(DATA_DIR),
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "warn_threshold_gb": STORAGE_WARN_GB,
        "warning": warning,
        "upload_dir": str(UPLOAD_DIR),
        "object_storage": lq_object_storage.object_storage_status(),
    }


def latest_backup_integrity() -> Dict[str, Any]:
    recent = list_automatic_backups()
    if not recent:
        return {"ok": False, "reason": "no_backup"}
    latest = recent[0]
    json_ok = bool(latest.get("json_bytes") and int(latest["json_bytes"]) > 100)
    sqlite_ok = bool(latest.get("sqlite_file") and int(latest.get("sqlite_bytes") or 0) > 0)
    return {
        "ok": bool(json_ok and sqlite_ok),
        "timestamp": latest.get("timestamp"),
        "json_ok": json_ok,
        "sqlite_ok": sqlite_ok,
        "checked_at": now_iso(),
    }


def resolve_backup_file(kind: str, timestamp: Optional[str] = None) -> Optional[Path]:
    kind = kind.lower()
    if kind not in ("json", "sqlite"):
        return None
    ext = "json" if kind == "json" else "sqlite3"
    if timestamp:
        stamp = timestamp.strip()
        if not re.fullmatch(r"\d{8}-\d{6}", stamp):
            return None
        path = BACKUP_DIR / f"jawdah-{stamp}.{ext}"
        return path if path.exists() else None
    recent = list_automatic_backups()
    if not recent:
        return None
    latest = recent[0]
    fname = latest["json_file"] if kind == "json" else latest.get("sqlite_file")
    if not fname:
        return None
    path = BACKUP_DIR / fname
    return path if path.exists() else None


def prune_old_backups() -> None:
    json_files = sorted(BACKUP_DIR.glob("jawdah-*.json"), key=lambda p: p.stat().st_mtime)
    while len(json_files) > BACKUP_RETENTION:
        old = json_files.pop(0)
        stamp = old.stem.replace("jawdah-", "")
        sqlite_path = BACKUP_DIR / f"jawdah-{stamp}.sqlite3"
        old.unlink(missing_ok=True)
        sqlite_path.unlink(missing_ok=True)


def run_automatic_backup(reason: str = "scheduled") -> Optional[Dict[str, Any]]:
    global LAST_AUTO_BACKUP_AT
    if not BACKUP_LOCK.acquire(blocking=False):
        return None
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        json_path = BACKUP_DIR / f"jawdah-{stamp}.json"
        sqlite_path = BACKUP_DIR / f"jawdah-{stamp}.sqlite3"
        with connect() as db:
            payload = build_backup_payload(db)
            if DB_PATH.exists():
                dest = sqlite3.connect(str(sqlite_path))
                db.backup(dest)
                dest.close()
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        prune_old_backups()
        LAST_AUTO_BACKUP_AT = now_iso()
        result = {
            "timestamp": stamp,
            "json_file": json_path.name,
            "sqlite_file": sqlite_path.name,
            "reason": reason,
            "created_at": LAST_AUTO_BACKUP_AT,
        }
        offsite = push_offsite_backup(
            json_path,
            sqlite_path,
            {"timestamp": stamp, "created_at": LAST_AUTO_BACKUP_AT, "reason": reason, "version": APP_VERSION},
        )
        result["offsite"] = offsite
        print(f"Automatic backup created ({reason}): {json_path.name}")
        return result
    except Exception as exc:
        print(f"Automatic backup failed ({reason}): {exc}")
        return None
    finally:
        BACKUP_LOCK.release()


def backup_due() -> bool:
    if not AUTO_BACKUP_ENABLED:
        return False
    json_files = sorted(BACKUP_DIR.glob("jawdah-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not json_files:
        return True
    last_mtime = json_files[0].stat().st_mtime
    return (time.time() - last_mtime) >= BACKUP_INTERVAL_HOURS * 3600


def auto_backup_worker() -> None:
    if backup_due():
        run_automatic_backup("startup")
    while True:
        time.sleep(BACKUP_INTERVAL_HOURS * 3600)
        run_automatic_backup("scheduled")


def start_auto_backup_scheduler() -> None:
    if not AUTO_BACKUP_ENABLED:
        print("Automatic backup: disabled")
        return
    thread = threading.Thread(target=auto_backup_worker, name="jawdah-auto-backup", daemon=True)
    thread.start()
    print(f"Automatic backup: every {BACKUP_INTERVAL_HOURS}h, retention {BACKUP_RETENTION}, dir={BACKUP_DIR}")


def backup_table_counts(db: sqlite3.Connection) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table in TABLES:
        if table in ("users", "audit_log"):
            continue
        counts[table] = int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return counts


def restore_backup_tables(db: sqlite3.Connection, tables: Dict[str, Any], mode: str = "merge") -> None:
    if mode == "replace":
        for table in ["audit_log", "maintenance", "accounts", "payments", "invoices", "contracts", "clients", "properties"]:
            db.execute(f"DELETE FROM {table}")
    for table, items in tables.items():
        if table not in TABLES or table == "users":
            continue
        for item in items:
            cols = [c for c in TABLES[table] if c in item]
            if not cols or not item.get("id"):
                continue
            values = [item[c] for c in cols]
            placeholders = ",".join(["?"] * len(cols))
            updates = ",".join([f"{c}=excluded.{c}" for c in cols if c != "id"])
            db.execute(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                values,
            )


# Business tables wiped by reset — users / chart of accounts / login devices kept.
OPERATIONAL_KEEP_TABLES = {
    "users",
    "chart_accounts",
    "workflow_policies",
    "biometric_credentials",
    "staff_devices",
}
OPERATIONAL_EXTRA_CLEAR_TABLES = [
    "sessions",
    "alert_dismissals",
    "alert_notifications",
    "ai_usage_log",
    "work_journal",
    "daily_operations",
    "module_fix_runs",
    "trusted_devices",
]


def clear_upload_files() -> Dict[str, int]:
    """Remove uploaded business files; keep folder structure."""
    removed = 0
    ensure_upload_dirs()
    if not UPLOAD_DIR.exists():
        return {"removed_files": 0}
    for path in UPLOAD_DIR.rglob("*"):
        if path.is_file():
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return {"removed_files": removed}


def reset_operational_data(db: sqlite3.Connection, *, clear_uploads: bool = True) -> Dict[str, Any]:
    """Zero business data so the team can re-enter clean records. Keeps users."""
    cleared: Dict[str, int] = {}
    errors: List[str] = []
    # Child-first order so FK constraints do not block the wipe.
    delete_order = [
        "estate_reservation_invoices",
        "estate_contract_settlements",
        "estate_contract_invoices",
        "estate_contracts",
        "estate_status_history",
        "estate_month_closes",
        "estate_maintenance",
        "estate_accessories",
        "estate_rooms",
        "estate_apartments",
        "estate_buildings",
        "estate_properties",
        "hospitality_folios",
        "hospitality_events",
        "hospitality_bookings",
        "hospitality_season_rates",
        "hospitality_rooms",
        "inventory_transactions",
        "inventory_items",
        "bank_reconciliations",
        "bank_transactions",
        "approvals",
        "accounting_budgets",
        "financial_periods",
        "payments",
        "invoices",
        "accounts",
        "purchase_invoices",
        "revenues",
        "attendance_adjustments",
        "attendance_days",
        "attendance_punches",
        "payroll_import_batches",
        "salaries",
        "admin_expenses",
        "maintenance",
        "contracts",
        "clients",
        "properties",
        "branches",
        "audit_log",
        "module_fix_runs",
        "daily_operations",
        "work_journal",
        "ai_usage_log",
        "alert_notifications",
        "alert_dismissals",
        "sessions",
    ]
    seen = set(delete_order)
    for table in list(TABLES.keys()) + OPERATIONAL_EXTRA_CLEAR_TABLES:
        if table not in seen and table not in OPERATIONAL_KEEP_TABLES:
            delete_order.append(table)
    # Disable FK during wipe so residual cycles cannot block a clean slate.
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        for table in delete_order:
            if table in OPERATIONAL_KEEP_TABLES:
                continue
            try:
                before = int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
                db.execute(f"DELETE FROM {table}")
                cleared[table] = before
            except sqlite3.Error as exc:
                cleared[table] = -1
                errors.append(f"{table}: {exc}")
    finally:
        db.execute("PRAGMA foreign_keys = ON")
    seed_chart_accounts(db)
    users_kept = int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0] or 0)
    upload_stats = clear_upload_files() if clear_uploads else {"removed_files": 0, "skipped": True}
    return {
        "ok": len(errors) == 0,
        "cleared": cleared,
        "errors": errors,
        "users_kept": users_kept,
        "uploads": upload_stats,
        "kept": sorted(OPERATIONAL_KEEP_TABLES),
    }


def verify_backup_restore(db: sqlite3.Connection) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    expected_db = str((DATA_DIR / "jawdah.sqlite3").resolve())
    expected_backup_dir = str((DATA_DIR / "backups").resolve())
    checks.append({
        "name": "database_path",
        "ok": str(DB_PATH.resolve()) == expected_db,
        "value": str(DB_PATH),
        "expected": expected_db,
    })
    checks.append({
        "name": "backup_directory",
        "ok": str(BACKUP_DIR.resolve()) == expected_backup_dir,
        "value": str(BACKUP_DIR),
        "expected": expected_backup_dir,
    })
    checks.append({
        "name": "auto_backup_enabled",
        "ok": AUTO_BACKUP_ENABLED,
        "value": AUTO_BACKUP_ENABLED,
    })

    recent = list_automatic_backups()
    checks.append({"name": "backup_files_present", "ok": bool(recent), "value": len(recent)})
    if not recent:
        score = round(sum(1 for c in checks if c["ok"]) / len(checks) * 100, 1)
        return {"ok": False, "score": score, "checks": checks}

    latest = recent[0]
    json_path = BACKUP_DIR / latest["json_file"]
    sqlite_name = latest.get("sqlite_file")
    sqlite_path = BACKUP_DIR / sqlite_name if sqlite_name else None
    checks.append({"name": "latest_json_backup", "ok": json_path.exists() and json_path.stat().st_size > 0, "value": latest["json_file"]})
    checks.append({
        "name": "latest_sqlite_backup",
        "ok": bool(sqlite_path and sqlite_path.exists() and sqlite_path.stat().st_size > 0),
        "value": sqlite_name or "",
    })

    live_counts = backup_table_counts(db)
    backup_payload: Dict[str, Any] = {}
    if json_path.exists():
        try:
            backup_payload = json.loads(json_path.read_text(encoding="utf-8"))
            checks.append({"name": "json_backup_parse", "ok": isinstance(backup_payload.get("tables"), dict), "value": len(backup_payload.get("tables", {}))})
        except Exception as exc:
            checks.append({"name": "json_backup_parse", "ok": False, "value": str(exc)})

    if sqlite_path and sqlite_path.exists():
        try:
            with sqlite3.connect(str(sqlite_path)) as snap:
                for table, live_count in live_counts.items():
                    snap_count = int(snap.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    checks.append({
                        "name": f"snapshot_count_{table}",
                        "ok": snap_count == live_count,
                        "value": f"{snap_count}/{live_count}",
                    })
        except Exception as exc:
            checks.append({"name": "sqlite_backup_open", "ok": False, "value": str(exc)})

    tables = backup_payload.get("tables", {})
    if tables:
        for table, live_count in live_counts.items():
            json_count = len(tables.get(table, []))
            checks.append({
                "name": f"json_count_{table}",
                "ok": json_count == live_count,
                "value": f"{json_count}/{live_count}",
            })

    tmp_path: Optional[Path] = None
    test_db: Optional[sqlite3.Connection] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        with connect() as src, sqlite3.connect(str(tmp_path)) as dest:
            src.backup(dest)
        test_db = sqlite3.connect(str(tmp_path))
        test_db.row_factory = sqlite3.Row
        test_db.execute("PRAGMA foreign_keys = OFF")
        test_db.execute("DELETE FROM properties")
        test_db.commit()
        test_db.execute("PRAGMA foreign_keys = ON")
        restore_backup_tables(test_db, tables, mode="merge")
        test_db.commit()
        restored_properties = int(test_db.execute("SELECT COUNT(*) FROM properties").fetchone()[0])
        expected_properties = live_counts.get("properties", 0)
        checks.append({
            "name": "restore_merge_properties",
            "ok": restored_properties == expected_properties,
            "value": f"{restored_properties}/{expected_properties}",
        })
    except Exception as exc:
        checks.append({"name": "restore_merge_properties", "ok": False, "value": str(exc)})
    finally:
        if test_db is not None:
            test_db.close()
        if tmp_path and tmp_path.exists():
            for _ in range(5):
                try:
                    tmp_path.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.05)

    score = round(sum(1 for c in checks if c["ok"]) / len(checks) * 100, 1) if checks else 0.0
    critical_names = {
        "database_path",
        "backup_directory",
        "auto_backup_enabled",
        "backup_files_present",
        "latest_json_backup",
        "latest_sqlite_backup",
        "json_backup_parse",
        "restore_merge_properties",
        "sqlite_backup_open",
    }
    critical_ok = all(
        c["ok"]
        for c in checks
        if c["name"] in critical_names
    )
    # Count drift on hot tables can lag by seconds; score>=95 with critical OK is production-pass.
    ok = bool(critical_ok and score >= 95)
    return {
        "ok": ok,
        "score": score,
        "critical_ok": critical_ok,
        "checks": checks,
        "latest_backup": latest,
        "note": None if ok else "تحقق من مسارات النسخ أو أعد نسخاً احتياطياً الآن",
    }


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS trusted_devices (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_fingerprint TEXT NOT NULL,
                device_label TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                trusted_until TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                city TEXT,
                address TEXT,
                manager TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                location TEXT,
                building_no TEXT,
                apartment_no TEXT,
                room_no TEXT,
                latitude REAL,
                longitude REAL,
                image TEXT,
                last_update TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                national_id TEXT,
                balance REAL NOT NULL DEFAULT 0,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                client_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                rent_amount REAL NOT NULL,
                status TEXT NOT NULL,
                payment_cycle TEXT NOT NULL DEFAULT 'monthly',
                notes TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id),
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                invoice_no TEXT UNIQUE NOT NULL,
                contract_id TEXT NOT NULL,
                client_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                paid_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                FOREIGN KEY(contract_id) REFERENCES contracts(id),
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(property_id) REFERENCES properties(id)
            );
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                invoice_id TEXT NOT NULL,
                client_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                contract_id TEXT NOT NULL,
                payment_date TEXT NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY(invoice_id) REFERENCES invoices(id),
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(property_id) REFERENCES properties(id),
                FOREIGN KEY(contract_id) REFERENCES contracts(id)
            );
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                entry_date TEXT NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                client_id TEXT,
                property_id TEXT,
                invoice_id TEXT,
                amount REAL NOT NULL,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(property_id) REFERENCES properties(id),
                FOREIGN KEY(invoice_id) REFERENCES invoices(id)
            );
            CREATE TABLE IF NOT EXISTS purchase_invoices (
                id TEXT PRIMARY KEY,
                purchase_no TEXT UNIQUE NOT NULL,
                supplier TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                due_date TEXT,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                property_id TEXT,
                account_id TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            );
            CREATE TABLE IF NOT EXISTS revenues (
                id TEXT PRIMARY KEY,
                revenue_no TEXT UNIQUE NOT NULL,
                revenue_date TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL DEFAULT 0,
                client_id TEXT,
                property_id TEXT,
                account_id TEXT,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(property_id) REFERENCES properties(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            );
            CREATE TABLE IF NOT EXISTS salaries (
                id TEXT PRIMARY KEY,
                employee_name TEXT NOT NULL,
                salary_month TEXT NOT NULL,
                basic_salary REAL NOT NULL DEFAULT 0,
                allowances REAL NOT NULL DEFAULT 0,
                deductions REAL NOT NULL DEFAULT 0,
                net_salary REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                payment_date TEXT,
                account_id TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            );
            CREATE TABLE IF NOT EXISTS payroll_import_batches (
                id TEXT PRIMARY KEY,
                import_type TEXT NOT NULL,
                file_name TEXT,
                project_name TEXT,
                salary_month TEXT,
                status TEXT NOT NULL DEFAULT 'committed',
                row_count INTEGER NOT NULL DEFAULT 0,
                summary_json TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance_punches (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                record_no TEXT,
                machine_no INTEGER,
                employee_no TEXT NOT NULL,
                employee_name TEXT,
                mode INTEGER,
                io_mode INTEGER,
                punch_datetime TEXT NOT NULL,
                punch_date TEXT NOT NULL,
                punch_time TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'aglog',
                FOREIGN KEY(batch_id) REFERENCES payroll_import_batches(id)
            );
            CREATE TABLE IF NOT EXISTS attendance_days (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                employee_no TEXT NOT NULL,
                employee_name TEXT,
                work_date TEXT NOT NULL,
                day_name TEXT,
                shift_type TEXT,
                attendance_status TEXT,
                action_type TEXT,
                scheduled_time TEXT,
                actual_time TEXT,
                remarks TEXT,
                is_extra_punch INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(batch_id) REFERENCES payroll_import_batches(id)
            );
            CREATE TABLE IF NOT EXISTS attendance_adjustments (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                employee_no TEXT NOT NULL,
                employee_name TEXT,
                work_date TEXT NOT NULL,
                adjustment_type TEXT,
                value_before TEXT,
                value_after TEXT,
                adjusted_at TEXT,
                created_at TEXT,
                FOREIGN KEY(batch_id) REFERENCES payroll_import_batches(id)
            );
            CREATE TABLE IF NOT EXISTS admin_expenses (
                id TEXT PRIMARY KEY,
                expense_date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL DEFAULT 0,
                supplier TEXT,
                property_id TEXT,
                account_id TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            );
            CREATE TABLE IF NOT EXISTS inventory_items (
                id TEXT PRIMARY KEY,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                unit TEXT NOT NULL DEFAULT 'pcs',
                quantity REAL NOT NULL DEFAULT 0,
                min_quantity REAL NOT NULL DEFAULT 0,
                unit_cost REAL NOT NULL DEFAULT 0,
                location TEXT,
                property_id TEXT,
                notes TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id)
            );
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                tx_date TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                unit_cost REAL NOT NULL DEFAULT 0,
                reference TEXT,
                notes TEXT,
                FOREIGN KEY(item_id) REFERENCES inventory_items(id)
            );
            CREATE TABLE IF NOT EXISTS hospitality_rooms (
                id TEXT PRIMARY KEY,
                property_id TEXT,
                room_code TEXT NOT NULL,
                room_type TEXT,
                capacity INTEGER NOT NULL DEFAULT 2,
                rate_per_night REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'available',
                notes TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id)
            );
            CREATE TABLE IF NOT EXISTS hospitality_bookings (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                client_id TEXT,
                guest_name TEXT NOT NULL,
                guest_phone TEXT,
                checkin_date TEXT NOT NULL,
                checkout_date TEXT NOT NULL,
                nights INTEGER NOT NULL DEFAULT 1,
                rate_per_night REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'reserved',
                booking_source TEXT,
                property_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(room_id) REFERENCES hospitality_rooms(id),
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(property_id) REFERENCES properties(id)
            );
            CREATE TABLE IF NOT EXISTS hospitality_events (
                id TEXT PRIMARY KEY,
                service_kind TEXT NOT NULL,
                package_code TEXT,
                package_name TEXT,
                client_id TEXT,
                client_name TEXT NOT NULL,
                phone TEXT,
                event_date TEXT NOT NULL,
                guests INTEGER NOT NULL DEFAULT 0,
                location_zone TEXT,
                venue_location TEXT,
                waiters INTEGER NOT NULL DEFAULT 0,
                supervisors INTEGER NOT NULL DEFAULT 0,
                dallahs TEXT,
                total_amount REAL NOT NULL DEFAULT 0,
                deposit_required REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'reserved',
                outside_nizwa INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );
            CREATE TABLE IF NOT EXISTS hospitality_season_rates (
                id TEXT PRIMARY KEY,
                property_id TEXT,
                room_type TEXT,
                season_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                nightly_rate REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id)
            );
            CREATE TABLE IF NOT EXISTS hospitality_folios (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                folio_no TEXT UNIQUE NOT NULL,
                issue_date TEXT NOT NULL,
                total_amount REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open',
                notes TEXT,
                FOREIGN KEY(booking_id) REFERENCES hospitality_bookings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS bank_transactions (
                id TEXT PRIMARY KEY,
                bank_date TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                reference TEXT,
                type TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL DEFAULT 0,
                matched_account_id TEXT,
                status TEXT NOT NULL DEFAULT 'Unmatched',
                FOREIGN KEY(matched_account_id) REFERENCES accounts(id)
            );
            CREATE TABLE IF NOT EXISTS chart_accounts (
                id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                parent_code TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS financial_periods (
                id TEXT PRIMARY KEY,
                period_name TEXT UNIQUE NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                closed_by TEXT,
                closed_at TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS accounting_budgets (
                id TEXT PRIMARY KEY,
                month_key TEXT UNIQUE NOT NULL,
                revenue_target REAL NOT NULL DEFAULT 0,
                expense_budget REAL NOT NULL DEFAULT 0,
                collection_target REAL NOT NULL DEFAULT 0,
                cash_reserve_target REAL NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                entity TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                requested_by TEXT,
                approved_by TEXT,
                requested_at TEXT NOT NULL,
                approved_at TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS bank_reconciliations (
                id TEXT PRIMARY KEY,
                bank_name TEXT NOT NULL,
                period_name TEXT NOT NULL,
                book_balance REAL NOT NULL DEFAULT 0,
                bank_balance REAL NOT NULL DEFAULT 0,
                difference REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Open',
                reconciled_by TEXT,
                reconciled_at TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS maintenance (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                title TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                request_date TEXT NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                notes TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id)
            );
            CREATE TABLE IF NOT EXISTS estate_properties (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                location TEXT,
                building_count INTEGER NOT NULL DEFAULT 0,
                apartment_count INTEGER NOT NULL DEFAULT 0,
                room_count INTEGER NOT NULL DEFAULT 0,
                base_rent_price REAL NOT NULL DEFAULT 0,
                service_charge REAL NOT NULL DEFAULT 0,
                attachments TEXT,
                manager_name TEXT,
                tenant_client_id TEXT,
                tenant_phone TEXT,
                notes TEXT,
                image TEXT,
                last_update TEXT
            );
            CREATE TABLE IF NOT EXISTS estate_buildings (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                location TEXT,
                unit_count INTEGER NOT NULL DEFAULT 0,
                apartment_count INTEGER NOT NULL DEFAULT 0,
                room_count INTEGER NOT NULL DEFAULT 0,
                base_rent_price REAL NOT NULL DEFAULT 0,
                service_charge REAL NOT NULL DEFAULT 0,
                attachments TEXT,
                manager_name TEXT,
                tenant_client_id TEXT,
                tenant_phone TEXT,
                description TEXT,
                notes TEXT,
                image TEXT,
                last_update TEXT,
                FOREIGN KEY(property_id) REFERENCES estate_properties(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS estate_apartments (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                building_id TEXT NOT NULL,
                name TEXT NOT NULL,
                unit_kind TEXT NOT NULL DEFAULT 'شقة كاملة',
                status TEXT NOT NULL DEFAULT 'vacant',
                room_count INTEGER NOT NULL DEFAULT 0,
                floor_no INTEGER,
                area_sqm REAL NOT NULL DEFAULT 0,
                rent_price REAL NOT NULL DEFAULT 0,
                booking_deposit REAL NOT NULL DEFAULT 0,
                prepaid_amount REAL NOT NULL DEFAULT 0,
                reservation_start_date TEXT,
                reservation_end_date TEXT,
                booked_client_name TEXT,
                booked_client_phone TEXT,
                booked_client_id TEXT,
                booked_by_employee TEXT,
                maintenance_notes TEXT,
                maintenance_cost REAL NOT NULL DEFAULT 0,
                attachments TEXT,
                manager_name TEXT,
                tenant_client_id TEXT,
                tenant_phone TEXT,
                notes TEXT,
                image TEXT,
                last_update TEXT,
                FOREIGN KEY(property_id) REFERENCES estate_properties(id) ON DELETE CASCADE,
                FOREIGN KEY(building_id) REFERENCES estate_buildings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS estate_rooms (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                building_id TEXT NOT NULL,
                apartment_id TEXT,
                name TEXT NOT NULL,
                unit_kind TEXT NOT NULL DEFAULT 'غرفة مستقلة',
                room_type TEXT,
                status TEXT NOT NULL DEFAULT 'vacant',
                floor_no INTEGER,
                area_sqm REAL NOT NULL DEFAULT 0,
                rent_price REAL NOT NULL DEFAULT 0,
                booking_deposit REAL NOT NULL DEFAULT 0,
                prepaid_amount REAL NOT NULL DEFAULT 0,
                reservation_start_date TEXT,
                reservation_end_date TEXT,
                booked_client_name TEXT,
                booked_client_phone TEXT,
                booked_client_id TEXT,
                booked_by_employee TEXT,
                maintenance_notes TEXT,
                maintenance_cost REAL NOT NULL DEFAULT 0,
                attachments TEXT,
                manager_name TEXT,
                tenant_client_id TEXT,
                tenant_phone TEXT,
                notes TEXT,
                image TEXT,
                last_update TEXT,
                FOREIGN KEY(property_id) REFERENCES estate_properties(id) ON DELETE CASCADE,
                FOREIGN KEY(building_id) REFERENCES estate_buildings(id) ON DELETE CASCADE,
                FOREIGN KEY(apartment_id) REFERENCES estate_apartments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS estate_accessories (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                building_id TEXT,
                apartment_id TEXT,
                room_id TEXT,
                name TEXT NOT NULL,
                category TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                qty INTEGER NOT NULL DEFAULT 1,
                unit_cost REAL NOT NULL DEFAULT 0,
                supplier TEXT,
                invoice_no TEXT,
                responsible_name TEXT,
                notes TEXT,
                last_update TEXT,
                FOREIGN KEY(property_id) REFERENCES estate_properties(id) ON DELETE CASCADE,
                FOREIGN KEY(building_id) REFERENCES estate_buildings(id) ON DELETE SET NULL,
                FOREIGN KEY(apartment_id) REFERENCES estate_apartments(id) ON DELETE SET NULL,
                FOREIGN KEY(room_id) REFERENCES estate_rooms(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS estate_maintenance (
                id TEXT PRIMARY KEY,
                property_id TEXT,
                building_id TEXT,
                apartment_id TEXT,
                room_id TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                priority TEXT NOT NULL DEFAULT 'Medium',
                responsible_name TEXT,
                assigned_team TEXT,
                parts_details TEXT,
                parts_cost REAL NOT NULL DEFAULT 0,
                labor_cost REAL NOT NULL DEFAULT 0,
                invoice_no TEXT,
                invoice_date TEXT,
                vendor_name TEXT,
                total_cost REAL NOT NULL DEFAULT 0,
                approved_by TEXT,
                maintenance_date TEXT NOT NULL,
                next_followup_date TEXT,
                closed_at TEXT,
                notes TEXT,
                FOREIGN KEY(property_id) REFERENCES estate_properties(id) ON DELETE SET NULL,
                FOREIGN KEY(building_id) REFERENCES estate_buildings(id) ON DELETE SET NULL,
                FOREIGN KEY(apartment_id) REFERENCES estate_apartments(id) ON DELETE SET NULL,
                FOREIGN KEY(room_id) REFERENCES estate_rooms(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS estate_contracts (
                id TEXT PRIMARY KEY,
                contract_no TEXT UNIQUE NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                property_id TEXT,
                building_id TEXT,
                apartment_id TEXT,
                room_id TEXT,
                client_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                rent_amount REAL NOT NULL DEFAULT 0,
                payment_cycle TEXT NOT NULL DEFAULT 'monthly',
                status TEXT NOT NULL DEFAULT 'Draft',
                created_by TEXT,
                created_at TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                activated_by TEXT,
                activated_at TEXT,
                closed_at TEXT,
                close_note TEXT,
                attachments TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS estate_contract_invoices (
                id TEXT PRIMARY KEY,
                invoice_no TEXT UNIQUE NOT NULL,
                contract_id TEXT NOT NULL,
                due_date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                issued_at TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY(contract_id) REFERENCES estate_contracts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS estate_contract_settlements (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                close_date TEXT NOT NULL,
                total_scheduled REAL NOT NULL DEFAULT 0,
                total_paid REAL NOT NULL DEFAULT 0,
                outstanding_due REAL NOT NULL DEFAULT 0,
                future_cancelled INTEGER NOT NULL DEFAULT 0,
                closed_by TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(contract_id) REFERENCES estate_contracts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS estate_month_closes (
                id TEXT PRIMARY KEY,
                month_key TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'Closed',
                total_invoiced REAL NOT NULL DEFAULT 0,
                total_collected REAL NOT NULL DEFAULT 0,
                outstanding_due REAL NOT NULL DEFAULT 0,
                closed_by TEXT,
                closed_at TEXT NOT NULL,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS estate_status_history (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                property_id TEXT,
                building_id TEXT,
                apartment_id TEXT,
                room_id TEXT,
                old_status TEXT,
                new_status TEXT NOT NULL,
                changed_by TEXT,
                changed_at TEXT NOT NULL,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS estate_reservation_invoices (
                id TEXT PRIMARY KEY,
                invoice_no TEXT UNIQUE NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                property_id TEXT,
                building_id TEXT,
                apartment_id TEXT,
                room_id TEXT,
                client_id TEXT,
                client_name TEXT,
                issued_by TEXT,
                issue_date TEXT NOT NULL,
                due_date TEXT,
                rent_price REAL NOT NULL DEFAULT 0,
                deposit_amount REAL NOT NULL DEFAULT 0,
                prepaid_amount REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Open',
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                username TEXT,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id TEXT,
                details TEXT
            );
            CREATE TABLE IF NOT EXISTS staff_devices (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'web',
                push_token TEXT,
                device_label TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS biometric_credentials (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                credential_id TEXT UNIQUE NOT NULL,
                credential_data TEXT,
                public_key TEXT,
                algorithm TEXT,
                label TEXT,
                transports TEXT,
                sign_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_verified TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS alert_dismissals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                alert_key TEXT NOT NULL,
                dismissed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alert_notifications (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                recipient TEXT,
                subject TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                alert_count INTEGER NOT NULL DEFAULT 0,
                sent_by TEXT
            );
            CREATE TABLE IF NOT EXISTS ai_usage_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                username TEXT,
                question TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'rules',
                tokens_est INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS work_journal (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                work_date TEXT NOT NULL,
                text TEXT NOT NULL,
                attachments TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS daily_operations (
                id TEXT PRIMARY KEY,
                entry_date TEXT NOT NULL,
                employee_user_id TEXT,
                employee_name TEXT NOT NULL,
                icon TEXT,
                done_text TEXT NOT NULL,
                deferred_text TEXT,
                deferred_to TEXT,
                created_by_user_id TEXT NOT NULL,
                created_by_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(employee_user_id) REFERENCES users(id),
                FOREIGN KEY(created_by_user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS module_fix_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                username TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                preview_id TEXT,
                modules TEXT,
                max_rows INTEGER,
                candidates INTEGER NOT NULL DEFAULT 0,
                applied INTEGER NOT NULL DEFAULT 0,
                score_before REAL,
                score_after REAL,
                issues_before INTEGER,
                issues_after INTEGER,
                details_json TEXT
            );
            CREATE TABLE IF NOT EXISTS workflow_policies (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            );
            """
        )
        for col, definition in [
            ("contract_no", "TEXT"),
            ("contract_type", "TEXT DEFAULT 'Residential'"),
            ("tenant_nationality", "TEXT"),
            ("tenant_id_no", "TEXT"),
            ("unit_details", "TEXT"),
            ("deposit_amount", "REAL NOT NULL DEFAULT 0"),
            ("late_fee", "REAL NOT NULL DEFAULT 0"),
            ("grace_days", "INTEGER NOT NULL DEFAULT 5"),
            ("renewal_notice_days", "INTEGER NOT NULL DEFAULT 30"),
            ("legal_terms", "TEXT"),
            ("company_signatory", "TEXT"),
            ("approved_at", "TEXT"),
            ("approved_by", "TEXT"),
            ("activated_at", "TEXT"),
            ("activated_by", "TEXT"),
            ("ended_at", "TEXT"),
            ("attachments", "TEXT"),
        ]:
            ensure_column(db, "contracts", col, definition)
        for col, definition in [
            ("deposit_received", "INTEGER NOT NULL DEFAULT 0"),
            ("deposit_received_at", "TEXT"),
            ("deposit_received_amount", "REAL NOT NULL DEFAULT 0"),
        ]:
            ensure_column(db, "contracts", col, definition)
        for col, definition in [
            ("invoice_type", "TEXT DEFAULT 'rent'"),
            ("subtotal", "REAL"),
            ("vat_rate", "REAL"),
            ("vat_amount", "REAL"),
            ("grand_total", "REAL"),
            ("is_void", "INTEGER NOT NULL DEFAULT 0"),
            ("void_reason", "TEXT"),
            ("voided_at", "TEXT"),
            ("sequence_year", "INTEGER"),
            ("sequence_no", "INTEGER"),
            ("reissued_from", "TEXT"),
        ]:
            ensure_column(db, "invoices", col, definition)
        for col, definition in [
            ("branch_id", "TEXT"),
            ("building_no", "TEXT"),
            ("apartment_no", "TEXT"),
            ("room_no", "TEXT"),
            ("unit_kind", "TEXT"),
            ("unit_rooms_count", "INTEGER"),
            ("latitude", "REAL"),
            ("longitude", "REAL"),
        ]:
            ensure_column(db, "properties", col, definition)
        for col, definition in [
            ("email", "TEXT"),
            ("must_change_password", "INTEGER NOT NULL DEFAULT 0"),
            ("totp_secret", "TEXT"),
            ("totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("password_changed_at", "TEXT"),
        ]:
            ensure_column(db, "users", col, definition)
        ensure_security_runtime_tables(db)
        lq_quick_estate.ensure_tables(db)
        lq_auto_trading.ensure_tables(db)
        try:
            import lq_nizwa_estate_copy

            # نسخ صامت وآمن (idempotent) — لا يمس جداول نزوى الأصلية
            lq_nizwa_estate_copy.copy_qe_to_estate(db, uid_fn=uid, now_fn=now_iso, actor="system-auto-copy")
        except Exception as exc:
            print(f"[nizwa-estate-copy] skipped: {exc}")
        ensure_column(db, "clients", "id_card_image", "TEXT")
        ensure_column(db, "payments", "payment_proof_image", "TEXT")
        ensure_column(db, "payments", "received_by", "TEXT")
        for col, definition in [
            ("matched_invoice_id", "TEXT"),
            ("matched_payment_id", "TEXT"),
        ]:
            ensure_column(db, "bank_transactions", col, definition)
        for col, definition in [
            ("matched_count", "INTEGER NOT NULL DEFAULT 0"),
            ("unmatched_count", "INTEGER NOT NULL DEFAULT 0"),
            ("period_start", "TEXT"),
            ("period_end", "TEXT"),
        ]:
            ensure_column(db, "bank_reconciliations", col, definition)
        ensure_column(db, "inventory_items", "property_id", "TEXT")
        ensure_column(db, "hospitality_rooms", "property_id", "TEXT")
        ensure_column(db, "hospitality_rooms", "room_type", "TEXT")
        ensure_column(db, "hospitality_rooms", "capacity", "INTEGER NOT NULL DEFAULT 2")
        ensure_column(db, "hospitality_rooms", "rate_per_night", "REAL NOT NULL DEFAULT 0")
        ensure_column(db, "hospitality_rooms", "status", "TEXT NOT NULL DEFAULT 'available'")
        ensure_column(db, "hospitality_rooms", "notes", "TEXT")
        ensure_column(db, "hospitality_bookings", "property_id", "TEXT")
        ensure_column(db, "hospitality_bookings", "booking_source", "TEXT")
        ensure_column(db, "hospitality_bookings", "created_at", "TEXT")
        ensure_column(db, "hospitality_bookings", "guest_phone", "TEXT")
        ensure_column(db, "hospitality_bookings", "notes", "TEXT")
        ensure_column(db, "hospitality_events", "venue_location", "TEXT")
        ensure_column(db, "hospitality_events", "location_zone", "TEXT")
        ensure_column(db, "hospitality_events", "service_kind", "TEXT")
        ensure_column(db, "hospitality_season_rates", "property_id", "TEXT")
        ensure_column(db, "hospitality_season_rates", "room_type", "TEXT")
        ensure_column(db, "hospitality_season_rates", "season_name", "TEXT")
        ensure_column(db, "hospitality_season_rates", "start_date", "TEXT")
        ensure_column(db, "hospitality_season_rates", "end_date", "TEXT")
        ensure_column(db, "hospitality_season_rates", "nightly_rate", "REAL NOT NULL DEFAULT 0")
        ensure_column(db, "hospitality_season_rates", "active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(db, "hospitality_season_rates", "notes", "TEXT")
        ensure_column(db, "hospitality_folios", "booking_id", "TEXT")
        ensure_column(db, "hospitality_folios", "folio_no", "TEXT")
        ensure_column(db, "hospitality_folios", "issue_date", "TEXT")
        ensure_column(db, "hospitality_folios", "total_amount", "REAL NOT NULL DEFAULT 0")
        ensure_column(db, "hospitality_folios", "paid_amount", "REAL NOT NULL DEFAULT 0")
        ensure_column(db, "hospitality_folios", "balance_amount", "REAL NOT NULL DEFAULT 0")
        ensure_column(db, "hospitality_folios", "status", "TEXT NOT NULL DEFAULT 'open'")
        ensure_column(db, "hospitality_folios", "notes", "TEXT")
        for col, definition in [
            ("status", "TEXT NOT NULL DEFAULT 'active'"),
            ("base_rent_price", "REAL NOT NULL DEFAULT 0"),
            ("service_charge", "REAL NOT NULL DEFAULT 0"),
        ]:
            ensure_column(db, "estate_properties", col, definition)
        for col, definition in [
            ("status", "TEXT NOT NULL DEFAULT 'active'"),
            ("base_rent_price", "REAL NOT NULL DEFAULT 0"),
            ("service_charge", "REAL NOT NULL DEFAULT 0"),
            ("unit_count", "INTEGER NOT NULL DEFAULT 0"),
            ("description", "TEXT"),
        ]:
            ensure_column(db, "estate_buildings", col, definition)
        for col, definition in [
            ("status", "TEXT NOT NULL DEFAULT 'vacant'"),
            ("unit_kind", "TEXT NOT NULL DEFAULT 'شقة كاملة'"),
            ("floor_no", "INTEGER"),
            ("area_sqm", "REAL NOT NULL DEFAULT 0"),
            ("rent_price", "REAL NOT NULL DEFAULT 0"),
            ("booking_deposit", "REAL NOT NULL DEFAULT 0"),
            ("prepaid_amount", "REAL NOT NULL DEFAULT 0"),
            ("reservation_start_date", "TEXT"),
            ("reservation_end_date", "TEXT"),
            ("booked_client_name", "TEXT"),
            ("booked_client_phone", "TEXT"),
            ("booked_client_id", "TEXT"),
            ("booked_by_employee", "TEXT"),
            ("maintenance_notes", "TEXT"),
            ("maintenance_cost", "REAL NOT NULL DEFAULT 0"),
        ]:
            ensure_column(db, "estate_apartments", col, definition)
        for col, definition in [
            ("unit_kind", "TEXT NOT NULL DEFAULT 'غرفة مستقلة'"),
            ("floor_no", "INTEGER"),
            ("area_sqm", "REAL NOT NULL DEFAULT 0"),
            ("rent_price", "REAL NOT NULL DEFAULT 0"),
            ("booking_deposit", "REAL NOT NULL DEFAULT 0"),
            ("prepaid_amount", "REAL NOT NULL DEFAULT 0"),
            ("reservation_start_date", "TEXT"),
            ("reservation_end_date", "TEXT"),
            ("booked_client_name", "TEXT"),
            ("booked_client_phone", "TEXT"),
            ("booked_client_id", "TEXT"),
            ("booked_by_employee", "TEXT"),
            ("maintenance_notes", "TEXT"),
            ("maintenance_cost", "REAL NOT NULL DEFAULT 0"),
        ]:
            ensure_column(db, "estate_rooms", col, definition)
        for col, definition in [
            ("assigned_team", "TEXT"),
            ("labor_cost", "REAL NOT NULL DEFAULT 0"),
            ("invoice_date", "TEXT"),
            ("vendor_name", "TEXT"),
            ("approved_by", "TEXT"),
            ("closed_at", "TEXT"),
        ]:
            ensure_column(db, "estate_maintenance", col, definition)
        for col, definition in [
            ("payment_cycle", "TEXT NOT NULL DEFAULT 'monthly'"),
            ("status", "TEXT NOT NULL DEFAULT 'Draft'"),
            ("created_by", "TEXT"),
            ("created_at", "TEXT"),
            ("approved_by", "TEXT"),
            ("approved_at", "TEXT"),
            ("activated_by", "TEXT"),
            ("activated_at", "TEXT"),
            ("closed_at", "TEXT"),
            ("close_note", "TEXT"),
            ("attachments", "TEXT"),
            ("notes", "TEXT"),
        ]:
            ensure_column(db, "estate_contracts", col, definition)
        for col, definition in [
            ("credential_data", "TEXT"),
            ("public_key", "TEXT"),
            ("algorithm", "TEXT"),
            ("label", "TEXT"),
            ("transports", "TEXT"),
            ("sign_count", "INTEGER NOT NULL DEFAULT 0"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("last_verified", "TEXT"),
        ]:
            ensure_column(db, "biometric_credentials", col, definition)
        for col, definition in [
            ("employee_no", "TEXT"),
            ("project_name", "TEXT"),
            ("import_batch_id", "TEXT"),
        ]:
            ensure_column(db, "salaries", col, definition)
        migrate_property_statuses(db)
        seed_branches_from_buildings(db)
        ensure_workflow_policies_defaults(db)
        seed_if_empty(db)
        ensure_team_users(db)
        scrub_legacy_launch_quality_data(db)
        purged = purge_demo_business_data(db)
        if purged:
            sys.stderr.write(f"[NAJJAR] Startup purge: {purged}\n")
        seed_chart_accounts(db)
        db.commit()


def scrub_legacy_launch_quality_data(db: sqlite3.Connection) -> None:
    """Drop Launch Quality branding from persisted settings when NAJJAR is live."""
    try:
        from company_branding import DEFAULT_COMPANY_SETTINGS, load_company_settings, save_company_settings

        settings_path = DATA_DIR / "company_settings.json"
        if settings_path.exists():
            current = load_company_settings(settings_path)
            blob = json.dumps(current, ensure_ascii=False)
            if any(
                needle in blob
                for needle in (
                    "Launch Quality",
                    "جودة الانطلاقة",
                    "QUALITY OF LAUNCH",
                    "launchquality",
                )
            ):
                save_company_settings(settings_path, DEFAULT_COMPANY_SETTINGS)
    except Exception:
        pass
    try:
        db.execute(
            """
            UPDATE audit_log
            SET detail=replace(replace(detail, 'Launch Quality LLC', ?), 'جودة الانطلاقة', ?)
            WHERE detail LIKE '%Launch Quality%' OR detail LIKE '%جودة الانطلاقة%'
            """,
            (COMPANY_NAME, COMPANY_NAME_AR),
        )
    except sqlite3.Error:
        pass


def ensure_workflow_policies_defaults(db: sqlite3.Connection) -> None:
    for key, default in WORKFLOW_POLICY_DEFAULTS.items():
        existing = db.execute("SELECT key FROM workflow_policies WHERE key=?", (key,)).fetchone()
        if existing:
            continue
        db.execute(
            "INSERT INTO workflow_policies(key, value_json, updated_at, updated_by) VALUES(?,?,?,?)",
            (key, json.dumps(default, ensure_ascii=False), now_iso(), "system"),
        )


def insert(db: sqlite3.Connection, table: str, row: Dict[str, Any]) -> None:
    keys = list(row.keys())
    placeholders = ",".join(["?"] * len(keys))
    sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})"
    db.execute(sql, [row[k] for k in keys])


def seed_if_empty(db: sqlite3.Connection) -> None:
    """Bootstrap only real accounts + chart of accounts. Never insert demo business data."""
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for username, name, role, legacy_pwd in NAJJAR_TEAM_BOOTSTRAP:
            # Easy 1–5 passwords are intentional for this team roster.
            insert(
                db,
                "users",
                {
                    "id": uid("USR"),
                    "username": username,
                    "name": name,
                    "role": role,
                    "active": 1,
                    "password_hash": password_hash(legacy_pwd),
                    "email": resolve_user_email(username),
                    "must_change_password": 0,
                    "password_changed_at": now_iso(),
                    "created_at": now_iso(),
                    "last_login": None,
                },
            )
    # Official / production: never seed fake properties, clients, invoices, salaries, etc.
    seed_chart_accounts(db)
    purged = purge_demo_business_data(db)
    if purged:
        sys.stderr.write(f"[LQ Real-Only] Purged demo rows: {purged}\n")



def seed_chart_accounts(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM chart_accounts").fetchone()[0] > 0:
        return
    accounts = [
        ("1000", "Cash and Bank", "Asset"),
        ("1100", "Accounts Receivable", "Asset"),
        ("1200", "Inventory", "Asset"),
        ("2000", "Accounts Payable", "Liability"),
        ("3000", "Owner Equity", "Equity"),
        ("4000", "Rental Revenue", "Revenue"),
        ("4100", "Service Revenue", "Revenue"),
        ("5000", "Property Operating Expenses", "Expense"),
        ("5100", "Maintenance Expenses", "Expense"),
        ("5200", "Payroll Expenses", "Expense"),
        ("5300", "General and Administrative Expenses", "Expense"),
    ]
    for code, name, typ in accounts:
        insert(db, "chart_accounts", {"id": uid("COA"), "code": code, "name": name, "type": typ, "parent_code": None, "active": 1, "notes": ""})



def has_permission(user: Dict[str, Any], permission: str) -> bool:
    role = str(user.get("role") or "viewer").lower()
    uname = str(user.get("username") or "").strip().lower()
    if uname in FULL_ACCESS_USERNAMES:
        return True
    if uname in RESTRICTED_ADMIN_USERNAMES:
        role = "operations"
    # Owner/Admin privileges are limited to explicit full-access usernames.
    effective_role = "operations" if role in ("owner", "admin") else role
    perms = ROLE_PERMISSIONS.get(effective_role, set())
    if "all" in perms:
        return True
    if permission in perms:
        return True
    base = permission.split(":", 1)[0]
    if base in perms and not permission.endswith(":delete"):
        return True
    if permission.endswith(":read") and (base in perms or f"{base}:read" in perms):
        return True
    if permission == "approvals:request" and ("approvals:request" in perms or "approvals" in perms or "all" in perms):
        return True
    return False


def is_primary_owner_user(user: Dict[str, Any]) -> bool:
    uname = str((user or {}).get("username") or "").strip().lower()
    return uname in PRIMARY_OWNER_USERNAMES


def can_manage_daily_operations(user: Optional[Dict[str, Any]]) -> bool:
    uname = str((user or {}).get("username") or "").strip().lower()
    return uname in DAILY_OPS_MANAGER_USERNAMES


def default_daily_ops_icon(username: str, display_name: str = "") -> str:
    uname = str(username or "").strip().lower()
    if "waleed" in uname or uname == "owner":
        return "👑"
    if "yaqoub" in uname:
        return "🛰️"
    if "razan" in uname:
        return "🗂️"
    if "admin" in uname:
        return "🛡️"
    if "account" in uname:
        return "💼"
    if "oper" in uname:
        return "📋"
    if "maint" in uname:
        return "🛠️"
    first = str(display_name or uname or "•").strip()[:1]
    return first if first else "•"


def audit(db: sqlite3.Connection, user: Optional[Dict[str, Any]], action: str, entity: str, entity_id: Optional[str], details: str = "") -> None:
    insert(db, "audit_log", {"id": uid("LOG"), "created_at": now_iso(), "username": (user or {}).get("username"), "action": action, "entity": entity, "entity_id": entity_id, "details": details})


def approval_notes_pack(user_note: str = "", meta: Optional[Dict[str, Any]] = None) -> str:
    payload: Dict[str, Any] = {}
    if user_note:
        payload["note"] = user_note
    if meta:
        payload["meta"] = meta
    return json.dumps(payload, ensure_ascii=False) if payload else user_note or ""


def approval_notes_unpack(notes: str) -> Tuple[str, Dict[str, Any]]:
    raw = str(notes or "").strip()
    if not raw:
        return "", {}
    if raw.startswith("{") and raw.endswith("}"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return str(data.get("note") or ""), dict(data.get("meta") or {})
        except json.JSONDecodeError:
            pass
    return raw, {}


def can_decide_approval(user: Dict[str, Any], request_type: str) -> bool:
    role = user.get("role")
    uname = str(user.get("username") or "").strip().lower()
    if uname in RESTRICTED_ADMIN_USERNAMES:
        return False
    if role in ("admin", "owner") or "all" in ROLE_PERMISSIONS.get(role, set()):
        return True
    allowed = APPROVAL_DECIDE_ROLES.get(request_type, set())
    return role in allowed and has_permission(user, "approvals")


def create_approval_request(
    db: sqlite3.Connection,
    entity: str,
    entity_id: str,
    request_type: str,
    requested_by: str,
    notes: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    existing = db.execute(
        """
        SELECT id FROM approvals
        WHERE entity=? AND entity_id=? AND request_type=? AND lower(status)='pending'
        """,
        (entity, entity_id, request_type),
    ).fetchone()
    if existing:
        return str(existing["id"])
    approval_id = uid("APR")
    insert(
        db,
        "approvals",
        {
            "id": approval_id,
            "entity": entity,
            "entity_id": entity_id,
            "request_type": request_type,
            "status": "Pending",
            "requested_by": requested_by,
            "approved_by": None,
            "requested_at": now_iso(),
            "approved_at": None,
            "notes": approval_notes_pack(notes, meta),
        },
    )
    return approval_id


def pending_approvals_count(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT COUNT(*) FROM approvals WHERE lower(status)='pending'").fetchone()[0])


def pending_approvals_count(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT COUNT(*) FROM approvals WHERE lower(status)='pending'").fetchone()[0])


def build_staff_sync_payload(db: sqlite3.Connection, user: Dict[str, Any]) -> Dict[str, Any]:
    dash = build_dashboard(db)
    clients = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM clients").fetchall()}
    properties = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM properties").fetchall()}
    maintenance = rows_to_dicts(
        db.execute(
            """
            SELECT id, property_id, title, priority, status, request_date, cost, notes
            FROM maintenance
            WHERE lower(status) NOT IN ('closed','done','completed')
            ORDER BY CASE lower(priority) WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, request_date DESC
            LIMIT 40
            """
        ).fetchall()
    )
    for m in maintenance:
        m["property_name"] = properties.get(m.get("property_id"), "")
    overdue = rows_to_dicts(
        db.execute(
            """
            SELECT id, invoice_no, client_id, property_id, amount, paid_amount, due_date, status
            FROM invoices
            WHERE COALESCE(is_void,0)=0 AND lower(status)!='paid'
            AND due_date < ?
            ORDER BY due_date
            LIMIT 25
            """,
            (today(),),
        ).fetchall()
    )
    for inv in overdue:
        inv["client_name"] = clients.get(inv.get("client_id"), "")
        inv["remaining"] = round(max(0, float(inv.get("amount") or 0) - float(inv.get("paid_amount") or 0)), 3)
    contracts = rows_to_dicts(
        db.execute(
            """
            SELECT id, contract_no, client_id, property_id, end_date, status
            FROM contracts
            WHERE lower(status) IN ('active','renewed')
            ORDER BY end_date
            LIMIT 30
            """
        ).fetchall()
    )
    renewal = contract_renewal_stats(db)
    field_properties = rows_to_dicts(
        db.execute(
            "SELECT id, name, building_no, apartment_no, status, image FROM properties ORDER BY name LIMIT 50"
        ).fetchall()
    )
    for prop in field_properties:
        img = str(prop.get("image") or "")
        if img.startswith("/uploads/"):
            prop["photo_url"] = img
    return {
        "synced_at": now_iso(),
        "app_version": STAFF_APP_VERSION,
        "user": {
            "id": user.get("id"),
            "name": user.get("name"),
            "username": user.get("username"),
            "role": user.get("role"),
        },
        "permissions": sorted(ROLE_PERMISSIONS.get(user.get("role"), set())),
        "kpis": dash.get("kpis", {}),
        "decisions": dash.get("decisions", [])[:6],
        "maintenance_open": maintenance,
        "overdue_invoices": overdue,
        "contracts_watch": contracts,
        "field_properties": field_properties,
        "renewal": renewal,
        "pending_approvals": pending_approvals_count(db),
        "download": {
            "apk_url": STAFF_DOWNLOAD_APK,
            "windows_zip_url": STAFF_DOWNLOAD_ZIP,
            "download_page": f"{PRODUCTION_URL}/download.html",
        },
    }


def build_owner_staff_activity(db: sqlite3.Connection, days: int = 14) -> Dict[str, Any]:
    days = max(1, min(90, int(days or 14)))
    since_date = (date.today() - timedelta(days=days)).isoformat()
    since_ts = since_date + " 00:00:00"
    staff_rows = rows_to_dicts(
        db.execute(
            """
            SELECT id, username, name, role, last_login, active
            FROM users
            WHERE active=1 AND role NOT IN ('owner')
            ORDER BY name
            """
        ).fetchall()
    )
    staff: List[Dict[str, Any]] = []
    active_today = 0
    journal_today = 0
    audit_today = 0
    today_start = today() + " 00:00:00"
    for u in staff_rows:
        uid_val = u["id"]
        jcount = db.execute(
            "SELECT COUNT(*) FROM work_journal WHERE user_id=? AND work_date>=?",
            (uid_val, since_date),
        ).fetchone()[0]
        acount = db.execute(
            "SELECT COUNT(*) FROM audit_log WHERE username=? AND created_at>=?",
            (u["username"], since_ts),
        ).fetchone()[0]
        jtoday = db.execute(
            "SELECT COUNT(*) FROM work_journal WHERE user_id=? AND work_date=?",
            (uid_val, today()),
        ).fetchone()[0]
        atoday = db.execute(
            "SELECT COUNT(*) FROM audit_log WHERE username=? AND created_at>=?",
            (u["username"], today_start),
        ).fetchone()[0]
        last_journal = db.execute(
            "SELECT MAX(created_at) FROM work_journal WHERE user_id=?",
            (uid_val,),
        ).fetchone()[0]
        if jtoday or atoday or (u.get("last_login") or "") >= today_start:
            active_today += 1
        journal_today += int(jtoday or 0)
        audit_today += int(atoday or 0)
        staff.append(
            {
                **u,
                "journal_entries": int(jcount or 0),
                "audit_actions": int(acount or 0),
                "last_journal": last_journal,
            }
        )
    journal_rows = rows_to_dicts(
        db.execute(
            """
            SELECT w.id, w.user_id, w.work_date, w.text, w.attachments, w.created_at,
                   u.username, u.name AS user_name, u.role AS user_role
            FROM work_journal w
            JOIN users u ON u.id = w.user_id
            WHERE w.work_date >= ?
            ORDER BY w.created_at DESC
            LIMIT 300
            """,
            (since_date,),
        ).fetchall()
    )
    journals: List[Dict[str, Any]] = []
    for row in journal_rows:
        item = dict(row)
        try:
            item["attachments"] = json.loads(item.get("attachments") or "[]")
        except json.JSONDecodeError:
            item["attachments"] = []
        journals.append(item)
    audits = rows_to_dicts(
        db.execute(
            """
            SELECT created_at, username, action, entity, entity_id, details
            FROM audit_log
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT 400
            """,
            (since_ts,),
        ).fetchall()
    )
    devices = rows_to_dicts(
        db.execute(
            """
            SELECT d.id, d.user_id, d.platform, d.device_label, d.last_seen, d.created_at,
                   u.username, u.name AS user_name
            FROM staff_devices d
            JOIN users u ON u.id = d.user_id
            ORDER BY d.last_seen DESC
            LIMIT 40
            """
        ).fetchall()
    )
    return {
        "generated_at": now_iso(),
        "days": days,
        "since_date": since_date,
        "summary": {
            "staff_count": len(staff),
            "journal_today": journal_today,
            "audit_today": audit_today,
            "active_today": active_today,
        },
        "staff": staff,
        "journals": journals,
        "audits": audits,
        "devices": devices,
    }


def normalize_timeline_days(value: Any, default: int = 7) -> int:
    try:
        days = int(value)
    except Exception:
        days = default
    return max(0, min(days, 365))


def build_owner_live_hub(db: sqlite3.Connection, timeline_days: int = 7) -> Dict[str, Any]:
    dashboard = build_dashboard(db)
    k = dashboard.get("kpis") or {}
    accounts = rows_to_dicts(
        db.execute(
            "SELECT id, entry_date, type, category, amount, property_id, description FROM accounts ORDER BY entry_date DESC LIMIT 300"
        ).fetchall()
    )
    properties = rows_to_dicts(db.execute("SELECT id, name, type, status FROM properties").fetchall())
    inventory_items = rows_to_dicts(db.execute("SELECT id, name, quantity, unit_cost, property_id FROM inventory_items").fetchall())
    journals = rows_to_dicts(
        db.execute(
            """
            SELECT w.id, w.user_id, w.work_date, w.text, w.created_at, u.name AS user_name, u.username
            FROM work_journal w
            JOIN users u ON u.id = w.user_id
            ORDER BY w.created_at DESC
            LIMIT 20
            """
        ).fetchall()
    )
    audits = rows_to_dicts(
        db.execute(
            """
            SELECT id, created_at, username, action, entity, details
            FROM audit_log
            WHERE username IS NOT NULL AND username != 'system'
            ORDER BY created_at DESC
            LIMIT 24
            """
        ).fetchall()
    )
    timeline_days = normalize_timeline_days(timeline_days, 7)
    timeline_cutoff = (datetime.now() - timedelta(days=timeline_days)).strftime("%Y-%m-%d %H:%M:%S") if timeline_days > 0 else ""
    # Majlis external events (not hotel room bookings)
    events_sql = """
            SELECT
                id,
                created_at,
                client_name,
                package_name,
                event_date,
                venue_location,
                status,
                total_amount,
                paid_amount,
                balance_amount,
                service_kind,
                phone
            FROM hospitality_events
    """
    events_args: List[Any] = []
    if timeline_days > 0:
        events_sql += " WHERE datetime(COALESCE(created_at, event_date)) >= datetime(?)"
        events_args.append(timeline_cutoff)
    events_sql += """
            ORDER BY datetime(COALESCE(created_at, event_date)) DESC
            LIMIT 20
    """
    majlis_events = rows_to_dicts(db.execute(events_sql, tuple(events_args)).fetchall())
    # Keep empty room-timeline list for backward compatibility; UI now shows majlis events.
    timeline_updates: List[Dict[str, Any]] = []
    prop_map = {p["id"]: p for p in properties}
    inv_value_by_property: Dict[str, float] = {}
    for item in inventory_items:
        pid = str(item.get("property_id") or "").strip()
        if not pid:
            continue
        inv_value_by_property[pid] = inv_value_by_property.get(pid, 0.0) + float(item.get("quantity") or 0) * float(item.get("unit_cost") or 0)
    acct_by_property: Dict[str, Dict[str, float]] = {}
    for row in accounts:
        pid = str(row.get("property_id") or "").strip()
        if not pid:
            continue
        if pid not in acct_by_property:
            acct_by_property[pid] = {"income": 0.0, "expense": 0.0}
        kind = str(row.get("type") or "").lower()
        amt = float(row.get("amount") or 0)
        if kind == "income":
            acct_by_property[pid]["income"] += amt
        elif kind == "expense":
            acct_by_property[pid]["expense"] += amt
    property_finance = []
    for pid, vals in acct_by_property.items():
        property_finance.append(
            {
                "property_id": pid,
                "property_name": (prop_map.get(pid) or {}).get("name") or pid,
                "income": round(vals.get("income", 0), 3),
                "expense": round(vals.get("expense", 0), 3),
                "net": round(vals.get("income", 0) - vals.get("expense", 0), 3),
                "inventory_value": round(inv_value_by_property.get(pid, 0), 3),
            }
        )
    property_finance.sort(key=lambda x: x["net"], reverse=True)
    all_majlis = rows_to_dicts(
        db.execute(
            """
            SELECT id, status, total_amount, paid_amount, balance_amount, service_kind, event_date
            FROM hospitality_events
            """
        ).fetchall()
    )
    active_majlis = [
        e
        for e in all_majlis
        if str(e.get("status") or "").lower() in ("reserved", "confirmed")
    ]
    majlis_revenue = sum(float(e.get("total_amount") or 0) for e in all_majlis)
    majlis_paid = sum(float(e.get("paid_amount") or 0) for e in all_majlis)
    majlis_balance = sum(
        float(e.get("balance_amount") or max(0.0, float(e.get("total_amount") or 0) - float(e.get("paid_amount") or 0)))
        for e in all_majlis
    )
    return {
        "kpis": {
            "properties": int(k.get("properties") or 0),
            "occupancy": float(k.get("occupancy") or 0),
            "income": float(k.get("income") or 0),
            "expense": float(k.get("expense") or 0),
            "net": float(k.get("net") or 0),
            "overdue": float(k.get("overdue") or 0),
            "inventory_value": float(k.get("inventory_value") or 0),
        },
        "channels": {
            "realestate": {
                "units": len(properties),
                "active_contracts": int(db.execute("SELECT COUNT(*) FROM contracts WHERE lower(status)='active'").fetchone()[0]),
                "property_stock_items": sum(1 for i in inventory_items if i.get("property_id")),
            },
            "hospitality": {
                "events_total": len(all_majlis),
                "active_events": len(active_majlis),
                "revenue": round(majlis_revenue, 3),
                "collected": round(majlis_paid, 3),
                "balance": round(majlis_balance, 3),
                # Legacy hotel keys kept at zero so old UI never shows fake room occupancy.
                "units": 0,
                "income": round(majlis_revenue, 3),
                "active_bookings": len(active_majlis),
                "occupancy_pct": 0,
                "adr": 0,
                "revpar": 0,
                "note": "مجالس خارجية · مفصولة عن العقارات والغرف",
            },
        },
        "property_finance": property_finance[:12],
        "recent_staff_journal": journals,
        "recent_staff_actions": audits,
        "recent_timeline_updates": timeline_updates,
        "recent_majlis_events": majlis_events,
        "timeline_filter": {"days": timeline_days},
        "ts": now_iso(),
    }


def build_hospitality_summary(db: sqlite3.Connection, from_date: str, to_date: str) -> Dict[str, Any]:
    rooms = rows_to_dicts(db.execute("SELECT id, status, room_type, rate_per_night FROM hospitality_rooms").fetchall())
    bookings = rows_to_dicts(
        db.execute(
            """
            SELECT id, room_id, checkin_date, checkout_date, nights, total_amount, paid_amount, balance_amount, status
            FROM hospitality_bookings
            WHERE date(checkin_date) <= date(?) AND date(checkout_date) >= date(?)
            ORDER BY checkin_date DESC
            """,
            (to_date, from_date),
        ).fetchall()
    )
    total_rooms = len(rooms)
    occupied_rooms = sum(1 for r in rooms if str(r.get("status") or "").lower() == "occupied")
    active_bookings = [b for b in bookings if str(b.get("status") or "").lower() in ("reserved", "checked_in")]
    sold_nights = sum(int(b.get("nights") or 0) for b in active_bookings)
    total_revenue = sum(float(b.get("total_amount") or 0) for b in bookings)
    paid_revenue = sum(float(b.get("paid_amount") or 0) for b in bookings)
    balance_revenue = sum(float(b.get("balance_amount") or 0) for b in bookings)
    booking_count = max(len(bookings), 1)
    adr = (total_revenue / booking_count) if booking_count else 0
    revpar = (total_revenue / total_rooms) if total_rooms else 0
    occupancy = (occupied_rooms / total_rooms * 100.0) if total_rooms else 0.0
    by_type: Dict[str, Dict[str, float]] = {}
    room_map = {r["id"]: r for r in rooms}
    for b in bookings:
        rt = str((room_map.get(b.get("room_id")) or {}).get("room_type") or "Standard")
        if rt not in by_type:
            by_type[rt] = {"bookings": 0, "revenue": 0.0}
        by_type[rt]["bookings"] += 1
        by_type[rt]["revenue"] += float(b.get("total_amount") or 0)
    type_rows = [{"room_type": k, "bookings": int(v["bookings"]), "revenue": round(v["revenue"], 3)} for k, v in by_type.items()]
    type_rows.sort(key=lambda x: x["revenue"], reverse=True)
    return {
        "period": {"from": from_date, "to": to_date},
        "kpis": {
            "rooms": total_rooms,
            "occupied_rooms": occupied_rooms,
            "occupancy_pct": round(occupancy, 2),
            "bookings": len(bookings),
            "active_bookings": len(active_bookings),
            "total_revenue": round(total_revenue, 3),
            "paid_revenue": round(paid_revenue, 3),
            "balance_revenue": round(balance_revenue, 3),
            "adr": round(adr, 3),
            "revpar": round(revpar, 3),
            "sold_nights": sold_nights,
        },
        "room_type_breakdown": type_rows,
        "recent_bookings": bookings[:30],
    }


def execute_contract_approval(db: sqlite3.Connection, user: Dict[str, Any], contract_id: str) -> List[Dict[str, Any]]:
    contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
    if not contract:
        raise ValueError("Contract not found")
    if str(contract["status"] or "").strip().lower() in ("active", "activated"):
        raise ValueError("Contract is already active")
    start = datetime.fromisoformat(contract["start_date"]).date()
    end = datetime.fromisoformat(contract["end_date"]).date()
    rent = float(contract["rent_amount"] or 0)
    if rent <= 0 or end < start:
        raise ValueError("Invalid contract dates or rent")
    prop = db.execute("SELECT status FROM properties WHERE id=?", (contract["property_id"],)).fetchone()
    if not prop:
        raise ValueError("Property not found")
    if property_status_blocks_rental(prop["status"]):
        raise ValueError("Property is under maintenance or suspended")
    conflict = conflicting_contract_for_property(db, str(contract["property_id"]), contract["start_date"], contract["end_date"], contract_id)
    if conflict:
        raise ValueError(f"Contract period conflicts with {conflict.get('contract_no') or conflict.get('id')}")
    db.execute(
        "UPDATE contracts SET status=?, approved_at=?, approved_by=? WHERE id=?",
        ("Approved", now_iso(), user.get("username") or user.get("name"), contract_id),
    )
    audit(db, user, "approve", "contracts", contract_id, "Approved contract; waiting activation")
    return []


def execute_contract_activation(db: sqlite3.Connection, user: Dict[str, Any], contract_id: str) -> List[Dict[str, Any]]:
    contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
    if not contract:
        raise ValueError("Contract not found")
    status = str(contract["status"] or "").strip().lower()
    if status not in ("approved", "active", "activated"):
        raise ValueError("Contract must be approved before activation")
    if status in ("active", "activated"):
        raise ValueError("Contract is already active")
    if active_contract_exists_for_property(db, str(contract["property_id"]), contract_id):
        raise ValueError("Another active contract exists for this property")
    prop = db.execute("SELECT status FROM properties WHERE id=?", (contract["property_id"],)).fetchone()
    if not prop:
        raise ValueError("Property not found")
    if property_status_blocks_rental(prop["status"]):
        raise ValueError("Property is under maintenance or suspended")
    conflict = conflicting_contract_for_property(db, str(contract["property_id"]), contract["start_date"], contract["end_date"], contract_id)
    if conflict:
        raise ValueError(f"Contract period conflicts with {conflict.get('contract_no') or conflict.get('id')}")
    start = datetime.fromisoformat(contract["start_date"]).date()
    end = datetime.fromisoformat(contract["end_date"]).date()
    rent = float(contract["rent_amount"] or 0)
    if rent <= 0 or end < start:
        raise ValueError("Invalid contract dates or rent")
    created: List[Dict[str, Any]] = []
    created_count = 0
    cycle = str(contract["payment_cycle"] or "monthly").strip().lower()
    step_months = 1
    max_invoices = 120
    if cycle in ("quarterly", "quarter"):
        step_months = 3
    elif cycle in ("yearly", "annual"):
        step_months = 12
    elif cycle in ("once", "one-time", "single"):
        max_invoices = 1
    due = start
    while due <= end and created_count < max_invoices:
        exists_invoice = db.execute(
            "SELECT id FROM invoices WHERE contract_id=? AND due_date=?",
            (contract_id, due.isoformat()),
        ).fetchone()
        if not exists_invoice:
            desc = contract_invoice_description(db, contract, due.isoformat())
            inv = build_invoice_row(
                db,
                contract,
                desc,
                rent,
                due_date=due.isoformat(),
                invoice_type="rent",
            )
            insert(db, "invoices", inv)
            created.append(inv)
            created_count += 1
        due = add_months(due, step_months)
    db.execute(
        "UPDATE contracts SET status=?, activated_at=?, activated_by=? WHERE id=?",
        ("Active", now_iso(), user.get("username") or user.get("name"), contract_id),
    )
    sync_property_status_for_contract(db, contract["property_id"], "Active")
    audit(db, user, "activate", "contracts", contract_id, f"Activated contract and generated {len(created)} invoices")
    return created


def execute_invoice_payment(
    db: sqlite3.Connection,
    user: Dict[str, Any],
    invoice_id: str,
    amount: float,
    method: str = "Cash",
    note: str = "Invoice payment",
    payment_date: Optional[str] = None,
    bank_name: str = "Main Bank",
    payment_proof_image: Optional[str] = None,
) -> Dict[str, Any]:
    invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not invoice:
        raise ValueError("Invoice not found")
    if int(invoice["is_void"] or 0):
        raise ValueError("Cannot pay a void invoice")
    if amount <= 0:
        raise ValueError("Payment amount must be positive")
    remaining = float(invoice["amount"]) - float(invoice["paid_amount"])
    if amount > remaining + 0.001:
        raise ValueError("Payment exceeds remaining invoice balance")
    new_paid = float(invoice["paid_amount"]) + amount
    status = "Paid" if new_paid >= float(invoice["amount"]) - 0.001 else "Partial"
    payment = {
        "id": uid("PAY"),
        "invoice_id": invoice["id"],
        "client_id": invoice["client_id"],
        "property_id": invoice["property_id"],
        "contract_id": invoice["contract_id"],
        "payment_date": payment_date or today(),
        "amount": amount,
        "method": method or "Cash",
        "note": note or "Invoice payment",
        "payment_proof_image": payment_proof_image or None,
        "received_by": user.get("username") or user.get("name") or "system",
    }
    account = {
        "id": uid("ACC"),
        "entry_date": payment["payment_date"],
        "type": "income",
        "category": "Collection",
        "description": f"Payment for {invoice['invoice_no']}",
        "client_id": invoice["client_id"],
        "property_id": invoice["property_id"],
        "invoice_id": invoice["id"],
        "amount": amount,
    }
    insert(db, "payments", payment)
    insert(db, "accounts", account)
    db.execute("UPDATE invoices SET paid_amount=?, status=? WHERE id=?", (new_paid, status, invoice["id"]))
    inv_type = detect_invoice_type(
        str(invoice["description"] or ""),
        invoice["invoice_type"] if "invoice_type" in invoice.keys() else None,
    )
    if inv_type == "deposit":
        sync_contract_deposit(db, invoice["contract_id"], amount)
    method_l = str(method or "").strip().lower()
    if method_l in ("bank transfer", "card", "bank", "تحويل بنكي"):
        insert(
            db,
            "bank_transactions",
            {
                "id": uid("BNK"),
                "bank_date": payment["payment_date"],
                "bank_name": bank_name or "Main Bank",
                "reference": invoice["invoice_no"],
                "type": "deposit",
                "description": f"تحصيل {invoice['invoice_no']} — {payment['note']}",
                "amount": amount,
                "matched_account_id": account["id"],
                "matched_invoice_id": invoice["id"],
                "matched_payment_id": payment["id"],
                "status": "Matched",
            },
        )
    audit(db, user, "pay", "invoices", invoice["id"], f"Collected {amount} for {invoice['invoice_no']}")
    return {"payment": payment, "status": status, "paid_amount": new_paid}


def next_invoice_no(db: sqlite3.Connection) -> tuple[str, int, int]:
    year = date.today().year
    prefix = f"INV-{year}-"
    row = db.execute(
        "SELECT MAX(CAST(substr(invoice_no, -4) AS INTEGER)) FROM invoices WHERE invoice_no LIKE ?",
        (prefix + "%",),
    ).fetchone()[0]
    seq = int(row or 0) + 1
    return f"{prefix}{seq:04d}", year, seq


def next_estate_reservation_invoice_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    prefix = f"RSV-{year}-"
    row = db.execute(
        "SELECT MAX(CAST(substr(invoice_no, -4) AS INTEGER)) FROM estate_reservation_invoices WHERE invoice_no LIKE ?",
        (prefix + "%",),
    ).fetchone()[0]
    seq = int(row or 0) + 1
    return f"{prefix}{seq:04d}"


def next_estate_contract_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    prefix = f"EST-{year}-"
    row = db.execute(
        "SELECT MAX(CAST(substr(contract_no, -4) AS INTEGER)) FROM estate_contracts WHERE contract_no LIKE ?",
        (prefix + "%",),
    ).fetchone()[0]
    seq = int(row or 0) + 1
    return f"{prefix}{seq:04d}"


def next_estate_contract_invoice_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    prefix = f"ECI-{year}-"
    row = db.execute(
        "SELECT MAX(CAST(substr(invoice_no, -4) AS INTEGER)) FROM estate_contract_invoices WHERE invoice_no LIKE ?",
        (prefix + "%",),
    ).fetchone()[0]
    seq = int(row or 0) + 1
    return f"{prefix}{seq:04d}"


def estate_contract_schedule_due_dates(start_date: str, end_date: str, payment_cycle: str) -> List[str]:
    s = datetime.fromisoformat(str(start_date)).date()
    e = datetime.fromisoformat(str(end_date)).date()
    if e < s:
        raise ValueError("Invalid contract date range")
    cycle = str(payment_cycle or "monthly").strip().lower()
    if cycle == "once":
        return [s.isoformat()]
    step = 1 if cycle == "monthly" else (3 if cycle == "quarterly" else 12)
    dates: List[str] = []
    cur = s
    while cur <= e:
        dates.append(cur.isoformat())
        nxt = add_months(cur, step)
        if nxt == cur:
            break
        cur = nxt
    if not dates:
        dates.append(s.isoformat())
    return dates


def generate_estate_contract_invoices(
    db: sqlite3.Connection,
    contract_row: Dict[str, Any],
    actor_name: str,
    replace_open: bool = False,
) -> Dict[str, Any]:
    contract_id = str(contract_row.get("id") or "")
    if not contract_id:
        raise ValueError("Contract id missing")
    if replace_open:
        db.execute("DELETE FROM estate_contract_invoices WHERE contract_id=? AND lower(status)='pending'", (contract_id,))
    due_dates = estate_contract_schedule_due_dates(
        str(contract_row.get("start_date") or ""),
        str(contract_row.get("end_date") or ""),
        str(contract_row.get("payment_cycle") or "monthly"),
    )
    amount = round(float(contract_row.get("rent_amount") or 0), 3)
    if amount <= 0:
        raise ValueError("Rent amount must be positive")
    created = 0
    skipped = 0
    for due in due_dates:
        if is_estate_month_closed(db, due):
            raise ValueError(f"لا يمكن إنشاء دفعة بتاريخ {due} لأن الشهر مقفل ماليًا")
        exists_row = db.execute(
            "SELECT id FROM estate_contract_invoices WHERE contract_id=? AND due_date=? LIMIT 1",
            (contract_id, due),
        ).fetchone()
        if exists_row:
            skipped += 1
            continue
        row = {
            "id": uid("ECI"),
            "invoice_no": next_estate_contract_invoice_no(db),
            "contract_id": contract_id,
            "due_date": due,
            "amount": amount,
            "paid_amount": 0,
            "status": "Pending",
            "issued_at": today(),
            "note": f"Auto schedule by {actor_name}",
        }
        insert(db, "estate_contract_invoices", row)
        created += 1
    return {"created": created, "skipped": skipped, "count": len(due_dates)}


def month_key_from_date_str(value: str) -> str:
    d = datetime.fromisoformat(str(value)).date()
    return d.strftime("%Y-%m")


def is_estate_month_closed(db: sqlite3.Connection, date_str: str) -> bool:
    mk = month_key_from_date_str(date_str)
    row = db.execute(
        "SELECT id FROM estate_month_closes WHERE month_key=? AND lower(status)='closed' LIMIT 1",
        (mk,),
    ).fetchone()
    return bool(row)


def log_estate_status_history(
    db: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    old_status: str,
    new_status: str,
    actor_name: str,
    note: str = "",
) -> None:
    insert(
        db,
        "estate_status_history",
        {
            "id": uid("ESH"),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "property_id": payload.get("property_id"),
            "building_id": payload.get("building_id"),
            "apartment_id": payload.get("apartment_id") if entity_type == "room" else payload.get("id"),
            "room_id": payload.get("id") if entity_type == "room" else None,
            "old_status": old_status or None,
            "new_status": new_status,
            "changed_by": actor_name,
            "changed_at": now_iso(),
            "note": note,
        },
    )


def estate_unit_table(entity_type: str) -> str:
    et = str(entity_type or "").strip().lower()
    return "estate_rooms" if et == "room" else "estate_apartments"


def estate_unit_status_blocks_contract(status: Any) -> bool:
    return str(status or "").strip().lower() in ("maintenance", "suspended")


def estate_contract_dates_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    try:
        sa = datetime.fromisoformat(str(start_a)).date()
        ea = datetime.fromisoformat(str(end_a)).date()
        sb = datetime.fromisoformat(str(start_b)).date()
        eb = datetime.fromisoformat(str(end_b)).date()
    except Exception:
        return False
    return not (ea < sb or eb < sa)


def conflicting_active_estate_contract(
    db: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    start_date: str,
    end_date: str,
    exclude_contract_id: str = "",
) -> Optional[Dict[str, Any]]:
    rows = rows_to_dicts(
        db.execute(
            """
            SELECT id, contract_no, status, start_date, end_date
            FROM estate_contracts
            WHERE lower(entity_type)=lower(?) AND entity_id=? AND (?='' OR id<>?)
            ORDER BY start_date
            """,
            (entity_type, entity_id, exclude_contract_id, exclude_contract_id),
        ).fetchall()
    )
    for row in rows:
        if str(row.get("status") or "").strip().lower() not in ESTATE_UNIT_ACTIVE_STATUSES:
            continue
        if estate_contract_dates_overlap(
            start_date,
            end_date,
            str(row.get("start_date") or ""),
            str(row.get("end_date") or ""),
        ):
            return row
    return None


def set_estate_unit_status(
    db: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    target_status: str,
    actor_name: str,
    note: str,
) -> None:
    table = estate_unit_table(entity_type)
    row = db.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
    if not row:
        return
    current_status = str(row["status"] or "").strip().lower()
    next_status = str(target_status or "").strip().lower()
    if not next_status or current_status == next_status:
        return
    if next_status == "vacant" and current_status in ("maintenance", "suspended"):
        return
    db.execute(
        f"UPDATE {table} SET status=?, last_update=? WHERE id=?",
        (next_status, today(), entity_id),
    )
    log_estate_status_history(
        db,
        entity_type,
        entity_id,
        dict(row),
        current_status,
        next_status,
        actor_name,
        note,
    )


def ensure_estate_reservation_invoice(
    db: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    actor_name: str,
) -> None:
    open_row = db.execute(
        "SELECT id FROM estate_reservation_invoices WHERE entity_type=? AND entity_id=? AND lower(status)='open' ORDER BY rowid DESC LIMIT 1",
        (entity_type, entity_id),
    ).fetchone()
    if open_row:
        return
    deposit = round(float(payload.get("booking_deposit") or 0), 3)
    prepaid = round(float(payload.get("prepaid_amount") or 0), 3)
    rent = round(float(payload.get("rent_price") or 0), 3)
    total = round(max(0.0, deposit + prepaid), 3)
    if total <= 0:
        return
    issue_date = today()
    due_date = str(payload.get("reservation_start_date") or issue_date)
    client_id = str(payload.get("booked_client_id") or "").strip() or None
    client_name = str(payload.get("booked_client_name") or "").strip() or ""
    if client_id and not client_name:
        c = db.execute("SELECT name FROM clients WHERE id=?", (client_id,)).fetchone()
        if c:
            client_name = str(c["name"] or "")
    row = {
        "id": uid("RSV"),
        "invoice_no": next_estate_reservation_invoice_no(db),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "property_id": payload.get("property_id"),
        "building_id": payload.get("building_id"),
        "apartment_id": payload.get("apartment_id") if entity_type == "room" else entity_id,
        "room_id": entity_id if entity_type == "room" else None,
        "client_id": client_id,
        "client_name": client_name or "Reservation Client",
        "issued_by": actor_name,
        "issue_date": issue_date,
        "due_date": due_date,
        "rent_price": rent,
        "deposit_amount": deposit,
        "prepaid_amount": prepaid,
        "total_amount": total,
        "status": "Open",
        "note": f"Auto reservation invoice for {entity_type} {entity_id}",
    }
    insert(db, "estate_reservation_invoices", row)
    insert(
        db,
        "accounts",
        {
            "id": uid("ACC"),
            "entry_date": issue_date,
            "type": "income",
            "category": "Estate Reservation",
            "description": f"Reservation {row['invoice_no']} - {entity_type} {entity_id}",
            "client_id": client_id,
            # accounts.property_id references legacy properties table, not estate_properties
            "property_id": None,
            "invoice_id": None,
            "amount": total,
        },
    )


def invoice_tax_breakdown(subtotal: float, vat_rate: float | None = None) -> Dict[str, float]:
    rate = VAT_RATE if vat_rate is None else float(vat_rate)
    sub = round(float(subtotal or 0), 3)
    vat = round(sub * rate, 3)
    grand = round(sub + vat, 3)
    return {"subtotal": sub, "vat_rate": rate, "vat_amount": vat, "grand_total": grand}


def build_invoice_row(
    db: sqlite3.Connection,
    contract: Any,
    description: str,
    subtotal: float,
    issue_date: str | None = None,
    due_date: str | None = None,
    invoice_type: str = "rent",
    vat_rate: float | None = None,
    source_invoice_id: str | None = None,
) -> Dict[str, Any]:
    tax = invoice_tax_breakdown(subtotal, vat_rate)
    invoice_no, seq_year, seq_no = next_invoice_no(db)
    description_text = str(description or "").strip() or contract_invoice_description(db, contract, due_date)
    return {
        "id": uid("INV"),
        "invoice_no": invoice_no,
        "contract_id": contract["id"],
        "client_id": contract["client_id"],
        "property_id": contract["property_id"],
        "issue_date": issue_date or today(),
        "due_date": due_date or (date.today() + timedelta(days=7)).isoformat(),
        "description": description_text,
        "invoice_type": invoice_type,
        "subtotal": tax["subtotal"],
        "vat_rate": tax["vat_rate"],
        "vat_amount": tax["vat_amount"],
        "grand_total": tax["grand_total"],
        "amount": tax["grand_total"],
        "paid_amount": 0,
        "status": "Pending",
        "is_void": 0,
        "void_reason": "",
        "voided_at": None,
        "sequence_year": seq_year,
        "sequence_no": seq_no,
        "reissued_from": source_invoice_id or "",
    }


def detect_invoice_type(description: str, explicit: str | None = None) -> str:
    if explicit:
        return str(explicit).strip().lower()
    desc = str(description or "").lower()
    if any(token in desc for token in ("تأمين", "deposit", "security", "امان")):
        return "deposit"
    return "rent"


def sync_contract_deposit(db: sqlite3.Connection, contract_id: str, paid_amount: float) -> None:
    contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
    if not contract:
        return
    required = float(contract["deposit_amount"] or 0)
    if required <= 0:
        return
    received = float(contract["deposit_received_amount"] or 0) + float(paid_amount or 0)
    received_flag = 1 if received >= required - 0.001 else int(contract["deposit_received"] or 0)
    received_at = contract["deposit_received_at"] or (today() if received_flag else None)
    db.execute(
        "UPDATE contracts SET deposit_received=?, deposit_received_at=?, deposit_received_amount=? WHERE id=?",
        (received_flag, received_at, round(received, 3), contract_id),
    )


def normalize_deposit_fields(data: Dict[str, Any]) -> None:
    raw = data.get("deposit_received")
    if raw in (1, "1", True, "yes", "Yes", "نعم", "تم"):
        data["deposit_received"] = 1
        data.setdefault("deposit_received_at", today())
        data["deposit_received_amount"] = float(data.get("deposit_received_amount") or data.get("deposit_amount") or 0)
    elif raw in (0, "0", False, "no", "No", "لا"):
        data["deposit_received"] = 0
        if not data.get("deposit_received_at"):
            data["deposit_received_at"] = None
        data["deposit_received_amount"] = float(data.get("deposit_received_amount") or 0)

def next_purchase_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    count = db.execute("SELECT COUNT(*) FROM purchase_invoices WHERE purchase_no LIKE ?", (f"PINV-{year}-%",)).fetchone()[0]
    return f"PINV-{year}-{count + 1:04d}"

def next_revenue_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    count = db.execute("SELECT COUNT(*) FROM revenues WHERE revenue_no LIKE ?", (f"REV-{year}-%",)).fetchone()[0]
    return f"REV-{year}-{count + 1:04d}"

def next_contract_no(db: sqlite3.Connection, contract_type: str = "Residential") -> str:
    year = date.today().year
    code = {"Residential":"RES", "Commercial":"COM", "Short-Term":"STR", "Hospitality":"HOS"}.get(contract_type, "RES")
    pattern = f"LQL-{code}-{year}-%"
    count = db.execute("SELECT COUNT(*) FROM contracts WHERE contract_no LIKE ?", (pattern,)).fetchone()[0]
    return f"LQL-{code}-{year}-{count + 1:04d}"


def next_hospitality_folio_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    count = db.execute("SELECT COUNT(*) FROM hospitality_folios WHERE folio_no LIKE ?", (f"HFO-{year}-%",)).fetchone()[0]
    return f"HFO-{year}-{count + 1:04d}"


def seasonal_rate_for_booking(
    db: sqlite3.Connection,
    property_id: Optional[str],
    room_type: Optional[str],
    checkin_date: str,
    checkout_date: str,
) -> Optional[float]:
    pid = str(property_id or "").strip()
    rtype = str(room_type or "").strip()
    q = """
        SELECT nightly_rate, room_type, start_date, end_date, property_id
        FROM hospitality_season_rates
        WHERE active=1
          AND date(start_date) <= date(?)
          AND date(end_date) >= date(?)
          AND (? = '' OR property_id = ?)
          AND (room_type IS NULL OR room_type='' OR ? = '' OR lower(room_type)=lower(?))
        ORDER BY
          CASE WHEN property_id=? THEN 0 ELSE 1 END,
          CASE WHEN lower(room_type)=lower(?) THEN 0 ELSE 1 END,
          start_date DESC
        LIMIT 1
    """
    row = db.execute(q, (checkin_date, checkout_date, pid, pid, rtype, rtype, pid, rtype)).fetchone()
    if not row:
        return None
    return float(row["nightly_rate"] or 0)


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return date(year, month, day)


def contract_duration_months(start: str, end: str) -> int:
    try:
        s = datetime.fromisoformat(str(start)).date()
        e = datetime.fromisoformat(str(end)).date()
    except ValueError:
        return 12
    months = max(1, (e.year - s.year) * 12 + (e.month - s.month))
    if e.day >= s.day:
        months = max(1, months)
    return months


def contract_renewal_stats(db: sqlite3.Connection) -> Dict[str, int]:
    today_d = date.today()
    expiring = 0
    expired = 0
    rows = db.execute(
        "SELECT end_date, renewal_notice_days, status FROM contracts WHERE lower(status) LIKE '%active%'"
    ).fetchall()
    for row in rows:
        try:
            end = datetime.fromisoformat(str(row["end_date"])).date()
        except ValueError:
            continue
        notice = int(row["renewal_notice_days"] or 30)
        days_left = (end - today_d).days
        if days_left < 0:
            expired += 1
        elif days_left <= notice:
            expiring += 1
    return {"expiring": expiring, "expired": expired}


def default_legal_terms() -> str:
    return (
        "The tenant shall pay rent on or before the due date. The company may apply late fees after the grace period. "
        "The tenant is responsible for damages caused by misuse, unauthorized alterations, lost keys, and violations of building rules. "
        "The unit must be returned in good condition, excluding normal wear. Subleasing is not allowed without written approval. "
        "Utilities, services, and maintenance responsibilities follow the signed contract and applicable laws in the Sultanate of Oman. "
        "This contract protects Launch Quality LLC as the property management and leasing company while preserving the tenant's lawful rights."
    )


def active_contract_exists_for_property(db: sqlite3.Connection, property_id: str, exclude_contract_id: str = "") -> bool:
    rows = db.execute(
        """
        SELECT id, status FROM contracts
        WHERE property_id=? AND (?='' OR id<>?)
        """,
        (property_id, exclude_contract_id, exclude_contract_id),
    ).fetchall()
    for row in rows:
        st = str(row["status"] or "").strip().lower()
        if st in CONTRACT_ACTIVE_STATUSES:
            return True
    return False


def contract_dates_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    try:
        sa = datetime.fromisoformat(str(start_a)).date()
        ea = datetime.fromisoformat(str(end_a)).date()
        sb = datetime.fromisoformat(str(start_b)).date()
        eb = datetime.fromisoformat(str(end_b)).date()
    except Exception:
        return False
    return not (ea < sb or eb < sa)


def conflicting_contract_for_property(
    db: sqlite3.Connection,
    property_id: str,
    start_date: str,
    end_date: str,
    exclude_contract_id: str = "",
) -> Optional[Dict[str, Any]]:
    rows = rows_to_dicts(
        db.execute(
            """
            SELECT id, contract_no, status, start_date, end_date
            FROM contracts
            WHERE property_id=? AND (?='' OR id<>?)
            ORDER BY start_date
            """,
            (property_id, exclude_contract_id, exclude_contract_id),
        ).fetchall()
    )
    for row in rows:
        st = str(row.get("status") or "").strip().lower()
        if st not in CONTRACT_ACTIVE_STATUSES:
            continue
        if contract_dates_overlap(start_date, end_date, str(row.get("start_date") or ""), str(row.get("end_date") or "")):
            return row
    return None


def property_status_blocks_rental(status: Any) -> bool:
    st = normalize_property_status(status)
    return st in ("تحت الصيانة", "موقوفة")


def sync_property_status_for_contract(db: sqlite3.Connection, property_id: str, contract_status: str) -> None:
    status = str(contract_status or "").strip().lower()
    if status == "active":
        db.execute(
            "UPDATE properties SET status=?, last_update=? WHERE id=?",
            ("مستأجرة", today(), property_id),
        )
        return
    if status in ("expired", "cancelled", "canceled", "renewed", "closed"):
        if not active_contract_exists_for_property(db, property_id):
            current = db.execute("SELECT status FROM properties WHERE id=?", (property_id,)).fetchone()
            if current and normalize_property_status(current["status"]) in ("تحت الصيانة", "موقوفة"):
                return
            db.execute(
                "UPDATE properties SET status=?, last_update=? WHERE id=?",
                ("شاغرة", today(), property_id),
            )


def contract_invoice_description(db: sqlite3.Connection, contract: Any, due_date: Optional[str] = None) -> str:
    prop = db.execute(
        "SELECT building_no, apartment_no, room_no, location FROM properties WHERE id=?",
        (contract["property_id"],),
    ).fetchone()
    client = db.execute("SELECT name FROM clients WHERE id=?", (contract["client_id"],)).fetchone()
    unit = "وحدة"
    if prop:
        unit_parts = []
        if prop["building_no"]:
            unit_parts.append(f"بناية {prop['building_no']}")
        if prop["apartment_no"]:
            unit_parts.append(f"شقة {prop['apartment_no']}")
        if prop["room_no"]:
            unit_parts.append(f"غرفة {prop['room_no']}")
        unit = " - ".join(unit_parts) if unit_parts else "وحدة"
    client_name = str(client["name"] or "").strip() if client else "عميل"
    due_text = due_date or ""
    return f"إيجار {unit} للعميل {client_name}" + (f" - استحقاق {due_text}" if due_text else "")


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


PROPERTY_STATUSES_AR = ("شاغرة", "محجوزة", "مستأجرة", "تحت الصيانة", "موقوفة")
GEOCODE_CACHE: Dict[str, Tuple[float, float]] = {}


def normalize_property_status(status: Any) -> str:
    raw = str(status or "").strip()
    if not raw:
        return "شاغرة"
    lower = raw.lower()
    mapping = {
        "vacant": "شاغرة",
        "rented": "مستأجرة",
        "leased": "مستأجرة",
        "maintenance": "تحت الصيانة",
        "under_maintenance": "تحت الصيانة",
        "suspended": "موقوفة",
        "stopped": "موقوفة",
        "pending": "محجوزة",
        "reserved": "محجوزة",
        "صيانة": "تحت الصيانة",
    }
    if lower in mapping:
        return mapping[lower]
    if raw in PROPERTY_STATUSES_AR:
        return raw
    return raw


def property_display_name(data: Dict[str, Any]) -> str:
    building = str(data.get("building_no") or "").strip()
    apartment = str(data.get("apartment_no") or "").strip()
    room = str(data.get("room_no") or "").strip()
    unit_kind = str(data.get("unit_kind") or "").strip() or "شقة كاملة"
    room_count = str(data.get("unit_rooms_count") or "").strip()
    if building or apartment or room:
        parts = [f"بناية {building}", f"وحدة {apartment}"]
        if unit_kind == "غرفة مستقلة" and room:
            parts.append(f"غرفة {room}")
        if unit_kind == "شقة كاملة" and room_count:
            parts.append(f"{room_count} غرف")
        parts.append(unit_kind)
        return " - ".join([p for p in parts if p.strip()])
    return str(data.get("name") or "").strip()


def geocode_property_location(location: str) -> Optional[Tuple[float, float]]:
    key = str(location or "").strip()
    if not key:
        return None
    if key in GEOCODE_CACHE:
        return GEOCODE_CACHE[key]
    query = key if any(token in key.lower() for token in ("oman", "nizwa", "نزوى")) else f"{key}, Nizwa, Oman"
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": "1"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "NAJJARTrading/49.0"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read().decode("utf-8") or "[]")
        if isinstance(raw, list) and raw:
            lat = float(raw[0].get("lat"))
            lng = float(raw[0].get("lon"))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                GEOCODE_CACHE[key] = (lat, lng)
                return lat, lng
    except Exception:
        return None
    return None


def prepare_property_payload(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload = dict(data)
    payload["status"] = normalize_property_status(payload.get("status"))
    for field in ("building_no", "apartment_no", "location"):
        val = str(payload.get(field) or "").strip()
        if not val:
            return None, f"Missing required field: {field}"
        payload[field] = val
    unit_kind = str(payload.get("unit_kind") or "").strip() or "شقة كاملة"
    if unit_kind not in ("غرفة مستقلة", "شقة كاملة"):
        return None, "نوع الوحدة يجب أن يكون غرفة مستقلة أو شقة كاملة"
    payload["unit_kind"] = unit_kind
    room_no = str(payload.get("room_no") or "").strip()
    if unit_kind == "غرفة مستقلة":
        if not room_no:
            return None, "رقم الغرفة مطلوب للوحدة من نوع غرفة مستقلة"
        payload["room_no"] = room_no
    else:
        # Full apartment: do not store a room number — rooms_count is informational only.
        payload["room_no"] = ""
    rooms_count_raw = payload.get("unit_rooms_count")
    if rooms_count_raw in (None, ""):
        payload["unit_rooms_count"] = None
    else:
        try:
            rooms_count = int(rooms_count_raw)
        except (TypeError, ValueError):
            return None, "عدد غرف الشقة يجب أن يكون رقماً صحيحاً"
        if rooms_count <= 0:
            return None, "عدد غرف الشقة يجب أن يكون أكبر من صفر"
        payload["unit_rooms_count"] = rooms_count
    try:
        price = float(payload.get("price") if payload.get("price") not in (None, "") else 0)
    except (TypeError, ValueError):
        return None, "Invalid price"
    if price < 0:
        return None, "Price must be non-negative"
    payload["price"] = price
    lat_raw = payload.get("latitude")
    lng_raw = payload.get("longitude")
    if lat_raw not in (None, ""):
        try:
            lat = float(lat_raw)
        except (TypeError, ValueError):
            return None, "Invalid latitude"
        if lat < -90 or lat > 90:
            return None, "Latitude must be between -90 and 90"
        payload["latitude"] = lat
    else:
        payload["latitude"] = None
    if lng_raw not in (None, ""):
        try:
            lng = float(lng_raw)
        except (TypeError, ValueError):
            return None, "Invalid longitude"
        if lng < -180 or lng > 180:
            return None, "Longitude must be between -180 and 180"
        payload["longitude"] = lng
    else:
        payload["longitude"] = None
    if payload["latitude"] is None and payload["longitude"] is None and payload.get("location"):
        coords = geocode_property_location(str(payload.get("location") or ""))
        if coords:
            payload["latitude"], payload["longitude"] = coords
    if not str(payload.get("name") or "").strip():
        payload["name"] = property_display_name(payload)
    payload.setdefault("type", str(payload.get("type") or "Apartment").strip() or "Apartment")
    img = str(payload.get("image") or "").strip()
    if not img:
        payload.setdefault("image", "🏠")
    elif img.startswith("data:"):
        payload["image"] = "🏠"
    else:
        payload["image"] = img
    payload["last_update"] = str(payload.get("last_update") or today())
    return payload, None


def ensure_upload_dirs() -> None:
    PROPERTY_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    WORK_JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_CARD_DIR.mkdir(parents=True, exist_ok=True)
    PAYMENT_PROOF_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "estate_images").mkdir(parents=True, exist_ok=True)


def mirror_upload_best_effort(url: str, file_bytes: bytes, content_type: str) -> None:
    """Mirror a just-written local upload to object storage; never raise."""
    try:
        lq_object_storage.mirror_upload_url(url, file_bytes, content_type or "application/octet-stream")
    except Exception:
        pass


def is_stored_property_image(value: Any) -> bool:
    s = str(value or "").strip()
    return s.startswith("/uploads/properties/")


def property_photo_path_from_url(url: str) -> Optional[Path]:
    s = str(url or "").strip()
    if not is_stored_property_image(s):
        return None
    rel = s.lstrip("/").replace("\\", "/")
    if not rel.startswith("uploads/properties/"):
        return None
    full = (UPLOAD_DIR / rel.removeprefix("uploads/")).resolve()
    try:
        full.relative_to(PROPERTY_PHOTO_DIR.resolve())
    except ValueError:
        return None
    return full


def delete_property_photo_file(image_value: Any) -> None:
    url = str(image_value or "").strip()
    path = property_photo_path_from_url(url)
    if path and path.exists() and path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    try:
        lq_object_storage.delete_upload_url(url)
    except Exception:
        pass


def decode_property_photo_payload(data: Dict[str, Any]) -> Tuple[Optional[bytes], str]:
    raw = str(data.get("image") or data.get("data") or "").strip()
    content_type = str(data.get("content_type") or "").strip().lower()
    if raw.startswith("data:"):
        header, payload = raw.split(",", 1)
        meta = header[5:]
        mime = meta.split(";")[0].strip().lower() if meta else ""
        if not mime.startswith("image/"):
            raise ValueError("نوع الملف غير مدعوم — استخدم صورة JPG أو PNG أو WebP")
        file_bytes = base64.b64decode(payload)
        return file_bytes, mime or "image/jpeg"
    if data.get("base64"):
        file_bytes = base64.b64decode(str(data.get("base64")))
        mime = content_type or "image/jpeg"
        if not mime.startswith("image/"):
            raise ValueError("نوع الملف غير مدعوم")
        return file_bytes, mime
    raise ValueError("لم يتم إرسال صورة")


def extension_for_image_type(content_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(content_type.lower(), ".jpg")


def save_property_photo_file(property_id: str, file_bytes: bytes, content_type: str) -> str:
    if len(file_bytes) > MAX_PROPERTY_PHOTO_BYTES:
        raise ValueError(f"حجم الصورة كبير — الحد الأقصى {MAX_PROPERTY_PHOTO_BYTES // (1024 * 1024)}MB")
    if not content_type.startswith("image/"):
        raise ValueError("نوع الملف غير مدعوم")
    ensure_upload_dirs()
    digest = hashlib.sha256(file_bytes).hexdigest()[:10]
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(property_id))
    ext = extension_for_image_type(content_type)
    filename = f"{safe_id}-{digest}{ext}"
    target = PROPERTY_PHOTO_DIR / filename
    target.write_bytes(file_bytes)
    url = f"/uploads/properties/{filename}"
    mirror_upload_best_effort(url, file_bytes, content_type)
    return url


def save_named_image_upload(folder: str, prefix: str, file_bytes: bytes, content_type: str, max_bytes: int) -> str:
    if len(file_bytes) > max_bytes:
        raise ValueError(f"حجم الصورة كبير — الحد الأقصى {max_bytes // (1024 * 1024)}MB")
    if not content_type.startswith("image/"):
        raise ValueError("نوع الملف غير مدعوم (صور فقط)")
    ensure_upload_dirs()
    digest = hashlib.sha256(file_bytes).hexdigest()[:10]
    safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "", str(prefix or "upload"))[:40] or "upload"
    ext = extension_for_image_type(content_type)
    filename = f"{safe_prefix}-{digest}{ext}"
    target_dir = (UPLOAD_DIR / folder).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    target.write_bytes(file_bytes)
    url = f"/uploads/{folder}/{filename}"
    mirror_upload_best_effort(url, file_bytes, content_type)
    return url


def save_contract_attachment(contract_id: str, file_bytes: bytes, content_type: str, original_name: str) -> Dict[str, str]:
    ensure_upload_dirs()
    if not file_bytes:
        raise ValueError("Empty contract attachment")
    if len(file_bytes) > MAX_CLIENT_CARD_BYTES:
        raise ValueError("Contract attachment exceeds max allowed size")
    ext = (
        extension_for_image_type(content_type)
        if str(content_type or "").startswith("image/")
        else (mimetypes.guess_extension(content_type or "") or Path(str(original_name or "")).suffix or ".bin")
    )
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(original_name or "attachment"))[:80] or "attachment"
    stem = Path(safe_name).stem[:40] or "attachment"
    final_name = f"{contract_id}-{uid('CAT')}-{stem}{ext}"
    target = CONTRACT_ATTACHMENT_DIR / final_name
    target.write_bytes(file_bytes)
    url = f"/uploads/contracts/{final_name}"
    mirror_upload_best_effort(url, file_bytes, content_type or "application/octet-stream")
    return {
        "name": safe_name,
        "type": content_type or "application/octet-stream",
        "url": url,
        "uploaded_at": now_iso(),
    }


def is_stored_upload_url(value: Any, folder: str) -> bool:
    prefix = f"/uploads/{folder.strip('/')}/"
    return str(value or "").strip().startswith(prefix)


def upload_path_from_url(url: str, folder: str) -> Optional[Path]:
    s = str(url or "").strip()
    prefix = f"/uploads/{folder.strip('/')}/"
    if not s.startswith(prefix):
        return None
    rel = s.lstrip("/").replace("\\", "/")
    expected = f"uploads/{folder.strip('/')}/"
    if not rel.startswith(expected):
        return None
    root = (UPLOAD_DIR / folder.strip("/")).resolve()
    full = (UPLOAD_DIR / rel.removeprefix("uploads/")).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        return None
    return full


def delete_upload_file(url: str, folder: str) -> None:
    path = upload_path_from_url(url, folder)
    if path and path.exists() and path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    try:
        lq_object_storage.delete_upload_url(url)
    except Exception:
        pass


def decode_upload_payload(data: Dict[str, Any]) -> Tuple[bytes, str]:
    raw = str(data.get("image") or data.get("data") or "").strip()
    content_type = str(data.get("content_type") or data.get("type") or "").strip().lower()
    if raw.startswith("data:"):
        header, payload = raw.split(",", 1)
        mime = header[5:].split(";")[0].strip().lower()
        if not mime:
            mime = content_type or "application/octet-stream"
        return base64.b64decode(payload), mime
    if data.get("base64"):
        mime = content_type or "application/octet-stream"
        return base64.b64decode(str(data.get("base64"))), mime
    raise ValueError("لم يتم إرسال الملف")


def save_journal_attachment(entry_id: str, file_bytes: bytes, content_type: str, original_name: str) -> Dict[str, str]:
    if len(file_bytes) > MAX_JOURNAL_FILE_BYTES:
        raise ValueError(f"حجم الملف كبير — الحد {MAX_JOURNAL_FILE_BYTES // (1024 * 1024)}MB")
    ensure_upload_dirs()
    digest = hashlib.sha256(file_bytes).hexdigest()[:10]
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(entry_id))[:24] or "entry"
    base_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(original_name or "file").name)[:80] or "file"
    if content_type.startswith("image/"):
        ext = extension_for_image_type(content_type)
        filename = f"{safe_id}-{digest}{ext}"
    else:
        stem = Path(base_name).stem[:40] or "file"
        ext = Path(base_name).suffix[:12]
        filename = f"{safe_id}-{digest}-{stem}{ext}"
    target = WORK_JOURNAL_DIR / filename
    target.write_bytes(file_bytes)
    url = f"/uploads/work_journal/{filename}"
    mirror_upload_best_effort(url, file_bytes, content_type or "application/octet-stream")
    return {
        "name": original_name or filename,
        "type": content_type,
        "url": url,
    }


def parse_journal_attachments(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not raw:
        return []
    try:
        data = json.loads(str(raw))
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def journal_row_to_item(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    item["attachments"] = parse_journal_attachments(item.get("attachments"))
    return item


def seed_branches_from_buildings(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM branches").fetchone()[0] > 0:
        return
    insert(
        db,
        "branches",
        {
            "id": uid("BR"),
            "code": "HQ",
            "name": "الفرع الرئيسي · Muscat",
            "city": "Muscat",
            "address": COMPANY_NAME,
            "manager": "Operations",
            "active": 1,
            "notes": "Default headquarters branch",
            "created_at": now_iso(),
        },
    )
    rows = db.execute(
        "SELECT DISTINCT building_no, location FROM properties WHERE trim(coalesce(building_no,''))!=''"
    ).fetchall()
    for row in rows:
        bno = str(row["building_no"]).strip()
        code = re.sub(r"[^A-Z0-9]", "", bno.upper())[:12] or "SITE"
        if db.execute("SELECT id FROM branches WHERE code=?", (code,)).fetchone():
            code = f"{code}-{secrets.token_hex(2).upper()}"
        branch_id = uid("BR")
        city = str(row["location"] or "Oman").strip()
        insert(
            db,
            "branches",
            {
                "id": branch_id,
                "code": code,
                "name": f"بناية {bno}",
                "city": city,
                "address": f"Building {bno}",
                "manager": "",
                "active": 1,
                "notes": "Auto-created from property portfolio",
                "created_at": now_iso(),
            },
        )
        db.execute(
            "UPDATE properties SET branch_id=? WHERE building_no=? AND (branch_id IS NULL OR branch_id='')",
            (branch_id, bno),
        )


def migrate_property_statuses(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT id, status, name, building_no, apartment_no, room_no FROM properties").fetchall()
    for row in rows:
        normalized = normalize_property_status(row["status"])
        updates: Dict[str, Any] = {}
        if normalized != row["status"]:
            updates["status"] = normalized
        if not str(row["name"] or "").strip() and (row["building_no"] or row["apartment_no"] or row["room_no"]):
            updates["name"] = property_display_name(dict(row))
        if updates:
            sets = ", ".join(f"{col}=?" for col in updates)
            db.execute(f"UPDATE properties SET {sets} WHERE id=?", list(updates.values()) + [row["id"]])


def ensure_user(
    db: sqlite3.Connection,
    username: str,
    name: str,
    role: str,
    password: str,
    email: str = "",
) -> None:
    """Ensure a team account exists. Never overwrite an existing user's password."""
    row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    email_val = resolve_user_email(username, email)
    if row:
        db.execute(
            "UPDATE users SET name=?, role=?, active=1 WHERE username=?",
            (name, role, username),
        )
        if email_val:
            db.execute("UPDATE users SET email=? WHERE username=?", (email_val, username))
        return
    pwd, must_change = resolve_bootstrap_password(username, role, password)
    # New accounts always require a real password change — no silent defaults in production.
    if username in CORE_USERNAMES:
        must_change = True
    insert(
        db,
        "users",
        {
            "id": uid("USR"),
            "username": username,
            "name": name,
            "role": role,
            "active": 1,
            "password_hash": password_hash(pwd),
            "email": email_val,
            "must_change_password": 1 if must_change else 0,
            "created_at": now_iso(),
            "last_login": None,
        },
    )


def force_user_credentials(
    db: sqlite3.Connection,
    username: str,
    name: str,
    role: str,
    password: str,
    *,
    email: str = "",
    active: bool = True,
) -> None:
    """Upsert a user and force role/password to be effective now."""
    username_norm = str(username or "").strip().lower()
    if not username_norm:
        return
    email_val = resolve_user_email(username_norm, email)
    row = db.execute("SELECT id FROM users WHERE lower(username)=?", (username_norm,)).fetchone()
    pwd_hash = password_hash(password)
    now_v = now_iso()
    active_v = 1 if active else 0
    if row:
        db.execute(
            """
            UPDATE users
            SET username=?, name=?, role=?, active=?, password_hash=?, email=?,
                must_change_password=0, password_changed_at=?
            WHERE id=?
            """,
            (
                username_norm,
                name,
                role,
                active_v,
                pwd_hash,
                email_val or None,
                now_v,
                row["id"],
            ),
        )
        return
    insert(
        db,
        "users",
        {
            "id": uid("USR"),
            "username": username_norm,
            "name": name,
            "role": role,
            "active": active_v,
            "password_hash": pwd_hash,
            "email": email_val or None,
            "must_change_password": 0,
            "password_changed_at": now_v,
            "created_at": now_v,
            "last_login": None,
        },
    )


def purge_demo_business_data(db: sqlite3.Connection) -> Dict[str, int]:
    """Remove known sample/demo business rows so production stays real-only."""
    removed: Dict[str, int] = {}
    demo_deletes = [
        ("properties", "id IN ('P-1001','P-1002','P-1003','P-1004')"),
        ("clients", "id IN ('C-1001','C-1002')"),
        ("contracts", "id IN ('CT-1001') OR contract_no='LQL-RES-2026-0001'"),
        ("invoices", "id IN ('INV-ID-1001') OR invoice_no='INV-2026-0001'"),
        ("accounts", "id IN ('ACC-1001','ACC-1002')"),
        ("maintenance", "id IN ('M-1001')"),
        ("purchase_invoices", "id IN ('PINV-ID-1001') OR purchase_no='PINV-2026-0001'"),
        ("revenues", "id IN ('REV-ID-1001') OR revenue_no='REV-2026-0001'"),
        ("salaries", "id IN ('SAL-1001') OR employee_name='Building Supervisor'"),
        ("admin_expenses", "id IN ('GNA-1001')"),
        ("inventory_transactions", "id IN ('ITX-1001')"),
        ("inventory_items", "id IN ('ITEM-1001') OR sku='AC-FILTER-01'"),
        ("bank_transactions", "id IN ('BNK-1001') OR reference='OPENING'"),
        ("audit_log", "action='seed' AND entity='database'"),
    ]
    for table, where in demo_deletes:
        try:
            cur = db.execute(f"DELETE FROM {table} WHERE {where}")
            if cur.rowcount:
                removed[table] = int(cur.rowcount)
        except sqlite3.Error:
            continue
    return removed


def ensure_team_users(db: sqlite3.Connection) -> None:
    """NAJJAR-only accounts — legacy Launch Quality ERP users are deactivated."""
    for username, name, role, password in NAJJAR_TEAM_BOOTSTRAP:
        env_key = "LQ_USER_PASSWORD_" + re.sub(r"[^A-Z0-9]+", "_", str(username).upper()).strip("_")
        override = (os.environ.get(env_key) or "").strip()
        effective_password = override or password
        force_user_credentials(
            db,
            username,
            name,
            role,
            effective_password,
            active=True,
        )
    allowed = tuple(sorted(NAJJAR_TEAM_USERNAMES))
    placeholders = ",".join("?" * len(allowed))
    db.execute(
        f"UPDATE users SET active=0 WHERE lower(username) NOT IN ({placeholders})",
        allowed,
    )
    db.execute(
        f"UPDATE users SET active=1 WHERE lower(username) IN ({placeholders})",
        allowed,
    )


class JawdahHandler(BaseHTTPRequestHandler):
    server_status = "NAJJAR"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def cors_origin(self) -> str:
        if CORS_ORIGIN and CORS_ORIGIN != "*":
            return CORS_ORIGIN
        origin = self.headers.get("Origin", "").strip()
        return origin or "*"

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-LQ-Device")
        self.send_header("Access-Control-Max-Age", "86400")

    def send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(raw)

    def send_redirect(self, location: str, *, permanent: bool = False) -> None:
        """302 (or 301) with the same one-shot purge headers HTML pages carry."""
        self.send_response(301 if permanent else 302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        if self.client_needs_purge():
            self.send_purge_headers()
        self.end_headers()

    @staticmethod
    def _site_cleanup_paths() -> frozenset[str]:
        """Reachable while publishing is off — device cleanup only."""
        return frozenset({
            "/closed", "/closed.html",
            "/remove", "/remove-old-app.html",
            "/حذف", "/حذف-التطبيق", "/old-app",
            "/fresh", "/fresh.html", "/reset-cache.html",
            "/remove-old-app.html",
            "/clear-cache", "/تحديث",
            "/sw.js", "/favicon.ico",
        })

    def _site_closed_gate(self, path: str, safe: str, _send_bytes) -> bool:
        """When publishing is off, answer every public face with /closed."""
        if SITE_PUBLISHED:
            return False
        if path in self._site_cleanup_paths():
            if path in ("/closed", "/closed.html"):
                closed = (PUBLIC_DIR / "closed.html").read_bytes()
                _send_bytes(closed, "text/html; charset=utf-8",
                            cache="no-store, no-cache, must-revalidate, max-age=0")
                return True
            return False
        if NAJJAR_PUBLISHED:
            legacy_to_najjar = {
                "/auto-trading/customer.html": NAJJAR_HOME,
                "/auto-trading/login.html": NAJJAR_LOGIN,
                "/auto-trading/platforms.html": NAJJAR_PLATFORMS,
                "/auto-trading.html": NAJJAR_STAFF,
            }
            if path in legacy_to_najjar:
                self.send_redirect(legacy_to_najjar[path])
                return True
            if not ERP_PUBLISHED and path in _RETIRED_ERP_PAGES:
                self.send_redirect(NAJJAR_LOGIN)
                return True
            if not ERP_PUBLISHED and safe in ("app.js", "app.css"):
                stub = (
                    f"location.replace({NAJJAR_LOGIN!r});"
                    if safe == "app.js"
                    else "/* ERP retired — NAJJAR only */"
                )
                _send_bytes(
                    stub.encode("utf-8"),
                    "application/javascript; charset=utf-8" if safe == "app.js" else "text/css; charset=utf-8",
                    cache="no-store, no-cache, must-revalidate, max-age=0",
                )
                return True
            if (
                _is_najjar_public_path(path)
                or _is_auto_trading_asset(safe)
                or _is_najjar_brand_asset(safe)
                or _is_najjar_download_asset(path, safe)
            ):
                return False
            if path == "/manifest.webmanifest":
                manifest = (PUBLIC_DIR / "manifest.webmanifest").read_bytes()
                _send_bytes(manifest, "application/manifest+json; charset=utf-8",
                            cache="no-store, no-cache, must-revalidate, max-age=0")
                return True
        if path == "/manifest.webmanifest":
            body = json.dumps({
                "id": "/closed",
                "name": "Unpublished",
                "short_name": "Closed",
                "start_url": "/closed",
                "scope": "/closed",
                "display": "browser",
                "background_color": "#0a0a0a",
                "theme_color": "#0a0a0a",
            }, ensure_ascii=False).encode("utf-8")
            _send_bytes(body, "application/manifest+json; charset=utf-8",
                        cache="no-store, no-cache, must-revalidate, max-age=0")
            return True
        if path in ("/app.js",) or safe == "app.js":
            _send_bytes(
                b"location.replace('/closed');",
                "application/javascript; charset=utf-8",
                cache="no-store, no-cache, must-revalidate, max-age=0",
            )
            return True
        if path in ("/app.css",) or safe == "app.css":
            _send_bytes(b"/* unpublished */", "text/css; charset=utf-8",
                        cache="no-store, no-cache, must-revalidate, max-age=0")
            return True
        self.send_redirect(SITE_CLOSED_URL)
        return True

    def send_html(self, html: str, status: int = 200) -> None:
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_cors_headers()
        if self.client_needs_purge():
            self.send_purge_headers()
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def token_from_request(self, query: str = "") -> str:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        params = urllib.parse.parse_qs(query or "")
        qtok = (params.get("token") or [""])[0].strip()
        if qtok:
            return qtok
        # Cookie fallback (survives navigation when localStorage is flaky)
        cookie = self.headers.get("Cookie", "") or ""
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(SESSION_COOKIE + "="):
                return urllib.parse.unquote(part.split("=", 1)[1].strip())
            if part.startswith(LEGACY_SESSION_COOKIE + "="):
                return urllib.parse.unquote(part.split("=", 1)[1].strip())
        return ""

    def client_needs_purge(self) -> bool:
        """True until this device has been told to drop an older installed build."""
        if not CLIENT_PURGE_GENERATION:
            return False
        cookie = self.headers.get("Cookie", "") or ""
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(CLIENT_PURGE_COOKIE + "="):
                return urllib.parse.unquote(part.split("=", 1)[1].strip()) != CLIENT_PURGE_GENERATION
            if part.startswith("lq_purge="):
                return True
        return True

    def send_purge_headers(self) -> None:
        """Wipe the stale worker, its caches and its stored shell — once per device."""
        self.send_header("Clear-Site-Data", CLIENT_PURGE_DIRECTIVES)
        self.send_header(
            "Set-Cookie",
            "{}={}; Path=/; Max-Age=31536000; SameSite=Lax".format(
                CLIENT_PURGE_COOKIE, urllib.parse.quote(CLIENT_PURGE_GENERATION)
            ),
        )

    def current_user(self, db: sqlite3.Connection, query: str = "") -> Optional[Dict[str, Any]]:
        token = self.token_from_request(query)
        if not token:
            return None
        row = db.execute(
            """
            SELECT u.id,u.username,u.name,u.role,u.active,u.email,u.created_at,u.last_login,
                   u.must_change_password,u.password_changed_at,s.expires_at
            FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token=? AND u.active=1
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now():
            db.execute("DELETE FROM sessions WHERE token=?", (token,))
            db.commit()
            return None
        return dict(row)

    def require_user(self, db: sqlite3.Connection, permission: Optional[str] = None, query: str = "") -> Optional[Dict[str, Any]]:
        user = self.current_user(db, query)
        if not user:
            self.send_json({"ok": False, "error": "Authentication required"}, 401)
            return None
        if permission and not has_permission(user, permission):
            self.send_json({"ok": False, "error": "Permission denied"}, 403)
            return None
        return user

    def request_rp_id(self) -> str:
        host = (self.headers.get("Host") or "").strip()
        host = host.split(":")[0].strip().lower()
        if host and host not in ("127.0.0.1",):
            return host
        return rp_id_from_origin(PRODUCTION_URL)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api("GET", parsed.path, parsed.query)
        else:
            self.serve_static(parsed.path)

    def do_HEAD(self) -> None:
        """Browsers/download managers often probe with HEAD first.
        Without this method Python returns 501 and some clients abort the download.
        """
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_cors_headers()
            self.end_headers()
            return
        self.serve_static(parsed.path, head_only=True)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        self.handle_api("POST", parsed.path, parsed.query)

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        self.handle_api("PUT", parsed.path, parsed.query)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        self.handle_api("DELETE", parsed.path, parsed.query)

    def serve_static(self, path: str, head_only: bool = False) -> None:
        # Short stable aliases so old/cached 404 bookmarks still fail less often.
        download_name: Optional[str] = None
        # Public site face = NAJJAR & AL SAMOOM TRADING (Launch Quality ERP entry points stay hidden).
        if path in ("/go", "/دخول", "/start"):
            path = "/go.html"
        if path in ("/fresh", "/تحديث", "/clear-cache"):
            path = "/fresh.html"
        # Short enough to read down a phone line to a branch, because reaching every
        # device is the only way the installed icon actually leaves them.
        if path in ("/remove", "/remove-old-app", "/حذف-التطبيق", "/حذف", "/old-app"):
            path = "/remove-old-app.html"
        if path in ("/closed",):
            path = "/closed.html"
        if path in (
            "/NAJJAR-Trading.exe",
            "/najjar-trading.exe",
            "/lq-setup.exe",
            "/windows-setup.exe",
            "/LaunchQuality-Setup.exe",
            "/LaunchQuality.exe",
            "/app-windows.exe",
            "/windows.exe",
        ):
            download_name = "NAJJAR-Trading.exe"
            path = "/releases/windows/NAJJAR-Trading-Setup.exe"
        if path in ("/windows-setup", "/get-windows", "/تحميل-ويندوز", "/download-windows"):
            path = "/get-windows.html"
        if path in ("/get-android", "/android-apk", "/تحميل-اندرويد", "/download-android"):
            path = "/get-android.html"
        if path in ("/NAJJAR-Trading.apk", "/najjar-trading.apk"):
            download_name = "NAJJAR-Trading.apk"
            path = "/releases/android/NAJJAR-Trading.apk"
        if path in ("/lq-staff.apk", "/Launch-Quality-Staff.apk", "/android.apk"):
            download_name = "NAJJAR-Trading.apk"
            path = "/releases/android/NAJJAR-Trading.apk"
        if path in (
            "/NAJJAR-Trading-Windows.zip",
            "/najjar-trading.zip",
            "/lq-portable.zip",
            "/windows-portable.zip",
            "/LaunchQuality-Windows.zip",
            "/windows.zip",
        ):
            download_name = "NAJJAR-Trading-Windows.zip"
            path = "/releases/windows/NAJJAR-Trading-Windows.zip"
        if path in (
            "/NAJJAR-Desktop-Shortcut.zip",
            "/najjar-desktop.zip",
            "/desktop-shortcut.zip",
        ):
            download_name = "NAJJAR-Desktop-Shortcut.zip"
            path = "/releases/windows/NAJJAR-Desktop-Shortcut.zip"
        if path in (
            "/NAJJAR-Trading.url",
            "/najjar-trading.url",
            "/desktop.url",
        ):
            download_name = "NAJJAR Trading.url"
            path = "/releases/windows/NAJJAR-Trading.url"

        def _send_bytes(raw: bytes, ctype: str, *, disposition: str | None = None, cache: str | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            if disposition:
                self.send_header("Content-Disposition", disposition)
            if cache:
                self.send_header("Cache-Control", cache)
            # Carried on page loads only: an asset or API response arrives while the
            # app is mid-flight, and wiping storage under it would strand the tab.
            if ctype.startswith("text/html") and self.client_needs_purge():
                self.send_purge_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(raw)

        safe_peek = Path(urllib.parse.unquote(path).lstrip("/")).as_posix()
        original_path = path
        original_safe = safe_peek

        if NAJJAR_PUBLISHED:
            legacy_target = _najjar_legacy_redirect(path)
            if legacy_target:
                return self.send_redirect(legacy_target, permanent=True)

        if self._site_closed_gate(path, safe_peek, _send_bytes):
            return

        najjar_file = _najjar_page_file(path) if NAJJAR_PUBLISHED else None
        if najjar_file:
            safe_peek = najjar_file
            path = "/" + najjar_file

        # Published face only — when LQ_SITE_PUBLISHED=0 the gate above already sent
        # every other request to /closed (except NAJJAR on NAJJAR_BASE when enabled).
        if SITE_PUBLISHED:
            if path in ("/", "", "/index.html", "/najjar", "/najjar/", "/النجار", "/سيارات", "/auto", "/autotrading"):
                self.send_response(302)
                self.send_header("Location", NAJJAR_HOME)
                self.end_headers()
                return
            if path in (
                "/najjar-login", "/najjar/login", "/دخول-النجار", "/auto-trading/login",
                "/go.html", "/start.html",
                "/login", "/login.html",
            ):
                if path != NAJJAR_LOGIN:
                    self.send_response(302)
                    self.send_header("Location", NAJJAR_LOGIN)
                    self.end_headers()
                    return
            ERP_STAFF_LOGIN = NAJJAR_LOGIN
            ERP_STAFF_HOME = NAJJAR_PLATFORMS
            erp_login = {
                "/app.html", "/app", "/app/", "/app/app.html",
                "/Launch_Quality_LLC.html", "/Launch Quality LLC.html",
                "/install.html", "/download.html", "/docs.html",
                "/quick-estate.html", "/reset-cache.html",
            }
            erp_portal = {
                "/portal-select.html", "/portal-select",
                "/erp", "/erp.html", "/إدارة", "/منصات", "/platforms",
            }
            if path in erp_login:
                return self.send_redirect(ERP_STAFF_LOGIN)
            if path in erp_portal:
                return self.send_redirect(ERP_STAFF_HOME)
            if path == "/app.js":
                _send_bytes(
                    ("location.replace(%r);" % NAJJAR_LOGIN).encode("utf-8"),
                    "application/javascript; charset=utf-8",
                    cache="no-store, no-cache, must-revalidate, max-age=0",
                )
                return
            if path == "/app.css":
                _send_bytes(b"/* Launch Quality ERP retired */", "text/css; charset=utf-8",
                            cache="no-store, no-cache, must-revalidate, max-age=0")
                return
            if path in ("/najjar-platforms", "/najjar/platforms", "/منصات-النجار"):
                self.send_response(302)
                self.send_header("Location", NAJJAR_PLATFORMS)
                self.end_headers()
                return
            if path in ("/najjar-admin", "/najjar/dashboard", "/لوحة-النجار"):
                self.send_response(302)
                self.send_header("Location", NAJJAR_STAFF)
                self.end_headers()
                return
            legacy_auto_html = {
                "/auto-trading/customer.html": NAJJAR_HOME,
                "/auto-trading/login.html": NAJJAR_LOGIN,
                "/auto-trading/platforms.html": NAJJAR_PLATFORMS,
                "/auto-trading.html": NAJJAR_STAFF,
            }
            if path in legacy_auto_html:
                return self.send_redirect(legacy_auto_html[path])

        if not SITE_PUBLISHED and NAJJAR_PUBLISHED:
            legacy_to_najjar = {
                "/auto-trading/customer.html": NAJJAR_HOME,
                "/auto-trading/login.html": NAJJAR_LOGIN,
                "/auto-trading/platforms.html": NAJJAR_PLATFORMS,
                "/auto-trading.html": NAJJAR_STAFF,
            }
            if original_path in legacy_to_najjar:
                return self.send_redirect(legacy_to_najjar[original_path])
            if original_safe.startswith("auto-trading/") and original_safe.endswith(".html"):
                return self.send_redirect(SITE_CLOSED_URL)

        if path == "/favicon.ico":
            fav = PUBLIC_DIR / "favicon.ico"
            if not fav.is_file():
                fav = PUBLIC_DIR / "assets" / "app-icon-192.png"
            if fav.is_file():
                data = fav.read_bytes()
                ctype = "image/x-icon" if fav.suffix.lower() == ".ico" else "image/png"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(204)
            self.end_headers()
            return
        # Decode URL-encoded paths (e.g. %20) so files with spaces can be served.
        safe = Path(urllib.parse.unquote(path).lstrip("/")).as_posix()
        # Vehicle paperwork carries landed costs and the names of previous owners.
        if safe.startswith("auto-trading/documents/"):
            with connect() as db:
                doc_user = self.current_user(db, urllib.parse.urlparse(self.path).query)
            if not doc_user:
                self.send_response(401)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_cors_headers()
                self.end_headers()
                if not head_only:
                    self.wfile.write(json.dumps({"ok": False, "error": "Authentication required"}).encode("utf-8"))
                return
        if safe.startswith("uploads/"):
            # Secure contract and sensitive uploads behind authenticated sessions.
            protected_prefixes = (
                "uploads/contracts/",
                "uploads/client_cards/",
                "uploads/payment_proofs/",
                "uploads/work_journal/",
                "uploads/properties/",
                "uploads/estate_images/",
                "uploads/attachments/",
            )
            if safe.startswith(protected_prefixes):
                static_query = urllib.parse.urlparse(self.path).query
                with connect() as db:
                    user = self.current_user(db, static_query)
                if not user:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_cors_headers()
                    self.end_headers()
                    if not head_only:
                        self.wfile.write(json.dumps({"ok": False, "error": "Authentication required"}).encode("utf-8"))
                    return
            upload_root = UPLOAD_DIR.resolve()
            full = (UPLOAD_DIR / safe.removeprefix("uploads/")).resolve()
            if str(full).startswith(str(upload_root)) and full.exists() and full.is_file():
                raw = full.read_bytes()
                ctype = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
                _send_bytes(raw, ctype, cache="public, max-age=86400")
                return
            # Local miss → try object storage mirror, optionally hydrate local cache
            if str(full).startswith(str(upload_root)):
                remote, remote_ctype = lq_object_storage.fetch_upload_url("/" + safe)
                if remote is not None:
                    try:
                        full.parent.mkdir(parents=True, exist_ok=True)
                        full.write_bytes(remote)
                    except OSError:
                        pass
                    ctype = remote_ctype or mimetypes.guess_type(safe)[0] or "application/octet-stream"
                    _send_bytes(remote, ctype, cache="public, max-age=86400")
                    return
        full = (PUBLIC_DIR / safe).resolve()
        public_root = PUBLIC_DIR.resolve()
        if str(full).startswith(str(public_root)) and full.exists() and not full.is_dir():
            raw = full.read_bytes()
            ctype = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
            if full.suffix in {".html", ".css", ".js"}:
                ctype += "; charset=utf-8"
            disposition = None
            cache = None
            if full.suffix.lower() in {".exe", ".msi", ".zip", ".apk", ".bat", ".ps1", ".cmd"}:
                fname = download_name or full.name
                disposition = f'attachment; filename="{fname}"'
                cache = "no-cache, must-revalidate"
            elif safe.endswith(".html"):
                cache = "no-store, no-cache, must-revalidate, max-age=0"
            elif safe.endswith((".css", ".js")):
                # Prevent stale dashboard shells from hiding functions
                cache = "no-store, no-cache, must-revalidate, max-age=0"
            elif full.suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}:
                if "brand-logo" in safe or "login-logo" in safe:
                    cache = "no-cache, must-revalidate"
                else:
                    cache = "public, max-age=86400"
            _send_bytes(raw, ctype, disposition=disposition, cache=cache)
            return
        # Safe fallback — only when publishing is on and ERP paths slipped through.
        if SITE_PUBLISHED:
            if path == "/app.html":
                return self.send_redirect(NAJJAR_LOGIN)
            if path == "/portal-select.html":
                return self.send_redirect(NAJJAR_PLATFORMS)
            if path == "/app.css":
                raw = b"/* retired */"
                _send_bytes(raw, "text/css; charset=utf-8", cache="no-store")
                return
            if path == "/app.js":
                raw = ("location.replace(%r);" % NAJJAR_LOGIN).encode("utf-8")
                _send_bytes(raw, "application/javascript; charset=utf-8", cache="no-store")
                return
        elif path in ("/app.html", "/portal-select.html", "/app.js", "/app.css"):
            return self.send_redirect(SITE_CLOSED_URL)
        self.send_error(404, "File not found")

    def handle_api(self, method: str, path: str, query: str) -> None:
        try:
            with connect() as db:
                parts = [p for p in path.split("/") if p][1:]
                if not parts:
                    return self.send_json({"ok": True, "status": "production"})
                if not SITE_PUBLISHED and parts[0] != "health" and not (
                    NAJJAR_PUBLISHED and _najjar_api_allowed(parts)
                ):
                    return self.send_json(
                        {"ok": False, "error": "Site unpublished", "closed": True},
                        503,
                    )
                if not ERP_PUBLISHED and parts[0] != "health" and not _najjar_api_allowed(parts):
                    return self.send_json(
                        {"ok": False, "error": "ERP retired — NAJJAR only", "najjar_only": True},
                        503,
                    )
                if parts[0] == "quick-estate":
                    user = self.require_user(db, "dashboard")
                    if not user:
                        return None
                    payload: Dict[str, Any] = {}
                    if method in ("POST", "PUT", "PATCH"):
                        payload = self.read_json() or {}
                    qmap = urllib.parse.parse_qs(query or "")
                    return lq_quick_estate.handle_api(
                        db, method, parts[1:], qmap, payload, user, self.send_json
                    )
                if parts[0] == "auto-trading":
                    if parts[1:2] == ["showroom"] and method == "GET":
                        # Public feed for the customer page — no session required.
                        return self.send_json({
                            "ok": True,
                            "vehicles": lq_auto_trading.public_showroom(db),
                            "company": lq_auto_trading.public_company_card(),
                        })
                    user = self.require_user(db, "dashboard")
                    if not user:
                        return None
                    payload = {}
                    if method in ("POST", "PUT", "PATCH", "DELETE"):
                        payload = self.read_json() or {}
                    qmap = urllib.parse.parse_qs(query or "")
                    return lq_auto_trading.handle_api(
                        db, method, parts[1:], qmap, payload, user, self.send_json
                    )
                if parts[0] == "health" and method == "GET":
                    return self.send_json({
                        "ok": True,
                        "status": "healthy",
                        "service": "najjar",
                        "erp_published": ERP_PUBLISHED,
                        "najjar_published": NAJJAR_PUBLISHED,
                        "najjar_base": NAJJAR_BASE,
                        "version": APP_VERSION,
                        "release_channel": RELEASE_CHANNEL,
                        "stable": STABLE_RELEASE,
                        "stable_tag": STABLE_TAG,
                        "edition": APP_EDITION,
                        "base_edition": APP_BASE_EDITION,
                        "edition_label": APP_EDITION_LABEL,
                        "env_mode": APP_ENV_MODE,
                        "env_label_ar": APP_ENV_LABEL_AR,
                        "base_name_ar": "التطوير المؤسسي",
                        "database": str(DB_PATH),
                        "database_engine": "sqlite",
                        "postgres_url_configured": bool(LQ_DATABASE_URL),
                        "postgres_driver": lq_postgres.psycopg_available(),
                        "postgres_import_error": lq_postgres.psycopg_import_error(),
                        "postgres_probe_ok": None,
                        "postgres_note": "SQLite production primary — Postgres shadow optional via DATABASE_URL",
                        "platform_ready": True,
                        "offsite": offsite_config(),
                        "auto_backup": {
                            "enabled": AUTO_BACKUP_ENABLED,
                            "interval_hours": BACKUP_INTERVAL_HOURS,
                            "retention": BACKUP_RETENTION,
                            "directory": str(BACKUP_DIR),
                            "last_backup": LAST_AUTO_BACKUP_AT or (list_automatic_backups()[0]["created_at"] if list_automatic_backups() else None),
                        },
                        "storage": storage_status(),
                        "object_storage": lq_object_storage.object_storage_status(),
                        "backup_integrity": latest_backup_integrity(),
                        "security": {
                            "mfa_mode": mfa_enforce_mode(),
                            "totp_ready": True,
                            "smtp_configured": smtp_configured(),
                        },
                    })
                if parts[0] == "openapi.json" and method == "GET":
                    spec = build_openapi_spec(PRODUCTION_URL, APP_VERSION)
                    return self.send_json({"ok": True, "openapi": spec})
                if parts[0] == "audit_feed" and method == "GET":
                    user = self.require_user(db, "audit:read")
                    return None if not user else self.api_audit_feed(db, user, query)
                if parts[0] == "owner" and len(parts) >= 2 and parts[1] == "staff_activity" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_owner_staff_activity(db, user, query)
                if parts[0] == "owner" and len(parts) >= 2 and parts[1] == "live_hub" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_owner_live_hub(db, user, query)
                if parts[0] == "enterprise_status" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_enterprise_status(db, user)
                if parts[0] == "platform_readiness" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_platform_readiness(db)
                if parts[0] == "business_catalog" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_business_catalog(db)
                if parts[0] == "business_catalog" and len(parts) >= 2 and parts[1] == "office_fee" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_business_office_fee()
                if parts[0] == "business_catalog" and len(parts) >= 2 and parts[1] == "hospitality_quote" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_business_hospitality_quote()
                if parts[0] == "business_catalog" and len(parts) >= 2 and parts[1] == "condolence_quote" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_business_condolence_quote()
                if parts[0] == "hospitality" and len(parts) >= 2 and parts[1] == "event_book" and method == "POST":
                    user = self.require_user(db, "hospitality_events")
                    return None if not user else self.api_hospitality_event_book(db, user)
                if parts[0] == "documents" and len(parts) >= 2 and parts[1] == "lease_cancel" and method == "POST":
                    user = self.require_user(db, "contracts:read")
                    return None if not user else self.api_lease_cancel_template(db, user)
                if parts[0] == "database" and len(parts) >= 2 and parts[1] == "status" and method == "GET":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_database_status(db, user)
                if parts[0] == "database" and len(parts) >= 2 and parts[1] == "postgres_probe" and method == "GET":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_database_postgres_probe(db, user)
                if parts[0] == "database" and len(parts) >= 2 and parts[1] == "migrate_preview" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_database_migrate_preview(db, user)
                if parts[0] == "database" and len(parts) >= 2 and parts[1] == "migrate_shadow" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_database_migrate_shadow(db, user)
                if parts[0] == "database" and len(parts) >= 2 and parts[1] == "verify_shadow" and method == "GET":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_database_verify_shadow(db, user)
                if parts[0] == "storage" and len(parts) >= 2 and parts[1] == "object_status" and method == "GET":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_storage_object_status(db, user)
                if parts[0] == "storage" and len(parts) >= 2 and parts[1] == "object_probe" and method == "GET":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_storage_object_probe(db, user)
                if parts[0] == "storage" and len(parts) >= 2 and parts[1] == "sync_uploads" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_storage_sync_uploads(db, user)
                if parts[0] == "login_preview" and method == "GET":
                    dash = build_dashboard(db)
                    k = dash.get("kpis") or {}
                    collection = round((float(k.get("paid") or 0) / float(k.get("billed") or 1)) * 100) if k.get("billed") else 0
                    return self.send_json({
                        "ok": True,
                        "preview": {
                            "revenue": k.get("income", 0),
                            "profit": k.get("net", 0),
                            "occupancy": k.get("occupancy", 0),
                            "assets": k.get("properties", 0),
                            "health": k.get("health", 0),
                            "overdue": k.get("overdue", 0),
                            "expiring": k.get("expiring", 0),
                            "collection_rate": collection,
                            "series": dash.get("series") or [],
                            "decisions": (dash.get("decisions") or [])[:4],
                        },
                    })
                if parts[0] == "login" and len(parts) >= 2 and parts[1] == "otp" and method == "POST":
                    return self.api_login_otp(db)
                if parts[0] == "security" and len(parts) >= 2 and parts[1] == "status" and method == "GET":
                    user = self.require_user(db)
                    return None if not user else self.api_security_status(db, user)
                if parts[0] == "security" and len(parts) >= 2 and parts[1] == "devices" and method == "GET":
                    user = self.require_user(db)
                    return None if not user else self.api_trusted_devices(db, user)
                if parts[0] == "security" and len(parts) >= 2 and parts[1] == "devices" and method == "POST":
                    user = self.require_user(db)
                    return None if not user else self.api_revoke_trusted_device(db, user)
                if parts[0] == "security" and len(parts) >= 2 and parts[1] == "totp_setup" and method == "POST":
                    user = self.require_user(db)
                    return None if not user else self.api_totp_setup(db, user)
                if parts[0] == "security" and len(parts) >= 2 and parts[1] == "totp_confirm" and method == "POST":
                    user = self.require_user(db)
                    return None if not user else self.api_totp_confirm(db, user)
                if parts[0] == "security" and len(parts) >= 2 and parts[1] == "totp_disable" and method == "POST":
                    user = self.require_user(db)
                    return None if not user else self.api_totp_disable(db, user)
                if parts[0] == "login" and method == "POST":
                    return self.api_login(db)
                if parts[0] == "biometric" and len(parts) >= 3 and parts[1] == "register" and parts[2] == "options" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_biometric_register_options(db, user)
                if parts[0] == "biometric" and len(parts) >= 3 and parts[1] == "register" and parts[2] == "finish" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_biometric_register_finish(db, user)
                if parts[0] == "biometric" and len(parts) >= 3 and parts[1] == "auth" and parts[2] == "options" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_biometric_auth_options(db, user)
                if parts[0] == "biometric" and len(parts) >= 3 and parts[1] == "auth" and parts[2] == "finish" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_biometric_auth_finish(db, user)
                if parts[0] == "biometric" and len(parts) >= 2 and parts[1] == "status" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_biometric_status(db, user)
                if parts[0] == "biometric" and len(parts) >= 2 and parts[1] == "clear" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_biometric_clear(db, user)
                if parts[0] == "logout" and method == "POST":
                    return self.api_logout(db)
                if parts[0] == "change_password" and method == "POST":
                    user = self.require_user(db)
                    return None if not user else self.api_change_password(db, user)
                if parts[0] == "me" and method == "GET":
                    user = self.require_user(db, query=query)
                    if not user:
                        return None
                    role = str(user.get("role") or "viewer").lower()
                    sections = sorted(NAJJAR_SECTION_ACCESS.get(role) or NAJJAR_SECTION_ACCESS["viewer"])
                    if str(user.get("username") or "").lower() in FULL_ACCESS_USERNAMES:
                        sections = sorted(NAJJAR_SECTION_ACCESS["owner"])
                    perms = ROLE_PERMISSIONS.get(role, set())
                    return self.send_json({
                        "ok": True,
                        "user": user,
                        "permissions": sorted(perms) if perms != {"all"} else ["all"],
                        "najjar_sections": sections,
                        "role_label_ar": ROLE_LABELS_AR.get(role, role),
                        "version": APP_VERSION,
                        "base_edition": APP_BASE_EDITION,
                        "edition_label": APP_EDITION_LABEL,
                        "env_mode": APP_ENV_MODE,
                        "env_label_ar": APP_ENV_LABEL_AR,
                    })
                if parts[0] == "dashboard" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_dashboard(db)
                if parts[0] == "bootstrap" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_bootstrap(db, user)
                if parts[0] == "invoice_from_contract" and method == "POST":
                    user = self.require_user(db, "invoices")
                    return None if not user else self.api_invoice_from_contract(db, user)
                if parts[0] == "manual_invoice" and method == "POST":
                    user = self.require_user(db, "invoices")
                    return None if not user else self.api_manual_invoice(db, user)
                if parts[0] == "reissue_invoice" and method == "POST":
                    user = self.require_user(db, "invoices")
                    return None if not user else self.api_reissue_invoice(db, user)
                if parts[0] == "approve_contract" and method == "POST":
                    user = self.require_user(db, "contracts")
                    return None if not user else self.api_approve_contract(db, user)
                if parts[0] == "activate_contract" and method == "POST":
                    user = self.require_user(db, "contracts")
                    return None if not user else self.api_activate_contract(db, user)
                if parts[0] == "request_approval" and method == "POST":
                    user = self.require_user(db, "approvals:request")
                    return None if not user else self.api_request_approval(db, user)
                if parts[0] == "decide_approval" and method == "POST":
                    user = self.require_user(db, "approvals")
                    return None if not user else self.api_decide_approval(db, user)
                if parts[0] == "renew_contract" and method == "POST":
                    user = self.require_user(db, "contracts")
                    return None if not user else self.api_renew_contract(db, user)
                if parts[0] == "end_contract" and method == "POST":
                    user = self.require_user(db, "contracts")
                    return None if not user else self.api_end_contract(db, user)
                if parts[0] == "contract_template" and method == "POST":
                    user = self.require_user(db, "contracts:read")
                    return None if not user else self.api_contract_template(db, user)
                if parts[0] == "pay_invoice" and method == "POST":
                    user = self.require_user(db, "invoices")
                    return None if not user else self.api_pay_invoice(db, user)
                if parts[0] == "void_invoice" and method == "POST":
                    user = self.require_user(db, "invoices")
                    return None if not user else self.api_void_invoice(db, user)
                if parts[0] == "invoice_audit" and method == "GET":
                    user = self.require_user(db, "invoices:read")
                    return None if not user else self.api_invoice_audit(db, user, query)
                if parts[0] == "tenant_statement" and method == "GET":
                    user = self.require_user(db, "invoices:read")
                    return None if not user else self.api_tenant_statement(db, user, query)
                if parts[0] == "accountant_reports" and method == "GET":
                    user = self.require_user(db, "reports:read")
                    return None if not user else self.api_accountant_reports(db, query)
                if parts[0] == "receivables" and len(parts) >= 2 and parts[1] == "aging" and method == "GET":
                    user = self.require_user(db, "invoices:read")
                    return None if not user else self.api_receivables_aging(db, user, query)
                if parts[0] == "receivables" and len(parts) >= 2 and parts[1] == "reminders" and method == "GET":
                    user = self.require_user(db, "invoices:read")
                    return None if not user else self.api_receivables_reminders(db, user, query)
                if parts[0] == "receivables" and len(parts) >= 2 and parts[1] == "reminders" and method == "POST":
                    user = self.require_user(db, "invoices")
                    return None if not user else self.api_receivables_send_reminders(db, user)
                if parts[0] == "accounting_platform_overview" and method == "GET":
                    user = self.require_user(db, "accounts:read")
                    return None if not user else self.api_accounting_platform_overview(db, query)
                if parts[0] == "accounting_cfo_overview" and method == "GET":
                    user = self.require_user(db, "accounts:read")
                    return None if not user else self.api_accounting_cfo_overview(db, query)
                if parts[0] == "financial_statements" and method == "GET":
                    user = self.require_user(db, "accounts:read")
                    return None if not user else self.api_financial_statements(db)
                if parts[0] == "accounts_insights" and method == "GET":
                    user = self.require_user(db, "accounts:read")
                    return None if not user else self.api_accounts_insights(db, query)
                if parts[0] == "hospitality_summary" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_hospitality_summary(db, query)
                if parts[0] == "bank_reconciliation_preview" and method == "GET":
                    user = self.require_user(db, "bank_reconciliations:read")
                    return None if not user else self.api_bank_reconciliation_preview(db, query)
                if parts[0] == "auto_match_bank" and method == "POST":
                    user = self.require_user(db, "bank_reconciliations")
                    return None if not user else self.api_auto_match_bank(db, user)
                if parts[0] == "close_financial_period" and method == "POST":
                    user = self.require_user(db, "financial_periods")
                    return None if not user else self.api_close_financial_period(db, user)
                if parts[0] == "bank_reconciliation_alerts" and method == "GET":
                    user = self.require_user(db, "bank_reconciliations:read")
                    return None if not user else self.api_bank_reconciliation_alerts(db)
                if parts[0] == "staff" and len(parts) >= 2 and parts[1] == "manifest" and method == "GET":
                    return self.api_staff_manifest()
                if parts[0] == "staff" and len(parts) >= 2 and parts[1] == "sync" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_staff_sync(db, user)
                if parts[0] == "staff" and len(parts) >= 2 and parts[1] == "push_register" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_staff_push_register(db, user)
                if parts[0] == "staff" and len(parts) >= 2 and parts[1] == "maintenance_update" and method == "POST":
                    user = self.require_user(db, "maintenance")
                    return None if not user else self.api_staff_maintenance_update(db, user)
                if parts[0] == "staff" and len(parts) >= 2 and parts[1] == "quick_maintenance" and method == "POST":
                    user = self.require_user(db, "maintenance")
                    return None if not user else self.api_staff_quick_maintenance(db, user)
                if parts[0] == "alert_center" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_alert_center(db, user)
                if parts[0] == "role_board" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_role_board(db, user)
                if parts[0] == "payroll" and len(parts) >= 3 and parts[1] == "import" and parts[2] == "preview" and method == "POST":
                    user = self.require_user(db, "salaries")
                    return None if not user else self.api_payroll_import_preview(db, user)
                if parts[0] == "payroll" and len(parts) >= 3 and parts[1] == "import" and parts[2] == "commit" and method == "POST":
                    user = self.require_user(db, "salaries")
                    return None if not user else self.api_payroll_import_commit(db, user)
                if parts[0] == "payroll" and len(parts) >= 2 and parts[1] == "import_batches" and method == "GET":
                    user = self.require_user(db, "salaries:read")
                    return None if not user else self.api_payroll_import_batches(db, user, query)
                if parts[0] == "payroll" and len(parts) >= 2 and parts[1] == "attendance_summary" and method == "GET":
                    user = self.require_user(db, "salaries:read")
                    return None if not user else self.api_payroll_attendance_summary(db, user, query)
                if parts[0] == "alert_dismiss" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_alert_dismiss(db, user)
                if parts[0] == "alert_notify" and method == "POST":
                    user = self.require_user(db, "reports:read")
                    return None if not user else self.api_alert_notify(db, user)
                if parts[0] == "production_status" and method == "GET":
                    user = self.require_user(db, "reports:read")
                    return None if not user else self.api_production_status(db)
                if parts[0] == "workflow_policies" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_workflow_policies(db, user)
                if parts[0] == "workflow_policies" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_update_workflow_policies(db, user)
                if parts[0] == "backup" and len(parts) >= 2 and parts[1] == "status" and method == "GET":
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_backup_status()
                if parts[0] == "backup" and len(parts) >= 2 and parts[1] == "archive" and method == "GET":
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_backup_archive(db)
                if parts[0] == "backup" and len(parts) >= 2 and parts[1] == "verify" and method == "GET":
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_backup_verify(db)
                if parts[0] == "backup" and len(parts) >= 2 and parts[1] == "download" and method == "GET":
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_backup_download(query)
                if parts[0] == "backup" and len(parts) >= 2 and parts[1] == "run" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_backup_run(db, user)
                if parts[0] == "backup" and method == "GET":
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_backup(db)
                if parts[0] == "restore" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_restore(db, user)
                if parts[0] == "admin" and len(parts) >= 2 and parts[1] == "reset_operational" and method == "POST":
                    user = self.require_user(db)
                    return None if not user else self.api_admin_reset_operational(db, user)
                if parts[0] == "export" and len(parts) >= 2 and parts[1] == "bundle" and method == "POST":
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_export_bundle_zip(user)
                if parts[0] == "export" and len(parts) >= 2 and parts[1] == "timeline_audit" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_export_timeline_audit_csv(db, user, query)
                if parts[0] == "export" and len(parts) >= 2 and parts[1] == "module_fix_history" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_export_module_fix_history_csv(db, user, query)
                if parts[0] == "export" and method == "GET" and len(parts) >= 2:
                    user = self.require_user(db, "backup:export")
                    return None if not user else self.api_export_csv(db, parts[1])
                if parts[0] == "operations_check" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_operations_check(db, user)
                if parts[0] == "module_integrity" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_module_integrity(db)
                if parts[0] == "module_integrity_history" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_module_integrity_history(db, user, query)
                if parts[0] == "module_integrity_history_kpi" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_module_integrity_history_kpi(db, user, query)
                if parts[0] == "module_integrity_fix" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_module_integrity_fix(db, user)
                if parts[0] == "module_integrity_autorun" and method == "POST":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_module_integrity_autorun(db, user)
                if parts[0] == "operational_intel" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_operational_intel(db, user)
                if parts[0] == "ai" and len(parts) >= 2 and parts[1] == "usage" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_ai_usage(db, user)
                if parts[0] == "ai" and len(parts) >= 2 and parts[1] == "brief" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_ai_brief(db, user)
                if parts[0] == "ai" and len(parts) >= 2 and parts[1] == "ask" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_ai_ask(db, user)
                if parts[0] == "ai" and len(parts) >= 2 and parts[1] == "ask_preview" and method == "POST":
                    return self.api_ai_ask_preview(db)
                if parts[0] == "events" and len(parts) >= 2 and parts[1] == "stream" and method == "GET":
                    return self.api_events_stream(db, query)
                if parts[0] == "otp" and len(parts) >= 2 and parts[1] == "send" and method == "POST":
                    return self.api_otp_send(db)
                if parts[0] == "otp" and len(parts) >= 2 and parts[1] == "verify" and method == "POST":
                    return self.api_otp_verify()
                if parts[0] == "report" and len(parts) >= 2 and parts[1] == "executive" and method == "GET":
                    user = self.require_user(db, "reports:read", query)
                    return None if not user else self.api_report_executive(db, user)
                if parts[0] == "report" and len(parts) >= 2 and parts[1] == "accountant" and method == "GET":
                    user = self.require_user(db, "reports:read", query)
                    return None if not user else self.api_report_accountant(db, user, query)
                if parts[0] == "report" and len(parts) >= 2 and parts[1] == "bank_reconciliation" and method == "GET":
                    user = self.require_user(db, "bank_reconciliations:read", query)
                    return None if not user else self.api_report_bank_reconciliation(db, user, query)
                if parts[0] == "report" and len(parts) >= 2 and parts[1] == "hospitality" and method == "GET":
                    user = self.require_user(db, "reports:read", query)
                    return None if not user else self.api_report_hospitality(db, user, query)
                if parts[0] == "permissions" and len(parts) >= 2 and parts[1] == "ui" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_permissions_ui(user)
                if parts[0] == "permissions" and len(parts) >= 2 and parts[1] == "audit" and method == "GET":
                    user = self.require_user(db, "admin")
                    return None if not user else self.api_permissions_audit(db, user)
                if (
                    parts[0] == "work_journal"
                    and method == "GET"
                    and len(parts) >= 2
                    and parts[1] == "today"
                ):
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_work_journal_list(db, user, today())
                if parts[0] == "daily_operations" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_daily_operations_list(db, user, query)
                if parts[0] == "daily_operations" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_daily_operations_create(db, user)
                if parts[0] == "work_journal" and method == "GET":
                    user = self.require_user(db, "dashboard")
                    if not user:
                        return None
                    params = urllib.parse.parse_qs(query or "")
                    work_date = (params.get("date") or [today()])[0].strip() or today()
                    return self.api_work_journal_list(db, user, work_date)
                if parts[0] == "work_journal" and method == "POST":
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_work_journal_create(db, user)
                if parts[0] == "work_journal" and method == "DELETE" and len(parts) >= 2:
                    user = self.require_user(db, "dashboard")
                    return None if not user else self.api_work_journal_delete(db, user, parts[1])
                if (
                    parts[0] == "properties"
                    and len(parts) >= 3
                    and parts[2] == "photo"
                    and method == "POST"
                ):
                    user = self.require_user(db, "properties")
                    return None if not user else self.api_property_photo(db, user, parts[1])
                if parts[0] == "estate_convert_reservation" and method == "POST":
                    user = self.require_user(db, "estate_actions_convert")
                    return None if not user else self.api_estate_convert_reservation(db, user)
                if parts[0] == "estate_convert_to_contract" and method == "POST":
                    user = self.require_user(db, "estate_actions_contract_create")
                    return None if not user else self.api_estate_convert_to_contract(db, user)
                if parts[0] == "estate_contract_request_approval" and method == "POST":
                    user = self.require_user(db, "approvals:request")
                    return None if not user else self.api_estate_contract_request_approval(db, user)
                if parts[0] == "estate_contract_approve" and method == "POST":
                    user = self.require_user(db, "approvals")
                    return None if not user else self.api_estate_contract_approve(db, user)
                if parts[0] == "estate_contract_activate" and method == "POST":
                    user = self.require_user(db, "estate_actions_contract_create")
                    return None if not user else self.api_estate_contract_activate(db, user)
                if parts[0] == "estate_contract_generate_schedule" and method == "POST":
                    user = self.require_user(db, "estate_actions_contract_create")
                    return None if not user else self.api_estate_contract_generate_schedule(db, user)
                if parts[0] == "estate_contract_pay_invoice" and method == "POST":
                    user = self.require_user(db, "estate_apartments")
                    return None if not user else self.api_estate_contract_pay_invoice(db, user)
                if parts[0] == "estate_contract_close" and method == "POST":
                    user = self.require_user(db, "estate_actions_contract_close")
                    return None if not user else self.api_estate_contract_close(db, user)
                if parts[0] == "estate_month_close" and method == "POST":
                    user = self.require_user(db, "estate_actions_month_close")
                    return None if not user else self.api_estate_month_close(db, user)
                if parts[0] == "estate_operations_check" and method == "GET":
                    user = self.require_user(db, "estate_apartments:read")
                    return None if not user else self.api_estate_operations_check(db, user)
                if parts[0] == "estate_copy_from_nizwa" and method == "POST":
                    user = self.require_user(db, "estate_properties")
                    if not user:
                        return None
                    if str(user.get("role") or "").lower() not in ("owner", "admin"):
                        return self.send_json({"ok": False, "error": "نسخ بيانات نزوى متاح للمالك/الإدارة فقط"}, 403)
                    return self.api_estate_copy_from_nizwa(db, user)
                if parts[0] in TABLES:
                    return self.api_crud(db, method, parts, query)
                self.send_json({"ok": False, "error": "Unknown endpoint"}, 404)
        except sqlite3.IntegrityError as exc:
            self.send_json({"ok": False, "error": "Database integrity error", "detail": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"ok": False, "error": "Server error", "detail": str(exc)}, 500)

    def cleanup_pending_logins(self, db: Optional[sqlite3.Connection] = None) -> None:
        now_ts = time.time()
        expired = [k for k, v in PENDING_LOGINS.items() if now_ts > float(v.get("expires_ts", 0))]
        for key in expired:
            PENDING_LOGINS.pop(key, None)
        if db is None:
            return
        ensure_security_runtime_tables(db)
        db.execute("DELETE FROM security_pending_logins WHERE expires_ts < ?", (now_ts,))
        db.execute("DELETE FROM security_otp_codes WHERE exp < ?", (now_ts,))

    def is_device_trusted(self, db: sqlite3.Connection, user_id: str, fingerprint: str) -> bool:
        if not fingerprint:
            return False
        row = db.execute(
            """
            SELECT id, trusted_until FROM trusted_devices
            WHERE user_id=? AND device_fingerprint=? AND active=1
            ORDER BY last_seen_at DESC LIMIT 1
            """,
            (user_id, fingerprint),
        ).fetchone()
        if not row:
            return False
        until = str(row["trusted_until"] or "")
        try:
            if datetime.fromisoformat(until) < datetime.now():
                db.execute("UPDATE trusted_devices SET active=0 WHERE id=?", (row["id"],))
                return False
        except ValueError:
            return False
        db.execute(
            "UPDATE trusted_devices SET last_seen_at=? WHERE id=?",
            (now_iso(), row["id"]),
        )
        return True

    def trust_device(
        self,
        db: sqlite3.Connection,
        user_id: str,
        fingerprint: str,
        *,
        label: str = "",
        user_agent: str = "",
    ) -> Optional[str]:
        if not fingerprint:
            return None
        until = (datetime.now() + timedelta(days=device_trust_days())).isoformat(sep=" ")
        existing = db.execute(
            "SELECT id FROM trusted_devices WHERE user_id=? AND device_fingerprint=?",
            (user_id, fingerprint),
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE trusted_devices
                SET active=1, last_seen_at=?, trusted_until=?, device_label=COALESCE(NULLIF(?,''), device_label),
                    user_agent=COALESCE(NULLIF(?,''), user_agent)
                WHERE id=?
                """,
                (now_iso(), until, label, user_agent, existing["id"]),
            )
            return str(existing["id"])
        device_id = uid("DEV")
        insert(
            db,
            "trusted_devices",
            {
                "id": device_id,
                "user_id": user_id,
                "device_fingerprint": fingerprint,
                "device_label": label or "جهاز موثوق",
                "user_agent": user_agent[:240],
                "created_at": now_iso(),
                "last_seen_at": now_iso(),
                "trusted_until": until,
                "active": 1,
            },
        )
        return device_id

    def apply_password_rotation(self, db: sqlite3.Connection, row: sqlite3.Row) -> sqlite3.Row:
        # Easy team passwords (1–5) must keep working — do not force rotation.
        uname = str(row["username"] if "username" in row.keys() else "").strip().lower()
        if uname in NAJJAR_TEAM_USERNAMES:
            return row
        if password_needs_rotation(row["password_changed_at"] if "password_changed_at" in row.keys() else None, created_at=row["created_at"] if "created_at" in row.keys() else None):
            if not bool(row["must_change_password"] if "must_change_password" in row.keys() else 0):
                db.execute("UPDATE users SET must_change_password=1 WHERE id=?", (row["id"],))
                db.commit()
                refreshed = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
                return refreshed or row
        return row

    def issue_session(
        self,
        db: sqlite3.Connection,
        row: sqlite3.Row,
        via: str = "password",
        remember: bool = False,
        *,
        device_fingerprint: str = "",
        device_label: str = "",
        user_agent: str = "",
    ) -> None:
        row = self.apply_password_rotation(db, row)
        token = secrets.token_urlsafe(32)
        session_hours = 30 * 24 if remember else 12
        expires = (datetime.now() + timedelta(hours=session_hours)).isoformat()
        db.execute("INSERT INTO sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)", (token, row["id"], now_iso(), expires))
        db.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), row["id"]))
        trusted = False
        if remember and device_fingerprint:
            self.trust_device(db, row["id"], device_fingerprint, label=device_label, user_agent=user_agent)
            trusted = True
        elif device_fingerprint:
            trusted = self.is_device_trusted(db, row["id"], device_fingerprint)
        audit(db, dict(row), "login", "users", row["id"], f"User login ({via})")
        db.commit()
        user = dict(row)
        user.pop("password_hash", None)
        user["must_change_password"] = bool(user.get("must_change_password"))
        user["security"] = security_status_payload(
            user,
            trusted_device=trusted,
            totp_enabled=bool(user.get("totp_enabled")),
        )
        max_age = session_hours * 3600
        # Keep cookie in sync with bearer token so portal → app navigation stays authenticated
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={urllib.parse.quote(token)}; Path=/; Max-Age={max_age}; SameSite=Lax",
        )
        self.send_header("Set-Cookie", f"{LEGACY_SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax")
        self.send_cors_headers()
        payload = {
            "ok": True,
            "token": token,
            "user": user,
            "expires_at": expires,
            "must_change_password": user["must_change_password"],
            "security": user["security"],
        }
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def begin_mfa_challenge(
        self,
        db: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        remember: bool,
        device_fingerprint: str,
        device_label: str,
        user_agent: str,
    ) -> Dict[str, Any]:
        self.cleanup_pending_logins(db)
        challenge_id = uid("MFA")
        username = str(row["username"])
        keys = row.keys()
        totp_enabled = bool(row["totp_enabled"] if "totp_enabled" in keys else 0)
        totp_secret = str(row["totp_secret"] if "totp_secret" in keys else "") or ""
        method = "email"
        enroll_secret = ""
        enroll_uri = ""
        code = ""
        sent = False
        detail = ""

        if totp_enabled and totp_secret:
            method = "totp"
            sent = True
            detail = "أدخل رمز تطبيق المصادقة"
            store_pending_login(
                db,
                challenge_id,
                {
                    "user_id": row["id"],
                    "username": username,
                    "remember": remember,
                    "device_fingerprint": device_fingerprint,
                    "device_label": device_label,
                    "user_agent": user_agent,
                    "expires_ts": time.time() + pending_login_ttl_seconds(),
                    "method": method,
                    "totp_secret": "",
                },
            )
            return {
                "challenge_id": challenge_id,
                "sent": True,
                "detail": detail,
                "username": username,
                "mfa_method": method,
                "message": "أدخل رمز تطبيق المصادقة (Google Authenticator / Authy)",
            }

        to_addr = resolve_user_email(username, str(row["email"] or "").strip())
        if to_addr and smtp_configured():
            method = "email"
            code = f"{secrets.randbelow(900000) + 100000:06d}"
            store_otp_code(db, username, code, purpose="mfa")
            store_pending_login(
                db,
                challenge_id,
                {
                    "user_id": row["id"],
                    "username": username,
                    "remember": remember,
                    "device_fingerprint": device_fingerprint,
                    "device_label": device_label,
                    "user_agent": user_agent,
                    "expires_ts": time.time() + pending_login_ttl_seconds(),
                    "method": method,
                    "totp_secret": "",
                },
            )
            subject = f"{COMPANY_NAME} — رمز التحقق MFA"
            body = (
                f"رمز التحقق لحساب {username}: {code}\n"
                f"صالح لمدة {OTP_TTL_SECONDS // 60} دقائق.\n"
                "إذا لم تطلب هذا الرمز تجاهل الرسالة."
            )
            sent, detail = send_alert_email(to_addr, subject, body)
            if not sent and os.environ.get("LQ_OTP_DEBUG") == "1":
                sys.stderr.write(f"[LQ MFA debug] {username}: {code} ({detail})\n")
                sent = True
                detail = "OTP logged (debug mode)"
            return {
                "challenge_id": challenge_id,
                "sent": sent,
                "detail": detail,
                "username": username,
                "mfa_method": method,
                "message": "أدخل رمز OTP من البريد لإكمال الدخول الآمن",
            }

        # No SMTP: enroll TOTP on the spot (completes MFA without email).
        method = "totp_enroll"
        enroll_secret = generate_totp_secret()
        enroll_uri = totp_provisioning_uri(enroll_secret, username)
        store_pending_login(
            db,
            challenge_id,
            {
                "user_id": row["id"],
                "username": username,
                "remember": remember,
                "device_fingerprint": device_fingerprint,
                "device_label": device_label,
                "user_agent": user_agent,
                "expires_ts": time.time() + pending_login_ttl_seconds(),
                "method": method,
                "totp_secret": enroll_secret,
            },
        )
        return {
            "challenge_id": challenge_id,
            "sent": True,
            "detail": "فعّل تطبيق المصادقة ثم أدخل الرمز",
            "username": username,
            "mfa_method": method,
            "totp_secret": enroll_secret,
            "totp_uri": enroll_uri,
            "message": "امسح السر في Google Authenticator ثم أدخل الرمز المكوّن من 6 أرقام",
        }

    def api_login(self, db: sqlite3.Connection) -> None:
        data = self.read_json()
        username = str(data.get("username", "")).strip().lower()
        password = str(data.get("password", ""))
        remember = bool(data.get("remember_device"))
        fingerprint = normalize_device_fingerprint(data.get("device_fingerprint") or data.get("device_id"))
        device_label = str(data.get("device_label") or "").strip()[:80]
        user_agent = str(self.headers.get("User-Agent") or "")[:240]
        row = db.execute("SELECT * FROM users WHERE lower(username)=? AND active=1", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return self.send_json({"ok": False, "error": "Invalid username or password"}, 401)
        trusted = self.is_device_trusted(db, row["id"], fingerprint) if fingerprint else False
        if role_requires_mfa(str(row["role"])) and not trusted:
            challenge = self.begin_mfa_challenge(
                db,
                row,
                remember=remember,
                device_fingerprint=fingerprint,
                device_label=device_label,
                user_agent=user_agent,
            )
            if challenge["sent"]:
                audit(db, dict(row), "mfa_challenge", "users", row["id"], f"MFA required ({challenge.get('mfa_method')})")
                db.commit()
                payload = {
                    "ok": True,
                    "mfa_required": True,
                    "challenge_id": challenge["challenge_id"],
                    "username": challenge["username"],
                    "mfa_method": challenge.get("mfa_method") or "email",
                    "message": challenge.get("message") or "أدخل رمز OTP لإكمال الدخول الآمن",
                    "expires_in": OTP_TTL_SECONDS,
                }
                if challenge.get("totp_secret"):
                    payload["totp_secret"] = challenge["totp_secret"]
                    payload["totp_uri"] = challenge.get("totp_uri")
                return self.send_json(payload)
            if mfa_enforce_mode() == "strict":
                return self.send_json(
                    {
                        "ok": False,
                        "error": "تعذر إرسال رمز MFA — فعّل البريد أو LQ_OTP_DEBUG",
                        "detail": challenge.get("detail"),
                    },
                    503,
                )
            # soft mode: continue login when delivery fails
            audit(db, dict(row), "mfa_bypass_soft", "users", row["id"], str(challenge.get("detail") or ""))
            db.commit()
        self.issue_session(
            db,
            row,
            via="password",
            remember=remember,
            device_fingerprint=fingerprint,
            device_label=device_label,
            user_agent=user_agent,
        )

    def api_login_otp(self, db: sqlite3.Connection) -> None:
        data = self.read_json()
        username = str(data.get("username", "")).strip()
        code = str(data.get("code", "")).strip()
        challenge_id = str(data.get("challenge_id") or "").strip()
        remember = bool(data.get("remember_device"))
        fingerprint = normalize_device_fingerprint(data.get("device_fingerprint") or data.get("device_id"))
        device_label = str(data.get("device_label") or "").strip()[:80]
        user_agent = str(self.headers.get("User-Agent") or "")[:240]
        # Passwordless OTP login is opt-in; MFA completion always allowed with challenge_id.
        if not challenge_id and not otp_login_enabled():
            return self.send_json(
                {
                    "ok": False,
                    "error": "دخول OTP بدون كلمة مرور معطّل — استخدم كلمة المرور أو فعّل LQ_OTP_LOGIN_ENABLED",
                },
                403,
            )

        pending = None
        method = "email"
        if challenge_id:
            self.cleanup_pending_logins(db)
            pending = load_pending_login(db, challenge_id)
            if not pending:
                return self.send_json({"ok": False, "error": "انتهت صلاحية التحقق — أعد تسجيل الدخول"}, 401)
            if str(pending.get("username")) != username and username.lower() != str(pending.get("username") or "").lower():
                return self.send_json({"ok": False, "error": "Challenge mismatch"}, 401)
            username = str(pending.get("username") or username)
            method = str(pending.get("method") or "email")
            remember = bool(pending.get("remember"))
            fingerprint = pending.get("device_fingerprint") or fingerprint
            device_label = pending.get("device_label") or device_label
            user_agent = pending.get("user_agent") or user_agent

        row = db.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if not row and username:
            row = db.execute("SELECT * FROM users WHERE lower(username)=? AND active=1", (username.lower(),)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "User not found"}, 404)

        keys = row.keys()
        if method in ("totp", "totp_enroll"):
            secret = ""
            if method == "totp_enroll":
                secret = str((pending or {}).get("totp_secret") or "")
            else:
                secret = str(row["totp_secret"] if "totp_secret" in keys else "") or ""
            if not verify_totp(secret, code):
                return self.send_json({"ok": False, "error": "رمز تطبيق المصادقة غير صحيح"}, 401)
            if method == "totp_enroll" and secret:
                db.execute(
                    "UPDATE users SET totp_secret=?, totp_enabled=1 WHERE id=?",
                    (secret, row["id"]),
                )
                db.commit()
                row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone() or row
            if challenge_id:
                clear_pending_login(db, challenge_id)
        else:
            stored = load_otp_code(db, username)
            if not stored or time.time() > stored[1] or stored[0] != code:
                return self.send_json({"ok": False, "error": "Invalid or expired OTP code"}, 401)
            clear_otp_code(db, username)
            if challenge_id:
                clear_pending_login(db, challenge_id)

        # Completing MFA always trusts the current device when fingerprint present.
        if fingerprint:
            remember = True
        self.issue_session(
            db,
            row,
            via="otp" if not challenge_id else f"mfa:{method}",
            remember=remember,
            device_fingerprint=fingerprint,
            device_label=device_label or "جهاز بعد MFA",
            user_agent=user_agent,
        )

    def api_trusted_devices(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        rows = rows_to_dicts(
            db.execute(
                """
                SELECT id, device_label, user_agent, created_at, last_seen_at, trusted_until, active
                FROM trusted_devices
                WHERE user_id=?
                ORDER BY last_seen_at DESC
                LIMIT 50
                """,
                (user["id"],),
            ).fetchall()
        )
        full = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        payload_user = dict(full) if full else dict(user)
        payload_user.pop("password_hash", None)
        payload_user.pop("totp_secret", None)
        fingerprint = normalize_device_fingerprint(self.headers.get("X-LQ-Device") or "")
        trusted = self.is_device_trusted(db, user["id"], fingerprint) if fingerprint else False
        self.send_json(
            {
                "ok": True,
                "devices": rows,
                "security": security_status_payload(
                    payload_user,
                    trusted_device=trusted,
                    totp_enabled=bool(payload_user.get("totp_enabled")),
                ),
            }
        )

    def api_revoke_trusted_device(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        device_id = str(data.get("device_id") or data.get("id") or "").strip()
        if not device_id:
            return self.send_json({"ok": False, "error": "device_id مطلوب"}, 400)
        row = db.execute(
            "SELECT id FROM trusted_devices WHERE id=? AND user_id=?",
            (device_id, user["id"]),
        ).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "الجهاز غير موجود"}, 404)
        db.execute("UPDATE trusted_devices SET active=0 WHERE id=?", (device_id,))
        audit(db, user, "revoke_device", "trusted_devices", device_id, "Revoked trusted device")
        db.commit()
        self.send_json({"ok": True, "revoked": device_id})

    def api_security_status(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        fingerprint = normalize_device_fingerprint(
            self.headers.get("X-LQ-Device") or ""
        )
        trusted = self.is_device_trusted(db, user["id"], fingerprint) if fingerprint else False
        db.commit()
        full = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        payload_user = dict(full) if full else dict(user)
        payload_user.pop("password_hash", None)
        payload_user.pop("totp_secret", None)
        totp_on = bool(payload_user.get("totp_enabled"))
        self.send_json(
            {
                "ok": True,
                "security": security_status_payload(
                    payload_user,
                    trusted_device=trusted,
                    totp_enabled=totp_on,
                ),
            }
        )

    def api_totp_setup(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        secret = generate_totp_secret()
        # Keep pending secret in session memory keyed by user until confirm.
        PENDING_LOGINS[f"TOTPSETUP:{user['id']}"] = {
            "totp_secret": secret,
            "expires_ts": time.time() + 600,
            "username": user.get("username"),
        }
        self.send_json(
            {
                "ok": True,
                "totp_secret": secret,
                "totp_uri": totp_provisioning_uri(secret, str(user.get("username") or "user")),
                "message": "أضف السر لتطبيق المصادقة ثم أكّد بالرمز",
            }
        )

    def api_totp_confirm(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        code = str(data.get("code") or "").strip()
        pending = PENDING_LOGINS.get(f"TOTPSETUP:{user['id']}")
        secret = str((pending or {}).get("totp_secret") or data.get("totp_secret") or "").strip()
        if not secret or not verify_totp(secret, code):
            return self.send_json({"ok": False, "error": "رمز غير صحيح — أعد المحاولة"}, 400)
        db.execute(
            "UPDATE users SET totp_secret=?, totp_enabled=1 WHERE id=?",
            (secret, user["id"]),
        )
        PENDING_LOGINS.pop(f"TOTPSETUP:{user['id']}", None)
        audit(db, user, "totp_enable", "users", user["id"], "Enabled authenticator MFA")
        db.commit()
        self.send_json({"ok": True, "totp_enabled": True})

    def api_totp_disable(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        password = str(data.get("password") or "")
        row = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return self.send_json({"ok": False, "error": "كلمة المرور مطلوبة لتعطيل TOTP"}, 401)
        db.execute("UPDATE users SET totp_secret=NULL, totp_enabled=0 WHERE id=?", (user["id"],))
        audit(db, user, "totp_disable", "users", user["id"], "Disabled authenticator MFA")
        db.commit()
        self.send_json({"ok": True, "totp_enabled": False})

    def parse_client_data(self, client_data_b64: str) -> Dict[str, Any]:
        raw = b64url_decode(client_data_b64)
        if not raw:
            raise ValueError("بيانات clientDataJSON مفقودة")
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValueError("تعذر قراءة clientDataJSON") from exc

    def api_biometric_register_options(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        if FIDO2_AVAILABLE:
            rp_id = self.request_rp_id()
            rp = PublicKeyCredentialRpEntity(id=rp_id, name=COMPANY_NAME)
            server = Fido2Server(rp)
            existing_rows = db.execute(
                "SELECT credential_data FROM biometric_credentials WHERE user_id=? AND active=1 AND credential_data IS NOT NULL",
                (user["id"],),
            ).fetchall()
            credentials: List[Any] = []
            for row in existing_rows:
                blob = str(row["credential_data"] or "").strip()
                if not blob:
                    continue
                try:
                    credentials.append(AttestedCredentialData(b64url_decode(blob)))
                except Exception:
                    continue
            user_entity = {
                "id": str(user["id"]).encode("utf-8"),
                "name": str(user.get("username") or user["id"]),
                "displayName": str(user.get("name") or user.get("username") or user["id"]),
            }
            options, server_state = server.register_begin(
                user=user_entity,
                credentials=credentials,
                user_verification="required",
                authenticator_attachment="platform",
            )
            state = store_biometric_flow_state(str(user["id"]), "register_fido2", {"rp_id": rp_id, "server_state": server_state})
            return self.send_json({"ok": True, "state": state, "publicKey": webauthn_to_jsonable(options)})
        challenge = create_biometric_challenge(str(user["id"]), "register")
        existing = db.execute(
            "SELECT credential_id FROM biometric_credentials WHERE user_id=? AND active=1",
            (user["id"],),
        ).fetchall()
        self.send_json(
            {
                "ok": True,
                "state": challenge["state"],
                "publicKey": {
                    "challenge": challenge["challenge"],
                    "rp": {"name": COMPANY_NAME, "id": self.request_rp_id()},
                    "user": {
                        "id": b64url_encode(str(user["id"]).encode("utf-8")),
                        "name": str(user.get("username") or user["id"]),
                        "displayName": str(user.get("name") or user.get("username") or user["id"]),
                    },
                    "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
                    "timeout": 60000,
                    "attestation": "none",
                    "authenticatorSelection": {"authenticatorAttachment": "platform", "userVerification": "required"},
                    "excludeCredentials": [{"type": "public-key", "id": str(row["credential_id"])} for row in existing],
                },
            }
        )

    def api_biometric_register_finish(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        state = str(data.get("state") or "").strip()
        credential = data.get("credential") or {}
        if not state or not isinstance(credential, dict):
            return self.send_json({"ok": False, "error": "بيانات التسجيل غير مكتملة"}, 400)
        if FIDO2_AVAILABLE:
            flow = consume_biometric_flow_state(state, str(user["id"]), "register_fido2")
            if flow:
                rp_id = str(flow.get("rp_id") or self.request_rp_id())
                server_state = flow.get("server_state")
                if not isinstance(server_state, dict):
                    return self.send_json({"ok": False, "error": "حالة التسجيل غير صالحة"}, 400)
                response = credential.get("response") or {}
                client_json = str(response.get("clientDataJSON") or "")
                attestation_obj = str(response.get("attestationObject") or "")
                if not client_json or not attestation_obj:
                    return self.send_json({"ok": False, "error": "بيانات WebAuthn ناقصة"}, 400)
                try:
                    rp = PublicKeyCredentialRpEntity(id=rp_id, name=COMPANY_NAME)
                    server = Fido2Server(rp)
                    client_data = CollectedClientData(b64url_decode(client_json))
                    att_obj = AttestationObject(b64url_decode(attestation_obj))
                    auth_data = server.register_complete(server_state, client_data, att_obj)
                    cred_data = auth_data.credential_data
                    credential_id = b64url_encode(cred_data.credential_id)
                    credential_blob = b64url_encode(bytes(cred_data))
                    sign_count = int(getattr(auth_data, "sign_count", 0) or 0)
                    alg = str(getattr(cred_data.public_key, "ALGORITHM", "") or "")
                except Exception as exc:
                    return self.send_json({"ok": False, "error": "فشل التحقق التشفيري للتسجيل", "detail": str(exc)}, 400)
                label = str(data.get("label") or "هذا الجهاز").strip()[:100]
                transports_payload = response.get("transports")
                transports: List[str] = []
                if isinstance(transports_payload, list):
                    transports = [str(item).strip() for item in transports_payload if str(item).strip()]
                row_id = uid("BIO")
                db.execute(
                    """
                    INSERT INTO biometric_credentials(id,user_id,credential_id,credential_data,public_key,algorithm,label,transports,sign_count,active,created_at,last_verified)
                    VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
                    ON CONFLICT(credential_id) DO UPDATE SET
                        user_id=excluded.user_id,
                        credential_data=excluded.credential_data,
                        public_key=excluded.public_key,
                        algorithm=excluded.algorithm,
                        label=excluded.label,
                        transports=excluded.transports,
                        active=1,
                        sign_count=excluded.sign_count,
                        last_verified=excluded.last_verified
                    """,
                    (
                        row_id,
                        user["id"],
                        credential_id,
                        credential_blob,
                        b64url_encode(bytes(getattr(cred_data, "public_key"))),
                        alg,
                        label or "هذا الجهاز",
                        json.dumps(transports, ensure_ascii=False),
                        sign_count,
                        now_iso(),
                        now_iso(),
                    ),
                )
                audit(db, user, "biometric_register", "users", user["id"], f"Registered biometric credential ({credential_id[:18]}...)")
                db.commit()
                return self.send_json({"ok": True, "message": "تم تسجيل البصمة المؤسسية (تحقق تشفيري كامل)"})
        expected = consume_biometric_challenge(state, str(user["id"]), "register")
        if not expected:
            return self.send_json({"ok": False, "error": "انتهت صلاحية جلسة التسجيل، أعد المحاولة"}, 400)
        response = credential.get("response") or {}
        try:
            client_data = self.parse_client_data(str(response.get("clientDataJSON") or ""))
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        if str(client_data.get("type") or "") != "webauthn.create":
            return self.send_json({"ok": False, "error": "نوع التسجيل غير صحيح"}, 400)
        if str(client_data.get("challenge") or "") != expected:
            return self.send_json({"ok": False, "error": "تحدي التسجيل غير مطابق"}, 400)
        credential_id = str(credential.get("id") or credential.get("rawId") or "").strip()
        if not credential_id:
            return self.send_json({"ok": False, "error": "معرف البصمة غير موجود"}, 400)
        label = str(data.get("label") or "هذا الجهاز").strip()[:100]
        transports_payload = response.get("transports")
        transports: List[str] = []
        if isinstance(transports_payload, list):
            transports = [str(item).strip() for item in transports_payload if str(item).strip()]
        row_id = uid("BIO")
        db.execute(
            """
            INSERT INTO biometric_credentials(id,user_id,credential_id,credential_data,public_key,algorithm,label,transports,sign_count,active,created_at,last_verified)
            VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
            ON CONFLICT(credential_id) DO UPDATE SET
                user_id=excluded.user_id,
                credential_data=excluded.credential_data,
                public_key=excluded.public_key,
                algorithm=excluded.algorithm,
                label=excluded.label,
                transports=excluded.transports,
                active=1,
                last_verified=excluded.last_verified
            """,
            (
                row_id,
                user["id"],
                credential_id,
                None,
                None,
                None,
                label or "هذا الجهاز",
                json.dumps(transports, ensure_ascii=False),
                0,
                now_iso(),
                now_iso(),
            ),
        )
        audit(db, user, "biometric_register", "users", user["id"], f"Registered biometric credential ({credential_id[:18]}...)")
        db.commit()
        self.send_json({"ok": True, "message": "تم تسجيل البصمة المؤسسية"})

    def api_biometric_auth_options(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        if FIDO2_AVAILABLE:
            rp_id = self.request_rp_id()
            rp = PublicKeyCredentialRpEntity(id=rp_id, name=COMPANY_NAME)
            server = Fido2Server(rp)
            rows = db.execute(
                """
                SELECT credential_data
                FROM biometric_credentials
                WHERE user_id=? AND active=1 AND credential_data IS NOT NULL
                ORDER BY created_at DESC
                """,
                (user["id"],),
            ).fetchall()
            credentials: List[Any] = []
            for row in rows:
                blob = str(row["credential_data"] or "").strip()
                if not blob:
                    continue
                try:
                    credentials.append(AttestedCredentialData(b64url_decode(blob)))
                except Exception:
                    continue
            if not credentials:
                return self.send_json({"ok": False, "error": "لا توجد بصمة قابلة للتحقق التشفيري. أعد التسجيل."}, 400)
            options, server_state = server.authenticate_begin(credentials=credentials, user_verification="required")
            state = store_biometric_flow_state(str(user["id"]), "verify_fido2", {"rp_id": rp_id, "server_state": server_state})
            return self.send_json({"ok": True, "state": state, "publicKey": webauthn_to_jsonable(options)})
        rows = db.execute(
            """
            SELECT credential_id
            FROM biometric_credentials
            WHERE user_id=? AND active=1
            ORDER BY created_at DESC
            """,
            (user["id"],),
        ).fetchall()
        if not rows:
            return self.send_json({"ok": False, "error": "لا توجد بصمة مربوطة لهذا الحساب"}, 400)
        challenge = create_biometric_challenge(str(user["id"]), "verify")
        self.send_json(
            {
                "ok": True,
                "state": challenge["state"],
                "publicKey": {
                    "challenge": challenge["challenge"],
                    "timeout": 60000,
                    "userVerification": "required",
                    "rpId": self.request_rp_id(),
                    "allowCredentials": [{"type": "public-key", "id": str(row["credential_id"])} for row in rows],
                },
            }
        )

    def api_biometric_auth_finish(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        state = str(data.get("state") or "").strip()
        credential = data.get("credential") or {}
        if not state or not isinstance(credential, dict):
            return self.send_json({"ok": False, "error": "بيانات التحقق غير مكتملة"}, 400)
        if FIDO2_AVAILABLE:
            flow = consume_biometric_flow_state(state, str(user["id"]), "verify_fido2")
            if flow:
                rp_id = str(flow.get("rp_id") or self.request_rp_id())
                server_state = flow.get("server_state")
                if not isinstance(server_state, dict):
                    return self.send_json({"ok": False, "error": "حالة التحقق غير صالحة"}, 400)
                response = credential.get("response") or {}
                credential_id = str(credential.get("id") or credential.get("rawId") or "").strip()
                row = db.execute(
                    "SELECT id, credential_data FROM biometric_credentials WHERE credential_id=? AND user_id=? AND active=1",
                    (credential_id, user["id"]),
                ).fetchone()
                if not row or not row["credential_data"]:
                    return self.send_json({"ok": False, "error": "لا يوجد اعتماد مطابق للحساب الحالي"}, 403)
                try:
                    rp = PublicKeyCredentialRpEntity(id=rp_id, name=COMPANY_NAME)
                    server = Fido2Server(rp)
                    stored_cred = AttestedCredentialData(b64url_decode(str(row["credential_data"])))
                    client_data = CollectedClientData(b64url_decode(str(response.get("clientDataJSON") or "")))
                    auth_data = AuthenticatorData(b64url_decode(str(response.get("authenticatorData") or "")))
                    signature = b64url_decode(str(response.get("signature") or ""))
                    server.authenticate_complete(
                        server_state,
                        [stored_cred],
                        stored_cred.credential_id,
                        client_data,
                        auth_data,
                        signature,
                    )
                    sign_count = int(getattr(auth_data, "counter", 0) or 0)
                except Exception as exc:
                    return self.send_json({"ok": False, "error": "فشل التحقق التشفيري للبصمة", "detail": str(exc)}, 401)
                db.execute(
                    "UPDATE biometric_credentials SET last_verified=?, sign_count=? WHERE id=?",
                    (now_iso(), sign_count, row["id"]),
                )
                audit(db, user, "biometric_verify", "users", user["id"], f"Verified biometric credential ({credential_id[:18]}...)")
                db.commit()
                return self.send_json({"ok": True, "verified_at": now_iso(), "mode": "fido2"})
        expected = consume_biometric_challenge(state, str(user["id"]), "verify")
        if not expected:
            return self.send_json({"ok": False, "error": "انتهت جلسة التحقق، أعد المحاولة"}, 400)
        response = credential.get("response") or {}
        try:
            client_data = self.parse_client_data(str(response.get("clientDataJSON") or ""))
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        if str(client_data.get("type") or "") != "webauthn.get":
            return self.send_json({"ok": False, "error": "نوع تحقق غير صحيح"}, 400)
        if str(client_data.get("challenge") or "") != expected:
            return self.send_json({"ok": False, "error": "تحدي التحقق غير مطابق"}, 400)
        credential_id = str(credential.get("id") or credential.get("rawId") or "").strip()
        if not credential_id:
            return self.send_json({"ok": False, "error": "معرف الاعتماد مفقود"}, 400)
        row = db.execute(
            """
            SELECT id, user_id, sign_count
            FROM biometric_credentials
            WHERE credential_id=? AND user_id=? AND active=1
            """,
            (credential_id, user["id"]),
        ).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "هذا الاعتماد غير مرتبط بالحساب الحالي"}, 403)
        sign_count = int(row["sign_count"] or 0)
        auth_data_b64 = str(response.get("authenticatorData") or "")
        if auth_data_b64:
            auth_raw = b64url_decode(auth_data_b64)
            if len(auth_raw) >= 37:
                flags = auth_raw[32]
                if (flags & 0x04) == 0:
                    return self.send_json({"ok": False, "error": "التحقق الحيوي لم يتم بشكل آمن (UV)"}, 401)
                sign_count = int.from_bytes(auth_raw[33:37], "big")
        db.execute(
            "UPDATE biometric_credentials SET last_verified=?, sign_count=? WHERE id=?",
            (now_iso(), sign_count, row["id"]),
        )
        audit(db, user, "biometric_verify", "users", user["id"], f"Verified biometric credential ({credential_id[:18]}...)")
        db.commit()
        self.send_json({"ok": True, "verified_at": now_iso()})

    def api_biometric_status(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        rows = rows_to_dicts(
            db.execute(
                """
                SELECT id, credential_id, credential_data, algorithm, label, transports, sign_count, active, created_at, last_verified
                FROM biometric_credentials
                WHERE user_id=?
                ORDER BY created_at DESC
                """,
                (user["id"],),
            ).fetchall()
        )
        for item in rows:
            item["transports"] = json.loads(item["transports"]) if item.get("transports") else []
            cid = str(item.get("credential_id") or "")
            item["credential_hint"] = f"{cid[:8]}...{cid[-6:]}" if len(cid) > 16 else cid
            item["crypto_verified"] = bool(item.get("credential_data"))
            item.pop("credential_id", None)
            item.pop("credential_data", None)
        active_count = sum(1 for item in rows if int(item.get("active") or 0) == 1)
        self.send_json({"ok": True, "active_count": active_count, "fido2_available": FIDO2_AVAILABLE, "items": rows})

    def api_biometric_clear(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        binding_id = str(data.get("binding_id") or "").strip()
        if binding_id:
            db.execute(
                "UPDATE biometric_credentials SET active=0 WHERE id=? AND user_id=?",
                (binding_id, user["id"]),
            )
            details = f"Cleared biometric binding {binding_id}"
        else:
            db.execute("UPDATE biometric_credentials SET active=0 WHERE user_id=?", (user["id"],))
            details = "Cleared all biometric bindings"
        audit(db, user, "biometric_clear", "users", user["id"], details)
        db.commit()
        self.send_json({"ok": True})

    def api_change_password(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        new_password = str(data.get("new_password") or "")
        force = bool(data.get("force"))
        row = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "User not found"}, 404)
        must_change = bool(row["must_change_password"] or 0)
        if not force or not must_change:
            old_password = str(data.get("old_password") or "")
            if not verify_password(old_password, row["password_hash"]):
                return self.send_json({"ok": False, "error": "كلمة المرور الحالية غير صحيحة"}, 401)
        err = validate_new_password(new_password, user.get("username") or "")
        if err:
            return self.send_json({"ok": False, "error": err}, 400)
        db.execute(
            "UPDATE users SET password_hash=?, must_change_password=0, password_changed_at=? WHERE id=?",
            (password_hash(new_password), now_iso(), user["id"]),
        )
        audit(db, user, "change_password", "users", user["id"], "Password updated")
        db.commit()
        self.send_json({"ok": True, "message": "تم تحديث كلمة المرور"})

    def api_logout(self, db: sqlite3.Connection) -> None:
        token = self.token_from_request("")
        user = self.current_user(db)
        if token:
            db.execute("DELETE FROM sessions WHERE token=?", (token,))
        if user:
            audit(db, user, "logout", "users", user["id"], "User logout")
        db.commit()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax")
        self.send_header("Set-Cookie", f"{LEGACY_SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax")
        payload = b'{"ok": true}'
        self.send_header("Content-Length", str(len(payload)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def api_bootstrap(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = {}
        for table, cols in TABLES.items():
            if table == "users" and user["role"] not in ("admin", "owner"):
                continue
            visible_cols = ",".join(cols)
            data[table] = rows_to_dicts(db.execute(f"SELECT {visible_cols} FROM {table} ORDER BY rowid DESC").fetchall())
        self.send_json({"ok": True, "data": data, "dashboard": build_dashboard(db), "user": user})

    def api_dashboard(self, db: sqlite3.Connection) -> None:
        self.send_json({"ok": True, "dashboard": build_dashboard(db)})

    def api_work_journal_list(self, db: sqlite3.Connection, user: Dict[str, Any], work_date: str) -> None:
        rows = db.execute(
            """
            SELECT id, user_id, work_date, text, attachments, created_at
            FROM work_journal
            WHERE user_id=? AND work_date=?
            ORDER BY created_at DESC
            """,
            (user["id"], work_date),
        ).fetchall()
        items = [journal_row_to_item(row) for row in rows]
        self.send_json({"ok": True, "items": items, "work_date": work_date})

    def api_work_journal_create(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        text = str(data.get("text") or "").strip()
        if not text:
            return self.send_json({"ok": False, "error": "أدخل وصف العمل المنجز"}, 400)
        work_date = str(data.get("work_date") or today()).strip() or today()
        files_payload = data.get("files") or []
        if not isinstance(files_payload, list):
            files_payload = []
        if len(files_payload) > MAX_JOURNAL_FILES_PER_ENTRY:
            return self.send_json(
                {"ok": False, "error": f"الحد الأقصى {MAX_JOURNAL_FILES_PER_ENTRY} ملفات لكل إدخال"},
                400,
            )
        entry_id = uid("WJ")
        stored: List[Dict[str, str]] = []
        for file_item in files_payload[:MAX_JOURNAL_FILES_PER_ENTRY]:
            if not isinstance(file_item, dict):
                continue
            try:
                file_bytes, content_type = decode_upload_payload(file_item)
                stored.append(
                    save_journal_attachment(
                        entry_id,
                        file_bytes,
                        content_type,
                        str(file_item.get("name") or "file"),
                    )
                )
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
        insert(
            db,
            "work_journal",
            {
                "id": entry_id,
                "user_id": user["id"],
                "work_date": work_date,
                "text": text,
                "attachments": json.dumps(stored, ensure_ascii=False),
                "created_at": now_iso(),
            },
        )
        audit(db, user, "create", "work_journal", entry_id, "Daily work journal entry")
        db.commit()
        row = db.execute(
            "SELECT id, user_id, work_date, text, attachments, created_at FROM work_journal WHERE id=?",
            (entry_id,),
        ).fetchone()
        self.send_json({"ok": True, "item": journal_row_to_item(row)})

    def api_work_journal_delete(self, db: sqlite3.Connection, user: Dict[str, Any], entry_id: str) -> None:
        row = db.execute(
            "SELECT id, user_id, attachments FROM work_journal WHERE id=?",
            (entry_id,),
        ).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "السجل غير موجود"}, 404)
        if row["user_id"] != user["id"] and user.get("role") not in ("admin", "owner"):
            return self.send_json({"ok": False, "error": "لا يمكنك حذف سجل مستخدم آخر"}, 403)
        for attachment in parse_journal_attachments(row["attachments"]):
            url = attachment.get("url")
            if url:
                delete_upload_file(str(url), "work_journal")
        db.execute("DELETE FROM work_journal WHERE id=?", (entry_id,))
        audit(db, user, "delete", "work_journal", entry_id, "Deleted daily work entry")
        db.commit()
        self.send_json({"ok": True})

    def api_daily_operations_list(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        from_date = str((params.get("from") or [""])[0] or "").strip()
        to_date = str((params.get("to") or [""])[0] or "").strip()
        if not from_date:
            from_date = (date.today() - timedelta(days=14)).isoformat()
        if not to_date:
            to_date = date.today().isoformat()
        rows = rows_to_dicts(
            db.execute(
                """
                SELECT
                    d.id,
                    d.entry_date,
                    d.employee_user_id,
                    d.employee_name,
                    d.icon,
                    d.done_text,
                    d.deferred_text,
                    d.deferred_to,
                    d.created_by_user_id,
                    d.created_by_name,
                    d.created_at,
                    eu.username AS employee_username,
                    cu.username AS created_by_username
                FROM daily_operations d
                LEFT JOIN users eu ON eu.id = d.employee_user_id
                LEFT JOIN users cu ON cu.id = d.created_by_user_id
                WHERE date(d.entry_date) >= date(?) AND date(d.entry_date) <= date(?)
                ORDER BY d.entry_date DESC, d.created_at DESC
                LIMIT 600
                """,
                (from_date, to_date),
            ).fetchall()
        )
        for row in rows:
            icon = str(row.get("icon") or "").strip()
            if not icon:
                row["icon"] = default_daily_ops_icon(str(row.get("employee_username") or ""), str(row.get("employee_name") or ""))
        self.send_json(
            {
                "ok": True,
                "items": rows,
                "period": {"from": from_date, "to": to_date},
                "can_manage_all": can_manage_daily_operations(user),
            }
        )

    def api_daily_operations_create(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        done_text = str(data.get("done_text") or "").strip()
        deferred_text = str(data.get("deferred_text") or "").strip()
        if not done_text and not deferred_text:
            return self.send_json({"ok": False, "error": "أدخل الأعمال المنجزة أو المؤجلة"}, 400)
        entry_date = str(data.get("entry_date") or today()).strip() or today()
        deferred_to = str(data.get("deferred_to") or "").strip() or None
        target_user_id = str(data.get("employee_user_id") or "").strip()
        requested_name = str(data.get("employee_name") or "").strip()
        manager = can_manage_daily_operations(user)
        actor_id = str(user.get("id") or "")
        if not target_user_id:
            target_user_id = "" if (manager and requested_name) else actor_id
        if not manager and target_user_id != actor_id:
            return self.send_json({"ok": False, "error": "يمكنك إضافة عملياتك اليومية فقط"}, 403)
        employee_user_id: Optional[str] = None
        employee_username = ""
        employee_name = requested_name
        emp_row = db.execute("SELECT id, username, name FROM users WHERE id=?", (target_user_id,)).fetchone() if target_user_id else None
        if emp_row:
            employee_user_id = str(emp_row["id"])
            employee_username = str(emp_row["username"] or "")
            if not employee_name:
                employee_name = str(emp_row["name"] or "") or employee_username
        elif manager and requested_name:
            employee_user_id = None
            employee_username = ""
        else:
            return self.send_json({"ok": False, "error": "الموظف المحدد غير موجود"}, 404)
        icon = str(data.get("icon") or "").strip() or default_daily_ops_icon(employee_username, employee_name)
        op_id = uid("DOP")
        created_by_name = str(user.get("name") or user.get("username") or "System")
        insert(
            db,
            "daily_operations",
            {
                "id": op_id,
                "entry_date": entry_date,
                "employee_user_id": employee_user_id,
                "employee_name": employee_name,
                "icon": icon,
                "done_text": done_text,
                "deferred_text": deferred_text or None,
                "deferred_to": deferred_to,
                "created_by_user_id": actor_id,
                "created_by_name": created_by_name,
                "created_at": now_iso(),
            },
        )
        audit(
            db,
            user,
            "create",
            "daily_operations",
            op_id,
            f"Daily ops entry for {employee_name} on {entry_date}",
        )
        db.commit()
        row = rows_to_dicts(
            db.execute(
                """
                SELECT
                    d.id,
                    d.entry_date,
                    d.employee_user_id,
                    d.employee_name,
                    d.icon,
                    d.done_text,
                    d.deferred_text,
                    d.deferred_to,
                    d.created_by_user_id,
                    d.created_by_name,
                    d.created_at,
                    eu.username AS employee_username,
                    cu.username AS created_by_username
                FROM daily_operations d
                LEFT JOIN users eu ON eu.id = d.employee_user_id
                LEFT JOIN users cu ON cu.id = d.created_by_user_id
                WHERE d.id=?
                LIMIT 1
                """,
                (op_id,),
            ).fetchall()
        )
        self.send_json({"ok": True, "item": row[0] if row else None})

    def api_property_photo(self, db: sqlite3.Connection, user: Dict[str, Any], property_id: str) -> None:
        row = db.execute("SELECT id, image FROM properties WHERE id=?", (property_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "العقار غير موجود"}, 404)
        try:
            data = self.read_json()
            file_bytes, content_type = decode_property_photo_payload(data)
            old_image = row["image"]
            image_url = save_property_photo_file(property_id, file_bytes, content_type)
            db.execute(
                "UPDATE properties SET image=?, last_update=? WHERE id=?",
                (image_url, today(), property_id),
            )
            audit(db, user, "update", "properties", property_id, "Uploaded property photo")
            db.commit()
            if is_stored_property_image(old_image) and old_image != image_url:
                delete_property_photo_file(old_image)
            return self.send_json({"ok": True, "image": image_url, "item": {"id": property_id, "image": image_url}})
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"ok": False, "error": "تعذر حفظ الصورة", "detail": str(exc)}, 500)

    def api_estate_convert_reservation(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        entity_type = str(data.get("entity_type") or "").strip().lower()
        entity_id = str(data.get("entity_id") or "").strip()
        tenant_client_id = str(data.get("tenant_client_id") or "").strip() or None
        note = str(data.get("note") or "Converted from reserved to occupied").strip()
        if entity_type not in ("apartment", "room"):
            return self.send_json({"ok": False, "error": "entity_type must be apartment or room"}, 400)
        if not entity_id:
            return self.send_json({"ok": False, "error": "entity_id مطلوب"}, 400)
        table = "estate_apartments" if entity_type == "apartment" else "estate_rooms"
        row = db.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "العنصر غير موجود"}, 404)
        current_status = str(row["status"] or "").strip().lower()
        if current_status != "reserved":
            return self.send_json({"ok": False, "error": "يمكن التحويل فقط من حالة محجوزة"}, 400)
        if not tenant_client_id:
            tenant_client_id = str(row["booked_client_id"] or "").strip() or None
        if tenant_client_id and not exists(db, "clients", tenant_client_id):
            return self.send_json({"ok": False, "error": "العميل المحدد غير موجود"}, 400)
        tenant_phone = str(row["tenant_phone"] or "").strip() or str(row["booked_client_phone"] or "").strip() or None
        db.execute(
            f"""
            UPDATE {table}
            SET status='occupied',
                tenant_client_id=?,
                tenant_phone=?,
                reservation_start_date=NULL,
                reservation_end_date=NULL,
                last_update=?
            WHERE id=?
            """,
            (tenant_client_id, tenant_phone, today(), entity_id),
        )
        log_estate_status_history(
            db,
            entity_type,
            entity_id,
            dict(row),
            "reserved",
            "occupied",
            str(user.get("name") or user.get("username") or "System"),
            note,
        )
        db.execute(
            "UPDATE estate_reservation_invoices SET status='Closed', note=COALESCE(note,'') || ' | Closed by conversion to occupied at ' || ? WHERE entity_type=? AND entity_id=? AND lower(status)='open'",
            (now_iso(), entity_type, entity_id),
        )
        audit(db, user, "convert_reservation", table, entity_id, note)
        db.commit()
        self.send_json({"ok": True, "entity_type": entity_type, "entity_id": entity_id, "status": "occupied"})

    def api_estate_convert_to_contract(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        entity_type = str(data.get("entity_type") or "").strip().lower()
        entity_id = str(data.get("entity_id") or "").strip()
        if entity_type not in ("apartment", "room"):
            return self.send_json({"ok": False, "error": "entity_type must be apartment or room"}, 400)
        if not entity_id:
            return self.send_json({"ok": False, "error": "entity_id مطلوب"}, 400)
        table = "estate_apartments" if entity_type == "apartment" else "estate_rooms"
        row = db.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "العنصر غير موجود"}, 404)
        status_now = str(row["status"] or "").strip().lower()
        if estate_unit_status_blocks_contract(status_now):
            return self.send_json({"ok": False, "error": "لا يمكن تأجير أو تفعيل عقد لوحدة تحت الصيانة أو موقوفة"}, 400)
        if status_now not in ("vacant", "reserved", "occupied"):
            return self.send_json({"ok": False, "error": "يجب أن تكون حالة الوحدة شاغرة/محجوزة/مؤجرة لإنشاء مسودة عقد"}, 400)

        tenant_client_id = str(data.get("tenant_client_id") or "").strip() or str(row["tenant_client_id"] or "").strip() or str(row["booked_client_id"] or "").strip()
        if not tenant_client_id:
            return self.send_json({"ok": False, "error": "حدد العميل/المستأجر قبل إنشاء العقد"}, 400)
        if not exists(db, "clients", tenant_client_id):
            return self.send_json({"ok": False, "error": "العميل المحدد غير موجود"}, 400)
        c_row = db.execute("SELECT name, phone FROM clients WHERE id=?", (tenant_client_id,)).fetchone()
        tenant_phone = str(data.get("tenant_phone") or "").strip() or str(row["tenant_phone"] or "").strip() or str(c_row["phone"] if c_row else "") or None

        start_date = str(data.get("start_date") or row["reservation_start_date"] or today()).strip()
        end_date = str(data.get("end_date") or row["reservation_end_date"] or "").strip()
        if not end_date:
            d0 = datetime.fromisoformat(start_date).date()
            end_date = (d0 + timedelta(days=365)).isoformat()
        try:
            sdt = datetime.fromisoformat(start_date).date()
            edt = datetime.fromisoformat(end_date).date()
        except Exception:
            return self.send_json({"ok": False, "error": "تواريخ العقد غير صحيحة"}, 400)
        if edt < sdt:
            return self.send_json({"ok": False, "error": "تاريخ نهاية العقد يجب أن يكون بعد البداية"}, 400)

        rent_amount = round(float(data.get("rent_amount") or row["rent_price"] or 0), 3)
        if rent_amount <= 0:
            return self.send_json({"ok": False, "error": "سعر الإيجار يجب أن يكون أكبر من صفر"}, 400)
        payment_cycle = str(data.get("payment_cycle") or "monthly").strip().lower()
        if payment_cycle not in ("monthly", "quarterly", "yearly", "once"):
            payment_cycle = "monthly"

        contract_row = {
            "id": uid("ESC"),
            "contract_no": next_estate_contract_no(db),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "property_id": row["property_id"],
            "building_id": row["building_id"],
            "apartment_id": (entity_id if entity_type == "apartment" else row["apartment_id"]),
            "room_id": (entity_id if entity_type == "room" else None),
            "client_id": tenant_client_id,
            "start_date": sdt.isoformat(),
            "end_date": edt.isoformat(),
            "rent_amount": rent_amount,
            "payment_cycle": payment_cycle,
            "status": "Draft",
            "created_by": str(user.get("name") or user.get("username") or "System"),
            "created_at": now_iso(),
            "attachments": str(data.get("attachments") or "[]"),
            "notes": str(data.get("notes") or "Generated from reservation flow as draft"),
        }
        insert(db, "estate_contracts", contract_row)
        audit(db, user, "create_contract_draft", "estate_contracts", contract_row["id"], f"Estate contract draft {contract_row['contract_no']} for {entity_type} {entity_id}")
        db.commit()
        self.send_json(
            {
                "ok": True,
                "contract": contract_row,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "message": "تم إنشاء العقد كمسودة. أرسل طلب اعتماد ثم فعّل العقد لإصدار الفواتير.",
            }
        )

    def api_estate_contract_request_approval(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = str(data.get("contract_id") or "").strip()
        notes = str(data.get("notes") or "طلب اعتماد عقد عقاري").strip()
        if not contract_id:
            return self.send_json({"ok": False, "error": "contract_id مطلوب"}, 400)
        row = db.execute("SELECT * FROM estate_contracts WHERE id=?", (contract_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "العقد غير موجود"}, 404)
        st = str(row["status"] or "").strip().lower()
        if st in ("approved", "active"):
            return self.send_json({"ok": False, "error": "العقد معتمد/مفعّل مسبقاً"}, 400)
        if st != "draft":
            return self.send_json({"ok": False, "error": "يمكن إرسال طلب الاعتماد من حالة مسودة فقط"}, 400)
        approval_id = create_approval_request(
            db,
            "estate_contracts",
            contract_id,
            "contract",
            user.get("name") or user.get("username") or "System",
            notes,
        )
        db.execute("UPDATE estate_contracts SET status=? WHERE id=?", ("ApprovalRequested", contract_id))
        audit(db, user, "request_approval", "estate_contracts", contract_id, f"estate approval {approval_id}")
        db.commit()
        self.send_json({"ok": True, "approval_id": approval_id, "status": "ApprovalRequested"})

    def api_estate_contract_approve(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = str(data.get("contract_id") or "").strip()
        if not contract_id:
            return self.send_json({"ok": False, "error": "contract_id مطلوب"}, 400)
        if not can_decide_approval(user, "contract"):
            return self.send_json({"ok": False, "error": "لا تملك صلاحية اعتماد العقد"}, 403)
        row = db.execute("SELECT * FROM estate_contracts WHERE id=?", (contract_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "العقد غير موجود"}, 404)
        st = str(row["status"] or "").strip().lower()
        if st == "active":
            return self.send_json({"ok": False, "error": "العقد مفعّل مسبقاً"}, 400)
        if st != "approvalrequested":
            return self.send_json({"ok": False, "error": "لا يمكن اعتماد العقد إلا بعد طلب اعتماد"}, 400)
        try:
            sdt = datetime.fromisoformat(str(row["start_date"] or "")).date()
            edt = datetime.fromisoformat(str(row["end_date"] or "")).date()
        except Exception:
            return self.send_json({"ok": False, "error": "تواريخ العقد غير صحيحة"}, 400)
        if edt < sdt:
            return self.send_json({"ok": False, "error": "تاريخ نهاية العقد يجب أن يكون بعد البداية"}, 400)
        conflict = conflicting_active_estate_contract(
            db,
            str(row["entity_type"] or "").strip().lower(),
            str(row["entity_id"] or "").strip(),
            str(row["start_date"] or ""),
            str(row["end_date"] or ""),
            contract_id,
        )
        if conflict:
            return self.send_json(
                {
                    "ok": False,
                    "error": f"يوجد عقد متعارض {conflict.get('contract_no') or conflict.get('id')} للفترة {conflict.get('start_date')} - {conflict.get('end_date')}",
                },
                400,
            )
        db.execute(
            "UPDATE estate_contracts SET status=?, approved_by=?, approved_at=? WHERE id=?",
            ("Approved", user.get("name") or user.get("username"), now_iso(), contract_id),
        )
        db.execute(
            """
            UPDATE approvals
            SET status='Approved', approved_by=?, approved_at=?
            WHERE entity='estate_contracts' AND entity_id=? AND request_type='contract' AND lower(status)='pending'
            """,
            (user.get("name") or user.get("username"), now_iso(), contract_id),
        )
        audit(db, user, "approve", "estate_contracts", contract_id, "Estate contract approved")
        db.commit()
        self.send_json({"ok": True, "status": "Approved"})

    def api_estate_contract_activate(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = str(data.get("contract_id") or "").strip()
        if not contract_id:
            return self.send_json({"ok": False, "error": "contract_id مطلوب"}, 400)
        contract = db.execute("SELECT * FROM estate_contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "العقد غير موجود"}, 404)
        status = str(contract["status"] or "").strip().lower()
        if status == "active":
            return self.send_json({"ok": False, "error": "العقد مفعّل مسبقاً"}, 400)
        if status != "approved":
            return self.send_json({"ok": False, "error": "دورة العقد الإلزامية: مسودة → طلب اعتماد → معتمد → مفعّل"}, 400)
        entity_type = str(contract["entity_type"] or "").strip().lower()
        entity_id = str(contract["entity_id"] or "").strip()
        table = estate_unit_table(entity_type)
        unit_row = db.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
        if not unit_row:
            return self.send_json({"ok": False, "error": "الوحدة المرتبطة بالعقد غير موجودة"}, 404)
        if estate_unit_status_blocks_contract(unit_row["status"]):
            return self.send_json({"ok": False, "error": "لا يمكن تفعيل عقد لوحدة تحت الصيانة أو موقوفة"}, 400)
        conflict = conflicting_active_estate_contract(
            db,
            entity_type,
            entity_id,
            str(contract["start_date"] or ""),
            str(contract["end_date"] or ""),
            contract_id,
        )
        if conflict:
            return self.send_json(
                {
                    "ok": False,
                    "error": f"يوجد عقد نشط متداخل {conflict.get('contract_no') or conflict.get('id')}",
                },
                400,
            )
        actor_name = str(user.get("name") or user.get("username") or "System")
        client_row = db.execute("SELECT phone FROM clients WHERE id=?", (contract["client_id"],)).fetchone()
        tenant_phone = str(client_row["phone"] if client_row else "").strip() or str(unit_row["tenant_phone"] or "").strip()
        db.execute(
            "UPDATE estate_contracts SET status=?, activated_by=?, activated_at=? WHERE id=?",
            ("Active", user.get("name") or user.get("username"), now_iso(), contract_id),
        )
        schedule_result = generate_estate_contract_invoices(
            db,
            dict(contract),
            actor_name,
            replace_open=False,
        )
        db.execute(
            f"""
            UPDATE {table}
            SET status='occupied',
                tenant_client_id=?,
                tenant_phone=?,
                reservation_start_date=NULL,
                reservation_end_date=NULL,
                last_update=?
            WHERE id=?
            """,
            (contract["client_id"], tenant_phone, today(), entity_id),
        )
        db.execute(
            "UPDATE estate_reservation_invoices SET status='Closed', note=COALESCE(note,'') || ' | Closed by contract activation at ' || ? WHERE entity_type=? AND entity_id=? AND lower(status)='open'",
            (now_iso(), entity_type, entity_id),
        )
        log_estate_status_history(
            db,
            entity_type,
            entity_id,
            dict(unit_row),
            str(unit_row["status"] or ""),
            "occupied",
            actor_name,
            "Contract activated",
        )
        audit(db, user, "activate", "estate_contracts", contract_id, f"Activated and generated {schedule_result.get('created', 0)} invoices")
        db.commit()
        self.send_json({"ok": True, "status": "Active", "result": schedule_result})

    def api_estate_contract_generate_schedule(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = str(data.get("contract_id") or "").strip()
        if not contract_id:
            return self.send_json({"ok": False, "error": "contract_id مطلوب"}, 400)
        contract = db.execute("SELECT * FROM estate_contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "العقد غير موجود"}, 404)
        if str(contract["status"] or "").strip().lower() != "active":
            return self.send_json({"ok": False, "error": "يمكن جدولة دفعات العقود النشطة فقط"}, 400)
        replace_open = bool(data.get("replace_open"))
        try:
            result = generate_estate_contract_invoices(
                db,
                dict(contract),
                str(user.get("name") or user.get("username") or "System"),
                replace_open=replace_open,
            )
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        audit(db, user, "generate_schedule", "estate_contracts", contract_id, f"created={result.get('created')} skipped={result.get('skipped')} replace_open={replace_open}")
        db.commit()
        self.send_json({"ok": True, "contract_id": contract_id, "result": result})

    def api_estate_contract_pay_invoice(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        invoice_id = str(data.get("invoice_id") or "").strip()
        amount = round(float(data.get("amount") or 0), 3)
        payment_date = str(data.get("payment_date") or today()).strip() or today()
        if not invoice_id:
            return self.send_json({"ok": False, "error": "invoice_id مطلوب"}, 400)
        if amount <= 0:
            return self.send_json({"ok": False, "error": "مبلغ التحصيل يجب أن يكون أكبر من صفر"}, 400)
        try:
            _ = datetime.fromisoformat(payment_date).date()
        except Exception:
            return self.send_json({"ok": False, "error": "تاريخ التحصيل غير صحيح"}, 400)
        if is_estate_month_closed(db, payment_date):
            return self.send_json({"ok": False, "error": "لا يمكن تسجيل تحصيل داخل شهر مقفل ماليًا"}, 400)
        row = db.execute("SELECT * FROM estate_contract_invoices WHERE id=?", (invoice_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "فاتورة العقد غير موجودة"}, 404)
        remaining = round(float(row["amount"] or 0) - float(row["paid_amount"] or 0), 3)
        if remaining <= 0:
            return self.send_json({"ok": False, "error": "الفاتورة مسددة بالكامل"}, 400)
        if amount - remaining > 0.001:
            return self.send_json({"ok": False, "error": f"المبلغ يتجاوز المتبقي {fmt_omr(remaining)}"}, 400)
        new_paid = round(float(row["paid_amount"] or 0) + amount, 3)
        new_status = "Paid" if new_paid >= float(row["amount"] or 0) - 0.001 else "Partial"
        db.execute(
            "UPDATE estate_contract_invoices SET paid_amount=?, status=? WHERE id=?",
            (new_paid, new_status, invoice_id),
        )
        contract = db.execute("SELECT * FROM estate_contracts WHERE id=?", (row["contract_id"],)).fetchone()
        client_id = contract["client_id"] if contract else None
        estate_property_ref = contract["property_id"] if contract else None
        insert(
            db,
            "accounts",
            {
                "id": uid("ACC"),
                "entry_date": payment_date,
                "type": "income",
                "category": "Estate Contract Collection",
                "description": f"Collection {row['invoice_no']} (estate:{estate_property_ref or '-'})",
                "client_id": client_id,
                # accounts.property_id references legacy properties table, not estate_properties
                "property_id": None,
                "invoice_id": None,
                "amount": amount,
            },
        )
        audit(db, user, "pay", "estate_contract_invoices", invoice_id, f"Collected {amount} for {row['invoice_no']} on {payment_date}")
        db.commit()
        self.send_json({"ok": True, "invoice_id": invoice_id, "paid_amount": new_paid, "status": new_status, "payment_date": payment_date})

    def api_estate_contract_close(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = str(data.get("contract_id") or "").strip()
        if not contract_id:
            return self.send_json({"ok": False, "error": "contract_id مطلوب"}, 400)
        contract = db.execute("SELECT * FROM estate_contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "العقد غير موجود"}, 404)
        if str(contract["status"] or "").strip().lower() != "active":
            return self.send_json({"ok": False, "error": "يمكن إغلاق العقود النشطة فقط"}, 400)
        close_date = str(data.get("close_date") or today()).strip() or today()
        try:
            close_dt = datetime.fromisoformat(close_date).date()
        except Exception:
            return self.send_json({"ok": False, "error": "تاريخ الإغلاق غير صحيح"}, 400)
        if is_estate_month_closed(db, close_dt.isoformat()):
            return self.send_json({"ok": False, "error": "لا يمكن إغلاق عقد بتاريخ داخل شهر مقفل ماليًا"}, 400)
        force_close = bool(data.get("force_close"))
        note = str(data.get("note") or "Contract closed").strip()
        rows = rows_to_dicts(
            db.execute(
                "SELECT * FROM estate_contract_invoices WHERE contract_id=? ORDER BY due_date ASC",
                (contract_id,),
            ).fetchall()
        )
        overdue_rows: List[Dict[str, Any]] = []
        future_cancel_ids: List[str] = []
        total_scheduled = 0.0
        total_paid = 0.0
        outstanding_due = 0.0
        for r in rows:
            amount = round(float(r.get("amount") or 0), 3)
            paid_amount = round(float(r.get("paid_amount") or 0), 3)
            rem = round(max(0.0, amount - paid_amount), 3)
            total_scheduled += amount
            total_paid += paid_amount
            due_s = str(r.get("due_date") or "")
            due_dt = None
            try:
                due_dt = datetime.fromisoformat(due_s).date()
            except Exception:
                pass
            if rem > 0:
                if due_dt and due_dt <= close_dt:
                    outstanding_due += rem
                    overdue_rows.append(
                        {
                            "id": r.get("id"),
                            "invoice_no": r.get("invoice_no"),
                            "due_date": due_s,
                            "remaining": rem,
                        }
                    )
                elif due_dt and due_dt > close_dt and paid_amount <= 0:
                    future_cancel_ids.append(str(r.get("id")))
        preview = {
            "contract_id": contract_id,
            "contract_no": contract["contract_no"],
            "close_date": close_dt.isoformat(),
            "total_scheduled": round(total_scheduled, 3),
            "total_paid": round(total_paid, 3),
            "outstanding_due": round(outstanding_due, 3),
            "future_cancelled_count": len(future_cancel_ids),
            "overdue_items": overdue_rows,
        }
        if outstanding_due > 0 and not force_close:
            return self.send_json(
                {
                    "ok": False,
                    "error": "لا يمكن إغلاق العقد قبل معالجة المتأخرات المستحقة. سدّد أو استخدم force_close بصلاحية مناسبة.",
                    "settlement_preview": preview,
                },
                400,
            )
        role = str(user.get("role") or "").strip().lower()
        if outstanding_due > 0 and force_close and role not in ("owner", "admin"):
            return self.send_json({"ok": False, "error": "force_close مسموح فقط للمالك/الإدارة"}, 403)
        if future_cancel_ids:
            marks = ",".join("?" for _ in future_cancel_ids)
            db.execute(
                f"UPDATE estate_contract_invoices SET status='Cancelled', note=COALESCE(note,'') || ' | Cancelled due to contract close at ' || ? WHERE id IN ({marks})",
                [now_iso(), *future_cancel_ids],
            )
        close_status = str(data.get("close_status") or "ended").strip().lower()
        if close_status not in ("ended", "cancelled"):
            close_status = "ended"
        db.execute(
            "UPDATE estate_contracts SET status=?, end_date=?, closed_at=?, close_note=? WHERE id=?",
            (close_status.capitalize(), close_dt.isoformat(), now_iso(), note, contract_id),
        )
        settlement = {
            "id": uid("ECS"),
            "contract_id": contract_id,
            "close_date": close_dt.isoformat(),
            "total_scheduled": round(total_scheduled, 3),
            "total_paid": round(total_paid, 3),
            "outstanding_due": round(outstanding_due, 3),
            "future_cancelled": len(future_cancel_ids),
            "closed_by": str(user.get("name") or user.get("username") or "System"),
            "note": note,
            "created_at": now_iso(),
        }
        insert(db, "estate_contract_settlements", settlement)
        audit(
            db,
            user,
            "close_contract",
            "estate_contracts",
            contract_id,
            f"{close_status.capitalize()} {contract['contract_no']} | outstanding={settlement['outstanding_due']} | future_cancelled={settlement['future_cancelled']}",
        )
        entity_type = str(contract["entity_type"] or "").strip().lower()
        entity_id = str(contract["entity_id"] or "").strip()
        active_after = db.execute(
            "SELECT id FROM estate_contracts WHERE lower(entity_type)=lower(?) AND entity_id=? AND lower(status)='active' AND id<>?",
            (entity_type, entity_id, contract_id),
        ).fetchone()
        if not active_after and entity_id:
            set_estate_unit_status(
                db,
                entity_type=entity_type,
                entity_id=entity_id,
                target_status="vacant",
                actor_name=str(user.get("name") or user.get("username") or "System"),
                note=f"Contract {close_status}",
            )
        db.commit()
        self.send_json({"ok": True, "contract_id": contract_id, "status": close_status.capitalize(), "settlement": settlement, "preview": preview})

    def api_estate_month_close(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        month_key = str(data.get("month_key") or "").strip()
        force = bool(data.get("force"))
        note = str(data.get("note") or "").strip()
        try:
            if len(month_key) != 7:
                raise ValueError("invalid")
            month_start = datetime.fromisoformat(month_key + "-01").date()
        except Exception:
            return self.send_json({"ok": False, "error": "month_key يجب أن يكون بصيغة YYYY-MM"}, 400)
        if month_start > date.today():
            return self.send_json({"ok": False, "error": "لا يمكن إقفال شهر مستقبلي"}, 400)
        month_end = add_months(month_start, 1) - timedelta(days=1)
        inv_rows = rows_to_dicts(
            db.execute(
                "SELECT * FROM estate_contract_invoices WHERE strftime('%Y-%m', due_date)=?",
                (month_key,),
            ).fetchall()
        )
        total_invoiced = round(sum(float(x.get("amount") or 0) for x in inv_rows), 3)
        total_collected = round(sum(float(x.get("paid_amount") or 0) for x in inv_rows), 3)
        outstanding_due = round(sum(max(0.0, float(x.get("amount") or 0) - float(x.get("paid_amount") or 0)) for x in inv_rows), 3)
        overdue_open = rows_to_dicts(
            db.execute(
                """
                SELECT id, invoice_no, due_date, amount, paid_amount
                FROM estate_contract_invoices
                WHERE date(due_date) <= date(?) AND lower(status)!='paid'
                ORDER BY due_date ASC
                """,
                (month_end.isoformat(),),
            ).fetchall()
        )
        preview = {
            "month_key": month_key,
            "period": {"start": month_start.isoformat(), "end": month_end.isoformat()},
            "total_invoiced": total_invoiced,
            "total_collected": total_collected,
            "outstanding_due": outstanding_due,
            "overdue_open_count": len(overdue_open),
            "overdue_open_items": [
                {
                    "id": r["id"],
                    "invoice_no": r["invoice_no"],
                    "due_date": r["due_date"],
                    "remaining": round(max(0.0, float(r.get("amount") or 0) - float(r.get("paid_amount") or 0)), 3),
                }
                for r in overdue_open[:25]
            ],
        }
        if overdue_open and not force:
            return self.send_json(
                {
                    "ok": False,
                    "error": "يوجد ذمم مفتوحة حتى نهاية هذا الشهر. عالج المتأخرات أو استخدم force=true بصلاحية الإدارة.",
                    "preview": preview,
                },
                400,
            )
        role = str(user.get("role") or "").strip().lower()
        if overdue_open and force and role not in ("owner", "admin"):
            return self.send_json({"ok": False, "error": "force لإقفال الشهر مسموح فقط للمالك/الإدارة"}, 403)
        exists_close = db.execute("SELECT id FROM estate_month_closes WHERE month_key=?", (month_key,)).fetchone()
        closed_by = str(user.get("name") or user.get("username") or "System")
        if exists_close:
            db.execute(
                """
                UPDATE estate_month_closes
                SET status='Closed', total_invoiced=?, total_collected=?, outstanding_due=?, closed_by=?, closed_at=?, note=?
                WHERE month_key=?
                """,
                (total_invoiced, total_collected, outstanding_due, closed_by, now_iso(), note, month_key),
            )
            close_id = exists_close["id"]
        else:
            close_id = uid("EMC")
            insert(
                db,
                "estate_month_closes",
                {
                    "id": close_id,
                    "month_key": month_key,
                    "status": "Closed",
                    "total_invoiced": total_invoiced,
                    "total_collected": total_collected,
                    "outstanding_due": outstanding_due,
                    "closed_by": closed_by,
                    "closed_at": now_iso(),
                    "note": note,
                },
            )
        audit(db, user, "month_close", "estate_month_closes", close_id, f"Closed month {month_key} | outstanding={outstanding_due}")
        db.commit()
        self.send_json({"ok": True, "month_close_id": close_id, "month_key": month_key, "preview": preview})

    def api_estate_operations_check(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        checks: List[Dict[str, Any]] = []
        required_tables = [
            "estate_properties",
            "estate_buildings",
            "estate_apartments",
            "estate_rooms",
            "estate_accessories",
            "estate_maintenance",
            "estate_status_history",
            "estate_reservation_invoices",
            "estate_contracts",
            "estate_contract_invoices",
            "estate_contract_settlements",
            "estate_month_closes",
        ]
        for t in required_tables:
            exists_row = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (t,)).fetchone()
            checks.append({"name": f"table:{t}", "ok": bool(exists_row), "value": 1 if exists_row else 0})
        dangling_reserved = db.execute(
            """
            SELECT COUNT(*)
            FROM (
              SELECT 'apartment' AS entity_type, id, status FROM estate_apartments
              UNION ALL
              SELECT 'room' AS entity_type, id, status FROM estate_rooms
            ) e
            WHERE lower(status)='reserved'
              AND NOT EXISTS (
                SELECT 1 FROM estate_reservation_invoices i
                WHERE i.entity_type=e.entity_type AND i.entity_id=e.id AND lower(i.status)='open'
              )
            """
        ).fetchone()[0]
        checks.append({"name": "reserved_with_open_invoice", "ok": int(dangling_reserved or 0) == 0, "value": int(dangling_reserved or 0)})
        active_contracts = db.execute("SELECT COUNT(*) FROM estate_contracts WHERE lower(status)='active'").fetchone()[0]
        reserved_total = db.execute("SELECT COUNT(*) FROM estate_apartments WHERE lower(status)='reserved'").fetchone()[0] + db.execute("SELECT COUNT(*) FROM estate_rooms WHERE lower(status)='reserved'").fetchone()[0]
        status_history_count = db.execute("SELECT COUNT(*) FROM estate_status_history").fetchone()[0]
        overdue_contract_invoices = db.execute(
            "SELECT COUNT(*) FROM estate_contract_invoices WHERE lower(status)!='paid' AND date(due_date) < date(?)",
            (today(),),
        ).fetchone()[0]
        due_soon_contract_invoices = db.execute(
            "SELECT COUNT(*) FROM estate_contract_invoices WHERE lower(status)!='paid' AND date(due_date) >= date(?) AND date(due_date) <= date(?, '+7 day')",
            (today(), today()),
        ).fetchone()[0]
        active_past_end = db.execute(
            "SELECT COUNT(*) FROM estate_contracts WHERE lower(status)='active' AND date(end_date) < date(?)",
            (today(),),
        ).fetchone()[0]
        closed_months = db.execute("SELECT COUNT(*) FROM estate_month_closes WHERE lower(status)='closed'").fetchone()[0]
        checks.append({"name": "status_history_exists", "ok": int(status_history_count or 0) > 0, "value": int(status_history_count or 0)})
        checks.append({"name": "overdue_contract_invoices", "ok": int(overdue_contract_invoices or 0) == 0, "value": int(overdue_contract_invoices or 0)})
        checks.append({"name": "active_contracts_past_end", "ok": int(active_past_end or 0) == 0, "value": int(active_past_end or 0)})
        score = 100 - (15 if int(dangling_reserved or 0) > 0 else 0)
        if status_history_count == 0:
            score -= 10
        if int(overdue_contract_invoices or 0) > 0:
            score -= min(20, int(overdue_contract_invoices or 0) * 2)
        if int(active_past_end or 0) > 0:
            score -= min(15, int(active_past_end or 0) * 2)
        if any(not c["ok"] for c in checks if c["name"].startswith("table:")):
            score -= 30
        score = max(0, min(100, score))
        self.send_json(
            {
                "ok": True,
                "score": score,
                "checks": checks,
                "metrics": {
                    "reserved_total": int(reserved_total or 0),
                    "active_contracts": int(active_contracts or 0),
                    "status_history_rows": int(status_history_count or 0),
                    "dangling_reserved_without_invoice": int(dangling_reserved or 0),
                    "overdue_contract_invoices": int(overdue_contract_invoices or 0),
                    "due_soon_contract_invoices": int(due_soon_contract_invoices or 0),
                    "active_contracts_past_end": int(active_past_end or 0),
                    "closed_months": int(closed_months or 0),
                },
            }
        )

    def api_estate_copy_from_nizwa(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        import lq_nizwa_estate_copy

        result = lq_nizwa_estate_copy.copy_qe_to_estate(
            db,
            uid_fn=uid,
            now_fn=now_iso,
            actor=str(user.get("name") or user.get("username") or "owner"),
        )
        if result.get("ok"):
            audit(
                db,
                user,
                "copy",
                "estate_properties",
                str(result.get("property_id") or ""),
                f"Copied Nizwa qe_* into estate_* | {result.get('created')}",
            )
            db.commit()
        self.send_json(result, 200 if result.get("ok") else 400)

    def api_crud(self, db: sqlite3.Connection, method: str, parts: List[str], query: str) -> None:
        table = parts[0]
        item_id = parts[1] if len(parts) > 1 else None
        perm_base = table
        read_perm = f"{perm_base}:read"
        write_perm = perm_base
        delete_perm = f"{perm_base}:delete"
        if table == "users":
            write_perm = "admin"
            read_perm = "admin"
            delete_perm = "admin"
        user = self.require_user(db, read_perm if method == "GET" else (delete_perm if method == "DELETE" else write_perm))
        if not user:
            return
        visible_cols = TABLES[table]
        if method == "GET":
            cols = ",".join(visible_cols)
            if item_id:
                row = db.execute(f"SELECT {cols} FROM {table} WHERE id=?", (item_id,)).fetchone()
                return self.send_json({"ok": bool(row), "item": dict(row) if row else None})
            return self.send_json({"ok": True, "items": rows_to_dicts(db.execute(f"SELECT {cols} FROM {table} ORDER BY rowid DESC").fetchall())})
        if method in ("POST", "PUT"):
            data = self.read_json()
            if table == "users":
                return self.save_user(db, user, method, data, item_id)
            return self.save_generic(db, user, table, data, item_id, method)
        if method == "DELETE":
            if not item_id:
                return self.send_json({"ok": False, "error": "Missing id"}, 400)
            if table == "users":
                return self.send_json(
                    {
                        "ok": False,
                        "error": "لا يُسمح بحذف المستخدمين. عطّل الحساب (active=0) للحفاظ على سجل العمليات.",
                        "hint": "استخدم PUT /api/users/{id} مع active=false",
                    },
                    400,
                )
            if table == "properties":
                row = db.execute("SELECT image FROM properties WHERE id=?", (item_id,)).fetchone()
                if row:
                    delete_property_photo_file(row["image"])
            if table in ("estate_properties", "estate_buildings", "estate_apartments", "estate_rooms"):
                row = db.execute(f"SELECT image FROM {table} WHERE id=?", (item_id,)).fetchone()
                if row:
                    delete_upload_file(str(row["image"] or ""), "estate_images")
            reason = protected_delete_reason(db, table, item_id)
            if reason:
                return self.send_json({"ok": False, "error": reason}, 400)
            db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            audit(db, user, "delete", table, item_id, "Deleted record")
            db.commit()
            return self.send_json({"ok": True})

    def save_user(self, db: sqlite3.Connection, user: Dict[str, Any], method: str, data: Dict[str, Any], item_id: Optional[str]) -> None:
        def as_flag(value: Any, default: bool) -> int:
            if value is None:
                return 1 if default else 0
            if isinstance(value, bool):
                return 1 if value else 0
            raw = str(value).strip().lower()
            if raw in ("1", "true", "yes", "on", "y", "t"):
                return 1
            if raw in ("0", "false", "no", "off", "n", "f"):
                return 0
            return 1 if default else 0
        if method == "POST":
            required = ["username", "name", "role", "password"]
            missing = [k for k in required if not data.get(k)]
            if missing:
                return self.send_json({"ok": False, "error": f"Missing: {', '.join(missing)}"}, 400)
            username = str(data.get("username") or "").strip().lower()
            if not username:
                return self.send_json({"ok": False, "error": "اسم المستخدم مطلوب"}, 400)
            role_value = str(data.get("role") or "").strip().lower()
            if role_value in ("owner", "admin") and username not in FULL_ACCESS_USERNAMES:
                return self.send_json({"ok": False, "error": "صلاحية كاملة (Owner/Admin) متاحة فقط لحسابات وليد ويعقوب وأحمد"}, 403)
            pwd_error = validate_new_password(str(data.get("password") or ""), str(data.get("username") or ""))
            if pwd_error:
                return self.send_json({"ok": False, "error": pwd_error}, 400)
            email_val = str(data.get("email") or "").strip() or None
            row = {
                "id": data.get("id") or uid("USR"), "username": username, "name": data["name"].strip(),
                "role": role_value or "viewer", "active": as_flag(data.get("active"), True), "email": email_val,
                "must_change_password": as_flag(data.get("must_change_password"), True),
                "password_hash": password_hash(str(data["password"])),
                "password_changed_at": None, "created_at": now_iso(), "last_login": None,
            }
            insert(db, "users", row)
            audit(db, user, "create", "users", row["id"], f"Created user {row['username']}")
            db.commit()
            row.pop("password_hash", None)
            return self.send_json({"ok": True, "item": row})
        if not item_id:
            return self.send_json({"ok": False, "error": "Missing id"}, 400)
        current = db.execute("SELECT * FROM users WHERE id=?", (item_id,)).fetchone()
        if not current:
            return self.send_json({"ok": False, "error": "User not found"}, 404)
        username = str(data.get("username", current["username"]) or current["username"]).strip().lower()
        role_value = str(data.get("role", current["role"]) or current["role"]).strip().lower()
        if role_value in ("owner", "admin") and username not in FULL_ACCESS_USERNAMES:
            return self.send_json({"ok": False, "error": "صلاحية كاملة (Owner/Admin) متاحة فقط لحسابات وليد ويعقوب وأحمد"}, 403)
        fields = {
            "username": username,
            "name": str(data.get("name", current["name"]) or current["name"]).strip(),
            "role": role_value or "viewer",
            "active": as_flag(data.get("active"), bool(current["active"])),
            "email": str(data.get("email", current["email"]) or "").strip() or None,
            "must_change_password": as_flag(data.get("must_change_password"), bool(current["must_change_password"])),
        }
        db.execute(
            "UPDATE users SET username=?,name=?,role=?,active=?,email=?,must_change_password=? WHERE id=?",
            (fields["username"], fields["name"], fields["role"], fields["active"], fields["email"], fields["must_change_password"], item_id),
        )
        if data.get("password"):
            pwd_error = validate_new_password(str(data.get("password") or ""), str(fields.get("username") or ""))
            if pwd_error:
                return self.send_json({"ok": False, "error": pwd_error}, 400)
            db.execute(
                "UPDATE users SET password_hash=?, password_changed_at=?, must_change_password=? WHERE id=?",
                (password_hash(str(data["password"])), now_iso(), as_flag(data.get("must_change_password"), True), item_id),
            )
        audit(db, user, "update", "users", item_id, f"Updated user {fields['username']}")
        db.commit()
        return self.send_json({"ok": True})

    def save_generic(self, db: sqlite3.Connection, user: Dict[str, Any], table: str, data: Dict[str, Any], item_id: Optional[str], method: str) -> None:
        if table == "audit_log":
            return self.send_json({"ok": False, "error": "سجل التدقيق للقراءة فقط"}, 403)
        row_id = item_id or data.get("id") or uid(table[:3].upper())
        data["id"] = row_id
        actor_name = str(user.get("name") or user.get("username") or "System")
        estate_prev_status = ""
        estate_new_status = ""
        estate_entity_type = ""
        estate_reserved_transition = False
        if method == "PUT" and table in ("estate_properties", "estate_buildings", "estate_apartments", "estate_rooms"):
            pricing_fields = {"base_rent_price", "service_charge", "rent_price", "booking_deposit", "prepaid_amount"}
            touching_pricing = any(field in data for field in pricing_fields)
            pricing_changed = touching_pricing
            if touching_pricing and item_id:
                current_row = db.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
                if current_row:
                    pricing_changed = False
                    for field in pricing_fields:
                        if field not in data:
                            continue
                        try:
                            old_v = round(float(current_row[field] or 0), 3)
                            new_v = round(float(data.get(field) or 0), 3)
                        except Exception:
                            old_v = current_row[field]
                            new_v = data.get(field)
                        if old_v != new_v:
                            pricing_changed = True
                            break
            if pricing_changed and not has_permission(user, "estate_actions_pricing_edit"):
                return self.send_json({"ok": False, "error": "تعديل التسعير العقاري يتطلب صلاحية estate_actions_pricing_edit"}, 403)
        if table == "clients":
            if not str(data.get("name") or "").strip():
                return self.send_json({"ok": False, "error": "اسم العميل مطلوب"}, 400)
            upload = data.get("id_card_upload")
            if isinstance(upload, dict) and (upload.get("image") or upload.get("data") or upload.get("base64")):
                try:
                    file_bytes, content_type = decode_upload_payload(upload)
                    data["id_card_image"] = save_named_image_upload(
                        "client_cards",
                        f"client-{row_id}",
                        file_bytes,
                        content_type,
                        MAX_CLIENT_CARD_BYTES,
                    )
                except ValueError as exc:
                    return self.send_json({"ok": False, "error": str(exc)}, 400)
        if table in ("estate_properties", "estate_buildings", "estate_apartments", "estate_rooms"):
            image_upload = data.get("image_upload")
            if isinstance(image_upload, dict) and (image_upload.get("image") or image_upload.get("data") or image_upload.get("base64")):
                previous_image = None
                if method == "PUT" and item_id:
                    row = db.execute(f"SELECT image FROM {table} WHERE id=?", (item_id,)).fetchone()
                    if row:
                        previous_image = str(row["image"] or "").strip() or None
                try:
                    file_bytes, content_type = decode_upload_payload(image_upload)
                    data["image"] = save_named_image_upload(
                        "estate_images",
                        f"{table}-{row_id}",
                        file_bytes,
                        content_type,
                        MAX_PROPERTY_PHOTO_BYTES,
                    )
                except ValueError as exc:
                    return self.send_json({"ok": False, "error": str(exc)}, 400)
                if previous_image and previous_image != data.get("image") and is_stored_upload_url(previous_image, "estate_images"):
                    delete_upload_file(previous_image, "estate_images")
        if table == "branches":
            if not str(data.get("name") or "").strip() or not str(data.get("code") or "").strip():
                return self.send_json({"ok": False, "error": "رمز الفرع والاسم مطلوبان"}, 400)
            data.setdefault("created_at", now_iso())
            data.setdefault("active", int(bool(data.get("active", True))))
        if table == "contracts":
            status_explicit = "status" in data
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM contracts WHERE id=?", (item_id,)).fetchone()
                if current:
                    merged = dict(current)
                    merged.update(data)
                    data = merged
                    current_status = str(current["status"] or "").strip().lower()
                    if current_status in CONTRACT_EDIT_LOCK_STATUSES:
                        changed_core = []
                        for fld in CONTRACT_CORE_FIELDS:
                            if str(current[fld] or "") != str(data.get(fld) or ""):
                                changed_core.append(fld)
                        if changed_core and user.get("role") not in ("owner", "admin"):
                            return self.send_json({"ok": False, "error": "لا يمكن تعديل بيانات العقد الأساسية بعد الاعتماد إلا بصلاحية خاصة"}, 403)
            if not data.get("property_id") or not data.get("client_id") or float(data.get("rent_amount") or 0) <= 0:
                return self.send_json({"ok": False, "error": "اختر العقار والعميل وأدخل مبلغ إيجار أكبر من صفر"}, 400)
            if not exists(db, "properties", data["property_id"]) or not exists(db, "clients", data["client_id"]):
                return self.send_json({"ok": False, "error": "العقار أو العميل غير موجود — أضفهما أولاً ثم أعد المحاولة"}, 400)
            try:
                start_d = datetime.fromisoformat(str(data.get("start_date") or "")).date()
                end_d = datetime.fromisoformat(str(data.get("end_date") or "")).date()
            except Exception:
                return self.send_json({"ok": False, "error": "تاريخ البداية/النهاية غير صحيح"}, 400)
            if end_d < start_d:
                return self.send_json({"ok": False, "error": "لا يمكن أن يكون تاريخ نهاية العقد قبل البداية"}, 400)
            prop_row = db.execute("SELECT status FROM properties WHERE id=?", (str(data["property_id"]),)).fetchone()
            if not prop_row:
                return self.send_json({"ok": False, "error": "العقار غير موجود"}, 400)
            if property_status_blocks_rental(prop_row["status"]):
                return self.send_json({"ok": False, "error": "لا يمكن تأجير أو تفعيل عقد لوحدة تحت الصيانة أو موقوفة"}, 400)
            conflict = conflicting_contract_for_property(
                db,
                str(data["property_id"]),
                str(data.get("start_date") or ""),
                str(data.get("end_date") or ""),
                str(item_id or ""),
            )
            if conflict:
                return self.send_json(
                    {
                        "ok": False,
                        "error": f"يوجد تعارض مع عقد نشط {conflict.get('contract_no') or conflict.get('id')} للفترة {conflict.get('start_date')} - {conflict.get('end_date')}",
                    },
                    400,
                )
            requested_status = str(data.get("status") or "Draft").strip().lower()
            if status_explicit and requested_status in ("active", "activated"):
                return self.send_json({"ok": False, "error": "تفعيل العقد يتم فقط عبر إجراء «تفعيل العقد»"}, 400)
            if requested_status == "approved" and user.get("role") not in ("owner", "admin", "accountant"):
                return self.send_json({"ok": False, "error": "اعتماد العقد محصور بحسابات الاعتماد"}, 403)
            data.setdefault("contract_type", "Residential")
            data.setdefault("contract_no", next_contract_no(db, data.get("contract_type") or "Residential"))
            data["deposit_amount"] = 0
            data.setdefault("late_fee", 0)
            data.setdefault("grace_days", 5)
            data.setdefault("renewal_notice_days", 30)
            data.setdefault("payment_cycle", "monthly")
            data.setdefault("status", "Draft")
            data.setdefault("legal_terms", default_legal_terms())
            data.setdefault("company_signatory", COMPANY_NAME)
            data.setdefault("attachments", "[]")
            uploads = data.get("attachments_upload")
            if isinstance(uploads, list) and uploads:
                stored_attachments: List[Dict[str, str]] = []
                for file_item in uploads[:8]:
                    if not isinstance(file_item, dict):
                        continue
                    file_bytes, content_type = decode_upload_payload(file_item)
                    stored = save_contract_attachment(
                        row_id,
                        file_bytes,
                        content_type,
                        str(file_item.get("name") or "contract-attachment"),
                    )
                    stored["uploaded_by"] = user.get("username") or user.get("name") or "system"
                    stored_attachments.append(stored)
                if stored_attachments:
                    data["attachments"] = json.dumps(stored_attachments, ensure_ascii=False)
            if method in ("POST", "PUT") and "deposit_received" in data:
                normalize_deposit_fields(data)
        if table == "properties":
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM properties WHERE id=?", (item_id,)).fetchone()
                if current:
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            prepared, err = prepare_property_payload(data)
            if err:
                return self.send_json({"ok": False, "error": err}, 400)
            data.update(prepared)
        if table == "estate_properties":
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_properties WHERE id=?", (item_id,)).fetchone()
                if current:
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            if not str(data.get("name") or "").strip():
                return self.send_json({"ok": False, "error": "اسم العقار مطلوب"}, 400)
            status_map = {"active": "active", "نشط": "active", "inactive": "inactive", "غير نشط": "inactive", "suspended": "suspended", "موقوف": "suspended", "موقوفة": "suspended"}
            raw_status = str(data.get("status") or "active").strip().lower()
            data["status"] = status_map.get(raw_status, "active")
            data["building_count"] = int(float(data.get("building_count") or 0))
            data["apartment_count"] = int(float(data.get("apartment_count") or 0))
            data["room_count"] = int(float(data.get("room_count") or 0))
            if data["building_count"] < 0 or data["apartment_count"] < 0 or data["room_count"] < 0:
                return self.send_json({"ok": False, "error": "أعداد العقار لا يمكن أن تكون سالبة"}, 400)
            data["base_rent_price"] = round(float(data.get("base_rent_price") or 0), 3)
            data["service_charge"] = round(float(data.get("service_charge") or 0), 3)
            if data["base_rent_price"] < 0 or data["service_charge"] < 0:
                return self.send_json({"ok": False, "error": "الأسعار ورسوم الخدمة يجب أن تكون موجبة أو صفر"}, 400)
        if table == "estate_buildings":
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_buildings WHERE id=?", (item_id,)).fetchone()
                if current:
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            prop_id = str(data.get("property_id") or "").strip()
            if not prop_id or not exists(db, "estate_properties", prop_id):
                return self.send_json({"ok": False, "error": "اختر العقار الصحيح للبناية"}, 400)
            if not str(data.get("name") or "").strip():
                return self.send_json({"ok": False, "error": "اسم/رقم البناية مطلوب"}, 400)
            status_map = {"active": "active", "نشط": "active", "inactive": "inactive", "غير نشط": "inactive", "suspended": "suspended", "موقوف": "suspended", "موقوفة": "suspended"}
            raw_status = str(data.get("status") or "active").strip().lower()
            data["status"] = status_map.get(raw_status, "active")
            data["property_id"] = prop_id
            data["apartment_count"] = int(float(data.get("apartment_count") or 0))
            data["room_count"] = int(float(data.get("room_count") or 0))
            if data["apartment_count"] < 0 or data["room_count"] < 0:
                return self.send_json({"ok": False, "error": "أعداد البناية لا يمكن أن تكون سالبة"}, 400)
            data["unit_count"] = int(float(data.get("unit_count") or (data["apartment_count"] + data["room_count"])))
            if data["unit_count"] < 0:
                return self.send_json({"ok": False, "error": "عدد الوحدات لا يمكن أن يكون سالبًا"}, 400)
            data["description"] = str(data.get("description") or data.get("notes") or "").strip() or None
            data["base_rent_price"] = round(float(data.get("base_rent_price") or 0), 3)
            data["service_charge"] = round(float(data.get("service_charge") or 0), 3)
            if data["base_rent_price"] < 0 or data["service_charge"] < 0:
                return self.send_json({"ok": False, "error": "الأسعار ورسوم الخدمة غير صحيحة"}, 400)
        if table == "estate_apartments":
            estate_entity_type = "apartment"
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_apartments WHERE id=?", (item_id,)).fetchone()
                if current:
                    estate_prev_status = str(current["status"] or "")
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            prop_id = str(data.get("property_id") or "").strip()
            bld_id = str(data.get("building_id") or "").strip()
            if not prop_id or not exists(db, "estate_properties", prop_id):
                return self.send_json({"ok": False, "error": "اختر العقار أولاً"}, 400)
            if not bld_id:
                return self.send_json({"ok": False, "error": "اختر البناية أولاً"}, 400)
            bld = db.execute("SELECT id, property_id FROM estate_buildings WHERE id=?", (bld_id,)).fetchone()
            if not bld:
                return self.send_json({"ok": False, "error": "البناية غير موجودة"}, 400)
            if str(bld["property_id"] or "") != prop_id:
                return self.send_json({"ok": False, "error": "البناية لا تتبع العقار المحدد"}, 400)
            status_map = {
                "draft": "draft",
                "مسودة": "draft",
                "vacant": "vacant",
                "empty": "vacant",
                "فارغة": "vacant",
                "شاغرة": "vacant",
                "occupied": "occupied",
                "rented": "occupied",
                "مؤجرة": "occupied",
                "maintenance": "maintenance",
                "صيانة": "maintenance",
                "تحت الصيانة": "maintenance",
                "reserved": "reserved",
                "محجوزة": "reserved",
                "محجوز": "reserved",
                "suspended": "suspended",
                "موقوفة": "suspended",
                "موقوف": "suspended",
            }
            raw_status = str(data.get("status") or "vacant").strip().lower()
            status_norm = status_map.get(raw_status)
            if not status_norm:
                return self.send_json({"ok": False, "error": "حالة الشقة غير معتمدة. المسموح: شاغرة/محجوزة/مؤجرة/تحت الصيانة/موقوفة"}, 400)
            data["status"] = status_norm
            data["property_id"] = prop_id
            data["building_id"] = bld_id
            data["unit_kind"] = "شقة كاملة"
            if not str(data.get("name") or "").strip():
                return self.send_json({"ok": False, "error": "اسم/رقم الشقة مطلوب"}, 400)
            data["room_count"] = int(float(data.get("room_count") or 0))
            if data["room_count"] < 0:
                return self.send_json({"ok": False, "error": "عدد الغرف لا يمكن أن يكون سالبًا"}, 400)
            floor_raw = str(data.get("floor_no") or "").strip()
            data["floor_no"] = int(float(floor_raw)) if floor_raw else None
            data["area_sqm"] = round(float(data.get("area_sqm") or 0), 3)
            if data["area_sqm"] < 0:
                return self.send_json({"ok": False, "error": "المساحة يجب أن تكون موجبة أو صفر"}, 400)
            data["rent_price"] = round(float(data.get("rent_price") or 0), 3)
            data["booking_deposit"] = round(float(data.get("booking_deposit") or 0), 3)
            data["prepaid_amount"] = round(float(data.get("prepaid_amount") or 0), 3)
            data["maintenance_cost"] = round(float(data.get("maintenance_cost") or 0), 3)
            if data["rent_price"] < 0 or data["booking_deposit"] < 0 or data["prepaid_amount"] < 0 or data["maintenance_cost"] < 0:
                return self.send_json({"ok": False, "error": "الأسعار والتأمين والمدفوع مقدمًا يجب أن تكون أرقامًا موجبة أو صفر"}, 400)
            if status_norm == "reserved":
                if data["booking_deposit"] <= 0:
                    return self.send_json({"ok": False, "error": "في حالة الحجز يجب إدخال تأمين الحجز"}, 400)
                if data["prepaid_amount"] < 0:
                    return self.send_json({"ok": False, "error": "المدفوع مقدمًا غير صحيح"}, 400)
                start_date = str(data.get("reservation_start_date") or "").strip()
                end_date = str(data.get("reservation_end_date") or "").strip()
                if not start_date or not end_date:
                    return self.send_json({"ok": False, "error": "الحجز يتطلب تاريخ بداية ونهاية"}, 400)
                try:
                    sdt = datetime.fromisoformat(start_date).date()
                    edt = datetime.fromisoformat(end_date).date()
                except Exception:
                    return self.send_json({"ok": False, "error": "تواريخ الحجز غير صحيحة"}, 400)
                if edt < sdt:
                    return self.send_json({"ok": False, "error": "تاريخ نهاية الحجز يجب أن يكون بعد البداية"}, 400)
                booked_name = str(data.get("booked_client_name") or "").strip()
                booked_phone = str(data.get("booked_client_phone") or "").strip()
                booked_employee = str(data.get("booked_by_employee") or "").strip()
                if not booked_name or not booked_phone or not booked_employee:
                    return self.send_json({"ok": False, "error": "حالة محجوزة تتطلب اسم العميل وهاتفه واسم الموظف الذي حجز"}, 400)
                booked_client_id = str(data.get("booked_client_id") or "").strip()
                if booked_client_id and not exists(db, "clients", booked_client_id):
                    return self.send_json({"ok": False, "error": "معرف العميل المحجوز له غير موجود"}, 400)
                estate_reserved_transition = method == "POST" or estate_prev_status.lower() != "reserved"
            if status_norm == "maintenance":
                if not str(data.get("maintenance_notes") or "").strip():
                    return self.send_json({"ok": False, "error": "حالة الصيانة تتطلب وصف أعمال الصيانة"}, 400)
            if status_norm != "reserved":
                data["booked_client_name"] = str(data.get("booked_client_name") or "").strip() or None
                data["booked_client_phone"] = str(data.get("booked_client_phone") or "").strip() or None
                data["booked_client_id"] = str(data.get("booked_client_id") or "").strip() or None
                data["booked_by_employee"] = str(data.get("booked_by_employee") or "").strip() or None
                data["reservation_start_date"] = None
                data["reservation_end_date"] = None
            if status_norm != "maintenance":
                data["maintenance_notes"] = str(data.get("maintenance_notes") or "").strip() or None
            estate_new_status = status_norm
        if table == "estate_rooms":
            estate_entity_type = "room"
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_rooms WHERE id=?", (item_id,)).fetchone()
                if current:
                    estate_prev_status = str(current["status"] or "")
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            prop_id = str(data.get("property_id") or "").strip()
            bld_id = str(data.get("building_id") or "").strip()
            apt_id = str(data.get("apartment_id") or "").strip()
            if not prop_id or not exists(db, "estate_properties", prop_id):
                return self.send_json({"ok": False, "error": "اختر العقار الصحيح للغرفة"}, 400)
            bld = db.execute("SELECT id, property_id FROM estate_buildings WHERE id=?", (bld_id,)).fetchone() if bld_id else None
            if not bld:
                return self.send_json({"ok": False, "error": "اختر البناية الصحيحة للغرفة"}, 400)
            if str(bld["property_id"] or "") != prop_id:
                return self.send_json({"ok": False, "error": "البناية لا تتبع العقار المحدد"}, 400)
            apt = db.execute("SELECT id, property_id, building_id FROM estate_apartments WHERE id=?", (apt_id,)).fetchone() if apt_id else None
            if apt_id and not apt:
                return self.send_json({"ok": False, "error": "الشقة المحددة غير موجودة"}, 400)
            if apt and (str(apt["property_id"] or "") != prop_id or str(apt["building_id"] or "") != bld_id):
                return self.send_json({"ok": False, "error": "الشقة لا تتبع نفس العقار/البناية"}, 400)
            if not str(data.get("name") or "").strip():
                return self.send_json({"ok": False, "error": "اسم/رقم الغرفة مطلوب"}, 400)
            status_map = {
                "draft": "draft", "مسودة": "draft",
                "vacant": "vacant", "فارغة": "vacant", "شاغرة": "vacant",
                "occupied": "occupied", "مؤجرة": "occupied", "rented": "occupied",
                "maintenance": "maintenance", "صيانة": "maintenance", "تحت الصيانة": "maintenance",
                "reserved": "reserved", "محجوزة": "reserved", "محجوز": "reserved",
                "suspended": "suspended", "موقوفة": "suspended", "موقوف": "suspended",
            }
            raw_status = str(data.get("status") or "vacant").strip().lower()
            status_norm = status_map.get(raw_status)
            if not status_norm:
                return self.send_json({"ok": False, "error": "حالة الغرفة غير معتمدة. المسموح: شاغرة/محجوزة/مؤجرة/تحت الصيانة/موقوفة"}, 400)
            data["status"] = status_norm
            data["property_id"] = prop_id
            data["building_id"] = bld_id
            data["apartment_id"] = apt_id or None
            data["unit_kind"] = "غرفة مستقلة"
            floor_raw = str(data.get("floor_no") or "").strip()
            data["floor_no"] = int(float(floor_raw)) if floor_raw else None
            data["area_sqm"] = round(float(data.get("area_sqm") or 0), 3)
            if data["area_sqm"] < 0:
                return self.send_json({"ok": False, "error": "المساحة يجب أن تكون موجبة أو صفر"}, 400)
            data["rent_price"] = round(float(data.get("rent_price") or 0), 3)
            data["booking_deposit"] = round(float(data.get("booking_deposit") or 0), 3)
            data["prepaid_amount"] = round(float(data.get("prepaid_amount") or 0), 3)
            data["maintenance_cost"] = round(float(data.get("maintenance_cost") or 0), 3)
            if data["rent_price"] < 0 or data["booking_deposit"] < 0 or data["prepaid_amount"] < 0 or data["maintenance_cost"] < 0:
                return self.send_json({"ok": False, "error": "قيم الأسعار/التأمين/المقدم/الصيانة غير صحيحة"}, 400)
            if status_norm == "reserved":
                booked_name = str(data.get("booked_client_name") or "").strip()
                booked_phone = str(data.get("booked_client_phone") or "").strip()
                booked_employee = str(data.get("booked_by_employee") or "").strip()
                start_date = str(data.get("reservation_start_date") or "").strip()
                end_date = str(data.get("reservation_end_date") or "").strip()
                if not start_date or not end_date:
                    return self.send_json({"ok": False, "error": "حجز الغرفة يتطلب تاريخ بداية ونهاية"}, 400)
                try:
                    sdt = datetime.fromisoformat(start_date).date()
                    edt = datetime.fromisoformat(end_date).date()
                except Exception:
                    return self.send_json({"ok": False, "error": "تواريخ حجز الغرفة غير صحيحة"}, 400)
                if edt < sdt:
                    return self.send_json({"ok": False, "error": "نهاية الحجز يجب أن تكون بعد بدايته"}, 400)
                if data["booking_deposit"] <= 0 or not booked_name or not booked_phone or not booked_employee:
                    return self.send_json({"ok": False, "error": "الغرفة المحجوزة تتطلب التأمين + بيانات العميل + الموظف الحاجز"}, 400)
                booked_client_id = str(data.get("booked_client_id") or "").strip()
                if booked_client_id and not exists(db, "clients", booked_client_id):
                    return self.send_json({"ok": False, "error": "معرف العميل المحجوز له غير موجود"}, 400)
                estate_reserved_transition = method == "POST" or estate_prev_status.lower() != "reserved"
            if status_norm == "maintenance":
                if not str(data.get("maintenance_notes") or "").strip():
                    return self.send_json({"ok": False, "error": "حالة صيانة الغرفة تتطلب تفاصيل الصيانة"}, 400)
            if status_norm != "reserved":
                data["booked_client_name"] = None
                data["booked_client_phone"] = None
                data["booked_client_id"] = None
                data["booked_by_employee"] = None
                data["reservation_start_date"] = None
                data["reservation_end_date"] = None
            if status_norm != "maintenance":
                data["maintenance_notes"] = None
            estate_new_status = status_norm
        if table == "estate_accessories":
            estate_entity_type = "accessory"
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_accessories WHERE id=?", (item_id,)).fetchone()
                if current:
                    estate_prev_status = str(current["status"] or "")
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            prop_id = str(data.get("property_id") or "").strip()
            bld_id = str(data.get("building_id") or "").strip()
            apt_id = str(data.get("apartment_id") or "").strip()
            room_id = str(data.get("room_id") or "").strip()
            if not prop_id or not exists(db, "estate_properties", prop_id):
                return self.send_json({"ok": False, "error": "اختر العقار الصحيح للملحق"}, 400)
            if bld_id:
                bld = db.execute("SELECT id, property_id FROM estate_buildings WHERE id=?", (bld_id,)).fetchone()
                if not bld:
                    return self.send_json({"ok": False, "error": "البناية المحددة للملحق غير موجودة"}, 400)
                if str(bld["property_id"] or "") != prop_id:
                    return self.send_json({"ok": False, "error": "البناية لا تتبع العقار المحدد"}, 400)
            if apt_id:
                apt = db.execute("SELECT id, property_id, building_id FROM estate_apartments WHERE id=?", (apt_id,)).fetchone()
                if not apt:
                    return self.send_json({"ok": False, "error": "الشقة المحددة للملحق غير موجودة"}, 400)
                if str(apt["property_id"] or "") != prop_id:
                    return self.send_json({"ok": False, "error": "الشقة لا تتبع العقار المحدد"}, 400)
                if bld_id and str(apt["building_id"] or "") != bld_id:
                    return self.send_json({"ok": False, "error": "الشقة لا تتبع البناية المحددة"}, 400)
            if room_id:
                room = db.execute("SELECT id, property_id, building_id, apartment_id FROM estate_rooms WHERE id=?", (room_id,)).fetchone()
                if not room:
                    return self.send_json({"ok": False, "error": "الغرفة المحددة للملحق غير موجودة"}, 400)
                if str(room["property_id"] or "") != prop_id:
                    return self.send_json({"ok": False, "error": "الغرفة لا تتبع العقار المحدد"}, 400)
                if bld_id and str(room["building_id"] or "") != bld_id:
                    return self.send_json({"ok": False, "error": "الغرفة لا تتبع البناية المحددة"}, 400)
                if apt_id and str(room["apartment_id"] or "") != apt_id:
                    return self.send_json({"ok": False, "error": "الغرفة لا تتبع الشقة المحددة"}, 400)
            if not str(data.get("name") or "").strip():
                return self.send_json({"ok": False, "error": "اسم الملحق مطلوب"}, 400)
            status_map = {
                "available": "available", "متاح": "available", "جاهز": "available",
                "installed": "installed", "مركب": "installed",
                "maintenance": "maintenance", "صيانة": "maintenance", "تحت الصيانة": "maintenance",
                "retired": "retired", "موقوف": "retired", "ملغى": "retired",
            }
            raw_status = str(data.get("status") or "available").strip().lower()
            status_norm = status_map.get(raw_status)
            if not status_norm:
                return self.send_json({"ok": False, "error": "حالة الملحق غير معتمدة"}, 400)
            data["status"] = status_norm
            data["property_id"] = prop_id
            data["building_id"] = bld_id or None
            data["apartment_id"] = apt_id or None
            data["room_id"] = room_id or None
            data["qty"] = int(float(data.get("qty") or 1))
            data["unit_cost"] = round(float(data.get("unit_cost") or 0), 3)
            if data["qty"] <= 0:
                return self.send_json({"ok": False, "error": "كمية الملحق يجب أن تكون أكبر من صفر"}, 400)
            if data["unit_cost"] < 0:
                return self.send_json({"ok": False, "error": "تكلفة الملحق يجب أن تكون موجبة أو صفر"}, 400)
            estate_new_status = status_norm
        if table == "estate_maintenance":
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_maintenance WHERE id=?", (item_id,)).fetchone()
                if current:
                    merged = dict(current)
                    merged.update(data)
                    data = merged
            if not str(data.get("title") or "").strip():
                return self.send_json({"ok": False, "error": "عنوان طلب الصيانة مطلوب"}, 400)
            status_raw = str(data.get("status") or "Open").strip().lower()
            status_map = {
                "open": "Open",
                "in progress": "In Progress",
                "closed": "Closed",
            }
            data["status"] = status_map.get(status_raw, "Open")
            data.setdefault("priority", "Medium")
            data["parts_cost"] = round(float(data.get("parts_cost") or 0), 3)
            data["labor_cost"] = round(float(data.get("labor_cost") or 0), 3)
            data["total_cost"] = round(float(data.get("total_cost") or 0), 3)
            if data["parts_cost"] < 0 or data["labor_cost"] < 0 or data["total_cost"] < 0:
                return self.send_json({"ok": False, "error": "تكاليف الصيانة يجب أن تكون موجبة أو صفر"}, 400)
            if data["total_cost"] <= 0:
                data["total_cost"] = round(data["parts_cost"] + data["labor_cost"], 3)
            for f_name, t_name in [("property_id", "estate_properties"), ("building_id", "estate_buildings"), ("apartment_id", "estate_apartments"), ("room_id", "estate_rooms")]:
                val_id = str(data.get(f_name) or "").strip()
                if val_id and not exists(db, t_name, val_id):
                    return self.send_json({"ok": False, "error": f"المعرف المرتبط بـ {f_name} غير موجود"}, 400)
            if not str(data.get("maintenance_date") or "").strip():
                data["maintenance_date"] = today()
            if data["status"] == "Closed" and not str(data.get("closed_at") or "").strip():
                data["closed_at"] = now_iso()
        if table == "estate_contracts":
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM estate_contracts WHERE id=?", (item_id,)).fetchone()
                if not current:
                    return self.send_json({"ok": False, "error": "العقد غير موجود"}, 404)
                merged = dict(current)
                merged.update(data)
                data = merged
                if str(current["status"] or "").strip().lower() in ("approved", "active"):
                    locked = {"entity_type", "entity_id", "property_id", "building_id", "apartment_id", "room_id", "client_id", "start_date", "end_date", "rent_amount", "payment_cycle", "contract_no"}
                    changed_locked = [k for k in locked if str(current[k] or "") != str(data.get(k) or "")]
                    if changed_locked and user.get("role") not in ("owner", "admin"):
                        return self.send_json({"ok": False, "error": "لا يمكن تعديل بيانات العقد الأساسية بعد الاعتماد إلا للمالك/الإدارة"}, 403)
            if method == "POST":
                required = ["entity_type", "entity_id", "client_id", "start_date", "end_date", "rent_amount"]
                missing = [k for k in required if not str(data.get(k) or "").strip()]
                if missing:
                    return self.send_json({"ok": False, "error": f"بيانات العقد ناقصة: {', '.join(missing)}"}, 400)
                data.setdefault("contract_no", next_estate_contract_no(db))
                data.setdefault("status", "Draft")
                data.setdefault("payment_cycle", "monthly")
                data.setdefault("created_by", actor_name)
                data.setdefault("created_at", now_iso())
                data.setdefault("attachments", "[]")
            data["rent_amount"] = round(float(data.get("rent_amount") or 0), 3)
            if data["rent_amount"] <= 0:
                return self.send_json({"ok": False, "error": "قيمة الإيجار يجب أن تكون أكبر من صفر"}, 400)
            try:
                sd = datetime.fromisoformat(str(data.get("start_date") or "")).date()
                ed = datetime.fromisoformat(str(data.get("end_date") or "")).date()
            except Exception:
                return self.send_json({"ok": False, "error": "تواريخ العقد غير صحيحة"}, 400)
            if ed < sd:
                return self.send_json({"ok": False, "error": "تاريخ نهاية العقد يجب أن يكون بعد البداية"}, 400)
            cycle = str(data.get("payment_cycle") or "monthly").strip().lower()
            if cycle not in ("monthly", "quarterly", "yearly", "once"):
                cycle = "monthly"
            data["payment_cycle"] = cycle
            if str(data.get("entity_type") or "").strip().lower() not in ("apartment", "room"):
                return self.send_json({"ok": False, "error": "entity_type يجب أن يكون apartment أو room"}, 400)
            if not exists(db, "clients", str(data.get("client_id") or "").strip()):
                return self.send_json({"ok": False, "error": "العميل غير موجود"}, 400)
            et = str(data.get("entity_type") or "").strip().lower()
            eid = str(data.get("entity_id") or "").strip()
            src_table = "estate_apartments" if et == "apartment" else "estate_rooms"
            if not exists(db, src_table, eid):
                return self.send_json({"ok": False, "error": "العنصر المرتبط بالعقد غير موجود"}, 400)
            unit_row = db.execute(f"SELECT status FROM {src_table} WHERE id=?", (eid,)).fetchone()
            if not unit_row:
                return self.send_json({"ok": False, "error": "الوحدة المرتبطة بالعقد غير موجودة"}, 400)
            if estate_unit_status_blocks_contract(unit_row["status"]):
                return self.send_json({"ok": False, "error": "لا يمكن إنشاء أو تفعيل عقد لوحدة تحت الصيانة أو موقوفة"}, 400)
            conflict = conflicting_active_estate_contract(
                db,
                et,
                eid,
                str(data.get("start_date") or ""),
                str(data.get("end_date") or ""),
                str(item_id or ""),
            )
            if conflict:
                return self.send_json(
                    {
                        "ok": False,
                        "error": f"يوجد عقد متعارض {conflict.get('contract_no') or conflict.get('id')} للفترة {conflict.get('start_date')} - {conflict.get('end_date')}",
                    },
                    400,
                )
            raw_status = str(data.get("status") or "Draft").strip().lower()
            status_map = {
                "draft": "Draft",
                "مسودة": "Draft",
                "approvalrequested": "ApprovalRequested",
                "طلب اعتماد": "ApprovalRequested",
                "approved": "Approved",
                "معتمد": "Approved",
                "active": "Active",
                "مفعل": "Active",
                "activated": "Active",
                "ended": "Ended",
                "منتهي": "Ended",
                "cancelled": "Cancelled",
                "canceled": "Cancelled",
                "ملغى": "Cancelled",
            }
            normalized_status = status_map.get(raw_status)
            if not normalized_status:
                return self.send_json({"ok": False, "error": "حالة العقد غير معتمدة"}, 400)
            if normalized_status == "Active":
                return self.send_json({"ok": False, "error": "تفعيل العقد يتم فقط عبر إجراء «تفعيل العقد» بعد الاعتماد"}, 400)
            data["status"] = normalized_status
        if table == "estate_contract_invoices":
            return self.send_json({"ok": False, "error": "فواتير العقود تُدار عبر محرك الجدولة والتحصيل فقط"}, 403)
        if table == "accounting_budgets":
            month_key = str(data.get("month_key") or "").strip()
            try:
                if len(month_key) != 7:
                    raise ValueError("invalid")
                _ = datetime.fromisoformat(month_key + "-01").date()
            except Exception:
                return self.send_json({"ok": False, "error": "month_key يجب أن يكون بصيغة YYYY-MM"}, 400)
            data["month_key"] = month_key
            data["revenue_target"] = round(float(data.get("revenue_target") or 0), 3)
            data["expense_budget"] = round(float(data.get("expense_budget") or 0), 3)
            data["collection_target"] = round(float(data.get("collection_target") or 0), 3)
            data["cash_reserve_target"] = round(float(data.get("cash_reserve_target") or 0), 3)
            if data["revenue_target"] < 0 or data["expense_budget"] < 0 or data["collection_target"] < 0 or data["cash_reserve_target"] < 0:
                return self.send_json({"ok": False, "error": "قيم الأهداف يجب أن تكون موجبة أو صفر"}, 400)
            if method == "POST":
                data.setdefault("created_at", now_iso())
            data["updated_at"] = now_iso()
        if table == "invoices":
            return self.send_json({"ok": False, "error": "الفاتورة تُنشأ من العقد — من قائمة العقود اضغط «فاتورة» أو اعتمد العقد لتوليد الجدول"}, 400)
        if table == "payments":
            return self.send_json({"ok": False, "error": "Create payments from an invoice using the payment action"}, 400)
        if table == "accounts" and float(data.get("amount") or 0) <= 0:
            return self.send_json({"ok": False, "error": "Account entry requires positive amount"}, 400)
        if table == "purchase_invoices":
            data.setdefault("purchase_no", next_purchase_no(db))
            data.setdefault("invoice_date", today())
            data.setdefault("status", "Pending")
            data.setdefault("paid_amount", 0)
            if float(data.get("amount") or 0) <= 0:
                return self.send_json({"ok": False, "error": "Purchase invoice requires positive amount"}, 400)
            if method == "POST":
                acc_id = uid("ACC")
                insert(db, "accounts", {"id":acc_id,"entry_date":data.get("invoice_date") or today(),"type":"expense","category":data.get("category") or "Purchases","description":f"Purchase invoice {data.get('purchase_no')} - {data.get('supplier')}","client_id":None,"property_id":data.get("property_id"),"invoice_id":None,"amount":float(data.get("amount") or 0)})
                data["account_id"] = acc_id
        if table == "revenues":
            data.setdefault("revenue_no", next_revenue_no(db))
            data.setdefault("revenue_date", today())
            if float(data.get("amount") or 0) <= 0:
                return self.send_json({"ok": False, "error": "Revenue requires positive amount"}, 400)
            if method == "POST":
                acc_id = uid("ACC")
                insert(db, "accounts", {"id":acc_id,"entry_date":data.get("revenue_date") or today(),"type":"income","category":data.get("category") or "Revenue","description":data.get("description") or f"Revenue {data.get('revenue_no')}","client_id":data.get("client_id"),"property_id":data.get("property_id"),"invoice_id":None,"amount":float(data.get("amount") or 0)})
                data["account_id"] = acc_id
        if table == "salaries":
            net = float(data.get("net_salary") or 0) or (float(data.get("basic_salary") or 0) + float(data.get("allowances") or 0) - float(data.get("deductions") or 0))
            data["net_salary"] = net
            data.setdefault("status", "Pending")
            if net <= 0:
                return self.send_json({"ok": False, "error": "Salary net amount must be positive"}, 400)
            if method == "POST":
                acc_id = uid("ACC")
                insert(db, "accounts", {"id":acc_id,"entry_date":data.get("payment_date") or today(),"type":"expense","category":"Payroll","description":f"Salary {data.get('employee_name')} {data.get('salary_month')}","client_id":None,"property_id":None,"invoice_id":None,"amount":net})
                data["account_id"] = acc_id
        if table == "admin_expenses":
            if float(data.get("amount") or 0) <= 0:
                return self.send_json({"ok": False, "error": "Expense requires positive amount"}, 400)
            if method == "POST":
                acc_id = uid("ACC")
                insert(db, "accounts", {"id":acc_id,"entry_date":data.get("expense_date") or today(),"type":"expense","category":data.get("category") or "G&A","description":data.get("description") or "Administrative expense","client_id":None,"property_id":data.get("property_id"),"invoice_id":None,"amount":float(data.get("amount") or 0)})
                data["account_id"] = acc_id
        if table == "inventory_transactions":
            if not exists(db, "inventory_items", data.get("item_id", "")):
                return self.send_json({"ok": False, "error": "Inventory transaction requires valid item"}, 400)
            qty = float(data.get("quantity") or 0)
            if qty <= 0:
                return self.send_json({"ok": False, "error": "Inventory quantity must be positive"}, 400)
            if method == "POST":
                item_row = db.execute(
                    "SELECT id, name, property_id FROM inventory_items WHERE id=?",
                    (data.get("item_id"),),
                ).fetchone()
                sign = 1 if str(data.get("tx_type", "in")).lower() in ("in","purchase","return") else -1
                db.execute("UPDATE inventory_items SET quantity = quantity + ? WHERE id=?", (sign*qty, data.get("item_id")))
                if item_row:
                    tx_cost = float(data.get("unit_cost") or 0) * qty
                    if tx_cost > 0:
                        if sign < 0:
                            insert(
                                db,
                                "accounts",
                                {
                                    "id": uid("ACC"),
                                    "entry_date": data.get("tx_date") or today(),
                                    "type": "expense",
                                    "category": "Property Stock Consumption",
                                    "description": f"Inventory OUT {item_row['name']} ({data.get('item_id')})",
                                    "client_id": None,
                                    "property_id": item_row["property_id"],
                                    "invoice_id": None,
                                    "amount": tx_cost,
                                },
                            )
                        elif str(data.get("tx_type", "in")).lower() in ("purchase", "in"):
                            insert(
                                db,
                                "accounts",
                                {
                                    "id": uid("ACC"),
                                    "entry_date": data.get("tx_date") or today(),
                                    "type": "expense",
                                    "category": "Property Stock In",
                                    "description": f"Inventory IN {item_row['name']} ({data.get('item_id')})",
                                    "client_id": None,
                                    "property_id": item_row["property_id"],
                                    "invoice_id": None,
                                    "amount": tx_cost,
                                },
                            )
        if table == "inventory_items":
            pid = str(data.get("property_id") or "").strip()
            if pid and not exists(db, "properties", pid):
                return self.send_json({"ok": False, "error": "العقار المرتبط بالمخزن غير موجود"}, 400)
            data["property_id"] = pid or None
        if table == "hospitality_rooms":
            room_code = str(data.get("room_code") or "").strip()
            if not room_code:
                return self.send_json({"ok": False, "error": "رقم/رمز الغرفة مطلوب"}, 400)
            pid = str(data.get("property_id") or "").strip()
            if pid and not exists(db, "properties", pid):
                return self.send_json({"ok": False, "error": "العقار المرتبط بالغرفة غير موجود"}, 400)
            data["property_id"] = pid or None
            data["room_code"] = room_code
            data.setdefault("room_type", "Standard")
            data.setdefault("capacity", 2)
            data.setdefault("rate_per_night", 0)
            data.setdefault("status", "available")
        if table == "hospitality_bookings":
            current_row = None
            timeline_change_details = ""
            if method == "PUT" and item_id:
                current_row = db.execute("SELECT * FROM hospitality_bookings WHERE id=?", (item_id,)).fetchone()
                if current_row:
                    merged = dict(current_row)
                    merged.update(data)
                    data = merged
            if method == "PUT" and current_row:
                old_checkin = str(current_row["checkin_date"] or "")
                old_checkout = str(current_row["checkout_date"] or "")
                new_checkin = str(data.get("checkin_date") or old_checkin)
                new_checkout = str(data.get("checkout_date") or old_checkout)
                if (new_checkin != old_checkin or new_checkout != old_checkout) and user.get("role") not in ("owner", "admin", "operations"):
                    return self.send_json({"ok": False, "error": "تعديل فترة الحجز مسموح للمالك/الإدارة/العمليات فقط"}, 403)
                if new_checkin != old_checkin or new_checkout != old_checkout:
                    timeline_change_details = f"{old_checkin}→{new_checkin} | {old_checkout}→{new_checkout}"
            room_id = str(data.get("room_id") or "").strip()
            if not room_id:
                return self.send_json({"ok": False, "error": "اختر الغرفة أولاً"}, 400)
            room = db.execute("SELECT * FROM hospitality_rooms WHERE id=?", (room_id,)).fetchone()
            if not room:
                return self.send_json({"ok": False, "error": "الغرفة غير موجودة"}, 400)
            guest_name = str(data.get("guest_name") or "").strip()
            if not guest_name:
                return self.send_json({"ok": False, "error": "اسم النزيل مطلوب"}, 400)
            checkin = str(data.get("checkin_date") or "").strip()
            checkout = str(data.get("checkout_date") or "").strip()
            if not checkin or not checkout:
                return self.send_json({"ok": False, "error": "تاريخ الدخول والخروج مطلوب"}, 400)
            try:
                in_dt = datetime.fromisoformat(checkin).date()
                out_dt = datetime.fromisoformat(checkout).date()
            except Exception:
                return self.send_json({"ok": False, "error": "تواريخ الحجز غير صحيحة"}, 400)
            nights = max(1, (out_dt - in_dt).days)
            seasonal = seasonal_rate_for_booking(
                db,
                room["property_id"],
                room["room_type"],
                in_dt.isoformat(),
                out_dt.isoformat(),
            )
            rate = float(data.get("rate_per_night") or seasonal or room["rate_per_night"] or 0)
            total = float(data.get("total_amount") or 0) or (rate * nights)
            paid = float(data.get("paid_amount") or 0)
            if total <= 0:
                return self.send_json({"ok": False, "error": "إجمالي الحجز يجب أن يكون أكبر من صفر"}, 400)
            balance = round(total - paid, 3)
            status = str(data.get("status") or "reserved").strip().lower()
            overlap = db.execute(
                """
                SELECT id, guest_name, checkin_date, checkout_date, status
                FROM hospitality_bookings
                WHERE room_id=?
                  AND id != ?
                  AND lower(status) NOT IN ('checked_out','cancelled')
                  AND NOT (date(checkout_date) <= date(?) OR date(checkin_date) >= date(?))
                ORDER BY checkin_date ASC
                LIMIT 1
                """,
                (room_id, str(item_id or ""), in_dt.isoformat(), out_dt.isoformat()),
            ).fetchone()
            if overlap:
                return self.send_json(
                    {
                        "ok": False,
                        "error": f"الغرفة محجوزة بالفعل خلال هذه الفترة (حجز: {overlap['id']} · {overlap['guest_name']})",
                    },
                    400,
                )
            data["room_id"] = room_id
            data["property_id"] = room["property_id"]
            data["guest_name"] = guest_name
            data["checkin_date"] = in_dt.isoformat()
            data["checkout_date"] = out_dt.isoformat()
            data["nights"] = nights
            data["rate_per_night"] = round(rate, 3)
            data["total_amount"] = round(total, 3)
            data["paid_amount"] = round(paid, 3)
            data["balance_amount"] = round(balance, 3)
            data["status"] = status
            data.setdefault("booking_source", "direct")
            data.setdefault("created_at", now_iso())
            if status in ("checked_in", "occupied"):
                db.execute("UPDATE hospitality_rooms SET status='occupied' WHERE id=?", (room_id,))
            elif status in ("checked_out", "cancelled", "closed"):
                db.execute("UPDATE hospitality_rooms SET status='available' WHERE id=?", (room_id,))
            else:
                db.execute("UPDATE hospitality_rooms SET status='reserved' WHERE id=?", (room_id,))
            if method == "POST" and paid > 0:
                insert(
                    db,
                    "accounts",
                    {
                        "id": uid("ACC"),
                        "entry_date": data.get("checkin_date") or today(),
                        "type": "income",
                        "category": "Hospitality Booking",
                        "description": f"Hospitality booking {row_id} - {guest_name}",
                        "client_id": data.get("client_id") or None,
                        "property_id": room["property_id"],
                        "invoice_id": None,
                        "amount": round(paid, 3),
                    },
                )
            if method == "POST":
                folio_id = uid("HFO")
                folio_no = next_hospitality_folio_no(db)
                insert(
                    db,
                    "hospitality_folios",
                    {
                        "id": folio_id,
                        "booking_id": row_id,
                        "folio_no": folio_no,
                        "issue_date": data.get("checkin_date") or today(),
                        "total_amount": round(total, 3),
                        "paid_amount": round(paid, 3),
                        "balance_amount": round(balance, 3),
                        "status": "closed" if balance <= 0 else "open",
                        "notes": data.get("notes"),
                    },
                )
            if method == "PUT" and item_id:
                f = db.execute("SELECT id FROM hospitality_folios WHERE booking_id=? ORDER BY rowid DESC LIMIT 1", (item_id,)).fetchone()
                if f:
                    db.execute(
                        "UPDATE hospitality_folios SET total_amount=?, paid_amount=?, balance_amount=?, status=? WHERE id=?",
                        (round(total, 3), round(paid, 3), round(balance, 3), ("closed" if balance <= 0 else "open"), f["id"]),
                    )
        if table == "hospitality_events":
            if method == "POST":
                return self.send_json(
                    {"ok": False, "error": "استخدم /api/hospitality/event_book لحجز الباقات والعزاء"},
                    400,
                )
            if method == "PUT" and item_id:
                current = db.execute("SELECT * FROM hospitality_events WHERE id=?", (item_id,)).fetchone()
                if current:
                    merged = dict(current)
                    merged.update(data)
                    data = merged
                total = float(data.get("total_amount") or 0)
                paid = float(data.get("paid_amount") or 0)
                data["balance_amount"] = round(max(0.0, total - paid), 3)
                data["total_amount"] = round(total, 3)
                data["paid_amount"] = round(paid, 3)
                data["deposit_required"] = round(float(data.get("deposit_required") or 0), 3)
                data["guests"] = int(data.get("guests") or 0)
                data["outside_nizwa"] = int(bool(data.get("outside_nizwa")))
        if table == "hospitality_season_rates":
            season_name = str(data.get("season_name") or "").strip()
            start_date = str(data.get("start_date") or "").strip()
            end_date = str(data.get("end_date") or "").strip()
            rate = float(data.get("nightly_rate") or 0)
            if not season_name or not start_date or not end_date or rate <= 0:
                return self.send_json({"ok": False, "error": "بيانات الموسم غير مكتملة"}, 400)
            try:
                sdt = datetime.fromisoformat(start_date).date()
                edt = datetime.fromisoformat(end_date).date()
            except Exception:
                return self.send_json({"ok": False, "error": "تواريخ الموسم غير صحيحة"}, 400)
            if edt < sdt:
                return self.send_json({"ok": False, "error": "تاريخ نهاية الموسم يجب أن يكون بعد البداية"}, 400)
            pid = str(data.get("property_id") or "").strip()
            if pid and not exists(db, "properties", pid):
                return self.send_json({"ok": False, "error": "العقار غير موجود"}, 400)
            data["property_id"] = pid or None
            data["season_name"] = season_name
            data["start_date"] = sdt.isoformat()
            data["end_date"] = edt.isoformat()
            data["nightly_rate"] = round(rate, 3)
            data["active"] = int(bool(data.get("active", 1)))
        cols = [c for c in TABLES[table] if c in data]
        clean = {c: data.get(c) for c in cols}
        if method == "POST":
            insert(db, table, clean)
            audit(db, user, "create", table, row_id, "Created record")
            if table in ("estate_apartments", "estate_rooms", "estate_accessories"):
                if not estate_new_status:
                    estate_new_status = str(clean.get("status") or "")
                log_estate_status_history(
                    db,
                    estate_entity_type or ("apartment" if table == "estate_apartments" else ("room" if table == "estate_rooms" else "accessory")),
                    row_id,
                    clean,
                    "",
                    estate_new_status,
                    actor_name,
                    "Initial status on create",
                )
                if table in ("estate_apartments", "estate_rooms") and estate_new_status == "reserved":
                    ensure_estate_reservation_invoice(
                        db,
                        estate_entity_type or ("apartment" if table == "estate_apartments" else "room"),
                        row_id,
                        clean,
                        actor_name,
                    )
                    audit(db, user, "auto_invoice", "estate_reservation_invoices", row_id, f"Auto reservation invoice created for {table}")
            if table == "estate_contracts" and str(clean.get("status") or "").strip().lower() == "active":
                schedule_result = generate_estate_contract_invoices(
                    db,
                    clean,
                    actor_name,
                    replace_open=False,
                )
                audit(
                    db,
                    user,
                    "generate_schedule",
                    "estate_contracts",
                    row_id,
                    f"Auto schedule created={schedule_result.get('created')} skipped={schedule_result.get('skipped')}",
                )
            if table == "contracts":
                sync_property_status_for_contract(db, clean.get("property_id") or "", clean.get("status") or "Draft")
            if table == "contracts" and user.get("role") == "operations":
                create_approval_request(
                    db,
                    "contracts",
                    row_id,
                    "contract",
                    user.get("name") or user.get("username") or "System",
                    "طلب اعتماد عقد جديد من العمليات",
                )
            db.commit()
            return self.send_json({"ok": True, "item": clean})
        else:
            if not item_id:
                return self.send_json({"ok": False, "error": "Missing id"}, 400)
            before_row = None
            if table == "contracts":
                before_row = db.execute("SELECT * FROM contracts WHERE id=?", (item_id,)).fetchone()
            update_cols = [c for c in cols if c != "id"]
            if not update_cols:
                return self.send_json({"ok": True})
            sql = f"UPDATE {table} SET {','.join([c+'=?' for c in update_cols])} WHERE id=?"
            db.execute(sql, [clean[c] for c in update_cols] + [item_id])
            audit_details = "Updated record"
            if table in ("contracts", "estate_contracts") and before_row:
                changed = []
                for fld in update_cols:
                    old_v = before_row[fld] if fld in before_row.keys() else None
                    new_v = clean.get(fld)
                    if str(old_v or "") != str(new_v or ""):
                        changed.append(f"{fld}: {old_v} -> {new_v}")
                if changed:
                    audit_details = " | ".join(changed[:12])
            audit(db, user, "update", table, item_id, audit_details)
            if table in ("estate_apartments", "estate_rooms", "estate_accessories"):
                current_status = str(clean.get("status") or "")
                if not current_status:
                    current_status = estate_new_status
                if current_status and (current_status != estate_prev_status):
                    log_estate_status_history(
                        db,
                        estate_entity_type or ("apartment" if table == "estate_apartments" else ("room" if table == "estate_rooms" else "accessory")),
                        str(item_id),
                        clean,
                        estate_prev_status,
                        current_status,
                        actor_name,
                        "Status changed by update",
                    )
                if table in ("estate_apartments", "estate_rooms") and current_status != "reserved" and estate_prev_status.lower() == "reserved":
                    db.execute(
                        "UPDATE estate_reservation_invoices SET status='Closed', note=COALESCE(note,'') || ' | Closed after status moved to ' || ? WHERE entity_type=? AND entity_id=? AND lower(status)='open'",
                        (current_status, estate_entity_type or ("apartment" if table == "estate_apartments" else "room"), str(item_id)),
                    )
                if table in ("estate_apartments", "estate_rooms") and current_status == "reserved" and estate_reserved_transition:
                    ensure_estate_reservation_invoice(
                        db,
                        estate_entity_type or ("apartment" if table == "estate_apartments" else "room"),
                        str(item_id),
                        clean,
                        actor_name,
                    )
                    audit(db, user, "auto_invoice", "estate_reservation_invoices", str(item_id), f"Auto reservation invoice created for {table}")
            if table == "hospitality_bookings" and timeline_change_details:
                audit(
                    db,
                    user,
                    "timeline_update",
                    "hospitality_bookings",
                    item_id,
                    f"Timeline booking dates changed: {timeline_change_details}",
                )
            if table == "contracts":
                property_id = clean.get("property_id")
                status = clean.get("status")
                if property_id and status:
                    sync_property_status_for_contract(db, property_id, status)
            if table == "estate_contracts":
                status = str(clean.get("status") or "").strip().lower()
                entity_type = str(clean.get("entity_type") or "").strip().lower()
                entity_id = str(clean.get("entity_id") or "").strip()
                if status == "active" and entity_id:
                    set_estate_unit_status(
                        db,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        target_status="occupied",
                        actor_name=actor_name,
                        note="Contract set active by update",
                    )
                if status in ("ended", "cancelled") and entity_id:
                    other_active = db.execute(
                        "SELECT id FROM estate_contracts WHERE lower(entity_type)=lower(?) AND entity_id=? AND lower(status)='active' AND id<>?",
                        (entity_type, entity_id, str(item_id)),
                    ).fetchone()
                    if not other_active:
                        set_estate_unit_status(
                            db,
                            entity_type=entity_type,
                            entity_id=entity_id,
                            target_status="vacant",
                            actor_name=actor_name,
                            note="Contract ended/cancelled by update",
                        )
            db.commit()
            return self.send_json({"ok": True})

    def api_invoice_from_contract(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        policies = load_workflow_policies(db)
        contract_id = data.get("contract_id")
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Contract not found"}, 404)
        contract_status = str(contract["status"] or "").strip().lower()
        if contract_status not in ("active", "activated"):
            return self.send_json({"ok": False, "error": "لا يمكن إصدار فاتورة إلا بعد اعتماد وتفعيل العقد"}, 400)
        due_policy_err = validate_invoice_due_date_by_policy(data.get("due_date"), user, policies)
        if due_policy_err:
            return self.send_json({"ok": False, "error": due_policy_err}, 400)
        if not exists(db, "properties", contract["property_id"]) or not exists(db, "clients", contract["client_id"]):
            return self.send_json({"ok": False, "error": "Contract references missing client/property"}, 400)
        amount = float(data.get("amount") or contract["rent_amount"])
        default_desc = contract_invoice_description(db, contract, data.get("due_date"))
        inv_type = detect_invoice_type(data.get("description") or default_desc, data.get("invoice_type"))
        invoice = build_invoice_row(
            db,
            contract,
            data.get("description") or ("تأمين عقد / Contract deposit" if inv_type == "deposit" else default_desc),
            amount,
            issue_date=data.get("issue_date"),
            due_date=data.get("due_date"),
            invoice_type=inv_type,
        )
        insert(db, "invoices", invoice)
        audit(db, user, "create", "invoices", invoice["id"], f"Invoice {invoice['invoice_no']} from contract {contract_id}")
        db.commit()
        self.send_json({"ok": True, "item": invoice})

    def api_manual_invoice(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        policies = load_workflow_policies(db)
        contract_id = data.get("contract_id")
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Manual invoice requires an existing contract"}, 400)
        contract_status = str(contract["status"] or "").strip().lower()
        if contract_status not in ("active", "activated"):
            return self.send_json({"ok": False, "error": "لا يمكن إصدار فاتورة إلا بعد اعتماد وتفعيل العقد"}, 400)
        due_policy_err = validate_invoice_due_date_by_policy(data.get("due_date"), user, policies)
        if due_policy_err:
            return self.send_json({"ok": False, "error": due_policy_err}, 400)
        amount_value = float(data.get("amount") or 0)
        if amount_value <= 0:
            return self.send_json({"ok": False, "error": "Invoice amount must be positive"}, 400)
        manual_threshold = _workflow_policy_float(policies, "manual_invoice_approval_threshold")
        if amount_value >= manual_threshold and not can_decide_approval(user, "manual_invoice"):
            meta = {
                "contract_id": contract_id,
                "amount": amount_value,
                "description": data.get("description") or "Manual invoice",
                "issue_date": data.get("issue_date"),
                "due_date": data.get("due_date"),
                "invoice_type": data.get("invoice_type"),
            }
            approval_id = create_approval_request(
                db,
                "contracts",
                contract_id,
                "manual_invoice",
                user.get("name") or user.get("username") or "System",
                f"فاتورة يدوية بمبلغ {fmt_omr(amount_value)} تحتاج اعتماد",
                meta=meta,
            )
            audit(db, user, "request_approval", "approvals", approval_id, f"Manual invoice approval {amount_value}")
            db.commit()
            return self.send_json({
                "ok": True,
                "approval_required": True,
                "approval_id": approval_id,
                "message": f"المبلغ {fmt_omr(amount_value)} يحتاج اعتماد المدير/المحاسب قبل إصدار الفاتورة (الحد {fmt_omr(manual_threshold)})",
            })
        inv_type = detect_invoice_type(data.get("description") or "Manual invoice", data.get("invoice_type"))
        invoice = build_invoice_row(
            db,
            contract,
            data.get("description") or "Manual invoice",
            amount_value,
            issue_date=data.get("issue_date"),
            due_date=data.get("due_date"),
            invoice_type=inv_type,
        )
        insert(db, "invoices", invoice)
        audit(db, user, "create", "invoices", invoice["id"], f"Manual invoice {invoice['invoice_no']}")
        db.commit()
        self.send_json({"ok": True, "item": invoice})

    def api_reissue_invoice(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        invoice_id = data.get("invoice_id")
        source = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not source:
            return self.send_json({"ok": False, "error": "Invoice not found"}, 404)
        amount_value = float(data.get("amount") or source["amount"] or 0)
        if amount_value <= 0:
            return self.send_json({"ok": False, "error": "Invoice amount must be positive"}, 400)
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (source["contract_id"],)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Contract not found for invoice"}, 404)
        src = dict(source)
        subtotal = float(src.get("subtotal") or 0)
        if subtotal <= 0:
            grand = float(src.get("amount") or amount_value)
            rate = float(src.get("vat_rate") or VAT_RATE)
            subtotal = round(grand / (1 + rate), 3) if rate > 0 else grand
        invoice = build_invoice_row(
            db,
            contract,
            data.get("description") or f"Reissue of {source['invoice_no']} - {source['description']}",
            subtotal,
            issue_date=data.get("issue_date"),
            due_date=data.get("due_date") or source["due_date"],
            invoice_type=detect_invoice_type(str(source["description"] or ""), source.get("invoice_type")),
            source_invoice_id=invoice_id,
        )
        insert(db, "invoices", invoice)
        audit(db, user, "reissue", "invoices", invoice["id"], f"Reissued {source['invoice_no']} as {invoice['invoice_no']}")
        db.commit()
        self.send_json({"ok": True, "item": invoice, "source_invoice_id": invoice_id})

    def api_pay_invoice(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        policies = load_workflow_policies(db)
        invoice_id = data.get("invoice_id")
        amount = float(data.get("amount") or 0)
        payment_proof_image: Optional[str] = None
        proof_payload = data.get("payment_proof_upload")
        if isinstance(proof_payload, dict) and (proof_payload.get("image") or proof_payload.get("data") or proof_payload.get("base64")):
            try:
                file_bytes, content_type = decode_upload_payload(proof_payload)
                payment_proof_image = save_named_image_upload(
                    "payment_proofs",
                    f"pay-{invoice_id}",
                    file_bytes,
                    content_type,
                    MAX_PAYMENT_PROOF_BYTES,
                )
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            return self.send_json({"ok": False, "error": "Invoice not found"}, 404)
        payment_threshold = _workflow_policy_float(policies, "payment_approval_threshold")
        if amount >= payment_threshold and not can_decide_approval(user, "payment"):
            approval_id = data.get("approval_id")
            if approval_id:
                row = db.execute(
                    "SELECT * FROM approvals WHERE id=? AND lower(status)='approved'",
                    (approval_id,),
                ).fetchone()
                if not row or row["entity_id"] != invoice_id or row["request_type"] != "payment":
                    return self.send_json({"ok": False, "error": "اعتماد التحصيل غير صالح أو غير موجود"}, 400)
            else:
                meta = {
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "method": data.get("method") or "Cash",
                    "note": data.get("note") or "Invoice payment",
                    "payment_date": data.get("payment_date") or today(),
                    "bank_name": data.get("bank_name") or "Main Bank",
                }
                aid = create_approval_request(
                    db,
                    "invoices",
                    invoice_id,
                    "payment",
                    user.get("name") or user.get("username") or "System",
                    f"تحصيل {fmt_omr(amount)} يحتاج اعتماد",
                    meta=meta,
                )
                audit(db, user, "request_approval", "approvals", aid, f"Payment approval {amount}")
                db.commit()
                return self.send_json({
                    "ok": True,
                    "approval_required": True,
                    "approval_id": aid,
                    "message": f"تحصيل {fmt_omr(amount)} يحتاج اعتماد المدير/المحاسب (الحد {fmt_omr(payment_threshold)})",
                })
        try:
            result = execute_invoice_payment(
                db,
                user,
                str(invoice_id),
                amount,
                method=str(data.get("method") or "Cash"),
                note=str(data.get("note") or "Invoice payment"),
                payment_date=data.get("payment_date"),
                bank_name=str(data.get("bank_name") or "Main Bank"),
                payment_proof_image=payment_proof_image,
            )
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        db.commit()
        self.send_json({"ok": True, **result})

    def api_void_invoice(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        invoice_id = data.get("invoice_id")
        reason = str(data.get("reason") or "Cancelled by accountant").strip()
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            return self.send_json({"ok": False, "error": "Invoice not found"}, 404)
        if int(invoice["is_void"] or 0):
            return self.send_json({"ok": False, "error": "Invoice is already void"}, 400)
        if float(invoice["paid_amount"] or 0) > 0:
            return self.send_json({"ok": False, "error": "Cannot void an invoice with payments — use reissue instead"}, 400)
        db.execute(
            "UPDATE invoices SET is_void=1, status='Void', void_reason=?, voided_at=? WHERE id=?",
            (reason, now_iso(), invoice_id),
        )
        audit(db, user, "void", "invoices", invoice_id, f"Void {invoice['invoice_no']}: {reason}")
        db.commit()
        self.send_json({"ok": True, "invoice_id": invoice_id, "status": "Void"})

    def api_audit_feed(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        limit = min(500, max(1, int((params.get("limit") or ["100"])[0] or 100)))
        entity = (params.get("entity") or [""])[0].strip()
        username = (params.get("username") or [""])[0].strip()
        action = (params.get("action") or [""])[0].strip()
        sql = "SELECT id, created_at, username, action, entity, entity_id, details FROM audit_log WHERE 1=1"
        args: List[Any] = []
        if entity:
            sql += " AND entity=?"
            args.append(entity)
        if username:
            sql += " AND username LIKE ?"
            args.append(f"%{username}%")
        if action:
            sql += " AND action LIKE ?"
            args.append(f"%{action}%")
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        rows = rows_to_dicts(db.execute(sql, args).fetchall())
        total = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        self.send_json({"ok": True, "total": total, "events": rows, "limit": limit})

    def api_owner_staff_activity(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        if user.get("role") not in ("owner", "admin"):
            return self.send_json({"ok": False, "error": "Owner access only"}, 403)
        params = urllib.parse.parse_qs(query or "")
        days = int((params.get("days") or ["14"])[0] or 14)
        activity = build_owner_staff_activity(db, days)
        self.send_json({"ok": True, "activity": activity})

    def api_owner_live_hub(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        if not is_primary_owner_user(user):
            return self.send_json({"ok": False, "error": "لوحة المالك الحية مخصصة لوليد ويعقوب فقط"}, 403)
        params = urllib.parse.parse_qs(query or "")
        timeline_days = normalize_timeline_days((params.get("timeline_days") or ["7"])[0], 7)
        self.send_json({"ok": True, "hub": build_owner_live_hub(db, timeline_days)})

    def api_enterprise_status(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        branches = rows_to_dicts(db.execute("SELECT * FROM branches ORDER BY name").fetchall())
        branch_stats: List[Dict[str, Any]] = []
        for b in branches:
            props = db.execute(
                "SELECT COUNT(*) FROM properties WHERE branch_id=?",
                (b["id"],),
            ).fetchone()[0]
            rented = db.execute(
                "SELECT COUNT(*) FROM properties WHERE branch_id=? AND (status LIKE '%مستأ%' OR lower(status) LIKE '%rent%')",
                (b["id"],),
            ).fetchone()[0]
            branch_stats.append({
                **b,
                "properties": int(props or 0),
                "rented": int(rented or 0),
                "occupancy": round((rented / props * 100), 1) if props else 0,
            })
        audit_today = db.execute(
            "SELECT COUNT(*) FROM audit_log WHERE created_at>=?",
            (today() + " 00:00:00",),
        ).fetchone()[0]
        db_status = lq_postgres.build_database_platform_status(db, TABLES)
        readiness = build_platform_readiness(db)
        self.send_json({
            "ok": True,
            "version": APP_VERSION,
            "branches": branch_stats,
            "audit_today": int(audit_today or 0),
            "audit_total": db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
            "offsite": offsite_config(),
            "object_storage": lq_object_storage.object_storage_status(),
            "security": readiness["components"]["security"],
            "platform_readiness": readiness,
            "database": {
                "engine": "sqlite",
                "path": str(DB_PATH),
                "postgres_url_configured": bool(LQ_DATABASE_URL),
                "postgres_driver": lq_postgres.psycopg_available(),
                "platform": db_status,
            },
            "api": {
                "openapi": "/api/openapi.json",
                "docs": "/docs.html",
                "production": PRODUCTION_URL,
            },
        })

    def api_platform_readiness(self, db: sqlite3.Connection) -> None:
        self.send_json(build_platform_readiness(db))

    def api_business_catalog(self, db: sqlite3.Connection) -> None:
        payload = lq_business_catalog.catalog_payload()
        users = rows_to_dicts(
            db.execute(
                "SELECT username, name, role, active FROM users WHERE active=1 ORDER BY role, name"
            ).fetchall()
        )
        self.send_json({"ok": True, "version": APP_VERSION, "catalog": payload, "active_users": users})

    def api_business_office_fee(self) -> None:
        data = self.read_json()
        code = str(data.get("service_code") or data.get("code") or "").strip()
        parties = int(data.get("parties") or 2)
        result = lq_business_catalog.calc_office_fee(code, parties)
        status = 200 if result.get("ok") else 400
        self.send_json(result, status)

    def api_business_hospitality_quote(self) -> None:
        data = self.read_json()
        guests = int(data.get("guests") or 0)
        outside = bool(data.get("outside_nizwa"))
        result = lq_business_catalog.quote_event_package(guests, outside_nizwa=outside)
        status = 200 if result.get("ok") else 400
        self.send_json(result, status)

    def api_business_condolence_quote(self) -> None:
        data = self.read_json()
        zone = str(data.get("zone") or "nizwa")
        self.send_json(lq_business_catalog.quote_condolence(zone))

    def api_hospitality_event_book(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        kind = str(data.get("service_kind") or "event").strip().lower()
        client_name = str(data.get("client_name") or data.get("guest_name") or "").strip()
        phone = str(data.get("phone") or "").strip()
        event_date = str(data.get("event_date") or today()).strip()
        notes = str(data.get("notes") or "").strip()
        client_id = str(data.get("client_id") or "").strip() or None
        paid = float(data.get("paid_amount") or 0)
        if not client_name:
            return self.send_json({"ok": False, "error": "اسم العميل مطلوب"}, 400)

        if kind == "condolence":
            quote = lq_business_catalog.quote_condolence(str(data.get("location_zone") or data.get("zone") or "nizwa"))
            package_code = "condolence"
            package_name = f"واجب عزاء — {quote['zone_label']}"
            guests = 0
            waiters = 8
            supervisors = 2
            dallahs = "حسب الخدمة"
            location_zone = quote["zone"]
            outside = 1 if location_zone != "nizwa" else 0
            total = float(quote["price_omr"])
            deposit = float(quote["deposit_omr"])
        else:
            guests = int(data.get("guests") or 0)
            outside_flag = bool(data.get("outside_nizwa"))
            quote = lq_business_catalog.quote_event_package(guests, outside_nizwa=outside_flag)
            if not quote.get("ok"):
                return self.send_json(quote, 400)
            pkg = quote["package"]
            package_code = pkg["code"]
            package_name = pkg["name_ar"]
            waiters = int(pkg["waiters"])
            supervisors = int(pkg["supervisors"])
            dallahs = str(pkg["dallahs"])
            location_zone = "outside" if outside_flag else "nizwa"
            outside = 1 if outside_flag else 0
            total = float(quote["price_omr"])
            deposit = float(quote["deposit_omr"])

        status = str(data.get("status") or "reserved").strip() or "reserved"
        venue_location = str(data.get("venue_location") or data.get("majlis_location") or "").strip()
        balance = max(0.0, total - paid)
        event_id = uid("HEV")
        row = {
            "id": event_id,
            "service_kind": "condolence" if kind == "condolence" else "event",
            "package_code": package_code,
            "package_name": package_name,
            "client_id": client_id,
            "client_name": client_name,
            "phone": phone,
            "event_date": event_date,
            "guests": guests,
            "location_zone": location_zone,
            "venue_location": venue_location,
            "waiters": waiters,
            "supervisors": supervisors,
            "dallahs": dallahs,
            "total_amount": total,
            "deposit_required": deposit,
            "paid_amount": paid,
            "balance_amount": balance,
            "status": status,
            "outside_nizwa": outside,
            "notes": notes,
            "created_by": user.get("username") or user.get("name") or "",
            "created_at": now_iso(),
        }
        insert(db, "hospitality_events", row)
        # Mirror paid amount into accounts as majlis hospitality revenue when payment recorded.
        if paid > 0:
            insert(
                db,
                "accounts",
                {
                    "id": uid("ACC"),
                    "entry_date": event_date or today(),
                    "type": "income",
                    "category": "Majlis Hospitality",
                    "description": f"عربون/تحصيل مجلس خارجي · {package_name} · {client_name}"
                    + (f" · {venue_location}" if venue_location else ""),
                    "client_id": client_id,
                    "property_id": None,
                    "invoice_id": None,
                    "amount": paid,
                },
            )
        audit(db, user, "hospitality_event_book", "hospitality_events", event_id, f"{package_name} · {total}")
        db.commit()
        self.send_json({"ok": True, "event": row, "quote": quote})

    def api_lease_cancel_template(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        company = lq_business_catalog.COMPANY_PROFILE
        applicant = str(data.get("applicant_name") or "").strip()
        id_no = str(data.get("id_no") or "").strip()
        building = str(data.get("building_no") or "").strip()
        apartment = str(data.get("apartment_no") or "").strip()
        room = str(data.get("room_no") or "").strip()
        shop = str(data.get("shop_no") or "").strip()
        reasons = data.get("reasons") or []
        if isinstance(reasons, str):
            reasons = [r.strip() for r in reasons.split("\n") if r.strip()]
        while len(reasons) < 3:
            reasons.append("")
        effective = str(data.get("effective_date") or "").strip()
        unit_kind = str(data.get("unit_kind") or "apartment").strip().lower()
        clause = (
            "البند رقم (5) من العقد — غرف: إيجار، إنترنت، صرف صحي، أو أي أضرار/صيانة"
            if unit_kind == "room"
            else "البند رقم (4) من العقد — شقق/محلات: كهرباء، ماء، إنترنت، إيجار أو صيانة"
        )
        to_name = str(data.get("to_name") or company["name_ar"]).strip()
        submitted = str(data.get("submitted_at") or today())
        reason_rows = "".join(
            f"<tr><td style='width:28px'>{i+1}.</td><td>{html_escape(reasons[i] or '................................')}</td></tr>"
            for i in range(3)
        )
        html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>طلب إلغاء عقد الإيجار</title>
<style>
@page{{size:A4;margin:16mm}}
body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;color:#111;line-height:1.9;margin:0}}
.sheet{{max-width:900px;margin:0 auto;padding:18px}}
h1{{text-align:center;margin:0 0 18px;font-size:22px}}
.meta{{font-size:13px;color:#444;text-align:center;margin-bottom:18px}}
.line{{margin:10px 0}}
.box{{border:1px solid #ddd;border-radius:10px;padding:12px;margin:14px 0;background:#fafafa}}
table{{width:100%;border-collapse:collapse}}
td{{padding:6px 4px;vertical-align:top}}
.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:28px}}
.sig{{border:1px dashed #999;min-height:90px;padding:10px;border-radius:8px}}
.actions{{margin-bottom:12px}}
button{{border:0;background:#0b1220;color:#f5d76e;padding:10px 14px;border-radius:10px;font-weight:800}}
@media print{{.actions{{display:none}}}}
</style>
</head>
<body>
<div class="sheet">
  <div class="actions"><button onclick="window.print()">طباعة</button></div>
  <h1>طلب إلغاء عقد الإيجار</h1>
  <div class="meta">{html_escape(company['name_ar'])} · س.ت {html_escape(company['cr_no'])} · {html_escape(company['address_ar'])}<br>
  هاتف: {html_escape(company['phones']['landline'])} · واتساب: {html_escape(company['phones']['whatsapp'])}</div>
  <p class="line">إلى الأفاضل / <strong>{html_escape(to_name)}</strong></p>
  <p class="line">أتقدم إليكم أنا / <strong>{html_escape(applicant or '................')}</strong>
  حامل الهوية رقم / <strong>{html_escape(id_no or '................')}</strong></p>
  <p class="line">بطلب إلغاء عقد إيجار:
    المبنى رقم <strong>{html_escape(building or '....')}</strong> ·
    الشقة رقم <strong>{html_escape(apartment or '....')}</strong> ·
    الغرفة <strong>{html_escape(room or '....')}</strong> ·
    المحل <strong>{html_escape(shop or '....')}</strong>
  </p>
  <div class="box">
    <strong>وذلك للأسباب التالية:</strong>
    <table>{reason_rows}</table>
  </div>
  <p class="line">ويكون إلغاء العقد اعتباراً من تاريخ: <strong>{html_escape(effective or '__ / __ / ____')}</strong></p>
  <p class="line">مع الالتزام بفترة الإخطار الشهرية وسداد أجرة شهر الإخطار حسب العقد.</p>
  <div class="box"><strong>الالتزامات المالية:</strong><br>{html_escape(clause)}</div>
  <p class="line">سوف أكون شاكراً لكم على حسن تعاونكم معنا.</p>
  <div class="sign">
    <div class="sig">مقدم الطلب /<br>{html_escape(applicant)}</div>
    <div class="sig">تاريخ تقديم الطلب /<br>{html_escape(submitted)}</div>
    <div class="sig">التوقيع /</div>
  </div>
</div>
</body>
</html>"""
        audit(db, user, "lease_cancel_template", "documents", None, applicant or "blank")
        db.commit()
        self.send_json({"ok": True, "html": html})

    def api_database_status(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        status = lq_postgres.build_database_platform_status(db, TABLES)
        self.send_json({"ok": True, "database": status})

    def api_database_postgres_probe(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        probe = lq_postgres.probe_postgres()
        self.send_json({"ok": bool(probe.get("ok")), "probe": probe})

    def api_database_migrate_preview(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        result = lq_postgres.shadow_migrate_from_sqlite(db, TABLES, dry_run=True)
        audit(db, user, "db_migrate_preview", "database", "postgres", f"tables={result.get('copied_tables')}")
        db.commit()
        self.send_json({"ok": bool(result.get("ok")), "result": result})

    def api_database_migrate_shadow(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        confirm = str(data.get("confirm") or "").strip().lower()
        if confirm not in ("shadow", "yes", "1", "true"):
            return self.send_json({"ok": False, "error": "confirm=shadow required"}, 400)
        result = lq_postgres.shadow_migrate_from_sqlite(db, TABLES, dry_run=False)
        audit(
            db,
            user,
            "db_migrate_shadow",
            "database",
            "postgres",
            f"ok={result.get('ok')} rows={result.get('copied_rows')} errors={len(result.get('errors') or [])}",
        )
        db.commit()
        self.send_json({"ok": bool(result.get("ok")), "result": result})

    def api_database_verify_shadow(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        result = lq_postgres.verify_shadow(db, TABLES)
        self.send_json({"ok": bool(result.get("ok")), "verify": result})

    def api_storage_object_status(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        self.send_json({"ok": True, "object_storage": lq_object_storage.object_storage_status(), "disk": storage_status()})

    def api_storage_object_probe(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        probe = lq_object_storage.probe_object_storage()
        audit(db, user, "storage_object_probe", "storage", "object", f"ok={probe.get('ok')}")
        db.commit()
        self.send_json({"ok": bool(probe.get("ok")), "probe": probe})

    def api_storage_sync_uploads(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        confirm = str(data.get("confirm") or "").strip().lower()
        if confirm not in ("sync", "yes", "1", "true"):
            return self.send_json({"ok": False, "error": "confirm=sync required"}, 400)
        result = lq_object_storage.sync_local_tree(UPLOAD_DIR)
        audit(
            db,
            user,
            "storage_sync_uploads",
            "storage",
            "object",
            f"ok={result.get('ok')} uploaded={result.get('uploaded')} scanned={result.get('scanned')}",
        )
        db.commit()
        self.send_json({"ok": bool(result.get("ok")), "result": result})

    def api_invoice_audit(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        invoice_id = (params.get("invoice_id") or [""])[0].strip()
        if not invoice_id:
            return self.send_json({"ok": False, "error": "invoice_id required"}, 400)
        invoice = db.execute("SELECT invoice_no FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            return self.send_json({"ok": False, "error": "Invoice not found"}, 404)
        rows = db.execute(
            """
            SELECT created_at, username, action, details
            FROM audit_log
            WHERE entity='invoices' AND (entity_id=? OR details LIKE ?)
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (invoice_id, f"%{invoice['invoice_no']}%"),
        ).fetchall()
        self.send_json({"ok": True, "invoice_id": invoice_id, "invoice_no": invoice["invoice_no"], "events": rows_to_dicts(rows)})

    def api_tenant_statement(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        client_id = str((params.get("client_id") or [""])[0] or "").strip()
        if not client_id:
            return self.send_json({"ok": False, "error": "client_id required"}, 400)
        client = db.execute("SELECT id,name,phone,email,national_id,balance FROM clients WHERE id=?", (client_id,)).fetchone()
        if not client:
            return self.send_json({"ok": False, "error": "Client not found"}, 404)
        contracts = rows_to_dicts(
            db.execute(
                """
                SELECT id, contract_no, property_id, start_date, end_date, rent_amount, status, approved_at, activated_at
                FROM contracts
                WHERE client_id=?
                ORDER BY start_date DESC
                """,
                (client_id,),
            ).fetchall()
        )
        invoices = rows_to_dicts(
            db.execute(
                """
                SELECT id, invoice_no, contract_id, issue_date, due_date, amount, paid_amount, status, description
                FROM invoices
                WHERE client_id=?
                ORDER BY issue_date DESC
                """,
                (client_id,),
            ).fetchall()
        )
        payments = rows_to_dicts(
            db.execute(
                """
                SELECT p.id, p.invoice_id, p.contract_id, p.payment_date, p.amount, p.method, p.note, p.payment_proof_image,
                       p.received_by
                FROM payments p
                WHERE p.client_id=?
                ORDER BY p.payment_date DESC, p.id DESC
                """,
                (client_id,),
            ).fetchall()
        )
        total_required = round(sum(float(i.get("amount") or 0) for i in invoices), 3)
        total_paid = round(sum(float(i.get("paid_amount") or 0) for i in invoices), 3)
        total_remaining = round(max(0.0, total_required - total_paid), 3)
        self.send_json(
            {
                "ok": True,
                "client": dict(client),
                "contracts": contracts,
                "invoices": invoices,
                "payments": payments,
                "summary": {
                    "rent_required": total_required,
                    "total_paid": total_paid,
                    "remaining": total_remaining,
                    "client_balance": float(client["balance"] or 0),
                },
            }
        )

    def api_request_approval(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        entity = str(data.get("entity") or "").strip()
        entity_id = str(data.get("entity_id") or "").strip()
        request_type = str(data.get("request_type") or "").strip()
        notes = str(data.get("notes") or "").strip()
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if not entity or not entity_id or not request_type:
            return self.send_json({"ok": False, "error": "entity, entity_id, request_type required"}, 400)
        if request_type == "contract" and entity == "contracts":
            contract = db.execute("SELECT status FROM contracts WHERE id=?", (entity_id,)).fetchone()
            if not contract:
                return self.send_json({"ok": False, "error": "Contract not found"}, 404)
            status_lower = str(contract["status"] or "").lower()
            if status_lower in ("active", "activated", "approved"):
                return self.send_json({"ok": False, "error": "العقد معتمد/مفعّل مسبقاً"}, 400)
        approval_id = create_approval_request(
            db,
            entity,
            entity_id,
            request_type,
            user.get("name") or user.get("username") or "System",
            notes or f"طلب اعتماد {request_type}",
            meta=meta or None,
        )
        audit(db, user, "request_approval", "approvals", approval_id, f"{request_type} for {entity_id}")
        if request_type == "contract" and entity == "contracts":
            db.execute("UPDATE contracts SET status=? WHERE id=?", ("ApprovalRequested", entity_id))
        db.commit()
        self.send_json({
            "ok": True,
            "approval_id": approval_id,
            "message": "تم إرسال الطلب — سيظهر للمدير في مركز الاعتمادات",
        })

    def api_decide_approval(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        approval_id = str(data.get("approval_id") or "").strip()
        decision = str(data.get("decision") or "").strip().lower()
        note = str(data.get("notes") or "").strip()
        if not approval_id or decision not in ("approve", "reject", "approved", "rejected"):
            return self.send_json({"ok": False, "error": "approval_id and decision (approve/reject) required"}, 400)
        row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "Approval not found"}, 404)
        if str(row["status"] or "").lower() != "pending":
            return self.send_json({"ok": False, "error": "الطلب ليس قيد الانتظار"}, 400)
        request_type = str(row["request_type"] or "")
        if not can_decide_approval(user, request_type):
            return self.send_json({"ok": False, "error": "لا تملك صلاحية اعتماد هذا النوع"}, 403)
        approved = decision in ("approve", "approved")
        status = "Approved" if approved else "Rejected"
        approved_by = user.get("name") or user.get("username") or "System"
        approved_at = now_iso()
        _, meta = approval_notes_unpack(row["notes"])
        result: Dict[str, Any] = {}
        if approved:
            try:
                if request_type == "contract":
                    created = execute_contract_approval(db, user, row["entity_id"])
                    result = {"created_invoices": created}
                elif request_type == "manual_invoice":
                    contract_id = meta.get("contract_id") or row["entity_id"]
                    contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
                    if not contract:
                        raise ValueError("Contract not found for invoice approval")
                    amount_value = float(meta.get("amount") or 0)
                    inv_type = detect_invoice_type(
                        meta.get("description") or "Manual invoice",
                        meta.get("invoice_type"),
                    )
                    invoice = build_invoice_row(
                        db,
                        contract,
                        meta.get("description") or "Manual invoice",
                        amount_value,
                        issue_date=meta.get("issue_date"),
                        due_date=meta.get("due_date"),
                        invoice_type=inv_type,
                    )
                    insert(db, "invoices", invoice)
                    audit(db, user, "create", "invoices", invoice["id"], f"Approved manual invoice {invoice['invoice_no']}")
                    result = {"item": invoice}
                elif request_type == "payment":
                    invoice_id = meta.get("invoice_id") or row["entity_id"]
                    pay_result = execute_invoice_payment(
                        db,
                        user,
                        str(invoice_id),
                        float(meta.get("amount") or 0),
                        method=str(meta.get("method") or "Cash"),
                        note=str(meta.get("note") or "Invoice payment"),
                        payment_date=meta.get("payment_date"),
                        bank_name=str(meta.get("bank_name") or "Main Bank"),
                    )
                    result = pay_result
                else:
                    raise ValueError(f"Unsupported approval type: {request_type}")
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
        db.execute(
            "UPDATE approvals SET status=?, approved_by=?, approved_at=?, notes=? WHERE id=?",
            (
                status,
                approved_by,
                approved_at,
                approval_notes_pack(note or row["notes"], meta) if meta else (note or row["notes"]),
                approval_id,
            ),
        )
        audit(db, user, "decide_approval", "approvals", approval_id, f"{status} {request_type}")
        db.commit()
        self.send_json({"ok": True, "status": status, "approval_id": approval_id, "result": result})

    def api_approve_contract(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = data.get("contract_id")
        if not can_decide_approval(user, "contract"):
            return self.send_json({"ok": False, "error": "لا تملك صلاحية اعتماد العقود — استخدم طلب اعتماد"}, 403)
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Contract not found"}, 404)
        try:
            created = execute_contract_approval(db, user, contract_id)
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        pending = db.execute(
            """
            SELECT id FROM approvals
            WHERE entity='contracts' AND entity_id=? AND request_type='contract' AND lower(status)='pending'
            """,
            (contract_id,),
        ).fetchone()
        if pending:
            db.execute(
                "UPDATE approvals SET status='Approved', approved_by=?, approved_at=? WHERE id=?",
                (user.get("name") or user.get("username"), now_iso(), pending["id"]),
            )
        db.commit()
        self.send_json({"ok": True, "created_invoices": created, "status": "Approved"})

    def api_activate_contract(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        policies = load_workflow_policies(db)
        contract_id = str(data.get("contract_id") or "").strip()
        if not contract_id:
            return self.send_json({"ok": False, "error": "contract_id required"}, 400)
        uname = str(user.get("username") or "").strip().lower()
        if uname in RESTRICTED_ADMIN_USERNAMES:
            return self.send_json({"ok": False, "error": "تفعيل العقد يتطلب إذن المالك"}, 403)
        owner_admin_only = _workflow_policy_bool(policies, "contract_activation_owner_admin_only")
        if owner_admin_only and user.get("role") not in ("owner", "admin"):
            return self.send_json({"ok": False, "error": "تفعيل العقد محصور بحسابات الإدارة/المالك"}, 403)
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Contract not found"}, 404)
        try:
            created = execute_contract_activation(db, user, contract_id)
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, 400)
        db.commit()
        self.send_json({"ok": True, "status": "Active", "created_invoices": created})

    def api_renew_contract(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = data.get("contract_id")
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Contract not found"}, 404)
        status = str(contract["status"] or "").lower()
        if status in ("renewed", "closed", "draft"):
            return self.send_json({"ok": False, "error": "This contract cannot be renewed"}, 400)
        try:
            old_end = datetime.fromisoformat(str(contract["end_date"])).date()
        except ValueError:
            return self.send_json({"ok": False, "error": "Invalid contract end date"}, 400)
        months = int(data.get("months") or contract_duration_months(contract["start_date"], contract["end_date"]))
        if months <= 0 or months > 120:
            return self.send_json({"ok": False, "error": "Invalid renewal duration"}, 400)
        new_start = old_end + timedelta(days=1)
        if data.get("start_date"):
            try:
                new_start = datetime.fromisoformat(str(data["start_date"])).date()
            except ValueError:
                return self.send_json({"ok": False, "error": "Invalid start date"}, 400)
        if data.get("end_date"):
            try:
                new_end = datetime.fromisoformat(str(data["end_date"])).date()
            except ValueError:
                return self.send_json({"ok": False, "error": "Invalid end date"}, 400)
        else:
            new_end = add_months(new_start, months)
        if new_end <= new_start:
            return self.send_json({"ok": False, "error": "Renewal end date must be after start date"}, 400)
        rent = float(data["rent_amount"]) if data.get("rent_amount") not in (None, "") else float(contract["rent_amount"] or 0)
        if rent <= 0:
            return self.send_json({"ok": False, "error": "Invalid rent amount"}, 400)
        prev_no = contract["contract_no"] or contract["id"]
        new_contract = {
            "id": uid("CT"),
            "contract_no": next_contract_no(db, contract["contract_type"] or "Residential"),
            "contract_type": contract["contract_type"],
            "property_id": contract["property_id"],
            "client_id": contract["client_id"],
            "tenant_nationality": contract["tenant_nationality"],
            "tenant_id_no": contract["tenant_id_no"],
            "unit_details": contract["unit_details"],
            "start_date": new_start.isoformat(),
            "end_date": new_end.isoformat(),
            "rent_amount": rent,
            "deposit_amount": 0,
            "late_fee": contract["late_fee"],
            "grace_days": contract["grace_days"],
            "renewal_notice_days": contract["renewal_notice_days"],
            "status": "Draft",
            "payment_cycle": contract["payment_cycle"],
            "legal_terms": contract["legal_terms"] or default_legal_terms(),
            "company_signatory": contract["company_signatory"] or COMPANY_NAME,
            "approved_at": None,
            "notes": f"Renewal from {prev_no}",
        }
        insert(db, "contracts", new_contract)
        db.execute("UPDATE contracts SET status=? WHERE id=?", ("Renewed", contract_id))
        sync_property_status_for_contract(db, contract["property_id"], "Renewed")
        audit(db, user, "renew", "contracts", contract_id, f"Renewed {prev_no} -> {new_contract['contract_no']}")
        db.commit()
        self.send_json({"ok": True, "contract": new_contract, "previous_contract_id": contract_id})

    def api_end_contract(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = data.get("contract_id")
        contract = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return self.send_json({"ok": False, "error": "Contract not found"}, 404)
        status = str(contract["status"] or "").lower()
        if status in ("cancelled", "canceled", "renewed"):
            return self.send_json({"ok": False, "error": "This contract is already closed"}, 400)
        ended_at = data.get("ended_at") or today()
        try:
            datetime.fromisoformat(str(ended_at)).date()
        except ValueError:
            return self.send_json({"ok": False, "error": "Invalid end date"}, 400)
        requested_status = str(data.get("status") or "").strip().lower()
        final_status = "Expired" if requested_status in ("expired", "ended", "منتهي") else "Cancelled"
        reason = str(data.get("reason") or "").strip()
        existing_notes = str(contract["notes"] or "").strip()
        note_line = f"Contract ended on {ended_at}"
        if reason:
            note_line += f": {reason}"
        notes = (existing_notes + "\n" + note_line).strip() if existing_notes else note_line
        db.execute(
            "UPDATE contracts SET status=?, ended_at=?, notes=? WHERE id=?",
            (final_status, ended_at, notes, contract_id),
        )
        sync_property_status_for_contract(db, contract["property_id"], final_status)
        audit(db, user, "end", "contracts", contract_id, note_line)
        db.commit()
        self.send_json({"ok": True, "status": final_status, "ended_at": ended_at})

    def api_contract_template(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        contract_id = data.get("contract_id")
        c = db.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not c:
            return self.send_json({"ok": False, "error": "Contract not found"}, 404)
        client = db.execute("SELECT * FROM clients WHERE id=?", (c["client_id"],)).fetchone()
        prop = db.execute("SELECT * FROM properties WHERE id=?", (c["property_id"],)).fetchone()
        try:
            attachments = json.loads(c["attachments"] or "[]")
        except Exception:
            attachments = []
        duration_days = max(0, (datetime.fromisoformat(c["end_date"]).date() - datetime.fromisoformat(c["start_date"]).date()).days + 1)
        duration_months = contract_duration_months(c["start_date"], c["end_date"])
        attachment_html = "".join(
            f"<li>{html_escape(a.get('name', 'Attachment'))} - {html_escape(a.get('type', 'file'))} - by {html_escape(a.get('uploaded_by', 'system'))} - {html_escape(a.get('uploaded_at', ''))}</li>"
            for a in attachments if isinstance(a, dict)
        ) or "<li>لا توجد مرفقات</li>"
        deposit_required = float(c["deposit_amount"] or 0)
        inv_rows = db.execute("SELECT description, paid_amount FROM invoices WHERE contract_id=?", (contract_id,)).fetchall()
        deposit_pool = [
            r for r in inv_rows
            if deposit_required > 0 and any(
                token in str(r["description"] or "").lower()
                for token in ("تأمين", "deposit", "security", "امان")
            )
        ]
        pool = deposit_pool if deposit_pool else inv_rows
        deposit_paid = sum(float(r["paid_amount"] or 0) for r in pool)
        if int(c["deposit_received"] or 0):
            deposit_label = "تم استلام التأمين المالي"
            deposit_badge = "ok"
            deposit_paid = float(c["deposit_received_amount"] or deposit_paid)
        elif deposit_required <= 0:
            deposit_label = "لا يوجد تأمين مالي"
            deposit_badge = "ok"
        elif deposit_paid >= deposit_required:
            deposit_label = "تم استلام التأمين المالي"
            deposit_badge = "ok"
        else:
            deposit_label = "لم يُستلم التأمين المالي بالكامل"
            deposit_badge = "no"
        client_email = html_escape(client["email"] if client else "")
        client_national = html_escape(c["tenant_id_no"] or (client["national_id"] if client else ""))
        tenant_nat = html_escape(c["tenant_nationality"] or "")
        company_ar = COMPANY_NAME_AR
        company_en = "QUALITY OF LAUNCH PROJECTS LLC"
        owner_line = "يعقوب فاضل الخصيبي · Yaqoub Fadel Al-Khasibi"
        phones = "25225026 · GSM: 98203088 / 92120205 / 92269656"
        email = "jiwdat@gmail.com"
        addr = "نزوى — حي التراث الشمالي قرب الدوار"
        html = f"""<!doctype html>
<html lang="ar" dir="ltr">
<head>
<meta charset="utf-8">
<title>{html_escape(c['contract_no'] or c['id'])} - {company_en}</title>
<style>
  @page{{size:A4;margin:14mm}}
  *{{box-sizing:border-box}}
  body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;margin:0;color:#111827;background:#fff;line-height:1.7}}
  .sheet{{max-width:980px;margin:0 auto;padding:22px}}
  .hero{{border-bottom:4px solid #c9a227;padding-bottom:16px;margin-bottom:18px;display:grid;grid-template-columns:110px 1fr;gap:18px;align-items:start}}
  .hero img{{width:96px;height:96px;object-fit:contain}}
  .hero h1{{margin:0;color:#0b1220;font-size:24px}}
  .hero h2{{margin:4px 0 0;color:#8f631b;font-size:15px}}
  .hero p{{margin:6px 0;color:#4b5563;font-size:13px;line-height:1.65}}
  .badge{{display:inline-block;border:1px solid #c9a227;border-radius:999px;padding:5px 12px;color:#8f631b;margin-top:8px;font-weight:800}}
  .grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:16px 0}}
  .box{{border:1px solid #e5d39a;border-radius:14px;padding:14px;background:#fffdf7}}
  .box h3{{margin:0 0 8px;color:#8f631b;font-size:13px}}
  table{{width:100%;border-collapse:collapse;margin:16px 0;direction:ltr}}
  th,td{{border:1px solid #e5e7eb;padding:10px;text-align:right;vertical-align:top}}
  th{{background:#0b1220;color:#f5d76e}}
  .terms{{white-space:pre-wrap}}
  .dep{{display:inline-block;border-radius:999px;padding:4px 12px;font-size:12px;font-weight:800;margin-top:8px}}
  .dep.ok{{background:#ecfdf5;color:#047857;border:1px solid #6ee7b7}}
  .dep.no{{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca}}
  .signatures{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:28px}}
  .sig{{border:1px solid #d8b15b;border-radius:14px;min-height:110px;padding:12px;background:#fff}}
  .actions{{position:sticky;top:0;background:#fff;padding:10px 0;margin-bottom:8px;text-align:left}}
  button{{border:0;border-radius:12px;padding:10px 16px;font-weight:800;background:#0b1220;color:#f5d76e;cursor:pointer}}
  .footer{{margin-top:18px;padding-top:12px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;text-align:center}}
  @media print{{.actions{{display:none}}.sheet{{padding:0}}}}
</style>
</head>
<body>
<div class="sheet">
  <div class="actions"><button onclick="window.print()">طباعة / Print PDF</button></div>
  <header class="hero">
    <img src="/assets/brand-logo-gold.png?v=12" alt="{company_en}">
    <div>
      <h1>{company_ar}</h1>
      <h2>{company_en}</h2>
      <p>{owner_line}<br>إدارة العقارات والضيافة · Real Estate & Hospitality Management<br>
      س.ت: 1466316 · الرمز البريدي: 611 · {addr} · سلطنة عُمان<br>
      {email} · هاتف: {phones}</p>
      <span class="badge">عقد إيجار · Lease Contract — {html_escape(c['contract_no'] or c['id'])}</span>
    </div>
  </header>
  <section class="grid">
    <div class="box"><h3>بيانات العميل · Client</h3><p><strong>{html_escape(client['name'] if client else '')}</strong><br>
    هاتف: {html_escape(client['phone'] if client else '')}<br>
    بريد: {client_email}<br>
    هوية / سجل: {client_national}<br>
    جنسية: {tenant_nat}</p></div>
    <div class="box"><h3>العقار والوحدة · Property</h3><p>{html_escape(prop['name'] if prop else '')}<br>
    {html_escape(c['unit_details'] or (prop['location'] if prop else ''))}<br>
  الموقع: {html_escape(prop['location'] if prop else '')}</p></div>
  </section>
  <table>
    <tr><th>بداية العقد</th><td>{html_escape(c['start_date'])}</td><th>نهاية العقد</th><td>{html_escape(c['end_date'])}</td></tr>
    <tr><th>المدة</th><td>{duration_months} شهر / {duration_days} يوم</td><th>الحالة</th><td>{html_escape(c['status'])}</td></tr>
    <tr><th>الإيجار الشهري</th><td>{fmt_omr(c['rent_amount'])}</td><th>دورة الدفع</th><td>{html_escape(c['payment_cycle'])}</td></tr>
    <tr><th>غرامة التأخير</th><td>{fmt_omr(c['late_fee'])}</td><th>مهلة السداد</th><td>{html_escape(c['grace_days'])} يوم</td></tr>
  </table>
  <section class="box">
    <h3>الشروط القانونية</h3>
    <p class="terms">{html_escape(c['legal_terms'] or default_legal_terms())}</p>
  </section>
  <section class="box">
    <h3>المرفقات</h3>
    <ul>{attachment_html}</ul>
  </section>
  <section class="signatures">
    <div class="sig"><strong>توقيع المستأجر</strong></div>
    <div class="sig"><strong>توقيع الشركة</strong><br>{html_escape(c['company_signatory'] or company_en)}</div>
    <div class="sig"><strong>الختم</strong></div>
  </section>
  <div class="footer">{company_ar} · {company_en} · C.R. 1466316 · {email} · {phones}</div>
</div>
</body>
</html>"""
        self.send_json({"ok": True, "html": html})

    def api_bank_reconciliation_preview(self, db: sqlite3.Connection, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        bank_name = (params.get("bank_name") or [""])[0].strip()
        period_name = (params.get("period_name") or [""])[0].strip()
        payload = build_bank_reconciliation_data(db, bank_name=bank_name, period_name=period_name)
        self.send_json({"ok": True, **payload})

    def api_auto_match_bank(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        bank_name = str(data.get("bank_name") or "").strip()
        period_name = str(data.get("period_name") or "").strip()
        period_start, period_end = resolve_period_bounds(db, period_name)
        result = auto_match_bank_transactions(db, bank_name=bank_name, period_start=period_start, period_end=period_end)
        audit(
            db, user, "auto_match", "bank_transactions", None,
            f"Auto-matched {result['matched']} bank transactions for {bank_name or 'All Banks'} / {period_name or 'all'}",
        )
        db.commit()
        preview = build_bank_reconciliation_data(db, bank_name=bank_name, period_name=period_name)
        self.send_json({"ok": True, "match_result": result, "preview": preview})

    def api_close_financial_period(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        period_id = str(data.get("period_id") or "").strip()
        force = bool(data.get("force"))
        if not period_id:
            return self.send_json({"ok": False, "error": "period_id required"}, 400)
        row = db.execute("SELECT * FROM financial_periods WHERE id=?", (period_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "Period not found"}, 404)
        if str(row["status"] or "").lower() == "closed":
            return self.send_json({"ok": False, "error": "Period is already closed"}, 400)
        period_name = row["period_name"]
        if not force:
            rec = db.execute(
                """
                SELECT * FROM bank_reconciliations
                WHERE period_name=? AND lower(status) IN ('reconciled','matched')
                ORDER BY reconciled_at DESC LIMIT 1
                """,
                (period_name,),
            ).fetchone()
            variance_rec = db.execute(
                """
                SELECT * FROM bank_reconciliations
                WHERE period_name=? ORDER BY reconciled_at DESC LIMIT 1
                """,
                (period_name,),
            ).fetchone()
            if not variance_rec:
                return self.send_json({
                    "ok": False,
                    "error": "لا يوجد تسوية بنكية مسجّلة لهذه الفترة — أنشئ تسوية أولاً أو استخدم force=true",
                }, 400)
            if abs(float(variance_rec["difference"] or 0)) > 0.001 and not rec:
                return self.send_json({
                    "ok": False,
                    "error": f"فرق التسوية {fmt_omr(float(variance_rec['difference'] or 0))} — أصلح الفرق أو استخدم force",
                }, 400)
        closed_at = now_iso()
        closed_by = user.get("name") or user.get("username") or "System"
        db.execute(
            "UPDATE financial_periods SET status='Closed', closed_by=?, closed_at=?, notes=COALESCE(notes,'') WHERE id=?",
            (closed_by, closed_at, period_id),
        )
        audit(db, user, "close", "financial_periods", period_id, f"Closed period {period_name}")
        db.commit()
        self.send_json({"ok": True, "period_id": period_id, "period_name": period_name, "status": "Closed", "closed_at": closed_at})

    def api_bank_reconciliation_alerts(self, db: sqlite3.Connection) -> None:
        alerts = build_bank_variance_alerts(db)
        self.send_json({"ok": True, "alerts": alerts})

    def api_staff_manifest(self) -> None:
        self.send_json({
            "ok": True,
            "manifest": {
                "version": STAFF_APP_VERSION,
                "production_url": PRODUCTION_URL,
                "download_page": f"{PRODUCTION_URL}{NAJJAR_LOGIN}",
                "install_page": f"{PRODUCTION_URL}/remove",
                "app_url": f"{PRODUCTION_URL}{NAJJAR_PLATFORMS}",
                "apk_url": STAFF_DOWNLOAD_APK,
                "windows_zip_url": STAFF_DOWNLOAD_ZIP,
                "features": [
                    "staff_sync_api",
                    "field_mode",
                    "maintenance_quick_update",
                    "maintenance_quick_create",
                    "offline_sync_cache",
                    "deep_link_sections",
                    "push_register",
                    "pwa_install",
                ],
                "phase": "10 — Field App Integration",
            },
        })

    def api_staff_sync(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        self.send_json({"ok": True, "sync": build_staff_sync_payload(db, user)})

    def api_staff_push_register(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        platform = str(data.get("platform") or "web").strip()
        push_token = str(data.get("push_token") or "").strip() or uid("WEB")
        device_label = str(data.get("device_label") or "").strip()[:200]
        existing = db.execute(
            "SELECT id FROM staff_devices WHERE user_id=? AND push_token=?",
            (user["id"], push_token),
        ).fetchone()
        now = now_iso()
        if existing:
            db.execute(
                "UPDATE staff_devices SET last_seen=?, platform=?, device_label=? WHERE id=?",
                (now, platform, device_label, existing["id"]),
            )
            device_id = existing["id"]
        else:
            device_id = uid("DEV")
            insert(
                db,
                "staff_devices",
                {
                    "id": device_id,
                    "user_id": user["id"],
                    "platform": platform,
                    "push_token": push_token,
                    "device_label": device_label,
                    "created_at": now,
                    "last_seen": now,
                },
            )
        audit(db, user, "push_register", "staff_devices", device_id, f"Registered {platform} device")
        db.commit()
        self.send_json({"ok": True, "device_id": device_id, "message": "تم تسجيل الجهاز للإشعارات"})

    def api_staff_maintenance_update(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        maint_id = str(data.get("maintenance_id") or "").strip()
        if not maint_id:
            return self.send_json({"ok": False, "error": "maintenance_id required"}, 400)
        row = db.execute("SELECT * FROM maintenance WHERE id=?", (maint_id,)).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "Maintenance request not found"}, 404)
        status = str(data.get("status") or row["status"]).strip()
        notes = str(data.get("notes") or row["notes"] or "").strip()
        cost = float(data.get("cost") if data.get("cost") is not None else row["cost"] or 0)
        db.execute("UPDATE maintenance SET status=?, notes=?, cost=? WHERE id=?", (status, notes, cost, maint_id))
        audit(db, user, "field_update", "maintenance", maint_id, f"Field update → {status}")
        db.commit()
        self.send_json({"ok": True, "maintenance_id": maint_id, "status": status})

    def api_staff_quick_maintenance(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        property_id = str(data.get("property_id") or "").strip()
        if not property_id:
            return self.send_json({"ok": False, "error": "property_id required"}, 400)
        prop = db.execute("SELECT id, name FROM properties WHERE id=?", (property_id,)).fetchone()
        if not prop:
            return self.send_json({"ok": False, "error": "Property not found"}, 404)
        title = str(data.get("title") or "").strip() or "طلب صيانة من الميدان"
        priority = str(data.get("priority") or "Medium").strip()
        notes = str(data.get("notes") or "من تطبيق الميدان").strip()
        maint_id = uid("M")
        insert(
            db,
            "maintenance",
            {
                "id": maint_id,
                "property_id": property_id,
                "title": title,
                "priority": priority,
                "status": "Open",
                "request_date": today(),
                "cost": 0,
                "notes": notes,
            },
        )
        audit(db, user, "quick_create", "maintenance", maint_id, title)
        db.commit()
        self.send_json({"ok": True, "maintenance_id": maint_id, "title": title, "property_name": prop["name"]})

    def api_receivables_aging(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        bucket = str((params.get("bucket") or [""])[0] or "").strip()
        payload = build_receivables_aging(db, bucket_filter=bucket or None)
        self.send_json({"ok": True, "receivables": payload})

    def api_receivables_reminders(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        bucket = str((params.get("bucket") or [""])[0] or "").strip()
        payload = build_receivables_aging(db, bucket_filter=bucket or None)
        candidates = [x for x in payload.get("items") or [] if float(x.get("remaining") or 0) > 0 and int(x.get("days_late") or 0) > 0]
        self.send_json({
            "ok": True,
            "candidates": candidates,
            "count": len(candidates),
            "channels": {
                "email": bool(os.environ.get("LQ_SMTP_HOST")),
                "sms": bool(os.environ.get("LQ_SMS_ENABLED")),
                "whatsapp": bool(os.environ.get("LQ_WHATSAPP_ENABLED")),
            },
        })

    def api_receivables_send_reminders(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        channel = str(data.get("channel") or "email").strip().lower()
        invoice_ids = data.get("invoice_ids") or []
        if isinstance(invoice_ids, str):
            invoice_ids = [x.strip() for x in invoice_ids.split(",") if x.strip()]
        invoice_ids = [str(x) for x in invoice_ids if str(x).strip()]
        bucket = str(data.get("bucket") or "").strip()
        aging = build_receivables_aging(db, bucket_filter=bucket or None)
        items = [x for x in aging.get("items") or [] if int(x.get("days_late") or 0) > 0]
        if invoice_ids:
            wanted = set(invoice_ids)
            items = [x for x in items if str(x.get("invoice_id")) in wanted]
        if not items:
            return self.send_json({"ok": False, "error": "لا توجد فواتير متأخرة للتذكير"}, 400)
        if channel not in ("email", "sms", "whatsapp", "log"):
            return self.send_json({"ok": False, "error": "Unsupported channel"}, 400)

        sent = 0
        failed = 0
        queued = 0
        logs: List[Dict[str, Any]] = []
        # Group by client for cleaner reminders
        by_client: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            cid = str(it.get("client_id") or "unknown")
            by_client.setdefault(cid, []).append(it)

        for cid, group in by_client.items():
            first = group[0]
            client_name = str(first.get("client_name") or "عميل")
            email = str(first.get("client_email") or "").strip()
            phone = str(first.get("client_phone") or "").strip()
            total_rem = round(sum(float(x.get("remaining") or 0) for x in group), 3)
            lines = [
                f"{COMPANY_NAME} — تذكير تحصيل",
                f"العميل: {client_name}",
                f"إجمالي المتأخر: {total_rem} OMR",
                "",
            ]
            for x in group[:20]:
                lines.append(
                    f"- {x.get('invoice_no')} | استحقاق {x.get('due_date')} | متبقي {x.get('remaining')} OMR | تأخير {x.get('days_late')} يوم ({x.get('bucket')})"
                )
            body = "\n".join(lines)
            subject = f"تذكير تحصيل · {client_name} · {total_rem} OMR"
            status = "queued"
            detail = ""
            recipient = email or phone or SUPPORT_EMAIL
            if channel == "email":
                if not email:
                    status = "failed"
                    detail = "لا يوجد بريد للعميل"
                    failed += 1
                else:
                    ok, detail = send_alert_email(email, subject, body)
                    status = "sent" if ok else "failed"
                    recipient = email
                    if ok:
                        sent += 1
                    else:
                        failed += 1
            elif channel in ("sms", "whatsapp"):
                if not phone:
                    status = "failed"
                    detail = "لا يوجد هاتف للعميل"
                    failed += 1
                else:
                    status = "queued"
                    detail = f"{channel.upper()} queued — فعّل LQ_{channel.upper()}_ENABLED للإرسال الفعلي"
                    recipient = phone
                    queued += 1
            else:  # log only
                status = "logged"
                detail = "Saved reminder log only"
                queued += 1

            log_id = uid("RR")
            insert(
                db,
                "alert_notifications",
                {
                    "id": log_id,
                    "created_at": now_iso(),
                    "channel": f"receivables:{channel}",
                    "recipient": recipient,
                    "subject": subject,
                    "message": body[:4000],
                    "status": status,
                    "alert_count": len(group),
                    "sent_by": user.get("name") or user.get("username"),
                },
            )
            logs.append({"id": log_id, "client_id": cid, "status": status, "detail": detail, "recipient": recipient})

        audit(db, user, "receivables_remind", "invoices", "", f"{channel}: sent={sent} queued={queued} failed={failed}")
        db.commit()
        self.send_json({
            "ok": True,
            "channel": channel,
            "sent": sent,
            "queued": queued,
            "failed": failed,
            "clients": len(by_client),
            "invoices": len(items),
            "logs": logs[:50],
        })

    def api_alert_center(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        payload = build_alert_center(db, user_id=user.get("id"), role=str(user.get("role") or "viewer"))
        self.send_json({"ok": True, "center": payload})

    def api_role_board(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        board = build_role_board(db, user)
        self.send_json({"ok": True, "board": board})

    def api_payroll_import_preview(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        import_type = str(data.get("import_type") or "").strip().lower()
        content = str(data.get("content") or data.get("text") or "")
        file_name = str(data.get("file_name") or "").strip()
        salary_month = str(data.get("salary_month") or "").strip()
        project_name = str(data.get("project_name") or "").strip()
        if data.get("base64") and not content:
            try:
                content = base64.b64decode(str(data.get("base64"))).decode("utf-8", errors="replace")
            except Exception:
                return self.send_json({"ok": False, "error": "تعذر قراءة الملف"}, 400)
        try:
            payload = lq_payroll_import.build_preview(
                import_type,
                content,
                file_name=file_name,
                salary_month=salary_month,
                project_name=project_name,
            )
            preview_id = lq_payroll_import.store_preview(str(user.get("username") or ""), payload)
            public = {
                "preview_id": preview_id,
                "import_type": import_type,
                "file_name": file_name,
                "salary_month": payload.get("salary_month"),
                "project_name": project_name,
                "summary": payload.get("summary") or {},
                "sample_rows": (payload.get("rows") or [])[:25],
                "row_count": len(payload.get("rows") or []),
                "expires_in_seconds": lq_payroll_import.PREVIEW_TTL_SECONDS,
            }
            audit(db, user, "payroll_import_preview", "payroll_import", preview_id, f"{import_type} rows={public['row_count']}")
            db.commit()
            self.send_json({"ok": True, "preview": public})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)

    def api_payroll_import_commit(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        preview_id = str(data.get("preview_id") or "").strip()
        if not preview_id:
            return self.send_json({"ok": False, "error": "preview_id مطلوب"}, 400)
        try:
            preview = lq_payroll_import.pop_preview(str(user.get("username") or ""), preview_id)
            result = lq_payroll_import.commit_preview(
                db,
                user,
                preview,
                insert_fn=insert,
                uid_fn=uid,
                today_fn=today,
            )
            audit(
                db,
                user,
                "payroll_import_commit",
                "payroll_import_batches",
                result["batch_id"],
                f"{result['import_type']} rows={result['committed_rows']}",
            )
            db.commit()
            self.send_json({"ok": True, "result": result})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)

    def api_payroll_import_batches(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        limit = min(100, max(1, int((params.get("limit") or ["30"])[0] or 30)))
        rows = rows_to_dicts(
            db.execute(
                "SELECT * FROM payroll_import_batches ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )
        for row in rows:
            try:
                row["summary"] = json.loads(row.pop("summary_json") or "{}")
            except json.JSONDecodeError:
                row["summary"] = {}
        self.send_json({"ok": True, "batches": rows})

    def api_payroll_attendance_summary(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        month = str((params.get("month") or [""])[0] or "").strip()
        employee_no = lq_payroll_import.normalize_employee_no(str((params.get("employee_no") or [""])[0] or ""))
        punch_count = db.execute("SELECT COUNT(*) FROM attendance_punches").fetchone()[0]
        day_count = db.execute("SELECT COUNT(*) FROM attendance_days").fetchone()[0]
        adj_count = db.execute("SELECT COUNT(*) FROM attendance_adjustments").fetchone()[0]
        batch_count = db.execute("SELECT COUNT(*) FROM payroll_import_batches").fetchone()[0]
        recent_batches = rows_to_dicts(
            db.execute(
                "SELECT id, import_type, file_name, project_name, salary_month, row_count, created_by, created_at FROM payroll_import_batches ORDER BY created_at DESC LIMIT 8"
            ).fetchall()
        )
        punches_sql = "SELECT employee_no, employee_name, punch_date, COUNT(*) AS punch_count FROM attendance_punches"
        punches_args: List[Any] = []
        if month:
            punches_sql += " WHERE punch_date LIKE ?"
            punches_args.append(f"{month}%")
        if employee_no:
            punches_sql += " AND employee_no=?" if month else " WHERE employee_no=?"
            punches_args.append(employee_no)
        punches_sql += " GROUP BY employee_no, employee_name, punch_date ORDER BY punch_date DESC LIMIT 50"
        daily = rows_to_dicts(db.execute(punches_sql, punches_args).fetchall())
        self.send_json({
            "ok": True,
            "summary": {
                "punch_count": int(punch_count or 0),
                "attendance_day_rows": int(day_count or 0),
                "adjustment_count": int(adj_count or 0),
                "batch_count": int(batch_count or 0),
            },
            "recent_batches": recent_batches,
            "daily_punches": daily,
        })

    def api_alert_dismiss(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        alert_key = str(data.get("alert_key") or data.get("id") or "").strip()
        if not alert_key:
            return self.send_json({"ok": False, "error": "alert_key required"}, 400)
        existing = db.execute(
            "SELECT id FROM alert_dismissals WHERE user_id=? AND alert_key=?",
            (user["id"], alert_key),
        ).fetchone()
        if not existing:
            insert(
                db,
                "alert_dismissals",
                {
                    "id": uid("AD"),
                    "user_id": user["id"],
                    "alert_key": alert_key,
                    "dismissed_at": now_iso(),
                },
            )
        audit(db, user, "dismiss_alert", "alert_dismissals", alert_key, "Dismissed alert")
        db.commit()
        center = build_alert_center(
            db, user_id=user.get("id"), role=str(user.get("role") or "viewer")
        )
        self.send_json({"ok": True, "center": center})

    def api_alert_notify(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        channel = str(data.get("channel") or "email").strip().lower()
        recipient = str(data.get("recipient") or SUPPORT_EMAIL).strip()
        center = build_alert_center(
            db, user_id=user.get("id"), role=str(user.get("role") or "viewer")
        )
        alerts = center.get("alerts") or []
        high = [a for a in alerts if a.get("level") in ("Critical", "High")]
        subject = f"{COMPANY_NAME} — تنبيهات ({len(high)} عاجلة)"
        lines = [f"مركز التنبيهات · {now_iso()}", ""]
        for a in high[:25]:
            lines.append(f"[{a.get('level')}] {a.get('title')}: {a.get('text')}")
        body = "\n".join(lines)
        status = "queued"
        detail = ""
        if channel == "email":
            ok, detail = send_alert_email(recipient, subject, body)
            status = "sent" if ok else "failed"
        elif channel == "sms":
            status = "queued"
            detail = "SMS channel queued — تكوين LQ_SMS_ENABLED مطلوب للإرسال الفعلي"
        else:
            return self.send_json({"ok": False, "error": "Unsupported channel"}, 400)
        log_id = uid("ALN")
        insert(
            db,
            "alert_notifications",
            {
                "id": log_id,
                "created_at": now_iso(),
                "channel": channel,
                "recipient": recipient,
                "subject": subject,
                "message": body[:4000],
                "status": status,
                "alert_count": len(high),
                "sent_by": user.get("name") or user.get("username"),
            },
        )
        audit(db, user, "alert_notify", "alert_notifications", log_id, f"{channel} to {recipient}: {status}")
        db.commit()
        self.send_json({
            "ok": True,
            "notification_id": log_id,
            "channel": channel,
            "status": status,
            "detail": detail,
            "alert_count": len(high),
        })

    def api_report_bank_reconciliation(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        reconciliation_id = (params.get("reconciliation_id") or [""])[0].strip()
        bank_name = (params.get("bank_name") or [""])[0].strip()
        period_name = (params.get("period_name") or [""])[0].strip()
        owner = user.get("name") or user.get("username") or "المحاسب"
        if reconciliation_id:
            rec = db.execute("SELECT * FROM bank_reconciliations WHERE id=?", (reconciliation_id,)).fetchone()
            if not rec:
                return self.send_json({"ok": False, "error": "Reconciliation not found"}, 404)
            rec_dict = dict(rec)
            preview = build_bank_reconciliation_data(
                db, bank_name=rec_dict.get("bank_name") or "", period_name=rec_dict.get("period_name") or "",
            )
            html = build_bank_reconciliation_html(rec_dict, preview, owner)
            return self.send_html(html)
        preview = build_bank_reconciliation_data(db, bank_name=bank_name, period_name=period_name)
        rec_dict = {
            "bank_name": bank_name or preview.get("bank_name"),
            "period_name": period_name or preview.get("period_name"),
            "book_balance": preview.get("book_balance"),
            "bank_balance": 0,
            "difference": preview.get("book_balance"),
            "status": "Preview",
            "reconciled_by": owner,
            "reconciled_at": now_iso(),
            "matched_count": preview.get("matched_count"),
            "unmatched_count": preview.get("unmatched_count"),
            "period_start": preview.get("period_start"),
            "period_end": preview.get("period_end"),
            "notes": "معاينة قبل الحفظ",
        }
        html = build_bank_reconciliation_html(rec_dict, preview, owner)
        self.send_html(html)

    def api_report_hospitality(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        folio_id = (params.get("folio_id") or [""])[0].strip()
        from_date = (params.get("from") or [date.today().replace(day=1).isoformat()])[0].strip() or date.today().replace(day=1).isoformat()
        to_date = (params.get("to") or [today()])[0].strip() or today()
        owner = user.get("name") or user.get("username") or COMPANY_NAME
        if folio_id:
            folio = db.execute(
                """
                SELECT f.*, b.guest_name, b.guest_phone, b.checkin_date, b.checkout_date, b.nights, b.room_id,
                       r.room_code, r.room_type, p.name AS property_name
                FROM hospitality_folios f
                LEFT JOIN hospitality_bookings b ON b.id=f.booking_id
                LEFT JOIN hospitality_rooms r ON r.id=b.room_id
                LEFT JOIN properties p ON p.id=b.property_id
                WHERE f.id=? OR f.folio_no=?
                """,
                (folio_id, folio_id),
            ).fetchone()
            if not folio:
                return self.send_json({"ok": False, "error": "Hospitality folio not found"}, 404)
            html = build_hospitality_folio_html(dict(folio), owner)
            return self.send_html(html)
        try:
            datetime.fromisoformat(from_date)
            datetime.fromisoformat(to_date)
        except Exception:
            return self.send_json({"ok": False, "error": "Invalid date range"}, 400)
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        summary = build_hospitality_summary(db, from_date, to_date)
        html = build_hospitality_report_html(summary, owner)
        self.send_html(html)

    def api_financial_statements(self, db: sqlite3.Connection) -> None:
        accounts = rows_to_dicts(db.execute("SELECT * FROM accounts").fetchall())
        invoices = rows_to_dicts(db.execute("SELECT * FROM invoices").fetchall())
        purchase_invoices = rows_to_dicts(db.execute("SELECT * FROM purchase_invoices").fetchall())
        salaries = rows_to_dicts(db.execute("SELECT * FROM salaries").fetchall())
        admin_expenses = rows_to_dicts(db.execute("SELECT * FROM admin_expenses").fetchall())
        inventory = rows_to_dicts(db.execute("SELECT * FROM inventory_items").fetchall())
        bank = rows_to_dicts(db.execute("SELECT * FROM bank_transactions").fetchall())
        income = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "income")
        expense = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "expense")
        ar = sum(max(0, float(i["amount"] or 0)-float(i["paid_amount"] or 0)) for i in invoices)
        ap = sum(max(0, float(p["amount"] or 0)-float(p["paid_amount"] or 0)) for p in purchase_invoices)
        inventory_value = sum(float(i["quantity"] or 0)*float(i["unit_cost"] or 0) for i in inventory)
        bank_balance = sum((1 if b["type"] in ("deposit","in","income") else -1)*float(b["amount"] or 0) for b in bank)
        payroll = sum(float(s["net_salary"] or 0) for s in salaries)
        ga = sum(float(e["amount"] or 0) for e in admin_expenses)
        self.send_json({"ok": True, "statements": {
            "income_statement": {"revenue": income, "expenses": expense, "net_income": income-expense, "payroll": payroll, "general_admin": ga},
            "balance_sheet": {"assets": {"cash_bank": bank_balance, "accounts_receivable": ar, "inventory": inventory_value}, "liabilities": {"accounts_payable": ap}, "equity": {"retained_earnings": income-expense}},
            "linked_storage": {"tables": sorted(TABLES.keys()), "backup_ready": True}
        }})

    def api_accounts_insights(self, db: sqlite3.Connection, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        months_limit = max(3, min(18, int((params.get("months") or ["6"])[0] or "6")))
        rows = rows_to_dicts(db.execute("SELECT entry_date,type,category,amount FROM accounts ORDER BY entry_date ASC").fetchall())
        month_buckets: Dict[str, Dict[str, float]] = {}
        expense_by_category: Dict[str, float] = {}
        income_by_category: Dict[str, float] = {}
        today_dt = date.today()
        for i in range(months_limit):
            dt = (today_dt.replace(day=1) - timedelta(days=31 * i)).replace(day=1)
            key = dt.strftime("%Y-%m")
            month_buckets[key] = {"income": 0.0, "expense": 0.0}
        for row in rows:
            entry_date = str(row.get("entry_date") or "").strip()
            amount = float(row.get("amount") or 0)
            tx_type = str(row.get("type") or "").strip().lower()
            category = str(row.get("category") or "غير مصنف").strip() or "غير مصنف"
            month_key = entry_date[:7] if len(entry_date) >= 7 else ""
            if month_key in month_buckets:
                if tx_type == "income":
                    month_buckets[month_key]["income"] += amount
                elif tx_type == "expense":
                    month_buckets[month_key]["expense"] += amount
            if tx_type == "income":
                income_by_category[category] = income_by_category.get(category, 0.0) + amount
            elif tx_type == "expense":
                expense_by_category[category] = expense_by_category.get(category, 0.0) + amount
        series = []
        for key in sorted(month_buckets.keys()):
            m = month_buckets[key]
            series.append({"month": key, "income": round(m["income"], 3), "expense": round(m["expense"], 3), "net": round(m["income"] - m["expense"], 3)})
        top_expense = [{"category": k, "amount": round(v, 3)} for k, v in sorted(expense_by_category.items(), key=lambda item: item[1], reverse=True)[:6]]
        top_income = [{"category": k, "amount": round(v, 3)} for k, v in sorted(income_by_category.items(), key=lambda item: item[1], reverse=True)[:6]]
        self.send_json(
            {
                "ok": True,
                "months": months_limit,
                "cashflow_series": series,
                "top_expense_categories": top_expense,
                "top_income_categories": top_income,
            }
        )

    def api_hospitality_summary(self, db: sqlite3.Connection, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        from_date = str((params.get("from") or [today()])[0]).strip() or today()
        to_date = str((params.get("to") or [today()])[0]).strip() or today()
        try:
            datetime.fromisoformat(from_date)
            datetime.fromisoformat(to_date)
        except Exception:
            return self.send_json({"ok": False, "error": "صيغة التاريخ غير صحيحة"}, 400)
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        self.send_json({"ok": True, "summary": build_hospitality_summary(db, from_date, to_date)})

    def api_accountant_reports(self, db: sqlite3.Connection, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        report_type = (params.get("type") or ["summary"])[0].strip().lower()
        client_id = (params.get("client_id") or [""])[0].strip()
        month = (params.get("month") or [today()[:7]])[0].strip()
        payload = build_accountant_report_data(db, report_type, client_id=client_id, month=month)
        if payload.get("error"):
            return self.send_json({"ok": False, "error": payload["error"]}, 400)
        self.send_json({"ok": True, "type": report_type, "report": payload})

    def api_accounting_platform_overview(self, db: sqlite3.Connection, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        months = max(3, min(18, int((params.get("months") or ["12"])[0] or 12)))
        today_d = date.today()
        invoices = rows_to_dicts(db.execute("SELECT invoice_no, issue_date, due_date, amount, paid_amount, status, client_id FROM invoices").fetchall())
        estate_inv = rows_to_dicts(db.execute("SELECT invoice_no, issued_at, due_date, amount, paid_amount, status FROM estate_contract_invoices").fetchall())
        accounts_rows = rows_to_dicts(db.execute("SELECT entry_date, type, amount, category FROM accounts").fetchall())
        periods = rows_to_dicts(db.execute("SELECT id, period_name, start_date, end_date, status, closed_at FROM financial_periods ORDER BY start_date DESC").fetchall())
        month_closes = rows_to_dicts(db.execute("SELECT month_key, status, total_invoiced, total_collected, outstanding_due, closed_at FROM estate_month_closes ORDER BY month_key DESC").fetchall())
        bank_total = float(db.execute("SELECT COALESCE(SUM(CASE WHEN type IN ('deposit','in','income') THEN amount ELSE -amount END),0) FROM bank_transactions").fetchone()[0] or 0)

        billed_total = 0.0
        collected_total = 0.0
        overdue_total = 0.0
        aging = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}

        def consume_invoice_rows(rows: List[Dict[str, Any]], issue_key: str) -> None:
            nonlocal billed_total, collected_total, overdue_total
            for r in rows:
                amount = float(r.get("amount") or 0)
                paid = float(r.get("paid_amount") or 0)
                rem = max(0.0, amount - paid)
                billed_total += amount
                collected_total += paid
                due_s = str(r.get("due_date") or "").strip()
                if rem <= 0 or not due_s:
                    continue
                try:
                    due_d = datetime.fromisoformat(due_s).date()
                except Exception:
                    continue
                if due_d < today_d:
                    overdue_total += rem
                    days = (today_d - due_d).days
                    if days <= 30:
                        aging["0-30"] += rem
                    elif days <= 60:
                        aging["31-60"] += rem
                    elif days <= 90:
                        aging["61-90"] += rem
                    else:
                        aging["90+"] += rem

        consume_invoice_rows(invoices, "issue_date")
        consume_invoice_rows(estate_inv, "issued_at")

        monthly: List[Dict[str, Any]] = []
        for i in range(months - 1, -1, -1):
            anchor = add_months(today_d.replace(day=1), -i)
            mk = anchor.strftime("%Y-%m")
            income = sum(float(a.get("amount") or 0) for a in accounts_rows if str(a.get("entry_date") or "").startswith(mk) and str(a.get("type") or "").lower() == "income")
            expense = sum(float(a.get("amount") or 0) for a in accounts_rows if str(a.get("entry_date") or "").startswith(mk) and str(a.get("type") or "").lower() == "expense")
            billed_m = sum(float(x.get("amount") or 0) for x in invoices if str(x.get("issue_date") or "").startswith(mk)) + sum(float(x.get("amount") or 0) for x in estate_inv if str(x.get("issued_at") or "").startswith(mk))
            collected_m = sum(float(x.get("paid_amount") or 0) for x in invoices if str(x.get("issue_date") or "").startswith(mk)) + sum(float(x.get("paid_amount") or 0) for x in estate_inv if str(x.get("issued_at") or "").startswith(mk))
            monthly.append({"month": mk, "income": round(income, 3), "expense": round(expense, 3), "net": round(income - expense, 3), "billed": round(billed_m, 3), "collected": round(collected_m, 3)})

        forecast_30 = 0.0
        for r in invoices + estate_inv:
            amount = float(r.get("amount") or 0)
            paid = float(r.get("paid_amount") or 0)
            rem = max(0.0, amount - paid)
            due_s = str(r.get("due_date") or "").strip()
            if rem <= 0 or not due_s:
                continue
            try:
                due_d = datetime.fromisoformat(due_s).date()
            except Exception:
                continue
            if today_d <= due_d <= (today_d + timedelta(days=30)):
                forecast_30 += rem

        open_periods = [p for p in periods if str(p.get("status") or "").lower() == "open"]
        closed_periods = [p for p in periods if str(p.get("status") or "").lower() == "closed"]
        latest_close = month_closes[0] if month_closes else None
        overdue_count = int(
            sum(
                1
                for r in invoices + estate_inv
                if max(0.0, float(r.get("amount") or 0) - float(r.get("paid_amount") or 0)) > 0
                and str(r.get("due_date") or "") < today()
            )
        )

        decisions: List[Dict[str, Any]] = []
        if overdue_total > 0:
            decisions.append({"severity": "high", "title": "تحصيل عاجل", "detail": f"المتأخرات الحالية {fmt_omr(overdue_total)}", "action_section": "invoices"})
        if len(open_periods) > 2:
            decisions.append({"severity": "medium", "title": "فترات كثيرة مفتوحة", "detail": f"يوجد {len(open_periods)} فترات مفتوحة — يفضل الإقفال التدريجي", "action_section": "financial-periods"})
        if bank_total < 0:
            decisions.append({"severity": "high", "title": "رصيد البنك سلبي", "detail": f"الرصيد الحالي {fmt_omr(bank_total)}", "action_section": "bank"})
        if not decisions:
            decisions.append({"severity": "ok", "title": "الوضع المحاسبي مستقر", "detail": "لا توجد مخاطر مالية عاجلة حسب المؤشرات الحالية", "action_section": "accounts"})

        health = 100
        if overdue_total > 0:
            health -= min(35, int(overdue_total / 500))
        if len(open_periods) > 2:
            health -= min(20, len(open_periods) * 3)
        if bank_total < 0:
            health -= 15
        health = max(0, min(100, health))

        self.send_json(
            {
                "ok": True,
                "kpis": {
                    "billed_total": round(billed_total, 3),
                    "collected_total": round(collected_total, 3),
                    "overdue_total": round(overdue_total, 3),
                    "forecast_next_30_days": round(forecast_30, 3),
                    "bank_balance": round(bank_total, 3),
                    "open_periods": len(open_periods),
                    "closed_periods": len(closed_periods),
                    "overdue_count": overdue_count,
                    "health": health,
                },
                "aging": {k: round(v, 3) for k, v in aging.items()},
                "cashflow_monthly": monthly,
                "decisions": decisions,
                "latest_month_close": latest_close,
                "periods_summary": {
                    "open": len(open_periods),
                    "closed": len(closed_periods),
                    "latest_open": open_periods[0] if open_periods else None,
                },
            }
        )

    def api_accounting_cfo_overview(self, db: sqlite3.Connection, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        months = max(3, min(24, int((params.get("months") or ["12"])[0] or 12)))
        today_d = date.today()
        budgets = {
            str(x["month_key"]): x
            for x in rows_to_dicts(
                db.execute(
                    "SELECT month_key, revenue_target, expense_budget, collection_target, cash_reserve_target, notes FROM accounting_budgets"
                ).fetchall()
            )
        }
        accounts_rows = rows_to_dicts(db.execute("SELECT entry_date, type, amount FROM accounts").fetchall())
        inv_rows = rows_to_dicts(db.execute("SELECT issue_date, due_date, amount, paid_amount FROM invoices").fetchall())
        est_inv_rows = rows_to_dicts(db.execute("SELECT issued_at, due_date, amount, paid_amount FROM estate_contract_invoices").fetchall())
        month_closes = {str(x["month_key"]): x for x in rows_to_dicts(db.execute("SELECT month_key, status, closed_at FROM estate_month_closes").fetchall())}

        def month_totals(mk: str) -> Dict[str, float]:
            revenue = sum(float(a.get("amount") or 0) for a in accounts_rows if str(a.get("entry_date") or "").startswith(mk) and str(a.get("type") or "").lower() == "income")
            expense = sum(float(a.get("amount") or 0) for a in accounts_rows if str(a.get("entry_date") or "").startswith(mk) and str(a.get("type") or "").lower() == "expense")
            billed = sum(float(x.get("amount") or 0) for x in inv_rows if str(x.get("issue_date") or "").startswith(mk)) + sum(float(x.get("amount") or 0) for x in est_inv_rows if str(x.get("issued_at") or "").startswith(mk))
            collected = sum(float(x.get("paid_amount") or 0) for x in inv_rows if str(x.get("issue_date") or "").startswith(mk)) + sum(float(x.get("paid_amount") or 0) for x in est_inv_rows if str(x.get("issued_at") or "").startswith(mk))
            return {"revenue": round(revenue, 3), "expense": round(expense, 3), "net": round(revenue - expense, 3), "billed": round(billed, 3), "collected": round(collected, 3)}

        rows: List[Dict[str, Any]] = []
        for i in range(months - 1, -1, -1):
            mk = add_months(today_d.replace(day=1), -i).strftime("%Y-%m")
            actual = month_totals(mk)
            b = budgets.get(mk) or {}
            rev_target = float(b.get("revenue_target") or 0)
            exp_budget = float(b.get("expense_budget") or 0)
            col_target = float(b.get("collection_target") or 0)
            reserve_target = float(b.get("cash_reserve_target") or 0)
            billed = float(actual["billed"] or 0)
            collected = float(actual["collected"] or 0)
            collection_rate = round((collected / billed * 100.0), 2) if billed > 0 else 0.0
            rows.append(
                {
                    "month": mk,
                    "actual_revenue": actual["revenue"],
                    "target_revenue": rev_target,
                    "variance_revenue": round(actual["revenue"] - rev_target, 3),
                    "actual_expense": actual["expense"],
                    "budget_expense": exp_budget,
                    "variance_expense": round(exp_budget - actual["expense"], 3),
                    "actual_net": actual["net"],
                    "billed": actual["billed"],
                    "collected": actual["collected"],
                    "collection_rate": collection_rate,
                    "collection_target": col_target,
                    "cash_reserve_target": reserve_target,
                    "month_closed": bool(month_closes.get(mk)),
                }
            )

        recent = rows[-3:] if len(rows) >= 3 else rows
        avg_collection_rate = 0.0
        if recent:
            avg_collection_rate = sum(float(r.get("collection_rate") or 0) for r in recent) / max(1, len(recent))
        avg_collection_ratio = max(0.0, min(1.0, avg_collection_rate / 100.0))
        open_receivables = 0.0
        for r in inv_rows + est_inv_rows:
            amount = float(r.get("amount") or 0)
            paid = float(r.get("paid_amount") or 0)
            open_receivables += max(0.0, amount - paid)
        purchase_due = float(db.execute("SELECT COALESCE(SUM(amount-paid_amount),0) FROM purchase_invoices WHERE status!='Paid'").fetchone()[0] or 0)
        payroll_pending = float(db.execute("SELECT COALESCE(SUM(net_salary),0) FROM salaries WHERE lower(status)='pending'").fetchone()[0] or 0)
        obligations_30 = round(max(0.0, purchase_due) + max(0.0, payroll_pending), 3)
        bank_balance = float(db.execute("SELECT COALESCE(SUM(CASE WHEN type IN ('deposit','in','income') THEN amount ELSE -amount END),0) FROM bank_transactions").fetchone()[0] or 0)
        scen = {
            "conservative": max(0.40, avg_collection_ratio - 0.15),
            "base": max(0.0, min(1.0, avg_collection_ratio)),
            "optimistic": min(0.98, avg_collection_ratio + 0.12),
        }
        scenarios: List[Dict[str, Any]] = []
        for name, ratio in scen.items():
            projected_col = round(open_receivables * ratio, 3)
            projected_cash_30 = round(bank_balance + projected_col - obligations_30, 3)
            scenarios.append(
                {
                    "name": name,
                    "collection_ratio": round(ratio * 100.0, 2),
                    "projected_collection_30": projected_col,
                    "projected_cash_30": projected_cash_30,
                }
            )
        current = rows[-1] if rows else {}
        alerts: List[Dict[str, Any]] = []
        if current:
            rev_target = float(current.get("target_revenue") or 0)
            exp_budget = float(current.get("budget_expense") or 0)
            col_target = float(current.get("collection_target") or 0)
            reserve_target = float(current.get("cash_reserve_target") or 0)
            if rev_target > 0 and float(current.get("actual_revenue") or 0) < rev_target * 0.9:
                alerts.append({"code": "revenue_below_target", "severity": "high", "message": "الإيراد أقل من الهدف الشهري بأكثر من 10%"})
            if exp_budget > 0 and float(current.get("actual_expense") or 0) > exp_budget * 1.1:
                alerts.append({"code": "expense_over_budget", "severity": "high", "message": "المصروفات تجاوزت الموازنة بأكثر من 10%"})
            if col_target > 0 and float(current.get("collected") or 0) < col_target * 0.9:
                alerts.append({"code": "collection_below_target", "severity": "medium", "message": "التحصيل أقل من الهدف الشهري"})
            if reserve_target > 0 and scenarios:
                base_cash = float(next((x["projected_cash_30"] for x in scenarios if x["name"] == "base"), 0))
                if base_cash < reserve_target:
                    alerts.append({"code": "cash_reserve_risk", "severity": "high", "message": "التوقع النقدي الأساسي أقل من حد الاحتياطي المطلوب"})

        decisions: List[Dict[str, Any]] = []
        if alerts:
            for a in alerts:
                go = "invoices" if "collection" in a["code"] or "revenue" in a["code"] else ("admin-expenses" if "expense" in a["code"] else "bank")
                decisions.append({"severity": a["severity"], "title": a["code"], "detail": a["message"], "action_section": go})
        else:
            decisions.append({"severity": "ok", "title": "stable", "detail": "المؤشرات المالية ضمن الحدود المحددة", "action_section": "accounts"})

        self.send_json(
            {
                "ok": True,
                "months": rows,
                "kpis": {
                    "bank_balance": round(bank_balance, 3),
                    "open_receivables": round(open_receivables, 3),
                    "obligations_30_days": obligations_30,
                    "avg_collection_rate": round(avg_collection_rate, 2),
                },
                "scenarios": scenarios,
                "alerts": alerts,
                "decisions": decisions,
            }
        )

    def api_report_accountant(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        report_type = (params.get("type") or ["summary"])[0].strip().lower()
        client_id = (params.get("client_id") or [""])[0].strip()
        month = (params.get("month") or [today()[:7]])[0].strip()
        payload = build_accountant_report_data(db, report_type, client_id=client_id, month=month)
        if payload.get("error"):
            return self.send_json({"ok": False, "error": payload["error"]}, 400)
        owner = user.get("name") or user.get("username") or "المحاسب"
        html = build_accountant_report_html(report_type, payload, owner, client_id=client_id, month=month)
        self.send_html(html)

    def api_production_status(self, db: sqlite3.Connection) -> None:
        workflow_policies = load_workflow_policies(db)
        props = db.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
        clients = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        contracts = db.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        invoices = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        accounts = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        users = db.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        audit_rows = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        chart = db.execute("SELECT COUNT(*) FROM chart_accounts").fetchone()[0]
        bank_rows = db.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        inv_bad = db.execute("SELECT COUNT(*) FROM invoices WHERE contract_id NOT IN (SELECT id FROM contracts)").fetchone()[0]
        con_bad = db.execute("SELECT COUNT(*) FROM contracts WHERE property_id NOT IN (SELECT id FROM properties) OR client_id NOT IN (SELECT id FROM clients)").fetchone()[0]
        overdue = db.execute("SELECT COALESCE(SUM(amount-paid_amount),0) FROM invoices WHERE status!='Paid' AND due_date < ?", (today(),)).fetchone()[0]
        low_stock = db.execute("SELECT COUNT(*) FROM inventory_items WHERE quantity <= min_quantity").fetchone()[0]
        business_checks = [
            {"name": "العقارات والوحدات", "ok": props > 0, "value": props, "kind": "business"},
            {"name": "المستأجرون", "ok": clients > 0, "value": clients, "kind": "business"},
            {"name": "العقود", "ok": contracts > 0 and con_bad == 0, "value": contracts, "kind": "business"},
            {"name": "الفواتير", "ok": invoices > 0 and inv_bad == 0, "value": invoices, "kind": "business"},
            {"name": "الحسابات", "ok": accounts > 0, "value": accounts, "kind": "business"},
            {"name": "دليل الحسابات", "ok": chart >= 8, "value": chart, "kind": "business"},
            {"name": "كشف البنك", "ok": bank_rows > 0, "value": bank_rows, "kind": "business"},
        ]
        platform = build_platform_readiness(db)
        platform_checks = [
            {"name": "المستخدمون والصلاحيات", "ok": users >= 1, "value": users, "kind": "platform"},
            {"name": "سجل التدقيق", "ok": True, "value": audit_rows, "kind": "platform"},
            {"name": "قاعدة البيانات (SQLite)", "ok": bool(platform["components"]["database"].get("ready")), "value": platform["components"]["database"].get("sqlite", {}).get("tables", 0), "kind": "platform"},
            {"name": "التخزين الدائم", "ok": bool(platform["components"]["storage"].get("production_storage_ready")), "value": platform["components"]["storage"].get("mode") or "local", "kind": "platform"},
            {"name": "الأمان / MFA", "ok": bool(platform["components"]["security"].get("ready")), "value": platform["components"]["security"].get("mfa_mode") or "soft", "kind": "platform"},
        ]
        checks = platform_checks + business_checks
        business_score = round(sum(1 for c in business_checks if c["ok"]) / max(len(business_checks), 1) * 100, 1)
        platform_score = float(platform.get("platform_score") or 0)
        # Overall score prioritizes platform readiness; empty real-only business data does not tank the platform.
        score = platform_score
        self.send_json({
            "ok": True,
            "version": APP_VERSION,
            "score": score,
            "platform_score": platform_score,
            "business_score": business_score,
            "platform_ready": bool(platform.get("platform_ready")),
            "real_only": True,
            "checks": checks,
            "platform_readiness": platform,
            "alerts": {"overdue": float(overdue or 0), "low_stock": low_stock, "broken_contract_links": con_bad, "broken_invoice_links": inv_bad},
            "workflow": {
                "policy_count": len(workflow_policies),
                "contract_activation_owner_admin_only": _workflow_policy_bool(workflow_policies, "contract_activation_owner_admin_only"),
                "manual_invoice_approval_threshold": _workflow_policy_float(workflow_policies, "manual_invoice_approval_threshold"),
                "payment_approval_threshold": _workflow_policy_float(workflow_policies, "payment_approval_threshold"),
            },
        })

    def api_workflow_policies(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        policies = load_workflow_policies(db)
        self.send_json(
            {
                "ok": True,
                "policies": policies,
                "defaults": WORKFLOW_POLICY_DEFAULTS,
                "editable": str(user.get("role") or "").strip().lower() in ("owner", "admin"),
            }
        )

    def api_update_workflow_policies(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        incoming = data.get("policies")
        if not isinstance(incoming, dict) or not incoming:
            return self.send_json({"ok": False, "error": "policies object required"}, 400)
        current = load_workflow_policies(db)
        updated: Dict[str, Any] = {}
        for key, raw in incoming.items():
            try:
                val = _coerce_workflow_policy_value(str(key), raw)
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
            db.execute(
                """
                INSERT INTO workflow_policies(key, value_json, updated_at, updated_by)
                VALUES(?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at,
                    updated_by=excluded.updated_by
                """,
                (
                    key,
                    json.dumps(val, ensure_ascii=False),
                    now_iso(),
                    user.get("username") or user.get("name") or "system",
                ),
            )
            updated[key] = val
            current[key] = val
        audit(
            db,
            user,
            "workflow_policy_update",
            "workflow_policies",
            None,
            " | ".join([f"{k}={updated[k]}" for k in sorted(updated.keys())]),
        )
        db.commit()
        self.send_json({"ok": True, "policies": current, "updated": updated})

    def api_backup(self, db: sqlite3.Connection) -> None:
        self.send_json({"ok": True, "backup": build_backup_payload(db)})

    def api_backup_archive(self, db: sqlite3.Connection) -> None:
        self.send_json({"ok": True, "archive": build_backup_payload(db), "exported_at": now_iso()})

    def api_backup_status(self) -> None:
        recent = list_automatic_backups()
        self.send_json({
            "ok": True,
            "auto_backup": {
                "enabled": AUTO_BACKUP_ENABLED,
                "interval_hours": BACKUP_INTERVAL_HOURS,
                "retention": BACKUP_RETENTION,
                "directory": str(BACKUP_DIR),
                "last_backup": LAST_AUTO_BACKUP_AT or (recent[0]["created_at"] if recent else None),
            },
            "storage": storage_status(),
            "object_storage": lq_object_storage.object_storage_status(),
            "backup_integrity": latest_backup_integrity(),
            "offsite": offsite_config(),
            "recent": recent[:10],
        })

    def api_backup_verify(self, db: sqlite3.Connection) -> None:
        result = verify_backup_restore(db)
        self.send_json({"ok": result["ok"], "verification": result})

    def api_backup_download(self, query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        kind = (params.get("kind") or ["json"])[0].lower()
        timestamp = (params.get("timestamp") or [""])[0] or None
        path = resolve_backup_file(kind, timestamp)
        if not path:
            return self.send_json({"ok": False, "error": "Backup file not found"}, 404)
        try:
            path.resolve().relative_to(BACKUP_DIR.resolve())
        except ValueError:
            return self.send_json({"ok": False, "error": "Invalid backup path"}, 400)
        raw = path.read_bytes()
        ctype = "application/json" if kind == "json" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_backup_run(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        audit(db, user, "backup", "database", None, "Manual automatic backup triggered")
        db.commit()
        result = run_automatic_backup("manual")
        if not result:
            return self.send_json({"ok": False, "error": "Backup already running or failed"}, 503)
        self.send_json({"ok": True, "backup": result})

    def api_restore(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        backup = data.get("backup") or data
        tables = backup.get("tables", {})
        mode = data.get("mode") or "merge"
        restore_backup_tables(db, tables, mode=mode)
        audit(db, user, "restore", "database", None, f"Restore mode {mode}")
        db.commit()
        self.send_json({"ok": True})

    def api_admin_reset_operational(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        """Wipe all business data; keep users and login devices. Requires confirm=RESET."""
        data = self.read_json()
        confirm = str(data.get("confirm") or "").strip().upper()
        if confirm not in ("RESET", "YES", "1", "TRUE"):
            return self.send_json(
                {
                    "ok": False,
                    "error": "confirm=RESET required — this deletes properties, clients, contracts, invoices, and related records",
                },
                400,
            )
        uname = str(user.get("username") or "").strip().lower()
        role = str(user.get("role") or "").strip().lower()
        if uname not in FULL_ACCESS_USERNAMES and role not in ("admin", "owner"):
            return self.send_json({"ok": False, "error": "Permission denied — admin/owner only"}, 403)
        # Safety snapshot before wipe
        backup = run_automatic_backup(reason="pre-operational-reset")
        result = reset_operational_data(db, clear_uploads=bool(data.get("clear_uploads", True)))
        audit(
            db,
            user,
            "reset_operational",
            "database",
            "wipe",
            f"users_kept={result.get('users_kept')} uploads={result.get('uploads')}",
        )
        db.commit()
        self.send_json(
            {
                "ok": True,
                "message": "تم تصفير بيانات العمل — الحسابات محفوظة",
                "users_kept": result.get("users_kept"),
                "cleared": result.get("cleared"),
                "uploads": result.get("uploads"),
                "kept": result.get("kept"),
                "backup_before": backup,
            }
        )

    def api_export_csv(self, db: sqlite3.Connection, table: str) -> None:
        if table not in TABLES:
            return self.send_json({"ok": False, "error": "Unknown table"}, 404)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=TABLES[table])
        writer.writeheader()
        for row in rows_to_dicts(db.execute(f"SELECT {','.join(TABLES[table])} FROM {table}").fetchall()):
            writer.writerow(row)
        raw = output.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=jawdah-{table}.csv")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_export_timeline_audit_csv(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        if not is_primary_owner_user(user):
            return self.send_json({"ok": False, "error": "لوحة المالك الحية مخصصة لوليد ويعقوب فقط"}, 403)
        params = urllib.parse.parse_qs(query or "")
        timeline_days = normalize_timeline_days((params.get("timeline_days") or ["7"])[0], 7)
        timeline_cutoff = (datetime.now() - timedelta(days=timeline_days)).strftime("%Y-%m-%d %H:%M:%S") if timeline_days > 0 else ""
        sql = """
            SELECT
                a.created_at,
                a.username,
                a.entity_id AS booking_id,
                r.room_code,
                b.guest_name,
                b.checkin_date,
                b.checkout_date,
                a.details
            FROM audit_log a
            LEFT JOIN hospitality_bookings b ON b.id = a.entity_id
            LEFT JOIN hospitality_rooms r ON r.id = b.room_id
            WHERE a.action = 'timeline_update'
              AND a.entity = 'hospitality_bookings'
        """
        args: List[Any] = []
        if timeline_days > 0:
            sql += " AND datetime(a.created_at) >= datetime(?)"
            args.append(timeline_cutoff)
        sql += " ORDER BY a.created_at DESC LIMIT 1000"
        rows = rows_to_dicts(db.execute(sql, tuple(args)).fetchall())
        output = io.StringIO()
        fieldnames = [
            "created_at",
            "username",
            "booking_id",
            "room_code",
            "guest_name",
            "checkin_date",
            "checkout_date",
            "details",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})
        raw = output.getvalue().encode("utf-8-sig")
        suffix = "all" if timeline_days == 0 else f"{timeline_days}d"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=jawdah-timeline-audit-{suffix}.csv")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_export_module_fix_history_csv(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        rows, filters = self.query_module_fix_history_rows(db, query, default_limit=500, max_limit=2000)
        output = io.StringIO()
        fieldnames = [
            "id",
            "created_at",
            "username",
            "mode",
            "status",
            "preview_id",
            "modules",
            "max_rows",
            "candidates",
            "applied",
            "score_before",
            "score_after",
            "issues_before",
            "issues_after",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row.get("id"),
                    "created_at": row.get("created_at"),
                    "username": row.get("username"),
                    "mode": row.get("mode"),
                    "status": row.get("status"),
                    "preview_id": row.get("preview_id"),
                    "modules": row.get("modules"),
                    "max_rows": row.get("max_rows"),
                    "candidates": row.get("candidates"),
                    "applied": row.get("applied"),
                    "score_before": row.get("score_before"),
                    "score_after": row.get("score_after"),
                    "issues_before": row.get("issues_before"),
                    "issues_after": row.get("issues_after"),
                }
            )
        raw = output.getvalue().encode("utf-8-sig")
        suffix = today()
        mode_suffix = filters.get("mode") or "all"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=jawdah-module-fix-history-{mode_suffix}-{suffix}.csv")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_export_bundle_zip(self, user: Dict[str, Any]) -> None:
        data = self.read_json()
        files = data.get("files") if isinstance(data, dict) else None
        if not isinstance(files, dict) or not files:
            return self.send_json({"ok": False, "error": "No files provided"}, 400)
        if len(files) > 30:
            return self.send_json({"ok": False, "error": "Too many files"}, 400)
        zip_buffer = io.BytesIO()
        total_bytes = 0
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                if not isinstance(name, str) or not isinstance(content, str):
                    continue
                safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name.strip())[:120] or "export.csv"
                if not re.search(r"\.(csv|json|txt)$", safe_name.lower()):
                    safe_name += ".csv"
                raw = content.encode("utf-8-sig")
                total_bytes += len(raw)
                if total_bytes > 15 * 1024 * 1024:
                    return self.send_json({"ok": False, "error": "Export bundle too large"}, 400)
                zf.writestr(safe_name, raw)
        out = zip_buffer.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="jawdah-filtered-bundle-{date.today().isoformat()}.zip"')
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def api_operations_check(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        checks: List[Dict[str, Any]] = []
        props = db.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
        clients = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        contracts = db.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        invoices = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        broken_contracts = db.execute(
            "SELECT COUNT(*) FROM contracts WHERE property_id NOT IN (SELECT id FROM properties) OR client_id NOT IN (SELECT id FROM clients)"
        ).fetchone()[0]
        broken_invoices = db.execute(
            "SELECT COUNT(*) FROM invoices WHERE contract_id NOT IN (SELECT id FROM contracts)"
        ).fetchone()[0]
        overdue = db.execute(
            "SELECT COALESCE(SUM(amount-paid_amount),0) FROM invoices WHERE status!='Paid' AND due_date < ?",
            (today(),),
        ).fetchone()[0]
        branches = db.execute("SELECT COUNT(*) FROM branches").fetchone()[0]
        users_n = int(db.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0] or 0)
        verify = verify_backup_restore(db)
        offsite = offsite_config()
        platform = build_platform_readiness(db)
        backup_recent = list_automatic_backups()
        audit_total = int(db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] or 0)
        audit_today = int(
            db.execute("SELECT COUNT(*) FROM audit_log WHERE created_at>=?", (today() + " 00:00:00",)).fetchone()[0] or 0
        )
        timeline_updates = int(
            db.execute("SELECT COUNT(*) FROM audit_log WHERE action='timeline_update'").fetchone()[0] or 0
        )

        def add(name: str, ok: bool, value: Any = "", hint: str = "", kind: str = "platform") -> None:
            checks.append({"name": name, "ok": ok, "value": value, "hint": hint, "kind": kind})

        # Platform / system readiness (empty real-only business data does not fail these)
        add("المستخدمون", users_n >= 1, users_n, "حسابات الدخول", "platform")
        add("الفروع", branches >= 0, branches, "اختياري حتى تُضاف مواقع", "platform")
        add("نسخ احتياطي", AUTO_BACKUP_ENABLED, LAST_AUTO_BACKUP_AT or "—", "المستندات → نسخ احتياطي", "platform")
        add("فحص الاستعادة", bool(verify.get("ok")), f"{verify.get('score')}%", "backup/verify", "platform")
        add(
            "Off-site",
            bool(offsite.get("enabled")),
            offsite.get("last_push") or offsite.get("mode") or "local-volume",
            offsite.get("note") or "مرآة Volume جاهزة",
            "platform",
        )
        add("جاهزية المنصة", bool(platform.get("platform_ready")), f"{platform.get('platform_score')}%", "/api/platform_readiness", "platform")
        add("سجل العمليات", True, audit_total, "audit_log", "platform")
        add("ربط Timeline", True, timeline_updates, "timeline_update audit events", "platform")

        # Business data (real-only may be empty until staff enter real records)
        add("العقارات مسجّلة", props > 0, props, "أضف عقاراً من قسم المشاريع", "business")
        add("العملاء مسجّلون", clients > 0, clients, "أضف عميلاً من قسم العملاء", "business")
        add("العقود", contracts > 0, contracts, "أنشئ عقداً بعد العقار والعميل", "business")
        add("الفواتير", invoices > 0, invoices, "أنشئ فاتورة من زر «فاتورة» على العقد", "business")
        add("ترابط العقود", broken_contracts == 0, broken_contracts, "عقود مكسورة الربط", "business")
        add("ترابط الفواتير", broken_invoices == 0, broken_invoices, "فواتير بدون عقد", "business")
        add("متأخرات", overdue <= 0, f"{fmt_omr(float(overdue or 0))}", "راجع الفواتير", "business")
        add("عمليات اليوم", audit_today >= 0, audit_today, "إدخال يومي اختياري", "business")

        platform_checks = [c for c in checks if c.get("kind") == "platform"]
        business_checks = [c for c in checks if c.get("kind") == "business"]
        platform_score = round(sum(1 for c in platform_checks if c["ok"]) / max(len(platform_checks), 1) * 100, 1)
        business_score = round(sum(1 for c in business_checks if c["ok"]) / max(len(business_checks), 1) * 100, 1)
        # Overall ops score = platform readiness (real-only empty data must not tank it)
        score = platform_score
        self.send_json({
            "ok": True,
            "version": APP_VERSION,
            "score": score,
            "platform_score": platform_score,
            "business_score": business_score,
            "platform_ready": bool(platform.get("platform_ready")),
            "real_only": True,
            "checks": checks,
            "user_role": user.get("role"),
            "recent_backup": backup_recent[0] if backup_recent else None,
            "offsite": offsite,
            "platform_readiness": platform,
            "audit": {
                "total": audit_total,
                "today": audit_today,
                "timeline_updates": timeline_updates,
            },
        })

    def api_module_integrity(self, db: sqlite3.Connection, return_payload_only: bool = False) -> Optional[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []

        def add_issue(module: str, severity: str, title: str, entity_id: Any = None, details: str = "") -> None:
            issues.append({
                "module": module,
                "severity": severity,
                "title": title,
                "entity_id": entity_id,
                "details": details,
            })

        # Contracts: broken links, invalid dates, conflicting active overlaps.
        broken_contract_rows = rows_to_dicts(
            db.execute(
                """
                SELECT c.id, c.contract_no, c.property_id, c.client_id
                FROM contracts c
                LEFT JOIN properties p ON p.id=c.property_id
                LEFT JOIN clients cl ON cl.id=c.client_id
                WHERE p.id IS NULL OR cl.id IS NULL
                LIMIT 120
                """
            ).fetchall()
        )
        for row in broken_contract_rows:
            add_issue(
                "contracts",
                "critical",
                "عقد مرتبط بعقار/عميل غير موجود",
                row.get("id"),
                f"contract_no={row.get('contract_no') or row.get('id')} property_id={row.get('property_id')} client_id={row.get('client_id')}",
            )

        invalid_contract_dates = rows_to_dicts(
            db.execute(
                """
                SELECT id, contract_no, start_date, end_date
                FROM contracts
                WHERE IFNULL(start_date,'')<>'' AND IFNULL(end_date,'')<>'' AND end_date < start_date
                LIMIT 120
                """
            ).fetchall()
        )
        for row in invalid_contract_dates:
            add_issue(
                "contracts",
                "critical",
                "عقد بتواريخ غير صالحة (النهاية قبل البداية)",
                row.get("id"),
                f"contract_no={row.get('contract_no') or row.get('id')} {row.get('start_date')} -> {row.get('end_date')}",
            )

        active_rows = rows_to_dicts(
            db.execute(
                """
                SELECT id, contract_no, property_id, start_date, end_date
                FROM contracts
                WHERE lower(IFNULL(status,'')) IN ('active','activated')
                ORDER BY property_id, start_date
                """
            ).fetchall()
        )
        by_property: Dict[Any, List[Dict[str, Any]]] = {}
        for row in active_rows:
            by_property.setdefault(row.get("property_id"), []).append(row)
        for pid, rows in by_property.items():
            for i in range(len(rows)):
                a = rows[i]
                a_start = str(a.get("start_date") or "")
                a_end = str(a.get("end_date") or "9999-12-31")
                if not a_start:
                    continue
                for j in range(i + 1, len(rows)):
                    b = rows[j]
                    b_start = str(b.get("start_date") or "")
                    b_end = str(b.get("end_date") or "9999-12-31")
                    if not b_start:
                        continue
                    if b_start > a_end:
                        break
                    if not (a_end < b_start or b_end < a_start):
                        add_issue(
                            "contracts",
                            "critical",
                            "تداخل عقود نشطة على نفس الوحدة",
                            f"{a.get('id')}|{b.get('id')}",
                            f"property_id={pid} A={a.get('contract_no') or a.get('id')} B={b.get('contract_no') or b.get('id')}",
                        )
                        break

        # Invoices & payments integrity
        broken_invoice_rows = rows_to_dicts(
            db.execute(
                """
                SELECT i.id, i.invoice_no, i.contract_id, i.client_id, i.property_id
                FROM invoices i
                LEFT JOIN contracts c ON c.id=i.contract_id
                LEFT JOIN clients cl ON cl.id=i.client_id
                LEFT JOIN properties p ON p.id=i.property_id
                WHERE c.id IS NULL OR cl.id IS NULL OR p.id IS NULL
                LIMIT 120
                """
            ).fetchall()
        )
        for row in broken_invoice_rows:
            add_issue(
                "invoices",
                "critical",
                "فاتورة مرتبطة بسجل مفقود (عقد/عميل/وحدة)",
                row.get("id"),
                f"invoice_no={row.get('invoice_no') or row.get('id')}",
            )

        overpaid_rows = rows_to_dicts(
            db.execute(
                """
                SELECT id, invoice_no, amount, paid_amount
                FROM invoices
                WHERE COALESCE(paid_amount,0) > COALESCE(amount,0)
                LIMIT 120
                """
            ).fetchall()
        )
        for row in overpaid_rows:
            add_issue(
                "invoices",
                "high",
                "فاتورة مدفوعة بأكثر من إجماليها",
                row.get("id"),
                f"invoice_no={row.get('invoice_no') or row.get('id')} paid={row.get('paid_amount')} amount={row.get('amount')}",
            )

        broken_payment_rows = rows_to_dicts(
            db.execute(
                """
                SELECT p.id, p.invoice_id, p.amount, p.payment_date
                FROM payments p
                LEFT JOIN invoices i ON i.id=p.invoice_id
                WHERE i.id IS NULL OR COALESCE(p.amount,0) <= 0
                LIMIT 120
                """
            ).fetchall()
        )
        for row in broken_payment_rows:
            add_issue(
                "payments",
                "high",
                "دفعة غير صالحة (فاتورة مفقودة أو مبلغ <= 0)",
                row.get("id"),
                f"invoice_id={row.get('invoice_id')} amount={row.get('amount')}",
            )

        # Hospitality bookings
        broken_booking_rows = rows_to_dicts(
            db.execute(
                """
                SELECT b.id, b.room_id, b.client_id, b.checkin_date, b.checkout_date, b.status
                FROM hospitality_bookings b
                LEFT JOIN hospitality_rooms r ON r.id=b.room_id
                LEFT JOIN clients c ON c.id=b.client_id
                WHERE r.id IS NULL OR c.id IS NULL
                   OR IFNULL(b.checkin_date,'')='' OR IFNULL(b.checkout_date,'')=''
                   OR b.checkout_date < b.checkin_date
                LIMIT 120
                """
            ).fetchall()
        )
        for row in broken_booking_rows:
            add_issue(
                "hospitality",
                "high",
                "حجز ضيافة غير صالح (مرجع/تواريخ)",
                row.get("id"),
                f"room_id={row.get('room_id')} client_id={row.get('client_id')} {row.get('checkin_date')} -> {row.get('checkout_date')}",
            )

        booking_rows = rows_to_dicts(
            db.execute(
                """
                SELECT id, room_id, checkin_date, checkout_date, status
                FROM hospitality_bookings
                WHERE lower(IFNULL(status,'')) IN ('reserved','checked_in')
                ORDER BY room_id, checkin_date
                """
            ).fetchall()
        )
        by_room: Dict[Any, List[Dict[str, Any]]] = {}
        for row in booking_rows:
            by_room.setdefault(row.get("room_id"), []).append(row)
        for room_id, rows in by_room.items():
            for i in range(len(rows)):
                a = rows[i]
                a_start = str(a.get("checkin_date") or "")
                a_end = str(a.get("checkout_date") or "")
                if not (a_start and a_end):
                    continue
                for j in range(i + 1, len(rows)):
                    b = rows[j]
                    b_start = str(b.get("checkin_date") or "")
                    b_end = str(b.get("checkout_date") or "")
                    if not (b_start and b_end):
                        continue
                    if b_start > a_end:
                        break
                    if not (a_end < b_start or b_end < a_start):
                        add_issue(
                            "hospitality",
                            "critical",
                            "تداخل حجوزات على نفس الغرفة",
                            f"{a.get('id')}|{b.get('id')}",
                            f"room_id={room_id}",
                        )
                        break

        # Inventory consistency
        orphan_tx_rows = rows_to_dicts(
            db.execute(
                """
                SELECT t.id, t.item_id, t.quantity, t.tx_type
                FROM inventory_transactions t
                LEFT JOIN inventory_items i ON i.id=t.item_id
                WHERE i.id IS NULL OR COALESCE(t.quantity,0) <= 0
                LIMIT 120
                """
            ).fetchall()
        )
        for row in orphan_tx_rows:
            add_issue(
                "inventory",
                "high",
                "حركة مخزون غير صالحة (صنف مفقود/كمية <= 0)",
                row.get("id"),
                f"item_id={row.get('item_id')} qty={row.get('quantity')} type={row.get('tx_type')}",
            )

        negative_stock_rows = rows_to_dicts(
            db.execute(
                """
                SELECT id, sku, item_name, quantity
                FROM inventory_items
                WHERE COALESCE(quantity,0) < 0
                LIMIT 120
                """
            ).fetchall()
        )
        for row in negative_stock_rows:
            add_issue(
                "inventory",
                "critical",
                "رصيد مخزون سالب",
                row.get("id"),
                f"{row.get('sku') or row.get('item_name')} quantity={row.get('quantity')}",
            )

        critical_count = sum(1 for x in issues if x["severity"] == "critical")
        high_count = sum(1 for x in issues if x["severity"] == "high")
        total = len(issues)
        score = max(0.0, round(100 - (critical_count * 12 + high_count * 5 + (total - critical_count - high_count) * 2), 1))

        by_module: Dict[str, int] = {}
        for issue in issues:
            key = str(issue.get("module") or "general")
            by_module[key] = by_module.get(key, 0) + 1

        payload = {
            "ok": True,
            "score": score,
            "summary": {
                "total_issues": total,
                "critical": critical_count,
                "high": high_count,
                "other": max(0, total - critical_count - high_count),
            },
            "by_module": by_module,
            "issues": issues[:300],
        }
        if return_payload_only:
            return payload
        self.send_json(payload)
        return None

    def api_module_integrity_fix(
        self,
        db: sqlite3.Connection,
        user: Dict[str, Any],
        return_payload_only: bool = False,
        override_dry_run: Optional[bool] = None,
        override_modules: Optional[List[str]] = None,
        override_max_rows: Optional[int] = None,
        require_preview_guard: bool = True,
        override_preview_id: Optional[str] = None,
        override_confirm_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        payload = self.read_json() if self.command == "POST" else {}
        dry_run = bool((payload or {}).get("dry_run", True)) if override_dry_run is None else bool(override_dry_run)
        allowed_modules = {"contracts", "hospitality", "payments", "invoices", "inventory"}
        if override_modules is not None:
            raw_modules = [str(x).strip().lower() for x in (override_modules or [])]
        else:
            raw_modules = [str(x).strip().lower() for x in ((payload or {}).get("modules") or [])]
        selected_modules = {m for m in raw_modules if m in allowed_modules}
        if not selected_modules:
            selected_modules = set(allowed_modules)
        req_max_rows = override_max_rows if override_max_rows is not None else (payload or {}).get("max_rows", 200)
        try:
            max_rows = int(req_max_rows or 200)
        except Exception:
            max_rows = 200
        max_rows = max(10, min(1000, max_rows))

        cleanup_module_fix_previews()
        username = str(user.get("username") or user.get("name") or "").strip().lower()
        preview_id = str(override_preview_id if override_preview_id is not None else (payload or {}).get("preview_id", "")).strip()
        confirm_text = str(override_confirm_text if override_confirm_text is not None else (payload or {}).get("confirm_text", "")).strip().upper()
        if not dry_run and require_preview_guard:
            if confirm_text != "APPLY":
                log_module_fix_run(
                    db,
                    username=username,
                    mode="apply",
                    status="rejected_missing_confirm",
                    preview_id=preview_id,
                    modules=sorted(selected_modules),
                    max_rows=max_rows,
                    details={"error": "Second approval required"},
                )
                db.commit()
                err = {
                    "ok": False,
                    "error": "Second approval required",
                    "detail": "Send confirm_text='APPLY' and a valid preview_id from dry-run.",
                }
                if return_payload_only:
                    return err
                return self.send_json(err, 400)
            if not preview_id:
                log_module_fix_run(
                    db,
                    username=username,
                    mode="apply",
                    status="rejected_missing_preview",
                    preview_id="",
                    modules=sorted(selected_modules),
                    max_rows=max_rows,
                    details={"error": "Missing preview_id"},
                )
                db.commit()
                err = {"ok": False, "error": "Missing preview_id", "detail": "Run dry-run first to get preview_id."}
                if return_payload_only:
                    return err
                return self.send_json(err, 400)
            pkey = module_fix_preview_key(username, preview_id)
            preview_info = MODULE_FIX_PREVIEWS.get(pkey) or {}
            preview_scope = set(str(x).strip().lower() for x in (preview_info.get("modules") or []))
            if not preview_info:
                log_module_fix_run(
                    db,
                    username=username,
                    mode="apply",
                    status="rejected_invalid_preview",
                    preview_id=preview_id,
                    modules=sorted(selected_modules),
                    max_rows=max_rows,
                    details={"error": "Invalid preview_id"},
                )
                db.commit()
                err = {"ok": False, "error": "Invalid preview_id", "detail": "Preview token not found or expired."}
                if return_payload_only:
                    return err
                return self.send_json(err, 400)
            if preview_scope != set(selected_modules) or int(preview_info.get("max_rows") or 0) != int(max_rows):
                log_module_fix_run(
                    db,
                    username=username,
                    mode="apply",
                    status="rejected_scope_mismatch",
                    preview_id=preview_id,
                    modules=sorted(selected_modules),
                    max_rows=max_rows,
                    details={
                        "error": "Preview scope mismatch",
                        "preview_modules": sorted(preview_scope),
                        "preview_max_rows": int(preview_info.get("max_rows") or 0),
                    },
                )
                db.commit()
                err = {
                    "ok": False,
                    "error": "Preview scope mismatch",
                    "detail": "Scope/max_rows changed after preview. Re-run dry-run first.",
                }
                if return_payload_only:
                    return err
                return self.send_json(err, 400)

        actions: List[Dict[str, Any]] = []

        def add_action(name: str, candidates: int, applied: int, notes: str = "") -> None:
            actions.append(
                {
                    "name": name,
                    "candidates": int(candidates or 0),
                    "applied": int(applied or 0),
                    "notes": notes,
                }
            )
        def enabled(module: str) -> bool:
            return module in selected_modules

        # 1) Contracts with invalid date order.
        if enabled("contracts"):
            bad_contract_dates = rows_to_dicts(
                db.execute(
                    """
                    SELECT id, contract_no, start_date, end_date
                    FROM contracts
                    WHERE IFNULL(start_date,'')<>'' AND IFNULL(end_date,'')<>'' AND end_date < start_date
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            applied_bad_contract_dates = 0
            if not dry_run:
                for row in bad_contract_dates:
                    db.execute(
                        "UPDATE contracts SET start_date=?, end_date=? WHERE id=?",
                        (row.get("end_date"), row.get("start_date"), row.get("id")),
                    )
                    applied_bad_contract_dates += 1
                    audit(
                        db,
                        user,
                        "autofix_swap_dates",
                        "contracts",
                        str(row.get("id")),
                        f"Auto-fix swapped start/end date for contract {row.get('contract_no') or row.get('id')}",
                    )
            add_action("contracts.swap_invalid_dates", len(bad_contract_dates), applied_bad_contract_dates)

        # 2) Hospitality bookings with invalid date order.
        if enabled("hospitality"):
            bad_booking_dates = rows_to_dicts(
                db.execute(
                    """
                    SELECT id, checkin_date, checkout_date
                    FROM hospitality_bookings
                    WHERE IFNULL(checkin_date,'')<>'' AND IFNULL(checkout_date,'')<>'' AND checkout_date < checkin_date
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            applied_bad_booking_dates = 0
            if not dry_run:
                for row in bad_booking_dates:
                    db.execute(
                        "UPDATE hospitality_bookings SET checkin_date=?, checkout_date=? WHERE id=?",
                        (row.get("checkout_date"), row.get("checkin_date"), row.get("id")),
                    )
                    applied_bad_booking_dates += 1
                    audit(
                        db,
                        user,
                        "autofix_swap_dates",
                        "hospitality_bookings",
                        str(row.get("id")),
                        "Auto-fix swapped invalid booking dates",
                    )
            add_action("hospitality.swap_invalid_dates", len(bad_booking_dates), applied_bad_booking_dates)

        # 3) Payments: orphans and non-positive amounts.
        affected_invoice_ids: set[str] = set()
        if enabled("payments"):
            orphan_payments = rows_to_dicts(
                db.execute(
                    """
                    SELECT p.id, p.invoice_id
                    FROM payments p
                    LEFT JOIN invoices i ON i.id=p.invoice_id
                    WHERE i.id IS NULL
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            non_positive_payments = rows_to_dicts(
                db.execute(
                    """
                    SELECT p.id, p.invoice_id, p.amount
                    FROM payments p
                    JOIN invoices i ON i.id=p.invoice_id
                    WHERE COALESCE(p.amount,0) <= 0
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            applied_orphan_payments = 0
            applied_non_positive_payments = 0
            if not dry_run:
                for row in orphan_payments:
                    db.execute("DELETE FROM payments WHERE id=?", (row.get("id"),))
                    applied_orphan_payments += 1
                    audit(
                        db,
                        user,
                        "autofix_delete_orphan",
                        "payments",
                        str(row.get("id")),
                        f"Removed orphan payment invoice_id={row.get('invoice_id')}",
                    )
                for row in non_positive_payments:
                    db.execute("DELETE FROM payments WHERE id=?", (row.get("id"),))
                    applied_non_positive_payments += 1
                    inv_id = str(row.get("invoice_id") or "").strip()
                    if inv_id:
                        affected_invoice_ids.add(inv_id)
                    audit(
                        db,
                        user,
                        "autofix_delete_nonpositive",
                        "payments",
                        str(row.get("id")),
                        f"Removed non-positive payment amount={row.get('amount')}",
                    )
            add_action("payments.delete_orphans", len(orphan_payments), applied_orphan_payments)
            add_action("payments.delete_non_positive", len(non_positive_payments), applied_non_positive_payments)

        # 4) Inventory transactions: remove orphans and normalize non-positive quantity.
        if enabled("inventory"):
            orphan_inv_tx = rows_to_dicts(
                db.execute(
                    """
                    SELECT t.id, t.item_id
                    FROM inventory_transactions t
                    LEFT JOIN inventory_items i ON i.id=t.item_id
                    WHERE i.id IS NULL
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            bad_qty_tx = rows_to_dicts(
                db.execute(
                    """
                    SELECT t.id, t.quantity
                    FROM inventory_transactions t
                    JOIN inventory_items i ON i.id=t.item_id
                    WHERE COALESCE(t.quantity,0) <= 0
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            applied_orphan_tx = 0
            applied_bad_qty_tx = 0
            if not dry_run:
                for row in orphan_inv_tx:
                    db.execute("DELETE FROM inventory_transactions WHERE id=?", (row.get("id"),))
                    applied_orphan_tx += 1
                    audit(
                        db,
                        user,
                        "autofix_delete_orphan",
                        "inventory_transactions",
                        str(row.get("id")),
                        f"Removed orphan inventory transaction item_id={row.get('item_id')}",
                    )
                for row in bad_qty_tx:
                    qty = float(row.get("quantity") or 0)
                    new_qty = abs(qty) if abs(qty) > 0.0001 else 1.0
                    db.execute("UPDATE inventory_transactions SET quantity=? WHERE id=?", (round(new_qty, 3), row.get("id")))
                    applied_bad_qty_tx += 1
                    audit(
                        db,
                        user,
                        "autofix_normalize_quantity",
                        "inventory_transactions",
                        str(row.get("id")),
                        f"Normalized quantity {qty} -> {new_qty}",
                    )
            add_action("inventory_transactions.delete_orphans", len(orphan_inv_tx), applied_orphan_tx)
            add_action("inventory_transactions.normalize_non_positive_qty", len(bad_qty_tx), applied_bad_qty_tx)

        # 5) Inventory items with negative stock -> set to zero.
        if enabled("inventory"):
            negative_stock_rows = rows_to_dicts(
                db.execute(
                    """
                    SELECT id, sku, item_name, quantity
                    FROM inventory_items
                    WHERE COALESCE(quantity,0) < 0
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            applied_negative_stock = 0
            if not dry_run:
                for row in negative_stock_rows:
                    old_qty = float(row.get("quantity") or 0)
                    db.execute("UPDATE inventory_items SET quantity=0 WHERE id=?", (row.get("id"),))
                    applied_negative_stock += 1
                    audit(
                        db,
                        user,
                        "autofix_set_zero",
                        "inventory_items",
                        str(row.get("id")),
                        f"Set negative stock to zero ({old_qty}) for {row.get('sku') or row.get('item_name')}",
                    )
            add_action("inventory_items.set_negative_to_zero", len(negative_stock_rows), applied_negative_stock)

        # 6) Invoices overpaid -> cap to amount, then sync status.
        if enabled("invoices"):
            overpaid_invoices = rows_to_dicts(
                db.execute(
                    """
                    SELECT id, invoice_no, amount, paid_amount, status, is_void
                    FROM invoices
                    WHERE COALESCE(paid_amount,0) > COALESCE(amount,0)
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
            )
            applied_overpaid = 0
            if not dry_run:
                for row in overpaid_invoices:
                    inv_id = str(row.get("id"))
                    affected_invoice_ids.add(inv_id)
                    amount = float(row.get("amount") or 0)
                    paid_old = float(row.get("paid_amount") or 0)
                    if int(row.get("is_void") or 0) == 1:
                        continue
                    new_paid = max(0.0, min(paid_old, amount))
                    new_status = "Paid" if new_paid >= amount - 0.001 else ("Partial" if new_paid > 0.001 else "Pending")
                    db.execute("UPDATE invoices SET paid_amount=?, status=? WHERE id=?", (round(new_paid, 3), new_status, inv_id))
                    applied_overpaid += 1
                    audit(
                        db,
                        user,
                        "autofix_cap_paid",
                        "invoices",
                        inv_id,
                        f"Capped paid_amount {paid_old} -> {new_paid} for {row.get('invoice_no') or inv_id}",
                    )
            add_action("invoices.cap_overpaid", len(overpaid_invoices), applied_overpaid)

        # 7) Re-sync touched invoices with payment totals after payment cleanup.
        invoice_sync_candidates = 0
        invoice_sync_applied = 0
        if enabled("invoices") and affected_invoice_ids:
            invoice_sync_candidates = len(affected_invoice_ids)
            if not dry_run:
                for inv_id in sorted(affected_invoice_ids):
                    inv = db.execute(
                        "SELECT id, invoice_no, amount, paid_amount, status, is_void FROM invoices WHERE id=?",
                        (inv_id,),
                    ).fetchone()
                    if not inv:
                        continue
                    if int(inv["is_void"] or 0) == 1:
                        continue
                    paid_sum = db.execute(
                        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?",
                        (inv_id,),
                    ).fetchone()[0]
                    amount = float(inv["amount"] or 0)
                    old_paid = float(inv["paid_amount"] or 0)
                    old_status = str(inv["status"] or "")
                    new_paid = max(0.0, min(float(paid_sum or 0), amount))
                    new_status = "Paid" if new_paid >= amount - 0.001 else ("Partial" if new_paid > 0.001 else "Pending")
                    if abs(new_paid - old_paid) > 0.001 or new_status != old_status:
                        db.execute("UPDATE invoices SET paid_amount=?, status=? WHERE id=?", (round(new_paid, 3), new_status, inv_id))
                        invoice_sync_applied += 1
                        audit(
                            db,
                            user,
                            "autofix_sync_invoice",
                            "invoices",
                            inv_id,
                            f"Synced paid/status from payments ({old_paid},{old_status}) -> ({new_paid},{new_status})",
                        )
        add_action("invoices.sync_from_payments", invoice_sync_candidates, invoice_sync_applied)

        applied_total = sum(int(a.get("applied") or 0) for a in actions)
        candidate_total = sum(int(a.get("candidates") or 0) for a in actions)

        if not dry_run:
            audit(
                db,
                user,
                "autofix_run",
                "module_integrity",
                None,
                f"Module integrity auto-fix applied={applied_total} candidates={candidate_total}",
            )
            db.commit()
            if require_preview_guard and preview_id:
                MODULE_FIX_PREVIEWS.pop(module_fix_preview_key(username, preview_id), None)

        result = {
            "ok": True,
            "dry_run": dry_run,
            "summary": {
                "candidates": candidate_total,
                "applied": applied_total if not dry_run else 0,
                "mode": "preview" if dry_run else "applied",
            },
            "scope": {
                "modules": sorted(selected_modules),
                "max_rows": max_rows,
            },
            "actions": actions,
            "notes": [
                "Auto-fix applies only deterministic safe operations.",
                "Broken references (e.g. contract points to missing property/client) are reported in integrity scan and require manual business decision.",
            ],
        }
        if dry_run:
            preview_id_new = uid("PRV")
            expires_ts = time.time() + MODULE_FIX_PREVIEW_TTL_SECONDS
            MODULE_FIX_PREVIEWS[module_fix_preview_key(username, preview_id_new)] = {
                "username": username,
                "modules": sorted(selected_modules),
                "max_rows": max_rows,
                "created_at": now_iso(),
                "expires_ts": expires_ts,
                "expires_at": datetime.fromtimestamp(expires_ts).replace(microsecond=0).isoformat(sep=" "),
                "candidate_total": candidate_total,
            }
            result["preview"] = {
                "id": preview_id_new,
                "expires_in_seconds": MODULE_FIX_PREVIEW_TTL_SECONDS,
                "expires_at": MODULE_FIX_PREVIEWS[module_fix_preview_key(username, preview_id_new)]["expires_at"],
            }
            log_module_fix_run(
                db,
                username=username,
                mode="preview",
                status="ok",
                preview_id=preview_id_new,
                modules=sorted(selected_modules),
                max_rows=max_rows,
                candidates=candidate_total,
                applied=0,
                details={
                    "scope": result.get("scope"),
                    "summary": result.get("summary"),
                },
            )
            db.commit()
        elif preview_id:
            result["preview_validated"] = preview_id
            log_module_fix_run(
                db,
                username=username,
                mode="apply",
                status="ok",
                preview_id=preview_id,
                modules=sorted(selected_modules),
                max_rows=max_rows,
                candidates=candidate_total,
                applied=applied_total,
                details={
                    "scope": result.get("scope"),
                    "summary": result.get("summary"),
                },
            )
            db.commit()
        if return_payload_only:
            return result
        self.send_json(result)
        return None

    def api_module_integrity_autorun(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json() if self.command == "POST" else {}
        username = str(user.get("username") or user.get("name") or "").strip().lower()
        confirm_text = str((data or {}).get("confirm_text", "")).strip().upper() if isinstance(data, dict) else ""
        if confirm_text != "APPLY":
            log_module_fix_run(
                db,
                username=username,
                mode="autorun",
                status="rejected_missing_confirm",
                details={"error": "Second approval required"},
            )
            db.commit()
            return self.send_json(
                {
                    "ok": False,
                    "error": "Second approval required",
                    "detail": "Send confirm_text='APPLY' to execute autorun.",
                },
                400,
            )
        modules = [str(x).strip().lower() for x in (data.get("modules") or [])] if isinstance(data, dict) else []
        max_rows_raw = (data.get("max_rows") if isinstance(data, dict) else None)
        try:
            max_rows = int(max_rows_raw) if max_rows_raw is not None else None
        except Exception:
            max_rows = None
        before = self.api_module_integrity(db, return_payload_only=True) or {}
        preview_result = self.api_module_integrity_fix(
            db,
            user,
            return_payload_only=True,
            override_dry_run=True,
            override_modules=modules or None,
            override_max_rows=max_rows,
            require_preview_guard=False,
        ) or {}
        if not bool(preview_result.get("ok", False)):
            return self.send_json(preview_result, 400)
        preview_id = str(((preview_result or {}).get("preview") or {}).get("id") or "").strip()
        if not preview_id:
            return self.send_json({"ok": False, "error": "Preview generation failed"}, 500)
        fix_result = self.api_module_integrity_fix(
            db,
            user,
            return_payload_only=True,
            override_dry_run=False,
            override_modules=modules or None,
            override_max_rows=max_rows,
            require_preview_guard=True,
            override_preview_id=preview_id,
            override_confirm_text="APPLY",
        ) or {}
        if not bool(fix_result.get("ok", False)):
            return self.send_json(fix_result, 400)
        after = self.api_module_integrity(db, return_payload_only=True) or {}
        before_score = float(before.get("score") or 0)
        after_score = float(after.get("score") or 0)
        log_module_fix_run(
            db,
            username=username,
            mode="autorun",
            status="ok",
            preview_id=preview_id,
            modules=list((fix_result.get("scope") or {}).get("modules") or []),
            max_rows=int((fix_result.get("scope") or {}).get("max_rows") or 0),
            candidates=int((fix_result.get("summary") or {}).get("candidates") or 0),
            applied=int((fix_result.get("summary") or {}).get("applied") or 0),
            score_before=before_score,
            score_after=after_score,
            issues_before=int((before.get("summary") or {}).get("total_issues") or 0),
            issues_after=int((after.get("summary") or {}).get("total_issues") or 0),
            details={"delta": {"score_change": round(after_score - before_score, 2)}},
        )
        db.commit()
        self.send_json(
            {
                "ok": True,
                "before": before,
                "preview": preview_result,
                "fix": fix_result,
                "after": after,
                "delta": {
                    "score_change": round(after_score - before_score, 2),
                    "issues_before": int((before.get("summary") or {}).get("total_issues") or 0),
                    "issues_after": int((after.get("summary") or {}).get("total_issues") or 0),
                },
                "scope": (fix_result.get("scope") if isinstance(fix_result, dict) else None) or {},
            }
        )

    def query_module_fix_history_rows(self, db: sqlite3.Connection, query: str, default_limit: int = 50, max_limit: int = 500) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        params = urllib.parse.parse_qs(query or "")
        try:
            limit = int((params.get("limit") or [str(default_limit)])[0] or default_limit)
        except Exception:
            limit = default_limit
        limit = max(1, min(max_limit, limit))

        mode_filter = str((params.get("mode") or [""])[0] or "").strip().lower()
        status_filter = str((params.get("status") or [""])[0] or "").strip().lower()
        username_filter = str((params.get("username") or [""])[0] or "").strip().lower()
        preview_filter = str((params.get("preview_id") or [""])[0] or "").strip()
        from_date = str((params.get("from") or [""])[0] or "").strip()
        to_date = str((params.get("to") or [""])[0] or "").strip()

        sql = "SELECT * FROM module_fix_runs"
        clauses: List[str] = []
        args: List[Any] = []
        if mode_filter:
            clauses.append("lower(mode)=?")
            args.append(mode_filter)
        if status_filter:
            clauses.append("lower(status)=?")
            args.append(status_filter)
        if username_filter:
            clauses.append("lower(username) LIKE ?")
            args.append(f"%{username_filter}%")
        if preview_filter:
            clauses.append("preview_id LIKE ?")
            args.append(f"%{preview_filter}%")
        if from_date:
            clauses.append("datetime(created_at) >= datetime(?)")
            args.append(from_date + " 00:00:00")
        if to_date:
            clauses.append("datetime(created_at) <= datetime(?)")
            args.append(to_date + " 23:59:59")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        rows = rows_to_dicts(db.execute(sql, tuple(args)).fetchall())
        filters = {
            "mode": mode_filter,
            "status": status_filter,
            "username": username_filter,
            "preview_id": preview_filter,
            "from": from_date,
            "to": to_date,
            "limit": limit,
        }
        return rows, filters

    def api_module_integrity_history(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        rows, filters = self.query_module_fix_history_rows(db, query, default_limit=60, max_limit=500)
        out: List[Dict[str, Any]] = []
        for row in rows:
            modules: List[str] = []
            try:
                parsed = json.loads(str(row.get("modules") or "[]"))
                if isinstance(parsed, list):
                    modules = [str(x) for x in parsed]
            except Exception:
                modules = []
            details = {}
            try:
                details = json.loads(str(row.get("details_json") or "{}"))
            except Exception:
                details = {}
            out.append(
                {
                    "id": row.get("id"),
                    "created_at": row.get("created_at"),
                    "username": row.get("username"),
                    "mode": row.get("mode"),
                    "status": row.get("status"),
                    "preview_id": row.get("preview_id"),
                    "modules": modules,
                    "max_rows": row.get("max_rows"),
                    "candidates": row.get("candidates"),
                    "applied": row.get("applied"),
                    "score_before": row.get("score_before"),
                    "score_after": row.get("score_after"),
                    "issues_before": row.get("issues_before"),
                    "issues_after": row.get("issues_after"),
                    "details": details,
                }
            )
        self.send_json({"ok": True, "history": out, "limit": filters.get("limit"), "filters": filters})

    def api_module_integrity_history_kpi(self, db: sqlite3.Connection, user: Dict[str, Any], query: str) -> None:
        params = urllib.parse.parse_qs(query or "")
        try:
            days = int((params.get("days") or ["1"])[0] or 1)
        except Exception:
            days = 1
        days = max(1, min(365, days))
        since_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        total = int(
            db.execute(
                "SELECT COUNT(*) FROM module_fix_runs WHERE datetime(created_at) >= datetime(?)",
                (since_dt,),
            ).fetchone()[0]
            or 0
        )
        ok_total = int(
            db.execute(
                "SELECT COUNT(*) FROM module_fix_runs WHERE datetime(created_at) >= datetime(?) AND lower(status)='ok'",
                (since_dt,),
            ).fetchone()[0]
            or 0
        )
        rejected_total = int(
            db.execute(
                "SELECT COUNT(*) FROM module_fix_runs WHERE datetime(created_at) >= datetime(?) AND lower(status) LIKE 'rejected%'",
                (since_dt,),
            ).fetchone()[0]
            or 0
        )
        apply_ok = int(
            db.execute(
                """
                SELECT COUNT(*) FROM module_fix_runs
                WHERE datetime(created_at) >= datetime(?)
                  AND lower(status)='ok'
                  AND lower(mode) IN ('apply','autorun')
                """,
                (since_dt,),
            ).fetchone()[0]
            or 0
        )
        applied_sum = int(
            db.execute(
                """
                SELECT COALESCE(SUM(applied),0) FROM module_fix_runs
                WHERE datetime(created_at) >= datetime(?) AND lower(status)='ok'
                """,
                (since_dt,),
            ).fetchone()[0]
            or 0
        )
        candidates_sum = int(
            db.execute(
                """
                SELECT COALESCE(SUM(candidates),0) FROM module_fix_runs
                WHERE datetime(created_at) >= datetime(?) AND lower(status)='ok'
                """,
                (since_dt,),
            ).fetchone()[0]
            or 0
        )
        success_rate = round((ok_total / total) * 100, 1) if total > 0 else 0.0
        apply_effectiveness = round((applied_sum / candidates_sum) * 100, 1) if candidates_sum > 0 else 0.0
        alerts: List[Dict[str, Any]] = []
        if total >= MODULE_FIX_MIN_ATTEMPTS_FOR_ALERT and success_rate < MODULE_FIX_MIN_SUCCESS_RATE:
            alerts.append(
                {
                    "code": "success_rate_low",
                    "severity": "high",
                    "message": f"نسبة نجاح الإصلاح منخفضة ({success_rate}%) أقل من الحد {MODULE_FIX_MIN_SUCCESS_RATE}%",
                    "value": success_rate,
                    "threshold": MODULE_FIX_MIN_SUCCESS_RATE,
                }
            )
        if rejected_total > MODULE_FIX_MAX_REJECTED:
            alerts.append(
                {
                    "code": "rejected_too_many",
                    "severity": "high",
                    "message": f"عدد عمليات الرفض مرتفع ({rejected_total}) أعلى من الحد {MODULE_FIX_MAX_REJECTED}",
                    "value": rejected_total,
                    "threshold": MODULE_FIX_MAX_REJECTED,
                }
            )
        if candidates_sum >= 10 and apply_effectiveness < MODULE_FIX_MIN_APPLY_EFFECTIVENESS:
            alerts.append(
                {
                    "code": "effectiveness_low",
                    "severity": "medium",
                    "message": f"فعالية تطبيق الإصلاح منخفضة ({apply_effectiveness}%) أقل من الحد {MODULE_FIX_MIN_APPLY_EFFECTIVENESS}%",
                    "value": apply_effectiveness,
                    "threshold": MODULE_FIX_MIN_APPLY_EFFECTIVENESS,
                }
            )
        health_status = "alert" if any(a.get("severity") == "high" for a in alerts) else ("warning" if alerts else "ok")

        top_users = rows_to_dicts(
            db.execute(
                """
                SELECT username, COUNT(*) as runs, COALESCE(SUM(applied),0) as applied_total
                FROM module_fix_runs
                WHERE datetime(created_at) >= datetime(?)
                GROUP BY username
                ORDER BY runs DESC, applied_total DESC
                LIMIT 5
                """,
                (since_dt,),
            ).fetchall()
        )

        self.send_json(
            {
                "ok": True,
                "window_days": days,
                "since": since_dt,
                "kpi": {
                    "attempts": total,
                    "success": ok_total,
                    "rejected": rejected_total,
                    "apply_success": apply_ok,
                    "applied_total": applied_sum,
                    "candidates_total": candidates_sum,
                    "success_rate": success_rate,
                    "apply_effectiveness": apply_effectiveness,
                },
                "thresholds": {
                    "min_attempts_for_alert": MODULE_FIX_MIN_ATTEMPTS_FOR_ALERT,
                    "min_success_rate": MODULE_FIX_MIN_SUCCESS_RATE,
                    "max_rejected": MODULE_FIX_MAX_REJECTED,
                    "min_apply_effectiveness": MODULE_FIX_MIN_APPLY_EFFECTIVENESS,
                },
                "alerts": alerts,
                "health_status": health_status,
                "top_users": top_users,
            }
        )

    def api_operational_intel(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        dash = build_dashboard(db)
        intel = build_operational_intel(db, dash)
        usage = ai_usage_stats(db, user["id"])
        self.send_json({
            "ok": True,
            "assistant": AI_ASSISTANT_NAME,
            "intel": intel,
            "usage": usage,
            "llm_enabled": bool(OPENAI_API_KEY),
        })

    def api_ai_usage(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        self.send_json({"ok": True, "usage": ai_usage_stats(db, user["id"]), "llm_enabled": bool(OPENAI_API_KEY)})

    def api_ai_brief(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        dash = build_dashboard(db)
        intel = build_operational_intel(db, dash)
        self.send_json({
            "ok": True,
            "assistant": AI_ASSISTANT_NAME,
            "brief": intel.get("brief"),
            "recommendations": intel.get("recommendations", [])[:8],
            "generated_at": now_iso(),
        })

    def api_ai_ask(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        data = self.read_json()
        question = str(data.get("question", "")).strip()
        if not question:
            return self.send_json({"ok": False, "error": "Missing question"}, 400)
        usage = ai_usage_stats(db, user["id"])
        if usage["count"] >= AI_DAILY_LIMIT:
            return self.send_json({
                "ok": False,
                "error": f"تم بلوغ حد Walid اليوم ({AI_DAILY_LIMIT} سؤال) — جرّب غداً أو استخدم التوصيات التلقائية",
                "usage": usage,
            }, 429)
        dash = build_dashboard(db)
        intel = build_operational_intel(db, dash)
        result = compose_walid_reply(question, dash, intel, allow_llm=True)
        log_ai_usage(db, user, question, result.get("mode", "rules"), int(result.get("tokens_est") or 0))
        audit(db, user, "ai_ask", "walid", None, question[:120])
        db.commit()
        usage = ai_usage_stats(db, user["id"])
        self.send_json({
            "ok": True,
            "assistant": AI_ASSISTANT_NAME,
            "usage": usage,
            "llm_enabled": bool(OPENAI_API_KEY),
            **result,
        })

    def api_ai_ask_preview(self, db: sqlite3.Connection) -> None:
        data = self.read_json()
        question = str(data.get("question", "")).strip() or "overview"
        dash = build_dashboard(db)
        k = dash.get("kpis") or {}
        preview = {
            "revenue": k.get("income", 0),
            "profit": k.get("net", 0),
            "occupancy": k.get("occupancy", 0),
            "assets": k.get("properties", 0),
            "health": k.get("health", 0),
            "overdue": k.get("overdue", 0),
            "expiring": k.get("expiring", 0),
        }
        intel = build_operational_intel(db, dash)
        result = compose_walid_reply(question, dash, intel, allow_llm=False, limited=True)
        self.send_json({
            "ok": True,
            "assistant": AI_ASSISTANT_NAME,
            "reply": result["reply"],
            "actions": result.get("actions", [])[:2],
            "preview": preview,
        })

    def api_otp_send(self, db: sqlite3.Connection) -> None:
        if not otp_login_enabled():
            return self.send_json(
                {
                    "ok": False,
                    "error": "دخول OTP بدون كلمة مرور معطّل — MFA يعمل تلقائياً بعد كلمة المرور للأدوار المحمية",
                    "otp_login_enabled": False,
                },
                403,
            )
        data = self.read_json()
        username = str(data.get("username", "")).strip()
        if not username:
            return self.send_json({"ok": False, "error": "Missing username"}, 400)
        row = db.execute(
            "SELECT id, username, email FROM users WHERE username=? AND active=1",
            (username,),
        ).fetchone()
        if not row:
            row = db.execute(
                "SELECT id, username, email FROM users WHERE lower(username)=? AND active=1",
                (username.lower(),),
            ).fetchone()
        if not row:
            return self.send_json({"ok": False, "error": "User not found"}, 404)
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        store_otp_code(db, str(row["username"]), code, purpose="login")
        db.commit()
        to_addr = resolve_user_email(str(row["username"]), str(row["email"] or "").strip())
        if not to_addr:
            return self.send_json(
                {
                    "ok": False,
                    "error": "لا يوجد بريد للمستخدم — عيّن email أو LQ_EMAIL_<USER>",
                },
                400,
            )
        subject = f"{COMPANY_NAME} — رمز الدخول OTP"
        body = (
            f"رمز الدخول لحساب {username}: {code}\n"
            f"صالح لمدة {OTP_TTL_SECONDS // 60} دقائق.\n"
            "إذا لم تطلب هذا الرمز تجاهل الرسالة."
        )
        sent, detail = send_alert_email(to_addr, subject, body)
        if not sent and os.environ.get("LQ_OTP_DEBUG") == "1":
            sys.stderr.write(f"[LQ OTP debug] {username}: {code} ({detail})\n")
            sent = True
            detail = "OTP logged (debug mode)"
        if not sent:
            return self.send_json(
                {
                    "ok": False,
                    "error": "تعذر إرسال OTP — فعّل LQ_SMTP_HOST على السيرفر",
                    "detail": detail,
                },
                503,
            )
        masked = to_addr.split("@")[0][:2] + "***@" + to_addr.split("@")[-1] if "@" in to_addr else to_addr[-4:]
        self.send_json(
            {
                "ok": True,
                "message": f"تم إرسال رمز التحقق إلى {masked}",
                "expires_in": OTP_TTL_SECONDS,
                "channel": "email",
            }
        )

    def api_otp_verify(self) -> None:
        data = self.read_json()
        username = str(data.get("username", "")).strip()
        code = str(data.get("code", "")).strip()
        if not otp_login_enabled():
            return self.send_json({"ok": False, "error": "OTP login disabled", "otp_login_enabled": False}, 403)
        with connect() as db:
            stored = load_otp_code(db, username)
            if stored and time.time() <= stored[1] and stored[0] == code:
                return self.send_json({"ok": True, "verified": True, "message": "OTP verified"})
        return self.send_json({"ok": False, "error": "Invalid or expired OTP code"}, 401)

    def api_permissions_ui(self, user: Dict[str, Any]) -> None:
        self.send_json({"ok": True, **ui_permissions_for_user(user)})

    def api_permissions_audit(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        role_rows = db.execute("SELECT role, COUNT(*) as c FROM users WHERE active=1 GROUP BY role").fetchall()
        role_counts = {str(r["role"]): int(r["c"] or 0) for r in role_rows}
        matrix = {}
        for role, perms in ROLE_PERMISSIONS.items():
            ui = ui_permissions_for_role(role)
            matrix[role] = {
                "active_users": role_counts.get(role, 0),
                "permission_count": len(perms),
                "sensitive": {
                    "approve_contract": has_permission({"role": role}, "approvals"),
                    "backup_write": has_permission({"role": role}, "backup"),
                    "users_write": has_permission({"role": role}, "admin"),
                    "delete_invoices": has_permission({"role": role}, "invoices:delete"),
                },
                "ui_sections": ui.get("sections", []),
                "ui_write_sections": ui.get("write_sections", []),
            }
        self.send_json({"ok": True, "version": APP_VERSION, "roles": matrix})

    def api_report_executive(self, db: sqlite3.Connection, user: Dict[str, Any]) -> None:
        dash = build_dashboard(db)
        owner = user.get("name") or COMPANY_NAME
        html = build_executive_report_html(owner, dash)
        self.send_html(html)

    def api_events_stream(self, db: sqlite3.Connection, query: str) -> None:
        user = self.current_user(db, query)
        token = self.token_from_request(query)
        public_only = not user and not token
        if token and not user:
            return self.send_json({"ok": False, "error": "Invalid or expired token"}, 401)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_cors_headers()
        self.end_headers()
        prev: Optional[Dict[str, float]] = None
        try:
            for _ in range(120):
                audit_total = int(db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] or 0)
                latest_row = db.execute(
                    """
                    SELECT created_at, username, action, entity, entity_id, details
                    FROM audit_log
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                latest_audit = None
                if latest_row:
                    latest_audit = {
                        "created_at": latest_row["created_at"],
                        "username": latest_row["username"],
                        "action": latest_row["action"],
                        "entity": latest_row["entity"],
                        "entity_id": latest_row["entity_id"],
                        "details": latest_row["details"],
                    }
                if public_only:
                    payload = {
                        "type": "health",
                        "health": 100,
                        "audit_total": audit_total,
                        "latest_audit": latest_audit,
                        "last_backup": LAST_AUTO_BACKUP_AT or (list_automatic_backups()[0]["created_at"] if list_automatic_backups() else None),
                        "ts": now_iso(),
                    }
                else:
                    dash = build_dashboard(db)
                    k = dash.get("kpis") or {}
                    cur = {
                        "overdue": float(k.get("overdue") or 0),
                        "expiring": float(k.get("expiring") or 0),
                        "health": float(k.get("health") or 0),
                        "alert_center_total": float(k.get("alert_center_total") or 0),
                        "alert_center_high": float(k.get("alert_center_high") or 0),
                        "pending_approvals": float(k.get("pending_approvals") or 0),
                    }
                    deltas = {}
                    if prev:
                        for key in cur:
                            deltas[key] = round(cur[key] - prev.get(key, 0), 2)
                    prev = cur
                    payload = {
                        "type": "kpis",
                        "kpis": cur,
                        "deltas": deltas,
                        "audit_total": audit_total,
                        "latest_audit": latest_audit,
                        "last_backup": LAST_AUTO_BACKUP_AT or (list_automatic_backups()[0]["created_at"] if list_automatic_backups() else None),
                        "ts": now_iso(),
                    }
                line = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
                time.sleep(LIVE_STREAM_INTERVAL_SEC)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


UI_SECTIONS_ALL = [
    "dashboard", "estate-platform", "accounting-platform", "hospitality-platform", "owner-staff", "owner-live", "daily-ops", "hospitality", "properties", "tasks", "clients", "contracts", "revenues", "invoices",
    "receivables",
    "admin-expenses", "maintenance", "reports", "messages", "walid", "enterprise", "business-catalog",
    "production", "timeline", "backup", "settings", "accounts", "purchases", "payroll",
    "inventory", "bank", "chart-accounts", "statements", "bank-reconciliation",
    "financial-periods", "approvals", "users", "qa",
]
UI_WRITE_SECTIONS_ALL = [
    "estate-platform", "accounting-platform", "hospitality-platform", "properties", "clients", "contracts", "invoices", "hospitality", "maintenance", "inventory",
    "accounts", "purchases", "payroll", "revenues", "admin-expenses", "bank",
    "chart-accounts", "statements", "bank-reconciliation", "financial-periods",
    "users", "approvals", "backup",
]
UI_KPIS_ALL = [
    "properties", "rented", "vacant", "income", "expense", "net", "health", "occupancy",
    "overdue", "maintenance", "expiring", "expired", "paid", "billed", "bank_balance",
    "payroll", "inventory_value", "purchases_due",
]
UI_PERMISSIONS_BY_ROLE: Dict[str, Dict[str, List[str]]] = {
    "owner": {"sections": UI_SECTIONS_ALL, "kpis": UI_KPIS_ALL},
    "admin": {
        "sections": [
            "dashboard", "estate-platform", "accounting-platform", "hospitality-platform",
            "daily-ops", "hospitality", "properties", "tasks", "clients", "contracts",
            "invoices", "receivables", "maintenance", "inventory", "accounts",
            "purchases", "payroll", "revenues", "admin-expenses", "bank",
            "chart-accounts", "statements", "bank-reconciliation", "financial-periods",
            "approvals", "reports", "messages", "timeline", "backup",
        ],
        "kpis": [
            "properties", "rented", "vacant", "income", "expense", "net", "health",
            "occupancy", "overdue", "maintenance", "expiring", "expired", "paid",
            "billed", "bank_balance", "payroll", "inventory_value", "purchases_due",
        ],
    },
    "accountant": {
        "sections": [
            "dashboard", "estate-platform", "accounting-platform", "hospitality-platform",
            "daily-ops", "hospitality", "properties", "clients", "contracts", "invoices",
            "receivables", "revenues",
            "admin-expenses", "accounts", "purchases", "payroll", "inventory", "bank",
            "chart-accounts", "statements", "bank-reconciliation", "financial-periods",
            "reports", "backup", "messages", "timeline", "approvals",
        ],
        "kpis": [
            "income", "expense", "net", "overdue", "paid", "billed", "bank_balance", "payroll",
            "inventory_value", "purchases_due", "health", "occupancy",
        ],
    },
    "operations": {
        "sections": [
            "dashboard", "estate-platform", "hospitality-platform", "daily-ops",
            "hospitality", "properties", "tasks", "clients", "contracts", "invoices",
            "receivables", "maintenance", "inventory", "reports", "messages", "timeline",
            "backup", "approvals",
        ],
        "kpis": ["properties", "rented", "vacant", "occupancy", "maintenance", "expiring", "health"],
    },
    "maintenance": {
        "sections": [
            "dashboard", "estate-platform", "hospitality-platform", "daily-ops",
            "hospitality", "properties", "maintenance", "inventory", "reports",
            "messages", "backup",
        ],
        "kpis": ["maintenance", "properties", "vacant", "inventory_value", "health"],
    },
    "reception": {
        "sections": [
            "dashboard", "estate-platform", "hospitality-platform", "daily-ops",
            "hospitality", "properties", "tasks", "clients", "contracts", "invoices",
            "messages", "timeline", "reports",
        ],
        "kpis": ["properties", "occupancy", "overdue", "health"],
    },
    "viewer": {
        "sections": [
            "dashboard", "estate-platform", "hospitality-platform", "daily-ops",
            "hospitality", "properties", "clients", "contracts", "invoices", "reports",
            "maintenance", "messages", "timeline", "backup",
        ],
        "kpis": ["properties", "occupancy", "health", "overdue", "net"],
    },
}
UI_WRITE_BY_ROLE: Dict[str, List[str]] = {
    "owner": list(UI_WRITE_SECTIONS_ALL),
    "admin": [
        "estate-platform", "accounting-platform", "hospitality-platform", "properties",
        "hospitality", "clients", "contracts", "invoices", "maintenance", "inventory",
        "accounts", "purchases", "payroll", "revenues", "admin-expenses", "bank",
        "chart-accounts", "statements", "bank-reconciliation", "financial-periods",
        "approvals", "backup",
    ],
    "accountant": [
        "accounting-platform", "hospitality-platform", "invoices", "hospitality", "accounts", "purchases", "payroll", "revenues", "admin-expenses",
        "bank", "chart-accounts", "statements", "bank-reconciliation", "financial-periods",
        "approvals", "backup",
    ],
    "operations": [
        "estate-platform", "accounting-platform", "hospitality-platform", "properties", "hospitality", "clients", "contracts", "invoices", "maintenance", "inventory", "approvals",
    ],
    "maintenance": ["estate-platform", "accounting-platform", "maintenance", "inventory"],
    "viewer": [],
}


def ui_permissions_for_role(role: str) -> Dict[str, Any]:
    base = dict(UI_PERMISSIONS_BY_ROLE.get(role, UI_PERMISSIONS_BY_ROLE["viewer"]))
    base["role"] = role
    base["write_sections"] = list(UI_WRITE_BY_ROLE.get(role, []))
    base["read_only"] = role == "viewer"
    return base


def ui_permissions_for_user(user: Dict[str, Any]) -> Dict[str, Any]:
    role = str((user or {}).get("role") or "viewer").lower()
    uname = str((user or {}).get("username") or "").strip().lower()
    base = ui_permissions_for_role(role)
    if uname in RESTRICTED_ADMIN_USERNAMES:
        base = ui_permissions_for_role("operations")
        # Keep account label as admin while enforcing strict operational scope.
        base["role"] = "admin"
        forbidden = {
            "owner-staff",
            "owner-live",
            "users",
            "walid",
            "enterprise",
            "production",
            "qa",
            "settings",
            "business-catalog",
        }
        base["sections"] = [s for s in base.get("sections", []) if s not in forbidden]
        base["write_sections"] = [s for s in base.get("write_sections", []) if s not in forbidden]
    return base


def fmt_omr(n: float) -> str:
    return f"{float(n or 0):,.2f} OMR"


def ai_usage_today(db: sqlite3.Connection, user_id: str) -> int:
    start = today() + " 00:00:00"
    row = db.execute(
        "SELECT COUNT(*) FROM ai_usage_log WHERE user_id=? AND created_at>=?",
        (user_id, start),
    ).fetchone()
    return int(row[0] or 0)


def ai_usage_stats(db: sqlite3.Connection, user_id: str) -> Dict[str, Any]:
    count = ai_usage_today(db, user_id)
    return {
        "count": count,
        "limit": AI_DAILY_LIMIT,
        "remaining": max(0, AI_DAILY_LIMIT - count),
        "llm_enabled": bool(OPENAI_API_KEY),
        "model": AI_MODEL if OPENAI_API_KEY else None,
    }


def log_ai_usage(
    db: sqlite3.Connection,
    user: Dict[str, Any],
    question: str,
    mode: str,
    tokens_est: int = 0,
) -> None:
    db.execute(
        "INSERT INTO ai_usage_log(id,user_id,username,question,mode,tokens_est,created_at) VALUES(?,?,?,?,?,?,?)",
        (
            uid("ai"),
            user["id"],
            user.get("username") or "",
            question[:500],
            mode,
            tokens_est,
            now_iso(),
        ),
    )


def property_label_row(prop_row: Optional[Dict[str, Any]], properties_map: Dict[str, str]) -> str:
    if not prop_row:
        return "—"
    pid = prop_row.get("id") if isinstance(prop_row, dict) else None
    if pid and properties_map.get(pid):
        return str(properties_map[pid])
    if isinstance(prop_row, dict):
        b = prop_row.get("building_no") or ""
        n = prop_row.get("name") or ""
        return f"{b} {n}".strip() or str(pid or "—")
    return str(prop_row)


def build_operational_intel(db: sqlite3.Connection, dash: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    dash = dash or build_dashboard(db)
    k = dash.get("kpis") or {}
    today_s = today()
    today_d = date.today()
    clients = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM clients").fetchall()}
    properties = {r["id"]: r["name"] for r in db.execute("SELECT id, name, building_no FROM properties").fetchall()}
    props_full = {r["id"]: dict(r) for r in db.execute("SELECT * FROM properties").fetchall()}

    overdue_rows = rows_to_dicts(
        db.execute(
            """
            SELECT * FROM invoices
            WHERE COALESCE(is_void,0)=0 AND lower(status)!='paid'
            AND (amount - paid_amount) > 0.001 AND due_date < ?
            ORDER BY due_date
            """,
            (today_s,),
        ).fetchall()
    )
    debtor_map: Dict[str, Dict[str, Any]] = {}
    for inv in overdue_rows:
        cid = str(inv.get("client_id") or "")
        rem = max(0.0, float(inv.get("amount") or 0) - float(inv.get("paid_amount") or 0))
        if not debtor_map.get(cid):
            debtor_map[cid] = {
                "client_id": cid,
                "name": clients.get(cid, "—"),
                "total": 0.0,
                "invoice_count": 0,
                "oldest_due": inv.get("due_date"),
            }
        debtor_map[cid]["total"] += rem
        debtor_map[cid]["invoice_count"] += 1
        if str(inv.get("due_date") or "") < str(debtor_map[cid]["oldest_due"] or "9999"):
            debtor_map[cid]["oldest_due"] = inv.get("due_date")
    overdue_debtors = sorted(debtor_map.values(), key=lambda x: -float(x["total"]))[:15]

    expiring_contracts: List[Dict[str, Any]] = []
    contracts = rows_to_dicts(
        db.execute(
            "SELECT * FROM contracts WHERE lower(status) IN ('active','renewed') OR lower(status) LIKE '%active%'"
        ).fetchall()
    )
    for c in contracts:
        try:
            end = datetime.fromisoformat(str(c["end_date"])).date()
        except ValueError:
            continue
        days_left = (end - today_d).days
        if days_left <= 90:
            expiring_contracts.append({
                "contract_id": c["id"],
                "contract_no": c.get("contract_no") or c["id"],
                "client_name": clients.get(c.get("client_id"), "—"),
                "property_name": property_label_row(props_full.get(c.get("property_id")), properties),
                "end_date": c.get("end_date"),
                "days_left": days_left,
                "rent_amount": float(c.get("rent_amount") or 0),
                "status": "expired" if days_left < 0 else "expiring",
            })
    expiring_contracts.sort(key=lambda x: x["days_left"])

    pending_deposits: List[Dict[str, Any]] = []
    for c in contracts:
        required = float(c.get("deposit_amount") or 0)
        if required <= 0:
            continue
        received = float(c.get("deposit_received_amount") or 0)
        if received >= required - 0.001:
            continue
        pending_deposits.append({
            "contract_id": c["id"],
            "contract_no": c.get("contract_no") or c["id"],
            "client_name": clients.get(c.get("client_id"), "—"),
            "required": required,
            "received": received,
            "outstanding": round(required - received, 3),
        })

    urgent_maintenance = rows_to_dicts(
        db.execute(
            """
            SELECT * FROM maintenance
            WHERE lower(status) NOT IN ('closed','done','completed')
            ORDER BY CASE lower(priority) WHEN 'high' THEN 0 WHEN 'urgent' THEN 0 ELSE 1 END, request_date
            LIMIT 12
            """
        ).fetchall()
    )
    maint_out: List[Dict[str, Any]] = []
    for m in urgent_maintenance:
        maint_out.append({
            "id": m["id"],
            "title": m.get("title") or "طلب صيانة",
            "priority": m.get("priority") or "Medium",
            "property_name": property_label_row(props_full.get(m.get("property_id")), properties),
            "status": m.get("status"),
            "request_date": m.get("request_date"),
        })

    recommendations: List[Dict[str, Any]] = []
    overdue_total = sum(float(d["total"]) for d in overdue_debtors)
    if overdue_debtors:
        recommendations.append({
            "priority": "high",
            "category": "collection",
            "title": "تحصيل المتأخرات",
            "text": f"{len(overdue_debtors)} عميل لم يدفع — إجمالي {fmt_omr(overdue_total)}",
            "section": "invoices",
            "action_label": "فتح الفواتير",
        })
    expired_ct = [c for c in expiring_contracts if c["days_left"] < 0]
    soon_ct = [c for c in expiring_contracts if 0 <= c["days_left"] <= 60]
    if expired_ct:
        recommendations.append({
            "priority": "high",
            "category": "renewal",
            "title": "عقود منتهية",
            "text": f"{len(expired_ct)} عقد منتهٍ يحتاج تجديد أو إغلاق فوري",
            "section": "contracts",
            "action_label": "العقود",
        })
    if soon_ct:
        recommendations.append({
            "priority": "medium",
            "category": "renewal",
            "title": "تجديد قريب",
            "text": f"{len(soon_ct)} عقد ينتهي خلال 60 يوم — ابدأ التجديد",
            "section": "contracts",
            "action_label": "متابعة التجديد",
        })
    if pending_deposits:
        recommendations.append({
            "priority": "medium",
            "category": "deposit",
            "title": "تأمينات معلقة",
            "text": f"{len(pending_deposits)} عقد بدون تأمين كامل",
            "section": "contracts",
            "action_label": "مراجعة التأمين",
        })
    high_maint = [m for m in maint_out if str(m.get("priority") or "").lower() in ("high", "urgent")]
    if high_maint:
        recommendations.append({
            "priority": "high",
            "category": "maintenance",
            "title": "صيانة عاجلة",
            "text": f"{len(high_maint)} طلب صيانة عالي الأهمية",
            "section": "maintenance",
            "action_label": "الصيانة",
        })
    if int(k.get("vacant") or 0) > 0:
        recommendations.append({
            "priority": "low",
            "category": "occupancy",
            "title": "رفع الإشغال",
            "text": f"{k.get('vacant')} وحدة شاغرة — فعّل التسويق",
            "section": "properties",
            "action_label": "المحفظة",
        })
    if int(k.get("pending_approvals") or 0) > 0:
        recommendations.append({
            "priority": "high",
            "category": "approvals",
            "title": "اعتمادات معلقة",
            "text": f"{k.get('pending_approvals')} طلب بانتظار الاعتماد",
            "section": "approvals",
            "action_label": "مركز الاعتمادات",
        })

    coll = round((float(k.get("paid") or 0) / float(k.get("billed") or 1)) * 100) if k.get("billed") else 0
    brief_parts = [
        f"جاهزية التشغيل {k.get('health', 0)}% · إشغال {k.get('occupancy', 0)}%.",
        f"الإيرادات {fmt_omr(k.get('income', 0))} وصافي {fmt_omr(k.get('net', 0))}.",
        f"تحصيل {coll}% · متأخرات {fmt_omr(k.get('overdue', 0))}.",
    ]
    if overdue_debtors:
        top = overdue_debtors[0]
        brief_parts.append(f"أعلى متأخر: {top['name']} ({fmt_omr(top['total'])}).")
    if expiring_contracts:
        n_soon = len([c for c in expiring_contracts if c["days_left"] <= 30])
        if n_soon:
            brief_parts.append(f"{n_soon} عقد خلال 30 يوم.")
    if recommendations:
        brief_parts.append(f"أولوية اليوم: {recommendations[0]['title']}.")

    suggested_questions = [
        "من لم يدفع؟",
        "ما العقود التي تنتهي قريباً؟",
        "ملخص تنفيذي اليوم",
        "أولويات التحصيل",
        "طلبات الصيانة العاجلة",
        "من لم يستلم التأمين؟",
    ]

    return {
        "brief": " ".join(brief_parts),
        "recommendations": recommendations[:10],
        "overdue_debtors": overdue_debtors,
        "expiring_contracts": expiring_contracts[:20],
        "pending_deposits": pending_deposits[:15],
        "urgent_maintenance": maint_out,
        "suggested_questions": suggested_questions,
        "kpis": k,
        "decisions": (dash.get("decisions") or [])[:6],
    }


def walid_rules_reply(
    question: str,
    dash: Dict[str, Any],
    intel: Dict[str, Any],
    limited: bool = False,
) -> Dict[str, Any]:
    q = question.lower()
    k = dash.get("kpis") or intel.get("kpis") or {}
    actions: List[Dict[str, str]] = []
    parts: List[str] = []
    sufficient = False

    def act(label: str, section: str, action: str = "navigate") -> None:
        actions.append({"label": label, "section": section, "action": action})

    if any(w in q for w in ["لم يدفع", "من لم", "debtor", "didn't pay", "who pay", "متأخرين", "لم يدفعوا"]):
        debtors = intel.get("overdue_debtors") or []
        if debtors:
            lines = [
                f"• {d['name']}: {fmt_omr(d['total'])} ({d['invoice_count']} فاتورة · أقدم {d.get('oldest_due') or '—'})"
                for d in debtors[:8 if limited else 12]
            ]
            parts.append("العملاء الذين لم يدفعوا / Overdue clients:\n" + "\n".join(lines))
            total = sum(float(d["total"]) for d in debtors)
            parts.append(f"الإجمالي: {fmt_omr(total)} من {len(debtors)} عميل.")
        else:
            parts.append("لا متأخرات حالياً — التحصيل سليم ✅")
        act("الفواتير والتحصيل", "invoices")
        sufficient = True

    if any(w in q for w in ["تنتهي", "expir", "تجديد", "renew", "انتهاء", "ينتهي"]):
        rows = intel.get("expiring_contracts") or []
        if rows:
            lines = [
                f"• {c['contract_no']} · {c['client_name']} · {c['property_name']} · "
                f"{'منتهي' if c['days_left'] < 0 else f'{c['days_left']} يوم'} ({c.get('end_date')})"
                for c in rows[:8 if limited else 15]
            ]
            parts.append("العقود القريبة من الانتهاء / Expiring contracts:\n" + "\n".join(lines))
        else:
            parts.append("لا عقود نشطة قريبة من الانتهاء خلال 90 يوم.")
        act("إدارة العقود", "contracts")
        sufficient = True

    if any(w in q for w in ["تأمين", "deposit", "security"]):
        deps = intel.get("pending_deposits") or []
        if deps:
            lines = [
                f"• {d['contract_no']} · {d['client_name']} · متبقي {fmt_omr(d['outstanding'])}"
                for d in deps[:8 if limited else 12]
            ]
            parts.append("عقود بتأمين غير مكتمل / Pending deposits:\n" + "\n".join(lines))
        else:
            parts.append("كل التأمينات المطلوبة مستلمة ✅")
        act("العقود", "contracts")
        sufficient = True

    if any(w in q for w in ["صيان", "maint", "repair", "عاجل"]):
        maint = intel.get("urgent_maintenance") or []
        if maint:
            lines = [
                f"• [{m.get('priority')}] {m.get('title')} · {m.get('property_name')} · {m.get('status')}"
                for m in maint[:8 if limited else 12]
            ]
            parts.append("طلبات الصيانة المفتوحة / Open maintenance:\n" + "\n".join(lines))
        else:
            parts.append("لا طلبات صيانة مفتوحة — التشغيل مستقر.")
        act("الصيانة", "maintenance")
        sufficient = True

    if any(w in q for w in ["توص", "recommend", "اقتراح", "priority", "أولوية", "priorities"]):
        recs = intel.get("recommendations") or []
        if recs:
            lines = [f"• [{r['priority']}] {r['title']}: {r['text']}" for r in recs[:6 if limited else 10]]
            parts.append("توصيات Walid / Recommendations:\n" + "\n".join(lines))
            for r in recs[:3]:
                act(r.get("action_label") or r["title"], r.get("section") or "dashboard")
        else:
            parts.append("لا توصيات حرجة — استمر في المراقبة الروتينية.")
        sufficient = True

    if any(w in q for w in ["profit", "ربح", "صافي", "net", "margin"]):
        net = float(k.get("net") or 0)
        parts.append(
            f"صافي الربح / Net: {fmt_omr(net)} — إيراد {fmt_omr(k.get('income', 0))} · مصروف {fmt_omr(k.get('expense', 0))}."
        )
        act("التقارير المالية", "reports")
        sufficient = True

    if any(w in q for w in ["overdue", "متأخر", "late", "collection", "تحصيل"]):
        overdue = float(k.get("overdue") or 0)
        coll = round((float(k.get("paid") or 0) / float(k.get("billed") or 1)) * 100) if k.get("billed") else 0
        parts.append(f"المتأخرات: {fmt_omr(overdue)} · نسبة التحصيل: {coll}%.")
        act("الفواتير", "invoices")
        sufficient = True

    if any(w in q for w in ["occup", "إشغال", "vacant", "شاغ"]):
        parts.append(f"الإشغال {k.get('occupancy', 0)}% · شاغر {k.get('vacant', 0)} وحدة.")
        act("المشاريع", "properties")
        sufficient = True

    if any(w in q for w in ["health", "جاهز", "status", "overview", "summary", "ملخص", "تنفيذي"]):
        parts.append(intel.get("brief") or f"جاهزية {k.get('health', 0)}%.")
        for d in (intel.get("decisions") or dash.get("decisions") or [])[:3]:
            parts.append(f"• {d.get('level')}: {d.get('text')}")
        act("لوحة التحكم", "dashboard")
        act("التقرير التنفيذي", "reports")
        sufficient = True

    if not parts:
        parts.append(intel.get("brief") or "التشغيل مستقر — اسأل عن المتأخرات، العقود، أو الصيانة.")
        act("وليد · الذكاء", "walid")
        act("لوحة التحكم", "dashboard")

    reply = "\n\n".join(parts[:2 if limited else 4])
    return {
        "reply": reply,
        "actions": actions[:2 if limited else 6],
        "recommendations": (intel.get("recommendations") or [])[:3],
        "mode": "rules",
        "sufficient": sufficient,
        "tokens_est": 0,
    }


def walid_llm_reply(question: str, intel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not OPENAI_API_KEY:
        return None
    compact = {
        "brief": intel.get("brief"),
        "kpis": intel.get("kpis"),
        "overdue_debtors": [
            {"name": d["name"], "total": d["total"], "invoices": d["invoice_count"]}
            for d in (intel.get("overdue_debtors") or [])[:8]
        ],
        "expiring_contracts": [
            {
                "no": c["contract_no"],
                "client": c["client_name"],
                "days_left": c["days_left"],
                "end": c.get("end_date"),
            }
            for c in (intel.get("expiring_contracts") or [])[:8]
        ],
        "pending_deposits": len(intel.get("pending_deposits") or []),
        "urgent_maintenance": len(
            [m for m in (intel.get("urgent_maintenance") or [])
             if str(m.get("priority") or "").lower() in ("high", "urgent")]
        ),
        "recommendations": intel.get("recommendations") or [],
    }
    system = (
        f"You are {AI_ASSISTANT_NAME}, the operational AI for {COMPANY_NAME} (Oman real-estate ERP). "
        "Answer primarily in Arabic with clear numbers in OMR. Use ONLY the JSON operational snapshot. "
        "Be concise, actionable, max 180 words. Suggest 1-2 next steps."
    )
    user_msg = f"Snapshot:\n{json.dumps(compact, ensure_ascii=False)}\n\nQuestion: {question}"
    try:
        payload = json.dumps({
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 450,
            "temperature": 0.25,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            return None
        usage = body.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        actions: List[Dict[str, str]] = []
        recs = intel.get("recommendations") or []
        for r in recs[:3]:
            actions.append({
                "label": r.get("action_label") or r["title"],
                "section": r.get("section") or "dashboard",
                "action": "navigate",
            })
        return {
            "reply": text,
            "actions": actions,
            "recommendations": recs[:3],
            "mode": "llm",
            "sufficient": True,
            "tokens_est": tokens,
        }
    except Exception:
        return None


def compose_walid_reply(
    question: str,
    dash: Dict[str, Any],
    intel: Dict[str, Any],
    allow_llm: bool = False,
    limited: bool = False,
) -> Dict[str, Any]:
    rules = walid_rules_reply(question, dash, intel, limited=limited)
    if rules.get("sufficient") or not allow_llm:
        return rules
    llm = walid_llm_reply(question, intel)
    if llm:
        return llm
    return rules


def analyze_ai_question(question: str, dash: Dict[str, Any], limited: bool = False) -> Dict[str, Any]:
    intel = {
        "brief": "",
        "recommendations": [],
        "kpis": dash.get("kpis") or {},
        "overdue_debtors": [],
        "expiring_contracts": [],
        "pending_deposits": [],
        "urgent_maintenance": [],
        "decisions": dash.get("decisions") or [],
    }
    return compose_walid_reply(question, dash, intel, allow_llm=False, limited=limited)


def build_executive_report_html(owner: str, dash: Dict[str, Any]) -> str:
    k = dash.get("kpis") or {}
    decisions = dash.get("decisions") or []
    dec_html = "".join(
        f'<li><strong>{html_escape(d.get("level", ""))}</strong> — {html_escape(d.get("text", ""))}</li>'
        for d in decisions
    )
    return f"""<!doctype html>
<html lang="ar" dir="ltr">
<head>
<meta charset="utf-8">
<title>Executive Report · {COMPANY_NAME}</title>
<style>
  body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;margin:32px;color:#111;background:#fff}}
  h1{{color:#8f631b;border-bottom:3px solid #d8b15b;padding-bottom:12px}}
  .meta{{color:#555;margin-bottom:24px}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}
  .kpi{{border:1px solid #ddd;border-radius:12px;padding:14px;background:#faf8f3}}
  .kpi b{{display:block;font-size:22px;color:#071426}}
  ul{{line-height:1.8}}
  @media print{{button{{display:none}}}}
</style>
</head>
<body>
<h1>{COMPANY_NAME} — التقرير التنفيذي</h1>
<p class="meta">Prepared for / أُعد لـ: <strong>{html_escape(owner)}</strong> · {now_iso()}</p>
<div class="kpis">
  <div class="kpi"><span>الإيرادات</span><b>{fmt_omr(k.get('income', 0))}</b></div>
  <div class="kpi"><span>المصروفات</span><b>{fmt_omr(k.get('expense', 0))}</b></div>
  <div class="kpi"><span>صافي الربح</span><b>{fmt_omr(k.get('net', 0))}</b></div>
  <div class="kpi"><span>المتأخرات</span><b>{fmt_omr(k.get('overdue', 0))}</b></div>
  <div class="kpi"><span>الإشغال</span><b>{k.get('occupancy', 0)}%</b></div>
  <div class="kpi"><span>جاهزية النظام</span><b>{k.get('health', 0)}%</b></div>
  <div class="kpi"><span>عقود تنتهي</span><b>{k.get('expiring', 0)}</b></div>
  <div class="kpi"><span>صيانة مفتوحة</span><b>{k.get('maintenance', 0)}</b></div>
</div>
<h2>قرارات تنفيذية · Executive Decisions</h2>
<ul>{dec_html or '<li>لا قرارات حرجة — stable operations</li>'}</ul>
<p style="margin-top:40px"><button onclick="window.print()">طباعة / Print PDF</button></p>
<script>window.onload=function(){{setTimeout(function(){{window.print()}},400)}}</script>
</body>
</html>"""


def build_accountant_report_data(
    db: sqlite3.Connection,
    report_type: str,
    client_id: str = "",
    month: str = "",
) -> Dict[str, Any]:
    accounts = rows_to_dicts(db.execute("SELECT * FROM accounts").fetchall())
    invoices = rows_to_dicts(db.execute("SELECT * FROM invoices WHERE COALESCE(is_void,0)=0").fetchall())
    clients = {r["id"]: dict(r) for r in db.execute("SELECT * FROM clients").fetchall()}
    contracts = rows_to_dicts(db.execute("SELECT * FROM contracts").fetchall())
    today_s = today()

    income = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "income")
    expense = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "expense")
    billed = sum(float(i["amount"] or 0) for i in invoices)
    paid = sum(float(i["paid_amount"] or 0) for i in invoices)
    outstanding = sum(max(0, float(i["amount"] or 0) - float(i["paid_amount"] or 0)) for i in invoices)
    overdue_rows = [
        i for i in invoices
        if str(i.get("status") or "").lower() != "paid"
        and float(i.get("amount") or 0) - float(i.get("paid_amount") or 0) > 0.001
        and str(i.get("due_date") or "") < today_s
    ]
    overdue_total = sum(max(0, float(i["amount"] or 0) - float(i["paid_amount"] or 0)) for i in overdue_rows)

    if report_type == "summary":
        pending_deposits = [
            c for c in contracts
            if float(c.get("deposit_amount") or 0) > 0 and not int(c.get("deposit_received") or 0)
        ]
        return {
            "generated_at": now_iso(),
            "income": round(income, 3),
            "expense": round(expense, 3),
            "net": round(income - expense, 3),
            "billed": round(billed, 3),
            "collected": round(paid, 3),
            "outstanding": round(outstanding, 3),
            "overdue_total": round(overdue_total, 3),
            "collection_rate": round((paid / billed * 100) if billed else 0, 1),
            "pending_deposits_count": len(pending_deposits),
            "pending_deposits_amount": round(sum(float(c.get("deposit_amount") or 0) for c in pending_deposits), 3),
            "overdue_count": len(overdue_rows),
            "invoice_count": len(invoices),
            "client_count": len(clients),
        }

    if report_type == "trial_balance":
        purchase_invoices = rows_to_dicts(db.execute("SELECT * FROM purchase_invoices").fetchall())
        bank = rows_to_dicts(db.execute("SELECT * FROM bank_transactions").fetchall())
        ar = outstanding
        ap = sum(max(0, float(p["amount"] or 0) - float(p["paid_amount"] or 0)) for p in purchase_invoices)
        bank_balance = sum(
            (1 if str(b["type"]).lower() in ("deposit", "in", "income") else -1) * float(b["amount"] or 0)
            for b in bank
        )
        payroll = sum(float(s["net_salary"] or 0) for s in rows_to_dicts(db.execute("SELECT * FROM salaries").fetchall()))
        ga = sum(float(e["amount"] or 0) for e in rows_to_dicts(db.execute("SELECT * FROM admin_expenses").fetchall()))
        inventory_value = sum(
            float(i["quantity"] or 0) * float(i["unit_cost"] or 0)
            for i in rows_to_dicts(db.execute("SELECT * FROM inventory_items").fetchall())
        )
        lines = [
            {"side": "debit", "label": "ذمم مدينة / Accounts Receivable", "amount": ar},
            {"side": "debit", "label": "نقدية وبنوك / Cash & Bank", "amount": bank_balance},
            {"side": "debit", "label": "مخزون / Inventory", "amount": inventory_value},
            {"side": "credit", "label": "ذمم دائنة / Accounts Payable", "amount": ap},
            {"side": "credit", "label": "إيرادات / Revenue", "amount": income},
            {"side": "credit", "label": "مصروفات / Expenses", "amount": expense},
            {"side": "credit", "label": "رواتب / Payroll", "amount": payroll},
            {"side": "credit", "label": "مصروفات إدارية / G&A", "amount": ga},
        ]
        debit_total = round(sum(l["amount"] for l in lines if l["side"] == "debit"), 3)
        credit_total = round(sum(l["amount"] for l in lines if l["side"] == "credit"), 3)
        return {
            "generated_at": now_iso(),
            "lines": [{**l, "amount": round(float(l["amount"] or 0), 3)} for l in lines],
            "debit_total": debit_total,
            "credit_total": credit_total,
            "difference": round(debit_total - credit_total, 3),
        }

    if report_type == "overdue":
        rows = []
        for inv in sorted(overdue_rows, key=lambda x: x.get("due_date") or ""):
            client = clients.get(inv.get("client_id"), {})
            rem = max(0, float(inv.get("amount") or 0) - float(inv.get("paid_amount") or 0))
            rows.append({
                "invoice_no": inv.get("invoice_no"),
                "client_name": client.get("name") or inv.get("client_id"),
                "due_date": inv.get("due_date"),
                "issue_date": inv.get("issue_date"),
                "amount": round(float(inv.get("amount") or 0), 3),
                "paid": round(float(inv.get("paid_amount") or 0), 3),
                "remaining": round(rem, 3),
                "status": inv.get("status"),
            })
        return {"generated_at": now_iso(), "rows": rows, "total": round(overdue_total, 3), "count": len(rows)}

    if report_type == "deposits":
        rows = []
        for c in contracts:
            dep = float(c.get("deposit_amount") or 0)
            if dep <= 0:
                continue
            if int(c.get("deposit_received") or 0):
                continue
            client = clients.get(c.get("client_id"), {})
            rows.append({
                "contract_no": c.get("contract_no") or c.get("id"),
                "client_name": client.get("name") or c.get("client_id"),
                "start_date": c.get("start_date"),
                "end_date": c.get("end_date"),
                "deposit_amount": round(dep, 3),
                "status": c.get("status"),
            })
        return {
            "generated_at": now_iso(),
            "rows": rows,
            "total": round(sum(r["deposit_amount"] for r in rows), 3),
            "count": len(rows),
        }

    if report_type == "client_statement":
        if not client_id:
            return {"error": "client_id required"}
        client = clients.get(client_id)
        if not client:
            return {"error": "Client not found"}
        inv_rows = [i for i in invoices if i.get("client_id") == client_id]
        acc_rows = [a for a in accounts if a.get("client_id") == client_id]
        pay_rows = rows_to_dicts(
            db.execute(
                "SELECT p.* FROM payments p JOIN invoices i ON i.id=p.invoice_id WHERE i.client_id=? ORDER BY p.payment_date DESC",
                (client_id,),
            ).fetchall()
        )
        total = sum(float(i.get("amount") or 0) for i in inv_rows)
        paid_amt = sum(float(i.get("paid_amount") or 0) for i in inv_rows)
        return {
            "generated_at": now_iso(),
            "client": client,
            "invoices": inv_rows,
            "accounts": acc_rows,
            "payments": pay_rows,
            "totals": {
                "billed": round(total, 3),
                "paid": round(paid_amt, 3),
                "outstanding": round(total - paid_amt, 3),
            },
        }

    if report_type == "monthly":
        month = month or today_s[:7]
        inv_m = [i for i in invoices if str(i.get("issue_date") or "").startswith(month)]
        acc_m = [a for a in accounts if str(a.get("entry_date") or "").startswith(month)]
        inc_m = sum(float(a["amount"] or 0) for a in acc_m if a["type"] == "income")
        exp_m = sum(float(a["amount"] or 0) for a in acc_m if a["type"] == "expense")
        billed_m = sum(float(i.get("amount") or 0) for i in inv_m)
        paid_m = sum(float(i.get("paid_amount") or 0) for i in inv_m)
        return {
            "generated_at": now_iso(),
            "month": month,
            "income": round(inc_m, 3),
            "expense": round(exp_m, 3),
            "net": round(inc_m - exp_m, 3),
            "billed": round(billed_m, 3),
            "collected": round(paid_m, 3),
            "invoice_count": len(inv_m),
            "transaction_count": len(acc_m),
        }

    return {"error": f"Unknown report type: {report_type}"}


def build_accountant_report_html(
    report_type: str,
    data: Dict[str, Any],
    owner: str,
    client_id: str = "",
    month: str = "",
) -> str:
    company_ar = COMPANY_NAME_AR
    company_en = "QUALITY OF LAUNCH PROJECTS LLC"
    titles = {
        "summary": "ملخص المحاسب · Accountant Summary",
        "trial_balance": "ميزان مراجعة مبسّط · Trial Balance",
        "overdue": "تقرير المتأخرات · Overdue Invoices",
        "deposits": "تأمينات غير مستلمة · Pending Deposits",
        "client_statement": "كشف حساب عميل · Client Statement",
        "monthly": f"تقرير شهري · Monthly Report {data.get('month', month)}",
    }
    title = titles.get(report_type, "تقرير محاسبي")

    def table(headers: List[str], rows: List[List[str]]) -> str:
        head = "".join(f"<th>{html_escape(h)}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td>{html_escape(c)}</td>" for c in row) + "</tr>" for row in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body or '<tr><td colspan=\"'+str(len(headers))+'\">لا توجد بيانات</td></tr>'}</tbody></table>"

    body = ""
    if report_type == "summary":
        body = f"""<div class="kpis">
          <div class="kpi"><span>الإيرادات</span><b>{fmt_omr(data.get('income',0))}</b></div>
          <div class="kpi"><span>المصروفات</span><b>{fmt_omr(data.get('expense',0))}</b></div>
          <div class="kpi"><span>الصافي</span><b>{fmt_omr(data.get('net',0))}</b></div>
          <div class="kpi"><span>المتأخرات</span><b>{fmt_omr(data.get('overdue_total',0))}</b></div>
          <div class="kpi"><span>ذمم مدينة</span><b>{fmt_omr(data.get('outstanding',0))}</b></div>
          <div class="kpi"><span>نسبة التحصيل</span><b>{data.get('collection_rate',0)}%</b></div>
          <div class="kpi"><span>تأمينات معلقة</span><b>{data.get('pending_deposits_count',0)}</b></div>
          <div class="kpi"><span>قيمة التأمينات</span><b>{fmt_omr(data.get('pending_deposits_amount',0))}</b></div>
        </div>"""
    elif report_type == "trial_balance":
        rows = [[l["label"], l["side"], fmt_omr(l["amount"])] for l in data.get("lines", [])]
        body = table(["البند", "مدين/دائن", "المبلغ"], rows)
        body += f"<p><strong>إجمالي مدين:</strong> {fmt_omr(data.get('debit_total',0))} · <strong>إجمالي دائن:</strong> {fmt_omr(data.get('credit_total',0))} · <strong>الفرق:</strong> {fmt_omr(data.get('difference',0))}</p>"
    elif report_type == "overdue":
        rows = [[r.get("invoice_no",""), r.get("client_name",""), r.get("due_date",""), fmt_omr(r.get("remaining",0))] for r in data.get("rows",[])]
        body = table(["فاتورة", "العميل", "الاستحقاق", "المتبقي"], rows)
        body += f"<p><strong>إجمالي المتأخرات:</strong> {fmt_omr(data.get('total',0))} ({data.get('count',0)} فاتورة)</p>"
    elif report_type == "deposits":
        rows = [[r.get("contract_no",""), r.get("client_name",""), r.get("start_date",""), r.get("end_date",""), fmt_omr(r.get("deposit_amount",0))] for r in data.get("rows",[])]
        body = table(["العقد", "العميل", "البداية", "النهاية", "عربون/وديعة"], rows)
        body += f"<p><strong>إجمالي العربون/الودائع غير المستلمة:</strong> {fmt_omr(data.get('total',0))} (عقود الإيجار تُنشأ بدون تأمين إيجار)</p>"
    elif report_type == "client_statement":
        c = data.get("client") or {}
        t = data.get("totals") or {}
        body = f"<p><strong>{html_escape(c.get('name',''))}</strong> · {html_escape(c.get('phone',''))} · {html_escape(c.get('email',''))}</p>"
        body += f"<p>إجمالي: {fmt_omr(t.get('billed',0))} · مدفوع: {fmt_omr(t.get('paid',0))} · متبقي: {fmt_omr(t.get('outstanding',0))}</p>"
        inv_rows = [[i.get("invoice_no",""), i.get("issue_date",""), fmt_omr(i.get("amount",0)), fmt_omr(i.get("paid_amount",0)), i.get("status","")] for i in data.get("invoices",[])]
        body += "<h3>الفواتير</h3>" + table(["رقم", "تاريخ", "إجمالي", "مدفوع", "حالة"], inv_rows)
        acc_rows = [[a.get("entry_date",""), a.get("type",""), a.get("description",""), fmt_omr(a.get("amount",0))] for a in data.get("accounts",[])]
        body += "<h3>الحركات</h3>" + table(["تاريخ", "نوع", "وصف", "مبلغ"], acc_rows)
    elif report_type == "monthly":
        body = f"""<div class="kpis">
          <div class="kpi"><span>إيرادات الشهر</span><b>{fmt_omr(data.get('income',0))}</b></div>
          <div class="kpi"><span>مصروفات الشهر</span><b>{fmt_omr(data.get('expense',0))}</b></div>
          <div class="kpi"><span>صافي الشهر</span><b>{fmt_omr(data.get('net',0))}</b></div>
          <div class="kpi"><span>فواتير الشهر</span><b>{fmt_omr(data.get('billed',0))}</b></div>
          <div class="kpi"><span>محصّل الشهر</span><b>{fmt_omr(data.get('collected',0))}</b></div>
          <div class="kpi"><span>عدد الفواتير</span><b>{data.get('invoice_count',0)}</b></div>
        </div>"""

    return f"""<!doctype html>
<html lang="ar" dir="ltr">
<head>
<meta charset="utf-8">
<title>{html_escape(title)}</title>
<style>
  @page{{size:A4;margin:14mm}}
  body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;margin:24px;color:#111;background:#fff;line-height:1.6}}
  .head{{border-bottom:4px solid #c9a227;padding-bottom:14px;margin-bottom:18px}}
  .head img{{width:72px;height:72px;object-fit:contain;float:right;margin-left:14px}}
  h1{{margin:0;color:#0b1220;font-size:22px}}
  h2{{color:#8f631b;font-size:16px}}
  .meta{{color:#555;margin:12px 0 20px}}
  .kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}}
  .kpi{{border:1px solid #e5d39a;border-radius:12px;padding:12px;background:#fffdf7}}
  .kpi b{{display:block;font-size:18px;color:#071426;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}}
  th,td{{border:1px solid #e5e7eb;padding:8px;text-align:right}}
  th{{background:#0b1220;color:#f5d76e}}
  .foot{{margin-top:24px;padding-top:12px;border-top:1px solid #ddd;font-size:12px;color:#666;text-align:center}}
  @media print{{button{{display:none}}}}
</style>
</head>
<body>
<div class="head">
  <img src="/assets/brand-logo-gold.png?v=12" alt="Logo">
  <h1>{html_escape(company_ar)}</h1>
  <h2>{html_escape(company_en)} · {html_escape(title)}</h2>
</div>
<p class="meta">أُعد بواسطة: <strong>{html_escape(owner)}</strong> · {html_escape(data.get('generated_at', now_iso()))}</p>
{body}
<p style="margin-top:28px"><button onclick="window.print()">طباعة / حفظ PDF</button></p>
<div class="foot">C.R. 1466316 · info@alamal.info · +968 71924089</div>
<script>window.onload=function(){{setTimeout(function(){{window.print()}},500)}}</script>
</body>
</html>"""


def bank_tx_signed_amount(tx: Dict[str, Any]) -> float:
    amt = float(tx.get("amount") or 0)
    t = str(tx.get("type") or "").lower()
    return amt if t in ("deposit", "in", "income") else -amt


def resolve_period_bounds(db: sqlite3.Connection, period_name: str) -> Tuple[str, str]:
    if not period_name:
        return "", ""
    row = db.execute(
        "SELECT start_date, end_date FROM financial_periods WHERE period_name=?",
        (period_name,),
    ).fetchone()
    if row:
        return str(row["start_date"] or ""), str(row["end_date"] or "")
    if len(period_name) == 7 and period_name[4] == "-":
        return f"{period_name}-01", f"{period_name}-31"
    return "", ""


def auto_match_bank_transactions(
    db: sqlite3.Connection,
    bank_name: str = "",
    period_start: str = "",
    period_end: str = "",
) -> Dict[str, Any]:
    sql = "SELECT * FROM bank_transactions WHERE lower(status) NOT IN ('matched','reconciled')"
    args: List[Any] = []
    if bank_name:
        sql += " AND bank_name=?"
        args.append(bank_name)
    if period_start:
        sql += " AND bank_date>=?"
        args.append(period_start)
    if period_end:
        sql += " AND bank_date<=?"
        args.append(period_end)
    unmatched = rows_to_dicts(db.execute(sql, args).fetchall())
    payments = rows_to_dicts(db.execute("SELECT * FROM payments ORDER BY payment_date DESC").fetchall())
    invoices = {r["id"]: dict(r) for r in db.execute("SELECT * FROM invoices").fetchall()}
    accounts_by_invoice: Dict[str, str] = {}
    for a in rows_to_dicts(db.execute("SELECT id, invoice_id FROM accounts WHERE invoice_id IS NOT NULL").fetchall()):
        accounts_by_invoice[str(a["invoice_id"])] = a["id"]
    matched_ids: set = set()
    matched = 0
    for tx in unmatched:
        if str(tx.get("type") or "").lower() not in ("deposit", "in", "income"):
            continue
        amt = float(tx.get("amount") or 0)
        if amt <= 0:
            continue
        tx_date = str(tx.get("bank_date") or "")
        ref = str(tx.get("reference") or "") + " " + str(tx.get("description") or "")
        best_pay = None
        for pay in payments:
            if pay["id"] in matched_ids:
                continue
            if abs(float(pay.get("amount") or 0) - amt) > 0.001:
                continue
            pay_date = str(pay.get("payment_date") or "")
            if tx_date and pay_date and abs(int(tx_date.replace("-", "")) - int(pay_date.replace("-", ""))) > 7:
                continue
            inv = invoices.get(pay.get("invoice_id"))
            if inv and inv.get("invoice_no") and inv["invoice_no"] in ref:
                best_pay = pay
                break
            if not best_pay:
                best_pay = pay
        if not best_pay:
            for inv_id, inv in invoices.items():
                if inv.get("invoice_no") and inv["invoice_no"] in ref:
                    rem = float(inv.get("amount") or 0) - float(inv.get("paid_amount") or 0)
                    if abs(rem - amt) <= 0.001 or abs(float(inv.get("amount") or 0) - amt) <= 0.001:
                        db.execute(
                            "UPDATE bank_transactions SET matched_invoice_id=?, status='Matched' WHERE id=?",
                            (inv_id, tx["id"]),
                        )
                        matched += 1
                        break
            continue
        inv_id = best_pay.get("invoice_id")
        acc_id = accounts_by_invoice.get(str(inv_id))
        db.execute(
            """
            UPDATE bank_transactions SET matched_invoice_id=?, matched_payment_id=?, matched_account_id=?, status='Matched'
            WHERE id=?
            """,
            (inv_id, best_pay["id"], acc_id, tx["id"]),
        )
        matched_ids.add(best_pay["id"])
        matched += 1
    return {"matched": matched, "scanned": len(unmatched)}


def build_bank_reconciliation_data(
    db: sqlite3.Connection,
    bank_name: str = "",
    period_name: str = "",
) -> Dict[str, Any]:
    period_start, period_end = resolve_period_bounds(db, period_name)
    sql = "SELECT * FROM bank_transactions WHERE 1=1"
    args: List[Any] = []
    if bank_name:
        sql += " AND bank_name=?"
        args.append(bank_name)
    if period_start:
        sql += " AND bank_date>=?"
        args.append(period_start)
    if period_end:
        sql += " AND bank_date<=?"
        args.append(period_end)
    rows = rows_to_dicts(db.execute(sql, args).fetchall())
    invoices = {r["id"]: dict(r) for r in db.execute("SELECT id, invoice_no, client_id FROM invoices").fetchall()}
    clients = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM clients").fetchall()}
    book_balance = round(sum(bank_tx_signed_amount(r) for r in rows), 3)
    matched_rows = []
    unmatched_rows = []
    for r in rows:
        status = str(r.get("status") or "").lower()
        inv_id = r.get("matched_invoice_id")
        inv_no = invoices.get(inv_id, {}).get("invoice_no") if inv_id else ""
        client_name = ""
        if inv_id and invoices.get(inv_id):
            client_name = clients.get(invoices[inv_id].get("client_id"), "")
        item = {
            "id": r["id"],
            "bank_date": r.get("bank_date"),
            "reference": r.get("reference"),
            "type": r.get("type"),
            "description": r.get("description"),
            "amount": round(float(r.get("amount") or 0), 3),
            "status": r.get("status"),
            "invoice_no": inv_no,
            "client_name": client_name,
        }
        if status in ("matched", "reconciled") or inv_id:
            matched_rows.append(item)
        else:
            unmatched_rows.append(item)
    payments_sql = "SELECT p.*, i.invoice_no FROM payments p LEFT JOIN invoices i ON i.id=p.invoice_id WHERE 1=1"
    pay_args: List[Any] = []
    if period_start:
        payments_sql += " AND p.payment_date>=?"
        pay_args.append(period_start)
    if period_end:
        payments_sql += " AND p.payment_date<=?"
        pay_args.append(period_end)
    payments_no_bank = []
    bank_payment_ids = {
        str(r.get("matched_payment_id") or "")
        for r in rows if r.get("matched_payment_id")
    }
    for p in rows_to_dicts(db.execute(payments_sql, pay_args).fetchall()):
        method = str(p.get("method") or "").lower()
        if method not in ("bank transfer", "card", "bank", "تحويل بنكي"):
            continue
        if p["id"] in bank_payment_ids:
            continue
        payments_no_bank.append({
            "payment_id": p["id"],
            "payment_date": p.get("payment_date"),
            "amount": round(float(p.get("amount") or 0), 3),
            "invoice_no": p.get("invoice_no"),
            "method": p.get("method"),
        })
    open_periods = [
        dict(p) for p in db.execute(
            "SELECT id, period_name, start_date, end_date FROM financial_periods WHERE lower(status)='open' ORDER BY start_date DESC"
        ).fetchall()
    ]
    alerts = build_bank_variance_alerts(db)
    return {
        "bank_name": bank_name or "All Banks",
        "period_name": period_name,
        "period_start": period_start,
        "period_end": period_end,
        "book_balance": book_balance,
        "transaction_count": len(rows),
        "matched_count": len(matched_rows),
        "unmatched_count": len(unmatched_rows),
        "matched_transactions": matched_rows,
        "unmatched_transactions": unmatched_rows,
        "payments_without_bank": payments_no_bank,
        "open_periods": open_periods,
        "alerts": alerts,
    }


def build_bank_variance_alerts(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    unmatched = db.execute(
        "SELECT COUNT(*) FROM bank_transactions WHERE lower(status) NOT IN ('matched','reconciled')"
    ).fetchone()[0]
    if unmatched:
        alerts.append({
            "level": "High",
            "text": f"{unmatched} حركة بنك غير مطابقة — راجع تسوية البنك",
            "count": unmatched,
            "type": "unmatched_bank",
        })
    variances = rows_to_dicts(
        db.execute(
            """
            SELECT bank_name, period_name, difference, reconciled_at FROM bank_reconciliations
            WHERE abs(difference) > 0.001 AND lower(status) IN ('variance','pending','open')
            ORDER BY reconciled_at DESC LIMIT 5
            """
        ).fetchall()
    )
    for v in variances:
        alerts.append({
            "level": "High",
            "text": f"فرق تسوية {v.get('bank_name')} / {v.get('period_name')}: {fmt_omr(float(v.get('difference') or 0))}",
            "type": "variance",
            "bank_name": v.get("bank_name"),
            "period_name": v.get("period_name"),
        })
    open_periods = db.execute(
        "SELECT COUNT(*) FROM financial_periods WHERE lower(status)='open'"
    ).fetchone()[0]
    if open_periods > 2:
        alerts.append({
            "level": "Medium",
            "text": f"{open_periods} فترات مالية مفتوحة — يُفضّل إقفال الفترات المنتهية",
            "type": "open_periods",
        })
    return alerts


def get_dismissed_alert_keys(db: sqlite3.Connection, user_id: str) -> set:
    rows = db.execute("SELECT alert_key FROM alert_dismissals WHERE user_id=?", (user_id,)).fetchall()
    return {str(r["alert_key"]) for r in rows}


ROLE_ALERT_CATEGORIES: Dict[str, set] = {
    "owner": {"contracts", "finance", "governance", "inventory", "operations"},
    "admin": {"contracts", "finance", "governance", "inventory", "operations"},
    "accountant": {"finance", "governance", "contracts"},
    "operations": {"contracts", "operations", "inventory", "governance"},
    "maintenance": {"operations", "inventory"},
    "viewer": {"contracts", "operations", "finance"},
}

ROLE_BOARD_META: Dict[str, Dict[str, Any]] = {
    "owner": {
        "title_ar": "لوحة المالك",
        "subtitle_ar": "ملخص تنفيذي وتنبيهات تحتاج قراراً اليوم",
        "quick_actions": [
            {"section": "approvals", "label": "مركز الاعتمادات"},
            {"section": "receivables", "label": "التحصيل الذكي"},
            {"section": "messages", "label": "التنبيهات"},
            {"section": "reports", "label": "التقارير"},
        ],
    },
    "admin": {
        "title_ar": "لوحة الإدارة",
        "subtitle_ar": "تشغيل كامل + متابعة المخاطر",
        "quick_actions": [
            {"section": "dashboard", "label": "لوحة التحكم"},
            {"section": "approvals", "label": "الاعتمادات"},
            {"section": "users", "label": "المستخدمون"},
            {"section": "messages", "label": "التنبيهات"},
        ],
    },
    "accountant": {
        "title_ar": "لوحة المحاسب",
        "subtitle_ar": "تحصيل، اعتمادات، بنك، ومتأخرات",
        "quick_actions": [
            {"section": "receivables", "label": "التحصيل الذكي"},
            {"section": "invoices", "label": "الفواتير"},
            {"section": "approvals", "label": "الاعتمادات"},
            {"section": "bank-reconciliation", "label": "تسوية البنك"},
        ],
    },
    "operations": {
        "title_ar": "لوحة العمليات",
        "subtitle_ar": "عقود، إشغال، وصيانة يومية",
        "quick_actions": [
            {"section": "contracts", "label": "العقود"},
            {"section": "properties", "label": "العقارات"},
            {"section": "maintenance", "label": "الصيانة"},
            {"section": "daily-ops", "label": "العمليات اليومية"},
        ],
    },
    "maintenance": {
        "title_ar": "لوحة الصيانة",
        "subtitle_ar": "طلبات عاجلة ومخزون منخفض",
        "quick_actions": [
            {"section": "maintenance", "label": "طلبات الصيانة"},
            {"section": "inventory", "label": "المخزن"},
            {"section": "properties", "label": "العقارات"},
            {"section": "messages", "label": "التنبيهات"},
        ],
    },
    "viewer": {
        "title_ar": "لوحة المتابعة",
        "subtitle_ar": "عرض مؤشرات وتنبيهات للقراءة فقط",
        "quick_actions": [
            {"section": "dashboard", "label": "لوحة التحكم"},
            {"section": "reports", "label": "التقارير"},
            {"section": "messages", "label": "التنبيهات"},
        ],
    },
}

KPI_LABELS_AR: Dict[str, str] = {
    "properties": "العقارات",
    "rented": "مستأجرة",
    "vacant": "شاغرة",
    "income": "الإيرادات",
    "expense": "المصروفات",
    "net": "الصافي",
    "health": "صحة النظام",
    "occupancy": "الإشغال %",
    "overdue": "المتأخرات",
    "maintenance": "صيانة مفتوحة",
    "expiring": "عقود قاربت الانتهاء",
    "expired": "عقود منتهية",
    "paid": "المحصّل",
    "billed": "المفوتر",
    "bank_balance": "رصيد البنك",
    "payroll": "الرواتب",
    "inventory_value": "قيمة المخزون",
    "purchases_due": "مشتريات مستحقة",
    "pending_approvals": "اعتمادات معلّقة",
    "alert_center_total": "تنبيهات",
    "alert_center_high": "تنبيهات عاجلة",
}


def filter_alerts_for_role(alerts: List[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
    allowed = ROLE_ALERT_CATEGORIES.get(str(role or "viewer").lower(), ROLE_ALERT_CATEGORIES["viewer"])
    return [a for a in alerts if str(a.get("category") or "") in allowed]


def build_alert_center(
    db: sqlite3.Connection,
    user_id: Optional[str] = None,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    today_d = date.today()
    dismissed = get_dismissed_alert_keys(db, user_id) if user_id else set()
    clients = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM clients").fetchall()}
    properties = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM properties").fetchall()}
    alerts: List[Dict[str, Any]] = []

    def push(alert: Dict[str, Any]) -> None:
        key = str(alert.get("id") or "")
        if key in dismissed:
            return
        alerts.append(alert)

    contracts = rows_to_dicts(
        db.execute(
            "SELECT * FROM contracts WHERE lower(status) IN ('active','renewed') OR lower(status) LIKE '%active%'"
        ).fetchall()
    )
    for c in contracts:
        try:
            end = datetime.fromisoformat(str(c["end_date"])).date()
        except ValueError:
            continue
        days_left = (end - today_d).days
        client_name = clients.get(c.get("client_id"), "")
        prop_name = properties.get(c.get("property_id"), "")
        label = f"{c.get('contract_no') or c['id']} · {client_name}"
        if days_left < 0:
            push({
                "id": f"contract-expired-{c['id']}",
                "type": "contract_expired",
                "category": "contracts",
                "level": "Critical",
                "title": "عقد منتهٍ",
                "text": f"{label} انتهى منذ {abs(days_left)} يوم — قرار تجديد أو إغلاق",
                "entity": "contracts",
                "entity_id": c["id"],
                "action_section": "contracts",
                "action_label": "إدارة العقد",
                "days_left": days_left,
                "due_date": c.get("end_date"),
            })
        elif days_left <= 30:
            push({
                "id": f"contract-30-{c['id']}",
                "type": "contract_expiry_30",
                "category": "contracts",
                "level": "High",
                "title": "عقد خلال 30 يوم",
                "text": f"{label} · {prop_name} · يتبقى {days_left} يوم",
                "entity": "contracts",
                "entity_id": c["id"],
                "action_section": "contracts",
                "action_label": "تجديد",
                "days_left": days_left,
                "due_date": c.get("end_date"),
            })
        elif days_left <= 60:
            push({
                "id": f"contract-60-{c['id']}",
                "type": "contract_expiry_60",
                "category": "contracts",
                "level": "Medium",
                "title": "عقد خلال 60 يوم",
                "text": f"{label} · يتبقى {days_left} يوم",
                "entity": "contracts",
                "entity_id": c["id"],
                "action_section": "contracts",
                "action_label": "متابعة",
                "days_left": days_left,
                "due_date": c.get("end_date"),
            })
        elif days_left <= 90:
            push({
                "id": f"contract-90-{c['id']}",
                "type": "contract_expiry_90",
                "category": "contracts",
                "level": "Medium",
                "title": "عقد خلال 90 يوم",
                "text": f"{label} · يتبقى {days_left} يوم",
                "entity": "contracts",
                "entity_id": c["id"],
                "action_section": "contracts",
                "action_label": "متابعة",
                "days_left": days_left,
                "due_date": c.get("end_date"),
            })
        notice = int(c.get("renewal_notice_days") or 30)
        if 0 <= days_left <= notice:
            push({
                "id": f"renewal-{c['id']}",
                "type": "renewal_reminder",
                "category": "contracts",
                "level": "High",
                "title": "تذكير تجديد عقد",
                "text": f"{label} · قرار تجديد قبل {c.get('end_date')} ({days_left} يوم)",
                "entity": "contracts",
                "entity_id": c["id"],
                "action_section": "contracts",
                "action_label": "تجديد الآن",
                "days_left": days_left,
            })
        dep = float(c.get("deposit_amount") or 0)
        if dep > 0 and not int(c.get("deposit_received") or 0):
            push({
                "id": f"deposit-{c['id']}",
                "type": "pending_deposit",
                "category": "finance",
                "level": "High",
                "title": "تأمين غير مستلم",
                "text": f"{label} · تأمين {fmt_omr(dep)} غير مستلم",
                "entity": "contracts",
                "entity_id": c["id"],
                "action_section": "contracts",
                "action_label": "متابعة التأمين",
                "amount": dep,
            })

    overdue_invoices = rows_to_dicts(
        db.execute(
            """
            SELECT id, invoice_no, client_id, amount, paid_amount, due_date
            FROM invoices
            WHERE COALESCE(is_void,0)=0 AND lower(status)!='paid' AND due_date < ?
            ORDER BY due_date
            LIMIT 40
            """,
            (today(),),
        ).fetchall()
    )
    for inv in overdue_invoices:
        rem = max(0, float(inv.get("amount") or 0) - float(inv.get("paid_amount") or 0))
        push({
            "id": f"overdue-inv-{inv['id']}",
            "type": "overdue_invoice",
            "category": "finance",
            "level": "High",
            "title": "فاتورة متأخرة",
            "text": f"{inv.get('invoice_no')} · {clients.get(inv.get('client_id'), '')} · {fmt_omr(rem)} · استحقاق {inv.get('due_date')}",
            "entity": "invoices",
            "entity_id": inv["id"],
            "action_section": "invoices",
            "action_label": "تحصيل",
            "amount": rem,
            "due_date": inv.get("due_date"),
        })

    for appr in rows_to_dicts(
        db.execute(
            "SELECT * FROM approvals WHERE lower(status)='pending' ORDER BY requested_at DESC LIMIT 20"
        ).fetchall()
    ):
        push({
            "id": f"approval-{appr['id']}",
            "type": "pending_approval",
            "category": "governance",
            "level": "High",
            "title": "طلب اعتماد",
            "text": f"{appr.get('request_type')} · {appr.get('requested_by')} · {appr.get('requested_at')}",
            "entity": appr.get("entity"),
            "entity_id": appr.get("entity_id"),
            "action_section": "approvals",
            "action_label": "مراجعة",
        })

    for ba in build_bank_variance_alerts(db):
        push({
            "id": f"bank-{ba.get('type', 'variance')}-{ba.get('bank_name', '')}-{ba.get('period_name', '')}",
            "type": ba.get("type", "bank_variance"),
            "category": "finance",
            "level": ba.get("level", "High"),
            "title": "تنبيه بنكي",
            "text": ba.get("text", ""),
            "action_section": "bank-reconciliation",
            "action_label": "تسوية البنك",
        })

    low_stock = rows_to_dicts(
        db.execute(
            "SELECT id, name, sku, quantity, min_quantity FROM inventory_items WHERE quantity <= min_quantity LIMIT 15"
        ).fetchall()
    )
    for item in low_stock:
        push({
            "id": f"stock-{item['id']}",
            "type": "low_stock",
            "category": "inventory",
            "level": "Medium",
            "title": "مخزون منخفض",
            "text": f"{item.get('name')} ({item.get('sku')}) · {item.get('quantity')}/{item.get('min_quantity')}",
            "entity": "inventory_items",
            "entity_id": item["id"],
            "action_section": "inventory",
            "action_label": "المخزن",
        })

    for m in rows_to_dicts(
        db.execute(
            """
            SELECT id, title, property_id, priority, status FROM maintenance
            WHERE lower(status) NOT IN ('closed','done','completed') AND lower(priority)='high'
            LIMIT 15
            """
        ).fetchall()
    ):
        push({
            "id": f"maint-high-{m['id']}",
            "type": "maintenance_high",
            "category": "operations",
            "level": "High",
            "title": "صيانة عاجلة",
            "text": f"{m.get('title')} · {properties.get(m.get('property_id'), '')}",
            "entity": "maintenance",
            "entity_id": m["id"],
            "action_section": "maintenance",
            "action_label": "فتح الصيانة",
        })

    level_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Good": 4}
    alerts.sort(key=lambda a: (level_order.get(a.get("level", "Low"), 9), a.get("days_left") or 9999))
    role_key = str(role or "viewer").lower()
    if role is not None:
        alerts = filter_alerts_for_role(alerts, role_key)

    summary = {
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a.get("level") == "Critical"),
        "high": sum(1 for a in alerts if a.get("level") == "High"),
        "contracts": sum(1 for a in alerts if a.get("category") == "contracts"),
        "finance": sum(1 for a in alerts if a.get("category") == "finance"),
        "operations": sum(1 for a in alerts if a.get("category") == "operations"),
        "inventory": sum(1 for a in alerts if a.get("category") == "inventory"),
        "governance": sum(1 for a in alerts if a.get("category") == "governance"),
        "dismissed": len(dismissed),
        "role": role_key if role is not None else None,
    }
    top = alerts[:3]
    return {
        "generated_at": now_iso(),
        "role": role_key if role is not None else None,
        "summary": summary,
        "top_priorities": top,
        "alerts": alerts,
        "channels": {
            "in_app": True,
            "email": bool(os.environ.get("LQ_SMTP_HOST")),
            "sms": bool(os.environ.get("LQ_SMS_ENABLED")),
        },
    }


def build_role_board(db: sqlite3.Connection, user: Dict[str, Any]) -> Dict[str, Any]:
    role = str((user or {}).get("role") or "viewer").lower()
    meta = ROLE_BOARD_META.get(role, ROLE_BOARD_META["viewer"])
    dash = build_dashboard(db)
    kpis_all = dash.get("kpis") or {}
    allowed_keys = list(ui_permissions_for_role(role).get("kpis") or [])
    # Always surface pending approvals / alert counts for decision roles
    for extra in ("pending_approvals", "alert_center_total", "alert_center_high", "expiring", "expired"):
        if extra not in allowed_keys and role in ("owner", "admin", "accountant", "operations"):
            allowed_keys.append(extra)
    money_keys = {
        "income", "expense", "net", "overdue", "paid", "billed", "bank_balance",
        "payroll", "inventory_value", "purchases_due",
    }
    cards: List[Dict[str, Any]] = []
    for key in allowed_keys:
        if key not in kpis_all:
            continue
        val = kpis_all.get(key)
        if key in money_keys:
            display = fmt_omr(float(val or 0))
        elif key in ("occupancy", "health"):
            display = f"{float(val or 0):.0f}%"
        else:
            display = str(int(float(val or 0))) if isinstance(val, (int, float)) or str(val).replace(".", "", 1).isdigit() else str(val)
        cards.append({
            "key": key,
            "label": KPI_LABELS_AR.get(key, key),
            "value": val,
            "display": display,
        })
        if len(cards) >= 8:
            break
    center = build_alert_center(db, user_id=(user or {}).get("id"), role=role)
    alerts = center.get("alerts") or []
    top = center.get("top_priorities") or alerts[:3]
    return {
        "role": role,
        "username": (user or {}).get("username"),
        "name": (user or {}).get("name"),
        "title_ar": meta.get("title_ar"),
        "subtitle_ar": meta.get("subtitle_ar"),
        "kpis": cards,
        "alerts": alerts[:12],
        "top_priorities": top,
        "summary": center.get("summary") or {},
        "quick_actions": meta.get("quick_actions") or [],
        "decisions": (dash.get("decisions") or [])[:4],
        "generated_at": now_iso(),
    }


def build_receivables_aging(db: sqlite3.Connection, bucket_filter: Optional[str] = None) -> Dict[str, Any]:
    """Smart receivables: aging buckets + open invoice items for reminders."""
    today_d = date.today()
    today_s = today_d.isoformat()
    buckets = {
        "current": {"key": "current", "label": "حالي (غير مستحق)", "amount": 0.0, "count": 0},
        "1-30": {"key": "1-30", "label": "1–30 يوم", "amount": 0.0, "count": 0},
        "31-60": {"key": "31-60", "label": "31–60 يوم", "amount": 0.0, "count": 0},
        "61-90": {"key": "61-90", "label": "61–90 يوم", "amount": 0.0, "count": 0},
        "90+": {"key": "90+", "label": "أكثر من 90 يوم", "amount": 0.0, "count": 0},
    }
    clients = {str(c["id"]): c for c in rows_to_dicts(db.execute("SELECT id, name, phone, email FROM clients").fetchall())}
    invoices = rows_to_dicts(
        db.execute(
            """
            SELECT id, invoice_no, client_id, property_id, contract_id, due_date, amount, paid_amount, status, COALESCE(is_void,0) AS is_void
            FROM invoices
            WHERE COALESCE(is_void,0)=0
              AND lower(COALESCE(status,'')) NOT IN ('paid','void','cancelled')
            """
        ).fetchall()
    )
    props = {str(p["id"]): p for p in rows_to_dicts(db.execute("SELECT id, name FROM properties").fetchall())}
    items: List[Dict[str, Any]] = []
    total_open = 0.0
    total_overdue = 0.0

    def bucket_for(days_late: int) -> str:
        if days_late <= 0:
            return "current"
        if days_late <= 30:
            return "1-30"
        if days_late <= 60:
            return "31-60"
        if days_late <= 90:
            return "61-90"
        return "90+"

    for inv in invoices:
        amount = float(inv.get("amount") or 0)
        paid = float(inv.get("paid_amount") or 0)
        rem = round(max(0.0, amount - paid), 3)
        if rem <= 0.001:
            continue
        due_s = str(inv.get("due_date") or "").strip()
        try:
            due_d = datetime.fromisoformat(due_s[:10]).date() if due_s else today_d
        except Exception:
            due_d = today_d
        days_late = (today_d - due_d).days
        bkey = bucket_for(days_late)
        if bucket_filter and bucket_filter not in (bkey, "overdue"):
            continue
        if bucket_filter == "overdue" and days_late <= 0:
            continue
        client = clients.get(str(inv.get("client_id") or ""), {})
        prop = props.get(str(inv.get("property_id") or ""), {})
        row = {
            "invoice_id": inv.get("id"),
            "invoice_no": inv.get("invoice_no"),
            "client_id": inv.get("client_id"),
            "client_name": client.get("name") or inv.get("client_id") or "—",
            "client_phone": client.get("phone") or "",
            "client_email": client.get("email") or "",
            "property_id": inv.get("property_id"),
            "property_name": prop.get("name") or "",
            "contract_id": inv.get("contract_id"),
            "due_date": due_s,
            "amount": round(amount, 3),
            "paid_amount": round(paid, 3),
            "remaining": rem,
            "status": inv.get("status"),
            "days_late": days_late,
            "bucket": bkey,
            "priority": "critical" if days_late > 90 else ("high" if days_late > 60 else ("medium" if days_late > 30 else ("low" if days_late > 0 else "current"))),
        }
        items.append(row)
        buckets[bkey]["amount"] = round(float(buckets[bkey]["amount"]) + rem, 3)
        buckets[bkey]["count"] = int(buckets[bkey]["count"]) + 1
        total_open += rem
        if days_late > 0:
            total_overdue += rem

    items.sort(key=lambda x: (-int(x.get("days_late") or 0), -float(x.get("remaining") or 0)))
    collection_rate = 0.0
    billed = sum(float(i.get("amount") or 0) for i in invoices) or 0.0
    paid_sum = sum(float(i.get("paid_amount") or 0) for i in invoices) or 0.0
    if billed > 0:
        collection_rate = round((paid_sum / billed) * 100, 1)

    return {
        "as_of": today_s,
        "buckets": buckets,
        "bucket_order": ["current", "1-30", "31-60", "61-90", "90+"],
        "total_open": round(total_open, 3),
        "total_overdue": round(total_overdue, 3),
        "collection_rate": collection_rate,
        "items": items,
        "item_count": len(items),
        "overdue_count": sum(1 for x in items if int(x.get("days_late") or 0) > 0),
    }


def send_alert_email(to: str, subject: str, body: str) -> Tuple[bool, str]:
    host = os.environ.get("LQ_SMTP_HOST", "").strip()
    if not host:
        return False, "SMTP not configured (set LQ_SMTP_HOST)"
    port = int(os.environ.get("LQ_SMTP_PORT", "587") or "587")
    user = os.environ.get("LQ_SMTP_USER", "").strip()
    password = os.environ.get("LQ_SMTP_PASS", "").strip()
    from_addr = os.environ.get("LQ_SMTP_FROM", SUPPORT_EMAIL).strip()
    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if os.environ.get("LQ_SMTP_TLS", "1") == "1":
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to], msg.as_string())
        return True, "sent"
    except Exception as exc:
        return False, str(exc)


def build_bank_reconciliation_html(
    rec: Dict[str, Any],
    preview: Dict[str, Any],
    owner: str,
) -> str:
    company_ar = COMPANY_NAME_AR
    company_en = "QUALITY OF LAUNCH PROJECTS LLC"
    title = "تقرير تسوية بنكية · Bank Reconciliation"

    def table(headers: List[str], rows: List[List[str]]) -> str:
        head = "".join(f"<th>{html_escape(h)}</th>" for h in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{html_escape(c)}</td>" for c in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body or '<tr><td colspan=\"'+str(len(headers))+'\">لا توجد بيانات</td></tr>'}</tbody></table>"

    diff = float(rec.get("difference") or 0)
    bank_bal = float(rec.get("bank_balance") or 0)
    book_bal = float(rec.get("book_balance") or preview.get("book_balance") or 0)
    if not bank_bal and diff:
        bank_bal = book_bal - diff

    summary = f"""
    <div class="kpis">
      <div class="kpi"><span>رصيد الدفاتر</span><b>{fmt_omr(book_bal)}</b></div>
      <div class="kpi"><span>رصيد كشف البنك</span><b>{fmt_omr(bank_bal)}</b></div>
      <div class="kpi"><span>الفرق</span><b>{fmt_omr(diff)}</b></div>
      <div class="kpi"><span>مطابقة</span><b>{preview.get('matched_count',0)}</b></div>
      <div class="kpi"><span>غير مطابقة</span><b>{preview.get('unmatched_count',0)}</b></div>
      <div class="kpi"><span>الحالة</span><b>{html_escape(rec.get('status',''))}</b></div>
    </div>
    <p><strong>البنك:</strong> {html_escape(rec.get('bank_name',''))} · <strong>الفترة:</strong> {html_escape(rec.get('period_name',''))}</p>
    """

    unmatched_rows = [
        [r.get("bank_date", ""), r.get("reference", ""), r.get("type", ""), fmt_omr(float(r.get("amount", 0)))]
        for r in preview.get("unmatched_transactions", [])
    ]
    matched_rows = [
        [r.get("bank_date", ""), r.get("invoice_no", ""), r.get("client_name", ""), fmt_omr(float(r.get("amount", 0)))]
        for r in preview.get("matched_transactions", [])
    ]
    body = summary
    body += "<h3>حركات غير مطابقة</h3>" + table(["تاريخ", "مرجع", "نوع", "مبلغ"], unmatched_rows)
    body += "<h3>حركات مطابقة</h3>" + table(["تاريخ", "فاتورة", "عميل", "مبلغ"], matched_rows)
    if rec.get("notes"):
        body += f"<p><strong>ملاحظات:</strong> {html_escape(rec.get('notes',''))}</p>"

    return f"""<!doctype html>
<html lang="ar" dir="ltr">
<head>
<meta charset="utf-8">
<title>{html_escape(title)}</title>
<style>
  @page{{size:A4;margin:14mm}}
  body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;margin:24px;color:#111;background:#fff;line-height:1.6}}
  .head{{border-bottom:4px solid #c9a227;padding-bottom:14px;margin-bottom:18px}}
  .head img{{width:72px;height:72px;object-fit:contain;float:right;margin-left:14px}}
  h1{{margin:0;color:#0b1220;font-size:22px}}
  h2{{color:#8f631b;font-size:16px}}
  .meta{{color:#555;margin:12px 0 20px}}
  .kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}}
  .kpi{{border:1px solid #e5d39a;border-radius:12px;padding:12px;background:#fffdf7}}
  .kpi b{{display:block;font-size:18px;color:#071426;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}}
  th,td{{border:1px solid #e5e7eb;padding:8px;text-align:right}}
  th{{background:#0b1220;color:#f5d76e}}
  .foot{{margin-top:24px;padding-top:12px;border-top:1px solid #ddd;font-size:12px;color:#666;text-align:center}}
  @media print{{button{{display:none}}}}
</style>
</head>
<body>
<div class="head">
  <img src="/assets/brand-logo-gold.png?v=12" alt="Logo">
  <h1>{html_escape(company_ar)}</h1>
  <h2>{html_escape(company_en)} · {html_escape(title)}</h2>
</div>
<p class="meta">أُعد بواسطة: <strong>{html_escape(owner)}</strong> · {html_escape(rec.get('reconciled_at') or now_iso())}</p>
{body}
<p style="margin-top:28px"><button onclick="window.print()">طباعة / حفظ PDF</button></p>
<div class="foot">C.R. 1466316 · info@alamal.info · +968 71924089</div>
<script>window.onload=function(){{setTimeout(function(){{window.print()}},500)}}</script>
</body>
</html>"""


def build_hospitality_report_html(summary: Dict[str, Any], owner: str) -> str:
    k = summary.get("kpis") or {}
    period = summary.get("period") or {}
    rows = summary.get("room_type_breakdown") or []
    rows_html = "".join(
        f"<tr><td>{html_escape(str(r.get('room_type') or 'Standard'))}</td><td>{int(r.get('bookings') or 0)}</td><td>{fmt_omr(float(r.get('revenue') or 0))}</td></tr>"
        for r in rows
    ) or "<tr><td colspan='3'>لا توجد بيانات</td></tr>"
    return f"""<!doctype html>
<html lang="ar" dir="ltr">
<head>
<meta charset="utf-8">
<title>تقرير أداء الضيافة</title>
<style>
  @page{{size:A4;margin:14mm}}
  body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;margin:24px;color:#111;background:#fff;line-height:1.6}}
  .head{{border-bottom:4px solid #c9a227;padding-bottom:14px;margin-bottom:18px}}
  h1{{margin:0;color:#0b1220;font-size:22px}}
  h2{{color:#8f631b;font-size:15px}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0 18px}}
  .kpi{{border:1px solid #e5d39a;border-radius:12px;padding:10px;background:#fffdf7}}
  .kpi b{{display:block;font-size:17px;color:#071426;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;margin-top:12px}}
  th,td{{border:1px solid #e5e7eb;padding:8px;text-align:right}}
  th{{background:#0b1220;color:#f5d76e}}
</style>
</head>
<body>
<div class="head">
  <h1>تقرير أداء الضيافة</h1>
  <h2>{COMPANY_NAME} · {html_escape(str(period.get('from') or ''))} → {html_escape(str(period.get('to') or ''))}</h2>
</div>
<p>أُعد بواسطة: <strong>{html_escape(owner)}</strong> · {html_escape(now_iso())}</p>
<div class="kpis">
  <div class="kpi"><span>الغرف</span><b>{int(k.get('rooms') or 0)}</b></div>
  <div class="kpi"><span>الإشغال</span><b>{float(k.get('occupancy_pct') or 0):.2f}%</b></div>
  <div class="kpi"><span>ADR</span><b>{fmt_omr(float(k.get('adr') or 0))}</b></div>
  <div class="kpi"><span>RevPAR</span><b>{fmt_omr(float(k.get('revpar') or 0))}</b></div>
  <div class="kpi"><span>الإيراد الكلي</span><b>{fmt_omr(float(k.get('total_revenue') or 0))}</b></div>
  <div class="kpi"><span>المدفوع</span><b>{fmt_omr(float(k.get('paid_revenue') or 0))}</b></div>
  <div class="kpi"><span>المتبقي</span><b>{fmt_omr(float(k.get('balance_revenue') or 0))}</b></div>
  <div class="kpi"><span>الليالي المباعة</span><b>{int(k.get('sold_nights') or 0)}</b></div>
</div>
<h3>توزيع الإيراد حسب نوع الغرفة</h3>
<table><thead><tr><th>نوع الغرفة</th><th>عدد الحجوزات</th><th>الإيراد</th></tr></thead><tbody>{rows_html}</tbody></table>
<p style="margin-top:26px"><button onclick="window.print()">طباعة / حفظ PDF</button></p>
</body>
</html>"""


def build_hospitality_folio_html(folio: Dict[str, Any], owner: str) -> str:
    return f"""<!doctype html>
<html lang="ar" dir="ltr">
<head>
<meta charset="utf-8">
<title>فوليو ضيافة {html_escape(str(folio.get('folio_no') or folio.get('id') or ''))}</title>
<style>
  @page{{size:A4;margin:14mm}}
  body{{font-family:Tajawal,Segoe UI,Arial,sans-serif;margin:24px;color:#111;background:#fff}}
  .head{{border-bottom:4px solid #c9a227;padding-bottom:12px;margin-bottom:16px}}
  .box{{border:1px solid #e5d39a;border-radius:10px;padding:12px;margin:8px 0;background:#fffdf7}}
  .line{{display:flex;justify-content:space-between;gap:8px;padding:4px 0}}
  .tot{{font-size:18px;font-weight:700}}
</style>
</head>
<body>
<div class="head"><h1>فوليو/فاتورة ضيافة</h1><h2>{html_escape(str(folio.get('folio_no') or folio.get('id') or ''))}</h2></div>
<p>أُعد بواسطة: <strong>{html_escape(owner)}</strong> · {html_escape(str(folio.get('issue_date') or now_iso()))}</p>
<div class="box">
  <div class="line"><span>النزيل</span><b>{html_escape(str(folio.get('guest_name') or ''))}</b></div>
  <div class="line"><span>الهاتف</span><b>{html_escape(str(folio.get('guest_phone') or ''))}</b></div>
  <div class="line"><span>العقار</span><b>{html_escape(str(folio.get('property_name') or ''))}</b></div>
  <div class="line"><span>الغرفة</span><b>{html_escape(str(folio.get('room_code') or ''))} · {html_escape(str(folio.get('room_type') or ''))}</b></div>
  <div class="line"><span>الدخول</span><b>{html_escape(str(folio.get('checkin_date') or ''))}</b></div>
  <div class="line"><span>الخروج</span><b>{html_escape(str(folio.get('checkout_date') or ''))}</b></div>
  <div class="line"><span>الليالي</span><b>{int(folio.get('nights') or 0)}</b></div>
</div>
<div class="box">
  <div class="line tot"><span>الإجمالي</span><b>{fmt_omr(float(folio.get('total_amount') or 0))}</b></div>
  <div class="line"><span>المدفوع</span><b>{fmt_omr(float(folio.get('paid_amount') or 0))}</b></div>
  <div class="line"><span>المتبقي</span><b>{fmt_omr(float(folio.get('balance_amount') or 0))}</b></div>
  <div class="line"><span>الحالة</span><b>{html_escape(str(folio.get('status') or 'open'))}</b></div>
</div>
<p style="margin-top:22px"><button onclick="window.print()">طباعة / حفظ PDF</button></p>
</body>
</html>"""


def html_escape(s: str) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def exists(db: sqlite3.Connection, table: str, row_id: str) -> bool:
    return db.execute(f"SELECT 1 FROM {table} WHERE id=?", (row_id,)).fetchone() is not None


def protected_delete_reason(db: sqlite3.Connection, table: str, row_id: str) -> str:
    if table == "invoices":
        return "الفواتير لا تُحذف — استخدم الإلغاء (Void) أو إعادة الإصدار"
    checks = {
        "properties": [("contracts", "property_id", "Property has contracts"), ("invoices", "property_id", "Property has invoices"), ("accounts", "property_id", "Property has accounts")],
        "clients": [("contracts", "client_id", "Client has contracts"), ("invoices", "client_id", "Client has invoices"), ("accounts", "client_id", "Client has accounts")],
        "contracts": [("invoices", "contract_id", "Contract has invoices")],
        "invoices": [("payments", "invoice_id", "Invoice has payments"), ("accounts", "invoice_id", "Invoice has accounts")],
    }
    for child, col, msg in checks.get(table, []):
        if db.execute(f"SELECT 1 FROM {child} WHERE {col}=? LIMIT 1", (row_id,)).fetchone():
            return msg
    return ""


def build_dashboard(db: sqlite3.Connection) -> Dict[str, Any]:
    prop_total = db.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    rented = db.execute(
        "SELECT COUNT(*) FROM properties WHERE status='مستأجرة' OR lower(status) LIKE '%rented%' OR lower(status) LIKE '%leased%'"
    ).fetchone()[0]
    vacant = db.execute(
        "SELECT COUNT(*) FROM properties WHERE status='شاغرة' OR lower(status) LIKE '%vacant%'"
    ).fetchone()[0]
    reserved = db.execute(
        "SELECT COUNT(*) FROM properties WHERE status='محجوزة' OR lower(status) LIKE '%pending%' OR lower(status) LIKE '%reserved%'"
    ).fetchone()[0]
    maintenance_props = db.execute(
        "SELECT COUNT(*) FROM properties WHERE status='صيانة' OR lower(status) LIKE '%maintenance%'"
    ).fetchone()[0]
    maintenance_count = db.execute("SELECT COUNT(*) FROM maintenance WHERE lower(status) NOT IN ('closed','done','completed')").fetchone()[0]
    invoices = rows_to_dicts(db.execute("SELECT * FROM invoices").fetchall())
    accounts = rows_to_dicts(db.execute("SELECT * FROM accounts").fetchall())
    income = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "income")
    expense = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "expense")
    billed = sum(float(i["amount"] or 0) for i in invoices)
    paid = sum(float(i["paid_amount"] or 0) for i in invoices)
    overdue = sum(
        max(0, float(i["amount"] or 0) - float(i["paid_amount"] or 0))
        for i in invoices
        if str(i.get("status") or "") != "Paid"
        and not int(i.get("is_void") or 0)
        and str(i.get("due_date") or "") < today()
    )
    occupancy = round((rented / prop_total * 100), 1) if prop_total else 0
    months = []
    for m in range(5, -1, -1):
        d = date.today().replace(day=1) - timedelta(days=31*m)
        key = d.strftime("%Y-%m")
        month_income = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "income" and str(a["entry_date"]).startswith(key))
        month_expense = sum(float(a["amount"] or 0) for a in accounts if a["type"] == "expense" and str(a["entry_date"]).startswith(key))
        months.append({"month": key, "income": month_income, "expense": month_expense})
    health = 100
    if overdue > 0: health -= 15
    if maintenance_count > 0: health -= min(20, maintenance_count * 5)
    if occupancy < 70: health -= 15
    health = max(0, min(100, health))
    renewal = contract_renewal_stats(db)
    expiring = renewal["expiring"]
    expired = renewal["expired"]
    if expiring > 0:
        health -= min(20, expiring * 4)
    if expired > 0:
        health -= min(25, expired * 6)
    health = max(0, min(100, health))
    decisions = []
    if expired > 0:
        decisions.append({"level":"High","text":f"{expired} عقد منتهٍ يحتاج تجديد أو إغلاق فوري"})
    pending_appr = pending_approvals_count(db)
    if pending_appr > 0:
        decisions.append({"level":"High","text":f"{pending_appr} طلب اعتماد بانتظار المدير — راجع مركز الاعتمادات"})
    if expiring > 0:
        decisions.append({"level":"High","text":f"{expiring} عقد يحتاج قرار تجديد قبل انتهاء المدة"})
    if overdue > 0:
        decisions.append({"level":"High","text":"متابعة الفواتير المتأخرة قبل إقفال الشهر"})
    for alert in build_bank_variance_alerts(db)[:3]:
        decisions.append({"level": alert.get("level", "Medium"), "text": alert.get("text", "")})
    if vacant > 0:
        decisions.append({"level":"Medium","text":"تسويق العقارات الشاغرة لرفع الإشغال"})
    if maintenance_count > 0:
        decisions.append({"level":"Medium","text":"إغلاق طلبات الصيانة المفتوحة لحماية جودة الخدمة"})
    if not decisions:
        decisions.append({"level":"Good","text":"التشغيل مستقر اليوم"})
    purchases_due = db.execute("SELECT COALESCE(SUM(amount-paid_amount),0) FROM purchase_invoices WHERE status != 'Paid'").fetchone()[0]
    payroll_total = db.execute("SELECT COALESCE(SUM(net_salary),0) FROM salaries").fetchone()[0]
    inventory_value = db.execute("SELECT COALESCE(SUM(quantity*unit_cost),0) FROM inventory_items").fetchone()[0]
    bank_balance = db.execute("SELECT COALESCE(SUM(CASE WHEN type IN ('deposit','in','income') THEN amount ELSE -amount END),0) FROM bank_transactions").fetchone()[0]
    alert_summary = build_alert_center(db).get("summary") or {}
    return {
        "kpis": {
            "properties": prop_total, "rented": rented, "vacant": vacant, "reserved": reserved,
            "maintenance_properties": maintenance_props, "maintenance": maintenance_count,
            "property_status": {
                "rented": rented, "vacant": vacant, "reserved": reserved, "maintenance": maintenance_props,
            },
            "income": income, "expense": expense, "net": income - expense, "billed": billed, "paid": paid,
            "overdue": overdue, "occupancy": occupancy, "health": health,
            "purchases_due": float(purchases_due or 0), "payroll": float(payroll_total or 0), "inventory_value": float(inventory_value or 0), "bank_balance": float(bank_balance or 0),
            "expiring": expiring, "expired": expired,
            "pending_approvals": pending_appr,
            "approval_threshold": APPROVAL_THRESHOLD,
            "alert_center_total": int(alert_summary.get("total") or 0),
            "alert_center_high": int(alert_summary.get("high") or 0) + int(alert_summary.get("critical") or 0),
        },
        "series": months,
        "decisions": decisions,
        "renewal": renewal,
    }


def main() -> None:
    ensure_upload_dirs()
    init_db()
    start_auto_backup_scheduler()
    with connect() as db:
        schema_overview = {
            "properties_cols": len(db.execute("PRAGMA table_info(properties)").fetchall()),
            "contracts_cols": len(db.execute("PRAGMA table_info(contracts)").fetchall()),
            "invoices_cols": len(db.execute("PRAGMA table_info(invoices)").fetchall()),
        }
    print(f"Schema overview: {schema_overview}")
    print(f"{COMPANY_NAME} {APP_VERSION} [{APP_EDITION_LABEL}] running on http://{HOST}:{PORT}")
    print(f"Database: {DB_PATH}")
    print(f"Data dir: {DATA_DIR} | Backup dir: {BACKUP_DIR}")
    print("Health check: /api/health")
    ThreadingHTTPServer((HOST, PORT), JawdahHandler).serve_forever()


if __name__ == "__main__":
    main()
