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


# ─── El modal de especificidad (BLAST) ───────────────────────────────────────
#
# TODA la logica del modal vive aqui (regla 6): la pagina no decide nada — ni ordena, ni
# marca en rojo, ni elige un estado. Si empieza a hacerlo, se mueve aqui.
#
# Y el modal NO ejecuta el BLAST: prepara la peticion, la entrega y recoge el resultado.
# Ver `blast.py` para por que (CORS + sin red saliente) y `blast_store.py` para que pasa
# al subirlo.

BLAST_MODAL_NOTE = (
    "Guia y pasajera son DOS CONSULTAS distintas y las dos hacen falta: la pasajera "
    "tambien se carga en AGO2 en alguna fraccion, asi que sus off-targets son reales. "
    "Se marcan por separado a proposito."
)


def blast_candidate_rows(selection, *, species: str) -> list[dict[str, object]]:
    """Una fila por candidato, con los dos nombres de consulta ya construidos."""
    filas = []
    for choice in selection.selection.chosen:
        ventana = selection.window_of(choice)
        bloque = None
        filas.append(
            {
                "start": choice.start,
                "guia_id": f"{species}_pos{choice.start}_guia",
                "pasajera_id": f"{species}_pos{choice.start}_pasajera",
                "guia": ventana.evaluation.guide.replace("U", "T"),
                "pasajera": _passenger_dna(ventana.evaluation.guide),
                "asimetria": f"{choice.asymmetry:+.2f}",
                "veredicto": ventana.verdict.value,
                # Todo lo que sale del panel de esta corrida ES del panel. La casilla
                # «solo los del panel» existe para cuando se listan mas.
                "panel": True,
            }
        )
    return filas


def _passenger_dna(guide: str) -> str:
    from .blocks import build_block
    from .scaffold import SGEP_SCAFFOLD

    return build_block(guide, scaffold=SGEP_SCAFFOLD).passenger.replace("U", "T")


def blast_query(selection, *, species: str, starts, guides: bool, passengers: bool):
    """El FASTA de consulta de lo marcado. Aborta si no queda nada que consultar."""
    from .blast import QueryFasta
    from .errors import ShmirDesignError

    if not guides and not passengers:
        raise ShmirDesignError(
            "No se ha marcado ni guia ni pasajera: no hay nada que consultar. Son dos "
            "preguntas distintas y hace falta al menos una. Se aborta."
        )
    pedidos = list(dict.fromkeys(int(s) for s in starts))
    if not pedidos:
        raise ShmirDesignError(
            "No se ha marcado ningun candidato: no se genera un FASTA vacio. Se aborta."
        )
    por_inicio = {c.start: c for c in selection.selection.chosen}
    fuera = [s for s in pedidos if s not in por_inicio]
    if fuera:
        raise ShmirDesignError(
            f"Estos sitios no estan en el panel de esta corrida: "
            f"{', '.join(str(s) for s in fuera)}. Se aborta en vez de consultar una "
            f"guia que no existe aqui."
        )
    registros = []
    for inicio in pedidos:
        ventana = selection.window_of(por_inicio[inicio])
        guia = ventana.evaluation.guide.replace("U", "T")
        if guides:
            registros.append((f"{species}_pos{inicio}_guia", guia))
        if passengers:
            registros.append(
                (f"{species}_pos{inicio}_pasajera", _passenger_dna(
                    ventana.evaluation.guide
                ))
            )
    return QueryFasta.from_records(registros)


#: Que ajustes se enseñan y en que orden. Los TODOS, no solo los cambiados.
_SETTING_FIELDS = (
    "task", "word_size", "evalue", "dust", "outfmt", "db", "entrez_query",
    "include_predicted", "remote",
)


def blast_setting_rows(params) -> list[dict[str, object]]:
    """Una fila por ajuste, con `modificado` para que la pagina lo pinte en rojo.

    La pagina NO decide cual va en rojo: recibe el booleano. Es la misma leccion del
    `.out` sin especie — un veredicto con ajustes cambiados no puede ser indistinguible
    de uno estandar, y para eso hay que verlo.
    """
    from .blast import DEFAULTS

    tocados = set(params.modified())

    def _fmt(valor):
        if isinstance(valor, bool):
            return "SI" if valor else "no"
        if isinstance(valor, float):
            return f"{valor:g}"
        return str(valor)

    return [
        {
            "ajuste": campo,
            "valor": _fmt(getattr(params, campo)),
            "por_defecto": _fmt(getattr(DEFAULTS, campo)),
            "modificado": campo in tocados,
        }
        for campo in _SETTING_FIELDS
    ]


def blast_warnings(params) -> list[dict[str, object]]:
    """Los avisos del modal. `bloquea` = esta corrida no puede cerrar el frente."""
    from .seed_load import WHY_NOT_BLAST

    avisos = []
    if not params.can_give_verdict:
        avisos.append({"bloquea": True, "texto": params.why_no_verdict})
    # Este sale SIEMPRE, con o sin ajustes tocados: no bloquea ESTE modal, pero deja
    # claro que un PASS aqui no cubre el otro frente.
    avisos.append(
        {
            "bloquea": False,
            "texto": (
                "Este modal es para COMPLEMENTARIEDAD EXTENSA. El off-target mediado por "
                f"seed es OTRO frente (`offtarget_seed`) y no se busca aqui. "
                f"{WHY_NOT_BLAST}"
            ),
        }
    )
    return avisos


def blast_command_text(params, *, query_path: str, out_path: str | None = None) -> str:
    """La orden lista para copiar, con TODOS los parametros."""
    return params.command(query_path=query_path, out_path=out_path)


def blast_executor_text() -> str:
    """Que ejecutor hay hoy y por que. La pagina lo imprime tal cual."""
    from .blast import default_executor

    ejecutor = default_executor()
    return f"Ejecutor: {ejecutor.name}. {ejecutor.why}"


def blast_params_from_form(valores: dict) -> "object":
    """Lo tecleado en el modal → `BlastParams`. Tambien esto vive fuera de la pagina.

    Convertir «SI»/«no» a booleano y un texto a entero es una DECISION, por poca que
    parezca: si la hace la pagina, no tiene test y el dia que alguien escriba «si» en
    minusculas el ajuste se lee como `False` sin que nadie se entere. La validacion de
    rango la hace `BlastParams.__post_init__`, que es donde estaba ya.
    """
    from .blast import BlastParams
    from .errors import ShmirDesignError

    def _si(clave: str) -> bool:
        crudo = str(valores.get(clave, "")).strip().lower()
        if crudo in ("si", "sí", "s", "true", "1"):
            return True
        if crudo in ("no", "n", "false", "0", ""):
            return False
        raise ShmirDesignError(
            f"El ajuste {clave!r} vale {valores.get(clave)!r} y solo entiende SI o no; "
            f"se aborta en vez de leerlo como «no» por descarte."
        )

    try:
        palabra = int(str(valores["word_size"]).strip())
        evalor = float(str(valores["evalue"]).strip())
    except (KeyError, ValueError) as exc:
        raise ShmirDesignError(
            f"No se pudo leer un ajuste numerico del modal ({exc}); se aborta en vez de "
            f"caer al valor por defecto sin decirlo."
        ) from exc
    return BlastParams(
        task=str(valores["task"]).strip(),
        word_size=palabra,
        evalue=evalor,
        dust=str(valores["dust"]).strip(),
        outfmt=str(valores["outfmt"]).strip(),
        db=str(valores["db"]).strip(),
        entrez_query=str(valores["entrez_query"]).strip(),
        include_predicted=_si("include_predicted"),
        remote=_si("remote"),
    )


# ─── El modal de colision de seed (este SI ejecuta) ──────────────────────────
#
# Mismo patron que el de BLAST y la misma regla 6: la pagina no decide nada. La
# diferencia es que aqui no hay orden que copiar — el calculo es subcadena contra
# `mature.fa`, ya cargado y verificado.


def seed_preview_rows(selection, *, species: str, params=None, starts=None,
                      guides: bool = True, passengers: bool = True):
    """La tabla de lo que se va a comparar, con el heptamero COMPARTIDO ya marcado."""
    from .seed_scan import DEFAULTS, preview_rows

    filas = preview_rows(
        selection, species=species, params=params or DEFAULTS, starts=starts,
        guides=guides, passengers=passengers,
    )
    return [
        {
            "candidato": f"3utr:{f.start}",
            "start": f.start,
            "hebra": f.strand,
            "secuencia": f.sequence,
            "heptamero": f.heptamer,
            "comparte": ", ".join(f"3utr:{s}" for s in f.shared_with),
            "marcada": f.checked,
        }
        for f in filas
    ]


_SEED_SETTINGS = ("window", "species_prefix", "level", "normalize_u_t")


def seed_setting_rows(params):
    """Un ajuste por fila, con `modificado` y `fijo`. La pagina solo pinta."""
    from .seed_scan import LEVELS, SEED_WINDOWS, SeedParams

    base = SeedParams()
    tocados = set(params.modified())
    opciones = {
        "window": tuple(sorted(SEED_WINDOWS)),
        "level": LEVELS,
        "species_prefix": ("mmu-", ""),
        "normalize_u_t": ("SI",),
    }
    return [
        {
            "ajuste": campo,
            "valor": (
                "SI" if getattr(params, campo) is True
                else str(getattr(params, campo) or "TODAS")
            ),
            "por_defecto": (
                "SI" if getattr(base, campo) is True
                else str(getattr(base, campo) or "TODAS")
            ),
            "modificado": campo in tocados,
            # La normalizacion no es editable: apagarla daria cero colisiones y
            # parecerian buenas noticias. Se enseña, no se ofrece.
            "fijo": campo == "normalize_u_t",
            "opciones": opciones[campo],
        }
        for campo in _SEED_SETTINGS
    ]


def seed_source_text(mature) -> str:
    """Release y md5 de `mature.fa` A LA VISTA, no escondidos en un tooltip."""
    if mature is None:
        return (
            "NOT_RUN: no hay `mature.fa` cargado, asi que no hay contra que comparar. "
            "NOT_RUN no es PASS."
        )
    return f"Fuente: {mature.provenance}"


def seed_highlights(scan):
    """Los tres bloques que van DESTACADOS, no enterrados en la tabla."""
    from .seed_scan import MIR30_NOTE

    con_mir30 = scan.mir30_results
    pasajeras = scan.for_strand("pasajera")
    return {
        "mir30": {
            "activo": bool(con_mir30),
            "texto": (
                (
                    "Colision con la familia miR-30 en: "
                    + ", ".join(f"3utr:{r.start} ({r.strand})" for r in con_mir30)
                    + ". " if con_mir30 else "Sin colisiones con la familia miR-30. "
                )
                + MIR30_NOTE
            ),
        },
        "pasajeras": {
            "activo": bool(pasajeras),
            "texto": (
                f"{len(pasajeras)} consulta(s) de PASAJERA, separadas de las de guia y "
                f"NUNCA sumadas en un veredicto unico: la pasajera se carga a RISC en "
                f"alguna proporcion, asi que sus off-targets son igual de reales — pero "
                f"son otra consulta."
            ),
        },
        "tasa_base": {"activo": True, "texto": scan.base_rate.describe()},
    }


def seed_load_placeholder(utr3_set):
    """El hueco del OTRO frente, preparado en la misma interfaz y en NOT_RUN visible."""
    from .filters import FilterState
    from .seed_scan import WHAT_THIS_DOES_NOT_ANSWER

    if utr3_set is None:
        return {
            "state": FilterState.NOT_RUN,
            "texto": (
                f"CARGA DE OFF-TARGETS POR SEED — NOT_RUN. Falta "
                f"`transcriptoma_3utr.fa`. {WHAT_THIS_DOES_NOT_ANSWER}"
            ),
        }
    return {
        "state": FilterState.PASS,
        "texto": (
            f"CARGA DE OFF-TARGETS POR SEED — hay transcriptoma cargado "
            f"({utr3_set.provenance}). Sigue siendo un numero comparativo, nunca un "
            f"veredicto."
        ),
    }


def seed_params_from_form(valores: dict):
    """Lo elegido en el modal → `SeedParams`. Fuera de la pagina, como en BLAST."""
    from .seed_scan import SeedParams

    return SeedParams(
        window=str(valores.get("window", "2-8")),
        species_prefix=(
            "" if str(valores.get("species_prefix", "mmu-")) == "TODAS"
            else str(valores.get("species_prefix", "mmu-"))
        ),
        level=str(valores.get("level", "ambos")),
    )


def seed_run(selection, *, mature, params, species: str, starts, guides, passengers):
    """Atajo con nombre estable para la pagina. La logica esta en `seed_scan`."""
    from .seed_scan import run_scan

    return run_scan(
        selection, mature=mature, params=params, species=species, starts=starts,
        guides=guides, passengers=passengers,
    )


def seed_result_rows(scan):
    """Una fila por consulta. La hebra va en su columna: no se funden."""
    return [
        {
            "candidato": f"3utr:{r.start}",
            "hebra": r.strand,
            "heptamero": r.heptamer,
            "ventana": r.window,
            "nivel": r.level,
            "miR-30": "SI" if r.mir30 else "",
            "colisiones": ", ".join(c.name for c in r.collisions),
        }
        for r in scan.results
    ]


# ─────────────── tercer modal: carga de off-targets mediada por seed ───────────────
#
# El fichero que lo cierra —`transcriptoma_3utr.fa`— NO esta, asi que este modal tiene
# una pieza que los otros dos no necesitan: la SUBIDA, con su procedencia. Un fichero sin
# ensamblaje y sin fecha de la tabla no es reproducible, asi que la subida los exige y
# `Provenance` aborta si falta alguno.

_OFFTARGET_SETTINGS = ("null_draws", "null_seed", "species_prefix", "normalize_u_t")


def offtarget_placeholder(catalog):
    """El frente, en NOT_RUN VISIBLE mientras falte el fichero."""
    from .filters import FilterState
    from .offtarget import MISSING_FILE, USE_NOTE

    if catalog is None:
        return {
            "state": FilterState.NOT_RUN,
            "texto": (
                f"CARGA DE OFF-TARGETS POR SEED — NOT_RUN. Falta `{MISSING_FILE}`. "
                f"NOT_RUN no es PASS, y sobre todo NO ES CERO: no haber contado cuantos "
                f"mensajeros llevan esta seed no es lo mismo que no llevarla ninguno."
            ),
        }
    return {
        "state": FilterState.PASS,
        "texto": (
            f"CARGA DE OFF-TARGETS POR SEED — hay catalogo cargado "
            f"({catalog.provenance.assembly}, {catalog.provenance.table_date}, "
            f"{len(catalog.records)} registro(s)). {USE_NOTE}"
        ),
    }


def offtarget_route_text() -> str:
    from .offtarget import UCSC_ROUTE

    return UCSC_ROUTE


def offtarget_provenance_from_form(form: dict, *, md5: str):
    """El formulario de procedencia → `Provenance`. Aborta si falta un campo."""
    from .offtarget import Provenance

    return Provenance(
        source=str(form.get("source", "")),
        assembly=str(form.get("assembly", "")),
        table=str(form.get("table", "")),
        table_date=str(form.get("table_date", "")),
        representative=str(form.get("representative", "")),
        version=str(form.get("version", "")),
        md5=md5,
    )


def offtarget_upload_rows(raw, *, declared_md5=None, gene_map=None):
    """Lo que se comprueba al recibir el fichero, en filas con `avisa`."""
    from .offtarget import validate_upload

    informe = validate_upload(raw, declared_md5=declared_md5, gene_map=gene_map)
    return [
        {"campo": "secuencias", "valor": f"{informe.records}", "avisa": False},
        {"campo": "longitud total", "valor": f"{informe.total_nt} nt", "avisa": False},
        {"campo": "md5", "valor": informe.md5, "avisa": False},
        {
            "campo": "identificadores distintos",
            "valor": f"{informe.audit.distinct_ids}",
            "avisa": bool(informe.audit.repeated_ids),
        },
        {
            "campo": "isoformas por gen",
            "valor": informe.audit.warning(),
            "avisa": informe.audit.inflated or not informe.audit.checked_by_gene,
        },
    ]


def offtarget_catalog_from_upload(raw, *, form: dict, declared_md5=None, gene_map=None):
    """Del fichero subido al catalogo, con su procedencia y su indice."""
    from .offtarget import build_catalog, validate_upload

    informe = validate_upload(raw, declared_md5=declared_md5, gene_map=gene_map)
    return build_catalog(
        informe.parsed,
        provenance=offtarget_provenance_from_form(form, md5=informe.md5),
        gene_map=gene_map,
    )


def offtarget_setting_rows(params):
    """Un ajuste por fila, con `modificado` y `fijo`. La pagina solo pinta."""
    from .offtarget import OfftargetParams

    base = OfftargetParams()
    tocados = set(params.modified())
    opciones = {
        "null_draws": ("10000", "20000", "50000"),
        "null_seed": ("0", "1", "2", "3"),
        "species_prefix": ("mmu-", "hsa-"),
        "normalize_u_t": ("SI",),
    }
    return [
        {
            "ajuste": campo,
            "valor": (
                "SI" if getattr(params, campo) is True
                else str(getattr(params, campo) or "TODAS")
            ),
            "por_defecto": (
                "SI" if getattr(base, campo) is True
                else str(getattr(base, campo) or "TODAS")
            ),
            "modificado": campo in tocados,
            # La normalizacion no es editable: sin ella una guia en ADN contra un 3'UTR
            # en ARN daria CERO sitios, y cero parece una buena noticia.
            "fijo": campo == "normalize_u_t",
            "opciones": opciones[campo],
        }
        for campo in _OFFTARGET_SETTINGS
    ]


def offtarget_params_from_form(valores: dict):
    """Lo elegido en el modal → `OfftargetParams`. La conversion vive AQUI."""
    from .offtarget import DEFAULTS, OfftargetParams

    return OfftargetParams(
        null_draws=int(valores.get("null_draws", DEFAULTS.null_draws)),
        null_seed=int(valores.get("null_seed", DEFAULTS.null_seed)),
        species_prefix=str(valores.get("species_prefix", DEFAULTS.species_prefix)),
    )


def offtarget_limitation_rows():
    """Las tres limitaciones, para pintarlas JUNTO al resultado y no en un pie."""
    from .offtarget import LIMITATIONS

    return [
        {
            "clave": lim.key,
            "titulo": lim.title,
            "texto": lim.text,
            "direccion": lim.direction,
        }
        for lim in LIMITATIONS
    ]


def offtarget_upper_bound():
    from .offtarget import UPPER_BOUND_NOTE

    return {"activo": True, "texto": UPPER_BOUND_NOTE}


def offtarget_run(selection, *, catalog, mature, params, species, starts, guides,
                  passengers, target, target_label):
    """Atajo con nombre estable para la pagina. La logica esta en `offtarget`."""
    from .offtarget import run_scan

    return run_scan(
        selection, catalog=catalog, mature=mature, params=params, species=species,
        starts=starts, guides=guides, passengers=passengers, target=target,
        target_label=target_label,
    )


def offtarget_result_rows(scan):
    """Una fila por consulta y UNA COLUMNA POR CLASE. Sin ningun total."""
    from .offtarget import SITE_CLASSES

    filas = []
    for r in scan.results:
        fila = {
            "candidato": f"3utr:{r.start}",
            "hebra": r.strand,
            "seed": r.patterns.heptamer,
        }
        for clase in SITE_CLASSES:
            fila[clase] = r.counts.sites[clase]
            fila[f"{clase} percentil"] = round(r.percentiles[clase], 1)
        filas.append(fila)
    return filas


def offtarget_control_rows(scan):
    """Los controles biologicos: conteo, no percentil. Ver `CONTROLS_NOTE`."""
    from .offtarget import SITE_CLASSES

    return [
        {
            "control": c.name,
            "seed": c.heptamer,
            **{clase: c.sites[clase] for clase in SITE_CLASSES},
        }
        for c in scan.controls
    ]


def offtarget_self_count_rows(scan):
    """El autoconteo sobre la propia diana, con `anomalo` ya resuelto."""
    return [
        {
            "consulta": consulta,
            "diana": propio.target_label,
            "sitios": propio.occurrences,
            "esperado": propio.expected,
            "anomalo": propio.anomalous,
            "lectura": propio.describe(),
        }
        for consulta, propio in scan.self_counts.items()
    ]


def offtarget_highlights(scan):
    """Los bloques que van DESTACADOS, con `activo` ya decidido fuera de la pagina."""
    from .offtarget import CONTROLS_NOTE, UPPER_BOUND_NOTE, USE_NOTE

    raros = scan.anomalous_self_counts
    lineas_nula = []
    for clave, nula in scan.nulls.items():
        lineas_nula.append(f"[{clave}] " + " · ".join(nula.describe()))
    return {
        "limite_superior": {"activo": True, "texto": UPPER_BOUND_NOTE},
        "uso": {"activo": True, "texto": USE_NOTE},
        "nula": {"activo": True, "texto": "\n".join(lineas_nula)},
        "controles": {"activo": bool(scan.controls), "texto": CONTROLS_NOTE},
        "isoformas": {
            "activo": scan.audit.inflated or not scan.audit.checked_by_gene,
            "texto": scan.audit.warning(),
        },
        "autoconteo": {
            "activo": bool(raros),
            "texto": (
                " ".join(s.describe() for s in raros) if raros
                else "Todas las hebras tienen UN solo sitio en su propia diana."
            ),
        },
    }


# ─────────────── fichas de obtencion: como se resuelve cada NOT_RUN ───────────────


def obtencion_rows(front: str, *, species: str):
    """La ficha de un frente, ya resuelta contra la especie y lista para pintar.

    La pagina no resuelve nada: recibe listas y textos. Si la especie no tiene declarado
    algo que la ficha necesita —el prefijo de miRBase, el ensamblaje de UCSC—, eso sale
    en `avisos` ademas de dentro del paso, porque un paso largo se lee en diagonal.
    """
    from .obtencion import resolve_ficha
    from .species import resolve

    ficha = resolve_ficha(front, species=resolve(species))
    return {
        "frente": ficha.front,
        "pregunta": ficha.question,
        "fuente": ficha.source,
        "url": ficha.url,
        "tamano": ficha.size,
        "validacion": ficha.validation,
        "pasos": list(ficha.steps),
        "ficheros": [
            {
                "nombre": f.name,
                "por_que": f.why,
                "obligatorio": f.required,
            }
            for f in ficha.files
        ],
        "metadatos": [{"nombre": m.name, "por_que": m.why} for m in ficha.metadata],
        "avisos": list(ficha.warnings),
        "sin_fichero": ficha.no_file,
        "por_que_sin_fichero": ficha.why_no_file,
        "sin_declarar": list(ficha.undeclared),
        "texto": ficha.render(),
    }


def front_help_rows(tiling, selection, *, species: str):
    """Los frentes de esta corrida, con su estado y CON su ficha de obtencion.

    Es lo que convierte «falta el recurso» en algo accionable. Sale para TODOS los
    frentes, tambien los cerrados: un frente cerrado con su ficha delante deja ver con
    que se cerro.
    """
    from .filters import FilterState
    from .selection import blocking_fronts

    filas = []
    for frente in blocking_fronts(tiling, selection):
        ficha = obtencion_rows(frente.name, species=species)
        filas.append(
            {
                "frente": frente.name,
                "abierto": frente.blocking,
                "estado": FilterState.NOT_RUN if frente.blocking else FilterState.PASS,
                "motivo": frente.reason,
                "ficha": ficha,
            }
        )
    return filas
