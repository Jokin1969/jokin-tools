@echo off
REM Arranca el agente de impresión sin ventana (pythonw). Si ya está corriendo,
REM no lanza otro. Ejecuta este .bat con doble clic o desde install_startup.bat.
setlocal
cd /d "%~dp0"

REM ¿Ya hay un agente corriendo?
tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV 2>NUL | find /I "pythonw.exe" >NUL
if not errorlevel 1 (
  echo [agente] Ya parece haber un pythonw en marcha. Si no es este agente, ciérralo antes.
)

where pythonw >NUL 2>&1
if errorlevel 1 (
  echo [agente] No se encuentra pythonw. Instala Python 3 y marca "Add to PATH".
  pause
  exit /b 1
)

start "" pythonw "%~dp0agent.py"
echo [agente] Lanzado en segundo plano.
