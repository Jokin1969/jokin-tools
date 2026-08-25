"""Filtros duros sobre ventanas de 22 nt (pasos 4-8 del pipeline).

Umbrales verificados por el responsable del proyecto: GC 0.30-0.52, homopolimero
maximo 3, asimetria >= +0.5 kcal/mol, sin motivo G-cuadruplex, U forzada en la
posicion 1 de la guia.

La asimetria se calcula sobre la GUIA ya transformada, con el proxy de `thermo.py`
(Turner 2004, ARN, 37 C; ver alli la advertencia de que es un proxy heuristico y no una
energia libre de duplex). Pasando `asymmetry_model=None` el filtro queda en NOT_RUN, que
no es PASS: entonces ninguna ventana puede declararse apta (regla 3).

El motivo G-cuadruplex se comprueba sobre la diana Y sobre la guia: una diana con tramos
de C produce una guia con tramos de G, y esa guia es la molecula que se sintetiza.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .filters import FilterResult, FilterState, Verdict, overall_verdict
from .polya import normalize_sequence
from .thermo import turner_asymmetry

WINDOW_SIZE = 22
GC_MIN = 0.30
GC_MAX = 0.52
MAX_HOMOPOLYMER = 3
MIN_ASYMMETRY = 0.5  # kcal/mol

#: Motivo G-cuadruplex canonico: cuatro tramos de >=3 G separados por 1-7 nt.
G4_PATTERN = re.compile(r"G{3,}[ACGUTN]{1,7}G{3,}[ACGUTN]{1,7}G{3,}[ACGUTN]{1,7}G{3,}")
HOMOPOLYMER_PATTERN = re.compile(r"(.)\1{" + str(MAX_HOMOPOLYMER) + r",}")

COMPLEMENT = str.maketrans("ACGTN", "UGCAN")

#: Un modelo de asimetria recibe la ventana diana y devuelve kcal/mol.
AsymmetryModel = Callable[[str], float]


def gc_fraction(sequence: str) -> float:
    cleaned = normalize_sequence(sequence)
    return (cleaned.count("G") + cleaned.count("C")) / len(cleaned)


def reverse_complement_rna(sequence: str) -> str:
    """Complementario inverso en notacion ARN (A→U)."""
    return normalize_sequence(sequence).translate(COMPLEMENT)[::-1]


def guide_from_target(sequence: str) -> str:
    """Guia de la diana, con U forzada en la posicion 1 (paso 6, transformacion)."""
    guide = reverse_complement_rna(sequence)
    return "U" + guide[1:]


def filter_gc(sequence: str) -> FilterResult:
    value = gc_fraction(sequence)
    if GC_MIN <= value <= GC_MAX:
        return FilterResult(
            name="GC",
            state=FilterState.PASS,
            reason=f"GC {value:.3f} dentro de [{GC_MIN:.2f}, {GC_MAX:.2f}].",
        )
    lado = "por debajo del minimo" if value < GC_MIN else "por encima del maximo"
    return FilterResult(
        name="GC",
        state=FilterState.FAIL,
        reason=f"GC {value:.3f} {lado} [{GC_MIN:.2f}, {GC_MAX:.2f}].",
    )


def filter_homopolymer(sequence: str) -> FilterResult:
    cleaned = normalize_sequence(sequence)
    match = HOMOPOLYMER_PATTERN.search(cleaned)
    if match is None:
        return FilterResult(
            name="homopolimero",
            state=FilterState.PASS,
            reason=f"Sin tramos de mas de {MAX_HOMOPOLYMER} nt iguales seguidos.",
        )
    return FilterResult(
        name="homopolimero",
        state=FilterState.FAIL,
        reason=(
            f"Homopolimero {match.group(0)} ({len(match.group(0))} nt) en la posicion "
            f"{match.start() + 1}; el maximo es {MAX_HOMOPOLYMER}."
        ),
    )


def filter_g4(sequence: str, *, name: str = "G4_diana") -> FilterResult:
    """Motivo G-cuadruplex. Vale para la diana (ADN) y para la guia (ARN)."""
    cleaned = "".join(str(sequence).split()).upper()
    match = G4_PATTERN.search(cleaned)
    if match is None:
        return FilterResult(
            name=name,
            state=FilterState.PASS,
            reason="Sin motivo G-cuadruplex (4 tramos de >=3 G separados por 1-7 nt).",
        )
    return FilterResult(
        name=name,
        state=FilterState.FAIL,
        reason=(
            f"Motivo G-cuadruplex {match.group(0)} en la posicion {match.start() + 1}."
        ),
    )


def filter_asymmetry(
    guide: str,
    model: AsymmetryModel | None = turner_asymmetry,
) -> FilterResult:
    """Asimetria de la GUIA (no de la diana). `model=None` deja el filtro en NOT_RUN."""
    if model is None:
        return FilterResult(
            name="asimetria",
            state=FilterState.NOT_RUN,
            reason=(
                "No se paso ningun modelo de asimetria, asi que el filtro no se "
                f"ejecuta. Umbral sin aplicar: >= {MIN_ASYMMETRY} kcal/mol. "
                "NOT_RUN no es PASS."
            ),
        )

    value = model(guide)
    estado = FilterState.PASS if value >= MIN_ASYMMETRY else FilterState.FAIL
    comparacion = ">=" if estado is FilterState.PASS else "por debajo de"
    return FilterResult(
        name="asimetria",
        state=estado,
        reason=(
            f"Asimetria {value:+.2f} kcal/mol {comparacion} {MIN_ASYMMETRY}, "
            f"sobre la guia {guide} (proxy heuristico, ver thermo.py)."
        ),
    )


@dataclass(frozen=True)
class WindowEvaluation:
    sequence: str
    guide: str
    filters: tuple[FilterResult, ...]
    offset: int = 0
    #: Valor de la asimetria en kcal/mol, o None si el filtro no llego a correr.
    #: La seleccion ordena por este numero, no por el texto del motivo.
    asymmetry: float | None = None

    @property
    def verdict(self) -> Verdict:
        return overall_verdict(list(self.filters))

    @property
    def failures(self) -> tuple[FilterResult, ...]:
        return tuple(r for r in self.filters if r.state is FilterState.FAIL)

    def format_text(self, indent: str = "") -> str:
        lines = [
            f"{indent}offset {self.offset}: {self.sequence}  "
            f"veredicto={self.verdict.value}",
            f"{indent}  guia (5'→3', U forzada en 1): {self.guide}",
        ]
        lines.extend(
            f"{indent}  {r.name:<13} {r.state.value:<7} {r.reason}" for r in self.filters
        )
        return "\n".join(lines)


def evaluate_window(
    sequence: str,
    *,
    asymmetry_model: AsymmetryModel | None = turner_asymmetry,
    offset: int = 0,
) -> WindowEvaluation:
    """Aplica los filtros duros a una ventana de 22 nt y devuelve todos los motivos."""
    cleaned = normalize_sequence(sequence)
    if len(cleaned) != WINDOW_SIZE:
        raise ValueError(
            f"La ventana mide {len(cleaned)} nt y los filtros estan definidos sobre "
            f"{WINDOW_SIZE} nt; se aborta la evaluacion en vez de aplicar umbrales "
            f"que no le corresponden."
        )
    desconocida = cleaned.find("N")
    if desconocida != -1:
        motivo = (
            f"La ventana tiene una base desconocida (N) en la posicion "
            f"{desconocida + 1}: no es evaluable. NOT_RUN no es PASS."
        )
        return WindowEvaluation(
            sequence=cleaned,
            guide=guide_from_target(cleaned),
            filters=tuple(
                FilterResult(name=name, state=FilterState.NOT_RUN, reason=motivo)
                for name in ("GC", "homopolimero", "G4_diana", "G4_guia", "asimetria")
            ),
            offset=offset,
        )

    guide = guide_from_target(cleaned)
    return WindowEvaluation(
        sequence=cleaned,
        guide=guide,
        filters=(
            filter_gc(cleaned),
            filter_homopolymer(cleaned),
            filter_g4(cleaned, name="G4_diana"),
            filter_g4(guide, name="G4_guia"),
            filter_asymmetry(guide, asymmetry_model),
        ),
        offset=offset,
        asymmetry=None if asymmetry_model is None else asymmetry_model(guide),
    )
