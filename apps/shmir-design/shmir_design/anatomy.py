"""Anatomia del transcrito: que tramo es cada posicion (paso 1).

Sin esto, tilar un mRNA entero trata el 5'UTR y el CDS como si fueran 3'UTR, y los
tercios `proximal/medio/distal` se calculan sobre el transcrito completo. El resultado
es que hay que restar a mano el desplazamiento del 3'UTR para comparar con las tablas
del proyecto — y ahi es donde se cuelan los errores.

Con la anatomia declarada, cada ventana sale con sus DOS coordenadas: la del transcrito
y la del 3'UTR. Los tercios se calculan siempre sobre el 3'UTR.

No hay deteccion de ORF: o se declaran las coordenadas del CDS, o se declara que la
secuencia entera es el 3'UTR. Adivinar el marco abierto de lectura y equivocarse de
isoforma desplazaria todas las coordenadas sin que nada avise.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from .polya import Tercio


class Region(StrEnum):
    UTR5 = "5'UTR"
    CDS = "CDS"
    UTR3 = "3'UTR"


@dataclass(frozen=True)
class Anatomy:
    """Tramos del transcrito, 1-based e inclusivos. `utr3` es obligatorio."""

    length: int
    utr3: tuple[int, int]
    utr5: tuple[int, int] | None = None
    cds: tuple[int, int] | None = None
    warnings: tuple[str, ...] = field(default=())

    @classmethod
    def from_cds(cls, cds: tuple[int, int], length: int) -> Anatomy:
        inicio, fin = cds
        if inicio < 1 or fin < inicio:
            raise ValueError(
                f"CDS {inicio}-{fin} invalido: coordenadas 1-based y fin >= inicio; "
                f"se aborta."
            )
        if fin > length:
            raise ValueError(
                f"El CDS termina en {fin} y el transcrito mide {length} nt; se aborta "
                f"en vez de recortar el CDS por nuestra cuenta."
            )
        if fin >= length:
            raise ValueError(
                f"El CDS termina en {fin}, el ultimo nucleotido del transcrito: no "
                f"queda 3'UTR que analizar; se aborta."
            )

        avisos: list[str] = []
        if (fin - inicio + 1) % 3 != 0:
            avisos.append(
                f"El CDS {inicio}-{fin} mide {fin - inicio + 1} nt, que no es multiplo "
                f"de 3. Revisa las coordenadas: el 3'UTR podria estar desplazado."
            )
        return cls(
            length=length,
            utr3=(fin + 1, length),
            utr5=(1, inicio - 1) if inicio > 1 else None,
            cds=(inicio, fin),
            warnings=tuple(avisos),
        )

    @classmethod
    def whole_is_utr3(cls, length: int) -> Anatomy:
        if length < 1:
            raise ValueError(f"Longitud {length} invalida; se aborta.")
        return cls(length=length, utr3=(1, length))

    @property
    def utr3_length(self) -> int:
        return self.utr3[1] - self.utr3[0] + 1

    @property
    def declared(self) -> bool:
        """¿Se declaro la anatomia completa, o solo que todo es 3'UTR?"""
        return self.cds is not None

    def _check(self, position: int) -> None:
        if position < 1 or position > self.length:
            raise ValueError(
                f"La posicion {position} esta fuera del transcrito (1-{self.length}); "
                f"se aborta en vez de devolver un tramo inventado."
            )

    def region_of(self, position: int) -> Region:
        self._check(position)
        if self.utr5 is not None and self.utr5[0] <= position <= self.utr5[1]:
            return Region.UTR5
        if self.cds is not None and self.cds[0] <= position <= self.cds[1]:
            return Region.CDS
        return Region.UTR3

    def utr3_position(self, position: int) -> int | None:
        """Coordenada dentro del 3'UTR, o None si la posicion no cae en el 3'UTR."""
        self._check(position)
        if not self.utr3[0] <= position <= self.utr3[1]:
            return None
        return position - self.utr3[0] + 1

    def transcript_position(self, utr3_position: int) -> int:
        if not 1 <= utr3_position <= self.utr3_length:
            raise ValueError(
                f"La posicion {utr3_position} esta fuera del 3'UTR "
                f"(1-{self.utr3_length}); se aborta."
            )
        return self.utr3[0] + utr3_position - 1

    def crosses_boundary(self, start: int, end: int) -> bool:
        """¿La ventana pisa dos tramos? Entonces su etiqueta es la del punto medio."""
        return self.region_of(start) is not self.region_of(end)

    def tercio_of(self, start: int, end: int) -> Tercio | None:
        """Tercio del 3'UTR, calculado SOBRE EL 3'UTR. None si la ventana no cae ahi."""
        middle = (start + end) / 2
        relative = middle - self.utr3[0] + 1
        if relative < 1 or relative > self.utr3_length:
            return None
        index = math.floor((relative - 1) * 3 / self.utr3_length)
        return (Tercio.PROXIMAL, Tercio.MEDIO, Tercio.DISTAL)[min(2, max(0, index))]
