import math
import threading
from datetime import datetime, timezone

from app.config import settings
from app.database import get_conn
from app.engagement import assign_actions


class DeliveryWorker:
    """Simulates order delivery without contacting any external platform."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._process_batch()
            self._stop.wait(settings.delivery_interval_seconds)

    def _process_batch(self) -> None:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT o.id, o.user_id, o.quantity, o.delivered, o.target_url,
                       s.name AS service_name, s.platform
                FROM orders o
                JOIN services s ON s.id = o.service_id
                WHERE o.status = 'processing'
                ORDER BY o.id ASC
                LIMIT 20
                """
            ).fetchall()

            now = datetime.now(timezone.utc).isoformat()
            for row in rows:
                order = dict(row)
                quantity = order["quantity"]
                delivered = order["delivered"]
                remaining = quantity - delivered
                if remaining <= 0:
                    continue
                batch = min(
                    remaining,
                    max(1, math.ceil(quantity * settings.delivery_batch_ratio)),
                )
                clicked = assign_actions(conn, order, batch)
                increment = clicked if clicked else batch
                new_delivered = min(quantity, delivered + increment)
                status = "completed" if new_delivered >= quantity else "processing"
                conn.execute(
                    """
                    UPDATE orders
                    SET delivered = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_delivered, status, now, order["id"]),
                )


worker = DeliveryWorker()
