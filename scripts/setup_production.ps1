# Quality of Launch Services LLC - production bootstrap
param(
  [string]$BaseUrl = "https://web-production-08d73.up.railway.app",
  [string]$AdminUser = "admin",
  [string]$AdminPass = $env:ADMIN_PASSWORD
)

if (-not $AdminPass) { throw "Set ADMIN_PASSWORD environment variable or pass -AdminPass" }

$ErrorActionPreference = "Stop"
$settingsPath = Join-Path (Split-Path $PSScriptRoot -Parent) "data\company_settings.json"
if (-not (Test-Path $settingsPath)) { throw "Missing company_settings.json at $settingsPath" }
$settings = Get-Content $settingsPath -Raw -Encoding UTF8

Write-Host "Logging in as $AdminUser..."
$login = Invoke-RestMethod -Uri "$BaseUrl/api/login" -Method POST -Body (@{username=$AdminUser;password=$AdminPass}|ConvertTo-Json) -ContentType "application/json; charset=utf-8"
$headers = @{ Authorization = "Bearer $($login.token)" }

Write-Host "Saving company settings..."
$saved = Invoke-RestMethod -Uri "$BaseUrl/api/company_settings" -Method PUT -Headers $headers -Body $settings -ContentType "application/json; charset=utf-8"
Write-Host "Company: $($saved.settings.name_ar)"

$requiredUsers = @(
  @{ username = "operations"; name = "Operations Team"; role = "operations"; password = "LaunchOps2026" },
  @{ username = "maintenance"; name = "Maintenance Team"; role = "maintenance"; password = "LaunchMaint2026" }
)

Write-Host "Ensuring team users..."
$boot = Invoke-RestMethod -Uri "$BaseUrl/api/bootstrap" -Headers $headers
$users = @($boot.data.users)
foreach ($req in $requiredUsers) {
  $existing = $users | Where-Object { $_.username -eq $req.username } | Select-Object -First 1
  if ($existing) {
    $body = @{ name = $req.name; role = $req.role; active = $true; password = $req.password } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl/api/users/$($existing.id)" -Method PUT -Headers $headers -Body $body -ContentType "application/json; charset=utf-8" | Out-Null
    Write-Host "  updated: $($req.username)"
  } else {
    $body = @{ username = $req.username; name = $req.name; role = $req.role; active = $true; password = $req.password } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl/api/users" -Method POST -Headers $headers -Body $body -ContentType "application/json; charset=utf-8" | Out-Null
    Write-Host "  created: $($req.username)"
  }
}

Write-Host "Current users:"
$boot2 = Invoke-RestMethod -Uri "$BaseUrl/api/bootstrap" -Headers $headers
foreach ($u in $boot2.data.users) {
  Write-Host ("  - {0} ({1}) name={2}" -f $u.username, $u.role, $u.name)
}

Write-Host "Verifying backup export..."
$backup = Invoke-RestMethod -Uri "$BaseUrl/api/backup" -Headers $headers
$tables = $backup.backup.data.PSObject.Properties.Name
Write-Host "Backup tables: $($tables.Count)"

Write-Host "DONE - open $BaseUrl and add properties, clients, and contracts."
