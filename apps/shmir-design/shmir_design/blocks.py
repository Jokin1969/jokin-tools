"""Generador de bloques listos para pedir (tanda B).

Sobre un candidato ya calculado, monta las dos salidas y las comprueba. La arquitectura
es fija salvo dos variables — guia y pasajera — y todas las piezas se copian LITERALMENTE
de su procedencia: aqui no se reconstruye ni una base (regla 1).

    MluI  exon5'  MVM5'  esp5'  [ NheI  ctx5'  flanco5  PASAJERA  loop  GUIA  flanco3
    ctx3'  SacI ]  esp3'  MVM3'  exon3'  AgeI

  - **modulo NheI-SacI, 149 nt** — para intercambiar solo la horquilla en un plasmido
    que ya lleva el intron. Es lo que se usa normalmente.
  - **cassette MluI-AgeI, 318 pb** — intron completo, para montarlo de cero o cuando el
    modulo no pasa la comprobacion de abajo.

## La comprobacion que no es opcional

Los espaciadores se optimizaron para una horquilla concreta (la de 1018). Con otra guia
el contexto podria capturar los flancos del pri-miR y deshacer el tallo basal. Es un
fallo silencioso: el bloque se pediria igual y no funcionaria. Solo se ve plegando, y por
eso se pliega dos veces:

  1. el 97-mero aislado, que debe dar la estructura de SGEP;
  2. el **intron completo de 296 nt**, comprobando que el 97-mero conserva ahi la misma
     estructura que tenia solo.

Si falla (1), la horquilla en si no es estandar. Si falla (2), **el modulo NheI-SacI no
es seguro para ese candidato**: el intron de destino deshace la horquilla, y como ese
mismo intron esta dentro del cassette, el cassette con los espaciadores estandar tampoco
sirve.

Para ese caso hay una salida, y esta AUTORIZADA explicitamente:
`--reoptimizar-espaciadores` genera espaciadores de novo para esa guia con
`shmir_design/spacers.py`. Va apagado por defecto, porque genera secuencia. Cuando se
usa, el cassette resultante lleva un intron distinto y **deja de ser intercambiable con
el modulo NheI-SacI estandar**; la salida lo dice en cada sitio donde aparece.

Python 3.11+, solo libreria estandar salvo ViennaRNA, que es opcional (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from .errors import ShmirDesignError
from .hard_filters import longest_homopolymer as _longest_homopolymer
from .filters import FilterResult, FilterState
from .scaffold import (
    REFERENCE_HAIRPIN,
    SGEP_SCAFFOLD,
    Hairpin,
    ScaffoldSpec,
    build_hairpin,
)

MODULE_LENGTH = 149
CASSETTE_LENGTH = 318
INTRON_LENGTH = 296
HAIRPIN_LENGTH = 97

#: Brazos de homologia para Gibson, a cada lado.
GIBSON_ARM = 30

#: Homopolimero maximo permitido EN LA PARTE VARIABLE. El GGGG del contexto 3' es
#: nativo de SGEP y no cuenta: recortarlo cambiaria el andamio.
MAX_HOMOPOLYMER = 3

#: Enzimas heredadas de SGEP que viajan DENTRO del modulo. En el plasmido final no son
#: unicas, asi que no sirven para el clonaje; se avisa en la hoja de pedido.
INHERITED_SITES = MappingProxyType({"XhoI": "CTCGAG", "EcoRI": "GAATTC"})


@dataclass(frozen=True)
class Piece:
    """Una pieza fija, con su procedencia. Se copia literal, no se reconstruye."""

    sequence: str
    source: str

    def __len__(self) -> int:
        return len(self.sequence)


_PLASMIDO = "plásmido receptor"
_SGEP = "SGEP #111170"
_NOVO = "diseño de novo"

#: La especie del VECTOR. Las 12 piezas de `PIECES` no son valores por defecto ni
#: parametros: son el plasmido CONCRETO de PrP murino. Para otra especie no se
#: parametrizan — se sustituyen — y hasta que alguien traiga otro plasmido, todo lo que
#: se construye con ellas (modulo de 149, cassette de 318, hoja de pedido y control sin
#: intron) NO APLICA. Emitirlos con las piezas equivocadas seria peor que no emitirlos:
#: saldrian con la forma correcta.
VECTOR_SPECIES = "mouse"

VECTOR_DESCRIPTION = "pAAV_G130E_W144Y_mouse_PrP_4xmiR-183T (PrP murino)"


@dataclass(frozen=True)
class VectorApplicability:
    """¿Aplica el vector de este proyecto a la especie que se esta diseñando?"""

    species: str
    applies: bool
    note: str

    @property
    def state(self):
        from .filters import FilterState

        return FilterState.PASS if self.applies else FilterState.NO_APLICA


def vector_applies_to(species: str) -> VectorApplicability:
    """Lo dice la app, en vez de emitir el modulo con las piezas de otra especie."""
    from .species import resolve

    resuelta = resolve(species) if species else None
    slug = resuelta.slug if resuelta is not None else ""
    if slug == VECTOR_SPECIES:
        return VectorApplicability(
            species=slug, applies=True,
            note=(
                f"El vector de este proyecto es {VECTOR_DESCRIPTION} y la especie del "
                f"diseño es la suya: módulo, cassette, hoja de pedido y control sin "
                f"intrón aplican."
            ),
        )
    quien = resuelta.scientific if resuelta is not None else "una especie sin declarar"
    return VectorApplicability(
        species=slug, applies=False,
        note=(
            f"NO_APLICA: el vector de este proyecto es {VECTOR_DESCRIPTION}, y esta "
            f"corrida es de {quien}. Las 12 piezas del plásmido NO son un parámetro con "
            f"valor por defecto: son ese vector concreto, así que el MÓDULO NheI-SacI, "
            f"el CASSETTE MluI-AgeI, la HOJA DE PEDIDO y el CONTROL SIN INTRÓN no se "
            f"emiten. Emitirlos con las piezas murinas daria fragmentos con la forma "
            f"correcta y la secuencia equivocada, que es peor que no darlos. Para otra "
            f"especie hace falta OTRO plásmido, y entonces se sustituye `blocks.PIECES` "
            f"— no se parametriza."
        ),
    )


PIECES: MappingProxyType[str, Piece] = MappingProxyType(
    {
        "MluI": Piece("ACGCGT", _PLASMIDO),
        "exon5": Piece("AAGAG", _PLASMIDO),
        "MVM5": Piece("GTAAGGGTTTAAGGGATGGTTGGTTGGTGGGGTATTAATG", _PLASMIDO),
        "espaciador5": Piece("TACAATGATCCAAATCAAGA", _NOVO),
        "NheI": Piece("GCTAGC", _PLASMIDO),
        "contexto5": Piece("GAAGGCTCGAGAAGGTATAT", f"{_SGEP} posiciones 1739-1758"),
        "contexto3": Piece("CTTCAAGGGGCTAGAATTCG", f"{_SGEP} posiciones 1856-1875"),
        "SacI": Piece("GAGCTC", _PLASMIDO),
        "espaciador3": Piece(
            "ATGGATTTGTGTAAAGATCCAGTGCCTATGTATTGTTGGAAAGTA", _NOVO
        ),
        "MVM3": Piece("TTTAATTACCTGGAGCACCTGCCTGAAATCACTTTTTTTCAG", _PLASMIDO),
        "exon3": Piece("GTTGG", _PLASMIDO),
        "AgeI": Piece("ACCGGT", _PLASMIDO),
    }
)


def _s(nombre: str) -> str:
    return PIECES[nombre].sequence


@dataclass(frozen=True)
class Block:
    """Los dos niveles de salida de un candidato, con sus comprobaciones."""

    guide: str
    passenger: str
    hairpin: Hairpin
    module: str
    cassette: str
    intron: str
    module_gibson: str
    cassette_gibson: str | None
    checks: tuple[FilterResult, ...]
    structure_in_intron: str = ""
    structure_alone: str = ""
    #: Espaciadores usados. `standard=False` significa generados de novo para esta guia.
    spacers: object | None = None

    @property
    def custom_spacers(self) -> bool:
        return self.spacers is not None and not self.spacers.standard

    def check(self, name: str) -> FilterResult:
        for resultado in self.checks:
            if resultado.name == name:
                return resultado
        disponibles = ", ".join(r.name for r in self.checks)
        raise KeyError(f"No hay comprobación {name!r}; las que hay: {disponibles}.")

    @property
    def module_safe(self) -> bool:
        """El modulo solo es seguro si los DOS plegados pasaron. NOT_RUN no basta."""
        return all(
            self.check(n).state is FilterState.PASS
            for n in ("plegado_97mero", "plegado_en_intron")
        )

    @property
    def failed(self) -> tuple[FilterResult, ...]:
        return tuple(r for r in self.checks if r.state is FilterState.FAIL)

    @property
    def not_run(self) -> tuple[FilterResult, ...]:
        return tuple(r for r in self.checks if r.state is FilterState.NOT_RUN)


def _check_lengths(module: str, cassette: str, intron: str) -> FilterResult:
    esperado = {
        "modulo": (len(module), MODULE_LENGTH),
        "cassette": (len(cassette), CASSETTE_LENGTH),
        "intron": (len(intron), INTRON_LENGTH),
    }
    malos = {k: v for k, v in esperado.items() if v[0] != v[1]}
    if malos:
        detalle = "; ".join(f"{k}: {a} nt y se esperaban {b}" for k, (a, b) in malos.items())
        return FilterResult(
            name="longitudes",
            state=FilterState.FAIL,
            reason=f"Longitud incorrecta — {detalle}. Se aborta el pedido.",
        )
    return FilterResult(
        name="longitudes",
        state=FilterState.PASS,
        reason=(
            f"modulo {MODULE_LENGTH} nt, cassette {CASSETTE_LENGTH} pb, intrón "
            f"{INTRON_LENGTH} nt."
        ),
    )


def _check_unique_sites(cassette: str) -> FilterResult:
    conteos = {
        nombre: cassette.count(_s(nombre)) for nombre in ("NheI", "SacI")
    }
    repetidos = {k: v for k, v in conteos.items() if v != 1}
    if repetidos:
        detalle = "; ".join(f"{k} aparece {v} vez/veces" for k, v in repetidos.items())
        return FilterResult(
            name="sitios_unicos",
            state=FilterState.FAIL,
            reason=(
                f"{detalle}. La guía o la pasajera generan un segundo sitio: eso rompe "
                f"el clonaje por NheI/SacI, que es la via normal."
            ),
        )
    return FilterResult(
        name="sitios_unicos",
        state=FilterState.PASS,
        reason="GCTAGC (NheI) y GAGCTC (SacI) aparecen una sola vez cada uno.",
    )


def _check_no_outer_sites(module: str) -> FilterResult:
    presentes = [n for n in ("MluI", "AgeI") if _s(n) in module]
    if presentes:
        return FilterResult(
            name="sin_MluI_AgeI",
            state=FilterState.FAIL,
            reason=(
                f"El módulo contiene {', '.join(presentes)}: cortaria también dentro "
                f"del inserto al montar el cassette."
            ),
        )
    return FilterResult(
        name="sin_MluI_AgeI",
        state=FilterState.PASS,
        reason="El módulo no contiene ACGCGT (MluI) ni ACCGGT (AgeI).",
    )


def _check_homopolymers(guide: str, passenger: str) -> FilterResult:
    variable = f"{passenger}|{guide}"
    peor_base, peor = "", 0
    for tramo in (passenger, guide):
        base, largo = _longest_homopolymer(tramo)
        if largo > peor:
            peor_base, peor = base, largo
    if peor > MAX_HOMOPOLYMER:
        return FilterResult(
            name="homopolimeros",
            state=FilterState.FAIL,
            reason=(
                f"La parte variable ({variable}) tiene un homopolimero de {peor} "
                f"{peor_base}: el límite es {MAX_HOMOPOLYMER}."
            ),
        )
    return FilterResult(
        name="homopolimeros",
        state=FilterState.PASS,
        reason=(
            f"Sin homopolimeros de más de {MAX_HOMOPOLYMER} en la parte variable "
            f"(guía y pasajera). El GGGG del contexto 3' es nativo de SGEP y no cuenta: "
            f"recortarlo cambiaría el andamio."
        ),
    )


def _check_folding(
    hairpin: str, intron: str, *, available: bool
) -> tuple[FilterResult, FilterResult, str, str]:
    if not available:
        motivo = (
            "ViennaRNA no está instalado, así que no se ha comprobado el plegado. "
            "NOT_RUN no es PASS: los espaciadores se optimizaron para OTRA horquilla y "
            "sin plegar no se puede saber si esta sobrevive. `pip install ViennaRNA`."
        )
        return (
            FilterResult(name="plegado_97mero", state=FilterState.NOT_RUN, reason=motivo),
            FilterResult(
                name="plegado_en_intron", state=FilterState.NOT_RUN, reason=motivo
            ),
            "",
            "",
        )

    from .folding import dot_bracket  # noqa: PLC0415

    referencia = dot_bracket(REFERENCE_HAIRPIN)[0]
    sola = dot_bracket(hairpin)[0]
    if sola == referencia:
        aislado = FilterResult(
            name="plegado_97mero",
            state=FilterState.PASS,
            reason=f"El 97-mero aislado pliega como la referencia de SGEP. {sola}",
        )
    else:
        aislado = FilterResult(
            name="plegado_97mero",
            state=FilterState.FAIL,
            reason=(
                f"El 97-mero aislado NO pliega como la referencia: la horquilla en si "
                f"no es estándar.\n  esperada {referencia}\n  obtenida {sola}"
            ),
        )

    offset = intron.index(hairpin)
    dentro = dot_bracket(intron)[0][offset : offset + len(hairpin)]
    if dentro == sola:
        en_intron = FilterResult(
            name="plegado_en_intron",
            state=FilterState.PASS,
            reason=(
                f"Dentro del intrón de {INTRON_LENGTH} nt el 97-mero conserva la misma "
                f"estructura que aislado: el contexto no captura los flancos del pri-miR."
            ),
        )
    else:
        en_intron = FilterResult(
            name="plegado_en_intron",
            state=FilterState.FAIL,
            reason=(
                f"Dentro del intrón de {INTRON_LENGTH} nt el 97-mero NO conserva su "
                f"estructura: el contexto captura los flancos del pri-miR y deshace el "
                f"tallo basal. EL MÓDULO NheI-SacI NO ES SEGURO para esta guía, y el "
                f"cassette con estos espaciadores tampoco — el mismo intrón va dentro. "
                f"Hacen falta espaciadores reoptimizados, que es secuencia de novo y la "
                f"regla 1 no deja generarla sin autorización escrita.\n"
                f"  aislado {sola}\n  en intrón {dentro}"
            ),
        )
    return aislado, en_intron, dentro, sola


def _check_transgene(transgene) -> FilterResult:
    if transgene is None:
        return FilterResult(
            name="hits_transgen",
            state=FilterState.NOT_RUN,
            reason=(
                "No se paso el resultado del filtro del transgén, así que queda sin "
                "comprobar si este candidato apaga la propia construcción terapeutica. "
                "NOT_RUN no es PASS."
            ),
        )
    if transgene.hits:
        return FilterResult(
            name="hits_transgen",
            state=FilterState.FAIL,
            reason=(
                f"{len(transgene.hits)} sitio(s) en el casete del transgén: "
                + "; ".join(h.describe() for h in transgene.hits)
            ),
        )
    return FilterResult(
        name="hits_transgen",
        state=FilterState.PASS,
        reason="Cero sitios en el casete del transgén.",
    )


def _check_spacers(eleccion, pedido: bool, en_intron: FilterResult) -> FilterResult:
    """Que espaciadores lleva el bloque. Los de novo se marcan en toda la salida."""
    if eleccion is not None:
        return FilterResult(
            name="espaciadores",
            state=FilterState.PASS,
            reason=(
                f"GENERADOS DE NOVO para esta guía (5' {eleccion.spacer5}, 3' "
                f"{eleccion.spacer3}). Los estándar no conservaban la estructura del "
                f"97-mero dentro del intrón. El cassette NO es intercambiable con el "
                f"módulo NheI-SacI estándar."
            ),
        )
    if en_intron.state is FilterState.FAIL and not pedido:
        return FilterResult(
            name="espaciadores",
            state=FilterState.NOT_RUN,
            reason=(
                "Los espaciadores estándar no valen para esta guía y no se pidio "
                "reoptimizarlos. Con --reoptimizar-espaciadores se generan de novo para "
                "esta guía; hasta entonces no hay bloque válido. NOT_RUN no es PASS."
            ),
        )
    return FilterResult(
        name="espaciadores",
        state=FilterState.PASS,
        reason="Los espaciadores ESTÁNDAR del proyecto, sin tocar.",
    )


def build_block(
    guide: str,
    *,
    scaffold: ScaffoldSpec | None = None,
    recipient: str | None = None,
    transgene=None,
    reoptimize_spacers: bool = False,
    available: bool | None = None,
) -> Block:
    """Monta el modulo y el cassette de una guia, y los comprueba.

    `reoptimize_spacers` solo entra en juego si el 97-mero NO conserva su estructura
    dentro del intron con los espaciadores estandar. Genera secuencia de novo, asi que
    va apagado por defecto y lo que produce se marca en toda la salida.
    """
    # Import diferido a proposito: `spacers` necesita PIECES de este modulo, asi que
    # importarlo arriba seria un ciclo.
    from .spacers import STANDARD_3, STANDARD_5, choose_spacers  # noqa: PLC0415
    from .folding import VIENNA_AVAILABLE  # noqa: PLC0415

    usable = VIENNA_AVAILABLE if available is None else available
    hairpin = build_hairpin(guide, scaffold=scaffold or SGEP_SCAFFOLD)

    module = (
        _s("NheI") + _s("contexto5") + hairpin.sequence + _s("contexto3") + _s("SacI")
    )

    def montar(espaciador5: str, espaciador3: str) -> str:
        return _s("MVM5") + espaciador5 + module + espaciador3 + _s("MVM3")

    espaciador5, espaciador3 = STANDARD_5, STANDARD_3
    eleccion = None
    intron = montar(espaciador5, espaciador3)

    aislado, en_intron, estructura_intron, estructura_sola = _check_folding(
        hairpin.sequence, intron, available=usable
    )

    if (
        reoptimize_spacers
        and usable
        and en_intron.state is FilterState.FAIL
    ):
        busqueda = choose_spacers(
            hairpin=hairpin.sequence,
            structure_alone=estructura_sola,
            assemble=montar,
        )
        if busqueda.choice is not None:
            eleccion = busqueda.choice
            espaciador5, espaciador3 = eleccion.spacer5, eleccion.spacer3
            intron = montar(espaciador5, espaciador3)
            aislado, en_intron, estructura_intron, estructura_sola = _check_folding(
                hairpin.sequence, intron, available=usable
            )
            en_intron = FilterResult(
                name=en_intron.name,
                state=en_intron.state,
                reason=(
                    f"{en_intron.reason} CON ESPACIADORES GENERADOS DE NOVO para esta "
                    f"guía: los estándar no conservaban la estructura. El cassette "
                    f"resultante NO es intercambiable con el módulo NheI-SacI estándar."
                ),
            )

    cassette = _s("MluI") + _s("exon5") + intron + _s("exon3") + _s("AgeI")

    inicio = cassette.index(module)
    module_gibson = cassette[inicio - GIBSON_ARM : inicio + len(module) + GIBSON_ARM]

    cassette_gibson = None
    if recipient is not None:
        limpio = "".join(str(recipient).split()).upper()
        if cassette not in limpio:
            raise ShmirDesignError(
                "El plásmido receptor que se ha dado no contiene el cassette "
                "MluI-AgeI, así que no se pueden sacar de el los brazos de homologia. "
                "Se aborta en vez de inventar contexto."
            )
        posicion = limpio.index(cassette)
        if posicion < GIBSON_ARM or posicion + len(cassette) + GIBSON_ARM > len(limpio):
            raise ShmirDesignError(
                f"El plásmido receptor no tiene {GIBSON_ARM} pb a los dos lados del "
                f"cassette; se aborta en vez de recortar el brazo."
            )
        cassette_gibson = limpio[
            posicion - GIBSON_ARM : posicion + len(cassette) + GIBSON_ARM
        ]


    gibson_cassette = (
        FilterResult(
            name="gibson_cassette",
            state=FilterState.PASS,
            reason=f"Brazos de {GIBSON_ARM} pb tomados del plásmido receptor dado.",
        )
        if cassette_gibson is not None
        else FilterResult(
            name="gibson_cassette",
            state=FilterState.NOT_RUN,
            reason=(
                f"Los brazos de {GIBSON_ARM} pb del cassette caen FUERA del cassette, "
                f"en el plásmido receptor, que no se ha dado. No se inventan: pasa el "
                f"receptor y salen. NOT_RUN no es PASS."
            ),
        )
    )

    checks = (
        _check_lengths(module, cassette, intron),
        _check_unique_sites(cassette),
        _check_no_outer_sites(module),
        _check_homopolymers(hairpin.guide, hairpin.passenger.sequence),
        aislado,
        en_intron,
        _check_transgene(transgene),
        gibson_cassette,
        _check_spacers(eleccion, reoptimize_spacers, en_intron),
    )

    return Block(
        guide=hairpin.guide,
        passenger=hairpin.passenger.sequence,
        hairpin=hairpin,
        module=module,
        cassette=cassette,
        intron=intron,
        module_gibson=module_gibson,
        cassette_gibson=cassette_gibson,
        checks=checks,
        structure_in_intron=estructura_intron,
        structure_alone=estructura_sola,
        spacers=eleccion,
    )


# ─── Salidas ─────────────────────────────────────────────────────────────────

FASTA_WRAP = 60

CHECK_ORDER = (
    "longitudes",
    "espaciadores",
    "sitios_unicos",
    "sin_MluI_AgeI",
    "homopolimeros",
    "plegado_97mero",
    "plegado_en_intron",
    "hits_transgen",
    "gibson_cassette",
)

AVISO_ENZIMAS = (
    "XhoI (CTCGAG) y EcoRI (GAATTC) van DENTRO del módulo, heredadas de los contextos "
    "de SGEP. En el plásmido final NO son únicas, así que no sirven para el clonaje: "
    "el clonaje va por NheI/SacI o por síntesis directa del bloque."
)


def _wrap(sequence: str, width: int = FASTA_WRAP) -> str:
    return "\n".join(sequence[i : i + width] for i in range(0, len(sequence), width))


def _label(block: Block, especie: str, sufijo: str) -> str:
    return f"{especie}_{block.guide}_{sufijo}"


def blocks_fasta(blocks: list[Block], *, species: str) -> str:
    """FASTA con los dos niveles de cada candidato y cabeceras informativas."""
    partes: list[str] = []
    for block in blocks:
        estado = "modulo_seguro" if block.module_safe else "MODULO_NO_VERIFICADO"
        fallos = ",".join(r.name for r in block.failed) or "ninguno"
        espaciadores = (
            "ESPACIADORES_DE_NOVO_NO_INTERCAMBIABLE"
            if block.custom_spacers
            else "espaciadores_estandar"
        )
        for sufijo, secuencia, nota in (
            ("modulo_NheI_SacI", block.module, f"{MODULE_LENGTH} nt"),
            (
                "modulo_NheI_SacI_gibson",
                block.module_gibson,
                f"{MODULE_LENGTH}+{2 * GIBSON_ARM} nt, brazos de homologia",
            ),
            ("cassette_MluI_AgeI", block.cassette, f"{CASSETTE_LENGTH} pb"),
        ):
            partes.append(
                f">{_label(block, species, sufijo)} {nota} | {estado} | "
                f"{espaciadores} | fallos={fallos}\n"
                + _wrap(secuencia)
            )
        if block.cassette_gibson is not None:
            partes.append(
                f">{_label(block, species, 'cassette_MluI_AgeI_gibson')} "
                f"{CASSETTE_LENGTH}+{2 * GIBSON_ARM} pb, brazos del receptor | {estado}\n"
                + _wrap(block.cassette_gibson)
            )
    return "\n".join(partes)


def blocks_tsv(blocks: list[Block], *, species: str) -> str:
    """Una fila por candidato, con el resultado de CADA comprobacion en su columna."""
    columnas = [
        "especie", "guia", "pasajera",
        "modulo_149", "cassette_318", "modulo_gibson", "cassette_gibson",
        "longitud_modulo", "longitud_cassette", "longitud_intron",
        "modulo_seguro", "espaciadores", "espaciador5", "espaciador3",
        *(f"check:{n}" for n in CHECK_ORDER),
        "motivos",
    ]
    filas = [columnas]
    for block in blocks:
        estados = {r.name: r.state.value for r in block.checks}
        motivos = "; ".join(
            f"{r.name}={r.state.value}: {r.reason}"
            for r in block.checks
            if r.state is not FilterState.PASS
        )
        filas.append(
            [
                species,
                block.guide,
                block.passenger,
                block.module,
                block.cassette,
                block.module_gibson,
                block.cassette_gibson or "",
                str(len(block.module)),
                str(len(block.cassette)),
                str(len(block.intron)),
                "si" if block.module_safe else "no",
                "de_novo" if block.custom_spacers else "estandar",
                block.spacers.spacer5 if block.spacers else "",
                block.spacers.spacer3 if block.spacers else "",
                *(estados.get(n, "") for n in CHECK_ORDER),
                motivos,
            ]
        )
    return "\n".join(
        "\t".join(c.replace("\t", " ").replace("\n", " ") for c in fila)
        for fila in filas
    )


#: El error que arruinaria la RT-qPCR de empalme SIN DAR NINGUNA SEÑAL: los dos
#: cebadores dentro del ORF de PrP amplifican tambien el endogeno del tejido, asi que
#: sale banda, sale del tamaño esperado, y no es del vector. Va destacado en la hoja
#: porque un fallo que produce el resultado correcto-en-apariencia no se ve leyendo.
PRIMER_WARNING = (
    "**La especificidad de vector la da el cebador de AGUAS ARRIBA, y solo ese.** La "
    "ventana de aguas abajo entra en el ORF de PrP, así que un par con los DOS cebadores "
    "ahi amplificaria también el Prnp ENDOGENO del tejido: saldria banda, del tamaño "
    "esperado, y no sería del vector. **Es el error que arruinaria el ensayo sin dar "
    "ninguna señal.**"
)


def order_sheet(
    blocks: list[Block],
    *,
    species: str,
    intronless=None,
    rtpcr=None,
) -> str:
    """Hoja de pedido legible: secuencias en bloques de 60 y que enzimas usar.

    `intronless` es el control SIN INTRON (`splicing.IntronlessControl`): un fragmento
    mas que se pide igual que los demas, y sin el la lectura 3 del frente del empalme no
    existe. `rtpcr` es el plan de la RT-PCR de empalme, que trae el aviso del cebador.
    """
    if not blocks and intronless is None and rtpcr is None:
        return (
            "No hay ningún bloque que pedir: la selección está vacía. No se emite hoja "
            "de pedido en blanco."
        )
    if not blocks:
        lineas = [f"═══ Hoja de pedido — {species} ═══", ""]
        _extras(lineas, intronless, rtpcr)
        return "\n".join(lineas)

    lineas = [
        f"═══ Hoja de pedido — {species} ═══",
        "",
        f"  {len(blocks)} candidato(s). Dos niveles por candidato:",
        f"    · módulo NheI-SacI, {MODULE_LENGTH} nt — intercambia solo la horquilla en "
        f"un plásmido que ya lleva el intrón",
        f"    · cassette MluI-AgeI, {CASSETTE_LENGTH} pb — intrón completo, para montar "
        f"de cero",
        "",
        f"  ⚠  {AVISO_ENZIMAS}",
        "",
    ]

    for numero, block in enumerate(blocks, start=1):
        lineas.append(f"── Candidato {numero} — guía {block.guide} ──")
        lineas.append(f"  pasajera {block.passenger}")
        if block.custom_spacers:
            lineas.append("")
            lineas.extend(
                f"  {t}" for t in block.spacers.format_text().splitlines()
            )
            lineas.append("")
        if not block.module_safe:
            lineas.append(
                "  ⚠  MÓDULO NO VERIFICADO: no se ha podido confirmar que la horquilla "
                "sobreviva dentro del intrón."
            )
        for resultado in block.checks:
            if resultado.state is not FilterState.PASS:
                lineas.append(f"  ⚠  {resultado.name}: {resultado.reason}")
        for titulo, secuencia in (
            (f"módulo NheI-SacI ({len(block.module)} nt)", block.module),
            (
                f"módulo + brazos Gibson ({len(block.module_gibson)} nt)",
                block.module_gibson,
            ),
            (f"cassette MluI-AgeI ({len(block.cassette)} pb)", block.cassette),
        ):
            lineas.append(f"  {titulo}:")
            lineas.extend(f"    {t}" for t in _wrap(secuencia).splitlines())
        if block.cassette_gibson is not None:
            lineas.append(
                f"  cassette + brazos Gibson ({len(block.cassette_gibson)} pb):"
            )
            lineas.extend(
                f"    {t}" for t in _wrap(block.cassette_gibson).splitlines()
            )
        lineas.append("")

    lineas.append("  Clonaje: NheI + SacI para el módulo; MluI + AgeI para el cassette.")
    lineas.append(f"  {AVISO_ENZIMAS}")
    _extras(lineas, intronless, rtpcr)
    return "\n".join(lineas)


def _extras(lineas: list[str], intronless, rtpcr) -> None:
    """El control sin intron y el aviso del cebador, al final y con su titulo."""
    if intronless is not None:
        lineas.extend(["", "── Fragmento CONTROL SIN INTRÓN ──"])
        lineas.extend(f"  {t}" for t in intronless.describe())
        lineas.append("  secuencia:")
        lineas.extend(f"    {t}" for t in _wrap(intronless.sequence).splitlines())
    if rtpcr is not None:
        lineas.extend(["", "── RT-PCR de empalme: ventanas de cebador ──"])
        lineas.append(f"  {rtpcr.upstream.describe()}")
        lineas.append(f"  {rtpcr.downstream.describe()}")
        lineas.append(f"  ⚠  {PRIMER_WARNING}")
