@echo off
REM Registra el agente para que arranque solo al iniciar sesión en Windows:
REM crea un acceso directo a start_agent.bat en la carpeta de Inicio.
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%~dp0start_agent.bat"
set "SHORTCUT=%STARTUP%\JokinToolsPrintAgent.lnk"

powershell -NoProfile -Command ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath='%TARGET%';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.WindowStyle=7;" ^
  "$s.Save()"

if exist "%SHORTCUT%" (
  echo [agente] Instalado en el arranque de Windows:
  echo   %SHORTCUT%
  echo Se iniciara automaticamente la proxima vez que inicies sesion.
  echo Para arrancarlo ahora, ejecuta start_agent.bat.
) else (
  echo [agente] No se pudo crear el acceso directo de arranque.
)
pause
