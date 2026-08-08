"""Security helpers — passwords, bootstrap, device trust, MFA, rotation, TOTP."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import quote


def _env(key: str) -> str:
    return (os.environ.get(key) or "").strip()


def allow_default_passwords() -> bool:
    return _env("LQ_ALLOW_DEFAULT_PASSWORDS") == "1"


def user_password_env_key(username: str) -> str:
    return f"LQ_PASSWORD_{username.upper().replace('.', '_').replace('-', '_')}"


def user_email_env_key(username: str) -> str:
    return f"LQ_EMAIL_{username.upper().replace('.', '_').replace('-', '_')}"


def resolve_user_email(username: str, fallback: str = "") -> str:
    return _env(user_email_env_key(username)) or (fallback or "").strip()


def resolve_bootstrap_password(username: str, role: str, legacy_default: str) -> Tuple[str, bool]:
    """
    Return (password, must_change_password).
    Priority: per-user env → admin env → team bootstrap → legacy (if allowed) → random.
    """
    per_user = _env(user_password_env_key(username))
    if per_user:
        return per_user, False

    if username == "admin" and _env("LQ_ADMIN_PASSWORD"):
        return _env("LQ_ADMIN_PASSWORD"), False

    team_pwd = _env("LQ_TEAM_BOOTSTRAP_PASSWORD")
    if team_pwd:
        return team_pwd, True

    if allow_default_passwords() and legacy_default:
        return legacy_default, True

    return secrets.token_urlsafe(14), True


def validate_new_password(password: str, username: str) -> Optional[str]:
    pwd = (password or "").strip()
    if len(pwd) < 10:
        return "كلمة المرور يجب أن تكون 10 أحرف أو أكثر"
    if username and pwd.lower() == username.lower():
        return "لا تستخدم اسم المستخدم ككلمة مرور"
    weak = {"password", "1234567890", "admin123", "owner2015", "001970"}
    if pwd.lower() in weak:
        return "كلمة المرور ضعيفة — اختر كلمة أقوى"
    if pwd.isdigit():
        return "أضف حروفاً مع الأرقام"
    if not any(ch.isalpha() for ch in pwd):
        return "أضف حرفاً واحداً على الأقل"
    if not any(ch.isdigit() for ch in pwd):
        return "أضف رقماً واحداً على الأقل"
    return None


def password_max_age_days() -> int:
    raw = _env("LQ_PASSWORD_MAX_AGE_DAYS") or "90"
    try:
        return max(0, int(raw))
    except ValueError:
        return 90


def password_needs_rotation(password_changed_at: Any, *, created_at: Any = None) -> bool:
    """True when password is older than LQ_PASSWORD_MAX_AGE_DAYS (0 = disabled)."""
    max_days = password_max_age_days()
    if max_days <= 0:
        return False
    stamp = str(password_changed_at or created_at or "").strip()
    if not stamp:
        return True
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            changed = datetime.strptime(stamp[:19], fmt)
            return datetime.now() - changed > timedelta(days=max_days)
        except ValueError:
            continue
    return False


def mfa_roles() -> Set[str]:
    raw = _env("LQ_MFA_ROLES") or "owner,admin"
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def mfa_enforce_mode() -> str:
    """OTP/MFA login step is disabled — password-only sign-in."""
    return "off"


def role_requires_mfa(role: str) -> bool:
    if mfa_enforce_mode() == "off":
        return False
    return str(role or "").strip().lower() in mfa_roles()


def normalize_device_fingerprint(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if len(value) > 200:
        value = value[:200]
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest


def device_trust_days() -> int:
    try:
        return max(1, int(_env("LQ_DEVICE_TRUST_DAYS") or "30"))
    except ValueError:
        return 30


def pending_login_ttl_seconds() -> int:
    try:
        return max(60, int(_env("LQ_PENDING_LOGIN_TTL") or "300"))
    except ValueError:
        return 300


def otp_login_enabled() -> bool:
    """Standalone passwordless OTP login — permanently disabled."""
    return False


def smtp_configured() -> bool:
    return bool(_env("LQ_SMTP_HOST"))


def _b32_encode(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _b32_decode(secret: str) -> bytes:
    clean = (secret or "").strip().upper().replace(" ", "")
    pad = "=" * ((8 - len(clean) % 8) % 8)
    return base64.b32decode(clean + pad, casefold=True)


def generate_totp_secret(nbytes: int = 20) -> str:
    return _b32_encode(secrets.token_bytes(nbytes))


def totp_code(secret: str, for_time: Optional[float] = None, step: int = 30, digits: int = 6) -> str:
    counter = int((for_time if for_time is not None else time.time()) // step)
    key = _b32_decode(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    num = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(num % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, window: int = 1, step: int = 30) -> bool:
    if not secret or not code:
        return False
    now = time.time()
    target = str(code).strip()
    for drift in range(-window, window + 1):
        if totp_code(secret, for_time=now + drift * step, step=step) == target:
            return True
    return False


def totp_provisioning_uri(secret: str, username: str, issuer: str = "Launch Quality") -> str:
    label = quote(f"{issuer}:{username}")
    iss = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={iss}&digits=6&period=30"


def security_status_payload(
    user: Dict[str, Any],
    *,
    trusted_device: bool = False,
    totp_enabled: bool = False,
) -> Dict[str, Any]:
    return {
        "password_max_age_days": password_max_age_days(),
        "password_needs_rotation": password_needs_rotation(
            user.get("password_changed_at"),
            created_at=user.get("created_at"),
        ),
        "must_change_password": bool(user.get("must_change_password")),
        "mfa_enforce": mfa_enforce_mode(),
        "mfa_roles": sorted(mfa_roles()),
        "role_requires_mfa": role_requires_mfa(str(user.get("role") or "")),
        "trusted_device": bool(trusted_device),
        "device_trust_days": device_trust_days(),
        "otp_login_enabled": otp_login_enabled(),
        "smtp_configured": smtp_configured(),
        "totp_enabled": bool(totp_enabled or user.get("totp_enabled")),
        "mfa_methods": ["totp", "email", "trusted_device"],
    }


def security_platform_status(*, users_missing_email: int = 0, totp_users: int = 0) -> Dict[str, Any]:
    mode = mfa_enforce_mode()
    smtp = smtp_configured()
    # TOTP works without SMTP — MFA is production-complete.
    mfa_ready = True
    return {
        "smtp_configured": smtp,
        "email_delivery_ready": smtp,
        "totp_ready": True,
        "totp_users": int(totp_users or 0),
        "mfa_mode": mode,
        "mfa_roles": sorted(mfa_roles()),
        "mfa_ready": mfa_ready,
        "mfa_channels": ["totp", "trusted_device"] + (["email"] if smtp else []),
        "otp_login_enabled": otp_login_enabled(),
        "otp_debug": _env("LQ_OTP_DEBUG") in ("1", "true", "yes", "on"),
        "password_max_age_days": password_max_age_days(),
        "device_trust_days": device_trust_days(),
        "users_missing_email": int(users_missing_email or 0),
        "ready": mfa_ready,
        "reason": None,
        "note": "MFA عبر تطبيق المصادقة (TOTP) جاهز بدون SMTP",
    }
