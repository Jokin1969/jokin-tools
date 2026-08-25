"""Salidas del diseño: TSV, FASTA, oligos e informe de texto.

Cinco salidas, y ninguna esconde nada:

- `tsv_all_windows`: TODAS las ventanas, con el estado de CADA filtro en su propia
  columna. Nunca un booleano agregado: un `PASS` global no deja ver que la seed no
  llego a correr.
- `tsv_selected`: los candidatos elegidos, con su rango por asimetria, su tercio, su
  veredicto y los filtros que no corrieron.
- `fasta_guides`: las guias en ADN, para pasarlas por BLAST (paso 12, manual en la v1).
- `tsv_oligos`: la horquilla ensamblada de cada candidato, con sus avisos en cada fila.
- `text_report`: anatomia del transcrito, señales de poliadenilacion, bloques
  conservados, avisos y CUALES FILTROS NO SE EJECUTARON.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from .conservation import ConservationReport
from .accessibility import CONTEXT_WINDOWS, DISCREPANCY
from .filters import FilterState, Verdict
from .folding import VIENNA_AVAILABLE
from .mirna import SEED_SPACE
from .reference import ReferenceTranscript
from .gblock import build_gblock
from .scaffold import ScaffoldSpec, build_hairpin
from .comparative import comparative_text, comparative_tsv
from .external_score import manual_instructions
from .selection import (
    coverage_report,
    ReportSelection,
    penalty_sensitivity,
    polya_mode_comparison,
)
from .specificity import (
    SEED_CAVEAT,
    TAXIDS,
    TRANSGENE_ORIENTATION_NOTE,
    blast_command,
)
from .tiling import TilingReport

FASTA_WRAP = 60


def _tsv(rows: list[list[str]]) -> str:
    return "\n".join(
        "\t".join(field.replace("\t", " ").replace("\n", " ") for field in row)
        for row in rows
    )


def tsv_all_windows(report: TilingReport) -> str:
    """TODAS las ventanas, un estado por filtro y columna."""
    return report.format_tsv()


def _sin_correr(selection: ReportSelection) -> str:
    if not selection.not_run_filters:
        return "ninguno"
    return "; ".join(
        f"{name} ({count} ventana(s))"
        for name, count in selection.not_run_filters.items()
    )


def tsv_selected(selection: ReportSelection, *, species: str) -> str:
    """Los candidatos, con el estado de CADA filtro en su columna.

    Quien abra este fichero tiene que poder ver que filtro falta sin abrir otro: un
    `INCOMPLETE` a secas invita a decidir sin saber que le falta al candidato.
    """
    chosen = list(selection.selection.chosen)
    filtros = (
        [r.name for r in selection.window_of(chosen[0]).filters] if chosen else []
    )
    rows = [
        [
            "especie",
            "rango_asimetria",
            "inicio",
            "fin",
            "region",
            "inicio_3utr",
            "fin_3utr",
            "tercio",
            "asimetria_kcal",
            "penalizacion",
        ]
        + filtros
        + [
            "bandera_polyA_debil",
            "biofisicos_ok",
            "riesgo_APA",
            "veredicto",
            "diana",
            "guia",
            "filtros_sin_correr",
        ]
    ]
    sin_correr = _sin_correr(selection)
    for choice in chosen:
        window = selection.window_of(choice)
        estados = {r.name: r.state.value for r in window.filters}
        rows.append(
            [
                species,
                str(selection.selection.rank_of(choice.start)),
                str(choice.start),
                str(choice.end),
                window.region.value,
                "" if window.inicio_3utr is None else str(window.inicio_3utr),
                "" if window.fin_3utr is None else str(window.fin_3utr),
                choice.tercio.value if choice.tercio else "",
                f"{choice.asymmetry_raw:+.2f}",
                f"{choice.penalty:.2f}",
            ]
            + [estados[name] for name in filtros]
            + [
                str(window.bandera_polyA_debil),
                str(window.biofisicos_ok),
                str(window.riesgo_APA),
                window.verdict.value,
                window.evaluation.sequence,
                window.evaluation.guide,
                sin_correr,
            ]
        )
    return _tsv(rows)


def fasta_guides(selection: ReportSelection, *, species: str) -> str:
    """Guias en ADN, listas para BLAST. En ARN blastn no las quiere."""
    lines: list[str] = []
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        guide_dna = window.evaluation.guide.replace("U", "T")
        rank = selection.selection.rank_of(choice.start)
        lines.append(
            f">{species}_pos{choice.start}_rank{rank} guia(ADN) "
            f"tercio={choice.tercio.value if choice.tercio else choice.region.value} "
            f"asimetria={choice.asymmetry:+.2f} "
            f"veredicto={window.verdict.value}"
        )
        lines.extend(
            guide_dna[i : i + FASTA_WRAP] for i in range(0, len(guide_dna), FASTA_WRAP)
        )
    return "\n".join(lines)


def tsv_oligos(
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    *,
    species: str,
) -> str:
    """Horquillas ensambladas. Cada fila lleva sus avisos: no se pueden perder de vista."""
    rows = [
        [
            "especie",
            "inicio",
            "andamio",
            "andamio_verificado",
            "longitud",
            "guia",
            "pasajera",
            "oligo",
            "gblock_149",
            "gblock_veredicto",
            "gblock_motivos",
            "avisos",
        ]
    ]
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        hairpin = build_hairpin(window.evaluation.guide, scaffold=scaffold)
        gblock = build_gblock(hairpin)
        rows.append(
            [
                species,
                str(choice.start),
                scaffold.name,
                str(scaffold.verified),
                str(len(hairpin.sequence)),
                hairpin.guide,
                hairpin.passenger.sequence,
                hairpin.sequence,
                gblock.sequence,
                gblock.verdict.value,
                "; ".join(f"{c.name}: {c.reason}" for c in gblock.failures) or "—",
                " | ".join(hairpin.warnings),
            ]
        )
    return _tsv(rows)


def text_report(
    *,
    species: str,
    tiling: TilingReport,
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    transcript: ReferenceTranscript | None = None,
    conservation: ConservationReport | None = None,
    anatomy_warnings: tuple[str, ...] = (),
    provenance: tuple[str, ...] = (),
) -> str:
    lines = [
        f"═══ Diseño de shmiR — {species} ═══",
        "",
        "── Anatomia del transcrito ──",
    ]
    anatomia = tiling.anatomy
    if transcript is None and anatomia is not None and anatomia.declared:
        lines.append(
            "  Declarada por quien lanzo el analisis (no hay transcrito verificado):"
        )
        lines.append(f"  total {anatomia.length} nt")
        if anatomia.utr5:
            lines.append(
                f"  5'UTR {anatomia.utr5[0]}-{anatomia.utr5[1]} "
                f"({anatomia.utr5[1] - anatomia.utr5[0] + 1} nt)"
            )
        lines.append(
            f"  CDS   {anatomia.cds[0]}-{anatomia.cds[1]} "
            f"({anatomia.cds[1] - anatomia.cds[0] + 1} nt)"
        )
        lines.append(
            f"  3'UTR {anatomia.utr3[0]}-{anatomia.utr3[1]} "
            f"({anatomia.utr3_length} nt)"
        )
        lines.extend(f"  ⚠  {w}" for w in anatomia.warnings)
        lines.append(
            "  Las ventanas llevan sus dos coordenadas: la del transcrito y la del "
            "3'UTR. Los tercios se calculan sobre el 3'UTR."
        )
    elif transcript is None:
        lines.append(
            f"  Se ha tratado TODA la secuencia ({anatomia.length if anatomia else '?'} "
            f"nt) como 3'UTR, por declaracion explicita."
        )
    else:
        lines.extend(
            [
                f"  {transcript.accession} — {transcript.organism}, {transcript.gene}",
                f"  total {transcript.length} nt   md5 {transcript.md5}",
                f"  5'UTR {transcript.utr5[0]}-{transcript.utr5[1]} "
                f"({transcript.utr5_length} nt)",
                f"  CDS   {transcript.cds[0]}-{transcript.cds[1]} "
                f"({transcript.cds_length} nt, {transcript.protein_length} aa + stop)",
                f"  3'UTR {transcript.utr3[0]}-{transcript.utr3[1]} "
                f"({transcript.utr3_length} nt)",
            ]
        )

    if anatomia is not None:
        lines.append(f"  Procedencia de la anatomia: {anatomia.source.describe()}")
        if tiling.tile_range is not None:
            lines.append(
                f"  Rango tilado: {tiling.tile_range.describe(anatomia)}"
            )
            if not tiling.tile_range.is_whole(anatomia):
                lines.append(
                    "  Fuera de ese rango no se ha evaluado NADA: las ventanas que no "
                    "caben enteras dentro no aparecen en ninguna salida."
                )
    lines.extend(f"  ⚠  {w}" for w in anatomy_warnings)

    if selection.selection.config.region_quota is not None:
        reparto = ", ".join(
            f"{region.value}: {cuantos}"
            for region, cuantos in selection.selection.config.region_quota
        )
        lines.append(f"  Cuota por region pedida — {reparto}")
        lines.append(
            "  Los filtros de polyA y APA salen NO_APLICA fuera del 3'UTR: son "
            "heuristicas de 3'UTR y sobre el ORF no dan ni PASS ni FAIL."
        )

    lines.extend(["", "── Señales de poliadenilacion ──"])
    if tiling.signals:
        lines.extend(f"  · {s.describe()}" for s in tiling.signals)
    else:
        lines.append("  Ninguna encontrada.")

    lines.extend(["", "── Bloques conservados ──"])
    if conservation is None:
        lines.append(
            "  No se comparo con otra especie: no hay bloques conservados que reportar."
        )
    elif not conservation.blocks:
        lines.append(
            f"  Ninguno de >= {conservation.min_length} nt entre "
            f"{conservation.species[0]} y {conservation.species[1]}."
        )
    else:
        for block in conservation.blocks:
            lines.append(
                f"  · {block.length} nt, GC {block.gc_fraction * 100:.1f}% — "
                + "; ".join(hit.describe() for hit in block.hits)
            )
            lines.append(f"    {block.sequence}")

    lines.extend(
        [
            "",
            "── Tiling y seleccion ──",
            f"  ventanas:        {selection.total}",
            f"  biofisicos_ok:   {tiling.biofisicos_ok()}",
            f"  elegibles:       {selection.eligible} con criterio ESCALONADO "
            f"(la variante rara de poliadenilacion penaliza, no excluye)",
            f"                   {selection.eligible_strict} con criterio ESTRICTO "
            f"(±flanco para los doce hexameros por igual)",
            f"  sitios:          {len(selection.selection.sites)}",
            f"  seleccionados:   {len(selection.selection.chosen)} de "
            f"{selection.selection.config.n_candidates} pedidos "
            f"(espaciado minimo {selection.selection.config.min_spacing} nt entre "
            f"posiciones de inicio)",
        ]
    )
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        lines.append(
            f"    #{selection.selection.rank_of(choice.start)} "
            f"pos {choice.start}-{choice.end} "
            f"{(choice.tercio.value if choice.tercio else choice.region.value):<8} "
            f"asim {choice.asymmetry:+.2f}  {window.verdict.value}"
            + ("  riesgo_APA" if window.riesgo_APA else "")
        )

    lines.extend(["", "── Especificidad ──"])
    if tiling.specificity_db is None:
        lines.append(
            "  NOT_RUN: no hay base de RefSeq RNA cargada. NOT_RUN no es PASS — un "
            "fallo de red, un timeout o una base ausente nunca se convierten en PASS."
        )
    else:
        lines.append(f"  Base: {tiling.specificity_db.provenance}")
        lines.append(
            "  Parametros: escaneo exhaustivo local, hasta 2 desapareamientos, guia y "
            "pasajera por separado; solo cuentan los hits antisentido."
        )
    if selection.selection.chosen and species in TAXIDS:
        lines.append(
            f"  BLAST remoto de inspeccion (NUNCA fuente del veredicto), solo para los "
            f"{len(selection.selection.chosen)} supervivientes:"
        )
        lines.append(f"    {blast_command(f'{species}_guias.fasta', species)}")
        lines.append("    Etiqueta de NCBI: una sumision cada ~10 s, polling >= 60 s.")
    elif selection.selection.chosen:
        lines.append(
            f"  Para el BLAST remoto hace falta el taxid de {species!r}, que no esta "
            f"declarado (conocidos: {', '.join(sorted(TAXIDS))}). No se inventa."
        )
    lines.append(f"  ⚠  {SEED_CAVEAT}")

    if provenance:
        lines.extend(
            [
                "",
                "── Procedencia de los ficheros de referencia usados ──",
                "  Copiado del manifiesto de data/reference/. Sin estas lineas, dentro "
                "de un año",
                "  nadie podra saber con que version de cada base se saco este "
                "veredicto.",
            ]
        )
        lines.extend(f"    {l}" for l in provenance)

    lines.extend(["", "── Tabla comparativa de los candidatos ──"])
    lines.append(comparative_text(selection, scaffold))

    lines.extend(["", "── Score externo (columna vacia) ──"])
    lines.append(
        manual_instructions(
            [
                selection.window_of(choice).evaluation.guide
                for choice in selection.selection.chosen
            ]
        )
    )

    lines.extend(["", "── Rango que cubre la seleccion ──"])
    lines.append(
        coverage_report(
            selection.selection, sites=list(selection.selection.sites)
        ).format_text()
    )
    if not selection.selection.config.spread_coverage:
        lines.append(
            "  La seleccion se hizo por asimetria, no repartiendo. La asimetria predice "
            "SELECCION DE HEBRA, no potencia: si lo que se quiere es correlacionar "
            "parametros contra el knockdown medido, --reparto-rango reparte los "
            "candidatos por los extremos de los parametros dudosos."
        )

    lines.extend(["", "── Poliadenilacion alternativa (APA) ──"])
    if tiling.apa_sites is None:
        con_riesgo = sum(1 for w in tiling.windows if w.riesgo_APA)
        lines.append(
            f"  riesgo_APA es una PREDICCION, no un dato: {con_riesgo} de "
            f"{len(tiling.windows)} ventana(s) "
            f"({con_riesgo / len(tiling.windows):.1%}) quedan por detras de una señal "
            f"de APA posible."
        )
        lines.append(
            "  Que esa señal se use o no, esto no lo puede saber. Si se usa, esas "
            "ventanas tienen un techo de knockdown duro e invisible. Con una tabla de "
            "PolyA_DB o PolyASite (--apa-medido) el dato sustituiria a la prediccion."
        )
    else:
        lines.append(f"  Sitios MEDIDOS: {tiling.apa_sites.provenance}")
        lines.append(
            "  El dato sustituye a la prediccion. Un sitio medido ES el sitio de corte, "
            "no el hexamero: no se le suman los 10-30 nt."
        )
        con_techo = [
            w for w in tiling.windows
            if w.apa is not None and w.apa.knockdown_ceiling is not None
        ]
        if con_techo:
            peor = min(w.apa.knockdown_ceiling for w in con_techo)
            lines.append(
                f"  Techo de knockdown mas bajo entre las ventanas evaluadas: "
                f"{peor:.0%}."
            )
        elif tiling.apa_sites is not None and not tiling.apa_sites.has_fractions:
            lines.append(
                "  La tabla no trae la fraccion de lecturas de todos los sitios, asi "
                "que hay riesgo identificado pero no techo. No se inventa."
            )

    lines.extend(["", "── Accesibilidad de la diana ──"])
    if not tiling.accessibility:
        lines.append(
            "  NOT_RUN: no se pidio (--accesibilidad). NOT_RUN no es cero: no haber "
            "plegado no es lo mismo que una diana inaccesible."
        )
    elif not VIENNA_AVAILABLE:
        lines.append(
            "  NOT_RUN: se pidio, pero ViennaRNA no esta instalado "
            "(`pip install ViennaRNA`). NOT_RUN no es cero."
        )
    else:
        calculadas = [w for w in tiling.windows if w.accesibilidad is not None]
        discrepantes = [
            w for w in calculadas if w.accesibilidad.discrepant
        ]
        lines.append(
            f"  Calculada en {len(calculadas)} ventana(s), con dos ventanas de "
            f"contexto: ±{CONTEXT_WINDOWS[0]} y ±{CONTEXT_WINDOWS[1]} nt."
        )
        lines.append(
            f"  En {len(discrepantes)} de ellas las dos ventanas discrepan mas de "
            f"{DISCREPANCY:.0%}: ahi el numero depende de donde se corte el contexto y "
            f"no sirve para desempatar."
        )
        lines.append(
            "  Es el criterio peor predicho del pipeline: va de DESEMPATE y no descarta "
            "a nadie. Se guarda para poder correlacionarlo contra el knockdown medido."
        )

    lines.extend(["", "── Elementos repetitivos ──"])
    if tiling.mask is None:
        lines.append(
            "  NOT_RUN: no hay mascara de repeticiones cargada. Una guia derivada de un "
            "elemento repetitivo tiene miles de sitios perfectos: no es un off-target, "
            "es una guia inservible. NOT_RUN no es PASS."
        )
    else:
        lines.append(f"  Mascara: {tiling.mask.provenance}")
        lines.append(
            "  El enmascarado va ANTES de tilar y se RETILA: una ventana parcialmente "
            "repetitiva se reevalua entera, no se tacha de una lista ya hecha."
        )

    lines.extend(["", "── Colision de seed con miARN endogeno ──"])
    if tiling.mature is None:
        lines.append(
            "  NOT_RUN: no hay tabla de maduros de miRBase cargada. Compartir seed con "
            "un miARN abundante no produce off-targets dispersos: reprime su red de "
            "dianas entera. NOT_RUN no es PASS."
        )
    else:
        lines.append(f"  Maduros: {tiling.mature.provenance}")
        if tiling.abundance is None:
            lines.append(
                "  Lista de abundancia en cerebro: AUSENTE. El nivel FAIL queda en "
                "NOT_RUN; el nivel de aviso si ha corrido y las colisiones se listan "
                "por candidato."
            )
        else:
            lines.append(f"  Abundancia: {tiling.abundance.provenance}")
        lines.append(
            f"  Dos niveles porque hay {SEED_SPACE} 7-meros posibles: una colision por "
            f"azar no es rara, asi que el FAIL solo lo da la lista curada."
        )

    lines.extend(["", "── Carga de off-targets por seed ──"])
    if tiling.utr3_set is None:
        lines.append(
            "  NOT_RUN: no hay FASTA de 3'UTR del transcriptoma cargado. Esto NO es un "
            "cero: no saber cuantos sitios de seed hay no es lo mismo que no haber "
            "ninguno."
        )
        lines.append(
            "  Ningun alineador devuelve estos sitios — la especificidad compara la "
            "guia entera — asi que un veredicto de especificidad limpio no dice nada "
            "sobre esto."
        )
    else:
        lines.append(f"  3'UTR: {tiling.utr3_set.provenance}")
        lines.append(
            "  Numero comparativo entre candidatos, nunca veredicto: sale en la tabla "
            "como criterio de desempate."
        )

    lines.extend(["", "── Transgen terapeutico ──"])
    if tiling.transgene_db is None:
        lines.append(
            "  NOT_RUN: no hay casete del transgen cargado, asi que queda sin comprobar "
            "si algun candidato apaga la propia construccion terapeutica. NOT_RUN no es "
            "PASS."
        )
        lines.append(
            "  Por que importa: una guia a 1 desapareamiento del ORF del transgen lo "
            "silencia casi igual que a su diana perfecta. El fallo seria silencioso — "
            "knockdown global bonito y ningun beneficio en el ratio."
        )
    else:
        lines.append(f"  Casete: {tiling.transgene_db.provenance}")
        lines.append(
            "  Parametros: mismo motor que la especificidad (escaneo exhaustivo local, "
            "hasta 2 desapareamientos, guia y pasajera por separado). Aqui no hay gen "
            "diana que excluir: FAIL con 0 o 1 desapareamiento, aviso con 2."
        )
        tocados = [
            w for w in tiling.windows
            if w.filter("transgen").state is FilterState.FAIL
        ]
        lines.append(
            f"  Ventanas que tocan el casete (FAIL): {len(tocados)} de "
            f"{len(tiling.windows)}."
        )
        lines.append(f"  ⚠  {TRANSGENE_ORIENTATION_NOTE}")

    lines.extend(
        [
            "",
            "── Criterio de poliadenilacion: los tres modos lado a lado ──",
            f"  Modo usado en esta corrida: {tiling.polya_mode.value}",
            "  El corte no ocurre en el hexamero, ocurre 10-30 nt aguas abajo: el "
            "hexamero se queda",
            "  dentro del ARNm maduro. La ventana que desaparece es la que empieza "
            "DESPUES del corte,",
            "  asi que la zona prohibida por esa razon es asimetrica y esta desplazada "
            "aguas abajo.",
        ]
    )
    lines.append(polya_mode_comparison(tiling, selection.selection.config).format_text())

    sensibilidad = penalty_sensitivity(tiling, selection.selection.config)
    lines.extend(
        [
            "",
            "── Sensibilidad de la penalizacion por poliadenilacion debil ──",
            f"  ventanas con bandera: {sensibilidad.flagged}",
        ]
    )
    if sensibilidad.flagged:
        lines.extend(
            f"    {valor:.1f} kcal/mol → {', '.join(str(p) for p in posiciones) or '—'}"
            for valor, posiciones in sensibilidad.selections.items()
        )
    lines.append(f"  {sensibilidad.describe()}")

    lines.extend(["", "── FILTROS QUE NO SE EJECUTARON ──"])
    if not selection.not_run_filters:
        lines.append("  Ninguno: todos los filtros corrieron.")
    else:
        lines.extend(
            f"  {name}: NOT_RUN en {count} de {selection.total} ventanas"
            for name, count in selection.not_run_filters.items()
        )
        lines.append(
            "  NOT_RUN no es PASS. Mientras haya filtros sin correr, la seleccion es "
            "PROVISIONAL y ningun candidato esta aprobado: su veredicto es INCOMPLETE."
        )

    lines.extend(["", "── Avisos ──"])
    avisos: list[str] = []
    for aviso in tiling.avisos:
        avisos.append(f"  ⚠  [{aviso.code}] {aviso.message}")
    for warning in scaffold.warnings:
        avisos.append(f"  ⚠  {warning}")
    for nota in selection.selection.notes:
        avisos.append(f"  ⚠  seleccion: {nota}")
    for pendiente in selection.selection.quota_unfilled:
        avisos.append(f"  ⚠  cuota por tercio sin cubrir — {pendiente}")
    if tiling.seeds is not None and tiling.seeds.is_bootstrap:
        avisos.append(
            "  ⚠  El filtro de seed corrio con una lista de arranque, NO con miRBase "
            "completo: sirve para probar la mecanica, no para cribar."
        )
    lines.extend(avisos or ["  Ninguno."])

    if any(w.verdict is Verdict.PASS for w in tiling.windows):
        lines.append("")
        lines.append("  Hay ventanas con veredicto PASS: todos sus filtros corrieron.")
    return "\n".join(lines)
