import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

# In-memory OAuth state (single Railway instance + volume = OK for demo)
_oauth_states: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_base() -> str:
    return settings.public_base_url.rstrip("/")


def oauth_configured(platform: str) -> bool:
    platform = platform.lower()
    if platform == "instagram":
        return bool(settings.instagram_client_id and settings.instagram_client_secret)
    if platform == "tiktok":
        return bool(settings.tiktok_client_key and settings.tiktok_client_secret)
    return False


def start_oauth(platform: str, user_id: int) -> str:
    platform = platform.lower()
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {"platform": platform, "user_id": user_id}

    if platform == "instagram":
        if not oauth_configured("instagram"):
            raise ValueError("Instagram OAuth غير مُعد — أضف SMM_INSTAGRAM_CLIENT_ID و SMM_INSTAGRAM_CLIENT_SECRET")
        redirect_uri = f"{_public_base()}/api/social/oauth/instagram/callback"
        params = urlencode(
            {
                "client_id": settings.instagram_client_id,
                "redirect_uri": redirect_uri,
                "scope": "user_profile,user_media",
                "response_type": "code",
                "state": state,
            }
        )
        return f"https://api.instagram.com/oauth/authorize?{params}"

    if platform == "tiktok":
        if not oauth_configured("tiktok"):
            raise ValueError("TikTok OAuth غير مُعد — أضف SMM_TIKTOK_CLIENT_KEY و SMM_TIKTOK_CLIENT_SECRET")
        redirect_uri = f"{_public_base()}/api/social/oauth/tiktok/callback"
        params = urlencode(
            {
                "client_key": settings.tiktok_client_key,
                "redirect_uri": redirect_uri,
                "scope": "user.info.basic",
                "response_type": "code",
                "state": state,
            }
        )
        return f"https://www.tiktok.com/v2/auth/authorize/?{params}"

    raise ValueError(f"منصة غير مدعومة: {platform}")


def pop_oauth_state(state: str) -> dict[str, Any] | None:
    return _oauth_states.pop(state, None)


async def exchange_instagram_code(code: str) -> dict[str, Any]:
    redirect_uri = f"{_public_base()}/api/social/oauth/instagram/callback"
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": settings.instagram_client_id,
                "client_secret": settings.instagram_client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        token_res.raise_for_status()
        token_data = token_res.json()

        long_res = await client.get(
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": settings.instagram_client_secret,
                "access_token": token_data["access_token"],
            },
        )
        long_res.raise_for_status()
        long_data = long_res.json()

        profile_res = await client.get(
            "https://graph.instagram.com/me",
            params={
                "fields": "id,username,account_type,media_count",
                "access_token": long_data["access_token"],
            },
        )
        profile_res.raise_for_status()
        profile = profile_res.json()

    return {
        "platform_user_id": str(profile["id"]),
        "username": profile.get("username", ""),
        "profile_url": f"https://www.instagram.com/{profile.get('username', '')}/",
        "access_token": long_data["access_token"],
        "meta": {
            "account_type": profile.get("account_type"),
            "media_count": profile.get("media_count"),
            "verified_via": "oauth",
        },
    }


async def exchange_tiktok_code(code: str) -> dict[str, Any]:
    redirect_uri = f"{_public_base()}/api/social/oauth/tiktok/callback"
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        token_res.raise_for_status()
        token_body = token_res.json()
        token_data = token_body.get("data", token_body)

        access_token = token_data["access_token"]
        profile_res = await client.get(
            "https://open.tiktokapis.com/v2/user/info/",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "open_id,union_id,avatar_url,display_name,username"},
        )
        profile_res.raise_for_status()
        profile_body = profile_res.json()
        user = profile_body.get("data", {}).get("user", {})

    username = user.get("username") or user.get("display_name") or user.get("open_id", "")
    profile_url = f"https://www.tiktok.com/@{username}" if username else ""

    return {
        "platform_user_id": user.get("open_id") or user.get("union_id", ""),
        "username": username,
        "profile_url": profile_url,
        "access_token": access_token,
        "meta": {
            "display_name": user.get("display_name"),
            "avatar_url": user.get("avatar_url"),
            "verified_via": "oauth",
        },
    }
