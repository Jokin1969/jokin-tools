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


@dataclass(frozen=True)
class SiteComparison:
    """Un sitio de la referencia, con lo que dice cada uno de los dos exports."""

    start: int
    guide: str
    score_a: float | None = None
    score_b: float | None = None
    rank_a: int | None = None
    rank_b: int | None = None

    @property
    def rank_shift(self) -> int | None:
        if self.rank_a is None or self.rank_b is None:
            return None
        return self.rank_b - self.rank_a

    @property
    def score_delta(self) -> float | None:
        if self.score_a is None or self.score_b is None:
            return None
        return self.score_b - self.score_a


@dataclass(frozen=True)
class ExportComparison:
    """Dos exports cruzados POR SITIO sobre la referencia.

    El cruce no va por guia ni por coordenada declarada: una ventana corrida da otra
    guia, y una entrada distinta corre las coordenadas. Lo unico estable entre las dos
    corridas es donde cae la ventana sobre el 3'UTR de referencia.
    """

    axis: str
    shared: tuple[SiteComparison, ...]
    only_a: tuple[SiteComparison, ...]
    only_b: tuple[SiteComparison, ...]
    without_site_a: int
    without_site_b: int

    @property
    def overlap(self) -> float:
        total = len(self.shared) + len(self.only_a) + len(self.only_b)
        return len(self.shared) / total if total else 0.0

    @property
    def moved(self) -> tuple[SiteComparison, ...]:
        return tuple(s for s in self.shared if s.rank_shift)

    def format_text(self) -> str:
        lineas = [
            "── Comparacion de dos corridas de miRarchitect ──",
            f"  Lo que cambia entre las dos: {self.axis}",
            f"  sitios en las dos:      {len(self.shared)}",
            f"  solo en la primera:     {len(self.only_a)}",
            f"  solo en la segunda:     {len(self.only_b)}",
            f"  SOLAPAMIENTO DE SITIOS: {self.overlap:.1%}",
            f"  cambian de puesto:      {len(self.moved)} de {len(self.shared)}",
        ]
        if self.moved:
            mayor = max(abs(s.rank_shift) for s in self.moved)
            lineas.append(f"  mayor salto de puesto:  {mayor}")
            lineas.append("  sitio      guia                       puesto      score")
            for sitio in sorted(self.moved, key=lambda s: -abs(s.rank_shift)):
                lineas.append(
                    f"  {sitio.start:<10} {sitio.guide:<24} "
                    f"{sitio.rank_a}→{sitio.rank_b} ({sitio.rank_shift:+d})   "
                    f"{sitio.score_a:.2f}→{sitio.score_b:.2f} "
                    f"({sitio.score_delta:+.2f})"
                )
        if self.without_site_a or self.without_site_b:
            lineas.append(
                f"  filas sin sitio en la referencia: {self.without_site_a} en la "
                f"primera, {self.without_site_b} en la segunda. No se cruzan: no hay "
                f"con que."
            )
        lineas.extend(
            [
                "",
                "  Que hacer con esta cifra: el umbral no lo pone este programa. Un "
                "solapamiento",
                "  bajo obliga a DEGRADAR la confianza que se le da a la puntuacion, y "
                "a decirlo",
                "  en el informe; uno alto no la valida, solo deja de ser un motivo "
                "para bajarla.",
            ]
        )
        return "\n".join(lineas)


def _site_of(row: ExportRow, utr3: str) -> int | None:
    """Donde cae la ventana sobre la REFERENCIA, o `None` si no cae en ningun sitio."""
    posicion = utr3.find(row.target)
    return posicion + 1 if posicion >= 0 else None


def compare_exports(
    a: Export, b: Export, utr3: str, *, axis: str
) -> ExportComparison:
    """Cruza dos exports por sitio. `axis` declara QUE cambia entre los dos.

    Se exige declararlo porque las dos preguntas que contesta esta funcion —cuanto
    mueve la puntuacion un cambio de la entrada, y cuanto la mueve un cambio de
    andamio— se responden con la misma aritmetica y significan cosas distintas. Un
    numero sin saber de que es no dice nada.
    """
    if not axis:
        raise ShmirDesignError(
            "Hay que declarar que cambia entre los dos exports (`axis`): la misma cifra "
            "significa una cosa si lo que cambio fue la secuencia de entrada y otra si "
            "fue el andamio."
        )

    def indexar(export: Export) -> tuple[dict[int, tuple[ExportRow, int]], int]:
        sitios: dict[int, tuple[ExportRow, int]] = {}
        sin_sitio = 0
        for puesto, fila in enumerate(export.rows, start=1):
            inicio = _site_of(fila, utr3)
            if inicio is None:
                sin_sitio += 1
            else:
                sitios[inicio] = (fila, puesto)
        return sitios, sin_sitio

    sitios_a, sin_a = indexar(a)
    sitios_b, sin_b = indexar(b)

    compartidos = tuple(
        SiteComparison(
            start=inicio,
            guide=sitios_a[inicio][0].guide,
            score_a=sitios_a[inicio][0].score,
            score_b=sitios_b[inicio][0].score,
            rank_a=sitios_a[inicio][1],
            rank_b=sitios_b[inicio][1],
        )
        for inicio in sorted(set(sitios_a) & set(sitios_b))
    )
    solo_a = tuple(
        SiteComparison(
            start=i, guide=sitios_a[i][0].guide,
            score_a=sitios_a[i][0].score, rank_a=sitios_a[i][1],
        )
        for i in sorted(set(sitios_a) - set(sitios_b))
    )
    solo_b = tuple(
        SiteComparison(
            start=i, guide=sitios_b[i][0].guide,
            score_b=sitios_b[i][0].score, rank_b=sitios_b[i][1],
        )
        for i in sorted(set(sitios_b) - set(sitios_a))
    )
    return ExportComparison(
        axis=axis, shared=compartidos, only_a=solo_a, only_b=solo_b,
        without_site_a=sin_a, without_site_b=sin_b,
    )
