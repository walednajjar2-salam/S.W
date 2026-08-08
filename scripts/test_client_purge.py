#!/usr/bin/env python3
"""Prove that a released build actually reaches a device carrying an older one.

The complaint this guards against is that opening the company site on a staff
device launched a build that had been retired: an installed app had cached its
own shell in a service worker, so it answered before the network ever did and
shipping a release changed nothing on that device.

Two different devices need two different rescues, and testing only one of them
would leave half the fleet stranded:

* A retired worker that passed navigations through to the network (or a device
  with no worker at all, just a stale HTTP cache) does reach the server, so the
  ``Clear-Site-Data`` header on the page response wipes it. Scenario B.
* A retired worker that answered navigations from its own cache never lets a
  request out, so that header can never arrive. The only thing that still leaves
  the device is the browser's own check for a newer copy of the worker script —
  which is why ``public/sw.js`` is kept on disk as a worker whose only job is to
  delete itself and everything it cached. Scenario A.

Both scenarios run against a real Chrome, because every claim here is about
browser behaviour rather than about our own code.

Run: python3 scripts/test_client_purge.py [--trace]
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402  (path set above)

TRACE = "--trace" in sys.argv

CHROME_CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]

CURRENT_BUILD = "CURRENT BUILD FROM SERVER"
RETIRED_BUILD = "RETIRED BUILD FROM DEVICE CACHE"

# The retired worker, in its most stubborn form: it answers navigations out of its
# own cache, so nothing it serves ever consults the network.
CACHE_FIRST_SW = """
self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open('retired-shell');
    await c.put('/', new Response(
      '<!doctype html><title>retired</title><body data-build="%s">retired</body>',
      { headers: { 'Content-Type': 'text/html' } }));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
  if (e.request.mode === 'navigate') {
    e.respondWith(caches.match('/').then((r) => r || fetch(e.request)));
  }
});
""" % RETIRED_BUILD

# The retired worker in its milder form: it caches assets but lets navigations
# through, so the server still gets a chance to speak.
PASSTHROUGH_SW = """
self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open('retired-assets');
    await c.put('/stale-asset.txt', new Response('stale'));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));
"""

RETIRED_PAGE = """<!doctype html><meta charset="utf-8"><title>installing</title>
<body data-build="{build}">
<script>
  localStorage.setItem('jawdah_cloud_token', 'stale-token');
  // Max-Age, matching the login response in server.py. A cookie without one is a
  // session cookie and dies when the browser closes, which would look like the
  // purge destroying the session when nothing of the sort happened.
  document.cookie = 'lq_token=signed-in-session; Path=/; Max-Age=86400; SameSite=Lax';
  navigator.serviceWorker.register('/sw.js').then(() => navigator.serviceWorker.ready)
    .then(() => {{ document.title = 'ready'; }})
    .catch((e) => {{ document.title = 'failed: ' + e; }});
</script>
"""

# The current build registers nothing. That is the other half of the fix: a page
# that still called register() would hand the device a fresh worker moments after
# the purge removed the old one, and the cleanup would undo itself every visit.
CURRENT_PAGE = f"""<!doctype html><meta charset="utf-8"><title>current</title>
<body data-build="{CURRENT_BUILD}">current build
"""

SELF_DESTRUCT_SW = (ROOT / "public" / "sw.js").read_text()


class Fixture(ThreadingHTTPServer):
    daemon_threads = True
    phase = "retired"        # "retired" installs the old worker; "current" is the release
    retired_sw = CACHE_FIRST_SW
    purge_hits = 0
    sw_fetches = 0


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # keep the test output readable
        pass

    def _send(self, raw: bytes, ctype: str, purge: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if purge:
            # Byte-for-byte what server.py sends, imported rather than retyped so
            # this cannot quietly drift away from production.
            self.send_header("Clear-Site-Data", server.CLIENT_PURGE_DIRECTIVES)
            self.send_header(
                "Set-Cookie",
                "{}={}; Path=/; Max-Age=31536000; SameSite=Lax".format(
                    server.CLIENT_PURGE_COOKIE, server.CLIENT_PURGE_GENERATION
                ),
            )
            self.server.purge_hits += 1
        self.end_headers()
        self.wfile.write(raw)
        if TRACE:
            print(f"      fixture <- {self.path:22s} phase={self.server.phase:8s} "
                  f"purge={'yes' if purge else 'no'}")

    def _purged_already(self) -> bool:
        """The same gate as server.client_needs_purge, so "once" is measured."""
        marker = f"{server.CLIENT_PURGE_COOKIE}={server.CLIENT_PURGE_GENERATION}"
        return marker in (self.headers.get("Cookie", "") or "")

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path == "/sw.js":
            self.server.sw_fetches += 1
            body = self.server.retired_sw if self.server.phase == "retired" else SELF_DESTRUCT_SW
            self._send(body.encode(), "application/javascript", False)
            return

        if path == "/favicon.ico":
            # Not HTML, so it must never carry the purge — mirroring the real
            # server, where only page loads do. An earlier version of this fixture
            # answered it as HTML and credited the header with a rescue that had
            # actually come in through a side door.
            self._send(b"", "image/x-icon", False)
            return

        if self.server.phase == "retired":
            self._send(RETIRED_PAGE.format(build=CURRENT_BUILD).encode(),
                       "text/html; charset=utf-8", False)
            return

        self._send(CURRENT_PAGE.encode(), "text/html; charset=utf-8",
                   not self._purged_already())


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_chrome() -> str:
    for name in CHROME_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("no Chrome binary found; cannot verify browser behaviour")


class Device:
    """A staff device: one Chrome profile, visited by a fresh browser each time.

    Every visit is its own Chrome process. Clearing site storage tears the
    renderer down mid-command, and a driver holding one long-lived websocket
    wedges at precisely the moment the cleanup being tested succeeds. Relaunching
    also matches what actually happens on a phone — the app is opened again — and
    the profile directory is what carries workers, caches and cookies between
    visits, exactly as a real device would.
    """

    def __init__(self, chrome: str, profile: Path) -> None:
        self.chrome = chrome
        self.profile = profile

    def _launch(self, port: int) -> subprocess.Popen:
        return subprocess.Popen(
            [
                self.chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                f"--user-data-dir={self.profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _shutdown(port: int) -> bool:
        """Ask Chrome to close itself so it flushes the profile to disk.

        SIGTERM does not: cookies written during the visit are lost, which reads
        exactly like the purge marker failing to persist and sends you looking for
        a bug in the header instead of in the harness.
        """
        import websocket

        try:
            raw = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=3
            ).read()
            endpoint = json.loads(raw).get("webSocketDebuggerUrl")
            if not endpoint:
                return False
            ws = websocket.create_connection(endpoint, timeout=8)
            try:
                ws.send(json.dumps({"id": 1, "method": "Browser.close", "params": {}}))
                ws.recv()
            finally:
                ws.close()
            return True
        except (urllib.error.URLError, OSError, ValueError,
                websocket.WebSocketException):
            return False

    @staticmethod
    def _page_socket(port: int, timeout: float = 25.0):
        import websocket

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json/list", timeout=2
                ).read()
                for t in json.loads(raw):
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        return websocket.create_connection(
                            t["webSocketDebuggerUrl"], timeout=20
                        )
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(0.4)
        raise SystemExit("Chrome never exposed a debuggable page")

    def visit(self, url: str, *, settle: float = 2.5, expression: str | None = None,
              clear_site: bool = False):
        """Open the site once and optionally read the device state back."""
        import websocket

        port = free_port()
        proc = self._launch(port)
        ws = None
        try:
            ws = self._page_socket(port)
            seq = {"n": 0}

            def cmd(method: str, **params):
                seq["n"] += 1
                mine = seq["n"]
                ws.send(json.dumps({"id": mine, "method": method, "params": params}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == mine:
                        if "error" in msg:
                            raise RuntimeError(f"{method}: {msg['error']}")
                        return msg.get("result", {})

            if clear_site:
                cmd("Network.enable")
                cmd("Network.clearBrowserCookies")
                cmd("Network.clearBrowserCache")

            try:
                cmd("Page.navigate", url=url)
            except (websocket.WebSocketTimeoutException,
                    websocket.WebSocketConnectionClosedException, OSError):
                # The purge can take the renderer down with it. The visit still
                # happened; the state it left behind is read on the next one.
                if TRACE:
                    print("      (renderer went down during navigation)")
                return None
            time.sleep(settle)

            if expression is None:
                return None
            for _ in range(12):
                try:
                    res = cmd("Runtime.evaluate", expression=expression,
                              awaitPromise=True, returnByValue=True)
                    if "exceptionDetails" not in res:
                        return res["result"].get("value")
                except (RuntimeError, websocket.WebSocketTimeoutException,
                        websocket.WebSocketConnectionClosedException, OSError):
                    pass
                time.sleep(0.6)
            return None
        finally:
            try:
                if ws:
                    ws.close()
            except OSError:
                pass
            self._shutdown(port)
            try:
                proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
            # The next launch must not race the flush, or registrations and cookies
            # appear to vanish on their own.
            time.sleep(1.0)


STATE_JS = """
(async () => {
  const regs = await navigator.serviceWorker.getRegistrations();
  const keys = (window.caches && caches.keys) ? await caches.keys() : [];
  let stored = null;
  try { stored = localStorage.getItem('jawdah_cloud_token'); } catch (e) { stored = 'blocked'; }
  return {
    workers: regs.length,
    caches: keys.length,
    token: stored,
    cookie: document.cookie,
    build: document.body ? document.body.getAttribute('data-build') : null,
    controlled: !!navigator.serviceWorker.controller
  };
})()
"""

READY_JS = ("(async()=>{await navigator.serviceWorker.ready;"
            "return (await navigator.serviceWorker.getRegistrations()).length})()")


def describe(label: str, state: dict) -> None:
    print(f"    {label:34s} build={state['build']!r}")
    print(f"    {'':34s} workers={state['workers']} caches={state['caches']} "
          f"controlled={state['controlled']} token={state['token']!r}")
    print(f"    {'':34s} cookies={state['cookie']!r}")


def run_scenario(device: Device, fixture: Fixture, origin: str, *,
                 name: str, retired_sw: str, expect_shell_from_cache: bool,
                 failures: list[str]) -> None:
    print(f"\n=== {name} ===")
    fixture.phase = "retired"
    fixture.retired_sw = retired_sw

    # 1 — the retired build takes hold of the device.
    device.visit(origin + "/", clear_site=True, expression=READY_JS)
    installed = device.visit(origin + "/", expression=READY_JS)
    if not installed:
        failures.append(f"{name}: the retired worker never installed; "
                        "nothing below would be meaningful")
        return

    # 2 — reproduce the complaint: the server has the new build, the device does not.
    before = device.visit(origin + "/", expression=STATE_JS)
    if before is None:
        failures.append(f"{name}: could not read the device state before the release")
        return
    describe("device before the release", before)
    if expect_shell_from_cache and before["build"] != RETIRED_BUILD:
        failures.append(
            f"{name}: expected the device to be serving its own cached shell, saw "
            f"{before['build']!r} — the rescue below would be credited for a problem "
            "that was never reproduced")
    if not before["controlled"]:
        failures.append(f"{name}: the retired worker is not controlling the page")

    # 3 — ship the release, then open the site the way a staff member would.
    fixture.phase = "current"
    sw_before = fixture.sw_fetches
    device.visit(origin + "/")
    after = device.visit(origin + "/", expression=STATE_JS)
    if after is None:
        failures.append(f"{name}: could not read the device state after the release")
        return
    describe("device after the release", after)
    print(f"    {'':34s} purge responses={fixture.purge_hits} "
          f"worker-script fetches={fixture.sw_fetches - sw_before}")

    if after["workers"]:
        failures.append(f"{name}: {after['workers']} retired worker(s) survived")
    if after["caches"]:
        failures.append(f"{name}: {after['caches']} stale cache(s) survived")
    if after["build"] != CURRENT_BUILD:
        failures.append(f"{name}: device still shows {after['build']!r}")

    # A signed-in staff member must not be thrown out by the cleanup: the session
    # rides in a cookie, and Clear-Site-Data leaves cookies alone.
    if "lq_token" not in (after["cookie"] or ""):
        failures.append(f"{name}: the session cookie was destroyed — every staff member "
                        "would be signed out by the cleanup")

    # 4 — and it must not keep happening.
    hits = fixture.purge_hits
    again = device.visit(origin + "/", expression=STATE_JS)
    if again is None:
        failures.append(f"{name}: could not read the device state on the following visit")
        return
    print(f"    {'next visit':34s} build={again['build']!r} workers={again['workers']} "
          f"extra purges={fixture.purge_hits - hits}")
    if again["build"] != CURRENT_BUILD or again["workers"]:
        failures.append(f"{name}: the device drifted back to a stale state")
    if fixture.purge_hits > hits:
        failures.append(f"{name}: the device was purged again after being marked clean — "
                        "staff would lose local state on every page load")


def main() -> int:
    chrome = find_chrome()
    fixture = Fixture(("127.0.0.1", free_port()), Handler)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{fixture.server_address[1]}"

    failures: list[str] = []
    profiles: list[Path] = []

    try:
        print(f"chrome     : {chrome}")
        print(f"fixture    : {origin}")
        print(f"directives : Clear-Site-Data: {server.CLIENT_PURGE_DIRECTIVES}")
        print(f"generation : {server.CLIENT_PURGE_GENERATION}")

        for name, retired_sw, cached_shell in (
            ("A · retired worker served the shell from its own cache "
             "(header cannot reach it; public/sw.js must)", CACHE_FIRST_SW, True),
            ("B · retired worker passed navigations through "
             "(Clear-Site-Data reaches it)", PASSTHROUGH_SW, False),
        ):
            # A separate profile per scenario: one device, one history. Reusing a
            # profile would let scenario A's cleaned state vouch for scenario B.
            profile = Path(tempfile.mkdtemp(prefix="lq-purge-profile-"))
            profiles.append(profile)
            run_scenario(
                Device(chrome, profile), fixture, origin,
                name=name, retired_sw=retired_sw,
                expect_shell_from_cache=cached_shell, failures=failures,
            )
    finally:
        fixture.shutdown()
        for profile in profiles:
            shutil.rmtree(profile, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: both kinds of device drop the retired build and land on the current")
    print("      one, signed-in sessions survive, and the cleanup does not repeat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
