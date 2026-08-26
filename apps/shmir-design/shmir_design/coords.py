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

#: Techo del espacio `3utr`, DERIVADO de las referencias del proyecto. No se teclea: si
#: entra una referencia con un 3'UTR mas largo, el techo sube solo.
#:
#: Existe porque `Position` impedia construir una posicion SIN marco pero no impedia
#: declarar el marco EQUIVOCADO, y eso ha pasado tres veces: `3utr:1784` sobre un 3'UTR
#: humano de 1606 nt —en un informe que ya se estaba entregando— y los tramos de techo
#: como `3utr:1-1200` … `3utr:1273-2191` sobre uno murino de 1242. Los dos eran
#: coordenadas del TRANSCRITO etiquetadas como 3'UTR, y ninguno dio error.
#:
#: Lo que NO hace: garantizar que el marco sea el correcto. Eso necesita un contexto que
#: esta clase no tiene. Lo que si hace es convertir el caso IMPOSIBLE —una posicion que
#: no cabe en ningun 3'UTR conocido— en un aborto en vez de en una linea que se lee sin
#: sospechar nada. Para afinar por especie esta `limit`.
_MAX_UTR3: int | None = None


def max_utr3() -> int:
    """La longitud del 3'UTR mas largo que conoce el proyecto."""
    global _MAX_UTR3
    if _MAX_UTR3 is None:
        # Import perezoso: `coords` es el modulo mas bajo del paquete y `reference`
        # arrastra fetch y errores. Se resuelve una vez y se cachea.
        from .reference import REFERENCES

        _MAX_UTR3 = max(r.utr3_length for r in REFERENCES.values())
    return _MAX_UTR3


def check_utr3_range(value: int, limit: int | None = None) -> None:
    """Aborta si `value` no cabe en un 3'UTR. `limit` afina; nunca relaja el techo."""
    techo = max_utr3()
    if value > techo:
        raise ValueError(
            f"3utr:{value} no cabe en ningun 3'UTR conocido del proyecto: el mas largo "
            f"mide {techo} nt. Casi seguro es una coordenada del TRANSCRITO etiquetada "
            f"como 3'UTR (seria tx:{value}); el marco se saca de la anatomia con "
            f"coords.frame_of(), no se pone a mano. Se aborta en vez de imprimir una "
            f"posicion que no existe."
        )
    if limit is not None and value > limit:
        raise ValueError(
            f"3utr:{value} se sale del 3'UTR que se esta analizando, que mide {limit} "
            f"nt. Se aborta: o el marco es otro (seria tx:{value}) o la conversion tiene "
            f"un desfase."
        )


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
        if self.frame is Frame.UTR3:
            check_utr3_range(self.value)
        # `tx` NO se comprueba: el marco del transcrito no tiene techo conocido —lo
        # tilado puede ser cualquier cosa— y ponerle uno seria inventarse un limite. Lo
        # que se caza es lo imposible, no lo sospechoso.

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


def label(value: int | None, frame: Frame, *, limit: int | None = None) -> str:
    """Atajo para una posicion suelta. `None` va VACIO, nunca `3utr:0`.

    `limit` es la longitud del 3'UTR que se esta analizando, cuando el que llama la
    tiene: afina el techo global a la especie concreta. Nunca lo relaja.
    """
    if value is None:
        return ""
    posicion = Position(value, frame)
    if frame is Frame.UTR3:
        check_utr3_range(value, limit)
    return str(posicion)


def span(start: int, end: int, frame: Frame, *, limit: int | None = None) -> str:
    """Intervalo etiquetado UNA vez: `3utr:158-277`.

    Repetir la etiqueta en los dos extremos se lee peor y ocupa el doble, y el riesgo
    que cierra esto —un extremo en un espacio y el otro en otro— no existe: el intervalo
    es de un unico espacio por construccion.
    """
    inicio = Position(start, frame)
    fin = Position(end, frame)
    if frame is Frame.UTR3:
        check_utr3_range(start, limit)
        check_utr3_range(end, limit)
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


def bound_of(anatomy) -> int | None:
    """La longitud del 3'UTR de esta anatomia, para afinar el techo. `None` si no hay."""
    if anatomy is None or not getattr(anatomy, "utr3", None):
        return None
    inicio, fin = anatomy.utr3
    return fin - inicio + 1
