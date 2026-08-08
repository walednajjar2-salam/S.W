#!/usr/bin/env python3
"""Verify critical ops-complete (42-item) requirements against local codebase + DB."""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from lq_expand.security import validate_new_password  # noqa: E402


def ok(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def main() -> int:
    fails = 0

    # 1) Version / env label — the release marker must be present and consistent,
    # so a new release does not need this file edited to keep passing.
    app_release = re.search(r"v(\d+)\.(\d+)", server.APP_VERSION)
    tag_release = re.search(r"v(\d+)\.(\d+)", str(server.STABLE_TAG))
    fails += not ok("APP_VERSION release marker", bool(app_release), server.APP_VERSION)
    fails += not ok("STABLE_TAG release marker", bool(tag_release), str(server.STABLE_TAG))
    fails += not ok(
        "version and stable tag agree",
        bool(app_release and tag_release and app_release.groups() == tag_release.groups()),
        f"{server.APP_VERSION} / {server.STABLE_TAG}",
    )
    fails += not ok(
        "release at least v70",
        bool(app_release) and int(app_release.group(1)) >= 70,
        server.APP_VERSION,
    )
    fails += not ok("STAFF_APP_VERSION 70.x", server.STAFF_APP_VERSION.startswith("70."), server.STAFF_APP_VERSION)
    fails += not ok("env label present", bool(server.APP_ENV_LABEL_AR), server.APP_ENV_LABEL_AR)
    fails += not ok("official label Arabic", "رسمية" in server.APP_ENV_LABEL_AR or server.APP_ENV_MODE == "trial")

    # 2) Roles
    for role in ("owner", "admin", "deputy", "accountant", "operations", "reception", "maintenance", "viewer"):
        fails += not ok(f"role:{role}", role in server.ROLE_PERMISSIONS)
    fails += not ok("role labels Arabic", "نائب المدير" in server.ROLE_LABELS_AR.values())

    # 3) Credentials file has no bootstrap passwords
    cred = (ROOT / "docs" / "CREDENTIALS_REPORT.md").read_text(encoding="utf-8")
    fails += not ok(
        "credentials no plaintext passwords",
        "111111" not in cred and "owner2015" not in cred and "`001970`" not in cred and "555555" not in cred,
    )

    # 4) Password policy
    fails += not ok("password rejects short", validate_new_password("Ab1", "x") is not None)
    fails += not ok("password rejects digits-only", validate_new_password("1234567890", "x") is not None)
    fails += not ok("password accepts strong", validate_new_password("SecurePass9x", "x") is None)

    # 5) Temp DB integration checks
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        db_path = td_path / "jawdah.sqlite3"
        backup_dir = td_path / "backups"
        old_data = server.DATA_DIR
        old_db = server.DB_PATH
        old_backup = server.BACKUP_DIR
        server.DATA_DIR = td_path
        server.DB_PATH = db_path
        server.BACKUP_DIR = backup_dir
        try:
            server.init_db()
            with server.connect() as db:
                src = (ROOT / "server.py").read_text(encoding="utf-8")
                fails += not ok("users delete blocked in source", "لا يُسمح بحذف المستخدمين" in src)
                fails += not ok(
                    "uploads properties protected",
                    "uploads/properties/" in src and "uploads/estate_images/" in src and "uploads/attachments/" in src,
                )

                payload, err = server.prepare_property_payload(
                    {
                        "status": "شاغرة",
                        "building_no": "B1",
                        "apartment_no": "A1",
                        "location": "نزوى",
                        "unit_kind": "شقة كاملة",
                        "room_no": "should-clear",
                        "unit_rooms_count": 3,
                        "price": 100,
                    }
                )
                fails += not ok(
                    "full apt clears room_no",
                    err is None and payload and payload.get("room_no") == "",
                    str(err or payload),
                )

                fails += not ok("estate suspended in apartment map source", '"suspended": "suspended"' in src)
                fails += not ok("contract deposit forced 0", 'data["deposit_amount"] = 0' in src)
                fails += not ok("verify_backup_restore exists", hasattr(server, "verify_backup_restore"))

                snap = server.run_automatic_backup("ops-verify")
                fails += not ok("automatic backup created", bool(snap and snap.get("timestamp")), str(snap))
                report = server.verify_backup_restore(db)
                fails += not ok("backup verify runnable", isinstance(report, dict), str(report)[:120])
                fails += not ok(
                    "backup verify critical_ok",
                    bool(report.get("critical_ok") or report.get("ok")),
                    f"score={report.get('score')} critical_ok={report.get('critical_ok')}",
                )

                fails += not ok("blocks maintenance rental", server.property_status_blocks_rental("تحت الصيانة"))
                fails += not ok("blocks suspended rental", server.property_status_blocks_rental("موقوفة"))
                fails += not ok("allows vacant rental", not server.property_status_blocks_rental("شاغرة"))
                fails += not ok(
                    "conflict helper exists",
                    hasattr(server, "conflicting_contract_for_property")
                    or hasattr(server, "active_contract_exists_for_property"),
                )

                # Contract lifecycle: property + client + approve/activate sync
                prop_id = server.uid("PROP")
                client_id = server.uid("CLI")
                server.insert(
                    db,
                    "properties",
                    {
                        "id": prop_id,
                        "name": "بناية B1 - وحدة A9",
                        "type": "Apartment",
                        "status": "شاغرة",
                        "price": 120,
                        "location": "نزوى",
                        "building_no": "B1",
                        "apartment_no": "A9",
                        "room_no": "",
                        "latitude": None,
                        "longitude": None,
                        "image": "🏠",
                        "last_update": server.today(),
                        "notes": "",
                        "branch_id": None,
                        "unit_kind": "شقة كاملة",
                        "unit_rooms_count": 3,
                    },
                )
                server.insert(
                    db,
                    "clients",
                    {
                        "id": client_id,
                        "name": "مستأجر اختبار",
                        "phone": "90000000",
                        "email": "",
                        "national_id": "X",
                        "id_card_image": "",
                        "notes": "",
                        "balance": 0,
                    },
                )
                contract_id = server.uid("CON")
                server.insert(
                    db,
                    "contracts",
                    {
                        "id": contract_id,
                        "contract_no": "LQL-TEST-0001",
                        "contract_type": "Residential",
                        "property_id": prop_id,
                        "client_id": client_id,
                        "tenant_nationality": "OM",
                        "tenant_id_no": "X",
                        "unit_details": "B1-A9",
                        "start_date": "2026-01-01",
                        "end_date": "2026-12-31",
                        "rent_amount": 120,
                        "deposit_amount": 0,
                        "deposit_received": 0,
                        "deposit_received_at": None,
                        "deposit_received_amount": 0,
                        "late_fee": 0,
                        "grace_days": 5,
                        "renewal_notice_days": 30,
                        "status": "Draft",
                        "payment_cycle": "monthly",
                        "legal_terms": "",
                        "company_signatory": "Launch Quality LLC",
                        "approved_at": None,
                        "ended_at": None,
                        "attachments": "[]",
                        "notes": "",
                    },
                )
                user = {"id": "U1", "username": "owner", "role": "owner", "name": "Owner"}
                try:
                    server.execute_contract_activation(db, user, contract_id)
                    activate_before_approve = False
                except ValueError:
                    activate_before_approve = True
                fails += not ok("activation blocked before approve", activate_before_approve)

                server.execute_contract_approval(db, user, contract_id)
                approved = db.execute("SELECT status, approved_by FROM contracts WHERE id=?", (contract_id,)).fetchone()
                fails += not ok(
                    "contract approved_by recorded",
                    str(approved["status"]) == "Approved" and bool(approved["approved_by"]),
                    dict(approved),
                )

                created = server.execute_contract_activation(db, user, contract_id)
                activated = db.execute(
                    "SELECT status, activated_by FROM contracts WHERE id=?", (contract_id,)
                ).fetchone()
                prop = db.execute("SELECT status FROM properties WHERE id=?", (prop_id,)).fetchone()
                fails += not ok(
                    "contract activated_by recorded",
                    str(activated["status"]) == "Active" and bool(activated["activated_by"]),
                )
                fails += not ok(
                    "activate sets unit rented",
                    server.normalize_property_status(prop["status"]) == "مستأجرة",
                    prop["status"],
                )
                fails += not ok("activation creates invoices", len(created) > 0, str(len(created)))

                db.execute("UPDATE contracts SET status=?, ended_at=? WHERE id=?", ("Closed", server.now_iso(), contract_id))
                server.sync_property_status_for_contract(db, prop_id, "Closed")
                prop2 = db.execute("SELECT status FROM properties WHERE id=?", (prop_id,)).fetchone()
                fails += not ok(
                    "close sets unit vacant",
                    server.normalize_property_status(prop2["status"]) == "شاغرة",
                    prop2["status"],
                )

                db.execute("UPDATE properties SET status=? WHERE id=?", ("موقوفة", prop_id))
                db.execute("UPDATE contracts SET status=? WHERE id=?", ("Closed", contract_id))
                server.sync_property_status_for_contract(db, prop_id, "Closed")
                prop3 = db.execute("SELECT status FROM properties WHERE id=?", (prop_id,)).fetchone()
                fails += not ok(
                    "close preserves suspended",
                    server.normalize_property_status(prop3["status"]) == "موقوفة",
                    prop3["status"],
                )
                db.commit()
        finally:
            server.DATA_DIR = old_data
            server.DB_PATH = old_db
            server.BACKUP_DIR = old_backup

    # 6) Employee package policy
    pol = (ROOT / "docs" / "EMPLOYEE_PACKAGE_POLICY.md").read_text(encoding="utf-8")
    fails += not ok("employee policy forbids passwords", "password" in pol.lower() or "كلمات" in pol)

    # 7) Setup iss exists
    fails += not ok("LaunchQuality-Setup.iss exists", (ROOT / "scripts" / "LaunchQuality-Setup.iss").exists())

    # 8) Ops doc
    ops = (ROOT / "docs" / "OPS_COMPLETE_42_AR.md").read_text(encoding="utf-8")
    fails += not ok("OPS_COMPLETE doc exists", bool(ops))
    fails += not ok("OPS_COMPLETE has 42 matrix", "مصفوفة البنود الـ42" in ops and "| 42 |" in ops)

    # 9) Frontend markers
    app_js = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
    app_html = (ROOT / "public" / "app.html").read_text(encoding="utf-8")
    fails += not ok("UI disableUser present", "function disableUser" in app_js)
    fails += not ok("UI env badge present", "applyEnvModeBadge" in app_js and "lqEnvModeLabel" in app_html)
    fails += not ok("UI suspended status option", 'value="موقوفة"' in app_html or "موقوفة" in app_html)
    fails += not ok("UI araboun not insurance rent", "عربون حجز" in app_html or "عربون الحجز" in app_js)

    print("\n" + ("ALL CHECKS PASSED" if fails == 0 else f"{fails} CHECK(S) FAILED"))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
