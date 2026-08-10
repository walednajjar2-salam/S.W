import math
import threading
import time
from datetime import datetime, timezone

from app.config import settings
from app.database import get_conn


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
                SELECT id, quantity, delivered
                FROM orders
                WHERE status = 'processing'
                ORDER BY id ASC
                LIMIT 20
                """
            ).fetchall()

            now = datetime.now(timezone.utc).isoformat()
            for row in rows:
                order_id = row["id"]
                quantity = row["quantity"]
                delivered = row["delivered"]
                batch = max(1, math.ceil(quantity * settings.delivery_batch_ratio))
                new_delivered = min(quantity, delivered + batch)
                status = "completed" if new_delivered >= quantity else "processing"
                conn.execute(
                    """
                    UPDATE orders
                    SET delivered = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_delivered, status, now, order_id),
                )


worker = DeliveryWorker()
