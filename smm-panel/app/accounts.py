import json
import re
import secrets
import sqlite3
import string
from datetime import datetime, timezone

from app.auth import hash_password
from app.database import get_conn

EMAIL_PREFIX_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,30}[a-z0-9])?$", re.I)
DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,60}[a-z0-9])$", re.I)
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_GENERATE_COUNT = 10000


def generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_invite_code() -> str:
    body = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
    return f"SW-{body}"


def _next_available_index(conn, prefix: str, domain: str) -> int:
    prefix = prefix.lower()
    domain = domain.lower()
    like = f"{prefix}%@{domain}"
    rows = conn.execute(
        "SELECT email FROM users WHERE email LIKE ?", (like,)
    ).fetchall()
    highest = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)@{re.escape(domain)}$")
    for row in rows:
        match = pattern.match(row["email"])
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def create_user(
    *,
    email: str,
    password: str,
    name: str,
    role: str = "user",
    balance: float = 0,
) -> dict:
    email = email.strip().lower()
    name = name.strip()
    if role not in ("user", "admin"):
        raise ValueError("الدور يجب أن يكون user أو admin")
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if exists:
            raise ValueError("البريد مستخدم مسبقاً")
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, name, role, balance)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, hash_password(password), name, role, float(balance)),
        )
        if balance:
            conn.execute(
                """
                INSERT INTO wallet_transactions (user_id, amount, kind, note)
                VALUES (?, ?, 'admin_adjust', 'رصيد ابتدائي')
                """,
                (cur.lastrowid, float(balance)),
            )
        row = conn.execute(
            "SELECT id, email, name, role, balance, created_at FROM users WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def generate_users(
    count: int,
    email_prefix: str = "user",
    email_domain: str = "example.com",
    name_prefix: str = "عميل",
    password: str | None = None,
    balance: float = 0,
    link_instagram: bool = True,
    link_tiktok: bool = True,
) -> list[dict]:
    if count < 1 or count > MAX_GENERATE_COUNT:
        raise ValueError(f"عدد الحسابات يجب أن يكون بين 1 و {MAX_GENERATE_COUNT}")
    prefix = (email_prefix or "user").strip().lower().replace(" ", "")
    domain = (email_domain or "example.com").strip().lower().replace(" ", "")
    names = (name_prefix or "عميل").strip() or "عميل"
    if not EMAIL_PREFIX_RE.fullmatch(prefix):
        raise ValueError("بادئة البريد غير صالحة")
    if not DOMAIN_RE.fullmatch(domain):
        raise ValueError("نطاق البريد غير صالح")

    shared = (password or "").strip() or generate_password()
    password_hash = hash_password(shared)
    platforms: list[str] = []
    if link_instagram:
        platforms.append("instagram")
    if link_tiktok:
        platforms.append("tiktok")
    created: list[dict] = []
    social_rows: list[tuple] = []
    wallet_rows: list[tuple] = []
    with get_conn() as conn:
        index = _next_available_index(conn, prefix, domain)
        for _ in range(count):
            while True:
                email = f"{prefix}{index}@{domain}"
                taken = conn.execute(
                    "SELECT 1 FROM users WHERE email = ?", (email,)
                ).fetchone()
                if not taken:
                    break
                index += 1
            name = f"{names} {index}"
            cur = conn.execute(
                """
                INSERT INTO users (email, password_hash, name, role, balance)
                VALUES (?, ?, ?, 'user', ?)
                """,
                (email, password_hash, name, float(balance)),
            )
            user_id = cur.lastrowid
            if balance:
                wallet_rows.append((user_id, float(balance), "admin_adjust", "رصيد ابتدائي"))
            linked, link_rows = _auto_link_rows(user_id, f"{prefix}{index}", platforms)
            social_rows.extend(link_rows)
            created.append(
                {
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "password": shared,
                    "balance": round(float(balance), 2),
                    "role": "user",
                    "linked": linked,
                }
            )
            index += 1
        if wallet_rows:
            conn.executemany(
                """
                INSERT INTO wallet_transactions (user_id, amount, kind, note)
                VALUES (?, ?, ?, ?)
                """,
                wallet_rows,
            )
        if social_rows:
            conn.executemany(
                """
                INSERT INTO social_connections
                (user_id, platform, platform_user_id, username, profile_url,
                 access_token, verified, meta_json, connected_at, updated_at)
                VALUES (?, ?, '', ?, ?, '', 0, ?, ?, ?)
                ON CONFLICT(user_id, platform) DO UPDATE SET
                    username = excluded.username,
                    profile_url = excluded.profile_url,
                    meta_json = excluded.meta_json,
                    updated_at = excluded.updated_at
                """,
                social_rows,
            )
    return created


def _auto_link_rows(
    user_id: int, handle: str, platforms: list[str]
) -> tuple[list[dict], list[tuple]]:
    from app.platforms import (
        instagram_profile_url,
        is_valid_social_username,
        tiktok_profile_url,
    )

    handle = re.sub(r"[^A-Za-z0-9._]", "", (handle or "").strip().lstrip("@"))[:30]
    if not is_valid_social_username(handle):
        handle = f"user{user_id}"
    now = datetime.now(timezone.utc).isoformat()
    meta = json.dumps({"verified_via": "auto"}, ensure_ascii=False)
    linked: list[dict] = []
    rows: list[tuple] = []
    for platform in platforms:
        if platform == "instagram":
            url = instagram_profile_url(handle)
        elif platform == "tiktok":
            url = tiktok_profile_url(handle)
        else:
            continue
        rows.append((user_id, platform, handle, url, meta, now, now))
        linked.append({"platform": platform, "username": handle, "profile_url": url})
    return linked, rows


def create_invite_code(max_uses: int = 1, note: str = "", created_by: int | None = None) -> dict:
    if max_uses < 1 or max_uses > 1000:
        raise ValueError("عدد الاستخدامات يجب أن يكون بين 1 و 1000")
    for _ in range(8):
        code = generate_invite_code()
        try:
            with get_conn() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO invite_codes (code, max_uses, note, created_by)
                    VALUES (?, ?, ?, ?)
                    """,
                    (code, max_uses, (note or "").strip()[:200], created_by),
                )
                row = conn.execute(
                    "SELECT * FROM invite_codes WHERE id = ?", (cur.lastrowid,)
                ).fetchone()
            return dict(row)
        except sqlite3.IntegrityError:
            continue
    raise ValueError("تعذّر إنشاء كود الدعوة")


def list_invite_codes() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM invite_codes ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [dict(r) for r in rows]


def disable_invite_code(code_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invite_codes WHERE id = ?", (code_id,)
        ).fetchone()
        if not row:
            raise ValueError("كود الدعوة غير موجود")
        conn.execute("UPDATE invite_codes SET active = 0 WHERE id = ?", (code_id,))
        row = conn.execute(
            "SELECT * FROM invite_codes WHERE id = ?", (code_id,)
        ).fetchone()
    return dict(row)


def consume_invite_code(conn, code: str) -> dict:
    raw = (code or "").strip().upper()
    if not raw:
        raise ValueError("أدخل كود الدعوة")
    row = conn.execute(
        "SELECT * FROM invite_codes WHERE code = ?", (raw,)
    ).fetchone()
    if not row or not row["active"]:
        raise ValueError("كود الدعوة غير صالح")
    if row["used_count"] >= row["max_uses"]:
        raise ValueError("تم استهلاك كود الدعوة بالكامل")
    conn.execute(
        "UPDATE invite_codes SET used_count = used_count + 1 WHERE id = ?",
        (row["id"],),
    )
    return dict(row)
