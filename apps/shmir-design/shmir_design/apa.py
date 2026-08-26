"""Poliadenilacion alternativa con sitios MEDIDOS (bloque 5).

No es lo mismo que la zona prohibida. La zona prohibida pregunta si la ventana TOCA una
señal; el APA pregunta si esta POR DETRAS de un sitio de corte. Si lo esta, la diana no
existe en la isoforma corta, y eso es un techo de knockdown duro e invisible: por mucho
que la shmiR funcione, la fraccion de transcritos que ya no contiene la diana no se
puede silenciar.

En el 3'UTR murino el riesgo predicho afecta a 928 ventanas (42,8 %). Si el AATAAA de
288 resulta funcional, todas esas ventanas tienen ese techo.

**Esto no lo resuelve la app.** Lo que si hace es aceptar el dato: cuando hay un fichero
de sitios medidos (PolyA_DB, PolyASite), el dato SUSTITUYE a la prediccion, y con la
fraccion de lecturas de cada sitio se puede dar el techo. Cuando no lo hay, `riesgo_APA`
sigue siendo una PREDICCION y tanto el codigo como el informe lo dicen con esa palabra.

Geometria: un sitio medido ES el sitio de corte, no el hexamero. No se le suman los
10-30 nt de `polya.CLEAVAGE_*`; esa correccion es para las señales predichas.

Formato del fichero: `posicion<TAB>fraccion<TAB>nombre`, una linea por sitio, `#` para
comentarios; `fraccion` puede ir vacia si la fuente no la trae. La conversion desde un
volcado de PolyA_DB o PolyASite se hace UNA VEZ a mano y se versiona con su checksum,
igual que el resto de fixtures — no se adivina aqui el reparto de columnas de un fichero
que nadie ha visto (regla 4).

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from . import coords, polya, reference
from .errors import ChecksumMismatchError, ShmirDesignError

COORD_SYSTEMS = ("3utr", "transcrito")


@dataclass(frozen=True)
class ApaSite:
    """Un sitio de corte medido. `fraction` es None si la fuente no la trae."""

    position: int
    fraction: float | None
    name: str = ""

    def describe(self) -> str:
        trozo = f"{self.name or 'sitio'} en {self.position}"
        if self.fraction is not None:
            trozo += f" ({self.fraction:.0%} de las lecturas)"
        return trozo


@dataclass(frozen=True)
class ApaSites:
    sites: tuple[ApaSite, ...]
    source: str
    version: str
    checksum: str
    coords: str = "3utr"

    def __post_init__(self) -> None:
        for campo, valor in (
            ("source", self.source),
            ("version", self.version),
            ("checksum", self.checksum),
        ):
            if not valor or not str(valor).strip():
                raise ValueError(
                    f"Los sitios de APA necesitan {campo}: sin procedencia el dato no "
                    f"es auditable y no puede sustituir a una prediccion. Se aborta."
                )
        if self.coords not in COORD_SYSTEMS:
            raise ValueError(
                f"Sistema de coordenadas {self.coords!r} desconocido; se esperaba uno "
                f"de {', '.join(COORD_SYSTEMS)}. Se aborta en vez de suponer cual es."
            )
        if not self.sites:
            raise ShmirDesignError(
                f"{self.source}: no hay ningun sitio de APA. Se aborta: una tabla vacia "
                f"convertiria el riesgo en un cero medido, que es peor que una "
                f"prediccion honesta."
            )

    @property
    def provenance(self) -> str:
        return (
            f"{self.source}, version {self.version}, checksum {self.checksum}, "
            f"{len(self.sites)} sitio(s), coordenadas de {self.coords}"
        )

    @property
    def has_fractions(self) -> bool:
        return all(s.fraction is not None for s in self.sites)


def parse_apa_sites(
    text: str, *, source: str, version: str, checksum: str, coords: str = "3utr"
) -> ApaSites:
    """Lee la tabla de sitios medidos. Cualquier linea mal formada aborta la carga."""
    sitios: list[ApaSite] = []
    for numero, linea in enumerate(text.splitlines(), start=1):
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        campos = linea.split("\t") if "\t" in linea else linea.split()
        try:
            posicion = int(campos[0])
        except (ValueError, IndexError) as exc:
            raise ShmirDesignError(
                f"{source}:{numero}: la posicion {campos[0] if campos else ''!r} no es "
                f"un entero ({exc}); se aborta la carga de sitios de APA."
            ) from exc
        if posicion < 1:
            raise ShmirDesignError(
                f"{source}:{numero}: posicion {posicion} invalida (1-based); se aborta."
            )

        fraccion: float | None = None
        if len(campos) > 1 and campos[1].strip():
            try:
                fraccion = float(campos[1])
            except ValueError as exc:
                raise ShmirDesignError(
                    f"{source}:{numero}: la fraccion {campos[1]!r} no es un numero "
                    f"({exc}); se aborta en vez de tratarla como ausente."
                ) from exc
            if not 0.0 <= fraccion <= 1.0:
                raise ShmirDesignError(
                    f"{source}:{numero}: la fraccion {fraccion} esta fuera de [0, 1]. "
                    f"Se aborta: si la fuente da porcentajes o cuentas, hay que "
                    f"convertirlas antes, no aqui."
                )
        nombre = campos[2].strip() if len(campos) > 2 else ""
        sitios.append(ApaSite(position=posicion, fraction=fraccion, name=nombre))

    resultado = ApaSites(
        sites=tuple(sorted(sitios, key=lambda s: s.position)),
        source=source,
        version=version,
        checksum=checksum,
        coords=coords,
    )
    total = sum(s.fraction for s in resultado.sites if s.fraction is not None)
    if total > 1.0 + 1e-9:
        raise ShmirDesignError(
            f"{source}: las fracciones de lecturas suman {total:.4g}, mas de 1. Se "
            f"aborta: o la fuente da porcentajes, o hay sitios duplicados."
        )
    return resultado


def load_apa_sites(
    path: Path | str,
    *,
    version: str,
    expected_md5: str | None = None,
    coords: str = "3utr",
) -> ApaSites:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer la tabla de sitios de APA {path} ({exc}); el riesgo de "
            f"APA se quedaria en prediccion y eso hay que decirlo, no suponerlo."
        ) from exc
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de sustituir ninguna prediccion por el."
        )
    try:
        texto = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(f"{path}: no es UTF-8 ({exc}); se aborta.") from exc
    return parse_apa_sites(
        texto, source=str(path), version=version, checksum=md5, coords=coords
    )


@dataclass(frozen=True)
class ApaAssessment:
    """Riesgo de APA de una ventana. `measured` distingue dato de prediccion."""

    risk: bool
    measured: bool
    reason: str
    lost_fraction: float | None = None
    upstream: tuple[ApaSite, ...] = ()

    @property
    def knockdown_ceiling(self) -> float | None:
        """Fraccion maxima de transcritos silenciables. None si no hay dato."""
        if self.lost_fraction is None:
            return None
        return 1.0 - self.lost_fraction

    def as_column(self) -> str:
        if self.knockdown_ceiling is not None:
            return f"{self.knockdown_ceiling:.2f}"
        return f"prediccion:{'si' if self.risk else 'no'}"


def apa_assessment(
    *,
    window_start: int,
    sites: ApaSites | None,
    predicted_risk: bool,
) -> ApaAssessment:
    """Riesgo de APA. Con sitios medidos, el dato sustituye a la prediccion."""
    if sites is None:
        return ApaAssessment(
            risk=predicted_risk,
            measured=False,
            reason=(
                f"riesgo_APA={'si' if predicted_risk else 'no'} es una PREDICCION: no "
                f"hay tabla de sitios de poliadenilacion medidos cargada, asi que no se "
                f"sabe si el sitio proximal se usa. Con PolyA_DB o PolyASite este "
                f"numero se sustituiria por el dato."
            ),
        )

    #: Un sitio ESTRICTAMENTE anterior al inicio de la ventana corta el transcrito
    #: antes de la diana: en esa isoforma la diana no existe.
    arriba = tuple(s for s in sites.sites if s.position < window_start)
    if not arriba:
        return ApaAssessment(
            risk=False,
            measured=True,
            reason=(
                f"Dato medido: no hay ningun sitio de corte por delante de la ventana, "
                f"asi que la diana existe en todas las isoformas. {sites.provenance}."
            ),
            lost_fraction=0.0 if sites.has_fractions else None,
            upstream=(),
        )

    if not all(s.fraction is not None for s in arriba):
        return ApaAssessment(
            risk=True,
            measured=True,
            reason=(
                f"Dato medido: la ventana queda por detras de "
                f"{len(arriba)} sitio(s) de corte "
                f"({'; '.join(s.describe() for s in arriba)}), pero la fuente no trae "
                f"la fraccion de lecturas de todos ellos, asi que no se puede dar el "
                f"techo de knockdown. No se inventa. {sites.provenance}."
            ),
            upstream=arriba,
        )

    perdida = sum(s.fraction for s in arriba)
    return ApaAssessment(
        risk=perdida > 0.0,
        measured=True,
        reason=(
            f"Dato medido: la ventana queda por detras de "
            f"{'; '.join(s.describe() for s in arriba)}, asi que la diana falta en el "
            f"{perdida:.0%} de los transcritos. Techo de knockdown: "
            f"{1.0 - perdida:.0%}. {sites.provenance}."
        ),
        lost_fraction=perdida,
        upstream=arriba,
    )


# ─── El mapeo genomico↔transcrito, resuelto SIN coordenadas genomicas ────────
#
# El `.gb` de NM_011170.3 no trae coordenadas genomicas, asi que durante un tiempo aqui
# habia DOS mapeos posibles y ninguna forma de elegir: si la coordenada que publica
# PolyA_DB era el hexamero, `131937444` caia en 3utr:228 y el candidato `3utr:221`
# dejaba de ser inmune; si era el sitio de corte, caia detras y no le afectaba.
#
# El desempate no necesita ningun dato externo: lo da la propia leyenda de la base
# (`polya.PAS_IS_CLEAVAGE_SITE`). Y una vez resuelta la semantica, la comprobacion NO se
# hace con una resta —un solo punto de apoyo siempre cuadra—, sino exigiendo que las
# CUATRO coordenadas publicadas aterricen a la vez, con el MISMO desfase, sobre un
# hexamero de la CLASE que la propia base declara para cada una.

_POLYADB_CLASSES = ("AAUAAA", "AUUAAA", "Other")


def polyadb_class(motif: str) -> str:
    """La etiqueta que PolyA_DB pondria a nuestro hexamero (ADN → ARN).

    La base etiqueta en ARN y nosotros buscamos en ADN; sin traducir, `AATAAA` no
    coincidiria con `AAUAAA` y la comprobacion daria cero aciertos, que parece un
    resultado y es un desajuste de alfabeto — el mismo fallo que `mirna._seed_of`.
    """
    motif = motif.upper()
    if motif not in polya.ALL_SIGNALS:
        raise ValueError(
            f"{motif!r} no es una señal de poliadenilacion conocida, asi que no se le "
            f"puede asignar la clase que usaria PolyA_DB; se aborta el anclaje."
        )
    return {"AATAAA": "AAUAAA", "ATTAAA": "AUUAAA"}.get(motif, "Other")


class MappingHypothesis(StrEnum):
    CORTE = "PAS = sitio de corte"
    HEXAMERO = "PAS = hexamero"
    SIN_RESOLVER = "sin resolver"


@dataclass(frozen=True)
class PasAnchor:
    """Una coordenada publicada por PolyA_DB, con la clase de hexamero que declara."""

    locus: str
    genomic: int
    declared_class: str
    expression: bool = True
    note: str = ""

    def __post_init__(self) -> None:
        if not self.locus.strip():
            raise ValueError(
                "Un anclaje necesita su locus: sin el, una coordenada suelta no se "
                "puede volver a comprobar contra la base. Se aborta."
            )
        if self.declared_class not in _POLYADB_CLASSES:
            raise ValueError(
                f"Clase de hexamero {self.declared_class!r} desconocida; PolyA_DB usa "
                f"{', '.join(_POLYADB_CLASSES)}. Se aborta en vez de comparar contra "
                f"una etiqueta inventada."
            )


@dataclass(frozen=True)
class AnchoredSite:
    """Un PAS ya colocado sobre el 3'UTR: su hexamero y su banda de corte.

    `candidates` puede traer MAS DE UNO. Que un PAS admita dos hexameros de su clase
    dentro de la banda no invalida el anclaje —el desfase sigue acotado igual—, pero
    ese sitio concreto no identifica un hexamero y no puede entrar al modelo con banda
    de corte propia. Se dice, no se elige por nuestra cuenta.
    """

    locus: str
    genomic: int
    declared_class: str
    candidates: tuple[tuple[int, str], ...]
    expression: bool
    note: str = ""

    @property
    def ambiguous(self) -> bool:
        return len(self.candidates) > 1

    @property
    def motif(self) -> str:
        return self._unico()[1]

    @property
    def hexamer_start(self) -> int:
        return self._unico()[0]

    @property
    def hexamer_end(self) -> int:
        pos, motivo = self._unico()
        return pos + len(motivo) - 1

    @property
    def cleavage_band(self) -> tuple[int, int]:
        fin = self.hexamer_end
        return (fin + polya.CLEAVAGE_MIN, fin + polya.CLEAVAGE_MAX)

    def _unico(self) -> tuple[int, str]:
        if len(self.candidates) != 1:
            raise ValueError(
                f"{self.locus} admite {len(self.candidates)} hexameros de clase "
                f"{self.declared_class} dentro de su banda "
                f"({', '.join(f'{m} en 3utr:{p}' for p, m in self.candidates)}); no "
                f"identifica uno solo, asi que no se le asigna ninguno. Se aborta en "
                f"vez de elegir por nuestra cuenta."
            )
        return self.candidates[0]

    def describe(self) -> str:
        from .coords import Frame, label, span

        if self.ambiguous:
            cuales = ", ".join(
                f"{m} en {label(p, Frame.UTR3)}" for p, m in self.candidates
            )
            return (
                f"{self.locus}  {self.declared_class:<7} → AMBIGUO: {len(self.candidates)} "
                f"hexameros de su clase en la banda ({cuales}). Ancla, pero NO entra al "
                f"modelo con banda propia."
            )
        return (
            f"{self.locus}  {self.declared_class:<7} → corte "
            f"{span(*self.cleavage_band, Frame.UTR3)}, hexamero {self.motif} en "
            f"{label(self.hexamer_start, Frame.UTR3)}"
            + ("" if self.expression else "  (sin datos de expresion)")
            + (f"  ← {self.note}" if self.note else "")
        )


@dataclass(frozen=True)
class AnchorResult:
    hypothesis: MappingHypothesis
    anchors: tuple[AnchoredSite, ...]
    offsets: tuple[int, ...]
    cleavage_anchored: int
    hexamer_best: int
    total: int
    sequence_md5: str

    def by_locus(self, locus: str) -> AnchoredSite:
        for sitio in self.anchors:
            if sitio.locus == locus:
                return sitio
        raise KeyError(
            f"{locus!r} no quedo anclado sobre esta secuencia; se aborta en vez de "
            f"devolver el sitio de al lado."
        )

    def describe(self) -> list[str]:
        if self.hypothesis is not MappingHypothesis.CORTE:
            return [
                f"MAPEO GENOMICO↔TRANSCRITO: SIN RESOLVER sobre esta secuencia "
                f"({self.cleavage_anchored} de {self.total} coordenadas anclan). No se "
                f"usa: un techo que depende de una conversion sin comprobar no es un "
                f"techo medido.",
            ]
        lineas = [
            "MAPEO GENOMICO↔TRANSCRITO — RESUELTO SIN COORDENADAS GENOMICAS.",
            f"  {polya.PAS_IS_CLEAVAGE_SITE}",
            "  Hipotesis «PAS = hexamero»: DESCARTADA. Un hexamero es un punto, no una "
            "banda, asi que",
            f"  bajo esa lectura el aterrizaje tiene que ser EXACTO — y no hay ningun "
            f"desfase que haga",
            f"  aterrizar mas de {self.hexamer_best} de las {self.total} coordenadas. "
            f"Bajo «PAS = corte» aterrizan las {self.cleavage_anchored},",
            "  con el MISMO desfase y con la CLASE de hexamero que declara la propia "
            "base en cada una.",
            f"  No es una resta: son {self.total} puntos de apoyo independientes. "
            f"Desfase 3'UTR→mm10 acotado a "
            f"{self.offsets[0]}-{self.offsets[-1]} ({len(self.offsets)} valores); se "
            f"deja como INTERVALO",
            "  porque la banda de corte mide 20 nt y fijarlo en un entero seria "
            "inventarse precision.",
            "",
        ]
        for sitio in self.anchors:
            lineas.append(f"    {sitio.describe()}")
        return lineas


def anchor_polyadb(
    utr3: str,
    anchors,
    *,
    cleavage_min: int = polya.CLEAVAGE_MIN,
    cleavage_max: int = polya.CLEAVAGE_MAX,
) -> AnchorResult:
    """Coloca las coordenadas de PolyA_DB sobre el 3'UTR, y dice bajo que lectura.

    Se prueban las dos hipotesis contra la MISMA secuencia:

    - **corte** — la coordenada es el sitio de corte, asi que su hexamero cae en una
      BANDA `[p - cleavage_max, p - cleavage_min]`. Cuadra si en esa banda hay un
      hexamero de la clase que la base declara.
    - **hexamero** — la coordenada es el hexamero, asi que el aterrizaje es EXACTO.

    Solo se da por resuelta si TODAS las coordenadas anclan bajo la hipotesis del corte
    con un mismo desfase. Con una sola no se resuelve nada: una resta siempre cuadra.
    """
    secuencia = reference.canonical_form(utr3, name="3'UTR")
    anchors = tuple(anchors)
    if not anchors:
        raise ValueError(
            "No hay ninguna coordenada que anclar; se aborta en vez de dar por resuelto "
            "un mapeo que nadie ha comprobado."
        )

    hexameros: list[tuple[int, str]] = []
    for pos in range(1, len(secuencia) - 4):
        motivo = secuencia[pos - 1:pos + 5]
        if motivo in polya.ALL_SIGNALS:
            hexameros.append((pos, motivo))

    genomicas = [a.genomic for a in anchors]
    minimo, maximo = min(genomicas), max(genomicas)
    # El desfase posible esta acotado por la propia secuencia: toda coordenada tiene que
    # caer dentro del 3'UTR. Se barre ese intervalo y nada mas.
    inferior, superior = maximo - len(secuencia), minimo - 1

    def bajo_corte(desfase: int):
        colocados = []
        for ancla in anchors:
            corte = ancla.genomic - desfase
            if not 1 <= corte <= len(secuencia):
                return None
            elegidos = [
                (pos, motivo) for pos, motivo in hexameros
                if corte - cleavage_max <= pos + 5 <= corte - cleavage_min
                and polyadb_class(motivo) == ancla.declared_class
            ]
            if not elegidos:
                return None
            colocados.append((ancla, elegidos))
        return colocados

    validos = [d for d in range(inferior, superior + 1) if bajo_corte(d) is not None]

    inicios = {pos: motivo for pos, motivo in hexameros}
    mejor_hexamero = 0
    for desfase in range(inferior, superior + 1):
        aciertos = sum(
            1 for a in anchors
            if (a.genomic - desfase) in inicios
            and polyadb_class(inicios[a.genomic - desfase]) == a.declared_class
        )
        mejor_hexamero = max(mejor_hexamero, aciertos)

    if not validos:
        return AnchorResult(
            hypothesis=MappingHypothesis.SIN_RESOLVER,
            anchors=(),
            offsets=(),
            cleavage_anchored=0,
            hexamer_best=mejor_hexamero,
            total=len(anchors),
            sequence_md5=reference.sequence_md5(secuencia),
        )

    # Con varios desfases validos, el hexamero asignado a cada PAS tiene que ser el
    # MISMO en todos: si no lo es, el anclaje no identifica un sitio y no se usa.
    colocados: list[AnchoredSite] = []
    for indice, ancla in enumerate(anchors):
        opciones = set()
        for desfase in validos:
            for pos, motivo in bajo_corte(desfase)[indice][1]:
                opciones.add((pos, motivo))
        colocados.append(
            AnchoredSite(
                locus=ancla.locus,
                genomic=ancla.genomic,
                declared_class=ancla.declared_class,
                candidates=tuple(sorted(opciones)),
                expression=ancla.expression,
                note=ancla.note,
            )
        )

    colocados.sort(key=lambda s: s.candidates[0][0])
    return AnchorResult(
        hypothesis=MappingHypothesis.CORTE,
        anchors=tuple(colocados),
        offsets=tuple(validos),
        cleavage_anchored=len(colocados),
        hexamer_best=mejor_hexamero,
        total=len(anchors),
        sequence_md5=reference.sequence_md5(secuencia),
    )


# ─── La fraccion de isoforma larga, MEDIDA ───────────────────────────────────
#
# Aportada el 2026-08-26 desde PolyA_DB v4.1. Es lo que convierte el TECHO de
# «indeterminado» en un numero. La conversion de coordenadas que la bloqueaba esta
# resuelta arriba (`anchor_polyadb`), sin coordenadas genomicas y sobre cuatro puntos.


@dataclass(frozen=True)
class MeasuredSite:
    """Un PAS con datos de expresion en 3'READS+."""

    locus: str
    hexamer: str
    pse: float          # Poly(A) Site Expression, fraccion 0-1
    avg_rpm: float
    distal: bool
    note: str = ""

    @property
    def weighted(self) -> float:
        return self.avg_rpm * self.pse


def long_isoform_fraction(sites, *, weighted: bool) -> float:
    """Fraccion de isoforma LARGA a partir de los PAS medidos.

    `weighted=True`  → Σ(AvgRPM × PSE) del distal / Σ de todos. Es la buena: `AvgRPM`
                       esta condicionado a las muestras CON expresion, asi que sin
                       ponderar por PSE se cuenta como si todas expresaran.
    `weighted=False` → Σ(AvgRPM) del distal / Σ de todos. Se registra para poder ver
                       cuanto mueve la ponderacion, no para usarla.
    """
    if not sites:
        raise ValueError(
            "No hay ningun PAS medido: la fraccion de isoforma larga no se calcula "
            "sobre una lista vacia. Se aborta."
        )
    valor = (lambda s: s.weighted) if weighted else (lambda s: s.avg_rpm)
    total = sum(valor(s) for s in sites)
    distal = sum(valor(s) for s in sites if s.distal)
    if not distal:
        raise ValueError(
            "Ningun PAS medido es distal, asi que la fraccion de isoforma larga saldria "
            "0 por construccion y no por medida. Se aborta."
        )
    return distal / total


@dataclass(frozen=True)
class MeasuredFraction:
    source: str
    version: str
    date: str
    assembly: str
    gene: str
    gene_id: str
    representative: str
    total_pas: int
    with_expression: int
    sites: tuple[MeasuredSite, ...]
    #: Comprobaciones que BLOQUEAN el uso del dato. Mientras haya una, el dato no
    #: entra al pipeline. No es lo mismo que una reserva: una reserva se anota y se
    #: sigue, una comprobacion pendiente para el paso.
    pending: tuple[str, ...]
    tissue: str
    #: Reservas que se anotan y NO bloquean, porque no mueven el valor. Meterlas en
    #: `pending` haria que el dato pareciera inutilizable por algo que no cambia
    #: ninguna cifra, y eso es tan engañoso como omitirlas.
    caveats: tuple[str, ...] = ()
    #: A QUE secuencia se refieren estas coordenadas. La tabla no se aplica a
    #: ninguna otra: anclar unas coordenadas de Prnp murino sobre otro 3'UTR seria
    #: anclar ruido, y el ruido ancla si se le deja bastante sitio.
    utr3_md5: str = ""
    #: Las coordenadas publicadas, con la clase de hexamero que declara la base.
    #: Incluye las que NO tienen expresion: no cuentan para la fraccion, pero son
    #: puntos de apoyo del anclaje, y el anclaje se sostiene sobre su numero.
    anchors: tuple[PasAnchor, ...] = ()

    @property
    def working_value(self) -> float:
        return long_isoform_fraction(self.sites, weighted=True)

    @property
    def unweighted_value(self) -> float:
        return long_isoform_fraction(self.sites, weighted=False)

    @property
    def why_weighted(self) -> str:
        return (
            "La ponderada es la de trabajo porque AvgRPM esta condicionado a muestras "
            "CON expresion: sin ponderar por PSE se cuenta como si todas expresaran."
        )

    @property
    def usable(self) -> bool:
        """Mientras queden comprobaciones pendientes, el dato NO entra al pipeline."""
        return not self.pending

    def describe(self) -> list[str]:
        lineas = [
            f"FRACCION DE ISOFORMA LARGA — MEDIDA. {self.source} {self.version} "
            f"({self.date}), {self.assembly}, {self.gene} (Gene ID {self.gene_id}).",
            f"  {self.total_pas} PAS en el gen, {self.with_expression} con datos de "
            f"expresion; los demas por debajo de deteccion en 3'READS+ —incluidos los "
            f"intermedios del 3'UTR—, asi que no introducen techos.",
            f"  Representativo de la base: {self.representative} (NO es nuestro "
            f"NM_011170.3).",
            "",
            "  Sitios con expresion:",
        ]
        for sitio in self.sites:
            lineas.append(
                f"    {sitio.locus}  {sitio.hexamer:<7} PSE {sitio.pse:.1%}  "
                f"AvgRPM {sitio.avg_rpm:.2f}  "
                f"{'DISTAL' if sitio.distal else 'proximal'}"
                + (f"  ← {sitio.note}" if sitio.note else "")
            )
        lineas.extend(
            [
                "",
                f"  ponderada    Σ(AvgRPM × PSE) distal / Σ total = "
                f"{self.working_value:.2f}   ← VALOR DE TRABAJO",
                f"  sin ponderar Σ(AvgRPM) distal / Σ total        = "
                f"{self.unweighted_value:.2f}",
                f"  {self.why_weighted}",
                "",
                f"  TEJIDO: {self.tissue}. Las neuronas ALARGAN los 3'UTR, asi que la "
                f"fraccion larga en cerebro sera probablemente MAYOR. El "
                f"{self.working_value:.2f} es un LIMITE INFERIOR conservador para "
                f"nuestro tejido — y por eso la RT-qPCR de los dos amplicones deja de "
                f"ser solo confirmacion: puede MEJORAR el numero.",
                "",
            ]
        )
        if self.pending:
            lineas.append(
                "  PENDIENTE ANTES DE USARLO. El dato NO entra al pipeline todavia:"
            )
            lineas.extend(f"    {i}. {p}" for i, p in enumerate(self.pending, start=1))
        else:
            lineas.append(
                "  SIN COMPROBACIONES PENDIENTES: el dato ENTRA al pipeline. El mapeo "
                "genomico↔transcrito,"
            )
            lineas.append(
                "  que era lo unico que lo bloqueaba, esta resuelto sobre cuatro puntos "
                "de apoyo (ver arriba)."
            )
        if self.caveats:
            lineas.append("")
            lineas.append(
                "  RESERVAS ANOTADAS. No bloquean porque no mueven el valor, y por eso "
                "mismo no se omiten:"
            )
            lineas.extend(f"    {i}. {c}" for i, c in enumerate(self.caveats, start=1))
        return lineas


#: El `.gb` de NM_011170.3 sigue sin traer coordenadas genomicas —su bloque PRIMARY
#: referencia cDNA y EST (CK622972.1, AK148061.1, AK158908.1, AV361844.1), no un
#: cromosoma— y ya no hace falta: el mapeo se resuelve con `anchor_polyadb` sobre la
#: secuencia que ya esta en el repositorio. Ver `polya.PAS_IS_CLEAVAGE_SITE`.
POLYA_DB_PRNP = MeasuredFraction(
    source="PolyA_DB",
    version="v4.1",
    date="2025-09-15",
    assembly="mm10",
    gene="Prnp",
    gene_id="19122",
    representative="NM_001278256.1",
    total_pas=15,
    with_expression=5,
    utr3_md5="19f5fa2a77a87892770e2affdc90e0e4",
    sites=(
        MeasuredSite("chr2:+:131937444", "Other", 0.211, 0.55, distal=False,
                     note="TERCER sitio de corte, el proximal MAS USADO de los tres"),
        MeasuredSite("chr2:+:131937504", "AAUAAA", 0.235, 0.34, distal=False,
                     note="nuestro AATAAA de 3utr:288"),
        MeasuredSite("chr2:+:131938392", "Other", 0.705, 1.65, distal=True,
                     note="racimo terminal"),
    ),
    anchors=(
        PasAnchor("chr2:+:131937444", 131937444, "Other",
                  note="proximal mas usado: PSE 21,1 %, AvgRPM 0,55"),
        PasAnchor("chr2:+:131937504", 131937504, "AAUAAA",
                  note="PSE 23,5 %, AvgRPM 0,34"),
        PasAnchor("chr2:+:131938392", 131938392, "Other",
                  note="PSE 70,5 %, AvgRPM 1,65"),
        PasAnchor("chr2:+:131938427", 131938427, "AUUAAA", expression=False,
                  note="fuerza 99,9 %, conservado en humano y rata; SIN expresion, "
                       "asi que no entra en la fraccion — solo ancla"),
    ),
    tissue="TODOS LOS TEJIDOS, no cerebro",
    pending=(),
    caveats=(
        "El PAS terminal 131938427 y el que tiene expresion (131938392, 35 nt aguas "
        "arriba) se anotan como DOS y no se fusionan sin comprobarlo: fusionarlos suma "
        "su expresion y sube la fraccion larga sin dato. El anclaje los coloca sobre "
        "hexameros DISTINTOS —ATTAAA en 3utr:1214 el uno; TATAAA en 3utr:1178 o en "
        "3utr:1189 el otro, que ademas no distingue entre los dos—, asi que tampoco por "
        "ahi hay motivo para fusionarlos. NO MUEVE EL VALOR: 131938427 no tiene "
        "expresion, luego no suma nada a ninguna de las dos formulas.",
    ),
)


# ─── El techo deja de ser UNO: con tres sitios va POR TRAMOS ─────────────────
#
# Un solo numero (0,86) responde a «cuanta isoforma larga hay», que es la pregunta del
# extremo distal. La pregunta de un candidato es otra: «que fraccion de transcritos
# conserva MI diana». Y eso depende de por detras de CUANTOS cortes esta.
#
# Con los tres sitios medidos hay tres respuestas y no una:
#
#   por delante de 3utr:251  → la diana esta en todas las isoformas: sin techo
#   entre 3utr:271 y 3utr:303 → falta solo en la del corte proximal mas usado: 0,91
#   por detras de 3utr:323   → falta en las dos proximales: 0,86
#
# Colapsarlo a 0,86 para todos castigaria a las ventanas del tramo intermedio con un
# techo que no es el suyo. Y colapsarlo a 1,00 para las de delante del corte de 288
# —que es lo que habia— se saltaba un sitio de corte entero.


@dataclass(frozen=True)
class CeilingLayer:
    """Un tramo del 3'UTR con el mismo techo, y de que sitios lo hereda."""

    start_range: tuple[int, int]
    ceiling: float | None
    lost: tuple[MeasuredSite, ...]
    in_band: bool
    reason: str
    #: El espacio en que van `start_range`: el de LO TILADO, que con un mRNA completo
    #: NO es el del 3'UTR. Sin esto los tramos salian etiquetados `3utr:` con numeros
    #: del transcrito — el mismo fallo que motivo `coords.py`.
    frame: "coords.Frame" = None

    def describe(self) -> str:
        from .coords import span

        techo = "sin techo" if self.ceiling is None and not self.in_band else (
            "TECHO INDETERMINADO" if self.ceiling is None
            else f"techo {self.ceiling:.2f}"
        )
        return f"{span(*self.start_range, self.frame)}  {techo:<20} {self.reason}"


@dataclass(frozen=True)
class MeasuredApa:
    """La tabla medida, ya colocada sobre la secuencia que se esta analizando."""

    source: str
    table: MeasuredFraction
    anchor: AnchorResult
    #: Inicios de hexamero en el marco de LO TILADO.
    signal_starts: tuple[int, ...]
    offset: int
    layers: tuple[CeilingLayer, ...]
    #: El espacio de `signal_starts`, `earliest_cut` y los tramos.
    frame: "coords.Frame" = None

    @property
    def earliest_cut(self) -> int:
        """El corte mas temprano de todos los sitios medidos, en el marco de lo tilado.

        Es la frontera de la INMUNIDAD, y es la definicion estricta: por delante de
        aqui la ventana se conserva en TODAS las isoformas. Con el tercer sitio esta
        frontera se adelanta, asi que la lista de inmunes se recalcula — no se hereda.
        """
        return min(
            s.cleavage_band[0] + self.offset
            for s in self.anchor.anchors
            if not s.ambiguous
        )

    def layer_for(self, start: int) -> CeilingLayer:
        for capa in self.layers:
            if capa.start_range[0] <= start <= capa.start_range[1]:
                return capa
        raise ValueError(
            f"La posicion {start} cae fuera de los tramos de techo "
            f"({self.layers[0].start_range[0]}-{self.layers[-1].start_range[1]}); "
            f"se aborta en vez de devolver el techo del tramo de al lado."
        )

    def describe(self) -> list[str]:
        lineas = list(self.anchor.describe())
        lineas.extend(
            [
                "",
                "  TECHO POR TRAMOS. Con tres sitios de corte medidos el techo ya no es "
                "UNO: la pregunta",
                "  de un candidato no es cuanta isoforma larga hay, es que fraccion de "
                "transcritos conserva",
                "  SU diana — y eso depende de por detras de cuantos cortes esta.",
            ]
        )
        lineas.extend(f"    {c.describe()}" for c in self.layers)
        return lineas


def ceiling_layers(measured: "MeasuredApa") -> tuple[CeilingLayer, ...]:
    """Los tramos de techo de una tabla ya anclada. Cubren el 3'UTR entero, sin huecos."""
    return measured.layers


def _build_layers(
    anchor: AnchorResult, table: MeasuredFraction, length: int, offset: int, frame
):
    por_locus = {s.locus: s for s in table.sites}
    utiles = [
        s for s in anchor.anchors
        if not s.ambiguous and s.locus in por_locus and not por_locus[s.locus].distal
    ]
    if not utiles:
        raise ValueError(
            "Ningun sitio PROXIMAL medido quedo anclado sin ambiguedad, asi que no hay "
            "con que construir los tramos de techo. Se aborta en vez de emitir un techo "
            "unico que no se sabe de donde sale."
        )
    total = sum(s.weighted for s in table.sites)

    bordes = sorted({1, length + 1}
                    | {s.cleavage_band[0] + offset + 1 for s in utiles}
                    | {s.cleavage_band[1] + offset + 1 for s in utiles})
    capas: list[CeilingLayer] = []
    for inicio, siguiente in zip(bordes, bordes[1:]):
        fin = siguiente - 1
        detras = [s for s in utiles if inicio > s.cleavage_band[1] + offset]
        banda = [
            s for s in utiles
            if s.cleavage_band[0] + offset < inicio <= s.cleavage_band[1] + offset
        ]
        perdidos = tuple(por_locus[s.locus] for s in detras)
        if banda:
            capas.append(CeilingLayer(
                start_range=(inicio, fin), ceiling=None, lost=perdidos, in_band=True,
                frame=frame,
                reason=(
                    "dentro de la banda de corte de "
                    + ", ".join(s.locus for s in banda)
                    + ": no se sabe de que lado cae, asi que el techo es INDETERMINADO "
                      "(PENALIZADO, no TECHO)"
                ),
            ))
            continue
        if not detras:
            capas.append(CeilingLayer(
                start_range=(inicio, fin), ceiling=None, lost=(), in_band=False,
                frame=frame,
                reason="por delante de todos los cortes medidos: la diana esta en TODAS "
                       "las isoformas. INMUNE.",
            ))
            continue
        conservado = total - sum(s.weighted for s in perdidos)
        capas.append(CeilingLayer(
            start_range=(inicio, fin), ceiling=conservado / total, lost=perdidos,
            in_band=False, frame=frame,
            reason="por detras de " + ", ".join(s.locus for s in detras),
        ))
    return tuple(capas)


def resolve_measured(
    sequence: str,
    table: MeasuredFraction,
    *,
    anatomy=None,
) -> "MeasuredApa | None":
    """Coloca la tabla medida sobre la secuencia que se va a tilar, o devuelve `None`.

    `None` significa **esta tabla no habla de esta secuencia**, y es lo que tiene que
    pasar con cualquier otro 3'UTR: unas coordenadas de Prnp murino ancladas sobre otra
    secuencia anclarian ruido. La condicion es el md5 canonico del 3'UTR, igual que en
    el manifiesto — no el nombre del gen, que se puede teclear mal.

    Si hay anatomia, la tabla se ancla sobre el 3'UTR y las posiciones se devuelven en
    el marco de LO TILADO, que es el que usan las ventanas y las señales.
    """
    secuencia = reference.canonical_form(sequence, name="secuencia")
    if anatomy is not None and getattr(anatomy, "utr3", None):
        inicio, fin = anatomy.utr3
        utr3 = secuencia[inicio - 1:fin]
        offset = inicio - 1
        marco = coords.frame_of(anatomy)
    else:
        utr3 = secuencia
        offset = 0
        marco = coords.Frame.UTR3

    if not table.utr3_md5:
        raise ValueError(
            f"La tabla de {table.source} {table.version} no declara a que 3'UTR se "
            f"refiere, asi que no hay forma de comprobar que habla de esta secuencia; "
            f"se aborta en vez de anclarla sobre lo que haya."
        )
    if reference.sequence_md5(utr3) != table.utr3_md5:
        return None

    ancla = anchor_polyadb(utr3, table.anchors)
    if ancla.hypothesis is not MappingHypothesis.CORTE:
        return None
    return MeasuredApa(
        source=f"{table.source} {table.version}",
        table=table,
        anchor=ancla,
        signal_starts=tuple(
            sorted(s.hexamer_start + offset for s in ancla.anchors if not s.ambiguous)
        ),
        offset=offset,
        layers=_build_layers(ancla, table, len(utr3) + offset, offset, marco),
        frame=marco,
    )


# ─── El cabo suelto: 131938392 ───────────────────────────────────────────────
#
# Es el PAS con MAS expresion de los tres (PSE 70,5 %, AvgRPM 1,65) y es el NUMERADOR de
# la fraccion larga. Su lectura no esta resuelta y no se cierra por conveniencia hacia la
# que sostiene el numero que ya tenemos.


@dataclass(frozen=True)
class ClusterReading:
    locus: str
    resolved: bool
    band: tuple[int, int]
    hexamers: tuple[tuple[int, str], ...]
    terminal_locus: str
    conserved_block: tuple[int, int]
    external_site: int

    def describe(self) -> list[str]:
        from .coords import Frame, label, span

        banda = span(*self.band, Frame.UTR3)
        return [
            f"CABO SUELTO — NO RESUELTO: {self.locus}. Es el PAS con MAS expresion de "
            f"los tres (PSE 70,5 %,",
            "  AvgRPM 1,65) y es el NUMERADOR de la fraccion larga, asi que de su "
            "lectura depende lo que",
            "  significa el 0.86. Hay DOS, con consecuencias distintas:",
            f"    (a) es el racimo del PAS terminal {self.terminal_locus} → los dos son "
            f"el mismo sitio de corte",
            "        y la fraccion larga 0.86 es exactamente lo que dice ser.",
            f"    (b) es un corte PROPIO en {banda} → hay un TERCER corte por delante "
            f"del terminal, y todo",
            "        lo que quede detras lleva un techo adicional. Peor: por detras de "
            "esa banda ya no queda",
            "        ningun PAS CON EXPRESION MEDIDA, asi que ahi la medida no acota "
            "nada — no es un techo",
            "        bajo, es un techo del que esta tabla no sabe nada.",
            "  El anclaje de cuatro puntos ESTRECHA la banda a "
            f"{banda} (antes se estimaba mas ancha) pero NO",
            "  desempata: los dos hexameros de su clase que caben ahi son "
            + ", ".join(
                f"{m} en {label(p, Frame.UTR3)}" for p, m in self.hexamers
            )
            + ",",
            "  y por eso el sitio ancla pero no entra al modelo con banda propia.",
            "  QUE HAY HOY EN ESA ZONA, para saber cuanto cuesta no resolverlo:",
            f"    · el bloque conservado de {span(*self.conserved_block, Frame.UTR3)} "
            f"queda POR DELANTE de la banda: no le afecta.",
            f"    · {label(self.external_site, Frame.UTR3)} de la lista externa cae "
            f"DENTRO de la banda — indeterminado,",
            "      ni detras ni delante. Ya fallaba nuestro propio filtro duro de "
            "polyA, asi que no cambia nada hoy.",
            "    · CERO ventanas elegibles por detras de la banda, y cero dentro. "
            "Ninguno de los diez esta ahi.",
            "  POR QUE EL FRENTE SIGUE CERRADO IGUAL, y no por conveniencia: bajo las "
            "DOS lecturas el techo",
            "  del panel es >= 0.86. Bajo (a) es 0.86 exacto; bajo (b) los diez siguen "
            "por delante de la banda,",
            "  asi que conservan su diana en la isoforma de este corte Y en la "
            "terminal, cuya expresion no",
            "  esta medida — o sea 0.86 MAS lo que no se ha contado. La ambiguedad no "
            "mueve el numero DEL PANEL;",
            "  moveria el de cualquier candidato que se pusiera por detras de "
            f"{banda}, y hoy no hay ninguno.",
            "  QUE LO RESOLVERIA: 3'-end seq de cerebro murino, o la regla de "
            "agrupamiento que use la propia",
            "  base para decidir si estos dos PAS son un racimo. Ninguna de las dos "
            "esta aqui.",
        ]


CLUSTER_READING = ClusterReading(
    locus="chr2:+:131938392",
    resolved=False,
    band=(1199, 1207),
    hexamers=((1178, "TATAAA"), (1189, "TATAAA")),
    terminal_locus="chr2:+:131938427",
    conserved_block=(1138, 1163),
    external_site=1200,
)
