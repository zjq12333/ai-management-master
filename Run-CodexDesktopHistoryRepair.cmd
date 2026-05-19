@echo off
setlocal
cd /d "%~dp0"
title Codex Desktop History Repair

echo.
echo ============================================
echo   Codex Desktop History Repair
echo ============================================
echo.
echo Safe defaults:
echo - restore only visible, real conversations
echo - skip archived conversations
echo - skip deleted or empty workspace folders
echo - skip threads without session files or user messages
echo.
echo Provider sync is optional and uses codex-threadripper only if already installed.
echo.
choice /C YN /M "Run safe repair now"
if errorlevel 2 (
  echo.
  echo Cancelled.
  pause
  exit /b 0
)

echo.
echo Starting repair...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-CodexDesktopHistory.ps1" -SyncProvider
set "EXITCODE=%ERRORLEVEL%"
echo.
if "%EXITCODE%"=="0" (
  echo Repair finished successfully.
) else (
  echo Repair failed with exit code %EXITCODE%.
)
echo.
pause
exit /b %EXITCODE%
