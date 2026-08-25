"""Enmascarado de repeticiones (paso 1 del orden de operaciones).

El orden es: enmascarar y **RETILAR**. Nunca tachar candidatos a posteriori: una
ventana parcialmente solapada con un elemento repetitivo hay que reevaluarla entera
sobre la secuencia enmascarada, no eliminarla de una lista ya hecha.

El enmascarado convierte las posiciones repetitivas en `N`, y una ventana con `N` no es
evaluable: sus filtros de secuencia salen en NOT_RUN. Asi el enmascarado no puede
inflar ningun conteo por accidente.

Sin fixture de `rmsk` cargado, el paso no se ejecuta y el filtro `repeticiones` queda en
NOT_RUN para todas las ventanas: NOT_RUN no es PASS (regla 3).

Las señales de poliadenilacion se buscan sobre la secuencia SIN enmascarar: una señal
dentro de un elemento repetitivo sigue siendo una señal, y perderla seria menos
conservador, no mas.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .filters import FilterResult, FilterState

FILTER_NAME = "repeticiones"


@dataclass(frozen=True)
class RepeatMask:
    """Intervalos repetitivos, 1-based e inclusivos, sobre el 3'UTR."""

    intervals: tuple[tuple[int, int], ...]
    source: str

    def __post_init__(self) -> None:
        if not self.intervals:
            raise ValueError(
                f"La mascara de {self.source!r} no tiene ningun intervalo; se aborta en "
                f"vez de dejar correr un enmascarado que no enmascara nada. Si no hay "
                f"datos de repeticiones, pasa None y el filtro quedara en NOT_RUN."
            )
        if not self.source or not self.source.strip():
            raise ValueError("La mascara necesita una procedencia identificable.")
        for start, end in self.intervals:
            if start < 1 or end < start:
                raise ValueError(
                    f"Intervalo ({start}, {end}) invalido: las coordenadas son 1-based e "
                    f"inclusivas y el final no puede ser menor que el inicio; se aborta."
                )

    def covers(self, position: int) -> bool:
        return any(start <= position <= end for start, end in self.intervals)

    def overlapping(self, start: int, end: int) -> tuple[tuple[int, int], ...]:
        return tuple(
            (a, b) for a, b in self.intervals if start <= b and end >= a
        )


def apply_mask(sequence: str, mask: RepeatMask | None) -> str:
    """Sustituye por N los tramos repetitivos. Sin mascara, devuelve la secuencia igual."""
    if mask is None:
        return sequence
    bases = list(sequence)
    for start, end in mask.intervals:
        if end > len(sequence):
            raise ValueError(
                f"El intervalo repetitivo ({start}, {end}) de {mask.source!r} se sale de "
                f"la secuencia, que mide {len(sequence)} nt; se aborta el enmascarado "
                f"por coordenadas incoherentes."
            )
        for position in range(start, end + 1):
            bases[position - 1] = "N"
    return "".join(bases)


def filter_repeats(start: int, end: int, mask: RepeatMask | None) -> FilterResult:
    """Estado del filtro de repeticiones para una ventana en [start, end], 1-based."""
    if mask is None:
        return FilterResult(
            name=FILTER_NAME,
            state=FilterState.NOT_RUN,
            reason=(
                "No hay mascara de repeticiones cargada (falta el fixture de rmsk), "
                "asi que el filtro no se ejecuta. NOT_RUN no es PASS."
            ),
        )

    solapados = mask.overlapping(start, end)
    if solapados:
        detalle = ", ".join(f"{a}-{b}" for a, b in solapados)
        return FilterResult(
            name=FILTER_NAME,
            state=FilterState.FAIL,
            reason=f"Solapa elemento(s) repetitivo(s) de {mask.source}: {detalle}.",
        )
    return FilterResult(
        name=FILTER_NAME,
        state=FilterState.PASS,
        reason=f"Sin solape con los {len(mask.intervals)} elemento(s) de {mask.source}.",
    )


def load_mask_file(path: Path | str) -> RepeatMask:
    """Lee intervalos repetitivos de un fichero `inicio<TAB>fin`, 1-based e inclusivos.

    Formato propio y deliberadamente tonto: el fixture de `rmsk` se recorta a mano una
    vez (ver `docs/fixtures.md`) y esto solo lo lee. Cualquier linea mal formada aborta
    la carga; una mascara a medias enmascararia de menos, que es el error peligroso.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"No existe el fichero de repeticiones {path}; se aborta el enmascarado."
        ) from exc
    except OSError as exc:
        raise OSError(
            f"No se pudo leer el fichero de repeticiones {path} ({exc}); se aborta el "
            f"enmascarado."
        ) from exc

    intervals: list[tuple[int, int]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(
                f"{path}, linea {number}: se esperaban 2 campos (inicio y fin) y hay "
                f"{len(parts)}; se aborta el enmascarado."
            )
        try:
            start, end = int(parts[0]), int(parts[1])
        except ValueError as exc:
            raise ValueError(
                f"{path}, linea {number}: {parts!r} no son coordenadas enteras ({exc}); "
                f"se aborta el enmascarado."
            ) from exc
        intervals.append((start, end))

    if not intervals:
        raise ValueError(
            f"{path} no tiene ningun intervalo; se aborta en vez de correr un "
            f"enmascarado vacio que parecería haber enmascarado algo."
        )
    return RepeatMask(intervals=tuple(intervals), source=f"fichero {path}")
