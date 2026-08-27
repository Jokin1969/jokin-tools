"""Descarga de referencias (paso 0 del pipeline).

Camino OPCIONAL: los datos de referencia entran como fixtures versionados
(`docs/fixtures.md`), asi que nada del analisis depende de esto. Solo sirve para
regenerar un fixture desde una maquina con salida a internet.

Regla 4: **este modulo no contiene ninguna URL**. La base del endpoint la pasa quien
la haya verificado; `tools/reference_data.py --fetch` la exige por linea de comandos. Cuando el
endpoint este verificado desde este proyecto y anotado en `docs/endpoints-verificados.md`,
se podra fijar aqui un valor por defecto — hasta entonces, no.

Dos trampas conocidas del endpoint de NCBI, ambas cubiertas aqui:

- responde 200 con un XML de error, asi que el codigo HTTP no basta: la respuesta
  tiene que empezar por '>' antes de parsearla;
- limita a 3 peticiones/segundo sin clave de API (10 con clave), y el limite es por
  IP: si algo paraleliza la descarga, necesita un limitador compartido.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

from .errors import FetchError

#: Peticiones por segundo permitidas por NCBI segun haya o no clave de API.
RATE_LIMIT_PER_SECOND = 3
RATE_LIMIT_PER_SECOND_WITH_KEY = 10

EFETCH_PARAMS = {"db": "nuccore", "rettype": "fasta", "retmode": "text"}
PREVIEW_CHARS = 300


def build_efetch_url(
    base_url: str,
    accession: str,
    *,
    api_key: str | None = None,
    tool: str | None = None,
    email: str | None = None,
) -> str:
    """Compone la peticion de efetch sobre una base que da quien la ha verificado."""
    if not base_url or not base_url.strip():
        raise ValueError(
            "Falta la URL base del endpoint: este proyecto no escribe URLs que no haya "
            "verificado (regla 4). Pasa la base verificada por --efetch-url."
        )
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(
            f"URL base {base_url!r} invalida: se exige https y un host; "
            f"se aborta la descarga."
        )
    if not accession or not accession.strip():
        raise ValueError("Falta el accession que descargar; se aborta la descarga.")

    params = {**EFETCH_PARAMS, "id": accession.strip()}
    for name, value in (("api_key", api_key), ("tool", tool), ("email", email)):
        if value:
            params[name] = value
    return f"{base_url.strip()}?{urllib.parse.urlencode(params)}"


def download_text(url: str, *, timeout: float = 60.0) -> str:
    """Descarga texto. Cualquier fallo aborta el paso 0 con su causa."""
    request = urllib.request.Request(url, headers={"User-Agent": "shmir-design/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise FetchError(
            f"{url} respondio HTTP {exc.code} ({exc.reason}); se aborta el paso 0 "
            f"(descarga + verificación de checksum) y con el todo el pipeline."
        ) from exc
    except urllib.error.URLError as exc:
        raise FetchError(
            f"No se pudo conectar con {url} ({exc.reason}); se aborta el paso 0 "
            f"(descarga + verificación de checksum) y con el todo el pipeline."
        ) from exc
    except TimeoutError as exc:
        raise FetchError(
            f"{url} no respondio en {timeout} s; se aborta el paso 0 "
            f"(descarga + verificación de checksum)."
        ) from exc

    try:
        return raw.decode(charset)
    except (UnicodeDecodeError, LookupError) as exc:
        raise FetchError(
            f"La respuesta de {url} no se pudo decodificar como {charset} ({exc}); "
            f"se aborta el paso 0."
        ) from exc


def parse_fasta_payload(payload: str, *, source: str) -> tuple[str, str]:
    """Valida que la respuesta es un FASTA de un unico registro y lo separa.

    Devuelve (cabecera sin '>', secuencia sin saltos). No normaliza ni valida las
    bases: de eso se encargan `reference.verify_transcript` y `polya`.
    """
    text = payload.strip()
    if not text:
        raise FetchError(
            f"{source} devolvio una respuesta vacía; se aborta el paso 0. "
            f"Sin secuencia no hay análisis y no se inventa ninguna."
        )
    if not text.startswith(">"):
        preview = text[:PREVIEW_CHARS].replace("\n", " ")
        raise FetchError(
            f"La respuesta de {source} no empieza por '>': no es FASTA. "
            f"Un código HTTP 200 no basta, NCBI devuelve sus errores así. "
            f"Primeros {PREVIEW_CHARS} caracteres: {preview}"
        )

    headers: list[str] = []
    lines: list[list[str]] = []
    for line in text.splitlines():
        if line.startswith(">"):
            headers.append(line[1:].strip())
            lines.append([])
        elif line.strip():
            lines[-1].append(line.strip())

    if len(headers) != 1:
        raise FetchError(
            f"{source} devolvio {len(headers)} registros FASTA y se esperaba "
            f"exactamente 1; se aborta el paso 0 para no analizar la secuencia "
            f"equivocada."
        )
    sequence = "".join(lines[0])
    if not sequence:
        raise FetchError(
            f"{source} devolvio una cabecera sin secuencia ({headers[0]!r}); "
            f"se aborta el paso 0."
        )
    return headers[0], sequence


def min_interval_seconds(*, has_api_key: bool) -> float:
    """Intervalo minimo entre peticiones para respetar el limite de NCBI."""
    limit = RATE_LIMIT_PER_SECOND_WITH_KEY if has_api_key else RATE_LIMIT_PER_SECOND
    return 1.0 / limit
