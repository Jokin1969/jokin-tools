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

from .errors import ChecksumMismatchError, ShmirDesignError
from .filters import FilterResult, FilterState

FILTER_NAME = "repeticiones"


@dataclass(frozen=True)
class RepeatElement:
    """Un elemento repetitivo con su nombre y su familia, 1-based e inclusivo.

    La familia importa: en raton el riesgo son los SINE B1/B2, y una guia derivada de
    uno de ellos tiene miles de sitios perfectos. Eso no es un off-target, es una guia
    inservible, y el motivo del FAIL tiene que decirlo con esas palabras.
    """

    start: int
    end: int
    name: str
    family: str

    @property
    def is_sine(self) -> bool:
        return self.family.upper().startswith("SINE")

    def describe(self) -> str:
        return f"{self.name} ({self.family}) en {self.start}-{self.end}"


@dataclass(frozen=True)
class RepeatMask:
    """Intervalos repetitivos, 1-based e inclusivos, sobre el 3'UTR."""

    intervals: tuple[tuple[int, int], ...]
    source: str
    elements: tuple[RepeatElement, ...] = ()
    version: str | None = None
    checksum: str | None = None

    @property
    def provenance(self) -> str:
        partes = [self.source]
        if self.version:
            partes.append(f"version {self.version}")
        if self.checksum:
            partes.append(f"checksum {self.checksum}")
        partes.append(f"{len(self.intervals)} elemento(s)")
        if self.elements:
            sines = sum(1 for e in self.elements if e.is_sine)
            partes.append(f"{sines} SINE")
        return ", ".join(partes)

    def elements_overlapping(self, start: int, end: int) -> tuple[RepeatElement, ...]:
        return tuple(
            e for e in self.elements if start <= e.end and end >= e.start
        )

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
            raise ShmirDesignError(
                f"El intervalo repetitivo ({start}, {end}) de {mask.source!r} se sale de "
                f"la secuencia, que mide {len(sequence)} nt. Se aborta el enmascarado: "
                f"si el fichero de repeticiones esta en coordenadas genomicas, no sirve "
                f"aqui — hay que correr RepeatMasker sobre el propio FASTA del "
                f"transcrito, o convertir las coordenadas antes. Enmascarar con estas "
                f"taparia el tramo equivocado sin avisar."
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
        con_nombre = mask.elements_overlapping(start, end)
        detalle = (
            ", ".join(e.describe() for e in con_nombre)
            if con_nombre
            else ", ".join(f"{a}-{b}" for a, b in solapados)
        )
        return FilterResult(
            name=FILTER_NAME,
            state=FilterState.FAIL,
            reason=(
                f"Solapa elemento(s) repetitivo(s) de {mask.source}: {detalle}. Una "
                f"guia derivada de un elemento repetitivo tiene miles de sitios "
                f"perfectos: no es un off-target, es una guia inservible."
            ),
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


# ─── Lectura de RepeatMasker de verdad (bloque 2) ────────────────────────────

#: Columnas de la tabla `rmsk` de UCSC que interesan. genoStart es 0-BASED y genoEnd
#: exclusivo: la conversion a 1-based inclusivo es +1 en el inicio y nada en el final.
_UCSC_GENO_START = 6
_UCSC_GENO_END = 7
_UCSC_REP_NAME = 10
_UCSC_REP_CLASS = 11
_UCSC_REP_FAMILY = 12
_UCSC_MIN_FIELDS = 13

#: Columnas del `.out` de RepeatMasker: begin, end, repeat, class/family.
_OUT_BEGIN = 5
_OUT_END = 6
_OUT_REPEAT = 9
_OUT_CLASS = 10
_OUT_MIN_FIELDS = 11


def _require_provenance(version: str, checksum: str) -> None:
    for campo, valor in (("version", version), ("checksum", checksum)):
        if not valor or not str(valor).strip():
            raise ValueError(
                f"La mascara de repeticiones necesita {campo}: sin procedencia el "
                f"enmascarado no es auditable. Se aborta."
            )


def _build(
    elementos: list[RepeatElement], *, source: str, version: str, checksum: str
) -> RepeatMask:
    if not elementos:
        raise ShmirDesignError(
            f"{source}: no se leyo ningun elemento repetitivo. Se aborta en vez de "
            f"dejar correr una mascara vacia, que enmascararia de menos sin avisar."
        )
    elementos.sort(key=lambda e: (e.start, e.end))
    return RepeatMask(
        intervals=tuple((e.start, e.end) for e in elementos),
        source=source,
        elements=tuple(elementos),
        version=version,
        checksum=checksum,
    )


def parse_rmsk_out(
    text: str, *, source: str, version: str, checksum: str
) -> RepeatMask:
    """Lee la salida `.out` de RepeatMasker. Coordenadas de la secuencia consultada."""
    _require_provenance(version, checksum)
    elementos: list[RepeatElement] = []
    for numero, linea in enumerate(text.splitlines(), start=1):
        if not linea.strip():
            continue
        campos = linea.split()
        if not campos[0].lstrip("-").isdigit():
            continue  # cabecera
        if len(campos) < _OUT_MIN_FIELDS:
            raise ShmirDesignError(
                f"{source}:{numero}: una fila de RepeatMasker tiene {len(campos)} "
                f"campo(s) y hacen falta al menos {_OUT_MIN_FIELDS}; se aborta el "
                f"enmascarado en vez de saltarse la fila."
            )
        try:
            inicio, fin = int(campos[_OUT_BEGIN]), int(campos[_OUT_END])
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source}:{numero}: las coordenadas no son numeros ({exc}); se aborta."
            ) from exc
        elementos.append(
            RepeatElement(
                start=inicio,
                end=fin,
                name=campos[_OUT_REPEAT],
                family=campos[_OUT_CLASS],
            )
        )
    return _build(elementos, source=source, version=version, checksum=checksum)


def parse_rmsk_table(
    text: str, *, source: str, version: str, checksum: str
) -> RepeatMask:
    """Lee la tabla `rmsk` de UCSC. genoStart es 0-based; se convierte a 1-based."""
    _require_provenance(version, checksum)
    elementos: list[RepeatElement] = []
    for numero, linea in enumerate(text.splitlines(), start=1):
        if not linea.strip() or linea.startswith("#"):
            continue
        campos = linea.split("\t")
        if len(campos) < _UCSC_MIN_FIELDS:
            raise ShmirDesignError(
                f"{source}:{numero}: la tabla rmsk tiene {len(campos)} campo(s) y hacen "
                f"falta al menos {_UCSC_MIN_FIELDS}; se aborta el enmascarado."
            )
        try:
            inicio = int(campos[_UCSC_GENO_START]) + 1
            fin = int(campos[_UCSC_GENO_END])
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source}:{numero}: las coordenadas no son numeros ({exc}); se aborta."
            ) from exc
        elementos.append(
            RepeatElement(
                start=inicio,
                end=fin,
                name=campos[_UCSC_REP_NAME],
                family=f"{campos[_UCSC_REP_CLASS]}/{campos[_UCSC_REP_FAMILY]}",
            )
        )
    return _build(elementos, source=source, version=version, checksum=checksum)


def load_rmsk(
    path: Path | str, *, version: str, expected_md5: str | None = None
) -> RepeatMask:
    """Lee un fichero de repeticiones detectando el formato, y comprueba su md5."""
    import hashlib

    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el fichero de repeticiones {path} ({exc}); se aborta el "
            f"enmascarado."
        ) from exc
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de enmascarar nada con el."
        )
    try:
        texto = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(f"{path}: no es UTF-8 ({exc}); se aborta.") from exc

    parece_tabla = any(
        linea.count("\t") >= _UCSC_MIN_FIELDS - 1
        for linea in texto.splitlines()
        if linea.strip() and not linea.startswith("#")
    )
    lector = parse_rmsk_table if parece_tabla else parse_rmsk_out
    return lector(texto, source=str(path), version=version, checksum=md5)
