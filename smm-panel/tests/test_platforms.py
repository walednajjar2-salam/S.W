from app.platforms import (
    extract_username,
    parse_instagram,
    parse_tiktok,
    validate_url_for_platform,
)


def test_instagram_profile_urls():
    parsed = parse_instagram("https://www.instagram.com/najjar.official/")
    assert parsed["kind"] == "profile"
    assert parsed["username"] == "najjar.official"

    parsed = parse_instagram("https://m.instagram.com/najjar.official/?hl=ar")
    assert parsed["username"] == "najjar.official"

    parsed = parse_instagram("instagram.com/najjar.official")
    assert parsed["username"] == "najjar.official"


def test_instagram_post_and_reel():
    post = parse_instagram("https://www.instagram.com/p/AbC123xyz/")
    assert post["kind"] == "post"
    assert post["id"] == "AbC123xyz"

    reel = parse_instagram("https://www.instagram.com/reel/ReEl99/?igsh=abc")
    assert reel["kind"] == "post"
    assert reel["id"] == "ReEl99"

    reels = parse_instagram("https://www.instagram.com/reels/ReEl88")
    assert reels["id"] == "ReEl88"


def test_tiktok_profile_and_video():
    profile = parse_tiktok("https://www.tiktok.com/@najjar.tt")
    assert profile["kind"] == "profile"
    assert profile["username"] == "najjar.tt"
    assert profile["url"] == "https://www.tiktok.com/@najjar.tt"

    video = parse_tiktok("https://www.tiktok.com/@najjar.tt/video/1234567890123456789?lang=ar")
    assert video["kind"] == "video"
    assert video["id"] == "1234567890123456789"
    assert video["username"] == "najjar.tt"


def test_tiktok_short_links_are_recognized():
    short = parse_tiktok("https://vm.tiktok.com/ZMabcdef/")
    assert short["kind"] == "short"
    share = parse_tiktok("https://www.tiktok.com/t/ZTabcdef/")
    assert share["kind"] == "short"


def test_extract_username_from_handle_or_url():
    assert extract_username("@najjar.official", "instagram") == "najjar.official"
    assert extract_username("https://instagram.com/najjar.official", "instagram") == "najjar.official"
    assert extract_username("najjar.tt", "tiktok") == "najjar.tt"
    assert extract_username("https://www.tiktok.com/@najjar.tt", "tiktok") == "najjar.tt"


def test_validate_matches_platform():
    ok, _, parsed = validate_url_for_platform("https://instagram.com/najjar.official", "instagram")
    assert ok and parsed["platform"] == "instagram"

    ok, msg, _ = validate_url_for_platform("https://instagram.com/najjar.official", "tiktok")
    assert not ok
    assert "تيك توك" in msg
