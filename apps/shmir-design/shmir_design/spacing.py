"""Cuando dos candidatos son EL MISMO SITIO del panel.

221 y 223 son dos ventanas corridas 2 nt. Bajo la regla de espaciado del proyecto son el
mismo sitio, aunque las guias sean distintas y una fuente externa las liste como dos
entradas. Presentar la segunda como un candidato nuevo cuenta dos veces la misma plaza.

El aviso NO descarta nada: puede interesar cambiar una por otra, y para eso hay que ver
que compiten y con que numeros. Descartarla en silencio quitaria esa decision.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .coords import Frame, label
from .selection import DEFAULT_MIN_SPACING

#: El espaciado minimo entre posiciones de inicio, el mismo que usa la seleccion.
SITE_SPACING = DEFAULT_MIN_SPACING


def same_site(a: int, b: int, *, spacing: int = SITE_SPACING) -> bool:
    """¿Dos posiciones de inicio caen dentro del mismo sitio?

    `spacing` es el MINIMO exigido entre dos elegidos, asi que a exactamente esa
    distancia todavia no se cumple.
    """
    return abs(a - b) <= spacing


@dataclass(frozen=True)
class ReferenceSet:
    """Contra QUE se mide si una plaza es nueva. La etiqueta es obligatoria.

    Sin ella, «4 plazas nuevas» no es un resultado: el mismo cruce da 7 plazas contra
    los 6 candidatos elegidos y ninguna contra los 90 sitios elegibles, porque seis
    posiciones no cubren 1242 nt. La cifra sin la referencia es una cifra suelta, igual
    que una longitud sin su md5.
    """

    label: str
    starts: dict[int, str]
    frame: Frame

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValueError(
                "Un conjunto de referencia necesita etiqueta: la cuenta de plazas "
                "nuevas depende de contra que se mida, y sin decirlo el numero no "
                "significa nada. Se aborta."
            )
        if not isinstance(self.frame, Frame):
            raise ValueError(
                f"Espacio de coordenadas {self.frame!r} desconocido en el conjunto de "
                f"referencia {self.label!r}; se aborta."
            )

    @property
    def size(self) -> int:
        return len(self.starts)


@dataclass(frozen=True)
class SiteConflict:
    candidate_start: int
    candidate_guide: str
    reference_start: int
    reference_guide: str
    distance: int
    reference_label: str
    frame: Frame = Frame.UTR3

    @property
    def message(self) -> str:
        return (
            f"El candidato de {label(self.candidate_start, self.frame)} esta a "
            f"{self.distance} nt del de {label(self.reference_start, self.frame)}, que "
            f"ya esta en {self.reference_label}: bajo el espaciado del proyecto son EL "
            f"MISMO SITIO, asi que no es una plaza nueva del panel.\n"
            f"    nuevo       {label(self.candidate_start, self.frame):>10}  "
            f"{self.candidate_guide}\n"
            f"    referencia  {label(self.reference_start, self.frame):>10}  "
            f"{self.reference_guide}\n"
            f"    No se descarta: puede interesar cambiar uno por otro. Lo que no se "
            f"puede es contarlos como dos."
        )


@dataclass(frozen=True)
class SiteComparison:
    """El resultado, con la referencia DENTRO. No se puede leer sin ella."""

    reference: ReferenceSet
    conflicts: tuple[SiteConflict, ...]
    new_plazas: tuple[int, ...]
    identical: tuple[int, ...]
    spacing: int
    candidates: int
    #: Plaza nueva -> otros candidatos externos que caen en ELLA. Dos externos a menos
    #: del espaciado son una plaza, no dos.
    merged: dict[int, tuple[int, ...]] = None

    def describe(self) -> str:
        lineas = [
            f"Espaciado de sitios ({self.spacing} nt) de {self.candidates} candidato(s) "
            f"externo(s) CONTRA {self.reference.label} ({self.reference.size} "
            f"posicion(es)).",
            "  La cifra de plazas nuevas depende de esta referencia y solo de ella: "
            "contra un",
            "  subconjunto seleccionado casi todo parece nuevo. Cambiar la referencia "
            "cambia el numero.",
        ]
        if self.identical:
            lineas.append(
                "  IDENTICAS a una ventana de la referencia (misma posicion de inicio): "
                + ", ".join(label(p, self.reference.frame) for p in self.identical)
            )
        lineas.append(
            f"  plazas NUEVAS: "
            + (
                ", ".join(label(p, self.reference.frame) for p in self.new_plazas)
                if self.new_plazas
                else "ninguna"
            )
        )
        for plaza, otras in (self.merged or {}).items():
            lineas.append(
                f"  {label(plaza, self.reference.frame)} absorbe a "
                + ", ".join(label(p, self.reference.frame) for p in otras)
                + f": entre ellas tambien hay menos de {self.spacing} nt, asi que son "
                f"UNA plaza."
            )
        lineas.extend(f"  · {c.message}" for c in self.conflicts)
        return "\n".join(lineas)


def compare_sites(
    *,
    candidates: dict[int, str],
    reference: ReferenceSet,
    spacing: int = SITE_SPACING,
) -> SiteComparison:
    """Que candidatos externos son plaza nueva CONTRA `reference`, y cuales no.

    `reference` es obligatoria y lleva su etiqueta: es el conjunto completo de
    candidatos, no el subconjunto que la seleccion haya elegido. Medir contra los
    elegidos infla la cuenta de plazas nuevas — es lo que hizo salir «7 plazas» donde
    contra la tabla completa no queda ninguna.
    """
    conflictos = tuple(
        SiteConflict(
            candidate_start=inicio,
            candidate_guide=guia,
            reference_start=otro,
            reference_guide=reference.starts[otro],
            distance=abs(inicio - otro),
            reference_label=reference.label,
            frame=reference.frame,
        )
        for inicio, guia in sorted(candidates.items())
        for otro in sorted(reference.starts)
        if inicio != otro and same_site(inicio, otro, spacing=spacing)
    )
    con_conflicto = {c.candidate_start for c in conflictos}
    identicas = tuple(p for p in sorted(candidates) if p in reference.starts)
    sobreviven = [
        p for p in sorted(candidates)
        if p not in con_conflicto and p not in reference.starts
    ]
    # Y los supervivientes se agrupan ENTRE ELLOS: dos candidatos externos a menos del
    # espaciado son una plaza nueva, no dos. Contarlos por separado es el mismo error de
    # doble cuenta, un nivel mas abajo.
    nuevas: list[int] = []
    agrupadas: dict[int, tuple[int, ...]] = {}
    for inicio in sobreviven:
        if nuevas and same_site(nuevas[-1], inicio, spacing=spacing):
            agrupadas[nuevas[-1]] = agrupadas.get(nuevas[-1], ()) + (inicio,)
            continue
        nuevas.append(inicio)
    return SiteComparison(
        reference=reference,
        conflicts=conflictos,
        new_plazas=tuple(nuevas),
        identical=identicas,
        spacing=spacing,
        candidates=len(candidates),
        merged=agrupadas,
    )


def site_conflicts(
    *,
    candidates: dict[int, str],
    reference: ReferenceSet,
    spacing: int = SITE_SPACING,
) -> tuple[SiteConflict, ...]:
    """Solo los choques. `compare_sites` da ademas las plazas nuevas y la referencia."""
    return compare_sites(
        candidates=candidates, reference=reference, spacing=spacing
    ).conflicts
