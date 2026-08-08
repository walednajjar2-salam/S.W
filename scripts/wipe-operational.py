#!/usr/bin/env python3
"""Wipe all operational data (keep users). Works locally or against cloud API."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = os.environ.get("LQ_API", "https://web-production-08d73.up.railway.app/api").rstrip("/")
USER = os.environ.get("LQ_ADMIN_USER", "admin")
PASSWORD = os.environ.get("LQ_ADMIN_PASS", "555555")


def api_call(method: str, path: str, token: str | None = None, body: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}/{path.lstrip('/')}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": raw}
        return e.code, payload


def wipe_cloud() -> bool:
    print(f"Cloud wipe via {API}")
    candidates = [
        (USER, PASSWORD),
        ("waleed", "111111"),
        ("admin", "555555"),
        ("yaqoub", "owner2015"),
    ]
    token = None
    used = None
    for u, p in candidates:
        _, login = api_call("POST", "login", body={"username": u, "password": p})
        if login.get("token"):
            token = login["token"]
            used = u
            break
    if not token:
        print("Login failed for all candidates")
        return False
    print("Logged in as:", used)

    code, resp = api_call("POST", "admin/reset_operational", token, {"confirm": "RESET", "clear_uploads": True})
    if code == 200 and resp.get("ok"):
        print("Reset OK — users kept:", resp.get("users_kept"))
        print("Cleared:", json.dumps(resp.get("cleared") or {}, ensure_ascii=False))
        return True

    print("admin/reset_operational:", code, resp.get("error") or resp)
    return False


def wipe_local() -> bool:
    os.environ.setdefault("LQ_NO_SAMPLE_DATA", "1")
    from server import connect, init_db, reset_operational_data, seed_chart_accounts

    init_db()
    with connect() as db:
        cleared = reset_operational_data(db)
        seed_chart_accounts(db)
        users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        db.commit()
    print("Local wipe OK — users kept:", users)
    print("Cleared:", json.dumps(cleared, ensure_ascii=False))
    return True


def counts_cloud(token: str) -> dict:
    _, boot = api_call("GET", "bootstrap", token)
    data = boot.get("data") or {}
    return {k: len(v) if isinstance(v, list) else v for k, v in sorted(data.items()) if k != "users"}


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
    ok = True
    if mode in ("local", "both"):
        print("\n=== Local database ===")
        ok = wipe_local() and ok
    if mode in ("cloud", "both"):
        print("\n=== Cloud production ===")
        ok = wipe_cloud() and ok
        _, login = api_call("POST", "login", body={"username": USER, "password": PASSWORD})
        if login.get("token"):
            print("Remaining (excluding users):", json.dumps(counts_cloud(login["token"]), ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
