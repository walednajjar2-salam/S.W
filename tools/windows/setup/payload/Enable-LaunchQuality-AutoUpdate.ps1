param(
    [string]$ManifestUrl = "https://web-production-08d73.up.railway.app/releases/windows/latest.json",
    [string]$UpdaterScriptPath = "$PSScriptRoot\Update-LaunchQuality.ps1",
    [string]$TaskName = "LaunchQuality-AutoUpdate"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $UpdaterScriptPath)) {
    throw "Updater script not found: $UpdaterScriptPath"
}

$triggerA = New-ScheduledTaskTrigger -AtLogOn
$triggerB = New-ScheduledTaskTrigger -Daily -At 3:00AM
$triggerB.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration ([TimeSpan]::MaxValue)).Repetition

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$UpdaterScriptPath`" -ManifestUrl `"$ManifestUrl`""
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerA,$triggerB) -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Scheduled task '$TaskName' created/updated successfully."
