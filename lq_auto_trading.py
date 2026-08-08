"""Al-Najjar & Al-Sumoom Auto Trading — النجار والسموم لتجارة واستيراد السيارات."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
# Reference catalogue of the office vehicles. It holds VINs, licence numbers and
# previous-owner details, so it lives outside public/ and reaches visitors only
# through the filtered showroom feed.
SEED_PATH = BASE_DIR / "reference" / "seed_vehicles.json"
_LEGACY_SEED_PATH = BASE_DIR / "public" / "auto-trading" / "seed_vehicles.json"
if not SEED_PATH.exists() and _LEGACY_SEED_PATH.exists():
    SEED_PATH = _LEGACY_SEED_PATH

COMPANY_PROFILE: Dict[str, Any] = {
    "name_ar": "النجار والسموم للتجارة — سيارات مستعملة ومستوردة",
    "name_en": "NAJJAR & AL SAMOOM TRADING",
    "tagline_en": "USED & IMPORTED CARS",
    "bank_account_name_en": "Al Najjar Trading",
    "activity_ar": "تجارة واستيراد السيارات — مستعمل ومستورد",
    "activity_en": "Used & imported cars",
    "motto_ar": "سيارتك بثقة — من الاستيراد إلى التسليم",
    "address_ar": "محافظة الداخلية — نزوى — الفلج",
    "address_en": "Al-Dakhilia Governorate · Nizwa · Falaj",
    "country_ar": "سلطنة عُمان",
    "hours": "08:00 — 20:00",
    # Printed on contracts, invoices and vouchers when filled in. A VAT number
    # is what turns the sales invoice into a tax invoice, so it stays blank
    # until the company is actually registered for VAT.
    "cr_no": "",
    "vat_no": "",
    "vat_rate": 5.0,
    "logo_url": "/auto-trading/assets/logo-official-clear.png",
    "logo_mark_url": "/auto-trading/assets/logo-mark.png",
    "logo_card_url": "/auto-trading/assets/logo-official.png",
    "phones": {
        "owner": "71924089",
        "whatsapp_1": "71924089",
        "whatsapp_2": "93391994",
        "hamad": "77548482",
        "hamad_intl": "+96877548482",
        "office": "95551994",
    },
    "contacts": [
        {"label_ar": "وليد — واتساب", "phone": "71924089", "note": "+968 71924089", "whatsapp": True},
        {"label_ar": "المبيعات — واتساب", "phone": "93391994", "note": "+968 93391994", "whatsapp": True},
        {"label_ar": "حمد", "phone": "77548482", "note": "+968 7754 8482"},
        {"label_ar": "المكتب", "phone": "95551994", "note": "+968 9555 1994"},
    ],
    "bank": {
        "name_ar": "بنك صحار الدولي",
        "name_en": "Sohar International Bank",
        "account_name_en": "Al Najjar Trading",
        "account_number": "234020022484",
        "swift": "BSHROMRUXXX",
        "iban": "OM070300000234020022484",
    },
    "staff": [
        {"name_ar": "وليد النجار", "username": "waleed.najjar", "role": "owner", "role_ar": "مجلس إدارة", "phone": "71924089", "password_hint": "1"},
        {"name_ar": "حمد السموم", "username": "hamad.sumoom", "role": "owner", "role_ar": "مجلس إدارة", "phone": "77548482", "password_hint": "2"},
        {"name_ar": "ساره", "username": "sara", "role": "operations", "role_ar": "تشغيل", "phone": "", "password_hint": "3"},
        {"name_ar": "مبيعات", "username": "sales", "role": "sales", "role_ar": "مبيعات", "phone": "", "password_hint": "4"},
        {"name_ar": "محاسبة", "username": "accounting", "role": "accountant", "role_ar": "محاسبة", "phone": "", "password_hint": "5"},
    ],
    "partners": [
        {
            "code": "waleed",
            "name_ar": "وليد النجار",
            "username": "waleed.najjar",
            "phone": "71924089",
            "ownership_pct": 50.0,
        },
        {
            "code": "hamad",
            "name_ar": "حمد السموم",
            "username": "hamad.sumoom",
            "phone": "77548482",
            "ownership_pct": 50.0,
        },
    ],
    "platforms": [
        {"id": "america", "label_ar": "USA", "icon": "🇺🇸", "kind": "auctions", "tags": ["Copart", "IAAI"]},
        {"id": "salam", "label_ar": "SALAM TRADING", "icon": "🚗", "kind": "partner"},
        {"id": "oman", "label_ar": "عُمان", "icon": "🇴🇲", "kind": "inventory"},
        {"id": "dubai", "label_ar": "دبي", "icon": "🇦🇪", "kind": "import"},
        {"id": "jordan", "label_ar": "الأردن", "icon": "🇯🇴", "kind": "import"},
        {"id": "iran", "label_ar": "إيران", "icon": "🇮🇷", "kind": "import"},
        {"id": "india", "label_ar": "الهند", "icon": "🇮🇳", "kind": "import"},
        {"id": "saudi", "label_ar": "السعودية", "icon": "🇸🇦", "kind": "import"},
    ],
}

VALID_STATUSES = {"متاحة", "محجوزة", "مباعة", "قيد الاستيراد", "صيانة"}
EDITABLE_VEHICLE_FIELDS = (
    "status", "list_price", "purchase_cost", "plate_no", "license_valid_until",
    "insurance_company", "insurance_policy", "insurance_type", "buyer_name", "buyer_phone",
    "import_ref", "origin_country", "notes", "reserved_by", "reserved_until",
    "seller_name", "seller_phone", "seller_id", "purchase_date", "photos",
)
LOCKED_VEHICLE_FIELDS = ("stock_no", "make", "model", "variant", "vin", "engine_no", "year")
EXPENSE_CATEGORIES = (
    "شحن واستيراد", "جمارك وترخيص", "صيانة وتجهيز", "تنظيف وتجميل", "عمولات ووسطاء",
    "إيجار ومكتب", "رواتب", "وقود وتنقل", "تأمين", "أخرى",
)
CAPITAL_ENTRY_TYPES = {
    "opening": "مساهمة افتتاحية",
    "contribution": "زيادة رأس مال",
    "withdrawal": "سحب من رأس المال",
    "distribution": "توزيع أرباح",
    "adjustment": "تسوية",
}
DEFAULT_PARTNERS = (
    {
        "code": "waleed",
        "name_ar": "وليد النجار",
        "username": "waleed.najjar",
        "phone": "71924089",
        "ownership_pct": 50.0,
    },
    {
        "code": "hamad",
        "name_ar": "حمد السموم",
        "username": "hamad.sumoom",
        "phone": "77548482",
        "ownership_pct": 50.0,
    },
)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


# Databases whose reference catalogue has already been seeded in this process.
_BOOTSTRAPPED_DBS: set[str] = set()


def _db_path(db: sqlite3.Connection) -> str:
    try:
        for _, name, file in db.execute("PRAGMA database_list").fetchall():
            if name == "main":
                return str(file or ":memory:")
    except sqlite3.Error:
        pass
    return ":memory:"


def _ensure_vehicle_columns(db: sqlite3.Connection) -> None:
    for col, typ in (
        ("first_registration", "TEXT"),
        ("license_doc_no", "TEXT"),
        ("insurance_type", "TEXT"),
        ("license_source", "TEXT"),
        ("mortgage", "TEXT"),
        ("sort_order", "INTEGER NOT NULL DEFAULT 999"),
        ("seller_name", "TEXT"),
        ("seller_phone", "TEXT"),
        ("seller_id", "TEXT"),
        ("purchase_date", "TEXT"),
        ("photos", "TEXT"),
        ("price_usd", "REAL NOT NULL DEFAULT 0"),
    ):
        try:
            db.execute(f"ALTER TABLE at_vehicles ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass


def _vehicle_row_from_seed(item: Dict[str, Any]) -> Dict[str, Any]:
    photos = item.get("photos") or item.get("images") or []
    if isinstance(photos, str):
        photos_json = photos
    else:
        photos_json = json.dumps(list(photos), ensure_ascii=False)
    return {
        "stock_no": item["stock_no"],
        "make": item["make"],
        "model": item["model"],
        "variant": item.get("variant", ""),
        "vehicle_type": item.get("vehicle_type", ""),
        "color": item.get("color", ""),
        "year": item.get("year"),
        "vin": item.get("vin", ""),
        "engine_no": item.get("engine_no", ""),
        "engine_cc": item.get("engine_cc", ""),
        "seats": item.get("seats"),
        "axles": item.get("axles"),
        "origin_country": item.get("origin_country", ""),
        "import_ref": item.get("import_ref", ""),
        "purchase_cost": float(item.get("purchase_cost") or 0),
        "list_price": float(item.get("list_price") or 0),
        "price_usd": float(item.get("price_usd") or 0),
        "status": item.get("status", "متاحة"),
        "plate_no": item.get("plate_no", ""),
        "license_valid_until": item.get("license_valid_until", ""),
        "first_registration": item.get("first_registration", ""),
        "license_doc_no": item.get("license_doc_no", ""),
        "insurance_company": item.get("insurance_company", ""),
        "insurance_policy": item.get("insurance_policy", ""),
        "insurance_type": item.get("insurance_type", ""),
        "license_source": item.get("license_source", ""),
        "mortgage": item.get("mortgage", ""),
        "notes": item.get("notes", ""),
        "photos": photos_json,
        "sort_order": int(item["sort_order"]) if item.get("sort_order") is not None else 999,
    }


# Columns the seed file owns. Everything else (status, prices, plate, insurance,
# buyer/seller, notes…) belongs to the staff and must survive a re-sync.
SEED_REFRESHABLE_COLUMNS = (
    "stock_no", "make", "model", "variant", "vehicle_type", "color", "year", "vin",
    "engine_no", "engine_cc", "seats", "axles", "first_registration", "license_doc_no",
    "license_source", "photos", "sort_order", "notes",
)


def sync_seed_vehicles(db: sqlite3.Connection) -> None:
    """Insert reference vehicles from the seed file and refresh their spec sheet.

    Operational fields edited in the portal are never overwritten: the seed is a
    catalogue of specifications, not a source of truth for stock state or pricing.
    """
    if not SEED_PATH.exists():
        return
    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        return
    seed_stocks = {str(r.get("stock_no") or "") for r in rows if r.get("stock_no")}
    for idx, item in enumerate(rows, start=1):
        if not item.get("stock_no") or not item.get("make") or not item.get("model"):
            continue
        if item.get("sort_order") is None:
            item["sort_order"] = idx
        row = _vehicle_row_from_seed(item)
        existing = None
        if row["vin"]:
            existing = db.execute("SELECT id, stock_no FROM at_vehicles WHERE vin=?", (row["vin"],)).fetchone()
        if not existing:
            existing = db.execute(
                "SELECT id, stock_no FROM at_vehicles WHERE stock_no=?",
                (row["stock_no"],),
            ).fetchone()
        if existing:
            sets = ", ".join(f"{col}=?" for col in SEED_REFRESHABLE_COLUMNS)
            db.execute(
                f"UPDATE at_vehicles SET {sets}, updated_at=? WHERE id=?",
                (
                    *(row[col] for col in SEED_REFRESHABLE_COLUMNS),
                    now_iso(), existing[0],
                ),
            )
            if item.get("pin_price"):
                db.execute(
                    "UPDATE at_vehicles SET list_price=?, price_usd=?, updated_at=? WHERE id=?",
                    (row["list_price"], row["price_usd"], now_iso(), existing[0]),
                )
        else:
            db.execute(
                """INSERT INTO at_vehicles(
                    stock_no, make, model, variant, vehicle_type, color, year, vin, engine_no,
                    engine_cc, seats, axles, origin_country, import_ref, purchase_cost, list_price, price_usd,
                    status, plate_no, license_valid_until, first_registration, license_doc_no,
                    insurance_company, insurance_policy, insurance_type, license_source, mortgage, notes,
                    photos, sort_order, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["stock_no"], row["make"], row["model"], row["variant"], row["vehicle_type"], row["color"],
                    row["year"], row["vin"], row["engine_no"], row["engine_cc"], row["seats"], row["axles"],
                    row["origin_country"], row["import_ref"], row["purchase_cost"], row["list_price"], row["price_usd"],
                    row["status"], row["plate_no"], row["license_valid_until"], row["first_registration"],
                    row["license_doc_no"], row["insurance_company"], row["insurance_policy"], row["insurance_type"],
                    row["license_source"], row["mortgage"], row["notes"], row["photos"], row["sort_order"],
                    now_iso(), now_iso(),
                ),
            )
    # One-off removal of the pre-launch demo stock (AT-001…AT-005). Only rows that
    # were never traded are dropped, and never anything the staff created later.
    demo_stocks = ("AT-001", "AT-002", "AT-003", "AT-004", "AT-005")
    for code in demo_stocks:
        if code in seed_stocks:
            continue
        db.execute(
            """DELETE FROM at_vehicles WHERE stock_no=? AND lower(status) NOT IN ('مباعة','sold')
               AND id NOT IN (SELECT vehicle_id FROM at_sales WHERE vehicle_id IS NOT NULL)
               AND id NOT IN (SELECT vehicle_id FROM at_purchases WHERE vehicle_id IS NOT NULL)""",
            (code,),
        )
    db.commit()


def ensure_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS at_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_no TEXT NOT NULL UNIQUE,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            variant TEXT,
            vehicle_type TEXT,
            color TEXT,
            year INTEGER,
            vin TEXT,
            engine_no TEXT,
            engine_cc TEXT,
            seats INTEGER,
            axles INTEGER,
            origin_country TEXT,
            import_ref TEXT,
            purchase_cost REAL NOT NULL DEFAULT 0,
            list_price REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'متاحة',
            plate_no TEXT,
            license_valid_until TEXT,
            insurance_company TEXT,
            insurance_policy TEXT,
            buyer_name TEXT,
            buyer_phone TEXT,
            reserved_by TEXT,
            reserved_until TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_import_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            origin_country TEXT NOT NULL,
            supplier TEXT,
            vehicle_count INTEGER NOT NULL DEFAULT 1,
            total_cost REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'قيد الشحن',
            eta_date TEXT,
            arrival_date TEXT,
            notes TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_no TEXT NOT NULL UNIQUE,
            vehicle_id INTEGER NOT NULL REFERENCES at_vehicles(id),
            stock_no TEXT NOT NULL,
            buyer_name TEXT NOT NULL,
            buyer_phone TEXT,
            buyer_id TEXT,
            sale_price REAL NOT NULL,
            deposit_amount REAL NOT NULL DEFAULT 0,
            payment_method TEXT,
            sale_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'مكتمل',
            notes TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_no TEXT NOT NULL UNIQUE,
            vehicle_id INTEGER REFERENCES at_vehicles(id),
            stock_no TEXT,
            seller_name TEXT NOT NULL,
            seller_phone TEXT,
            seller_id TEXT,
            source_country TEXT,
            purchase_price REAL NOT NULL DEFAULT 0,
            paid_amount REAL NOT NULL DEFAULT 0,
            payment_method TEXT,
            purchase_date TEXT NOT NULL,
            notes TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_no TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            vehicle_id INTEGER REFERENCES at_vehicles(id),
            stock_no TEXT,
            amount REAL NOT NULL DEFAULT 0,
            payee TEXT,
            expense_date TEXT NOT NULL,
            payment_method TEXT,
            notes TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            display_name TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name_ar TEXT NOT NULL,
            username TEXT,
            phone TEXT,
            ownership_pct REAL NOT NULL DEFAULT 50,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_capital_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_no TEXT NOT NULL UNIQUE,
            partner_id INTEGER NOT NULL REFERENCES at_partners(id),
            entry_type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            entry_date TEXT NOT NULL,
            method TEXT,
            reference_no TEXT,
            notes TEXT,
            distribution_id INTEGER,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS at_capital_distributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dist_no TEXT NOT NULL UNIQUE,
            period_label TEXT,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'مسودة',
            dist_date TEXT NOT NULL,
            paid_at TEXT,
            notes TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    _ensure_vehicle_columns(db)
    path = _db_path(db)
    if path not in _BOOTSTRAPPED_DBS:
        sync_seed_vehicles(db)
        _BOOTSTRAPPED_DBS.add(path)
    _ensure_partners(db)


def _audit(db: sqlite3.Connection, user: Dict[str, Any], action: str, entity_type: str, entity_id: str = "", details: Any = None) -> None:
    if isinstance(details, dict):
        details = json.dumps(details, ensure_ascii=False)
    db.execute(
        "INSERT INTO at_audit(user_id, display_name, action, entity_type, entity_id, details, created_at) VALUES(?,?,?,?,?,?,?)",
        (
            str(user.get("id") or user.get("username") or ""),
            str(user.get("display_name") or user.get("name") or user.get("username") or "النظام"),
            action,
            entity_type,
            str(entity_id),
            details or "",
            now_iso(),
        ),
    )


def _next_doc_no(db: sqlite3.Connection, table: str, column: str, letter: str) -> str:
    """Sequence document numbers from the highest issued number of the year.

    Counting rows would re-issue a number as soon as one is removed, and the
    document tables reject duplicates.
    """
    year = datetime.now().year
    prefix = f"AT-{letter}-{year}-"
    last = db.execute(
        f"SELECT MAX(CAST(substr({column}, ?) AS INTEGER)) FROM {table} WHERE {column} LIKE ?",
        (len(prefix) + 1, prefix + "%"),
    ).fetchone()[0]
    return f"{prefix}{int(last or 0) + 1:04d}"


def _next_sale_no(db: sqlite3.Connection) -> str:
    return _next_doc_no(db, "at_sales", "sale_no", "S")


def _next_import_no(db: sqlite3.Connection) -> str:
    return _next_doc_no(db, "at_import_orders", "order_no", "I")


def _next_purchase_no(db: sqlite3.Connection) -> str:
    return _next_doc_no(db, "at_purchases", "purchase_no", "P")


def _next_expense_no(db: sqlite3.Connection) -> str:
    return _next_doc_no(db, "at_expenses", "expense_no", "E")


def _next_capital_entry_no(db: sqlite3.Connection) -> str:
    return _next_doc_no(db, "at_capital_entries", "entry_no", "C")


def _next_distribution_no(db: sqlite3.Connection) -> str:
    return _next_doc_no(db, "at_capital_distributions", "dist_no", "D")


def _ensure_partners(db: sqlite3.Connection) -> None:
    for p in DEFAULT_PARTNERS:
        existing = db.execute("SELECT id FROM at_partners WHERE code=?", (p["code"],)).fetchone()
        if existing:
            db.execute(
                """UPDATE at_partners SET name_ar=?, username=?, phone=?, ownership_pct=?, active=1, updated_at=?
                   WHERE code=?""",
                (
                    p["name_ar"], p["username"], p["phone"], float(p["ownership_pct"]),
                    now_iso(), p["code"],
                ),
            )
        else:
            db.execute(
                """INSERT INTO at_partners(code, name_ar, username, phone, ownership_pct, active, notes, created_at, updated_at)
                   VALUES(?,?,?,?,?,1,'',?,?)""",
                (
                    p["code"], p["name_ar"], p["username"], p["phone"], float(p["ownership_pct"]),
                    now_iso(), now_iso(),
                ),
            )
    db.commit()


def _partner_capital_balance(db: sqlite3.Connection, partner_id: int) -> float:
    """Capital in company: contributions minus withdrawals. Profit distributions tracked separately."""
    row = db.execute(
        """SELECT COALESCE(SUM(
               CASE
                 WHEN entry_type IN ('opening','contribution','adjustment') THEN amount
                 WHEN entry_type='withdrawal' THEN -amount
                 ELSE 0
               END
           ), 0) AS bal
           FROM at_capital_entries WHERE partner_id=?""",
        (partner_id,),
    ).fetchone()
    return float(row["bal"] if row else 0)


def _partner_distributions_total(db: sqlite3.Connection, partner_id: int) -> float:
    row = db.execute(
        """SELECT COALESCE(SUM(amount),0) AS tot FROM at_capital_entries
           WHERE partner_id=? AND entry_type='distribution'""",
        (partner_id,),
    ).fetchone()
    return float(row["tot"] if row else 0)


def _profit_summary(db: sqlite3.Connection) -> Dict[str, Any]:
    """Trading result on a cost-of-sales basis.

    Subtracting every purchase from every sale reports a loss for each car still
    standing in the showroom, and pure profit for a car bought last season. Only
    the cost of the cars actually sold belongs against their sale price; what is
    spent on unsold stock stays in inventory until it leaves the yard.
    """
    sales_total = float(db.execute("SELECT COALESCE(SUM(sale_price),0) FROM at_sales").fetchone()[0])
    cost_of_sales = float(db.execute(
        """SELECT COALESCE(SUM(v.purchase_cost),0) FROM at_vehicles v
           WHERE v.id IN (SELECT vehicle_id FROM at_sales WHERE vehicle_id IS NOT NULL)"""
    ).fetchone()[0])
    expenses_on_sold = float(db.execute(
        """SELECT COALESCE(SUM(amount),0) FROM at_expenses
           WHERE vehicle_id IN (SELECT vehicle_id FROM at_sales WHERE vehicle_id IS NOT NULL)"""
    ).fetchone()[0])
    overhead = float(db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM at_expenses WHERE vehicle_id IS NULL"
    ).fetchone()[0])
    inventory_cost = float(db.execute(
        """SELECT COALESCE(SUM(v.purchase_cost),0) FROM at_vehicles v
           WHERE v.id NOT IN (SELECT vehicle_id FROM at_sales WHERE vehicle_id IS NOT NULL)"""
    ).fetchone()[0])
    inventory_expenses = float(db.execute(
        """SELECT COALESCE(SUM(amount),0) FROM at_expenses
           WHERE vehicle_id IS NOT NULL
             AND vehicle_id NOT IN (SELECT vehicle_id FROM at_sales WHERE vehicle_id IS NOT NULL)"""
    ).fetchone()[0])
    gross_profit = sales_total - cost_of_sales - expenses_on_sold
    return {
        "sales_total": sales_total,
        "cost_of_sales": cost_of_sales,
        "expenses_on_sold": expenses_on_sold,
        "overhead": overhead,
        "gross_profit": gross_profit,
        "net_profit": gross_profit - overhead,
        "inventory_cost": inventory_cost + inventory_expenses,
    }


def _capital_summary(db: sqlite3.Connection) -> Dict[str, Any]:
    partners = [dict(r) for r in db.execute(
        "SELECT * FROM at_partners WHERE active=1 ORDER BY id ASC"
    ).fetchall()]
    for p in partners:
        pid = int(p["id"])
        p["capital_balance"] = _partner_capital_balance(db, pid)
        p["distributions_total"] = _partner_distributions_total(db, pid)
        p["ownership_pct"] = float(p.get("ownership_pct") or 0)
    total_capital = sum(float(p["capital_balance"]) for p in partners)
    total_contrib = float(db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM at_capital_entries WHERE entry_type IN ('opening','contribution')"
    ).fetchone()[0])
    total_withdrawals = float(db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM at_capital_entries WHERE entry_type='withdrawal'"
    ).fetchone()[0])
    total_distributed = float(db.execute(
        "SELECT COALESCE(SUM(total_amount),0) FROM at_capital_distributions WHERE status IN ('معتمد','مدفوع')"
    ).fetchone()[0])
    profit = _profit_summary(db)
    return {
        "partners": partners,
        "total_capital": total_capital,
        "total_contributions": total_contrib,
        "total_withdrawals": total_withdrawals,
        "total_distributed": total_distributed,
        # The whole chain travels together: a partner shown a gross profit he
        # cannot subtract back to the sale price does not trust the number.
        "sales_total": profit["sales_total"],
        "gross_profit": profit["gross_profit"],
        "net_profit": profit["net_profit"],
        "cost_of_sales": profit["cost_of_sales"],
        "expenses_on_sold": profit["expenses_on_sold"],
        "overhead": profit["overhead"],
        "inventory_cost": profit["inventory_cost"],
        "distributable_estimate": max(0.0, profit["net_profit"] - total_distributed),
        "entry_types": CAPITAL_ENTRY_TYPES,
    }


# Vehicle details the printed contracts, invoices and vouchers identify the car by.
DOC_VEHICLE_FIELDS = (
    "make", "model", "variant", "color", "year", "vehicle_type",
    "vin", "engine_no", "engine_cc", "plate_no", "origin_country", "import_ref",
)


def with_doc_vehicle(row: Dict[str, Any], vehicle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Attach the vehicle identity to a sale or purchase for immediate printing.

    Only fields the transaction itself does not carry are copied, so a record's
    own buyer, notes and stock number are never shadowed by the vehicle's.
    """
    out = dict(row)
    for key in DOC_VEHICLE_FIELDS:
        if vehicle and key not in out:
            out[key] = vehicle.get(key)
    return out


# Fields a visitor may see. Costs, buyer/seller identities and internal notes stay private.
PUBLIC_VEHICLE_FIELDS = (
    "id", "stock_no", "make", "model", "variant", "vehicle_type", "color", "year",
    "vin", "engine_cc", "seats", "axles", "origin_country", "status", "sort_order",
    "first_registration", "license_valid_until", "plate_no", "import_ref", "notes",
)
PUBLIC_STATUSES = ("متاحة", "محجوزة", "قيد الاستيراد")


def public_company_card() -> Dict[str, Any]:
    """Branding and contact details for visitors — no staff or partner records."""
    keys = (
        "name_ar", "name_en", "tagline_en", "activity_ar", "motto_ar", "address_ar",
        "address_en", "country_ar", "hours", "logo_url", "logo_mark_url", "contacts", "bank",
    )
    return {key: COMPANY_PROFILE.get(key) for key in keys}


def public_showroom(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Vehicles offered to visitors, with only the public half of each record.

    Prices are published for cars standing in the showroom. A car still on the
    water carries its landed cost, not a retail price, so it is quoted on request.
    """
    ensure_tables(db)
    placeholders = ",".join("?" for _ in PUBLIC_STATUSES)
    rows = db.execute(
        f"SELECT * FROM at_vehicles WHERE status IN ({placeholders}) ORDER BY sort_order ASC, stock_no ASC",
        PUBLIC_STATUSES,
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        public = {key: item.get(key) for key in PUBLIC_VEHICLE_FIELDS}
        photos = item.get("photos")
        if isinstance(photos, str) and photos.strip():
            try:
                photos = json.loads(photos)
            except json.JSONDecodeError:
                photos = [photos]
        public["photos"] = photos if isinstance(photos, list) else []
        on_the_way = item.get("status") == "قيد الاستيراد"
        public["list_price"] = 0 if on_the_way else float(item.get("list_price") or 0)
        public["price_usd"] = 0 if on_the_way else float(item.get("price_usd") or 0)
        public["price_on_request"] = bool(on_the_way or public["list_price"] <= 0)
        out.append(public)
    return out


def _vehicle_photos_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(p).strip() for p in parsed if str(p).strip()]
        except json.JSONDecodeError:
            return [raw.strip()]
    return []


def _photos_json(raw: Any) -> str:
    return json.dumps(_vehicle_photos_list(raw), ensure_ascii=False)


def _save_vehicle_photo_file(vehicle_id: int, payload: Dict[str, Any]) -> str:
    from server import MAX_PROPERTY_PHOTO_BYTES, decode_upload_payload, save_named_image_upload

    file_bytes, content_type = decode_upload_payload(payload)
    return save_named_image_upload(
        "auto-trading/vehicles",
        f"vehicle-{vehicle_id}",
        file_bytes,
        content_type,
        MAX_PROPERTY_PHOTO_BYTES,
    )


def handle_api(
    db: sqlite3.Connection,
    method: str,
    parts: List[str],
    query: Dict[str, List[str]],
    payload: Dict[str, Any],
    user: Dict[str, Any],
    send_json: Callable[..., None],
) -> bool:
    """Handle /api/auto-trading/* routes. parts begins after 'auto-trading'."""
    ensure_tables(db)
    if not parts:
        return send_json({
            "ok": True,
            "portal": "autotrading",
            "label": COMPANY_PROFILE["name_ar"],
            "company": COMPANY_PROFILE,
        }) or True

    head = parts[0]

    if head == "company" and method == "GET":
        return send_json({"ok": True, "company": COMPANY_PROFILE}) or True

    if head == "dashboard" and method == "GET":
        stats = {
            "total_vehicles": db.execute("SELECT COUNT(*) FROM at_vehicles").fetchone()[0],
            "available": db.execute("SELECT COUNT(*) FROM at_vehicles WHERE status='متاحة'").fetchone()[0],
            "reserved": db.execute("SELECT COUNT(*) FROM at_vehicles WHERE status='محجوزة'").fetchone()[0],
            "sold": db.execute("SELECT COUNT(*) FROM at_vehicles WHERE status='مباعة'").fetchone()[0],
            "importing": db.execute("SELECT COUNT(*) FROM at_vehicles WHERE status='قيد الاستيراد'").fetchone()[0],
            "service": db.execute("SELECT COUNT(*) FROM at_vehicles WHERE status='صيانة'").fetchone()[0],
            "stock_value": db.execute(
                "SELECT COALESCE(SUM(list_price),0) FROM at_vehicles WHERE status IN ('متاحة','محجوزة')"
            ).fetchone()[0],
            "sales_count": db.execute("SELECT COUNT(*) FROM at_sales").fetchone()[0],
            "sales_total": db.execute("SELECT COALESCE(SUM(sale_price),0) FROM at_sales").fetchone()[0],
            "pending_imports": db.execute(
                "SELECT COUNT(*) FROM at_import_orders WHERE status NOT IN ('مستلم','ملغي')"
            ).fetchone()[0],
            "purchases_count": db.execute("SELECT COUNT(*) FROM at_purchases").fetchone()[0],
            "purchases_total": db.execute("SELECT COALESCE(SUM(purchase_price),0) FROM at_purchases").fetchone()[0],
            "expenses_count": db.execute("SELECT COUNT(*) FROM at_expenses").fetchone()[0],
            "expenses_total": db.execute("SELECT COALESCE(SUM(amount),0) FROM at_expenses").fetchone()[0],
        }
        profit = _profit_summary(db)
        stats["cost_of_sales"] = profit["cost_of_sales"]
        stats["expenses_on_sold"] = profit["expenses_on_sold"]
        stats["gross_profit"] = profit["gross_profit"]
        stats["net_profit"] = profit["net_profit"]
        stats["overhead"] = profit["overhead"]
        stats["inventory_cost"] = profit["inventory_cost"]
        capital = _capital_summary(db)
        stats["total_capital"] = capital["total_capital"]
        stats["total_distributed"] = capital["total_distributed"]
        stats["distributable_estimate"] = capital["distributable_estimate"]
        stats["partners"] = capital["partners"]
        today = datetime.now().strftime("%Y-%m-%d")
        stats["today_purchases"] = db.execute(
            "SELECT COUNT(*) FROM at_purchases WHERE purchase_date=?", (today,)
        ).fetchone()[0]
        stats["today_sales"] = db.execute(
            "SELECT COUNT(*) FROM at_sales WHERE sale_date=?", (today,)
        ).fetchone()[0]
        stats["today_expenses"] = db.execute(
            "SELECT COUNT(*) FROM at_expenses WHERE expense_date=?", (today,)
        ).fetchone()[0]
        recent = db.execute("SELECT * FROM at_audit ORDER BY id DESC LIMIT 12").fetchall()
        return send_json({"ok": True, "stats": stats, "recent": [dict(r) for r in recent], "company": COMPANY_PROFILE, "capital": capital}) or True

    if head == "vehicles" and method == "GET" and len(parts) == 1:
        status_filter = (query.get("status") or [""])[0].strip()
        make_filter = (query.get("make") or [""])[0].strip()
        search_q = (query.get("q") or [""])[0].strip().lower()
        sql = "SELECT * FROM at_vehicles WHERE 1=1"
        params: List[Any] = []
        if status_filter:
            sql += " AND status=?"
            params.append(status_filter)
        if make_filter:
            sql += " AND make=?"
            params.append(make_filter)
        if search_q:
            like = f"%{search_q}%"
            sql += (
                " AND (lower(stock_no) LIKE ? OR lower(make) LIKE ? OR lower(model) LIKE ?"
                " OR lower(variant) LIKE ? OR lower(vin) LIKE ? OR lower(plate_no) LIKE ?"
                " OR lower(notes) LIKE ? OR lower(seller_name) LIKE ? OR lower(buyer_name) LIKE ?)"
            )
            params.extend([like] * 9)
        sql += " ORDER BY sort_order ASC, stock_no ASC"
        rows = db.execute(sql, params).fetchall()
        makes = [r[0] for r in db.execute("SELECT DISTINCT make FROM at_vehicles ORDER BY make").fetchall()]
        return send_json({"ok": True, "vehicles": [dict(r) for r in rows], "makes": makes}) or True

    if head == "vehicles" and len(parts) == 2 and method == "GET":
        try:
            vehicle_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم المركبة غير صحيح"}, 400) or True
        row = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not row:
            return send_json({"ok": False, "error": "المركبة غير موجودة"}, 404) or True
        sales = db.execute("SELECT * FROM at_sales WHERE vehicle_id=? ORDER BY id DESC", (vehicle_id,)).fetchall()
        return send_json({"ok": True, "vehicle": dict(row), "sales": [dict(r) for r in sales]}) or True

    if head == "vehicles" and len(parts) == 2 and method == "POST":
        try:
            vehicle_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم المركبة غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "المركبة غير موجودة"}, 404) or True
        cur = dict(current)
        for field in LOCKED_VEHICLE_FIELDS:
            if field in payload and str(payload[field]) != str(cur.get(field) or ""):
                return send_json({"ok": False, "error": f"الحقل {field} ثابت وممنوع تغييره"}, 400) or True
        updates: Dict[str, Any] = {}
        for field in EDITABLE_VEHICLE_FIELDS:
            if field in payload:
                val = payload[field]
                if field == "status" and val not in VALID_STATUSES:
                    return send_json({"ok": False, "error": "حالة غير صالحة"}, 400) or True
                if field in ("list_price", "purchase_cost"):
                    val = float(val or 0)
                if field == "photos":
                    val = _photos_json(val)
                updates[field] = val
        if not updates:
            return send_json({"ok": False, "error": "لا توجد حقول للتحديث"}, 400) or True
        sets = ", ".join(f"{k}=?" for k in updates)
        db.execute(
            f"UPDATE at_vehicles SET {sets}, updated_at=? WHERE id=?",
            (*updates.values(), now_iso(), vehicle_id),
        )
        _audit(db, user, "vehicle_updated", "vehicle", str(vehicle_id), updates)
        db.commit()
        row = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        return send_json({"ok": True, "vehicle": dict(row)}) or True

    if head == "vehicles" and len(parts) == 3 and parts[2] == "photos" and method == "POST":
        try:
            vehicle_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم المركبة غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "المركبة غير موجودة"}, 404) or True
        upload = payload.get("upload") or payload
        if not isinstance(upload, dict) or not (upload.get("image") or upload.get("data") or upload.get("base64")):
            return send_json({"ok": False, "error": "لم يتم إرسال صورة"}, 400) or True
        try:
            url = _save_vehicle_photo_file(vehicle_id, upload)
        except ValueError as exc:
            return send_json({"ok": False, "error": str(exc)}, 400) or True
        photos = _vehicle_photos_list(dict(current).get("photos"))
        if url not in photos:
            photos.append(url)
        db.execute(
            "UPDATE at_vehicles SET photos=?, updated_at=? WHERE id=?",
            (_photos_json(photos), now_iso(), vehicle_id),
        )
        _audit(db, user, "vehicle_photo_added", "vehicle", str(vehicle_id), {"url": url})
        db.commit()
        row = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        return send_json({"ok": True, "vehicle": dict(row), "url": url}) or True

    if head == "vehicles" and len(parts) == 3 and parts[2] == "photos" and method == "DELETE":
        try:
            vehicle_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم المركبة غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "المركبة غير موجودة"}, 404) or True
        photo_url = str(payload.get("url") or (query.get("url") or [""])[0]).strip()
        if not photo_url:
            return send_json({"ok": False, "error": "حدد الصورة للحذف"}, 400) or True
        photos = _vehicle_photos_list(dict(current).get("photos"))
        if photo_url not in photos:
            return send_json({"ok": False, "error": "الصورة غير موجودة في المعرض"}, 404) or True
        photos = [p for p in photos if p != photo_url]
        db.execute(
            "UPDATE at_vehicles SET photos=?, updated_at=? WHERE id=?",
            (_photos_json(photos), now_iso(), vehicle_id),
        )
        try:
            from server import delete_upload_file

            if photo_url.startswith("/uploads/auto-trading/vehicles/"):
                delete_upload_file(photo_url, "auto-trading/vehicles")
        except Exception:
            pass
        _audit(db, user, "vehicle_photo_removed", "vehicle", str(vehicle_id), {"url": photo_url})
        db.commit()
        row = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        return send_json({"ok": True, "vehicle": dict(row), "removed": photo_url}) or True

    if head == "vehicles" and len(parts) == 2 and method == "DELETE":
        try:
            vehicle_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم المركبة غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "المركبة غير موجودة"}, 404) or True
        cur = dict(current)
        if cur.get("status") == "مباعة":
            return send_json({"ok": False, "error": "لا يمكن حذف مركبة مباعة"}, 400) or True
        sale = db.execute("SELECT id FROM at_sales WHERE vehicle_id=? LIMIT 1", (vehicle_id,)).fetchone()
        if sale:
            return send_json({"ok": False, "error": "لا يمكن حذف مركبة لها سجل بيع"}, 400) or True
        stock_no = str(cur.get("stock_no") or "")
        db.execute("DELETE FROM at_purchases WHERE vehicle_id=?", (vehicle_id,))
        db.execute("DELETE FROM at_expenses WHERE vehicle_id=?", (vehicle_id,))
        db.execute("DELETE FROM at_vehicles WHERE id=?", (vehicle_id,))
        _audit(db, user, "vehicle_deleted", "vehicle", str(vehicle_id), {"stock_no": stock_no})
        db.commit()
        return send_json({"ok": True, "deleted": vehicle_id, "stock_no": stock_no}) or True

    if head == "vehicles" and method == "POST" and len(parts) == 1:
        stock_no = str(payload.get("stock_no") or "").strip()
        make = str(payload.get("make") or "").strip()
        model = str(payload.get("model") or "").strip()
        if not stock_no or not make or not model:
            return send_json({"ok": False, "error": "رقم المخزون والماركة والطراز مطلوبة"}, 400) or True
        if db.execute("SELECT id FROM at_vehicles WHERE stock_no=?", (stock_no,)).fetchone():
            return send_json({"ok": False, "error": "رقم المخزون موجود مسبقاً"}, 400) or True
        status = str(payload.get("status") or "متاحة")
        if status not in VALID_STATUSES:
            status = "متاحة"
        seller_name = str(payload.get("seller_name") or "").strip()
        seller_phone = str(payload.get("seller_phone") or "").strip()
        seller_id = str(payload.get("seller_id") or "").strip()
        purchase_date = str(payload.get("purchase_date") or "").strip()
        purchase_cost = float(payload.get("purchase_cost") or 0)
        photos_json = _photos_json(payload.get("photos") or [])
        db.execute(
            """INSERT INTO at_vehicles(
                stock_no, make, model, variant, vehicle_type, color, year, vin, engine_no,
                engine_cc, seats, axles, origin_country, import_ref, purchase_cost, list_price,
                status, plate_no, license_valid_until, insurance_company, insurance_policy, notes,
                seller_name, seller_phone, seller_id, purchase_date, photos,
                created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                stock_no, make, model,
                str(payload.get("variant") or ""),
                str(payload.get("vehicle_type") or ""),
                str(payload.get("color") or ""),
                int(payload.get("year") or 0) or None,
                str(payload.get("vin") or ""),
                str(payload.get("engine_no") or ""),
                str(payload.get("engine_cc") or ""),
                int(payload.get("seats") or 0) or None,
                int(payload.get("axles") or 0) or None,
                str(payload.get("origin_country") or ""),
                str(payload.get("import_ref") or ""),
                purchase_cost,
                float(payload.get("list_price") or 0),
                status,
                str(payload.get("plate_no") or ""),
                str(payload.get("license_valid_until") or ""),
                str(payload.get("insurance_company") or ""),
                str(payload.get("insurance_policy") or ""),
                str(payload.get("notes") or ""),
                seller_name, seller_phone, seller_id, purchase_date, photos_json,
                now_iso(), now_iso(),
            ),
        )
        vid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _audit(db, user, "vehicle_created", "vehicle", str(vid), {"stock_no": stock_no, "make": make, "model": model})
        if seller_name and purchase_cost > 0:
            purchase_no = _next_purchase_no(db)
            db.execute(
                """INSERT INTO at_purchases(
                    purchase_no, vehicle_id, stock_no, seller_name, seller_phone, seller_id,
                    source_country, purchase_price, paid_amount, payment_method, purchase_date,
                    notes, created_by, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    purchase_no, vid, stock_no, seller_name, seller_phone, seller_id,
                    str(payload.get("origin_country") or ""), purchase_cost, purchase_cost,
                    str(payload.get("purchase_payment_method") or "نقد"),
                    purchase_date or datetime.now().strftime("%Y-%m-%d"),
                    "شراء تلقائي عند إضافة المركبة", str(user.get("username") or ""), now_iso(),
                ),
            )
            _audit(db, user, "purchase_created", "purchase", purchase_no, {"stock_no": stock_no, "seller": seller_name})
        db.commit()
        row = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vid,)).fetchone()
        return send_json({"ok": True, "vehicle": dict(row)}, 201) or True

    if head == "sales" and method == "GET":
        # The chassis and engine numbers travel with the sale so a contract
        # reprinted from this list still identifies the vehicle it transfers.
        rows = db.execute(
            """SELECT s.*, v.make, v.model, v.variant, v.color, v.year, v.vehicle_type,
                      v.vin, v.engine_no, v.engine_cc, v.plate_no,
                      v.origin_country, v.import_ref
               FROM at_sales s LEFT JOIN at_vehicles v ON v.id=s.vehicle_id
               ORDER BY s.id DESC LIMIT 100"""
        ).fetchall()
        return send_json({"ok": True, "sales": [dict(r) for r in rows]}) or True

    if head == "sales" and method == "POST":
        try:
            vehicle_id = int(payload.get("vehicle_id") or 0)
        except (TypeError, ValueError):
            return send_json({"ok": False, "error": "اختر مركبة"}, 400) or True
        vehicle = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not vehicle:
            return send_json({"ok": False, "error": "المركبة غير موجودة"}, 404) or True
        v = dict(vehicle)
        if v["status"] == "مباعة":
            return send_json({"ok": False, "error": "المركبة مباعة مسبقاً"}, 400) or True
        buyer_name = str(payload.get("buyer_name") or "").strip()
        if not buyer_name:
            return send_json({"ok": False, "error": "اسم المشتري مطلوب"}, 400) or True
        sale_price = float(payload.get("sale_price") or v.get("list_price") or 0)
        deposit = float(payload.get("deposit_amount") or 0)
        sale_no = _next_sale_no(db)
        sale_date = str(payload.get("sale_date") or datetime.now().strftime("%Y-%m-%d"))
        db.execute(
            """INSERT INTO at_sales(
                sale_no, vehicle_id, stock_no, buyer_name, buyer_phone, buyer_id,
                sale_price, deposit_amount, payment_method, sale_date, status, notes,
                created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sale_no, vehicle_id, v["stock_no"], buyer_name,
                str(payload.get("buyer_phone") or ""),
                str(payload.get("buyer_id") or ""),
                sale_price, deposit,
                str(payload.get("payment_method") or "نقد"),
                sale_date, "مكتمل",
                str(payload.get("notes") or ""),
                str(user.get("username") or ""),
                now_iso(),
            ),
        )
        db.execute(
            "UPDATE at_vehicles SET status='مباعة', buyer_name=?, buyer_phone=?, updated_at=? WHERE id=?",
            (buyer_name, str(payload.get("buyer_phone") or ""), now_iso(), vehicle_id),
        )
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _audit(db, user, "sale_created", "sale", str(sid), {"sale_no": sale_no, "stock_no": v["stock_no"], "buyer": buyer_name})
        db.commit()
        row = db.execute("SELECT * FROM at_sales WHERE id=?", (sid,)).fetchone()
        return send_json({"ok": True, "sale": with_doc_vehicle(dict(row), v)}, 201) or True

    if head == "imports" and method == "GET":
        rows = db.execute("SELECT * FROM at_import_orders ORDER BY id DESC").fetchall()
        return send_json({"ok": True, "imports": [dict(r) for r in rows]}) or True

    if head == "imports" and len(parts) == 2 and method == "POST":
        try:
            import_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم الطلب غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM at_import_orders WHERE id=?", (import_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "الطلب غير موجود"}, 404) or True
        updates: Dict[str, Any] = {}
        for field in ("status", "eta_date", "arrival_date", "notes", "supplier", "total_cost", "vehicle_count"):
            if field in payload:
                val = payload[field]
                if field in ("total_cost",):
                    val = float(val or 0)
                if field == "vehicle_count":
                    val = int(val or 1)
                updates[field] = val
        if not updates:
            return send_json({"ok": False, "error": "لا توجد حقول للتحديث"}, 400) or True
        sets = ", ".join(f"{k}=?" for k in updates)
        db.execute(
            f"UPDATE at_import_orders SET {sets}, updated_at=? WHERE id=?",
            (*updates.values(), now_iso(), import_id),
        )
        _audit(db, user, "import_updated", "import", str(import_id), updates)
        db.commit()
        row = db.execute("SELECT * FROM at_import_orders WHERE id=?", (import_id,)).fetchone()
        return send_json({"ok": True, "import": dict(row)}) or True

    if head == "imports" and method == "POST" and len(parts) == 1:
        origin = str(payload.get("origin_country") or "").strip()
        if not origin:
            return send_json({"ok": False, "error": "بلد المنشأ مطلوب"}, 400) or True
        order_no = _next_import_no(db)
        db.execute(
            """INSERT INTO at_import_orders(
                order_no, origin_country, supplier, vehicle_count, total_cost, status,
                eta_date, arrival_date, notes, created_by, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order_no, origin,
                str(payload.get("supplier") or ""),
                int(payload.get("vehicle_count") or 1),
                float(payload.get("total_cost") or 0),
                str(payload.get("status") or "قيد الشحن"),
                str(payload.get("eta_date") or ""),
                str(payload.get("arrival_date") or ""),
                str(payload.get("notes") or ""),
                str(user.get("username") or ""),
                now_iso(), now_iso(),
            ),
        )
        iid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _audit(db, user, "import_created", "import", str(iid), {"order_no": order_no, "origin": origin})
        db.commit()
        row = db.execute("SELECT * FROM at_import_orders WHERE id=?", (iid,)).fetchone()
        return send_json({"ok": True, "import": dict(row)}, 201) or True

    if head == "purchases" and method == "GET":
        rows = db.execute(
            """SELECT p.*, v.make, v.model, v.variant, v.color, v.year, v.vehicle_type,
                      v.vin, v.engine_no, v.engine_cc, v.plate_no,
                      v.origin_country, v.import_ref
               FROM at_purchases p LEFT JOIN at_vehicles v ON v.id=p.vehicle_id
               ORDER BY p.id DESC LIMIT 200"""
        ).fetchall()
        return send_json({"ok": True, "purchases": [dict(r) for r in rows]}) or True

    if head == "purchases" and method == "POST":
        seller_name = str(payload.get("seller_name") or "").strip()
        if not seller_name:
            return send_json({"ok": False, "error": "اسم البائع مطلوب"}, 400) or True
        purchase_price = float(payload.get("purchase_price") or 0)
        if purchase_price <= 0:
            return send_json({"ok": False, "error": "سعر الشراء مطلوب"}, 400) or True
        vehicle_id = None
        stock_no = str(payload.get("stock_no") or "").strip()
        try:
            vehicle_id = int(payload.get("vehicle_id") or 0) or None
        except (TypeError, ValueError):
            vehicle_id = None
        vehicle_row = None
        if vehicle_id:
            vehicle_row = db.execute("SELECT * FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
        elif stock_no:
            vehicle_row = db.execute("SELECT * FROM at_vehicles WHERE stock_no=?", (stock_no,)).fetchone()
            if vehicle_row:
                vehicle_id = vehicle_row["id"]
        if vehicle_row:
            stock_no = vehicle_row["stock_no"]
        purchase_no = _next_purchase_no(db)
        purchase_date = str(payload.get("purchase_date") or datetime.now().strftime("%Y-%m-%d"))
        db.execute(
            """INSERT INTO at_purchases(
                purchase_no, vehicle_id, stock_no, seller_name, seller_phone, seller_id,
                source_country, purchase_price, paid_amount, payment_method, purchase_date,
                notes, created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                purchase_no, vehicle_id, stock_no, seller_name,
                str(payload.get("seller_phone") or ""),
                str(payload.get("seller_id") or ""),
                str(payload.get("source_country") or ""),
                purchase_price,
                float(payload.get("paid_amount") or purchase_price),
                str(payload.get("payment_method") or "نقد"),
                purchase_date,
                str(payload.get("notes") or ""),
                str(user.get("username") or ""),
                now_iso(),
            ),
        )
        if vehicle_id:
            db.execute(
                """UPDATE at_vehicles SET purchase_cost=?, seller_name=?, seller_phone=?, seller_id=?,
                   purchase_date=?, updated_at=? WHERE id=?""",
                (
                    purchase_price, seller_name, str(payload.get("seller_phone") or ""),
                    str(payload.get("seller_id") or ""), purchase_date, now_iso(), vehicle_id,
                ),
            )
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _audit(db, user, "purchase_created", "purchase", str(pid), {"purchase_no": purchase_no, "seller": seller_name, "stock_no": stock_no})
        db.commit()
        row = db.execute("SELECT * FROM at_purchases WHERE id=?", (pid,)).fetchone()
        vehicle_for_doc = dict(vehicle_row) if vehicle_row else None
        return send_json({"ok": True, "purchase": with_doc_vehicle(dict(row), vehicle_for_doc)}, 201) or True

    if head == "expenses" and method == "GET":
        rows = db.execute(
            """SELECT ex.*, v.make, v.model
               FROM at_expenses ex LEFT JOIN at_vehicles v ON v.id=ex.vehicle_id
               ORDER BY ex.id DESC LIMIT 200"""
        ).fetchall()
        return send_json({"ok": True, "expenses": [dict(r) for r in rows], "categories": list(EXPENSE_CATEGORIES)}) or True

    if head == "expenses" and method == "POST":
        amount = float(payload.get("amount") or 0)
        if amount <= 0:
            return send_json({"ok": False, "error": "قيمة المصروف مطلوبة"}, 400) or True
        category = str(payload.get("category") or "أخرى").strip() or "أخرى"
        vehicle_id = None
        stock_no = str(payload.get("stock_no") or "").strip()
        try:
            vehicle_id = int(payload.get("vehicle_id") or 0) or None
        except (TypeError, ValueError):
            vehicle_id = None
        if vehicle_id and not stock_no:
            v_row = db.execute("SELECT stock_no FROM at_vehicles WHERE id=?", (vehicle_id,)).fetchone()
            if v_row:
                stock_no = v_row["stock_no"]
        expense_no = _next_expense_no(db)
        expense_date = str(payload.get("expense_date") or datetime.now().strftime("%Y-%m-%d"))
        db.execute(
            """INSERT INTO at_expenses(
                expense_no, category, vehicle_id, stock_no, amount, payee, expense_date,
                payment_method, notes, created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                expense_no, category, vehicle_id, stock_no, amount,
                str(payload.get("payee") or ""),
                expense_date,
                str(payload.get("payment_method") or "نقد"),
                str(payload.get("notes") or ""),
                str(user.get("username") or ""),
                now_iso(),
            ),
        )
        eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _audit(db, user, "expense_created", "expense", str(eid), {"expense_no": expense_no, "category": category, "amount": amount})
        db.commit()
        row = db.execute("SELECT * FROM at_expenses WHERE id=?", (eid,)).fetchone()
        return send_json({"ok": True, "expense": dict(row)}, 201) or True

    if head == "transactions" and method == "GET":
        # Every row states whether money came in or went out, so the ledger can
        # be totalled as cash flow. A capital entry's direction depends on its
        # type: partners paying in is cash in, a withdrawal or a profit payout is
        # cash out.
        limit = 300
        rows = db.execute(
            f"""
            SELECT * FROM (
                SELECT 'شراء' AS kind, 'out' AS flow, '' AS detail,
                       p.purchase_date AS tx_date, p.purchase_no AS ref_no,
                       p.stock_no AS stock_no, p.seller_name AS party, p.purchase_price AS amount,
                       p.notes AS notes, p.created_by AS created_by, p.created_at AS created_at
                FROM at_purchases p
                UNION ALL
                SELECT 'بيع' AS kind, 'in' AS flow, '' AS detail,
                       s.sale_date AS tx_date, s.sale_no AS ref_no,
                       s.stock_no AS stock_no, s.buyer_name AS party, s.sale_price AS amount,
                       s.notes AS notes, s.created_by AS created_by, s.created_at AS created_at
                FROM at_sales s
                UNION ALL
                SELECT 'مصروف' AS kind, 'out' AS flow, ex.category AS detail,
                       ex.expense_date AS tx_date, ex.expense_no AS ref_no,
                       COALESCE(ex.stock_no, '') AS stock_no, COALESCE(ex.payee, ex.category) AS party,
                       ex.amount AS amount, ex.notes AS notes, ex.created_by AS created_by, ex.created_at AS created_at
                FROM at_expenses ex
                UNION ALL
                SELECT 'رأس مال' AS kind,
                       CASE WHEN ce.entry_type IN ('withdrawal','distribution') THEN 'out' ELSE 'in' END AS flow,
                       ce.entry_type AS detail,
                       ce.entry_date AS tx_date, ce.entry_no AS ref_no,
                       '' AS stock_no, pr.name_ar AS party, ce.amount AS amount,
                       ce.notes AS notes, ce.created_by AS created_by, ce.created_at AS created_at
                FROM at_capital_entries ce
                LEFT JOIN at_partners pr ON pr.id=ce.partner_id
            )
            ORDER BY tx_date DESC, created_at DESC LIMIT {limit}
            """
        ).fetchall()
        return send_json({
            "ok": True,
            "transactions": [dict(r) for r in rows],
            "entry_types": CAPITAL_ENTRY_TYPES,
        }) or True

    if head == "capital" and method == "GET":
        summary = _capital_summary(db)
        entries = db.execute(
            """SELECT ce.*, p.name_ar AS partner_name, p.code AS partner_code
               FROM at_capital_entries ce
               LEFT JOIN at_partners p ON p.id=ce.partner_id
               ORDER BY ce.id DESC LIMIT 300"""
        ).fetchall()
        dists = db.execute(
            "SELECT * FROM at_capital_distributions ORDER BY id DESC LIMIT 100"
        ).fetchall()
        return send_json({
            "ok": True,
            "summary": summary,
            "entries": [dict(r) for r in entries],
            "distributions": [dict(r) for r in dists],
            "entry_types": CAPITAL_ENTRY_TYPES,
        }) or True

    if head == "capital" and method == "POST" and len(parts) == 1:
        partner_id = None
        try:
            partner_id = int(payload.get("partner_id") or 0) or None
        except (TypeError, ValueError):
            partner_id = None
        partner_code = str(payload.get("partner_code") or "").strip().lower()
        if not partner_id and partner_code:
            prow = db.execute("SELECT id FROM at_partners WHERE code=?", (partner_code,)).fetchone()
            partner_id = int(prow["id"]) if prow else None
        if not partner_id:
            return send_json({"ok": False, "error": "اختر الشريك (وليد النجار أو حمد السموم)"}, 400) or True
        partner = db.execute("SELECT * FROM at_partners WHERE id=?", (partner_id,)).fetchone()
        if not partner:
            return send_json({"ok": False, "error": "الشريك غير موجود"}, 404) or True
        entry_type = str(payload.get("entry_type") or "contribution").strip().lower()
        if entry_type not in CAPITAL_ENTRY_TYPES:
            return send_json({"ok": False, "error": "نوع حركة رأس المال غير معتمد"}, 400) or True
        amount = float(payload.get("amount") or 0)
        if amount <= 0:
            return send_json({"ok": False, "error": "المبلغ يجب أن يكون أكبر من صفر"}, 400) or True
        entry_no = _next_capital_entry_no(db)
        entry_date = str(payload.get("entry_date") or datetime.now().strftime("%Y-%m-%d"))
        db.execute(
            """INSERT INTO at_capital_entries(
                entry_no, partner_id, entry_type, amount, entry_date, method, reference_no,
                notes, distribution_id, created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,NULL,?,?)""",
            (
                entry_no, partner_id, entry_type, amount, entry_date,
                str(payload.get("method") or "تحويل بنكي"),
                str(payload.get("reference_no") or ""),
                str(payload.get("notes") or ""),
                str(user.get("username") or ""),
                now_iso(),
            ),
        )
        eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _audit(db, user, "capital_entry", "capital", str(eid), {
            "entry_no": entry_no, "partner": partner["name_ar"], "type": entry_type, "amount": amount,
        })
        db.commit()
        row = db.execute("SELECT * FROM at_capital_entries WHERE id=?", (eid,)).fetchone()
        return send_json({"ok": True, "entry": dict(row), "summary": _capital_summary(db)}, 201) or True

    if head == "distributions" and method == "GET":
        rows = db.execute("SELECT * FROM at_capital_distributions ORDER BY id DESC LIMIT 100").fetchall()
        return send_json({"ok": True, "distributions": [dict(r) for r in rows], "summary": _capital_summary(db)}) or True

    if head == "distributions" and method == "POST" and len(parts) == 1:
        total_amount = float(payload.get("total_amount") or 0)
        if total_amount <= 0:
            return send_json({"ok": False, "error": "مبلغ التوزيع مطلوب"}, 400) or True
        partners = [dict(r) for r in db.execute(
            "SELECT * FROM at_partners WHERE active=1 ORDER BY id ASC"
        ).fetchall()]
        if len(partners) < 1:
            return send_json({"ok": False, "error": "لا يوجد شركاء مسجلون"}, 400) or True
        # Optional custom split: {partner_code: amount}
        custom = payload.get("splits") if isinstance(payload.get("splits"), dict) else {}
        pct_sum = sum(float(p.get("ownership_pct") or 0) for p in partners) or 100.0
        splits: List[Dict[str, Any]] = []
        assigned = 0.0
        for i, p in enumerate(partners):
            if p["code"] in custom:
                share = float(custom[p["code"]] or 0)
            elif i == len(partners) - 1:
                share = round(total_amount - assigned, 3)
            else:
                share = round(total_amount * (float(p["ownership_pct"] or 0) / pct_sum), 3)
                assigned += share
            if share < 0:
                return send_json({"ok": False, "error": "حصص التوزيع غير صحيحة"}, 400) or True
            splits.append({"partner_id": int(p["id"]), "partner_code": p["code"], "partner_name": p["name_ar"], "amount": share})
        status = str(payload.get("status") or "معتمد").strip() or "معتمد"
        if status not in ("مسودة", "معتمد", "مدفوع"):
            status = "معتمد"
        dist_no = _next_distribution_no(db)
        dist_date = str(payload.get("dist_date") or datetime.now().strftime("%Y-%m-%d"))
        period_label = str(payload.get("period_label") or "").strip() or f"توزيع {dist_date}"
        paid_at = now_iso() if status == "مدفوع" else None
        db.execute(
            """INSERT INTO at_capital_distributions(
                dist_no, period_label, total_amount, status, dist_date, paid_at, notes, created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                dist_no, period_label, total_amount, status, dist_date, paid_at,
                str(payload.get("notes") or ""),
                str(user.get("username") or ""),
                now_iso(),
            ),
        )
        dist_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        if status in ("معتمد", "مدفوع"):
            for sp in splits:
                if float(sp["amount"]) <= 0:
                    continue
                entry_no = _next_capital_entry_no(db)
                db.execute(
                    """INSERT INTO at_capital_entries(
                        entry_no, partner_id, entry_type, amount, entry_date, method, reference_no,
                        notes, distribution_id, created_by, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        entry_no, sp["partner_id"], "distribution", float(sp["amount"]), dist_date,
                        str(payload.get("method") or "تحويل بنكي"),
                        dist_no,
                        f"توزيع أرباح — {period_label}",
                        dist_id,
                        str(user.get("username") or ""),
                        now_iso(),
                    ),
                )
        _audit(db, user, "capital_distribution", "distribution", str(dist_id), {
            "dist_no": dist_no, "total": total_amount, "status": status, "splits": splits,
        })
        db.commit()
        row = db.execute("SELECT * FROM at_capital_distributions WHERE id=?", (dist_id,)).fetchone()
        return send_json({
            "ok": True,
            "distribution": dict(row),
            "splits": splits,
            "summary": _capital_summary(db),
        }, 201) or True

    if head == "distributions" and len(parts) == 2 and method == "POST":
        try:
            dist_id = int(parts[1])
        except ValueError:
            return send_json({"ok": False, "error": "رقم التوزيع غير صحيح"}, 400) or True
        current = db.execute("SELECT * FROM at_capital_distributions WHERE id=?", (dist_id,)).fetchone()
        if not current:
            return send_json({"ok": False, "error": "التوزيع غير موجود"}, 404) or True
        status = str(payload.get("status") or "").strip()
        if status not in ("مسودة", "معتمد", "مدفوع"):
            return send_json({"ok": False, "error": "حالة التوزيع غير معتمدة"}, 400) or True
        paid_at = current["paid_at"]
        if status == "مدفوع" and not paid_at:
            paid_at = now_iso()
        db.execute(
            "UPDATE at_capital_distributions SET status=?, paid_at=? WHERE id=?",
            (status, paid_at, dist_id),
        )
        # If approving a draft that has no capital entries yet, create them.
        if status in ("معتمد", "مدفوع"):
            existing_entries = db.execute(
                "SELECT COUNT(*) FROM at_capital_entries WHERE distribution_id=?", (dist_id,)
            ).fetchone()[0]
            if not existing_entries:
                partners = [dict(r) for r in db.execute(
                    "SELECT * FROM at_partners WHERE active=1 ORDER BY id ASC"
                ).fetchall()]
                pct_sum = sum(float(p.get("ownership_pct") or 0) for p in partners) or 100.0
                total_amount = float(current["total_amount"] or 0)
                assigned = 0.0
                for i, p in enumerate(partners):
                    if i == len(partners) - 1:
                        share = round(total_amount - assigned, 3)
                    else:
                        share = round(total_amount * (float(p["ownership_pct"] or 0) / pct_sum), 3)
                        assigned += share
                    if share <= 0:
                        continue
                    entry_no = _next_capital_entry_no(db)
                    db.execute(
                        """INSERT INTO at_capital_entries(
                            entry_no, partner_id, entry_type, amount, entry_date, method, reference_no,
                            notes, distribution_id, created_by, created_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            entry_no, int(p["id"]), "distribution", share, current["dist_date"],
                            "تحويل بنكي", current["dist_no"],
                            f"توزيع أرباح — {current['period_label']}",
                            dist_id, str(user.get("username") or ""), now_iso(),
                        ),
                    )
        _audit(db, user, "capital_distribution_status", "distribution", str(dist_id), {"status": status})
        db.commit()
        row = db.execute("SELECT * FROM at_capital_distributions WHERE id=?", (dist_id,)).fetchone()
        return send_json({"ok": True, "distribution": dict(row), "summary": _capital_summary(db)}) or True

    return send_json({"ok": False, "error": "المسار غير موجود"}, 404) or True
