@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta Instalar.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m local_ocr
pause
