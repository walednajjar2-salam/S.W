import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

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


def _public_base() -> str:
    return settings.public_base_url.rstrip("/")


def oauth_configured(platform: str) -> bool:
    platform = platform.lower()
    if platform == "instagram":
        return bool(settings.instagram_client_id and settings.instagram_client_secret)
    if platform == "tiktok":
        return bool(settings.tiktok_client_key and settings.tiktok_client_secret)
    return False


def instagram_redirect_uri() -> str:
    return f"{_public_base()}/api/social/oauth/instagram/callback"


def tiktok_redirect_uri() -> str:
    return f"{_public_base()}/api/social/oauth/tiktok/callback"


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
    state: str, platform: str, user_id: int, code_verifier: str = ""
) -> None:
    cutoff = (_now() - OAUTH_STATE_TTL).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
        conn.execute(
            """
            INSERT INTO oauth_states (state, platform, user_id, code_verifier, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (state, platform, user_id, code_verifier, _now_iso()),
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
    }


def start_oauth(platform: str, user_id: int) -> str:
    platform = platform.lower()
    state = secrets.token_urlsafe(24)

    if platform == "instagram":
        if not oauth_configured("instagram"):
            raise ValueError(
                "Instagram OAuth غير مُعد — أضف SMM_INSTAGRAM_CLIENT_ID و SMM_INSTAGRAM_CLIENT_SECRET"
            )
        _save_oauth_state(state, platform, user_id)
        params = urlencode(
            {
                "client_id": settings.instagram_client_id,
                "redirect_uri": instagram_redirect_uri(),
                "response_type": "code",
                "scope": "instagram_business_basic",
                "state": state,
            }
        )
        return f"{INSTAGRAM_AUTHORIZE_URL}?{params}"

    if platform == "tiktok":
        if not oauth_configured("tiktok"):
            raise ValueError(
                "TikTok OAuth غير مُعد — أضف SMM_TIKTOK_CLIENT_KEY و SMM_TIKTOK_CLIENT_SECRET"
            )
        verifier, challenge = _pkce_pair()
        _save_oauth_state(state, platform, user_id, verifier)
        params = urlencode(
            {
                "client_key": settings.tiktok_client_key,
                "redirect_uri": tiktok_redirect_uri(),
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


async def exchange_instagram_code(code: str) -> dict[str, Any]:
    code = sanitize_oauth_code(code)
    if not code:
        raise ValueError("رمز إنستجرام فارغ")
    redirect_uri = instagram_redirect_uri()
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_res = await client.post(
            INSTAGRAM_TOKEN_URL,
            data={
                "client_id": settings.instagram_client_id,
                "client_secret": settings.instagram_client_secret,
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
                    "client_secret": settings.instagram_client_secret,
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


async def exchange_tiktok_code(code: str, code_verifier: str = "") -> dict[str, Any]:
    code = sanitize_oauth_code(code)
    if not code:
        raise ValueError("رمز تيك توك فارغ")
    payload = {
        "client_key": settings.tiktok_client_key,
        "client_secret": settings.tiktok_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": tiktok_redirect_uri(),
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
