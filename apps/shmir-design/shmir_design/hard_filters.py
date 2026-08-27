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
from functools import lru_cache

from .filters import FilterResult, FilterState, Verdict, overall_verdict
from .polya import SIGNAL_FLANK, normalize_sequence
from .thermo import turner_asymmetry

WINDOW_SIZE = 22
GC_MIN = 0.30
GC_MAX = 0.52
MAX_HOMOPOLYMER = 3
MIN_ASYMMETRY = 0.5  # kcal/mol

#: Motivo G-cuadruplex canonico: cuatro tramos de >=3 G separados por 1-7 nt.

#: G4 SE RETIRÓ el 2026-08-27. Un regex de tres guaninas NO es un predictor de G-
#: cuadruplex: la estructura es real y sí bloquea el acceso de RISC, pero formarla depende
#: de ESTABILIDAD, no de coincidencia de motivo, y la mayoría de secuencias que casan el
#: patrón no forman nada. La pregunta que contestaba es legítima; el criterio con el que
#: la contestaba, no.
#:
#: La arqueología entera está en `docs/procedencia-g4.md` y la errata en `docs/erratas.md`
#: nº 9 — incluido el dato de que NUNCA excluyó a nadie (cero FAIL en 1221 ventanas de
#: ratón y 1585 de humano) y por qué eso es PEOR: un filtro que rechaza se audita solo,
#: uno que siempre aprueba no lo mira nadie.
#:
#: PARA VOLVER A ENTRAR hacen falta tres cosas por escrito: predictor con CITA, umbral con
#: JUSTIFICACIÓN en `justificacion.py`, y decisión explícita de si es filtro duro o
#: desempate. Voto de partida del responsable: desempate, nunca filtro.
G4_WITHDRAWN = (
    "El filtro G4 se retiró: un regex de tres guaninas no es un predictor de "
    "G-cuadruplex. Para volver hace falta predictor con cita, umbral justificado y "
    "decisión explícita de duro o desempate. Ver `docs/procedencia-g4.md`."
)


@lru_cache(maxsize=None)
def homopolymer_pattern(max_run: int) -> re.Pattern[str]:
    """Tramos de mas de `max_run` bases iguales seguidas."""
    return re.compile(r"(.)\1{" + str(max_run) + r",}")


HOMOPOLYMER_PATTERN = homopolymer_pattern(MAX_HOMOPOLYMER)


@dataclass(frozen=True)
class Thresholds:
    """Umbrales ajustables. Los valores por defecto son los verificados del proyecto.

    Estan aqui juntos para que una interfaz pueda ofrecerlos sin tocar la logica: los
    filtros son los mismos, solo cambia el numero contra el que comparan.
    """

    gc_min: float = GC_MIN
    gc_max: float = GC_MAX
    max_homopolymer: int = MAX_HOMOPOLYMER
    min_asymmetry: float = MIN_ASYMMETRY
    polya_flank: int = SIGNAL_FLANK

    def __post_init__(self) -> None:
        for nombre, valor in (("gc_min", self.gc_min), ("gc_max", self.gc_max)):
            if not 0.0 <= valor <= 1.0:
                raise ValueError(
                    f"{nombre}={valor}: el GC es una fracción entre 0 y 1; se aborta."
                )
        if self.gc_min > self.gc_max:
            raise ValueError(
                f"gc_min={self.gc_min} es mayor que gc_max={self.gc_max}: ninguna "
                f"ventana podría pasar; se aborta en vez de filtrarlo todo en silencio."
            )
        if self.max_homopolymer < 1:
            raise ValueError(
                f"max_homopolymer={self.max_homopolymer}: debe ser al menos 1; se aborta."
            )
        if self.polya_flank < 0:
            raise ValueError(
                f"polya_flank={self.polya_flank}: la zona prohibida no puede ser "
                f"negativa; se aborta."
            )


DEFAULT_THRESHOLDS = Thresholds()

COMPLEMENT = str.maketrans("ACGTN", "UGCAN")

#: Un modelo de asimetria recibe la ventana diana y devuelve kcal/mol.
AsymmetryModel = Callable[[str], float]


def longest_homopolymer(sequence: str) -> tuple[str, int]:
    """Base y longitud del tramo mas largo de bases iguales seguidas.

    Es la MISMA propiedad que mira `homopolymer_pattern`, expresada de otra forma:
    la regex responde "¿pasa del umbral?" y esto responde "¿de cuanto y de que base?",
    que es lo que hace falta para escribir el motivo del rechazo. Hay un test que exige
    que las dos coincidan para cualquier umbral; si alguien cambia una, salta.
    """
    peor, actual, base, ganadora = 0, 0, "", ""
    for i, letra in enumerate(sequence):
        actual = actual + 1 if i and letra == base else 1
        base = letra
        if actual > peor:
            peor, ganadora = actual, letra
    return ganadora, peor


def gc_fraction(sequence: str) -> float:
    cleaned = normalize_sequence(sequence)
    return (cleaned.count("G") + cleaned.count("C")) / len(cleaned)


def reverse_complement_rna(sequence: str) -> str:
    """Complementario inverso en notacion ARN (A→U)."""
    return normalize_sequence(sequence).translate(COMPLEMENT)[::-1]


def guide_from_target(sequence: str) -> str:
    """Guia de la diana, con U forzada en la posición 1 (paso 6, transformacion)."""
    guide = reverse_complement_rna(sequence)
    return "U" + guide[1:]


def filter_gc(sequence: str, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> FilterResult:
    value = gc_fraction(sequence)
    rango = f"[{thresholds.gc_min:.2f}, {thresholds.gc_max:.2f}]"
    if thresholds.gc_min <= value <= thresholds.gc_max:
        return FilterResult(
            name="GC",
            state=FilterState.PASS,
            reason=f"GC {value:.3f} dentro de {rango}.",
        )
    lado = (
        "por debajo del mínimo" if value < thresholds.gc_min else "por encima del máximo"
    )
    return FilterResult(
        name="GC",
        state=FilterState.FAIL,
        reason=f"GC {value:.3f} {lado} {rango}.",
    )


def filter_homopolymer(
    sequence: str, thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> FilterResult:
    cleaned = normalize_sequence(sequence)
    match = homopolymer_pattern(thresholds.max_homopolymer).search(cleaned)
    if match is None:
        return FilterResult(
            name="homopolimero",
            state=FilterState.PASS,
            reason=(
                f"Sin tramos de más de {thresholds.max_homopolymer} nt iguales seguidos."
            ),
        )
    return FilterResult(
        name="homopolimero",
        state=FilterState.FAIL,
        reason=(
            f"Homopolimero {match.group(0)} ({len(match.group(0))} nt) en la posición "
            f"{match.start() + 1}; el máximo es {thresholds.max_homopolymer}."
        ),
    )


def filter_asymmetry(
    guide: str,
    model: AsymmetryModel | None = turner_asymmetry,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> FilterResult:
    """Asimetria de la GUIA (no de la diana). `model=None` deja el filtro en NOT_RUN."""
    if model is None:
        return FilterResult(
            name="asimetria",
            state=FilterState.NOT_RUN,
            reason=(
                "No se paso ningún modelo de asimetría, así que el filtro no se "
                f"ejecuta. Umbral sin aplicar: >= {MIN_ASYMMETRY} kcal/mol. "
                "NOT_RUN no es PASS."
            ),
        )

    value = model(guide)
    estado = (
        FilterState.PASS if value >= thresholds.min_asymmetry else FilterState.FAIL
    )
    comparacion = ">=" if estado is FilterState.PASS else "por debajo de"
    return FilterResult(
        name="asimetria",
        state=estado,
        reason=(
            f"Asimetria {value:+.2f} kcal/mol {comparacion} "
            f"{thresholds.min_asymmetry}, "
            f"sobre la guía {guide} (proxy heuristico, ver thermo.py)."
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
            f"{indent}  guía (5'→3', U forzada en 1): {self.guide}",
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
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> WindowEvaluation:
    """Aplica los filtros duros a una ventana de 22 nt y devuelve todos los motivos."""
    cleaned = normalize_sequence(sequence)
    if len(cleaned) != WINDOW_SIZE:
        raise ValueError(
            f"La ventana mide {len(cleaned)} nt y los filtros están definidos sobre "
            f"{WINDOW_SIZE} nt; se aborta la evaluación en vez de aplicar umbrales "
            f"que no le corresponden."
        )
    desconocida = cleaned.find("N")
    if desconocida != -1:
        motivo = (
            f"La ventana tiene una base desconocida (N) en la posición "
            f"{desconocida + 1}: no es evaluable. NOT_RUN no es PASS."
        )
        return WindowEvaluation(
            sequence=cleaned,
            guide=guide_from_target(cleaned),
            filters=tuple(
                FilterResult(name=name, state=FilterState.NOT_RUN, reason=motivo)
                # LOS MISMOS que la rama normal, sin excepción. Quitar los dos G4
                # de aquí dejó 66 filas de 36 columnas bajo una cabecera de 38: todo lo
                # que va detrás se corre y `veredicto` acaba debajo de `G4_diana`. Un
                # TSV descuadrado no da ningún error — sólo un fichero equivocado, que es
                # el mismo fallo que aborta `Block.__post_init__` en el informe.
                for name in (
                    "GC", "homopolimero", "asimetria",
                )
            ),
            offset=offset,
        )

    guide = guide_from_target(cleaned)
    return WindowEvaluation(
        sequence=cleaned,
        guide=guide,
        filters=(
            filter_gc(cleaned, thresholds),
            filter_homopolymer(cleaned, thresholds),
            filter_asymmetry(guide, asymmetry_model, thresholds),
        ),
        offset=offset,
        asymmetry=None if asymmetry_model is None else asymmetry_model(guide),
    )
