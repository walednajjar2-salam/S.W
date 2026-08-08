#!/usr/bin/env bash
# Cross-compile NAJJAR Windows desktop launcher (opens Edge/Chrome to login).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/scripts/najjar_app_url.sh"

VERSION="${LQ_APP_VERSION:-70.5.2}"
LAUNCHER_DIR="$ROOT/tools/windows/launcher"
OUT_EXE="$ROOT/public/releases/windows/portable/NAJJAR-Trading.exe"
SETUP_EXE="$ROOT/public/releases/windows/NAJJAR-Trading-Setup.exe"
PORTABLE_ZIP="$ROOT/public/releases/windows/NAJJAR-Trading-Windows.zip"
PORTABLE_DIR="$ROOT/public/releases/windows/portable"
LEGACY_EXE="$ROOT/public/releases/windows/portable/LaunchQuality.exe"
LEGACY_SETUP="$ROOT/public/releases/windows/LaunchQuality-Setup.exe"
LEGACY_ZIP="$ROOT/public/releases/windows/LaunchQuality-Portable.zip"

echo "==> Building Windows launcher v${VERSION}"
echo "    URL: ${NAJJAR_APP_URL}"

(
  cd "$LAUNCHER_DIR"
  cp "$PORTABLE_DIR/AppIcon.ico" ./AppIcon.ico
  rm -f resource.syso
  if command -v goversioninfo >/dev/null 2>&1; then
    goversioninfo -64 -o resource.syso
  elif [[ -x "${GOPATH:-$HOME/go}/bin/goversioninfo" ]]; then
    "${GOPATH:-$HOME/go}/bin/goversioninfo" -64 -o resource.syso
  else
    echo "WARN: goversioninfo not found — EXE will ship without embedded metadata"
  fi
  GOOS=windows GOARCH=amd64 CGO_ENABLED=0 \
    LQ_APP_URL="$NAJJAR_APP_URL" \
    go build -ldflags="-H windowsgui -s -w" -o "$OUT_EXE" .
  rm -f resource.syso AppIcon.ico
)

cp "$OUT_EXE" "$SETUP_EXE"
cp "$OUT_EXE" "$LEGACY_EXE"
cp "$OUT_EXE" "$ROOT/public/releases/windows/LaunchQuality-Setup.exe"
echo "${VERSION}" > "$PORTABLE_DIR/VERSION.txt"

for f in Run-LaunchQuality.bat Run-LaunchQuality.vbs Open-LaunchQuality.html; do
  if [[ -f "$PORTABLE_DIR/$f" ]]; then
    sed -i "s|https://web-production-08d73.up.railway.app[^\"' ]*|${NAJJAR_APP_URL}|g" "$PORTABLE_DIR/$f" || true
  fi
done

(
  cd "$PORTABLE_DIR"
  rm -f "$PORTABLE_ZIP" "$LEGACY_ZIP"
  zip -r -9 "$PORTABLE_ZIP" . -x "*.DS_Store"
  cp "$PORTABLE_ZIP" "$LEGACY_ZIP"
)

ls -la "$OUT_EXE" "$SETUP_EXE" "$PORTABLE_ZIP"
echo "OK: NAJJAR-Trading Windows launcher"
