"""¿Está el fichero? La pregunta que importa es si TIENE CONTENIDO.

Existe por la errata nº 15 generalizada. Alli `provided` era `True` porque la ENTRADA
estaba en el registro, no porque hubiera secuencia. El mismo patron —un estado derivado
de que algo EXISTA en vez de que TENGA ALGO DENTRO— vive en todas partes donde este
proyecto decide con `Path.is_file()`:

  - el panel de ficheros de referencia pinta PRESENTE y ofrece sus cuatro acciones;
  - `fixture_available` decide si un test se SALTA de forma visible o corre de verdad;
  - el paso 3 cuenta cuantos frentes se van a poder cerrar.

Un fichero de 0 bytes existe, pasa `is_file()`, y no contiene nada. La descarga que se
corto a medias, el `touch` que alguien hizo para probar, el volumen que se quedo sin
espacio a mitad de escritura: los tres dejan exactamente eso. Y los tres se leian como
«lo tenemos».

Un fichero de solo espacios en blanco es el mismo caso y va aqui tambien: separarlos
dejaria medio agujero abierto, que es peor que ninguno porque parece cerrado.

Lo que esto NO hace: no valida el formato ni el md5 — eso lo hace el cargador de cada
filtro, que es quien sabe. Aqui solo se contesta «¿hay algo?».

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["hay_fichero", "ficheros_con_contenido"]

#: Cuanto se lee para decidir si hay algo. No hace falta el fichero entero: `mature.fa`
#: son 5,6 MB y esto se llama en cada rerun de Streamlit.
_MUESTRA = 4096


def hay_fichero(ruta) -> bool:
    """¿Existe Y tiene contenido? Un fichero de 0 bytes o en blanco NO cuenta."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return False
    if ruta.stat().st_size == 0:
        return False
    with ruta.open("rb") as f:
        return bool(f.read(_MUESTRA).strip())


def ficheros_con_contenido(directorio) -> set[str]:
    """Los nombres del directorio que superan `hay_fichero`. Sin directorio, vacio."""
    directorio = Path(directorio)
    if not directorio.is_dir():
        return set()
    return {p.name for p in directorio.iterdir() if hay_fichero(p)}
