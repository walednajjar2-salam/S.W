from datetime import datetime, timezone

ACTION_LABELS = {
    "follow": "متابعة",
    "like": "لايك",
    "view": "مشاهدة",
    "subscribe": "اشتراك",
}


def infer_action(service_name: str) -> str:
    name = service_name or ""
    lowered = name.lower()
    if "لايك" in name or "like" in lowered:
        return "like"
    if "مشاهد" in name or "view" in lowered:
        return "view"
    if "مشترك" in name or "subscribe" in lowered:
        return "subscribe"
    if "متابع" in name or "follow" in lowered:
        return "follow"
    return "follow"


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def assign_actions(conn, order: dict, count: int) -> int:
    """Assign generated/linked panel accounts to click follow/like on the order URL."""
    if count < 1:
        return 0
    order_id = order["id"]
    owner_id = order["user_id"]
    platform = (order.get("platform") or "").strip().lower()
    target_url = (order.get("target_url") or "").strip()
    if not platform or not target_url:
        return 0

    action = infer_action(order.get("service_name") or "")
    candidates = conn.execute(
        """
        SELECT sc.user_id
        FROM social_connections sc
        WHERE sc.platform = ?
          AND sc.user_id != ?
          AND sc.user_id NOT IN (
              SELECT actor_user_id
              FROM engagement_actions
              WHERE order_id = ? AND actor_user_id IS NOT NULL
          )
        ORDER BY
          CASE WHEN json_extract(sc.meta_json, '$.verified_via') = 'auto' THEN 0 ELSE 1 END,
          sc.user_id DESC
        LIMIT ?
        """,
        (platform, owner_id, order_id, count),
    ).fetchall()
    if not candidates:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (order_id, row["user_id"], action, target_url, "clicked", now, now)
        for row in candidates
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO engagement_actions
        (order_id, actor_user_id, action, target_url, status, clicked_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def engagement_counts(conn, order_ids: list[int]) -> dict[int, dict]:
    if not order_ids:
        return {}
    placeholders = ",".join("?" * len(order_ids))
    rows = conn.execute(
        f"""
        SELECT order_id, action, COUNT(*) AS assigned
        FROM engagement_actions
        WHERE order_id IN ({placeholders})
        GROUP BY order_id, action
        """,
        order_ids,
    ).fetchall()
    return {
        row["order_id"]: {"action": row["action"], "assigned": row["assigned"]}
        for row in rows
    }


def attach_engagement(orders: list[dict], conn) -> list[dict]:
    counts = engagement_counts(conn, [order["id"] for order in orders])
    for order in orders:
        inferred = infer_action(order.get("service_name") or "")
        stats = counts.get(order["id"]) or {}
        action = stats.get("action") or inferred
        order["engagement"] = {
            "action": action,
            "action_label": action_label(action),
            "assigned": int(stats.get("assigned") or 0),
            "target_url": order.get("target_url") or "",
        }
    return orders


def order_engagement_payload(conn, order: dict, limit: int = 50) -> dict:
    action = infer_action(order.get("service_name") or "")
    assigned = conn.execute(
        "SELECT COUNT(*) AS c FROM engagement_actions WHERE order_id = ?",
        (order["id"],),
    ).fetchone()["c"]
    actors = conn.execute(
        """
        SELECT ea.clicked_at, ea.action, ea.target_url, ea.status,
               u.email, u.name, sc.username, sc.profile_url
        FROM engagement_actions ea
        JOIN users u ON u.id = ea.actor_user_id
        LEFT JOIN social_connections sc
          ON sc.user_id = ea.actor_user_id AND sc.platform = ?
        WHERE ea.order_id = ?
        ORDER BY ea.id ASC
        LIMIT ?
        """,
        (order["platform"], order["id"], limit),
    ).fetchall()
    return {
        "order_id": order["id"],
        "action": action,
        "action_label": action_label(action),
        "target_url": order["target_url"],
        "assigned": assigned,
        "quantity": order["quantity"],
        "delivered": order["delivered"],
        "actors": [dict(row) for row in actors],
    }
