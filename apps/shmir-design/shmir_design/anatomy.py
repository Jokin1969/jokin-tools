"""Anatomia del transcrito: que tramo es cada posicion (paso 1).

Sin esto, tilar un mRNA entero trata el 5'UTR y el CDS como si fueran 3'UTR, y los
tercios `proximal/medio/distal` se calculan sobre el transcrito completo. El resultado
es que hay que restar a mano el desplazamiento del 3'UTR para comparar con las tablas
del proyecto — y ahi es donde se cuelan los errores.

Con la anatomia declarada, cada ventana sale con sus DOS coordenadas: la del transcrito
y la del 3'UTR. Los tercios se calculan siempre sobre el 3'UTR.

La anatomia NUNCA se adivina. Hay tres vias para fijarla, y las tres dejan constancia
de cual se uso en `Anatomy.source` (`RegionSource`), que sale impreso en el informe:

  1. coordenadas del CDS declaradas a mano (`--cds`)
  2. la feature CDS de un GenBank suministrado (`shmir_design/genbank.py`)
  3. la declaracion explicita de que la secuencia entera ya es el 3'UTR

`shmir_design/orf.py` puede PROPONER un marco de lectura, pero su propuesta no llega
hasta aqui: no hay ninguna funcion que convierta un ORF en una `Anatomy`. Equivocarse
de isoforma desplazaria todas las coordenadas sin que nada avise, asi que esa frontera
la fija una persona.

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


class RegionSource(StrEnum):
    """De donde salio la frontera del 3'UTR. Siempre se imprime en el informe.

    Sin esto, una anatomia declarada a mano y una leida de una anotacion son
    indistinguibles en la salida, y el lector no puede saber cuanta confianza darle a
    los tercios ni a las etiquetas de region.
    """

    CDS_DECLARADA = "cds_declarada"
    ANOTACION_GENBANK = "anotacion_genbank"
    TODO_3UTR_DECLARADO = "todo_3utr_declarado"
    FIXTURE_VERIFICADO = "fixture_verificado"
    SIN_RESOLVER = "sin_resolver"

    def describe(self) -> str:
        return {
            RegionSource.CDS_DECLARADA: (
                "coordenadas del CDS declaradas a mano en la linea de comandos"
            ),
            RegionSource.ANOTACION_GENBANK: (
                "feature CDS de un fichero GenBank suministrado y verificado"
            ),
            RegionSource.TODO_3UTR_DECLARADO: (
                "declarado explicitamente: la secuencia entera ya es el 3'UTR"
            ),
            RegionSource.FIXTURE_VERIFICADO: (
                "coordenadas del transcrito de referencia, comprobadas por checksum"
            ),
            RegionSource.SIN_RESOLVER: (
                "SIN RESOLVER: no se declaro donde acaba el CDS, asi que no se sabe "
                "que tramo es cada posicion"
            ),
        }[self]


@dataclass(frozen=True)
class Anatomy:
    """Tramos del transcrito, 1-based e inclusivos. `utr3` es obligatorio."""

    length: int
    utr3: tuple[int, int]
    utr5: tuple[int, int] | None = None
    cds: tuple[int, int] | None = None
    warnings: tuple[str, ...] = field(default=())
    source: RegionSource = RegionSource.SIN_RESOLVER

    def __post_init__(self) -> None:
        if self.source is RegionSource.SIN_RESOLVER:
            raise ValueError(
                "No se puede construir una Anatomy con source=SIN_RESOLVER: si la "
                "frontera del 3'UTR no esta resuelta no hay anatomia que usar, y "
                "tilar con una inventada corre todas las coordenadas en silencio. "
                "Declara --cds, pasa un GenBank, o declara que la secuencia ya es el "
                "3'UTR. SIN_RESOLVER solo existe para decirlo en el informe."
            )

    @classmethod
    def from_cds(
        cls,
        cds: tuple[int, int],
        length: int,
        source: RegionSource = RegionSource.CDS_DECLARADA,
    ) -> Anatomy:
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
            source=source,
        )

    @classmethod
    def whole_is_utr3(cls, length: int, *, source: RegionSource) -> Anatomy:
        """`source` es obligatorio y va por nombre a proposito.

        Antes esta llamada era el fallback silencioso de `tools/design.py` cuando no se
        pasaba `--cds`: un transcrito completo se tilaba entero como si fuera 3'UTR.
        Exigir que quien la llame declare POR QUE cree que todo es 3'UTR hace imposible
        volver a caer aqui por descuido.
        """
        if length < 1:
            raise ValueError(f"Longitud {length} invalida; se aborta.")
        return cls(length=length, utr3=(1, length), source=source)

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


#: Los tres codones de parada. No hay mas, y no se aceptan variantes.
STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})


def check_cds_boundaries(sequence: str, anatomy: Anatomy) -> tuple[str, ...]:
    """Comprueba que el CDS declarado cuadra con las bases que hay debajo.

    Es el chequeo que pilla el error mas frecuente al declarar coordenadas a mano: el
    desplazamiento de un nucleotido, y la confusion entre 0-based y 1-based. Un CDS
    corrido una base deja el 3'UTR corrido tambien, y con el todas las posiciones, los
    tercios y la comparacion con las tablas del proyecto — sin que nada avise.

    No genera ni corrige nada (regla 1): solo lee las bases que ya estan y las compara
    con lo declarado. Devuelve los avisos; la decision de abortar es de quien llama.
    """
    if len(sequence) != anatomy.length:
        raise ValueError(
            f"La secuencia mide {len(sequence)} nt y la anatomia dice {anatomy.length}; "
            f"se aborta el chequeo del CDS en vez de comprobar coordenadas contra otra "
            f"secuencia."
        )
    if anatomy.cds is None:
        return (
            f"No hay CDS declarado ({anatomy.source.describe()}): el chequeo del codon "
            f"de parada no se puede ejecutar.",
        )

    inicio, fin = anatomy.cds
    upper = sequence.upper()
    avisos: list[str] = []

    primero = upper[inicio - 1 : inicio + 2]
    if primero != "ATG":
        avisos.append(
            f"El CDS declarado empieza en {inicio} con {primero!r}, que no es ATG. "
            f"Revisa las coordenadas: si estan corridas, todo el 3'UTR lo esta tambien."
        )

    ultimo = upper[fin - 3 : fin]
    if ultimo not in STOP_CODONS:
        vecinos = {
            desplazamiento: upper[fin - 3 + desplazamiento : fin + desplazamiento]
            for desplazamiento in (-2, -1, 1, 2)
        }
        pistas = [
            f"{d:+d} -> {c!r}" for d, c in vecinos.items() if c in STOP_CODONS
        ]
        aviso = (
            f"El CDS declarado termina en {fin} con {ultimo!r}, que no es un codon de "
            f"parada ({', '.join(sorted(STOP_CODONS))})."
        )
        if pistas:
            aviso += (
                f" Hay uno a {' y a '.join(pistas)}: parece un desplazamiento de "
                f"coordenadas, no un CDS raro."
            )
        else:
            aviso += (
                " No hay ninguno cerca tampoco, asi que puede ser un CDS parcial o una "
                "secuencia que no corresponde a estas coordenadas."
            )
        avisos.append(aviso)

    return tuple(avisos)


def cds_stop_codon_ok(sequence: str, anatomy: Anatomy) -> bool | None:
    """¿El CDS declarado termina en un codon de parada?

    `None` cuando no hay CDS declarado y por tanto la pregunta no aplica — que no es lo
    mismo que responder que si.
    """
    if anatomy.cds is None:
        return None
    return sequence.upper()[anatomy.cds[1] - 3 : anatomy.cds[1]] in STOP_CODONS
