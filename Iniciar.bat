@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Primero ejecuta Instalar.bat.
  pause
  exit /b 1
)
start "Local OCR" ".venv\Scripts\pythonw.exe" -m local_ocr
