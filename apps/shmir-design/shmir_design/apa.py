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
