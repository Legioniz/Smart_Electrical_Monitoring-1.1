@echo off
setlocal
cd /d "%~dp0"
echo This downloads/verifies Node.js LTS, checks the existing MySQL 8.4 service,
echo installs the required Visual C++ runtime if missing, and builds React.
echo Optional Ollama: pass -InstallOllama to the PowerShell script.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1" -SetupOnly %*
if errorlevel 1 pause
