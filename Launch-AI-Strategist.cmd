@echo off
setlocal

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "APP_DIR=%ROOT_DIR%\ai-strategist-desktop"
set "PRIMARY_EXE=%APP_DIR%\src-tauri\target\release\AI-Strategist.exe"
set "FALLBACK_MANAGER_EXE=%ROOT_DIR%\third_party\codex-plus-plus\target\release\codex-plus-plus-manager.exe"
set "START_SCRIPT=%ROOT_DIR%\Start-AI-Strategist.ps1"
set "SHORTCUT_SCRIPT=%ROOT_DIR%\Update-AI-Strategist-Shortcut.ps1"

if not exist "%APP_DIR%\package.json" (
  echo AI Strategist desktop project was not found: %APP_DIR%
  pause
  exit /b 1
)

if exist "%SHORTCUT_SCRIPT%" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SHORTCUT_SCRIPT%" -RepoRoot "%ROOT_DIR%" >nul 2>nul
)

if exist "%START_SCRIPT%" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%START_SCRIPT%" -RepoRoot "%ROOT_DIR%"
  exit /b %ERRORLEVEL%
)

if exist "%PRIMARY_EXE%" (
  start "" "%PRIMARY_EXE%"
  exit /b 0
)

where npm >nul 2>nul
if errorlevel 1 (
  echo Built AI Strategist executable was not found:
  echo   %PRIMARY_EXE%
  echo.
  echo npm was also not found in PATH, so development mode cannot be started.
  echo.
  if exist "%FALLBACK_MANAGER_EXE%" (
    echo Starting fallback Codex++ manager shell instead:
    echo   %FALLBACK_MANAGER_EXE%
    start "" "%FALLBACK_MANAGER_EXE%"
    exit /b 0
  )
  pause
  exit /b 1
)

npm --prefix "%APP_DIR%" run dev
