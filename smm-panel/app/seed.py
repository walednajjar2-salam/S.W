from app.auth import hash_password
from app.config import settings
from app.database import get_conn


DEFAULT_SERVICES = [
    {
        "platform": "instagram",
        "name": "متابعين إنستجرام",
        "description": "محاكاة تسليم — بدون بوتات حقيقية",
        "min_qty": 100,
        "max_qty": 50000,
        "price_per_1000": 2.5,
    },
    {
        "platform": "instagram",
        "name": "لايكات إنستجرام",
        "description": "محاكاة تسليم على رابط منشور",
        "min_qty": 50,
        "max_qty": 20000,
        "price_per_1000": 1.2,
    },
    {
        "platform": "tiktok",
        "name": "متابعين تيك توك",
        "description": "محاكاة تسليم — تعليمي فقط",
        "min_qty": 100,
        "max_qty": 100000,
        "price_per_1000": 1.8,
    },
    {
        "platform": "tiktok",
        "name": "مشاهدات تيك توك",
        "description": "محاكاة مشاهدات على رابط فيديو",
        "min_qty": 1000,
        "max_qty": 1000000,
        "price_per_1000": 0.5,
    },
    {
        "platform": "youtube",
        "name": "مشتركين يوتيوب",
        "description": "محاكاة تسليم على رابط قناة",
        "min_qty": 100,
        "max_qty": 10000,
        "price_per_1000": 5.0,
    },
]


def seed_if_empty() -> None:
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count == 0:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, name, role, balance)
                VALUES (?, ?, ?, 'admin', 1000)
                """,
                (
                    settings.admin_email,
                    hash_password(settings.admin_password),
                    "Najjar",
                ),
            )

        svc_count = conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"]
        if svc_count == 0:
            for svc in DEFAULT_SERVICES:
                conn.execute(
                    """
                    INSERT INTO services
                    (platform, name, description, min_qty, max_qty, price_per_1000, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        svc["platform"],
                        svc["name"],
                        svc["description"],
                        svc["min_qty"],
                        svc["max_qty"],
                        svc["price_per_1000"],
                    ),
                )
