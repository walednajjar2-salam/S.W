"""Nizwa Estate portal — عقارات نزوى (ported from My program / Starting_Quality_Program_v1_51)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
SEED_PATH = BASE_DIR / "public" / "quick-estate" / "seed_units.json"

VALID_STATUSES = {"شاغرة", "مؤجرة", "محجوزة", "صيانة"}
EDITABLE_UNIT_FIELDS = ("status", "tenant_name", "phone", "rent_amount", "contract_start", "contract_end", "identity_no")
LOCKED_UNIT_FIELDS = ("building_no", "apartment_no", "bathroom", "rooms_count", "average_rent", "services", "location_url")
CONTRACT_STATUS_LABELS = {
    "draft": "مسودة",
    "pending": "بانتظار الاعتماد",
    "approved": "معتمد",
    "rejected": "مرفوض",
    "cancelled": "ملغي",
}
APPROVER_ROLES = {"owner", "admin", "deputy", "manager"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS qe_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_no INTEGER NOT NULL,
            apartment_no TEXT NOT NULL,
            original_excel_ref TEXT,
            status TEXT NOT NULL,
            bathroom TEXT NOT NULL,
            rooms_count INTEGER NOT NULL,
            tenant_name TEXT,
            phone TEXT,
            average_rent REAL NOT NULL DEFAULT 0,
            rent_amount REAL NOT NULL DEFAULT 0,
            contract_start TEXT,
            contract_end TEXT,
            identity_no TEXT,
            services TEXT NOT NULL,
            location_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(building_no, apartment_no)
        );
        CREATE TABLE IF NOT EXISTS qe_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_no TEXT NOT NULL UNIQUE,
            unit_id INTEGER NOT NULL REFERENCES qe_units(id),
            tenant_name TEXT NOT NULL,
            phone TEXT,
            identity_no TEXT,
            start_date TEXT,
            end_date TEXT,
            average_rent REAL NOT NULL,
            rent_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            notes TEXT,
            created_by TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            rejection_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS qe_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            display_name TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    if db.execute("SELECT COUNT(*) FROM qe_units").fetchone()[0] == 0 and SEED_PATH.exists():
        rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for item in rows:
            db.execute(
                """INSERT INTO qe_units(
                    building_no, apartment_no, original_excel_ref, status, bathroom, rooms_count,
                    tenant_name, phone, average_rent, rent_amount, contract_start, contract_end,
                    identity_no, services, location_url, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item["building_no"],
                    str(item["apartment_no"]),
                    item.get("original_excel_ref", ""),
                    item["status"],
                    item["bathroom"],
                    item["rooms_count"],
                    item.get("tenant_name", ""),
                    item.get("phone", ""),
                    item["average_rent"],
                    item["rent_amount"],
                    item.get("contract_start", ""),
                    item.get("contract_end", ""),
                    item.get("identity_no", ""),
                    item["services"],
                    item.get("location_url", ""),
                    now_iso(),
                    now_iso(),
                ),
            )
    db.execute(
        "UPDATE qe_units SET rooms_count = CASE WHEN building_no = 4 THEN 3 ELSE 1 END "
        "WHERE rooms_count != CASE WHEN building_no = 4 THEN 3 ELSE 1 END"
    )
    db.commit()


def _audit(db: sqlite3.Connection, user: Dict[str, Any], action: str, entity_type: str, entity_id: str = "", details: Any = None) -> None:
    if isinstance(details, dict):
        details = json.dumps(details, ensure_ascii=False)
    db.execute(
        "INSERT INTO qe_audit(user_id, display_name, action, entity_type, entity_id, details, created_at) VALUES(?,?,?,?,?,?,?)",
        (
            str(user.get("id") or user.get("username") or ""),
            str(user.get("display_name") or user.get("username") or "النظام"),
            action,
            entity_type,
            str(entity_id),
            details or "",
            now_iso(),
        ),
    )


def _can_approve(user: Dict[str, Any]) -> bool:
    return str(user.get("role") or "").lower() in APPROVER_ROLES


def handle_api(
    db: sqlite3.Connection,
    method: str,
    parts: List[str],
    query: Dict[str, List[str]],
    payload: Dict[str, Any],
    user: Dict[str, Any],
    send_json: Callable[..., None],
) -> bool:
    """Handle /api/quick-estate/* routes. parts begins after 'quick-estate'."""
    ensure_tables(db)
    if not parts:
        return send_json({"ok": True, "portal": "nizwaestate", "label": "عقارات نزوى"}) or True

    head = parts[0]

    if head == "dashboard" and method == "GET":
        stats = {
            "total_units": db.execute("SELECT COUNT(*) FROM qe_units").fetchone()[0],
            "occupied": db.execute("SELECT COUNT(*) FROM qe_units WHERE status='مؤجرة'").fetchone()[0],
            "vacant": db.execute("SELECT COUNT(*) FROM qe_units WHERE status='شاغرة'").fetchone()[0],
            "reserved": db.execute("SELECT COUNT(*) FROM qe_units WHERE status='محجوزة'").fetchone()[0],
            "maintenance": db.execute("SELECT COUNT(*) FROM qe_units WHERE status='صيانة'").fetchone()[0],
            "pending_contracts": db.execute("SELECT COUNT(*) FROM qe_contracts WHERE status='pending'").fetchone()[0],
        }
        recent = db.execute("SELECT * FROM qe_audit ORDER BY id DESC LIMIT 10").fetchall()
        return send_json({"ok": True, "stats": stats, "recent": [dict(r) for r in recent]}) or True

    if head == "units" and method == "GET" and len(parts) == 1:
        rows = db.execute("SELECT * FROM qe_units ORDER BY building_no, CAST(apartment_no AS INTEGER)").fetchall()
        buildings = [r[0] for r in db.execute("SELECT DISTINCT building_no FROM qe_units ORDER BY building_no").fetchall()]
        return send_json({"ok": True, "units": [dict(r) for r in rows], "buildings": buildings}) or True

    if head == "units" and len(parts) == 2 and method == "GET":
        try:
            unit_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم الوحدة غير صحيح"}, 400) or True
        row = db.execute("SELECT * FROM qe_units WHERE id=?", (unit_id,)).fetchone()
        if not row:
            return send_json({"ok": False, "error": "الوحدة غير موجودة"}, 404) or True
        contracts = db.execute(
            "SELECT * FROM qe_contracts WHERE unit_id=? ORDER BY id DESC",
            (unit_id,),
        ).fetchall()
        return send_json({"ok": True, "unit": dict(row), "contracts": [dict(r) for r in contracts]}) or True

    if head == "units" and len(parts) == 2 and method == "POST":
        try:
            unit_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم الوحدة غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM qe_units WHERE id=?", (unit_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "الوحدة غير موجودة"}, 404) or True
        for field in LOCKED_UNIT_FIELDS:
            if field in payload and str(payload[field]) != str(current[field]):
                return send_json({"ok": False, "error": f"الحقل {field} ثابت وممنوع تغييره"}, 400) or True
        changes: Dict[str, Any] = {}
        for field in EDITABLE_UNIT_FIELDS:
            if field not in payload:
                continue
            value = payload[field]
            if field == "status":
                if value not in VALID_STATUSES:
                    return send_json({"ok": False, "error": "حالة الشقة غير صحيحة"}, 400) or True
            elif field == "rent_amount":
                try:
                    value = max(0.0, float(value or 0))
                except (ValueError, TypeError):
                    return send_json({"ok": False, "error": "مبلغ الإيجار غير صحيح"}, 400) or True
            else:
                value = str(value or "").strip()
            if str(value) != str(current[field] if current[field] is not None else ""):
                changes[field] = value
        if "tenant_name" in changes:
            if changes["tenant_name"] and "status" not in changes:
                changes["status"] = "مؤجرة"
            elif not changes["tenant_name"] and current["status"] == "مؤجرة" and "status" not in changes:
                changes["status"] = "شاغرة"
        if changes:
            set_sql = ",".join(f"{k}=?" for k in changes)
            db.execute(f"UPDATE qe_units SET {set_sql}, updated_at=? WHERE id=?", (*changes.values(), now_iso(), unit_id))
            _audit(db, user, "unit_updated", "unit", str(unit_id), changes)
            db.commit()
        row = db.execute("SELECT * FROM qe_units WHERE id=?", (unit_id,)).fetchone()
        return send_json({"ok": True, "message": "تم حفظ بيانات الوحدة دون مغادرة الصفحة", "unit": dict(row)}) or True

    if head == "contracts" and method == "GET" and len(parts) == 1:
        status = (query.get("status") or [""])[0].strip()
        params: List[Any] = []
        where = ""
        if status:
            where = " WHERE c.status=?"
            params.append(status)
        rows = db.execute(
            f"""SELECT c.*, u.building_no, u.apartment_no
                FROM qe_contracts c JOIN qe_units u ON u.id=c.unit_id
                {where} ORDER BY c.id DESC""",
            params,
        ).fetchall()
        return send_json({"ok": True, "contracts": [dict(r) for r in rows], "labels": CONTRACT_STATUS_LABELS}) or True

    if head == "contracts" and parts[1:] == ["create"] and method == "POST":
        try:
            unit_id = int(payload.get("unit_id"))
        except (ValueError, TypeError):
            return send_json({"ok": False, "error": "اختر الوحدة"}, 400) or True
        unit = db.execute("SELECT * FROM qe_units WHERE id=?", (unit_id,)).fetchone()
        if not unit:
            return send_json({"ok": False, "error": "الوحدة غير موجودة"}, 404) or True
        tenant_name = str(payload.get("tenant_name") or unit["tenant_name"] or "").strip()
        if not tenant_name:
            return send_json({"ok": False, "error": "اسم المستأجر مطلوب"}, 400) or True
        try:
            rent_amount = float(payload.get("rent_amount", unit["rent_amount"]) or 0)
        except (ValueError, TypeError):
            return send_json({"ok": False, "error": "مبلغ الإيجار غير صحيح"}, 400) or True
        seq = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM qe_contracts").fetchone()[0]
        contract_no = f"QE-{datetime.now().year}-{seq:05d}"
        creator = str(user.get("id") or user.get("username") or "user")
        cur = db.execute(
            """INSERT INTO qe_contracts(
                contract_no,unit_id,tenant_name,phone,identity_no,start_date,end_date,
                average_rent,rent_amount,status,notes,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,'draft',?,?,?,?)""",
            (
                contract_no,
                unit_id,
                tenant_name,
                str(payload.get("phone") or unit["phone"] or "").strip(),
                str(payload.get("identity_no") or unit["identity_no"] or "").strip(),
                str(payload.get("start_date") or unit["contract_start"] or "").strip(),
                str(payload.get("end_date") or unit["contract_end"] or "").strip(),
                float(unit["average_rent"]),
                rent_amount,
                str(payload.get("notes") or "").strip(),
                creator,
                now_iso(),
                now_iso(),
            ),
        )
        contract_id = cur.lastrowid
        _audit(db, user, "contract_created", "contract", str(contract_id), {"contract_no": contract_no})
        db.commit()
        contract = db.execute("SELECT * FROM qe_contracts WHERE id=?", (contract_id,)).fetchone()
        return send_json({"ok": True, "message": "تم إنشاء العقد كمسودة", "contract": dict(contract)}) or True

    if head == "contracts" and len(parts) == 3 and method == "POST":
        try:
            contract_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم العقد غير صحيح"}, 400) or True
        action = parts[2]
        contract = db.execute("SELECT * FROM qe_contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            return send_json({"ok": False, "error": "العقد غير موجود"}, 404) or True
        if action == "submit":
            if contract["status"] != "draft":
                return send_json({"ok": False, "error": "يمكن إرسال المسودات فقط"}, 400) or True
            db.execute("UPDATE qe_contracts SET status='pending', updated_at=? WHERE id=?", (now_iso(), contract_id))
            _audit(db, user, "contract_submitted", "contract", str(contract_id))
            db.commit()
            return send_json({"ok": True, "message": "أُرسل العقد للاعتماد"}) or True
        if action == "approve":
            if not _can_approve(user):
                return send_json({"ok": False, "error": "الاعتماد متاح للإدارة فقط"}, 403) or True
            if contract["status"] != "pending":
                return send_json({"ok": False, "error": "العقد ليس بانتظار الاعتماد"}, 400) or True
            approver = str(user.get("id") or user.get("username") or "")
            db.execute(
                "UPDATE qe_contracts SET status='approved', approved_by=?, approved_at=?, updated_at=? WHERE id=?",
                (approver, now_iso(), now_iso(), contract_id),
            )
            db.execute(
                """UPDATE qe_units SET tenant_name=?,phone=?,identity_no=?,contract_start=?,contract_end=?,rent_amount=?,status='مؤجرة',updated_at=? WHERE id=?""",
                (
                    contract["tenant_name"],
                    contract["phone"],
                    contract["identity_no"],
                    contract["start_date"],
                    contract["end_date"],
                    contract["rent_amount"],
                    now_iso(),
                    contract["unit_id"],
                ),
            )
            _audit(db, user, "contract_approved", "contract", str(contract_id))
            db.commit()
            return send_json({"ok": True, "message": "تم اعتماد العقد وتفعيله"}) or True
        if action == "reject":
            if not _can_approve(user):
                return send_json({"ok": False, "error": "الرفض متاح للإدارة فقط"}, 403) or True
            if contract["status"] != "pending":
                return send_json({"ok": False, "error": "العقد ليس بانتظار الاعتماد"}, 400) or True
            reason = str(payload.get("reason") or "").strip()
            if not reason:
                return send_json({"ok": False, "error": "اكتب سبب الرفض"}, 400) or True
            db.execute(
                "UPDATE qe_contracts SET status='rejected', rejection_reason=?, updated_at=? WHERE id=?",
                (reason, now_iso(), contract_id),
            )
            _audit(db, user, "contract_rejected", "contract", str(contract_id), {"reason": reason})
            db.commit()
            return send_json({"ok": True, "message": "تم رفض العقد"}) or True
        return send_json({"ok": False, "error": "إجراء غير معروف"}, 404) or True

    if head == "me" and method == "GET":
        return send_json(
            {
                "ok": True,
                "user": {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "display_name": user.get("display_name") or user.get("username"),
                    "role": user.get("role"),
                },
            }
        ) or True

    return send_json({"ok": False, "error": "المسار غير موجود"}, 404) or True
