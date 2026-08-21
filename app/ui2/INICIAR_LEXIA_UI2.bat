@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro .venv\Scripts\python.exe
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "app\ui2\launch_ui2.py"
pause
