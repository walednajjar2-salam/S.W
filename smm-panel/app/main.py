from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import json

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.database import get_conn, init_db
from app.schemas import (
    AdminCreateUser,
    AuthResponse,
    BalanceAdjust,
    GenerateUsersRequest,
    InviteCodeCreate,
    LoginRequest,
    OAuthConfigUpdate,
    OrderCreate,
    RegisterRequest,
    ServiceCreate,
    ServiceUpdate,
    SocialLinkRequest,
    UrlValidateRequest,
    WalletTopUp,
)
from app.accounts import (
    consume_invite_code,
    create_invite_code,
    create_user,
    disable_invite_code,
    generate_users,
    list_invite_codes,
)
from app.seed import seed_if_empty
from app.worker import worker
from app.config import settings
from app.platforms import (
    instagram_profile_url,
    preview_url,
    resolve_social_url,
    tiktok_profile_url,
    validate_url_for_platform,
)
from app.social_oauth import (
    exchange_instagram_code,
    exchange_tiktok_code,
    oauth_configured,
    oauth_status_payload,
    pop_oauth_state,
    public_base_from_headers,
    save_oauth_setting,
    start_oauth,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "public"
ASSETS_DIR = STATIC_DIR / "assets"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_if_empty()
    worker.start()
    yield
    worker.stop()


app = FastAPI(
    title="لوحة خدمات — نموذج تعليمي",
    description="نظام طلبات ومحفظة وطابور تسليم محاكى — بدون بوتات",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _user_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "balance": round(row["balance"], 2),
        "created_at": row["created_at"],
    }


def _calc_amount(price_per_1000: float, quantity: int) -> float:
    return round((price_per_1000 / 1000) * quantity, 4)


def _social_public(row: dict) -> dict:
    meta = {}
    if row.get("meta_json"):
        try:
            meta = json.loads(row["meta_json"])
        except json.JSONDecodeError:
            meta = {}
    return {
        "id": row["id"],
        "platform": row["platform"],
        "username": row["username"],
        "profile_url": row["profile_url"],
        "verified": bool(row["verified"]),
        "connected_at": row["connected_at"],
        "meta": meta,
    }


def _save_social_connection(user_id: int, data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(data.get("meta") or {}, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO social_connections
            (user_id, platform, platform_user_id, username, profile_url,
             access_token, verified, meta_json, connected_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, platform) DO UPDATE SET
                platform_user_id = excluded.platform_user_id,
                username = excluded.username,
                profile_url = excluded.profile_url,
                access_token = excluded.access_token,
                verified = excluded.verified,
                meta_json = excluded.meta_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                data["platform"],
                data.get("platform_user_id", ""),
                data["username"],
                data["profile_url"],
                data.get("access_token", ""),
                1 if data.get("verified") else 0,
                meta_json,
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT * FROM social_connections
            WHERE user_id = ? AND platform = ?
            """,
            (user_id, data["platform"]),
        ).fetchone()
    return _social_public(dict(row))


def _oauth_redirect(ok: bool, platform: str, msg: str = "") -> RedirectResponse:
    if ok:
        return RedirectResponse(f"/panel?oauth=success&platform={platform}")
    return RedirectResponse(
        f"/panel?oauth=error&platform={platform}&msg={quote(msg[:160])}"
    )


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "S.W",
        "mode": "simulation",
        "bots": False,
        "database": settings.db_path,
        "integrations": {
            "instagram_oauth": oauth_configured("instagram"),
            "tiktok_oauth": oauth_configured("tiktok"),
        },
    }


@app.get("/api/auth/register-status")
def register_status():
    with get_conn() as conn:
        active = conn.execute(
            """
            SELECT COUNT(*) AS c FROM invite_codes
            WHERE active = 1 AND used_count < max_uses
            """
        ).fetchone()["c"]
    return {"open": False, "requires_invite": True, "has_active_codes": bool(active)}


@app.post("/api/auth/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    try:
        with get_conn() as conn:
            exists = conn.execute(
                "SELECT id FROM users WHERE email = ?", (body.email.lower(),)
            ).fetchone()
            if exists:
                raise ValueError("البريد مستخدم مسبقاً")
            consume_invite_code(conn, body.invite_code)
            cur = conn.execute(
                """
                INSERT INTO users (email, password_hash, name, role, balance)
                VALUES (?, ?, ?, 'user', ?)
                """,
                (
                    body.email.lower(),
                    hash_password(body.password),
                    body.name.strip(),
                    settings.default_user_balance,
                ),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
    except ValueError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    user = dict(row)
    token = create_access_token(user["id"], user["role"])
    return AuthResponse(access_token=token, user=_user_public(user))


@app.post("/api/auth/login", response_model=AuthResponse)
def login(body: LoginRequest):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (body.email.lower(),)
        ).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "بيانات الدخول غير صحيحة")
    user = dict(row)
    token = create_access_token(user["id"], user["role"])
    return AuthResponse(access_token=token, user=_user_public(user))


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return _user_public(user)


@app.get("/api/services")
def list_services(active_only: bool = True):
    query = "SELECT * FROM services"
    params: tuple = ()
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY platform, id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/services")
def create_service(body: ServiceCreate, _: dict = Depends(require_admin)):
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO services
            (platform, name, description, min_qty, max_qty, price_per_1000, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.platform.strip().lower(),
                body.name.strip(),
                body.description.strip(),
                body.min_qty,
                body.max_qty,
                body.price_per_1000,
                1 if body.active else 0,
            ),
        )
        row = conn.execute(
            "SELECT * FROM services WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.patch("/api/services/{service_id}")
def update_service(
    service_id: int, body: ServiceUpdate, _: dict = Depends(require_admin)
):
    fields = []
    values = []
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "active":
            fields.append("active = ?")
            values.append(1 if value else 0)
        else:
            fields.append(f"{key} = ?")
            values.append(value.strip() if isinstance(value, str) else value)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "لا توجد حقول للتحديث")
    values.append(service_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE services SET {', '.join(fields)} WHERE id = ?", values
        )
        row = conn.execute(
            "SELECT * FROM services WHERE id = ?", (service_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الخدمة غير موجودة")
    return dict(row)


@app.post("/api/orders")
async def create_order(body: OrderCreate, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        svc = conn.execute(
            "SELECT * FROM services WHERE id = ? AND active = 1", (body.service_id,)
        ).fetchone()
        if not svc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "الخدمة غير متاحة")
        svc = dict(svc)

    target = body.target_url.strip()
    if not target:
        with get_conn() as conn:
            linked = conn.execute(
                """
                SELECT profile_url FROM social_connections
                WHERE user_id = ? AND platform = ?
                """,
                (user["id"], svc["platform"]),
            ).fetchone()
        if not linked:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "لا يوجد حساب مربوط تلقائياً لهذه المنصة — اربط الحساب أو أدخل الرابط",
            )
        target = linked["profile_url"]

    resolved = await resolve_social_url(target)
    ok, url_msg, parsed = validate_url_for_platform(resolved, svc["platform"])
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, url_msg)
    target_url = parsed["url"] if parsed else resolved

    with get_conn() as conn:
        if body.quantity < svc["min_qty"] or body.quantity > svc["max_qty"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"الكمية يجب أن تكون بين {svc['min_qty']} و {svc['max_qty']}",
            )
        amount = _calc_amount(svc["price_per_1000"], body.quantity)
        fresh = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if fresh["balance"] < amount:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"الرصيد غير كافٍ. المطلوب: {amount}$",
            )
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (amount, user["id"]),
        )
        conn.execute(
            """
            INSERT INTO wallet_transactions (user_id, amount, kind, note)
            VALUES (?, ?, 'order', ?)
            """,
            (user["id"], -amount, f"طلب خدمة #{body.service_id}"),
        )
        cur = conn.execute(
            """
            INSERT INTO orders
            (user_id, service_id, target_url, quantity, amount, delivered, status, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, 'processing', ?)
            """,
            (
                user["id"],
                body.service_id,
                target_url,
                body.quantity,
                amount,
                now,
            ),
        )
        order = conn.execute(
            """
            SELECT o.*, s.name AS service_name, s.platform
            FROM orders o
            JOIN services s ON s.id = o.service_id
            WHERE o.id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        new_balance = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user["id"],)
        ).fetchone()["balance"]
    result = dict(order)
    result["balance_after"] = round(new_balance, 2)
    return result


@app.get("/api/orders")
def list_orders(user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        if user["role"] == "admin":
            rows = conn.execute(
                """
                SELECT o.*, s.name AS service_name, s.platform, u.email AS user_email
                FROM orders o
                JOIN services s ON s.id = o.service_id
                JOIN users u ON u.id = o.user_id
                ORDER BY o.id DESC
                LIMIT 200
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT o.*, s.name AS service_name, s.platform
                FROM orders o
                JOIN services s ON s.id = o.service_id
                WHERE o.user_id = ?
                ORDER BY o.id DESC
                LIMIT 100
                """,
                (user["id"],),
            ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/wallet/transactions")
def wallet_transactions(user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM wallet_transactions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (user["id"],),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/wallet/topup")
def wallet_topup(body: WalletTopUp, user: dict = Depends(get_current_user)):
    """Demo top-up — no real payment gateway."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (body.amount, user["id"]),
        )
        conn.execute(
            """
            INSERT INTO wallet_transactions (user_id, amount, kind, note)
            VALUES (?, ?, 'topup', 'شحن تجريبي')
            """,
            (user["id"], body.amount),
        )
        balance = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user["id"],)
        ).fetchone()["balance"]
    return {"balance": round(balance, 2), "added": body.amount}


@app.get("/api/admin/users")
def admin_users(_: dict = Depends(require_admin)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, name, role, balance, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/users")
def admin_create_user(body: AdminCreateUser, _: dict = Depends(require_admin)):
    try:
        user = create_user(
            email=str(body.email),
            password=body.password,
            name=body.name,
            balance=body.balance,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return user


@app.post("/api/admin/users/generate")
def admin_generate_users(body: GenerateUsersRequest, _: dict = Depends(require_admin)):
    try:
        created = generate_users(
            count=body.count,
            email_prefix=body.email_prefix,
            email_domain=body.email_domain,
            name_prefix=body.name_prefix,
            password=body.password or None,
            balance=body.balance,
            link_instagram=body.link_instagram,
            link_tiktok=body.link_tiktok,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"count": len(created), "accounts": created}


@app.get("/api/admin/invite-codes")
def admin_invite_codes(_: dict = Depends(require_admin)):
    return list_invite_codes()


@app.post("/api/admin/invite-codes")
def admin_create_invite(body: InviteCodeCreate, user: dict = Depends(require_admin)):
    try:
        return create_invite_code(body.max_uses, body.note, user["id"])
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@app.post("/api/admin/invite-codes/{code_id}/disable")
def admin_disable_invite(code_id: int, _: dict = Depends(require_admin)):
    try:
        return disable_invite_code(code_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/api/admin/users/{user_id}/balance")
def admin_adjust_balance(
    user_id: int, body: BalanceAdjust, _: dict = Depends(require_admin)
):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "المستخدم غير موجود")
        new_balance = row["balance"] + body.amount
        if new_balance < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "الرصيد لا يمكن أن يكون سالباً")
        conn.execute(
            "UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id)
        )
        conn.execute(
            """
            INSERT INTO wallet_transactions (user_id, amount, kind, note)
            VALUES (?, ?, 'admin_adjust', ?)
            """,
            (user_id, body.amount, body.note or "تعديل من المدير"),
        )
    return {"user_id": user_id, "balance": round(new_balance, 2)}


@app.get("/api/admin/stats")
def admin_stats(_: dict = Depends(require_admin)):
    with get_conn() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        services = conn.execute(
            "SELECT COUNT(*) AS c FROM services WHERE active = 1"
        ).fetchone()["c"]
        orders = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM orders"
        ).fetchone()["s"]
        processing = conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE status = 'processing'"
        ).fetchone()["c"]
    return {
        "users": users,
        "active_services": services,
        "orders": orders,
        "revenue": round(revenue, 2),
        "processing_orders": processing,
    }


@app.get("/api/social/connections")
def list_social_connections(user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM social_connections
            WHERE user_id = ?
            ORDER BY platform
            """,
            (user["id"],),
        ).fetchall()
    return [_social_public(dict(r)) for r in rows]


@app.get("/api/social/oauth/status")
def social_oauth_status(request: Request, user: dict = Depends(get_current_user)):
    base = public_base_from_headers(dict(request.headers), request.url.scheme)
    return oauth_status_payload(base, include_config=user["role"] == "admin")


@app.get("/api/admin/oauth-config")
def admin_oauth_config(request: Request, _: dict = Depends(require_admin)):
    base = public_base_from_headers(dict(request.headers), request.url.scheme)
    return oauth_status_payload(base, include_config=True)


@app.put("/api/admin/oauth-config")
def update_oauth_config(body: OAuthConfigUpdate, request: Request, _: dict = Depends(require_admin)):
    data = body.model_dump(exclude_unset=True)
    secret_keys = {"instagram_client_secret", "tiktok_client_secret"}
    for key, value in data.items():
        if key in secret_keys and not (value or "").strip():
            continue
        save_oauth_setting(key, value or "")
    base = public_base_from_headers(dict(request.headers), request.url.scheme)
    return oauth_status_payload(base, include_config=True)


@app.post("/api/social/link")
async def link_social_manual(body: SocialLinkRequest, user: dict = Depends(get_current_user)):
    if body.platform == "instagram":
        profile_url = instagram_profile_url(body.username)
    else:
        profile_url = tiktok_profile_url(body.username)

    meta = {"verified_via": "manual"}
    try:
        preview = await preview_url(profile_url, body.platform)
        if preview.get("preview"):
            meta["preview"] = preview["preview"]
    except Exception:
        pass

    return _save_social_connection(
        user["id"],
        {
            "platform": body.platform,
            "platform_user_id": "",
            "username": body.username,
            "profile_url": profile_url,
            "access_token": "",
            "verified": False,
            "meta": meta,
        },
    )


@app.delete("/api/social/connections/{platform}")
def unlink_social(platform: str, user: dict = Depends(get_current_user)):
    platform = platform.strip().lower()
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM social_connections WHERE user_id = ? AND platform = ?",
            (user["id"], platform),
        )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لا يوجد حساب مربوط")
    return {"ok": True, "platform": platform}


@app.get("/api/social/oauth/{platform}/start")
def social_oauth_start(platform: str, request: Request, user: dict = Depends(get_current_user)):
    try:
        base = public_base_from_headers(dict(request.headers), request.url.scheme)
        url = start_oauth(platform, user["id"], base)
    except ValueError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return {"url": url}


@app.get("/api/social/oauth/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
):
    if error:
        return _oauth_redirect(False, "instagram", error_description or error)
    payload = pop_oauth_state(state)
    if not payload or payload.get("platform") != "instagram":
        return _oauth_redirect(False, "instagram", "جلسة الربط انتهت — أعد المحاولة من اللوحة")
    try:
        data = await exchange_instagram_code(code, payload.get("redirect_uri") or None)
        data["platform"] = "instagram"
        data["verified"] = True
        _save_social_connection(payload["user_id"], data)
        return _oauth_redirect(True, "instagram")
    except Exception as exc:
        return _oauth_redirect(False, "instagram", str(exc))


@app.get("/api/social/oauth/tiktok/callback")
async def tiktok_oauth_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
):
    if error:
        return _oauth_redirect(False, "tiktok", error_description or error)
    payload = pop_oauth_state(state)
    if not payload or payload.get("platform") != "tiktok":
        return _oauth_redirect(False, "tiktok", "جلسة الربط انتهت — أعد المحاولة من اللوحة")
    try:
        data = await exchange_tiktok_code(
            code,
            payload.get("code_verifier") or "",
            payload.get("redirect_uri") or None,
        )
        data["platform"] = "tiktok"
        data["verified"] = True
        _save_social_connection(payload["user_id"], data)
        return _oauth_redirect(True, "tiktok")
    except Exception as exc:
        return _oauth_redirect(False, "tiktok", str(exc))


@app.post("/api/platforms/validate")
async def validate_platform_url(body: UrlValidateRequest, _: dict = Depends(get_current_user)):
    if body.platform:
        ok, message, parsed = validate_url_for_platform(body.url, body.platform)
        preview = None
        if ok and parsed:
            full = await preview_url(parsed["url"], body.platform)
            preview = full.get("preview")
        return {"ok": ok, "message": message, "parsed": parsed, "preview": preview}
    result = await preview_url(body.url)
    return result


@app.get("/api/platforms/preview")
async def platform_preview(
    url: str = Query(..., min_length=5),
    platform: str | None = Query(default=None),
    _: dict = Depends(get_current_user),
):
    return await preview_url(url, platform)


@app.get("/api/payment/info")
def payment_info(_: dict = Depends(get_current_user)):
    """بيانات التحويل البنكي — تُضبط من Railway Variables."""
    return {
        "phone": settings.payment_phone,
        "account": settings.payment_account,
        "bank": settings.payment_bank,
        "holder": settings.payment_holder,
        "iban": settings.payment_iban,
        "swift": settings.payment_swift,
        "configured": bool(
            settings.payment_phone
            or settings.payment_account
            or settings.payment_iban
        ),
    }


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(ASSETS_DIR / "login.html")


@app.get("/register")
def register_page():
    return FileResponse(ASSETS_DIR / "register.html")


@app.get("/panel")
def panel_page():
    return FileResponse(ASSETS_DIR / "panel.html")


app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
