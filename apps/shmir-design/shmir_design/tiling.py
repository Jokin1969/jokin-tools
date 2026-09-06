"""Tiling del 3'UTR y contadores de referencia (pasos 3 y 15).

Trocea el 3'UTR en ventanas solapantes de 22 nt, evalua cada una con todos los filtros
disponibles y cuenta dos cosas DISTINTAS:

- `biofisicos_ok`: ventanas que superan TODOS los filtros biofisicos —GC, homopolimero,
  asimetria, G4 diana, G4 guia y zona prohibida de poliadenilacion— y solo esos. Es el
  contador de referencia: no depende de ningun recurso externo, asi que es comprobable
  sin miRBase y sin red.
- `aptas`: ventanas con veredicto PASS, es decir que ademas superan los filtros
  externos. Con miRBase ausente esto es 0, porque la seed queda en NOT_RUN y NOT_RUN no
  es PASS (regla 3).

Confundir los dos contadores es exactamente el error que hace que un candidato
incompleto parezca aprobado. Por eso son dos nombres, dos metodos y dos columnas.

Sitios independientes = bloques de posiciones de inicio contiguas entre las que pasan.

Este modulo NO retila tras enmascarar repeticiones (paso 2, pendiente): cuando entre,
el enmascarado va ANTES de tilar, no despues, porque una ventana parcialmente solapada
con un elemento repetitivo hay que reevaluarla, no tacharla.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .accessibility import NOT_ASKED, Accessibility, accessibility_of
from .anatomy import Anatomy, Region, RegionSource, TileRange
from .coords import Frame, label, tiled_frame
from .apa import ApaAssessment, ApaSites, MeasuredApa, apa_assessment
from .errors import ShmirDesignError
from .filters import (
    FilterResult,
    FilterState,
    Verdict,
    biophysical_ok,
    check_substitution,
    overall_verdict,
)
from .masking import RepeatMask, apply_mask, filter_polymorphic, filter_repeats
from .hard_filters import (
    DEFAULT_THRESHOLDS,
    WINDOW_SIZE,
    AsymmetryModel,
    Thresholds,
    WindowEvaluation,
    evaluate_window,
)
from .polya import (
    POLYA_COLUMNS,
    Aviso,
    PolyAAnnotation,
    PolyAMode,
    PolyASignal,
    annotate_polya,
    Tercio,
    Window,
    annotate_3utr,
    find_polya_signals,
    promote_by_measurement,
    normalize_sequence,
)
from .mirna import AbundanceList, MatureSet, filter_seed_collision
from .scaffold import passenger_from_guide
from .seed_load import SEED_LOAD_SKIPPED, SeedLoad, Utr3Set, seed_load
from .seeds import SeedSet, bootstrap_expiry_note, filter_seed
from .specificity import (
    SpecificityDatabase,
    SpecificityResult,
    TransgeneResult,
    filter_specificity,
    filter_transgene,
)
from .reference import sequence_md5
from .thermo import turner_asymmetry


#: Estado por defecto del filtro de especificidad: sin base, NOT_RUN.
_ESPECIFICIDAD_SIN_BASE = FilterResult(
    name="especificidad",
    state=FilterState.NOT_RUN,
    reason=(
        "No hay base de RefSeq RNA cargada, así que el filtro de especificidad no se "
        "ejecuta. NOT_RUN no es PASS."
    ),
)


#: Estado por defecto de la colision de seed: sin miRBase, NOT_RUN.
_SEED_COLISION_SIN_BASE = FilterResult(
    name="seed_colision",
    state=FilterState.NOT_RUN,
    reason=(
        "No hay tabla de maduros de miRBase cargada, así que no se puede saber si la "
        "seed de esta guía coincide con la de un miARN endogeno. NOT_RUN no es PASS."
    ),
)


#: Estado por defecto del filtro del transgen: sin casete, NOT_RUN.
_TRANSGEN_SIN_BASE = FilterResult(
    name="transgen",
    state=FilterState.NOT_RUN,
    reason=(
        "No hay casete del transgén cargado, así que queda sin comprobar si el "
        "candidato apaga la propia construcción terapeutica. NOT_RUN no es PASS."
    ),
)


def _seed_bootstrap(
    guide: str, seeds: SeedSet | None, mature: MatureSet | None,
    *, sustituto: FilterResult | None = None,
) -> FilterResult:
    """El filtro `seed` de la lista de arranque, o SUSTITUIDO si esta el de verdad.

    `seed` y `seed_colision` responden a la MISMA pregunta con distinta profundidad. Si
    hay tabla de maduros de miRBase cargada, dejar los dos daria dos columnas que pueden
    contradecirse, y la peor de las dos —la de doce seeds— parece igual de autorizada.
    Asi que cuando esta el filtro real, este se retira diciendolo.

    SALIA `NO_APLICA` Y ERA EL ESTADO EQUIVOCADO (2026-09-02): `NO_APLICA` dice «a este
    candidato NO se le hace esta pregunta», y aqui si se le hace — la contesta la columna
    de al lado. `SUSTITUIDO` lo dice, NOMBRA al sustituto, y `check_substitution` impide
    que exista uno cuyo sustituto este en `NOT_RUN`: ahi la pregunta se perderia entre
    las dos columnas pareciendo resuelta en las dos.
    """
    if mature is not None:
        return check_substitution(
            FilterResult(
                name="seed",
                state=FilterState.SUSTITUIDO,
                reason=(
                    "La contesta `seed_colision`, que usa la tabla de maduros completa "
                    "y distingue colisión abundante (FAIL) de colisión anotada (aviso). "
                    "SUSTITUIDO no es PASS ni es «no aplica»: la pregunta SÍ se hace y "
                    "la respuesta está en la columna seed_colision."
                ),
            ),
            sustituto=sustituto,
        )
    return filter_seed(guide, seeds)


def tile_positions(utr_length: int, window_size: int = WINDOW_SIZE) -> list[int]:
    """Posiciones de inicio (1-based) de todas las ventanas que caben."""
    if utr_length < 1:
        raise ValueError(
            f"Longitud de 3'UTR invalida ({utr_length}); se aborta el tiling."
        )
    if window_size < 1:
        raise ValueError(
            f"Tamaño de ventana invalido ({window_size}); se aborta el tiling."
        )
    return list(range(1, utr_length - window_size + 2))


def independent_sites(positions: Iterable[int]) -> list[tuple[int, int]]:
    """Agrupa posiciones contiguas en sitios. Devuelve (inicio, fin) de cada bloque."""
    ordenadas = sorted(set(positions))
    if not ordenadas:
        return []
    sites: list[tuple[int, int]] = []
    inicio = anterior = ordenadas[0]
    for position in ordenadas[1:]:
        if position == anterior + 1:
            anterior = position
            continue
        sites.append((inicio, anterior))
        inicio = anterior = position
    sites.append((inicio, anterior))
    return sites


@dataclass(frozen=True)
class TiledWindow:
    window: Window
    evaluation: WindowEvaluation
    zona_prohibida: FilterResult
    seed: FilterResult
    repeticiones: FilterResult
    tercio: Tercio | None
    riesgo_APA: bool
    apa_aplica: bool = True
    region: Region = Region.UTR3
    inicio_3utr: int | None = None
    fin_3utr: int | None = None
    cruza_frontera: bool = False
    apa_upstream: tuple[PolyASignal, ...] = ()
    senales_debiles: tuple[PolyASignal, ...] = ()
    estricto_ok: bool = True
    especificidad: FilterResult | None = None
    transgen: FilterResult | None = None
    polya: PolyAAnnotation | None = None
    seed_colision: FilterResult | None = None
    #: Numeros comparativos, nunca veredictos: por eso NO entran en `filters`.
    carga_seed: SeedLoad | None = None
    accesibilidad: Accessibility | None = None
    apa: ApaAssessment | None = None
    #: Resultados completos, para que la tabla comparativa pueda dar los recuentos de
    #: hits por numero de desapareamientos y no solo el estado del filtro.
    especificidad_detalle: SpecificityResult | None = None
    transgen_detalle: TransgeneResult | None = None
    #: Eje de VIABILIDAD CLINICA, aparte de `repeticiones`: una repeticion polimorfica
    #: en longitud da respondedores y no respondedores por variacion de LONGITUD, y
    #: gnomAD —que anota sustituciones— capta mal esa variacion. Son dos ejes y por eso
    #: son dos columnas.
    repeticion_polimorfica: FilterResult | None = None

    @property
    def bandera_polyA_debil(self) -> bool:
        """Solapa una variante rara: no excluye, penaliza el ranking."""
        return bool(self.senales_debiles)

    @property
    def filters(self) -> tuple[FilterResult, ...]:
        return self.evaluation.filters + (
            self.zona_prohibida,
            self.repeticiones,
            *( (self.repeticion_polimorfica,)
               if self.repeticion_polimorfica is not None else () ),
            self.seed,
            self.especificidad or _ESPECIFICIDAD_SIN_BASE,
            self.transgen or _TRANSGEN_SIN_BASE,
            self.seed_colision or _SEED_COLISION_SIN_BASE,
        )

    def filter(self, name: str) -> FilterResult:
        for result in self.filters:
            if result.name == name:
                return result
        disponibles = ", ".join(r.name for r in self.filters)
        raise KeyError(
            f"La ventana no tiene ningún filtro {name!r}; los que hay: {disponibles}."
        )

    @property
    def biofisicos_ok(self) -> bool:
        return biophysical_ok(list(self.filters))

    @property
    def verdict(self) -> Verdict:
        return overall_verdict(list(self.filters))

    @property
    def failure_reasons(self) -> str:
        return "; ".join(
            f"{r.name}={r.state.value}: {r.reason}"
            for r in self.filters
            if r.state is not FilterState.PASS
        )


@dataclass(frozen=True)
class TilingReport:
    utr_length: int
    window_size: int
    windows: tuple[TiledWindow, ...]
    signals: tuple[PolyASignal, ...]
    anatomy: Anatomy | None = None
    specificity_db: SpecificityDatabase | None = None
    avisos: tuple[Aviso, ...] = ()
    seeds: SeedSet | None = None
    mask: RepeatMask | None = None
    thresholds: Thresholds = DEFAULT_THRESHOLDS
    tile_range: TileRange | None = None
    transgene_db: SpecificityDatabase | None = None
    mature: MatureSet | None = None
    abundance: AbundanceList | None = None
    utr3_set: Utr3Set | None = None
    accessibility: bool = False
    apa_sites: ApaSites | None = None
    #: La tabla de APA MEDIDO ya colocada sobre esta secuencia, si la hay. Es lo
    #: que promueve a APA_POSIBLE las señales con uso medido y lo que da el techo
    #: por tramos; `None` significa que no hay medida para esta secuencia y que
    #: `riesgo_APA` sigue siendo una PREDICCION.
    measured_apa: "MeasuredApa | None" = None
    #: POR QUE no hay medida, cuando no la hay. Son TRES estados y `measured_apa=None`
    #: no los distingue: no hay fichero / hay fichero y no habla de esta secuencia / se
    #: excluyo a proposito. Si el informe dijera lo mismo de los tres, nadie sabria si
    #: hay que subir un fichero o si el que hay es de otro gen.
    apa_missing_reason: str = ""
    #: Si la medida se EXCLUYO a proposito, el motivo escrito. Vacio = no se excluyo.
    #: Va aqui y no en una nota aparte porque tiene que viajar al veredicto: sin el,
    #: «se decidio no usarla» y «no habia» son el mismo `measured_apa=None`.
    apa_excluded_reason: str = ""
    polya_mode: PolyAMode = PolyAMode.ESCALONADO
    #: Longitud y md5 CANONICO de la secuencia que se analizo. Sin esto no hay forma de
    #: saber que se analizo: la errata del 3'UTR fabricado se detecto por longitud
    #: contra las coordenadas declaradas.
    sequence_length: int = 0
    sequence_md5: str = ""

    @property
    def frame(self) -> Frame:
        """El espacio en que van las coordenadas de LO TILADO. Se DERIVA, no se pone.

        Un solo sitio donde se decide. Cuando cada modulo lo suponia por su cuenta,
        cuatro de ellos supusieron `3utr` sobre un tilado de transcrito y salieron
        `3utr:1784`, `3utr:1185`, `3utr:1398` y `3utr:1856` — coordenadas del
        transcrito etiquetadas como 3'UTR, y ninguna dio error hasta que `coords` puso
        el techo. Quien pinte posiciones de este informe pide el marco aqui.
        """
        return tiled_frame(self.anatomy)

    def utr3_of(self, position: int) -> int | None:
        """`position` (en el marco de lo tilado) llevada al 3'UTR, o `None` si no cae.

        `None` no es un fallo: en un tilado de transcrito hay posiciones —las del CDS y
        las del 5'UTR— que sencillamente no estan en el 3'UTR. Quien pinte un mapa del
        3'UTR tiene que decidir que hace con ellas, y para decidirlo tiene que verlas.
        """
        if self.anatomy is None:
            return position
        return self.anatomy.utr3_position(position)

    @property
    def utr3_length(self) -> int:
        """Longitud del 3'UTR de esta corrida, que NO es la de lo tilado."""
        return self.utr_length if self.anatomy is None else self.anatomy.utr3_length

    def biofisicos_ok(self) -> int:
        return sum(1 for w in self.windows if w.biofisicos_ok)

    def aptas(self) -> int:
        return sum(1 for w in self.windows if w.verdict is Verdict.PASS)

    def sites_biofisicos(self) -> list[tuple[int, int]]:
        return independent_sites(
            w.window.start for w in self.windows if w.biofisicos_ok
        )

    def sites_aptas(self) -> list[tuple[int, int]]:
        return independent_sites(
            w.window.start for w in self.windows if w.verdict is Verdict.PASS
        )

    def not_run_counts(self) -> dict[str, int]:
        """En cuantas ventanas quedo NOT_RUN cada filtro. Mira todas, no la primera."""
        counts: dict[str, int] = {}
        for window in self.windows:
            for result in window.filters:
                if result.state is FilterState.NOT_RUN:
                    counts[result.name] = counts.get(result.name, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def format_text(self) -> str:
        lines = [
            f"3'UTR de {self.utr_length} nt — ventanas de {self.window_size} nt",
            f"  ventanas:        {len(self.windows)}",
            f"  biofisicos_ok:   {self.biofisicos_ok()} "
            f"({len(self.sites_biofisicos())} sitio(s) independiente(s))",
            f"  aptas (PASS):    {self.aptas()} "
            f"({len(self.sites_aptas())} sitio(s) independiente(s))",
        ]

        if self.mask is None:
            lines.append(
                "  repeticiones:    NOT_RUN — sin máscara de rmsk cargada (paso 1 sin "
                "ejecutar)."
            )
        else:
            lines.append(
                f"  repeticiones:    {len(self.mask.intervals)} intervalo(s) de "
                f"{self.mask.source}; se retilo sobre la secuencia enmascarada."
            )

        if self.seeds is None:
            lines.append(
                "  seed:            NOT_RUN — sin miRBase cargado, ninguna ventana "
                "puede declararse apta (regla 3)."
            )
        else:
            lines.append(f"  seed:            {self.seeds.source}")
            if self.seeds.is_bootstrap:
                lines.append(
                    "                   AVISO: es una lista de arranque para probar la "
                    "mecanica, NO un filtro real. El filtro real necesita mature.fa de "
                    "miRBase completo."
                )
                caducada = bootstrap_expiry_note()
                if caducada is not None:
                    lines.append(f"                   {caducada}")

        sin_correr = self.not_run_counts()
        if sin_correr:
            lines.append("  filtros que no llegaron a correr (NOT_RUN no es PASS):")
            lines.extend(
                f"    {name}: NOT_RUN en {count}/{len(self.windows)} ventanas"
                for name, count in sin_correr.items()
            )

        for aviso in self.avisos:
            lines.append("")
            lines.append(f"  ⚠  AVISO [{aviso.code}]")
            lines.append(f"     {aviso.message}")

        lines.append("")
        lines.append("La lista completa de ventanas está en el TSV (format_tsv).")
        return "\n".join(lines)

    def format_tsv(self) -> str:
        # Toda coordenada, etiquetada con su espacio: `3utr:449` o `tx:1398`. La
        # cabecera de la columna no viaja con la celda.
        marco = self.frame
        filtros = [r.name for r in self.windows[0].filters] if self.windows else []
        columns = (
            ["inicio", "fin", "region", "inicio_3utr", "fin_3utr", "diana", "guia", "tercio"]
            + list(POLYA_COLUMNS)
            + filtros
            + ["biofisicos_ok", "riesgo_APA", "veredicto", "motivos"]
        )
        rows = [columns]
        for tiled in self.windows:
            rows.append(
                [
                    label(tiled.window.start, marco),
                    label(tiled.window.end, marco),
                    tiled.region.value,
                    label(tiled.inicio_3utr, Frame.UTR3),
                    label(tiled.fin_3utr, Frame.UTR3),
                    tiled.evaluation.sequence,
                    tiled.evaluation.guide,
                    tiled.tercio.value if tiled.tercio else "",
                ]
                + [
                    # La etiqueta la pone `PolyAAnnotation.as_columns`, que es quien sabe
                    # de que posicion habla. Aqui habia un `_con_marco` que la ponia solo
                    # para el TSV, asi que la tabla de la pagina sacaba el entero desnudo:
                    # dos sitios haciendo lo mismo y uno olvidandose.
                    tiled.polya.as_columns()[c] if tiled.polya else ""
                    for c in POLYA_COLUMNS
                ]
                + [r.state.value for r in tiled.filters]
                + [
                    str(tiled.biofisicos_ok),
                    str(tiled.riesgo_APA) if tiled.apa_aplica else "NO_APLICA",
                    tiled.verdict.value,
                    tiled.failure_reasons,
                ]
            )
        return "\n".join(
            "\t".join(_tsv_safe(field) for field in row) for row in rows
        )


def _tsv_safe(field: str) -> str:
    return field.replace("\t", " ").replace("\r", " ").replace("\n", " ")


#: Centinela de «resuelvela tu». No es `None` a proposito: `None` significaba «no hay
#: medida» y era indistinguible de «nadie se acordo de pasarla», que es el fallo que esto
#: cierra. Un centinela que se confunde con un dato legitimo no es un centinela — misma
#: leccion que el espaciador vacio (errata nº 16).
#:
#: Es PUBLICO porque un llamador que quiera decir explicitamente «resuelvela tu» tiene
#: que poder escribirlo — sin un nombre, la unica forma seria omitir el argumento, y
#: entonces no hay manera de distinguir «lo decidi» de «no me acorde».
RESOLVER_MEDIDA = object()


def tile_utr(
    sequence: str,
    *,
    window_size: int = WINDOW_SIZE,
    seeds: SeedSet | None = None,
    mask: RepeatMask | None = None,
    anatomy: Anatomy | None = None,
    tile_range: TileRange | None = None,
    polya_mode: PolyAMode = PolyAMode.ESCALONADO,
    specificity_db: SpecificityDatabase | None = None,
    transgene_db: SpecificityDatabase | None = None,
    mature: MatureSet | None = None,
    abundance: AbundanceList | None = None,
    utr3_set: Utr3Set | None = None,
    #: DONDE contar la carga de seed. `None` = en todas las escaneables, que es lo que
    #: hace el CLI: una corrida por lotes se lo puede permitir. La PAGINA acota al panel.
    #:
    #: POR QUE HAY QUE ACOTARLO, medido el 2026-09-02 con el transcriptoma ya dentro:
    #: cada ventana barre el fichero ENTERO —0,4-0,7 s sobre 84 MB— y son 407 las que
    #: pasan los biofisicos, o sea 3-4 MINUTOS, y en CADA rerun de la pagina. Sin el
    #: fichero la corrida entera tarda 0,33 s.
    #:
    #: Y SE PUEDE ACOTAR porque `carga_seed` no alimenta ninguna seleccion ni ningun
    #: veredicto —es un numero comparativo, una COLUMNA—. Mismo escalon que la colision
    #: de seed, que ya se acota «por coste» unas lineas mas abajo. Donde no se cuenta
    #: sale `NOT_RUN` con el motivo: nunca un cero, nunca una celda que se lea como cero.
    seed_load_starts: frozenset[int] | None = None,
    expression: dict[str, float] | None = None,
    accessibility: bool = False,
    #: Especie del DISEÑO. VACIA = no declarada, y eso es un estado propio: el nucleo de
    #: abundancia esta autorizado para cerebro MURINO, asi que sobre otra especie el FAIL
    #: sale marcado `LISTA_DE_OTRA_ESPECIE` y sin declararla, `ESPECIE_NO_DECLARADA`.
    #: Por defecto NO es raton: poner raton por defecto es justo el patron que se esta
    #: quitando.
    species: str = "",
    apa_sites: ApaSites | None = None,
    #: LA MEDIDA ENTRA SOLA. Sin pasar nada, `tile_utr` resuelve la tabla de APA medido
    #: contra la secuencia (por md5 del 3'UTR) y la aplica si habla de ella. Ver
    #: `apa.WHY_MEASURE_IS_NOT_A_FLAG`: es un VEREDICTO, no una ordenacion, y hacerlo
    #: depender de que el llamador se acuerde es lo que dejaba a `3utr:221` en el panel.
    #: `None` ABORTA: era el salto silencioso. Para excluirla, `apa.ApaExcluded(motivo)`.
    measured_apa: "MeasuredApa | ApaExcluded | None" = RESOLVER_MEDIDA,
    #: Donde buscar la tabla de PolyA_DB. Sin declarar, los directorios de referencia
    #: de siempre. Se puede fijar para probar el caso «no hay fichero», que es un estado
    #: distinto de «la tabla no habla de esta secuencia» y tiene que poder comprobarse.
    reference_dir=None,
    asymmetry_model: AsymmetryModel | None = turner_asymmetry,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> TilingReport:
    """Enmascara, RETILA y evalua todas las ventanas. Ninguna se omite del informe.

    El orden importa: primero se enmascara y despues se trocea, para que una ventana
    parcialmente repetitiva se reevalue entera en vez de tacharse de una lista ya hecha.
    Las señales de poliadenilacion se buscan sobre la secuencia SIN enmascarar.
    """
    original = normalize_sequence(sequence, name="secuencia")
    # `tile_utr` sin anatomia significa lo que dice su nombre: la secuencia que llega
    # YA es un 3'UTR. Ese contrato esta en el nombre de la funcion, asi que aqui la
    # declaracion es explicita y queda registrada en `anatomy.source`. Lo que se elimino
    # fue el fallback del CLI, que aplicaba esto a transcritos completos sin decirlo.
    anatomy = anatomy or Anatomy.whole_is_utr3(
        len(original), source=RegionSource.TODO_3UTR_DECLARADO
    )
    if anatomy.length != len(original):
        raise ValueError(
            f"La anatomía declara {anatomy.length} nt y la secuencia mide "
            f"{len(original)}; se aborta antes de etiquetar ninguna ventana con "
            f"coordenadas que no son las suyas."
        )
    from .apa import (  # noqa: PLC0415
        POLYADB_FILENAME,
        ApaExcluded,
        find_polyadb,
        resolve_measured,
    )

    motivo_exclusion = ""
    motivo_sin_medida = ""
    if measured_apa is None:
        raise ShmirDesignError(
            "`measured_apa=None` ya no vale: era el salto SILENCIOSO de la tabla de APA "
            "medido, y de eso dependen veredictos —con la medida, `3utr:221` es FAIL "
            "duro por solape estérico; sin ella, sólo lleva una penalización—. No pases "
            "nada para que entre sola, o pasa `apa.ApaExcluded(reason=…)` con el motivo "
            "escrito para excluirla a propósito."
        )
    if isinstance(measured_apa, ApaExcluded):
        motivo_exclusion = measured_apa.reason
        measured_apa = None
    elif measured_apa is RESOLVER_MEDIDA:
        # LOS VALORES SALEN DEL FICHERO, no de una constante. La REGLA —que un hexamero
        # con uso medido se trate como funcional— es la que vive aqui y no lleva
        # bandera; el DATO entra por el gestor, y en otra especie basta con subir el
        # suyo. Hasta 2026-08-27 esto leia `apa.POLYA_DB_PRNP`, asi que fuera del raton
        # no habia forma de meter los numeros sin editar el modulo.
        tabla = find_polyadb(directory=reference_dir, species=species)
        if tabla is None:
            motivo_sin_medida = (
                f"No hay tabla de PolyA_DB en el directorio de referencia "
                f"({POLYADB_FILENAME.format(slug=species or '<especie>')}), así que el "
                f"frente del APA queda NOT_RUN y `riesgo_APA` sigue siendo una "
                f"PREDICCIÓN. Se sube por el gestor."
            )
            measured_apa = None
        else:
            # Se coloca sola sobre la secuencia que le corresponde y SOLO sobre esa: la
            # condicion es el md5 canonico del 3'UTR.
            measured_apa = resolve_measured(original, tabla, anatomy=anatomy)
            if measured_apa is None:
                motivo_sin_medida = (
                    f"La tabla de {tabla.source} {tabla.version} es de {tabla.gene} y "
                    f"su md5 de 3'UTR ({tabla.utr3_md5}) no es el de esta secuencia, "
                    f"así que NO habla de ella y no se promueve nada. No es un fallo: "
                    f"unas coordenadas ancladas sobre otro 3'UTR anclarían ruido."
                )

    signals = find_polya_signals(original, flank=thresholds.polya_flank)
    if measured_apa is not None:
        # La medida SUSTITUYE a la prediccion: una variante rara con uso medido
        # pesa mas que una canonica sin medir. La promocion va antes de anotar
        # ninguna ventana, para que ni un solo filtro vea la clasificacion vieja.
        signals = promote_by_measurement(
            signals, measured_apa.signal_starts, source=measured_apa.source
        )
    cleaned = apply_mask(original, mask)
    tile_range = tile_range or TileRange.resolve(anatomy, window_size=window_size)
    windows = [
        Window(start, window_size, label=f"w{start}")
        for start in tile_positions(len(cleaned), window_size)
        if tile_range.contains_window(start, start + window_size - 1)
    ]
    if not windows:
        raise ValueError(
            f"El rango de tilado {tile_range.describe(anatomy)} no contiene ni una "
            f"ventana entera de {window_size} nt; se aborta en vez de devolver un "
            f"informe vacío que pareceria 'no hay candidatos'."
        )
    annotated = annotate_3utr(windows, signals, len(cleaned), anatomy=anatomy)

    # LA DIANA YA NO SE PASA: sale de `data/diana/variantes.toml` por la ESPECIE, que
    # es lo que este informe ya lleva. Antes se exigia aqui un accession tecleado y se
    # abortaba sin el; hoy, sin declaracion, el filtro emite `NO_CIERRA` con el motivo —
    # que es informacion y no un veto. Ver `specificity.filter_specificity`.

    tiled: list[TiledWindow] = []
    for anotada in annotated.windows:
        start = anotada.window.start
        evaluation = evaluate_window(
            cleaned[start - 1 : start - 1 + window_size],
            asymmetry_model=asymmetry_model,
            offset=start,
            thresholds=thresholds,
        )
        region = anatomy.region_of(
            (anotada.window.start + anotada.window.end) // 2
        )
        # Bloque 9: polyA y APA son heuristicas del 3'UTR. Sobre una ventana del ORF o
        # del 5'UTR no dan ni PASS ni FAIL — la pregunta no va con ese candidato — y
        # tampoco es NOT_RUN, porque no hay ninguna laguna que tapar.
        # Bloque 5: con sitios medidos, el dato sustituye a la prediccion.
        apa = None
        if region is Region.UTR3:
            if apa_sites is not None and apa_sites.coords == "3utr":
                posicion = anatomy.utr3_position(anotada.window.start)
                if posicion is None:
                    # La ventana empieza ANTES del 3'UTR: cuenta como 3'UTR porque su
                    # punto medio cae ahi, pero su inicio no tiene coordenada de 3'UTR.
                    # Se ancla al principio del 3'UTR, que es la respuesta correcta a la
                    # pregunta del APA: una ventana que empieza en el CDS no puede estar
                    # por detras de ningun sitio de corte del 3'UTR. Antes se caia en la
                    # coordenada de TRANSCRITO y se comparaba contra sitios dados en
                    # coordenadas de 3'UTR — mezcla silenciosa de sistemas.
                    posicion = 1
            else:
                posicion = anotada.window.start
            apa = apa_assessment(
                window_start=posicion,
                sites=apa_sites,
                predicted_risk=anotada.riesgo_APA,
            )

        # El techo medido, si lo hay, viaja con la anotacion de polyA: es el MISMO
        # numero que `apa.knockdown_ceiling` y no puede salir relleno en una columna y
        # vacio en la otra.
        anotacion_polya = annotate_polya(
            anotada.window,
            list(signals),
            utr_length=len(cleaned),
            sequence=original,
            mode=polya_mode,
            fraccion_isoforma_larga=(
                apa.knockdown_ceiling if apa is not None else None
            ),
            # El marco de LO TILADO. Sin esto, `polyA_hexamero_pos` salia como un entero
            # desnudo en la tabla de la pagina: `1185` es `tx:1185`, o sea `3utr:236`.
            frame=tiled_frame(anatomy),
        )
        zona_prohibida = anotacion_polya.veredicto
        if region is not Region.UTR3:
            zona_prohibida = FilterResult(
                name=zona_prohibida.name,
                state=FilterState.NO_APLICA,
                reason=(
                    f"La ventana cae en {region.value}, no en el 3'UTR. Las señales de "
                    f"poliadenilación solo tienen sentido sobre el 3'UTR: aquí la "
                    f"pregunta no aplica. NO_APLICA no es PASS."
                ),
            )

        # Una ventana con N no tiene guia valida, y una que no supera los biofisicos no
        # se va a pedir: escanear bases de datos por ellas es tiempo tirado. Las dos
        # quedan NOT_RUN con el motivo escrito, que no es PASS.
        escaneable = evaluation.asymmetry is not None and biophysical_ok(
            list(evaluation.filters) + [zona_prohibida]
        )

        guia_adn = evaluation.guide.replace("U", "T")

        colision = None
        if mature is not None:
            colision = (
                filter_seed_collision(
                    guia_adn,
                    mature,
                    abundance,
                    passenger=passenger_from_guide(evaluation.guide).sequence,
                    species=species,
                ).as_filter()
                if escaneable
                else FilterResult(
                    name="seed_colision",
                    state=FilterState.NOT_RUN,
                    reason=(
                        "No evaluada: por coste, la colisión de seed solo se mira en "
                        "las ventanas que superan los filtros biofísicos. NOT_RUN no "
                        "es PASS."
                    ),
                )
            )

        # NO SE PIDIO NO ES NO SE PUDO. Antes esto dejaba `acceso = None` en los dos
        # casos y la celda salia vacia en los dos: la casilla sin marcar era
        # indistinguible de un calculo que se pidio y fallo. Ver `NOT_ASKED`.
        acceso = None if not escaneable else Accessibility(
            state=FilterState.NO_PEDIDO, reason=NOT_ASKED,
        )
        if accessibility and escaneable:
            acceso = accessibility_of(
                original, start=anotada.window.start, length=window_size
            )

        carga = None
        if utr3_set is not None and escaneable:
            if seed_load_starts is None or anotada.window.start in seed_load_starts:
                carga = seed_load(guia_adn, utr3_set, expression)
            else:
                # NO_PEDIDO, no NOT_RUN: acotar por coste es una DECISION —solo se
                # cuenta donde se lee, el panel— y no una laguna. `NOT_RUN` aqui manda a
                # conseguir algo, y no hay nada que conseguir. Misma distincion que la
                # accesibilidad sin marcar (errata nº 91).
                carga = SeedLoad(
                    state=FilterState.NO_PEDIDO,
                    reason=SEED_LOAD_SKIPPED,
                    utrs=utr3_set,
                )

        transgen = None
        transgen_detalle = None
        if transgene_db is not None:
            if not escaneable:
                transgen = FilterResult(
                    name="transgen",
                    state=FilterState.NOT_RUN,
                    reason=(
                        "No evaluada: por coste, el casete del transgén solo se escanea "
                        "en las ventanas que superan los filtros biofísicos. NOT_RUN no "
                        "es PASS."
                    ),
                )
            else:
                transgen_detalle = filter_transgene(
                    evaluation.guide.replace("U", "T"),
                    passenger_from_guide(evaluation.guide).sequence,
                    transgene_db,
                )
                transgen = transgen_detalle.as_filter()

        especificidad = None
        especificidad_detalle = None
        if specificity_db is not None:
            if not escaneable:
                especificidad = FilterResult(
                    name="especificidad",
                    state=FilterState.NOT_RUN,
                    reason=(
                        "No evaluada: por coste, la especificidad solo se escanea en "
                        "las ventanas que superan los filtros biofísicos. NOT_RUN no "
                        "es PASS."
                    ),
                )
            else:
                especificidad_detalle = filter_specificity(
                    evaluation.guide.replace("U", "T"),
                    passenger_from_guide(evaluation.guide).sequence,
                    specificity_db,
                    species=species,
                )
                especificidad = especificidad_detalle.as_filter()

        tiled.append(
            TiledWindow(
                window=anotada.window,
                evaluation=evaluation,
                zona_prohibida=zona_prohibida,
                seed=_seed_bootstrap(
                    evaluation.guide, seeds, mature, sustituto=colision,
                ),
                repeticiones=filter_repeats(start, anotada.window.end, mask),
                repeticion_polimorfica=filter_polymorphic(
                    start, anotada.window.end, mask
                ),
                especificidad=especificidad,
                especificidad_detalle=especificidad_detalle,
                transgen=transgen,
                transgen_detalle=transgen_detalle,
                polya=anotacion_polya,
                seed_colision=colision,
                carga_seed=carga,
                accesibilidad=acceso,
                tercio=anotada.tercio,
                riesgo_APA=(
                    (apa.risk if apa is not None else anotada.riesgo_APA)
                    and region is Region.UTR3
                ),
                apa=apa,
                apa_aplica=region is Region.UTR3,
                apa_upstream=anotada.apa_upstream,
                senales_debiles=anotada.senales_debiles,
                estricto_ok=anotada.estricto_ok,
                region=region,
                inicio_3utr=anatomy.utr3_position(anotada.window.start),
                fin_3utr=anatomy.utr3_position(anotada.window.end),
                cruza_frontera=anatomy.crosses_boundary(
                    anotada.window.start, anotada.window.end
                ),
            )
        )

    return TilingReport(
        utr_length=len(cleaned),
        window_size=window_size,
        windows=tuple(tiled),
        signals=tuple(signals),
        measured_apa=measured_apa,
        apa_excluded_reason=motivo_exclusion,
        apa_missing_reason=motivo_sin_medida,
        anatomy=anatomy,
        specificity_db=specificity_db,
        avisos=annotated.avisos,
        seeds=seeds,
        mask=mask,
        thresholds=thresholds,
        tile_range=tile_range,
        transgene_db=transgene_db,
        mature=mature,
        abundance=abundance,
        utr3_set=utr3_set,
        accessibility=accessibility,
        apa_sites=apa_sites,
        polya_mode=polya_mode,
        sequence_length=len(original),
        sequence_md5=sequence_md5(original),
    )
