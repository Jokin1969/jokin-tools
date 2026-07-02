#!/usr/bin/env python3
"""
Agente local de impresión (modelo pull) para Jokin's Tools · Imprimir.

Se ejecuta en el PC que tiene acceso a la impresora. Cada pocos segundos pregunta
al servidor si hay algún trabajo en cola; si lo hay, descarga el PDF y lo imprime
en silencio con SumatraPDF, y le dice al servidor si salió bien o mal (que a su
vez avisa por email al remitente).

Solo hace peticiones SALIENTES por HTTPS: no necesita abrir puertos ni que el
servidor alcance tu red. Solo requiere Python 3 y SumatraPDF (sin pip install).

Configuración: edita config.json (ver config.example.json).
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

# On Windows, a windowless process (pythonw) spawning a console child (PowerShell,
# SumatraPDF) flashes a console window. CREATE_NO_WINDOW keeps them hidden. The
# flag is 0 on other platforms, so this is a no-op there.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd, **kwargs):
    """subprocess.run without flashing a console window on Windows."""
    return subprocess.run(cmd, creationflags=_NO_WINDOW, **kwargs)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"[agente] No existe {CONFIG_PATH}. Copia config.example.json a config.json y edítalo.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for key in ("server_url", "api_key"):
        if not cfg.get(key):
            sys.exit(f"[agente] Falta '{key}' en config.json.")
    cfg.setdefault("printer", "")
    cfg.setdefault("sumatra_path", r"C:\Program Files\SumatraPDF\SumatraPDF.exe")
    cfg.setdefault("poll_seconds", 5)
    cfg["server_url"] = cfg["server_url"].rstrip("/")
    return cfg


def api(cfg, method, path, body=None):
    url = cfg["server_url"] + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Api-Key", cfg["api_key"])
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _get(cfg, path, with_key=True, timeout=30):
    req = urllib.request.Request(cfg["server_url"] + path, method="GET")
    if with_key:
        req.add_header("X-Api-Key", cfg["api_key"])
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", None) or resp.getcode()
        return status, resp.read().decode("utf-8")


def list_printers():
    """Nombres de impresoras instaladas (PowerShell Get-Printer)."""
    try:
        out = _run(
            ["powershell", "-NoProfile", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=25,
        )
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def report_printers(cfg):
    """Envía al servidor la lista de impresoras (para el selector del panel/apps)."""
    printers = list_printers()
    if printers:
        try:
            api(cfg, "POST", "/imprimir/api/agent/printers", {"printers": printers})
        except Exception:
            pass
    return printers


def do_check():
    """Valida de una vez toda la instalación e imprime un informe ✓/✗."""
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        if not good:
            ok = False
        print(f"  [{'OK' if good else 'XX'}] {label}" + (f" — {detail}" if detail else ""))

    print("== Comprobación del agente de impresión (jokin-tools) ==")
    if not os.path.exists(CONFIG_PATH):
        print(f"  [XX] No existe {CONFIG_PATH}. Copia config.example.json a config.json y edítalo.")
        return 1
    cfg = load_config()  # sale si faltan server_url / api_key
    print(f"  Servidor  : {cfg['server_url']}")
    print(f"  Impresora : {cfg.get('printer') or '(la del trabajo)'}")
    print(f"  SumatraPDF: {cfg['sumatra_path']}")
    print("-" * 60)

    # SumatraPDF
    have_sumatra = os.path.exists(cfg["sumatra_path"])
    line(have_sumatra, "SumatraPDF encontrado", "" if have_sumatra else "corrige 'sumatra_path' en config.json")

    # Impresora
    printer = cfg.get("printer") or ""
    if printer:
        names = list_printers()
        if names:
            found = any(printer.lower() == n.lower() or printer.split("\\")[-1].lower() == n.lower() for n in names)
            line(found, "Impresora visible", printer if found else f"'{printer}' no está entre: {', '.join(names)}")
        else:
            print(f"  [??] No pude listar impresoras; comprueba a mano que exista {printer}")

    # Servidor accesible + servicio activo
    try:
        st, body = _get(cfg, "/imprimir/api/health", with_key=False)
        line(st == 200, "Servidor accesible", f"health={body.strip()}")
        enabled = '"enabled":true' in body.replace(" ", "")
        line(enabled, "Servicio activado en el servidor", "" if enabled else "pon IMPRIMIR_ENABLED=true en el servidor y redespliega")
    except Exception as e:
        line(False, "Servidor accesible", f"{e} · ¿URL correcta y hay Internet?")

    # API key válida
    try:
        st, _ = _get(cfg, "/imprimir/api/jobs")
        line(st == 200, "API key válida", "" if st == 200 else f"HTTP {st}")
    except urllib.error.HTTPError as e:
        hint = "la api_key NO coincide con IMPRIMIR_AGENT_KEY del servidor" if e.code in (401, 403) else f"HTTP {e.code}"
        line(False, "API key válida", hint)
    except Exception as e:
        line(False, "API key válida", str(e))

    print("-" * 60)
    print("  RESULTADO:", "TODO OK — el agente puede funcionar." if ok else "HAY PROBLEMAS — revisa las líneas [XX].")
    return 0 if ok else 1


def print_pdf(cfg, pdf_bytes, printer):
    """Imprime en silencio con SumatraPDF. Lanza excepción si falla."""
    sumatra = cfg["sumatra_path"]
    if not os.path.exists(sumatra):
        raise RuntimeError(f"No se encuentra SumatraPDF en {sumatra}")
    target = printer or cfg.get("printer") or ""
    if not target:
        raise RuntimeError("No hay impresora configurada (ni en el trabajo ni en config.json)")

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pdf_bytes)
        # -print-to <impresora> -silent -exit-when-done: sin diálogos.
        result = _run(
            [sumatra, "-print-to", target, "-silent", "-exit-when-done", tmp],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"SumatraPDF devolvió código {result.returncode}: {result.stderr.strip()}")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def process_one(cfg):
    """Procesa un trabajo si lo hay. Devuelve True si imprimió algo."""
    resp = api(cfg, "GET", "/imprimir/api/jobs/next")
    job = resp.get("job")
    if not job:
        return False

    job_id = job["id"]
    name = job.get("filename", f"job-{job_id}")
    printer = job.get("printer") or cfg.get("printer") or ""
    print(f"[agente] Trabajo #{job_id}: {name} → {printer or '(config)'}")

    try:
        pdf_bytes = base64.b64decode(job["pdf_base64"])
        print_pdf(cfg, pdf_bytes, printer)
    except Exception as e:  # noqa: BLE001 — queremos reportar cualquier fallo
        print(f"[agente] ✗ Error imprimiendo #{job_id}: {e}")
        try:
            api(cfg, "POST", f"/imprimir/api/jobs/{job_id}/failed", {"error": str(e)})
        except Exception as e2:  # noqa: BLE001
            print(f"[agente] (no se pudo avisar del fallo: {e2})")
        return True

    try:
        api(cfg, "POST", f"/imprimir/api/jobs/{job_id}/done")
        print(f"[agente] ✓ Impreso #{job_id}")
    except Exception as e:  # noqa: BLE001
        print(f"[agente] (impreso, pero no se pudo confirmar: {e})")
    return True


def main():
    cfg = load_config()
    poll = max(2, int(cfg.get("poll_seconds", 5)))
    print(f"[agente] Iniciado. Servidor: {cfg['server_url']} · impresora: {cfg.get('printer') or '(la del trabajo)'} · cada {poll}s")
    report_printers(cfg)                 # publica las impresoras al arrancar
    report_every = max(1, 300 // poll)   # y luego ~cada 5 min (oculto, sin ventana)
    backoff = poll
    i = 0
    while True:
        try:
            # Vacía la cola de golpe si hay varios trabajos.
            while process_one(cfg):
                pass
            i += 1
            if i % report_every == 0:
                report_printers(cfg)
            backoff = poll
        except urllib.error.HTTPError as e:
            print(f"[agente] HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"[agente] Sin conexión con el servidor: {e.reason}. Reintento en {backoff}s.")
            backoff = min(backoff * 2, 120)
        except Exception as e:  # noqa: BLE001
            print(f"[agente] Error inesperado: {e}")
        time.sleep(backoff)


if __name__ == "__main__":
    if "--check" in sys.argv or "-c" in sys.argv:
        sys.exit(do_check())
    try:
        main()
    except KeyboardInterrupt:
        print("\n[agente] Detenido.")
