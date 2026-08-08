#!/usr/bin/env python3
"""Post-deploy verification for Portal API on Railway production."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://web-production-08d73.up.railway.app/api"


def call(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw}
        return exc.code, payload


def main() -> int:
    rows: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        rows.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    code, health = call("GET", "/health")
    add("/api/health", code == 200 and health.get("ok") and health.get("status") == "healthy", health.get("version", ""))

    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        add("admin login (ADMIN_PASSWORD)", False, "ADMIN_PASSWORD not set")
        staff = ""
    else:
        code, login = call("POST", "/login", {"username": "admin", "password": admin_password})
        staff = login.get("token", "")
        add("admin login (ADMIN_PASSWORD)", code == 200 and bool(staff), login.get("user", {}).get("role", ""))

    code, dash = call("GET", "/dashboard", token=staff)
    add("/api/dashboard staff Bearer", code == 200 and dash.get("ok") is True, f"occupancy={dash.get('dashboard', {}).get('kpis', {}).get('occupancy')}")

    code, backup_status = call("GET", "/backup/status", token=staff)
    add(
        "/api/backup/status includes storage telemetry",
        code == 200 and backup_status.get("ok") is True and isinstance(backup_status.get("storage"), dict),
        f"storage_warning={backup_status.get('storage', {}).get('warning')}",
    )
    add(
        "/api/backup/status integrity check",
        code == 200 and isinstance(backup_status.get("backup_integrity"), dict),
        f"integrity_ok={backup_status.get('backup_integrity', {}).get('ok')}",
    )

    code, pa = call("GET", "/permissions/audit", token=staff)
    add(
        "/api/permissions/audit admin matrix",
        code == 200 and pa.get("ok") is True and bool((pa.get("roles") or {}).get("admin")),
        f"roles={len(pa.get('roles') or {})}",
    )

    code, contracts_res = call("GET", "/contracts", token=staff)
    code2, invoices_res = call("GET", "/invoices", token=staff)
    contracts = {c.get("id"): c for c in (contracts_res.get("items") or [])}
    broken_links = []
    if code == 200 and code2 == 200:
        for inv in invoices_res.get("items") or []:
            cid = inv.get("contract_id")
            if cid and cid not in contracts:
                broken_links.append(inv.get("invoice_no") or inv.get("id"))
    add(
        "invoice->contract linking integrity",
        code == 200 and code2 == 200 and not broken_links,
        "broken=" + str(len(broken_links)),
    )

    code, bad = call("GET", "/portal/dashboard?token=invalid-token-probe")
    add(
        "/api/portal/dashboard route exists",
        code == 401 and "Unknown endpoint" not in str(bad.get("error", "")),
        f"http={code} error={bad.get('error')}",
    )

    portal_token = None
    code, gen = call("POST", "/portal/generate_token", {"client_id": "C-1001"}, token=staff)
    if code == 200 and gen.get("ok"):
        portal_token = gen.get("token")
        add("portal token for C-1001", True, "via generate_token (existing code)")
    else:
        code, client = call("GET", "/clients/C-1001", token=staff)
        portal_token = (client.get("item") or {}).get("portal_token")
        add("portal token for C-1001", bool(portal_token), gen.get("error") or "from client record")

    if not portal_token:
        add("portal dashboard real token", False, "no token")
        add("TEST maintenance write", False, "skipped")
        add("TEST payment proof write", False, "skipped")
    else:
        q = urllib.parse.urlencode({"token": portal_token})
        code, pd = call("GET", f"/portal/dashboard?{q}")
        add(
            "portal dashboard real token",
            code == 200 and pd.get("ok") is True,
            f"tenant={pd.get('client', {}).get('name')} invoices={len(pd.get('invoices') or [])}",
        )

        code, maint = call(
            "POST",
            "/portal/maintenance",
            {
                "token": portal_token,
                "title": "TEST",
                "priority": "Medium",
                "notes": "TEST Flutter portal deploy verification",
            },
        )
        add("TEST maintenance write", code == 200 and maint.get("ok") is True, "title=TEST")

        open_inv = [i for i in (pd.get("invoices") or []) if i.get("status") != "Paid"]
        if open_inv:
            inv = open_inv[0]
            remaining = float(inv.get("amount") or 0) - float(inv.get("paid_amount") or 0)
            if remaining <= 0:
                remaining = 1.0
            code, proof = call(
                "POST",
                "/portal/submit_proof",
                {
                    "token": portal_token,
                    "invoice_id": inv.get("id"),
                    "amount": remaining,
                    "transfer_ref": "TEST-DEPLOY",
                    "note": "TEST payment proof deploy verification",
                    "proof_image": "",
                },
            )
            add(
                "TEST payment proof write",
                code == 200 and proof.get("ok") is True,
                f"invoice={inv.get('invoice_no')} amount={remaining} OMR",
            )
        else:
            add("TEST payment proof write", False, "no open invoice")

    failed = [r for r in rows if not r[1]]
    print("\nSummary:", "ALL PASS" if not failed else f"{len(failed)} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
