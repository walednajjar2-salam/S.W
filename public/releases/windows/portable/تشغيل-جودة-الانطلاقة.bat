@echo off
chcp 65001 >nul
title NAJJAR Trading
cd /d "%~dp0"
start "" "%~dp0LaunchQuality.exe"
