# Cleanup duplicate Nizwa apartment properties and sync statuses on live
param(
  [string]$BaseUrl = "https://web-production-08d73.up.railway.app",
  [string]$AdminUser = "admin",
  [string]$AdminPass = $env:ADMIN_PASSWORD
)

if (-not $AdminPass) { throw "Set ADMIN_PASSWORD environment variable or pass -AdminPass" }

$ErrorActionPreference = "Stop"
$dataPath = Join-Path (Split-Path $PSScriptRoot -Parent) "data\nizwa_apartments.json"
$payload = Get-Content $dataPath -Raw -Encoding UTF8 | ConvertFrom-Json
$today = (Get-Date).ToString("yyyy-MM-dd")

function Apt-No-From-Name($name) {
  foreach ($part in ($name -split '\s+')) {
    if ($part -match '^\d+$') { return $part }
  }
  return $null
}

function Invoke-Api($Method, $Url, $Headers, $BodyObj = $null) {
  $params = @{ Uri = $Url; Method = $Method; Headers = $Headers }
  if ($BodyObj) {
    $params.Body = ($BodyObj | ConvertTo-Json -Depth 6 -Compress)
    $params.ContentType = "application/json; charset=utf-8"
  }
  return Invoke-RestMethod @params
}

Write-Host "Login..."
$login = Invoke-RestMethod -Uri "$BaseUrl/api/login" -Method POST -Body (@{username=$AdminUser;password=$AdminPass}|ConvertTo-Json) -ContentType "application/json"
$h = @{ Authorization = "Bearer $($login.token)" }

$props = @(Invoke-Api GET "$BaseUrl/api/properties" $h).items
$contracts = @(Invoke-Api GET "$BaseUrl/api/contracts" $h).items
$clients = @(Invoke-Api GET "$BaseUrl/api/clients" $h).items

$contractByProp = @{}
foreach ($c in $contracts) {
  if ($c.property_id) { $contractByProp[$c.property_id] = $c }
}

$aptStatus = @{}
foreach ($apt in $payload.apartments) { $aptStatus[[string]$apt.no] = $apt.status }

$deleted = 0
$updated = 0
$groups = @{}

foreach ($p in $props) {
  $no = Apt-No-From-Name $p.name
  $isNizwa = ($p.type -eq "Apartment") -or ($p.location -match '611|nizwa|Turath') -or ($null -ne $no -and $no -match '^(10[1-5]|11[9-9]|12[0-2])$')
  if (-not $no -and $p.name -match 'Deploy Test') {
    Write-Host "  DELETE test property $($p.name)"
    Invoke-Api DELETE "$BaseUrl/api/properties/$($p.id)" $h | Out-Null
    $deleted++
    continue
  }
  if (-not $no -or -not $isNizwa) { continue }
  if (-not $groups.ContainsKey($no)) { $groups[$no] = @() }
  $groups[$no] += $p
}

function Prop-Score($p) {
  $s = 0
  $con = $contractByProp[$p.id]
  if ($con) { $s += 10 }
  if ($p.status -eq "Rented") { $s += 5 }
  if ($p.status -eq "Vacant") { $s += 1 }
  return $s
}

foreach ($no in $groups.Keys | Sort-Object) {
  $list = @($groups[$no])
  if ($list.Count -le 1) {
    $keep = $list[0]
  } else {
    $keep = $list | Sort-Object { Prop-Score $_ } -Descending | Select-Object -First 1
    foreach ($p in $list) {
      if ($p.id -eq $keep.id) { continue }
      $hasContract = $contractByProp.ContainsKey($p.id)
      if (-not $hasContract -and $p.status -eq "Vacant") {
        Write-Host "  DELETE duplicate apt $no -> $($p.id)"
        try {
          Invoke-Api DELETE "$BaseUrl/api/properties/$($p.id)" $h | Out-Null
          $deleted++
        } catch {
          Write-Host "    skip (linked): $($_.Exception.Message)"
        }
      } else {
        Write-Host "  KEEP duplicate apt $no (linked) -> $($p.id)"
      }
    }
  }

  $targetStatus = if ($aptStatus[$no] -eq "rented") { "Rented" } else { "Vacant" }
  $con = $contractByProp[$keep.id]
  if ($no -eq "104" -and $con -and $con.end_date -and $con.end_date -lt $today) {
    $targetStatus = "Vacant"
  }

  if ($keep.status -ne $targetStatus) {
    $body = @{
      name = $keep.name
      type = $keep.type
      status = $targetStatus
      price = [double]$keep.price
      location = $keep.location
      image = $keep.image
      last_update = $today
      notes = $keep.notes
    }
    Invoke-Api PUT "$BaseUrl/api/properties/$($keep.id)" $h $body | Out-Null
    Write-Host "  UPDATE apt $no status -> $targetStatus"
    $updated++
  }
}

Write-Host ""
Write-Host "CLEANUP DONE"
Write-Host "Deleted: $deleted"
Write-Host "Updated: $updated"
Write-Host "Open: $BaseUrl"
