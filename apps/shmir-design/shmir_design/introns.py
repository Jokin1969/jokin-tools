"""El registro de intrones. La unidad del cuarto modal NO es el candidato.

Los otros tres modales preguntan sobre una guia de 22 nt. Este pregunta sobre el
**cassette montado**: intron completo, con su modulo dentro, con la guia y la pasajera de
ese candidato concreto, y con contexto exonico a los dos lados. Asi que la unidad es el
par **candidato x intron** — diez candidatos y tres intrones son treinta consultas, no
una lista de diez— y eso obliga a que los intrones sean de primera clase en vez de doce
piezas sueltas dentro de `blocks.PIECES`.

## Los cuatro elementos se DERIVAN; el punto de ramificacion NO es un dato

Donante (`GT`), aceptor (`AG`) y tracto de polipirimidinas salen de la secuencia sin
ambiguedad: se buscan y se comprueban, y si no estan se aborta. El **punto de
ramificacion no**: el motivo `YURAY` es un criterio **declarado como parametro de este
analisis, no una cita**, y en un intron pueden caber varios. Asi que sale como
`CANDIDATO`, con todos los que caben, y cuando no cabe ninguno vale `None` — que no es
«no lo hay», es «no se ha podido señalar ninguno». Es la misma disciplina que el `.out`
sin resumen: no haber podido comprobarlo no es que coincida.

## Los tres estados son distintos y aqui se distinguen

  - `mvm_actual` — **disponible**, ensamblado de piezas versionadas. Nadie lo teclea.
  - `quimerico_cmv_globina` — **no aportado**. Se extrae de un plasmido del laboratorio y
    no se reconstruye de memoria: eso es la errata nº 5 esperando a repetirse, y una
    secuencia plausible es el peor resultado posible de este software (regla 1).
  - `mvm_sin_criptico` — lo **diseña la app**, derivado del primero, con dos criterios
    computables (`intron_design.py`). Es una PROPUESTA, no una construccion aprobada:
    pasa por el mismo modal que las demas antes de ir a sintesis.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .blocks import MODULE_LENGTH, PIECES
from .errors import ShmirDesignError
from .filters import FilterState

#: Por debajo de esto el espliceosoma no ensambla bien. Se aplica a los TRES intrones.
MIN_INTRON_LENGTH = 80

WHY_MIN_LENGTH = (
    f"Un intron por debajo de {MIN_INTRON_LENGTH} nt no deja sitio a que el "
    f"espliceosoma ensamble: el donante, el punto de ramificacion y el aceptor tienen "
    f"que caber con separacion suficiente. DONDE MUERDE DE VERDAD: con el modulo de "
    f"{MODULE_LENGTH} nt dentro este limite es inalcanzable, asi que sobre el intron "
    f"terapeutico no protege de nada — vale para el intron VACIO (el del parental, que "
    f"mide 82 y pasa por dos) y para los intrones que vengan, que pueden ser mucho mas "
    f"cortos que el MVM. Decir que protege algo que no puede pasar seria peor que no "
    f"ponerlo."
)

#: Criterio del punto de ramificacion. DECLARADO como parametro, no citado — igual que
#: `splicing.SPLICE_SITE_CRITERION`, del que sale.
BRANCH_CRITERION = (
    "Punto de ramificacion: motivo YURAY (pirimidina, purina, A, cualquiera, pirimidina) "
    "entre 18 y 40 nt aguas arriba de la A del aceptor. Es un criterio DECLARADO como "
    "parametro de este analisis y NO una cita. Por eso sale como CANDIDATO y nunca como "
    "dato: si caben varios, salen todos y no se elige por nuestra cuenta."
)

BRANCH_WINDOW = (18, 40)

_PYRIMIDINES = frozenset("CT")


class ElementOrigin(StrEnum):
    #: Sale de la secuencia sin ambiguedad: o esta o no esta.
    DERIVADO = "derivado"
    #: Sale de un criterio declarado, y pueden caber varios.
    CANDIDATO = "candidato"


@dataclass(frozen=True)
class SpliceElement:
    """Uno de los cuatro elementos, con su posicion DENTRO del intron (1-based)."""

    name: str
    start: int
    end: int
    sequence: str
    origin: ElementOrigin

    def __post_init__(self) -> None:
        # El invariante de intervalos del proyecto, aqui tambien: una coordenada que no
        # cuadra con la secuencia que describe es el fallo que no da ningun error.
        if self.end - self.start + 1 != len(self.sequence):
            raise ShmirDesignError(
                f"El elemento {self.name!r} declara {self.start}-{self.end} "
                f"({self.end - self.start + 1} nt) y su secuencia mide "
                f"{len(self.sequence)}. Se aborta: coordenadas transcritas en vez de "
                f"derivadas es exactamente el fallo que este invariante existe para cazar."
            )

    def describe(self) -> str:
        marca = "" if self.origin is ElementOrigin.DERIVADO else "  [CANDIDATO]"
        return f"{self.name}: intron:{self.start}-{self.end}  {self.sequence}{marca}"


@dataclass(frozen=True)
class IntronElements:
    """Los cuatro. El punto de ramificacion puede faltar, y eso NO es «no lo hay»."""

    donor: SpliceElement
    ppt: SpliceElement
    acceptor: SpliceElement
    branch_point: SpliceElement | None
    branch_candidates: tuple[SpliceElement, ...]
    length: int

    @property
    def branch_ambiguous(self) -> bool:
        return len(self.branch_candidates) > 1

    def describe(self) -> list[str]:
        lineas = [
            f"Elementos del intron ({self.length} nt), DERIVADOS de la secuencia:",
            f"  {self.donor.describe()}",
            f"  {self.ppt.describe()}   ({len(self.ppt.sequence)} pirimidinas contiguas)",
            f"  {self.acceptor.describe()}",
        ]
        if self.branch_point is None:
            lineas.append(
                "  punto_de_ramificacion: NINGUN candidato en la ventana. No es «no lo "
                "hay»: es que no se ha podido señalar ninguno con este criterio."
            )
        else:
            lineas.append(f"  {self.branch_point.describe()}")
        if self.branch_ambiguous:
            lineas.append(
                f"  ATENCION: caben {len(self.branch_candidates)} candidatos y no se "
                f"elige por nuestra cuenta: "
                + ", ".join(f"intron:{c.start} {c.sequence}" for c in self.branch_candidates)
            )
        lineas.append(f"  {BRANCH_CRITERION}")
        return lineas


def _clean(sequence: str) -> str:
    return "".join(str(sequence).split()).upper()


def check_length(sequence: str, *, name: str) -> int:
    """El suelo de los 80 nt. Devuelve la longitud si pasa; si no, ABORTA."""
    limpio = _clean(sequence)
    if len(limpio) < MIN_INTRON_LENGTH:
        raise ShmirDesignError(
            f"El intron {name!r} montado mide {len(limpio)} nt y el minimo es "
            f"{MIN_INTRON_LENGTH}. Se aborta en vez de emitir una construccion que no se "
            f"puede empalmar. {WHY_MIN_LENGTH}"
        )
    return len(limpio)


def _ppt_length(sequence: str, acceptor_start: int) -> int:
    """Pirimidinas CONTIGUAS aguas arriba del aceptor. Contiguas, no un porcentaje: un
    porcentaje en una ventana diluye y da tractos donde no los hay."""
    n, i = 0, acceptor_start - 2
    while i >= 0 and sequence[i] in _PYRIMIDINES:
        n += 1
        i -= 1
    return n


def _branch_candidates(sequence: str) -> list[tuple[int, str]]:
    salida = []
    a = len(sequence) - 2                      # 0-based de la A del AG final
    for distancia in range(BRANCH_WINDOW[0], BRANCH_WINDOW[1] + 1):
        j = a - distancia
        if j < 0 or j + 5 > len(sequence):
            continue
        motivo = sequence[j:j + 5]
        if (
            motivo[0] in _PYRIMIDINES
            and motivo[1] in "AG"
            and motivo[2] == "A"
            and motivo[4] in _PYRIMIDINES
        ):
            salida.append((j + 1, motivo))
    return salida


def locate_elements(sequence: str, *, name: str) -> IntronElements:
    """Los cuatro elementos, buscados en la secuencia. Ninguno se teclea."""
    limpio = _clean(sequence)
    if len(limpio) < 4:
        raise ShmirDesignError(
            f"{name}: {len(limpio)} nt no dan ni para un donante y un aceptor."
        )
    if limpio[:2] != "GT":
        raise ShmirDesignError(
            f"{name}: el intron empieza por {limpio[:2]!r} y un donante canonico es GT. "
            f"Se aborta en vez de buscar el donante en otro sitio: si esto no empieza por "
            f"GT, o no es un intron o no empieza donde se cree que empieza, y las dos "
            f"cosas invalidan todas las coordenadas de aqui en adelante."
        )
    if limpio[-2:] != "AG":
        raise ShmirDesignError(
            f"{name}: el intron acaba en {limpio[-2:]!r} y un aceptor canonico es AG. "
            f"Se aborta por la misma razon que con el donante."
        )

    aceptor_inicio = len(limpio) - 1           # 1-based de la A del AG
    tracto = _ppt_length(limpio, aceptor_inicio)
    if tracto == 0:
        raise ShmirDesignError(
            f"{name}: no hay ni una pirimidina contigua aguas arriba del aceptor, asi "
            f"que no hay tracto de polipirimidinas. Se aborta: es el elemento contra el "
            f"que se compara todo sitio criptico, y sin el no hay referencia interna."
        )

    candidatos = tuple(
        SpliceElement(
            name="punto_de_ramificacion", start=inicio, end=inicio + 4,
            sequence=motivo, origin=ElementOrigin.CANDIDATO,
        )
        for inicio, motivo in _branch_candidates(limpio)
    )
    return IntronElements(
        donor=SpliceElement(
            name="donante", start=1, end=2, sequence=limpio[:2],
            origin=ElementOrigin.DERIVADO,
        ),
        ppt=SpliceElement(
            name="tracto_polipirimidinas",
            start=aceptor_inicio - tracto,
            end=aceptor_inicio - 1,
            sequence=limpio[aceptor_inicio - 1 - tracto:aceptor_inicio - 1],
            origin=ElementOrigin.DERIVADO,
        ),
        acceptor=SpliceElement(
            name="aceptor", start=aceptor_inicio, end=len(limpio),
            sequence=limpio[-2:], origin=ElementOrigin.DERIVADO,
        ),
        # Si caben varios NO se elige: se deja el primero como representante para poder
        # pintar algo, y `branch_ambiguous` obliga a enseñarlos todos.
        branch_point=candidatos[0] if candidatos else None,
        branch_candidates=candidatos,
        length=len(limpio),
    )


# ───────────────────────────── el registro ─────────────────────────────


@dataclass(frozen=True)
class Intron:
    """Un intron del registro. `provided=False` = no lo tenemos, y se dice."""

    name: str
    description: str
    source: str
    #: Las piezas de `blocks.PIECES` que van antes y despues del modulo. Vacio si el
    #: intron no se ensambla de piezas (los aportados llegan enteros).
    five_piece: str = ""
    three_piece: str = ""
    #: La secuencia entera, para los aportados. Vacia si no se ha aportado.
    raw_sequence: str = ""
    provided: bool = True
    #: `True` si lo DISEÑA la app en vez de venir de fuera.
    derived: bool = False
    derived_from: str = ""
    why_missing: str = ""
    ficha: str = ""
    #: Contexto exonico declarado a los dos lados, tambien de piezas versionadas.
    exon5_piece: str = ""
    exon3_piece: str = ""

    @property
    def state(self) -> FilterState:
        return FilterState.PASS if self.provided else FilterState.NOT_RUN

    @property
    def empty_sequence(self) -> str:
        """El intron SIN modulo: el del casete parental."""
        if self.raw_sequence:
            return _clean(self.raw_sequence)
        return (
            PIECES[self.five_piece].sequence + PIECES[self.three_piece].sequence
        )

    def require_sequence(self) -> str:
        if self.provided:
            return self.empty_sequence
        raise ShmirDesignError(
            f"El intron {self.name!r} no se ha aportado. {self.why_missing} "
            f"NO se reconstruye ni se teclea de memoria (regla 1): una secuencia "
            f"plausible es el peor resultado posible de este software."
        )

    def with_module(self, module: str, *, spacer5: str = "", spacer3: str = "") -> str:
        """El intron con el modulo dentro. Es lo que se pliega y lo que se consulta."""
        if not self.provided:
            self.require_sequence()
        if self.raw_sequence:
            raise ShmirDesignError(
                f"El intron {self.name!r} llego entero, asi que no se sabe DONDE va el "
                f"modulo dentro. Hace falta declarar sus puntos de insercion antes de "
                f"montarlo; se aborta en vez de pegarlo en un sitio cualquiera."
            )
        montado = (
            PIECES[self.five_piece].sequence
            + (spacer5 or PIECES["espaciador5"].sequence)
            + _clean(module)
            + (spacer3 or PIECES["espaciador3"].sequence)
            + PIECES[self.three_piece].sequence
        )
        check_length(montado, name=self.name)
        return montado

    def elements(self, module: str = "") -> IntronElements:
        secuencia = self.with_module(module) if module else self.empty_sequence
        return locate_elements(secuencia, name=self.name)


_ERRATA = (
    "Se extrae de un plasmido comercial que lo lleve (familia pAAV-MCS y equivalentes), "
    "preferiblemente de un `.dna` de SnapGene o un `.gb` del laboratorio. NADIE lo teclea "
    "ni lo reconstruye de memoria: eso es la errata nº 5 del registro esperando a "
    "repetirse — un 3'UTR anunciado como «1242 nt verificados» que traia 1246 dejo "
    "inservible una corrida entera. Al cargarlo, la app localiza donante, punto de "
    "ramificacion, tracto de polipirimidinas y aceptor POR SECUENCIA y los declara."
)

INTRONS: dict[str, Intron] = {
    "mvm_actual": Intron(
        name="mvm_actual",
        description=(
            "El intron MVM del casete de hoy. Se ensambla de piezas versionadas: nadie "
            "lo teclea."
        ),
        source="blocks.PIECES (plasmido receptor)",
        five_piece="MVM5",
        three_piece="MVM3",
        exon5_piece="exon5",
        exon3_piece="exon3",
        provided=True,
    ),
    "quimerico_cmv_globina": Intron(
        name="quimerico_cmv_globina",
        description=(
            "Intron quimerico CMV / beta-globina, el de la familia pAAV-MCS. NO lo "
            "tenemos."
        ),
        source="plasmido comercial del laboratorio",
        provided=False,
        why_missing=_ERRATA,
        ficha="intron_quimerico",
    ),
    "mvm_sin_criptico": Intron(
        name="mvm_sin_criptico",
        description=(
            "Variante del MVM con el donante criptico del flanco 5' de miR-E roto y "
            "espaciadores nuevos de 20-30 nt. Lo DISEÑA la app derivandolo del actual, "
            "con dos criterios computables. Es una PROPUESTA, no una construccion "
            "aprobada: pasa por el mismo modal que las demas antes de ir a sintesis."
        ),
        source="derivado de mvm_actual por `intron_design.py`",
        five_piece="MVM5",
        three_piece="MVM3",
        exon5_piece="exon5",
        exon3_piece="exon3",
        provided=False,
        derived=True,
        derived_from="mvm_actual",
        why_missing=(
            "Todavia no se ha diseñado en esta corrida. Se genera con "
            "`intron_design.design_variant()`, que necesita el 97-mero del candidato "
            "para poder aplicar el criterio estructural."
        ),
        ficha="intron_sin_criptico",
    ),
}


def get(name: str) -> Intron:
    intron = INTRONS.get(name)
    if intron is None:
        raise ShmirDesignError(
            f"No hay ningun intron {name!r} en el registro; los que hay: "
            f"{', '.join(sorted(INTRONS))}."
        )
    return intron


def available() -> tuple[Intron, ...]:
    return tuple(i for i in INTRONS.values() if i.provided)


def missing() -> tuple[Intron, ...]:
    """Los que faltan. Salen SIEMPRE, con NOT_RUN visible: un intron que no se ve no
    existe, y esa es la leccion de `offtarget_seed`."""
    return tuple(i for i in INTRONS.values() if not i.provided)
