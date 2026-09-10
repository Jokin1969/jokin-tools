"""La SEGUNDA VÍA: el mismo fichero, PINTADO en una pestaña.

**Qué está medido y qué no (errata nº 130, todavía SIN CAUSA ASIGNADA).** El 2026-09-08
se reportaron tres observaciones a la vez: el botón rojo del export no descarga, el icono
de descarga que Streamlit pinta en la esquina de la tabla tampoco, y el bloque copiable
sí. La lectura que se les dio —«el icono es cliente puro, así que el contenido llega a la
página y no sale del navegador»— es cierta sobre el ORIGEN de los bytes y **no separa los
dos casos muertos**. Leído el `bundle` de Streamlit 1.62.0 que instala el hub:

- ``DownloadButton`` termina en ``createDownloadLinkElement({url, filename}).click()``,
  o sea una pulsación **sintética** sobre un ``<a download>``;
- el icono de la tabla intenta ``showSaveFilePicker`` y, si falla, cae a ``Blob`` +
  ``<a download>``.

Los dos acaban en el mismo sitio. El bloque copiable no —es texto en la página—, y es el
único que funciona. Así que lo que comparten los dos muertos **no es el transporte: es la
maquinaria de descarga del navegador**. Eso es lo medido; por qué esa maquinaria no
responde en esa máquina sigue sin establecerse, y aquí no se afirma.

De ahí esta vía, que es el corolario ya escrito de la errata nº 124 llevado hasta el
final: *una vía y su alternativa no pueden compartir el mecanismo que falla*. El bloque
copiable lo cumplía y entrega un PEGADO; ésta entrega un FICHERO y tampoco lo comparte.

**Cómo**: el contenido se escribe en el directorio ``static/`` del script, que Streamlit
sirve en ``/app/static/`` con ``FileResponse`` **sin ``Content-Disposition``**. El enlace
lo pulsa una persona: no hay ningún ``click()`` de un script por medio.

**EL SUFIJO ES EL MECANISMO ENTERO, y por eso hay DOS MODOS y ninguno tiene defecto**
(principio nº 58). Con ``.txt`` el tipo es ``text/plain`` y el navegador **PINTA** el
contenido en una pestaña; con el nombre REAL, ``.tsv`` sale como
``text/tab-separated-values`` y ``.fa`` como ``application/octet-stream``, y entonces el
navegador **DESCARGA**.

Hasta el 2026-09-10 sólo existía el primero, y su docstring llamaba al segundo «volver a
la maquinaria de descarga». Esa frase mezclaba dos cosas que **están medidas y no son la
misma**: las dos vías muertas de la errata nº 130 terminan en una **pulsación SINTÉTICA**
sobre un ``<a download>`` —``DownloadButton`` sobre una URL de ``/media/`` cuyo id se
recicla en el rerun, y el icono de la tabla sobre un ``Blob``—; ésta es una **navegación
de verdad**, iniciada por una persona, a un fichero estático que ya existe en disco. Lo
que comparten es el gestor de descargas del navegador; lo que no comparten es todo lo
demás. Por eso el modo de descarga es una vía NUEVA y no la que ya falla, y por eso se
mide en un navegador de verdad (`test/shmir.smoke.test.js`) en vez de razonarse.

Los dos modos conviven a propósito: el botón de descarga usa el segundo, y el primero se
queda como la salida que **está medida** desde el 2026-09-08.

**Y el segundo ya está MEDIDO también** (2026-09-10). En Chromium, por el proxy del hub y
con el flujo real —elegir especie, subir el mRNA y su `.gb`, buscar candidatos y pulsar el
botón morado de la primera tabla—: el enlace sale a ``/shmir/app/static/anatomy_rows.tsv``
—sin ``.txt``— y **el navegador descarga el fichero**: 117 bytes, 4 líneas, la primera es
la cabecera de columnas. O sea que la vía de descarga que este módulo abre **sí baja
bytes**, mientras las dos de la errata nº 130 siguen sin bajar ninguno. Eso no le asigna
causa a aquella errata: la esquiva, que es lo que este módulo dice desde su primera línea.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .errors import ShmirDesignError

__all__ = [
    "INLINE_SUFFIX",
    "MAX_STATIC_BYTES",
    "STATIC_ENDPOINT",
    "WHY_A_SECOND_ROUTE",
    "mount_prefix",
    "publish",
    "static_dir",
]

#: El sufijo que decide qué hace el navegador. No es cosmético: ver el docstring.
INLINE_SUFFIX = ".txt"

#: Dónde sirve Streamlit el directorio `static/` del script. Va detrás del prefijo del
#: montaje, que en el hub es `/shmir` y en local es vacío.
STATIC_ENDPOINT = "/app/static/"

#: El tope de `MAX_APP_STATIC_FILE_SIZE` de Streamlit, leído de su fuente
#: (`web/server/starlette/starlette_server_config.py`). Por encima devuelve **404**, o
#: sea una pestaña vacía: se aborta aquí para que «no cabe» no se lea como «la segunda
#: vía tampoco funciona».
MAX_STATIC_BYTES = 200 * 1024 * 1024

WHY_A_SECOND_ROUTE = (
    "Los dos botones que no bajan nada terminan en una pulsación sintética sobre un "
    "enlace de descarga, medido en el código de Streamlit; el bloque copiable no, y es "
    "el que funciona. La causa de la errata nº 130 sigue sin causa asignada, así que "
    "esta vía no la arregla: la esquiva. El fichero se sirve como texto, el navegador "
    "lo pinta en una pestaña y se guarda desde ahí."
)


def mount_prefix(declared: str) -> str:
    """Normaliza el prefijo del montaje que declara Streamlit.

    `server.baseUrlPath` se guarda **tal cual se pasa** —no lo normaliza nadie—, así que
    `shmir`, `/shmir` y `/shmir/` son el mismo montaje escrito de tres formas y sólo una
    concatena bien. Vive aquí y no en la página porque es una decisión con test
    (regla 6): resuelta en la vista, el día que alguien arranque con `shmir` el enlace
    saldría a `shmir/app/static/…`, o sea relativo, y apuntaría a otro sitio según la
    URL desde la que se mire — sin dar ningún error.
    """
    limpio = str(declared).strip().strip("/")
    return f"/{limpio}" if limpio else ""


def static_dir(main_script) -> Path:
    """El directorio que Streamlit sirve en `/app/static/`, DERIVADO del script.

    La ruta la decide `file_util.get_app_static_dir`, que es
    `Path(main_script).parent / "static"` y **no es configurable**. Se deriva en vez de
    escribirse para que mover la página no deje esta vía apuntando a un directorio que
    ya no sirve nadie — y sin dar ningún error (principio nº 13).
    """
    return Path(main_script).resolve().parent / "static"


def publish(
    nombre: str,
    contenido: str,
    *,
    directory,
    base_path: str,
    inline: bool,
    max_bytes: int = MAX_STATIC_BYTES,
) -> dict:
    """Publica `contenido` en la ruta estática. Devuelve URL y nombre real.

    `inline` decide QUÉ HACE EL NAVEGADOR con el enlace, y **no tiene valor por
    defecto** porque es el mecanismo entero: `True` añade `.txt` y el contenido se
    **PINTA** en una pestaña; `False` conserva el nombre real y el navegador lo
    **DESCARGA**. Un defecto aquí elegiría en silencio cuál de las dos cosas pasa.

    `base_path` es el prefijo del montaje y **tampoco** tiene valor por defecto: con
    `/shmir` supuesto, la app en local daría un enlace roto; con vacío supuesto, la del
    hub daría un 404 del hub. Los dos, en silencio.

    Del nombre sobrevive el NOMBRE y se cae toda la ruta, la misma regla que
    `presentation.upload_path`: no se limpia `..`, se descarta entera.
    """
    if base_path and not base_path.startswith("/"):
        raise ShmirDesignError(
            f"El prefijo del montaje {base_path!r} tiene que empezar por «/» "
            f"(en el hub es «/shmir»; en local, vacío)."
        )
    # EL TIPO SE COMPRUEBA, no se convierte (errata nº 50). Con `str(nombre)`, un
    # objeto cualquiera daría un nombre construido de su `repr` —con la forma correcta y
    # sin ningún error—, que es exactamente cómo `species.resolve` acabó fabricando una
    # especie a partir de cualquier cosa.
    if not isinstance(nombre, str):
        raise ShmirDesignError(
            f"El nombre del fichero tiene que ser una cadena, y llegó {type(nombre).__name__}."
        )
    crudo = nombre
    if "\x00" in crudo or "\\" in crudo:
        raise ShmirDesignError(f"Nombre de fichero {nombre!r} no válido.")
    limpio = PurePosixPath(crudo).name.strip()
    if not limpio or limpio in (".", ".."):
        raise ShmirDesignError(f"Nombre de fichero {nombre!r} no válido.")

    datos = contenido.encode("utf-8")
    if len(datos) > max_bytes:
        raise ShmirDesignError(
            f"«{limpio}» ocupa {len(datos):,} bytes y la ruta estática de Streamlit "
            f"corta en {max_bytes:,}: por encima devuelve un 404, o sea una pestaña "
            f"vacía. Queda el bloque copiable."
        )

    base = Path(directory)
    fichero = f"{limpio}{INLINE_SUFFIX}" if inline else limpio
    ruta = base / fichero
    if not ruta.resolve().is_relative_to(base.resolve()):
        raise ShmirDesignError(
            f"El fichero {nombre!r} acabaría en {ruta.resolve()}, fuera de {base}."
        )
    try:
        base.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
    except OSError as exc:
        # rule2-ok: se añade contexto y se relanza como error del proyecto. Sin la ruta
        # dentro, «no se pudo escribir» no dice dónde hay que mirar.
        raise ShmirDesignError(
            f"No se pudo publicar «{limpio}» en {base}: {exc}. Queda el bloque copiable."
        ) from exc

    return {
        "url": f"{base_path.rstrip('/')}{STATIC_ENDPOINT}{fichero}",
        "fichero": fichero,
        "guardar_como": limpio,
        "ruta": ruta,
        "bytes": len(datos),
        #: Qué va a hacer el navegador con este enlace. Viaja con la URL para que quien
        #: la pinte no tenga que volver a decidirlo — y para que el rótulo no pueda
        #: prometer una cosa y el enlace hacer otra.
        "modo": "pinta" if inline else "descarga",
    }
