"""Barrido del ORF conservado: la otra via cuando el 3'UTR no da un shmiR unico.

El 3'UTR de Prnp no tiene ni una ventana de 22 nt conservada raton/humano que supere los
filtros de secuencia (ver `conservation.single_shmir_verdict`), asi que un shmiR unico
para raton, Tg650 y clinica no cabe por ahi. El ORF si tiene tramos de identidad exacta
de 22 nt o mas, y ahi la pregunta se puede volver a hacer.

Se aplica la MISMA cascada, con la misma regla sobre lo que no aplica:

- SI aplican fuera del 3'UTR: GC, homopolimeros, asimetria, G-cuadruplex, colision de
  seed, elementos repetitivos y especificidad.
- NO aplican: polyA, APA y los tercios. Son heuristicas del 3'UTR y sobre una ventana del
  ORF la pregunta no se hace. Salen `NO_APLICA`, nunca `PASS` (regla 3, y `NO_APLICA` no
  es una cuarta forma de `NOT_RUN`).

CONTEXTO QUE NO ES UN DETALLE. El obstaculo clasico de la via ORF es que la guia apague
tambien el transgen terapeutico, y la solucion habitual es recodificar el transgen. Aqui
no hace falta: el ORF del casete AAV esta CODON-OPTIMIZADO, asi que ya es resistente a
una guia diseñada contra el ORF nativo. Eso no se supone — se comprueba con el filtro del
transgen, que sigue corriendo sobre estas ventanas como sobre las demas.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .conservation import Utr3, build_conservation_report
from .filters import FilterResult, FilterState
from .hard_filters import DEFAULT_THRESHOLDS, Thresholds

#: Lo que NO se le pregunta a una ventana del ORF, con el motivo que va escrito.
ORF_NOT_APPLICABLE = {
    "zona_prohibida_polyA": (
        "La ventana cae en el ORF, no en el 3'UTR. Las señales de poliadenilacion solo "
        "tienen sentido sobre el 3'UTR: aqui la pregunta no aplica. NO_APLICA no es PASS."
    ),
    "APA": (
        "La poliadenilacion alternativa recorta el 3'UTR, no el ORF: una ventana del ORF "
        "esta en todas las isoformas. La pregunta no aplica. NO_APLICA no es PASS."
    ),
    "tercio": (
        "Los tercios se cuentan sobre el 3'UTR. Una ventana del ORF no tiene tercio, y "
        "asignarle uno seria inventarse una coordenada. NO_APLICA no es PASS."
    ),
}

#: Los que SI aplican en el ORF pero necesitan un fichero. Sin el, NOT_RUN.
ORF_PENDING = {
    "seed_colision": "no hay lista curada de miARN abundantes cargada",
    "repeticiones": "no hay mascara de repeticiones cargada",
    "especificidad": "no hay base de RefSeq RNA cargada",
}

MIN_BLOCK = 22


@dataclass(frozen=True)
class OrfCandidate:
    orf_start_a: int
    orf_start_b: int
    tx_start_a: int
    tx_start_b: int
    target_a: str
    target_b: str
    guide: str
    filters: tuple[FilterResult, ...]

    @property
    def not_applicable(self) -> tuple[FilterResult, ...]:
        return tuple(
            FilterResult(name=nombre, state=FilterState.NO_APLICA, reason=motivo)
            for nombre, motivo in ORF_NOT_APPLICABLE.items()
        )

    @property
    def pending(self) -> tuple[FilterResult, ...]:
        return tuple(
            FilterResult(
                name=nombre,
                state=FilterState.NOT_RUN,
                reason=(
                    f"{motivo}. Este filtro SI aplica en el ORF; sin el recurso queda "
                    f"NOT_RUN, y NOT_RUN no es PASS."
                ),
            )
            for nombre, motivo in ORF_PENDING.items()
        )


@dataclass(frozen=True)
class OrfSweep:
    species: tuple[str, str]
    lengths: tuple[int, int]
    blocks: tuple
    windows: int
    passing: tuple[OrfCandidate, ...]
    min_block: int

    def describe(self) -> list[str]:
        from .coords import Frame, label

        a, b = self.species
        lineas = [
            f"BARRIDO DEL ORF CONSERVADO {a}/{b} — identidad exacta >= "
            f"{self.min_block} nt",
            f"  ORF: {self.lengths[0]} nt ({a}) y {self.lengths[1]} nt ({b}). "
            f"{len(self.blocks)} bloque(s) conservado(s), {self.windows} ventana(s) de "
            f"22 nt que caben dentro.",
            f"  Superan los filtros de SECUENCIA: {len(self.passing)}.",
        ]
        for candidato in self.passing:
            lineas.append(
                f"    · ORF {a} {candidato.orf_start_a} "
                f"({label(candidato.tx_start_a, Frame.TX)}) / "
                f"ORF {b} {candidato.orf_start_b} "
                f"({label(candidato.tx_start_b, Frame.TX)})  {candidato.target_a}"
            )
        if not self.passing:
            lineas.append(
                "    Ninguna. Por esta via tampoco hay shmiR unico, y con eso se cierran "
                "las dos."
            )
        lineas.extend(
            [
                "  polyA, APA y tercios salen NO_APLICA en estas ventanas: son "
                "heuristicas del 3'UTR y",
                "  sobre el ORF la pregunta no se hace. NO_APLICA no es PASS.",
                "  seed, repetitivos y especificidad SI aplican aqui, y hoy estan en "
                "NOT_RUN por falta de",
                "  fichero: estas ventanas NO estan aprobadas, estan preseleccionadas.",
                "  EL TRANSGEN NO ES UN OBSTACULO EN ESTE BACKBONE: el ORF del casete "
                "AAV esta",
                "  CODON-OPTIMIZADO, asi que ya es RESISTENTE a una guia contra el ORF "
                "nativo SIN",
                "  RECODIFICAR nada. El obstaculo clasico de la via ORF no existe aqui. "
                "Se comprueba igual",
                "  con el filtro del transgen: no se da por supuesto.",
            ]
        )
        return lineas


def orf_sweep(
    orf_a: str,
    orf_b: str,
    *,
    species: tuple[str, str],
    cds_start: tuple[int, int],
    min_block: int = MIN_BLOCK,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> OrfSweep:
    """Tramos de identidad exacta entre los dos ORF, con la cascada aplicada."""
    if min_block < 22:
        raise ValueError(
            f"min_block={min_block}: por debajo de 22 nt no cabe una guia entera dentro "
            f"del tramo conservado, asi que el barrido no significa nada. Se aborta."
        )
    informe = build_conservation_report(
        Utr3(species[0], orf_a),
        Utr3(species[1], orf_b),
        min_length=min_block,
        thresholds=thresholds,
    )
    candidatos: list[OrfCandidate] = []
    ventanas = 0
    for indice, bloque in enumerate(informe.blocks):
        hit_a = [h for h in bloque.hits if h.species == species[0]][0]
        hit_b = [h for h in bloque.hits if h.species == species[1]][0]
        for desplazamiento, evaluacion in enumerate(informe.evaluations[indice]):
            ventanas += 1
            if evaluacion.verdict.value != "PASS":
                continue
            inicio_a = hit_a.start + desplazamiento
            inicio_b = hit_b.start + desplazamiento
            candidatos.append(
                OrfCandidate(
                    orf_start_a=inicio_a,
                    orf_start_b=inicio_b,
                    tx_start_a=cds_start[0] + inicio_a - 1,
                    tx_start_b=cds_start[1] + inicio_b - 1,
                    target_a=orf_a[inicio_a - 1 : inicio_a - 1 + 22],
                    target_b=orf_b[inicio_b - 1 : inicio_b - 1 + 22],
                    guide=evaluacion.guide,
                    filters=tuple(evaluacion.filters),
                )
            )
    return OrfSweep(
        species=species,
        lengths=(len(orf_a), len(orf_b)),
        blocks=informe.blocks,
        windows=ventanas,
        passing=tuple(candidatos),
        min_block=min_block,
    )
