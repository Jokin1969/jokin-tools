"""La release de miRBase, y por qué los precursores y los maduros no se mezclan.

`mature.fa` (maduros) y `hairpin.fa` (precursores) son dos ficheros del mismo sitio y
**ninguno lleva la versión dentro**: se declara, y hoy se declara en el manifiesto de
`data/reference/`. Entre releases miRBase añade, retira y **RENOMBRA** entradas, así que
un maduro buscado dentro de un precursor de otra versión puede no aparecer, o aparecer
donde no toca — y el fallo no sería ruidoso: sería una geometría plausible.

Por eso esto **aborta** en vez de avisar, y aborta también cuando una de las dos no está
declarada: «no se pudo comparar» no es «coinciden».

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import ShmirDesignError

#: La release del proyecto. `mature.fa` esta en el manifiesto con esta version, y
#: `hairpin.fa` tiene que llegar con la MISMA. Se declara aqui porque es una decision
#: —que version usa este proyecto— y en un fichero se podria cambiar sin que se viera.
RELEASE_DECLARADA = "23"

#: Como se reconoce la release en el texto de procedencia del manifiesto.
_RELEASE = re.compile(r"\brelease\s*v?(\d+(?:\.\d+)?)\b", re.IGNORECASE)


def _normalizar(valor: str) -> str:
    """«v23», « 23 » y «23» son la misma release. Que no aborte por el prefijo."""
    return str(valor).strip().lstrip("vV").strip()


def comprobar_release(*, mature: str, hairpin: str) -> str:
    """Las dos releases o aborta. Devuelve la común, normalizada."""
    m, h = _normalizar(mature), _normalizar(hairpin)
    if not m or not h:
        cual = "mature.fa" if not m else "hairpin.fa"
        raise ShmirDesignError(
            f"No está declarada la release de miRBase de {cual}, y sin ella no se puede "
            f"comprobar que los maduros y los precursores son de la misma versión. Se "
            f"aborta: «no se pudo comparar» no es «coinciden». Se declara en el "
            f"manifiesto de `data/reference/`, junto a la procedencia del fichero."
        )
    if m != h:
        raise ShmirDesignError(
            f"`mature.fa` es de la release {m} de miRBase y `hairpin.fa` de la {h}. Se "
            f"aborta: entre releases miRBase añade, retira y RENOMBRA entradas, así que "
            f"un maduro buscado dentro de un precursor de otra versión puede no "
            f"aparecer o aparecer donde no toca — y eso no daría un error, daría una "
            f"geometría plausible. Hacen falta los dos ficheros de la MISMA release."
        )
    return m


def release_del_manifiesto(nombre: str, manifiesto: Path | str) -> str:
    """La release declarada para ese fichero, del manifiesto. Vacía si no está.

    Vacía es «no lo sé», no «no tiene»: quien llama decide, y `comprobar_release` aborta.
    """
    ruta = Path(manifiesto)
    if not ruta.is_file():
        return ""
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("#") or not linea.strip():
            continue
        campos = linea.split("\t")
        if campos and campos[0] == nombre:
            encontrado = _RELEASE.search(linea)
            return _normalizar(encontrado.group(1)) if encontrado else ""
    return ""
