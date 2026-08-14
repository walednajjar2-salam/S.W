from app.database import get_conn
from app.engagement import infer_action
from app.worker import worker


def test_infer_action_from_service_names():
    assert infer_action("متابعين إنستجرام") == "follow"
    assert infer_action("لايكات إنستجرام") == "like"
    assert infer_action("مشاهدات تيك توك") == "view"
    assert infer_action("مشتركين يوتيوب") == "subscribe"
    assert infer_action("Instagram likes") == "like"
    assert infer_action("TikTok followers") == "follow"


def test_generated_accounts_follow_target_url(client, auth_headers):
    generated = client.post(
        "/api/admin/users/generate",
        headers=auth_headers,
        json={
            "count": 4,
            "email_prefix": "clickig",
            "email_domain": "example.com",
            "password": "Pass1234",
            "balance": 50,
            "link_instagram": True,
            "link_tiktok": False,
        },
    )
    assert generated.status_code == 200, generated.text

    services = client.get("/api/services").json()
    follow = next(item for item in services if "متابعين إنستجرام" in item["name"])
    created = client.post(
        "/api/orders",
        headers=auth_headers,
        json={
            "service_id": follow["id"],
            "quantity": follow["min_qty"],
            "target_url": "https://www.instagram.com/najjar.official/",
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["engagement"]["action"] == "follow"
    assert order["engagement"]["assigned"] == 0

    worker._process_batch()
    worker._process_batch()

    listed = client.get("/api/orders", headers=auth_headers).json()
    row = next(item for item in listed if item["id"] == order["id"])
    assert row["engagement"]["assigned"] >= 4
    assert row["delivered"] >= 4
    assert row["engagement"]["action_label"] == "متابعة"

    detail = client.get(f"/api/orders/{order['id']}/engagement", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["assigned"] >= 4
    assert payload["action"] == "follow"
    assert "instagram.com/najjar.official" in payload["target_url"]
    usernames = {actor["username"] for actor in payload["actors"]}
    assert {"clickig1", "clickig2", "clickig3", "clickig4"} <= usernames
    assert all(actor["target_url"] == payload["target_url"] for actor in payload["actors"])
    assert all(actor["action"] == "follow" for actor in payload["actors"])
    assert all(actor["status"] == "clicked" for actor in payload["actors"])

    with get_conn() as conn:
        unique = conn.execute(
            "SELECT COUNT(DISTINCT actor_user_id) AS c FROM engagement_actions WHERE order_id = ?",
            (order["id"],),
        ).fetchone()["c"]
    assert unique == payload["assigned"]


def test_like_order_assigns_like_clicks(client, auth_headers):
    generated = client.post(
        "/api/admin/users/generate",
        headers=auth_headers,
        json={
            "count": 3,
            "email_prefix": "likebot",
            "email_domain": "example.com",
            "password": "Pass1234",
            "link_instagram": True,
            "link_tiktok": True,
        },
    )
    assert generated.status_code == 200, generated.text

    services = client.get("/api/services").json()
    likes = next(item for item in services if "لايكات إنستجرام" in item["name"])
    created = client.post(
        "/api/orders",
        headers=auth_headers,
        json={
            "service_id": likes["id"],
            "quantity": likes["min_qty"],
            "target_url": "https://www.instagram.com/p/AbC123xyz/",
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["id"]

    worker._process_batch()
    detail = client.get(f"/api/orders/{order_id}/engagement", headers=auth_headers).json()
    assert detail["action"] == "like"
    assert detail["action_label"] == "لايك"
    assert detail["assigned"] >= 3
    usernames = {actor["username"] for actor in detail["actors"]}
    assert {"likebot1", "likebot2", "likebot3"} <= usernames
    assert all(actor["action"] == "like" for actor in detail["actors"])
    assert "instagram.com/p/AbC123xyz" in detail["target_url"]


def test_order_owner_is_not_assigned_as_actor(client, auth_headers):
    generated = client.post(
        "/api/admin/users/generate",
        headers=auth_headers,
        json={
            "count": 2,
            "email_prefix": "ownerbot",
            "email_domain": "example.com",
            "password": "Pass1234",
            "balance": 50,
            "link_instagram": True,
            "link_tiktok": False,
        },
    )
    assert generated.status_code == 200, generated.text
    owner_email = generated.json()["accounts"][0]["email"]
    login = client.post(
        "/api/auth/login",
        json={"email": owner_email, "password": "Pass1234"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    services = client.get("/api/services").json()
    follow = next(item for item in services if "متابعين إنستجرام" in item["name"])
    created = client.post(
        "/api/orders",
        headers=headers,
        json={
            "service_id": follow["id"],
            "quantity": follow["min_qty"],
            "target_url": "https://www.instagram.com/target.page/",
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["id"]
    worker._process_batch()

    detail = client.get(f"/api/orders/{order_id}/engagement", headers=headers).json()
    emails = {actor["email"] for actor in detail["actors"]}
    assert owner_email not in emails
    assert "ownerbot2@example.com" in emails
