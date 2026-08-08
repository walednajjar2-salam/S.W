"""S3-compatible object storage for uploads (contracts, photos, proofs).

Supports AWS S3, Cloudflare R2, MinIO, and Railway Buckets.
When Railway injects BUCKET + ACCESS_KEY_ID + SECRET_ACCESS_KEY, storage
auto-enables (no extra LQ_OBJECT_STORAGE_ENABLED required).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

_LAST_WRITE: Optional[Dict[str, Any]] = None
_LAST_READ: Optional[Dict[str, Any]] = None
_LAST_ERROR: Optional[str] = None
_LOCK = threading.Lock()


def _env(*names: str, default: str = "") -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return default


def _env_truthy(name: str, default: str = "0") -> bool:
    return (os.environ.get(name) or default).strip().lower() in ("1", "true", "yes", "on")


def _cfg() -> Dict[str, Any]:
    # Explicit LQ_* / AWS_* first, then Railway Bucket injected names.
    bucket = _env("LQ_OBJECT_STORAGE_BUCKET", "AWS_S3_BUCKET", "BUCKET")
    access = _env(
        "LQ_OBJECT_STORAGE_ACCESS_KEY_ID",
        "AWS_ACCESS_KEY_ID",
        "ACCESS_KEY_ID",
    )
    secret = _env(
        "LQ_OBJECT_STORAGE_SECRET_ACCESS_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "SECRET_ACCESS_KEY",
    )
    region = _env(
        "LQ_OBJECT_STORAGE_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "REGION",
        default="auto",
    ) or "auto"
    endpoint = _env(
        "LQ_OBJECT_STORAGE_ENDPOINT_URL",
        "AWS_ENDPOINT_URL",
        "ENDPOINT",
    )
    # Railway Buckets default endpoint when bucket vars are present.
    railway_injected = bool(
        (os.environ.get("BUCKET") or "").strip()
        and (os.environ.get("ACCESS_KEY_ID") or "").strip()
        and (os.environ.get("SECRET_ACCESS_KEY") or "").strip()
    )
    if not endpoint and railway_injected:
        endpoint = "https://storage.railway.app"
    prefix = _env("LQ_OBJECT_STORAGE_PREFIX").strip().strip("/")
    public_base = _env("LQ_OBJECT_STORAGE_PUBLIC_BASE_URL").rstrip("/")
    local_fallback = _env_truthy("LQ_OBJECT_STORAGE_LOCAL_FALLBACK", "1")
    configured = bool(bucket and access and secret)
    explicit = (os.environ.get("LQ_OBJECT_STORAGE_ENABLED") or "").strip().lower()
    if explicit in ("0", "false", "no", "off"):
        enabled = False
    elif explicit in ("1", "true", "yes", "on"):
        enabled = configured
    else:
        # Auto-enable when credentials are present (Railway Bucket link).
        enabled = configured
    # Railway prefers virtual-hosted; older custom endpoints may need path style.
    addressing = _env("LQ_OBJECT_STORAGE_ADDRESSING", default="")
    if not addressing:
        if endpoint.rstrip("/").endswith("storage.railway.app"):
            addressing = "virtual"
        elif endpoint:
            addressing = "path"
        else:
            addressing = "auto"
    return {
        "enabled": enabled,
        "configured": configured,
        "bucket": bucket,
        "region": region,
        "endpoint_url": endpoint,
        "prefix": prefix,
        "public_base_url": public_base,
        "local_fallback": local_fallback,
        "access_configured": bool(access),
        "secret_configured": bool(secret),
        "access_key": access,
        "secret_key": secret,
        "addressing_style": addressing,
        "railway_injected": railway_injected,
        "provider": "railway-bucket" if railway_injected or endpoint.rstrip("/").endswith("storage.railway.app") else "s3-compatible",
    }


def boto3_available() -> bool:
    try:
        import boto3  # noqa: F401
        return True
    except Exception:
        return False


def object_storage_config() -> Dict[str, Any]:
    cfg = _cfg()
    return {
        "enabled": cfg["enabled"],
        "configured": cfg["configured"],
        "provider": cfg["provider"],
        "bucket_configured": bool(cfg["bucket"]),
        "endpoint_configured": bool(cfg["endpoint_url"]),
        "region": cfg["region"],
        "prefix": cfg["prefix"] or None,
        "public_base_configured": bool(cfg["public_base_url"]),
        "local_fallback": cfg["local_fallback"],
        "driver_installed": boto3_available(),
        "railway_injected": cfg["railway_injected"],
        "setup_hint": (
            None
            if cfg["configured"]
            else "Railway → Create → Bucket → Variables → Variable References (AWS SDK preset)"
        ),
    }


def object_storage_status() -> Dict[str, Any]:
    cfg = object_storage_config()
    with _LOCK:
        last_write = dict(_LAST_WRITE) if _LAST_WRITE else None
        last_read = dict(_LAST_READ) if _LAST_READ else None
        last_error = _LAST_ERROR
    cloud_ready = bool(cfg["enabled"] and cfg["driver_installed"] and cfg["configured"])
    return {
        **cfg,
        "last_write": last_write,
        "last_read": last_read,
        "last_error": last_error,
        # ready = production path usable (local durable always; cloud when linked)
        "ready": True,
        "local_durable_ready": True,
        "production_storage_ready": True,
        "cloud_ready": cloud_ready,
        "mode": "cloud" if cloud_ready else "local-durable",
        "note": (
            "التخزين السحابي جاهز"
            if cloud_ready
            else "التخزين المحلي الدائم جاهز على Volume — Bucket اختياري للنسخ السحابي"
        ),
        "setup_hint": (
            None
            if cloud_ready
            else "اختياري: Railway → Create → Bucket → Variable References (AWS SDK)"
        ),
    }


def _client():
    import boto3
    from botocore.config import Config

    cfg = _cfg()
    if not cfg["configured"]:
        raise RuntimeError("Object storage is not configured")
    style = cfg["addressing_style"] or "auto"
    kwargs: Dict[str, Any] = {
        "service_name": "s3",
        "region_name": cfg["region"] or "auto",
        "aws_access_key_id": cfg["access_key"],
        "aws_secret_access_key": cfg["secret_key"],
        "config": Config(signature_version="s3v4", s3={"addressing_style": style}),
    }
    if cfg["endpoint_url"]:
        kwargs["endpoint_url"] = cfg["endpoint_url"]
    return boto3.client(**kwargs), cfg


def key_from_upload_url(url: str) -> Optional[str]:
    s = str(url or "").strip().lstrip("/")
    if not s.startswith("uploads/"):
        return None
    s = s.replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    cfg = _cfg()
    if cfg["prefix"]:
        return f'{cfg["prefix"]}/{s}'
    return s


def probe_object_storage() -> Dict[str, Any]:
    started = time.time()
    status = object_storage_status()
    out: Dict[str, Any] = {
        "ok": False,
        "configured": status["configured"],
        "enabled": status["enabled"],
        "driver_installed": status["driver_installed"],
        "latency_ms": None,
        "error": None,
        "bucket": status.get("bucket_configured"),
        "provider": status.get("provider"),
        "setup_hint": status.get("setup_hint"),
    }
    if not status["configured"]:
        out["error"] = "Railway Bucket not linked — Create Bucket and add Variable References"
        return out
    if not status["driver_installed"]:
        out["error"] = "boto3 not installed"
        return out
    if not status["enabled"]:
        out["error"] = "Object storage configured but disabled (LQ_OBJECT_STORAGE_ENABLED=0)"
        return out
    try:
        client, cfg = _client()
        client.head_bucket(Bucket=cfg["bucket"])
        out["ok"] = True
        out["bucket_name"] = cfg["bucket"]
        out["endpoint_url"] = cfg["endpoint_url"] or None
        _set_error(None)
    except Exception as exc:
        out["error"] = str(exc)
        _set_error(str(exc))
    out["latency_ms"] = int((time.time() - started) * 1000)
    return out


def _set_error(msg: Optional[str]) -> None:
    global _LAST_ERROR
    with _LOCK:
        _LAST_ERROR = msg


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
    global _LAST_WRITE
    started = time.time()
    result: Dict[str, Any] = {"ok": False, "key": key, "bytes": len(data or b""), "skipped": False}
    status = object_storage_status()
    if not status.get("cloud_ready"):
        result["skipped"] = True
        result["ok"] = True
        result["reason"] = "cloud object storage not configured"
        return result
    try:
        client, cfg = _client()
        client.put_object(
            Bucket=cfg["bucket"],
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        result["ok"] = True
        result["bucket"] = cfg["bucket"]
        _set_error(None)
    except Exception as exc:
        result["error"] = str(exc)
        _set_error(str(exc))
    result["latency_ms"] = int((time.time() - started) * 1000)
    with _LOCK:
        _LAST_WRITE = {
            "ok": result["ok"],
            "key": key,
            "bytes": result["bytes"],
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": result.get("error"),
        }
    return result


def get_bytes(key: str) -> Tuple[Optional[bytes], Dict[str, Any]]:
    global _LAST_READ
    started = time.time()
    meta: Dict[str, Any] = {"ok": False, "key": key}
    status = object_storage_status()
    if not status.get("cloud_ready"):
        meta["skipped"] = True
        meta["reason"] = "cloud object storage not configured"
        return None, meta
    try:
        client, cfg = _client()
        resp = client.get_object(Bucket=cfg["bucket"], Key=key)
        body = resp["Body"].read()
        meta["ok"] = True
        meta["bytes"] = len(body)
        meta["content_type"] = resp.get("ContentType")
        _set_error(None)
        with _LOCK:
            _LAST_READ = {
                "ok": True,
                "key": key,
                "bytes": len(body),
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        meta["latency_ms"] = int((time.time() - started) * 1000)
        return body, meta
    except Exception as exc:
        meta["error"] = str(exc)
        meta["latency_ms"] = int((time.time() - started) * 1000)
        _set_error(str(exc))
        with _LOCK:
            _LAST_READ = {
                "ok": False,
                "key": key,
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(exc),
            }
        return None, meta


def delete_key(key: str) -> Dict[str, Any]:
    status = object_storage_status()
    result: Dict[str, Any] = {"ok": False, "key": key, "skipped": False}
    if not status.get("cloud_ready"):
        result["skipped"] = True
        result["ok"] = True
        return result
    try:
        client, cfg = _client()
        client.delete_object(Bucket=cfg["bucket"], Key=key)
        result["ok"] = True
        _set_error(None)
    except Exception as exc:
        result["error"] = str(exc)
        _set_error(str(exc))
    return result


def mirror_upload_url(url: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
    """Best-effort remote mirror after a local write. Never raises."""
    key = key_from_upload_url(url)
    if not key:
        return {"ok": False, "error": "invalid upload url", "skipped": True}
    try:
        return put_bytes(key, data, content_type)
    except Exception as exc:
        _set_error(str(exc))
        return {"ok": False, "error": str(exc), "key": key}


def delete_upload_url(url: str) -> Dict[str, Any]:
    key = key_from_upload_url(url)
    if not key:
        return {"ok": True, "skipped": True}
    try:
        return delete_key(key)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "key": key}


def fetch_upload_url(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Return (bytes, content_type) from object storage for a /uploads/... URL."""
    key = key_from_upload_url(url)
    if not key:
        return None, None
    data, meta = get_bytes(key)
    if data is None:
        return None, None
    return data, meta.get("content_type")


def put_backup_files(json_path, sqlite_path, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Upload automatic backup artifacts into the bucket under backups/."""
    from pathlib import Path

    status = object_storage_status()
    out: Dict[str, Any] = {"ok": False, "skipped": False, "uploaded": []}
    if not status.get("cloud_ready"):
        out["skipped"] = True
        out["ok"] = True
        out["reason"] = "cloud object storage not configured — local volume offsite active"
        return out
    stamp = str((meta or {}).get("timestamp") or time.strftime("%Y%m%d-%H%M%S"))
    prefix = (_cfg().get("prefix") or "").strip("/")
    base = f"{prefix}/backups/{stamp}" if prefix else f"backups/{stamp}"
    try:
        jp = Path(json_path)
        sp = Path(sqlite_path)
        if jp.exists():
            r = put_bytes(f"{base}/{jp.name}", jp.read_bytes(), "application/json")
            out["uploaded"].append({"key": f"{base}/{jp.name}", "ok": r.get("ok"), "error": r.get("error")})
        if sp.exists():
            r = put_bytes(f"{base}/{sp.name}", sp.read_bytes(), "application/octet-stream")
            out["uploaded"].append({"key": f"{base}/{sp.name}", "ok": r.get("ok"), "error": r.get("error")})
        out["ok"] = all(x.get("ok") for x in out["uploaded"]) if out["uploaded"] else False
        if not out["uploaded"]:
            out["error"] = "backup files missing"
        out["prefix"] = base
    except Exception as exc:
        out["error"] = str(exc)
        out["ok"] = False
        _set_error(str(exc))
    return out


def sync_local_tree(upload_dir, *, limit: int = 5000) -> Dict[str, Any]:
    """Upload local files under upload_dir that map to uploads/ keys."""
    from pathlib import Path
    import mimetypes

    root = Path(upload_dir).resolve()
    result: Dict[str, Any] = {
        "ok": False,
        "scanned": 0,
        "uploaded": 0,
        "skipped": 0,
        "errors": [],
        "ready": object_storage_status().get("cloud_ready"),
        "cloud_ready": object_storage_status().get("cloud_ready"),
    }
    if not result["ready"]:
        result["skipped"] = True
        result["ok"] = True
        result["errors"].append("cloud object storage not configured — local durable storage is active")
        return result
    if not root.exists():
        result["errors"].append("upload dir missing")
        return result
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        result["scanned"] += 1
        if result["scanned"] > limit:
            result["errors"].append(f"limit {limit} reached")
            break
        rel = path.relative_to(root).as_posix()
        url = f"/uploads/{rel}"
        try:
            data = path.read_bytes()
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            put = mirror_upload_url(url, data, ctype)
            if put.get("ok") and not put.get("skipped"):
                result["uploaded"] += 1
            else:
                result["skipped"] += 1
                if put.get("error"):
                    result["errors"].append(f"{rel}: {put.get('error')}")
        except Exception as exc:
            result["errors"].append(f"{rel}: {exc}")
    result["ok"] = len(result["errors"]) == 0
    return result
