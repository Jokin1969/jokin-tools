"""Estados de filtro de shmir-design (regla 3).

Tres estados, nunca un booleano:

  PASS     el filtro corrio con todos sus recursos y el candidato lo supera
  FAIL     el filtro corrio con todos sus recursos y el candidato no lo supera
  NOT_RUN  el filtro no llego a ejecutarse (recurso ausente, dependencia caida)

Un candidato con cualquier filtro en NOT_RUN no puede reportarse como aprobado: su
veredicto global es INCOMPLETE. `overall_verdict()` implementa esa agregacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FilterState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class FilterResult:
    """Resultado de un filtro sobre un candidato.

    `reason` es obligatorio y legible tambien en PASS: una salida en la que solo los
    fallos se explican deja al lector adivinando si un filtro llego a correr.
    """

    name: str
    state: FilterState
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError(
                f"El filtro {self.name!r} devolvio estado {self.state} sin motivo; "
                f"la regla 3 exige registrar por que, tambien en PASS."
            )


def overall_verdict(results: list[FilterResult]) -> Verdict:
    """Agrega varios filtros. Un solo NOT_RUN impide dar el candidato por aprobado."""
    if not results:
        raise ValueError(
            "No se puede emitir veredicto sin ningun filtro evaluado; "
            "un candidato sin filtros no es un candidato aprobado."
        )
    if any(r.state is FilterState.FAIL for r in results):
        return Verdict.FAIL
    if any(r.state is FilterState.NOT_RUN for r in results):
        return Verdict.INCOMPLETE
    return Verdict.PASS
