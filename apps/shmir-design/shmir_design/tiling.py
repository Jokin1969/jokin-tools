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

from .accessibility import Accessibility, accessibility_of
from .anatomy import Anatomy, Region, RegionSource, TileRange
from .apa import ApaAssessment, ApaSites, apa_assessment
from .filters import FilterResult, FilterState, Verdict, biophysical_ok, overall_verdict
from .masking import RepeatMask, apply_mask, filter_repeats
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
    normalize_sequence,
)
from .mirna import AbundanceList, MatureSet, filter_seed_collision
from .scaffold import passenger_from_guide
from .seed_load import SeedLoad, Utr3Set, seed_load
from .seeds import SeedSet, filter_seed
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
        "No hay base de RefSeq RNA cargada, asi que el filtro de especificidad no se "
        "ejecuta. NOT_RUN no es PASS."
    ),
)


#: Estado por defecto de la colision de seed: sin miRBase, NOT_RUN.
_SEED_COLISION_SIN_BASE = FilterResult(
    name="seed_colision",
    state=FilterState.NOT_RUN,
    reason=(
        "No hay tabla de maduros de miRBase cargada, asi que no se puede saber si la "
        "seed de esta guia coincide con la de un miARN endogeno. NOT_RUN no es PASS."
    ),
)


#: Estado por defecto del filtro del transgen: sin casete, NOT_RUN.
_TRANSGEN_SIN_BASE = FilterResult(
    name="transgen",
    state=FilterState.NOT_RUN,
    reason=(
        "No hay casete del transgen cargado, asi que queda sin comprobar si el "
        "candidato apaga la propia construccion terapeutica. NOT_RUN no es PASS."
    ),
)


def _seed_bootstrap(
    guide: str, seeds: SeedSet | None, mature: MatureSet | None
) -> FilterResult:
    """El filtro `seed` de la lista de arranque, o NO_APLICA si esta el de verdad.

    `seed` y `seed_colision` responden a la MISMA pregunta con distinta profundidad. Si
    hay tabla de maduros de miRBase cargada, dejar los dos daria dos columnas que pueden
    contradecirse, y la peor de las dos —la de doce seeds— parece igual de autorizada.
    Asi que cuando esta el filtro real, este se retira diciendolo.
    """
    if mature is not None:
        return FilterResult(
            name="seed",
            state=FilterState.NO_APLICA,
            reason=(
                "Sustituido por `seed_colision`, que usa la tabla de maduros completa y "
                "distingue colision abundante (FAIL) de colision anotada (aviso). "
                "NO_APLICA no es PASS: mira la columna seed_colision."
            ),
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

    @property
    def bandera_polyA_debil(self) -> bool:
        """Solapa una variante rara: no excluye, penaliza el ranking."""
        return bool(self.senales_debiles)

    @property
    def filters(self) -> tuple[FilterResult, ...]:
        return self.evaluation.filters + (
            self.zona_prohibida,
            self.repeticiones,
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
            f"La ventana no tiene ningun filtro {name!r}; los que hay: {disponibles}."
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
    polya_mode: PolyAMode = PolyAMode.ESCALONADO
    #: Longitud y md5 CANONICO de la secuencia que se analizo. Sin esto no hay forma de
    #: saber que se analizo: la errata del 3'UTR fabricado se detecto por longitud
    #: contra las coordenadas declaradas.
    sequence_length: int = 0
    sequence_md5: str = ""

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
                "  repeticiones:    NOT_RUN — sin mascara de rmsk cargada (paso 1 sin "
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
        lines.append("La lista completa de ventanas esta en el TSV (format_tsv).")
        return "\n".join(lines)

    def format_tsv(self) -> str:
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
                    str(tiled.window.start),
                    str(tiled.window.end),
                    tiled.region.value,
                    "" if tiled.inicio_3utr is None else str(tiled.inicio_3utr),
                    "" if tiled.fin_3utr is None else str(tiled.fin_3utr),
                    tiled.evaluation.sequence,
                    tiled.evaluation.guide,
                    tiled.tercio.value if tiled.tercio else "",
                ]
                + [
                    (tiled.polya.as_columns()[c] if tiled.polya else "")
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
    specificity_target: str | None = None,
    transgene_db: SpecificityDatabase | None = None,
    mature: MatureSet | None = None,
    abundance: AbundanceList | None = None,
    utr3_set: Utr3Set | None = None,
    expression: dict[str, float] | None = None,
    accessibility: bool = False,
    apa_sites: ApaSites | None = None,
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
            f"La anatomia declara {anatomy.length} nt y la secuencia mide "
            f"{len(original)}; se aborta antes de etiquetar ninguna ventana con "
            f"coordenadas que no son las suyas."
        )
    signals = find_polya_signals(original, flank=thresholds.polya_flank)
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
            f"informe vacio que pareceria 'no hay candidatos'."
        )
    annotated = annotate_3utr(windows, signals, len(cleaned), anatomy=anatomy)

    if specificity_db is not None and not specificity_target:
        raise ValueError(
            "Con base de especificidad hay que declarar el gen diana "
            "(specificity_target): sin el, todo sitio parece un off-target."
        )

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
        anotacion_polya = annotate_polya(
            anotada.window,
            list(signals),
            utr_length=len(cleaned),
            sequence=original,
            mode=polya_mode,
        )
        zona_prohibida = anotacion_polya.veredicto
        if region is not Region.UTR3:
            zona_prohibida = FilterResult(
                name=zona_prohibida.name,
                state=FilterState.NO_APLICA,
                reason=(
                    f"La ventana cae en {region.value}, no en el 3'UTR. Las señales de "
                    f"poliadenilacion solo tienen sentido sobre el 3'UTR: aqui la "
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
                ).as_filter()
                if escaneable
                else FilterResult(
                    name="seed_colision",
                    state=FilterState.NOT_RUN,
                    reason=(
                        "No evaluada: por coste, la colision de seed solo se mira en "
                        "las ventanas que superan los filtros biofisicos. NOT_RUN no "
                        "es PASS."
                    ),
                )
            )

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

        acceso = None
        if accessibility and escaneable:
            acceso = accessibility_of(
                original, start=anotada.window.start, length=window_size
            )

        carga = None
        if utr3_set is not None and escaneable:
            carga = seed_load(guia_adn, utr3_set, expression)

        transgen = None
        transgen_detalle = None
        if transgene_db is not None:
            if not escaneable:
                transgen = FilterResult(
                    name="transgen",
                    state=FilterState.NOT_RUN,
                    reason=(
                        "No evaluada: por coste, el casete del transgen solo se escanea "
                        "en las ventanas que superan los filtros biofisicos. NOT_RUN no "
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
                        "las ventanas que superan los filtros biofisicos. NOT_RUN no "
                        "es PASS."
                    ),
                )
            else:
                especificidad_detalle = filter_specificity(
                    evaluation.guide.replace("U", "T"),
                    passenger_from_guide(evaluation.guide).sequence,
                    specificity_db,
                    target=specificity_target,
                )
                especificidad = especificidad_detalle.as_filter()

        tiled.append(
            TiledWindow(
                window=anotada.window,
                evaluation=evaluation,
                zona_prohibida=zona_prohibida,
                seed=_seed_bootstrap(evaluation.guide, seeds, mature),
                repeticiones=filter_repeats(start, anotada.window.end, mask),
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
