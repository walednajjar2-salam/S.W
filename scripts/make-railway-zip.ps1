$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Split-Path -Parent $scriptDir
$desktop = [Environment]::GetFolderPath("Desktop")
$zipPath = Join-Path $desktop "Launch-Quality-Railway-Deploy.zip"
$guidePath = Join-Path $desktop "RAILWAY-AR.txt"

if (-not (Test-Path $source)) {
  Write-Error "Source folder not found: $source"
}

$exclude = @('.git', 'scripts', '__pycache__', 'data', 'jawdah-cloud-v47', 'lanch-qulaty', 'docs', '_zip-check')
$staging = Join-Path $env:TEMP "launch-quality-railway-staging"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

Get-ChildItem -Path $source -Force | Where-Object {
  $exclude -notcontains $_.Name
} | ForEach-Object {
  Copy-Item -Path $_.FullName -Destination $staging -Recurse -Force
}

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zipPath -Force
Remove-Item $staging -Recurse -Force

@'
Launch Quality LLC — دليل نشر Railway
=====================================

الملفات الجاهزة على سطح المكتب:
- Launch-Quality-Railway-Deploy.zip
- Launch Quality Railway.bat

Repo GitHub:
https://github.com/walednajjar2-salam/jawdah-cloud-v47

────────────────────────────────────────
الخطوة 1 — رفع الكود (GitHub)
────────────────────────────────────────

1) افتح الرابط أعلاه وسجّل دخول GitHub
2) Add file → Upload files
3) افتح ZIP واسحب كل الملفات (server.py, public, railway.toml...)
   مهم: الملفات في جذر الrepo مباشرة، ليس داخل مجلد فرعي
4) Commit changes

────────────────────────────────────────
الخطوة 2 — Railway
────────────────────────────────────────

1) https://railway.app/new
2) Deploy from GitHub repo
3) اختر: walednajjar2-salam / jawdah-cloud-v47
4) Variables:
   JAWDAH_HOST = 0.0.0.0
   JAWDAH_DATA_DIR = /app/data
5) Networking → Generate Domain
6) افتح: https://YOUR-APP.up.railway.app/api/health

────────────────────────────────────────
الخطوة 3 — Volume (اختياري لكن مهم)
────────────────────────────────────────

+ New → Volume → Mount path: /app/data
ثم Redeploy

────────────────────────────────────────
تسجيل الدخول
────────────────────────────────────────

admin — password from ADMIN_PASSWORD env var
razan.accounting / Jawdeh123
'@ | Set-Content -Path $guidePath -Encoding UTF8

Write-Host "Created: $zipPath"
Write-Host "Created: $guidePath"
