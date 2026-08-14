import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"sw-social-test-{os.getpid()}.db"
os.environ["SMM_DATABASE_PATH"] = str(TEST_DB)
os.environ["SMM_ADMIN_EMAIL"] = "walednajjar2@gmail.com"
os.environ["SMM_ADMIN_PASSWORD"] = "najjar"
os.environ["SMM_SECRET_KEY"] = "test-secret-key"
os.environ["SMM_PUBLIC_BASE_URL"] = "https://sw.test"
os.environ["SMM_INSTAGRAM_CLIENT_ID"] = "ig-app-id"
os.environ["SMM_INSTAGRAM_CLIENT_SECRET"] = "ig-app-secret"
os.environ["SMM_TIKTOK_CLIENT_KEY"] = "tt-client-key"
os.environ["SMM_TIKTOK_CLIENT_SECRET"] = "tt-client-secret"
os.environ["SMM_DELIVERY_INTERVAL_SECONDS"] = "120"

if TEST_DB.exists():
    TEST_DB.unlink()

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def client():
    with TestClient(app) as test_client:
        yield test_client
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def auth_headers(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "walednajjar2@gmail.com", "password": "najjar"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
