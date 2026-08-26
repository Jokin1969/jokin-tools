"""Lector del export de miRarchitect. Valida el fichero antes de creerselo.

El export limpio trae mucho mas que guia y score, y cada columna de mas es una
comprobacion que con un TSV de dos columnas no se podia hacer.

**Lo que NO prueba `guia == revcomp(diana)`.** Sale 26/26 sin excepciones porque la
columna `Target sequence` esta DERIVADA de la guia, no leida del transcrito. Sirve como
control de integridad del fichero —si alguna fila lo rompiera, el fichero esta dañado—
pero no distingue una corrupcion de la secuencia de entrada de una de la emision. Esa
prueba se retiro de las hipotesis por eso.

**El andamio se lee del LOOP, no de la etiqueta.** La columna `Pri-miRNA` dice
`hsa-mir-30a`, pero lo que decide es la secuencia: el loop del fichero es
`CTGTGAAGCCACAGATGGG` y el del proyecto `TAGTGAAGCCACAGATGTA`. Fiarse de la etiqueta es
lo que se deja de hacer aqui.

**La pasajera de la fuente se descarta a proposito.** Sigue la convencion de miR-30a
—dos nucleotidos borrados tras la posicion 9 y `GC` terminal— que no es la nuestra: la
nuestra cambia SOLO la posicion 1 y se elige plegando. Descartarla en silencio seria
peor que no leerla.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from .errors import ShmirDesignError
from .hard_filters import reverse_complement_rna
from .scaffold import ScaffoldSpec

#: El loop que trae el export de la corrida murina. Es el de miR-30a, no el nuestro.
SOURCE_LOOP = "CTGTGAAGCCACAGATGGG"

#: Por que no se usa la columna de pasajera de la fuente. Va escrito, no implicito.
PASSENGER_REJECTED = (
    "La pasajera del export sigue la convencion de miR-30a: "
    "revcomp(guia)[0:9] + revcomp(guia)[11:22] + 'GC', o sea dos nucleotidos borrados "
    "tras la posicion 9 y un GC terminal. La nuestra cambia SOLO la posicion 1 y se "
    "elige plegando contra la estructura de SGEP. Son horquillas distintas, asi que la "
    "columna se descarta: de miRarchitect se toma la guia y nada mas."
)

_COLUMNS = (
    "Pri-miRNA",
    "sequence_guide strand",
    "sequence_loop",
    "sequence_passenger strand",
    "Target sequence",
    "Start",
    "End",
    "Score",
)


def _dna(sequence: str) -> str:
    return "".join(sequence.split()).upper().replace("U", "T")


def _rc(sequence: str) -> str:
    return reverse_complement_rna(sequence).replace("U", "T")


def passenger_of(guide: str) -> str:
    """La pasajera que emite la fuente para esa guia. Se calcula para PODER descartarla.

    Verificada contra las 26 filas del export. No se usa para diseñar nada.
    """
    diana = _rc(_dna(guide))
    return diana[0:9] + diana[11:22] + "GC"


@dataclass(frozen=True)
class ExportRow:
    guide: str
    target: str
    start: int
    end: int
    score: float
    passenger: str

    @property
    def target_is_revcomp(self) -> bool:
        return self.guide == _rc(self.target)

    @property
    def declared_length(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class Export:
    rows: tuple[ExportRow, ...]
    loop: str
    flank5: str
    flank3: str
    declared_scaffold: str
    contained: tuple[tuple[str, str], ...]
    source: str

    integrity_note: str = (
        "`guia == revcomp(diana)` se comprueba como control de integridad del fichero, "
        "pero NO prueba nada sobre el origen de una corrupcion: la columna de diana "
        "esta derivada de la guia, no leida del transcrito."
    )

    @property
    def guide_lengths(self) -> set[int]:
        return {len(f.guide) for f in self.rows}

    @property
    def target_lengths(self) -> set[int]:
        return {len(f.target) for f in self.rows}

    @property
    def declared_lengths(self) -> set[int]:
        return {f.declared_length for f in self.rows}

    def check_scaffold(self, scaffold: ScaffoldSpec) -> None:
        """El loop del fichero contra el del andamio. Aborta si no son el mismo."""
        if self.loop != _dna(scaffold.loop):
            raise ShmirDesignError(
                f"{self.source}: el loop del fichero es {self.loop} y el del andamio "
                f"{scaffold.name} es {_dna(scaffold.loop)}. No son el mismo andamio, y "
                f"esto se decide por SECUENCIA: la etiqueta del fichero dice "
                f"{self.declared_scaffold!r}, pero una etiqueta no es una prueba. Un "
                f"score de procesamiento medido sobre otra horquilla no ordena estos "
                f"candidatos."
            )


def parse_export(text: str, *, source: str = "el export de miRarchitect") -> Export:
    """Lee el CSV y comprueba lo que se puede comprobar. Aborta ante cualquier rareza."""
    filas = list(csv.DictReader(StringIO(text)))
    if not filas:
        raise ShmirDesignError(f"{source}: el export no trae ninguna fila.")
    faltan = [c for c in _COLUMNS if c not in filas[0]]
    if faltan:
        raise ShmirDesignError(
            f"{source}: al export le faltan las columnas {faltan}. Se aborta: sin ellas "
            f"no se puede comprobar ni la longitud ni el andamio, que es justo para lo "
            f"que sirve un export limpio."
        )

    leidas: list[ExportRow] = []
    for numero, fila in enumerate(filas, start=2):
        try:
            inicio, fin = int(fila["Start"]), int(fila["End"])
            score = float(fila["Score"])
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source}, fila {numero}: Start/End/Score no son numeros "
                f"({fila['Start']!r}, {fila['End']!r}, {fila['Score']!r})."
            ) from exc
        entrada = ExportRow(
            guide=_dna(fila["sequence_guide strand"]),
            target=_dna(fila["Target sequence"]),
            start=inicio,
            end=fin,
            score=score,
            passenger=_dna(fila["sequence passenger strand"])
            if "sequence passenger strand" in fila
            else _dna(fila["sequence_passenger strand"]),
        )
        if not entrada.target_is_revcomp:
            raise ShmirDesignError(
                f"{source}, fila {numero}: la diana no es el complementario reverso de "
                f"la guia. El fichero esta dañado; se aborta antes de leer nada mas."
            )
        if entrada.declared_length != len(entrada.guide):
            raise ShmirDesignError(
                f"{source}, fila {numero}: End-Start+1 = {entrada.declared_length} y la "
                f"guia mide {len(entrada.guide)}. Se aborta: unas coordenadas que no "
                f"cuadran con su secuencia son el fallo que hay que cazar."
            )
        leidas.append(entrada)

    loops = {_dna(f["sequence_loop"]) for f in filas}
    if len(loops) != 1:
        raise ShmirDesignError(
            f"{source}: el fichero trae {len(loops)} loops distintos ({sorted(loops)}). "
            f"Un export con dos andamios no se puede tratar como uno solo."
        )
    etiquetas = {f["Pri-miRNA"].strip() for f in filas}

    # La comprobacion permanente: una guia contenida en otra fila del MISMO fichero es
    # la misma prediccion mutilada, no una ventana mas corta. En el fichero viejo la
    # habia y mapeaba exacta, porque el homopolimero se lo permitia.
    guias = [e.guide for e in leidas]
    contenidas = tuple(
        (a, b)
        for a in guias
        for b in guias
        if a != b and len(a) < len(b) and (b.startswith(a) or b.endswith(a))
    )

    return Export(
        rows=tuple(leidas),
        loop=loops.pop(),
        flank5=_dna(filas[0].get("sequence_5’ flanking region", "")),
        flank3=_dna(filas[0].get("sequence_3’ flanking region", "")),
        declared_scaffold=", ".join(sorted(etiquetas)),
        contained=contenidas,
        source=source,
    )
