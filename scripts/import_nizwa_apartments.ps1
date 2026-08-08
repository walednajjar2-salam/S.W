# Import Nizwa Al-Turath apartment roster into Launch Quality cloud
param(
  [string]$BaseUrl = "https://web-production-08d73.up.railway.app",
  [string]$AdminUser = "admin",
  [string]$AdminPass = $env:ADMIN_PASSWORD
)

if (-not $AdminPass) { throw "Set ADMIN_PASSWORD environment variable or pass -AdminPass" }

$ErrorActionPreference = "Stop"
$dataPath = Join-Path (Split-Path $PSScriptRoot -Parent) "data\nizwa_apartments.json"
$payload = Get-Content $dataPath -Raw -Encoding UTF8 | ConvertFrom-Json

function To-Status($code) {
  if ($code -eq "rented") { return "Rented" }
  if ($code -eq "vacant") { return "Vacant" }
  return "Maintenance"
}

function Apt-No-From-Name($name) {
  foreach ($part in ($name -split '\s+')) {
    if ($part -match '^\d+$') { return $part }
  }
  return $null
}

function Post-Json($Url, $Headers, $BodyObj) {
  $body = $BodyObj | ConvertTo-Json -Depth 6 -Compress
  return Invoke-RestMethod -Uri $Url -Method POST -Headers $Headers -Body $body -ContentType "application/json; charset=utf-8"
}

Write-Host "Login..."
$login = Invoke-RestMethod -Uri "$BaseUrl/api/login" -Method POST -Body (@{username=$AdminUser;password=$AdminPass}|ConvertTo-Json) -ContentType "application/json"
$h = @{ Authorization = "Bearer $($login.token)" }
$today = (Get-Date).ToString("yyyy-MM-dd")

$existingProps = @{}
try {
  $propResp = Invoke-RestMethod -Uri "$BaseUrl/api/properties" -Headers $h
  foreach ($p in @($propResp.items)) {
    $no = Apt-No-From-Name $p.name
    if ($no) { $existingProps[$no] = $p.id }
  }
} catch { Write-Host "Note: could not prefetch properties" }

$clientMap = @{}
$existingContracts = @{}
try {
  $conResp = Invoke-RestMethod -Uri "$BaseUrl/api/contracts" -Headers $h
  foreach ($c in @($conResp.items)) {
    if ($c.property_id) { $existingContracts[$c.property_id] = $true }
  }
} catch { Write-Host "Note: could not prefetch contracts" }

$created = @{ properties = 0; clients = 0; contracts = 0; invoices = 0 }

foreach ($apt in $payload.apartments) {
  $propName = "شقة $($apt.no) - $($payload.building.name_ar)"
  $rent = [double]$apt.rent
  if ($rent -le 0) { $rent = [double]$apt.avg_rent }
  $propBody = @{
    name = $propName
    type = "Apartment"
    status = (To-Status $apt.status)
    price = $rent
    location = $payload.building.location
    image = "building"
    last_update = $today
    notes = "no $($apt.no) | $($apt.unit_type) | $($apt.rooms) rooms | $($apt.notes)"
  }

  if ($existingProps.ContainsKey([string]$apt.no)) {
    $propId = $existingProps[[string]$apt.no]
    Write-Host "  skip apt $($apt.no) property exists"
  } else {
    $prop = Post-Json "$BaseUrl/api/properties" $h $propBody
    $created.properties++
    $propId = $prop.item.id
    $existingProps[[string]$apt.no] = $propId
  }

  if ($apt.tenant -and $apt.tenant.Trim().Length -gt 0 -and $apt.status -eq "rented") {
    $tKey = $apt.tenant.Trim()
    if (-not $clientMap.ContainsKey($tKey)) {
      $clientBody = @{
        name = $tKey
        phone = ($apt.phone | ForEach-Object { $_ })
        email = ""
        national_id = ""
        balance = 0
        notes = $payload.building.location
      }
      $cl = Post-Json "$BaseUrl/api/clients" $h $clientBody
      $clientMap[$tKey] = $cl.item.id
      $created.clients++
    }
    $clientId = $clientMap[$tKey]

    if ($apt.status -eq "rented" -and $rent -gt 0) {
      if ($existingContracts.ContainsKey($propId)) {
        Write-Host "  skip apt $($apt.no) contract exists"
        continue
      }
      $start = if ($apt.start) { $apt.start } else { $today }
      $end = if ($apt.end) { $apt.end } else { (Get-Date $start).AddMonths(12).ToString("yyyy-MM-dd") }
      $contractBody = @{
        contract_type = "Residential"
        property_id = $propId
        client_id = $clientId
        tenant_nationality = "Omani"
        tenant_id_no = ""
        unit_details = "apt $($apt.no) - $($apt.unit_type) - $($apt.rooms) rooms"
        start_date = $start
        end_date = $end
        rent_amount = $rent
        deposit_amount = 0
        late_fee = 0
        grace_days = 5
        renewal_notice_days = 90
        status = "Active"
        payment_cycle = "monthly"
        notes = $apt.notes
      }
      $con = Post-Json "$BaseUrl/api/contracts" $h $contractBody
      $created.contracts++
      $contractId = $con.item.id

      $invBody = @{
        contract_id = $contractId
        due_date = $end
        description = "Rent invoice apt $($apt.no)"
        amount = $rent
      }
      $inv = Post-Json "$BaseUrl/api/invoice_from_contract" $h $invBody
      $created.invoices++
      Write-Host "  OK apt $($apt.no) -> $($inv.item.invoice_no)"
    }
  } else {
    Write-Host "  OK apt $($apt.no) (vacant)"
  }
}

Write-Host ""
Write-Host "IMPORT DONE"
Write-Host "Properties: $($created.properties)"
Write-Host "Clients: $($created.clients)"
Write-Host "Contracts: $($created.contracts)"
Write-Host "Invoices: $($created.invoices)"
Write-Host "Open: $BaseUrl"
