# Local desktop shortcut — NO EXE required
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$appUrl = "https://web-production-08d73.up.railway.app/najjar-al-samoom-used-imported-cars/login.html"
$icon = Join-Path $here "AppIcon.ico"

foreach ($old in @("Launch Quality.lnk", "LaunchQuality.lnk", "NAJJAR Trading.lnk", "NAJJAR Trading.url")) {
  $p = Join-Path $desktop $old
  if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
}

$urlSrc = Join-Path $here "NAJJAR-Trading.url"
$urlDst = Join-Path $desktop "NAJJAR Trading.url"
if (Test-Path $urlSrc) {
  Copy-Item $urlSrc $urlDst -Force
} else {
  @"
[InternetShortcut]
URL=$appUrl
IconIndex=0
"@ | Set-Content $urlDst -Encoding ASCII
}

$browsers = @(
  (Join-Path ${env:ProgramFiles} "Microsoft\Edge\Application\msedge.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
  (Join-Path ${env:ProgramFiles} "Google\Chrome\Application\chrome.exe"),
  (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
)
$browser = $browsers | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($browser) {
  $lnk = Join-Path $desktop "NAJJAR Trading.lnk"
  $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
  $s.TargetPath = $browser
  $s.Arguments = "--new-window --start-maximized `"$appUrl`""
  $s.WorkingDirectory = $here
  $s.Description = "NAJJAR & AL SAMOOM TRADING"
  if (Test-Path $icon) { $s.IconLocation = "$icon,0" }
  $s.Save()
  Start-Process $browser -ArgumentList $s.Arguments
  Write-Host "تم: $lnk" -ForegroundColor Green
} else {
  Start-Process $urlDst
  Write-Host "تم: $urlDst" -ForegroundColor Green
}
