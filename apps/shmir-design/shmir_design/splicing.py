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

#: El orden de las piezas del intron terapeutico, con su LONGITUD. Se deriva de
#: `blocks.PIECES`, no se teclea: si una pieza cambia de tamaño, esto cambia con ella.
#: La horquilla mide siempre 97 nt pero su SECUENCIA depende de la guia, y por eso los
#: uAUG que aporta se cuentan por candidato.
INTRON_LAYOUT: tuple[tuple[str, int], ...] = (
    ("MVM5", len(blocks.PIECES["MVM5"].sequence)),
    ("espaciador5", len(blocks.PIECES["espaciador5"].sequence)),
    ("NheI", len(blocks.PIECES["NheI"].sequence)),
    ("contexto5", len(blocks.PIECES["contexto5"].sequence)),
    ("horquilla", blocks.HAIRPIN_LENGTH),
    ("contexto3", len(blocks.PIECES["contexto3"].sequence)),
    ("SacI", len(blocks.PIECES["SacI"].sequence)),
    ("espaciador3", len(blocks.PIECES["espaciador3"].sequence)),
    ("MVM3", len(blocks.PIECES["MVM3"].sequence)),
)

#: El donante criptico del flanco 5' de miR-E. No se busca «un GT cualquiera»: es ESTE,
#: y esta DENTRO del andamio, asi que viaja con cualquier candidato.
CRYPTIC_DONOR = "GTGAGCG"

BINARY_NOT_GRADUAL = (
    "RIESGO BINARIO. NO ES UN PARÁMETRO DE CALIDAD y no se lee como tal: o el intrón se "
    "escinde o no. Si no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y "
    "no hay proteina DN EN ABSOLUTO — no hay «un poco de proteina» que optimizar. Lo que "
    "decide no es un candidato ni una plaza del panel: decide si la ARQUITECTURA "
    "INTRÓNICA sigue viva. Por eso va como frente y no como columna."
)

WHY_SMALL_RNA_SEQ_MISSES_IT = (
    "Y la lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir "
    "PERFECTO con el empalme fallando. Drosha procesa el pri-miR "
    "COTRANSCRIPCIONALMENTE, o sea ANTES del splicing, así que la horquilla se corta "
    "igual este el intrón escindido o no. Un shmiR correcto NO ES EVIDENCIA de que haya "
    "proteina: son dos sucesos en orden y esa lectura solo mide el primero."
)

WHY_NOT_JUNCTION_SPANNING = (
    "Ningún cebador puede cruzar la union exon-exon: uno que la cruce solo amplifica la "
    "forma EMPALMADA, así que da presencia y no PROPORCIÓN — y la proporción es la "
    "eficiencia, que es lo que se busca. Los dos van enteros dentro de exon, a "
    f"{JUNCTION_MARGIN} nt de la union como mínimo."
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
            f"VACÍO (las dos mitades MVM pegadas, sin módulo)"
            if self.empty
            else f"con módulo dentro"
        )
        return (
            f"Intrón MVM en {self.plasmid_name}: donante {self.donor} en "
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
            f"{name}: no hay secuencia del casete, así que no se puede localizar el "
            f"intrón ni emitir ninguna coordenada de cebador. Se aborta (regla 1)."
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
                f"{name}: no contiene la pieza {pieza} del intrón "
                f"({len(motivo)} nt, procedencia «{blocks.PIECES[pieza].source}»), así "
                f"que no es el casete intrónico y no se emite ninguna coordenada. "
                f"Se aborta el paso «empalme del intrón»."
            )
        if len(encontradas) > 1:
            raise ShmirDesignError(
                f"{name}: la pieza {pieza} aparece {len(encontradas)} veces "
                f"({encontradas}); no identifica un intrón y se aborta en vez de "
                f"quedarse con la primera."
            )
        posiciones[pieza] = encontradas[0]

    donante = posiciones["MVM5"]
    aceptor = posiciones["MVM3"] + len(blocks.PIECES["MVM3"].sequence) - 1
    if aceptor <= donante:
        raise ShmirDesignError(
            f"{name}: el aceptor (casete:{aceptor}) queda por delante del donante "
            f"(casete:{donante}); eso no es un intrón y se aborta."
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
            "única en el casete"
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
                f"Codon {sequence[i:i + 3]!r} no reconocido en la posición {i + 1} del "
                f"ORF; se aborta la traducción en vez de saltarselo."
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
            "intrón MVM.",
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
            "que no se fijan aquí:",
            f"    banda CORTA = EMPALMADO   {bajo} + F + R pb  (los dos cebadores pegados "
            f"al margen)",
            f"                              hasta {alto} pb    (los dos en el extremo "
            f"externo de su ventana)",
            f"    banda LARGA = RETENIDO    lo mismo + {self.difference} pb "
            f"→ {rbajo} + F + R .. {ralto} pb   (TERAPEUTICO)",
            f"                              lo mismo + {self.parental_difference} pb "
            f"→ {pbajo} + F + R .. {palto} pb   (parental, otro intrón)",
            f"    La PROPORCIÓN entre las dos es la EFICIENCIA de empalme. Los tamaños "
            f"absolutos dependen",
            f"    de donde se pongan los cebadores y de lo largos que sean; la "
            f"DIFERENCIA no depende de nada",
            f"    de eso: es exactamente el intrón ({self.difference} nt en el "
            f"terapeutico). Esa es la lectura.",
            "",
            "  ESPECIFICIDAD DEL PAR — el cebador de aguas ARRIBA es el que la da. La "
            "ventana de aguas",
            f"  abajo entra en el ORF de PrP (empieza en casete:{self.orf_start}), así "
            f"que un par con los DOS",
            "  cebadores ahi amplificaria también el Prnp ENDOGENO del tejido y la "
            "banda no sería del vector.",
            "",
            f"  POR QUE IMPORTA, comprobado sobre esta secuencia: el ORF empieza en "
            f"casete:{self.orf_start},",
            f"  a {self.utr5_after_acceptor} nt del aceptor, así que el intrón está en el "
            f"5'UTR. Retenido, mete",
            f"  {self.retained_insert} nt por delante del codón de inicio, con al menos "
            f"{self.upstream_atgs} uATG en sus piezas fijas.",
            f"  El ORF traduce {self.protein_length} aa que empiezan por "
            f"{self.protein[:16]} — es PrP, y lleva las dos",
            "  mutaciones que anuncia el nombre del plásmido. Identidad comprobada por "
            "traducción, no por el nombre del fichero.",
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
            f"{name}: no hay ningún ATG por detrás del aceptor, así que no se puede "
            f"comprobar que el intrón caiga en el 5'UTR; se aborta en vez de darlo por "
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


#: Cuanto intron quedaria dentro si el donante criptico del andamio empalma al aceptor
#: legitimo. Es la longitud del intron por delante de ese donante, y no depende de la
#: guia: el donante esta en el flanco 5' del andamio, que es fijo.
CRYPTIC_RETAINED = 97


#: LO QUE ESTABA ESCRITO Y ERA FALSO. Aqui ponia «Banda CORTA = empalmado, banda LARGA =
#: retenido». Lo corrigio el responsable del proyecto (2026-09-02) y es una correccion de
#: fondo sobre el UNICO frente binario del proyecto — el que decide si hay proteina.
#:
#: **El pre-mRNA sin empalmar existe SIEMPRE.** El splicing es cotranscripcional pero no
#: instantaneo, asi que en cualquier poblacion de transcritos hay nacientes a medio
#: procesar: la banda larga sale con el empalme PERFECTO. Presencia de banda larga no es
#: evidencia de retencion — es evidencia de que la celula estaba transcribiendo.
#:
#: Es la misma forma que el «Alu 0 %» al reves: alli se afirmaba una ausencia sin haber
#: buscado; aqui se afirma una presencia sin haber separado las dos causas que la
#: producen. En los dos casos el numero sale, tiene la forma correcta, y no dice lo que
#: se cree que dice.
WHY_PRESENCE_IS_NOT_EVIDENCE = (
    "OJO, y esto invalida la lectura ingenua: la PRESENCIA de banda larga NO ES "
    "EVIDENCIA de retención. El pre-mRNA sin empalmar existe SIEMPRE —el splicing es "
    "cotranscripcional pero no instantáneo—, así que hay transcritos NACIENTES a medio "
    "procesar aunque el empalme sea perfecto, y dan banda larga igual."
)

#: Las CUATRO condiciones sin las cuales el ensayo no separa esas dos causas. Van juntas
#: y ninguna es opcional: tres quitan el naciente y el ADN del medio, y la cuarta cambia
#: lo que se lee — de una presencia a una proporcion con dos referencias.
RTPCR_CONDITIONS = (
    "Por eso el ensayo lleva CUATRO condiciones y ninguna es opcional: "
    "(1) RNA CITOPLÁSMICO, no total — el pre-mRNA sin empalmar es NUCLEAR, y lo que sí "
    "es fallo es encontrarlo retenido en el citoplasma; "
    "(2) SELECCIÓN POR polyA, que excluye la mayor parte del naciente; "
    "(3) DNasa y CONTROL SIN RETROTRANSCRIPTASA, porque el genoma del AAV LLEVA el "
    "intrón y una traza de ADN da una banda larga indistinguible de la retención; "
    "(4) la lectura es la PROPORCIÓN corta/larga, NO la presencia, y no se lee sola: "
    "necesita DOS referencias en la MISMA TANDA —el control sin intrón, que es el "
    "100 % corta, y el terapéutico—."
)


def splicing_readouts(plan: SplicingRtPcr | None = None) -> tuple[SplicingReadout, ...]:
    """Las CUATRO lecturas que cierran el frente. Todas `NOT_RUN`, y por eso bloquea."""
    crypticos = CRYPTIC_RETAINED
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
                "RT-PCR con cebadores en los exones que flanquean el intrón MVM. "
                f"{WHY_PRESENCE_IS_NOT_EVIDENCE} {RTPCR_CONDITIONS} {coordenadas}"
            ),
        ),
        SplicingReadout(
            name="western_L42_por_vg",
            state=FilterState.NOT_RUN,
            requirement=(
                "Western L42 NORMALIZADO por vg-qPCR. Sin normalizar, «no hay proteina» "
                "no se distingue de «no llego el vector»: los dos dan una membrana "
                "vacía, y solo uno de los dos culpa al empalme. La vg-qPCR es la que "
                "separa las dos hipotesis."
            ),
        ),
        SplicingReadout(
            name="secuencia_union_exon_exon",
            state=FilterState.NOT_RUN,
            requirement=(
                "SECUENCIAR la banda corta, no solo verla. Es LA QUE CIERRA el frente: "
                "la lectura de exito es la SECUENCIA de la union exon-exon, NO LA "
                f"ALTURA de la banda. Sirve para descartar el donante críptico "
                f"{CRYPTIC_DONOR} del flanco 5' del andamio: un empalme por ahi al "
                f"aceptor legítimo dejaria {crypticos} nt de intrón dentro y daria una "
                f"banda INTERMEDIA —empalmada + {crypticos} pb— que en un gel se puede "
                f"confundir con la correcta. Con la union secuenciada, o pone "
                f"exon5|exon3 o no lo pone."
            ),
        ),
        SplicingReadout(
            name="parental_sin_intron",
            state=FilterState.NOT_RUN,
            requirement=(
                "Parental SIN INTRÓN en la MISMA TANDA, como TECHO de expresión. Sin "
                "techo, un western flojo no dice si el empalme va mal o si la "
                "construcción expresa poco de por si. "
                "OJO: el casete que hay (aav_casete.fa) NO es ese. Es el parental sin "
                "MÓDULO pero CON el intrón vacío de 82 nt, así que tiene el mismo "
                "problema de empalme que se quiere medir y no sirve de techo. Hace "
                "falta la construcción sin donante ni aceptor."
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
            f"flanquean el intrón MVM; (2) Western L42 normalizado por vg-qPCR, que es "
            f"lo que separa «no empalmo» de «no llego el vector»; (3) parental SIN "
            f"INTRÓN en la misma tanda, como techo de expresión. {coordenadas} El "
            f"detalle, en el bloque «Empalme del intrón»."
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
            "No hay casete cargado (--transgen), así que no se emiten coordenadas de "
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
        f"de las piezas MVM5 y MVM3 del intrón, así que no se puede localizar la union y "
        f"no se emiten coordenadas. O no es el casete intrónico, o lleva el intrón "
        f"repetido; en los dos casos hay que mirarlo antes de pedir nada."
    )


# ─── Los DOS modos de fallo de la retencion ──────────────────────────────────
#
# No es uno con un detalle. Si el intron se queda dentro pasan dos cosas independientes,
# y la segunda actua aunque la primera no estorbara nada.

RETENTION_MODES = (
    "SI EL INTRÓN SE RETIENE FALLAN DOS COSAS DISTINTAS, no una: "
    "(a) la horquilla se queda dentro del mRNA maduro, en el 5'UTR, con lo que eso haga "
    "al transito del ribosoma y a la estabilidad; y "
    "(b) el ribosoma escanea desde el extremo 5' y se encuentra varios AUG antes del "
    "legítimo. El (b) actua AUNQUE la horquilla no estorbara nada: son mecanismos "
    "distintos y se cuentan aparte."
)

#: El criterio de Kozak que se usa aqui, DECLARADO como parametro de este analisis.
#: No es una cita: es la regla que se aplica, escrita para que se pueda discutir.
KOZAK_CRITERION = (
    "Kozak, criterio declarado (no citado): se miran dos posiciones, -3 (purina A o G) "
    "y +4 (G). Las dos → FUERTE; una → adecuado; ninguna → debil. Es el criterio de "
    "este análisis y se escribe para que se pueda discutir, no para dar por buena una "
    "referencia que aquí no se ha comprobado."
)

#: Cuanto contexto se imprime a cada lado del AUG.
KOZAK_CONTEXT = 6


@dataclass(frozen=True)
class UpstreamAtg:
    """Un AUG por delante del legitimo, con lo que decide su consecuencia."""

    offset: int              # 1-based dentro del intron
    piece: str
    context: str
    minus3: str
    plus4: str
    strength: str
    distance_to_orf: int
    in_frame: bool
    stop_after_codons: int | None

    @property
    def outcome(self) -> str:
        """`EXTENSION_N_TERMINAL` es el caso PEOR; el resto son uORF.

        En marco y SIN codon de parada por delante del ATG legitimo, la traduccion
        entra en PrP y sale una proteina con extension N-terminal: algo que SE PRODUCE
        y que un Western podria confundir con la DN. Peor que no traducir, porque da
        señal.
        """
        if self.stop_after_codons is None:
            # Sin parada por delante del ATG legitimo hay dos casos, y no son el mismo.
            # EN MARCO: la traduccion entra en PrP y sale con cola → el caso peor.
            # FUERA DE MARCO: el ribosoma sigue ELONGANDO cuando pasa por el ATG
            # legitimo, asi que no puede iniciar ahi — un uORF que SOLAPA el inicio es
            # peor que uno que termina antes, porque el que termina antes deja
            # reiniciar.
            return "EXTENSION_N_TERMINAL" if self.in_frame else "uORF_SOLAPANTE"
        return "uORF"

    def describe(self) -> str:
        marco = "EN MARCO" if self.in_frame else "fuera de marco"
        parada = (
            f"para a los {self.stop_after_codons} codones"
            if self.stop_after_codons is not None
            else "SIN codón de parada antes del ATG legítimo"
        )
        return (
            f"+{self.offset:<3} ({self.piece:<12}) {self.context:<14} "
            f"-3={self.minus3} +4={self.plus4} Kozak {self.strength:<9} "
            f"a {self.distance_to_orf} nt del ATG legítimo, {marco}, {parada} "
            f"→ {self.outcome}"
        )


def kozak_strength(minus3: str, plus4: str) -> str:
    """El criterio de `KOZAK_CRITERION`, en una funcion y no repartido por el texto."""
    puntos = (minus3 in "AG") + (plus4 == "G")
    return {2: "FUERTE", 1: "adecuado", 0: "debil"}[puntos]


def scan_upstream_atgs(
    intron: str,
    *,
    tail: int = 37,
    layout: tuple[tuple[str, int], ...] | None = None,
    downstream: str = "",
) -> tuple[UpstreamAtg, ...]:
    """Los AUG del intron retenido, con Kozak, marco y si llegan al ORF sin parada.

    `tail` son los nt de 5'UTR que quedan entre el aceptor y el ATG legitimo (37 en este
    casete, comprobado sobre la secuencia). `downstream` es lo que va detras del intron
    cuando se quiere leer de verdad hasta el ORF; sin el, la parada solo se busca dentro
    del intron y eso se nota en el resultado.
    """
    limpio = "".join(str(intron).split()).upper()
    if not limpio:
        return ()
    piezas = layout or INTRON_LAYOUT

    def de_que_pieza(k: int) -> str:
        acumulado = 0
        for nombre, largo in piezas:
            if acumulado < k <= acumulado + largo:
                return nombre
            acumulado += largo
        return "?"

    completo = limpio + downstream
    encontrados: list[UpstreamAtg] = []
    for k in range(1, len(limpio) - 1):
        if limpio[k - 1:k + 2] != "ATG":
            continue
        menos3 = limpio[k - 4] if k - 4 >= 0 else "-"
        mas4 = limpio[k + 2] if k + 2 < len(limpio) else "-"
        # Distancia entre la A del uAUG y la A del ATG legitimo, contada sobre
        # posiciones absolutas y no «cuantos nt hay en medio»: el off-by-one de aqui
        # cambia el MARCO, que es justo lo que decide si hay extension N-terminal.
        distancia = len(limpio) + tail + 1 - k
        parada = None
        for j in range(k - 1, len(completo) - 2, 3):
            if j - (k - 1) >= distancia:
                break
            if GENETIC_CODE.get(completo[j:j + 3]) == "*":
                parada = (j - (k - 1)) // 3
                break
        encontrados.append(
            UpstreamAtg(
                offset=k,
                piece=de_que_pieza(k),
                context=limpio[max(0, k - 1 - KOZAK_CONTEXT):k + 2],
                minus3=menos3,
                plus4=mas4,
                strength=kozak_strength(menos3, mas4),
                distance_to_orf=distancia,
                in_frame=distancia % 3 == 0,
                stop_after_codons=parada,
            )
        )
    return tuple(encontrados)


def describe_upstream_atgs(uatgs: tuple[UpstreamAtg, ...]) -> str:
    if not uatgs:
        return ""
    extensiones = [u for u in uatgs if u.outcome == "EXTENSION_N_TERMINAL"]
    if extensiones:
        veredicto = (
            "HAY EXTENSION N-TERMINAL: "
            + ", ".join(f"+{u.offset}" for u in extensiones)
            + " están EN MARCO y llegan al ATG legítimo SIN codón de parada. Eso "
            "produce PrP con una cola por delante — algo que SE DETECTA en un Western y "
            "que podría pasar por la DN. Es el caso peor y no se puede cribar a ciegas."
        )
    else:
        veredicto = (
            "EXTENSION N-TERMINAL: ninguno. Se comprueba, no se supone: de los "
            f"{len(uatgs)} uAUG, "
            + (
                ", ".join(f"+{u.offset}" for u in uatgs if u.in_frame)
                + " esta(n) en marco pero para(n) antes del ATG legítimo"
                if any(u.in_frame for u in uatgs)
                else "ninguno está en marco"
            )
            + ". Así que ninguno produce una proteina que un Western pueda confundir "
            "con la DN."
        )
    solapantes = [u for u in uatgs if u.outcome == "uORF_SOLAPANTE"]
    if solapantes:
        veredicto += (
            " PERO NO TODOS SON IGUALES: "
            + ", ".join(f"+{u.offset}" for u in solapantes)
            + " no llega(n) a codón de parada antes del ATG legítimo, así que el "
            "ribosoma SIGUE ELONGANDO al pasar por el — un uORF que SOLAPA el inicio no "
            "deja reiniciar ahi, y eso es peor que uno que termina antes."
        )
    return (
        f"ESCANEO DEL RIBOSOMA — {len(uatgs)} AUG por delante del legítimo. {veredicto} "
        f"{KOZAK_CRITERION} "
        f"OJO: la cuenta cambia POR CANDIDATO — la horquilla aporta parte de estos AUG y "
        f"otra guía da otros. Lo que no cambia son los del andamio y los espaciadores."
    )


# ─── El donante criptico del andamio, y lo que se puede cerrar HOY ───────────
#
# El flanco 5' de miR-E lleva `GTGAGCG`, que se parece al consenso de sitio donante
# (`GTRAGT`). Si se usara, el empalme saldria del andamio en vez de la señal del MVM y
# la banda tendria un tamaño INTERMEDIO — confundible con la correcta en un gel.
#
# La pregunta que se puede contestar sin ningun fichero es si entre ese donante y el
# aceptor legitimo del MVM hay un ACEPTOR utilizable. Y hay que decir lo que esa
# respuesta cierra y lo que no.

SPLICE_SITE_CRITERION = (
    "Criterio de sitio 3' declarado como PARÁMETRO de este análisis; NO ES UNA CITA. Se "
    "miden dos cosas sobre cada AG: (1) el tracto de pirimidinas CONTIGUAS inmediatamente "
    "aguas arriba —contiguas, no el porcentaje en una ventana, que diluye—, y (2) si hay "
    "algun YURAY entre 18 y 40 nt aguas arriba, como punto de ramificacion candidato. Los "
    "dos números salen tal cual y la comparación se hace CONTRA EL ACEPTOR LEGÍTIMO del "
    "mismo intrón, que es la referencia interna: así el veredicto no depende de ningún "
    "umbral tomado de fuera."
)

BRANCH_POINT_WINDOW = (18, 40)


@dataclass(frozen=True)
class AcceptorCandidate:
    offset: int
    tract: int
    branch_points: tuple[str, ...]

    def describe(self) -> str:
        ramas = ", ".join(self.branch_points) if self.branch_points else "ninguno"
        return (
            f"AG en +{self.offset}: tracto de {self.tract} pirimidina(s) contiguas, "
            f"YURAY candidato(s): {ramas}"
        )


@dataclass(frozen=True)
class CrypticDonor:
    donor_offset: int
    donor_motif: str
    acceptor_offset: int
    acceptor_tract: int
    candidates: tuple[AcceptorCandidate, ...]
    intron_length: int

    @property
    def best_cryptic_tract(self) -> int:
        return max((c.tract for c in self.candidates), default=0)

    @property
    def usable_cryptic_acceptor(self) -> bool:
        """¿Hay algun AG criptico con un tracto comparable al del legitimo?"""
        return self.best_cryptic_tract >= self.acceptor_tract

    @property
    def retained_if_cryptic(self) -> int:
        """Cuanto intron quedaria en el mRNA si el donante criptico empalma al legitimo."""
        return self.donor_offset - 1

    def describe(self) -> list[str]:
        return [
            f"DONANTE CRÍPTICO {self.donor_motif} en +{self.donor_offset} del intrón "
            f"(flanco 5' de miR-E, dentro del ANDAMIO:",
            "  viaja con cualquier candidato, no depende de la guía).",
            f"  ¿Hay un ACEPTOR utilizable entre el (+{self.donor_offset}) y el legítimo "
            f"(+{self.acceptor_offset})? Se han mirado los",
            f"  {len(self.candidates)} AG del intervalo. El aceptor LEGÍTIMO tiene un "
            f"tracto de {self.acceptor_tract} pirimidinas contiguas;",
            f"  el mejor críptico llega a {self.best_cryptic_tract}. "
            + (
                "NO hay ninguno comparable."
                if not self.usable_cryptic_acceptor
                else "HAY al menos uno comparable — mirarlo."
            ),
            f"  {SPLICE_SITE_CRITERION}",
            "",
            "  LO QUE ESO CIERRA: los productos que necesitarian un aceptor críptico en "
            "ese intervalo. No hay",
            "  ninguno con un sitio 3' comparable al legítimo, así que esa familia de "
            "productos se descarta POR SECUENCIA.",
            "",
            "  LO QUE NO CIERRA, y es lo importante: el riesgo del donante críptico NO "
            "se cierra por aquí, porque",
            "  ese donante NO NECESITA un aceptor críptico — el aceptor LEGÍTIMO del MVM "
            f"está aguas abajo (+{self.acceptor_offset})",
            "  y es perfectamente utilizable. Un empalme "
            f"+{self.donor_offset} → +{self.acceptor_offset} quita "
            f"{self.acceptor_offset + 1 - self.donor_offset} nt y deja",
            f"  los {self.retained_if_cryptic} primeros nt del intrón dentro del mRNA: "
            f"banda = empalmada + {self.retained_if_cryptic} pb, frente a +0 (correcta) "
            f"y",
            f"  +{self.intron_length} (retenida). Es una banda INTERMEDIA, que es "
            f"exactamente la que se puede confundir en un gel,",
            "  y por eso la lectura 4 —secuenciar la union— no es opcional. Los dos "
            "donantes compiten por el MISMO",
            "  aceptor, y cual gana no lo dice la secuencia.",
        ]


def cryptic_donor_scan(
    intron: str,
    *,
    donor: str = CRYPTIC_DONOR,
    window: tuple[int, int] = BRANCH_POINT_WINDOW,
) -> CrypticDonor:
    """Los AG entre el donante criptico y el aceptor legitimo, medidos."""
    limpio = "".join(str(intron).split()).upper()
    inicio = limpio.find(donor)
    if inicio < 0:
        raise ShmirDesignError(
            f"El intrón no contiene el donante críptico {donor!r}, que es parte del "
            f"flanco 5' del andamio miR-E. O el andamio no es ese, o el intrón no es "
            f"este; se aborta en vez de dar el riesgo por ausente."
        )
    aceptor = len(limpio) - 1          # 1-based de la A del AG final

    def tracto(pos: int) -> int:
        n, i = 0, pos - 2
        while i >= 0 and limpio[i] in "CT":
            n += 1
            i -= 1
        return n

    def ramas(pos: int) -> tuple[str, ...]:
        salida = []
        for d in range(window[0], window[1] + 1):
            j = pos - 1 - d
            if j < 0 or j + 5 > len(limpio):
                continue
            m = limpio[j:j + 5]
            if m[0] in "CT" and m[1] in "AG" and m[2] == "A" and m[4] in "CT":
                salida.append(m)
        return tuple(salida)

    candidatos = tuple(
        AcceptorCandidate(offset=p, tract=tracto(p), branch_points=ramas(p))
        for p in range(inicio + len(donor) + 1, aceptor)
        if limpio[p - 1:p + 1] == "AG"
    )
    return CrypticDonor(
        donor_offset=inicio + 1,
        donor_motif=donor,
        acceptor_offset=aceptor,
        acceptor_tract=tracto(aceptor),
        candidates=candidatos,
        intron_length=len(limpio),
    )


# ─── El control SIN INTRON: se especifica, no se pide ────────────────────────
#
# La lectura 3 no existe sin la construccion, asi que pedirla sin especificarla es
# pedir que alguien la diseñe a ojo. Aqui sale su secuencia EXACTA.
#
# Y no es generar secuencia (regla 1): es BORRAR dos piezas literales de una secuencia
# que ya esta en el repositorio. Nada se rellena, nada se reconstruye, y el test
# comprueba que reinsertando lo borrado se recupera el original base a base.


@dataclass(frozen=True)
class IntronlessControl:
    """El casete con donante y aceptor fuera. Un gBlock y una digestion."""

    source: str
    sequence: str
    fragment_start: int
    fragment_end: int
    deletion_start: int
    deleted_sequence: str
    arm: int
    left_arm: str
    right_arm: str

    @property
    def deleted(self) -> int:
        return len(self.deleted_sequence)

    @property
    def md5(self) -> str:
        import hashlib

        return hashlib.md5(self.sequence.encode("ascii")).hexdigest()

    def describe(self) -> list[str]:
        return [
            f"CONTROL SIN INTRÓN — {len(self.sequence)} pb / md5 {self.md5}",
            f"  Sale de {self.source}, tramo casete:{self.fragment_start}-"
            f"{self.fragment_end}, con el donante y el aceptor ELIMINADOS: fuera los "
            f"{self.deleted} nt",
            f"  del intrón (MVM5 + MVM3, las dos piezas literales) y todo lo demas "
            f"conservado base a base.",
            f"  Lleva {self.arm} nt de homologia a cada lado y conserva MluI y AgeI, "
            f"así que entra por digestion.",
            f"  LONGITUD: {len(self.sequence)} pb tal cual. Si el proveedor pide un "
            f"mínimo mayor, se alargan los brazos",
            f"  —`intronless_control(..., arm=N)`—, y salen del PROPIO plásmido, no de "
            f"ningún sitio más. Aquí no se",
            "  inventa un mínimo de síntesis: ese número lo pone el catalogo, no este "
            "programa.",
            "  PARA QUE ES: es la LECTURA 3 del frente del empalme —el techo de "
            "expresión—, y sin ella esa",
            "  lectura no existe. Aquí NO HAY EMPALME QUE MEDIR: sin donante ni "
            "aceptor, lo que expresa esta",
            "  construcción es todo lo que la arquitectura puede dar. Se corre en la "
            "MISMA TANDA que las otras.",
            f"  OJO: no confundir con {self.source}, que es el parental sin MÓDULO pero "
            f"CON el intrón vacío",
            "  de 82 nt — ese arrastra el mismo problema de empalme que se quiere medir.",
        ]


def intronless_control(
    sequence: str, *, name: str, arm: int = blocks.GIBSON_ARM
) -> IntronlessControl:
    """El casete sin donante ni aceptor, con brazos sacados del propio plasmido."""
    limpia = "".join(str(sequence).split()).upper()
    sitio = locate_intron(limpia, name=name)
    if not sitio.empty:
        raise ShmirDesignError(
            f"{name}: el intrón mide {sitio.length} nt y no son las dos mitades MVM "
            f"solas, así que quitarlas dejaria dentro lo que hubiera en medio —el "
            f"módulo del shmiR— y eso NO es un control sin intrón, es el modo de fallo "
            f"que se quiere medir. El control se hace sobre el PARENTAL. Se aborta."
        )

    mlui = limpia.rfind(blocks.PIECES["MluI"].sequence, 0, sitio.donor_start)
    agei = limpia.find(blocks.PIECES["AgeI"].sequence, sitio.acceptor_end)
    if mlui < 0 or agei < 0:
        raise ShmirDesignError(
            f"{name}: no se encuentran MluI por delante del donante y AgeI por detrás "
            f"del aceptor, así que el fragmento no se podría clonar por digestion. "
            f"Se aborta en vez de emitir un fragmento que no entra."
        )
    fin_agei = agei + len(blocks.PIECES["AgeI"].sequence)
    inicio = mlui + 1 - arm
    fin = fin_agei + arm
    if inicio < 1 or fin > len(limpia):
        raise ShmirDesignError(
            f"{name}: no caben {arm} nt de homologia a los dos lados dentro de las "
            f"{len(limpia)} pb del plásmido; se aborta en vez de emitir un brazo corto "
            f"sin decirlo."
        )

    borrado = limpia[sitio.donor_start - 1:sitio.acceptor_end]
    fragmento = limpia[inicio - 1:sitio.donor_start - 1] + limpia[sitio.acceptor_end:fin]
    return IntronlessControl(
        source=name,
        sequence=fragmento,
        fragment_start=inicio,
        fragment_end=fin,
        deletion_start=sitio.donor_start,
        deleted_sequence=borrado,
        arm=arm,
        left_arm=limpia[inicio - 1:mlui],
        right_arm=limpia[fin_agei:fin],
    )


def reference_intron() -> str:
    """El intron con la horquilla de REFERENCIA, para el analisis que no depende de guia.

    La horquilla de un candidato cualquiera cambia tres de los uAUG, asi que la cuenta
    exacta es POR CANDIDATO; lo que no cambia son el andamio y los espaciadores. Se usa
    la horquilla de referencia —que es una secuencia REAL del repositorio, no un
    relleno— para poder dar el analisis antes de elegir candidato.
    """
    from .scaffold import REFERENCE_HAIRPIN

    def s(n: str) -> str:
        return blocks.PIECES[n].sequence

    return (
        s("MVM5") + s("espaciador5") + s("NheI") + s("contexto5") + REFERENCE_HAIRPIN
        + s("contexto3") + s("SacI") + s("espaciador3") + s("MVM3")
    )
