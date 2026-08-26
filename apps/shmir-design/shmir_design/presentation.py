"""Todo lo que la interfaz necesita decidir, decidido aqui y probado aqui.

La UI no puede tener logica: si una funcion elige un color, ordena una tabla o dibuja
un mapa, vive en este modulo y tiene tests. `ui/streamlit_app.py` solo llama.

Stdlib pura, como el resto del nucleo: este modulo no importa Streamlit.

Python 3.11+ (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from .anatomy import Anatomy, RegionSource
from .blocks import blocks_fasta, blocks_tsv, build_block, order_sheet
from .comparative import comparative_tsv
from .cost import estimate_cost
from .conservation import (
    MIN_BLOCK_LENGTH,
    ConservationReport,
    Utr3,
    build_conservation_report,
)
from .errors import ShmirDesignError
from .hard_filters import DEFAULT_THRESHOLDS, Thresholds
from .filters import FilterState
from .outputs import fasta_guides, text_report, tsv_all_windows, tsv_oligos, tsv_selected
from .reference import ReferenceTranscript
from .resources import ResourceSet
from .scaffold import ScaffoldSpec
from .polya import POLYA_COLUMNS, normalize_sequence
from .selection import ReportSelection
from .tiling import TiledWindow, TilingReport

VERDE = "verde"
AMBAR = "ambar"


# ─── Semaforo ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StatusLight:
    color: str
    headline: str
    detail: str
    pending: tuple[str, ...] = field(default=())
    #: Cuantos filtros tiene un candidato en total, y cuantos llegaron a correr. El
    #: ambar sin grados deja de informar cuando siempre esta ambar: "faltan 2 de 9" y
    #: "faltan 8 de 9" son situaciones muy distintas.
    total: int = 0
    ran: int = 0


def status_light(selection: ReportSelection) -> StatusLight:
    """Verde si todos los filtros corrieron para los candidatos seleccionados.

    Mira los CANDIDATOS, no todas las ventanas del 3'UTR: una ventana enmascarada nunca
    se evalua —tiene N— y eso no significa que un filtro no haya llegado a correr. Lo
    que decide el color es si lo que se va a encargar esta filtrado del todo. Las
    ventanas no evaluables se cuentan aparte, en el detalle.
    """
    no_evaluables = sum(
        1
        for window in selection.windows.values()
        if any(r.state is FilterState.NOT_RUN for r in window.filters)
        and not window.biofisicos_ok
    )
    nota_no_evaluables = (
        f" Ademas hay {no_evaluables} ventana(s) no evaluable(s) (bases desconocidas "
        f"o enmascaradas); no son candidatas."
        if no_evaluables
        else ""
    )

    total = (
        len(selection.window_of(selection.selection.chosen[0]).filters)
        if selection.selection.chosen
        else 0
    )

    if not selection.selection.chosen:
        return StatusLight(
            color=AMBAR,
            headline="Ningun candidato seleccionado",
            detail=(
                "No hay ningun candidato que evaluar, asi que no hay nada que aprobar. "
                "Revisa los umbrales y cuantas ventanas superan los filtros."
                + nota_no_evaluables
            ),
        )

    pendientes = sorted(
        {
            r.name
            for choice in selection.selection.chosen
            for r in selection.window_of(choice).filters
            if r.state is FilterState.NOT_RUN
        }
    )
    if not pendientes:
        return StatusLight(
            color=VERDE,
            headline=f"Corrieron los {total} filtros para los candidatos",
            total=total,
            ran=total,
            detail=(
                f"Ninguno de los {len(selection.selection.chosen)} candidatos tiene "
                f"filtros en NOT_RUN: sus veredictos son completos." + nota_no_evaluables
            ),
        )

    return StatusLight(
        color=AMBAR,
        headline=(
            f"Faltan {len(pendientes)} de {total} filtros: "
            f"{', '.join(pendientes)}"
        ),
        detail=(
            f"NOT_RUN no es PASS. Corrieron {total - len(pendientes)} de {total} "
            f"filtros; no corrieron {', '.join(pendientes)}. Ningun candidato esta "
            f"aprobado y la seleccion es PROVISIONAL." + nota_no_evaluables
        ),
        pending=tuple(pendientes),
        total=total,
        ran=total - len(pendientes),
    )


# ─── Tablas ──────────────────────────────────────────────────────────────────
def _filter_columns(window: TiledWindow) -> dict[str, str]:
    return {r.name: r.state.value for r in window.filters}


def candidate_rows(selection: ReportSelection) -> list[dict[str, object]]:
    """Una fila por candidato, con el estado de CADA filtro en su propia columna."""
    rows: list[dict[str, object]] = []
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        rows.append(
            {
                "rango": selection.selection.rank_of(choice.start),
                "inicio": choice.start,
                "fin": choice.end,
                "region": window.region.value,
                "inicio_3utr": window.inicio_3utr,
                "fin_3utr": window.fin_3utr,
                "tercio": choice.tercio.value if choice.tercio else "—",
                # El VALOR de la asimetria y el ESTADO de su filtro son dos columnas:
                # si comparten nombre, el diccionario fusionado pierde el numero.
                "asimetria_kcal": round(choice.asymmetry, 2),
                # Los cinco campos de polyA por separado: un solo estado comprimido
                # deja al lector sin saber que filtro falta (bloque 3).
                **(
                    window.polya.as_columns()
                    if window.polya
                    else dict.fromkeys(POLYA_COLUMNS, "")
                ),
                # Numeros comparativos, no veredictos: vacios cuando no se calcularon,
                # nunca a cero (bloques 1b y 4).
                "carga_seed": (
                    window.carga_seed.as_column() if window.carga_seed else ""
                ),
                "accesibilidad": (
                    window.accesibilidad.as_column() if window.accesibilidad else ""
                ),
                **_filter_columns(window),
                "bandera_polyA_debil": window.bandera_polyA_debil,
                "biofisicos_ok": window.biofisicos_ok,
                "riesgo_APA": (
                    window.apa.as_column()
                    if window.apa is not None
                    else ("NO_APLICA" if not window.apa_aplica else window.riesgo_APA)
                ),
                "veredicto": window.verdict.value,
                "diana": window.evaluation.sequence,
                "guia": window.evaluation.guide,
            }
        )
    return rows


def window_rows(report: TilingReport) -> list[dict[str, object]]:
    """TODAS las ventanas. Ninguna se omite: omitir es esconder un NOT_RUN."""
    return [
        {
            "inicio": w.window.start,
            "fin": w.window.end,
            "region": w.region.value,
            "inicio_3utr": w.inicio_3utr,
            "tercio": w.tercio.value if w.tercio else "—",
            "asimetria_kcal": (
                None if w.evaluation.asymmetry is None
                else round(w.evaluation.asymmetry, 2)
            ),
            **_filter_columns(w),
            "bandera_polyA_debil": w.bandera_polyA_debil,
            "biofisicos_ok": w.biofisicos_ok,
            "veredicto": w.verdict.value,
            "diana": w.evaluation.sequence,
        }
        for w in report.windows
    ]


def anatomy_rows(
    transcript: ReferenceTranscript | None,
    utr3_length: int | None = None,
    *,
    anatomy: Anatomy | None = None,
) -> list[dict[str, object]]:
    """Anatomia del transcrito. Sin transcrito verificado no se adivina ningun ORF.

    Con una `Anatomy` resuelta —por GenBank o por coordenadas declaradas— se enseñan
    los tramos que esa anatomia tenga, cada uno con la procedencia que dice
    `RegionSource`. El transcrito verificado manda sobre lo declarado.
    """
    if transcript is None and anatomy is not None:
        tramos = [
            (nombre, tramo)
            for nombre, tramo in (
                ("5'UTR", anatomy.utr5),
                ("CDS", anatomy.cds),
                ("3'UTR", anatomy.utr3),
            )
            if tramo is not None
        ]
        return [
            {
                "tramo": nombre,
                "inicio": inicio,
                "fin": fin,
                "longitud": fin - inicio + 1,
                "origen": anatomy.source.describe(),
            }
            for nombre, (inicio, fin) in tramos
        ]
    if transcript is None:
        return [
            {
                "tramo": "3'UTR",
                "inicio": 1,
                "fin": utr3_length or 0,
                "longitud": utr3_length or 0,
                "origen": "declarado por ti, sin verificar",
            }
        ]
    return [
        {
            "tramo": nombre,
            "inicio": inicio,
            "fin": fin,
            "longitud": fin - inicio + 1,
            "origen": "verificado",
        }
        for nombre, (inicio, fin) in (
            ("5'UTR", transcript.utr5),
            ("CDS", transcript.cds),
            ("3'UTR", transcript.utr3),
        )
    ]


# ─── Mapa del 3'UTR ──────────────────────────────────────────────────────────
WIDTH = 1000
HEIGHT = 190
MARGIN = 40
TRACK_Y = 96
TRACK_H = 22


def _x(position: int, utr_length: int) -> float:
    usable = WIDTH - 2 * MARGIN
    return MARGIN + (position - 1) / max(1, utr_length - 1) * usable


def map_svg(
    report: TilingReport,
    selection: ReportSelection,
    conservation: ConservationReport | None = None,
    species: str | None = None,
) -> str:
    """Mapa del 3'UTR: candidatos, señales de poliadenilacion, mascara y bloques.

    Devuelve SVG como texto. Sin dependencias de dibujo: es una funcion pura y por eso
    se puede probar sin abrir un navegador.
    """
    length = report.utr_length
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="100%" role="img" aria-label="Mapa del 3\'UTR">',
        f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="#fbfaf7"/>',
        f'<rect x="{MARGIN}" y="{TRACK_Y}" width="{WIDTH - 2 * MARGIN}" '
        f'height="{TRACK_H}" fill="#e7e2d8" stroke="#b9b1a2"/>',
    ]

    # Tercios
    for fraccion, etiqueta in ((1 / 3, "proximal | medio"), (2 / 3, "medio | distal")):
        x = MARGIN + fraccion * (WIDTH - 2 * MARGIN)
        parts.append(
            f'<line x1="{x:.1f}" y1="{TRACK_Y - 6}" x2="{x:.1f}" '
            f'y2="{TRACK_Y + TRACK_H + 6}" stroke="#9a9184" stroke-dasharray="3 3"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{TRACK_Y + TRACK_H + 20}" font-size="10" '
            f'fill="#6b6357" text-anchor="middle">{escape(etiqueta)}</text>'
        )

    # Zonas enmascaradas
    if report.mask is not None:
        for start, end in report.mask.intervals:
            x1, x2 = _x(start, length), _x(min(end, length), length)
            parts.append(
                f'<rect data-mascara="{start}-{end}" x="{x1:.1f}" y="{TRACK_Y}" '
                f'width="{max(1.0, x2 - x1):.1f}" height="{TRACK_H}" fill="#8c8c8c" '
                f'opacity="0.75"><title>repeticion enmascarada {start}-{end}</title>'
                f'</rect>'
            )

    # Bloques conservados
    if conservation is not None and species is not None:
        for index, block in enumerate(conservation.blocks):
            hits = [h for h in block.hits if h.species == species]
            for hit in hits:
                x1, x2 = _x(hit.start, length), _x(min(hit.end, length), length)
                parts.append(
                    f'<rect data-bloque="{index}:{hit.start}-{hit.end}" x="{x1:.1f}" '
                    f'y="{TRACK_Y + TRACK_H + 4}" width="{max(2.0, x2 - x1):.1f}" '
                    f'height="7" fill="#2f7d5d"><title>bloque conservado '
                    f'{block.length} nt, {hit.start}-{hit.end}</title></rect>'
                )

    # Señales de poliadenilacion
    for signal in report.signals:
        x = _x(signal.position, length)
        color = "#c8501e" if signal.classification.name == "TERMINAL_PROBABLE" else "#b58900"
        parts.append(
            f'<polygon data-senal="{signal.position}" points="'
            f'{x:.1f},{TRACK_Y - 8} {x - 5:.1f},{TRACK_Y - 20} {x + 5:.1f},{TRACK_Y - 20}" '
            f'fill="{color}"><title>{escape(signal.describe())}</title></polygon>'
        )

    # Candidatos
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        x = _x(choice.start, length)
        rank = selection.selection.rank_of(choice.start)
        parts.append(
            f'<line data-candidato="{choice.start}" x1="{x:.1f}" y1="{TRACK_Y + TRACK_H}" '
            f'x2="{x:.1f}" y2="{TRACK_Y + TRACK_H + 34}" stroke="#1b6cb0" '
            f'stroke-width="2"/>'
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{TRACK_Y + TRACK_H + 40}" r="9" fill="#1b6cb0">'
            f'<title>#{rank} pos {choice.start}-{choice.end}, '
            f'{choice.tercio.value if choice.tercio else choice.region.value}, '
            f'asimetria {choice.asymmetry:+.2f}, {window.verdict.value}</title></circle>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{TRACK_Y + TRACK_H + 44}" font-size="10" '
            f'fill="#ffffff" text-anchor="middle">{rank}</text>'
        )

    # Escala
    for fraccion in (0.0, 0.5, 1.0):
        position = max(1, round(fraccion * length))
        x = _x(position, length)
        parts.append(
            f'<text x="{x:.1f}" y="{TRACK_Y - 26}" font-size="10" fill="#6b6357" '
            f'text-anchor="middle">{position}</text>'
        )
    parts.append(
        f'<text x="{MARGIN}" y="{HEIGHT - 8}" font-size="11" fill="#6b6357">'
        f"3'UTR de {length} nt — ▲ señal poliA · ▬ repeticion enmascarada · "
        f"▬ bloque conservado · ● candidato</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


# ─── Descargas ───────────────────────────────────────────────────────────────
def output_bundle(
    *,
    species: str,
    tiling: TilingReport,
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    transcript: ReferenceTranscript | None = None,
    conservation: ConservationReport | None = None,
    blocks: bool = False,
) -> dict[str, str]:
    """Las salidas, con los mismos nombres y contenido que el CLI."""
    salidas = {
        f"{species}_ventanas.tsv": tsv_all_windows(tiling),
        f"{species}_seleccionados.tsv": tsv_selected(selection, species=species),
        f"{species}_guias.fasta": fasta_guides(selection, species=species),
        f"{species}_oligos.tsv": tsv_oligos(selection, scaffold, species=species),
        f"{species}_informe.txt": text_report(
            species=species,
            tiling=tiling,
            selection=selection,
            scaffold=scaffold,
            transcript=transcript,
            conservation=conservation,
        ),
        f"{species}_comparativa.tsv": comparative_tsv(
            selection, scaffold, with_header=True, anatomy=tiling.anatomy
        ),
    }
    if blocks:
        salidas.update(block_bundle(selection, scaffold, species=species))
    return salidas


def conservation_for(
    sequences: dict[str, str],
    *,
    min_length: int = MIN_BLOCK_LENGTH,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> ConservationReport | None:
    """Bloques conservados entre dos 3'UTR, o `None` si solo hay uno.

    Con una sola especie no hay nada que comparar, y eso no es un error: la corrida
    murina es de una especie. Con mas de dos si se aborta — elegir dos por nuestra
    cuenta seria decidir cual es el modelo y cual la diana.
    """
    if len(sequences) < 2:
        return None
    if len(sequences) > 2:
        raise ShmirDesignError(
            f"Se han dado {len(sequences)} secuencias y los bloques conservados se "
            f"buscan entre DOS. Se aborta en vez de elegir dos por nuestra cuenta."
        )
    (nombre_a, seq_a), (nombre_b, seq_b) = sequences.items()
    return build_conservation_report(
        Utr3(nombre_a, seq_a),
        Utr3(nombre_b, seq_b),
        min_length=min_length,
        thresholds=thresholds,
    )


def block_bundle(
    selection: ReportSelection, scaffold: ScaffoldSpec, *, species: str
) -> dict[str, str]:
    """Bloques listos para pedir de los candidatos elegidos.

    Toda la decision vive aqui, no en la pagina: la UI solo enseña lo que devuelve.
    """
    bloques = [
        build_block(
            selection.window_of(choice).evaluation.guide.replace("U", "T"),
            scaffold=scaffold,
            transgene=selection.window_of(choice).transgen_detalle,
        )
        for choice in selection.selection.chosen
    ]
    return {
        f"{species}_bloques.fasta": blocks_fasta(bloques, species=species),
        f"{species}_bloques.tsv": blocks_tsv(bloques, species=species),
        f"{species}_hoja_de_pedido.txt": order_sheet(bloques, species=species),
    }


def block_rows(
    selection: ReportSelection, scaffold: ScaffoldSpec
) -> list[dict[str, object]]:
    """Una fila por bloque, con el estado de CADA comprobacion en su columna."""
    filas: list[dict[str, object]] = []
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        bloque = build_block(
            window.evaluation.guide.replace("U", "T"),
            scaffold=scaffold,
            transgene=window.transgen_detalle,
        )
        filas.append(
            {
                "inicio": choice.start,
                "guia": bloque.guide,
                "pasajera": bloque.passenger,
                "modulo_149": bloque.module,
                "cassette_318": bloque.cassette,
                "modulo_seguro": "si" if bloque.module_safe else "no",
                **{f"check:{r.name}": r.state.value for r in bloque.checks},
            }
        )
    return filas


# ─── Estimacion de coste ─────────────────────────────────────────────────────
#: Lo unico de `ResourceSet` que `estimate_cost` sabe cronometrar. Los demas campos
#: (`mask`, `expression`, `apa_sites`) no tienen una partida propia: el enmascarado
#: pasa antes de tilar y los otros dos son baratos. Splatear `as_kwargs()` entero
#: reventaria con TypeError, asi que la lista es explicita y hay test.
COST_FIELDS = (
    "specificity_db",
    "specificity_target",
    "transgene_db",
    "mature",
    "abundance",
    "utr3_set",
)


def cost_text(
    sequence: str,
    *,
    resources: ResourceSet | None = None,
    accessibility: bool = False,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> str:
    """Cuanto va a costar esta corrida, sin lanzarla.

    Recibe un 3'UTR, que es lo que la pagina tiene a mano, y declara esa anatomia por
    su nombre —el mismo contrato que `tile_utr` con una secuencia suelta—: aqui no se
    adivina ningun marco de lectura.

    La mascara no se aplica al estimar: reduce las ventanas elegibles, asi que el
    numero sale POR ENCIMA del tiempo real. Se dice, no se deja implicito.
    """
    original = normalize_sequence(sequence, name="3'UTR")
    campos = {}
    if resources is not None:
        completo = resources.as_kwargs()
        campos = {clave: completo[clave] for clave in COST_FIELDS}
    estimacion = estimate_cost(
        sequence=original,
        anatomy=Anatomy.whole_is_utr3(
            len(original), source=RegionSource.TODO_3UTR_DECLARADO
        ),
        thresholds=thresholds,
        accessibility=accessibility,
        **campos,
    )
    lineas = [estimacion.format_text()]
    if resources is not None and resources.mask is not None:
        lineas.append(
            "  Hay una mascara de repeticiones cargada y la estimacion NO la aplica: "
            "enmascarar deja"
        )
        lineas.append(
            "  menos ventanas elegibles, asi que el total de arriba es un techo, no "
            "una prediccion."
        )
    return "\n".join(lineas)
