#!/usr/bin/env python3
"""Nothing is published while LQ_SITE_PUBLISHED and LQ_NAJJAR_PUBLISHED are both off."""
from __future__ import annotations

import urllib.error
import urllib.request

ORIGIN = "http://127.0.0.1:8765"

CLOSED = "/closed"

# Paths that must redirect to /closed when publishing is fully off
MUST_CLOSE = [
    "/",
    "/index.html",
    "/najjar",
    "/najjar/",
    "/najjar/customer.html",
    "/auto-trading/customer.html",
    "/auto-trading/login.html",
    "/auto-trading/platforms.html",
    "/app.html",
    "/portal-select.html",
    "/erp",
    "/go.html",
]

# Paths that stay reachable for device cleanup
MUST_STAY = [
    "/closed",
    "/remove",
    "/fresh",
    "/sw.js",
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(path: str):
    opener = urllib.request.build_opener(NoRedirect)
    try:
        return opener.open(ORIGIN + path, timeout=5)
    except urllib.error.HTTPError as e:
        return e


def main() -> int:
    fails = 0
    try:
        probe = fetch("/najjar/customer.html")
        if probe.status == 200:
            print("SKIP  server has LQ_NAJJAR_PUBLISHED=1 (NAJJAR live at /najjar/)")
            print("      restart with LQ_NAJJAR_PUBLISHED=0 to run this test")
            print("      use scripts/test_najjar_path.py for the default mode")
            return 0
    except Exception:
        pass
    try:
        urllib.request.urlopen(ORIGIN + "/api/health", timeout=3).read()
    except Exception as exc:
        print(f"server not reachable at {ORIGIN}: {exc}")
        return 1

    for path in MUST_CLOSE:
        resp = fetch(path)
        loc = resp.headers.get("Location", "")
        ok = resp.status in (301, 302) and loc.startswith(CLOSED)
        print(f"{'PASS' if ok else 'FAIL'}  {path:34s} -> {resp.status} {loc!r}")
        if not ok:
            fails += 1

    for path in MUST_STAY:
        resp = fetch(path)
        loc = resp.headers.get("Location", "")
        ok = resp.status == 200 or (resp.status in (301, 302) and "remove-old-app" in loc)
        if path == "/remove":
            body = resp.read(8000).decode("utf-8", "replace")
            ok = resp.status == 200 and "إزالة التطبيق القديم" in body
        if path == "/closed":
            ok = resp.status == 200 and "النشر متوقف" in resp.read(4000).decode("utf-8", "replace")
        if path == "/fresh":
            ok = resp.status == 200
        if path == "/sw.js":
            ok = resp.status == 200
        print(f"{'PASS' if ok else 'FAIL'}  {path:34s} stays open")
        if not ok:
            fails += 1

    try:
        req = urllib.request.Request(
            ORIGIN + "/api/auto-trading/showroom",
            method="GET",
        )
        urllib.request.urlopen(req, timeout=5)
        print("FAIL  public showroom API still open")
        fails += 1
    except urllib.error.HTTPError as e:
        ok = e.code == 503
        print(f"{'PASS' if ok else 'FAIL'}  /api/auto-trading/showroom -> {e.code}")
        if not ok:
            fails += 1

    print()
    if fails:
        print(f"{fails} check(s) failed")
        return 1
    print("Site unpublished: OK — only /closed and cleanup paths respond")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
