#!/usr/bin/env python3
"""Verify NAJJAR team accounts are bootstrapped with stable credentials."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXPECTED = (
    ("waleed.najjar", "Walid Najjar", "owner", "1"),
    ("hamad.sumoom", "Hamad Al Samoom", "owner", "2"),
    ("sara", "Sara", "operations", "3"),
    ("sales", "Sales", "sales", "4"),
    ("accounting", "Accounting", "accountant", "5"),
)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="najjar_team_users_"))
    os.environ["JAWDAH_DATA_DIR"] = str(tmp)
    import server  # noqa: E402

    server.init_db()

    db_path = Path(os.environ["JAWDAH_DATA_DIR"]) / "jawdah.sqlite3"
    if not db_path.exists():
        print("FAIL: database not created", file=sys.stderr)
        return 1

    failures = 0
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        for username, name, role, password in EXPECTED:
            row = db.execute(
                "SELECT username, name, role, active, password_hash FROM users WHERE lower(username)=?",
                (username.lower(),),
            ).fetchone()
            if not row:
                print(f"FAIL: missing user {username}", file=sys.stderr)
                failures += 1
                continue
            if int(row["active"]) != 1:
                print(f"FAIL: {username} is not active", file=sys.stderr)
                failures += 1
            if row["name"] != name or row["role"] != role:
                print(
                    f"FAIL: {username} profile mismatch "
                    f"(name={row['name']!r}, role={row['role']!r})",
                    file=sys.stderr,
                )
                failures += 1
            if not server.verify_password(password, row["password_hash"]):
                print(f"FAIL: {username} password does not match {password!r}", file=sys.stderr)
                failures += 1

        extra = db.execute(
            "SELECT username FROM users WHERE active=1 AND lower(username) NOT IN (?,?,?,?,?)",
            tuple(u for u, *_ in EXPECTED),
        ).fetchall()
        if extra:
            print(
                "FAIL: unexpected active users: "
                + ", ".join(r["username"] for r in extra),
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(f"{failures} check(s) failed", file=sys.stderr)
        return 1

    print("OK: all 5 NAJJAR team accounts bootstrapped and active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
