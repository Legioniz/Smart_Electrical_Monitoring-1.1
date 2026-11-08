@echo off
setlocal
cd /d "%~dp0"
where powershell.exe >nul 2>nul || (echo Windows PowerShell was not found.& pause & exit /b 1)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo Smart Meter Explorer setup did not finish. Review .local\logs\windows-setup.log
  pause
  exit /b 1
)
pause
