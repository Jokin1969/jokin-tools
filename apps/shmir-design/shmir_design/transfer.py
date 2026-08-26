"""Cuando una puntuacion externa es TRANSFERIBLE de una entrada a otra.

La regla, comprobada sobre las dos corridas de miRarchitect en Prnp murino:

    Una puntuacion externa es transferible entre entradas si y solo si la ventana no
    solapa ninguna diferencia entre ellas — y esa condicion SE COMPRUEBA, no se supone.

De donde sale. Misma herramienta, mismo andamio, mismo gen, dos entradas que difieren en
18 sucesos sobre 1242 nt. Los 21 sitios que las dos corridas vieron con la MISMA ventana
salieron con score identico: el score es funcion local de la ventana de 22 nt y no
arrastra contexto. Donde la ventana coincide, la puntuacion vale.

Y el corolario que cuesta ver: **el puesto NO se transfiere.** Veinte de esos veintiun
sitios cambiaron de puesto con el score identico, porque el puesto depende del tamaño de
la lista y no del sitio. Transferir un ranking entre dos corridas de distinto tamaño es
un error aunque los scores sean los mismos.

`divergent_positions=None` NO significa "no hay diferencias": significa que nadie ha
mirado. Un `frozenset()` vacio si es una comprobacion hecha. Los dos casos se distinguen
porque confundirlos es exactamente suponer en vez de comprobar.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import ShmirDesignError

TRANSFER_RULE = (
    "Una puntuacion externa es transferible entre entradas si y solo si la ventana no "
    "solapa ninguna diferencia entre ellas, y esa condicion se comprueba, no se supone. "
    "El puesto NO se transfiere: depende del tamaño de la lista, no del sitio."
)


class Transferability(StrEnum):
    TRANSFERIBLE = "transferible"
    NO_TRANSFERIBLE = "no_transferible"
    #: Nadie ha alineado las dos entradas. No es lo mismo que "no hay diferencias".
    SIN_COMPROBAR = "sin_comprobar"


@dataclass(frozen=True)
class TransferVerdict:
    state: Transferability
    reason: str


def can_transfer(
    *, start: int, window: int, divergent_positions: frozenset[int] | None
) -> TransferVerdict:
    """¿Se puede llevar la puntuacion de esa ventana de una entrada a la otra?"""
    if window < 1:
        raise ShmirDesignError(
            f"Una ventana de {window} nt no describe nada; se aborta en vez de decidir "
            f"sobre un intervalo vacio."
        )
    if divergent_positions is None:
        return TransferVerdict(
            Transferability.SIN_COMPROBAR,
            "No se ha comprobado en que difieren las dos entradas, asi que no se sabe "
            "si esta ventana esta tocada. La regla exige comprobarlo, no suponerlo: sin "
            "el alineamiento de las dos entradas no se transfiere nada.",
        )
    fin = start + window - 1
    tocadas = sorted(p for p in divergent_positions if start <= p <= fin)
    if tocadas:
        return TransferVerdict(
            Transferability.NO_TRANSFERIBLE,
            f"La ventana {start}-{fin} solapa {len(tocadas)} posicion(es) que difieren "
            f"entre las dos entradas ({', '.join(map(str, tocadas))}): las dos corridas "
            f"no vieron lo mismo ahi, asi que la puntuacion no describe esta ventana.",
        )
    return TransferVerdict(
        Transferability.TRANSFERIBLE,
        f"La ventana {start}-{fin} no solapa ninguna diferencia entre las dos entradas: "
        f"las dos corridas vieron exactamente los mismos 22 nt. La puntuacion es "
        f"transferible; el PUESTO no.",
    )
