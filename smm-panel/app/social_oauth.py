import base64
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from app.config import settings
from app.database import get_conn
from app.platforms import instagram_profile_url, tiktok_profile_url

OAUTH_STATE_TTL = timedelta(minutes=15)
INSTAGRAM_AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH = "https://graph.instagram.com"
TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_URL = "https://open.tiktokapis.com/v2/user/info/"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


SETTING_KEYS = (
    "public_base_url",
    "instagram_client_id",
    "instagram_client_secret",
    "tiktok_client_key",
    "tiktok_client_secret",
)


def _is_public_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return bool(host) and host not in {"localhost", "127.0.0.1", "0.0.0.0"}


def get_oauth_secrets() -> dict[str, str]:
    stored: dict[str, str] = {}
    with get_conn() as conn:
        try:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        except sqlite3.OperationalError:
            rows = []
        stored = {row["key"]: (row["value"] or "").strip() for row in rows}

    def pick(key: str, env_val: str) -> str:
        if stored.get(key):
            return stored[key]
        return (env_val or "").strip()

    return {
        "public_base_url": pick("public_base_url", settings.public_base_url),
        "instagram_client_id": pick("instagram_client_id", settings.instagram_client_id),
        "instagram_client_secret": pick(
            "instagram_client_secret", settings.instagram_client_secret
        ),
        "tiktok_client_key": pick("tiktok_client_key", settings.tiktok_client_key),
        "tiktok_client_secret": pick(
            "tiktok_client_secret", settings.tiktok_client_secret
        ),
    }


def save_oauth_setting(key: str, value: str) -> None:
    if key not in SETTING_KEYS:
        raise ValueError(f"إعداد غير مدعوم: {key}")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, (value or "").strip()),
        )


def resolve_public_base(request_base: str | None = None) -> str:
    configured = (get_oauth_secrets().get("public_base_url") or "").rstrip("/")
    if configured and _is_public_url(configured):
        return configured
    request_base = (request_base or "").rstrip("/")
    if request_base:
        return request_base
    return configured or settings.public_base_url.rstrip("/")


def public_base_from_headers(headers: dict[str, str], fallback_scheme: str = "https") -> str:
    proto = (
        (headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto") or fallback_scheme)
        .split(",")[0]
        .strip()
        or fallback_scheme
    )
    host = (
        (headers.get("x-forwarded-host") or headers.get("X-Forwarded-Host") or headers.get("host") or headers.get("Host") or "")
        .split(",")[0]
        .strip()
    )
    request_base = f"{proto}://{host}" if host else ""
    return resolve_public_base(request_base)


def oauth_configured(platform: str) -> bool:
    creds = get_oauth_secrets()
    platform = platform.lower()
    if platform == "instagram":
        return bool(creds["instagram_client_id"] and creds["instagram_client_secret"])
    if platform == "tiktok":
        return bool(creds["tiktok_client_key"] and creds["tiktok_client_secret"])
    return False


def instagram_redirect_uri(public_base: str | None = None) -> str:
    return f"{resolve_public_base(public_base)}/api/social/oauth/instagram/callback"


def tiktok_redirect_uri(public_base: str | None = None) -> str:
    return f"{resolve_public_base(public_base)}/api/social/oauth/tiktok/callback"


def oauth_status_payload(public_base: str | None = None, include_config: bool = False) -> dict[str, Any]:
    base = resolve_public_base(public_base)
    creds = get_oauth_secrets()
    payload: dict[str, Any] = {
        "instagram": bool(creds["instagram_client_id"] and creds["instagram_client_secret"]),
        "tiktok": bool(creds["tiktok_client_key"] and creds["tiktok_client_secret"]),
        "public_base_url": base,
        "redirect_uris": {
            "instagram": f"{base}/api/social/oauth/instagram/callback",
            "tiktok": f"{base}/api/social/oauth/tiktok/callback",
        },
    }
    if include_config:
        payload["config"] = {
            "public_base_url": creds["public_base_url"],
            "instagram_client_id": creds["instagram_client_id"],
            "instagram_client_secret_set": bool(creds["instagram_client_secret"]),
            "tiktok_client_key": creds["tiktok_client_key"],
            "tiktok_client_secret_set": bool(creds["tiktok_client_secret"]),
        }
    return payload


def parse_instagram_token_payload(body: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError("استجابة إنستجرام غير صالحة")
    data = body.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        row = data[0]
        if row.get("access_token"):
            return row
    if isinstance(data, dict) and data.get("access_token"):
        return data
    if body.get("access_token"):
        return body
    raise ValueError(_api_error_message(body, "إنستجرام لم يُرجع access_token"))


def parse_tiktok_token_payload(body: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError("استجابة تيك توك غير صالحة")
    err = body.get("error")
    if isinstance(err, dict) and err.get("code") not in (None, "", "ok", "0"):
        raise ValueError(err.get("message") or err.get("code") or "فشل توكن تيك توك")
    if isinstance(err, str) and err and err not in ("ok", "success"):
        raise ValueError(body.get("error_description") or err)
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not data.get("access_token"):
        raise ValueError(_api_error_message(body, "تيك توك لم يُرجع access_token"))
    return data


def instagram_profile_from_json(profile: dict[str, Any], access_token: str) -> dict[str, Any]:
    username = (profile.get("username") or "").strip().lstrip("@")
    user_id = str(profile.get("user_id") or profile.get("id") or "")
    if not username and not user_id:
        raise ValueError("إنستجرام لم يُرجع بيانات الحساب")
    return {
        "platform": "instagram",
        "platform_user_id": user_id,
        "username": username,
        "profile_url": instagram_profile_url(username) if username else "",
        "access_token": access_token,
        "verified": True,
        "meta": {
            "name": profile.get("name"),
            "account_type": profile.get("account_type"),
            "media_count": profile.get("media_count"),
            "profile_picture_url": profile.get("profile_picture_url"),
            "verified_via": "oauth",
        },
    }


def tiktok_profile_from_json(user: dict[str, Any], access_token: str) -> dict[str, Any]:
    username = (user.get("username") or "").strip().lstrip("@")
    display_name = (user.get("display_name") or "").strip()
    handle = username or display_name.replace(" ", "")
    profile_url = user.get("profile_deep_link") or (
        tiktok_profile_url(username) if username else ""
    )
    return {
        "platform": "tiktok",
        "platform_user_id": str(user.get("open_id") or user.get("union_id") or ""),
        "username": username or display_name or str(user.get("open_id") or ""),
        "profile_url": profile_url or (tiktok_profile_url(handle) if handle else ""),
        "access_token": access_token,
        "verified": True,
        "meta": {
            "display_name": display_name,
            "avatar_url": user.get("avatar_url"),
            "is_verified": user.get("is_verified"),
            "verified_via": "oauth",
        },
    }


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _api_error_message(body: Any, fallback: str) -> str:
    if not isinstance(body, dict):
        return fallback
    err = body.get("error")
    if isinstance(err, dict):
        return str(
            err.get("message")
            or err.get("error_user_msg")
            or err.get("error_user_title")
            or err.get("code")
            or fallback
        )
    if isinstance(err, str) and err not in ("ok", "success"):
        return str(body.get("error_description") or err)
    return str(body.get("error_description") or body.get("error_message") or fallback)


def _save_oauth_state(
    state: str,
    platform: str,
    user_id: int,
    code_verifier: str = "",
    redirect_uri: str = "",
) -> None:
    cutoff = (_now() - OAUTH_STATE_TTL).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
        conn.execute(
            """
            INSERT INTO oauth_states
            (state, platform, user_id, code_verifier, redirect_uri, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (state, platform, user_id, code_verifier, redirect_uri, _now_iso()),
        )


def pop_oauth_state(state: str) -> dict[str, Any] | None:
    if not state:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM oauth_states WHERE state = ?", (state,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    created = datetime.fromisoformat(row["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if _now() - created > OAUTH_STATE_TTL:
        return None
    return {
        "platform": row["platform"],
        "user_id": row["user_id"],
        "code_verifier": row["code_verifier"] or "",
        "redirect_uri": row["redirect_uri"] if "redirect_uri" in row.keys() else "",
    }


def start_oauth(platform: str, user_id: int, public_base: str | None = None) -> str:
    platform = platform.lower()
    state = secrets.token_urlsafe(24)
    creds = get_oauth_secrets()
    base = resolve_public_base(public_base)

    if platform == "instagram":
        if not (creds["instagram_client_id"] and creds["instagram_client_secret"]):
            raise ValueError(
                "Instagram OAuth غير مُعد — احفظ App ID و Secret من لوحة الإدارة"
            )
        redirect_uri = f"{base}/api/social/oauth/instagram/callback"
        _save_oauth_state(state, platform, user_id, redirect_uri=redirect_uri)
        params = urlencode(
            {
                "client_id": creds["instagram_client_id"],
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "instagram_business_basic",
                "state": state,
                "enable_fb_login": "0",
                "force_authentication": "1",
            }
        )
        return f"{INSTAGRAM_AUTHORIZE_URL}?{params}"

    if platform == "tiktok":
        if not (creds["tiktok_client_key"] and creds["tiktok_client_secret"]):
            raise ValueError(
                "TikTok OAuth غير مُعد — احفظ Client Key و Secret من لوحة الإدارة"
            )
        redirect_uri = f"{base}/api/social/oauth/tiktok/callback"
        verifier, challenge = _pkce_pair()
        _save_oauth_state(state, platform, user_id, verifier, redirect_uri)
        params = urlencode(
            {
                "client_key": creds["tiktok_client_key"],
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "user.info.basic,user.info.profile",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            safe=",",
        )
        return f"{TIKTOK_AUTHORIZE_URL}?{params}"

    raise ValueError(f"منصة غير مدعومة: {platform}")


def sanitize_oauth_code(code: str) -> str:
    return (code or "").strip().split("#", 1)[0].rstrip("_")


async def _json_or_error(res: httpx.Response, fallback: str) -> dict[str, Any]:
    try:
        body = res.json()
    except ValueError:
        body = {"error_message": (res.text or "")[:200]}
    if res.is_error:
        raise ValueError(_api_error_message(body, f"{fallback} (HTTP {res.status_code})"))
    if not isinstance(body, dict):
        raise ValueError(fallback)
    return body


async def exchange_instagram_code(code: str, redirect_uri: str | None = None) -> dict[str, Any]:
    code = sanitize_oauth_code(code)
    if not code:
        raise ValueError("رمز إنستجرام فارغ")
    creds = get_oauth_secrets()
    redirect_uri = (redirect_uri or instagram_redirect_uri()).rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_res = await client.post(
            INSTAGRAM_TOKEN_URL,
            data={
                "client_id": creds["instagram_client_id"],
                "client_secret": creds["instagram_client_secret"],
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        token_body = await _json_or_error(token_res, "فشل تبادل رمز إنستجرام")
        token_data = parse_instagram_token_payload(token_body)
        short_token = token_data["access_token"]

        access_token = short_token
        try:
            long_res = await client.get(
                f"{INSTAGRAM_GRAPH}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": creds["instagram_client_secret"],
                    "access_token": short_token,
                },
            )
            long_body = await _json_or_error(long_res, "فشل توكن إنستجرام الطويل")
            if long_body.get("access_token"):
                access_token = long_body["access_token"]
        except ValueError:
            access_token = short_token

        profile = {}
        last_error = None
        for fields in (
            "user_id,username,name,account_type,profile_picture_url",
            "id,username,account_type,media_count",
        ):
            try:
                profile_res = await client.get(
                    f"{INSTAGRAM_GRAPH}/me",
                    params={"fields": fields, "access_token": access_token},
                )
                profile = await _json_or_error(profile_res, "فشل قراءة حساب إنستجرام")
                if profile.get("username") or profile.get("id") or profile.get("user_id"):
                    break
            except ValueError as exc:
                last_error = exc
                profile = {}
        if not profile:
            raise last_error or ValueError("فشل قراءة حساب إنستجرام")

    return instagram_profile_from_json(profile, access_token)


async def exchange_tiktok_code(
    code: str, code_verifier: str = "", redirect_uri: str | None = None
) -> dict[str, Any]:
    code = sanitize_oauth_code(code)
    if not code:
        raise ValueError("رمز تيك توك فارغ")
    creds = get_oauth_secrets()
    payload = {
        "client_key": creds["tiktok_client_key"],
        "client_secret": creds["tiktok_client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": (redirect_uri or tiktok_redirect_uri()).rstrip("/"),
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_res = await client.post(
            TIKTOK_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
        )
        token_body = await _json_or_error(token_res, "فشل تبادل رمز تيك توك")
        token_data = parse_tiktok_token_payload(token_body)
        access_token = token_data["access_token"]

        user: dict[str, Any] = {}
        last_error = None
        for fields in (
            "open_id,union_id,avatar_url,display_name,username,profile_deep_link,is_verified",
            "open_id,union_id,avatar_url,display_name",
        ):
            try:
                profile_res = await client.get(
                    TIKTOK_USER_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"fields": fields},
                )
                profile_body = await _json_or_error(profile_res, "فشل قراءة حساب تيك توك")
                err = profile_body.get("error")
                if isinstance(err, dict) and err.get("code") not in (None, "", "ok", "0"):
                    raise ValueError(err.get("message") or err.get("code"))
                user = profile_body.get("data", {}).get("user") or {}
                if user:
                    break
            except ValueError as exc:
                last_error = exc
                user = {}
        if not user:
            open_id = token_data.get("open_id")
            if open_id:
                user = {"open_id": open_id}
            else:
                raise last_error or ValueError("فشل قراءة حساب تيك توك")

    return tiktok_profile_from_json(user, access_token)
