@echo off
chcp 65001 >nul
title تثبيت أيقونة سطح المكتب
cd /d "%~dp0"
call "%~dp0Install-Desktop-Shortcut.bat"
