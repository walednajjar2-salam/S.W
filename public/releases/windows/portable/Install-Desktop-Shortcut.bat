@echo off
chcp 65001 >nul
title تثبيت أيقونة سطح المكتب
cd /d "%~dp0"
if exist "%~dp01-تثبيت-الآن.bat" (
  call "%~dp01-تثبيت-الآن.bat"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Desktop-Shortcut.ps1"
)
