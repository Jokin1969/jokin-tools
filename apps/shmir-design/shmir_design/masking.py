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

from dataclasses import dataclass, replace
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
    #: Especie de la BIBLIOTECA con la que se corrio, tal como la declara el resumen.
    species: str | None = None
    #: Biblioteca de repeticiones (p. ej. Dfam_3.0). El veredicto depende de ella tanto
    #: como del binario: la misma version del programa con otra biblioteca da otra cosa.
    library: str | None = None
    #: ¿Vino el RESUMEN completo junto al `.out`? Sin el, un fichero con CERO filas no
    #: distingue «no habia repetitivos» de «la corrida no llego a correr», y esa
    #: diferencia es la de PASS contra NOT_RUN.
    summary: str | None = None

    @property
    def conclusive(self) -> bool:
        """¿Se puede leer un CERO de este fichero como resultado?

        Con filas, si: hay algo que enseñar. Sin filas, solo si vino el resumen con los
        ceros explicitos por familia.
        """
        return bool(self.elements) or bool(self.summary)

    @property
    def provenance(self) -> str:
        partes = [self.source]
        if self.version:
            partes.append(f"version {self.version}")
        # La BIBLIOTECA va siempre que la haya, y pegada a la version: el veredicto
        # depende de las dos. La misma version del binario con otra biblioteca da otro
        # resultado, y «RepeatMasker 4.0.9» a solas no identifica la corrida.
        if self.library:
            partes.append(f"biblioteca {self.library}")
        if self.species:
            partes.append(f"especie {self.species}")
        if self.checksum:
            partes.append(f"checksum {self.checksum}")
        partes.append(f"{len(self.intervals)} elemento(s)")
        if self.elements:
            sines = sum(1 for e in self.elements if e.is_sine)
            partes.append(f"{sines} SINE")
        elif not self.summary:
            partes.append(
                "SIN filas y SIN resumen: NO CONCLUYENTE — un cero asi no distingue "
                "«no habia repetitivos» de «no llego a correr»"
            )
        return ", ".join(partes)

    def elements_overlapping(self, start: int, end: int) -> tuple[RepeatElement, ...]:
        return tuple(
            e for e in self.elements if start <= e.end and end >= e.start
        )

    def __post_init__(self) -> None:
        # Una mascara VACIA es legitima si vino el RESUMEN: significa «se busco y no hay
        # repetitivos», que es un resultado. Sin resumen sigue abortando, porque
        # entonces no se distingue de una corrida que no llego a correr.
        if not self.intervals and not self.summary:
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
    elementos: list[RepeatElement],
    *,
    source: str,
    version: str,
    checksum: str,
    summary: str | None = None,
) -> RepeatMask:
    """`summary` presente = una mascara VACIA es un resultado, no una laguna.

    Sin resumen, cero elementos se aborta: enmascararia de menos sin avisar y no hay
    forma de distinguirlo de una corrida que no llego a correr. Con el resumen —los
    ceros explicitos por familia— si se distingue, y entonces cero es cero.
    """
    if not elementos and not summary:
        raise ShmirDesignError(
            f"{source}: no se leyo ningun elemento repetitivo y NO vino el resumen. Se "
            f"aborta en vez de dejar correr una mascara vacia: sin el resumen, un cero "
            f"no distingue «no habia repetitivos» de «la corrida no llego a correr», y "
            f"esa diferencia es la de PASS contra NOT_RUN."
        )
    elementos.sort(key=lambda e: (e.start, e.end))
    return RepeatMask(
        intervals=tuple((e.start, e.end) for e in elementos),
        source=source,
        elements=tuple(elementos),
        version=version,
        checksum=checksum,
        summary=summary,
    )


#: La linea del resumen que declara con QUE biblioteca se corrio. Es lo unico que
#: distingue una corrida buena de una corrida contra la especie equivocada: el resto del
#: fichero sale con formato correcto y cifras plausibles.
_SPECIES_MARK = "the query species was assumed to be"


def declared_species(text: str) -> str | None:
    """La especie declarada en el resumen, en minusculas. `None` si no la declara."""
    for linea in text.splitlines():
        bajo = linea.strip().lower()
        if bajo.startswith(_SPECIES_MARK):
            return bajo[len(_SPECIES_MARK) :].strip(" .")
    return None


def parse_rmsk_out(
    text: str,
    *,
    source: str,
    version: str,
    checksum: str,
    expected_species: str,
    library: str | None = None,
    summary: str | None = None,
) -> RepeatMask:
    """Lee la salida `.out` de RepeatMasker. Coordenadas de la secuencia consultada.

    `expected_species` es OBLIGATORIO y se comprueba contra la especie que el propio
    fichero declara. Fallo real del 2026-08-26: un transcrito HUMANO corrido contra la
    biblioteca MURINA dio un fichero con formato correcto, cifras plausibles y Alu 0 % —
    imposible en humano—, y lo unico que lo delataba era la linea del resumen. Un cero
    obtenido SIN BUSCAR no puede pasar como veredicto.
    """
    _require_provenance(version, checksum)
    if not expected_species or not expected_species.strip():
        raise ValueError(
            "expected_species es obligatorio: sin decir que especie se esperaba, la "
            "comprobacion contra la biblioteca no se puede hacer y un cero sin buscar "
            "pasaria como veredicto. Se aborta."
        )
    esperada = expected_species.strip().lower()
    declarada = declared_species(text)
    if declarada is None:
        raise ShmirDesignError(
            f"{source}: el fichero no declara la especie de la biblioteca (falta la "
            f"linea «The query species was assumed to be ...» del resumen), asi que no "
            f"se puede comprobar contra la esperada ({esperada}). NO HABER PODIDO "
            f"COMPROBAR NO ES «COINCIDE»: se aborta el enmascarado."
        )
    if declarada != esperada:
        raise ShmirDesignError(
            f"{source}: la corrida se hizo contra la biblioteca de «{declarada}» y se "
            f"esperaba «{esperada}». Se aborta el enmascarado. Por que importa: una "
            f"corrida contra la especie equivocada sale con formato correcto y cifras "
            f"plausibles — un «Alu: 0 %» obtenido SIN BUSCAR Alu es indistinguible de "
            f"un «Alu: 0 %» real, y lo unico que lo delata es esta linea."
        )
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
    mask = _build(
        elementos, source=source, version=version, checksum=checksum, summary=summary
    )
    return replace(mask, species=declarada, library=library, summary=summary)


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
    path: Path | str,
    *,
    version: str,
    expected_md5: str | None = None,
    expected_species: str | None = None,
    library: str | None = None,
    summary_path: Path | str | None = None,
) -> RepeatMask:
    """Lee un fichero de repeticiones detectando el formato, y comprueba su md5.

    `expected_species` solo aplica al formato `.out`, que es el unico que declara la
    biblioteca con la que se corrio. En una tabla de UCSC la especie viene del ensamblaje
    y no hay linea que comprobar.

    `summary_path` es el RESUMEN (`.tbl`) que acompaña al `.out`. Sin el, un fichero con
    cero filas se aborta: no distingue «no habia repetitivos» de «no llego a correr».
    """
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
    if parece_tabla:
        return parse_rmsk_table(
            texto, source=str(path), version=version, checksum=md5
        )
    if not expected_species:
        raise ValueError(
            f"{path} es un `.out` de RepeatMasker y hace falta expected_species: es lo "
            f"unico que distingue una corrida contra la biblioteca correcta de una "
            f"contra otra especie, que sale con formato correcto y cifras plausibles. "
            f"Se aborta."
        )
    resumen = None
    if summary_path is not None:
        resumen_path = Path(summary_path)
        try:
            resumen = resumen_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ShmirDesignError(
                f"No se pudo leer el resumen {resumen_path} ({exc}); se aborta en vez "
                f"de leer el `.out` sin el."
            ) from exc
    return parse_rmsk_out(
        texto,
        source=str(path),
        version=version,
        checksum=md5,
        expected_species=expected_species,
        library=library,
        summary=resumen,
    )
