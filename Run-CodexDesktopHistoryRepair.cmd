@echo off
setlocal
cd /d "%~dp0"
title Codex Desktop History Repair

echo.
echo ============================================
echo   Codex Desktop History Repair
echo ============================================
echo.
echo This will repair Codex Desktop history visibility and workspace placement.
echo Codex Desktop may close and restart during the repair.
echo.
choice /C YN /M "Run repair now"
if errorlevel 2 (
  echo.
  echo Cancelled.
  pause
  exit /b 0
)

echo.
echo Starting repair...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-CodexDesktopHistory.ps1"
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
