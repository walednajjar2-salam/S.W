"""Off-site backup push: local volume mirror + object storage + optional webhook."""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

OFFSITE_BACKUP_URL = (os.environ.get("LQ_OFFSITE_BACKUP_URL") or "").strip()
OFFSITE_BACKUP_TOKEN = (os.environ.get("LQ_OFFSITE_BACKUP_TOKEN") or "").strip()
LAST_OFFSITE_BACKUP_AT: Optional[str] = None
LAST_OFFSITE_BACKUP_STATUS: Optional[Dict[str, Any]] = None


def local_offsite_dir() -> Path:
    base = Path(os.environ.get("JAWDAH_DATA_DIR") or "data").resolve()
    return base / "offsite-mirror"


def local_volume_ready() -> bool:
    """Railway volume at JAWDAH_DATA_DIR is the durable local offsite channel."""
    try:
        root = Path(os.environ.get("JAWDAH_DATA_DIR") or "data").resolve()
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".lq-offsite-ready"
        probe.write_text("ok", encoding="utf-8")
        return True
    except Exception:
        return False


def offsite_config() -> Dict[str, Any]:
    try:
        from lq_expand import object_storage as lq_object_storage

        obj = lq_object_storage.object_storage_status()
    except Exception:
        obj = {"ready": False, "configured": False, "cloud_ready": False, "production_storage_ready": False}
    cloud_ready = bool(obj.get("cloud_ready") or (obj.get("ready") and obj.get("configured")))
    webhook = bool(OFFSITE_BACKUP_URL)
    local_ready = local_volume_ready()
    if cloud_ready:
        mode = "object-storage"
    elif webhook:
        mode = "webhook"
    elif local_ready:
        mode = "local-volume"
    else:
        mode = "none"
    enabled = bool(cloud_ready or webhook or local_ready)
    return {
        "enabled": enabled,
        "url_configured": webhook,
        "object_storage_ready": cloud_ready,
        "object_storage_configured": bool(obj.get("configured")),
        "local_volume_ready": local_ready,
        "local_mirror_dir": str(local_offsite_dir()),
        "mode": mode,
        "last_push": LAST_OFFSITE_BACKUP_AT,
        "last_status": LAST_OFFSITE_BACKUP_STATUS,
        "setup_hint": (
            None
            if enabled
            else "تحقق من Volume على /app/data أو اربط Railway Bucket"
        ),
        "note": (
            "نسخ خارجي سحابي جاهز"
            if cloud_ready
            else (
                "Webhook جاهز"
                if webhook
                else "نسخ مرآة على Volume الدائم جاهز (Bucket اختياري)"
            )
        ),
    }


def _push_local_volume(json_path: Path, sqlite_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    try:
        dest_root = local_offsite_dir()
        dest_root.mkdir(parents=True, exist_ok=True)
        stamp = str(meta.get("timestamp") or "latest")
        dest = dest_root / stamp
        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in (json_path, sqlite_path):
            if src and Path(src).exists():
                target = dest / Path(src).name
                shutil.copy2(str(src), str(target))
                copied.append(str(target))
        # Keep a stable "latest" pointer copy for quick restore.
        latest = dest_root / "latest"
        latest.mkdir(parents=True, exist_ok=True)
        for src in (json_path, sqlite_path):
            if src and Path(src).exists():
                shutil.copy2(str(src), str(latest / Path(src).name))
        # Retention: keep last 30 stamped folders
        stamped = sorted(
            [p for p in dest_root.iterdir() if p.is_dir() and p.name not in ("latest",)],
            key=lambda p: p.name,
        )
        while len(stamped) > 30:
            old = stamped.pop(0)
            shutil.rmtree(old, ignore_errors=True)
        return {
            "ok": True,
            "channel": "local-volume",
            "copied": copied,
            "dir": str(dest),
            "timestamp": stamp,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "channel": "local-volume"}


def _push_webhook(json_path: Path, sqlite_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    if not OFFSITE_BACKUP_URL:
        return {"ok": True, "skipped": True, "reason": "LQ_OFFSITE_BACKUP_URL not set"}
    try:
        payload = {
            "app": "Launch Quality ERP",
            "version": meta.get("version"),
            "timestamp": meta.get("timestamp"),
            "created_at": meta.get("created_at"),
            "reason": meta.get("reason"),
            "sqlite_bytes": sqlite_path.stat().st_size if sqlite_path.exists() else 0,
            "backup": json.loads(json_path.read_text(encoding="utf-8")),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "LaunchQuality-OffsiteBackup/1.0"}
        if OFFSITE_BACKUP_TOKEN:
            headers["Authorization"] = f"Bearer {OFFSITE_BACKUP_TOKEN}"
        req = urllib.request.Request(OFFSITE_BACKUP_URL, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=90) as resp:
            return {"ok": True, "http_status": resp.status, "timestamp": meta.get("timestamp"), "channel": "webhook"}
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "error": f"HTTP {exc.code}",
            "detail": exc.read().decode("utf-8", errors="replace")[:300],
            "channel": "webhook",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "channel": "webhook"}


def push_offsite_backup(json_path: Path, sqlite_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Push backup to local volume mirror, object storage, and optional webhook."""
    global LAST_OFFSITE_BACKUP_AT, LAST_OFFSITE_BACKUP_STATUS
    channels: Dict[str, Any] = {}
    # 1) Always mirror onto durable local volume (Railway /app/data)
    channels["local_volume"] = _push_local_volume(json_path, sqlite_path, meta)
    # 2) Durable object storage copy (Railway Bucket / S3 / R2) when configured
    try:
        from lq_expand import object_storage as lq_object_storage

        obj_push = lq_object_storage.put_backup_files(json_path, sqlite_path, meta)
        channels["object_storage"] = obj_push
    except Exception as exc:
        channels["object_storage"] = {"ok": False, "error": str(exc)}
    # 3) Optional webhook mirror
    channels["webhook"] = _push_webhook(json_path, sqlite_path, meta)

    local_ok = bool(channels["local_volume"].get("ok"))
    obj_ok = bool(channels["object_storage"].get("ok")) and not channels["object_storage"].get("skipped")
    obj_skip = bool(channels["object_storage"].get("skipped"))
    wh_ok = bool(channels["webhook"].get("ok")) and not channels["webhook"].get("skipped")
    wh_skip = bool(channels["webhook"].get("skipped"))

    if local_ok or obj_ok or wh_ok:
        if obj_ok:
            mode = "object-storage"
        elif wh_ok:
            mode = "webhook"
        else:
            mode = "local-volume"
        status = {
            "ok": True,
            "timestamp": meta.get("timestamp"),
            "channels": channels,
            "mode": mode,
        }
    elif obj_skip and wh_skip and not local_ok:
        status = {
            "ok": False,
            "error": "local volume mirror failed and no cloud channel",
            "channels": channels,
        }
    else:
        status = {
            "ok": False,
            "error": "offsite push failed",
            "channels": channels,
        }
    LAST_OFFSITE_BACKUP_AT = meta.get("created_at")
    LAST_OFFSITE_BACKUP_STATUS = status
    return status
