"""El espacio de coordenadas va PEGADO al numero, siempre.

Contramedida generalizada de la de `reference.describe_sequence`, que ata longitud y md5
porque «referencia 1246 nt» a solas parece razonable. Aqui pasa lo mismo con las
posiciones: un `1018` no identifica nada. El 1018 del transcrito de raton es el 69 del
3'UTR, y el 1018 del 3'UTR es otro sitio. Los dos son enteros de cuatro cifras y ninguno
da error al imprimirse: dan una conversacion equivocada.

Por eso la etiqueta va INLINE —`3utr:1018`, `tx:1967`— en cualquier salida: informe,
avisos, motivos de filtro y celdas del TSV. En la cabecera de la columna NO basta: quien
copia una celda a un correo, o lee una linea suelta del informe, se lleva el numero sin
la cabecera.

Las coordenadas del proyecto son 1-based, asi que un 0 es un error de conversion y se
aborta en vez de imprimirlo.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

SEPARATOR = ":"


class Frame(StrEnum):
    """Los dos espacios en los que el proyecto cuenta posiciones.

    `TX` es el marco de LO TILADO cuando lo tilado es un transcrito: puede ser un mRNA
    completo de RefSeq o el trozo que se haya pasado. `UTR3` cuenta desde el primer
    nucleotido del 3'UTR. Cuando lo tilado YA es el 3'UTR los dos coinciden, y entonces
    el marco es `UTR3` — decir `tx:` ahi seria prometer un transcrito que no hay.
    """

    UTR3 = "3utr"
    TX = "tx"


@dataclass(frozen=True)
class Position:
    """Una posicion con su espacio. No se puede construir sin el.

    `value` sigue siendo un entero para calcular; lo que no existe es una forma de
    IMPRIMIRLA desnuda: `str()` y `format()` devuelven siempre la etiqueta pegada.
    """

    value: int
    frame: Frame

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise TypeError(
                f"Una posicion es un entero 1-based, no {type(self.value).__name__}; "
                f"se aborta en vez de imprimir una coordenada que no lo es."
            )
        if self.value < 1:
            raise ValueError(
                f"Posicion {self.value}: las coordenadas del proyecto son 1-based, asi "
                f"que un valor menor que 1 es un error de conversion (tipicamente un "
                f"0-based que se colo). Se aborta en vez de imprimirlo."
            )
        if not isinstance(self.frame, Frame):
            raise ValueError(
                f"Espacio de coordenadas {self.frame!r} desconocido; los que hay son "
                f"{', '.join(f.value for f in Frame)}. Se aborta: una posicion sin "
                f"espacio no identifica ningun sitio."
            )

    def __str__(self) -> str:
        return f"{self.frame.value}{SEPARATOR}{self.value}"

    def __format__(self, spec: str) -> str:
        # Sin esto, un `f"{posicion:>6}"` en cualquier tabla imprimiria el repr del
        # dataclass. Con spec se alinea la cadena ETIQUETADA, nunca el entero.
        return format(str(self), spec)

    def shifted(self, delta: int) -> "Position":
        """Misma posicion movida `delta` nt, en el MISMO espacio."""
        return Position(self.value + delta, self.frame)

    def to_utr3(self, offset: int) -> "Position":
        """Pasa del marco del transcrito al del 3'UTR restando el desfase.

        `offset` es la primera posicion del 3'UTR menos 1. Convertir una posicion que
        ya esta en el 3'UTR aborta: seria restar el desfase dos veces, que es
        exactamente como se fabrica un off-by-cientos.
        """
        if self.frame is Frame.UTR3:
            raise ValueError(
                f"{self} ya esta en el espacio del 3'UTR: restarle otra vez el desfase "
                f"de {offset} nt daria una posicion inventada. Se aborta."
            )
        return Position(self.value - offset, Frame.UTR3)


def label(value: int | None, frame: Frame) -> str:
    """Atajo para una posicion suelta. `None` va VACIO, nunca `3utr:0`."""
    if value is None:
        return ""
    return str(Position(value, frame))


def span(start: int, end: int, frame: Frame) -> str:
    """Intervalo etiquetado UNA vez: `3utr:158-277`.

    Repetir la etiqueta en los dos extremos se lee peor y ocupa el doble, y el riesgo
    que cierra esto —un extremo en un espacio y el otro en otro— no existe: el intervalo
    es de un unico espacio por construccion.
    """
    inicio = Position(start, frame)
    fin = Position(end, frame)
    if fin.value < inicio.value:
        raise ValueError(
            f"Intervalo {start}-{end} invertido en el espacio {frame.value}; se aborta "
            f"en vez de imprimir un tramo imposible."
        )
    return f"{inicio}-{fin.value}"


def parse(text: str) -> Position:
    """Lee de vuelta una posicion etiquetada: `3utr:449` → `Position(449, UTR3)`.

    Existe para que la etiqueta no sea solo decoracion: una celda etiquetada se puede
    volver a leer sin adivinar el espacio, y quien lea el TSV tiene que pasar por aqui.
    Un entero desnudo NO se acepta: es exactamente lo que esta contramedida prohibe.
    """
    if not isinstance(text, str) or SEPARATOR not in text:
        raise ValueError(
            f"{text!r} no lleva espacio de coordenadas (se esperaba algo como "
            f"'3utr:449'); se aborta en vez de suponer en que espacio esta."
        )
    marco, _, valor = text.partition(SEPARATOR)
    try:
        numero = int(valor)
    except ValueError as exc:
        raise ValueError(
            f"{text!r}: {valor!r} no es un entero; se aborta la lectura de la posicion."
        ) from exc
    try:
        return Position(numero, Frame(marco))
    except ValueError as exc:
        raise ValueError(
            f"{text!r}: espacio de coordenadas {marco!r} desconocido (los que hay son "
            f"{', '.join(f.value for f in Frame)}); se aborta."
        ) from exc


def frame_of(anatomy) -> Frame:
    """El espacio en que van las coordenadas de LO TILADO, sacado de la anatomia.

    Es la misma cuenta del desfase que hacia cada bloque del informe por su cuenta, en
    un solo sitio: si el 3'UTR empieza en la posicion 1 de lo tilado, lo tilado ES el
    3'UTR; si empieza mas adelante, lo tilado es un transcrito.

    Sin anatomia no se adivina: es la regla de `resolve.py`, y un marco supuesto es
    justo lo que produce el `1018` que era el 69.
    """
    if anatomy is None:
        raise ValueError(
            "No hay anatomia, asi que no se sabe en que espacio van las coordenadas de "
            "lo tilado; se aborta en vez de etiquetarlas al azar. La anatomia se "
            "resuelve con --genbank, --cds o --region 3utr."
        )
    utr3 = getattr(anatomy, "utr3", None)
    if not utr3:
        raise ValueError(
            f"La anatomia {anatomy!r} no declara 3'UTR, asi que no hay desfase con el "
            f"que decidir el espacio de coordenadas; se aborta."
        )
    return Frame.UTR3 if utr3[0] == 1 else Frame.TX


def offset_of(anatomy) -> int:
    """Desfase entre el marco de lo tilado y el del 3'UTR: `utr3[0] - 1`."""
    if anatomy is None or not getattr(anatomy, "utr3", None):
        return 0
    return anatomy.utr3[0] - 1
