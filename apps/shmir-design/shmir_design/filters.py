"""Estados de filtro de shmir-design (regla 3).

Tres estados, nunca un booleano:

  PASS       el filtro corrio con todos sus recursos y el candidato lo supera
  FAIL       el filtro corrio con todos sus recursos y el candidato no lo supera
  NOT_RUN    el filtro no llego a ejecutarse (recurso ausente, dependencia caida)
  NO_APLICA  la pregunta no va con este candidato

Un candidato con cualquier filtro en NOT_RUN no puede reportarse como aprobado: su
veredicto global es INCOMPLETE. `overall_verdict()` implementa esa agregacion.

NO_APLICA no es una cuarta forma de NOT_RUN, y la diferencia importa. NOT_RUN dice "no
pude comprobarlo": es una laguna, y una laguna impide aprobar. NO_APLICA dice "esa
pregunta no se le hace a este candidato": polyA, APA y los tercios son heuristicas del
3'UTR, y sobre una ventana del ORF no dan ni PASS ni FAIL, sino una pregunta mal hecha.
No hay nada que tapar, asi que no estorba al veredicto.

Lo que NO puede pasar: que NO_APLICA se use para esquivar un filtro que si aplicaba.
Solo lo pone quien sabe por que no aplica, y el motivo va escrito en `reason` como en
todos los demas estados.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


#: Filtros BIOFISICOS: los que solo dependen de la secuencia. El contador de
#: referencia (`biofisicos_ok`) cuenta las ventanas que los superan todos, y es
#: distinto del veredicto final: no incluye la seed ni ningun filtro que dependa de un
#: recurso externo. Asi el contador es comprobable sin miRBase, sin gnomAD y sin red.
BIOPHYSICAL_FILTERS = frozenset(
    {
        "GC",
        "homopolimero",
        "asimetria",
        "G4_diana",
        "G4_guia",
        "zona_prohibida_polyA",
    }
)


class FilterState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    NO_APLICA = "NO_APLICA"


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
                f"la regla 3 exige registrar por que, también en PASS."
            )


def overall_verdict(results: list[FilterResult]) -> Verdict:
    """Agrega varios filtros. Un solo NOT_RUN impide dar el candidato por aprobado."""
    if not results:
        raise ValueError(
            "No se puede emitir veredicto sin ningún filtro evaluado; "
            "un candidato sin filtros no es un candidato aprobado."
        )
    if any(r.state is FilterState.FAIL for r in results):
        return Verdict.FAIL
    if any(r.state is FilterState.NOT_RUN for r in results):
        return Verdict.INCOMPLETE
    if not any(r.state is FilterState.PASS for r in results):
        # Todo NO_APLICA: no se llego a preguntar nada, asi que no hay nada aprobado.
        return Verdict.INCOMPLETE
    return Verdict.PASS


def biophysical_ok(results: list[FilterResult]) -> bool:
    """¿La ventana supera TODOS los filtros biofisicos?

    Exige que los seis esten presentes, y cada uno en PASS o en NO_APLICA. Un filtro que
    no aparece no es un filtro superado: si falta, la respuesta es False, no un "bueno,
    los que hay pasan".

    NO_APLICA cuenta como no-estorbo por la razon del modulo: `zona_prohibida_polyA` es
    una heuristica del 3'UTR, y una ventana del ORF no puede quedar descartada por no
    superar una prueba que no se le hace. En una corrida solo-3'UTR no aparece ni un
    NO_APLICA, asi que el contador de referencia del proyecto no cambia de valor.
    """
    aceptables = (FilterState.PASS, FilterState.NO_APLICA)
    estados = {r.name: r.state for r in results}
    return all(estados.get(name) in aceptables for name in BIOPHYSICAL_FILTERS)
