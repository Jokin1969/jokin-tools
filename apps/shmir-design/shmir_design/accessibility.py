"""Accesibilidad de la diana (bloque 4, paso 13).

**Es el peor predicho de todos los criterios de este pipeline, y por eso va de
DESEMPATE, nunca de filtro.** No descarta a nadie: produce un numero que se guarda para
poder correlacionarlo despues contra el knockdown medido. Si resulta que no predice
nada, se sabra; si predice, tambien. Ese es el motivo de llevar diez candidatos a
sintesis y no dos.

Que se calcula: se pliega localmente una ventana de contexto alrededor de la diana y se
mira que fraccion de las 22 bases queda sin aparear, con desglose de las posiciones que
emparejan con la seed de la guia — que son las 15-21 de la diana, las mismas que en
`polya.py`.

**La eleccion de la ventana de contexto importa** y no hay un valor obviamente correcto,
asi que se calculan dos (±80 y ±150 nt) y las dos salen en el informe. Si discrepan, el
numero no es de fiar y el informe lo dice: es el mismo patron que el barrido de la
penalizacion.

ViennaRNA es una dependencia OPCIONAL. Sin ella esto es NOT_RUN, que **no es cero**: no
haber podido plegar no es lo mismo que una diana inaccesible.

Python 3.11+ (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .filters import FilterState
from .folding import VIENNA_AVAILABLE, dot_bracket

#: Los dos flancos que se prueban. El primero es el que va a la columna de la tabla.
CONTEXT_WINDOWS = (80, 150)

#: Posiciones de la diana que emparejan con la seed de la guia (las 2-8). Mismo calculo
#: que en `polya.py`: la guia es el complemento inverso.
SEED_TARGET_START = 15
SEED_TARGET_END = 21

#: A partir de aqui las dos ventanas se consideran discrepantes.
DISCREPANCY = 0.20


def context_slice(
    sequence: str, *, start: int, length: int, flank: int
) -> tuple[str, int]:
    """Tramo de contexto y desplazamiento de la diana dentro de el.

    Cerca de los extremos el contexto se recorta —no se rellena con nada (regla 1)— y
    el desplazamiento devuelto dice donde ha quedado la diana.
    """
    if start < 1 or start + length - 1 > len(sequence):
        raise ValueError(
            f"La diana {start}-{start + length - 1} no cabe en una secuencia de "
            f"{len(sequence)} nt; se aborta en vez de plegar un tramo recortado que ya "
            f"no contiene la diana entera."
        )
    desde = max(0, start - 1 - flank)
    hasta = min(len(sequence), start - 1 + length + flank)
    return sequence[desde:hasta], start - 1 - desde


@dataclass(frozen=True)
class Accessibility:
    """Numero comparativo, nunca veredicto."""

    state: FilterState
    unpaired_fraction: dict[int, float] = field(default_factory=dict)
    seed_unpaired_fraction: dict[int, float] = field(default_factory=dict)
    structure: dict[int, str] = field(default_factory=dict)
    energy: dict[int, float] = field(default_factory=dict)
    reason: str = ""

    @property
    def discrepant(self) -> bool:
        """¿Las dos ventanas de contexto dan respuestas distintas?"""
        if len(self.unpaired_fraction) < 2:
            return False
        valores = list(self.unpaired_fraction.values())
        return max(valores) - min(valores) >= DISCREPANCY

    def as_column(self) -> str:
        if not self.unpaired_fraction:
            return ""
        return f"{self.unpaired_fraction[CONTEXT_WINDOWS[0]]:.2f}"

    def format_text(self) -> str:
        if not self.unpaired_fraction:
            return f"Accesibilidad — NOT_RUN\n  {self.reason}"
        lines = ["Accesibilidad de la diana:"]
        for flanco in CONTEXT_WINDOWS:
            lines.append(
                f"  ventana ±{flanco} nt: {self.unpaired_fraction[flanco]:.2f} sin "
                f"aparear ({self.seed_unpaired_fraction[flanco]:.2f} en la seed), "
                f"ΔG {self.energy[flanco]:+.2f} kcal/mol"
            )
            lines.append(f"    {self.structure[flanco]}")
        if self.discrepant:
            lines.append(
                "  Las dos ventanas de contexto NO coinciden: el número depende de "
                "donde se corte el contexto, así que no es de fiar para desempatar."
            )
        else:
            lines.append(
                "  Las dos ventanas de contexto coinciden, así que el número no depende "
                "de donde se corte."
            )
        lines.append(
            "  Criterio de DESEMPATE, nunca filtro: es el peor predicho del pipeline y "
            "no descarta a nadie."
        )
        return "\n".join(lines)


def accessibility_of(
    sequence: str,
    *,
    start: int,
    length: int,
    available: bool | None = None,
) -> Accessibility:
    """Fraccion sin aparear de la diana, bajo las dos ventanas de contexto."""
    usable = VIENNA_AVAILABLE if available is None else available
    if not usable:
        return Accessibility(
            state=FilterState.NOT_RUN,
            reason=(
                "ViennaRNA no está instalado, así que la accesibilidad no se ha "
                "calculado. NOT_RUN no es cero: no haber podido plegar no es lo mismo "
                "que una diana inaccesible. `pip install ViennaRNA` si quieres este "
                "numero."
            ),
        )

    sin_aparear: dict[int, float] = {}
    seed: dict[int, float] = {}
    estructuras: dict[int, str] = {}
    energias: dict[int, float] = {}

    for flanco in CONTEXT_WINDOWS:
        tramo, offset = context_slice(
            sequence, start=start, length=length, flank=flanco
        )
        estructura, dg = dot_bracket(tramo)
        diana = estructura[offset : offset + length]
        sin_aparear[flanco] = diana.count(".") / length
        seed_tramo = diana[SEED_TARGET_START - 1 : SEED_TARGET_END]
        seed[flanco] = (
            seed_tramo.count(".") / len(seed_tramo) if seed_tramo else 0.0
        )
        estructuras[flanco] = diana
        energias[flanco] = dg

    return Accessibility(
        state=FilterState.PASS,
        unpaired_fraction=sin_aparear,
        seed_unpaired_fraction=seed,
        structure=estructuras,
        energy=energias,
        reason=(
            f"{sin_aparear[CONTEXT_WINDOWS[0]]:.2f} de las {length} bases sin aparear "
            f"con contexto ±{CONTEXT_WINDOWS[0]} nt. Número de desempate, no veredicto."
        ),
    )
