#!/usr/bin/env python3
"""Copy Nizwa qe_* into estate_* (duplicate only; qe untouched)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("JAWDAH_DATA_DIR", str(ROOT / "data"))

import server
import lq_nizwa_estate_copy


def main() -> int:
    server.init_db()
    db = server.connect()
    try:
        result = lq_nizwa_estate_copy.copy_qe_to_estate(
            db, uid_fn=server.uid, now_fn=server.now_iso, actor="cli-copy"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        qe = db.execute("SELECT COUNT(*) FROM qe_units").fetchone()[0]
        est = db.execute(
            "SELECT COUNT(*) FROM estate_apartments WHERE notes LIKE '%source:qe_unit:%'"
        ).fetchone()[0]
        blds = db.execute(
            "SELECT COUNT(*) FROM estate_buildings WHERE notes LIKE '%source:nizwa_qe_portfolio%'"
        ).fetchone()[0]
        print(f"VERIFY qe_units={qe} estate_apartments_copied={est} buildings={blds}")
        return 0 if result.get("ok") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
