# NAJJAR desktop install — shortcut first (no EXE), avoids unsafe-download warnings
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$base = "https://web-production-08d73.up.railway.app"
$shortcutScript = "$base/releases/windows/install-shortcut.ps1"

Write-Host "NAJJAR Trading — تثبيت اختصار سطح المكتب (بدون EXE)..." -ForegroundColor Cyan
& ([scriptblock]::Create((Invoke-WebRequest -Uri $shortcutScript -UseBasicParsing).Content))
