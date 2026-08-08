#!/usr/bin/env python3
"""NAJJAR is published under the English NAJJAR_BASE — legacy /najjar/* redirects."""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

ORIGIN = "http://127.0.0.1:8765"
CLOSED = "/closed"
NAJJAR = server.NAJJAR_BASE


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(path: str):
    opener = urllib.request.build_opener(NoRedirect)
    try:
        return opener.open(ORIGIN + path, timeout=5)
    except urllib.error.HTTPError as e:
        return e


def body_has(resp, needle: str) -> bool:
    try:
        return needle in resp.read(12000).decode("utf-8", "replace")
    except Exception:
        return False


def main() -> int:
    fails = 0
    try:
        urllib.request.urlopen(ORIGIN + "/api/health", timeout=3).read()
    except Exception as exc:
        print(f"server not reachable at {ORIGIN}: {exc}")
        return 1

    must_close = [
        "/",
    ]
    for path in must_close:
        resp = fetch(path)
        loc = resp.headers.get("Location", "")
        ok = resp.status in (301, 302) and loc.startswith(CLOSED)
        print(f"{'PASS' if ok else 'FAIL'}  {path:34s} -> {resp.status} {loc!r}")
        if not ok:
            fails += 1

    erp_to_najjar = [
        ("/index.html", NAJJAR + "/login.html"),
        ("/erp", NAJJAR + "/login.html"),
        ("/app.html", NAJJAR + "/login.html"),
        ("/portal-select.html", NAJJAR + "/login.html"),
    ]
    for path, target in erp_to_najjar:
        resp = fetch(path)
        loc = resp.headers.get("Location", "")
        ok = resp.status in (301, 302) and loc.startswith(target)
        print(f"{'PASS' if ok else 'FAIL'}  {path:34s} -> {resp.status} {loc!r}")
        if not ok:
            fails += 1

    legacy_to_najjar = [
        ("/auto-trading/customer.html", NAJJAR + "/customer.html"),
        ("/auto-trading/login.html", NAJJAR + "/login.html"),
        ("/auto-trading/platforms.html", NAJJAR + "/platforms.html"),
        ("/auto-trading.html", NAJJAR + "/staff.html"),
        ("/najjar/customer.html", NAJJAR + "/customer.html"),
        ("/najjar/login.html", NAJJAR + "/login.html"),
        ("/najjar/platforms.html", NAJJAR + "/platforms.html"),
        ("/najjar/staff.html", NAJJAR + "/staff.html"),
    ]
    for path, target in legacy_to_najjar:
        resp = fetch(path)
        loc = resp.headers.get("Location", "")
        ok = resp.status in (301, 302) and loc.startswith(target)
        print(f"{'PASS' if ok else 'FAIL'}  {path:34s} -> {resp.status} {loc!r}")
        if not ok:
            fails += 1

    najjar_pages = [
        (NAJJAR + "/", "Featured Selection"),
        (NAJJAR + "/customer.html", "Featured Selection"),
        (NAJJAR + "/login.html", "Walid Najjar"),
        (NAJJAR + "/platforms.html", "Platforms"),
    ]
    for path, needle in najjar_pages:
        resp = fetch(path)
        ok = resp.status == 200 and body_has(resp, needle)
        print(f"{'PASS' if ok else 'FAIL'}  {path:34s} open ({needle})")
        if not ok:
            fails += 1

    resp = fetch("/auto-trading/auto-trading.css")
    ok = resp.status == 200
    print(f"{'PASS' if ok else 'FAIL'}  /auto-trading/auto-trading.css asset")
    if not ok:
        fails += 1

    try:
        data = urllib.request.urlopen(ORIGIN + "/api/auto-trading/showroom", timeout=5).read()
        ok = b'"ok"' in data
        print(f"{'PASS' if ok else 'FAIL'}  /api/auto-trading/showroom public")
        if not ok:
            fails += 1
    except urllib.error.HTTPError as e:
        print(f"FAIL  /api/auto-trading/showroom -> {e.code}")
        fails += 1

    try:
        health = urllib.request.urlopen(ORIGIN + "/api/health", timeout=5).read().decode()
        ok = NAJJAR.strip('"') in health or NAJJAR.replace("/", "") in health
        print(f"{'PASS' if ok else 'FAIL'}  /api/health reports najjar_base")
        if not ok:
            fails += 1
    except Exception as exc:
        print(f"FAIL  /api/health -> {exc}")
        fails += 1

    try:
        urllib.request.urlopen(ORIGIN + "/api/bootstrap", timeout=5)
        print("FAIL  /api/bootstrap still open")
        fails += 1
    except urllib.error.HTTPError as e:
        ok = e.code == 503
        print(f"{'PASS' if ok else 'FAIL'}  /api/bootstrap -> {e.code} (ERP retired)")
        if not ok:
            fails += 1

    print()
    if fails:
        print(f"{fails} check(s) failed")
        return 1
    print(f"NAJJAR path: OK — live at {NAJJAR}/, legacy /najjar/ redirects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
