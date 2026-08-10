import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx

INSTAGRAM_USER_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?",
    re.I,
)
INSTAGRAM_POST_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?",
    re.I,
)
TIKTOK_USER_RE = re.compile(
    r"(?:https?://)?(?:(?:www|vm)\.)?tiktok\.com/@([A-Za-z0-9._]+)/?",
    re.I,
)
TIKTOK_VIDEO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)",
    re.I,
)

PLATFORM_URL_HINTS = {
    "instagram": "https://instagram.com/username أو رابط منشور/ريل",
    "tiktok": "https://tiktok.com/@username أو رابط فيديو",
    "youtube": "https://youtube.com/@channel أو /channel/...",
}


def normalize_platform(platform: str) -> str:
    return (platform or "").strip().lower()


def instagram_profile_url(username: str) -> str:
    clean = username.strip().lstrip("@")
    return f"https://www.instagram.com/{clean}/"


def tiktok_profile_url(username: str) -> str:
    clean = username.strip().lstrip("@")
    return f"https://www.tiktok.com/@{clean}"


def parse_instagram(url: str) -> dict[str, Any] | None:
    url = url.strip()
    post = INSTAGRAM_POST_RE.match(url)
    if post:
        return {
            "platform": "instagram",
            "kind": "post",
            "id": post.group(1),
            "url": url if url.startswith("http") else f"https://{url}",
        }
    user = INSTAGRAM_USER_RE.match(url)
    if user and user.group(1) not in ("p", "reel", "tv", "stories", "explore"):
        username = user.group(1)
        return {
            "platform": "instagram",
            "kind": "profile",
            "username": username,
            "url": instagram_profile_url(username),
        }
    return None


def parse_tiktok(url: str) -> dict[str, Any] | None:
    url = url.strip()
    video = TIKTOK_VIDEO_RE.match(url)
    if video:
        return {
            "platform": "tiktok",
            "kind": "video",
            "id": video.group(1),
            "url": url if url.startswith("http") else f"https://{url}",
        }
    user = TIKTOK_USER_RE.match(url)
    if user:
        username = user.group(1)
        return {
            "platform": "tiktok",
            "kind": "profile",
            "username": username,
            "url": tiktok_profile_url(username),
        }
    return None


def parse_platform_url(url: str, platform: str | None = None) -> dict[str, Any] | None:
    platform = normalize_platform(platform) if platform else None
    parsers = []
    if not platform or platform == "instagram":
        parsers.append(parse_instagram)
    if not platform or platform == "tiktok":
        parsers.append(parse_tiktok)

    for parser in parsers:
        result = parser(url)
        if result:
            if platform and result["platform"] != platform:
                continue
            return result
    return None


def validate_url_for_platform(url: str, platform: str) -> tuple[bool, str, dict | None]:
    platform = normalize_platform(platform)
    if platform == "youtube":
        lower = url.lower()
        if "youtube.com" in lower or "youtu.be" in lower:
            return True, "رابط يوتيوب صالح", {"platform": "youtube", "kind": "channel", "url": url}
        return False, "أدخل رابط يوتيوب صحيح (youtube.com أو youtu.be)", None

    parsed = parse_platform_url(url, platform)
    if not parsed:
        hint = PLATFORM_URL_HINTS.get(platform, "رابط غير صالح")
        label = {"instagram": "إنستجرام", "tiktok": "تيك توك"}.get(platform, platform)
        return False, f"رابط {label} غير صالح — مثال: {hint}", None
    return True, "الرابط صالح", parsed


async def fetch_tiktok_oembed(url: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.get(
                "https://www.tiktok.com/oembed",
                params={"url": url},
            )
            if res.status_code == 200:
                data = res.json()
                return {
                    "title": data.get("title") or data.get("author_name"),
                    "author": data.get("author_name"),
                    "author_url": data.get("author_url"),
                    "thumbnail": data.get("thumbnail_url"),
                }
    except httpx.HTTPError:
        pass
    return None


async def fetch_instagram_oembed(url: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.get(
                "https://www.instagram.com/oembed/",
                params={"url": url, "omitscript": "true"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; SW-Panel/1.0)"},
            )
            if res.status_code == 200 and res.text.strip():
                data = res.json()
                return {
                    "title": data.get("title") or data.get("author_name"),
                    "author": data.get("author_name"),
                    "author_url": data.get("author_url"),
                    "thumbnail": data.get("thumbnail_url"),
                }
    except (httpx.HTTPError, ValueError):
        pass
    return None


async def preview_url(url: str, platform: str | None = None) -> dict[str, Any]:
    ok, message, parsed = validate_url_for_platform(url, platform) if platform else (
        True,
        "",
        parse_platform_url(url),
    )
    if not parsed and platform:
        return {"ok": False, "message": message, "parsed": None, "preview": None}

    if not parsed:
        return {"ok": False, "message": "تعذّر تحليل الرابط", "parsed": None, "preview": None}

    preview = None
    if parsed["platform"] == "tiktok":
        preview = await fetch_tiktok_oembed(parsed["url"])
    elif parsed["platform"] == "instagram":
        preview = await fetch_instagram_oembed(parsed["url"])
        if not preview and parsed.get("username"):
            preview = {
                "title": f"@{parsed['username']}",
                "author": parsed["username"],
                "author_url": parsed["url"],
            }

    return {
        "ok": True,
        "message": message or "الرابط صالح",
        "parsed": parsed,
        "preview": preview,
    }
