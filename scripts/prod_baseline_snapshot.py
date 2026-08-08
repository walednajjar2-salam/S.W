#!/usr/bin/env python3
"""Create production safety baseline before code rollout."""
from __future__ import annotations

import json
import os
import urllib.request


BASE = os.environ.get("JAWDAH_BASE_URL", "https://web-production-08d73.up.railway.app").rstrip("/")
TOKEN = os.environ.get("JAWDAH_ADMIN_TOKEN", "").strip()


def call(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{BASE}/api/{path.lstrip('/')}"
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def main() -> int:
    health = call("GET", "/health")
    backup = call("POST", "/backup/run", {})
    status = call("GET", "/backup/status")
    snapshot = {
        "health": health,
        "backup_run": backup,
        "backup_status": status,
    }
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    ok = bool(health.get("ok") and backup.get("ok"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
