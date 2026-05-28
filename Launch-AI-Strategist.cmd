@echo off
setlocal

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "APP_DIR=%ROOT_DIR%\ai-strategist-desktop"
set "RELEASE_EXE=%APP_DIR%\src-tauri\target\release\AI-Strategist.exe"
set "SHORTCUT_SCRIPT=%ROOT_DIR%\Update-AI-Strategist-Shortcut.ps1"

if not exist "%APP_DIR%\package.json" (
  echo AI Strategist desktop project was not found: %APP_DIR%
  pause
  exit /b 1
)

if exist "%SHORTCUT_SCRIPT%" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SHORTCUT_SCRIPT%" -RepoRoot "%ROOT_DIR%" >nul 2>nul
)

if exist "%RELEASE_EXE%" (
  start "" "%RELEASE_EXE%"
  exit /b 0
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo Built desktop executable was not found:
  echo   %RELEASE_EXE%
  echo.
  echo pnpm was also not found in PATH, so development mode cannot be started.
  pause
  exit /b 1
)

pnpm --dir "%APP_DIR%" tauri dev
