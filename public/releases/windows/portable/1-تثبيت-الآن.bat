@echo off
chcp 65001 >nul
title NAJJAR Trading — تثبيت سطح المكتب
cd /d "%~dp0"

echo.
echo ============================================
echo   NAJJAR Trading — تثبيت سطح المكتب
echo ============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Desktop-Shortcut.ps1"
if errorlevel 1 goto :fallback
goto :done

:fallback
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  '$here=''%~dp0''; $d=[Environment]::GetFolderPath(''Desktop''); $exe=Join-Path $here ''NAJJAR-Trading.exe''; if(-not(Test-Path $exe)){$exe=Join-Path $here ''LaunchQuality.exe''}; $ico=Join-Path $here ''AppIcon.ico''; $name=''NAJJAR Trading.lnk''; $p=Join-Path $d $name; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath=$exe; $s.WorkingDirectory=$here; if(Test-Path $ico){$s.IconLocation=$ico+'',0''}; $s.Description=''NAJJAR Trading''; $s.Save(); Write-Host ''تم التثبيت''; Start-Process $exe'

:done
echo.
echo تم. افتح من سطح المكتب: NAJJAR Trading
echo.
timeout /t 4 >nul
exit /b 0
