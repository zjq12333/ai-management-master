@echo off
setlocal
cd /d "%~dp0"
title Codex Desktop History Repair - Dry Run

echo.
echo ============================================
echo   Codex Desktop History Repair - Dry Run
echo ============================================
echo.
echo This only previews the safe repair set. It will not close Codex or write files.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-CodexDesktopHistory.ps1" -DryRun
set "EXITCODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXITCODE%
