"""Automatic daily backups on the persistent data volume."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Asia/Muscat"
DEFAULT_TZ_OFFSET = timedelta(hours=4)


def resolve_timezone(name: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone(DEFAULT_TZ_OFFSET)


class AutoBackupService:
    def __init__(
        self,
        *,
        data_dir: Path,
        db_path: Path,
        company_settings_path: Path,
        tables: Dict[str, List[str]],
        rows_to_dicts: Callable[[Iterable[sqlite3.Row]], List[Dict[str, Any]]],
        now_iso: Callable[[], str],
        connect: Callable[[], sqlite3.Connection],
        enabled: bool = True,
        backup_hour: int = 3,
        retain_days: int = 14,
        timezone: str = DEFAULT_TZ,
    ) -> None:
        self.data_dir = data_dir
        self.db_path = db_path
        self.company_settings_path = company_settings_path
        self.tables = tables
        self.rows_to_dicts = rows_to_dicts
        self.now_iso = now_iso
        self.connect = connect
        self.enabled = enabled
        self.backup_hour = max(0, min(23, int(backup_hour)))
        self.retain_days = max(1, int(retain_days))
        self.timezone = resolve_timezone(timezone)
        self.backup_root = self.data_dir / "backups" / "daily"
        self.state_path = self.backup_root / "backup_state.json"
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if not self.enabled:
            print("Auto backup: disabled")
            return
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._loop, name="auto-backup", daemon=True)
        self._thread.start()
        if not self._read_state().get("last_day"):
            threading.Thread(target=self._initial_backup, name="auto-backup-initial", daemon=True).start()
        print(
            f"Auto backup: enabled (daily ~{self.backup_hour:02d}:00, "
            f"retain {self.retain_days} days, dir={self.backup_root})"
        )

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> Dict[str, Any]:
        state = self._read_state()
        archives = self._list_archives()
        return {
            "enabled": self.enabled,
            "schedule": f"daily at {self.backup_hour:02d}:00 ({getattr(self.timezone, 'key', 'UTC+4')})",
            "retain_days": self.retain_days,
            "directory": str(self.backup_root),
            "last_run": state.get("last_run"),
            "last_day": state.get("last_day"),
            "last_status": state.get("status"),
            "last_error": state.get("last_error"),
            "archive_count": len(archives),
            "archives": archives[:10],
            "next_due_now": self._is_due(),
        }

    def run_now(self, *, reason: str = "manual") -> Dict[str, Any]:
        if not self.enabled:
            raise ValueError("Automatic backup is disabled")
        with self._lock:
            return self._execute_backup(reason=reason, force=True)

    def build_export_payload(self, db: sqlite3.Connection) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"status": "production", "exported_at": self.now_iso(), "tables": {}}
        for table, cols in self.tables.items():
            payload["tables"][table] = self.rows_to_dicts(
                db.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall()
            )
        return payload

    def _initial_backup(self) -> None:
        time.sleep(3)
        try:
            if self._read_state().get("last_day"):
                return
            with self._lock:
                if not self._read_state().get("last_day"):
                    self._execute_backup(reason="startup")
        except Exception as exc:
            self._write_state({"status": "error", "last_error": str(exc), "last_run": self.now_iso()})
            print(f"Auto backup startup error: {exc}")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._is_due():
                    with self._lock:
                        self._execute_backup(reason="scheduled")
            except Exception as exc:
                self._write_state({"status": "error", "last_error": str(exc), "last_run": self.now_iso()})
                print(f"Auto backup error: {exc}")
            self._stop.wait(3600)

    def _is_due(self) -> bool:
        if not self.enabled:
            return False
        now = datetime.now(self.timezone)
        state = self._read_state()
        last_day = state.get("last_day")
        if last_day == now.strftime("%Y-%m-%d"):
            return False
        if now.hour < self.backup_hour:
            return False
        return True

    def _execute_backup(self, *, reason: str, force: bool = False) -> Dict[str, Any]:
        now = datetime.now(self.timezone)
        day_key = now.strftime("%Y-%m-%d")
        state = self._read_state()
        if not force and state.get("last_day") == day_key:
            return state

        stamp = now.strftime("%Y%m%d-%H%M%S")
        archive_dir = self.backup_root / stamp
        archive_dir.mkdir(parents=True, exist_ok=True)

        sqlite_target = archive_dir / "jawdah.sqlite3"
        json_target = archive_dir / "export.json"
        manifest_target = archive_dir / "manifest.json"

        db = self.connect()
        try:
            export_payload = self.build_export_payload(db)
        finally:
            db.close()
        json_target.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        src = sqlite3.connect(self.db_path)
        try:
            dst = sqlite3.connect(sqlite_target)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        if self.company_settings_path.exists():
            shutil.copy2(self.company_settings_path, archive_dir / "company_settings.json")

        table_counts = {name: len(rows) for name, rows in export_payload["tables"].items()}
        total_rows = sum(table_counts.values())
        size_bytes = sum(
            p.stat().st_size for p in archive_dir.iterdir() if p.is_file()
        )

        manifest = {
            "created_at": self.now_iso(),
            "day": day_key,
            "reason": reason,
            "version": export_payload.get("status"),
            "table_counts": table_counts,
            "total_rows": total_rows,
            "files": sorted(p.name for p in archive_dir.iterdir() if p.is_file()),
        }
        manifest_target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        removed = self._prune_old_archives()
        result = {
            "status": "ok",
            "last_run": self.now_iso(),
            "last_day": day_key,
            "archive": stamp,
            "total_rows": total_rows,
            "size_bytes": size_bytes,
            "removed_archives": removed,
            "last_error": None,
        }
        self._write_state(result)
        print(f"Auto backup saved: {archive_dir} ({total_rows} rows)")
        return result

    def _prune_old_archives(self) -> int:
        cutoff = datetime.now(self.timezone) - timedelta(days=self.retain_days)
        removed = 0
        for path in sorted(self.backup_root.iterdir()):
            if not path.is_dir() or path.name == "backup_state.json":
                continue
            try:
                created = datetime.strptime(path.name[:8], "%Y%m%d").replace(tzinfo=self.timezone)
            except ValueError:
                continue
            if created < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        return removed

    def _list_archives(self) -> List[Dict[str, Any]]:
        archives: List[Dict[str, Any]] = []
        for path in sorted(self.backup_root.iterdir(), reverse=True):
            if not path.is_dir():
                continue
            manifest_path = path / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    manifest = {}
            else:
                manifest = {}
            size_bytes = sum(p.stat().st_size for p in path.iterdir() if p.is_file())
            archives.append(
                {
                    "id": path.name,
                    "created_at": manifest.get("created_at"),
                    "total_rows": manifest.get("total_rows"),
                    "size_bytes": size_bytes,
                    "files": manifest.get("files", []),
                }
            )
        return archives

    def _read_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_state(self, patch: Dict[str, Any]) -> None:
        state = self._read_state()
        state.update(patch)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_auto_backup_service(
    *,
    data_dir: Path,
    db_path: Path,
    company_settings_path: Path,
    tables: Dict[str, List[str]],
    rows_to_dicts: Callable[[Iterable[sqlite3.Row]], List[Dict[str, Any]]],
    now_iso: Callable[[], str],
    connect: Callable[[], sqlite3.Connection],
) -> AutoBackupService:
    enabled = os.environ.get("JAWDAH_AUTO_BACKUP", "1").strip().lower() not in ("0", "false", "no", "off")
    backup_hour = int(os.environ.get("JAWDAH_BACKUP_HOUR", "3"))
    retain_days = int(os.environ.get("JAWDAH_BACKUP_RETAIN_DAYS", "14"))
    timezone = os.environ.get("JAWDAH_BACKUP_TZ", DEFAULT_TZ).strip() or DEFAULT_TZ
    return AutoBackupService(
        data_dir=data_dir,
        db_path=db_path,
        company_settings_path=company_settings_path,
        tables=tables,
        rows_to_dicts=rows_to_dicts,
        now_iso=now_iso,
        connect=connect,
        enabled=enabled,
        backup_hour=backup_hour,
        retain_days=retain_days,
        timezone=timezone,
    )
