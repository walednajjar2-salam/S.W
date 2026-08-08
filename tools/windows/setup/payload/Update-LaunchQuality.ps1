param(
    [string]$ManifestUrl = "https://web-production-08d73.up.railway.app/releases/windows/latest.json",
    [string]$WorkDir = "$env:ProgramData\LaunchQuality\Updater",
    [string]$CurrentVersionFile = "$env:ProgramData\LaunchQuality\version.txt",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] $Message"
}

function Get-SafeVersion {
    param([string]$Raw)
    try {
        return [version]($Raw -replace "[^0-9\.]", "")
    } catch {
        return [version]"0.0.0"
    }
}

if (!(Test-Path $WorkDir)) {
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
}

$logFile = Join-Path $WorkDir "updater.log"
Start-Transcript -Path $logFile -Append | Out-Null

try {
    Write-Log "Fetching update manifest: $ManifestUrl"
    $manifest = Invoke-RestMethod -Uri $ManifestUrl -Method Get
    if (-not $manifest) { throw "Manifest is empty." }

    $latestVersionRaw = [string]($manifest.version)
    $installerUrl = [string]($manifest.installer_url)
    $sha256 = [string]($manifest.sha256)

    if ([string]::IsNullOrWhiteSpace($latestVersionRaw)) { throw "Manifest version is missing." }
    if ([string]::IsNullOrWhiteSpace($installerUrl)) { throw "Manifest installer_url is missing." }

    $currentVersionRaw = "0.0.0"
    if (Test-Path $CurrentVersionFile) {
        $currentVersionRaw = (Get-Content $CurrentVersionFile -Raw).Trim()
    }

    $currentVersion = Get-SafeVersion $currentVersionRaw
    $latestVersion = Get-SafeVersion $latestVersionRaw

    Write-Log "Current version: $currentVersionRaw"
    Write-Log "Latest version: $latestVersionRaw"

    if ((-not $Force) -and ($latestVersion -le $currentVersion)) {
        Write-Log "No update required."
        exit 0
    }

    $installerPath = Join-Path $WorkDir "LaunchQuality-Setup-$latestVersionRaw.exe"
    Write-Log "Downloading installer: $installerUrl"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

    if (-not [string]::IsNullOrWhiteSpace($sha256)) {
        $actualHash = (Get-FileHash -Path $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $sha256.ToLowerInvariant()) {
            throw "SHA256 mismatch. expected=$sha256 actual=$actualHash"
        }
        Write-Log "SHA256 check passed."
    } else {
        Write-Log "SHA256 not provided in manifest; skipping hash check."
    }

    Write-Log "Running installer silently..."
    $proc = Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Installer exit code: $($proc.ExitCode)"
    }

    $targetDir = Split-Path $CurrentVersionFile -Parent
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    Set-Content -Path $CurrentVersionFile -Value $latestVersionRaw -Encoding UTF8
    Write-Log "Update completed successfully to version $latestVersionRaw"
    exit 0
} catch {
    Write-Log "Update failed: $($_.Exception.Message)"
    exit 1
} finally {
    Stop-Transcript | Out-Null
}

