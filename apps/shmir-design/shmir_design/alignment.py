"""Alineamiento global y PERFIL de diferencias por clase.

El perfil no es decoracion: distingue dos investigaciones distintas y con dos culpables
distintos. Un **trasvase** —copiar de una pantalla a un formulario— solo puede PERDER
caracteres: da deleciones y nada mas. Si el perfil trae inserciones, sustituciones o
transposiciones, la secuencia no se copio mal, se **genero**.

Esa lectura habria acortado varias tandas de investigacion sobre la errata nº 5: el
perfil de aquel bloque era 5 deleciones, 9 inserciones, 4 sustituciones y 2
transposiciones. Con esa sola linea, "trasvase" quedaba descartado desde el principio.

Las transposiciones se cuentan aparte de las sustituciones a proposito: `CT` → `TC` son
dos bases cambiadas pero UN suceso, y de otra naturaleza.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from .errors import ShmirDesignError

#: Puntuacion del alineamiento. Lineal y simetrica: no se busca biologia, se busca la
#: lista de cambios mas corta que explique una secuencia a partir de la otra.
MATCH, MISMATCH, GAP = 1, -1, -2


class DiffClass(StrEnum):
    DELECION = "delecion"
    INSERCION = "insercion"
    SUSTITUCION = "sustitucion"
    TRANSPOSICION = "transposicion"


@dataclass(frozen=True)
class Difference:
    kind: DiffClass
    ref_start: int
    other_start: int
    ref: str
    other: str

    def __str__(self) -> str:
        return (
            f"{self.kind.value:<14} ref {self.ref_start:>5}  otra {self.other_start:>5}"
            f"  {self.ref or '–'} → {self.other or '–'}"
        )


@dataclass(frozen=True)
class Alignment:
    ref_length: int
    other_length: int
    identities: int
    differences: tuple[Difference, ...]
    #: Posiciones de la REFERENCIA tocadas por alguna diferencia. Las inserciones no
    #: ocupan posicion en la referencia, asi que marcan la posicion donde se insertan.
    ref_positions: frozenset[int] = field(default_factory=frozenset)

    @property
    def profile(self) -> dict[DiffClass, int]:
        return dict(Counter(d.kind for d in self.differences))

    @property
    def only_deletions(self) -> bool:
        return bool(self.differences) and all(
            d.kind is DiffClass.DELECION for d in self.differences
        )

    @property
    def reading(self) -> str:
        """De QUE investigacion se trata, segun el perfil."""
        if not self.differences:
            return ""
        if self.only_deletions:
            return (
                "Solo hay deleciones. Es compatible con un TRASVASE: copiar de una "
                "pantalla pierde caracteres, y lo que pierde son las carreras de "
                "homopolimero. Investiga por donde paso el texto, no quien lo escribio."
            )
        clases = [
            k.value
            for k in (DiffClass.INSERCION, DiffClass.SUSTITUCION, DiffClass.TRANSPOSICION)
            if self.profile.get(k)
        ]
        return (
            f"Hay {', '.join(clases)}. Un trasvase solo puede PERDER caracteres, asi que "
            f"esto no se copio mal: se genero. Investiga de donde salio la secuencia, no "
            f"por donde paso."
        )

    def format_text(self) -> str:
        lineas = [
            "── Perfil de diferencias ──",
            f"  referencia {self.ref_length} nt   otra {self.other_length} nt   "
            f"({self.other_length - self.ref_length:+d})",
            f"  identidades {self.identities}   diferencias {len(self.differences)}",
        ]
        if self.differences:
            lineas.append(
                "  "
                + ", ".join(
                    f"{k.value} × {n}" for k, n in sorted(self.profile.items())
                )
            )
            lineas.append("")
            lineas.extend(f"  {d}" for d in self.differences)
        lineas.extend(["", f"  {self.reading}"] if self.reading else [])
        return "\n".join(lineas)


def _traceback(ref: str, other: str, punt: list[list[int]]) -> list[Difference]:
    i, j = len(ref), len(other)
    crudas: list[Difference] = []
    while i > 0 or j > 0:
        if (
            i > 0
            and j > 0
            and punt[i][j]
            == punt[i - 1][j - 1] + (MATCH if ref[i - 1] == other[j - 1] else MISMATCH)
        ):
            if ref[i - 1] != other[j - 1]:
                crudas.append(
                    Difference(DiffClass.SUSTITUCION, i, j, ref[i - 1], other[j - 1])
                )
            i, j = i - 1, j - 1
        elif i > 0 and punt[i][j] == punt[i - 1][j] + GAP:
            crudas.append(Difference(DiffClass.DELECION, i, j, ref[i - 1], ""))
            i -= 1
        else:
            crudas.append(Difference(DiffClass.INSERCION, i, j, "", other[j - 1]))
            j -= 1
    crudas.reverse()
    return crudas


def _fundir_transposiciones(crudas: list[Difference]) -> list[Difference]:
    """Dos sustituciones adyacentes que intercambian sus bases son UNA transposicion."""
    salida: list[Difference] = []
    saltar = False
    for n, actual in enumerate(crudas):
        if saltar:
            saltar = False
            continue
        siguiente = crudas[n + 1] if n + 1 < len(crudas) else None
        if (
            siguiente is not None
            and actual.kind is DiffClass.SUSTITUCION
            and siguiente.kind is DiffClass.SUSTITUCION
            and siguiente.ref_start == actual.ref_start + 1
            and actual.ref == siguiente.other
            and actual.other == siguiente.ref
        ):
            salida.append(
                Difference(
                    DiffClass.TRANSPOSICION,
                    actual.ref_start,
                    actual.other_start,
                    actual.ref + siguiente.ref,
                    actual.other + siguiente.other,
                )
            )
            saltar = True
            continue
        salida.append(actual)
    return salida


def align(ref: str, other: str) -> Alignment:
    """Alineamiento global de `other` contra `ref`, con el perfil de diferencias.

    Es O(n·m) en tiempo y memoria: pensado para 3'UTR de unos pocos miles de nt, no
    para genomas. Se aborta antes que comerse la maquina.
    """
    a = "".join(ref.split()).upper()
    b = "".join(other.split()).upper()
    if not a or not b:
        raise ShmirDesignError(
            "No se alinea una secuencia vacia: se aborta en vez de devolver un perfil "
            "que diria que todo es una diferencia."
        )
    if len(a) * len(b) > 25_000_000:
        raise ShmirDesignError(
            f"Alinear {len(a)} × {len(b)} nt no cabe en memoria con este algoritmo. "
            f"Se aborta: esto es para 3'UTR, no para genomas."
        )

    punt = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for j in range(len(b) + 1):
        punt[0][j] = j * GAP
    for i in range(1, len(a) + 1):
        punt[i][0] = i * GAP
        anterior, actual = punt[i - 1], punt[i]
        base = a[i - 1]
        for j in range(1, len(b) + 1):
            actual[j] = max(
                anterior[j - 1] + (MATCH if base == b[j - 1] else MISMATCH),
                anterior[j] + GAP,
                actual[j - 1] + GAP,
            )

    diferencias = _fundir_transposiciones(_traceback(a, b, punt))
    tocadas: set[int] = set()
    for d in diferencias:
        if d.kind is DiffClass.INSERCION:
            tocadas.add(d.ref_start)
        else:
            tocadas.update(range(d.ref_start, d.ref_start + max(1, len(d.ref))))
    consumidas = sum(len(d.ref) for d in diferencias if d.kind is not DiffClass.INSERCION)
    return Alignment(
        ref_length=len(a),
        other_length=len(b),
        identities=len(a) - consumidas,
        differences=tuple(diferencias),
        ref_positions=frozenset(tocadas),
    )
