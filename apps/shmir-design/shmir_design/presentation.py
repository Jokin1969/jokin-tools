"""Todo lo que la interfaz necesita decidir, decidido aqui y probado aqui.

La UI no puede tener logica: si una funcion elige un color, ordena una tabla o dibuja
un mapa, vive en este modulo y tiene tests. `ui/streamlit_app.py` solo llama.

Stdlib pura, como el resto del nucleo: este modulo no importa Streamlit.

Python 3.11+ (regla 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path, PurePosixPath

from . import coords
from .anatomy import Anatomy
from .coords import Frame
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
    #: Ventanas tiladas que NO pasan los filtros biofisicos, y el total del que salen.
    #: Van juntos a proposito: un numero suelto no dice si es mucho o poco, y el suelto
    #: fue justo el que produjo una aritmetica imposible en pantalla —«1221 ventanas a
    #: tilar» arriba y «1773 no evaluables» abajo— porque cada uno venia de un conjunto
    #: distinto con el mismo nombre.
    not_eligible: int = 0
    tiled: int = 0
    #: Filtros que calculan y NO emiten veredicto porque su criterio esta pendiente de
    #: decision escrita. No son frentes —no se cierran consiguiendo nada— y no cuentan
    #: para el color, pero salen NOMBRADOS: un filtro que no se ve no existe.
    undecided: tuple[str, ...] = ()


def status_light(selection: ReportSelection) -> StatusLight:
    """Verde si todos los filtros corrieron para los candidatos seleccionados.

    Mira los CANDIDATOS, no todas las ventanas del 3'UTR: una ventana enmascarada nunca
    se evalua —tiene N— y eso no significa que un filtro no haya llegado a correr. Lo
    que decide el color es si lo que se va a encargar esta filtrado del todo. Las
    ventanas no evaluables se cuentan aparte, en el detalle.
    """
    # QUE se cuenta aqui, y por que el texto no dice mas que eso.
    #
    # Antes esta cifra se anunciaba como «ventanas no evaluables (bases desconocidas o
    # enmascaradas)», y de las 1773 de la primera corrida real NI UNA tenia una N ni
    # estaba enmascarada: fallaban GC y homopolimero. El texto afirmaba una causa que
    # nadie habia comprobado — la misma familia que el «comprueba que Streamlit esta
    # instalado» pegado a un fallo de configuracion, y que el «Alu 0 %» obtenido sin
    # buscar Alu. Un diagnostico EQUIVOCADO cuesta mas que ninguno.
    #
    # Lo que se cuenta es exactamente esto: ventanas tiladas que no pasan los filtros
    # biofisicos. Y va con su total, porque un descartado sin total no se puede leer.
    tiladas = len(selection.windows)
    elegibles = sum(1 for w in selection.windows.values() if w.biofisicos_ok)
    no_elegibles = tiladas - elegibles
    # La descomposicion va COMPLETA o no va. Cuando lo tilado es un transcrito entero,
    # buena parte de las ventanas cae en el CDS y en el 5'UTR: esas no son candidatas por
    # REGION, no por los filtros, y mezclarlas en una sola resta produce justo la clase de
    # frase que esto viene a arreglar. (Escribiendo este mismo texto salio una primera
    # version que decia «las otras 407 si entran. De esas, 949 estan fuera del 3'UTR» —
    # 949 de 407. El fallo no es dificil de cometer: por eso la cuenta se emite entera.)
    fuera = sum(
        1 for w in selection.windows.values() if w.inicio_3utr is None
    )
    dentro = tiladas - fuera
    elegibles_dentro = sum(
        1
        for w in selection.windows.values()
        if w.inicio_3utr is not None and w.biofisicos_ok
    )
    nota_no_evaluables = (
        f" De las {tiladas} ventanas tiladas, {fuera} caen FUERA del 3'UTR (en el CDS o "
        f"el 5'UTR de lo tilado) y {dentro} dentro. Pasan los filtros biofísicos "
        f"{elegibles} en total: {elegibles_dentro} de las del 3'UTR y "
        f"{elegibles - elegibles_dentro} de las de fuera, que no son candidatas por "
        f"región. Por que falla cada una está en su fila de la tabla de ventanas: aquí "
        f"no se resume en una causa."
        if no_elegibles
        else ""
    )
    conteos = {"not_eligible": no_elegibles, "tiled": tiladas}

    # Los PENDIENTES DE DECISION no cuentan como filtros sin correr: su NOT_RUN no dice
    # «falta un recurso», dice «nadie ha decidido su criterio». Contarlos dejaba el verde
    # estructuralmente inalcanzable por algo que no se arregla consiguiendo nada — el
    # mismo fallo que tuvo la interfaz con sus tres parámetros.
    #
    # Y NO se esconden: salen aparte, con su nombre, en `undecided`.
    #
    # HOY NO HAY NINGUNO. El estado existió para G4 y se retiró con él (ver `filters.py`
    # y `docs/procedencia-g4.md`). El campo `undecided` se queda —vacío— porque es parte
    # del contrato de `StatusLight` y quien lo lee tiene que poder seguir leyéndolo; lo
    # que se fue es el conjunto que lo llenaba.
    sin_decidir: list[str] = []
    nota_sin_decidir = ""
    conteos = {**conteos, "undecided": ()}
    total = (
        len(selection.window_of(selection.selection.chosen[0]).filters)
        if selection.selection.chosen
        else 0
    )

    if not selection.selection.chosen:
        return StatusLight(
            color=AMBAR,
            headline="Ningún candidato seleccionado",
            detail=(
                "No hay ningún candidato que evaluar, así que no hay nada que aprobar. "
                "Revisa los umbrales y cuántas ventanas superan los filtros."
                + nota_no_evaluables + nota_sin_decidir
            ),
            **conteos,
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
            headline=f"Corrieron los {total} {FILTER_COUNT_NAME}",
            total=total,
            ran=total,
            detail=(
                f"Ninguno de los {len(selection.selection.chosen)} candidatos tiene "
                f"filtros en NOT_RUN: sus veredictos son completos."
                + nota_no_evaluables + nota_sin_decidir
            ),
            **conteos,
        )

    return StatusLight(
        color=AMBAR,
        headline=(
            f"Faltan {len(pendientes)} de {total} {FILTER_COUNT_NAME}: "
            f"{', '.join(pendientes)}"
        ),
        detail=(
            f"NOT_RUN no es PASS. Corrieron {total - len(pendientes)} de {total} "
            f"{FILTER_COUNT_NAME}; no corrieron {', '.join(pendientes)}. Ningún candidato esta "
            f"aprobado y la selección es PROVISIONAL."
            + nota_no_evaluables + nota_sin_decidir
        ),
        pending=tuple(pendientes),
        total=total,
        ran=total - len(pendientes),
        **conteos,
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


#: Por que el mapa no pone el marco.
#:
#: Se llama «Mapa del 3'UTR» y recibe un informe de tilado que puede ser de un
#: TRANSCRITO ENTERO. Cuando suponia que toda posicion era del 3'UTR pasaban dos cosas
#: a la vez, y solo una daba error:
#:
#:   - `signal.describe()` etiquetaba `3utr:1856` sobre un 3'UTR de 1242 nt. Eso lo
#:     abortaba `coords` — la cuarta vez que aparece la misma familia de fallo;
#:   - y el eje, los tercios y la escala se dibujaban sobre los 2191 nt de lo tilado.
#:     Eso NO daba ningun error: salia un mapa con la etiqueta «3'UTR» y las divisorias
#:     de los tercios en el sitio equivocado. Un mapa mudo y equivocado.
#:
#: Ahora el marco y la frontera salen de `report.frame` y `report.utr3_of()`, que los
#: derivan de la anatomia. Lo que no cae en el 3'UTR NO se dibuja y se DICE cuantos son:
#: descartarlos en silencio dejaria un mapa que parece completo.
WHY_THE_MAP_RECEIVES_THE_FRAME = (
    "El mapa dibuja el 3'UTR, y lo tilado puede ser el transcrito entero. El marco y la "
    "frontera se sacan de la anatomía (`report.frame`, `report.utr3_of`), no se suponen: "
    "suponerlos daba `3utr:1856` sobre un 3'UTR de 1242 nt y, peor, un eje de 2191 nt "
    "rotulado «3'UTR» con los tercios donde no era."
)


def map_svg(
    report: TilingReport,
    selection: ReportSelection,
    conservation: ConservationReport | None = None,
    species: str | None = None,
) -> str:
    """Mapa del 3'UTR: candidatos, señales de poliadenilacion, mascara y bloques.

    Devuelve SVG como texto. Sin dependencias de dibujo: es una funcion pura y por eso
    se puede probar sin abrir un navegador.

    El eje es el 3'UTR SIEMPRE, mida lo que mida lo tilado. Ver
    `WHY_THE_MAP_RECEIVES_THE_FRAME`.
    """
    marco = report.frame
    length = report.utr3_length
    fuera = 0

    def _en_utr3(position: int) -> int | None:
        return report.utr3_of(position)
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
            # Una repeticion puede caer entera en el CDS —el `(CTC)n` de tx:892-936 del
            # raton lo hace— y entonces no tiene sitio en un mapa del 3'UTR. Se cuenta
            # y se dice; dibujarla en la posicion equivalente del 3'UTR seria inventar
            # una repeticion donde no la hay.
            u1, u2 = _en_utr3(start), _en_utr3(min(end, report.utr_length))
            if u1 is None and u2 is None:
                fuera += 1
                continue
            u1 = 1 if u1 is None else u1
            u2 = length if u2 is None else u2
            x1, x2 = _x(u1, length), _x(u2, length)
            parts.append(
                f'<rect data-mascara="{coords.span(u1, u2, Frame.UTR3, limit=length)}" '
                f'x="{x1:.1f}" y="{TRACK_Y}" '
                f'width="{max(1.0, x2 - x1):.1f}" height="{TRACK_H}" fill="#8c8c8c" '
                f'opacity="0.75"><title>repeticion enmascarada '
                f'{coords.span(start, min(end, report.utr_length), marco)}</title>'
                f'</rect>'
            )

    # Bloques conservados
    if conservation is not None and species is not None:
        for index, block in enumerate(conservation.blocks):
            hits = [h for h in block.hits if h.species == species]
            for hit in hits:
                # Los bloques conservados se calculan SOBRE EL 3'UTR (la pagina le
                # pasa el 3'UTR a `conservation_for`), asi que ya estan en este marco.
                x1, x2 = _x(hit.start, length), _x(min(hit.end, length), length)
                parts.append(
                    f'<rect data-bloque="{index}:{hit.start}-{hit.end}" x="{x1:.1f}" '
                    f'y="{TRACK_Y + TRACK_H + 4}" width="{max(2.0, x2 - x1):.1f}" '
                    f'height="7" fill="#2f7d5d"><title>bloque conservado '
                    f'{block.length} nt, {hit.start}-{hit.end}</title></rect>'
                )

    # Señales de poliadenilacion
    for signal in report.signals:
        posicion = _en_utr3(signal.position)
        if posicion is None:
            fuera += 1
            continue
        x = _x(posicion, length)
        color = "#c8501e" if signal.classification.name == "TERMINAL_PROBABLE" else "#b58900"
        parts.append(
            f'<polygon data-senal="{coords.label(signal.position, marco)}" points="'
            f'{x:.1f},{TRACK_Y - 8} {x - 5:.1f},{TRACK_Y - 20} {x + 5:.1f},{TRACK_Y - 20}" '
            f'fill="{color}">'
            f'<title>{escape(signal.describe(frame=marco))}</title></polygon>'
        )

    # Candidatos
    for choice in selection.selection.chosen:
        window = selection.window_of(choice)
        posicion = _en_utr3(choice.start)
        if posicion is None:
            fuera += 1
            continue
        x = _x(posicion, length)
        rank = selection.selection.rank_of(choice.start)
        parts.append(
            f'<line data-candidato="{coords.label(choice.start, marco)}" '
            f'x1="{x:.1f}" y1="{TRACK_Y + TRACK_H}" '
            f'x2="{x:.1f}" y2="{TRACK_Y + TRACK_H + 34}" stroke="#1b6cb0" '
            f'stroke-width="2"/>'
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{TRACK_Y + TRACK_H + 40}" r="9" fill="#1b6cb0">'
            f'<title>#{rank} {coords.span(choice.start, choice.end, marco)}, '
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
    nota_fuera = (
        f" · {fuera} elemento(s) FUERA del 3'UTR, no dibujados" if fuera else ""
    )
    parts.append(
        f'<text x="{MARGIN}" y="{HEIGHT - 8}" font-size="11" fill="#6b6357">'
        f"3'UTR de {length} nt (marco de lo tilado: {marco.value}) — ▲ señal poliA · "
        f"▬ repetición enmascarada · ▬ bloque conservado · ● candidato"
        f"{nota_fuera}</text>"
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


def vector_note(species: str) -> dict[str, object]:
    """¿Aplica el vector del proyecto a esta especie? La app lo DICE, no lo supone."""
    from .blocks import vector_applies_to

    aplicabilidad = vector_applies_to(species)
    return {
        "aplica": aplicabilidad.applies,
        "estado": aplicabilidad.state,
        "texto": aplicabilidad.note,
    }


def block_rows(
    selection: ReportSelection, scaffold: ScaffoldSpec, *, species: str = ""
) -> list[dict[str, object]]:
    """Una fila por bloque, con el estado de CADA comprobacion en su columna.

    Con una especie que NO es la del vector devuelve la lista VACIA: el modulo y el
    cassette se construyen con las 12 piezas del plasmido murino, y emitirlos para otra
    especie daria fragmentos con la forma correcta y la secuencia equivocada. Quien
    llama tiene que enseñar `vector_note(species)` al lado — que es donde se explica.
    """
    from .blocks import vector_applies_to

    if species and not vector_applies_to(species).applies:
        return []
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


#: Por que la estimacion EXIGE la anatomia.
#:
#: Estimaba sobre el 3'UTR (`whole_is_utr3`) y la corrida tilaba el transcrito entero
#: con su anatomia. Dos conjuntos, el mismo nombre, y en pantalla una aritmetica
#: imposible: «ventanas a tilar: 1221» arriba y «1773 ventana(s) no evaluable(s)»
#: abajo, sobre 2170 ventanas que la estimacion nunca vio. No puede haber mas
#: descartadas que totales, y el que estaba mal era el de arriba.
#:
#: Fabricarse una anatomia para estimar es la misma clase de suposicion que `resolve.py`
#: prohibe: si el que llama no la tiene, lo que hay que hacer es abortar, no inventar
#: un marco y contar otra cosa con el nombre de esta.
WHY_THE_ESTIMATE_NEEDS_ANATOMY = (
    "La estimación tiene que tilar EXACTAMENTE lo que va a tilar la corrida. Con una "
    "anatomía fabricada contaba el 3'UTR (1221 ventanas) mientras la corrida contaba el "
    "transcrito entero (2170), y las dos cifras salian juntas en pantalla como si "
    "hablaran del mismo conjunto."
)


def cost_text(
    sequence: str,
    *,
    anatomy: Anatomy,
    resources: ResourceSet | None = None,
    accessibility: bool = False,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    tile_range=None,
) -> str:
    """Cuanto va a costar esta corrida, sin lanzarla.

    Recibe LA MISMA secuencia y LA MISMA anatomia que la corrida. Ver
    `WHY_THE_ESTIMATE_NEEDS_ANATOMY`: aqui no se fabrica ningun marco.

    La mascara no se aplica al estimar: reduce las ventanas elegibles, asi que el
    numero sale POR ENCIMA del tiempo real. Se dice, no se deja implicito.
    """
    if anatomy is None:
        raise ShmirDesignError(
            "No hay anatomía con la que estimar, así que no se sabe QUE se va a tilar. "
            "Se aborta en vez de suponer que la secuencia entera es 3'UTR: con esa "
            "suposicion la estimación contaba 1221 ventanas y la corrida tilaba 2170, y "
            "las dos cifras salian en la misma pantalla. "
            + WHY_THE_ESTIMATE_NEEDS_ANATOMY
        )
    original = normalize_sequence(sequence, name="secuencia a tilar")
    campos = {}
    if resources is not None:
        completo = resources.as_kwargs()
        campos = {clave: completo[clave] for clave in COST_FIELDS}
    estimacion = estimate_cost(
        sequence=original,
        anatomy=anatomy,
        tile_range=tile_range,
        thresholds=thresholds,
        accessibility=accessibility,
        **campos,
    )
    lineas = [estimacion.format_text()]
    if resources is not None and resources.mask is not None:
        lineas.append(
            "  Hay una máscara de repeticiones cargada y la estimación NO la aplica: "
            "enmascarar deja"
        )
        lineas.append(
            "  menos ventanas elegibles, así que el total de arriba es un techo, no "
            "una predicción."
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
    "Guía y pasajera son DOS CONSULTAS distintas y las dos hacen falta: la pasajera "
    "también se carga en AGO2 en alguna fracción, así que sus off-targets son reales. "
    "Se marcan por separado a propósito."
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
            "No se ha marcado ni guía ni pasajera: no hay nada que consultar. Son dos "
            "preguntas distintas y hace falta al menos una. Se aborta."
        )
    pedidos = list(dict.fromkeys(int(s) for s in starts))
    if not pedidos:
        raise ShmirDesignError(
            "No se ha marcado ningún candidato: no se genera un FASTA vacío. Se aborta."
        )
    por_inicio = {c.start: c for c in selection.selection.chosen}
    fuera = [s for s in pedidos if s not in por_inicio]
    if fuera:
        raise ShmirDesignError(
            f"Estos sitios no están en el panel de esta corrida: "
            f"{', '.join(str(s) for s in fuera)}. Se aborta en vez de consultar una "
            f"guía que no existe aquí."
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


def blast_defaults_for(species: str):
    """Los parametros de partida del modal, con el organismo de ESTA especie.

    Se PREGUNTA por el taxid en vez de capturar el abort: una especie sin taxid
    declarado devuelve el campo vacio, y entonces `blast_warnings` saca un aviso que
    BLOQUEA. Asi el hueco se ve en la interfaz en vez de reventar la pagina — y sigue
    siendo imposible que salga una orden con el taxid de otra especie.
    """
    from .blast import BlastParams
    from .species import resolve

    return BlastParams(entrez_query=resolve(species).taxid)


def blast_setting_rows(params) -> list[dict[str, object]]:
    """Una fila por ajuste, con `modificado` para que la pagina lo pinte en rojo.

    La pagina NO decide cual va en rojo: recibe el booleano. Es la misma leccion del
    `.out` sin especie — un veredicto con ajustes cambiados no puede ser indistinguible
    de uno estandar, y para eso hay que verlo.
    """
    from .blast import BlastParams

    # La referencia de «por defecto» lleva el MISMO organismo: el taxid no es un ajuste
    # que alguien haya tocado, es la identidad de la corrida.
    base = BlastParams(entrez_query=params.entrez_query)
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
            "por_defecto": _fmt(getattr(base, campo)),
            "modificado": campo in tocados,
        }
        for campo in _SETTING_FIELDS
    ]


def blast_warnings(params) -> list[dict[str, object]]:
    """Los avisos del modal. `bloquea` = esta corrida no puede cerrar el frente."""
    from .seed_load import WHY_NOT_BLAST

    avisos = []
    if not params.entrez_query:
        avisos.append({
            "bloquea": True,
            "texto": (
                "SIN ORGANISMO DECLARADO: esta especie no tiene taxid en "
                "`species.SPECIES`, así que la orden no se puede generar. No se pone "
                "uno por defecto — un `txid10090` sobre una secuencia que no es de "
                "raton devuelve los aciertos de OTRO organismo, y el resultado tiene la "
                "forma correcta. Se mira en el Taxonomy Browser del NCBI y se declara."
            ),
        })
    if not params.can_give_verdict:
        avisos.append({"bloquea": True, "texto": params.why_no_verdict})
    # Este sale SIEMPRE, con o sin ajustes tocados: no bloquea ESTE modal, pero deja
    # claro que un PASS aqui no cubre el otro frente.
    avisos.append(
        {
            "bloquea": False,
            "texto": (
                "Este modal es para COMPLEMENTARIEDAD EXTENSA. El off-target mediado por "
                f"seed es OTRO frente (`offtarget_seed`) y no se busca aquí. "
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
            f"No se pudo leer un ajuste numérico del modal ({exc}); se aborta en vez de "
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
            "nucleo": f.core,
            # Columna PROPIA: compartir nucleo sin compartir heptamero es otro eje, y
            # meterlo en «comparte» lo habria escondido debajo de la colision de seed.
            "comparte_nucleo": ", ".join(
                f"3utr:{s}" for s in f.shared_core_with
            ),
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
            "NOT_RUN: no hay `mature.fa` cargado, así que no hay contra que comparar. "
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
                    "Colisión con la familia miR-30 en: "
                    + ", ".join(f"3utr:{r.start} ({r.strand})" for r in con_mir30)
                    + ". " if con_mir30 else "Sin colisiones con la familia miR-30. "
                )
                + MIR30_NOTE
            ),
        },
        "pasajeras": {
            "activo": bool(pasajeras),
            "texto": (
                f"{len(pasajeras)} consulta(s) de PASAJERA, separadas de las de guía y "
                f"NUNCA sumadas en un veredicto único: la pasajera se carga a RISC en "
                f"alguna proporción, así que sus off-targets son igual de reales — pero "
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
            f"({utr3_set.provenance}). Sigue siendo un número comparativo, nunca un "
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
                f"NOT_RUN no es PASS, y sobre todo NO ES CERO: no haber contado cuántos "
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


def offtarget_route_text(species) -> str:
    """La ruta de descarga de UCSC para ESTA especie. La especie es obligatoria.

    Sin ella el texto salia con `mm39` escrito dentro, o sea con el ensamblaje del
    raton para cualquiera que abriera el modal — una instruccion correcta de principio
    a fin y del organismo equivocado.
    """
    from .offtarget import ucsc_route

    return ucsc_route(species)


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


# ─────────────────── el informe como documento: parcial o completo ────────────────


def informe_documento(selection, tiling, *, species: str, generated: str,
                      anatomy_source: str = "no declarada en esta corrida",
                      dossier_starts=None):
    """El documento entero. Parcial o completo segun los frentes, nunca dos productos."""
    from .informe_doc import build_document

    return build_document(
        species=species, tiling=tiling, selection=selection, generated=generated,
        anatomy_source=anatomy_source, dossier_starts=dossier_starts,
    )


def informe_files(documento, *, stem: str):
    """Los tres entregables, ya con nombre: markdown (fuente), `.docx` y `.pdf`.

    La pagina no decide el nombre ni el formato: recibe `nombre`, `datos` y `mime`. El
    markdown va tambien porque es la FUENTE de los otros dos — si alguien discute una
    frase del pdf, ahi esta el texto sin maquetar.
    """
    from .docx_writer import to_docx
    from .pdf_writer import to_pdf

    marca = "parcial" if documento.state == "PARCIAL" else "completo"
    base = f"{stem}_informe_{marca}"
    return [
        {
            "nombre": f"{base}.md",
            "datos": documento.markdown().encode("utf-8"),
            "mime": "text/markdown",
        },
        {
            "nombre": f"{base}.docx",
            "datos": to_docx(documento),
            "mime": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        },
        {
            "nombre": f"{base}.pdf",
            "datos": to_pdf(documento),
            "mime": "application/pdf",
        },
    ]


def informe_state_text(documento) -> str:
    """Que significa el estado, para pintarlo junto al boton."""
    from .informe_doc import WHAT_COMPLETE_MEANS, WHAT_PARTIAL_MEANS

    if documento.state == "PARCIAL":
        return (
            f"{WHAT_PARTIAL_MEANS} Frentes abiertos: "
            f"{', '.join(documento.open_fronts)}."
        )
    return WHAT_COMPLETE_MEANS


# ───────────────── fiabilidad de la frontera del 3'UTR: `.gb` o NO_FIABLE ──────────
#
# La entrada preferente es el `.gb`. Un FASTA con el CDS tecleado se acepta —hay que
# poder trabajar— pero entonces TODO lo que cuelga de donde empieza el 3'UTR queda
# NO_FIABLE, y eso se ve. Sin frontera fiable, «tercio medio» no significa nada: no es
# un matiz, es que la etiqueta no se refiere a nada.

#: Las procedencias de anatomia en las que la frontera la declara una ANOTACION, no una
#: persona. Son las dos unicas que hacen fiables los tercios y las zonas de polyA.
RELIABLE_SOURCES = ("anotacion_genbank", "fixture_verificado")

#: Que deja de ser fiable sin `.gb`. Va nombrado uno a uno: «algunas cosas» no sirve.
UNRELIABLE_OUTPUTS = (
    "tercios (proximal / medio / distal)",
    "la etiqueta de región de cada ventana",
    "las cuotas por tercio de la selección",
    "la distancia de cada señal de polyA al extremo 3'",
    "que señales cuentan como TERMINALES",
)


def anatomy_reliability(anatomy) -> dict[str, object]:
    """¿La frontera del 3'UTR viene de una ANOTACION o la declaro alguien?

    No es lo mismo y la salida no puede tratarlo igual. Con `.gb` (o con un fixture
    verificado por md5) la frontera la dice la anotacion; con el CDS tecleado o con «lo
    que subo YA es el 3'UTR», la dice quien lo teclea — y un off-by-one ahi corre el
    3'UTR entero y con el todos los tercios, sin dar ningun error.
    """
    from .filters import FilterState

    if anatomy is None:
        return {
            "fiable": False,
            "estado": FilterState.NOT_RUN,
            "procedencia": "sin resolver",
            "afectados": list(UNRELIABLE_OUTPUTS),
            "texto": (
                "SIN ANATOMÍA RESUELTA: no hay frontera de 3'UTR, así que no se puede "
                "tilar nada. Sube el `.gb`, declara el CDS o marca que lo subido YA es "
                "el 3'UTR."
            ),
        }
    procedencia = getattr(anatomy.source, "value", str(anatomy.source))
    if procedencia in RELIABLE_SOURCES:
        return {
            "fiable": True,
            "estado": FilterState.PASS,
            "procedencia": procedencia,
            "afectados": [],
            "texto": (
                f"Frontera del 3'UTR tomada de {anatomy.source.describe()}. Los tercios "
                f"y las zonas de polyA se apoyan en una ANOTACIÓN, no en una "
                f"declaracion."
            ),
        }
    return {
        "fiable": False,
        "estado": FilterState.NOT_RUN,
        "procedencia": procedencia,
        "afectados": list(UNRELIABLE_OUTPUTS),
        "texto": (
            f"NO_FIABLE: la frontera del 3'UTR sale de {anatomy.source.describe()}, o "
            f"sea de una DECLARACIÓN y no de una anotación. Se acepta —hay que poder "
            f"trabajar— pero lo que cuelga de esa frontera queda NO_FIABLE: "
            + "; ".join(UNRELIABLE_OUTPUTS)
            + ". Un off-by-one ahi corre el 3'UTR entero y con el todos los tercios, "
            "sin dar ningún error. Con el `.gb` del RefSeq lo declara la anotación y "
            "esto desaparece."
        ),
    }


# ─────────────── la tabla de sitios: UNA COLUMNA POR FRENTE, y todos ──────────────
#
# Es la vista que impide que vuelva a pasar lo de `offtarget_seed`. Un frente que no
# tiene columna no se ve, y lo que no se ve no existe: `carga_seed` era un numero y no
# un veredicto, asi que nunca estuvo en `not_run_filters` y el frente entero fue
# invisible durante semanas. Aqui la lista de columnas se DERIVA de los frentes que el
# informe conoce, asi que un frente nuevo aparece solo.

#: Cuanto espaciado hace falta entre dos SELECCIONADOS para que sean dos apuestas.
#: Sale de la configuracion de la seleccion, no se teclea aqui.
MIN_SPACING_WARNING = (
    "Dos candidatos a menos del espaciado mínimo NO son dos apuestas independientes: "
    "las causas de fallo son REGIONALES —un APA, un repetitivo, un tramo estructurado "
    "afectan a una región entera— así que fallan juntos."
)


def front_columns(tiling, selection) -> list[str]:
    """Los frentes que van a ser columna. Se DERIVAN, no se listan a mano."""
    from .selection import blocking_fronts

    nombres = [f.name for f in blocking_fronts(tiling, selection)]
    # `seed_colision` y `offtarget_seed` son por HEBRA en la ficha, pero en la tabla de
    # sitios la fila es el sitio: aqui va el estado del filtro de la ventana, que es lo
    # que la tabla puede decir. La ficha sigue siendo quien parte las dos hebras.
    return sorted(dict.fromkeys(nombres))


def site_table_rows(tiling, selection, *, species: str = "",
                    selected=None) -> list[dict[str, object]]:
    """TODOS los sitios elegibles, con UNA COLUMNA POR FRENTE.

    No solo los elegidos: la piscina entera. Un candidato que no esta en el panel sigue
    siendo un sitio con veredictos, y esconderlo deja al lector sin poder discutir la
    seleccion.

    `selected` son los inicios marcados a mano; si es `None`, se marcan los del panel.
    """
    from .selection import is_eligible

    columnas = front_columns(tiling, selection)
    elegidos = (
        {c.start for c in selection.selection.chosen} if selected is None
        else {int(s) for s in selected}
    )
    fiable = anatomy_reliability(tiling.anatomy)["fiable"]
    por_inicio = {c.start: c for c in selection.selection.chosen}

    filas = []
    for ventana in tiling.windows:
        if not is_eligible(ventana):
            continue
        estados = {r.name: r.state.value for r in ventana.filters}
        elegido = por_inicio.get(ventana.window.start)
        filas.append(
            {
                "elegido": ventana.window.start in elegidos,
                "sitio": f"3utr:{ventana.inicio_3utr}",
                "inicio": ventana.window.start,
                # Sin frontera fiable, «tercio medio» no se refiere a nada. No se
                # imprime un valor que parece un dato: se imprime que no es fiable.
                "tercio": (
                    (ventana.tercio.value if ventana.tercio else "—") if fiable
                    else "NO_FIABLE"
                ),
                "asimetria": (
                    None if ventana.evaluation.asymmetry is None
                    else round(ventana.evaluation.asymmetry, 2)
                ),
                "rango": (
                    selection.selection.rank_of(ventana.window.start)
                    if elegido is not None else ""
                ),
                **{
                    nombre: estados.get(nombre, "NOT_RUN") for nombre in columnas
                },
                "veredicto": ventana.verdict.value,
                "guia": ventana.evaluation.guide,
            }
        )
    return filas


def selection_warnings(tiling, selection, *, selected=None,
                       min_spacing: int | None = None) -> list[dict[str, object]]:
    """Los avisos de la seleccion a mano, con `rojo` ya decidido fuera de la pagina.

    Dos ejes distintos y ninguno cubre al otro: la DISTANCIA en el 3'UTR (espaciado) y
    el PARECIDO de seed (nucleo compartido). El espaciado no ve el segundo — mide
    nucleotidos, no seeds — y por eso los dos avisos van separados.
    """
    from .offtarget import MULTIPLEX_NOTE, core_conflicts

    marcados = sorted(
        {c.start for c in selection.selection.chosen} if selected is None
        else {int(s) for s in selected}
    )
    espaciado = (
        min_spacing if min_spacing is not None
        else getattr(selection.selection, "min_spacing", 50)
    )
    avisos: list[dict[str, object]] = []
    for i, uno in enumerate(marcados):
        for otro in marcados[i + 1 :]:
            if abs(otro - uno) < espaciado:
                avisos.append({
                    "rojo": True,
                    "texto": (
                        f"3utr:{uno} y 3utr:{otro} están a {abs(otro - uno)} nt, por "
                        f"debajo del espaciado mínimo de {espaciado} nt. "
                        f"{MIN_SPACING_WARNING}"
                    ),
                })
    for conflicto in core_conflicts(selection):
        if conflicto.a in marcados and conflicto.b in marcados:
            avisos.append({
                "rojo": True,
                "texto": (
                    conflicto.describe(
                        label_a=f"3utr:{conflicto.a}", label_b=f"3utr:{conflicto.b}"
                    )
                    + " " + MULTIPLEX_NOTE
                ),
            })
    return avisos


# ═══════════ los cuatro pasos: especie, secuencia, ficheros, diseñar ═══════════
#
# Lo que esto arregla: la pagina pedia la especie en una CAJA DE TEXTO LIBRE con
# «modelo» de valor inicial, unos ficheros se subian y otros habia que depositar a mano
# en un directorio del repositorio, y una casilla global decidia si se usaban. Las tres
# cosas juntas hacian falsa la promesa de la app: que alguien que no ha estado en estas
# conversaciones pueda abrirla y llegar a un informe sin abrir una terminal.

#: El valor del desplegable que significa «una especie que no esta declarada».
OTHER_SPECIES = "otra especie (no declarada)"

#: Por que no hay casilla global de «usar los ficheros de referencia». Se reexporta
#: desde `deposito` para que la pagina no tenga que importar dos modulos del nucleo.
from .deposito import WHY_NO_GLOBAL_TOGGLE  # noqa: E402

#: Como se declara una especie. Va en la interfaz porque es la unica salida real.
HOW_TO_DECLARE = (
    "Se añade una línea a `species.SPECIES` (en `shmir_design/species.py`) con sus "
    "identificadores VERIFICADOS: `mirbase_prefix` (el de tres letras que miRBase pone "
    "delante de cada maduro), `taxid` (el de NCBI Taxonomy Browser) y `ucsc_assembly` "
    "(el ensamblaje del Genome Browser). Ninguno de los tres se deduce del nombre: para "
    "Oryctolagus cuniculus, «ocu-», «oc-» y «ory-» son los tres plausibles y solo uno "
    "existe — filtrar con el equivocado da CERO colisiones, que parece una buena noticia."
)


def species_options() -> list[dict[str, object]]:
    """Las opciones del desplegable. Salen de `species.SPECIES` y de ningun otro sitio.

    Con su nombre cientifico completo: «raton» es un alias del proyecto y no identifica
    nada fuera de el. Y con una opcion EXPLICITA para lo que no esta declarado, porque
    esconderla no hace que el caso desaparezca — hace que llegue sin aviso.
    """
    from .species import SPECIES

    filas = []
    for especie in sorted(SPECIES.values(), key=lambda e: e.scientific):
        filas.append(
            {
                "valor": especie.scientific,
                "cientifico": especie.scientific,
                "etiqueta": f"{especie.scientific} ({especie.slug})",
                "declarada": True,
                "prefijo": especie.mirbase_prefix,
                "taxid": especie.taxid,
                "ensamblaje": especie.ucsc_assembly,
            }
        )
    filas.append(
        {
            "valor": OTHER_SPECIES,
            "cientifico": "",
            "etiqueta": OTHER_SPECIES,
            "declarada": False,
            "prefijo": "",
            "taxid": "",
            "ensamblaje": "",
        }
    )
    return filas


def species_default() -> None:
    """No hay valor por defecto: hay que elegir.

    `modelo` como valor inicial era PEOR que vacio. Parecia configurado, y con el la
    colision de seed y la especificidad salian rotas —sin prefijo de miRBase y sin
    taxid— sin que la pagina dijera por que.
    """
    return None


def species_needs_name(choice: str) -> bool:
    """¿Hay que teclear un nombre? Solo al elegir «otra especie»."""
    return str(choice).strip() == OTHER_SPECIES


def species_choice_note(choice: str) -> dict[str, object]:
    """Que frentes quedan cerrados con esta eleccion, y como se declara la especie."""
    from .species import fixture_report, resolve

    nombre = str(choice).strip()
    if not nombre or nombre == OTHER_SPECIES:
        if not nombre:
            raise ShmirDesignError(
                "No hay especie elegida. Sin ella no se sabe que ficheros hacen falta ni "
                "se puede comprobar que los que hay son de esta especie, así que se "
                "aborta en vez de suponer raton — que es lo que este proyecto lleva "
                "dentro por historia."
            )
        # «Otra especie» sin nombre todavia: se responde por el caso general, que es una
        # especie sin identificadores declarados.
        especie = resolve("Oryctolagus cuniculus")
        generico = True
    else:
        especie = resolve(nombre)
        generico = False

    informe = fixture_report(especie, have=())
    cerrados = [
        f"{f.front}: falta {f.missing}"
        for f in informe.rows
        if not f.available and (not especie.known or not f.available)
    ]
    if especie.known:
        cerrados = []
    return {
        "especie": especie.scientific if not generico else "",
        "declarada": especie.known,
        "bloquea": not especie.known,
        "cerrados": cerrados,
        "como_declararla": HOW_TO_DECLARE,
        "texto": (
            f"{especie.scientific} está declarada: prefijo de miRBase "
            f"«{especie.mirbase_prefix}», taxid {especie.taxid}, ensamblaje "
            f"{especie.ucsc_assembly}."
            if especie.known
            else (
                "Esta especie NO está declarada en el proyecto, así que se queda sin "
                "prefijo de miRBase, sin taxid y sin ensamblaje. Los frentes que "
                "dependen de esos tres valores ABORTAN en vez de correr con los del "
                "raton: un resultado con la forma correcta y la especie equivocada es "
                "peor que ninguno."
            )
        ),
    }


# ─────────────── el panel de ficheros de referencia de la barra lateral ───────────────


# ── El gestor de ficheros de referencia ──────────────────────────────────────────
#
# La pagina no importa `gestor.py`: pasa por aqui. Si lo importara acabaria decidiendo
# que botones pinta y que invalida que, y eso es la regla 6.


def reference_manager_rows(species: str, *, directory) -> list[dict]:
    """Las filas del gestor, con la marca y el resumen YA montados."""
    from .gestor import manager_rows  # noqa: PLC0415

    filas = []
    for fila in manager_rows(species, directory=directory):
        presente = fila["estado"] == "presente"
        marca = "✅" if presente else ("⬜" if fila["obligatorio"] else "▫️")
        if presente:
            trozos = [f"{fila['bytes']} bytes", f"md5 {fila['md5'][:8]}"]
            if fila["fecha"]:
                trozos.append(fila["fecha"])
            if fila["origen"]:
                trozos.append(fila["origen"])
            resumen = " · ".join(trozos)
        else:
            resumen = (
                f"FALTA{'' if fila['obligatorio'] else ' (opcional)'} — "
                f"{fila['que_desbloquea']}"
            )
        filas.append({**fila, "especie": species, "marca": marca, "resumen": resumen})
    return filas


def reference_preview(name: str, *, directory, lines: int = 10) -> dict:
    """La vista de las primeras lineas, con su cabecera ya escrita."""
    from .gestor import preview  # noqa: PLC0415

    vista = preview(name, directory=directory, lines=lines)
    if not vista.is_text:
        cabecera = f"{name}: binario"
    elif vista.truncated:
        cabecera = (
            f"{name}: primeras {vista.shown} de {vista.total_lines} líneas"
        )
    else:
        cabecera = f"{name}: {vista.total_lines} línea(s), entero"
    return {"cabecera": cabecera, "texto": vista.text, "es_texto": vista.is_text}


def reference_download(name: str, *, directory) -> bytes:
    """Los bytes tal como se subieron. Ver `gestor.WHY_DOWNLOAD`."""
    from .gestor import download  # noqa: PLC0415

    return download(name, directory=directory)


def reference_replace_plan(name: str, *, directory, payload: bytes, species=None) -> dict:
    """Que cambia y que deja de valer, ANTES de confirmar."""
    from .gestor import plan_replace  # noqa: PLC0415

    plan = plan_replace(
        name, directory=directory, payload=payload, species=species
    )
    return {
        "texto": plan.describe(),
        "invalida": list(plan.invalidates),
        "mismo": plan.same_file,
        "md5_viejo": plan.old_md5,
        "md5_nuevo": plan.new_md5,
    }


def reference_delete_plan(name: str, *, directory, species=None) -> dict:
    """Que frente vuelve a NOT_RUN. NO borra."""
    from .gestor import plan_delete  # noqa: PLC0415

    plan = plan_delete(name, directory=directory, species=species)
    return {"texto": plan.describe(), "frentes": list(plan.fronts)}


def reference_delete(name: str, *, directory) -> str:
    """Borra y devuelve el texto de lo que se fue, con su md5."""
    from .gestor import delete  # noqa: PLC0415

    return f"Borrado {name} (md5 {delete(name, directory=directory)})."


def reference_panel_rows(species: str, *, directory) -> list[dict[str, object]]:
    """Una fila por FICHERO que esta especie necesita: cual es, si esta, y su ficha.

    Se detecta solo lo que ya haya en el directorio —depositarlo ahi sigue funcionando—
    pero deja de ser necesario: cada fila trae su boton de subida.
    """
    from pathlib import Path

    from .species import required_files, resolve

    from .presencia import ficheros_con_contenido

    ruta = Path(directory)
    # No `is_file()`: un fichero de 0 bytes existe y no tiene nada dentro. Errata nº 15.
    presentes = ficheros_con_contenido(ruta)
    especie = resolve(species)

    filas: list[dict[str, object]] = []
    for fila in required_files(especie):
        ficha = obtencion_rows(fila.ficha, species=species)
        for nombre in fila.filenames:
            filas.append(
                {
                    "nombre": nombre,
                    "role": fila.role,
                    "que_desbloquea": fila.what,
                    "frentes": list(fila.fronts),
                    "presente": nombre in presentes,
                    "obligatorio": fila.required,
                    "hermano": nombre != fila.filename,
                    "extensiones": list(fila.extensions),
                    "ficha": ficha,
                }
            )
    return filas


#: Dos recuentos, dos nombres. En la misma pantalla salian «2 de 7 frentes» arriba y
#: «8 de 12 filtros» abajo, los dos llamados por su numero pelado, y no hay forma de
#: saber si son la misma cuenta mal hecha o dos cuentas distintas. Son dos:
#:
#:   - los 7 son los frentes que cierra un FICHERO de referencia. Se cuentan antes de
#:     correr nada y dicen si merece la pena ir a buscar algo;
#:   - los 12 son los filtros que se le corren a UN candidato, y cinco de ellos
#:     —GC, homopolimero, los dos G4 y la asimetria— son biofisicos: no necesitan
#:     ningun fichero, corren siempre y por eso nunca aparecen entre los 7.
FRONT_COUNT_NAME = "frentes que cierra un fichero de referencia"
FILTER_COUNT_NAME = "filtros por candidato"
FRONTS_VS_FILTERS = (
    f"Son dos cuentas distintas: los {FRONT_COUNT_NAME} se cuentan por FICHERO y antes "
    f"de correr nada; los {FILTER_COUNT_NAME} se cuentan sobre UN candidato ya evaluado "
    f"e incluyen los biofísicos (GC, homopolimero, G4 de diana y de guía, asimetría), "
    f"que no necesitan fichero ninguno y corren siempre. Por eso el segundo número es "
    f"mayor y por eso no cuadran entre si: no cuentan lo mismo."
)


def reference_panel_summary(species: str, *, directory) -> dict[str, object]:
    """Cuantos frentes se pueden cerrar con lo que hay, ANTES de ejecutar nada.

    Se cuentan FRENTES, no ficheros: es lo que el usuario decide —seguir, o ir a buscar
    un fichero primero— y un fichero que cierra dos frentes no vale lo mismo que uno que
    no cierra ninguno.
    """
    from pathlib import Path

    from .species import fixture_report, resolve

    from .presencia import ficheros_con_contenido

    ruta = Path(directory)
    presentes = tuple(sorted(ficheros_con_contenido(ruta)))
    informe = fixture_report(resolve(species), have=presentes)
    faltan = [f for f in informe.rows if not f.available]
    return {
        "cerrables": informe.closable,
        "total": len(informe.rows),
        "abiertos": [{"frente": f.front, "falta": f.missing} for f in faltan],
        "texto": informe.render(),
    }


def accept_reference_upload(
    species: str, *, directory, filename: str, payload: bytes, date: str,
    origin: str = "subido por la interfaz", **procedencia,
) -> dict[str, object]:
    """Recibe un fichero por la barra lateral. La pagina no valida, no calcula md5 y no
    escribe el manifiesto: llama aqui y pinta lo que vuelva."""
    from .deposito import accept_upload
    from .species import resolve

    resultado = accept_upload(
        directory,
        filename=filename,
        payload=payload,
        species=resolve(species),
        origin=origin,
        date=date,
        **procedencia,
    )
    return {
        "nombre": resultado.filename,
        "role": resultado.role,
        "md5": resultado.md5,
        "tamano": resultado.size,
        "frentes_cerrados": list(resultado.fronts_opened),
        "sigue_faltando": list(resultado.still_missing),
        "sustituida": resultado.replaced,
        "texto": resultado.render(),
    }


# ───────────────────────── la primera pantalla, en cuatro pasos ─────────────────────────


def steps_rows(*, species: str, sequence_loaded: bool, directory) -> list[dict[str, object]]:
    """Los cuatro pasos, en orden, con lo que falta en cada uno.

    El paso 3 dice cuantos frentes se van a poder cerrar ANTES de ejecutar nada: es lo
    que permite decidir si se sigue o se va a buscar un fichero primero. Y NO bloquea —
    un frente abierto deja los candidatos en INCOMPLETE, que es informacion, no un veto.
    """
    elegida = bool(str(species).strip()) and str(species).strip() != OTHER_SPECIES
    resumen = (
        reference_panel_summary(species, directory=directory) if elegida else None
    )
    return [
        {
            "numero": 1,
            "titulo": "Especie",
            "hecho": elegida,
            "abierto": not elegida,
            "cerrables": None,
            "total_frentes": None,
            "detalle": (
                species_choice_note(species)["texto"]
                if elegida
                else (
                    "Elige una de las especies declaradas. No hay valor por defecto a "
                    "propósito: uno preseleccionado parece configurado y deja dos frentes "
                    "rotos sin decir por que."
                )
            ),
        },
        {
            "numero": 2,
            "titulo": "Secuencia",
            "hecho": bool(sequence_loaded),
            "abierto": elegida and not sequence_loaded,
            "cerrables": None,
            "total_frentes": None,
            "detalle": (
                "El mRNA en FASTA, y con el su `.gb` si lo tienes: la anotación del CDS "
                "es la via fiable de resolver la anatomía. Sin ella, los tercios y las "
                "zonas de polyA salen NO_FIABLE."
            ),
        },
        {
            "numero": 3,
            "titulo": "Ficheros de referencia",
            "hecho": bool(resumen and not resumen["abiertos"]),
            "abierto": elegida,
            "cerrables": resumen["cerrables"] if resumen else None,
            "total_frentes": resumen["total"] if resumen else None,
            "detalle": (
                f"Con lo que hay se pueden cerrar {resumen['cerrables']} de "
                f"{resumen['total']} {FRONT_COUNT_NAME}. Los demas quedan en NOT_RUN, "
                f"VISIBLE en la tabla de candidatos. Sube lo que falte en el panel de la "
                f"barra lateral: cada fichero trae la ficha que dice de donde sale. "
                f"{FRONTS_VS_FILTERS}"
                if resumen
                else "Elige la especie primero: los ficheros que hacen falta dependen de ella."
            ),
        },
        {
            "numero": 4,
            "titulo": "Diseñar",
            "hecho": False,
            "abierto": elegida and bool(sequence_loaded),
            "cerrables": None,
            "total_frentes": None,
            "detalle": (
                "Se puede diseñar con frentes abiertos: los candidatos saldran "
                "INCOMPLETE y cada frente sin correr sale NOT_RUN en su columna. NOT_RUN "
                "no es PASS, y no haber contado no es contar cero."
            ),
        },
    ]


# ═══════════════ el CUARTO modal: prediccion de sitios de splicing ═══════════════
#
# La pagina no decide nada aqui tampoco. Recibe filas, textos y booleanos.
#
# Y una diferencia con los otros tres que la pagina TIENE que pintar antes del boton:
# SpliceAI no fue entrenado para esto, asi que sus puntuaciones absolutas no son
# interpretables y lo unico que vale es la comparacion relativa contra el legitimo del
# mismo intron. Eso va ARRIBA, no al pie.


def splice_warning_rows():
    """Los avisos que van ANTES del boton. Todos activos: ninguno es opcional."""
    from .spliceai import warning_blocks

    return warning_blocks()


def variant_proposal_text(guide: str, *, available=None) -> str:
    """La propuesta de `mvm_sin_criptico` para ESTA guía, o por qué no la hay.

    Va en el modal de empalme, junto a la lista de intrones, porque es donde se decide
    con qué intrón se consulta: un intrón que la app propone y que nadie ve es un intrón
    que no existe. Las dos decisiones son estructurales, así que hay una propuesta POR
    CANDIDATO y no una «del proyecto».
    """
    from .intron_design import design_variant  # noqa: PLC0415
    from .scaffold import SGEP_SCAFFOLD  # noqa: PLC0415

    if not str(guide).strip():
        return (
            "Sin guía no hay 97-mero y las dos decisiones de la variante son "
            "estructurales: no se propone nada."
        )
    try:
        return design_variant(
            guide=guide, scaffold=SGEP_SCAFFOLD, available=available
        ).describe_text()
    except ShmirDesignError as exc:
        # rule2-ok: frontera de presentacion. El motivo entero se enseña.
        return f"NO se pudo diseñar la variante — {exc}"


def reference_md5s(directory) -> dict[str, str]:
    """Fichero → md5 de lo que HAY hoy en el directorio de referencia.

    Se calcula del fichero, nunca se declara: es la misma regla del depósito. Un fichero
    vacío no entra —`presencia.hay_fichero`—, así que un `touch` no puede hacer que una
    corrida parezca obsoleta contra la nada.
    """
    import hashlib  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from .presencia import ficheros_con_contenido  # noqa: PLC0415

    raiz = Path(directory)
    salida = {}
    for nombre in sorted(ficheros_con_contenido(raiz)):
        salida[nombre] = hashlib.md5(
            (raiz / nombre).read_bytes(), usedforsecurity=False
        ).hexdigest()
    return salida


def run_freshness(kind: str, payload, *, actuales: dict[str, str]) -> dict[str, object]:
    """¿Sigue valiendo esta corrida? PASS / OBSOLETO / NOT_RUN, DERIVADO de los md5.

    La tabla de `insumos.CONSUMIDOS` dice qué consume cada tipo de corrida y dónde vive
    el md5 de cada insumo dentro del registro; aquí sólo se traduce el resultado a un
    estado. Los tres casos, y ninguno sobra: los ficheros son los mismos (PASS), alguno
    cambió (OBSOLETO), o no se ha podido comprobar (NOT_RUN) — que no es que coincida.
    """
    from .filters import FilterState  # noqa: PLC0415
    from .insumos import obsoleta  # noqa: PLC0415

    motivos = list(obsoleta(kind, payload, actuales=actuales))
    if not motivos:
        return {"estado": FilterState.PASS, "motivos": []}
    if all("no se ha podido comprobar" in m for m in motivos):
        return {"estado": FilterState.NOT_RUN, "motivos": motivos}
    return {"estado": FilterState.OBSOLETO, "motivos": motivos}


def obsolete_rows(store, *, directory) -> list[dict[str, object]]:
    """Una fila por corrida guardada, con su frescura. Es lo que pinta la página.

    Existe para que `insumos.obsoleta` no se quede como `store.save_*`: escrita, probada
    y sin llegar nunca a una pantalla. La comprobación que corre y no se ve es media
    comprobación.
    """
    from .insumos import CONSUMIDOS, md5s_de_corrida  # noqa: PLC0415

    hoy = reference_md5s(directory)
    filas = []
    for registro in store.records():
        if registro.kind not in CONSUMIDOS:
            continue
        frescura = run_freshness(registro.kind, registro.payload, actuales=hoy)
        filas.append(
            {
                "tipo": registro.kind,
                "fecha": registro.date,
                "estado": frescura["estado"],
                "motivos": frescura["motivos"],
                "insumos": md5s_de_corrida(registro.kind, registro.payload),
            }
        )
    return filas


def project_banner(store) -> dict[str, object]:
    """Lo que la barra lateral enseña de un proyecto abierto, ya resuelto.

    La página leía `almacen.project.slug`, `.reliable` y `.why_unreliable` — tres
    cadenas de atributos y tres suposiciones sin test. Corolario de la errata nº 17.
    """
    proyecto = store.project
    return {
        "titulo": f"Proyecto **{proyecto.slug}** — {len(store.records())} registro(s)",
        "fiable": bool(proyecto.reliable),
        "aviso": "" if proyecto.reliable else proyecto.why_unreliable,
    }


def anatomy_source_label(anatomy) -> str:
    """Cómo se resolvió la anatomía, en una palabra, para el informe.

    Antes era `anat.source.value if hasattr(anat, "source") else str(anat)` EN LA
    PÁGINA: una navegación y un `hasattr` de rescate, o sea dos suposiciones.
    """
    fuente = getattr(anatomy, "source", None)
    return getattr(fuente, "value", None) or str(anatomy)


def chosen_starts(selection) -> list[int]:
    """Los inicios de los candidatos elegidos, en el orden en que los eligió la app.

    Existe para que la página deje de escribir `[c.start for c in
    selection.selection.chosen]`, que estaba copiado en tres modales y en el botón de
    guardar. Cada una de esas copias es una suposición sobre la forma del modelo que
    ningún test comprueba — el corolario de la errata nº 17 — y las cuatro tendrían que
    cambiar a la vez el día que `Choice` cambie.

    OJO con el nombre: `selected_starts` es OTRA cosa y ya existía — lee del ALMACÉN la
    última selección guardada. Ésta lee la selección VIVA de esta corrida. Se llaman
    distinto porque son distintas, y confundirlas daría el panel de ayer.
    """
    return [c.start for c in selection.selection.chosen]


def has_selection(selection) -> bool:
    """¿Hay algún candidato elegido? Misma razón que arriba."""
    return bool(selection.selection.chosen)


def variant_proposal_for(selection, *, available=None) -> str:
    """La propuesta de variante para el PRIMER candidato elegido de esta selección.

    La página pedía el texto leyendo `guide` del primer elegido, y `Choice` no tiene
    ese campo: la guía se alcanza por `window_of(choice).evaluation.guide`, como hace
    `block_bundle`. Eran dos fallos en uno —un `AttributeError` en cuanto alguien
    abriera el modal, y una página NAVEGANDO el modelo, que es lo que la regla 6
    prohíbe—, y el segundo es el que produjo el primero. La navegación vive aquí.
    """
    elegidos = selection.selection.chosen
    if not elegidos:
        return variant_proposal_text("", available=available)
    guia = selection.window_of(elegidos[0]).evaluation.guide.replace("U", "T")
    return variant_proposal_text(guia, available=available)


def splice_intron_rows(names=None):
    """Estado de cada intron del registro. Los que faltan salen VISIBLES."""
    from .introns import INTRONS
    from .spliceai import intron_report

    return intron_report(names if names is not None else tuple(INTRONS))


def intron_geometry_rows(names=None, *, module_length: int = 149):
    """Por intrón: el desglose pieza a pieza y dónde cabe el módulo.

    Son las dos preguntas que hay que poder mirar ANTES de montar nada, y las dos
    salieron de la misma grieta: un total de 296 nt que nadie podía descomponer escondía
    65 nt de espaciadores de novo, y el sitio de inserción no se emitía en ninguna
    parte. Un número que no se puede descomponer y una restricción que no se ve son la
    misma clase de problema.

    Los intrones que NO se ensamblan de piezas —o que todavía no tenemos— salen con su
    motivo en `nota` y sin inventarse nada: es la regla 3 sobre geometría en vez de
    sobre filtros.
    """
    from .introns import (
        INTRONS,
        check_module_upstream,
        insertion_window,
        intron_breakdown,
        locate_elements,
    )

    filas = []
    for nombre in (names if names is not None else tuple(INTRONS)):
        entrada = INTRONS.get(nombre)
        if entrada is None:
            raise ShmirDesignError(
                f"No hay ningún intrón {nombre!r} en el registro; los que hay son "
                f"{', '.join(sorted(INTRONS))}."
            )
        fila = {
            "intron": nombre,
            "desglose": None,
            "insercion": None,
            "elementos": None,
            "aguas_arriba": None,
            "nota": "",
        }
        try:
            fila["desglose"] = intron_breakdown(nombre, module_length=module_length)
        except ShmirDesignError as exc:
            # rule2-ok: no es un fallo, es la ausencia dicha con su motivo.
            fila["nota"] = str(exc)
        try:
            secuencia = entrada.require_sequence()
        except ShmirDesignError as exc:
            # rule2-ok: el intrón no está. Se dice, y no se calcula geometría de nada.
            fila["nota"] = (fila["nota"] + " " + str(exc)).strip()
            filas.append(fila)
            continue
        elementos = locate_elements(secuencia, name=nombre)
        fila["elementos"] = elementos
        ventana = insertion_window(elementos, module_length=module_length)
        fila["insercion"] = ventana
        # La TERCERA restricción, comprobada sobre el primer sitio admisible. Sin
        # candidato a punto de ramificación sale NOT_RUN y no PASS — no haber podido
        # comprobarlo no es que se cumpla.
        fila["aguas_arriba"] = check_module_upstream(
            elementos, after=ventana.ranges[0][0]
        )
        filas.append(fila)
    return filas


def intron_geometry_text(names=None, *, module_length: int = 149) -> str:
    """El bloque de texto de lo anterior, ya montado. La página no formatea."""
    lineas: list[str] = []
    for fila in intron_geometry_rows(names, module_length=module_length):
        lineas.append(f"── {fila['intron']} ──")
        if fila["desglose"] is not None:
            lineas.extend(fila["desglose"].describe())
        if fila["elementos"] is not None:
            lineas.extend(fila["elementos"].describe())
        if fila["insercion"] is not None:
            lineas.extend(fila["insercion"].describe())
        if fila["aguas_arriba"] is not None:
            estado = fila["aguas_arriba"]
            marca = "OK" if estado.state is FilterState.PASS else "⬜"
            lineas.append(
                f"  {marca} {estado.name}: {estado.state.value} — {estado.reason}"
            )
        if fila["nota"]:
            lineas.append(f"  ⬜ {fila['nota']}")
        lineas.append("")
    return "\n".join(lineas).rstrip()


def splice_constructions(selection, *, target, intron_names, scaffold, starts=None,
                         cassette=None, context_nt=0):
    """Los pares candidato x intron, montados. La pagina no monta nada."""
    from .spliceai import build_constructions

    return build_constructions(
        selection, target=target, intron_names=tuple(intron_names),
        scaffold=scaffold, starts=starts, cassette=cassette,
        context_nt=int(context_nt),
    )


def splice_context_note(constructions) -> str:
    """Que contexto se ha dado, y si es poco lo dice. La pagina no lo juzga."""
    from .spliceai import context_note

    return context_note(constructions)


def splice_construction_rows(constructions):
    """Una fila por PAR. Es lo que se enseña antes de descargar el FASTA."""
    return [
        {
            "construccion": c.name,
            "candidato": c.candidate_start,
            "intron": c.intron,
            "longitud": len(c.sequence),
            "md5": c.md5,
            "contexto5": c.context_5,
            "contexto3": c.context_3,
            "donante": c.donor_position,
            "aceptor": c.acceptor_position,
            "criptico_conocido": c.cryptic_position or None,
            "andamio_modificado": c.scaffold_modified,
        }
        for c in constructions
    ]


def splice_query_text(constructions):
    from .spliceai import constructions_fasta

    return constructions_fasta(constructions)


def splice_executor_text():
    from .spliceai import Disabled

    ejecutor = Disabled()
    return f"{ejecutor.name}: {ejecutor.why}"


def splice_scan_from_result(raw, *, constructions):
    """Del TSV crudo al analisis. La pagina no parsea ni valida: llama aqui."""
    from .spliceai import scan_from_result

    return scan_from_result(raw, constructions=constructions)


def splice_result_rows(scan):
    """Una fila por par, YA comparada contra su propio referente interno."""
    from .spliceai import RELATIVE_THRESHOLD

    filas = []
    for par in scan.pairs:
        mejor = par.best_cryptic
        filas.append({
            "construccion": par.construction,
            "candidato": par.candidate_start,
            "intron": par.intron,
            "donante_legitimo": par.legit_donor,
            "aceptor_legitimo": par.legit_acceptor,
            "mejor_criptico_pos": mejor.position if mejor else None,
            "mejor_criptico_tipo": mejor.kind if mejor else "",
            "mejor_criptico_fraccion": mejor.fraction if mejor else None,
            "gtgagcg_fraccion": (
                par.known_cryptic.fraction if par.known_cryptic else None
            ),
            "cripticos": len(par.cryptics),
            "contexto": f"{par.context_5}/{par.context_3}",
            # Rojo cuando el mejor criptico se ACERCA al legitimo. No es un veredicto:
            # es lo que el propio criterio dice que hay que mirar.
            "avisa": bool(mejor and mejor.fraction >= 0.5),
            "umbral_relativo": RELATIVE_THRESHOLD,
        })
    return filas


def splice_exclusive_rows(scan):
    """Que guias introducen cripticos que las otras NO. Lo accionable."""
    from .spliceai import exclusive_rows

    return exclusive_rows(scan)


def splice_module_of(construction, *, target, scaffold):
    """El modulo de 149 nt de una construccion. Se DERIVA de su candidato.

    No se guarda dentro de `Construction` a proposito: seria la misma secuencia en dos
    sitios, y dos copias de lo mismo acaban discrepando.
    """
    from .blocks import build_block

    guia = target[construction.candidate_start - 1:
                  construction.candidate_start - 1 + 22]
    return build_block(guia, scaffold=scaffold).module


def splice_folding_rows(constructions, *, module_of, available=None):
    """La accesibilidad estructural, SEPARADA de la prediccion de sitios.

    Son dos preguntas y no se mezclan: una la contesta un modelo entrenado para otra
    cosa y la otra la contesta plegar la construccion real.
    """
    from .intron_folding import ELEMENTS, fold_intron
    from .introns import get as get_intron

    filas = []
    for construccion in constructions:
        resultado = fold_intron(
            get_intron(construccion.intron),
            module=module_of(construccion),
            available=available,
        )
        fila = {
            "construccion": construccion.name,
            "candidato": construccion.candidate_start,
            "intron": construccion.intron,
            "estado": resultado.state,
            "energia": resultado.energy,
            "motivo": resultado.reason,
        }
        for elemento in ELEMENTS:
            fila[elemento] = resultado.unpaired.get(elemento)
        filas.append(fila)
    return filas


def splice_highlights(scan):
    """Lo que va DESTACADO y no enterrado en la tabla."""
    from .spliceai import (
        CONTEXT_MATTERS,
        NO_ABSOLUTE_THRESHOLD,
        NOT_TRAINED_FOR_THIS,
        RELATIVE_ONLY,
        RELATIVE_THRESHOLD_NOTE,
        USE_NOTE,
        WHAT_IS_ACTIONABLE,
    )

    exclusivos = [f for f in splice_exclusive_rows(scan) if f["exclusivos"]]
    return {
        "entrenamiento": {"texto": NOT_TRAINED_FOR_THIS, "activo": True},
        "sin_umbral": {"texto": NO_ABSOLUTE_THRESHOLD, "activo": True},
        "relativo": {"texto": RELATIVE_ONLY, "activo": True},
        "contexto": {"texto": CONTEXT_MATTERS, "activo": True},
        "umbral_relativo": {"texto": RELATIVE_THRESHOLD_NOTE, "activo": True},
        "uso": {"texto": USE_NOTE, "activo": True},
        "accionable": {
            "texto": (
                f"{WHAT_IS_ACTIONABLE} En esta corrida hay {len(exclusivos)} "
                f"construcción(es) con crípticos que sus hermanas no tienen."
            ),
            "activo": bool(exclusivos),
        },
    }


def splice_variant_rows(scaffold, *, guide, available=None):
    """Las alternativas para romper el criptico, con sus DOS metricas.

    La pagina no elige: si empatan, se le dice que empatan y lo decide quien lee.
    """
    from .intron_design import (
        AUTHORIZATION,
        SCAFFOLD_MODIFIED_MARK,
        TIE_NOTE,
        choose_break,
    )

    eleccion = choose_break(scaffold, guide=guide, available=available)
    return {
        "estado": eleccion.state,
        "motivo": eleccion.reason,
        "filas": eleccion.rows(),
        "empate": eleccion.tie,
        "elegida": (
            None if eleccion.chosen is None
            else {
                "posicion": eleccion.chosen.position,
                "cambio": f"{eleccion.chosen.original}->{eleccion.chosen.replacement}",
                "motivo": eleccion.chosen.motif,
            }
        ),
        "empatadas": [c.motif for c in eleccion.tied],
        "nota_empate": TIE_NOTE,
        "autorizacion": AUTHORIZATION,
        "marca_andamio": SCAFFOLD_MODIFIED_MARK,
        "texto": "\n".join(eleccion.describe()),
    }


# ═════════════════ PERSISTENCIA: que lo calculado sobreviva a la pestaña ═════════════════
#
# El hueco mas grande que quedaba, y era del tipo que este proyecto ya conoce: la capa
# entera —`store.py`, JSONL append-only, la cadena de md5— estaba construida y testada, y
# **`store.save_*` no se llamaba desde ningun sitio**. Los cuatro modales calculaban,
# pintaban, y al cerrar la pestaña no quedaba nada.
#
# La pagina no toca `store.py` directamente: llama aqui, como con todo lo demas.


def projects_root():
    """Donde viven los proyectos. En un despliegue, en el volumen."""
    from .trabajo import projects_dir

    return projects_dir()


def project_list(base) -> list[dict[str, object]]:
    """Los proyectos que hay, con lo que hace falta para ELEGIR uno.

    Sin ninguno devuelve la lista vacia y NO aborta: no haber creado todavia ninguno es
    lo normal el primer dia, no un fallo.
    """
    from pathlib import Path

    from .store import LOG_FILE, PROJECT_FILE, ProjectStore

    raiz = Path(base)
    if not raiz.is_dir():
        return []
    filas = []
    for directorio in sorted(p for p in raiz.iterdir() if p.is_dir()):
        if not (directorio / PROJECT_FILE).is_file():
            continue
        almacen = ProjectStore.open(raiz, directorio.name)
        filas.append({
            "slug": almacen.project.slug,
            "creado": almacen.project.created,
            "md5": almacen.project.sequence_md5,
            "longitud": almacen.project.sequence_length,
            "especie": almacen.project.species,
            "fiable": almacen.project.reliable,
            "por_que_no_fiable": almacen.project.why_unreliable,
            "corridas": len(almacen.records()),
            "log": str(directorio / LOG_FILE),
        })
    return filas


def anatomy_payload(anatomy) -> tuple[dict | None, str]:
    """La anatomia como la guarda el proyecto, y de donde salio. La pagina no la modela.

    `None` significa que no se resolvio, y entonces el proyecto sale marcado NO_FIABLE —
    que es informacion, no un fallo: sin frontera del 3'UTR, los tercios y las zonas de
    polyA no se refieren a nada.
    """
    if anatomy is None:
        return None, "sin_resolver"
    utr3 = getattr(anatomy, "utr3", None)
    cds = getattr(anatomy, "cds", None)
    fuente = getattr(anatomy, "source", None)
    return (
        {
            "length": getattr(anatomy, "length", None),
            "utr3": list(utr3) if utr3 else None,
            "cds": list(cds) if cds else None,
        },
        getattr(fuente, "value", str(fuente or "sin_resolver")),
    )


def blast_run_from_upload(*, raw: str, query, params, declared_query_md5: str,
                          panel_names, database: dict, date: str, uploaded_by: str,
                          run_id: str):
    """Valida el `-outfmt 6` y construye la corrida. La pagina no valida nada.

    Las DOS comprobaciones de `blast_store.validate_upload` abortan: el md5 del FASTA de
    consulta declarado tiene que ser el que genero la app, y toda `query` del resultado
    tiene que estar en el panel. Es el fallo del CSV de miRarchitect.
    """
    from .blast_store import BlastDatabase, BlastRun, validate_upload

    validate_upload(
        raw=raw, query=query, declared_query_md5=declared_query_md5,
        panel_names=panel_names,
    )
    base = BlastDatabase(
        name=str(database.get("nombre", "")).strip(),
        version=str(database.get("version", "")).strip(),
        md5=(str(database.get("md5", "")).strip() or None),
        remote=bool(database.get("remota", False)),
    )
    return BlastRun.create(
        run_id=run_id, date=date, uploaded_by=uploaded_by, params=params,
        database=base, query=query, raw=raw,
    )


def seed_run_from_scan(scan, *, date: str, ran_by: str, run_id: str):
    """La corrida de colision de seed, lista para guardar."""
    from .seed_store import SeedRun

    return SeedRun.create(run_id=run_id, date=date, ran_by=ran_by, scan=scan)


def offtarget_run_from_scan(scan, *, date: str, ran_by: str, run_id: str):
    """La corrida de carga de off-targets, lista para guardar."""
    from .offtarget_store import OfftargetRun

    return OfftargetRun.create(run_id=run_id, date=date, ran_by=ran_by, scan=scan)


def splice_run_from_scan(scan, *, raw: str, date: str, ran_by: str, run_id: str,
                         executor: str, folding=None):
    """La corrida del cuarto modal, lista para guardar. La pagina no construye objetos."""
    from .splice_store import SpliceRun

    return SpliceRun.create(
        run_id=run_id, date=date, ran_by=ran_by, executor=executor,
        scan=scan, raw=raw, folding=folding,
    )


#: Qué puede ser el nombre de un proyecto. Va aquí y no en la página (regla 6).
#:
#: El nombre lo teclea una persona y se convierte en un DIRECTORIO. Sin comprobarlo,
#: «Prnp raton 2026/08/27» crea un anidado que `project_list` no lista nunca —el
#: proyecto existe y no aparece— y `..` o una ruta absoluta escriben FUERA del directorio
#: de proyectos, que es el volumen donde vive el registro de lo que se decidió.
PROJECT_SLUG_RULE = (
    "El nombre de un proyecto es UN nombre de carpeta: letras, dígitos, guion, guion "
    "bajo y punto. Ni barras, ni `..`, ni rutas absolutas — se convierte en un "
    "directorio, y con una barra dentro el proyecto se crea donde nadie lo busca."
)
_SLUG_OK = re.compile(r"^[A-Za-z0-9._-]+$")


def check_project_slug(slug: str) -> str:
    """Valida el nombre de un proyecto o ABORTA. Ver `PROJECT_SLUG_RULE`."""
    limpio = str(slug).strip()
    if not limpio or limpio in (".", "..") or not _SLUG_OK.match(limpio):
        raise ShmirDesignError(
            f"Nombre de proyecto {slug!r} no válido. {PROJECT_SLUG_RULE}"
        )
    return limpio


# ── Biblioteca del paso 2 ────────────────────────────────────────────────────────
#
# La pagina no toca `biblioteca.py`: pasa por aqui, como con todo lo demas. Si empezara a
# importarlo directamente, acabaria decidiendo sobre el almacen —que ordenar, que
# etiqueta poner, que hacer si falta— y eso es la regla 6.


@dataclass(frozen=True)
class LibraryFile:
    """Un fichero de la biblioteca con la MISMA forma que uno subido.

    La pagina usa exactamente dos cosas de un `UploadedFile`: `.name` y `.getvalue()`.
    Con esto, todo lo que hay aguas abajo —`_fasta_sequence`, `resolve_anatomy`— no se
    entera de si vino del navegador o del volumen. Distinguirlos aguas abajo serian dos
    caminos que divergen, y este proyecto ya lleva cuatro divergencias entre frontales.
    """

    name: str
    _data: bytes

    def getvalue(self) -> bytes:
        return self._data


def library_note() -> str:
    """Donde vive la biblioteca y por que sobrevive. Va a la vista, no en un comentario."""
    from .biblioteca import WHY_THE_VOLUME  # noqa: PLC0415

    return (
        f"{WHY_THE_VOLUME} Lo guardado aquí NO cierra ningún frente y no entra en el "
        f"manifiesto: es sólo para no volver a buscar el mismo fichero en cada sesión."
    )


def library_rows(slot: str, *, base=None) -> list[dict]:
    """Una fila por fichero guardado, con la etiqueta YA montada."""
    from .biblioteca import listar  # noqa: PLC0415

    return [
        {
            "id": e.id,
            "nombre": e.name,
            "guardado": e.date,
            "bytes": e.size,
            "etiqueta": f"{e.name} — {e.size} bytes, {e.date}, md5 {e.id[:8]}",
        }
        for e in listar(slot, base=base)
    ]


def library_file(slot: str, ident: str, *, base=None) -> LibraryFile:
    """Un fichero guardado, con la forma de uno subido. ABORTA si no cuadra el md5."""
    from .biblioteca import leer, listar  # noqa: PLC0415

    entrada = next((e for e in listar(slot, base=base) if e.id == ident), None)
    if entrada is None:
        raise ShmirDesignError(
            f"No hay ningún fichero {ident} guardado en la ranura {slot!r}; se aborta "
            f"en vez de seguir sin él."
        )
    return LibraryFile(name=entrada.name, _data=leer(slot, ident, base=base))


def library_save(slot: str, upload, *, date: str, base=None) -> dict:
    """Guarda lo que hay en el hueco. Devuelve la fila de lo guardado."""
    from .biblioteca import guardar  # noqa: PLC0415

    entrada = guardar(
        slot, nombre=upload.name, data=upload.getvalue(), date=str(date), base=base
    )
    return {
        "id": entrada.id,
        "nombre": entrada.name,
        "guardado": entrada.date,
        "bytes": entrada.size,
        "etiqueta": entrada.describe(),
    }


def library_delete(slot: str, ident: str, *, base=None) -> str:
    """Borra una entrada y devuelve el texto de lo que se fue."""
    from .biblioteca import borrar  # noqa: PLC0415

    return borrar(slot, ident, base=base).describe()


UPLOAD_NAME_RULE = (
    "El nombre de un fichero subido lo pone el NAVEGADOR, no el servidor: se escribe "
    "en disco, así que se queda con el nombre a secas y se comprueba que la ruta cae "
    "dentro del directorio de destino. Con `..` dentro, la escritura saldría del "
    "directorio temporal que se creó justo para contenerla."
)


def upload_path(directorio, nombre: str):
    """Ruta DENTRO de `directorio` para un fichero subido, o ABORTA.

    La regla es UNA: sobrevive el NOMBRE, se cae todo lo que va delante. `..` no es un
    caso especial —es ruta—, y por eso no hay que acertar con la lista de formas de
    escribirlo (`..%2f`, `....//`): no se limpia la ruta, se descarta entera. Si no
    queda nombre (`.`, `..`, vacío), se aborta en vez de inventarse uno.

    La extensión sobrevive —`resolve_anatomy` y `load_scaffold` deciden el formato por
    ella, así que comérsela rompería la carga sin decir por qué—. Y la comprobación
    final es sobre la ruta RESUELTA, que es la que acaba en `write_bytes`: comprobar el
    texto y escribir otra cosa es la mitad de una comprobación.

    Es la hermana pequeña de `check_project_slug`: allí el nombre lo teclea el usuario,
    aquí lo manda el navegador. Ver `UPLOAD_NAME_RULE`.
    """
    base = Path(directorio)
    crudo = str(nombre)
    if "\x00" in crudo or "\\" in crudo:
        raise ShmirDesignError(
            f"Nombre de fichero {nombre!r} no válido. {UPLOAD_NAME_RULE}"
        )
    limpio = PurePosixPath(crudo).name.strip()
    if not limpio or limpio in (".", ".."):
        raise ShmirDesignError(
            f"Nombre de fichero {nombre!r} no válido. {UPLOAD_NAME_RULE}"
        )
    ruta = base / limpio
    if not ruta.resolve().is_relative_to(base.resolve()):
        raise ShmirDesignError(
            f"El fichero {nombre!r} acabaría en {ruta.resolve()}, fuera de {base}. "
            f"{UPLOAD_NAME_RULE}"
        )
    return ruta


def project_create(base, *, slug: str, date: str, sequence: str, species: str,
                   anatomy, anatomy_source: str):
    """Crea el proyecto en disco. Repetir un slug ABORTA: nada se pisa.

    Se pasa la SECUENCIA, no su md5: el md5 lo deriva `ProjectStore.create` de lo que
    recibe. Un md5 que viene por parametro se puede teclear mal y entonces el proyecto
    identificaria una entrada que no es la suya — que es exactamente lo que este campo
    existe para impedir.
    """
    from .store import ProjectStore

    return ProjectStore.create(
        base, slug=check_project_slug(slug), sequence=sequence, species=str(species),
        anatomy=anatomy, anatomy_source=str(anatomy_source), created=str(date),
    )


def project_open(base, slug: str, *, expect_md5: str | None = None):
    """Abre un proyecto. Si se declara `expect_md5` y NO cuadra, se RECHAZA.

    Es el fallo del CSV de miRarchitect por la puerta de la persistencia: seguir
    apuntando corridas de OTRA secuencia en el log de esta. El log quedaria coherente de
    forma, la cadena de md5 no se romperia, y el resultado seria un proyecto que mezcla
    dos entradas sin que nada lo delate.
    """
    from .store import ProjectStore

    almacen = ProjectStore.open(base, check_project_slug(slug))
    if expect_md5 and almacen.project.sequence_md5 != str(expect_md5):
        raise ShmirDesignError(
            f"El proyecto {slug!r} se creo sobre una secuencia de md5 "
            f"{almacen.project.sequence_md5!r} y la que hay cargada es "
            f"{str(expect_md5)!r}. Se RECHAZA: seguir apuntando corridas de OTRA "
            f"SECUENCIA en este log lo dejaria coherente de forma —la cadena de md5 ni "
            f"se enteraria— y el proyecto mezclaria dos entradas sin que nada lo delate. "
            f"Crea otro proyecto para esta secuencia."
        )
    return almacen


def load_stores(store) -> dict[str, object]:
    """Los CUATRO almacenes reconstruidos desde el log. Un solo sitio, no cuatro."""
    from .store import (
        load_blast_store,
        load_offtarget_store,
        load_seed_store,
        load_splice_store,
    )

    return {
        "blast": load_blast_store(store),
        "seed": load_seed_store(store),
        "offtarget": load_offtarget_store(store),
        "splice": load_splice_store(store),
    }


def save_blast_run(store, run):
    from .store import save_blast_run as _guardar

    return _guardar(store, run)


def save_seed_run(store, run):
    from .store import save_seed_run as _guardar

    return _guardar(store, run)


def save_offtarget_run(store, run):
    from .store import save_offtarget_run as _guardar

    return _guardar(store, run)


def save_splice_run(store, run):
    from .store import save_splice_run as _guardar

    return _guardar(store, run)


def save_selection(store, *, starts, date: str, by: str):
    """La seleccion manual. Una nueva NO pisa la vieja: la SUCEDE."""
    from .store import save_selection as _guardar

    return _guardar(store, starts=starts, date=date, by=by)


def selected_starts(store):
    from .store import selected_starts as _leer

    return _leer(store)


def project_rows(store) -> list[dict[str, object]]:
    """El historial del proyecto, para pintarlo. Una fila por registro."""
    return [
        {
            "n": r.seq,
            "tipo": r.kind,
            "fecha": r.date,
            "resumen": _resumen_registro(r),
        }
        for r in store.records()
    ]


def _resumen_registro(record) -> str:
    """Una linea por registro. No interpreta: saca lo que el propio registro trae."""
    datos = record.payload
    if record.kind == "seleccion":
        return f"{len(datos.get('starts', []))} candidato(s) — {datos.get('by', '')}"
    if record.kind.startswith("corrida_"):
        return (
            f"{datos.get('run_id', 'sin id')} — {datos.get('ran_by', '')} "
            f"(resultado md5 {str(datos.get('result_md5', ''))[:8]})"
        )
    return str(datos.get("texto", ""))[:80]


# ═════════════════ EL CAMINO DE LA PAGINA, FUERA DE LA PAGINA ═════════════════
#
# Por que existe esto, y por que llega tan tarde.
#
# La suite tenia 2.767 tests en verde y la primera ejecucion real de la interfaz
# —`NM_011170.3.gb`, Mus musculus, sin subir nada— dio TRES fallos seguidos: un aborto
# de marco en el mapa, una aritmetica imposible entre la estimacion y el resultado, y un
# recuento que afirmaba una causa que no habia comprobado. Ninguno era sutil.
#
# No fallaba la cobertura de las funciones: fallaba que **nadie recorria el camino de la
# pagina de punta a punta y miraba la salida entera**. Cada test miraba lo suyo, y lo
# que se rompia era la juntura entre piezas que por separado estaban bien: la pagina
# tilaba el transcrito y le pasaba el 3'UTR a la estimacion; tilaba el transcrito y le
# pasaba el informe a un mapa que suponia 3'UTR.
#
# `page_run` es ese camino, y la pagina lo llama en vez de rehacerlo — si volviera a
# rehacerlo, volveria a poder divergir. `page_snapshot` lo pinta ENTERO para el golden,
# con la misma disciplina que el informe: se compara todo, no la presencia de trozos.


@dataclass(frozen=True)
class PageRun:
    """Lo que la pagina calcula antes de pintar nada."""

    species: str
    sequence: str
    anatomy: Anatomy
    tiling: TilingReport
    selection: ReportSelection
    utr3: str

    @property
    def frame(self) -> Frame:
        return self.tiling.frame


def page_run(
    *,
    species: str,
    sequence: str,
    anatomy: Anatomy,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    config=None,
    seeds=None,
    mask=None,
    accessibility: bool = False,
    resources: ResourceSet | None = None,
    tile_range=None,
) -> PageRun:
    """Tila y selecciona EXACTAMENTE como lo hace la pagina.

    Se tila la secuencia ENTERA con su anatomia, igual que el CLI: asi las coordenadas
    de transcrito son coordenadas de transcrito de verdad y no una copia de las del
    3'UTR. Que ventanas entran lo decide `tile_range`, en el nucleo.
    """
    from .selection import default_config, select_from_report
    from .tiling import tile_utr

    if anatomy is None:
        raise ShmirDesignError(
            "No hay anatomía, así que no se sabe que parte de la secuencia es el 3'UTR "
            "ni en que espacio van las coordenadas. Se aborta: es la regla de "
            "`resolve.py`, y un marco supuesto es lo que produce un `3utr:1856` sobre "
            "un 3'UTR de 1242 nt."
        )
    extra = dict(resources.as_kwargs()) if resources is not None else {}
    if mask is not None:
        extra["mask"] = mask  # la mascara subida a mano manda sobre la del manifiesto
    # LA TABLA DE APA MEDIDO LA RESUELVE `tile_utr`, del FICHERO del gestor. Aqui no
    # se pasa nada: la regla entra sola y el dato sale del deposito. Antes esto llamaba
    # a `resolve_measured` con la constante `apa.POLYA_DB_PRNP`, asi que la pagina
    # tenia que acordarse —y en otra especie no habia forma de meter los numeros—.
    tiling = tile_utr(
        sequence, anatomy=anatomy, seeds=seeds, thresholds=thresholds,
        accessibility=accessibility, species=species, tile_range=tile_range,
        **extra,
    )
    # `default_config()` es la configuracion DEL PROYECTO: panel de 10 y cuota de
    # inmunes emparejada con su frontera. `SelectionConfig()` a secas no la lleva, y
    # usarlo aqui dejaba el panel con tres inmunes sin decirlo.
    seleccion = select_from_report(
        tiling, config if config is not None else default_config()
    )
    inicio, fin = anatomy.utr3
    return PageRun(
        species=species,
        sequence=sequence,
        anatomy=anatomy,
        tiling=tiling,
        selection=seleccion,
        utr3=sequence[inicio - 1 : fin],
    )


def _tabla(filas, *, vacio: str) -> list[str]:
    """Una tabla de diccionarios en texto plano, con el ancho sacado de lo que hay."""
    if not filas:
        return [f"  {vacio}"]
    columnas = list(filas[0])
    anchos = {
        c: max([len(c)] + [len(str(f.get(c, ""))) for f in filas]) for c in columnas
    }
    lineas = ["  " + "  ".join(f"{c:<{anchos[c]}}" for c in columnas)]
    for fila in filas:
        lineas.append(
            "  " + "  ".join(f"{str(fila.get(c, '')):<{anchos[c]}}" for c in columnas)
        )
    return lineas


#: Los tiempos MEDIDOS no entran en el golden. Se miden en esta máquina y en este
#: momento, así que cambian en cada corrida: dejarlos dentro hace fallar el golden sin
#: que nadie haya tocado nada, y un golden que falla siempre deja de leerse — que es la
#: única forma en la que un golden sirve para algo. (Falló en la primera corrida de este
#: mismo test, con 205 ms contra 221.) Lo que sí queda fijado es que la partida EXISTA.
_TIEMPO = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:ms|s)\b")


def _sin_tiempos(texto: str) -> str:
    """Sustituye los tiempos medidos por una marca. Ver `_TIEMPO`."""
    return _TIEMPO.sub("<tiempo medido>", texto)


def _mapa_resumen(svg: str) -> list[str]:
    """Cuantos elementos DIBUJA el mapa, por tipo, mas su leyenda.

    El SVG entero no entra en el golden —mil coordenadas con decimales harian ilegible
    cualquier diff— pero un conteo por tipo si: un mapa que se queda sin candidatos, o
    que de pronto dibuja diez señales donde habia tres, sale en el diff. Guardar solo
    las dos ultimas lineas dejaba fuera exactamente eso.
    """
    conteos = {
        "candidato": svg.count("data-candidato="),
        "senal": svg.count("data-senal="),
        "mascara": svg.count("data-mascara="),
        "bloque": svg.count("data-bloque="),
    }
    leyenda = [l for l in svg.splitlines() if "3'UTR de" in l]
    return (
        [f"  {k}: {v}" for k, v in conteos.items()]
        + [f"  leyenda: {l.split('>', 1)[1].split('<')[0]}" for l in leyenda]
    )


def page_snapshot(
    *,
    species: str,
    sequence: str,
    anatomy: Anatomy,
    generated: str,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    config=None,
    resources: ResourceSet | None = None,
    max_rows: int = 12,
) -> str:
    """TODO lo que la pagina pinta de una especie, en texto, para compararlo entero.

    No es un resumen: si una seccion desaparece, el diff lo enseña. `max_rows` acota
    las tablas largas y **dice cuantas filas se dejan fuera** — recortar en silencio es
    como se fabrica una salida que parece completa.
    """
    corrida = page_run(
        species=species, sequence=sequence, anatomy=anatomy, thresholds=thresholds,
        config=config, resources=resources,
    )
    tiling, seleccion = corrida.tiling, corrida.selection
    luz = status_light(seleccion)
    documento = informe_documento(
        seleccion, tiling, species=species, generated=generated,
        anatomy_source=anatomy.source.value,
    )

    def _recorte(filas):
        cuerpo = _tabla(filas[:max_rows], vacio="(ninguna)")
        if len(filas) > max_rows:
            cuerpo.append(
                f"  … {len(filas) - max_rows} fila(s) mas, no listadas por el límite "
                f"de esta instantanea ({max_rows})."
            )
        return cuerpo

    lineas = [
        f"═══ La pagina, corrida entera — {species} ═══",
        "",
        f"  secuencia tilada   {len(sequence)} nt",
        f"  marco de lo tilado {corrida.frame.value}",
        f"  3'UTR              {corrida.anatomy.utr3_length} nt",
        f"  anatomía           {anatomy.source.value}",
        "",
        "── 1. Anatomía del transcrito ──",
        *_tabla(
            anatomy_rows(None, utr3_length=len(corrida.utr3), anatomy=anatomy),
            vacio="(sin anatomía)",
        ),
        "",
        "── 2. Estimación de coste, sobre LO MISMO que se tila ──",
        *[
            f"  {linea}"
            for linea in _sin_tiempos(
                cost_text(
                    sequence, anatomy=anatomy, resources=resources,
                    thresholds=thresholds,
                )
            ).splitlines()
        ],
        "",
        "── 3. Semaforo ──",
        f"  color      {luz.color}",
        f"  titular    {luz.headline}",
        f"  filtros    {luz.ran} de {luz.total} corrieron",
        f"  ventanas   {luz.tiled} tiladas, {luz.not_eligible} sin pasar los biofísicos",
        f"  detalle    {luz.detail}",
        "",
        "── 4. Mapa del 3'UTR ──",
        *_mapa_resumen(map_svg(tiling, seleccion)),
        "",
        f"── 5. Candidatos ({len(seleccion.selection.chosen)}) ──",
        *_recorte(candidate_rows(seleccion)),
        "",
        "── 6. Frentes ──",
        *_tabla(
            [
                {
                    "frente": f["frente"],
                    "estado": "NOT_RUN" if f["abierto"] else "CERRADO",
                    "motivo": f["motivo"],
                }
                for f in front_help_rows(tiling, seleccion, species=species)
            ],
            vacio="(ninguno)",
        ),
        "",
        "── 7. Avisos de la selección ──",
        *(
            [
                f"  [{'ROJO' if a['rojo'] else 'AVISO'}] {a['texto']}"
                for a in selection_warnings(tiling, seleccion)
            ]
            or ["  (ninguno)"]
        ),
        "",
        "── 8. Informe ──",
        f"  estado     {documento.state}",
        f"  {informe_state_text(documento)}",
        "",
        f"── 9. Ventanas tiladas: {len(tiling.windows)} ──",
        *_recorte(window_rows(tiling)),
        "",
    ]
    return "\n".join(lineas) + "\n"


# ═════════════ LAS DOS REGLAS DE LA SELECCION, LADO A LADO ═════════════
#
# La cuota por tercio y la cuota de INMUNES no compiten: hacen cosas distintas y las dos
# hacen falta. Con solo la de tercios, `3utr:359` (+4,82) desplaza a `3utr:200` (+3,80)
# por asimetria y el panel se queda con TRES inmunes en vez de cuatro — sin que nada lo
# diga, porque los dos son del tercio proximal y la cuota de tercios se cumple igual.
#
# Y eso importa porque los inmunes son la UNICA reserva si el APA de `3utr:288` resulta
# funcional: los sitios elegibles por delante del corte estan **20/0/0** por tercio, asi
# que no hay de donde rebalancear. Un panel con tres inmunes no es «casi» el de cuatro.


def immune_count(tiling, selection) -> int:
    """Cuantos candidatos del panel son INMUNES al truncamiento por la señal proximal.

    Inmune = empieza POR DELANTE del corte mas temprano, que se DERIVA del informe
    (`selection.derive_immune_cut`) y no se teclea. Ver la entrada de `CLAUDE.md` sobre
    por que la definicion estricta es la unica que vale.
    """
    from .selection import derive_immune_cut

    corte = derive_immune_cut(tiling)
    if corte is None:
        return 0
    return sum(1 for c in selection.selection.chosen if c.start < corte)


def selection_rules_report(*, species: str, sequence, anatomy, thresholds=None) -> str:
    """El panel bajo LAS DOS reglas, para poder compararlas.

    No elige: emite las dos y dice cuantos inmunes deja cada una, que es la cifra de la
    que cuelga la decision. La misma disciplina que `--polyA-modo`, que saca el top-N
    bajo los tres criterios y deja decidir con la tabla delante.
    """
    from .hard_filters import DEFAULT_THRESHOLDS
    from .selection import DEFAULT_CANDIDATES, DEFAULT_IMMUNE_QUOTA, SelectionConfig

    umbrales = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    reglas = (
        (
            "solo cuota por tercio",
            SelectionConfig(n_candidates=DEFAULT_CANDIDATES, apa_immune_quota=0),
        ),
        (
            f"cuota por tercio + cuota de inmunes = {DEFAULT_IMMUNE_QUOTA}",
            SelectionConfig(n_candidates=DEFAULT_CANDIDATES),
        ),
    )
    lineas = [
        "── El panel bajo las DOS reglas ──",
        "",
        "  Los inmunes son la ÚNICA reserva si el APA proximal resulta funcional: los",
        "  sitios elegibles por delante del corte están 20/0/0 por tercio, así que si se",
        "  pierden no hay de donde rebalancear. Por eso la cuota de inmunes es una CUOTA",
        "  y no una preferencia.",
    ]
    for etiqueta, config in reglas:
        corrida = page_run(
            species=species, sequence=sequence, anatomy=anatomy,
            thresholds=umbrales, config=config,
        )
        inmunes = immune_count(corrida.tiling, corrida.selection)
        lineas.extend(["", f"  {etiqueta} — {inmunes} inmunes de "
                       f"{len(corrida.selection.selection.chosen)}"])
        for choice in sorted(corrida.selection.selection.chosen, key=lambda c: c.start):
            u = corrida.anatomy.utr3_position(choice.start)
            marca = " [inmune]" if choice.start < (
                __import__("shmir_design.selection", fromlist=["derive_immune_cut"])
                .derive_immune_cut(corrida.tiling) or 0
            ) else ""
            lineas.append(
                f"    3utr:{u:<5} {choice.asymmetry:+.2f}  "
                f"{choice.tercio.value if choice.tercio else '—'}{marca}"
            )
    return "\n".join(lineas)


def stored_runs_note(stores) -> str:
    """Qué corridas trae el proyecto ya guardadas, por frente.

    Existe porque `load_stores` estaba importado en la página y **no se llamaba**: al
    reabrir un proyecto volvía la selección y los cuatro frentes salían otra vez
    `NOT_RUN`, así que la persistencia servía para la mitad de lo que dice servir. Es el
    mismo patrón que `store.save_*` y que `page_run` — tercera vez.

    Y el texto se construye AQUÍ y no en la página (regla 6): contar corridas y decidir
    qué se enseña es lógica, y en la página no tendría test.
    """
    partes = []
    for clave, almacen in sorted(stores.items()):
        corridas = getattr(almacen, "runs", None)
        partes.append(f"{clave}: {len(corridas) if corridas is not None else 0}")
    total = sum(
        len(getattr(a, "runs", None) or ()) for a in stores.values()
    )
    if not total:
        return (
            "El proyecto no tiene ninguna corrida guardada todavía. Los frentes salen "
            "NOT_RUN porque nadie los ha cerrado, no porque no se hayan releído."
        )
    return (
        "Corridas RECUPERADAS del proyecto — " + ", ".join(partes) + ". "
        "Vuelven del log, no se han vuelto a calcular."
    )


#: Por qué una corrida cacheada lleva HUELLA.
#:
#: El resultado de un modal se guarda en el estado de la página para que sobreviva al
#: rerun del botón de guardar. Pero el panel y los ajustes se pueden cambiar DESPUÉS, y
#: el resultado viejo se seguía pintando y ofreciendo para guardar: se persistía en el
#: log una corrida cuya procedencia no era la de pantalla. Es el fallo del CSV de
#: miRarchitect otra vez — un resultado que encaja de forma y es de otra cosa.
WHY_A_RUN_FINGERPRINT = (
    "Una corrida cacheada lleva la huella del panel y los ajustes con los que se hizo. "
    "Si cambian, se descarta: pintar un resultado viejo bajo unos ajustes nuevos es "
    "presentar una procedencia que no es la suya."
)


def run_fingerprint(*partes) -> str:
    """Huella de lo que produjo una corrida. Ver `WHY_A_RUN_FINGERPRINT`."""
    import hashlib

    crudo = "|".join(repr(p) for p in partes)
    return hashlib.md5(crudo.encode("utf-8")).hexdigest()
