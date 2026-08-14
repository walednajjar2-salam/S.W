import re
from typing import Any
from urllib.parse import urlparse

import httpx

INSTAGRAM_HOST = r"(?:https?://)?(?:www\.|m\.)?(?:instagram\.com|instagr\.am)"
INSTAGRAM_USER_RE = re.compile(
    rf"{INSTAGRAM_HOST}/([A-Za-z0-9._]+)/?",
    re.I,
)
INSTAGRAM_POST_RE = re.compile(
    rf"{INSTAGRAM_HOST}/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)",
    re.I,
)
TIKTOK_USER_RE = re.compile(
    r"(?:https?://)?(?:(?:www|m|vm)\.)?tiktok\.com/@([A-Za-z0-9._]+)/?",
    re.I,
)
TIKTOK_VIDEO_RE = re.compile(
    r"(?:https?://)?(?:(?:www|m)\.)?tiktok\.com/@([^/\s]+)/video/(\d+)",
    re.I,
)
TIKTOK_SHORT_RE = re.compile(
    r"(?:https?://)?(?:vm|vt)\.tiktok\.com/([A-Za-z0-9]+)/?",
    re.I,
)
TIKTOK_SHARE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?tiktok\.com/t/([A-Za-z0-9]+)/?",
    re.I,
)
USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
INSTAGRAM_RESERVED = {
    "p",
    "reel",
    "reels",
    "tv",
    "stories",
    "explore",
    "accounts",
    "share",
    "about",
    "developer",
    "legal",
    "directory",
    "emails",
    "lite",
    "direct",
    "tags",
}

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


def is_valid_social_username(username: str) -> bool:
    return bool(USERNAME_RE.fullmatch((username or "").strip().lstrip("@")))


def extract_username(value: str, platform: str | None = None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    platform = normalize_platform(platform) if platform else None
    maybe_url = raw if "://" in raw or "." in raw.split("/")[0] else ""
    if maybe_url or raw.startswith("http") or "instagram.com" in raw or "tiktok.com" in raw:
        url = raw if "://" in raw else f"https://{raw.lstrip('/')}"
        if not platform or platform == "instagram":
            parsed = parse_instagram(url)
            if parsed and parsed.get("username"):
                return parsed["username"]
        if not platform or platform == "tiktok":
            parsed = parse_tiktok(url)
            if parsed and parsed.get("username"):
                return parsed["username"]
    clean = raw.lstrip("@").strip().strip("/")
    if is_valid_social_username(clean):
        return clean
    return None


def parse_instagram(url: str) -> dict[str, Any] | None:
    url = (url or "").strip()
    post = INSTAGRAM_POST_RE.search(url)
    if post:
        found = url if url.startswith("http") else f"https://{url}"
        return {
            "platform": "instagram",
            "kind": "post",
            "id": post.group(1),
            "url": found.split("?")[0].rstrip("/") + "/",
        }
    user = INSTAGRAM_USER_RE.search(url)
    if user and user.group(1).lower() not in INSTAGRAM_RESERVED:
        username = user.group(1)
        return {
            "platform": "instagram",
            "kind": "profile",
            "username": username,
            "url": instagram_profile_url(username),
        }
    return None


def parse_tiktok(url: str) -> dict[str, Any] | None:
    url = (url or "").strip()
    video = TIKTOK_VIDEO_RE.search(url)
    if video:
        username = video.group(1).lstrip("@")
        video_id = video.group(2)
        found = url if url.startswith("http") else f"https://{url}"
        return {
            "platform": "tiktok",
            "kind": "video",
            "id": video_id,
            "username": username,
            "url": found.split("?")[0],
        }
    user = TIKTOK_USER_RE.search(url)
    if user:
        username = user.group(1)
        return {
            "platform": "tiktok",
            "kind": "profile",
            "username": username,
            "url": tiktok_profile_url(username),
        }
    if TIKTOK_SHORT_RE.search(url) or TIKTOK_SHARE_RE.search(url):
        found = url if url.startswith("http") else f"https://{url}"
        return {
            "platform": "tiktok",
            "kind": "short",
            "url": found.split("?")[0],
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


def is_unresolved_short_url(url: str) -> bool:
    parsed = parse_tiktok(url)
    if parsed and parsed.get("kind") == "short":
        return True
    host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    return host in {"l.instagram.com", "lm.instagram.com"}


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


async def resolve_social_url(url: str) -> str:
    url = (url or "").strip()
    if not url or not is_unresolved_short_url(url):
        return url
    target = url if url.startswith("http") else f"https://{url}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SW-Panel/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
            res = await client.head(target)
            if res.status_code >= 400:
                res = await client.get(target)
            return str(res.url)
    except httpx.HTTPError:
        return url


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
    resolved = await resolve_social_url(url)
    ok, message, parsed = validate_url_for_platform(resolved, platform) if platform else (
        True,
        "",
        parse_platform_url(resolved),
    )
    if not parsed and platform:
        return {"ok": False, "message": message, "parsed": None, "preview": None}

    if not parsed:
        return {"ok": False, "message": "تعذّر تحليل الرابط", "parsed": None, "preview": None}

    preview = None
    if parsed["platform"] == "tiktok":
        preview = await fetch_tiktok_oembed(parsed["url"])
        if not preview and parsed.get("username"):
            preview = {
                "title": f"@{parsed['username']}",
                "author": parsed["username"],
                "author_url": parsed["url"],
            }
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
