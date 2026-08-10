#!/usr/bin/env python3
"""Production smoke test for S.W panel."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def wait(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"Service not ready: {url}")


def main() -> int:
    port = os.environ.get("PORT", "8099")
    env = os.environ.copy()
    env["PORT"] = port
    env.setdefault("SMM_DATABASE_PATH", f"/tmp/sw-test-{port}.db")

    proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=os.path.join(os.path.dirname(__file__), "..", "smm-panel"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait(f"{base}/api/health")
        wait(f"{base}/login")
        wait(f"{base}/assets/styles.css")

        login_req = urllib.request.Request(
            f"{base}/api/auth/login",
            data=b'{"email":"walednajjar2@gmail.com","password":"najjar"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(login_req, timeout=5) as resp:
            body = resp.read().decode()
            if "access_token" not in body:
                raise RuntimeError("Login failed")

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
