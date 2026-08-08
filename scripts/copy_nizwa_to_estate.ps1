# Copy Nizwa seed units into estate_* via existing REST APIs (duplicate only).
# Usage:
#   $env:ADMIN_PASSWORD = '***'
#   .\scripts\copy_nizwa_to_estate.ps1
# Optional:
#   -BaseUrl https://web-production-08d73.up.railway.app
#   -Token <existing-bearer-token>
param(
  [string]$BaseUrl = "https://web-production-08d73.up.railway.app",
  [string]$AdminUser = "admin",
  [string]$AdminPass = $env:ADMIN_PASSWORD,
  [string]$Token = $env:JAWDAH_TOKEN
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$seedPath = Join-Path $root "public\quick-estate\seed_units.json"
if (-not (Test-Path $seedPath)) { throw "Missing seed: $seedPath" }
$units = Get-Content $seedPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Status-Map([string]$s) {
  switch ($s) {
    "شاغرة" { return "vacant" }
    "مؤجرة" { return "occupied" }
    "محجوزة" { return "reserved" }
    "صيانة" { return "maintenance" }
    default { return "vacant" }
  }
}

function Post-Json([string]$Path, $Body) {
  $uri = "$BaseUrl/api/$Path"
  $headers = @{ Authorization = "Bearer $script:authToken"; "Content-Type" = "application/json; charset=utf-8" }
  $json = $Body | ConvertTo-Json -Depth 8 -Compress
  return Invoke-RestMethod -Uri $uri -Method POST -Headers $headers -Body ([Text.Encoding]::UTF8.GetBytes($json))
}

function Get-Json([string]$Path) {
  $uri = "$BaseUrl/api/$Path"
  $headers = @{ Authorization = "Bearer $script:authToken" }
  return Invoke-RestMethod -Uri $uri -Method GET -Headers $headers
}

if ($Token) {
  $script:authToken = $Token
  Write-Host "Using provided token"
} else {
  if (-not $AdminPass) { throw "Set ADMIN_PASSWORD or -Token" }
  Write-Host "Login $AdminUser @ $BaseUrl ..."
  $login = Invoke-RestMethod -Uri "$BaseUrl/api/login" -Method POST -ContentType "application/json" -Body (@{ username = $AdminUser; password = $AdminPass } | ConvertTo-Json)
  if (-not $login.token) { throw "Login failed" }
  $script:authToken = $login.token
}

$MARKER = "source:nizwa_qe_portfolio"
$today = (Get-Date).ToString("yyyy-MM-dd")
$created = @{ property = 0; buildings = 0; apartments = 0; clients = 0; skipped = 0 }

# Prefer new endpoint if deployed
try {
  $copy = Post-Json "estate_copy_from_nizwa" @{ }
  if ($copy.ok) {
    Write-Host "Server-side copy OK:"
    $copy | ConvertTo-Json -Depth 6
    exit 0
  }
} catch {
  Write-Host "Note: estate_copy_from_nizwa not available yet — falling back to seed API copy"
}

$props = @()
try { $props = @(Get-Json "estate_properties").items } catch { $props = @() }
$prop = $props | Where-Object { $_.notes -like "*$MARKER*" } | Select-Object -First 1
if (-not $prop) {
  $propResp = Post-Json "estate_properties" @{
    name = "عقارات نزوى — حي التراث"
    status = "active"
    location = "حي التراث، نزوى، محافظة الداخلية، سلطنة عمان"
    building_count = @($units | Select-Object -ExpandProperty building_no -Unique).Count
    apartment_count = $units.Count
    room_count = 0
    base_rent_price = 0
    service_charge = 0
    attachments = "[]"
    manager_name = "إدارة نزوى"
    notes = "نسخة من منصة عقارات نزوى (seed) · $MARKER"
    last_update = $today
  }
  $propId = $propResp.item.id
  if (-not $propId) { $propId = $propResp.id }
  $created.property = 1
  Write-Host "Created property $propId"
} else {
  $propId = $prop.id
  Write-Host "Using existing property $propId"
}

$bldMap = @{}
$buildings = @()
try { $buildings = @(Get-Json "estate_buildings").items } catch { $buildings = @() }
foreach ($bno in ($units.building_no | Sort-Object -Unique)) {
  $bMarker = "${MARKER}:building:$bno"
  $existing = $buildings | Where-Object { $_.notes -like "*$bMarker*" -and $_.property_id -eq $propId } | Select-Object -First 1
  if ($existing) {
    $bldMap[$bno] = $existing.id
    continue
  }
  $cnt = @($units | Where-Object { $_.building_no -eq $bno }).Count
  $bResp = Post-Json "estate_buildings" @{
    property_id = $propId
    name = "بناية $bno"
    status = "active"
    location = "حي التراث، نزوى، محافظة الداخلية، سلطنة عمان"
    unit_count = $cnt
    apartment_count = $cnt
    room_count = 0
    base_rent_price = 0
    service_charge = 0
    attachments = "[]"
    notes = "نسخ من عقارات نزوى · $bMarker"
    last_update = $today
  }
  $bid = $bResp.item.id; if (-not $bid) { $bid = $bResp.id }
  $bldMap[$bno] = $bid
  $created.buildings++
  Write-Host "  building $bno -> $bid"
}

$apts = @()
try { $apts = @(Get-Json "estate_apartments").items } catch { $apts = @() }
$clients = @()
try { $clients = @(Get-Json "clients").items } catch { $clients = @() }

$i = 0
foreach ($u in $units) {
  $i++
  $unitMarker = "source:qe_seed:$($u.building_no)-$($u.apartment_no)"
  $exists = $apts | Where-Object { $_.notes -like "*$unitMarker*" } | Select-Object -First 1
  if ($exists) { $created.skipped++; continue }

  $clientId = $null
  $tenant = [string]$u.tenant_name
  $phone = [string]$u.phone
  if ($tenant) {
    $cMarker = "source:qe_tenant_seed:$($u.building_no)-$($u.apartment_no)"
    $cExisting = $clients | Where-Object { $_.notes -like "*$cMarker*" -or ($_.name -eq $tenant -and $_.phone -eq $phone) } | Select-Object -First 1
    if ($cExisting) {
      $clientId = $cExisting.id
    } else {
      $cResp = Post-Json "clients" @{
        name = $tenant
        phone = $phone
        email = ""
        national_id = [string]$u.identity_no
        balance = 0
        notes = "نسخ من عقارات نزوى · $cMarker"
      }
      $clientId = $cResp.item.id; if (-not $clientId) { $clientId = $cResp.id }
      $created.clients++
      $clients += [pscustomobject]@{ id = $clientId; name = $tenant; phone = $phone; notes = $cMarker }
    }
  }

  $st = Status-Map ([string]$u.status)
  $rent = [double]$u.rent_amount
  if ($rent -le 0) { $rent = [double]$u.average_rent }
  $payload = @{
    property_id = $propId
    building_id = $bldMap[[int]$u.building_no]
    name = "شقة $($u.apartment_no)"
    unit_kind = "شقة كاملة"
    status = $st
    room_count = [int]$u.rooms_count
    rent_price = $rent
    booking_deposit = 0
    prepaid_amount = 0
    reservation_start_date = $(if ($u.contract_start) { [string]$u.contract_start } else { $null })
    reservation_end_date = $(if ($u.contract_end) { [string]$u.contract_end } else { $null })
    booked_client_name = $(if ($st -eq "reserved") { $tenant } else { "" })
    booked_client_phone = $(if ($st -eq "reserved") { $phone } else { "" })
    booked_client_id = $(if ($st -eq "reserved") { $clientId } else { $null })
    tenant_client_id = $clientId
    tenant_phone = $phone
    attachments = "[]"
    notes = "نسخ من عقارات نزوى · $unitMarker · excel:$($u.original_excel_ref) · حمام:$($u.bathroom) · خدمات:$($u.services)"
    last_update = $today
  }
  Post-Json "estate_apartments" $payload | Out-Null
  $created.apartments++
  if (($i % 10) -eq 0) { Write-Host "  ... $i / $($units.Count)" }
}

Write-Host ""
Write-Host "DONE copy (qe seed → estate). Original Nizwa data untouched."
$created | ConvertTo-Json
Write-Host "units in seed: $($units.Count) | created apartments: $($created.apartments) | skipped: $($created.skipped)"
