"""
Copy عقارات نزوى (qe_*) → منصة العقارات (estate_*) as a duplicate.
Never deletes or modifies qe_* rows.
"""
from __future__ import annotations

import secrets
import sqlite3
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional


PROPERTY_MARKER = "source:nizwa_qe_portfolio"
UNIT_MARKER_PREFIX = "source:qe_unit:"
CONTRACT_MARKER_PREFIX = "source:qe_contract:"
CLIENT_MARKER_PREFIX = "source:qe_tenant:"
DEFAULT_LOCATION = "حي التراث، نزوى، محافظة الداخلية، سلطنة عمان"

STATUS_MAP = {
    "شاغرة": "vacant",
    "مؤجرة": "occupied",
    "محجوزة": "reserved",
    "صيانة": "maintenance",
    "vacant": "vacant",
    "occupied": "occupied",
    "rented": "occupied",
    "reserved": "reserved",
    "maintenance": "maintenance",
}

CONTRACT_STATUS_MAP = {
    "draft": "Draft",
    "pending": "ApprovalRequested",
    "approved": "Approved",
    "rejected": "Cancelled",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
}


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def _row_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _table_cols(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _find_by_marker(db: sqlite3.Connection, table: str, marker: str) -> Optional[sqlite3.Row]:
    cols = _table_cols(db, table)
    clauses = []
    args: list[Any] = []
    if "notes" in cols:
        clauses.append("notes LIKE ?")
        args.append(f"%{marker}%")
    if "attachments" in cols:
        clauses.append("attachments LIKE ?")
        args.append(f"%{marker}%")
    if not clauses:
        return None
    sql = f"SELECT * FROM {table} WHERE {' OR '.join(clauses)} LIMIT 1"
    return db.execute(sql, tuple(args)).fetchone()


def _map_unit_status(raw: str) -> str:
    return STATUS_MAP.get(str(raw or "").strip(), STATUS_MAP.get(str(raw or "").strip().lower(), "vacant"))


def _ensure_client(
    db: sqlite3.Connection,
    *,
    name: str,
    phone: str,
    identity_no: str,
    marker: str,
    uid_fn: Callable[[str], str],
) -> Optional[str]:
    name = str(name or "").strip()
    if not name:
        return None
    phone = str(phone or "").strip()
    identity_no = str(identity_no or "").strip()
    existing = _find_by_marker(db, "clients", marker)
    if existing:
        return str(existing["id"])
    if phone:
        by_phone = db.execute(
            "SELECT id FROM clients WHERE phone=? AND name=? LIMIT 1",
            (phone, name),
        ).fetchone()
        if by_phone:
            return str(by_phone["id"])
    if identity_no:
        by_nid = db.execute(
            "SELECT id FROM clients WHERE national_id=? AND ?<>'' LIMIT 1",
            (identity_no, identity_no),
        ).fetchone()
        if by_nid:
            return str(by_nid["id"])
    client_id = uid_fn("CLT")
    db.execute(
        """INSERT INTO clients(id, name, phone, email, national_id, balance, notes)
           VALUES(?,?,?,?,?,?,?)""",
        (
            client_id,
            name,
            phone,
            "",
            identity_no,
            0,
            f"نسخ من عقارات نزوى · {marker}",
        ),
    )
    return client_id


def _next_estate_contract_no(db: sqlite3.Connection) -> str:
    year = date.today().year
    prefix = f"EST-{year}-"
    row = db.execute(
        "SELECT MAX(CAST(substr(contract_no, -4) AS INTEGER)) FROM estate_contracts WHERE contract_no LIKE ?",
        (prefix + "%",),
    ).fetchone()[0]
    seq = int(row or 0) + 1
    return f"{prefix}{seq:04d}"


def copy_qe_to_estate(
    db: sqlite3.Connection,
    *,
    uid_fn: Optional[Callable[[str], str]] = None,
    now_fn: Optional[Callable[[], str]] = None,
    actor: str = "nizwa-copy",
) -> Dict[str, Any]:
    """
    Idempotent copy: qe_units / qe_contracts → estate_* (+ clients).
    Leaves qe_* untouched.
    """
    uid_fn = uid_fn or _uid
    now_fn = now_fn or _now
    stamp = now_fn()

    # Ensure qe tables/seed exist before copy
    try:
        from lq_quick_estate import ensure_tables

        ensure_tables(db)
    except Exception:
        pass

    qe_count = db.execute("SELECT COUNT(*) FROM qe_units").fetchone()[0]
    if qe_count == 0:
        return {"ok": False, "error": "لا توجد وحدات في عقارات نزوى للنسخ", "qe_units": 0}

    created = {
        "property": 0,
        "buildings": 0,
        "apartments": 0,
        "clients": 0,
        "contracts": 0,
        "skipped_apartments": 0,
        "skipped_contracts": 0,
    }

    prop = _find_by_marker(db, "estate_properties", PROPERTY_MARKER)
    if prop:
        property_id = str(prop["id"])
    else:
        property_id = uid_fn("EPR")
        loc_row = db.execute(
            "SELECT location_url FROM qe_units WHERE location_url IS NOT NULL AND trim(location_url)<>'' LIMIT 1"
        ).fetchone()
        location = DEFAULT_LOCATION
        if loc_row and loc_row[0]:
            location = f"{DEFAULT_LOCATION} · {loc_row[0]}"
        bld_count = db.execute("SELECT COUNT(DISTINCT building_no) FROM qe_units").fetchone()[0]
        db.execute(
            """INSERT INTO estate_properties(
                id, name, status, location, building_count, apartment_count, room_count,
                base_rent_price, service_charge, attachments, manager_name, tenant_client_id,
                tenant_phone, notes, image, last_update
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                property_id,
                "عقارات نزوى — حي التراث",
                "active",
                location,
                int(bld_count or 0),
                int(qe_count or 0),
                0,
                0,
                0,
                "[]",
                "إدارة نزوى",
                None,
                "",
                f"نسخة من منصة عقارات نزوى (qe_*) · {PROPERTY_MARKER}",
                "",
                stamp[:10],
            ),
        )
        created["property"] = 1

    building_ids: Dict[int, str] = {}
    for row in db.execute(
        "SELECT DISTINCT building_no FROM qe_units ORDER BY building_no"
    ).fetchall():
        bno = int(row[0])
        marker = f"{PROPERTY_MARKER}:building:{bno}"
        existing_b = _find_by_marker(db, "estate_buildings", marker)
        if existing_b:
            building_ids[bno] = str(existing_b["id"])
            continue
        unit_n = db.execute(
            "SELECT COUNT(*) FROM qe_units WHERE building_no=?", (bno,)
        ).fetchone()[0]
        bid = uid_fn("EBD")
        db.execute(
            """INSERT INTO estate_buildings(
                id, property_id, name, status, location, unit_count, apartment_count, room_count,
                base_rent_price, service_charge, attachments, manager_name, tenant_client_id,
                tenant_phone, description, notes, image, last_update
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                bid,
                property_id,
                f"بناية {bno}",
                "active",
                DEFAULT_LOCATION,
                int(unit_n or 0),
                int(unit_n or 0),
                0,
                0,
                0,
                "[]",
                "",
                None,
                "",
                f"نسخ من عقارات نزوى · بناية رقم {bno}",
                f"نسخ من عقارات نزوى · {marker}",
                "",
                stamp[:10],
            ),
        )
        building_ids[bno] = bid
        created["buildings"] += 1

    unit_to_apartment: Dict[int, str] = {}
    units = db.execute("SELECT * FROM qe_units ORDER BY building_no, id").fetchall()
    for u in units:
        ud = _row_dict(u)
        qe_id = int(ud["id"])
        marker = f"{UNIT_MARKER_PREFIX}{qe_id}"
        existing_a = _find_by_marker(db, "estate_apartments", marker)
        if existing_a:
            unit_to_apartment[qe_id] = str(existing_a["id"])
            created["skipped_apartments"] += 1
            continue

        bno = int(ud["building_no"])
        building_id = building_ids.get(bno)
        if not building_id:
            created["skipped_apartments"] += 1
            continue

        tenant_name = str(ud.get("tenant_name") or "").strip()
        phone = str(ud.get("phone") or "").strip()
        identity_no = str(ud.get("identity_no") or "").strip()
        client_marker = f"{CLIENT_MARKER_PREFIX}{qe_id}"
        client_id = None
        if tenant_name:
            before = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
            client_id = _ensure_client(
                db,
                name=tenant_name,
                phone=phone,
                identity_no=identity_no,
                marker=client_marker,
                uid_fn=uid_fn,
            )
            after = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
            if after > before:
                created["clients"] += 1

        status = _map_unit_status(str(ud.get("status") or ""))
        rent = float(ud.get("rent_amount") or 0) or float(ud.get("average_rent") or 0)
        apt_no = str(ud.get("apartment_no") or qe_id)
        apt_id = uid_fn("EAP")
        notes = (
            f"نسخ من عقارات نزوى · {marker} · "
            f"excel:{ud.get('original_excel_ref') or ''} · "
            f"حمام:{ud.get('bathroom') or ''} · "
            f"خدمات:{ud.get('services') or ''} · "
            f"هوية:{identity_no}"
        )
        db.execute(
            """INSERT INTO estate_apartments(
                id, property_id, building_id, name, unit_kind, status, room_count, floor_no, area_sqm,
                rent_price, booking_deposit, prepaid_amount, reservation_start_date, reservation_end_date,
                booked_client_name, booked_client_phone, booked_client_id, booked_by_employee,
                maintenance_notes, maintenance_cost, attachments, manager_name, tenant_client_id,
                tenant_phone, notes, image, last_update
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                apt_id,
                property_id,
                building_id,
                f"شقة {apt_no}",
                "شقة كاملة",
                status,
                int(ud.get("rooms_count") or 1),
                None,
                0,
                rent,
                0,
                0,
                str(ud.get("contract_start") or "") or None,
                str(ud.get("contract_end") or "") or None,
                tenant_name if status == "reserved" else "",
                phone if status == "reserved" else "",
                client_id if status == "reserved" else None,
                "",
                "",
                0,
                "[]",
                "",
                client_id,
                phone,
                notes,
                "",
                stamp[:10],
            ),
        )
        unit_to_apartment[qe_id] = apt_id
        created["apartments"] += 1

    # Refresh property counts
    db.execute(
        """UPDATE estate_properties SET
            building_count=(SELECT COUNT(*) FROM estate_buildings WHERE property_id=?),
            apartment_count=(SELECT COUNT(*) FROM estate_apartments WHERE property_id=?),
            last_update=?
           WHERE id=?""",
        (property_id, property_id, stamp[:10], property_id),
    )

    # Copy qe_contracts
    try:
        contracts = db.execute("SELECT * FROM qe_contracts ORDER BY id").fetchall()
    except sqlite3.Error:
        contracts = []

    for c in contracts:
        cd = _row_dict(c)
        qe_cid = int(cd["id"])
        marker = f"{CONTRACT_MARKER_PREFIX}{qe_cid}"
        if _find_by_marker(db, "estate_contracts", marker):
            created["skipped_contracts"] += 1
            continue
        unit_id = int(cd.get("unit_id") or 0)
        apt_id = unit_to_apartment.get(unit_id)
        if not apt_id:
            existing_apt = _find_by_marker(db, "estate_apartments", f"{UNIT_MARKER_PREFIX}{unit_id}")
            if existing_apt:
                apt_id = str(existing_apt["id"])
        if not apt_id:
            created["skipped_contracts"] += 1
            continue
        apt = db.execute("SELECT * FROM estate_apartments WHERE id=?", (apt_id,)).fetchone()
        if not apt:
            created["skipped_contracts"] += 1
            continue

        tenant_name = str(cd.get("tenant_name") or "").strip()
        phone = str(cd.get("phone") or "").strip()
        identity_no = str(cd.get("identity_no") or "").strip()
        client_id = apt["tenant_client_id"]
        if not client_id and tenant_name:
            client_id = _ensure_client(
                db,
                name=tenant_name,
                phone=phone,
                identity_no=identity_no,
                marker=f"{CLIENT_MARKER_PREFIX}contract:{qe_cid}",
                uid_fn=uid_fn,
            )
            created["clients"] += 1
        if not client_id:
            created["skipped_contracts"] += 1
            continue

        start_date = str(cd.get("start_date") or "").strip() or date.today().isoformat()
        end_date = str(cd.get("end_date") or "").strip()
        if not end_date:
            # default +1 year if missing
            try:
                y, m, d = [int(x) for x in start_date.split("-")[:3]]
                end_date = date(y + 1, m, d).isoformat()
            except Exception:
                end_date = date.today().replace(year=date.today().year + 1).isoformat()

        st = CONTRACT_STATUS_MAP.get(str(cd.get("status") or "").strip().lower(), "Draft")
        # If Nizwa marked approved and unit occupied, keep as Active for ops visibility
        unit_row = db.execute("SELECT status FROM qe_units WHERE id=?", (unit_id,)).fetchone()
        if st == "Approved" and unit_row and str(unit_row[0]) == "مؤجرة":
            st = "Active"

        rent = float(cd.get("rent_amount") or 0) or float(cd.get("average_rent") or 0)
        if rent <= 0:
            created["skipped_contracts"] += 1
            continue

        contract_no = str(cd.get("contract_no") or "").strip() or _next_estate_contract_no(db)
        # Avoid unique collision
        if db.execute("SELECT id FROM estate_contracts WHERE contract_no=?", (contract_no,)).fetchone():
            contract_no = _next_estate_contract_no(db)

        eid = uid_fn("ECT")
        db.execute(
            """INSERT INTO estate_contracts(
                id, contract_no, entity_type, entity_id, property_id, building_id, apartment_id, room_id,
                client_id, start_date, end_date, rent_amount, payment_cycle, status, created_by, created_at,
                approved_by, approved_at, activated_by, activated_at, closed_at, close_note, attachments, notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                eid,
                contract_no,
                "apartment",
                apt_id,
                apt["property_id"],
                apt["building_id"],
                apt_id,
                None,
                client_id,
                start_date,
                end_date,
                rent,
                "monthly",
                st,
                str(cd.get("created_by") or actor),
                str(cd.get("created_at") or stamp),
                cd.get("approved_by"),
                cd.get("approved_at"),
                actor if st == "Active" else None,
                stamp if st == "Active" else None,
                None,
                "",
                "[]",
                f"نسخ من عقارات نزوى · {marker} · {cd.get('notes') or ''} · {cd.get('rejection_reason') or ''}".strip(),
            ),
        )
        created["contracts"] += 1

    db.commit()
    return {
        "ok": True,
        "message": "تم نسخ بيانات عقارات نزوى إلى منصة العقارات (بدون حذف الأصلية)",
        "property_id": property_id,
        "qe_units": qe_count,
        "created": created,
    }
