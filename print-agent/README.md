# Agente de impresión local — Jokin's Tools · Imprimir

Imprime en tu impresora física los documentos que llegan por email a
`imprimir@joaquincastilla.com`. Este agente corre en el **PC que tiene acceso a
la impresora** (`\\cicpri042\Color`) y va **tirando** de la cola del servidor.

Formatos aceptados en el email: **PDF, imágenes (JPG/PNG) y Office
(DOCX/XLSX/PPTX)**. El servidor los convierte a PDF antes de encolarlos, así que
el agente siempre imprime PDF. El remitente recibe un **acuse de recibo** ("en
cola") y luego la **confirmación de impresión** (o el aviso de error).

Los administradores pueden ver la cola y **reimprimir** en la página de estado:
`https://TU-SERVIDOR/imprimir/status`.

```
Remitente ──email+PDF──▶  Buzón imprimir@…  ──IMAP──▶  Servidor (jokin-tools)
                                                          │  encola el PDF
                                                          ▼
                        Impresora  ◀── SumatraPDF ──  Agente local (este)
                                                          │  pull cada 5 s (HTTPS saliente)
                                                          ▼
                                                    marca "hecho" → email de confirmación
```

> ⚠️ Este agente NO es el mismo que el de otros proyectos (p. ej. el de Research
> Tools, que escucha en `http://localhost:9100`). Éste **pregunta** a tu servidor
> de jokin‑tools por trabajos (`server_url` + `api_key`). Pueden convivir: instala
> éste en **su propia carpeta** y déjalos correr a la vez.

## Requisitos
- **Python 3** (marca *Add Python to PATH* al instalar).
- **SumatraPDF** (https://www.sumatrapdfreader.org/). Ruta habitual:
  `C:\Program Files\SumatraPDF\SumatraPDF.exe` — pero si lo instalaste solo para
  tu usuario está en `C:\Users\<usuario>\AppData\Local\SumatraPDF\SumatraPDF.exe`.
  Pon la ruta correcta en `sumatra_path` (compruébalo con `where SumatraPDF` o
  mirando ese AppData).

## Comprobar la instalación de un vistazo
```
python agent.py --check
```
Valida config, conexión al servidor, validez de la API key y SumatraPDF, e imprime
un informe `[OK]`/`[XX]`. Úsalo siempre que algo no funcione.

## Instalación (Windows)
1. Copia esta carpeta `print-agent/` al PC de la impresora.
2. Copia `config.example.json` a `config.json` y rellénalo:
   - `server_url`: la URL pública del servidor (Railway).
   - `api_key`: **el mismo valor** que la variable `IMPRIMIR_AGENT_KEY` del servidor.
   - `printer`: `\\cicpri042\Color` (en JSON las barras van dobladas: `\\\\cicpri042\\Color`).
   - `sumatra_path`: ruta a `SumatraPDF.exe` si no es la de por defecto.
3. Doble clic en `start_agent.bat` para arrancarlo (sin ventana, en segundo plano).
4. (Opcional) Doble clic en `install_startup.bat` para que **arranque solo** al
   iniciar sesión en Windows.

Para comprobar el nombre exacto de la impresora:
`Configuración → Bluetooth y dispositivos → Impresoras`, o en PowerShell:
`Get-Printer | Format-List Name`. La impresora debe estar instalada/conectada en
ese PC (o accesible por su ruta de red `\\servidor\cola`).

## Probar sin email
Con el servidor y el agente en marcha, puedes encolar un PDF a mano (necesitas la
API key). Sustituye `SERVER` y `KEY`:

```powershell
# 1) Ver estado del servicio
curl.exe SERVER/imprimir/api/health

# 2) Ver la cola
curl.exe -H "X-Api-Key: KEY" SERVER/imprimir/api/jobs
```

Para una prueba real de punta a punta: envía un email **desde un remitente
autorizado** a `imprimir@joaquincastilla.com` con un PDF adjunto. En ~1 minuto el
servidor lo encola, el agente lo imprime y recibes un email de confirmación.

## Seguridad
- El agente **solo hace peticiones salientes** (no abre puertos).
- Se autentica con `api_key`; guárdala como un secreto.
- El servidor solo encola correos de **remitentes autorizados**
  (`IMPRIMIR_ALLOWLIST`).

## Resolución de problemas
- *No imprime nada*: revisa que `start_agent.bat` esté corriendo (busca
  `pythonw.exe` en el Administrador de tareas) y que `curl SERVER/imprimir/api/health`
  responda `ok:true`.
- *"No se encuentra SumatraPDF"*: corrige `sumatra_path` en `config.json`.
- *"API key inválida"*: `api_key` del agente y `IMPRIMIR_AGENT_KEY` del servidor
  deben coincidir exactamente.
- *Imprime en la impresora equivocada*: ajusta `printer` en `config.json` (tiene
  prioridad la del trabajo, y si no, esta).
