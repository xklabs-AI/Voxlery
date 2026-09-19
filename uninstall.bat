@echo off
setlocal
title Voxlery Automated Uninstaller

cd /d "%~dp0"

where powershell >nul 2>nul
if %ERRORLEVEL% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
) else (
    echo [!] PowerShell was not found on your system.
    echo Please run uninstall.ps1 directly or remove .venv and %%USERPROFILE%%\.voxlery manually.
)

if "%1" neq "--no-pause" (
    echo Press any key to exit...
    pause >nul
)
