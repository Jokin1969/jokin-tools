"""Plegado del 97-mero con ViennaRNA (dependencia OPCIONAL).

Sirve para una sola cosa, y es importante: comprobar que la horquilla montada tiene la
MISMA estructura secundaria que la de SGEP. El desapareamiento de la posicion 1 de la
pasajera existe para mantener el bulge basal; si alguien lo pierde —por un cambio de la
regla, por una guia rara— el plegado lo caza y el 97-mero sale marcado.

ViennaRNA no es una dependencia del nucleo: sin ella `check_fold` devuelve NOT_RUN, que
no es PASS, y el resto del pipeline funciona igual. Se instala con
`pip install ViennaRNA` (autorizada, ver `docs/dependencias-autorizadas.md`).

Python 3.11+ (regla 6).
"""

from __future__ import annotations

from functools import lru_cache

from .errors import InvalidSequenceError, ShmirDesignError
from .filters import FilterResult, FilterState

RNA_BASES = frozenset("ACGU")


class FoldingUnavailableError(ShmirDesignError):
    """No hay con que plegar: ViennaRNA no esta instalado."""


def _import_vienna():
    try:
        import RNA  # noqa: PLC0415
    except ImportError:
        # rule2-ok: comprobacion de disponibilidad de una dependencia OPCIONAL, no un
        # fallo que se esconda. Devolvemos None y quien llama decide: `check_fold` marca
        # NOT_RUN con el motivo y `_fold_with` aborta con instrucciones.
        return None
    return RNA


VIENNA_AVAILABLE = _import_vienna() is not None


def _to_rna(sequence: str) -> str:
    cleaned = "".join(str(sequence).split()).upper().replace("T", "U")
    for index, base in enumerate(cleaned, start=1):
        if base not in RNA_BASES:
            raise InvalidSequenceError(
                f"Caracter {base!r} no valido en la posicion {index} (se esperaba A, C, "
                f"G, T o U); se aborta el plegado."
            )
    return cleaned


def _fold_with(vienna, sequence: str) -> tuple[str, float]:
    if vienna is None:
        raise FoldingUnavailableError(
            "ViennaRNA no esta instalado, asi que no se puede plegar: "
            "`pip install ViennaRNA`. Se aborta en vez de dar por buena una estructura "
            "que nadie ha calculado."
        )
    structure, energy = vienna.fold(sequence)
    return structure, float(energy)


@lru_cache(maxsize=8192)
def _fold_cached(rna: str) -> tuple[str, float]:
    return _fold_with(_import_vienna(), rna)


def dot_bracket(sequence: str) -> tuple[str, float]:
    """Estructura en notacion punto-parentesis y su ΔG, en kcal/mol.

    Cacheado por secuencia: el plegado es determinista y puro, y la eleccion de la
    posicion 1 de la pasajera pliega cinco 97-meros por candidato — sin cache, tilar un
    3'UTR entero se va de minutos.
    """
    return _fold_cached(_to_rna(sequence))


def reference_structure(reference_hairpin: str) -> str:
    return dot_bracket(reference_hairpin)[0]


def check_fold(hairpin, available: bool | None = None) -> FilterResult:
    """¿La horquilla pliega como la de referencia del andamio?

    `available=False` fuerza el camino sin ViennaRNA (util para probarlo).
    """
    usable = VIENNA_AVAILABLE if available is None else available
    if not usable:
        return FilterResult(
            name="plegado",
            state=FilterState.NOT_RUN,
            reason=(
                "ViennaRNA no esta instalado, asi que no se ha comprobado que la "
                "horquilla pliegue como la de referencia. NOT_RUN no es PASS: "
                "`pip install ViennaRNA` si quieres esta comprobacion."
            ),
        )

    from .scaffold import REFERENCE_HAIRPIN  # noqa: PLC0415

    estructura, dg = dot_bracket(hairpin.sequence)
    referencia = reference_structure(REFERENCE_HAIRPIN)
    if estructura == referencia:
        return FilterResult(
            name="plegado",
            state=FilterState.PASS,
            reason=f"Misma estructura que la horquilla de referencia; ΔG {dg:.2f} kcal/mol. {estructura}",
        )
    return FilterResult(
        name="plegado",
        state=FilterState.FAIL,
        reason=(
            f"La estructura NO coincide con la de referencia. Esperada {referencia}; "
            f"obtenida {estructura} (ΔG {dg:.2f}). Revisa el desapareamiento de la "
            f"posicion 1 de la pasajera antes de pedir nada."
        ),
    )
