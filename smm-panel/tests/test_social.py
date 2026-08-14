from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from app.social_oauth import (
    instagram_profile_from_json,
    parse_instagram_token_payload,
    parse_tiktok_token_payload,
    pop_oauth_state,
    sanitize_oauth_code,
    start_oauth,
    tiktok_profile_from_json,
)


def test_sanitize_instagram_code_fragment():
    assert sanitize_oauth_code("AQBxCode#_") == "AQBxCode"
    assert sanitize_oauth_code("  abc  ") == "abc"


def test_parse_instagram_token_formats():
    nested = parse_instagram_token_payload(
        {"data": [{"access_token": "IGAAA", "user_id": "99"}]}
    )
    assert nested["access_token"] == "IGAAA"
    flat = parse_instagram_token_payload({"access_token": "IGBBB", "user_id": 1})
    assert flat["access_token"] == "IGBBB"


def test_parse_tiktok_token_formats():
    nested = parse_tiktok_token_payload({"data": {"access_token": "TTAAA", "open_id": "o1"}})
    assert nested["access_token"] == "TTAAA"
    flat = parse_tiktok_token_payload({"access_token": "TTBBB", "open_id": "o2"})
    assert flat["access_token"] == "TTBBB"


def test_instagram_and_tiktok_profile_mapping():
    ig = instagram_profile_from_json(
        {"user_id": "11", "username": "najjar.official", "account_type": "BUSINESS"},
        "tok",
    )
    assert ig["platform"] == "instagram"
    assert ig["username"] == "najjar.official"
    assert ig["profile_url"] == "https://www.instagram.com/najjar.official/"
    assert ig["verified"] is True

    tt = tiktok_profile_from_json(
        {"open_id": "oid", "username": "najjar.tt", "display_name": "Najjar"},
        "tok",
    )
    assert tt["platform"] == "tiktok"
    assert tt["username"] == "najjar.tt"
    assert tt["profile_url"] == "https://www.tiktok.com/@najjar.tt"


def test_start_oauth_urls_and_persisted_state():
    ig_url = start_oauth("instagram", 1)
    ig = urlparse(ig_url)
    assert ig.netloc == "www.instagram.com"
    assert ig.path == "/oauth/authorize"
    ig_qs = parse_qs(ig.query)
    assert ig_qs["scope"] == ["instagram_business_basic"]
    assert ig_qs["redirect_uri"] == ["https://sw.test/api/social/oauth/instagram/callback"]
    ig_state = pop_oauth_state(ig_qs["state"][0])
    assert ig_state["platform"] == "instagram"
    assert ig_state["user_id"] == 1

    tt_url = start_oauth("tiktok", 1)
    tt = urlparse(tt_url)
    assert "tiktok.com" in tt.netloc
    tt_qs = parse_qs(tt.query)
    assert "user.info.profile" in tt_qs["scope"][0]
    assert tt_qs["code_challenge_method"] == ["S256"]
    assert tt_qs["redirect_uri"] == ["https://sw.test/api/social/oauth/tiktok/callback"]
    tt_state = pop_oauth_state(tt_qs["state"][0])
    assert tt_state["platform"] == "tiktok"
    assert tt_state["code_verifier"]


def test_manual_link_instagram_and_tiktok(client, auth_headers):
    ig = client.post(
        "/api/social/link",
        headers=auth_headers,
        json={"platform": "instagram", "username": "https://instagram.com/najjar.official"},
    )
    assert ig.status_code == 200, ig.text
    body = ig.json()
    assert body["platform"] == "instagram"
    assert body["username"] == "najjar.official"
    assert "instagram.com/najjar.official" in body["profile_url"]

    tt = client.post(
        "/api/social/link",
        headers=auth_headers,
        json={"platform": "tiktok", "username": "@najjar.tt"},
    )
    assert tt.status_code == 200, tt.text
    assert tt.json()["username"] == "najjar.tt"

    listed = client.get("/api/social/connections", headers=auth_headers)
    platforms = {row["platform"] for row in listed.json()}
    assert platforms == {"instagram", "tiktok"}


def test_oauth_status_and_start_endpoints(client, auth_headers):
    status = client.get("/api/social/oauth/status", headers=auth_headers)
    assert status.status_code == 200
    data = status.json()
    assert data["instagram"] is True
    assert data["tiktok"] is True
    assert data["redirect_uris"]["instagram"].endswith("/api/social/oauth/instagram/callback")
    assert data["redirect_uris"]["tiktok"].endswith("/api/social/oauth/tiktok/callback")

    ig = client.get("/api/social/oauth/instagram/start", headers=auth_headers)
    assert ig.status_code == 200
    assert "instagram.com/oauth/authorize" in ig.json()["url"]

    tt = client.get("/api/social/oauth/tiktok/start", headers=auth_headers)
    assert tt.status_code == 200
    assert "tiktok.com" in tt.json()["url"]


def test_oauth_callback_saves_instagram_account(client, auth_headers):
    start = client.get("/api/social/oauth/instagram/start", headers=auth_headers)
    state = parse_qs(urlparse(start.json()["url"]).query)["state"][0]
    profile = {
        "platform": "instagram",
        "platform_user_id": "11",
        "username": "najjar.official",
        "profile_url": "https://www.instagram.com/najjar.official/",
        "access_token": "tok",
        "verified": True,
        "meta": {"verified_via": "oauth"},
    }
    with patch("app.main.exchange_instagram_code", new=AsyncMock(return_value=profile)):
        res = client.get(
            "/api/social/oauth/instagram/callback",
            params={"code": "IGCODE", "state": state},
            follow_redirects=False,
        )
    assert res.status_code in (302, 307)
    assert "oauth=success" in res.headers["location"]
    assert "platform=instagram" in res.headers["location"]

    listed = client.get("/api/social/connections", headers=auth_headers)
    ig = next(row for row in listed.json() if row["platform"] == "instagram")
    assert ig["verified"] is True
    assert ig["username"] == "najjar.official"


def test_oauth_callback_saves_tiktok_account(client, auth_headers):
    start = client.get("/api/social/oauth/tiktok/start", headers=auth_headers)
    state = parse_qs(urlparse(start.json()["url"]).query)["state"][0]
    profile = {
        "platform": "tiktok",
        "platform_user_id": "oid",
        "username": "najjar.tt",
        "profile_url": "https://www.tiktok.com/@najjar.tt",
        "access_token": "tok",
        "verified": True,
        "meta": {"verified_via": "oauth"},
    }
    with patch("app.main.exchange_tiktok_code", new=AsyncMock(return_value=profile)):
        res = client.get(
            "/api/social/oauth/tiktok/callback",
            params={"code": "TTCODE", "state": state},
            follow_redirects=False,
        )
    assert res.status_code in (302, 307)
    assert "oauth=success" in res.headers["location"]

    listed = client.get("/api/social/connections", headers=auth_headers)
    tt = next(row for row in listed.json() if row["platform"] == "tiktok")
    assert tt["verified"] is True
    assert tt["username"] == "najjar.tt"


def test_oauth_callback_rejects_missing_state(client):
    res = client.get(
        "/api/social/oauth/instagram/callback",
        params={"code": "x", "state": "missing"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 307)
    assert "oauth=error" in res.headers["location"]


def test_health_reports_integrations(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    integrations = res.json()["integrations"]
    assert integrations["instagram_oauth"] is True
    assert integrations["tiktok_oauth"] is True
