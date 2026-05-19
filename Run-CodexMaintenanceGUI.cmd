@echo off
setlocal
cd /d "%~dp0"

set "PYTHONW_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if exist "%PYTHONW_EXE%" (
  start "" "%PYTHONW_EXE%" -X utf8 "%~dp0CodexMaintenanceGUI.py"
  exit /b 0
)

set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
start "" "%PYTHON_EXE%" -X utf8 "%~dp0CodexMaintenanceGUI.py"
exit /b 0
