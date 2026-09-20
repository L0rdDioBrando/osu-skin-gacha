@echo off
chcp 65001 >nul
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "%~dp0osu!gacha.exe" (
  start "" "%~dp0osu!gacha.exe"
  exit /b
)
set "PYTHONHOME="
set "PYTHONPATH="
set "TCL_LIBRARY="
set "TK_LIBRARY="
set "APP_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python"
if exist ".runtime\customtkinter\__init__.py" if exist "%APP_PYTHON%\python.exe" (
  set "PYTHONPATH=%~dp0.runtime"
  set "TCL_LIBRARY=%APP_PYTHON%\tcl\tcl8.6"
  set "TK_LIBRARY=%APP_PYTHON%\tcl\tk8.6"
  "%APP_PYTHON%\python.exe" "%~dp0main.py"
  if errorlevel 1 pause
  exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure_python.ps1" --run
if errorlevel 1 pause
