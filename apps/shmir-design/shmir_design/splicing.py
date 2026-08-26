"""El empalme del intron MVM: el quinto frente, y el UNICO binario.

Todos los demas frentes son graduales. Una especificidad regular da off-targets; un techo
de APA baja el knockdown; una colision de seed secuestra una red. Se pueden medir, ordenar
y comparar, y un candidato malo se distingue de uno bueno.

Este no. Si el intron no se escinde, la horquilla se queda DENTRO del mRNA maduro, en el
5'UTR, y no hay proteina DN **en absoluto**. No hay «un poco de proteina»: la lectura de
exito es dicotomica y lo que decide no es un candidato, es si la ARQUITECTURA INTRONICA
sigue viva.

## Por que no estaba en la lista

Porque la lectura que se hace por defecto no lo coge. `small RNA-seq` puede salir
**perfecto** con el empalme fallando: Drosha procesa el pri-miR **cotranscripcionalmente**,
es decir ANTES del splicing, asi que la horquilla se corta igual esté el intron escindido
o no. Un shmiR correcto no es evidencia de que haya proteina — son dos sucesos en orden y
esa lectura solo mide el primero.

## Lo que hace este modulo, y lo que no

Localiza el intron sobre el plasmido **buscando las piezas de `blocks.PIECES`**, lee los
dinucleotidos GT/AG de la secuencia en vez de darlos por buenos, y deriva las ventanas
donde buscar los cebadores. **No emite cebadores**: eso necesita Tm, especificidad y
horquillas, y es la misma regla que en `polya.rtqpcr_amplicons`. Lo que si comprueba es
que las ventanas sean UNICAS en el plasmido, porque un cebador que aparece dos veces no
mide nada.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import blocks
from .errors import MissingSequenceError, ShmirDesignError
from .filters import FilterResult, FilterState

#: Ancho de la ventana donde BUSCAR el cebador. No es el cebador: es el sitio donde
#: ponerse a buscarlo, que es lo unico que se puede emitir sin Tm ni especificidad.
PRIMER_WINDOW = 60

#: Separacion minima entre el cebador y la union. Un cebador pegado a la union puede
#: acabar cruzandola al alargarlo, y ahi deja de servir (ver `WHY_NOT_JUNCTION_SPANNING`).
JUNCTION_MARGIN = 10

DONOR_DINUCLEOTIDE = "GT"
ACCEPTOR_DINUCLEOTIDE = "AG"

BINARY_NOT_GRADUAL = (
    "RIESGO BINARIO. NO ES UN PARAMETRO DE CALIDAD y no se lee como tal: o el intron se "
    "escinde o no. Si no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y "
    "no hay proteina DN EN ABSOLUTO — no hay «un poco de proteina» que optimizar. Lo que "
    "decide no es un candidato ni una plaza del panel: decide si la ARQUITECTURA "
    "INTRONICA sigue viva. Por eso va como frente y no como columna."
)

WHY_SMALL_RNA_SEQ_MISSES_IT = (
    "Y la lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir "
    "PERFECTO con el empalme fallando. Drosha procesa el pri-miR "
    "COTRANSCRIPCIONALMENTE, o sea ANTES del splicing, asi que la horquilla se corta "
    "igual este el intron escindido o no. Un shmiR correcto NO ES EVIDENCIA de que haya "
    "proteina: son dos sucesos en orden y esa lectura solo mide el primero."
)

WHY_NOT_JUNCTION_SPANNING = (
    "Ningun cebador puede cruzar la union exon-exon: uno que la cruce solo amplifica la "
    "forma EMPALMADA, asi que da presencia y no PROPORCION — y la proporcion es la "
    "eficiencia, que es lo que se busca. Los dos van enteros dentro de exon, a "
    f"{JUNCTION_MARGIN} nt de la union como minimo."
)

#: El codigo genetico estandar, generado y no tecleado (mismo criterio que `orf_sweep`).
_BASES = "TCAG"
_AMINOACIDOS = (
    "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
)
GENETIC_CODE = {
    a + b + c: _AMINOACIDOS[i]
    for i, (a, b, c) in enumerate(
        (x, y, z) for x in _BASES for y in _BASES for z in _BASES
    )
}


@dataclass(frozen=True)
class IntronLocation:
    """El intron colocado sobre el plasmido, con sus dinucleotidos LEIDOS."""

    plasmid_name: str
    plasmid_length: int
    donor_start: int
    acceptor_end: int
    donor: str
    acceptor: str

    @property
    def length(self) -> int:
        return self.acceptor_end - self.donor_start + 1

    @property
    def empty(self) -> bool:
        """¿Es el intron VACIO del parental — las dos mitades MVM y nada en medio?"""
        return self.length == (
            len(blocks.PIECES["MVM5"].sequence) + len(blocks.PIECES["MVM3"].sequence)
        )

    def describe(self) -> str:
        que = (
            f"VACIO (las dos mitades MVM pegadas, sin modulo)"
            if self.empty
            else f"con modulo dentro"
        )
        return (
            f"Intron MVM en {self.plasmid_name}: donante {self.donor} en "
            f"casete:{self.donor_start}, aceptor {self.acceptor} en "
            f"casete:{self.acceptor_end}, {self.length} nt, {que}."
        )


def locate_intron(sequence: str, *, name: str) -> IntronLocation:
    """Localiza el intron buscando las piezas de `blocks.PIECES`, no por coordenada.

    Aborta si falta una pieza, si aparece mas de una vez o si el aceptor va por delante
    del donante: en cualquiera de esos casos lo que hay no es este casete, y emitir
    coordenadas sobre otra cosa es exactamente el fallo que hay que evitar.
    """
    limpia = "".join(sequence.split()).upper()
    if not limpia:
        raise MissingSequenceError(
            f"{name}: no hay secuencia del casete, asi que no se puede localizar el "
            f"intron ni emitir ninguna coordenada de cebador. Se aborta (regla 1)."
        )

    posiciones = {}
    for pieza in ("MVM5", "MVM3"):
        motivo = blocks.PIECES[pieza].sequence
        encontradas = []
        i = limpia.find(motivo)
        while i >= 0:
            encontradas.append(i + 1)
            i = limpia.find(motivo, i + 1)
        if not encontradas:
            raise ShmirDesignError(
                f"{name}: no contiene la pieza {pieza} del intron "
                f"({len(motivo)} nt, procedencia «{blocks.PIECES[pieza].source}»), asi "
                f"que no es el casete intronico y no se emite ninguna coordenada. "
                f"Se aborta el paso «empalme del intron»."
            )
        if len(encontradas) > 1:
            raise ShmirDesignError(
                f"{name}: la pieza {pieza} aparece {len(encontradas)} veces "
                f"({encontradas}); no identifica un intron y se aborta en vez de "
                f"quedarse con la primera."
            )
        posiciones[pieza] = encontradas[0]

    donante = posiciones["MVM5"]
    aceptor = posiciones["MVM3"] + len(blocks.PIECES["MVM3"].sequence) - 1
    if aceptor <= donante:
        raise ShmirDesignError(
            f"{name}: el aceptor (casete:{aceptor}) queda por delante del donante "
            f"(casete:{donante}); eso no es un intron y se aborta."
        )

    sitio = IntronLocation(
        plasmid_name=name,
        plasmid_length=len(limpia),
        donor_start=donante,
        acceptor_end=aceptor,
        donor=limpia[donante - 1:donante + 1],
        acceptor=limpia[aceptor - 2:aceptor],
    )
    for etiqueta, leido, esperado in (
        ("donante", sitio.donor, DONOR_DINUCLEOTIDE),
        ("aceptor", sitio.acceptor, ACCEPTOR_DINUCLEOTIDE),
    ):
        if leido != esperado:
            raise ShmirDesignError(
                f"{name}: el dinucleotido {etiqueta} leido de la secuencia es {leido!r} "
                f"y se esperaba {esperado!r}. O las piezas no son las de este casete o "
                f"el casete no es el que dice ser; se aborta en vez de emitir "
                f"coordenadas sobre un sitio de empalme que no lo es."
            )
    return sitio


@dataclass(frozen=True)
class PrimerWindow:
    """Donde BUSCAR un cebador. No es un cebador."""

    label: str
    start: int
    end: int
    occurrences: int
    gc: float

    @property
    def usable(self) -> bool:
        """Una ventana que aparece dos veces no mide nada, asi que no vale."""
        return self.occurrences == 1

    def describe(self) -> str:
        estado = (
            "unica en el casete"
            if self.usable
            else f"APARECE {self.occurrences} VECES — NO VALE"
        )
        return (
            f"{self.label}: casete:{self.start}-{self.end} "
            f"({self.end - self.start + 1} nt, GC {self.gc:.0%}, {estado})"
        )


def _ventana(secuencia: str, label: str, inicio: int, fin: int) -> PrimerWindow:
    trozo = secuencia[inicio - 1:fin]
    cuenta, i = 0, secuencia.find(trozo)
    while i >= 0:
        cuenta += 1
        i = secuencia.find(trozo, i + 1)
    return PrimerWindow(
        label=label,
        start=inicio,
        end=fin,
        occurrences=cuenta,
        gc=sum(c in "GC" for c in trozo) / len(trozo) if trozo else 0.0,
    )


def translate(sequence: str) -> str:
    """Traduce hasta el primer codon de parada. No completa nada (regla 1)."""
    proteina = []
    for i in range(0, len(sequence) - 2, 3):
        residuo = GENETIC_CODE.get(sequence[i:i + 3])
        if residuo is None:
            raise ShmirDesignError(
                f"Codon {sequence[i:i + 3]!r} no reconocido en la posicion {i + 1} del "
                f"ORF; se aborta la traduccion en vez de saltarselo."
            )
        if residuo == "*":
            break
        proteina.append(residuo)
    return "".join(proteina)


@dataclass(frozen=True)
class SplicingRtPcr:
    """Lectura 1: RT-PCR de empalme. Coordenadas, nunca cebadores."""

    location: IntronLocation
    upstream: PrimerWindow
    downstream: PrimerWindow
    therapeutic_intron_length: int
    orf_start: int
    protein: str

    @property
    def protein_length(self) -> int:
        return len(self.protein)

    @property
    def utr5_after_acceptor(self) -> int:
        """nt de 5'UTR entre el aceptor y el codon de inicio."""
        return self.orf_start - self.location.acceptor_end - 1

    @property
    def retained_insert(self) -> int:
        return self.therapeutic_intron_length

    @property
    def upstream_atgs(self) -> int:
        """uATG en las piezas FIJAS del intron. La horquilla puede añadir mas."""
        return sum(
            blocks.PIECES[p].sequence.count("ATG")
            for p in ("MVM5", "espaciador5", "espaciador3", "MVM3")
        )

    @property
    def difference(self) -> int:
        """Banda larga − banda corta en el TERAPEUTICO. Exacta: es el intron entero.

        Es la unica cifra que no depende de donde caiga el cebador dentro de su ventana,
        y es justo la que se lee en el gel.
        """
        return self.therapeutic_intron_length

    @property
    def parental_difference(self) -> int:
        return self.location.length

    @property
    def spliced_range(self) -> tuple[int, int]:
        """El tramo EXONICO que entra en el amplicon empalmado, sin los cebadores.

        Ojo con el extremo bajo: NO es una banda de ese tamaño. El cebador tiene que
        caber ENTERO dentro de su ventana, asi que el minimo real es este numero MAS la
        suma de las dos longitudes de cebador. Darlo como si fuera una banda emitiria un
        amplicon de 22 pb, que es geometricamente imposible — y aqui no se inventa una
        longitud de cebador para taparlo: se dice la formula.
        """
        sitio = self.location
        corto = (sitio.donor_start - self.upstream.end - 1) + (
            self.downstream.start - sitio.acceptor_end - 1
        )
        largo = (sitio.donor_start - self.upstream.start) + (
            self.downstream.end - sitio.acceptor_end
        )
        return (corto, largo)

    @property
    def retained_range(self) -> tuple[int, int]:
        bajo, alto = self.spliced_range
        return (bajo + self.difference, alto + self.difference)

    def describe(self) -> list[str]:
        bajo, alto = self.spliced_range
        rbajo, ralto = self.retained_range
        pbajo = bajo + self.parental_difference
        palto = alto + self.parental_difference
        return [
            "LECTURA 1 — RT-PCR DE EMPALME. Cebadores en los exones que flanquean el "
            "intron MVM.",
            f"  {self.location.describe()}",
            "  VENTANAS donde buscar los cebadores (no se emiten cebadores: Tm, "
            "especificidad y",
            "  horquillas no se improvisan; es la misma regla que en los amplicones de "
            "RT-qPCR):",
            f"    {self.upstream.describe()}",
            f"    {self.downstream.describe()}",
            f"  {WHY_NOT_JUNCTION_SPANNING}",
            "",
            "  LO QUE SE LEE EN EL GEL. F y R son las longitudes de los dos cebadores, "
            "que no se fijan aqui:",
            f"    banda CORTA = EMPALMADO   {bajo} + F + R pb  (los dos cebadores pegados "
            f"al margen)",
            f"                              hasta {alto} pb    (los dos en el extremo "
            f"externo de su ventana)",
            f"    banda LARGA = RETENIDO    lo mismo + {self.difference} pb "
            f"→ {rbajo} + F + R .. {ralto} pb   (TERAPEUTICO)",
            f"                              lo mismo + {self.parental_difference} pb "
            f"→ {pbajo} + F + R .. {palto} pb   (parental, otro intron)",
            f"    La PROPORCION entre las dos es la EFICIENCIA de empalme. Los tamaños "
            f"absolutos dependen",
            f"    de donde se pongan los cebadores y de lo largos que sean; la "
            f"DIFERENCIA no depende de nada",
            f"    de eso: es exactamente el intron ({self.difference} nt en el "
            f"terapeutico). Esa es la lectura.",
            "",
            "  ESPECIFICIDAD DEL PAR — el cebador de aguas ARRIBA es el que la da. La "
            "ventana de aguas",
            f"  abajo entra en el ORF de PrP (empieza en casete:{self.orf_start}), asi "
            f"que un par con los DOS",
            "  cebadores ahi amplificaria tambien el Prnp ENDOGENO del tejido y la "
            "banda no seria del vector.",
            "",
            f"  POR QUE IMPORTA, comprobado sobre esta secuencia: el ORF empieza en "
            f"casete:{self.orf_start},",
            f"  a {self.utr5_after_acceptor} nt del aceptor, asi que el intron esta en el "
            f"5'UTR. Retenido, mete",
            f"  {self.retained_insert} nt por delante del codon de inicio, con al menos "
            f"{self.upstream_atgs} uATG en sus piezas fijas.",
            f"  El ORF traduce {self.protein_length} aa que empiezan por "
            f"{self.protein[:16]} — es PrP, y lleva las dos",
            "  mutaciones que anuncia el nombre del plasmido. Identidad comprobada por "
            "traduccion, no por el nombre del fichero.",
        ]


def splice_rtpcr_plan(
    sequence: str,
    *,
    name: str,
    therapeutic_intron_length: int = blocks.INTRON_LENGTH,
    window: int = PRIMER_WINDOW,
    margin: int = JUNCTION_MARGIN,
) -> SplicingRtPcr:
    """Las coordenadas de la lectura 1, derivadas de la union y nunca tecleadas."""
    limpia = "".join(sequence.split()).upper()
    sitio = locate_intron(limpia, name=name)

    arriba_fin = sitio.donor_start - margin - 1
    arriba_inicio = arriba_fin - window + 1
    abajo_inicio = sitio.acceptor_end + margin + 1
    abajo_fin = abajo_inicio + window - 1
    if arriba_inicio < 1 or abajo_fin > len(limpia):
        raise ShmirDesignError(
            f"{name}: no caben las ventanas de cebador de {window} nt a "
            f"{margin} nt de la union dentro de las {len(limpia)} pb del casete; se "
            f"aborta en vez de emitir una coordenada fuera de la secuencia."
        )

    # El ATG del ORF se BUSCA por detras del aceptor y se traduce; no se teclea su
    # posicion. Si no hay ninguno, el casete no es lo que decimos y se aborta.
    resto = limpia[sitio.acceptor_end:]
    inicio_orf = resto.find("ATG")
    if inicio_orf < 0:
        raise ShmirDesignError(
            f"{name}: no hay ningun ATG por detras del aceptor, asi que no se puede "
            f"comprobar que el intron caiga en el 5'UTR; se aborta en vez de darlo por "
            f"supuesto."
        )
    absoluto = sitio.acceptor_end + inicio_orf + 1
    return SplicingRtPcr(
        location=sitio,
        upstream=_ventana(limpia, "aguas arriba (exon 5')", arriba_inicio, arriba_fin),
        downstream=_ventana(limpia, "aguas abajo (exon 3')", abajo_inicio, abajo_fin),
        therapeutic_intron_length=therapeutic_intron_length,
        orf_start=absoluto,
        protein=translate(limpia[absoluto - 1:]),
    )


@dataclass(frozen=True)
class SplicingReadout:
    """Una de las tres lecturas. Ninguna la corre el software: todas son de banco."""

    name: str
    state: FilterState
    requirement: str

    def as_filter(self) -> FilterResult:
        return FilterResult(name=self.name, state=self.state, reason=self.requirement)


def splicing_readouts(plan: SplicingRtPcr | None = None) -> tuple[SplicingReadout, ...]:
    """Las TRES lecturas que cierran el frente. Todas `NOT_RUN`, y por eso bloquea."""
    coordenadas = (
        f"Coordenadas emitidas: ventanas casete:{plan.upstream.start}-"
        f"{plan.upstream.end} y casete:{plan.downstream.start}-{plan.downstream.end}; "
        f"diferencia entre bandas {plan.difference} pb."
        if plan is not None
        else "Coordenadas NO emitidas: falta el casete (--transgen)."
    )
    return (
        SplicingReadout(
            name="rtpcr_empalme",
            state=FilterState.NOT_RUN,
            requirement=(
                "RT-PCR con cebadores en los exones que flanquean el intron MVM. Banda "
                "CORTA = empalmado, banda LARGA = retenido, y la PROPORCION es la "
                f"eficiencia. {coordenadas}"
            ),
        ),
        SplicingReadout(
            name="western_L42_por_vg",
            state=FilterState.NOT_RUN,
            requirement=(
                "Western L42 NORMALIZADO por vg-qPCR. Sin normalizar, «no hay proteina» "
                "no se distingue de «no llego el vector»: los dos dan una membrana "
                "vacia, y solo uno de los dos culpa al empalme. La vg-qPCR es la que "
                "separa las dos hipotesis."
            ),
        ),
        SplicingReadout(
            name="parental_sin_intron",
            state=FilterState.NOT_RUN,
            requirement=(
                "Parental SIN INTRON en la MISMA TANDA, como TECHO de expresion. Sin "
                "techo, un western flojo no dice si el empalme va mal o si la "
                "construccion expresa poco de por si. "
                "OJO: el casete que hay (aav_casete.fa) NO es ese. Es el parental sin "
                "MODULO pero CON el intron vacio de 82 nt, asi que tiene el mismo "
                "problema de empalme que se quiere medir y no sirve de techo. Hace "
                "falta la construccion sin donante ni aceptor."
            ),
        ),
    )


@dataclass(frozen=True)
class SplicingFront:
    name: str
    reason: str
    blocking: bool = True


def splicing_front(plan: SplicingRtPcr | None = None) -> SplicingFront:
    """El quinto frente. El software NO puede cerrarlo: las tres lecturas son de banco.

    El motivo va CORTO a proposito: es una entrada de una lista, no el bloque. Repetir
    aqui las tres lecturas enteras hace que la lista de frentes ocupe una pantalla y
    deje de leerse, que es la forma de esconder algo a plena vista.
    """
    coordenadas = (
        f"Coordenadas emitidas: ventanas casete:{plan.upstream.start}-"
        f"{plan.upstream.end} y casete:{plan.downstream.start}-"
        f"{plan.downstream.end}, diferencia entre bandas {plan.difference} pb."
        if plan is not None
        else "Coordenadas NO emitidas en esta corrida: falta el casete (--transgen)."
    )
    return SplicingFront(
        name="empalme_intron",
        reason=(
            f"{BINARY_NOT_GRADUAL} {WHY_SMALL_RNA_SEQ_MISSES_IT} "
            f"SE CIERRA CON TRES LECTURAS DE BANCO, las tres NOT_RUN y ninguna la corre "
            f"este software: (1) RT-PCR de empalme con cebadores en los exones que "
            f"flanquean el intron MVM; (2) Western L42 normalizado por vg-qPCR, que es "
            f"lo que separa «no empalmo» de «no llego el vector»; (3) parental SIN "
            f"INTRON en la misma tanda, como techo de expresion. {coordenadas} El "
            f"detalle, en el bloque «Empalme del intron»."
        ),
    )


def plan_from_records(records, *, therapeutic_intron_length: int = blocks.INTRON_LENGTH):
    """El plan a partir de la base del transgen, o `(None, motivo)` con el motivo escrito.

    No captura excepciones para decidir: COMPRUEBA antes si el registro trae las dos
    piezas del intron, y solo entonces localiza. Un `try/except` aqui seria la regla 2
    por la puerta de atras — se tragaria un casete roto y lo llamaria «no hay casete».
    """
    if not records:
        return None, (
            "No hay casete cargado (--transgen), asi que no se emiten coordenadas de "
            "cebador. NOT_RUN no es PASS: el frente sigue igual de abierto."
        )
    mvm5 = blocks.PIECES["MVM5"].sequence
    mvm3 = blocks.PIECES["MVM3"].sequence
    for nombre, secuencia in records.items():
        limpia = "".join(str(secuencia).split()).upper()
        if limpia.count(mvm5) == 1 and limpia.count(mvm3) == 1:
            return (
                splice_rtpcr_plan(
                    limpia,
                    name=nombre,
                    therapeutic_intron_length=therapeutic_intron_length,
                ),
                "",
            )
    return None, (
        f"El casete cargado ({', '.join(list(records)[:3])}) no contiene UNA sola copia "
        f"de las piezas MVM5 y MVM3 del intron, asi que no se puede localizar la union y "
        f"no se emiten coordenadas. O no es el casete intronico, o lleva el intron "
        f"repetido; en los dos casos hay que mirarlo antes de pedir nada."
    )
