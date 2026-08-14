def test_generate_accounts_and_login(client, auth_headers):
    res = client.post(
        "/api/admin/users/generate",
        headers=auth_headers,
        json={
            "count": 3,
            "email_prefix": "client",
            "email_domain": "example.com",
            "name_prefix": "عميل",
            "password": "Pass1234",
            "balance": 25,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["count"] == 3
    emails = [row["email"] for row in data["accounts"]]
    assert emails == ["client1@example.com", "client2@example.com", "client3@example.com"]
    assert all(row["password"] == "Pass1234" for row in data["accounts"])

    login = client.post(
        "/api/auth/login",
        json={"email": "client1@example.com", "password": "Pass1234"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["balance"] == 25

    again = client.post(
        "/api/admin/users/generate",
        headers=auth_headers,
        json={"count": 1, "email_prefix": "client", "email_domain": "example.com"},
    )
    assert again.json()["accounts"][0]["email"] == "client4@example.com"


def test_invite_code_registration(client, auth_headers):
    closed = client.post(
        "/api/auth/register",
        json={
            "name": "بدون كود",
            "email": "nocode@example.com",
            "password": "secret1",
        },
    )
    assert closed.status_code == 403

    created = client.post(
        "/api/admin/invite-codes",
        headers=auth_headers,
        json={"max_uses": 1, "note": "تجربة"},
    )
    assert created.status_code == 200, created.text
    code = created.json()["code"]
    assert code.startswith("SW-")

    registered = client.post(
        "/api/auth/register",
        json={
            "name": "ضيف جديد",
            "email": "guest@example.com",
            "password": "secret1",
            "invite_code": code,
        },
    )
    assert registered.status_code == 200, registered.text
    assert registered.json()["user"]["email"] == "guest@example.com"

    reused = client.post(
        "/api/auth/register",
        json={
            "name": "آخر",
            "email": "guest2@example.com",
            "password": "secret1",
            "invite_code": code,
        },
    )
    assert reused.status_code == 403


def test_register_page_and_status(client):
    page = client.get("/register")
    assert page.status_code == 200
    login_page = client.get("/login")
    assert login_page.status_code == 200
    status = client.get("/api/auth/register-status")
    assert status.status_code == 200
    assert status.json()["requires_invite"] is True
