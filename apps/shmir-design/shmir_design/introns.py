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
  - `intron_quimerico` — **aportado**. Se EXTRAE por su anotacion del plasmido y
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
from .filters import FilterResult, FilterState

#: Por debajo de esto el espliceosoma no ensambla bien. Se aplica a los TRES intrones.
MIN_INTRON_LENGTH = 80

WHY_MIN_LENGTH = (
    f"Un intrón por debajo de {MIN_INTRON_LENGTH} nt no deja sitio a que el "
    f"espliceosoma ensamble: el donante, el punto de ramificacion y el aceptor tienen "
    f"que caber con separación suficiente. DONDE MUERDE DE VERDAD: con el módulo de "
    f"{MODULE_LENGTH} nt dentro este límite es inalcanzable, así que sobre el intrón "
    f"terapeutico no protege de nada — vale para el intrón VACÍO (el del parental, que "
    f"mide 82 y pasa por dos) y para los intrones que vengan, que pueden ser mucho más "
    f"cortos que el MVM. Decir que protege algo que no puede pasar sería peor que no "
    f"ponerlo."
)

#: Criterio del punto de ramificacion. DECLARADO como parametro, no citado — igual que
#: `splicing.SPLICE_SITE_CRITERION`, del que sale.
BRANCH_CRITERION = (
    "Punto de ramificacion: motivo YTNAY (pirimidina, T, cualquiera, A, pirimidina) con "
    "la A DE RAMIFICACION entre 18 y 40 nt aguas arriba de la A del aceptor. Es una "
    "CONVENCIÓN DECLARADA de este análisis y NO una cita, pero está CALIBRADA: se eligió "
    "por recuperar los casos conocidos de los dos intrones del registro, no por "
    "preferencia. Sale como CANDIDATO y nunca como dato, y salen TODOS los que caben con "
    "su posición y su distancia: el punto real puede no ser el que más se parece al "
    "consenso."
)

#: LA CALIBRACION, que es la justificacion (`tests/test_calibracion_ramificacion.py`).
#: Ninguno de los motivos que se barajaron tiene literatura citada detras, asi que elegir
#: «el que ya estaba» habria sido una preferencia entre cadenas que nadie puede citar. El
#: criterio comprobable es que RECUPERE LOS CASOS CONOCIDOS y siga discriminando. Con la
#: ventana 18-40 sobre la A DE RAMIFICACION —el ancla importa: la A esta en la posicion 3
#: de YURAY, la 4 de YTNAY y la 6 de YNYURAY, asi que anclar en el inicio del motivo mide
#: una cosa distinta en cada uno, que es el mismo fallo de marco del mapa del 3'UTR—:
#:
#:   motivo          MVM   quimerico   ¿recupera CTGAC?   ¿discrimina?
#:   YURAY            1        0             NO           si, pero pierde el caso conocido
#:   YTNAY            1        2             SI           SI          ← elegido
#:   YNYURAY          0        1             SI           pierde el MVM entero
#:   A+pirimidina     3        5             SI           NO, demasiado laxo
#:
#: `CTGAC` es el punto de ramificacion canonico de mamifero y esta en el quimerico: un
#: motivo que lo pierde esta mal calibrado por definicion. Lo conservado de verdad es la A
#: con una pirimidina detras; la posicion 2 varia, y exigir purina ahi —que es lo que hace
#: YURAY— descarta el ejemplo de manual. Entre los que valen se coge el MAS LAXO: perder
#: un punto real cuesta mas que emitir uno de mas, porque los de mas SE VEN.
#:
#: Y una convergencia que da confianza en el 107: los TRES motivos que ven algo en el
#: quimerico lo ponen en la misma A.
WHY_YTNAY_CALIBRADO = (
    "El motivo se eligió por CALIBRACIÓN y no por preferencia: de los cuatro probados "
    "(YURAY, YTNAY, YNYURAY y el mínimo A+pirimidina), YTNAY es el único que recupera el "
    "punto conocido de los DOS intrones —incluido CTGAC, el canónico de mamífero— sin "
    "dejar de discriminar. YURAY pierde CTGAC; YNYURAY pierde el MVM entero; el mínimo "
    "devuelve cinco candidatos en un intrón de 133 pb. La prueba entera corre en "
    "`tests/test_calibracion_ramificacion.py`."
)

BRANCH_WINDOW = (18, 40)

#: La A de ramificacion dentro del motivo YTNAY (0-based): Y-T-N-**A**-Y.
BRANCH_A_OFFSET = 3

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
    #: Solo para el punto de ramificacion: la A que ramifica y su distancia a la A
    #: del aceptor. Van en el elemento y no se recalculan fuera, que es donde se
    #: pierden — y donde se recalculan con el marco equivocado.
    branch_a: int | None = None
    to_acceptor: int | None = None

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
        detalle = ""
        if self.branch_a is not None:
            detalle = f"  A en intrón:{self.branch_a}, a {self.to_acceptor} nt del aceptor"
        return (
            f"{self.name}: intrón:{self.start}-{self.end}  {self.sequence}{marca}"
            f"{detalle}"
        )


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

    @property
    def branch_to_acceptor_range(self) -> tuple[int, int] | None:
        """Punto→aceptor como INTERVALO. `None` si no hay ningún candidato.

        Con varios candidatos no hay «el» número: hay un rango, y darlo como número
        sería elegir uno. Con uno solo el intervalo es de un punto, que también es la
        respuesta honesta — no se colapsa a escalar para que parezca más firme.
        """
        distancias = [
            c.to_acceptor for c in self.branch_candidates if c.to_acceptor is not None
        ]
        if not distancias:
            return None
        return (min(distancias), max(distancias))

    def describe(self) -> list[str]:
        lineas = [
            f"Elementos del intrón ({self.length} nt), DERIVADOS de la secuencia:",
            f"  {self.donor.describe()}",
            f"  {self.ppt.describe()}   ({len(self.ppt.sequence)} pirimidinas contiguas)",
            f"  {self.acceptor.describe()}",
        ]
        if self.branch_point is None:
            lineas.append(
                "  punto_de_ramificacion: NINGÚN candidato en la ventana. No es «no lo "
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
        rango = self.branch_to_acceptor_range
        if rango is not None:
            if rango[0] == rango[1]:
                lineas.append(f"  punto→aceptor: {rango[0]} nt")
            else:
                lineas.append(
                    f"  punto→aceptor: {rango[0]}-{rango[1]} nt (INTERVALO: hay "
                    f"{len(self.branch_candidates)} candidatos y no se elige uno)"
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
            f"El intrón {name!r} montado mide {len(limpio)} nt y el mínimo es "
            f"{MIN_INTRON_LENGTH}. Se aborta en vez de emitir una construcción que no se "
            f"puede empalmar. {WHY_MIN_LENGTH}"
        )
    return len(limpio)


#: Hasta donde se busca el tracto, aguas arriba de la A del aceptor.
PPT_WINDOW = 40

PPT_CRITERION = (
    "Tracto de polipirimidinas: la racha de pirimidinas CONTIGUAS más larga en los "
    f"{PPT_WINDOW} nt de delante de la A del aceptor. Contiguas y no un porcentaje: un "
    "porcentaje en una ventana diluye y da tractos donde no los hay. El HUECO hasta el "
    "aceptor se emite: no tiene por qué ser cero."
)

#: POR QUÉ LA RACHA MÁS LARGA Y NO LA QUE PEGA CON EL ACEPTOR (2026-08-27). La regla
#: anterior contaba pirimidinas hacia atrás DESDE el aceptor y paraba en la primera
#: purina. Funciona en el MVM, donde el tracto pega con el AG, y se rompe en el
#: quimérico, donde hay un `AC` en medio: devolvía un tracto de UNA base.
#:
#:   · MVM (82 nt)        racha 72-80,  9 nt, hueco 0 al aceptor
#:   · quimérico (133 pb) racha 119-129, 11 nt, hueco 2 al aceptor
#:
#: Las dos coinciden con lo declarado. La regla vieja no estaba «casi bien»: daba un
#: tracto de 1 nt sin ningún error, y un tracto de 1 nt es un intrón que no empalma.
WHY_LONGEST_RUN = (
    "El tracto es la racha contigua más larga de la ventana, no la que toca el aceptor: "
    "en el intrón quimérico hay un AC entre el tracto y el AG, y la regla anterior "
    "devolvía un tracto de UNA base sin dar ningún error. Medido en los dos intrones."
)


def _ppt_span(sequence: str, acceptor_start: int) -> tuple[int, int]:
    """La racha de pirimidinas mas larga de la ventana. Devuelve (inicio, fin) 1-based.

    Ver `PPT_CRITERION` y `WHY_LONGEST_RUN`. Ante empate gana la MAS CERCANA al
    aceptor, que es la que un espliceosoma usaria: elegir la primera por orden de
    lectura seria elegir por el orden del bucle.
    """
    fin_ventana = acceptor_start - 1              # 0-based, exclusivo
    inicio_ventana = max(0, fin_ventana - PPT_WINDOW)
    mejor = (0, 0, 0)                              # (largo, inicio, fin) 0-based
    i = inicio_ventana
    while i < fin_ventana:
        if sequence[i] not in _PYRIMIDINES:
            i += 1
            continue
        j = i
        while j < fin_ventana and sequence[j] in _PYRIMIDINES:
            j += 1
        if j - i >= mejor[0]:                      # >= : ante empate, la mas cercana
            mejor = (j - i, i, j)
        i = j
    if mejor[0] == 0:
        return (acceptor_start - 1, acceptor_start - 2)   # vacio
    return (mejor[1] + 1, mejor[2])


def _branch_candidates(sequence: str) -> list[tuple[int, str]]:
    """Todos los candidatos, con la ventana sobre la A DE RAMIFICACION.

    Anclar en la A y no en el inicio del motivo no es un detalle: la A cae en una
    posicion distinta en cada motivo, asi que una ventana sobre el inicio mide una cosa
    distinta en cada uno y los hace incomparables. Ver `BRANCH_CRITERION`.
    """
    salida = []
    a_aceptor = len(sequence) - 1              # 1-based de la A del AG final
    for inicio in range(1, len(sequence) - 4):
        motivo = sequence[inicio - 1:inicio + 4]
        if len(motivo) < 5:
            continue
        # YTNAY: pirimidina, T, cualquiera, A, pirimidina. Ver `WHY_YTNAY_CALIBRADO`.
        if not (
            motivo[0] in _PYRIMIDINES
            and motivo[1] == "T"
            and motivo[3] == "A"
            and motivo[4] in _PYRIMIDINES
        ):
            continue
        distancia = a_aceptor - (inicio + BRANCH_A_OFFSET)
        if BRANCH_WINDOW[0] <= distancia <= BRANCH_WINDOW[1]:
            salida.append((inicio, motivo))
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
            f"{name}: el intrón empieza por {limpio[:2]!r} y un donante canónico es GT. "
            f"Se aborta en vez de buscar el donante en otro sitio: si esto no empieza por "
            f"GT, o no es un intrón o no empieza donde se cree que empieza, y las dos "
            f"cosas invalidan todas las coordenadas de aquí en adelante."
        )
    if limpio[-2:] != "AG":
        raise ShmirDesignError(
            f"{name}: el intrón acaba en {limpio[-2:]!r} y un aceptor canónico es AG. "
            f"Se aborta por la misma razón que con el donante."
        )

    aceptor_inicio = len(limpio) - 1           # 1-based de la A del AG
    ppt_ini, ppt_fin = _ppt_span(limpio, aceptor_inicio)
    tracto = ppt_fin - ppt_ini + 1
    if tracto <= 0:
        raise ShmirDesignError(
            f"{name}: no hay ni una pirimidina contigua aguas arriba del aceptor, así "
            f"que no hay tracto de polipirimidinas. Se aborta: es el elemento contra el "
            f"que se compara todo sitio críptico, y sin el no hay referencia interna."
        )

    candidatos = tuple(
        SpliceElement(
            name="punto_de_ramificacion", start=inicio, end=inicio + 4,
            sequence=motivo, origin=ElementOrigin.CANDIDATO,
            branch_a=inicio + BRANCH_A_OFFSET,
            to_acceptor=aceptor_inicio - (inicio + BRANCH_A_OFFSET),
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
            start=ppt_ini,
            end=ppt_fin,
            sequence=limpio[ppt_ini - 1:ppt_fin],
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
class IntronPiece:
    """Una pieza del intrón montado, con su longitud y de dónde sale."""

    name: str
    length: int
    origin: str
    #: `True` si la generamos nosotros. En el total pesa igual que una del plásmido, y
    #: no vale lo mismo: por eso va marcada.
    de_novo: bool = False

    def describe(self) -> str:
        marca = "  ← DE NOVO" if self.de_novo else ""
        return f"{self.name:<14} {self.length:>4} nt   {self.origin}{marca}"


@dataclass(frozen=True)
class IntronBreakdown:
    """El intrón montado descompuesto. Un total que nadie puede descomponer no vale."""

    intron: str
    pieces: tuple[IntronPiece, ...]
    empty_length: int
    module_length: int

    @property
    def total(self) -> int:
        return sum(p.length for p in self.pieces)

    @property
    def de_novo_length(self) -> int:
        return sum(p.length for p in self.pieces if p.de_novo)

    def describe(self) -> list[str]:
        lineas = [
            f"Intrón «{self.intron}» montado, del donante al aceptor:",
            *(f"  {p.describe()}" for p in self.pieces),
            f"  {'TOTAL':<14} {self.total:>4} nt",
            "",
            "La resta que no cuadraba:",
            f"  intrón vacío                {self.empty_length:>4} nt",
            f"  módulo                      {self.module_length:>4} nt",
            f"  vacío + módulo              {self.empty_length + self.module_length:>4} nt",
            f"  espaciadores DE NOVO        {self.de_novo_length:>4} nt   ← la diferencia",
            f"  total                       {self.total:>4} nt",
        ]
        if self.de_novo_length:
            lineas.append(
                "  Los espaciadores YA ESTÁN en la construcción de hoy y son diseño de "
                "novo. Unos nuevos los SUSTITUYEN (`spacers.choose_spacers` reemplaza "
                "los estándar), no se suman a ellos."
            )
        return lineas


def intron_breakdown(intron: str, *, module_length: int) -> IntronBreakdown:
    """Descompone el intrón montado pieza a pieza. Ver `IntronBreakdown`."""
    from . import blocks  # noqa: PLC0415

    entrada = INTRONS.get(intron)
    if entrada is None:
        raise ShmirDesignError(
            f"No hay ningún intrón {intron!r} en el registro; los que hay son "
            f"{', '.join(sorted(INTRONS))}. Se aborta en vez de descomponer otro."
        )
    if not entrada.five_piece or not entrada.three_piece:
        raise ShmirDesignError(
            f"El intrón {intron!r} no se ensambla de piezas versionadas "
            f"({entrada.source}), así que no hay desglose que emitir: lo que se puede "
            f"decir de él sale de su SECUENCIA, no de un inventario de trozos."
        )

    piezas = blocks.PIECES

    def _pieza(nombre: str, *, de_novo: bool = False) -> IntronPiece:
        pieza = piezas[nombre]
        return IntronPiece(
            name=nombre, length=len(pieza.sequence),
            origin=pieza.source, de_novo=de_novo,
        )

    lista = (
        _pieza(entrada.five_piece),
        _pieza("espaciador5", de_novo=True),
        IntronPiece(
            name="módulo", length=int(module_length),
            origin="NheI + contexto5 + 97-mero + contexto3 + SacI",
        ),
        _pieza("espaciador3", de_novo=True),
        _pieza(entrada.three_piece),
    )
    return IntronBreakdown(
        intron=intron, pieces=lista,
        empty_length=len(entrada.empty_sequence),
        module_length=int(module_length),
    )


#: Las DOS restricciones declaradas para el sitio de inserción, y no hay más. No se
#: añade ningún mínimo de distancia —«el punto de ramificación a más de N nt del
#: aceptor»— porque nadie lo ha autorizado: un criterio que aparece sin haberse
#: discutido acaba emitiendo veredictos que nadie pidió (ver `docs/procedencia-g4.md`).
#: Lo que se emite son DISTANCIAS, que son un hecho; la decisión se toma mirándolas.
#: RANGO TIPICO de donante→punto de ramificacion en intrones de mamifero. Es CONTEXTO,
#: NO un filtro: no excluye a nadie y no emite veredicto. Se declara como convencion —
#: igual que el motivo— y esta aqui porque es un limite que NINGUNO de los otros dos
#: numeros captura: la ventana de insercion dice que el modulo CABE, y punto→aceptor dice
#: que esa separacion se conserva, pero ninguno de los dos ve que el modulo empuja el
#: punto de ramificacion a cientos de nucleotidos del donante.
TYPICAL_DONOR_TO_BRANCH = (18, 100)

DONOR_TO_BRANCH_CONTEXT = (
    "Que quepa geométricamente NO significa que empalme. Con el módulo y los "
    "espaciadores intercalados, la separación donante→punto de ramificación queda muy "
    "por encima del rango habitual en intrones de mamífero. Es una geometría ATÍPICA, y "
    "esto NO es un filtro: es contexto que hay que tener delante al leer el resultado, "
    "porque si las tres opciones fallan, ésta puede ser la razón común. Sólo el gel lo "
    "resuelve."
)

#: LINEA ABIERTA, anotada para que no se pierda: si donante→punto ES el problema, la
#: solucion NO es otro intron. Es (a) un MODULO MAS CORTO, o (b) insertar la horquilla en
#: un intron cuyo punto de ramificacion este MAS LEJOS DEL DONANTE de partida — que es
#: justo lo contrario de lo que parece: el quimerico tiene el punto a 100-104 del donante
#: frente a los 42 del MVM, asi que en este eje es PEOR, no mejor. Buscar «un intron mas
#: largo» empeora este numero si la longitud de mas esta antes del punto.
#: LA INVERSION, con las palabras del responsable del proyecto (2026-08-27): «sus 51 pb
#: de mas estan donde estorban y el argumento que le di era falso». El quimerico se
#: propuso, entre otras cosas, por ser mas largo — y en el eje donante→punto ser mas largo
#: es PEOR, porque su punto de ramificacion ya esta de partida a 100-104 nt del donante
#: frente a los 42 del MVM.
#:
#: NO LO DESCARTA, y eso es igual de importante: mejor donante (GTAAGT, consenso
#: perfecto), mejor tracto (11 pirimidinas frente a 9) y 97 posiciones de insercion frente
#: a 39. Lo que significa es que LOS TRES SON MEJORES EN EJES DISTINTOS y que NINGUNO DE
#: LOS TRES NUMEROS PREDICE EL EMPALME. Las tres opciones van a sintesis; el gel decide.
THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES = (
    "Los 51 pb de más del quimérico están donde estorban: en el eje donante→punto es "
    "PEOR que el MVM, no mejor. No lo descarta —mejor donante, mejor tracto, 97 "
    "posiciones de inserción frente a 39— pero significa que los tres son mejores en "
    "ejes distintos y que ninguno de los tres números predice el empalme. Las tres "
    "opciones van a síntesis; el gel decide."
)

OPEN_QUESTION_DONOR_TO_BRANCH = (
    "Si donante→punto resulta ser el problema, la salida no es cambiar de intrón sino "
    "acortar el módulo o buscar un intrón cuyo punto de ramificación esté más cerca del "
    "donante de partida. Un intrón más largo NO ayuda si la longitud de más está aguas "
    "arriba del punto: el quimérico tiene el punto a 100-104 nt del donante y el MVM a "
    "42, así que en este eje el quimérico es peor."
)


@dataclass(frozen=True)
class DonorToBranch:
    """La separacion donante→punto con el modulo dentro, y si esta fuera de rango."""

    intron: str
    empty: tuple[int, int]
    assembled: tuple[int, int]
    inserted: int

    @property
    def atypical(self) -> bool:
        return self.assembled[0] > TYPICAL_DONOR_TO_BRANCH[1]

    def describe(self) -> list[str]:
        def rango(par):
            return f"{par[0]} nt" if par[0] == par[1] else f"{par[0]}-{par[1]} nt"

        marca = "  ⚠ FUERA DEL RANGO TÍPICO" if self.atypical else ""
        return [
            f"{self.intron}: donante→punto {rango(self.empty)} en el intrón vacío, "
            f"{rango(self.assembled)} con los {self.inserted} nt intercalados{marca}",
            f"    rango habitual en mamífero: {TYPICAL_DONOR_TO_BRANCH[0]}-"
            f"{TYPICAL_DONOR_TO_BRANCH[1]} nt (convención declarada, no cita)",
        ]


def donor_to_branch(
    elements: IntronElements, *, name: str, inserted: int
) -> DonorToBranch | None:
    """Donante→punto con el modulo dentro. `None` sin candidatos: no se inventa."""
    distancias = [
        c.branch_a - elements.donor.end - 1
        for c in elements.branch_candidates
        if c.branch_a is not None
    ]
    if not distancias:
        return None
    vacio = (min(distancias), max(distancias))
    return DonorToBranch(
        intron=name, empty=vacio,
        assembled=(vacio[0] + inserted, vacio[1] + inserted),
        inserted=int(inserted),
    )


INSERTION_RULE = (
    "El módulo va entre el DONANTE y el TRACTO DE POLIPIRIMIDINAS, no invade ningún "
    "candidato a punto de ramificación, y va SIEMPRE aguas arriba del punto. Son las "
    "tres restricciones declaradas: las distancias se emiten para decidir, no se "
    "convierten en umbral por su cuenta."
)

#: LA TERCERA RESTRICCION, y por que es una regla y no una observacion. Insertar aguas
#: ABAJO del punto de ramificacion mete el modulo entre el punto y el aceptor, y esa
#: separacion es la que NO se puede estirar: en el MVM son 33 nt y pasarian a 182. Hoy la
#: construccion inserta aguas arriba, asi que se cumplia — pero por donde cae el corte,
#: no porque nada lo impidiera. Una consecuencia no impide nada.
MODULE_UPSTREAM_RULE = (
    "El módulo va SIEMPRE aguas arriba del punto de ramificación. Aguas abajo quedaría "
    "entre el punto y el aceptor, que es la separación que no se puede estirar."
)

#: Y lo que pasa cuando NO HAY candidato: la regla no se puede comprobar. No es que se
#: cumpla — es que no se sabe, y eso es `NOT_RUN` y no `PASS`. Le pasa hoy al intrón
#: quimérico con la convención `YURAY` (ver `WHY_ONE_CRITERION`).
MODULE_UPSTREAM_UNCHECKABLE = (
    "Sin ningún candidato a punto de ramificación, NO se puede comprobar que el módulo "
    "vaya aguas arriba de él. NOT_RUN, no PASS: la regla queda sin verificar y el sitio "
    "de inserción se elige a ciegas en ese eje."
)


def check_module_upstream(elements: IntronElements, *, after: int) -> FilterResult:
    """¿Va el módulo aguas arriba del punto? ABORTA si no. Ver `MODULE_UPSTREAM_RULE`.

    Sin candidatos devuelve `NOT_RUN` en vez de `PASS`: no haber podido comprobarlo no
    es que se cumpla, que es la regla 3 aplicada a la geometría en vez de a un filtro.
    """
    if not elements.branch_candidates:
        return FilterResult(
            name="modulo_aguas_arriba",
            state=FilterState.NOT_RUN,
            reason=MODULE_UPSTREAM_UNCHECKABLE,
        )
    primero = min(c.start for c in elements.branch_candidates)
    if after >= primero:
        raise ShmirDesignError(
            f"El módulo se insertaría tras intrón:{after}, y el primer candidato a "
            f"punto de ramificación empieza en intrón:{primero}: quedaría AGUAS ABAJO. "
            f"{MODULE_UPSTREAM_RULE} Se aborta en vez de montar una construcción que "
            f"estira la separación punto→aceptor."
        )
    return FilterResult(
        name="modulo_aguas_arriba",
        state=FilterState.PASS,
        reason=(
            f"El módulo va tras intrón:{after} y el primer candidato empieza en "
            f"intrón:{primero}: aguas arriba, como exige la regla."
        ),
    )


@dataclass(frozen=True)
class BranchDistance:
    """Distancia a UN candidato a punto de ramificación, con su lado.

    Hay que separar DOS cosas que es facil confundir, y confundirlas da un numero que
    parece razonable y no lo es:

    - `nt` es el hueco entre EL MODULO y el candidato. El modulo se intercala en ese
      hueco y lo parte; no lo alarga. Este numero NO cambia al insertar.
    - `donor_to_branch` es la separacion DONANTE → CANDIDATO en el intron YA MONTADO.
      Ese si crece con la longitud del modulo, y solo si el modulo cae en medio. Es el
      que importa: un punto de ramificacion empujado 149 nt lejos del donante es otra
      geometria de empalme.
    """

    candidate: str
    start: int
    side: str
    #: Hueco entre el modulo y el candidato. No cambia al insertar: el modulo lo parte.
    nt: int
    #: Separacion donante → candidato en el intron montado, con el modulo dentro.
    donor_to_branch: int
    #: Separacion candidato → aceptor en el intron montado.
    branch_to_acceptor: int

    def describe(self) -> str:
        return (
            f"{self.candidate} (intrón:{self.start}) {self.side} a {self.nt} nt del "
            f"módulo; montado: donante→punto {self.donor_to_branch} nt, "
            f"punto→aceptor {self.branch_to_acceptor} nt"
        )


@dataclass(frozen=True)
class InsertionOption:
    """Insertar TRAS esta posición del intrón vacío, y lo que queda a cada lado."""

    after: int
    to_donor: int
    to_ppt: int
    to_acceptor: int
    to_branch: tuple[BranchDistance, ...]

    def describe(self) -> str:
        ramas = "; ".join(d.describe() for d in self.to_branch) or "sin candidatos"
        return (
            f"tras intrón:{self.after} — donante a {self.to_donor} nt, tracto a "
            f"{self.to_ppt} nt, aceptor a {self.to_acceptor} nt · {ramas}"
        )


@dataclass(frozen=True)
class InsertionWindow:
    """Los tramos admisibles y cada opción con sus distancias."""

    ranges: tuple[tuple[int, int], ...]
    options: tuple[InsertionOption, ...]
    module_length: int
    blocked_by_branch: tuple[tuple[int, int], ...]

    def describe(self) -> list[str]:
        lineas = [
            f"Sitios de inserción admisibles para un módulo de {self.module_length} nt:",
        ]
        for inicio, fin in self.ranges:
            cuantas = fin - inicio + 1
            lineas.append(f"  intrón:{inicio}-{fin}  ({cuantas} posición(es))")
            for extremo in (inicio, fin) if inicio != fin else (inicio,):
                opcion = next(o for o in self.options if o.after == extremo)
                lineas.append(f"    {opcion.describe()}")
        for inicio, fin in self.blocked_by_branch:
            lineas.append(
                f"  EXCLUIDO intrón:{inicio}-{fin} — candidato a punto de ramificación."
            )
        lineas.append(f"  {INSERTION_RULE}")
        lineas.append(
            "  Los extremos de cada tramo van arriba; el resto de posiciones están en "
            "`options`. Si hay varios candidatos a punto de ramificación, la distancia "
            "sale POR CANDIDATO y no se elige uno."
        )
        return lineas


def insertion_window(
    elements: IntronElements, *, module_length: int
) -> InsertionWindow:
    """Dónde cabe el módulo dentro del intrón. Ver `INSERTION_RULE`.

    `after` es la posición del intrón VACÍO tras la cual se intercala el módulo, en
    coordenadas del intrón (1-based). Las distancias se dan en el intrón vacío y, para
    el punto de ramificación, también con el módulo dentro: intercalar 149 nt entre el
    donante y el punto los separa 149 nt más, y eso es lo que hay que poder mirar.
    """
    if module_length < 1:
        raise ShmirDesignError(
            f"Un módulo de {module_length} nt no se inserta en ningún sitio; se aborta "
            f"en vez de calcular una ventana sobre una longitud que no existe."
        )

    primera = elements.donor.end + 1
    ultima = elements.ppt.start - 1
    if ultima < primera:
        raise ShmirDesignError(
            f"Entre el donante (acaba en intrón:{elements.donor.end}) y el tracto de "
            f"polipirimidinas (empieza en intrón:{elements.ppt.start}) no queda ni una "
            f"posición para el módulo. {INSERTION_RULE}"
        )

    prohibidas = {
        p
        for c in elements.branch_candidates
        for p in range(c.start, c.end + 1)
    }
    admisibles = [p for p in range(primera, ultima + 1) if p not in prohibidas]
    # TERCERA RESTRICCION, declarada: el modulo va SIEMPRE aguas arriba del punto de
    # ramificacion. Hasta hoy era una CONSECUENCIA de donde se insertaba, no una regla —
    # y una consecuencia no impide nada. Ver `MODULE_UPSTREAM_RULE`.
    if elements.branch_candidates:
        primer_candidato = min(c.start for c in elements.branch_candidates)
        admisibles = [p for p in admisibles if p < primer_candidato]
    if not admisibles:
        raise ShmirDesignError(
            f"Entre el donante (intrón:{elements.donor.end}) y el tracto "
            f"(intrón:{elements.ppt.start}) todas las posiciones caen dentro de un "
            f"candidato a punto de ramificación. {INSERTION_RULE}"
        )

    tramos: list[tuple[int, int]] = []
    for posicion in admisibles:
        if tramos and posicion == tramos[-1][1] + 1:
            tramos[-1] = (tramos[-1][0], posicion)
        else:
            tramos.append((posicion, posicion))

    bloqueados = tuple(
        (c.start, c.end)
        for c in elements.branch_candidates
        if primera <= c.end and c.start <= ultima
    )

    opciones = tuple(
        InsertionOption(
            after=posicion,
            to_donor=posicion - elements.donor.end,
            to_ppt=elements.ppt.start - 1 - posicion,
            to_acceptor=elements.acceptor.start - 1 - posicion,
            to_branch=tuple(
                _branch_distance(posicion, c, module_length, elements)
                for c in elements.branch_candidates
            ),
        )
        for posicion in admisibles
    )

    return InsertionWindow(
        ranges=tuple(tramos),
        options=opciones,
        module_length=int(module_length),
        blocked_by_branch=bloqueados,
    )


def _branch_distance(
    after: int, candidate, module_length: int, elements: IntronElements
) -> BranchDistance:
    """La distancia a UN candidato, con la geometria del intron YA MONTADO.

    El modulo NO alarga el hueco en el que cae: lo parte. Lo que alarga son las
    separaciones ELEMENTO A ELEMENTO que lo cruzan. Confundir las dos da un numero
    plausible y equivocado — pasó al escribir el primer test de esto.
    """
    # Las dos separaciones se miden SOBRE LA A DE RAMIFICACION, que es el punto que
    # importa, y no sobre los extremos del motivo. Medir una sobre el inicio y otra
    # sobre el final del motivo daba dos numeros que no se pueden sumar — la misma
    # confusion de marco que el ancla de la ventana.
    a = candidate.branch_a if candidate.branch_a is not None else candidate.start
    donante_a_punto = a - elements.donor.end - 1
    punto_a_aceptor = elements.acceptor.start - a

    if after < candidate.start:
        # El modulo queda ENTRE el donante y el candidato: alarga esa separacion.
        return BranchDistance(
            candidate=candidate.sequence, start=candidate.start, side="aguas arriba",
            nt=candidate.start - after - 1,
            donor_to_branch=donante_a_punto + module_length,
            branch_to_acceptor=punto_a_aceptor,
        )
    # El modulo queda entre el candidato y el aceptor: alarga LA OTRA.
    return BranchDistance(
        candidate=candidate.sequence, start=candidate.start, side="aguas abajo",
        nt=after - candidate.end,
        donor_to_branch=donante_a_punto,
        branch_to_acceptor=punto_a_aceptor + module_length,
    )


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
            f"El intrón {self.name!r} no se ha aportado. {self.why_missing} "
            f"NO se reconstruye ni se teclea de memoria (regla 1): una secuencia "
            f"plausible es el peor resultado posible de este software."
        )

    def with_module(self, module: str, *, spacer5: str = "", spacer3: str = "") -> str:
        """El intron con el modulo dentro. Es lo que se pliega y lo que se consulta."""
        if not self.provided:
            self.require_sequence()
        if self.raw_sequence:
            raise ShmirDesignError(
                f"El intrón {self.name!r} llego entero, así que no se sabe DONDE va el "
                f"módulo dentro. Hace falta declarar sus puntos de inserción antes de "
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
    "Se extrae de un plásmido comercial que lo lleve (familia pAAV-MCS y equivalentes), "
    "preferiblemente de un `.dna` de SnapGene o un `.gb` del laboratorio. NADIE lo teclea "
    "ni lo reconstruye de memoria: eso es la errata nº 5 del registro esperando a "
    "repetirse — un 3'UTR anunciado como «1242 nt verificados» que traia 1246 dejo "
    "inservible una corrida entera. Al cargarlo, la app localiza donante, punto de "
    "ramificacion, tracto de polipirimidinas y aceptor POR SECUENCIA y los declara."
)

#: El intron quimerico se EXTRAE del plasmido depositado por su anotacion, y se
#: comprueba contra la longitud y el md5 declarados. No se teclea: si el fichero no esta,
#: la entrada queda sin secuencia y lo dice — que es la regla 3 sobre una secuencia en
#: vez de sobre un filtro.
QUIMERICO_PLASMID = "addgene_198131.gb"
QUIMERICO_FEATURE = ("intron", "chimeric intron")
QUIMERICO_MD5 = "5cd85dcf763f8e7df6f4e84ada503be0"
QUIMERICO_SPAN = (1216, 1348)
QUIMERICO_CONTEXT_NT = 15


def _cargar_quimerico() -> str:
    """Lo extrae del plasmido. Cadena vacia si el fichero no esta: NO se inventa."""
    from pathlib import Path  # noqa: PLC0415

    from .genbank import load_plasmid_feature  # noqa: PLC0415
    from .reference import reference_dirs  # noqa: PLC0415

    clave, etiqueta = QUIMERICO_FEATURE
    for directorio in reference_dirs(None):
        ruta = Path(directorio) / QUIMERICO_PLASMID
        if not ruta.is_file():
            continue
        feature = load_plasmid_feature(
            ruta, key=clave, label=etiqueta, expected_md5=QUIMERICO_MD5
        )
        if (feature.start, feature.end) != QUIMERICO_SPAN:
            raise ShmirDesignError(
                f"{ruta}: la feature «{etiqueta}» está en "
                f"{feature.start}-{feature.end} y se declaró en "
                f"{QUIMERICO_SPAN[0]}-{QUIMERICO_SPAN[1]}. Se aborta: una feature "
                f"corrida un nucleótido corre todas las coordenadas sin dar error."
            )
        return feature.sequence
    return ""


_QUIMERICO = _cargar_quimerico()


INTRONS: dict[str, Intron] = {
    "mvm_actual": Intron(
        name="mvm_actual",
        description=(
            "El intrón MVM del casete de hoy. Se ensambla de piezas versionadas: nadie "
            "lo teclea."
        ),
        source="blocks.PIECES (plásmido receptor)",
        five_piece="MVM5",
        three_piece="MVM3",
        exon5_piece="exon5",
        exon3_piece="exon3",
        provided=True,
    ),
    "intron_quimerico": Intron(
        name="intron_quimerico",
        # NOMBRE CORREGIDO (2026-08-27). Se llamaba `quimerico_cmv_globina` y la
        # descripcion decia «CMV / beta-globina»: las dos cosas estaban mal, y salieron
        # a la luz al llegar el fichero. La nota de la propia anotacion dice «chimera
        # between introns from human beta-globin and immunoglobulin heavy chain genes».
        # El donante GTAAGT viene de la beta-globina y el aceptor de la Ig. CMV es el
        # PROMOTOR del plasmido (497-1080), no parte del intron: por eso se colo.
        description=(
            "Intrón quimérico de β-globina humana e inmunoglobulina de cadena pesada, "
            "133 pb. Donante GTAAGT (consenso perfecto), tracto de 11 pirimidinas "
            "frente a las 9 del MVM, y sin GTGAGCG: no aporta un segundo donante "
            "críptico."
        ),
        source="Addgene #198131 (pCI_mini-mAgrin-AviTag), feature `intron` 1216-1348",
        provided=True,
        raw_sequence=_QUIMERICO,
        ficha="intron_quimerico",
    ),
    "mvm_sin_criptico": Intron(
        name="mvm_sin_criptico",
        description=(
            "Variante del MVM con el donante críptico del flanco 5' de miR-E roto y "
            "espaciadores nuevos de 20-30 nt. Lo DISEÑA la app derivandolo del actual, "
            "con dos criterios computables. Es una PROPUESTA, no una construcción "
            "aprobada: pasa por el mismo modal que las demas antes de ir a síntesis."
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
            "Todavía no se ha diseñado en esta corrida. Se genera con "
            "`intron_design.design_variant()`, que necesita el 97-mero del candidato "
            "para poder aplicar el criterio estructural: las dos decisiones son "
            "estructurales, así que no hay una variante «del proyecto» sino una POR "
            "CANDIDATO. Con la guía de referencia, el primer paso EMPATA entre dos "
            "alternativas y la app no elige: hace falta una decisión."
        ),
        ficha="intron_sin_criptico",
    ),
}


def get(name: str) -> Intron:
    intron = INTRONS.get(name)
    if intron is None:
        raise ShmirDesignError(
            f"No hay ningún intrón {name!r} en el registro; los que hay: "
            f"{', '.join(sorted(INTRONS))}."
        )
    return intron


def available() -> tuple[Intron, ...]:
    return tuple(i for i in INTRONS.values() if i.provided)


def missing() -> tuple[Intron, ...]:
    """Los que faltan. Salen SIEMPRE, con NOT_RUN visible: un intron que no se ve no
    existe, y esa es la leccion de `offtarget_seed`."""
    return tuple(i for i in INTRONS.values() if not i.provided)
