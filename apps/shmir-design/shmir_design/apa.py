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
from pathlib import Path

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


# ─── La fraccion de isoforma larga, MEDIDA ───────────────────────────────────
#
# Aportada el 2026-08-26 desde PolyA_DB v4.1. Es lo que convierte el TECHO de
# «indeterminado» en un numero — pero solo cuando la conversion de coordenadas este
# hecha, y esa NO se puede hacer con lo que hay en este repositorio.


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
    pending: tuple[str, ...]
    tissue: str

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
                "  PENDIENTE ANTES DE USARLO. El dato NO entra al pipeline todavia:",
            ]
        )
        lineas.extend(f"    {i}. {p}" for i, p in enumerate(self.pending, start=1))
        return lineas


#: La conversion no se puede hacer aqui, y el motivo es concreto: el `.gb` de
#: NM_011170.3 no trae coordenadas genomicas — su bloque PRIMARY referencia cDNA y EST
#: (CK622972.1, AK148061.1, AK158908.1, AV361844.1), no un cromosoma.
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
    sites=(
        MeasuredSite("chr2:+:131937444", "Other", 0.211, 0.55, distal=False,
                     note="segundo PAS proximal, NO estaba en nuestro modelo"),
        MeasuredSite("chr2:+:131937504", "AAUAAA", 0.235, 0.34, distal=False,
                     note="candidato a ser nuestro AATAAA proximal"),
        MeasuredSite("chr2:+:131938392", "Other", 0.705, 1.65, distal=True,
                     note="racimo terminal"),
    ),
    tissue="TODOS LOS TEJIDOS, no cerebro",
    pending=(
        "La conversion genomico↔transcrito, contra la anotacion real. AQUI NO SE PUEDE "
        "HACER: el .gb de NM_011170.3 no trae coordenadas genomicas — su bloque PRIMARY "
        "referencia cDNA y EST, no un cromosoma. Hace falta la anotacion genomica del "
        "transcrito (exones sobre mm10) o el registro de NM_001278256.1 para ver si "
        "comparten 3'UTR. Con la aritmetica sola salen DOS mapeos y no se elige: si "
        "131937504 es el HEXAMERO, 131937444 cae en 3utr:228 y 131938392 en 3utr:1176; "
        "si es el SITIO DE CORTE (banda 303-323), 131937444 cae en 3utr:243-263 y "
        "131938392 en 3utr:1191-1211.",
        "El segundo PAS proximal 131937444, que no estaba en nuestro modelo. Bajo el "
        "primer mapeo cae en 3utr:228 y quedaria POR DELANTE del candidato 3utr:221 — "
        "que dejaria de ser inmune y pasaria a tener riesgo esterico por solapar el "
        "hexamero. Bajo el segundo mapeo cae detras y no le afecta. Los cuatro inmunes "
        "dependen de cual sea: 3utr:10, 60, 143 y 221.",
        "El PAS terminal 131938427 (fuerza 99,9 %, conservado en humano y rata) no "
        "tiene datos de expresion; el que los tiene es 131938392, 35 nt aguas arriba. "
        "Probablemente el mismo racimo, pero se anotan como DOS y no se fusionan sin "
        "comprobarlo: fusionarlos suma su expresion y sube la fraccion larga sin dato.",
    ),
)
