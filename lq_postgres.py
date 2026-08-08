"""PostgreSQL controlled migration path for Launch Quality ERP.

Phase 1 (this module):
- Probe LQ_DATABASE_URL / DATABASE_URL
- Shadow schema create + copy from SQLite
- Verify row counts

SQLite remains the primary runtime engine until a later dialect adapter ships.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple


def database_url() -> str:
    return (os.environ.get("LQ_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()


_PSYCOPG_IMPORT_ERROR: Optional[str] = None


def psycopg_available() -> bool:
    global _PSYCOPG_IMPORT_ERROR
    try:
        import psycopg  # noqa: F401
        _PSYCOPG_IMPORT_ERROR = None
        return True
    except Exception as exc:
        _PSYCOPG_IMPORT_ERROR = str(exc)
        return False


def psycopg_import_error() -> Optional[str]:
    psycopg_available()
    return _PSYCOPG_IMPORT_ERROR


def _connect_pg(url: Optional[str] = None):
    import psycopg

    dsn = (url or database_url()).strip()
    if not dsn:
        raise RuntimeError("LQ_DATABASE_URL / DATABASE_URL is not set")
    # Railway sometimes provides postgres:// — psycopg accepts postgresql://
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://") :]
    return psycopg.connect(dsn, connect_timeout=8)


def probe_postgres(url: Optional[str] = None) -> Dict[str, Any]:
    started = time.time()
    out: Dict[str, Any] = {
        "configured": bool((url or database_url()).strip()),
        "driver_installed": psycopg_available(),
        "ok": False,
        "latency_ms": None,
        "server_version": None,
        "error": None,
    }
    if not out["configured"]:
        out["error"] = "LQ_DATABASE_URL not configured"
        return out
    if not out["driver_installed"]:
        out["error"] = "psycopg not installed"
        out["import_error"] = psycopg_import_error()
        return out
    try:
        with _connect_pg(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                row = cur.fetchone()
                out["server_version"] = str(row[0]) if row else None
                cur.execute("SELECT current_database(), current_user")
                dbrow = cur.fetchone()
                if dbrow:
                    out["database"] = dbrow[0]
                    out["user"] = dbrow[1]
        out["ok"] = True
        out["latency_ms"] = int((time.time() - started) * 1000)
    except Exception as exc:
        out["error"] = str(exc)
        out["latency_ms"] = int((time.time() - started) * 1000)
    return out


def _pg_create_sql(table: str, cols: List[str]) -> str:
    parts: List[str] = []
    for c in cols:
        if c == "id":
            parts.append("id TEXT PRIMARY KEY")
        else:
            parts.append(f'"{c}" TEXT')
    return f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(parts)})'


def _stringify(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def shadow_migrate_from_sqlite(
    sqlite_conn,
    tables: Dict[str, List[str]],
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Create Postgres tables matching TABLES and copy rows from SQLite."""
    probe = probe_postgres()
    result: Dict[str, Any] = {
        "ok": False,
        "dry_run": dry_run,
        "probe": probe,
        "tables": {},
        "copied_tables": 0,
        "copied_rows": 0,
        "errors": [],
        "phase": "shadow-copy",
        "primary_engine": "sqlite",
        "note": "SQLite remains primary. This creates a verified Postgres shadow copy.",
    }

    sqlite_counts: Dict[str, int] = {}
    for table, cols in tables.items():
        try:
            sqlite_counts[table] = int(sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
        except Exception:
            sqlite_counts[table] = 0

    if dry_run:
        # Always inventory SQLite; ok only when Postgres is reachable.
        result["tables"] = {
            t: {"sqlite_rows": sqlite_counts.get(t, 0), "action": "would_copy"}
            for t in tables
        }
        result["copied_tables"] = len(tables)
        result["copied_rows"] = sum(sqlite_counts.values())
        if probe.get("ok"):
            result["ok"] = True
        else:
            result["errors"].append(probe.get("error") or "probe failed")
        return result

    if not probe.get("ok"):
        result["errors"].append(probe.get("error") or "probe failed")
        result["tables"] = {
            t: {"sqlite_rows": sqlite_counts.get(t, 0), "action": "blocked"}
            for t in tables
        }
        return result

    try:
        with _connect_pg() as pg:
            with pg.cursor() as cur:
                for table, cols in tables.items():
                    info: Dict[str, Any] = {
                        "sqlite_rows": sqlite_counts.get(table, 0),
                        "pg_rows_before": 0,
                        "pg_rows_after": 0,
                        "copied": 0,
                        "ok": False,
                    }
                    try:
                        cur.execute(_pg_create_sql(table, cols))
                        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                        info["pg_rows_before"] = int(cur.fetchone()[0] or 0)
                        # Replace shadow snapshot for verification clarity
                        cur.execute(f'TRUNCATE TABLE "{table}"')
                        rows = sqlite_conn.execute(
                            f"SELECT {','.join(cols)} FROM {table}"
                        ).fetchall()
                        if rows:
                            placeholders = ",".join(["%s"] * len(cols))
                            col_sql = ",".join(f'"{c}"' for c in cols)
                            sql = f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})'
                            payload = []
                            for r in rows:
                                if hasattr(r, "keys"):
                                    d = dict(r)
                                    payload.append(tuple(_stringify(d.get(c)) for c in cols))
                                else:
                                    payload.append(tuple(_stringify(v) for v in r))
                            cur.executemany(sql, payload)
                            info["copied"] = len(payload)
                        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                        info["pg_rows_after"] = int(cur.fetchone()[0] or 0)
                        info["ok"] = info["pg_rows_after"] == info["sqlite_rows"]
                        if info["ok"]:
                            result["copied_tables"] += 1
                            result["copied_rows"] += info["copied"]
                        else:
                            result["errors"].append(
                                f"{table}: sqlite={info['sqlite_rows']} pg={info['pg_rows_after']}"
                            )
                    except Exception as exc:
                        info["error"] = str(exc)
                        result["errors"].append(f"{table}: {exc}")
                    result["tables"][table] = info
            pg.commit()
        result["ok"] = len(result["errors"]) == 0
    except Exception as exc:
        result["errors"].append(str(exc))
        result["ok"] = False
    return result


def verify_shadow(sqlite_conn, tables: Dict[str, List[str]]) -> Dict[str, Any]:
    probe = probe_postgres()
    out: Dict[str, Any] = {
        "ok": False,
        "probe": probe,
        "matches": 0,
        "mismatches": [],
        "missing_tables": [],
        "table_count": len(tables),
    }
    if not probe.get("ok"):
        return out
    try:
        with _connect_pg() as pg:
            with pg.cursor() as cur:
                for table in tables:
                    try:
                        sq = int(sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
                    except Exception:
                        sq = -1
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                        pg_count = int(cur.fetchone()[0] or 0)
                        if pg_count == sq:
                            out["matches"] += 1
                        else:
                            out["mismatches"].append({"table": table, "sqlite": sq, "postgres": pg_count})
                    except Exception:
                        out["missing_tables"].append(table)
        out["ok"] = not out["mismatches"] and not out["missing_tables"] and out["matches"] == len(tables)
    except Exception as exc:
        out["error"] = str(exc)
    return out


def build_database_platform_status(sqlite_conn, tables: Dict[str, List[str]]) -> Dict[str, Any]:
    probe = probe_postgres()
    sqlite_tables = 0
    sqlite_rows = 0
    for table in tables:
        try:
            sqlite_tables += 1
            sqlite_rows += int(sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
        except Exception:
            pass
    sqlite_ready = sqlite_tables > 0
    return {
        "primary_engine": "sqlite",
        "primary_ready": sqlite_ready,
        "sqlite": {
            "path_configured": True,
            "tables": sqlite_tables,
            "approx_rows": sqlite_rows,
            "production_ready": sqlite_ready,
        },
        "postgres": {
            "url_configured": bool(database_url()),
            "driver_installed": psycopg_available(),
            "probe": probe,
            "shadow_verify": None,
            "ready_for_shadow": bool(probe.get("ok")),
            "ready_for_primary": False,
            "optional": True,
            "primary_blocker": "اختياري — SQLite هو الأساسي في الإنتاج",
        },
        "phase": "sqlite-production + optional-postgres-shadow",
        "next_phase": "optional dialect adapter when needed",
        "note": "SQLite production-ready. Postgres shadow optional when DATABASE_URL is set.",
        "ready": sqlite_ready,
    }
