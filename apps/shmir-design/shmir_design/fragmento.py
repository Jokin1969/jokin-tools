"""El fragmento de síntesis: el intrón ENTERO, listo para pegar sobre la feature.

## Por qué los sitios de restricción salen

`NheI` y `SacI` existían para **digerir y ligar**: se pedía el módulo de 149 nt y se
metía en un plásmido que ya llevaba el intrón. El fragmento se manda a sintetizar
ENTERO, así que dentro del intrón esos 12 nt no cortan nada — son inertes, y ocupan
sitio en un tramo donante→punto de ramificación que ya está por encima del rango típico.

Salen por defecto y **no se borran**: `with_sites=True` los devuelve. Retirar una pieza
por defecto es una decisión; quitarla del código es perder la opción.

## Lo que se emite pasa a ser el intrón completo

Con el fragmento entero no hay ligación ni ensamblaje: se selecciona la feature del
intrón en SnapGene y se pega encima. **El plásmido crece exactamente lo que crece el
intrón** — un solo número que comprobar.

Y eso obliga a una condición que no es opcional: **los extremos del fragmento tienen que
ser los de la feature ANOTADA**, no los del intrón de GT a AG. Si coinciden, la
sustitución no puede descolocarse; si no, sale corrida y no da ningún error hasta
secuenciar.

## El desajuste de los diez nucleótidos, resuelto midiendo

En el `.dna` del casete la feature del intrón MVM va de 3129 a 3220 —92 nt— y el intrón
vacío del proyecto son 82 de GT a AG. La hipótesis era «contexto exónico anotado dentro
de la feature», y aquí se COMPRUEBA contra el casete versionado: los diez de más son
exactamente `exon5` (5 nt) y `exon3` (5 nt) de `blocks.PIECES`, una pieza versionada a
cada lado. Pegar 82 nt sobre una selección de 92 **borraría 10 nt de exón**.

Las dos piezas de exón se LEEN del casete y se contrastan con las versionadas: leerlas
sin contrastarlas daría el contexto del fichero que hubiera, y transcribirlas sin leer el
casete no comprobaría nada (principio nº 13).

## Los flancos son del PLÁSMIDO, no del intrón

El contexto exónico sale de la feature del casete receptor y no del registro de intrones,
y esto no es un detalle de implementación: el exón es del vector, y el mismo módulo
pegado en dos arquitecturas de intrón lleva los MISMOS 5 nt a cada lado. Lo que cambia
entre arquitecturas son los 10 nt siguientes — por eso la hoja de pedido destaca 15 y no
5: con 5 los dos fragmentos se ven idénticos en el extremo, que es justo lo que no hay
que creerse.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import blocks, introns, splicing
from .audit import Span
from .errors import ShmirDesignError
from .filters import FilterResult, FilterState, Verdict, overall_verdict
from .reference import sequence_md5

#: Cuántos nucleótidos de cada extremo se destacan en la hoja de pedido. NO son 5: con
#: los 5 del exón los dos fragmentos de las dos arquitecturas salen idénticos, y lo que
#: hay que poder distinguir de un vistazo es justo eso.
HIGHLIGHT = 15

#: El tramo de la feature del intrón MVM, REPORTADO del `.dna` del casete por el
#: responsable del proyecto (2026-09-05). No se usa para nada más que para CRUZARLO con
#: el tramo derivado del casete versionado: es un dato observado en otro fichero, y su
#: valor está en confirmar la derivación, no en sustituirla.
DECLARED_FEATURE_SPAN = (3129, 3220)
DECLARED_FEATURE_SOURCE = (
    "reportado del `.dna` del casete (SnapGene) por el responsable del proyecto el "
    "2026-09-05"
)

WHY_THE_SITES_LEAVE = (
    "NheI y SacI estaban para DIGERIR Y LIGAR: se pedía el módulo de "
    f"{blocks.MODULE_LENGTH} nt y se metía en un plásmido que ya llevaba el intrón. El "
    "fragmento se sintetiza ENTERO, así que dentro del intrón esos 12 nt no cortan "
    "nada — son inertes y ocupan sitio en un tramo donante→punto de ramificación que ya "
    "está por encima del rango típico. Salen por defecto y NO se borran: siguen "
    "disponibles como opción declarada, porque retirar algo por defecto es una decisión "
    "y quitarlo del código es perder la opción."
)

WHY_THE_ENDS_ARE_THE_CONDITION = (
    "La sustitución se hace seleccionando la feature del intrón y pegando encima, así "
    "que los extremos del fragmento tienen que ser LOS DE LA FEATURE ANOTADA y no los "
    "del intrón de GT a AG. Si coinciden, la sustitución no puede descolocarse. Si no, "
    "sale corrida y NO DA NINGÚN ERROR hasta secuenciar: la feature del casete son 92 "
    "nt y el intrón 82, y pegar 82 sobre una selección de 92 borraría 10 nt de exón."
)


#: El md5 de una secuencia NO se calcula aquí: se pide a `reference.sequence_md5`, que
#: es la definición del md5 de la secuencia CANÓNICA —sin blancos y en mayúsculas— y no
#: el del fichero. Dos cálculos del mismo número pueden dejar de coincidir sin que falle
#: nada, y este viaja en la cabecera del FASTA de fragmentos: lo compara la comprobación
#: del montaje contra el mismo número recalculado allí.
_md5 = sequence_md5


@dataclass(frozen=True)
class FeatureDelIntron:
    """Lo que la feature del intrón ANOTA en el casete, derivado de sus piezas.

    No se teclean coordenadas: `splicing.locate_intron` localiza el intrón buscando las
    dos mitades MVM y leyendo GT/AG, y de ahí se extiende una pieza de exón a cada lado
    comprobando que esté pegada. Un número escrito no puede validar el fichero del que
    salió (principio nº 13).
    """

    plasmid_name: str
    #: EL CASETE ENTERO del que se derivó, no su longitud. Está aquí, y no como un
    #: segundo parámetro de las funciones que lo recortan, porque una posición y una
    #: secuencia que llegan por separado no tienen nada que las obligue a compartir
    #: marco — el corolario del principio nº 13, y lo que caza
    #: `test_ningun_recorte_con_un_start_AJENO`. Dentro de este objeto la coordenada y
    #: la secuencia SON del mismo sitio por construcción.
    plasmid: str
    donor_start: int
    acceptor_end: int
    exon5: str
    exon3: str

    @property
    def plasmid_length(self) -> int:
        return len(self.plasmid)

    @property
    def sequence(self) -> str:
        """Lo que la feature cubre. Se recorta AQUÍ: la coordenada es suya."""
        return self.plasmid[self.start - 1 : self.end]

    def paste(self, fragment: str) -> str:
        """El plásmido con el fragmento pegado sobre la feature."""
        return self.plasmid[: self.start - 1] + fragment + self.plasmid[self.end :]

    def outside(self) -> str:
        """El plásmido FUERA del tramo que se sustituye, para comparar antes y después."""
        return self.plasmid[: self.start - 1] + self.plasmid[self.end :]

    def outside_after(self, pasted: str, fragment_length: int) -> str:
        """El plásmido de fuera del tramo, DESPUÉS de pegar un fragmento de ese tamaño.

        Comparado con `outside()` contesta la pregunta que importa: ¿se ha movido algo
        que no era el intrón? Un fragmento correcto con un tramo mal medido pega bien y
        borra exón, y eso no da error en ningún sitio.
        """
        return pasted[: self.start - 1] + pasted[self.start - 1 + fragment_length :]

    def ends_of(self, sequence: str) -> tuple[str, str]:
        """Los extremos de `sequence` con las longitudes de contexto de ESTA feature."""
        largo5, largo3 = len(self.exon5), len(self.exon3)
        return sequence[:largo5], sequence[len(sequence) - largo3 :]

    @property
    def start(self) -> int:
        return self.donor_start - len(self.exon5)

    @property
    def end(self) -> int:
        return self.acceptor_end + len(self.exon3)

    @property
    def span(self) -> Span:
        return Span(self.start, self.end)

    @property
    def length(self) -> int:
        return self.span.length

    @property
    def intron_length(self) -> int:
        """La feature MENOS su contexto exónico. Se resta lo que sobra, no se vuelve a
        medir el intrón: `splicing.locate_intron` ya lo midió y dos cuentas del mismo
        número pueden separarse."""
        return self.length - len(self.exon5) - len(self.exon3)

    def describe(self) -> str:
        return (
            f"Feature del intrón en {self.plasmid_name}: {self.start}-{self.end}, "
            f"{self.length} nt — el intrón son {self.intron_length} (de GT a AG) más "
            f"{len(self.exon5)} nt de exón por delante ({self.exon5}) y "
            f"{len(self.exon3)} por detrás ({self.exon3})."
        )


def locate_feature(cassette: str, *, name: str) -> FeatureDelIntron:
    """Deriva el tramo que cubre la feature del intrón. Aborta si el exón no está.

    Es la comprobación de la que depende todo lo demás: si el contexto exónico
    versionado no está pegado al intrón en el casete que se ha dado, ese casete no es
    éste y no se sabe qué cubre la feature. Se aborta en vez de emitir un fragmento con
    unos extremos que nadie ha comprobado.
    """
    limpia = "".join(str(cassette).split()).upper()
    sitio = splicing.locate_intron(limpia, name=name)

    extremos = {}
    for etiqueta, pieza, inicio in (
        ("exon5", "exon5", sitio.donor_start - len(blocks.PIECES["exon5"].sequence)),
        ("exon3", "exon3", sitio.acceptor_end + 1),
    ):
        esperado = blocks.PIECES[pieza].sequence
        if inicio < 1 or inicio + len(esperado) - 1 > len(limpia):
            raise ShmirDesignError(
                f"{name}: no caben los {len(esperado)} nt de contexto exónico "
                f"{etiqueta} junto al intrón (el intrón está en "
                f"{sitio.donor_start}-{sitio.acceptor_end} de {len(limpia)} nt). "
                f"Se aborta: sin contexto no se sabe qué cubre la feature."
            )
        leido = limpia[inicio - 1 : inicio - 1 + len(esperado)]
        if leido != esperado:
            raise ShmirDesignError(
                f"{name}: pegado al intrón, donde debería estar la pieza {etiqueta} "
                f"({esperado!r}, procedencia «{blocks.PIECES[pieza].source}»), hay "
                f"{leido!r}. O este casete no es el del proyecto o la pieza no es la "
                f"suya; se aborta en vez de emitir un fragmento cuyos extremos no "
                f"coinciden con los de la feature. {WHY_THE_ENDS_ARE_THE_CONDITION}"
            )
        extremos[etiqueta] = leido

    return FeatureDelIntron(
        plasmid_name=name,
        plasmid=limpia,
        donor_start=sitio.donor_start,
        acceptor_end=sitio.acceptor_end,
        exon5=extremos["exon5"],
        exon3=extremos["exon3"],
    )


def check_declared_span(feature: FeatureDelIntron) -> FilterResult:
    """Cruza el tramo DERIVADO con el reportado del `.dna`. Los dos, o no vale.

    Es la comprobación que cierra el desajuste: si los dos números coinciden, los diez
    nucleótidos de diferencia entre la feature (92) y el intrón (82) quedan EXPLICADOS
    —son las dos piezas de exón— en vez de supuestos.
    """
    declarado = f"{DECLARED_FEATURE_SPAN[0]}-{DECLARED_FEATURE_SPAN[1]}"
    derivado = f"{feature.start}-{feature.end}"
    if (feature.start, feature.end) != DECLARED_FEATURE_SPAN:
        return FilterResult(
            name="tramo_declarado",
            state=FilterState.FAIL,
            reason=(
                f"El tramo de la feature derivado del casete versionado es {derivado} "
                f"y el {DECLARED_FEATURE_SOURCE} es {declarado}. NO COINCIDEN: o el "
                f"casete del repositorio no es el del `.dna` o la feature está anotada "
                f"sobre otra cosa. Antes de pegar nada hay que aclararlo — una feature "
                f"corrida un nucleótido corre la sustitución entera sin dar error."
            ),
        )
    return FilterResult(
        name="tramo_declarado",
        state=FilterState.PASS,
        reason=(
            f"El tramo derivado del casete versionado ({derivado}, {feature.length} nt) "
            f"coincide con el {DECLARED_FEATURE_SOURCE} ({declarado}). Los "
            f"{feature.length - feature.intron_length} nt que separan la feature "
            f"({feature.length}) del intrón de GT a AG ({feature.intron_length}) son "
            f"CONTEXTO EXÓNICO ANOTADO DENTRO DE LA FEATURE: {len(feature.exon5)} nt "
            f"por delante ({feature.exon5}) y {len(feature.exon3)} por detrás "
            f"({feature.exon3}), las dos piezas versionadas `exon5` y `exon3`. Queda "
            f"comprobado, no supuesto."
        ),
    )


@dataclass(frozen=True)
class Fragment:
    """El fragmento que se manda a sintetizar, con sus comprobaciones."""

    intron_name: str
    label: str
    sequence: str
    intron: str
    module: str
    feature: FeatureDelIntron
    with_sites: bool
    checks: tuple[FilterResult, ...]

    @property
    def growth(self) -> int:
        """Cuánto crece el plásmido al pegar. Es UN número, y es el que se comprueba."""
        return len(self.sequence) - self.feature.length

    @property
    def plasmid_length(self) -> int:
        return self.feature.plasmid_length + self.growth

    @property
    def md5(self) -> str:
        return _md5(self.sequence)

    @property
    def intron_md5(self) -> str:
        """El md5 del intrón VACÍO de origen: identifica la ARQUITECTURA, no la guía."""
        return _md5(introns.get(self.intron_name).empty_sequence)

    @property
    def verdict(self) -> Verdict:
        return overall_verdict(self.checks)

    def head(self, nt: int = HIGHLIGHT) -> str:
        return self.sequence[:nt]

    def tail(self, nt: int = HIGHLIGHT) -> str:
        return self.sequence[-nt:]

    def check(self, name: str) -> FilterResult:
        for resultado in self.checks:
            if resultado.name == name:
                return resultado
        disponibles = ", ".join(r.name for r in self.checks)
        raise KeyError(f"No hay comprobación {name!r}; las que hay: {disponibles}.")


def _module(hairpin_sequence: str, *, with_sites: bool) -> str:
    def pieza(nombre: str) -> str:
        return blocks.PIECES[nombre].sequence

    nucleo = pieza("contexto5") + hairpin_sequence + pieza("contexto3")
    if with_sites:
        return pieza("NheI") + nucleo + pieza("SacI")
    return nucleo


def _check_ends(sequence: str, feature: FeatureDelIntron) -> FilterResult:
    delante, detras = feature.ends_of(sequence)
    if not sequence.startswith(feature.exon5) or not sequence.endswith(feature.exon3):
        return FilterResult(
            name="extremos_vs_feature",
            state=FilterState.FAIL,
            reason=(
                f"Los extremos del fragmento ({delante}… / "
                f"…{detras}) NO son los de la feature anotada "
                f"({feature.exon5}… / …{feature.exon3}). NO SE PEGA. "
                f"{WHY_THE_ENDS_ARE_THE_CONDITION}"
            ),
        )
    return FilterResult(
        name="extremos_vs_feature",
        state=FilterState.PASS,
        reason=(
            f"Los extremos del fragmento son los de la feature anotada "
            f"({feature.start}-{feature.end}): {feature.exon5} por delante y "
            f"{feature.exon3} por detrás, copiados de las piezas versionadas y leídos "
            f"del casete. La sustitución no puede descolocarse."
        ),
    )


def _check_sites(sequence: str, *, with_sites: bool) -> FilterResult:
    dianas = {n: blocks.PIECES[n].sequence for n in ("NheI", "SacI")}
    presentes = {n: sequence.count(s) for n, s in dianas.items()}
    if with_sites:
        malas = {n: c for n, c in presentes.items() if c != 1}
        if malas:
            return FilterResult(
                name="sitios",
                state=FilterState.FAIL,
                reason=(
                    f"Se han pedido los sitios de restricción y no aparecen una sola "
                    f"vez cada uno: {malas}. Se avisa en vez de mandarlo a sintetizar."
                ),
            )
        return FilterResult(
            name="sitios",
            state=FilterState.PASS,
            reason=(
                f"NheI ({dianas['NheI']}) y SacI ({dianas['SacI']}) VAN dentro, una vez "
                f"cada uno: es la OPCIÓN declarada, no lo de por defecto. "
                f"{WHY_THE_SITES_LEAVE}"
            ),
        )
    sobran = {n: c for n, c in presentes.items() if c}
    if sobran:
        return FilterResult(
            name="sitios",
            state=FilterState.FAIL,
            reason=(
                f"Los sitios de restricción tenían que salir y siguen apareciendo: "
                f"{sobran}. Puede ser la propia horquilla del candidato; se avisa en "
                f"vez de darlo por limpio."
            ),
        )
    return FilterResult(
        name="sitios",
        state=FilterState.PASS,
        reason=(
            f"Sin NheI ni SacI: 12 nt menos en el intrón. Siguen disponibles como "
            f"OPCIÓN declarada (`with_sites=True`). {WHY_THE_SITES_LEAVE}"
        ),
    )


def _check_paste(
    fragment_sequence: str, feature: FeatureDelIntron, *, intron: str
) -> tuple[FilterResult, ...]:
    """Pega el fragmento sobre la feature y comprueba EL RESULTADO.

    Es la única comprobación que mira lo que sale en vez de los ingredientes, y por eso
    es la que vale: que las piezas sean las correctas no dice que el plásmido resultante
    siga teniendo un intrón donde tenía uno.

    Son DOS comprobaciones y no una, porque preguntan cosas distintas:

      - `pegado` — que la sustitución sea exacta: el fragmento aparece UNA vez, donde
        tocaba, el resto del plásmido no se ha movido y el intrón sigue leyendo GT…AG.
        Vale para cualquier arquitectura, porque no supone ninguna.
      - `localizable` — que `splicing.locate_intron` siga encontrando el intrón en el
        plásmido resultante. Ese localizador busca **las dos mitades del MVM**, así que
        con otra arquitectura NO_APLICA, y eso hay que decirlo: de él salen las ventanas
        de cebador con las que se mide la eficiencia de empalme, y un intrón que la app
        no puede localizar es un frente que se queda sin medida. No es un fallo del
        fragmento; es una consecuencia de cambiar de intrón, y se ve aquí o no se ve.
    """
    pegado = feature.paste(fragment_sequence)
    crecimiento = len(fragment_sequence) - feature.length
    cuerpo = fragment_sequence.removeprefix(feature.exon5).removesuffix(feature.exon3)

    apariciones = pegado.count(fragment_sequence)
    fuera_antes = feature.outside()
    fuera_despues = feature.outside_after(pegado, len(fragment_sequence))
    donante, aceptor = cuerpo[:2], cuerpo[-2:]

    problemas = []
    if apariciones != 1:
        problemas.append(
            f"el fragmento aparece {apariciones} veces en el plásmido resultante"
        )
    if len(pegado) != feature.plasmid_length + crecimiento:
        problemas.append(
            f"el plásmido queda en {len(pegado)} pb y tenía que quedar en "
            f"{feature.plasmid_length + crecimiento}"
        )
    if fuera_despues != fuera_antes:
        problemas.append("el plásmido FUERA del tramo sustituido no es el mismo")
    if (donante, aceptor) != (
        splicing.DONOR_DINUCLEOTIDE, splicing.ACCEPTOR_DINUCLEOTIDE
    ):
        problemas.append(
            f"el intrón pegado empieza por {donante!r} y acaba en {aceptor!r}, y "
            f"tenían que ser {splicing.DONOR_DINUCLEOTIDE!r} y "
            f"{splicing.ACCEPTOR_DINUCLEOTIDE!r}"
        )

    if problemas:
        pegado_resultado = FilterResult(
            name="pegado",
            state=FilterState.FAIL,
            reason=(
                "Pegar el fragmento sobre la feature "
                f"{feature.start}-{feature.end} no da lo que tenía que dar: "
                + "; ".join(problemas)
                + ". NO SE PEGA."
            ),
        )
    else:
        pegado_resultado = FilterResult(
            name="pegado",
            state=FilterState.PASS,
            reason=(
                f"Pegado sobre {feature.start}-{feature.end} del casete: el fragmento "
                f"queda una sola vez y en su sitio, el resto del plásmido no se mueve, "
                f"y el intrón sigue leyendo {donante}…{aceptor}. El plásmido pasa de "
                f"{feature.plasmid_length} a {len(pegado)} pb — crece {crecimiento}, "
                f"que es exactamente lo que crece el intrón."
            ),
        )

    registro = introns.get(intron)
    de_piezas_mvm = (registro.five_piece, registro.three_piece) == ("MVM5", "MVM3")
    if not de_piezas_mvm:
        localizable = FilterResult(
            name="localizable",
            state=FilterState.NO_APLICA,
            reason=(
                f"`splicing.locate_intron` busca el intrón por las dos mitades del MVM "
                f"y {intron!r} no las lleva, así que sobre el plásmido con este "
                f"fragmento NO puede localizarlo. NO es un fallo del fragmento: es una "
                f"consecuencia de cambiar de arquitectura, y se dice porque de ese "
                f"localizador salen las ventanas de cebador con las que se mide la "
                f"eficiencia de empalme. Cambiar a este intrón deja ese frente sin "
                f"medida mientras el localizador siga siendo el del MVM."
            ),
        )
        return (pegado_resultado, localizable)

    try:
        sitio = splicing.locate_intron(pegado, name="el casete con el fragmento pegado")
    except ShmirDesignError as error:
        # rule2-ok: el fallo NO se traga — se convierte en el FilterResult `localizable`
        # con estado FAIL y con el mensaje original dentro. Relanzar tumbaría las otras
        # cuatro comprobaciones del fragmento, y aquí lo que se pide es un veredicto por
        # comprobación: la regla 3 sobre la 2.
        localizable = FilterResult(
            name="localizable",
            state=FilterState.FAIL,
            reason=(
                f"El intrón se ensambla de las piezas del MVM, así que "
                f"`splicing.locate_intron` tenía que encontrarlo en el plásmido "
                f"resultante, y no lo encuentra: {error}"
            ),
        )
    else:
        localizable = FilterResult(
            name="localizable",
            state=(
                FilterState.PASS if sitio.length == len(cuerpo) else FilterState.FAIL
            ),
            reason=(
                f"En el plásmido resultante el intrón se vuelve a localizar por sus "
                f"piezas: donante {sitio.donor} en {sitio.donor_start}, aceptor "
                f"{sitio.acceptor} en {sitio.acceptor_end}, {sitio.length} nt "
                + (
                    "— los mismos que se emitieron."
                    if sitio.length == len(cuerpo)
                    else f"y se emitieron {len(cuerpo)}: NO cuadra."
                )
            ),
        )
    return (pegado_resultado, localizable)


def build_fragment(
    hairpin,
    *,
    cassette: str,
    intron: str = "mvm_actual",
    with_sites: bool = False,
    label: str = "",
    name: str = "aav_casete.fa",
) -> Fragment:
    """Monta el fragmento de síntesis de una horquilla y lo comprueba.

    `cassette` es el casete receptor ENTERO: de él salen los extremos de la feature y
    contra él se comprueba que pegar el fragmento no descoloca nada.
    """
    limpio = "".join(str(cassette).split()).upper()
    feature = locate_feature(limpio, name=name)

    registro = introns.get(intron)
    if registro.retired:
        raise ShmirDesignError(
            f"El intrón {intron!r} está RETIRADO de la matriz y no se emite ningún "
            f"fragmento con él. Motivo registrado: {registro.retired}"
        )

    secuencia_horquilla = getattr(hairpin, "sequence", hairpin)
    modulo = _module(secuencia_horquilla, with_sites=with_sites)
    cuerpo = registro.with_module(modulo)
    fragmento_secuencia = feature.exon5 + cuerpo + feature.exon3
    crecimiento = len(fragmento_secuencia) - feature.length

    longitudes = FilterResult(
        name="longitudes",
        state=FilterState.PASS,
        reason=(
            f"Fragmento {len(fragmento_secuencia)} nt = {len(feature.exon5)} de exón + "
            f"{len(cuerpo)} de intrón + {len(feature.exon3)} de exón. Sustituye "
            f"{feature.length} nt, así que el plásmido crece {crecimiento} pb."
        ),
    )

    return Fragment(
        intron_name=intron,
        label=label,
        sequence=fragmento_secuencia,
        intron=cuerpo,
        module=modulo,
        feature=feature,
        with_sites=with_sites,
        checks=(
            check_declared_span(feature),
            _check_ends(fragmento_secuencia, feature),
            _check_sites(fragmento_secuencia, with_sites=with_sites),
            longitudes,
            *_check_paste(fragmento_secuencia, feature, intron=intron),
        ),
    )


# ─── La hoja de pedido ───────────────────────────────────────────────────────

WRAP = 60


def _wrap(secuencia: str) -> list[str]:
    return [secuencia[i : i + WRAP] for i in range(0, len(secuencia), WRAP)]


def fragment_order_sheet(fragment: Fragment) -> str:
    """Lo que hay que poder mirar de un vistazo ANTES de pegar.

    Los 15 nt de cada extremo van destacados por un motivo concreto: el módulo es el
    mismo en las dos arquitecturas de intrón y los flancos no, así que dos fragmentos
    distintos se parecen mucho. Comparar los extremos con la selección de SnapGene es lo
    único que se puede hacer a ojo antes de pegar.
    """
    feature = fragment.feature
    registro = introns.get(fragment.intron_name)
    etiqueta = f" — {fragment.label}" if fragment.label else ""
    lineas = [
        f"═══ Fragmento de síntesis{etiqueta} ═══",
        "",
        f"  Intrón de origen : {fragment.intron_name} ({registro.description})",
        f"  md5 del intrón   : {fragment.intron_md5}  "
        f"({len(registro.empty_sequence)} nt, vacío)",
        f"  md5 del fragmento: {fragment.md5}",
        "",
        f"  Longitud total   : {len(fragment.sequence)} nt",
        f"  Sustituye        : {feature.plasmid_name} {feature.start}-{feature.end} "
        f"({feature.length} nt, la feature del intrón)",
        f"  El plásmido crece: {fragment.growth} pb — de {feature.plasmid_length} a "
        f"{fragment.plasmid_length}",
        f"  Sitios NheI/SacI : {'DENTRO (opción declarada)' if fragment.with_sites else 'FUERA'}",
        "",
        "  ── Cómo se pega ──",
        "  Se selecciona la feature del intrón ENTERA en SnapGene y se pega el",
        "  fragmento encima. No hay digestión ni ensamblaje: el plásmido crece",
        f"  exactamente los {fragment.growth} pb que crece el intrón.",
        "",
        f"  ── Los {HIGHLIGHT} nt de cada extremo, para comprobarlos A OJO ──",
        f"  inicio: {fragment.head()}",
        f"          {'^' * len(feature.exon5)}{'-' * (HIGHLIGHT - len(feature.exon5))}"
        f"  ({len(feature.exon5)} de exón + {HIGHLIGHT - len(feature.exon5)} de intrón)",
        f"  final : {fragment.tail()}",
        f"          {'-' * (HIGHLIGHT - len(feature.exon3))}{'^' * len(feature.exon3)}"
        f"  ({HIGHLIGHT - len(feature.exon3)} de intrón + {len(feature.exon3)} de exón)",
        "",
        "  Los cinco de exón son los MISMOS en las dos arquitecturas de intrón; los",
        "  diez de al lado NO. Por eso se destacan quince y no cinco.",
        "",
        "  ── Secuencia ──",
    ]
    lineas.extend(f"    {t}" for t in _wrap(fragment.sequence))
    lineas.extend(["", "  ── Comprobaciones ──"])
    for resultado in fragment.checks:
        lineas.append(f"    [{resultado.state.value}] {resultado.name}")
        lineas.append(f"        {resultado.reason}")
    lineas.extend(["", f"  Veredicto: {fragment.verdict.value}"])
    return "\n".join(lineas)


#: Ancho de línea del FASTA de fragmentos.
FASTA_WRAP = 60


def fragment_record_name(fragment: Fragment, *, species: str = "") -> str:
    """El nombre del registro FASTA. UNA definición: lo escribe el emisor y lo LEE la
    comprobación del montaje, así que dos versiones dejarían de encontrarse."""
    trozos = [t for t in (species, fragment.label.replace(":", ""), "fragmento",
                          fragment.intron_name) if t]
    return "_".join(trozos)


def fragments_fasta(fragments, *, species: str = "") -> str:
    """El FASTA de fragmentos que viaja solo, con lo que hace falta para comprobarlo.

    La cabecera lleva la longitud, cuánto crece el plásmido, el tramo que sustituye y el
    **md5 de la secuencia**. Ese md5 no es decorado: `montaje.parse_fragments_fasta` lo
    recalcula y lo cruza, así que un FASTA retocado a mano por el camino se caza antes
    de compararlo con nada. Un fichero que viaja solo tiene que poder validarse solo.
    """
    lineas: list[str] = []
    for fragment in fragments:
        lineas.append(
            f">{fragment_record_name(fragment, species=species)} "
            f"longitud={len(fragment.sequence)} crece={fragment.growth} "
            f"sustituye={fragment.feature.plasmid_name}:{fragment.feature.start}-"
            f"{fragment.feature.end} intron={fragment.intron_name} "
            f"sitios={'dentro' if fragment.with_sites else 'fuera'} "
            f"md5={fragment.md5}"
        )
        lineas.extend(
            fragment.sequence[i : i + FASTA_WRAP]
            for i in range(0, len(fragment.sequence), FASTA_WRAP)
        )
    return "\n".join(lineas)
