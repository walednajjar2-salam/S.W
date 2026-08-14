import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def wait(url: str, timeout: float = 30.0) -> None:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"Service not ready: {url}")


def request(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=8) as resp:
        body = resp.read().decode()
        return resp.status, json.loads(body) if body else {}


def main() -> int:
    port = os.environ.get("PORT", "8099")
    env = os.environ.copy()
    env["PORT"] = port
    env.setdefault("SMM_DATABASE_PATH", f"/tmp/sw-test-{port}.db")

    import subprocess

    proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=str(Path(__file__).resolve().parent.parent / "smm-panel"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait(f"{base}/api/health")
        wait(f"{base}/login")
        wait(f"{base}/assets/styles.css")

        _, login = request(
            f"{base}/api/auth/login",
            method="POST",
            data=b'{"email":"walednajjar2@gmail.com","password":"najjar"}',
            headers={"Content-Type": "application/json"},
        )
        token = login.get("access_token")
        if not token:
            raise RuntimeError("Login failed")
        auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        _, connections = request(f"{base}/api/social/connections", headers=auth)
        if not isinstance(connections, list):
            raise RuntimeError("social connections failed")

        _, ig = request(
            f"{base}/api/social/link",
            method="POST",
            data=b'{"platform":"instagram","username":"najjar.official"}',
            headers=auth,
        )
        if ig.get("platform") != "instagram" or ig.get("username") != "najjar.official":
            raise RuntimeError(f"Instagram link failed: {ig}")

        _, tt = request(
            f"{base}/api/social/link",
            method="POST",
            data=b'{"platform":"tiktok","username":"@najjar.tt"}',
            headers=auth,
        )
        if tt.get("platform") != "tiktok" or tt.get("username") != "najjar.tt":
            raise RuntimeError(f"TikTok link failed: {tt}")

        _, status = request(f"{base}/api/social/oauth/status", headers=auth)
        if "instagram" not in status or "tiktok" not in status:
            raise RuntimeError(f"oauth status failed: {status}")
        if "instagram" not in (status.get("redirect_uris") or {}):
            raise RuntimeError("oauth redirect URIs missing")

        wait(f"{base}/register")
        _, generated = request(
            f"{base}/api/admin/users/generate",
            method="POST",
            data=b'{"count":1,"email_prefix":"smoke","email_domain":"example.com","password":"Smoke123"}',
            headers=auth,
        )
        if not generated.get("accounts"):
            raise RuntimeError(f"account generate failed: {generated}")

        _, invite = request(
            f"{base}/api/admin/invite-codes",
            method="POST",
            data=b'{"max_uses":1,"note":"smoke"}',
            headers=auth,
        )
        if not str(invite.get("code", "")).startswith("SW-"):
            raise RuntimeError(f"invite code failed: {invite}")

        print("OK: production smoke test passed")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
