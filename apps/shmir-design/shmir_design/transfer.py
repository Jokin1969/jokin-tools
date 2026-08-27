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

from .alignment import DiffClass
from .errors import ShmirDesignError

TRANSFER_RULE = (
    "Una puntuación externa es transferible entre entradas si y solo si la ventana no "
    "solapa ninguna diferencia entre ellas, y esa condición se comprueba, no se supone. "
    "El puesto NO se transfiere: depende del tamaño de la lista, no del sitio."
)


class WindowState(StrEnum):
    """Como esta una ventana respecto de las diferencias entre las dos entradas.

    Hacen falta TRES estados, no dos. Un indel dentro de una carrera de bases iguales no
    tiene posicion: el alineador lo coloca en un punto cualquiera de la carrera, asi que
    «¿cae dentro de esta ventana?» no siempre tiene respuesta. Colapsarlo a dos estados
    obliga a mentir en un sentido o en el otro.
    """

    LIMPIA = "limpia"
    TOCADA = "tocada"
    #: La carrera de una diferencia ambigua cruza el borde de la ventana.
    INDETERMINADA = "indeterminada"


@dataclass(frozen=True)
class WindowVerdict:
    state: WindowState
    reason: str


def classify_window(*, start: int, window: int, alignment) -> WindowVerdict:
    """En cual de los tres estados esta esa ventana. A PRIORI: solo mira el alineamiento.

    Lo inequivoco manda sobre lo ambiguo: si hay una diferencia de posicion cierta
    dentro, la ventana esta TOCADA y da igual lo que haya ademas. Y una carrera que cabe
    ENTERA dentro de la ventana tambien la deja tocada: el indel esta dentro se ponga
    donde se ponga.
    """
    if window < 1:
        raise ShmirDesignError(
            f"Una ventana de {window} nt no describe nada; se aborta en vez de decidir "
            f"sobre un intervalo vacío."
        )
    fin = start + window - 1
    ciertas: list[int] = []
    dudosas: list[tuple[int, int]] = []
    for diferencia in alignment.differences:
        if not diferencia.ambiguous:
            if start <= diferencia.ref_start <= fin:
                ciertas.append(diferencia.ref_start)
            continue
        # Los sitios posibles NO son los mismos para los dos tipos, y confundirlos es
        # lo que hacia salir TOCADA una ventana que las dos corridas vieron igual:
        #
        # - una DELECION borra una de las posiciones de la carrera: los sitios posibles
        #   son las posiciones a..z, y estan dentro de la ventana si lo estan ellas;
        # - una INSERCION se mete en una JUNTURA. Con una carrera a..z las junturas
        #   posibles son a-1, a, ..., z — y la de detras de `z` cae FUERA de una ventana
        #   que acaba en `z`. Por eso una carrera que "cabe entera" no basta para
        #   afirmar que la insercion esta dentro.
        a, z = diferencia.run_start, diferencia.run_end
        if diferencia.kind is DiffClass.INSERCION:
            sitios = range(a - 1, z + 1)          # junturas
            dentro = [j for j in sitios if start <= j <= fin - 1]
        else:
            sitios = range(a, z + 1)              # posiciones
            dentro = [p for p in sitios if start <= p <= fin]
        if len(dentro) == len(sitios):
            ciertas.append(a)          # todos los sitios posibles caen dentro
        elif dentro:
            dudosas.append((a, z))
    if ciertas:
        return WindowVerdict(
            WindowState.TOCADA,
            f"La ventana {start}-{fin} contiene {len(ciertas)} diferencia(s) de "
            f"posición cierta ({', '.join(map(str, sorted(ciertas)))}): las dos "
            f"entradas no dicen lo mismo ahi.",
        )
    if dudosas:
        tramos = ", ".join(f"{a}-{z}" for a, z in dudosas)
        return WindowVerdict(
            WindowState.INDETERMINADA,
            f"La ventana {start}-{fin} roza la carrera {tramos}, donde hay un indel "
            f"cuya posición es indistinguible: el alineador lo coloca en un punto "
            f"cualquiera de la carrera, así que NO SE PUEDE AFIRMAR si cae dentro o "
            f"fuera de la ventana. A priori no se transfiere; con las dos salidas "
            f"delante, si las dos cadenas coinciden, si.",
        )
    return WindowVerdict(
        WindowState.LIMPIA,
        f"La ventana {start}-{fin} no toca ninguna diferencia entre las dos entradas.",
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


def can_transfer_window(
    *, start: int, window: int, alignment, same_string: bool | None = None
) -> TransferVerdict:
    """La regla con los tres estados. `same_string` es la comprobacion DIRECTA.

    - `LIMPIA` transfiere.
    - `TOCADA` no.
    - `INDETERMINADA` no transfiere a priori, y transfiere solo si existe la
      comprobacion directa —las dos salidas delante— y las dos cadenas coinciden.

    Los dos criterios no estan disponibles en el mismo momento, y por eso no se
    sustituyen: a priori, decidiendo si un score se lleva a una entrada que aun no se ha
    corrido, solo hay alineamiento. A posteriori, la identidad de la cadena es
    observacion y no inferencia.
    """
    veredicto = classify_window(start=start, window=window, alignment=alignment)
    if veredicto.state is WindowState.LIMPIA:
        return TransferVerdict(Transferability.TRANSFERIBLE, veredicto.reason)
    if veredicto.state is WindowState.TOCADA:
        return TransferVerdict(Transferability.NO_TRANSFERIBLE, veredicto.reason)
    if same_string is True:
        return TransferVerdict(
            Transferability.TRANSFERIBLE,
            f"{veredicto.reason} COMPROBACIÓN DIRECTA: las dos salidas traen la misma "
            f"cadena para este sitio, así que la ventana fue la misma. Eso es "
            f"observacion, no inferencia, y resuelve la indeterminacion.",
        )
    if same_string is False:
        return TransferVerdict(
            Transferability.NO_TRANSFERIBLE,
            f"{veredicto.reason} COMPROBACIÓN DIRECTA: las dos salidas traen cadenas "
            f"DISTINTAS para este sitio.",
        )
    return TransferVerdict(Transferability.SIN_COMPROBAR, veredicto.reason)


def can_transfer(
    *, start: int, window: int, divergent_positions: frozenset[int] | None
) -> TransferVerdict:
    """La regla en su forma simple, sobre un conjunto de posiciones divergentes.

    No distingue lo ambiguo de lo cierto: para eso esta `can_transfer_window`, que
    recibe el alineamiento entero. Esta se queda para quien solo tenga las posiciones.
    """
    if window < 1:
        raise ShmirDesignError(
            f"Una ventana de {window} nt no describe nada; se aborta en vez de decidir "
            f"sobre un intervalo vacío."
        )
    if divergent_positions is None:
        return TransferVerdict(
            Transferability.SIN_COMPROBAR,
            "No se ha comprobado en que difieren las dos entradas, así que no se sabe "
            "si esta ventana está tocada. La regla exige comprobarlo, no suponerlo: sin "
            "el alineamiento de las dos entradas no se transfiere nada.",
        )
    fin = start + window - 1
    tocadas = sorted(p for p in divergent_positions if start <= p <= fin)
    if tocadas:
        return TransferVerdict(
            Transferability.NO_TRANSFERIBLE,
            f"La ventana {start}-{fin} solapa {len(tocadas)} posición(es) que difieren "
            f"entre las dos entradas ({', '.join(map(str, tocadas))}): las dos corridas "
            f"no vieron lo mismo ahi, así que la puntuación no describe esta ventana.",
        )
    return TransferVerdict(
        Transferability.TRANSFERIBLE,
        f"La ventana {start}-{fin} no solapa ninguna diferencia entre las dos entradas: "
        f"las dos corridas vieron exactamente los mismos 22 nt. La puntuación es "
        f"transferible; el PUESTO no.",
    )
