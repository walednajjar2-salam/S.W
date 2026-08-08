#!/usr/bin/env python3
"""Local pre-deploy checks for Tenant Portal API (portal.js contract)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PORT = 18765
BASE = f"http://127.0.0.1:{PORT}/api"


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def seed_portal_client(db_path: Path) -> str:
    token = "local-test-portal-token"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            INSERT OR REPLACE INTO clients
            (id, name, phone, email, national_id, balance, notes, portal_token, portal_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("C-TEST", "TEST Tenant", "90000000", "test@example.com", "T-1", 0, "local", token, 1),
        )
        db.execute(
            """
            INSERT OR REPLACE INTO properties
            (id, name, type, status, price, location, image, notes, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'))
            """,
            ("P-TEST", "TEST Unit 101", "Apartment", "Rented", 500, "Nizwa", "🏠", ""),
        )
        db.execute(
            """
            INSERT OR REPLACE INTO contracts
            (id, property_id, client_id, start_date, end_date, rent_amount, status, payment_cycle, notes)
            VALUES (?, ?, ?, date('now'), date('now','+1 year'), ?, ?, ?, ?)
            """,
            ("CT-TEST", "P-TEST", "C-TEST", 780, "Active", "monthly", ""),
        )
        db.execute(
            """
            INSERT OR REPLACE INTO invoices
            (id, invoice_no, contract_id, client_id, property_id, issue_date, due_date, amount, paid_amount, status, description)
            VALUES (?, ?, ?, ?, ?, date('now'), date('now','+7 day'), ?, ?, ?, ?)
            """,
            ("INV-TEST", "INV-TEST-001", "CT-TEST", "C-TEST", "P-TEST", 780, 0, "Pending", "TEST rent"),
        )
        db.commit()
    return token


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="lqllc_portal_test_"))
    os.environ["JAWDAH_DATA_DIR"] = str(tmp)
    os.environ["JAWDAH_HOST"] = "127.0.0.1"
    os.environ["JAWDAH_PORT"] = str(PORT)
    os.environ["JAWDAH_AUTO_BACKUP"] = "0"
    test_admin_password = os.environ.get("ADMIN_PASSWORD", "").strip() or "local-test-admin-password"
    os.environ["ADMIN_PASSWORD"] = test_admin_password

    import server  # noqa: WPS433

    server.ADMIN_PASSWORD = test_admin_password

    server.init_db()
    portal_token = seed_portal_client(server.DB_PATH)

    httpd = server.ThreadingHTTPServer(("127.0.0.1", PORT), server.JawdahHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.8)

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    try:
        health = request("GET", "/health")
        check("GET /api/health", health.get("ok") is True)

        login = request("POST", "/login", {"username": "admin", "password": test_admin_password})
        staff_token = login.get("token", "")
        check("POST /api/login admin (ADMIN_PASSWORD)", bool(staff_token), f"role={login.get('user', {}).get('role')}")

        dash = request("GET", "/dashboard", token=staff_token)
        check("GET /api/dashboard (staff)", dash.get("ok") is True)

        portal = request("GET", f"/portal/dashboard?token={portal_token}")
        check(
            "GET /api/portal/dashboard",
            portal.get("ok") is True and portal.get("client", {}).get("id") == "C-TEST",
            f"invoices={len(portal.get('invoices') or [])}",
        )

        maint = request(
            "POST",
            "/portal/maintenance",
            {"token": portal_token, "title": "TEST", "priority": "Medium", "notes": "local pre-deploy"},
        )
        check("POST /api/portal/maintenance TEST", maint.get("ok") is True)

        proof = request(
            "POST",
            "/portal/submit_proof",
            {
                "token": portal_token,
                "invoice_id": "INV-TEST",
                "amount": 780,
                "transfer_ref": "TEST-LOCAL",
                "note": "TEST proof",
                "proof_image": "",
            },
        )
        check("POST /api/portal/submit_proof TEST", proof.get("ok") is True)

        bad = None
        try:
            request("GET", "/portal/dashboard?token=invalid")
        except urllib.error.HTTPError as exc:
            bad = exc.code
        check("Invalid portal token rejected", bad == 401, f"http={bad}")

    finally:
        httpd.shutdown()

    print("\nLocal portal API checks:", "OK" if not failures else f"FAILED ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
