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
                    f"es auditable y no puede sustituir a una predicción. Se aborta."
                )
        if self.coords not in COORD_SYSTEMS:
            raise ValueError(
                f"Sistema de coordenadas {self.coords!r} desconocido; se esperaba uno "
                f"de {', '.join(COORD_SYSTEMS)}. Se aborta en vez de suponer cual es."
            )
        if not self.sites:
            raise ShmirDesignError(
                f"{self.source}: no hay ningún sitio de APA. Se aborta: una tabla vacía "
                f"convertiria el riesgo en un cero medido, que es peor que una "
                f"predicción honesta."
            )

    @property
    def provenance(self) -> str:
        return (
            f"{self.source}, versión {self.version}, checksum {self.checksum}, "
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
                f"{source}:{numero}: la posición {campos[0] if campos else ''!r} no es "
                f"un entero ({exc}); se aborta la carga de sitios de APA."
            ) from exc
        if posicion < 1:
            raise ShmirDesignError(
                f"{source}:{numero}: posición {posicion} invalida (1-based); se aborta."
            )

        fraccion: float | None = None
        if len(campos) > 1 and campos[1].strip():
            try:
                fraccion = float(campos[1])
            except ValueError as exc:
                raise ShmirDesignError(
                    f"{source}:{numero}: la fracción {campos[1]!r} no es un número "
                    f"({exc}); se aborta en vez de tratarla como ausente."
                ) from exc
            if not 0.0 <= fraccion <= 1.0:
                raise ShmirDesignError(
                    f"{source}:{numero}: la fracción {fraccion} está fuera de [0, 1]. "
                    f"Se aborta: si la fuente da porcentajes o cuentas, hay que "
                    f"convertirlas antes, no aquí."
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
            f"{source}: las fracciones de lecturas suman {total:.4g}, más de 1. Se "
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
            f"APA se quedaria en predicción y eso hay que decirlo, no suponerlo."
        ) from exc
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de sustituir ninguna predicción por el."
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
                f"riesgo_APA={'si' if predicted_risk else 'no'} es una PREDICCIÓN: no "
                f"hay tabla de sitios de poliadenilación medidos cargada, así que no se "
                f"sabe si el sitio proximal se usa. Con PolyA_DB o PolyASite este "
                f"número se sustituiria por el dato."
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
                f"Dato medido: no hay ningún sitio de corte por delante de la ventana, "
                f"así que la diana existe en todas las isoformas. {sites.provenance}."
            ),
            lost_fraction=0.0 if sites.has_fractions else None,
            upstream=(),
        )

    if not all(s.fraction is not None for s in arriba):
        return ApaAssessment(
            risk=True,
            measured=True,
            reason=(
                f"Dato medido: la ventana queda por detrás de "
                f"{len(arriba)} sitio(s) de corte "
                f"({'; '.join(s.describe() for s in arriba)}), pero la fuente no trae "
                f"la fracción de lecturas de todos ellos, así que no se puede dar el "
                f"techo de knockdown. No se inventa. {sites.provenance}."
            ),
            upstream=arriba,
        )

    perdida = sum(s.fraction for s in arriba)
    return ApaAssessment(
        risk=perdida > 0.0,
        measured=True,
        reason=(
            f"Dato medido: la ventana queda por detrás de "
            f"{'; '.join(s.describe() for s in arriba)}, así que la diana falta en el "
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
            f"{motif!r} no es una señal de poliadenilación conocida, así que no se le "
            f"puede asignar la clase que usaria PolyA_DB; se aborta el anclaje."
        )
    return {"AATAAA": "AAUAAA", "ATTAAA": "AUUAAA"}.get(motif, "Other")


class MappingHypothesis(StrEnum):
    CORTE = "PAS = sitio de corte"
    HEXAMERO = "PAS = hexámero"
    SIN_RESOLVER = "sin resolver"


@dataclass(frozen=True)
class PasAnchor:
    """Una coordenada publicada por PolyA_DB, con la clase de hexamero que declara."""

    locus: str
    genomic: int
    declared_class: str
    expression: bool = True
    note: str = ""
    #: PSE y AvgRPM del PAS, cuando los tiene. Van AQUI y no dentro de `note` porque el
    #: informe los IMPRIME: escritos en la prosa de la nota, el fichero los llevaba
    #: ademas en sus columnas y las dos copias ya habian empezado a discrepar — la nota
    #: decia «PSE 21,1 %» y la columna 0.211, y nada obligaba a que coincidieran.
    #: Principio nº 11: la cifra se emite, no se escribe.
    pse: float | None = None
    avgrpm: float | None = None

    def __post_init__(self) -> None:
        if not self.locus.strip():
            raise ValueError(
                "Un anclaje necesita su locus: sin el, una coordenada suelta no se "
                "puede volver a comprobar contra la base. Se aborta."
            )
        if self.declared_class not in _POLYADB_CLASSES:
            raise ValueError(
                f"Clase de hexámero {self.declared_class!r} desconocida; PolyA_DB usa "
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
    #: Viajan desde el `PasAnchor` para poder EMITIRLAS aqui. Escritas en la prosa de
    #: `note` estaban ademas en las columnas del fichero, y las dos copias ya habian
    #: empezado a discrepar. Principio nº 11.
    pse: float | None = None
    avgrpm: float | None = None

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
                f"{self.locus} admite {len(self.candidates)} hexámeros de clase "
                f"{self.declared_class} dentro de su banda "
                f"({', '.join(f'{m} en 3utr:{p}' for p, m in self.candidates)}); no "
                f"identifica uno solo, así que no se le asigna ninguno. Se aborta en "
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
                f"hexámeros de su clase en la banda ({cuales}). Ancla, pero NO entra al "
                f"modelo con banda propia."
            )
        return (
            f"{self.locus}  {self.declared_class:<7} → corte "
            f"{span(*self.cleavage_band, Frame.UTR3)}, hexámero {self.motif} en "
            f"{label(self.hexamer_start, Frame.UTR3)}"
            + ("" if self.expression else "  (sin datos de expresión)")
            + self._medida()
            + (f"  ← {self.note}" if self.note else "")
        )

    def _medida(self) -> str:
        """PSE y AvgRPM, EMITIDOS de las columnas. Vacio si el PAS no los tiene."""
        if self.pse is None or self.avgrpm is None:
            return ""
        return f"  PSE {self.pse:.1%}, AvgRPM {self.avgrpm:.2f}"


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
                f"usa: un techo que depende de una conversión sin comprobar no es un "
                f"techo medido.",
            ]
        lineas = [
            "MAPEO GENOMICO↔TRANSCRITO — RESUELTO SIN COORDENADAS GENOMICAS.",
            f"  {polya.PAS_IS_CLEAVAGE_SITE}",
            "  Hipotesis «PAS = hexámero»: DESCARTADA. Un hexámero es un punto, no una "
            "banda, así que",
            f"  bajo esa lectura el aterrizaje tiene que ser EXACTO — y no hay ningún "
            f"desfase que haga",
            f"  aterrizar más de {self.hexamer_best} de las {self.total} coordenadas. "
            f"Bajo «PAS = corte» aterrizan las {self.cleavage_anchored},",
            "  con el MISMO desfase y con la CLASE de hexámero que declara la propia "
            "base en cada una.",
            f"  No es una resta: son {self.total} puntos de apoyo independientes. "
            f"Desfase 3'UTR→mm10 acotado a "
            f"{self.offsets[0]}-{self.offsets[-1]} ({len(self.offsets)} valores); se "
            f"deja como INTERVALO",
            "  porque la banda de corte mide 20 nt y fijarlo en un entero sería "
            "inventarse precisión.",
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
                pse=ancla.pse,
                avgrpm=ancla.avgrpm,
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
            "No hay ningún PAS medido: la fracción de isoforma larga no se calcula "
            "sobre una lista vacía. Se aborta."
        )
    valor = (lambda s: s.weighted) if weighted else (lambda s: s.avg_rpm)
    total = sum(valor(s) for s in sites)
    distal = sum(valor(s) for s in sites if s.distal)
    if not distal:
        raise ValueError(
            "Ningún PAS medido es distal, así que la fracción de isoforma larga saldria "
            "0 por construcción y no por medida. Se aborta."
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
            "La ponderada es la de trabajo porque AvgRPM está condicionado a muestras "
            "CON expresión: sin ponderar por PSE se cuenta como si todas expresaran."
        )

    @property
    def usable(self) -> bool:
        """Mientras queden comprobaciones pendientes, el dato NO entra al pipeline."""
        return not self.pending

    def describe(self) -> list[str]:
        lineas = [
            f"FRACCIÓN DE ISOFORMA LARGA — MEDIDA. {self.source} {self.version} "
            f"({self.date}), {self.assembly}, {self.gene} (Gene ID {self.gene_id}).",
            f"  {self.total_pas} PAS en el gen, {self.with_expression} con datos de "
            f"expresión; los demas por debajo de detección en 3'READS+ —incluidos los "
            f"intermedios del 3'UTR—, así que no introducen techos.",
            f"  Representativo de la base: {self.representative} (NO es nuestro "
            f"NM_011170.3).",
            "",
            "  Sitios con expresión:",
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
                f"  TEJIDO: {self.tissue}. Las neuronas ALARGAN los 3'UTR, así que la "
                f"fracción larga en cerebro será probablemente MAYOR. El "
                f"{self.working_value:.2f} es un LÍMITE INFERIOR conservador para "
                f"nuestro tejido — y por eso la RT-qPCR de los dos amplicones deja de "
                f"ser solo confirmación: puede MEJORAR el número.",
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
                "  que era lo único que lo bloqueaba, está resuelto sobre cuatro puntos "
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
#: EL FORMATO, DECLARADO. Este fichero es DATO y entra por el gestor; la REGLA sobre
#: que hacer con el —que un hexamero con uso medido se trate como funcional— vive en el
#: codigo y no lleva bandera. Son dos cosas y van separadas a proposito.
POLYADB_COLUMNS = ("pas_id", "coordenada", "clase", "pse", "avgrpm", "distal", "nota")

#: Cabecera obligatoria. Sin `utr3_md5` la tabla no se puede aplicar a NADA —es la
#: condicion de que hable de esta secuencia— y sin `version` ni `ensamblaje` la corrida
#: no es reproducible: las cifras cambian entre versiones y dos ensamblajes dan
#: coordenadas distintas.
POLYADB_HEADER = ("fuente", "version", "ensamblaje", "gen", "tejido", "utr3_md5")

POLYADB_FORMAT = (
    "TSV con cabecera de metadatos en líneas `# clave<TAB>valor` y una fila por PAS. "
    f"Columnas: {', '.join(POLYADB_COLUMNS)}. Los PAS SIN expresión se incluyen igual, "
    f"con `pse` y `avgrpm` vacíos: sirven de ANCLA aunque no sumen a ninguna fracción. "
    f"Cabecera obligatoria: {', '.join(POLYADB_HEADER)}."
)

#: Nombre del fichero por especie. El del raton lleva sufijo como los demas desde que
#: hay dos especies: sin el, la tabla murina contaria como presente para un humano y su
#: frente saldria cerrado con los datos del gen equivocado.
POLYADB_FILENAME = "polya_db_{slug}.tsv"


def _cabecera(texto: str, *, source: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    reservas: list[str] = []
    for linea in texto.splitlines():
        if not linea.startswith("#"):
            continue
        cuerpo = linea.lstrip("#").strip()
        if "\t" not in cuerpo:
            continue                       # comentario libre, no metadato
        clave, valor = cuerpo.split("\t", 1)
        clave = clave.strip()
        if clave == "reserva":
            reservas.append(valor.strip())
        else:
            valores[clave] = valor.strip()
    valores["_reservas"] = "\n".join(reservas)
    faltan = [c for c in POLYADB_HEADER if not valores.get(c)]
    if faltan:
        raise ShmirDesignError(
            f"{source}: a la cabecera le faltan {', '.join(faltan)}. Sin `utr3_md5` la "
            f"tabla no se puede aplicar a ninguna secuencia —es la condición de que "
            f"hable de esta— y sin versión ni ensamblaje la corrida no es reproducible. "
            f"Se aborta en vez de aplicarla a medias.\n\n{POLYADB_FORMAT}"
        )
    return valores


def _fraccion(bruto: str, *, campo: str, source: str, fila: int) -> float:
    try:
        valor = float(bruto)
    except ValueError as exc:
        raise ShmirDesignError(
            f"{source}, fila {fila}: {campo}={bruto!r} no es un número; se aborta."
        ) from exc
    if not 0.0 <= valor <= 1.0:
        raise ShmirDesignError(
            f"{source}, fila {fila}: {campo}={valor} no es una FRACCIÓN (0-1). PolyA_DB "
            f"pública el PSE en tanto por ciento; aquí va en tanto por uno. Se aborta "
            f"en vez de meter un 21,1 donde se esperaba un 0,211."
        )
    return valor


def parse_polyadb(texto: str, *, source: str) -> MeasuredFraction:
    """Lee la tabla de PolyA_DB. Cualquier fila mal formada ABORTA la carga.

    No se salta ninguna linea «rara»: una tabla a medias daria un techo que parece
    medido y no lo es, y eso es peor que no tenerla.
    """
    cabecera = _cabecera(texto, source=source)
    filas = [
        l for l in texto.splitlines()
        if l.strip() and not l.startswith("#")
    ]
    if not filas:
        raise ShmirDesignError(
            f"{source}: no hay ni una fila de PAS. Una tabla vacía y «no hay tabla» son "
            f"cosas distintas y este fichero no las distingue; se aborta.\n\n"
            f"{POLYADB_FORMAT}"
        )
    columnas = tuple(c.strip() for c in filas[0].split("\t"))
    if columnas != POLYADB_COLUMNS:
        faltan = [c for c in POLYADB_COLUMNS if c not in columnas]
        sobran = [c for c in columnas if c not in POLYADB_COLUMNS]
        raise ShmirDesignError(
            f"{source}: las columnas no son las esperadas. "
            f"Faltan: {', '.join(faltan) or 'ninguna'}. "
            f"Sobran: {', '.join(sobran) or 'ninguna'}.\n\n{POLYADB_FORMAT}"
        )

    sitios: list[MeasuredSite] = []
    anclas: list[PasAnchor] = []
    for numero, linea in enumerate(filas[1:], start=2):
        campos = linea.split("\t")
        if len(campos) != len(POLYADB_COLUMNS):
            raise ShmirDesignError(
                f"{source}, fila {numero}: {len(campos)} campo(s) y se esperaban "
                f"{len(POLYADB_COLUMNS)}. Se aborta: una fila corrida mete el valor de "
                f"una columna en la de al lado y eso no da ningún error."
            )
        pas_id, coordenada, clase, pse, rpm, distal, nota = (c.strip() for c in campos)
        try:
            genomica = int(coordenada)
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source}, fila {numero}: la coordenada {coordenada!r} no es un entero."
            ) from exc
        con_expresion = bool(pse) and bool(rpm)
        if bool(pse) != bool(rpm):
            raise ShmirDesignError(
                f"{source}, fila {numero}: {pas_id} trae PSE o AvgRPM pero no los dos. "
                f"Los dos juntos o ninguno: la fracción ponderada necesita ambos, y una "
                f"a medias daria un número que no se refiere a nada."
            )
        if con_expresion:
            sitios.append(MeasuredSite(
                pas_id, clase,
                _fraccion(pse, campo="pse", source=source, fila=numero),
                float(rpm),
                distal=distal.lower() in ("si", "sí", "s", "true", "1"),
                note=nota,
            ))
        anclas.append(PasAnchor(
            pas_id, genomica, clase, expression=con_expresion, note=nota,
            pse=_fraccion(pse, campo="pse", source=source, fila=numero)
            if con_expresion else None,
            avgrpm=float(rpm) if con_expresion else None,
        ))

    if not sitios:
        raise ShmirDesignError(
            f"{source}: ningún PAS trae expresión, así que no hay fracción que calcular. "
            f"Se aborta: cero sitios con expresión y «no se midio» son cosas distintas."
        )
    reservas = tuple(
        r for r in cabecera.get("_reservas", "").split("\n") if r.strip()
    )
    return MeasuredFraction(
        source=cabecera["fuente"],
        version=cabecera["version"],
        date=cabecera.get("fecha", ""),
        assembly=cabecera["ensamblaje"],
        gene=cabecera["gen"],
        gene_id=cabecera.get("gen_id", ""),
        representative=cabecera.get("representante", ""),
        total_pas=int(cabecera.get("pas_totales") or len(anclas)),
        with_expression=int(cabecera.get("pas_con_expresion") or len(sitios)),
        utr3_md5=cabecera["utr3_md5"],
        sites=tuple(sitios),
        anchors=tuple(anclas),
        tissue=cabecera["tejido"],
        pending=(),
        caveats=reservas,
    )


def load_polyadb(path: Path | str, *, expected_md5: str | None = None) -> MeasuredFraction:
    """Carga la tabla desde disco, comprobando el md5 si se declara."""
    path = Path(path)
    try:
        bruto = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer la tabla de PolyA_DB {path} ({exc}); el frente del APA se "
            f"quedaria en predicción y eso hay que decirlo, no suponerlo."
        ) from exc
    md5 = hashlib.md5(bruto, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de sustituir ninguna predicción por el."
        )
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(f"{path}: no es UTF-8 ({exc}); se aborta.") from exc
    return parse_polyadb(texto, source=str(path))


def find_polyadb(*, directory=None, species: str = "") -> MeasuredFraction | None:
    """Busca la tabla en el directorio de referencia y la carga. `None` si no esta.

    `None` significa NO HAY FICHERO, y el frente queda NOT_RUN. Es distinto de que la
    tabla exista y no hable de esta secuencia —eso lo decide `resolve_measured` por
    md5— y las dos cosas se dicen distinto en el informe.

    Sin especie se prueban todos los nombres que haya: la tabla se aplica por md5 de
    todos modos, asi que una de otra especie no puede colarse.
    """
    from . import reference as _ref  # noqa: PLC0415

    directorios = [Path(directory)] if directory is not None else list(
        _ref.reference_dirs(None)
    )
    # LA ESPECIE SE RESUELVE, no se usa tal cual. `tile_utr` la recibe como venga —y en
    # este proyecto «raton» es un ALIAS, no el slug—, asi que formatear el nombre con lo
    # que llegue da `polya_db_raton.tsv`, que no existe. Lo cazo el golden: la tabla
    # dejo de encontrarse y el informe volvio a las cifras de antes de la promocion.
    slugs = _slugs_de(species) if species else _known_slugs()
    for carpeta in directorios:
        for slug in slugs:
            ruta = Path(carpeta) / POLYADB_FILENAME.format(slug=slug)
            if ruta.is_file() and ruta.stat().st_size:
                return load_polyadb(ruta)
    return None


def _slugs_de(species: str) -> list[str]:
    """El slug de esa especie. Una que no este declarada NO aborta aqui: se prueban
    todos, y el md5 del 3'UTR es quien decide — una tabla de otra especie no puede
    colarse por tener el nombre parecido."""
    from .errors import ShmirDesignError as _Error  # noqa: PLC0415
    from .species import resolve  # noqa: PLC0415

    try:
        return [resolve(species).slug]
    except _Error:
        # rule2-ok: una especie sin declarar no es un fallo AQUI. Buscar el fichero es
        # barato y aplicarlo lo decide el md5; abortar dejaria sin tabla a quien esta
        # trabajando con una especie que todavia no ha declarado.
        return _known_slugs()


def _known_slugs() -> list[str]:
    from .species import SPECIES  # noqa: PLC0415

    return sorted(SPECIES)


#: LA TABLA MURINA YA NO ESTA AQUI. DECIDIDO 2026-08-27.
#:
#: Estuvo cableada en `POLYA_DB_PRNP` —15 PAS con su PSE y su AvgRPM llegados por
#: conversacion— y de ella colgaban el techo por tramos, la promocion del `AATATA` de
#: `3utr:236` y el panel de diez. Ahora es `data/reference/polya_db_mouse.tsv`, con su
#: linea en el manifiesto y su md5, y se carga con `find_polyadb`.
#:
#: La constante se quito ENTERA en vez de dejarla «por si acaso»: mientras las dos
#: existieran habria dos definiciones del mismo dato sin nada que obligara a que
#: coincidieran, y ya habian empezado a separarse — las notas de los anclajes decian
#: «PSE 21,1 %» en la constante y la lectura del racimo en el fichero. Es el quinto par
#: duplicado del proyecto, y el unico cuya copia de codigo se podia borrar entera
#: porque la otra mitad es DATO y su sitio es el gestor.
#:
#: Quien la necesitaba en un test carga el fichero: `apa.find_polyadb(species=…)`.
WHERE_THE_MOUSE_TABLE_LIVES = (
    "La tabla de PolyA_DB murina vive en `data/reference/polya_db_mouse.tsv`, no en el "
    "código: entra por el gestor como cualquier otro fichero, con su md5 en el "
    "manifiesto. Se carga con `apa.find_polyadb`."
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
            f"La posición {start} cae fuera de los tramos de techo "
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
                "  de un candidato no es cuanta isoforma larga hay, es que fracción de "
                "transcritos conserva",
                "  SU diana — y eso depende de por detrás de cuántos cortes esta.",
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
            "Ningún sitio PROXIMAL medido quedo anclado sin ambigüedad, así que no hay "
            "con que construir los tramos de techo. Se aborta en vez de emitir un techo "
            "único que no se sabe de donde sale."
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
                    + ": no se sabe de que lado cae, así que el techo es INDETERMINADO "
                      "(PENALIZADO, no TECHO)"
                ),
            ))
            continue
        if not detras:
            capas.append(CeilingLayer(
                start_range=(inicio, fin), ceiling=None, lost=(), in_band=False,
                frame=frame,
                reason="por delante de todos los cortes medidos: la diana está en TODAS "
                       "las isoformas. INMUNE.",
            ))
            continue
        conservado = total - sum(s.weighted for s in perdidos)
        capas.append(CeilingLayer(
            start_range=(inicio, fin), ceiling=conservado / total, lost=perdidos,
            in_band=False, frame=frame,
            reason="por detrás de " + ", ".join(s.locus for s in detras),
        ))
    return tuple(capas)


#: LA MEDIDA ENTRA SIEMPRE QUE HAYA MEDIDA. DECIDIDO (2026-08-27) por el responsable
#: del proyecto, y el motivo es que son DOS VEREDICTOS y no dos ordenaciones:
#:
#:   - sin la medida, `3utr:221` lleva una PENALIZACION de -1,00 por solapar un hexamero
#:     variante — sigue en el panel, solo que peor colocada;
#:   - con la medida, el `AATATA` de `3utr:236` es `APA_POSIBLE` y `3utr:221` es FAIL
#:     duro por solape esterico.
#:
#: Y el dato existe: PSE 21,1 %, AvgRPM 0,55, el proximal MAS usado de los tres. El modo
#: sin medida trata ese hexamero como no funcional, que es la hipotesis MENOS
#: conservadora y ademas la falsa segun lo medido: el defecto favorecia al candidato
#: equivocado POR OMISION.
#:
#: Mismo criterio que el `.out` de RepeatMasker y que la casilla global que se quito: si
#: el dato esta en el deposito y es valido, se usa. Que un veredicto dependa de
#: acordarse de una bandera es la trampa que este proyecto ya cerro una vez.
WHY_MEASURE_IS_NOT_A_FLAG = (
    "La promoción por medida se aplica siempre que la tabla hable de esta secuencia. No "
    "es una preferencia de ordenación: sin ella una señal medida se trata como no "
    "funcional, que es la hipótesis menos conservadora y la falsa según el dato. "
    "Excluirla es posible, pero con motivo escrito (`ApaExcluded`), y el motivo viaja al "
    "veredicto: sin él, «se decidió no usarla» y «nadie se acordó» son el mismo "
    "resultado mudo."
)


@dataclass(frozen=True)
class ApaExcluded:
    """Excluir la tabla medida A PROPOSITO, con el motivo escrito.

    Es la unica forma de que la promocion no entre. `measured_apa=None` ya no vale y
    aborta: `None` era exactamente el salto silencioso, y es lo que hacia que el panel
    dependiera de que el llamador se acordara.
    """

    reason: str

    def __post_init__(self) -> None:
        if not str(self.reason).strip():
            raise ShmirDesignError(
                "Excluir la tabla de APA medido necesita un MOTIVO escrito. Sin él, "
                "«se decidió no usarla» y «nadie se acordó» dan el mismo NOT_RUN mudo, "
                "que es justo lo que la casilla global de ficheros dejó de permitir."
            )


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
            f"refiere, así que no hay forma de comprobar que habla de esta secuencia; "
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
            f"CABO SUELTO — NO RESUELTO: {self.locus}. Es el PAS con MÁS expresión de "
            f"los tres (PSE 70,5 %,",
            "  AvgRPM 1,65) y es el NUMERADOR de la fracción larga, así que de su "
            "lectura depende lo que",
            "  significa el 0.86. Hay DOS, con consecuencias distintas:",
            f"    (a) es el racimo del PAS terminal {self.terminal_locus} → los dos son "
            f"el mismo sitio de corte",
            "        y la fracción larga 0.86 es exactamente lo que dice ser.",
            f"    (b) es un corte PROPIO en {banda} → hay un TERCER corte por delante "
            f"del terminal, y todo",
            "        lo que quede detrás lleva un techo adicional. Peor: por detrás de "
            "esa banda ya no queda",
            "        ningún PAS CON EXPRESIÓN MEDIDA, así que ahi la medida no acota "
            "nada — no es un techo",
            "        bajo, es un techo del que esta tabla no sabe nada.",
            "  El anclaje de cuatro puntos ESTRECHA la banda a "
            f"{banda} (antes se estimaba más ancha) pero NO",
            "  desempata: los dos hexámeros de su clase que caben ahi son "
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
            "      ni detrás ni delante. Ya fallaba nuestro propio filtro duro de "
            "polyA, así que no cambia nada hoy.",
            "    · CERO ventanas elegibles por detrás de la banda, y cero dentro. "
            "Ninguno de los diez está ahi.",
            "  POR QUE EL FRENTE SIGUE CERRADO IGUAL, y no por conveniencia: bajo las "
            "DOS lecturas el techo",
            "  del panel es >= 0.86. Bajo (a) es 0.86 exacto; bajo (b) los diez siguen "
            "por delante de la banda,",
            "  así que conservan su diana en la isoforma de este corte Y en la "
            "terminal, cuya expresión no",
            "  está medida — o sea 0.86 MÁS lo que no se ha contado. La ambigüedad no "
            "mueve el número DEL PANEL;",
            "  moveria el de cualquier candidato que se pusiera por detrás de "
            f"{banda}, y hoy no hay ninguno.",
            "  QUE LO RESOLVERIA: 3'-end seq de cerebro murino, o la regla de "
            "agrupamiento que use la propia",
            "  base para decidir si estos dos PAS son un racimo. Ninguna de las dos "
            "está aquí.",
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
