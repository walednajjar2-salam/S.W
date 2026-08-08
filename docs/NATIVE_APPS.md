# Native apps (Windows + Android)

NAJJAR ships as a **web app** in thin native shells.

## Canonical URL

```
https://web-production-08d73.up.railway.app/najjar-al-samoom-used-imported-cars/login.html
```

Shared via `scripts/najjar_app_url.sh` or `LQ_APP_URL`.

## Download

| Platform | Page | Artifact |
|----------|------|----------|
| Android | `/get-android` | `/releases/android/NAJJAR-Trading.apk` |
| Windows | `/get-windows` | `/LaunchQuality.exe` + `/lq-portable.zip` |

## Build (from repo root)

```bash
./scripts/build_windows_launcher.sh
./scripts/build_android_webview_apk.sh
```

Env: `LQ_APP_URL`, `LQ_APP_VERSION`, `LQ_APP_VERSION_CODE`.

## Android

- Package: `com.launchquality.staff` (sideload upgrades)
- Label: **NAJJAR Trading**
- WebView + cookies/localStorage

## Windows

- Go launcher → Edge/Chrome full window
- ZIP: extract → `1-تثبيت-الآن.bat` → shortcut **NAJJAR Trading**

Update `public/releases/windows/latest.json` after version bumps.
