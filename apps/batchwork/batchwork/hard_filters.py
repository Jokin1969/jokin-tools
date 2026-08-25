"""Filtros duros sobre ventanas de 22 nt (pasos 4-8 del pipeline).

Umbrales verificados por el responsable del proyecto: GC 0.30-0.52, homopolimero
maximo 3, asimetria >= +0.5 kcal/mol, sin motivo G-cuadruplex, U forzada en la
posicion 1 de la guia.

**La asimetria no esta implementada.** Falta la definicion verificada — que extremos se
comparan, cuantos pares de bases y con que tabla de parametros de vecino mas proximo —
y adivinarla produciria un numero plausible y falso, que es justo lo que este proyecto
no puede permitirse. Mientras falte, el filtro devuelve NOT_RUN, que no es PASS
(regla 3): ninguna ventana puede declararse apta. En cuanto llegue la definicion, se
pasa como `asymmetry_model` y el filtro corre.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .filters import FilterResult, FilterState, Verdict, overall_verdict
from .polya import normalize_sequence

WINDOW_SIZE = 22
GC_MIN = 0.30
GC_MAX = 0.52
MAX_HOMOPOLYMER = 3
MIN_ASYMMETRY = 0.5  # kcal/mol

#: Motivo G-cuadruplex canonico: cuatro tramos de >=3 G separados por 1-7 nt.
G4_PATTERN = re.compile(r"G{3,}[ACGTN]{1,7}G{3,}[ACGTN]{1,7}G{3,}[ACGTN]{1,7}G{3,}")
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


def filter_g4(sequence: str) -> FilterResult:
    cleaned = normalize_sequence(sequence)
    match = G4_PATTERN.search(cleaned)
    if match is None:
        return FilterResult(
            name="G4",
            state=FilterState.PASS,
            reason="Sin motivo G-cuadruplex (4 tramos de >=3 G separados por 1-7 nt).",
        )
    return FilterResult(
        name="G4",
        state=FilterState.FAIL,
        reason=(
            f"Motivo G-cuadruplex {match.group(0)} en la posicion {match.start() + 1}."
        ),
    )


def filter_asymmetry(
    sequence: str,
    model: AsymmetryModel | None = None,
) -> FilterResult:
    if model is None:
        return FilterResult(
            name="asimetria",
            state=FilterState.NOT_RUN,
            reason=(
                "No hay definicion verificada de la asimetria (que extremos, cuantos "
                "pares de bases, que tabla de vecino mas proximo), asi que el filtro "
                f"no se ejecuta. Umbral pendiente de aplicar: >= {MIN_ASYMMETRY} "
                "kcal/mol. NOT_RUN no es PASS."
            ),
        )

    value = model(normalize_sequence(sequence))
    if value >= MIN_ASYMMETRY:
        return FilterResult(
            name="asimetria",
            state=FilterState.PASS,
            reason=f"Asimetria {value:.2f} kcal/mol >= {MIN_ASYMMETRY}.",
        )
    return FilterResult(
        name="asimetria",
        state=FilterState.FAIL,
        reason=f"Asimetria {value:.2f} kcal/mol por debajo de {MIN_ASYMMETRY}.",
    )


@dataclass(frozen=True)
class WindowEvaluation:
    sequence: str
    guide: str
    filters: tuple[FilterResult, ...]
    offset: int = 0

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
    asymmetry_model: AsymmetryModel | None = None,
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
    return WindowEvaluation(
        sequence=cleaned,
        guide=guide_from_target(cleaned),
        filters=(
            filter_gc(cleaned),
            filter_homopolymer(cleaned),
            filter_g4(cleaned),
            filter_asymmetry(cleaned, asymmetry_model),
        ),
        offset=offset,
    )
