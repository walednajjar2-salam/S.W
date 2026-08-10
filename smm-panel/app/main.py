from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    AuthResponse,
    BalanceAdjust,
    LoginRequest,
    OrderCreate,
    RegisterRequest,
    ServiceCreate,
    ServiceUpdate,
    WalletTopUp,
)
from app.seed import seed_if_empty
from app.worker import worker

STATIC_DIR = Path(__file__).resolve().parent.parent / "public"


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


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "simulation", "bots": False}


@app.post("/api/auth/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM users WHERE email = ?", (body.email.lower(),)
        ).fetchone()
        if exists:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "البريد مسجّل مسبقاً")
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, name, role, balance)
            VALUES (?, ?, ?, 'user', 0)
            """,
            (body.email.lower(), hash_password(body.password), body.name.strip()),
        )
        user_id = cur.lastrowid
        user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    token = create_access_token(user_id, user["role"])
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
def create_order(body: OrderCreate, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        svc = conn.execute(
            "SELECT * FROM services WHERE id = ? AND active = 1", (body.service_id,)
        ).fetchone()
        if not svc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "الخدمة غير متاحة")
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
                body.target_url,
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


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
