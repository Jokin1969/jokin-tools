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
class SiteConflict:
    candidate_start: int
    candidate_guide: str
    selected_start: int
    selected_guide: str
    distance: int

    @property
    def message(self) -> str:
        return (
            f"El candidato de {self.candidate_start} esta a {self.distance} nt del ya "
            f"seleccionado de {self.selected_start}: bajo el espaciado del proyecto son "
            f"EL MISMO SITIO, asi que no es una plaza nueva del panel.\n"
            f"    nuevo        {self.candidate_start:>5}  {self.candidate_guide}\n"
            f"    seleccionado {self.selected_start:>5}  {self.selected_guide}\n"
            f"    No se descarta: puede interesar cambiar uno por otro. Lo que no se "
            f"puede es contarlos como dos."
        )


def site_conflicts(
    *,
    candidates: dict[int, str],
    selected: dict[int, str],
    spacing: int = SITE_SPACING,
) -> tuple[SiteConflict, ...]:
    """Que candidatos caen dentro del espaciado de alguno ya seleccionado."""
    return tuple(
        SiteConflict(
            candidate_start=inicio,
            candidate_guide=guia,
            selected_start=elegido,
            selected_guide=selected[elegido],
            distance=abs(inicio - elegido),
        )
        for inicio, guia in sorted(candidates.items())
        for elegido in sorted(selected)
        if inicio != elegido and same_site(inicio, elegido, spacing=spacing)
    )
