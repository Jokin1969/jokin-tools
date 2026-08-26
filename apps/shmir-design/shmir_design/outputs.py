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

from .conservation import ConservationReport, single_shmir_verdict
from .accessibility import CONTEXT_WINDOWS, DISCREPANCY
from .filters import FilterState, Verdict
from .folding import VIENNA_AVAILABLE
from .coords import bound_of, Frame, frame_of, label, span
from .transgene import carries_scaffold_module
from .mirna import SEED_SPACE
from . import splicing
from .apa import CLUSTER_READING, POLYA_DB_PRNP
from .polya import rtqpcr_amplicons
from .reference import ReferenceTranscript
from .gblock import build_gblock
from .scaffold import ScaffoldSpec, build_hairpin
from .comparative import CONVENTION_NOTE, comparative_text, comparative_tsv
from .external_score import manual_instructions
from .selection import (
    apa_ceiling_table,
    blocking_fronts,
    measured_promotion_cost,
    promotion_clearance,
    is_eligible,
    tercio_counts,
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


def _envolver(texto: str, ancho: int) -> list[str]:
    """Parte un parrafo largo en lineas, sin cortar palabras."""
    palabras, lineas, actual = texto.split(), [], ""
    for palabra in palabras:
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return lineas


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
    marco = (
        frame_of(selection.anatomy) if selection.anatomy is not None else Frame.UTR3
    )
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
                label(choice.start, marco),
                label(choice.end, marco),
                window.region.value,
                label(window.inicio_3utr, Frame.UTR3),
                label(window.fin_3utr, Frame.UTR3),
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
    notes: tuple[str, ...] = (),
    provenance: tuple[str, ...] = (),
    convergence=None,
    polya_conservation=None,
    orf_sweep=None,
    triple_motive=None,
) -> str:
    lines = [
        f"═══ Diseño de shmiR — {species} ═══",
        "",
        "── Anatomia del transcrito ──",
    ]
    anatomia = tiling.anatomy
    # El espacio de coordenadas de TODO lo que se imprima aqui. Sale de la anatomia, no
    # se elige: `tx:1018` y `3utr:1018` son dos sitios distintos y el entero solo no
    # distingue cual es.
    marco = frame_of(anatomia) if anatomia is not None else Frame.UTR3
    desfase = anatomia.utr3[0] - 1 if anatomia is not None and anatomia.utr3 else 0
    # La longitud REAL del 3'UTR de esta especie. Afina el techo global de `coords`:
    # cualquier posicion que se emita en `3utr` y no quepa aqui es un desfase mal
    # aplicado, y aborta en vez de imprimirse.
    tope_utr3 = bound_of(anatomia)
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
        lines.extend(f"  · {s.describe(frame=marco)}" for s in tiling.signals)
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
        lines.append("")
        lines.extend(
            f"  {l}"
            for l in _envolver(single_shmir_verdict(conservation).describe(), 86)
        )

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
            f"pos {span(choice.start, choice.end, marco)} "
            f"{(choice.tercio.value if choice.tercio else choice.region.value):<8} "
            f"asim {choice.asymmetry:+.2f}  {window.verdict.value}"
            + ("  riesgo_APA" if window.riesgo_APA else "")
        )

    config = selection.selection.config
    if config.apa_immune_quota or config.min_per_tercio > 1 or config.tercio_quota:
        lines.extend(["", "── Reparto de plazas ──"])
        cuotas = []
        if config.tercio_quota:
            cuotas.append(
                "por tercio del 3'UTR "
                + ", ".join(f"{t.value} {n}" for t, n in config.tercio_quota)
            )
        elif config.require_one_per_tercio:
            cuotas.append(f"{config.min_per_tercio} por tercio del 3'UTR")
        if config.apa_immune_quota:
            cuotas.append(
                f"{config.apa_immune_quota} inmunes al corte de la señal proximal "
                f"(empiezan por delante de {label(config.apa_immune_before, marco)})"
            )
        lines.append("  Cuotas DURAS de este panel: " + "; ".join(cuotas) + ".")
        lines.append(
            "  De donde salen esas plazas: el bloque «solo de fuente externa» "
            "desaparecio por VACIO."
        )
        lines.append(
            "  Contra el conjunto completo de sitios elegibles no queda ni un sitio "
            "exclusivo de la"
        )
        lines.append(
            "  fuente externa que supere nuestros filtros duros, asi que sus plazas se "
            "reasignan a"
        )
        lines.append("  COBERTURA GEOGRAFICA.")
        lines.append(
            "  Por que a cobertura y no por asimetria: las causas de fallo son "
            "regionales, no puntuales"
        )
        lines.append(
            "  —un APA, un elemento repetitivo, un tramo estructurado afectan a una "
            "REGION entera—, asi"
        )
        lines.append(
            "  que con la prediccion SATURADA la unica variable que sigue comprando "
            "independencia entre apuestas"
        )
        lines.append(
            "  es el espaciado. Dos candidatos del mismo tramo con asimetrias distintas "
            "siguen"
        )
        lines.append("  compartiendo modo de fallo.")
        if config.apa_immune_quota and config.tercio_quota:
            lines.append(
                "  El espaciado NO se baja para meter un inmune mas: el espaciado "
                "compra INDEPENDENCIA"
            )
            lines.append(
                "  entre apuestas, no NUMERO de apuestas. Dos candidatos a 30 nt fallan "
                "juntos, asi que"
            )
            lines.append(
                "  un quinto inmune pegado a otro no compraria nada. La plaza que la "
                "cuota de inmunes no"
            )
            lines.append(
                "  puede llenar se reasigna al TERCIO MEDIO, que es donde el panel "
                "queda mas flojo:"
            )
            lines.append(
                "  si el APA resulta funcional se pierde un candidato; si no, se gana "
                "cobertura donde"
            )
            lines.append("  hace falta.")
        for fallo in selection.selection.quota_unfilled:
            lines.append(f"    ⚠  {fallo}")

    lines.extend(["", "── Cobertura por tercios ──"])
    lines.extend(f"  {l}" for l in tercio_counts(tiling).describe())

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
    lines.append(comparative_text(selection, scaffold, anatomy=tiling.anatomy))

    for nota in notes:
        lines.extend(["", *nota.splitlines()])

    lines.extend(["", "── Riesgo de polyA: los DOS riesgos, separados ──"])
    lines.append(
        "  La regla de ±flanco mezclaba dos cosas distintas, y esto las separa:"
    )
    lines.append(
        "    TRUNCAMIENTO  la ventana esta POR DETRAS del corte que dirige un hexamero "
        "funcional."
    )
    lines.append(
        "                  El corte cae 10-30 nt aguas abajo. Es un riesgo sobre la "
        "EXISTENCIA de"
    )
    lines.append("                  la diana: si esa isoforma se usa, el tramo no esta.")
    lines.append(
        "    ESTERICO      la ventana SOLAPA el hexamero y compite con CPSF/CstF por "
        "ese tramo."
    )
    lines.append(
        "                  Es un riesgo sobre la ACCESIBILIDAD, y solo existe si el "
        "hexamero se usa."
    )
    lines.append(
        "  Un mismo hexamero NUNCA produce los dos en la misma ventana: o estas encima "
        "de la"
    )
    lines.append("  señal, o estas por detras de su corte.")
    lines.append("")
    # El riesgo DOMINANTE es el del corte MAS TEMPRANO, y eso no es lo mismo que «la
    # canonica». Con el tercer sitio medido de PolyA_DB el corte mas temprano lo pone un
    # AATATA —variante rara— que entra por MEDIDA de uso, no por canonicidad. Filtrar
    # por hexamero canonico aqui dejaria fuera justo la señal que manda.
    canonicas = [
        s for s in tiling.signals if s.classification.value == "APA_POSIBLE"
    ]
    # TODAS las señales de APA, con cuanto panel condiciona cada una. Enseñar solo la
    # dominante esconde el resto: el 3'UTR humano tiene DOS y la segunda condiciona la
    # mitad distal, que es justo donde cae su bloque conservado.
    techos = apa_ceiling_table(tiling)
    if len(techos) > 1:
        lines.append(
            f"  SEÑALES DE APA POSIBLE: {len(techos)}. Cada una pone su propio techo, y "
            f"se cuentan aparte:"
        )
        for fila in techos:
            # La viñeta va SOLO en la primera linea: repetirla en las continuaciones
            # hace que cada trozo parezca una señal distinta, y aqui la cuenta de
            # señales es justo lo que se esta dando.
            trozos = _envolver(fila.describe(), 86)
            lines.append(f"    · {trozos[0]}")
            lines.extend(f"      {l}" for l in trozos[1:])
        lines.append("")
    coste = measured_promotion_cost(tiling)
    if coste.windows:
        lines.extend(f"  {l}" for l in _envolver(coste.describe(), 86))
        lines.append("")
    holguras = promotion_clearance(tiling, selection)
    if holguras.rows:
        lines.extend(f"  {l}" for l in _envolver(holguras.describe(), 86))
        lines.append("")
    if canonicas:
        dominante = min(canonicas, key=lambda s: s.position)
        corte = span(dominante.end + 10, dominante.end + 30, marco)
        # Las dos parejas, como en todo lo demas, y cada una con su espacio pegado.
        en_utr3 = (
            f" ({span(dominante.position - desfase, dominante.end - desfase, Frame.UTR3, limit=tope_utr3)})"
            if desfase
            else ""
        )
        lines.append(
            f"  RIESGO DE TRUNCAMIENTO DOMINANTE DEL PANEL: {dominante.motif} en "
            f"{span(dominante.position, dominante.end, marco)}{en_utr3}."
        )
        if dominante.evidence == "medida":
            lines.append(
                "  Clasificada APA_POSIBLE POR MEDIDA DE USO, no por canonicidad — y es "
                "el caso INVERSO"
            )
            lines.append(
                "  al del hexamero canonico: aqui el hexamero es una VARIANTE RARA "
                "("
                + dominante.motif
                + "), que por nuestra"
            )
            lines.append(
                "  cascada de prediccion saldria OTRA y valdria solo una penalizacion de "
                "ranking. Lo que la"
            )
            lines.append(
                "  sube es que hay dato de uso, y la medida SUSTITUYE a la prediccion: "
                "una variante rara"
            )
            lines.append(
                "  MEDIDA vale mas que una canonica sin medir. Procedencia del dato:"
            )
            lines.extend(
                f"    {l}" for l in _envolver(dominante.measured_use, 84)
            )
        else:
            lines.append(
                "  Clasificada APA_POSIBLE POR SER CANONICA y estar a mas de 100 nt del "
                "extremo 3',"
            )
            lines.append(
                "  NO POR EVIDENCIA DE USO: aqui no hay ni un dato de uso de este sitio. "
                "Es un SUPUESTO,"
            )
            lines.append(
                "  no una medida. Con una tabla de PolyA_DB o PolyASite (--apa-medido) "
                "dejaria de serlo."
            )
        lines.append(
            f"  Su corte cae en {corte}. Un candidato que empiece por detras pierde su "
            f"diana en la"
        )
        lines.append(
            "  isoforma CORTA y la conserva en la LARGA: el APA reparte los transcritos "
            "en una"
        )
        lines.append(
            "  MEZCLA DE ISOFORMAS, asi que lo que corre es un TECHO de knockdown — "
            "NO ES UN VETO."
        )
        detras, inmunes = [], []
        for choice in selection.selection.chosen:
            ventana = selection.window_of(choice)
            inicio = ventana.inicio_3utr if ventana.inicio_3utr else ventana.window.start
            (detras if ventana.window.start > dominante.end + 10 else inmunes).append(
                inicio
            )
        if detras:
            lines.append(
                f"    con TECHO (por detras del corte): "
                f"{', '.join(label(p, Frame.UTR3) for p in sorted(detras))}"
            )
            if tiling.measured_apa is None:
                lines.append(
                    "      techo indeterminado: fraccion_isoforma_larga NO MEDIDA. No es "
                    "0 ni 1 — es que"
                )
                lines.append(
                    "      nadie la ha medido, y hasta entonces el techo de estos "
                    "candidatos no se escribe."
                )
            else:
                # Con varios sitios medidos el techo NO es uno: depende de por detras de
                # cuantos cortes esta cada candidato. Se da el de cada uno.
                lines.append("      techo MEDIDO, y no es el mismo para todos:")
                for posicion in sorted(detras):
                    capa = tiling.measured_apa.layer_for(posicion + desfase)
                    lines.append(
                        f"        {label(posicion, Frame.UTR3)}: "
                        + (
                            "INDETERMINADO (dentro de una banda de corte)"
                            if capa.ceiling is None
                            else f"{capa.ceiling:.2f}"
                        )
                    )
        # Los inmunes del panel, y los que la piscina de elegibles tiene ademas. Con un
        # solo inmune el panel entero depende de que el supuesto de arriba sea falso.
        alternativas = [
            sitio.best
            for sitio in selection.selection.sites
            if sitio.best.start <= dominante.end + 10
            and sitio.best.start not in {c.start for c in selection.selection.chosen}
        ]
        alternativas.sort(key=lambda c: -c.asymmetry)
        # «Inmune» a secas no vale: el que ademas queda MARCADO en el eje esterico se
        # dice ahi mismo, porque leer «3utr:200» en la misma lista que 3utr:10 da a
        # entender que estan igual de limpios y no lo estan.
        marcados = {
            f.start: f.steric for f in promotion_clearance(tiling, selection).rows
        }
        lines.append(
            "    INMUNES al TRUNCAMIENTO por ser proximales a esa señal: "
            + (
                ", ".join(
                    label(p, Frame.UTR3, limit=tope_utr3)
                    + (f" [esterico {marcados[p]}]" if p in marcados else "")
                    for p in sorted(inmunes)
                )
                + " (del panel)"
                if inmunes
                else "ninguno del panel"
            )
        )
        if alternativas:
            top = alternativas[:6]
            lines.append(
                f"      INMUNES elegibles NO elegidos: {len(alternativas)} sitio(s). "
                f"Los mejores por asimetria:"
            )
            # En la MISMA pareja de coordenadas que las lineas de arriba: mezclar el
            # marco del transcrito con el del 3'UTR aqui daria un «1018» que no es el
            # 1018 de dos lineas mas arriba.
            def _en_3utr(choice) -> int:
                ventana = selection.windows[choice.label]
                return ventana.inicio_3utr or ventana.window.start

            # Las DOS cifras cuando hay penalizacion: la asimetria cruda y la neta.
            # Dar una sola columna con la neta hizo que el 221 saliera +4.15 al lado de
            # candidatos sin penalizar — misma columna, dos magnitudes distintas.
            def _asimetria(choice) -> str:
                if choice.penalty:
                    return (
                        f"{choice.asymmetry_raw:+.2f} − {choice.penalty:.2f} penal. "
                        f"= {choice.asymmetry:+.2f}"
                    )
                return f"{choice.asymmetry_raw:+.2f}"

            lines.append(
                "        "
                + "; ".join(
                    f"{label(_en_3utr(c), Frame.UTR3, limit=tope_utr3)} ({_asimetria(c)})"
                    for c in top
                )
                + "  ← inmunes tambien"
            )
            lines.append(
                "      Son las plazas con las que se cambia un candidato con techo por "
                "uno inmune."
            )
        if len(inmunes) + len(alternativas) < 3:
            lines.append(
                "    Con uno o dos inmunes el panel depende de un supuesto que aqui no "
                "se ha medido."
            )
        if not inmunes:
            lines.append(
                "    Ningun candidato del panel esta por delante de esa señal. Un panel "
                "entero por"
            )
            lines.append(
                "    detras del mismo corte comparte un unico modo de fallo: si esa "
                "isoforma domina,"
            )
            lines.append("    todos quedan con el mismo techo a la vez.")

        if polya_conservation is not None:
            lines.append("  Conservacion de esta señal en la otra especie:")
            lines.extend(
                f"    {l}"
                for l in _envolver(polya_conservation.describe(), 84)
            )
            if not polya_conservation.conserved:
                lines.extend(
                    f"    {l}"
                    for l in _envolver(
                        polya_conservation.prior_note(
                            ceiling=(
                                None if tiling.measured_apa is None
                                else tiling.measured_apa.layers[-1].ceiling
                            )
                        ),
                        84,
                    )
                )
                lines.append(
                    "    Consecuencia: el techo es un problema del MODELO murino, no "
                    "del candidato."
                )
        else:
            lines.append(
                "  Sobre si esta conservada en otra especie: NOT_RUN. No se ha pasado "
                "ningun 3'UTR"
            )
            lines.append(
                "  con el que comparar (--fasta-b), asi que este informe no lo "
                "confirma ni lo desmiente."
            )
        # El experimento que convierte el techo en un numero. Coordenadas derivadas,
        # esquivando las dianas del panel: en muestras tratadas un amplicon que solape
        # una diana mide corte por RNAi, no isoformas.
        plan = rtqpcr_amplicons(
            dominante,
            utr_length=tiling.sequence_length,
            frame=marco,
            # Los amplicones se quedan DENTRO de lo que se ha analizado como 3'UTR: sin
            # este limite, esquivar las dianas del panel empujaba el proximal hasta el
            # CDS, y ahi ya no hay coordenada de 3'UTR que emitir.
            first_position=desfase + 1,
            avoid=[
                (
                    selection.window_of(c).window.start,
                    selection.window_of(c).window.end,
                )
                for c in selection.selection.chosen
            ],
        )
        lines.extend(["", "  ── Fraccion de isoforma larga ──"])
        if tiling.measured_apa is not None:
            lines.extend(f"  {l}" for l in tiling.measured_apa.describe())
            lines.append("")
        lines.extend(f"  {l}" for l in POLYA_DB_PRNP.describe())
        if tiling.measured_apa is not None:
            lines.append("")
            lines.extend(f"  {l}" for l in CLUSTER_READING.describe())
        lines.append("")
        lines.append(
            "  ANTES DEL BANCO — mirar si la fraccion ya esta medida y publicada:"
        )
        lines.append(
            "    1. PolyA_DB / PolyASite: ¿hay sitio anotado en este 3'UTR, y con que "
            "fraccion de"
        )
        lines.append(
            "       lecturas? Si lo hay, entra por --apa-medido y el techo deja de "
            "estar indeterminado."
        )
        lines.append(
            "    2. Datos publicos de 3'-end seq (3'-seq / PAS-seq / QuantSeq REV) de "
            "CEREBRO murino"
        )
        lines.append(
            "       sobre Prnp: la fraccion de uso del sitio proximal se lee "
            "directamente de ahi."
        )
        lines.append(
            "    Si la fraccion esta publicada, el experimento de abajo es una "
            "CONFIRMACION, no un"
        )
        lines.append(
            "    descubrimiento — y entonces cuesta lo que cuesta comprobar dos "
            "amplicones, no una serie."
        )
        lines.append("")
        lines.extend(f"  {l}" for l in plan.describe(offset=desfase))

    if orf_sweep is not None:
        lines.extend(["", "── La otra via: ORF conservado ──"])
        lines.extend(f"  {l}" for l in orf_sweep.describe())

    if convergence is not None:
        lines.extend(["", "── Convergencia con la fuente externa ──"])
        lines.extend(f"  {l}" for l in convergence.describe(offset=desfase))

    lines.extend(["", "── Que se ha analizado ──"])
    lines.append(
        f"  {tiling.sequence_length} nt, md5 canonico {tiling.sequence_md5}"
    )
    lines.append(
        "  Sin estas dos cifras no hay forma de saber que secuencia se analizo. El md5 "
        "es el de la"
    )
    lines.append(
        "  secuencia canonica (mayusculas, sin cabecera, sin saltos), no el del fichero."
    )
    lines.extend(f"  {l}" for l in CONVENTION_NOTE.splitlines())

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
    if tiling.mask is not None:
        from .masking import WHY_POLYMORPHIC, WHY_REPEAT, is_polymorphic

        polimorficos = [e for e in tiling.mask.elements if is_polymorphic(e)]
        if polimorficos:
            # Aqui NO se lista ventana por ventana: el paso 15 enmascara y RETILA, asi
            # que las ventanas afectadas ya no estan en la piscina y una lista saldria
            # vacia. Lo que si se dice es que son DOS ejes con un solo hallazgo detras.
            lines.append(
                "  ⚠  DOS EJES, no uno: "
                + ", ".join(e.describe() for e in polimorficos)
                + " es una repeticion POLIMORFICA en longitud."
            )
            lines.extend(f"     {l}" for l in _envolver(WHY_REPEAT, 85))
            lines.extend(f"     {l}" for l in _envolver(WHY_POLYMORPHIC, 85))
            lines.append("")
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
        modulo = carries_scaffold_module(tiling.transgene_db)
        lines.extend(f"  {'⚠  ' if modulo.carries else ''}{l}"
                     for l in _envolver(modulo.describe(), 88))

    # ── El quinto frente. Va DESPUES del transgen porque comparte fichero, y ANTES de
    # los criterios de polyA porque no es un criterio: es un riesgo binario que decide
    # si la arquitectura sigue viva.
    lines.extend(["", "── Empalme del intron ──"])
    lines.extend(f"  {l}" for l in _envolver(splicing.BINARY_NOT_GRADUAL, 88))
    lines.extend(f"  {l}" for l in _envolver(splicing.WHY_SMALL_RNA_SEQ_MISSES_IT, 88))
    plan_empalme, motivo_empalme = splicing.plan_from_records(
        tiling.transgene_db.records if tiling.transgene_db is not None else None
    )
    lines.append("")
    if plan_empalme is None:
        lines.extend(f"  {l}" for l in _envolver(motivo_empalme, 88))
    else:
        lines.extend(f"  {l}" for l in plan_empalme.describe())
    lines.append("")
    # (a) y (b) van separados: son mecanismos distintos y el segundo actua aunque el
    # primero no estorbara nada.
    lines.extend(f"  {l}" for l in _envolver(splicing.RETENTION_MODES, 88))
    lines.append("")
    intron_teorico = splicing.reference_intron()
    uatgs = splicing.scan_upstream_atgs(intron_teorico)
    lines.append("  (b) EL SEGUNDO MODO — el escaneo del ribosoma:")
    for u in uatgs:
        lines.append(f"      {u.describe()}")
    lines.extend(f"    {l}" for l in _envolver(splicing.describe_upstream_atgs(uatgs), 86))
    lines.append("")
    criptico = splicing.cryptic_donor_scan(intron_teorico)
    lines.extend(f"  {l}" for l in criptico.describe())
    lines.append("")
    lines.append("  LAS CUATRO LECTURAS QUE LO CIERRAN. Ninguna la corre este software:")
    for lectura in splicing.splicing_readouts(plan_empalme):
        trozos = _envolver(f"{lectura.name} [{lectura.state.value}]: {lectura.requirement}", 84)
        lines.append(f"    · {trozos[0]}")
        lines.extend(f"      {l}" for l in trozos[1:])

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
            f"    {valor:.1f} kcal/mol → "
            f"{', '.join(label(p, marco) for p in posiciones) or '—'}"
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
        # Y con nombre y apellidos: cuantos FRENTES quedan abiertos, no «un
        # bloqueante». Un fichero pequeño que falta y una base de datos que falta
        # bloquean igual, y decir «solo falta uno» invita a pedir oligo.
        frentes = blocking_fronts(tiling, selection)
        abiertos = [f for f in frentes if f.blocking]
        cerrados = [f for f in frentes if not f.blocking]
        lines.append(
            f"  EL PANEL ES PROVISIONAL EN {len(abiertos)} FRENTE(S): "
            + ", ".join(sorted(f.name for f in abiertos))
            + "."
        )
        for frente in abiertos:
            if frente.name not in selection.not_run_filters:
                lines.extend(
                    f"    {l}" for l in _envolver(f"{frente.name}: {frente.reason}", 86)
                )
        # Un frente CERRADO no se borra de la lista: se enseña cerrado. Borrarlo dejaria
        # el informe sin memoria de por que se cerro, y el siguiente lector no sabria si
        # se resolvio o si nadie lo miro.
        for frente in cerrados:
            lines.append(f"  FRENTE CERRADO — {frente.name}:")
            lines.extend(f"    {l}" for l in _envolver(frente.reason, 86))
        lines.append(
            "  NO SE PIDE OLIGO hasta que los "
            + {3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho"}.get(
                len(abiertos), str(len(abiertos))
            )
            + " tengan veredicto. Que uno de ellos se arregle con un fichero pequeño"
        )
        lines.append(
            "  y otro necesite una base entera no cambia nada: los dos bloquean igual, "
            "y llamar «unico"
        )
        lines.append(
            "  bloqueante» al pequeño es lo que hace que se pida oligo con dos filtros "
            "sin correr."
        )
        # Y hay una tercera categoria desde que esta el empalme: un frente que NO se
        # cierra con ningun fichero. Meterlo en el mismo saco que los de recurso haria
        # pensar que basta con conseguir datos.
        if any(f.name == "empalme_intron" for f in abiertos):
            lines.append(
                "  Y uno de ellos NO SE CIERRA CON NINGUN FICHERO: el empalme del intron "
                "solo se cierra en el"
            )
            lines.append(
                "  banco, con las tres lecturas de su bloque. Ademas es el unico BINARIO "
                "— los demas degradan el"
            )
            lines.append(
                "  resultado, este lo anula: sin empalme no hay proteina DN en absoluto."
            )

    # ── Multiplexado: nucleos de seed compartidos ──────────────────────────────
    # Va SIEMPRE, no solo cuando hay conflicto: «ninguno» es informacion y su ausencia
    # se leeria como que nadie lo miro. Es el mismo papel que el aviso de espaciado, en
    # otro eje — y este el espaciado no lo ve, porque mide distancia y no parecido.
    from .offtarget import MULTIPLEX_NOTE, core_conflicts

    conflictos = core_conflicts(selection)
    lines.extend(["", "── Multiplexado: nucleos de seed compartidos ──"])
    if conflictos:
        for conflicto in conflictos:
            # Las dos etiquetas salen del MARCO del informe, no de un prefijo escrito
            # dentro de `describe()`: sobre un informe del transcrito completo eso
            # imprimia `3utr:` para coordenadas de transcrito, sin dar ningun error.
            texto = conflicto.describe(
                label_a=label(conflicto.a, marco),
                label_b=label(conflicto.b, marco),
            )
            envueltas = _envolver(texto, 86)
            lines.append(f"  ⚠  {envueltas[0]}")
            lines.extend(f"     {l}" for l in envueltas[1:])
        lines.extend(f"  {l}" for l in _envolver(MULTIPLEX_NOTE, 86))
    else:
        lines.append(
            "  Ninguna pareja del panel comparte el nucleo de 6 nt: en este eje los "
            "candidatos son"
        )
        lines.append(
            "  independientes. Se dice aunque salga limpio — su ausencia se leeria como "
            "que nadie lo miro."
        )

    # ── Triple motivo por ventana ──────────────────────────────────────────────
    # Estaba calculado y no salia en ninguna parte: era el unico analisis del proyecto
    # que existia solo porque alguien lo corria a mano. Las filas se calculan fuera
    # —hace falta un informe tilado SIN mascara— y entran por parametro, como la
    # convergencia.
    lines.extend(["", "── Triple motivo: repetitivo + polimorfico + TECHO ──"])
    if triple_motive is None:
        lines.append(
            "  NOT_RUN: hace falta la mascara de repeticiones y un tilado SIN "
            "enmascarar. Con la"
        )
        lines.append(
            "  mascara puesta el paso 15 retila, asi que esas ventanas ya no estan en la "
            "piscina y una"
        )
        lines.append("  lista por ventana saldria VACIA — que no es lo mismo que limpia.")
    elif not triple_motive:
        lines.append(
            "  Ninguna ventana elegible cae por los tres ejes a la vez sobre esta "
            "secuencia."
        )
    else:
        lines.append(
            f"  {len(triple_motive)} ventana(s) caen por TRES razones INDEPENDIENTES. No "
            f"se recuperan"
        )
        lines.append("  arreglando una:")
        for fila in triple_motive:
            lines.extend(f"    {l}" for l in _envolver(fila.describe(), 84))

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
