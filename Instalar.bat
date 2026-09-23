@echo off
setlocal
cd /d "%~dp0"
echo Preparando Local OCR. Esta primera instalacion necesita internet.
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Instala Python 3.12 de 64 bits desde https://www.python.org/downloads/windows/
  echo Activa el Python Launcher durante la instalacion y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Instalacion de Python completada. Abre Iniciar.bat.
echo Para OCR instala Tesseract; para Word instala LibreOffice. Consulta README.md.
pause
exit /b 0
:error
echo No se completo la instalacion. Conserva este mensaje para revisar el error.
pause
exit /b 1
