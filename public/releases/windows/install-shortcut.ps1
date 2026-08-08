# NAJJAR desktop shortcut — NO EXE download (avoids browser SmartScreen blocks)
$ErrorActionPreference = "Stop"

$base = "https://web-production-08d73.up.railway.app"
$appUrl = "$base/najjar-al-samoom-used-imported-cars/login.html"
$desktop = [Environment]::GetFolderPath("Desktop")

Write-Host "جاري إنشاء اختصار NAJJAR Trading على سطح المكتب..." -ForegroundColor Cyan

foreach ($old in @("Launch Quality.lnk", "LaunchQuality.lnk", "NAJJAR Trading.lnk", "NAJJAR Trading.url")) {
  $p = Join-Path $desktop $old
  if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
}

function Find-Browser {
  $candidates = @(
    (Join-Path ${env:ProgramFiles} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path ${env:ProgramFiles} "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
  )
  foreach ($p in $candidates) {
    if ($p -and (Test-Path $p)) { return $p }
  }
  return $null
}

$browser = Find-Browser
$urlPath = Join-Path $desktop "NAJJAR Trading.url"
$urlBody = @"
[InternetShortcut]
URL=$appUrl
IconFile=$base/releases/windows/portable/AppIcon.ico
IconIndex=0
"@
Set-Content -Path $urlPath -Value $urlBody -Encoding ASCII

if ($browser) {
  $lnkPath = Join-Path $desktop "NAJJAR Trading.lnk"
  $wsh = New-Object -ComObject WScript.Shell
  $s = $wsh.CreateShortcut($lnkPath)
  $s.TargetPath = $browser
  $s.Arguments = "--new-window --start-maximized `"$appUrl`""
  $s.WindowStyle = 1
  $s.Description = "NAJJAR & AL SAMOOM TRADING"
  $ico = Join-Path $env:LOCALAPPDATA "NAJJAR-Trading\AppIcon.ico"
  if (-not (Test-Path $ico)) {
    $icoDir = Split-Path $ico -Parent
    New-Item -ItemType Directory -Force -Path $icoDir | Out-Null
    try {
      Invoke-WebRequest -Uri "$base/releases/windows/portable/AppIcon.ico" -OutFile $ico -UseBasicParsing
    } catch { $ico = $null }
  }
  if ($ico -and (Test-Path $ico)) { $s.IconLocation = "$ico,0" }
  $s.Save()
  Write-Host "تم: $lnkPath" -ForegroundColor Green
  Start-Process $browser -ArgumentList $s.Arguments
} else {
  Write-Host "تم: $urlPath" -ForegroundColor Green
  Start-Process $urlPath
}

Write-Host "NAJJAR Trading جاهز على سطح المكتب — بدون تنزيل EXE." -ForegroundColor Green
