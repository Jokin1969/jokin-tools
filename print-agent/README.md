# Agente de impresión local — Jokin's Tools · Imprimir

Imprime en tu impresora física los PDF que llegan por email a
`imprimir@joaquincastilla.com`. Este agente corre en el **PC que tiene acceso a
la impresora** (`\\cicpri042\Color`) y va **tirando** de la cola del servidor.

```
Remitente ──email+PDF──▶  Buzón imprimir@…  ──IMAP──▶  Servidor (jokin-tools)
                                                          │  encola el PDF
                                                          ▼
                        Impresora  ◀── SumatraPDF ──  Agente local (este)
                                                          │  pull cada 5 s (HTTPS saliente)
                                                          ▼
                                                    marca "hecho" → email de confirmación
```

## Requisitos
- **Python 3** (marca *Add Python to PATH* al instalar).
- **SumatraPDF** (https://www.sumatrapdfreader.org/). Ruta por defecto:
  `C:\Program Files\SumatraPDF\SumatraPDF.exe`.

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
