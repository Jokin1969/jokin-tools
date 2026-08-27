"""Fixture de guias con su valor esperado, para la regresion de la pasajera.

`data/reference/guias_pasajera.fa` lleva en la cabecera de cada entrada lo que la regla
debe devolver:

    >nombre guia=TAGATAAGCATTATAATTCCTA bases_ok=ACG elegida=C
    TAGATAAGCATTATAATTCCTA

  - `bases_ok`: las bases que reproducen la estructura de SGEP en la posicion 1 de la
    pasajera. Se comparan contra `Passenger.candidates`.
  - `elegida`: la que el criterio debe elegir. Se compara contra `Passenger.chosen_base`.

Regla 1: de aqui no sale ninguna secuencia generada. Si el fichero no esta, los tests se
saltan de forma visible y no se sustituyen por guias inventadas — el valor esperado es
biologia, no formato, y una guia de mentira daria una regresion de mentira.

Invariante 4: el md5 esta declarado EN CODIGO, no solo en el manifiesto. Un checksum que
vive unicamente en un fichero de datos se puede editar para que un fichero malo pase.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import ChecksumMismatchError, ShmirDesignError

FIXTURE_NAME = "guias_pasajera.fa"

#: md5 del FICHERO tal cual, aportado con el fixture. No es el md5 de ninguna secuencia
#: canonica: aqui no hay transcrito que canonizar, hay una tabla de guias.
EXPECTED_MD5 = "6281e37478453f03a34ad0856d8c83f7"

#: Las cuatro guias que ya estaban en el repositorio con su propio test.
GUIDE_LENGTH = 22
VALID_BASES = frozenset("ACGT")


def fixture_path(data_dir: Path | str | None = None) -> Path:
    base = (
        Path(data_dir)
        if data_dir is not None
        else Path(__file__).resolve().parent.parent / "data" / "reference"
    )
    return base / FIXTURE_NAME


@dataclass(frozen=True)
class GuideExpectation:
    name: str
    guide: str
    ok: tuple[str, ...]
    chosen: str


def _bases(raw: str) -> tuple[str, ...]:
    """`ACT` y `A,C,T` son la misma cosa. Se aceptan las dos formas."""
    limpio = raw.strip().upper()
    if "," in limpio:
        return tuple(b.strip() for b in limpio.split(",") if b.strip())
    return tuple(limpio)


def _qualifiers(header: str, *, source: str, name: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for trozo in header.split()[1:]:
        if "=" not in trozo:
            continue
        clave, _, valor = trozo.partition("=")
        campos[clave.strip()] = valor.strip()
    for obligatorio in ("bases_ok", "elegida"):
        if obligatorio not in campos:
            raise ShmirDesignError(
                f"{source}: la cabecera de {name!r} no trae {obligatorio!r}. Se "
                f"esperaba `>nombre bases_ok=ACG elegida=C`; se aborta en vez de "
                f"adivinar el valor esperado de una regresion."
            )
    return campos


def parse_guide_fasta(text: str, *, source: str) -> tuple[GuideExpectation, ...]:
    """Lee el FASTA con los valores esperados en la cabecera."""
    entradas: list[GuideExpectation] = []
    nombre: str | None = None
    cabecera = ""
    partes: list[str] = []
    vistas: set[str] = set()

    def cerrar() -> None:
        nonlocal nombre, cabecera, partes
        if nombre is None:
            return
        guia = "".join(partes).upper().replace("U", "T")
        if len(guia) != GUIDE_LENGTH:
            raise ShmirDesignError(
                f"{source}: la guía {nombre!r} mide {len(guia)} nt y se esperaban "
                f"{GUIDE_LENGTH}; se aborta."
            )
        if set(guia) - VALID_BASES:
            raise ShmirDesignError(
                f"{source}: la guía {nombre!r} tiene bases que no son A/C/G/T; "
                f"se aborta."
            )
        if guia in vistas:
            raise ShmirDesignError(
                f"{source}: la guía de {nombre!r} está repetida; se aborta en vez de "
                f"contarla dos veces en la regresion."
            )
        vistas.add(guia)

        campos = _qualifiers(cabecera, source=source, name=nombre)
        ok = _bases(campos["bases_ok"])
        elegida = campos["elegida"].upper()
        for base in (*ok, elegida):
            if base not in VALID_BASES:
                raise ShmirDesignError(
                    f"{source}: {nombre!r} declara la base {base!r}, que no es A/C/G/T; "
                    f"se aborta."
                )
        if not ok:
            raise ShmirDesignError(
                f"{source}: {nombre!r} no declara ninguna base en bases_ok; se aborta."
            )
        if elegida not in ok:
            raise ShmirDesignError(
                f"{source}: {nombre!r} declara elegida={elegida} pero no está en "
                f"bases_ok={','.join(ok)}. La cabecera se contradice sola; se aborta."
            )
        entradas.append(
            GuideExpectation(name=nombre, guide=guia, ok=ok, chosen=elegida)
        )
        nombre, cabecera, partes = None, "", []

    for linea in text.splitlines():
        if linea.startswith(">"):
            cerrar()
            cabecera = linea[1:].strip()
            nombre = cabecera.split()[0] if cabecera else ""
            continue
        if nombre is not None:
            partes.append(linea.strip())
    cerrar()

    if not entradas:
        raise ShmirDesignError(
            f"{source}: no hay ninguna entrada; se aborta en vez de dar por pasada una "
            f"regresion vacía."
        )
    return tuple(entradas)


def load_guide_fixture(
    data_dir: Path | str | None = None, *, expected_md5: str | None = None
) -> tuple[GuideExpectation, ...]:
    """Lee el fixture comprobando su md5. Si no cuadra, PARA."""
    path = fixture_path(data_dir)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el fixture de guías {path} ({exc}); la regresion de la "
            f"pasajera queda sin ejecutar."
        ) from exc

    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    esperado = EXPECTED_MD5 if expected_md5 is None else expected_md5
    if md5 != esperado:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {esperado}. El fixture de guías NO es el "
            f"que dice ser; se aborta antes de fijar ninguna regresion con el."
        )
    try:
        texto = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(f"{path}: no es UTF-8 ({exc}); se aborta.") from exc
    return parse_guide_fasta(texto, source=str(path))
