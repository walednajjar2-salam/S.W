"""Real business reference catalog for مشاريع جودة الانطلاقة.

Seeded from office materials (services, land prices, hospitality packages,
staff roster, departments, bank accounts). Reference data only — not demo
operational leases/properties.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

COMPANY_PROFILE: Dict[str, Any] = {
    "name_ar": "مشاريع جودة الانطلاقة للخدمات",
    "name_en": "QUALITY OF LAUNCH PROJECTS LLC",
    "broker_name_ar": "مشاريع جودة الانطلاقة للوساطة العقارية",
    "cr_no": "1466316",
    "postal_code": "611",
    "po_box": "320",
    "email": "jiwdat@gmail.com",
    "email_alt": "startingquality@gmail.com",
    "address_ar": "نزوى — حي التراث الشمالي قرب الدوار",
    "country_ar": "سلطنة عُمان",
    "hours": "08:00 — 19:00",
    "motto_ar": "إذا أرضيناك فتحدث عنا.. وإذا لاحظت منا قصوراً فتحدث إلينا..",
    "activity_ar": "إدارة وتأجير العقارات المملوكة أو المؤجرة السكنية وغير السكنية ووساطة العقارات",
    "phones": {
        "landline": "25225026",
        "whatsapp": "98203088",
        "mobile_1": "92120205",
        "mobile_2": "92269656",
        "mobile_3": "92204210",
        "mobile_4": "92200218",
        "hospitality": "92204210",
    },
    "bank": {
        "name": "Bank Muscat",
        "accounts": [
            {
                "label_ar": "مشاريع جودة الانطلاقة",
                "label_en": "Starting Quality Project",
                "number": "0378063651660017",
                "phone": "",
            },
            {
                "label_ar": "يعقوب فاضل الخصيبي",
                "label_en": "Yaqoub Al Khusaibi",
                "number": "0368001970950016",
                "phone": "92200218",
            },
        ],
    },
    "departments": [
        {"id": "housing", "name_ar": "قسم خدمات الإسكان", "name_en": "Housing Services"},
        {"id": "realestate", "name_ar": "قسم خدمات العقارية", "name_en": "Real Estate Services"},
        {"id": "hospitality", "name_ar": "قسم خدمات الضيافة", "name_en": "Hospitality Services"},
    ],
}

# Handwritten management roster (real team — usernames for system accounts).
STAFF_ROSTER: List[Dict[str, str]] = [
    {"username": "yaqoub", "name": "يعقوب فاضل الخصيبي", "title": "المدير العام والمدير التنفيذي", "role": "owner", "department": "housing"},
    {"username": "owner", "name": "يعقوب فاضل الخصيبي", "title": "المالك / المدير التنفيذي", "role": "owner", "department": "housing"},
    {"username": "rahma", "name": "رحمة محمد عبد الهادي", "title": "شؤون إدارية — منسق المدير", "role": "admin", "department": "housing"},
    {"username": "waleed", "name": "وليد محمد عبد الهادي", "title": "مالك", "role": "owner", "department": "housing"},
    {"username": "marwan", "name": "مروان سالم الشعيلي", "title": "كاشير إداري وإعلام", "role": "operations", "department": "housing"},
    {"username": "ali", "name": "علي محمد علي النديش", "title": "مخزن", "role": "operations", "department": "realestate"},
    {"username": "mohammed.siraj", "name": "محمد صالح سراج النور", "title": "عقارات", "role": "operations", "department": "realestate"},
    {"username": "mohammed.riyami", "name": "محمد حمود الريامي", "title": "مسؤول إداري العلاقات العامة وخدمة العملاء", "role": "operations", "department": "housing"},
    {"username": "ahoud", "name": "عهود سعيد الشعيلي", "title": "تسويق ريسبشن ادخالات", "role": "reception", "department": "housing"},
    {"username": "mohammed.jahbul", "name": "محمد جهبول إسلام", "title": "مسؤول العمال", "role": "maintenance", "department": "hospitality"},
]

# Ministry / housing office services offered by the licensed office.
HOUSING_SERVICES: List[Dict[str, Any]] = [
    {"code": "mgmt", "name_ar": "إدارة جميع أنواع العقارات", "category": "housing"},
    {"code": "land_update", "name_ar": "تحديث طلبات الأراضي", "category": "housing"},
    {"code": "deed_doc", "name_ar": "طلب وثيقة عقارية", "category": "housing"},
    {"code": "deed_lost", "name_ar": "إصدار ملكية بدل فاقد", "category": "housing"},
    {"code": "deed_damaged", "name_ar": "إصدار ملكية بدل تالف", "category": "housing"},
    {"code": "deed_name", "name_ar": "إصدار ملكية مع تصحيح الاسم", "category": "housing"},
    {"code": "data_cert", "name_ar": "طلب شهادة بيانات عقارية", "category": "housing"},
    {"code": "land_renew", "name_ar": "تقديم طلب تجديد أرض سكنية استحقاق", "category": "housing"},
    {"code": "mortgage_reg", "name_ar": "الرهن / تسجيل عقد الرهن", "category": "housing"},
    {"code": "unemployed_letter", "name_ar": "رسالة لا يعمل لمن يهمه الأمر", "category": "housing"},
    {"code": "print_rent", "name_ar": "طباعة عقود الإيجارات", "category": "housing"},
    {"code": "print_sale", "name_ar": "طباعة عقود البيع والشراء", "category": "housing"},
    {"code": "buy_sell", "name_ar": "البيع والشراء", "category": "realestate"},
    {"code": "inheritance", "name_ar": "حصر الإرث", "category": "housing"},
    {"code": "gift", "name_ar": "الهبة / التنازل", "category": "housing"},
    {"code": "mortgage_release", "name_ar": "فك الرهن", "category": "housing"},
]

# Official office service fees — Al Dakhiliyah (effective 2023-01-01). Ministry platform fee +5 OMR separate.
OFFICE_SERVICE_PRICES: List[Dict[str, Any]] = [
    {"code": "buy_sell", "name_ar": "البيع / الشراء", "tiers": [{"parties": "2-5", "price": 10}, {"parties": "6-10", "price": 15}, {"parties": "11-15", "price": 20}], "note": "يزيد مع زيادة الأطراف"},
    {"code": "gift", "name_ar": "الهبة / التنازل", "tiers": [{"parties": "2-5", "price": 5}, {"parties": "6-10", "price": 10}, {"parties": "11-15", "price": 15}], "note": "يزيد مع زيادة الأطراف"},
    {"code": "inheritance", "name_ar": "حصر الإرث", "tiers": [{"parties": "2-5", "price": 5}, {"parties": "6-10", "price": 10}, {"parties": "11-15", "price": 15}], "note": "يزيد مع زيادة الأطراف"},
    {"code": "mortgage", "name_ar": "رهن", "tiers": [{"parties": "-", "price": 5}], "note": ""},
    {"code": "sale_mortgage", "name_ar": "بيع ورهن", "tiers": [{"parties": "-", "price": 15}], "note": "يزيد مع زيادة الأطراف"},
    {"code": "deed_replace", "name_ar": "بدل فاقد / تالف / تصحيح اسم", "tiers": [{"parties": "-", "price": 5}], "note": ""},
    {"code": "exchange", "name_ar": "المبادلة", "tiers": [{"parties": "-", "price": 10}], "note": ""},
    {"code": "seizure", "name_ar": "الحجز على عقار / فكه", "tiers": [{"parties": "-", "price": 5}], "note": ""},
    {"code": "certificates", "name_ar": "طلب شهادات بيانات / وثيقة عقارية", "tiers": [{"parties": "-", "price": 5}], "note": ""},
    {"code": "division", "name_ar": "معاملة القسمة", "tiers": [{"parties": "لكل طرف", "price": 2}], "note": "حد أدنى يعتمد على الملاك"},
    {"code": "print_sale_contract", "name_ar": "طباعة عقود البيع/الشراء", "tiers": [{"parties": "-", "price": 20}], "note": ""},
]
MINISTRY_PLATFORM_FEE_OMR = 5.0

# Land prices — Al Dakhiliyah governorate (OMR / m²).
LAND_PRICES: List[Dict[str, Any]] = [
    {"wilayat": "بدبد", "zone": "مركز المدينة", "residential": 22, "res_commercial": 55, "industrial": 23, "agricultural": 4, "tourism": 65},
    {"wilayat": "بدبد", "zone": "ضواحي المدينة", "residential": 11, "res_commercial": 38, "industrial": 20, "agricultural": 3, "tourism": 50},
    {"wilayat": "بدبد", "zone": "التجمعات الأخرى", "residential": 5, "res_commercial": 22, "industrial": 13, "agricultural": 1, "tourism": 23},
    {"wilayat": "سمائل", "zone": "مركز المدينة", "residential": 19, "res_commercial": 56, "industrial": 30, "agricultural": 4, "tourism": 65},
    {"wilayat": "سمائل", "zone": "ضواحي المدينة", "residential": 11, "res_commercial": 34, "industrial": 21, "agricultural": 2, "tourism": 45},
    {"wilayat": "سمائل", "zone": "التجمعات الأخرى", "residential": 5, "res_commercial": 20, "industrial": 12, "agricultural": 1, "tourism": 25},
    {"wilayat": "نزوى", "zone": "مركز المدينة", "residential": 26, "res_commercial": 71, "industrial": 41, "agricultural": 5, "tourism": 110},
    {"wilayat": "نزوى", "zone": "ضواحي المدينة", "residential": 16, "res_commercial": 45, "industrial": 26, "agricultural": 4, "tourism": 50},
    {"wilayat": "نزوى", "zone": "التجمعات الأخرى", "residential": 5, "res_commercial": 26, "industrial": 9, "agricultural": 1, "tourism": 35},
    {"wilayat": "إزكي", "zone": "مركز المدينة", "residential": 13, "res_commercial": 51, "industrial": 28, "agricultural": 3, "tourism": 57},
    {"wilayat": "إزكي", "zone": "ضواحي المدينة", "residential": 8, "res_commercial": 30, "industrial": 17, "agricultural": 2, "tourism": 40},
    {"wilayat": "إزكي", "zone": "التجمعات الأخرى", "residential": 4, "res_commercial": 18, "industrial": 12, "agricultural": 1, "tourism": 25},
    {"wilayat": "أدم", "zone": "مركز المدينة", "residential": 13, "res_commercial": 29, "industrial": 22, "agricultural": 2, "tourism": 40},
    {"wilayat": "أدم", "zone": "ضواحي المدينة", "residential": 5, "res_commercial": 20, "industrial": 14, "agricultural": 1, "tourism": 23},
    {"wilayat": "أدم", "zone": "التجمعات الأخرى", "residential": 3, "res_commercial": 12, "industrial": 5, "agricultural": 0.8, "tourism": 10},
    {"wilayat": "بهلاء", "zone": "مركز المدينة", "residential": 11, "res_commercial": 48, "industrial": 26, "agricultural": 3, "tourism": 57},
    {"wilayat": "بهلاء", "zone": "ضواحي المدينة", "residential": 6, "res_commercial": 28, "industrial": 16, "agricultural": 2, "tourism": 15},
    {"wilayat": "بهلاء", "zone": "التجمعات الأخرى", "residential": 4, "res_commercial": 10, "industrial": 10, "agricultural": 0.8, "tourism": 55},
    {"wilayat": "منح", "zone": "مركز المدينة", "residential": 9, "res_commercial": 21, "industrial": 22, "agricultural": 2, "tourism": 25},
    {"wilayat": "منح", "zone": "ضواحي المدينة", "residential": 7, "res_commercial": 19, "industrial": 13, "agricultural": 1, "tourism": 15},
    {"wilayat": "منح", "zone": "التجمعات الأخرى", "residential": 3, "res_commercial": 10, "industrial": 5, "agricultural": 0.8, "tourism": 45},
    {"wilayat": "الحمراء", "zone": "مركز المدينة", "residential": 9, "res_commercial": 28, "industrial": 20, "agricultural": 3, "tourism": 10},
    {"wilayat": "الحمراء", "zone": "ضواحي المدينة", "residential": 6, "res_commercial": 17, "industrial": 13, "agricultural": 1, "tourism": 45},
    {"wilayat": "الحمراء", "zone": "التجمعات الأخرى", "residential": 3, "res_commercial": 9, "industrial": 5, "agricultural": 0.8, "tourism": 20},
]

HOSPITALITY_PACKAGES: List[Dict[str, Any]] = [
    {"code": "offer1", "name_ar": "العرض الأول", "guests_min": 20, "guests_max": 120, "waiters": 5, "supervisors": 1, "dallahs": "5", "price_omr": 140},
    {"code": "offer2", "name_ar": "العرض الثاني", "guests_min": 120, "guests_max": 250, "waiters": 10, "supervisors": 1, "dallahs": "10", "price_omr": 230},
    {"code": "offer3", "name_ar": "العرض الثالث", "guests_min": 250, "guests_max": 400, "waiters": 15, "supervisors": 1, "dallahs": "15", "price_omr": 310},
    {"code": "offer4", "name_ar": "العرض الرابع", "guests_min": 400, "guests_max": 600, "waiters": 20, "supervisors": 2, "dallahs": "20-25", "price_omr": 400},
    {"code": "offer5", "name_ar": "العرض الخامس", "guests_min": 600, "guests_max": 800, "waiters": 30, "supervisors": 2, "dallahs": "25-30", "price_omr": 480},
    {"code": "offer6", "name_ar": "العرض السادس", "guests_min": 800, "guests_max": 1000, "waiters": 35, "supervisors": 2, "dallahs": "30-35", "price_omr": 550},
]

CONDOLENCE_PRICING: Dict[str, Any] = {
    "duration_days": 3,
    "shifts": [
        {"name_ar": "الفترة الصباحية", "from": "07:00", "to": "13:00", "staff": "4 مضيفين + صانع قهوة + مشرف"},
        {"name_ar": "استراحة تبديل", "from": "13:00", "to": "13:40", "staff": "صلاة / غداء"},
        {"name_ar": "الفترة المسائية", "from": "13:40", "to": "المغرب", "staff": "4 مضيفين + صانع قهوة + مشرف"},
    ],
    "includes": ["خدمات الضيافة كاملة", "لبان للموقع (يوفره صاحب العزاء)"],
    "prices": [
        {"zone": "داخل نزوى", "price_omr": 450},
        {"zone": "خارج نزوى (قريب)", "price_omr": 500},
        {"zone": "خارج المحافظة", "price_omr": 550, "note": "يبدأ من 550 حسب الموقع"},
    ],
    "notes": [
        "طلب مستلزمات إضافية يزيد السعر حسب الفواتير",
        "طلب مضيفين إضافيين يزيد السعر لكل فرد",
    ],
}

HOSPITALITY_TERMS: List[str] = [
    "خدمة ضيافة في مجالس خارجية — ليست غرفاً وليست مرتبطة بالعقارات",
    "الأسعار تشمل المستلزمات والخدمات المذكورة",
    "الأسعار لنزوى — خارج نزوى رسوم نقل إضافية",
    "تأكيد الحجز قبل 72 ساعة على الأقل",
    "عربون 30% عند الحجز والباقي بعد انتهاء الخدمة",
    "يمكن تعديل عدد الضيوف حتى 24 ساعة قبل المناسبة",
]


def calc_office_fee(service_code: str, parties: int = 2) -> Dict[str, Any]:
    row = next((x for x in OFFICE_SERVICE_PRICES if x["code"] == service_code), None)
    if not row:
        return {"ok": False, "error": "خدمة غير معروفة"}
    price = float(row["tiers"][0]["price"])
    if service_code in ("buy_sell", "gift", "inheritance"):
        if parties <= 5:
            price = float(row["tiers"][0]["price"])
        elif parties <= 10:
            price = float(row["tiers"][1]["price"])
        else:
            price = float(row["tiers"][2]["price"])
    elif service_code == "division":
        price = 2.0 * max(1, int(parties))
    platform = MINISTRY_PLATFORM_FEE_OMR
    return {
        "ok": True,
        "service_code": service_code,
        "name_ar": row["name_ar"],
        "parties": parties,
        "office_fee": price,
        "ministry_platform_fee": platform,
        "total": round(price + platform, 3),
        "currency": "OMR",
        "note": "أسعار المكتب لا تشمل رسوم منصة الوزارة (5 ر.ع)",
    }


def pick_hospitality_package(guests: int) -> Optional[Dict[str, Any]]:
    g = max(1, int(guests or 0))
    for pkg in HOSPITALITY_PACKAGES:
        if pkg["guests_min"] <= g <= pkg["guests_max"]:
            return dict(pkg)
    if g < HOSPITALITY_PACKAGES[0]["guests_min"]:
        return dict(HOSPITALITY_PACKAGES[0])
    return dict(HOSPITALITY_PACKAGES[-1])


def quote_condolence(zone: str = "nizwa") -> Dict[str, Any]:
    z = (zone or "nizwa").strip().lower()
    mapping = {
        "nizwa": ("داخل نزوى", 450.0),
        "near": ("خارج نزوى (قريب)", 500.0),
        "outside": ("خارج المحافظة", 550.0),
    }
    label, price = mapping.get(z, mapping["nizwa"])
    return {
        "ok": True,
        "service_kind": "condolence",
        "channel": "external_majlis",
        "zone": z,
        "zone_label": label,
        "duration_days": CONDOLENCE_PRICING["duration_days"],
        "shifts": CONDOLENCE_PRICING["shifts"],
        "includes": CONDOLENCE_PRICING["includes"],
        "price_omr": price,
        "deposit_omr": round(price * 0.30, 3),
        "notes": CONDOLENCE_PRICING["notes"],
        "currency": "OMR",
        "note": "واجب عزاء في موقع خارجي — مفصول عن العقارات والغرف",
    }


def quote_event_package(guests: int, *, outside_nizwa: bool = False) -> Dict[str, Any]:
    pkg = pick_hospitality_package(guests)
    if not pkg:
        return {"ok": False, "error": "لا عرض مناسب"}
    price = float(pkg["price_omr"])
    transport_note = "خارج نزوى: تُضاف رسوم نقل حسب الاتفاق" if outside_nizwa else "السعر لنزوى"
    return {
        "ok": True,
        "service_kind": "event",
        "channel": "external_majlis",
        "guests": int(guests or 0),
        "package": pkg,
        "price_omr": price,
        "deposit_omr": round(price * 0.30, 3),
        "outside_nizwa": bool(outside_nizwa),
        "transport_note": transport_note,
        "terms": HOSPITALITY_TERMS,
        "currency": "OMR",
        "note": "خدمة مجلس خارجي — مفصولة عن العقارات والغرف",
    }


def catalog_payload() -> Dict[str, Any]:
    return {
        "company": COMPANY_PROFILE,
        "staff": STAFF_ROSTER,
        "housing_services": HOUSING_SERVICES,
        "office_service_prices": OFFICE_SERVICE_PRICES,
        "ministry_platform_fee_omr": MINISTRY_PLATFORM_FEE_OMR,
        "land_prices": LAND_PRICES,
        "hospitality_packages": HOSPITALITY_PACKAGES,
        "hospitality_terms": HOSPITALITY_TERMS,
        "condolence": CONDOLENCE_PRICING,
    }


def ensure_business_staff(db, ensure_user_fn) -> List[str]:
    """Create/update display names for real staff without resetting passwords."""
    created: List[str] = []
    for row in STAFF_ROSTER:
        username = row["username"]
        # Bootstrap password only used when user does not exist.
        ensure_user_fn(db, username, row["name"], row["role"], "ChangeMeNow1")
        db.execute(
            "UPDATE users SET name=?, role=?, active=1 WHERE lower(username)=?",
            (row["name"], row["role"], username.lower()),
        )
        created.append(username)
    return created
