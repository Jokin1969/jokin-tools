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
from .filters import Verdict
from .reference import ReferenceTranscript
from .gblock import build_gblock
from .scaffold import ScaffoldSpec, build_hairpin
from .selection import ReportSelection, penalty_sensitivity
from .specificity import SEED_CAVEAT, TAXIDS, blast_command
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
            f"tercio={choice.tercio.value} asimetria={choice.asymmetry:+.2f} "
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
            f"pos {choice.start}-{choice.end} {choice.tercio.value:<8} "
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
