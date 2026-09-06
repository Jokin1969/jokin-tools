"""Todo lo que la interfaz necesita decidir, decidido aqui y probado aqui.

La UI no puede tener logica: si una funcion elige un color, ordena una tabla o dibuja
un mapa, vive en este modulo y tiene tests. `ui/streamlit_app.py` solo llama.

Stdlib pura, como el resto del nucleo: este modulo no importa Streamlit.

Python 3.11+ (regla 6).
"""

from __future__ import annotations

import inspect
import re
import textwrap
from dataclasses import dataclass, field
from html import escape
from pathlib import Path, PurePosixPath

from . import coords
from .anatomy import Anatomy
from .coords import Frame
from .blocks import blocks_fasta, blocks_tsv, build_block, order_sheet
from .comparative import comparative_tsv
from .seed_load import LOAD_COLUMNS as SEED_LOAD_COLUMNS
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
from .scaffold import ScaffoldSpec, build_hairpin
from .polya import POLYA_COLUMNS, cleavage_band, normalize_sequence
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


def status_light(selection: ReportSelection, *, resueltos=()) -> StatusLight:
    """Verde si todos los filtros corrieron para los candidatos seleccionados.

    `resueltos` son los filtros que una CORRIDA GUARDADA ha cerrado para todo el panel.
    Entra por parametro y no se adivina: este semaforo cuenta los filtros de la ventana,
    que no saben nada del registro del proyecto — y sin esto decia «6 de 10» con una
    corrida de BLAST valida encima, que es lo que se reporto el 2026-09-02.

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

    ya_resueltos = set(resueltos or ())
    pendientes = sorted(
        {
            r.name
            for choice in selection.selection.chosen
            for r in selection.window_of(choice).filters
            if r.state is FilterState.NOT_RUN and r.name not in ya_resueltos
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


def candidate_rows(
    selection: ReportSelection, *, species: str = "", stores=None,
) -> list[dict[str, object]]:
    """Una fila por candidato, con el estado de CADA filtro en su propia columna.

    LEE LOS ALMACENES (2026-09-02, errata nº 55). Son DOS tablas y las dos se llaman
    desde la pagina: esta —«Candidatos, un estado por filtro»— y `site_table_rows`, la de
    todos los sitios elegibles. El arreglo de `stores=` fue a la segunda y esta se quedo
    fuera, asi que la tarjeta decia «CERRADO por corrida guardada: los 10 candidatos» y la
    tabla de esos mismos diez decia `NOT_RUN` tres centimetros mas arriba.

    Lo cazo quien lo reporto **por el dato interno**: la ultima fila llevaba marcada
    `bandera_polyA_debil`, que es `3utr:1018` — el unico del panel con `ACTAAA` solapando.
    O sea, eran los diez del panel y no diez cualesquiera. Ver principio nº 23: dos
    artefactos que leen el mismo estado y solo uno actualizado.
    """
    # LA REFERENCIA DE `carga_seed`, UNA sola vez para toda la tabla: el percentil por
    # clase y los controles salen de la corrida guardada, no se recalculan aqui (la nula
    # son ≥10.000 sorteos por consulta — errata nº 59).
    referencia = seed_load_reference(
        stores=stores, species=species,
        starts=[c.start for c in selection.selection.chosen],
    )
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
                # LOS SUMANDOS, NO LA SUMA. `carga_seed` era `sum(counts.values())`
                # y salia sin sus tres sumandos —que estaban CALCULADOS en `counts` y se
                # tiraban en la celda—, sin percentil y sin el 6mer. O sea: la unica
                # columna visible de este eje era la unica que `WHY_NOT_SUMMED` prohibe.
                # Ver `seed_load.WHERE_THE_TOTAL_WENT`.
                **(
                    window.carga_seed.as_columns() if window.carga_seed
                    else dict.fromkeys(SEED_LOAD_COLUMNS, "")
                ),
                # Y LAS DEL FRENTE, que son OTRO contador: cuatro clases —con el 6mer—,
                # de la corrida guardada y con su percentil PEGADO en la misma celda.
                **seed_load_columns(
                    stores=stores, species=species, start=choice.start,
                    reference=referencia,
                ),
                "accesibilidad": (
                    window.accesibilidad.as_column() if window.accesibilidad else ""
                ),
                **_with_stores(
                    _filter_columns(window), stores, species, choice.start
                ),
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


def window_rows(
    report: TilingReport, *, species: str = "", stores=None,
) -> list[dict[str, object]]:
    """TODAS las ventanas. Ninguna se omite: omitir es esconder un NOT_RUN.

    LEE LOS ALMACENES, como las otras dos tablas. Era la TERCERA —«Todas las ventanas»,
    en su propio desplegable— y la encontro el guardia que se escribio al descubrir que
    eran dos: `_filter_columns` es el unico sitio que emite el estado por filtro de una
    fila, asi que todo el que lo llame tiene que pasar por `_with_stores`. Arreglar las
    tablas de una en una es como estuve dos tandas.
    """
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
            **_with_stores(
                _filter_columns(w), stores, species, w.window.start
            ),
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


# ─── El mismo mapa, en caracteres, para el informe ───────────────────────────
#
# El SVG se ve en la pagina y no entra en el documento: el informe sale en markdown,
# `.docx` y `.pdf`, y ese PDF se escribe a mano con las fuentes base-14 — no incrusta
# imagenes. Al documento llegaba un RESUMEN (cuantos elementos por tipo), que deja ver
# que un mapa se quedo sin candidatos y NO deja ver lo unico para lo que el mapa sirve:
# si los candidatos estan repartidos o apelotonados y que tramos quedan vacios.
#
# Un mapa de caracteres se dibuja UNA vez y sale igual en los tres formatos, que es
# exactamente la garantia que se pide: todo a la misma escala, y la misma escala en los
# tres. Y por eso es ASCII puro — el PDF codifica en WinAnsi y sustituye lo que no
# tiene, asi que un simbolo fuera de tabla desalinearia las columnas en un formato y no
# en los otros.

#: Columnas de la pista. Con el `pre` del PDF a cuerpo 7 caben 120 caracteres por linea;
#: 100 de pista mas la etiqueta del carril entra sin partirse, y una linea partida deja
#: de estar a escala, que es el mapa roto.
MAP_TEXT_WIDTH = 100

#: Ancho de la etiqueta del carril. Fijo: si cada carril rotula con lo que le cabe, los
#: carriles dejan de empezar en la misma columna y la escala se pierde.
MAP_TEXT_GUTTER = 8

WHY_THE_MAP_IS_CHARACTERS = (
    "El mapa del informe es de CARACTERES y no el SVG de la página: el PDF de este "
    "proyecto se escribe con las fuentes base-14 y no incrusta imágenes, así que un "
    "mapa dibujado saldría en un formato y no en los otros. En caracteres se dibuja una "
    "vez y sale igual en los tres — todo a la misma escala, y la misma escala en "
    "markdown, en `.docx` y en `.pdf`."
)


def _map_columns(utr_length: int) -> list[float]:
    """La escala, en UN solo sitio: nt por columna."""
    return [utr_length / MAP_TEXT_WIDTH]


def map_text(
    report: TilingReport,
    selection: ReportSelection,
    conservation: ConservationReport | None = None,
    species: str | None = None,
) -> str:
    """El mapa del 3'UTR en caracteres. Todos los carriles, a la MISMA escala.

    Mismo marco y misma frontera que `map_svg` —salen de `report.frame` y
    `report.utr3_of`— y por el mismo motivo: lo tilado puede ser el transcrito entero.
    Ver `WHY_THE_MAP_RECEIVES_THE_FRAME`.
    """
    largo = report.utr3_length
    marco = report.frame
    escala = largo / MAP_TEXT_WIDTH

    def columna(posicion: int) -> int:
        return min(
            MAP_TEXT_WIDTH - 1,
            max(0, round((posicion - 1) / max(1, largo - 1) * (MAP_TEXT_WIDTH - 1))),
        )

    def carril(etiqueta: str, marcas: dict[int, str], relleno: str = " ") -> str:
        pista = [relleno] * MAP_TEXT_WIDTH
        for col, ch in sorted(marcas.items()):
            if 0 <= col < MAP_TEXT_WIDTH:
                pista[col] = ch
        return f"  {etiqueta:<{MAP_TEXT_GUTTER}}" + "".join(pista)

    fuera = 0

    def en_utr3(posicion: int) -> int | None:
        return report.utr3_of(posicion)

    def nota(texto: str) -> list[str]:
        """Parte una nota para que NINGUNA linea se salga del ancho del mapa.

        Una linea que el PDF parte deja de estar a escala, y con ella se descoloca todo
        lo que va debajo. El limite es el del mapa, no el del PDF: asi las tres salidas
        —markdown, `.docx` y `.pdf`— parten por el mismo sitio.
        """
        limite = MAP_TEXT_WIDTH + MAP_TEXT_GUTTER - 2
        return ["  " + l for l in textwrap.wrap(texto, limite) or [""]]

    lineas: list[str] = []

    # Escala: una regla con la posicion cada diez columnas.
    regla = [" "] * MAP_TEXT_WIDTH
    numeros = [" "] * MAP_TEXT_WIDTH
    for col in range(0, MAP_TEXT_WIDTH, 10):
        regla[col] = "|"
        texto = str(max(1, round(col * escala) + 1))
        for i, ch in enumerate(texto):
            if col + i < MAP_TEXT_WIDTH:
                numeros[col + i] = ch
    lineas.append(f"  {'nt':<{MAP_TEXT_GUTTER}}" + "".join(numeros))
    lineas.append(f"  {'':<{MAP_TEXT_GUTTER}}" + "".join(regla))

    # Tercios, con su frontera EN LA COLUMNA que le toca.
    # LOS LIMITES SALEN DE `tercio_counts`, no se vuelven a dividir aquí: dos cuentas
    # del mismo corte pueden separarse, y entonces el mapa dibujaría una frontera que
    # la cuota no usa. Es el mismo criterio que la banda de corte.
    from .selection import tercio_counts  # noqa: PLC0415

    limites_tercios = tercio_counts(report).bounds
    tercios = [" "] * MAP_TEXT_WIDTH
    cortes = [columna(limites_tercios[0][1]), columna(limites_tercios[1][1])]
    tramos = [(0, cortes[0]), (cortes[0] + 1, cortes[1]), (cortes[1] + 1, MAP_TEXT_WIDTH - 1)]
    for (a, b), nombre in zip(tramos, ("proximal", "medio", "distal"), strict=True):
        ancho = b - a + 1
        etiqueta = nombre if len(nombre) <= ancho - 2 else nombre[: max(0, ancho - 2)]
        relleno = "-" * ancho
        if etiqueta:
            hueco = (ancho - len(etiqueta)) // 2
            relleno = "-" * hueco + etiqueta + "-" * (ancho - hueco - len(etiqueta))
        for i, ch in enumerate(relleno):
            tercios[a + i] = ch
    for corte in cortes:
        tercios[corte] = "|"
    lineas.append(f"  {'tercios':<{MAP_TEXT_GUTTER}}" + "".join(tercios))

    # Zonas enmascaradas.
    if report.mask is not None:
        mascara: dict[int, str] = {}
        for inicio, fin in report.mask.intervals:
            u1, u2 = en_utr3(inicio), en_utr3(min(fin, report.utr_length))
            if u1 is None and u2 is None:
                fuera += 1
                continue
            u1 = 1 if u1 is None else u1
            u2 = largo if u2 is None else u2
            for col in range(columna(u1), columna(u2) + 1):
                mascara[col] = "~"
        lineas.append(carril("mascara", mascara))

    # Bloques conservados. Sin conservacion el carril NO desaparece: lo dice.
    if conservation is not None and species is not None:
        bloques: dict[int, str] = {}
        for bloque in conservation.blocks:
            for hit in bloque.hits:
                if hit.species != species:
                    continue
                for col in range(columna(hit.start), columna(min(hit.end, largo)) + 1):
                    bloques[col] = "#"
        lineas.append(carril("conserv", bloques))
    else:
        lineas.append(
            f"  {'conserv':<{MAP_TEXT_GUTTER}}"
            "NOT_RUN: no se ha dado informe de conservación para esta especie."
        )

    # Señales de poliadenilacion, y SU BANDA DE CORTE en el carril de debajo.
    señales: dict[int, str] = {}
    banda: dict[int, str] = {}
    desbordadas = 0
    for signal in report.signals:
        posicion = en_utr3(signal.position)
        if posicion is None:
            fuera += 1
            continue
        # LA VIA IMPORTA Y SE VE. `A` a secas dice lo mismo de dos cosas que no se
        # parecen: una señal con uso MEDIDO y una clasificada por canonicidad SIN UN
        # SOLO DATO de uso. Es la distincion que `classification_label` ya lleva pegada
        # a la clase, traida al mapa — que es donde se mira el reparto.
        señales[columna(posicion)] = (
            "T" if signal.classification.name == "TERMINAL_PROBABLE"
            else ("M" if signal.evidence == "medida" else "A")
        )
        # LA BANDA DE CORTE PUEDE SALIRSE DEL TRANSCRITO, y no es un error: el corte
        # de una señal terminal cae 10-30 nt aguas abajo de un hexámero que ya está
        # cerca del final. Se recorta a lo que hay y se CUENTA lo que se sale, en vez
        # de abortar la conversión con una posición que no existe.
        desde, hasta = cleavage_band(signal)
        if desde > report.utr_length:
            desbordadas += 1
            continue
        if hasta > report.utr_length:
            desbordadas += 1
            hasta = report.utr_length
        u1, u2 = en_utr3(desde), en_utr3(hasta)
        if u1 is None and u2 is None:
            continue
        u1 = 1 if u1 is None else u1
        u2 = largo if u2 is None else u2
        for col in range(columna(u1), columna(u2) + 1):
            banda[col] = "="
    lineas.append(carril("polyA", señales))
    lineas.append(carril("corte", banda))

    # Candidatos, NUMERADOS por su puesto en el panel.
    elegidos = sorted(selection.selection.chosen, key=lambda c: c.start)
    candidatos: dict[int, str] = {}
    pie: list[str] = []
    for indice, choice in enumerate(elegidos, start=1):
        posicion = en_utr3(choice.start)
        if posicion is None:
            fuera += 1
            continue
        col = columna(posicion)
        marca = str(indice)
        for i, ch in enumerate(marca):
            candidatos.setdefault(col + i, ch)
        pie.append(f"{indice}={coords.label(choice.start, marco)}")
    lineas.append(carril("cand", candidatos))

    lineas.append("")
    lineas.extend(nota(
        f"3'UTR de {largo} nt en {MAP_TEXT_WIDTH} columnas — "
        f"{escala:.1f} nt por columna (marco de lo tilado: {marco.value})."
    ))
    lineas.extend(nota(
        "M = señal polyA con uso MEDIDO · A = señal polyA por canonicidad, sin dato "
        "de uso · T = terminal probable · = banda de corte (10-30 nt aguas abajo del "
        "hexámero) · # = bloque conservado · ~ = repetición enmascarada · dígito = "
        "candidato, por su puesto en el panel."
    ))
    if fuera:
        lineas.extend(nota(f"{fuera} elemento(s) FUERA del 3'UTR, no dibujados."))
    if desbordadas:
        lineas.extend(nota(
            f"{desbordadas} banda(s) de corte se salen del transcrito anotado: el "
            f"corte de una terminal cae aguas abajo del final. Van recortadas."
        ))
    # Los candidatos, con su coordenada: en la pista solo cabe el numero.
    if pie:
        actual = "  "
        for entrada in pie:
            if len(actual) + len(entrada) + 2 > MAP_TEXT_WIDTH + MAP_TEXT_GUTTER:
                lineas.append(actual.rstrip())
                actual = "  "
            actual += entrada + "  "
        lineas.append(actual.rstrip())
    return "\n".join(l.rstrip() for l in lineas)


def wrap_for_map(lines) -> list[str]:
    """Parte líneas de prosa al ancho del mapa, RESPETANDO su sangría.

    La cobertura por tercios va al lado del mapa y en el mismo bloque preformateado: su
    sangría es jerarquía —el tramo y sus detalles— y un `bullets` la aplana, mientras
    que dejarla sin partir hace que el PDF corte las frases por la mitad. Se parte por
    el mismo sitio en los tres formatos, que es la misma garantía que da el mapa.
    """
    limite = MAP_TEXT_WIDTH + MAP_TEXT_GUTTER
    salida: list[str] = []
    for linea in lines:
        sangria = " " * (len(linea) - len(linea.lstrip()))
        trozos = textwrap.wrap(
            linea.strip(), max(20, limite - len(sangria) - 2)
        ) or [""]
        salida.append(f"  {sangria}{trozos[0]}".rstrip())
        salida.extend(f"    {sangria}{t}".rstrip() for t in trozos[1:])
    return salida


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


#: Por que el fragmento NO se emite sin el casete. No es un extra que falte: los
#: extremos del fragmento son los de la FEATURE ANOTADA, y esos se derivan del casete.
#: Emitirlo sin el seria emitir un fragmento con unos extremos que nadie ha comprobado,
#: que es exactamente lo que borra 10 nt de exon al pegar.
FRAGMENT_NEEDS_CASSETTE = (
    "NOT_RUN: no hay casete conectado, así que no se emite ningún fragmento de "
    "síntesis. Los extremos del fragmento son los de la FEATURE ANOTADA del intrón y "
    "se DERIVAN del casete —contexto exónico incluido—; sin él saldrían unos extremos "
    "que nadie ha comprobado, y pegar eso sobre la selección de SnapGene borra exón sin "
    "dar ningún error hasta secuenciar. Se sube `aav_casete.fa` por el panel de "
    "referencia y sale."
)


def _intron_names(intron: str | tuple[str, ...] | None) -> tuple[str, ...]:
    """UNA o VARIAS arquitecturas, resueltas en un solo sitio.

    Aquí y no en cada llamador porque el CLI las recibe separadas por comas, la página
    por una lista y el núcleo por una cadena: tres formas de decir lo mismo y una sola
    de leerlo.

    `None` = LAS DEL REGISTRO que se pueden montar, que es lo que se pide por defecto
    desde el 2026-09-06: el primer experimento es cruzado por diseño. Se derivan de
    `introns.buildable()`, así que un intrón retirado sale solo y uno nuevo entra solo.
    """
    from .fragmento import default_introns  # noqa: PLC0415

    if intron is None:
        return default_introns()
    if isinstance(intron, str):
        nombres = [t.strip() for t in intron.split(",") if t.strip()]
    else:
        nombres = [str(t).strip() for t in intron if str(t).strip()]
    if not nombres:
        raise ShmirDesignError(
            "No se ha dado ninguna arquitectura de intrón para el fragmento. Se aborta "
            "en vez de emitir con una por defecto que nadie pidió."
        )
    return tuple(dict.fromkeys(nombres))


def _start_label(selection: ReportSelection, start: int) -> str:
    """La etiqueta de una posición del panel CON su marco, derivado de la anatomía que
    viaja con la selección.

    No `report.frame` —`ReportSelection` no lleva el informe— ni `Frame.UTR3` a secas:
    con un tilado del transcrito eso etiqueta `tx:1684` como `3utr:1684` y `coords`
    aborta la corrida entera, que es exactamente lo que pasó la primera vez que esto se
    escribió sin mirar de dónde salía el marco.

    Y hay un caso en que NO aborta y es peor: `selection_warnings` escribía la etiqueta
    a mano y emitía `3utr:1398` por `tx:1398`. Sobre el 3'UTR murino de 1242 nt esa
    posición es imposible, pero el techo del invariante se deriva del 3'UTR más largo
    que conoce el proyecto —1606, que lo pone el humano— así que cabe y pasa. El
    invariante caza lo imposible, no lo equivocado (principio nº 9): por eso la etiqueta
    se pide aquí en vez de construirse con una f-string en cada sitio que imprime.
    """
    return coords.label(start, coords.tiled_frame(selection.anatomy))


def _candidate_label(selection: ReportSelection, choice) -> str:
    """La etiqueta de un candidato. Delega: una sola definición del marco."""
    return _start_label(selection, choice.start)


def fragment_bundle(
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    *,
    species: str,
    cassette: str | None,
    intron: str | tuple[str, ...] | None = None,
    with_sites: bool = False,
    tiling=None,
    stores=None,
) -> dict[str, str]:
    """El fragmento de síntesis de cada candidato elegido: FASTA y hoja de pedido.

    Toda la decision vive aqui, no en la pagina (regla 6). Sin casete se emite la hoja
    IGUAL, diciendo por que esta vacia: un fichero que no aparece no se distingue de uno
    que nadie ha pedido.

    `intron` admite VARIAS arquitecturas y entonces sale la matriz entera —candidatos x
    intrones—, que es como esta planteado el primer experimento: *«cruzado por diseño,
    guías x intrones, para no descubrir con una sola guía que el problema era el
    intrón»* (responsable del proyecto, 2026-09-06). El defecto sigue siendo UNA, porque
    doblar lo que se manda a sintetizar es una decision de presupuesto y se pide.
    """
    from .fragmento import (
        build_fragment,
        fragment_order_sheet,
        fragments_fasta,
    )

    if not cassette:
        return {f"{species}_fragmentos.txt": FRAGMENT_NEEDS_CASSETTE}
    fragmentos = []
    for choice in selection.selection.chosen:
        ventana = selection.window_of(choice)
        # SIN `tiling` no se inventa una lista vacia: `None` es «nadie ha preguntado» y
        # la hoja lo DICE con otra frase. Un `()` aqui haria que un candidato que nadie
        # ha comprobado saliera identico a uno limpio, y esto es lo que se sintetiza.
        frentes = (
            None if tiling is None
            else candidate_fronts(
                tiling, selection, species=species, start=choice.start, stores=stores,
            )
        )
        for nombre in _intron_names(intron):
            fragmentos.append(
                build_fragment(
                    build_hairpin(
                        ventana.evaluation.guide.replace("U", "T"), scaffold=scaffold
                    ),
                    cassette=cassette,
                    intron=nombre,
                    with_sites=with_sites,
                    label=_candidate_label(selection, choice),
                    fronts=frentes,
                )
            )
    return {
        f"{species}_fragmentos.fasta": fragments_fasta(fragmentos, species=species),
        f"{species}_fragmentos.txt": "\n\n".join(
            fragment_order_sheet(f) for f in fragmentos
        ),
    }


def fragment_rows(
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    *,
    cassette: str | None,
    intron: str | tuple[str, ...] | None = None,
    with_sites: bool = False,
) -> list[dict[str, object]]:
    """Una fila por fragmento —candidato x intrón—, con lo que mirar antes de pegar."""
    from .fragmento import build_fragment

    if not cassette:
        return []
    filas: list[dict[str, object]] = []
    for choice in selection.selection.chosen:
        ventana = selection.window_of(choice)
        for nombre in _intron_names(intron):
            fragmento_ = build_fragment(
                build_hairpin(
                    ventana.evaluation.guide.replace("U", "T"), scaffold=scaffold
                ),
                cassette=cassette,
                intron=nombre,
                with_sites=with_sites,
                label=_candidate_label(selection, choice),
            )
            filas.append(
                {
                    "candidato": fragmento_.label,
                    "intron": fragmento_.intron_name,
                    "longitud": len(fragmento_.sequence),
                    "crece": fragmento_.growth,
                    "sustituye": (
                        f"{fragmento_.feature.start}-{fragmento_.feature.end}"
                    ),
                    "inicio_15": fragmento_.head(),
                    "final_15": fragmento_.tail(),
                    "md5": fragmento_.md5,
                    "veredicto": fragmento_.verdict.value,
                    **{f"check:{r.name}": r.state.value for r in fragmento_.checks},
                }
            )
    return filas


#: Lo que hace falta para comprobar un montaje, dicho en la pagina. NO es un fallo:
#: comprobar el vector montado es un paso posterior al diseño y sin sus dos ficheros no
#: se ha corrido nada — NOT_RUN, no PASS.
ASSEMBLY_NEEDS_BOTH = (
    "NOT_RUN: para comprobar el plásmido montado hacen falta las dos cosas — el "
    "fichero del vector (GenBank, FASTA, secuencia pelada o `.dna` de SnapGene) y el "
    "FASTA de fragmentos que emitió esta app. Se compara POR SECUENCIA: se busca el "
    "fragmento dentro del vector y se contrasta letra por letra, así que una feature "
    "corrida un nucleótido no engaña a la comprobación."
)


def assembly_report(
    plasmid,
    fragments_fasta_text: str,
    *,
    name: str = "",
    before_pasting: bool = False,
    architecture_change: bool = False,
):
    """La comprobación del montaje, para que la página sólo tenga que enseñarla.

    Vive aquí y no en la interfaz porque decide cosas: qué se compara, contra qué intrón
    previo y con qué veredicto (regla 6).

    `before_pasting` cambia LA PREGUNTA, no el rigor: sobre el plásmido receptor se
    pregunta «¿va este fragmento aquí?» y sobre el montado «¿está dentro lo que
    emitimos?». La primera no se puede hacer después — al pegar, el intrón anterior
    desaparece y con él la casilla de la matriz.
    """
    from .montaje import check_before_pasting, verify_assembly

    if before_pasting:
        return check_before_pasting(
            plasmid, fragments_fasta_text,
            architecture_change=architecture_change,
            name=name or "el plásmido receptor",
        )
    return verify_assembly(
        plasmid, fragments_fasta_text, name=name or "el plásmido montado"
    )


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


def _choices_de(selection, starts) -> list:
    """DELEGA en `ReportSelection.choices_for`, que es quien tiene los dos conjuntos.

    Esta funcion resolvia bien —panel MAS sitios elegibles— y vivia en la capa que el
    nucleo no puede llamar, asi que `seed_scan`, `spliceai` y `blast_query` tenian cada
    uno la suya contra el panel a secas. La definicion buena era inalcanzable justo para
    quien la necesitaba (errata nº 107).
    """
    return selection.choices_for(starts)


def blast_candidate_rows(selection, *, species: str,
                         starts=None) -> list[dict[str, object]]:
    """Una fila por candidato, con los dos nombres de consulta ya construidos.

    `starts` es el ALCANCE (`scope_starts`). Sin él, el panel — que es lo que hacía antes
    y lo único que podía hacer: la lista salía del panel elegido y cada fila llevaba
    `panel: True` ESCRITO, así que la casilla «sólo los del panel» de la página no
    filtraba nada. Un control que no se distingue de uno que funciona es la errata nº 32.
    Ahora `panel` se DERIVA, que es lo que lo hace significar algo.
    """
    del_panel = {c.start for c in selection.selection.chosen}
    pedidos = del_panel if starts is None else set(starts)
    marco = coords.tiled_frame(getattr(selection, "anatomy", None))
    filas = []
    for choice in _choices_de(selection, pedidos):
        ventana = selection.window_of(choice)
        bloque = None
        filas.append(
            {
                "start": choice.start,
                # La ETIQUETA sale de aqui y no de la pagina: la casilla la pintaba con
                # un `3utr:` propio (regla 6 y errata nº 121 a la vez).
                "etiqueta": coords.label(choice.start, marco),
                # Derivados, como todo lo demas: estos ids son los que despues busca
                # la ficha, asi que una quinta copia del formato los desconectaria.
                "guia_id": query_name(species, choice.start, "guia"),
                "pasajera_id": query_name(species, choice.start, "pasajera"),
                "guia": ventana.evaluation.guide.replace("U", "T"),
                "pasajera": _passenger_dna(ventana.evaluation.guide),
                "asimetria": f"{choice.asymmetry:+.2f}",
                "veredicto": ventana.verdict.value,
                # DERIVADO, no escrito: con el alcance grande hay filas que NO son
                # del panel, y esa marca es lo unico que las distingue en pantalla.
                "panel": choice.start in del_panel,
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
    # RESUELVE CONTRA LOS ELEGIBLES, no contra el panel. Aqui habia un
    # `{c.start: c for c in selection.selection.chosen}` y un aborto, asi que el alcance
    # «todos los sitios elegibles» que ofrece el propio selector se rechazaba — dos
    # definiciones en el mismo flujo y ganaba la restrictiva (errata nº 107).
    por_inicio = {c.start: c for c in selection.choices_for(pedidos)}
    registros = []
    for inicio in pedidos:
        ventana = selection.window_of(por_inicio[inicio])
        guia = ventana.evaluation.guide.replace("U", "T")
        # El NOMBRE lo pone `query_name`, que usa el SLUG. Aqui iba el nombre que se
        # pinta —`Mus musculus`— y BLAST corta `qseqid` en el primer espacio: las veinte
        # consultas llegaban al resultado como `Mus`. Ver errata nº 42.
        if guides:
            registros.append((query_name(species, inicio, "guia"), guia))
        if passengers:
            registros.append(
                (query_name(species, inicio, "pasajera"), _passenger_dna(
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


def blast_readiness(*, species, directory) -> list[dict[str, object]]:
    """Lo que le falta a ESTA corrida, dicho ANTES de pedir el fichero.

    Lo pide el responsable del proyecto con el caso delante: si algo va a quedarse sin
    cerrar, decirlo **antes** de bajarse una base de decenas de GB y echar horas de
    BLAST, no despues de guardar el resultado.

    Y lo que dice esta MEDIDO, no supuesto — que es la diferencia entre un aviso y el
    principio nº 3. Sin `refseq_rna.fa` en el deposito:

    - la corrida **si** llega a la tabla: su celda de `especificidad` pasa a tener
      veredicto. La corrida NO es inutil y el aviso no dice que lo sea;
    - el **frente** SI se cierra con la corrida, si cubre todo el panel (errata nº 68).
      Aqui ponia que lo cerraba «el filtro de la ventana, que necesita el catalogo
      cargado», y eso dejo de ser cierto ese dia — y ademas era el consejo justo al
      reves: una base de RefSeq de verdad NO entra en el filtro por ventana (errata
      nº 84, `specificity.scanner_budget`), asi que el catalogo cargado no cierra nada.
      Lo que el fichero SI da es la procedencia y la revalidacion de abajo;
    - y la corrida no se puede **revalidar**: sin md5 de hoy con el que comparar, sale
      «no se ha podido comprobar» cada vez que se mire (`insumos.obsoleta`).

    No BLOQUEA. Bloquear seria peor que el aviso al que sustituye: la corrida sirve.
    """
    from .insumos import fichero_de, insumos_de  # noqa: PLC0415
    from .presencia import ficheros_con_contenido  # noqa: PLC0415

    fichero = fichero_de(insumos_de("corrida_blast")[0], species)
    if directory is not None and fichero in ficheros_con_contenido(directory):
        return []
    return [{
        "bloquea": False,
        "texto": (
            f"**`{fichero}` NO está en el depósito**, y conviene saber qué cambia eso "
            f"ANTES de bajarse la base y lanzar el BLAST. La corrida **sí** sirve: al "
            f"subirla, los candidatos que consulte pasan a tener veredicto de "
            f"especificidad en la tabla, y **el frente se cierra** si la corrida cubre "
            f"todo el panel. Lo que el fichero da es otra cosa: la **procedencia** de la "
            f"base con la que se corrió. Y sin él la corrida quedará "
            f"sin poder revalidarse: sin el fichero no hay md5 de hoy con el que "
            f"comparar el que se registre, así que saldrá «no se ha podido comprobar» "
            f"cada vez que se mire. Es el mismo `{fichero}` del que sale la base: se "
            f"sube por el gestor y la ficha del frente dice de dónde bajarlo."
        ),
    }]


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
    # LOS PREDICHOS, en LOCAL, no se pueden afirmar. NO bloquea la corrida —una base
    # curada es perfectamente valida— pero el ajuste sale como `NOT_RUN` y con el motivo,
    # porque marcarlo como cumplido dejaria dos corridas, una remota y una local,
    # registradas igual. Ver `BlastParams.predicted_state`.
    from .filters import FilterState

    if params.predicted_state() is FilterState.NOT_RUN:
        avisos.append({
            "bloquea": False,
            "texto": (
                f"**predichos (`XM_`/`XR_`): NOT_RUN.** {params.predicted_reason()}"
            ),
        })
    # DE DONDE SALE EL FILTRO DE ORGANISMO en esta corrida. Sale siempre y no bloquea:
    # las dos vias son defendibles, y lo que no lo es es creer que la orden filtra
    # cuando no filtra. Ver `blast.BlastParams.organism_note`.
    if params.entrez_query:
        avisos.append({"bloquea": False, "texto": params.organism_note()})
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
            "candidato": coords.label(f.start, f.frame),
            "start": f.start,
            "hebra": f.strand,
            "secuencia": f.sequence,
            "heptamero": f.heptamer,
            "comparte": ", ".join(
                coords.label(s, f.frame) for s in f.shared_with
            ),
            "nucleo": f.core,
            # Columna PROPIA: compartir nucleo sin compartir heptamero es otro eje, y
            # meterlo en «comparte» lo habria escondido debajo de la colision de seed.
            "comparte_nucleo": ", ".join(
                coords.label(s, f.frame) for s in f.shared_core_with
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
                    + ", ".join(
                        f"{coords.label(r.start, r.frame)} ({r.strand})"
                        for r in con_mir30
                    )
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


#: POR QUE NO HAY —NI PUEDE HABER— UN PERCENTIL DE UN TOTAL, y hay que decirlo donde se
#: pide. `offtarget.WHY_NOT_SUMMED` prohibe sumar las clases porque la represion esperada
#: de un 8mer y la de un 6mer no se parecen en nada, asi que el percentil de una suma
#: seria el de una cantidad que este proyecto tiene decidido que no se refiere a nada.
#:
#: Lo que si se emite es CADA CLASE CON SU PERCENTIL PEGADO, que es la misma forma de
#: `reference.describe_sequence` («longitud y md5 JUNTOS»): una cifra comparativa no se
#: separa nunca de su referencia, porque quien copia una celda a un correo se lleva el
#: numero sin la cabecera.
#:
#: LA COLUMNA `carga_seed` YA NO EXISTE (2026-09-04). Era ese total, salia sin sus
#: sumandos y era la unica visible de este eje: ver `seed_load.WHERE_THE_TOTAL_WENT`.
WHY_NO_PERCENTILE_FOR_THE_TOTAL = (
    "Las clases no se suman: la represión esperada de un 8mer y la de un 6mer no se "
    "parecen en nada. Por eso no hay —ni puede haber— un percentil de un total: el "
    "percentil va POR CLASE, pegado a su conteo, y es lo que sale en las columnas "
    "`carga_<clase>`."
)

#: LAS DOS REFERENCIAS SON DISTINTAS Y NINGUNA SUSTITUYE A LA OTRA. La nula por
#: permutacion dice si un numero es RARO para esa composicion de heptamero; los controles
#: dicen que es «muchos sitios» EN BIOLOGIA. Un percentil alto sobre una carga pequeña y
#: una carga enorme dentro de lo esperable son cosas distintas, y hacen falta las dos para
#: leer la cifra.
WHY_BOTH_REFERENCES = (
    "Son DOS referencias y ninguna sustituye a la otra: el percentil contra la nula por "
    "permutación dice si el número es raro PARA ESA COMPOSICIÓN de heptámero, y los "
    "controles biológicos dan la MAGNITUD — qué es «muchos sitios» en un cerebro de "
    "verdad. Los controles no llevan percentil a propósito: se calcularía contra la nula "
    "de su propia composición, así que no sería comparable con el nuestro."
)


def seed_load_reference(*, stores, species: str, starts) -> dict[str, object]:
    """El percentil por clase y los controles que hacen legible `carga_seed`.

    **Reportado (2026-09-03)**: «carga_seed es la primera columna que discrimina de verdad
    —de 1.054 a 19.020, factor 18—. Pero le falta el percentil contra la nula por
    permutación y los controles de miR-124, miR-9 y let-7: sin ellos, 19.020 no se puede
    interpretar. Estaba en el diseño del modal y no aparece en el export.»

    Es la regla de redaccion del proyecto —**toda cifra comparativa con su referencia**—
    aplicada a la unica columna que seguia saliendo desnuda, y el principio nº 23 otra
    vez: la nula y los controles SE CALCULAN en el modal de off-targets y se guardan en el
    registro; lo que faltaba es que llegaran al artefacto que se lee.

    **No se recalcula nada aqui**, y no es pereza: la nula son ≥10.000 sorteos por
    consulta sobre un indice de 8-meros construido en una pasada por un fichero de 84 MB.
    Hacerlo en cada repintado de la pagina es exactamente la errata nº 59. Se LEE lo que
    la corrida ya guardo, que ademas es lo que garantiza que la tabla y el modal digan el
    mismo numero — dos calculos del mismo suceso acaban discrepando.

    Sin corrida, las celdas van VACIAS y el texto dice que falta: un numero comparativo
    que no se calculo va vacio, nunca a cero.
    """
    from .offtarget import CONTROL_NAMES, MISSING_FILE, SITE_CLASSES

    almacen = (stores or {}).get("offtarget")
    por_candidato: dict[int, dict[str, str]] = {}
    ultima = None
    # SIN ALMACEN NO SE PREGUNTA NADA, y por eso tampoco se resuelve la especie: la clave
    # de consulta la necesita quien busca en el registro, y aqui no hay registro. Sin este
    # corte, una tabla pedida sin especie —que es un camino legitimo, el del CLI— abortaba
    # al derivar una clave para la que no hay nada que buscar.
    for inicio in (starts if almacen is not None else ()):
        consulta = query_name(species, int(inicio), "guia")
        corrida = almacen.latest(consulta) if almacen is not None else None
        if corrida is None:
            continue
        resultado = corrida.result_for(consulta)
        if resultado is None:
            continue
        # EL CONTEO Y SU PERCENTIL, EN LA MISMA CELDA. Separarlos en dos columnas es lo
        # que hace que alguien copie el numero solo, que es el fallo que esto cierra.
        por_candidato[int(inicio)] = {
            clase: (
                f"{resultado.counts.sites[clase]} "
                f"(p{resultado.percentiles[clase]:.1f})"
            )
            for clase in SITE_CLASSES
        }
        ultima = corrida

    controles = [
        {
            "nombre": control.name,
            "heptamero": control.heptamer,
            **{clase: control.sites[clase] for clase in SITE_CLASSES},
        }
        for control in (ultima.scan.controls if ultima is not None else ())
    ]

    if ultima is None:
        texto = (
            f"CARGA DE SEED SIN REFERENCIA — NOT_RUN. Los conteos por clase del tilado "
            f"(`tilado_<clase>`) están, y solos no se pueden leer: falta el PERCENTIL "
            f"contra la nula por permutación, falta el `6mer` y "
            f"faltan los controles biológicos ({', '.join(CONTROL_NAMES)}). Los dos los "
            f"calcula el modal de carga de off-targets, que necesita "
            f"`{MISSING_FILE}` y una corrida guardada en el proyecto. "
            f"{WHY_BOTH_REFERENCES} {WHY_NO_PERCENTILE_FOR_THE_TOTAL}"
        )
    else:
        texto = (
            f"Percentiles y controles de la corrida {ultima.run_id} ({ultima.date}), "
            f"sobre {ultima.source}. {WHY_BOTH_REFERENCES} "
            f"{WHY_NO_PERCENTILE_FOR_THE_TOTAL}"
        )

    return {
        "hay": ultima is not None,
        "por_candidato": por_candidato,
        "controles": controles,
        "clases": tuple(SITE_CLASSES),
        "texto": texto,
    }


def seed_load_columns(*, stores, species: str, start: int, reference=None) -> dict[str, str]:
    """Las celdas `carga_<clase>` de UNA fila. Vacias si no hay corrida, nunca a cero."""
    from .offtarget import SITE_CLASSES

    vista = reference if reference is not None else seed_load_reference(
        stores=stores, species=species, starts=(start,)
    )
    celdas = vista["por_candidato"].get(int(start), {})
    return {f"carga_{clase}": celdas.get(clase, "") for clase in SITE_CLASSES}


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
            "candidato": coords.label(r.start, r.frame),
            "hebra": r.strand,
            "heptamero": r.heptamer,
            "ventana": r.window,
            # LA TASA BASE, EN LA FILA. Estaba solo en el aviso de encima de la tabla, y
            # ese se lee UNA vez mientras la fila se lee siempre — y peor: quien se lleva
            # el CSV se lleva las filas y no el aviso. Sin ella no se sabe si un LIMPIO
            # es notable o es lo que predice el azar, que es justo lo que este proyecto
            # tiene decidido que no puede faltar «tambien en los LIMPIO, para no dar una
            # falsa calma».
            "tasa_base": scan.base_rate.short,
            # EL VEREDICTO, no el estado a secas: con una ventana no estándar lleva la
            # ventana pegada. La cabecera se lee una vez y esta celda se descarga.
            "nivel": r.verdict,
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
            "candidato": coords.label(r.start, r.frame),
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


#: La SEGUNDA FUENTE que se retiró (errata nº 103). `front_help_rows` emitía el motivo y
#: la ficha de cada frente llamando a `blocking_fronts` **sin `closed_by_panel`**, así que
#: sobre una tarjeta pintada en verde ponía el motivo y las instrucciones del frente
#: ABIERTO — las dos cosas con pinta de dato. Lo que la sustituye no es otra función: es
#: que la propia tarjeta (`front_card_rows`) traiga su motivo y su ficha, para que no
#: puedan discrepar por construcción.
WHERE_THE_HELP_ROWS_WENT = (
    "`front_help_rows` ya no existe. Emitía el motivo y la ficha de cada frente por su "
    "cuenta, sin saber cuáles cierra el panel, y era la segunda definición del mismo "
    "hecho. Los dos campos los trae ahora cada tarjeta de `front_card_rows`: "
    "`motivo`/`resultado` y `ficha_titulo`/`ficha_texto`."
)


# ─────────────────── el informe como documento: parcial o completo ────────────────


def informe_documento(selection, tiling, *, species: str, generated: str,
                      anatomy_source: str = "no declarada en esta corrida",
                      dossier_starts=None, anatomy=None, stores=None,
                      conservation=None):
    """El documento entero. Parcial o completo segun los frentes, nunca dos productos.

    `anatomy` es OPCIONAL y no por comodidad: hay caminos que no la tienen —el CLI la
    deriva y otros la reciben declarada—, y un informe sin ella sigue siendo valido. Con
    ella entra la tabla de la anatomia del transcrito, la MISMA que pinta la pagina.
    """
    from .informe_doc import build_document

    return build_document(
        species=species, tiling=tiling, selection=selection, generated=generated,
        anatomy_source=anatomy_source, dossier_starts=dossier_starts, anatomy=anatomy,
        stores=stores, conservation=conservation,
    )


#: COMO SE LLAMA CADA BOTON DE DESCARGA DEL INFORME, y por que no se llama como el
#: fichero. Los tres botones se etiquetaban con el nombre del entregable
#: —`mouse_informe_parcial.docx`— asi que la seccion no se leia como «aqui se descarga el
#: informe» sino como una lista de ficheros sueltos: se reporto como «no encuentro donde
#: se descarga el informe» con los tres botones en pantalla. Misma leccion que
#: `BUTTON_DESIGN`: un boton se llama por lo que HACE. El nombre del fichero no se pierde
#: —va debajo, en la ayuda— porque es lo que luego hay que buscar en Descargas.
#:
#: El orden es Word, PDF y markdown: los dos primeros son los que se mandan y se imprimen,
#: y el markdown es la FUENTE, para discutir una frase sin maquetar. Alfabetico pondria
#: `.docx` antes que `.md` por casualidad y `.pdf` el ultimo sin ninguna razon.
INFORME_LABELS = (
    (
        "docx",
        "Descargar el informe en Word (.docx)",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ("pdf", "Descargar el informe en PDF", "application/pdf"),
    ("md", "Descargar el texto sin maquetar (.md)", "text/markdown"),
)


#: UN ENTREGABLE QUE FALLA NO SE LLEVA A LOS DEMAS. Reportado (2026-09-04): el `.docx`
#: abortaba porque su fecha venia de una clave que nadie escribia, y el aborto subia
#: hasta el `try` de `main()` —que pinta el motivo y hace `return`—, asi que se dejaban
#: de pintar los cuatro modales, «Descargas» y el paso 5. El error salia «en la seccion
#: del informe» porque ahi es donde el script se paraba.
#:
#: La regla es la misma que ya rige los frentes: un fallo se DICE, con su motivo entero
#: y en su sitio, y lo que no depende de el sigue funcionando. Esconder el boton roto
#: seria peor —quitaria la unica señal de que algo falla— asi que sale, con el motivo
#: en vez del boton.
DOWNLOAD_FAILED_NOTE = (
    "Este formato no se ha podido generar y el motivo va entero, aquí debajo. Los otros "
    "entregables de esta sección y el resto de la página no dependen de él: un fallo en "
    "una descarga no interrumpe nada más."
)


def informe_files(documento, *, stem: str):
    """Los tres entregables, ya con nombre, ETIQUETA y mime: `.docx`, `.pdf` y markdown.

    La pagina no decide el nombre, ni el formato, ni como se llama el boton: recibe
    `nombre`, `etiqueta`, `datos` y `mime` (regla 6). El markdown va tambien porque es la
    FUENTE de los otros dos — si alguien discute una frase del pdf, ahi esta el texto sin
    maquetar.

    **CADA FORMATO SE CONSTRUYE POR SEPARADO Y TRAE SU RESULTADO O SU MOTIVO**
    (`error`, vacio cuando ha ido bien). Antes se montaban los tres en una comprension,
    asi que uno que reventara se llevaba a los otros dos — y, sin guardia en la pagina,
    tambien todo lo que se pinta debajo. Ver `DOWNLOAD_FAILED_NOTE`.
    """
    from .docx_writer import to_docx
    from .pdf_writer import to_pdf

    marca = "parcial" if documento.state == "PARCIAL" else "completo"
    base = f"{stem}_informe_{marca}"
    contenido = {
        "md": lambda: documento.markdown().encode("utf-8"),
        "docx": lambda: to_docx(documento),
        "pdf": lambda: to_pdf(documento),
    }
    entregables = []
    for extension, etiqueta, mime in INFORME_LABELS:
        datos, motivo = None, ""
        try:
            datos = contenido[extension]()
        except (ShmirDesignError, ValueError, OSError) as exc:
            # rule2-ok: NO se traga nada — el motivo entero sale en `error` y la pagina
            # lo pinta EN EL SITIO de ese boton. Lo que se evita es que un formato roto
            # se lleve por delante a los otros dos y al resto de la pagina, que es lo
            # que pasaba: la excepcion subia al `try` de `main()`, que hace `return`.
            motivo = str(exc)
        entregables.append({
            "nombre": f"{base}.{extension}",
            "etiqueta": etiqueta,
            "datos": datos,
            "mime": mime,
            "error": motivo,
        })
    return entregables


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

    nombres: list[str] = []
    for frente in blocking_fronts(tiling, selection):
        declarado = STORE_FOR_FRONT.get(frente.name)
        if declarado and declarado["por_hebra"]:
            # DOS COLUMNAS, y no es formato: la pasajera es el eje donde menos datos hay
            # y fundirla con la guia la hace invisible. La ficha ya las partia; la tabla
            # decia «aqui la fila es el sitio» y con eso perdia una de las dos.
            nombres.extend(f"{frente.name}:{hebra}" for hebra in STRANDS)
        else:
            nombres.append(frente.name)
    return sorted(dict.fromkeys(nombres))


#: Que almacen contesta a que columna, y si su veredicto es POR HEBRA. Se declara —no se
#: adivina por el nombre— porque una corrida de BLAST cierra `especificidad` y NADA MAS:
#: si se propagara a otra columna, estaria contagiando un veredicto que nadie ha ganado.
#:
#: TENIA UNA SOLA FILA Y ESO PARECIA CONFIGURADO (2026-09-02). Los cuatro almacenes se
#: cargaban y solo BLAST llegaba a una columna, asi que `offtarget_seed` no tenia columna
#: con el transcriptoma delante y `verdicts_changed` decia 0 en tres de los cuatro
#: modales. Es el mismo disfraz que `UNDECIDED_FILTERS` con un miembro: una tabla de
#: declaracion con una fila no se lee como incompleta, se lee como decidida.
#: `tests/test_almacenes_declarados.py` lo cierra: todo frente con almacen tiene su fila.
#:
#: `por_hebra` NO es formato. La pasajera es el eje donde menos datos hay, y fundirla con
#: la guia en una columna la haria invisible — la ficha ya las parte y la tabla no lo
#: hacia. Un frente por hebra da DOS columnas, `<frente>:guia` y `<frente>:pasajera`.
STORE_FOR_FRONT = {
    "especificidad": {"almacen": "blast", "por_hebra": False},
    "seed_colision": {"almacen": "seed", "por_hebra": True},
    "offtarget_seed": {"almacen": "offtarget", "por_hebra": True},
}

#: Frentes con almacen que NO caben aqui, con el motivo. `empalme_sitios` se consulta por
#: PAR candidato x intron —`splice_store.verdict_for(start, intron)`—, que no es la clave
#: de consulta que usan los otros tres; darle una columna por candidato colapsaria justo
#: lo que ese frente existe para comparar. Se declara para que el test no lo eche de
#: menos en silencio, que es lo que dejo a `offtarget_seed` sin columna.
FRONTS_WITHOUT_COLUMN = {
    "empalme_sitios": (
        "su unidad es el par candidato x intrón, no el candidato: una columna por "
        "candidato colapsaria la comparación entre intrones, que es para lo que existe"
    ),
}


#: LO QUE FALTABA PARA QUE LA TABLA DE 270 FILAS SE PUEDA LEER (errata nº 55). «No se le
#: ha preguntado a este candidato» y «falta el fichero» decian las dos `NOT_RUN`, asi que
#: las 260 filas que nadie va a consultar nunca eran indistinguibles de las que esperan un
#: fichero. No es presentacion: son dos causas distintas y una se arregla consiguiendo
#: algo y la otra lanzando una corrida.
#:
#: Solo aparece cuando el proyecto YA tiene corridas de ese frente: sin ninguna, el estado
#: honesto sigue siendo `NOT_RUN` — nadie ha corrido nada, no es que este candidato se
#: haya quedado fuera.
SIN_CONSULTAR = "SIN_CONSULTAR"


def _with_stores(estados: dict, stores, species: str, start: int) -> dict:
    """Los estados de una fila, con lo que digan los almacenes encima. UN solo sitio."""
    if not stores:
        return estados
    return {
        nombre: (_store_state(stores, nombre, species, start) or estado)
        for nombre, estado in estados.items()
    }


def _store_state(stores, front: str, species: str, start: int) -> str | None:
    """El estado de ESE frente para ESE candidato segun los almacenes, o `None`.

    `None` significa «los almacenes no dicen nada de esto», que no es lo mismo que
    `NOT_RUN`: quien decide entonces es el filtro de la ventana, como siempre.
    """
    # Una columna por hebra llega como `<frente>:guia`. La hebra se saca del NOMBRE de la
    # columna, que es quien la lleva; el frente es lo de delante.
    nombre, _, hebra = front.partition(":")
    declarado = STORE_FOR_FRONT.get(nombre)
    if not declarado or not stores:
        return None
    if declarado["por_hebra"] and hebra not in STRANDS:
        # Un frente por hebra SIN hebra en la columna no se contesta: fundir las dos
        # seria dar por buena la de la pasajera con el estado de la guia.
        return None
    almacen = stores.get(declarado["almacen"])
    if almacen is None:
        return None
    consulta = query_name(species, start, hebra if declarado["por_hebra"] else "guia")
    # SIN CORRIDA PARA ESTE CANDIDATO, el almacen no dice nada — y `None` no es
    # `NOT_RUN`. Devolver su `NOT_RUN` lo hacia PISAR al filtro de la ventana: hoy no se
    # nota porque sin base cargada ese filtro tambien sale `NOT_RUN`, pero en cuanto
    # alguien deposite `refseq_rna.fa` un veredicto local de verdad quedaria sustituido
    # por un `NOT_RUN` del almacen. Es el mismo fallo latente que las cinco claves: no
    # se ve hasta que otra cosa cambia.
    if not almacen.history(consulta):
        # HAY CORRIDAS DE ESTE FRENTE PERO NINGUNA MIRO A ESTE CANDIDATO. No es lo mismo
        # que no haber corrido nada: se arregla lanzando una corrida que lo incluya, no
        # consiguiendo un fichero. Sin corridas de ningun tipo se devuelve `None` y manda
        # el filtro de la ventana, como siempre.
        return SIN_CONSULTAR if getattr(almacen, "runs", None) else None
    # LA ESPECIE VIAJA: decide que variantes de transcrito son la diana, y sin ella la
    # corrida no puede eximir su propio blanco (errata nº 56). Los otros tres almacenes
    # no tienen especie que pasar, asi que se MIRA LA FIRMA en vez de probar y cazar el
    # `TypeError`: eso se tragaria un `TypeError` de dentro del veredicto y repetiria la
    # llamada sin especie — un veredicto con la forma correcta, calculado con menos
    # informacion y sin que nadie se entere (regla 2).
    if "species" in inspect.signature(almacen.verdict_for).parameters:
        return almacen.verdict_for(consulta, species=species).state.value
    return almacen.verdict_for(consulta).state.value


#: Un frente se cierra CONSIGUIENDO LA RESPUESTA, no consiguiendo un `PASS`. Un `FAIL`
#: es una respuesta —el candidato cae— y deja el frente cerrado igual. Lo que NO cierra
#: es `NOT_RUN` ni `NO_CIERRA`: ahi no hay respuesta que leer.
#: LO QUE ES UNA LAGUNA. Se declara ESTO y lo demas se DERIVA (principio nº 13): una
#: lista de «los que responden» escrita a mano deja fuera al estado numero siete el dia
#: que se añada, y lo cuenta como hueco sin que nadie lo note.
#:
#: `SUSTITUIDO` y `NO_APLICA` SI son respuestas, y no es un detalle: el filtro `seed` sale
#: `SUSTITUIDO` en todo el panel cuando esta `mature.fa`, y `check_substitution` impide
#: que un `SUSTITUIDO` exista con su sustituto en `NOT_RUN`. Contarlos como laguna dejaba
#: abierto un frente que ya tiene respuesta.
ESTADOS_SIN_RESPUESTA = ("NOT_RUN", "SIN_CONSULTAR", "NO_CIERRA", "OBSOLETO")
ESTADOS_QUE_RESPONDEN = tuple(
    estado.value
    for estado in FilterState
    if estado.value not in ESTADOS_SIN_RESPUESTA
)


def verdict_with_stores(estados) -> str:
    """El veredicto de un candidato con los estados YA resueltos, almacenes incluidos.

    Existe porque la tabla pintaba la celda con lo que dicen los almacenes y la columna
    `veredicto` con lo que dice el informe de tilado: dos numeros del mismo suceso, uno
    al lado del otro y sin nada que los ate — la fila decia `especificidad: PASS` y
    `veredicto: INCOMPLETE`, las dos con pinta de medida.

    La agregacion NO se reimplementa: se construyen `FilterResult` con los estados
    efectivos y decide `filters.overall_verdict`, que es quien sabe que `NO_CIERRA`
    impide aprobar igual que `NOT_RUN`.
    """
    from .filters import FilterResult, FilterState, overall_verdict  # noqa: PLC0415

    resultados = [
        FilterResult(
            name=nombre,
            # SIN_CONSULTAR no es un `FilterState`: es una etiqueta de la TABLA que dice
            # por que no hay veredicto. Para agregar, bloquea igual que `NOT_RUN` — lo
            # que cambia es lo que hay que hacer, no si impide aprobar.
            state=FilterState(
                "NOT_RUN" if estado == SIN_CONSULTAR else estado
            ),
            # La regla 3 exige motivo TAMBIEN en PASS. Aqui el estado ya viene resuelto
            # —de la celda de la tabla— y el motivo largo vive en la ficha y en la
            # propia celda; esto solo agrega.
            reason=f"estado efectivo de la tabla: {estado}",
        )
        for nombre, estado in estados.items()
    ]
    return overall_verdict(resultados).value


def fronts_closed_over_panel(estados_por_frente, *, starts, origins=None) -> dict[str, str]:
    """Que frentes estan CONTESTADOS en todo el panel, y con que motivo.

    `estados_por_frente` es `{frente: {inicio: estado}}` — lo que dice cada candidato del
    panel, venga del fichero del deposito o de una corrida guardada. Sale de
    `panel_states_by_front`, que es el unico sitio donde se junta.

    **UN FRENTE SOLO SE CIERRA SI LO CUBRE TODO EL PANEL**, y esa mitad no se puede
    omitir: con seis candidatos contestados de diez, decir «frente cerrado» daria por
    comprobados cuatro que nadie miro. Es la misma regla que un `NOT_RUN` que no puede
    reportarse como aprobado, un piso mas arriba.

    Se llamaba `fronts_closed_by_runs` mientras solo miraba corridas. El nombre dejo de
    ser cierto en cuanto entraron los frentes que cierra un fichero, y un nombre que
    miente es el principio nº 27: se renombra en vez de ampliarle el significado.
    """
    return {
        frente: datos["motivo"]
        for frente, datos in run_coverage(
            estados_por_frente, starts=starts, origins=origins
        ).items()
        if datos["cerrado"]
    }


def run_coverage(estados_por_frente, *, starts, origins=None) -> dict[str, dict]:
    """CUANTOS candidatos del panel contesta cada frente, y si eso lo cierra.

    LA COBERTURA PARCIAL SE DICE. Sin esto, un frente consultado para 6 de 10 candidatos
    sale exactamente igual que uno que nadie ha tocado —tarjeta gris, «sin hacer»— y quien
    acaba de subir una corrida de horas ve la pantalla sin cambiar y concluye que la app
    no la ha recogido. La corrida SI esta y su celda de la tabla lo dice; lo que falta es
    que la tarjeta diga cuanto falta.

    `origins` es `{frente: {inicio: ORIGEN_*}}` y decide QUE TEXTO se escribe. Son dos
    causas distintas —una se arregla consiguiendo un fichero y la otra lanzando una
    corrida— asi que no pueden compartir motivo. Sin `origins` se asume corrida, que es
    lo unico que habia cuando esta funcion se escribio.
    """
    if not starts:
        return {}
    panel = sorted({int(s) for s in starts})
    origenes_por_frente = origins or {}
    salida: dict[str, dict] = {}
    for frente, por_candidato in (estados_por_frente or {}).items():
        cubiertos = [
            inicio for inicio in panel
            if por_candidato.get(inicio) in ESTADOS_QUE_RESPONDEN
        ]
        de_donde = {
            (origenes_por_frente.get(frente) or {}).get(inicio, ORIGEN_CORRIDA)
            for inicio in cubiertos
        }
        cerrado = len(cubiertos) == len(panel)
        if cerrado:
            motivo = _motivo_cerrado(len(panel), de_donde)
        elif cubiertos:
            motivo = _motivo_a_medias(panel, cubiertos, de_donde)
        else:
            motivo = ""
        # `motivo` y `avance` SON DOS PREGUNTAS y por eso son dos campos (errata nº 108).
        # `motivo` dice por que se cierra —y de ahi sale `frente.reason`, o sea el
        # resultado en VERDE—; `avance` dice CUANTO FALTA, que es para lo que se escribio
        # (errata nº 54: «6 de 10 no se pinta como uno sin tocar») y se pinta en AMBAR.
        # De un frente cerrado no falta nada, asi que ahi `avance` esta vacio: con el
        # mismo texto en los dos, la tarjeta decia lo mismo dos veces y en dos colores —
        # un ambar que dice «pendiente» debajo de un verde que dice «cerrado».
        salida[frente] = {
            "cerrado": cerrado,
            "cubiertos": len(cubiertos),
            "panel": len(panel),
            "motivo": motivo,
            "avance": "" if cerrado else motivo,
        }
    return salida


def _motivo_cerrado(panel: int, de_donde: set[str]) -> str:
    """De DONDE salio el cierre, con sus palabras. Nunca «corrida» de un fichero."""
    if de_donde == {ORIGEN_FICHERO}:
        return (
            f"CERRADO con lo que hay en el depósito: los {panel} candidatos del panel "
            f"tienen veredicto de este frente con el fichero que ya está cargado, sin "
            f"que haga falta ninguna corrida."
        )
    if de_donde == {ORIGEN_CORRIDA}:
        return (
            f"CERRADO por corrida guardada: los {panel} candidatos del panel "
            f"tienen veredicto de este frente en el registro del proyecto."
        )
    return (
        f"CERRADO: los {panel} candidatos del panel tienen veredicto de este frente — "
        f"unos con el fichero del depósito y otros por corrida guardada."
    )


def _motivo_a_medias(panel, cubiertos, de_donde: set[str]) -> str:
    """Contestado a medias. Y quien no contesta NO es siempre una corrida que falta."""
    faltan = [inicio for inicio in panel if inicio not in cubiertos]
    cola = (
        f"El frente NO se cierra con eso —darlo por cerrado daría por comprobados los "
        f"que nadie miró—, y lo que hay no se pierde: su veredicto está en la celda de "
        f"cada candidato cubierto. Faltan: "
        f"{', '.join(str(inicio) for inicio in faltan)}."
    )
    if de_donde == {ORIGEN_FICHERO}:
        return (
            f"EL FICHERO ESTÁ Y NO ALCANZA A TODO EL PANEL: {len(cubiertos)} de "
            f"{len(panel)} candidatos tienen veredicto de este frente y "
            f"{len(faltan)} no. {cola}"
        )
    return (
        f"HAY CORRIDA, PERO NO CUBRE EL PANEL: {len(cubiertos)} de "
        f"{len(panel)} candidatos tienen veredicto de este frente y "
        f"{len(faltan)} no. {cola}"
    )


def store_states_by_front(stores, *, species: str, starts) -> dict[str, dict[int, str]]:
    """`{frente: {inicio: estado}}` segun los ALMACENES. Una de las dos mitades.

    La otra es lo que dice el filtro de la ventana con el fichero del deposito delante;
    las dos se juntan en `panel_states_by_front`, que es de donde salen la celda y la
    tarjeta. Aqui solo esta el registro del proyecto.

    **LOS FRENTES POR HEBRA NO CONTESTABAN NADA** (2026-09-03). Se le preguntaba al
    almacen con el nombre PELADO del frente, y `_store_state` devuelve `None` para un
    frente por hebra sin hebra —a proposito: fundir las dos daria por buena la de la
    pasajera con el estado de la guia—. O sea que una corrida de seed o de off-targets
    que cubriera el panel entero **no cerraba su frente nunca**; solo la de BLAST podia.
    Coincide con lo que se observo —«la de especificidad es la unica verde»— y NO era la
    causa de aquello: es un fallo latente que el mismo reporte destapo.

    Un frente por hebra se contesta **con las dos**, o no se contesta.
    """
    salida: dict[str, dict[int, str]] = {}
    for frente, declarado in STORE_FOR_FRONT.items():
        columnas = (
            [f"{frente}:{hebra}" for hebra in STRANDS]
            if declarado["por_hebra"] else [frente]
        )
        por_candidato: dict[int, str] = {}
        for inicio in starts:
            estados = [
                _store_state(stores, columna, species, int(inicio))
                for columna in columnas
            ]
            if any(estado is None for estado in estados):
                # Los almacenes no dicen nada de esta hebra: manda el filtro de la
                # ventana, como siempre. `None` NO es `NOT_RUN`.
                continue
            por_candidato[int(inicio)] = _peor_de(estados)
        if por_candidato:
            salida[frente] = por_candidato
    return salida


def _peor_de(estados: list[str]) -> str:
    """El estado de un frente que llega por VARIAS columnas (una por hebra).

    Manda la laguna sobre la respuesta y el `FAIL` sobre el `PASS`. Nunca al reves:
    quedarse con la mejor de las dos hebras daria por buena la de la pasajera con el
    estado de la guia, que es lo que la ficha parte en dos filas para no hacer.
    """
    for estado in estados:
        if estado in ESTADOS_SIN_RESPUESTA:
            return estado
    return FilterState.FAIL.value if FilterState.FAIL.value in estados else estados[0]


#: DE DONDE SALE LA RESPUESTA de un candidato en un frente. Son dos causas distintas y
#: se arreglan con cosas distintas —una consiguiendo un fichero, la otra lanzando una
#: corrida—, asi que el motivo que se pinta no puede ser el mismo. Decir «cerrado por
#: corrida guardada» de un frente que nadie ha corrido manda a buscar en el registro del
#: proyecto, donde no hay nada.
ORIGEN_FICHERO = "fichero"
ORIGEN_CORRIDA = "corrida"


#: QUE SIGNIFICA cada laguna en la fila de un fragmento, en una línea. `origenes` da el
#: ORIGEN («fichero», «corrida»), que no es un motivo: puesto como motivo, la hoja decía
#: «especificidad — fichero» y eso no le dice nada a quien va a pedir el oligo.
#:
#: Se declara una frase POR ESTADO y se comprueba que no falte ninguno de
#: `ESTADOS_SIN_RESPUESTA`: un estado nuevo sin frase saldría mudo en el sitio donde más
#: caro es —la hoja de lo que se sintetiza— y nadie lo notaría, porque su producto normal
#: es una línea que parece completa.
LAGUNA_MEANING = {
    "NOT_RUN": (
        "no ha corrido para este candidato: falta el recurso o falta la corrida. "
        "NOT_RUN no es PASS"
    ),
    "SIN_CONSULTAR": (
        "hay corridas de este frente en el proyecto y a ESTE candidato no se le "
        "preguntó — que es distinto de que falte el fichero"
    ),
    "NO_CIERRA": (
        "hay corrida y NO cierra el frente: se arregla repitiéndola, no empezándola"
    ),
    "OBSOLETO": (
        "la corrida que lo contestaba quedó obsoleta porque el fichero que consumió "
        "ya no es el que hay"
    ),
}
_sin_frase = [e for e in ESTADOS_SIN_RESPUESTA if e not in LAGUNA_MEANING]
if _sin_frase:  # pragma: no cover - lo fija un test
    raise ShmirDesignError(
        f"Estos estados cuentan como laguna y no tienen frase en `LAGUNA_MEANING`: "
        f"{', '.join(_sin_frase)}. Sin ella saldrían mudos en la hoja de pedido."
    )


def _motivo_de_laguna(frente: str, estado: str, origen) -> str:
    """La línea que lee quien va a pedir el oligo: qué le falta a ESTE candidato."""
    frase = LAGUNA_MEANING[estado]
    if origen:
        return f"{frente}: {frase} (lo decide: {origen})."
    return f"{frente}: {frase}."


#: CUÁNTO SHA SE ENSEÑA. Corto para leerlo de un vistazo y comparable a ojo con lo que
#: dice GitHub; el entero viaja aparte, porque siete caracteres pueden ser ambiguos y
#: quien va a comparar de verdad necesita el completo.
BUILD_SHORT = 7

#: QUÉ HACER cuando el sello no cuadra con lo que se espera. Un sha a secas deja a quien
#: lo lee sin saber contra qué compararlo: es el principio nº 47 —la salida donde está el
#: bloqueo— aplicado al propio diagnóstico. La app NO puede saber cuál es el commit
#: «bueno», así que dice dónde mirarlo en vez de inventárselo.
BUILD_HELP = (
    "Si esto no coincide con el último commit de `main`, lo que estás viendo NO es lo "
    "último: el despliegue no se ha refrescado. Compáralo con el historial del "
    "repositorio; si coincide y aun así falta algo, entonces el problema no es el "
    "despliegue y hay que mirarlo por otro lado."
)

#: Y por qué se enseña TAMBIÉN cuando no hay variable. En local no la hay, y decir «sin
#: declarar» es información: lo que no puede pasar es que la ausencia del sello se lea
#: como que el sello coincide (principio nº 32).
BUILD_WHY_ALWAYS = (
    "El sello sale SIEMPRE, también cuando el entorno no declara ninguno. Un sello "
    "ausente y un sello que cuadra no se pueden parecer: la ausencia es lo que hay que "
    "poder ver."
)


#: LAS DOS ACCIONES, en un sitio. Estaban como literales sueltos en la página —el que se
#: escribe en `session_state`, el que se compara para pintar los pasos y el que decide si
#: se estima—, y una comparación a mano es lo que permitió que hubiera dos definiciones
#: de «se ha diseñado» (errata nº 124).
ACCION_DISENAR = "diseñar"
ACCION_ESTIMAR = "estimar"


def design_action(stored, *, resumed: bool):
    """Qué se va a hacer en esta corrida: `diseñar`, `estimar` o nada.

    **UNA sola definición**, y la falta de ella costó el paso 5 entero. Había dos: la que
    decide si se corre el diseño sabía que RETOMAR UN PROYECTO es ver su resultado —o sea,
    haber diseñado— y la que decide si el paso 5 es visible preguntaba sólo por el botón.
    Con un proyecto retomado, la primera decía «diseñar» y la segunda que no: se pintaban
    los cuatro modales y **no se pintaba la sección de ficheros de referencia**, que es la
    única vía alternativa cuando un modal falla.

    Es `resolve.py` otra vez: la misma pregunta contestada en dos sitios, y uno se entera
    de un camino nuevo y el otro no.

    `stored` MANDA cuando lo hay: retomar no puede pisar una estimación que se acaba de
    pedir. Sólo cuando no se ha pulsado nada, un proyecto retomado significa «diseñar».
    """
    if stored:
        return stored
    return ACCION_DISENAR if resumed else None


def build_banner() -> dict[str, object]:
    """QUÉ VERSIÓN está sirviendo esta página. Arriba, sin abrir nada.

    EL DATO YA ESTABA: `identidad.build_stamp()` lo lee de `SHMIR_BUILD`, que el hub pasa
    al proceso hijo desde `RAILWAY_GIT_COMMIT_SHA`. Su único consumidor era la cabecera
    del FASTA de consulta de SpliceAI — o sea que para saber qué versión servía la app
    había que generar un artefacto y abrirlo. Es el patrón de `page_run`: la capacidad
    cableada a un sitio y no al que la necesita.

    Y aquí lo que se pierde no es información, es TIEMPO AJENO: sin el sello en pantalla,
    «está fusionado» y «lo estás viendo» son indistinguibles desde la página, y la única
    forma de separarlos es que alguien vaya a mirar el despliegue. Pasó tres veces.
    """
    from .identidad import BUILD_NOT_DECLARED, build_stamp  # noqa: PLC0415

    commit = build_stamp()
    declarado = commit != BUILD_NOT_DECLARED
    corto = commit[:BUILD_SHORT] if declarado else commit
    return {
        "commit": commit,
        "corto": corto,
        "declarado": declarado,
        "texto": (
            f"Versión servida: **{corto}**" if declarado
            else f"Versión servida: **{BUILD_NOT_DECLARED}** — el entorno no la declara "
                 f"(es lo normal en local)."
        ),
        "ayuda": BUILD_HELP,
    }


def candidate_fronts(
    tiling, selection, *, species: str, start: int, stores=None,
) -> tuple[dict[str, str], ...]:
    """Los frentes SIN CONTESTAR de UN candidato, para su fila de la hoja de pedido.

    La unidad es el CANDIDATO y no el panel, y esa es toda la razón de que exista: el
    panel puede tener diez candidatos con corrida y uno sin ella —el caso del undécimo,
    `tx:2020`, que entró después del BLAST de los 88, del empalme y de la seed— y una
    nota general al principio de la hoja dice la verdad sobre el conjunto mientras cada
    fila se lee, se copia y se manda por separado.

    POR QUE IMPORTA MAS QUE OTROS `NOT_RUN`, con las palabras con que se pidió: *«un
    candidato sin BLAST en una hoja de once verificados es exactamente el hueco donde se
    cuela algo así»*. Y «algo así» tiene nombre — `tx:1746` contra **Adar**, el único
    candidato que ha caído por un motivo real, y lo atrapó este frente.

    Sale de `panel_states_by_front`, que es EL ÚNICO SITIO donde se decide si un frente
    está contestado. No se reimplementa aquí: sería la segunda regla para la misma
    pregunta, que es exactamente la errata nº 68.
    """
    inicio = int(start)
    if inicio not in {int(s) for s in chosen_starts(selection)}:
        raise ShmirDesignError(
            f"{inicio} no está en el panel de esta corrida, así que no tiene frentes que "
            f"emitir. Los del panel son: "
            f"{', '.join(str(s) for s in sorted(chosen_starts(selection)))}."
        )
    resuelto = panel_states_by_front(
        tiling, selection, species=species, stores=stores
    )
    estados, origenes = resuelto["estados"], resuelto["origenes"]
    filas = []
    # LOS FRENTES SIN COLUMNA POR CANDIDATO TAMBIEN SALEN, y no es un extra: si
    # `empalme_sitios` faltara de esta lista, la fila diria «sin contestar:
    # especificidad» y quien la lee concluye que el empalme SI esta contestado. Es
    # justo el fallo que esta seccion existe para impedir, un frente mas alla. Se
    # DERIVAN de `FRONTS_WITHOUT_COLUMN` y de los frentes abiertos, no se escriben.
    from .selection import blocking_fronts  # noqa: PLC0415

    abiertos = {
        f.name for f in blocking_fronts(tiling, selection) if f.blocking
    }
    for frente, porque in sorted(FRONTS_WITHOUT_COLUMN.items()):
        if frente not in abiertos:
            continue
        filas.append({
            "frente": frente,
            "estado": FilterState.NOT_RUN.value,
            "motivo": (
                f"{frente}: no tiene columna por candidato porque {porque}. Este "
                f"fragmento es uno de esos pares, y no consta consultado."
            ),
        })
    for frente in sorted(estados):
        estado = estados[frente].get(inicio)
        # `ESTADOS_SIN_RESPUESTA` es la MISMA lista con la que el panel decide si un
        # frente esta contestado. Escribirla otra vez aqui seria la segunda definicion
        # de que es una laguna, y la que se queda vieja el dia que entre un estado
        # nuevo — que es como `SIN_CONSULTAR` habria quedado fuera al nacer.
        if estado is None or estado not in ESTADOS_SIN_RESPUESTA:
            continue
        filas.append({
            "frente": frente,
            "estado": estado,
            "motivo": _motivo_de_laguna(
                frente, estado, origenes.get(frente, {}).get(inicio)
            ),
        })
    return tuple(filas)


def panel_states_by_front(
    tiling, selection, *, species: str, stores=None,
) -> dict[str, dict]:
    """Lo que dice CADA candidato del panel de CADA frente, y de donde sale.

    **ES EL UNICO SITIO donde se decide si un frente esta contestado**, y de aqui salen
    las dos cosas que discrepaban: la celda de la tabla y la tarjeta.

    El fallo que lo motiva (2026-09-03) es la errata nº 54 un consumidor mas alla. Habia
    **DOS reglas para la misma pregunta**: un frente cerrado por CORRIDA se decidia sobre
    el panel (`run_coverage`) y uno cerrado por FICHERO sobre las 2170 ventanas tiladas,
    via `ReportSelection.not_run_filters`. Y 1790 de esas ventanas ni llegan a los filtros con
    recurso porque ya cayeron antes — un `NOT_RUN` de una ventana descartada no es una
    laguna de nada, porque nadie iba a preguntarle. Resultado: `transgen` y
    `seed_colision` salian `PASS` en los diez del panel y sus tarjetas en gris.

    La unidad de la pregunta es **el panel**, para las dos. Y no se arregla la tarjeta:
    se junta el origen de las dos aqui, para que no puedan volver a separarse.

    Devuelve `{"estados": {frente: {inicio: estado}}, "origenes": {frente: {inicio: ...}}}`
    — una sola pasada y dos proyecciones, no dos calculos del mismo numero.
    """
    starts = [int(s) for s in chosen_starts(selection)]
    ventanas = {int(w.window.start): w for w in tiling.windows}
    estados: dict[str, dict[int, str]] = {}
    origenes: dict[str, dict[int, str]] = {}

    # 1. LO QUE DICE LA CELDA DE LA TABLA, letra por letra: `_filter_columns` —el unico
    #    sitio del que sale el estado por filtro de una fila— pasado por `_with_stores`,
    #    que es la misma expresion que pinta `candidate_rows`. Asi la tarjeta y la
    #    columna no pueden discrepar por construccion, no por coincidencia. De aqui sale
    #    lo que cierra un frente cuando su fichero esta en el deposito.
    for inicio in starts:
        ventana = ventanas.get(inicio)
        if ventana is None:
            continue
        efectivos = _with_stores(
            _filter_columns(ventana), stores, species, inicio
        )
        for frente, estado in efectivos.items():
            estados.setdefault(frente, {})[inicio] = estado
            origenes.setdefault(frente, {})[inicio] = ORIGEN_FICHERO

    # 2. LO QUE DICEN LOS ALMACENES, para dos cosas: MARCAR EL ORIGEN —«lo cerro una
    #    corrida» y «lo cerro el fichero» son dos causas y no pueden compartir texto— y
    #    contestar los frentes POR HEBRA, que `_with_stores` deja pasar a proposito
    #    (fundir las dos hebras en una columna daria por buena la de la pasajera con el
    #    estado de la guia). Para los demas, el paso 1 ya trae este mismo estado.
    for frente, por_candidato in store_states_by_front(
        stores, species=species, starts=starts
    ).items():
        for inicio, estado in por_candidato.items():
            estados.setdefault(frente, {})[inicio] = estado
            origenes.setdefault(frente, {})[inicio] = ORIGEN_CORRIDA

    return {"estados": estados, "origenes": origenes}


#: QUE HAY EN LA TABLA, dicho arriba. Sin esto, sus 270 filas se leen como si todas
#: fueran candidatos del panel — y las 260 que no lo son salen `NOT_RUN` con toda la
#: razon, porque nadie las ha consultado. La salida es correcta y la conclusion que
#: produce, falsa (errata nº 55).
TABLE_SCOPE_NOTE = (
    "Aquí salen TODOS los sitios elegibles, no sólo los del panel: un sitio que no se "
    "eligió sigue teniendo veredictos, y esconderlo dejaría sin poder discutir la "
    "selección. **Los del panel van arriba**, en el orden en que la app los eligió. En "
    "los demás, un `NOT_RUN` significa que **a ese candidato no se le ha preguntado** —"
    "las corridas se lanzan sobre el panel—, no que falte un fichero."
)


def panel_first(filas):
    """El panel ARRIBA y por rango; el resto detras, en su orden de posicion.

    La tabla enseña los ~270 sitios elegibles a proposito, y sólo los 10 del panel
    llevan las corridas. Repartidos entre los otros 260, lo que se ve al abrirla es
    `NOT_RUN` — con la tarjeta de al lado diciendo «CERRADO por corrida guardada». Fue
    exactamente lo que se reporto con captura.

    ORDENAR NO ES FILTRAR: no se quita ni una fila. Lo que cambia es cual se ve primero.
    """
    elegidas = [f for f in filas if f.get("elegido")]
    resto = [f for f in filas if not f.get("elegido")]
    elegidas.sort(
        key=lambda f: (f.get("rango") if isinstance(f.get("rango"), int) else 10**9)
    )
    return elegidas + resto


def site_table_rows(tiling, selection, *, species: str = "",
                    selected=None, stores=None) -> list[dict[str, object]]:
    """TODOS los sitios elegibles, con UNA COLUMNA POR FRENTE.

    No solo los elegidos: la piscina entera. Un candidato que no esta en el panel sigue
    siendo un sitio con veredictos, y esconderlo deja al lector sin poder discutir la
    seleccion.

    `selected` son los inicios marcados a mano; si es `None`, se marcan los del panel.

    `stores` son los almacenes del proyecto. SIN ellos la tabla decia `NOT_RUN` de
    frentes que el informe ya daba por cerrados —dos artefactos del mismo proyecto
    afirmando cosas distintas del mismo frente (principio nº 23)— y el desacuerdo habia
    que declararlo en pantalla. Con ellos, ese aviso sobra y se ha borrado.
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
                # `inicio_3utr` YA esta convertido al 3'UTR — el nombre lo dice y la
                # conversion la hace el tilado—, asi que el marco no se supone aqui.
                "sitio": coords.label(ventana.inicio_3utr, coords.Frame.UTR3),
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
                # El almacen MANDA donde tiene algo que decir; donde no, decide el
                # filtro de la ventana. Y sólo sobre SU columna: `STORE_FOR_FRONT`.
                **(efectivos := _with_stores(
                    {n: estados.get(n, "NOT_RUN") for n in columnas},
                    stores, species, ventana.window.start,
                )),
                # EL VEREDICTO CUENTA LO MISMO QUE LAS CELDAS. Antes salia
                # `ventana.verdict`, del informe de tilado, asi que una fila podia decir
                # `especificidad: PASS` y `veredicto: INCOMPLETE` — dos numeros del mismo
                # suceso, uno al lado del otro, sin nada que los ate.
                "veredicto": (
                    verdict_with_stores(efectivos) if stores
                    else ventana.verdict.value
                ),
                "guia": ventana.evaluation.guide,
            }
        )
    # EL PANEL ARRIBA. Ver `panel_first`: la tabla estaba bien y era ilegible.
    return panel_first(filas)


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
                        f"{_start_label(selection, uno)} y "
                        f"{_start_label(selection, otro)} están a {abs(otro - uno)} nt, "
                        f"por debajo del espaciado mínimo de {espaciado} nt. "
                        f"{MIN_SPACING_WARNING}"
                    ),
                })
    for conflicto in core_conflicts(selection):
        if conflicto.a in marcados and conflicto.b in marcados:
            avisos.append({
                "rojo": True,
                "texto": (
                    conflicto.describe(
                        label_a=_start_label(selection, conflicto.a),
                        label_b=_start_label(selection, conflicto.b),
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
    # LOS QUE CIERRAN, no los que están: un fichero sin la procedencia que su frente
    # exige no cierra nada, y contarlo aquí pinta la barra con un frente que no corre.
    presentes = _cierran(species, directory=ruta)
    informe = fixture_report(resolve(species), have=presentes)
    faltan = [f for f in informe.rows if not f.available]
    return {
        "cerrables": informe.closable,
        "total": len(informe.rows),
        "abiertos": [{"frente": f.front, "falta": f.missing} for f in faltan],
        "texto": informe.render(),
    }


# ═══════════ EL DEPOSITO, LEIDO DE UN SOLO SITIO PARA LOS CUATRO MODALES ═══════════
#
# Un modal que pide lo que el deposito ya tiene crea DOS COPIAS del mismo dato: la que
# escribio quien subio el fichero y la que teclea quien corre. Nada las ata, y cuando
# divergen ninguna dice cual manda — o peor, quien no se acuerda del ensamblaje se lo
# inventa y el conteo sale con la forma correcta sobre el genoma equivocado.
#
# QUE ficheros consume cada corrida ya estaba declarado, por ROL, en `insumos.CONSUMIDOS`
# — la tabla que existe para que un quinto modal no se quede fuera sin que nadie lo note.
# Esto la usa en vez de repetirla: la lectura pasa entera por `deposito.read_deposit`,
# como el estado por filtro pasa entero por `_filter_columns`.

#: Que hacer cuando la corrida no consume ningun fichero de referencia. NO es un hueco:
#: `insumos` lo declara VACIO a proposito, y la diferencia entre «se miro y no hay» y
#: «nadie lo miro» es justo lo que este texto conserva.
def deposit_note(kind: str) -> str:
    """La frase del panel cuando esa corrida no consume ningun fichero del depósito."""
    from .insumos import POR_QUE_EMPALME_NO_TIENE, insumos_de  # noqa: PLC0415

    if insumos_de(kind):
        return ""
    return POR_QUE_EMPALME_NO_TIENE


#: LO QUE LE PASA A UN FICHERO QUE ESTA Y NO TIENE PROCEDENCIA, dicho donde se arregla.
#:
#: No es un fallo suyo ni de quien lo subio: entro antes de que su frente exigiera las
#: cuatro columnas (errata nº 62), asi que esta, es valido, y su linea esta a medias.
#: Lo que se dice es QUE FALTA y que se arregla aqui — sin resubir el fichero, que era
#: la unica salida que ofrecia la app y que para un catalogo son decenas de MB.
PROVENANCE_MISSING_NOTE = (
    "A la línea de este fichero le falta {faltan}. El fichero está y es válido: entró "
    "antes de que su frente exigiera la procedencia de la tabla. Sin ella el conteo no "
    "es reproducible y el modal no puede dar veredicto — así que se declara aquí, y "
    "**el fichero no se vuelve a subir**."
)


def declare_provenance(directory, *, filename: str, species: str,
                       **valores: str) -> dict[str, object]:
    """Completa la procedencia de tabla de un fichero que ya está. La página no escribe.

    Los cuatro campos llegan por nombre (`assembly`, `table`, `table_date`,
    `representative`), que es como los declara `deposito.PROVENANCE_FIELDS`: la página
    los pinta con la etiqueta que le da `gestor` y no los renombra por el camino.
    """
    from .deposito import declare_provenance as declarar  # noqa: PLC0415
    from .species import resolve  # noqa: PLC0415

    fichero = declarar(directory, filename=filename, species=resolve(species), **valores)
    return {
        "nombre": fichero.filename,
        "falta": list(fichero.missing_provenance),
        "texto": (
            f"Procedencia declarada para {fichero.filename}. El fichero no se ha tocado "
            f"—sigue con su md5 {fichero.md5[:8]}…— y su frente ya puede dar veredicto."
        ),
    }


def deposit_file(role: str, *, species: str, directory) -> dict[str, object]:
    """Lo que el depósito sabe de ese rol, en una fila para pintar.

    La página no abre el manifiesto, no calcula ningún md5 y no decide si ofrece subida:
    recibe esta fila y la pinta (regla 6).
    """
    from .deposito import read_deposit  # noqa: PLC0415
    from .species import resolve  # noqa: PLC0415

    fichero = read_deposit(role, species=resolve(species), directory=directory)
    from .gestor import _procedencia_pedida  # noqa: PLC0415

    # DOS COSAS DISTINTAS Y DOS NOMBRES. Lo DECLARADO —para enseñarlo— y lo PEDIDO —las
    # casillas que hay que rellenar—. Compartían el nombre `procedencia` con formas
    # incompatibles (`campo`/`valor` frente a `clave`/`etiqueta`/`ayuda`), así que la
    # caja del gestor puesta sobre esta fila reventaba al PINTARSE (errata nº 123).
    # Renombrar, no ampliar el significado: principio nº 27.
    declarada = [
        {"campo": campo, "valor": valor}
        for campo, valor in fichero.provenance_fields().items()
        if str(valor).strip()
    ] if fichero.present else []
    pedida = _procedencia_pedida(fichero.role)
    return {
        "rol": fichero.role,
        "nombre": fichero.filename,
        # LA ESPECIE VIAJA EN LA FILA. `declare_provenance` la necesita para resolver el
        # nombre del fichero contra `required_files`, y sin ella la caja del modal se
        # pinta igual de bien y revienta AL PULSAR — peor que no tenerla.
        "especie": species,
        "presente": fichero.present,
        "registrado": fichero.registered,
        "md5": fichero.md5,
        "tamano": fichero.size,
        "procedencia_declarada": declarada,
        "procedencia_pedida": pedida,
        "falta_procedencia": list(fichero.missing_provenance),
        # SOLO se ofrece subida si el fichero NO esta. Ofrecerla teniendolo dentro es lo
        # que hacia el modal de off-targets, y con ello volvia a pedir la procedencia.
        "ofrecer_subida": not fichero.present,
        "avisa": fichero.stale_md5 or bool(fichero.missing_provenance),
        "texto": fichero.describe(),
    }


def deposit_for_run(kind: str, *, species: str, directory) -> list[dict[str, object]]:
    """Una fila por INSUMO declarado de esa corrida. Los cuatro modales llaman aquí."""
    from .insumos import insumos_de  # noqa: PLC0415

    return [
        deposit_file(insumo.rol, species=species, directory=directory)
        for insumo in insumos_de(kind)
    ]


def offtarget_catalog_from_deposit(*, species: str, directory, gene_map=None):
    """El catálogo Y SU PROCEDENCIA, del depósito. Cero campos que rellenar.

    La procedencia se DERIVA de la línea del manifiesto —los cuatro campos de tabla se
    declararon al subir el fichero y los otros tres los tenía desde siempre—, así que
    `Provenance` se monta sin que nadie vuelva a teclear nada. Si le falta alguno,
    `Provenance` aborta con el campo por su nombre: no se rellena por nuestra cuenta.
    """
    from pathlib import Path  # noqa: PLC0415

    from .deposito import read_deposit  # noqa: PLC0415
    from .offtarget import Provenance, build_catalog, validate_upload  # noqa: PLC0415
    from .species import resolve  # noqa: PLC0415

    fichero = read_deposit(
        "transcriptoma", species=resolve(species), directory=directory
    )
    if not fichero.present:
        return None
    crudo = (Path(directory) / fichero.filename).read_text(
        encoding="utf-8", errors="replace"
    )
    informe = validate_upload(crudo, declared_md5=fichero.md5, gene_map=gene_map)
    return build_catalog(
        informe.parsed,
        provenance=Provenance(**fichero.provenance_fields()),
        gene_map=gene_map,
    )


def blast_database_from_deposit(*, species: str, directory, remote: bool = False):
    """La base de BLAST tal como la registra el depósito, para la corrida.

    Los tres campos —nombre, versión y md5— se tecleaban en el modal con la línea del
    manifiesto delante. El md5 es el que decide si una corrida queda OBSOLETA cuando el
    fichero se reemplaza, así que tecleado a mano no ata nada.

    Sin fichero en el depósito la corrida se sigue pudiendo guardar —la base pudo correr
    en otra máquina, que es el caso normal de este frente— pero entonces el nombre lo
    dice y el md5 va VACÍO, que es la verdad: sin md5 no hay veredicto reproducible, y
    `blast_readiness` ya lo avisa ANTES de la descarga.
    """
    from .deposito import read_deposit  # noqa: PLC0415
    from .species import resolve  # noqa: PLC0415

    fichero = read_deposit("refseq", species=resolve(species), directory=directory)
    if not fichero.present:
        return {
            "nombre": fichero.filename,
            "version": "",
            "md5": "",
            "remota": remote,
            "texto": fichero.describe(),
        }
    entrada = fichero.provenance_fields()
    return {
        "nombre": fichero.filename,
        "version": entrada.get("version", ""),
        "md5": fichero.md5,
        "remota": remote,
        "texto": fichero.describe(),
    }


from .gestor import WHY_A_BACKUP_BUTTON as _WHY_A_BACKUP_BUTTON  # noqa: E402


#: Cómo se lee un tamaño. Vive aquí y no en la página porque elegir la unidad es una
#: decisión —84.000.000 y «84,0 MB» dicen lo mismo y sólo uno se lee de un vistazo— y la
#: página no decide (regla 6).
def size_text(nbytes: int) -> str:
    """Bytes → una cifra legible. Sin redondear a cero: 0 B es un dato."""
    valor = float(nbytes)
    for unidad in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidad == "GB":
            entero = unidad == "B"
            return f"{valor:.0f} {unidad}" if entero else f"{valor:.1f} {unidad}"
        valor /= 1024
    raise AssertionError  # pragma: no cover - el bucle siempre sale por el `return`


#: Por que existe el boton. Va a la pagina desde aqui, como todo lo demas.
WHY_A_BACKUP_BUTTON = _WHY_A_BACKUP_BUTTON


def backup_inventory(*, directory, projects=None) -> dict[str, object]:
    """Qué llevaría la copia de seguridad y cuánto pesa. NO construye el zip.

    Se pinta en CADA repintado, así que aquí no se comprime nada: con el transcriptoma
    dentro —84 MB— montar el zip sólo para enseñar un número costaría un minuto por clic.
    Es la lección de la errata nº 59.
    """
    from .gestor import backup_inventory as inventario  # noqa: PLC0415

    datos = dict(inventario(directory, projects=projects))
    trozos = [f"{datos['ficheros']} fichero(s) de referencia"]
    if datos["proyectos"]:
        trozos.append(f"{datos['proyectos']} proyecto(s)")
    if datos["guardados"]:
        trozos.append(f"{datos['guardados']} guardado(s) de la biblioteca")
    datos["texto"] = (
        f"{', '.join(trozos)} — {size_text(int(datos['bytes']))} sin comprimir."
    )
    return datos


def build_backup(*, directory, projects=None, date: str) -> dict[str, object]:
    """El zip entero, ya montado, con el nombre con el que se descarga.

    El NOMBRE lleva la fecha porque dos copias sin fecha no se distinguen, y eso es lo
    primero que hace falta saber de un zip encontrado dentro de un año.
    """
    from .gestor import export_all  # noqa: PLC0415

    crudo = export_all(directory, projects=projects, date=date)
    return {
        "datos": crudo,
        "nombre": f"shmir_copia_{date}.zip",
        "texto": (
            f"Copia lista: {size_text(len(crudo))} comprimidos. Dentro va el LEEME con "
            f"el inventario, los md5 y cómo se restaura."
        ),
    }


# ════════ A CUÁNTOS SE PREGUNTA: el alcance de una corrida ════════
#
# **No es lo mismo que cuántos se ELIGEN**, y la distincion es la que ordena todo esto:
# el panel sigue siendo de 10 con sus cuotas —4 inmunes, reparto por tercios, 50 nt de
# espaciado— y lo que cambia es a cuantos candidatos se les hace la pregunta. Bajar el
# espaciado para tener un panel mayor es OTRA decision, con su coste en independencia
# entre apuestas, y se discute aparte.
#
# **La unidad son los SITIOS, no las ventanas.** Ventanas solapadas de la misma region
# comparten casi toda su secuencia, asi que preguntar por las tres daria el mismo
# resultado repetido y ensuciaria cualquier recuento. «Cada region una vez» es lo correcto
# para especificidad, seed y off-targets. El representante de cada sitio es `Site.best`,
# que es el criterio con el que la seleccion YA ordena: elegir otro seria una segunda
# definicion de «el mejor».
#
# **Y el coste va POR MODAL, con lo NO MEDIDO dicho.** Un numero inventado es peor que
# «no lo se»: quien lo lee lo trata como una medida. Con la leccion de los cuatro minutos
# por clic delante (errata nº 59).

#: Los dos alcances. `panel` primero porque es el defecto: preguntar por los 86 es la
#: excepcion, no al reves.
SCOPES = ("panel", "elegibles")


@dataclass(frozen=True)
class CosteDelAlcance:
    """Lo que cuesta ampliar el alcance en ese modal, y si esta MEDIDO."""

    #: Cuantas consultas salen por candidato, y de donde sale ese numero. `None` = se
    #: deriva de otra cosa (los intrones disponibles) y no es una constante.
    #: Como se llama lo que se cuenta, en singular y en plural. Las DOS: pegarle una
    #: «s» al singular daba «par candidato x intróns», que es lo que pasa cuando se
    #: deriva algo que no es derivable.
    unidad: str
    unidad_plural: str
    medido: bool
    texto: str


COSTE_POR_ALCANCE: dict[str, CosteDelAlcance] = {
    "corrida_blast": CosteDelAlcance(
        unidad="secuencia en el FASTA de consulta",
        unidad_plural="secuencias en el FASTA de consulta", medido=True,
        texto=(
            "No cuesta nada aquí: la corrida la haces FUERA, y mandar más secuencias en "
            "un solo BLAST cuesta lo mismo que mandar menos. Lo único que crece es el "
            "FASTA."
        ),
    ),
    "corrida_seed": CosteDelAlcance(
        unidad="consulta de seed", unidad_plural="consultas de seed", medido=True,
        texto=(
            "Medido y barato: es búsqueda de subcadena contra `mature.fa`, que ya está "
            "cargado. Crece de forma lineal con las consultas."
        ),
    ),
    "corrida_offtarget": CosteDelAlcance(
        unidad="consulta de off-target", unidad_plural="consultas de off-target",
        medido=False,
        texto=(
            "El coste NO está medido con el catálogo delante: el índice se construye una "
            "vez, pero la distribución nula son 10.000 sorteos POR CONSULTA. Con el "
            "alcance grande eso se multiplica, y aquí nadie ha cronometrado cuánto. Se "
            "dice en vez de dar un número inventado."
        ),
    ),
    "corrida_empalme": CosteDelAlcance(
        unidad="par candidato × intrón", unidad_plural="pares candidato × intrón",
        medido=False,
        texto=(
            "El coste NO está medido: cada par candidato × intrón se PLIEGA, y el plegado "
            "es lo caro de todo el pipeline. Se dice en vez de dar un número inventado."
        ),
    ),
}


def _consultas_por_candidato(kind: str, units) -> int:
    """Cuántas consultas salen de un candidato en ese modal.

    Para los tres primeros son las HEBRAS, y esa cifra sale de `STRANDS`: escribir un 2
    aquí sería afirmar que son dos, que es algo que el núcleo ya declara.

    Para el EMPALME no se puede derivar y por eso se exige: la unidad es el par candidato
    × intrón, y cuántos intrones se consultan lo elige quien corre en ese mismo modal.
    Derivarlo de «los que tienen secuencia» daría un número que el usuario no ha pedido —
    una etiqueta que promete 172 cuando va a hacer 86.
    """
    if units is not None:
        return len(units)
    if kind == "corrida_empalme":
        raise ShmirDesignError(
            "El alcance del modal de empalme se cuenta en pares candidato × intrón, así "
            "que hay que decir QUÉ intrones se van a consultar: no se deriva del registro "
            "porque eso anunciaría consultas que nadie ha pedido. Se aborta."
        )
    return len(STRANDS)


def scope_starts(selection, scope: str) -> tuple[int, ...]:
    """Los candidatos a los que se pregunta con ese alcance.

    Un alcance desconocido ABORTA: devolver el panel por defecto daría una corrida de 10
    etiquetada como de 86, que es una procedencia falsa con la forma correcta.
    """
    if scope == "panel":
        return tuple(chosen_starts(selection))
    if scope == "elegibles":
        return tuple(sorted(s.best.start for s in selection.selection.sites))
    raise ShmirDesignError(
        f"Alcance {scope!r} desconocido; los que hay son {', '.join(SCOPES)}. Se aborta "
        f"en vez de coger uno por nuestra cuenta."
    )


def scope_rows(selection, *, kind: str, units=None) -> list[dict[str, object]]:
    """Las dos opciones de alcance, con su recuento y su coste ya montados.

    `units` son las unidades que se consultan por candidato cuando NO son las hebras:
    hoy, los intrones elegidos en el modal de empalme.
    """
    if kind not in COSTE_POR_ALCANCE:
        raise ShmirDesignError(
            f"No hay coste declarado para {kind!r}; los declarados son "
            f"{', '.join(sorted(COSTE_POR_ALCANCE))}. Se aborta: un modal cuyo coste "
            f"nadie ha decidido no puede ofrecer el alcance grande como si fuera gratis."
        )
    coste = COSTE_POR_ALCANCE[kind]
    por_candidato = _consultas_por_candidato(kind, units)
    filas = []
    for clave, nombre in (
        ("panel", "El panel"), ("elegibles", "Todos los sitios elegibles"),
    ):
        starts = scope_starts(selection, clave)
        consultas = len(starts) * por_candidato
        filas.append({
            "clave": clave,
            "candidatos": len(starts),
            "consultas": consultas,
            "starts": starts,
            "coste": coste.texto,
            "coste_medido": coste.medido,
            "etiqueta": (
                f"{nombre} — {len(starts)} candidatos, {consultas} "
                f"{coste.unidad if consultas == 1 else coste.unidad_plural}"
            ),
        })
    return filas


def selection_notes(selection) -> list[dict[str, object]]:
    """Lo que la selección tiene que decir de sí misma, para pintarlo JUNTO AL CONTROL.

    La más importante: **«se pedían 50 candidatos y sólo salen 14»**. El núcleo lo apunta
    desde siempre en `Selection.notes` y hasta hoy sólo lo emitía el informe de texto del
    CLI — así que quien sube el número en la barra lateral veía la MISMA tabla y concluía,
    con razón, que la app no le hacía caso. Un parámetro que no hace lo que dice y no lo
    dice es un parámetro que miente. Principio nº 23: dos artefactos leen el mismo estado
    y sólo uno lo cuenta.
    """
    return [
        {"texto": nota, "avisa": True} for nota in selection.selection.notes
    ]


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


# ═════════════════ LOS FICHEROS DE REFERENCIA SON DOS MOMENTOS ═════════════════
#
# El paso 3 pedia los siete frentes a la vez, antes de diseñar, como si todos sirvieran
# para lo mismo. No sirven para lo mismo, y presentarlos juntos hace creer que sin ellos
# no se puede empezar — que es FALSO: se puede diseñar hoy y refinar mañana.
#
#   - MOMENTO 1, obtener candidatos. Le hace falta la secuencia y su anatomia, y nada
#     mas. Los filtros biofisicos y la prediccion de polyA corren sin ningun fichero
#     externo. HOY LA LISTA ESTA VACIA, y eso no se declara: `tests/test_dos_momentos.py`
#     corre el diseño con el directorio de referencia VACIO y comprueba que salen
#     candidatos. El dia que algo pase a hacer falta para tilar, el test lo dice.
#   - MOMENTO 2, refinar y descartar. `mature.fa`, `transcriptoma_3utr.fa`,
#     `refseq_rna.fa`, la tabla de PolyA_DB… Estos no cambian QUE candidatos salen:
#     cambian que veredicto lleva cada uno y CUALES ACABAN CAYENDO.
#
# La frase del momento 2 tambien esta MEDIDA, no afirmada: el conjunto de elegibles con
# cualquier fichero de referencia es un SUBCONJUNTO del que sale sin ninguno —ninguno
# inventa un candidato— y lo que quita cada uno esta contado (PolyA_DB 17, `mature.fa`
# 2, la mascara murina 0 porque el 3'UTR del raton no tiene ni un repetitivo). Una prosa
# sobre la que el codigo puede discrepar es la que se queda atras, y es la que alguien
# va a leer: principio nº 11.

WHY_TWO_MOMENTS = (
    "Son dos momentos y no uno. Para OBTENER candidatos hace falta la secuencia y su "
    "anatomía, y nada más. Los ficheros de refinamiento no cambian qué candidatos "
    "salen: cambian qué veredicto lleva cada uno y cuáles acaban cayendo. Pedirlos "
    "todos antes de diseñar hace creer que sin ellos no se puede empezar."
)

#: La frase que abre el paso 5. Va EN LA SECCION y no en un tooltip: lo que hay que
#: entender para leer bien la lista no puede estar detrás de un gesto.
REFINEMENT_FRAMING = (
    "Los candidatos ya están. Estos ficheros no cambian cuáles son, cambian cuáles "
    "sobreviven."
)

#: Lo que le pasa a un frente que no se cierra. Va POR FILA y con estas palabras: es la
#: cuarta pregunta del criterio de aceptacion —«¿que pasa si no lo consigo?»— y su
#: respuesta no es «nada».
WHAT_IF_IT_NEVER_ARRIVES = (
    "Su frente se queda en NOT_RUN y los candidatos, en INCOMPLETE. No bloquea el "
    "diseño: bloquea aprobarlo."
)
WHAT_IF_PROVENANCE_NEVER_ARRIVES = (
    "Su frente se queda en NOT_RUN aunque el fichero esté: el modal aborta al pedir el "
    "veredicto. La diferencia con FALTA es la salida, no la gravedad — aquí no hay que "
    "conseguir nada, hay que DECLARAR cuatro campos sobre el fichero que ya está."
)
WHAT_IF_OPTIONAL_NEVER_ARRIVES = (
    "Nada se queda sin correr. El filtro corre igual y sin este fichero da un número "
    "menos afinado, no un hueco."
)
WHAT_IF_UNUSED_NEVER_ARRIVES = (
    "Nada. Su frente ya está cerrado por otro fichero, así que conseguirlo no cambiaría "
    "ningún veredicto."
)

#: LOS CUATRO ESTADOS, CONSTANTES. Siempre los mismos cuatro, siempre el mismo color, y
#: la leyenda al principio de la seccion. La pagina no elige ninguno: si eligiera un
#: color segun un umbral, eso seria logica en la pagina (regla 6).
#:
#: «NO USADO» existe porque el panel pedia `apa_medido.tsv` en ambar con
#: `polya_db_mouse.tsv` ya en el deposito: dos ficheros que cierran el MISMO frente, y
#: el que sobra se leia como trabajo pendiente. Una alternativa que no hace falta y una
#: cosa que falta de verdad no pueden tener el mismo color.
#: El estado del fichero QUE ESTÁ y NO CIERRA NADA. En un solo sitio: lo comparan
#: `_estado_de`, la leyenda y el panel, y tres literales acabarían discrepando. Se
#: DEFINE en `deposito`, que es donde se calcula el hecho que lo produce, y desde donde
#: el aviso del modal nombra la fila a la que hay que ir.
from .deposito import INCOMPLETE_PROVENANCE  # noqa: E402

WHY_PRESENT_IS_NOT_CLOSED = (
    "Un fichero PRESENTE cuya línea del manifiesto no lleva la procedencia que su "
    "frente EXIGE no cierra nada: el modal aborta y el veredicto sale NOT_RUN. Marcarlo "
    "verde es la tercera vez que pasa lo mismo —verde en el panel y NOT_RUN en el "
    "veredicto, como `refseq_rna.fa`— y aquí tenía una segunda consecuencia peor: una "
    "fila CERRADA va COLAPSADA, así que las cuatro acciones y la caja de «completar la "
    "procedencia» quedaban detrás de un gesto. EL ESTADO TAPABA SU PROPIO ARREGLO. "
    "Tampoco es FALTA: el fichero está, y volver a subir 84 MB no es lo que hace falta "
    "— la salida es declarar los campos sobre el que ya está."
)

REFINEMENT_STATES = (
    {
        "estado": "CERRADO",
        "color": "verde",
        "marca": "🟢",
        "significa": "está en el depósito y se está usando. Su frente puede correr.",
    },
    {
        "estado": INCOMPLETE_PROVENANCE,
        "color": "ámbar",
        "marca": "🟡",
        "significa": (
            "está en el depósito y AUN ASÍ no cierra su frente: a su línea del "
            "manifiesto le faltan campos de procedencia que el veredicto exige. Se "
            "completan sobre el fichero que ya está, sin volver a subirlo."
        ),
    },
    {
        "estado": "FALTA",
        "color": "ámbar",
        "marca": "🟠",
        "significa": (
            "no está, y su frente no se puede cerrar sin él: NOT_RUN, y los candidatos "
            "INCOMPLETE."
        ),
    },
    {
        "estado": "OPCIONAL",
        "color": "gris",
        "marca": "⚪",
        "significa": (
            "no está, y no bloquea nada: refina un filtro que corre igual sin él."
        ),
    },
    {
        "estado": "NO USADO",
        # LA MARCA DECIA LO CONTRARIO QUE EL TEXTO. Era «⚫», un círculo NEGRO, al lado
        # de una frase que dice «no hace falta conseguirlo». Se preguntó con la captura
        # delante —«¿por qué está en negro? parece como si faltara algo»— y es que en una
        # columna de 🟢 y 🟠 el negro es el que más grita: se lee como el peor estado, no
        # como el que no pide nada. Una raya se lee como «no aplica», que es lo que es.
        "estado_declarado_como": "gris claro",
        "color": "raya",
        "marca": "➖",
        "significa": (
            "no está y NO hace falta: otro fichero ya cierra su frente. No es trabajo "
            "pendiente."
        ),
    },
)

_COLOR = {e["estado"]: (e["color"], e["marca"]) for e in REFINEMENT_STATES}


def design_files_rows(species: str, *, directory) -> dict[str, object]:
    """MOMENTO 1: los ficheros imprescindibles para OBTENER candidatos.

    Hoy la lista sale vacía, y no porque esté escrito: se deriva de `required_files`
    filtrando los que hacen falta ANTES de tilar, que hoy no es ninguno — la anatomía
    sale del `.gb` del paso 2. Hay un test que corre el diseño con el directorio vacío
    y comprueba que salen candidatos, así que el día que algo pase a hacer falta aquí,
    la suite lo dice en vez de que este texto envejezca solo.
    """
    filas = [
        fila
        for fila in _refinement_rows(species, directory=directory)
        if fila["momento"] == 1
    ]
    if filas:
        texto = (
            f"Hacen falta {len(filas)} fichero(s) antes de poder obtener candidatos: "
            + ", ".join(f["nombre"] for f in filas)
            + "."
        )
    else:
        texto = (
            "Ninguno. La anatomía sale del `.gb` del paso 2, y los filtros biofísicos "
            "—GC, homopolímero, G4 y asimetría— no necesitan ningún fichero. Se puede "
            "diseñar ya: lo que hace falta para REFINAR se pide después, en el paso 5."
        )
    return {"filas": filas, "hacen_falta": len(filas), "texto": texto}


def refinement_panel(species: str, *, directory) -> dict[str, object]:
    """MOMENTO 2: los ficheros que deciden qué candidatos CAEN.

    Se pinta DESPUES del botón de diseñar y debajo de los resultados. Trae la frase de
    encuadre, el contador de frentes con su fracción para la barra, la leyenda de los
    cuatro estados y las filas YA ordenadas por impacto.
    """
    resumen = reference_panel_summary(species, directory=directory)
    cerrados, total = resumen["cerrables"], resumen["total"]
    filas = [
        fila
        for fila in _refinement_rows(species, directory=directory)
        if fila["momento"] == 2
    ]
    return {
        "frase": REFINEMENT_FRAMING,
        "progreso": {
            "cerrados": cerrados,
            "total": total,
            "fraccion": cerrados / total if total else 0.0,
            "texto": f"{cerrados} de {total} frentes cerrados",
        },
        "leyenda": list(REFINEMENT_STATES),
        "filas": filas,
    }


def _refinement_rows(species: str, *, directory) -> list[dict[str, object]]:
    """Una fila por fichero, con su estado, su grupo y si va colapsada.

    EL ORDEN ES POR IMPACTO, no alfabético: primero lo que cierra un frente, luego lo
    opcional, y dentro de cada grupo lo resuelto ABAJO. Alfabético pone `aav_casete.fa`
    delante de `transcriptoma_3utr.fa` sin ninguna razón, y quien entra a este panel
    entra a saber qué le falta.
    """
    from .species import fixture_report, resolve  # noqa: PLC0415

    especie = resolve(species)
    # Los que CIERRAN, por el mismo motivo que en `reference_panel_summary`: un fichero
    # sin su procedencia no cierra su frente, así que tampoco puede dejar a una
    # alternativa en «NO USADO».
    cierran = _cierran(species, directory=directory)
    informe = fixture_report(especie, have=cierran)
    # Que frentes estan cerrados y CON QUE fichero. De aqui sale «NO USADO»: una fila
    # cuyo frente ya cierra OTRO fichero que si esta no es trabajo pendiente.
    cerrado_por: dict[str, list[str]] = {}
    # DOS conjuntos, dos preguntas. `cierran` contesta «¿cierra su frente?» y decide
    # los estados; `en_disco` contesta «¿está el fichero?» y decide QUÉ BOTONES se
    # pintan. Fundirlos deja un fichero que está sin sus cuatro acciones — que es
    # justamente lo que hay que poder hacer con él.
    cierran_set = set(cierran)
    en_disco = set(_presentes(directory))
    presentes = cierran_set
    for frente in informe.rows:
        if frente.available:
            for clave in frente.keys:
                cerrado_por[clave] = [f for f in frente.files if f in presentes]

    filas = []
    for fila in reference_manager_rows(species, directory=directory):
        estado = _estado_de(fila, cerrado_por, presentes)
        color, marca = _COLOR[estado]
        opcional = not fila["obligatorio"]
        bloquea = estado in {"FALTA", INCOMPLETE_PROVENANCE}
        filas.append(
            {
                **fila,
                # Hoy ninguno es del momento 1. Se deja DERIVADO y no escrito a cero:
                # un fichero que pasara a hacer falta para tilar tiene que poder subir
                # al paso 3 cambiando `required_files`, no editando dos sitios.
                "momento": 1 if fila["role"] in _ROLES_PARA_DISEÑAR else 2,
                "estado": estado,
                "color": color,
                "marca": marca,
                "bloquea": bloquea,
                "grupo": 1 if opcional else 0,
                "resuelta": (
                    0 if estado in {"FALTA", "OPCIONAL", INCOMPLETE_PROVENANCE} else 1
                ),
                # NO se colapsa lo que pide trabajo. `SIN PROCEDENCIA` va abierta a
                # propósito: la caja de declarar los campos vive dentro de la fila, y
                # colapsarla escondía exactamente la salida del problema.
                "colapsada": estado in {"CERRADO", "NO USADO"},
                # ESTA O NO ESTA, dicho aqui y no deducido en la pagina. La pagina
                # elegia entre las cuatro acciones de lo presente y el hueco de subida
                # con `if fila["acciones"]:`, y esa lista NUNCA esta vacia —una fila
                # ausente lleva `["subir"]`, que es verdadera—. O sea que una fila
                # COLAPSADA Y AUSENTE («NO USADO»: su frente ya lo cierra otro fichero)
                # salia con «Ver», «Reemplazar», «Borrar» y «Descargar» sobre un fichero
                # que no esta: el panel enseñaba un error rojo al abrir la app y «Ver»
                # tiraba la pagina entera. Regla 6: lo que decide, decidido aqui.
                "presente": fila["nombre"] in en_disco,
                # Que frentes cierra, EN LA FILA. El panel ya no agrupa por frente
                # —el orden es por impacto—, asi que si el frente no viaja en la fila
                # deja de verse: un fichero sin frente visible es un fichero que no se
                # sabe para que sirve.
                "frentes_texto": ", ".join(fila["frentes"]) or "—",
                "por_que": _por_que(fila, estado, cerrado_por),
                "si_no_llega": (
                    WHAT_IF_PROVENANCE_NEVER_ARRIVES
                    if estado == INCOMPLETE_PROVENANCE
                    else WHAT_IF_IT_NEVER_ARRIVES if bloquea
                    else WHAT_IF_OPTIONAL_NEVER_ARRIVES if estado == "OPCIONAL"
                    else WHAT_IF_UNUSED_NEVER_ARRIVES if estado == "NO USADO"
                    # Un fichero que YA esta no tiene «si no llega»: la pregunta no se
                    # le hace. Vacio aqui es NO_APLICA, no un hueco.
                    else ""
                ),
            }
        )
    return sorted(filas, key=lambda f: (f["grupo"], f["resuelta"], f["nombre"]))


#: Los roles cuyo fichero hace falta ANTES de tilar. Vacio, y comprobado corriendo el
#: diseño sin ninguno (`tests/test_dos_momentos.py`). No es una lista que se rellene a
#: ojo: si algo entra aqui, el test del directorio vacio tiene que dejar de pasar.
_ROLES_PARA_DISEÑAR: frozenset[str] = frozenset()


def _presentes(directory):
    from pathlib import Path  # noqa: PLC0415

    from .presencia import ficheros_con_contenido  # noqa: PLC0415

    return tuple(sorted(ficheros_con_contenido(Path(directory))))


def _cierran(species: str, *, directory) -> tuple[str, ...]:
    """Los ficheros presentes QUE CIERRAN ALGO: los que además traen su procedencia.

    Estar en el depósito no cierra un frente. `transcriptoma_3utr.fa` sin los cuatro
    campos de la tabla está, se lee, y el modal de off-targets ABORTA — así que contarlo
    como cerrado pinta la barra de progreso y el semáforo con un frente que no corre.
    Es el mismo verde equivocado que `_estado_de` deja de dar, un nivel más arriba: si
    sólo se arregla la fila, la fila dice ámbar y la barra dice cerrado.

    Ver `WHY_PRESENT_IS_NOT_CLOSED`.
    """
    sin_procedencia = {
        fila["nombre"]
        for fila in reference_manager_rows(species, directory=directory)
        if fila["estado"] == "presente" and fila.get("falta_procedencia")
    }
    return tuple(f for f in _presentes(directory) if f not in sin_procedencia)


def _estado_de(fila, cerrado_por, presentes) -> str:
    """Los CINCO estados, derivados de tres hechos: si está, si su línea trae la
    procedencia que su frente exige, y si su frente ya cierra con otro.

    El orden de las ramas importa: una alternativa no usada tiene que decidirse ANTES de
    caer en «FALTA», que es justo lo que pasaba con `apa_medido.tsv`. Y estar presente
    ya no basta para CERRADO — ver `WHY_PRESENT_IS_NOT_CLOSED`.
    """
    if fila["estado"] == "presente":
        if fila.get("falta_procedencia"):
            return INCOMPLETE_PROVENANCE
        return "CERRADO"
    if not fila["obligatorio"]:
        return "OPCIONAL"
    otros = [
        f
        for clave in fila["frentes"]
        for f in cerrado_por.get(clave, ())
        if f != fila["nombre"]
    ]
    # TODOS sus frentes cerrados por otro, no alguno: un fichero que cierra dos frentes
    # y solo tiene uno cubierto sigue haciendo falta.
    if fila["frentes"] and all(cerrado_por.get(c) for c in fila["frentes"]) and otros:
        return "NO USADO"
    return "FALTA"


def _por_que(fila, estado: str, cerrado_por) -> str:
    """Por que esta fila esta en ese estado, con el nombre del fichero que lo decide."""
    if estado == "CERRADO":
        return f"Está en el depósito. Desbloquea: {fila['que_desbloquea']}."
    if estado == INCOMPLETE_PROVENANCE:
        return (
            f"ESTÁ en el depósito y AUN ASÍ no desbloquea {fila['que_desbloquea']}: a "
            f"su línea del manifiesto le faltan "
            f"{', '.join(fila['falta_procedencia'])}. El veredicto sale NOT_RUN hasta "
            f"que se declaren, y se declaran AQUÍ, sobre el fichero que ya está — no "
            f"hay que volver a subirlo. {WHY_PRESENT_IS_NOT_CLOSED}"
        )
    if estado == "OPCIONAL":
        return (
            f"No bloquea nada: {fila['que_desbloquea']}. El filtro corre sin él y con "
            f"él afina."
        )
    if estado == "NO USADO":
        otros = sorted(
            {
                f
                for clave in fila["frentes"]
                for f in cerrado_por.get(clave, ())
                if f != fila["nombre"]
            }
        )
        return (
            f"Su frente ya está cerrado por {', '.join(otros)}. Es una ALTERNATIVA que "
            f"no hace falta conseguir, no algo pendiente."
        )
    return f"Falta, y sin él no se puede cerrar: {fila['que_desbloquea']}."


# ───────────────────────── la primera pantalla, en cuatro pasos ─────────────────────────


def steps_rows(
    *, species: str, sequence_loaded: bool, directory, designed: bool = False
) -> list[dict[str, object]]:
    """Los CINCO pasos, en orden, con lo que falta en cada uno.

    Son cinco desde que los ficheros de referencia se partieron en sus DOS MOMENTOS (ver
    `WHY_TWO_MOMENTS`): el paso 3 pide solo lo imprescindible para OBTENER candidatos
    —hoy, nada— y el paso 5 los que deciden cuales caen. El 5 va DESPUES del boton y
    solo se ve con `designed=True`: antes de diseñar no hay candidatos que refinar, y
    enseñarlo arriba es lo que hacia creer que habia que reunirlo todo para empezar.

    Ninguno de los dos BLOQUEA — un frente abierto deja los candidatos en INCOMPLETE,
    que es informacion, no un veto.
    """
    elegida = bool(str(species).strip()) and str(species).strip() != OTHER_SPECIES
    resumen = (
        reference_panel_summary(species, directory=directory) if elegida else None
    )
    diseñar = (
        design_files_rows(species, directory=directory) if elegida else None
    )
    return [
        {
            "numero": 1,
            "titulo": "Especie",
            "hecho": elegida,
            "abierto": not elegida,
            "visible": True,
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
            "visible": True,
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
            "titulo": "Ficheros de referencia — para diseñar",
            # HECHO cuando no hace falta ninguno, que es hoy. Antes estaba atado a que
            # no quedara NINGUN frente abierto, asi que el paso 3 se quedaba abierto
            # para siempre y se leia como algo que falta para poder seguir.
            "hecho": bool(diseñar and not diseñar["hacen_falta"]),
            "abierto": elegida and bool(diseñar and diseñar["hacen_falta"]),
            "visible": True,
            "cerrables": None,
            "total_frentes": None,
            "detalle": (
                f"Sólo lo imprescindible para obtener candidatos. {diseñar['texto']}"
                if diseñar
                else "Elige la especie primero: los ficheros que hacen falta dependen de ella."
            ),
        },
        {
            "numero": 4,
            "titulo": "Diseñar",
            "hecho": bool(designed),
            "abierto": elegida and bool(sequence_loaded),
            "visible": True,
            "cerrables": None,
            "total_frentes": None,
            "detalle": (
                "Se puede diseñar con frentes abiertos: los candidatos saldran "
                "INCOMPLETE y cada frente sin correr sale NOT_RUN en su columna. NOT_RUN "
                "no es PASS, y no haber contado no es contar cero."
            ),
        },
        {
            "numero": 5,
            "titulo": "Refinamiento",
            "hecho": bool(resumen and not resumen["abiertos"]),
            "abierto": bool(designed and resumen and resumen["abiertos"]),
            # SOLO DESPUES DE DISEÑAR. Antes de haber diseñado no hay candidatos que
            # refinar, y ponerlo arriba con los demas es lo que hacia creer que sin
            # estos ficheros no se puede empezar.
            "visible": bool(designed),
            "cerrables": resumen["cerrables"] if resumen else None,
            "total_frentes": resumen["total"] if resumen else None,
            "detalle": (
                f"Los candidatos de arriba son PROVISIONALES. Cada fichero de esta "
                f"sección cierra un frente y puede tumbar alguno. "
                f"{resumen['cerrables']} de {resumen['total']} frentes cerrados. "
                f"{FRONTS_VS_FILTERS}"
                if resumen
                else "Elige la especie primero: los ficheros que hacen falta dependen de ella."
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
    from pathlib import Path  # noqa: PLC0415

    from .identidad import file_fingerprint  # noqa: PLC0415
    from .presencia import ficheros_con_contenido  # noqa: PLC0415

    raiz = Path(directory)
    salida = {}
    for nombre in sorted(ficheros_con_contenido(raiz)):
        salida[nombre] = file_fingerprint((raiz / nombre).read_bytes())
    return salida


def run_freshness(
    kind: str, payload, *, actuales: dict[str, str], especie,
) -> dict[str, object]:
    """¿Sigue valiendo esta corrida? PASS / OBSOLETO / NOT_RUN, DERIVADO de los md5.

    La tabla de `insumos.CONSUMIDOS` dice qué consume cada tipo de corrida y dónde vive
    el md5 de cada insumo dentro del registro; aquí sólo se traduce el resultado a un
    estado. Los tres casos, y ninguno sobra: los ficheros son los mismos (PASS), alguno
    cambió (OBSOLETO), o no se ha podido comprobar (NOT_RUN) — que no es que coincida.
    """
    from .filters import FilterState  # noqa: PLC0415
    from .insumos import obsoleta  # noqa: PLC0415

    motivos = list(obsoleta(kind, payload, actuales=actuales, especie=especie))
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
    # La especie sale del PROYECTO: es la que decide como se llama cada fichero en el
    # deposito (`refseq_rna.fa` en raton, `refseq_rna_human.fa` en humano). Escribir el
    # nombre aqui seria la errata nº 47 otra vez, un piso mas arriba.
    especie = store.project.species
    filas = []
    for registro in store.records():
        if registro.kind not in CONSUMIDOS:
            continue
        frescura = run_freshness(
            registro.kind, registro.payload, actuales=hoy, especie=especie,
        )
        filas.append(
            {
                "tipo": registro.kind,
                "fecha": registro.date,
                "estado": frescura["estado"],
                "motivos": frescura["motivos"],
                "insumos": md5s_de_corrida(
                    registro.kind, registro.payload, especie=especie,
                ),
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
        "titulo": (
            f"Proyecto **{proyecto.slug}** — "
            f"{project_entry_count(len(store.records()))}"
        ),
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


def variant_rows(selection, *, available=None) -> list[dict[str, object]]:
    """El desempate de `mvm_sin_criptico` resuelto POR CANDIDATO, con su columna.

    **La regla ya estaba en el codigo y el modal no la aplicaba** —`apply_tiebreak` vive
    en `intron_design` desde que se tomo la decision— y lo unico que se enseñaba era la
    propuesta del PRIMER elegido. Novena vez del patron: la capacidad escrita y probada,
    el consumidor sin cablear.

    **Medido antes de aplicarla** (2026-09-04): sobre el panel murino los DIEZ empatan, y
    siempre entre las mismas dos alternativas —`C@4` y `T@4`—, que son el par sobre el que
    se decidio con la guia de `3utr:60`. Ninguno queda sin empate y ninguno empata entre
    alternativas distintas, asi que ninguna de las dos salvaguardas se dispara.

    **Y `empate` sale igual aunque el resultado repita.** Es la columna que sólo servira
    el dia que entre un candidato que NO empate — y ese dia es lo unico que lo dira. Un
    valor constante que se calcula y no se enseña es indistinguible de uno que nadie ha
    mirado.
    """
    from .intron_design import (  # noqa: PLC0415
        TIEBREAK_RATIONALE, apply_tiebreak, choose_break,
    )
    from .scaffold import SGEP_SCAFFOLD  # noqa: PLC0415

    filas: list[dict[str, object]] = []
    for elegido in selection.selection.chosen:
        guia = selection.window_of(elegido).evaluation.guide.replace("U", "T")
        fila: dict[str, object] = {
            "inicio": elegido.start,
            "base": "",
            "posicion": "",
            "motivo_flanco": "",
            "empate": False,
            "alternativas": "",
            "motivo": "",
            "estado": "",
        }
        try:
            corte = choose_break(SGEP_SCAFFOLD, guide=guia, available=available)
            elegida = apply_tiebreak(corte)
        except ShmirDesignError as exc:
            # rule2-ok: no se traga — el motivo entero va en la fila y la pagina lo
            # pinta. Y NO tumba a los demas candidatos: es la leccion de la errata nº 94.
            fila["estado"] = "PARA"
            fila["motivo"] = str(exc)
            filas.append(fila)
            continue
        if elegida is None:
            fila["estado"] = "NOT_RUN"
            fila["motivo"] = corte.reason
            filas.append(fila)
            continue
        fila["base"] = elegida.replacement
        fila["posicion"] = elegida.position
        fila["motivo_flanco"] = elegida.motif
        fila["empate"] = corte.chosen is None
        fila["alternativas"] = ", ".join(
            sorted(f"{c.replacement}@{c.position}" for c in corte.tied)
        )
        fila["estado"] = "EMPATE" if fila["empate"] else "SIN EMPATE"
        # EL CRITERIO VIAJA CON LA FILA: la app NO lo mide, y un valor que sale sin decirlo
        # se lee como si lo hubiera medido.
        fila["motivo"] = (
            TIEBREAK_RATIONALE if fila["empate"]
            else "Sin empate: gana en lo que la app SÍ mide, no hace falta el desempate."
        )
        filas.append(fila)
    return filas


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


#: LOS DOS EJES MEDIDOS que comparan las dos arquitecturas, con la corrida del 2026-09-05
#: detrás. Las cifras se transcriben aquí a proposito y no se derivan: salen de una corrida
#: de SpliceAI que este proyecto NO ejecuta —el fichero esta en `data/medido/` con su
#: procedencia— y derivarlas exigiria reanalizar 13.480 filas en cada repintado. Lo que se
#: deriva es la GEOMETRIA, que sí es nuestra.
INTRON_AXES_MEASURED = (
    ("dispersión del donante legítimo entre las 10 guías",
     "18,1 % (0,783-0,925)", "1,8 % (0,956-0,973)", "quimérico"),
    ("dispersión del aceptor legítimo",
     "10,3 % (0,778-0,858)", "0,9 % (0,985-0,994)", "quimérico"),
    ("crípticos intrónicos por encima del 5 % del legítimo",
     "2 (11,9 % y 6,1 %, en 1 de 10)", "ninguno", "quimérico"),
    ("tracto de polipirimidinas",
     "9 pirimidinas", "11 pirimidinas", "quimérico"),
    ("donante→punto de ramificación, MONTADO",
     "256 nt", "249-253 nt", "ninguno: no discrimina"),
)


def intron_architecture_note() -> str:
    """La comparación de las dos arquitecturas, para el INFORME y no sólo para la página.

    Decide qué se sintetiza, así que no puede vivir en un desplegable de la interfaz: es
    el principio nº 23, que este proyecto lleva once veces arreglando. La lectura y la
    retirada del contrapeso van con el nombre de quien la hizo.
    """
    from .introns import (
        THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES, WHY_THE_COUNTERWEIGHT_WAS_RETIRED,
    )

    lineas = [
        "ARQUITECTURAS DE INTRÓN — lo medido sobre las 20 construcciones",
        "",
        f"  {'eje':<52} {'mvm_actual':<32} {'intron_quimerico':<32} gana",
    ]
    for eje, mvm, qui, gana in INTRON_AXES_MEASURED:
        lineas.append(f"  {eje:<52} {mvm:<32} {qui:<32} {gana}")
    lineas += [
        "",
        f"  {WHY_THE_COUNTERWEIGHT_WAS_RETIRED}",
        "",
        f"  LECTURA: {THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES}",
    ]
    return "\n".join(lineas)


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


#: EL CONTEXTO POR DEFECTO NO PUEDE SER EL QUE LA PROPIA APP DESACONSEJA. Estaba en 0, y
#: con 0 el contexto son las dos piezas de 5 nt del plasmido — que `context_note` califica
#: de «esencialmente NINGUN contexto para un modelo entrenado con ventana de 10.000». Un
#: valor por defecto que la app avisa de que no sirve es una trampa, no un defecto.
#:
#: Se pone en el TOPE del control: con `aav_casete.fa` cargado el contexto sale de
#: secuencia REAL —hasta 3133/2067 nt, o sea el plasmido entero— y pedir mas del que hay
#: NO lo inventa (regla 1): se da lo que hay. Sin casete se cae solo a las piezas, con su
#: aviso, que es el mismo sitio donde estaba antes pero por haberlo intentado.
SPLICE_CONTEXT_MAX = 5000
SPLICE_CONTEXT_DEFAULT = SPLICE_CONTEXT_MAX


def splice_constructions(selection, *, intron_names, scaffold, starts=None,
                         cassette=None, context_nt=SPLICE_CONTEXT_DEFAULT):
    """Los pares candidato x intron, montados, CON lo que no se pudo montar.

    La guia sale de la ventana de cada candidato y no de ninguna secuencia que pase la
    pagina: ver la errata nº 94. Y un fallo en uno no tumba a los demas — devuelve las
    dos mitades.
    """
    from .spliceai import build_panel

    # EL CASETE SE COMPRUEBA AQUÍ, ANTES DE MONTAR NADA. La comprobación existía sólo al
    # otro lado —`parse_result` rechaza un resultado cuyo md5 no cuadra— y eso llega
    # cuando la corrida de SpliceAI ya se ha gastado. Ver
    # `WHY_THE_CASSETTE_IS_CHECKED_BEFORE` y la errata nº 129.
    ficha = cassette_deposit_check(cassette)
    return build_panel(
        selection, intron_names=tuple(intron_names),
        scaffold=scaffold, starts=starts, cassette=cassette,
        context_nt=int(context_nt), cassette_check=str(ficha["estado"]),
    )


def splice_panel_summary(panel, *, introns, candidates: int) -> dict[str, object]:
    """Reconcilia lo ANUNCIADO con lo EMITIDO, y desglosa POR INTRÓN.

    **Reportado (2026-09-05)**: el selector anuncia «10 candidatos, 20 pares», el FASTA
    trae 10 registros, y la app no avisa de que falta la mitad. El núcleo ya devolvía las
    dos mitades —`build_panel` da 10 construcciones y 10 fallidas con su motivo— y lo que
    faltaba es esto: la línea que las pone una al lado de la otra.

    Son **dos contadores del mismo suceso** —el del alcance y el del resultado— y hasta
    ahora nada los ataba. Aquí se derivan los dos de lo mismo, que es la única forma de
    que no puedan discrepar.

    **El desglose va POR INTRÓN, no por par.** El fallo es del intrón —`intron_quimerico`
    llega entero y no declara dónde va el módulo— así que repetir el mismo motivo diez
    veces, una por candidato, es lo que hace que se lea como ruido en vez de como «falta
    la mitad de la corrida».
    """
    anunciadas = int(candidates) * len(tuple(introns))
    emitidas = len(panel.constructions)
    por_intron = []
    for nombre in introns:
        hechas = [c for c in panel.constructions if c.intron == nombre]
        fallos = [f for f in panel.failed if f.intron == nombre]
        motivos = sorted({f.reason for f in fallos})
        por_intron.append({
            "intron": nombre,
            "emitidas": len(hechas),
            "fallidas": len(fallos),
            "motivo": motivos[0] if motivos else "",
            "motivos_distintos": len(motivos),
        })
    faltan = anunciadas - emitidas
    texto = (
        f"**{emitidas} de {anunciadas} consulta(s)** — {candidates} candidato(s) × "
        f"{len(tuple(introns))} intrón(es)."
    )
    if faltan:
        texto += (
            f" **FALTAN {faltan}**, y no se emiten: el FASTA de abajo lleva sólo las "
            f"{emitidas} que se pudieron montar."
        )
    return {
        "anunciadas": anunciadas,
        "emitidas": emitidas,
        "faltan": faltan,
        "parcial": bool(faltan),
        "por_intron": por_intron,
        "texto": texto,
    }


def splice_fasta_name(panel, *, species: str, introns, candidates: int) -> str:
    """El nombre del FASTA, con el ESTADO dentro cuando es parcial.

    **El fichero es el que viaja.** Quien lo descarga y lo pasa por SpliceAI no tiene la
    pantalla delante, así que un FASTA con la mitad de las consultas y un nombre que no lo
    dice es media entrega que parece completa. El estado va en el nombre, igual que en el
    informe (`raton_informe_parcial.docx`).
    """
    from .species import resolve  # noqa: PLC0415

    resumen = splice_panel_summary(panel, introns=introns, candidates=candidates)
    slug = resolve(species).slug if species else "sin_especie"
    if not resumen["parcial"]:
        return f"construcciones_{slug}.fa"
    return (
        f"construcciones_{slug}_PARCIAL_"
        f"{resumen['emitidas']}de{resumen['anunciadas']}.fa"
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


def splice_query_text(panel, *, introns=None, candidates=None):
    """El FASTA que se descarga, CON el estado del panel dentro del fichero.

    **Un nombre se pierde en el primer `mv`.** El estado iba sólo en el nombre
    (`construcciones_raton_PARCIAL_10de20.fa`) y eso dura hasta que alguien lo renombra.
    Aquí va también en el bloque de comentario y en CADA cabecera `>`, que es lo que
    ningún lector de FASTA tira.

    Acepta un panel o una lista de construcciones: sin panel no hay estado que declarar,
    y entonces **no se declara ninguno** — un fichero que no sabe de qué corrida viene no
    puede decir «COMPLETO».
    """
    from .spliceai import constructions_fasta

    construcciones = getattr(panel, "constructions", panel)
    resumen = None
    if hasattr(panel, "constructions") and introns is not None and candidates is not None:
        resumen = splice_panel_summary(panel, introns=introns, candidates=candidates)
    return constructions_fasta(construcciones, summary=resumen)


def splice_executor_text():
    from .spliceai import Disabled

    ejecutor = Disabled()
    return f"{ejecutor.name}: {ejecutor.why}"


def splice_edge_note(raw, *, constructions) -> str | None:
    """Qué filas del resultado NO entraron por el borde de la conversión, o `None`.

    La página la PINTA; no decide nada (regla 6). Existe porque saltarse filas en
    silencio es peor que rechazar el fichero: quien lo sube tiene que saber que su
    resultado no entró entero, aunque lo que se quedara fuera no apunte a ningún sitio.
    """
    from .spliceai import edge_note

    return edge_note(raw, constructions=constructions)


def splice_scan_from_result(raw, *, constructions):
    """Del TSV crudo al analisis. La pagina no parsea ni valida: llama aqui."""
    from .spliceai import scan_from_result

    return scan_from_result(raw, constructions=constructions)


def splice_result_rows(scan):
    """Una fila por par, YA comparada contra su propio referente interno."""
    from .spliceai import RELATIVE_THRESHOLD, donor_fraction

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
            # LA REGIÓN SEPARA lo que introduce la guía de lo que viene con el plásmido:
            # un críptico en `contexto5` está en las diez y cambiar de candidato no lo
            # quita. Medido: el más fuerte de las diez cae ahí (construcción:1516).
            "mejor_criptico_region": mejor.region if mejor else "",
            "gtgagcg_fraccion": (
                par.known_cryptic.fraction if par.known_cryptic else None
            ),
            "cripticos": len(par.cryptics),
            "contexto": f"{par.context_5}/{par.context_3}",
            # Rojo cuando el mejor criptico se ACERCA al legitimo. No es un veredicto:
            # es lo que el propio criterio dice que hay que mirar.
            "avisa": bool(mejor and mejor.fraction >= 0.5),
            "umbral_relativo": RELATIVE_THRESHOLD,
            # LA GUÍA MODULA EL DONANTE LEGÍTIMO: el mismo sitio puntúa distinto según
            # qué módulo lleve dentro. Medido: 0,664 a 0,871 entre las diez, un 31 %.
            "donante_vs_hermanas": donor_fraction(scan, par),
            # El marco del resultado frente al de la app. Sale a la vista aunque sea
            # PASS: un guardia que sólo se ve cuando falla no se sabe si corrió.
            "marco": par.frame_check.state.value,
            "marco_motivo": par.frame_check.reason,
        })
    return filas


def splice_modulation_rows(scan):
    """Cuánto mueve la guía al donante legítimo, POR INTRÓN. Es un dato, no un veredicto."""
    from .spliceai import donor_modulation

    return [
        {
            "intron": m.intron,
            "pares": m.pairs,
            "minimo": m.minimum,
            "maximo": m.maximum,
            "recorrido": m.spread,
            "mas_bajo": m.lowest,
            "mas_alto": m.highest,
        }
        for m in donor_modulation(scan)
    ]


def splice_modulation_note():
    from .spliceai import MODULATION_NOTE

    return MODULATION_NOTE


def splice_exclusive_rows(scan):
    """Que guias introducen cripticos que las otras NO. Lo accionable."""
    from .spliceai import exclusive_rows

    return exclusive_rows(scan)


def splice_module_of(construction, *, selection, scaffold):
    """El modulo de 149 nt de una construccion. Se DERIVA de la VENTANA de su candidato.

    No se guarda dentro de `Construction` a proposito: seria la misma secuencia en dos
    sitios, y dos copias de lo mismo acaban discrepando.

    **Y la guia se PIDE, no se recorta.** Esto hacia
    `target[candidate_start - 1 : +22]` con `target` pasado por la pagina — el mismo
    fallo de la errata nº 94, vivo por un segundo camino: la tabla de accesibilidad
    estructural del modal montaba el modulo con la guia de OTRO SITIO, con la forma
    correcta y sin ningun error. Un `start` del panel va en el marco de LO TILADO y
    cualquier otra secuencia produce un recorte valido que no es el suyo.
    """
    from .blocks import build_block
    from .spliceai import guide_of

    elegido = next(
        c for c in selection.selection.chosen
        if c.start == construction.candidate_start
    )
    return build_block(
        guide_of(selection, elegido), scaffold=scaffold,
    ).module


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

    from .spliceai import (  # noqa: PLC0415
        GUIDE_DEPENDENT_NOTE, MODULATION_NOTE, donor_modulation, guide_dependent_sites,
    )

    exclusivos = [f for f in splice_exclusive_rows(scan) if f["exclusivos"]]
    variables = guide_dependent_sites(scan)
    modulacion = donor_modulation(scan)
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
        # EL HALLAZGO DE LA CORRIDA, y va DESTACADO aunque el número sea pequeño. Lo que
        # se destaca no es el valor —no hay umbral absoluto que aplicar— sino que exista
        # un eje por el que el módulo modula el empalme y esté MEDIDO.
        "depende_de_la_guia": {
            "texto": (
                f"{GUIDE_DEPENDENT_NOTE} En esta corrida "
                + _sitios_que_varian(variables)
            ),
            "activo": bool(variables),
        },
        # Y el efecto general, que no lo esperaba nadie: el sitio LEGÍTIMO, que es el
        # mismo en todas, puntúa distinto según qué módulo lleve dentro.
        "modulacion": {
            "texto": f"{MODULATION_NOTE} {_modulacion_medida(modulacion)}",
            "activo": bool(modulacion),
        },
    }


def _sitios_que_varian(sitios) -> str:
    """La frase de los sitios que dependen de la guía, con LAS DIEZ detrás."""
    if not sitios:
        return (
            "no hay ningún sitio que varíe con la guía por encima del criterio "
            "declarado — y eso no es «no hay ninguno»: es que ninguno llega al criterio."
        )
    trozos = []
    for sitio in sitios:
        # LISTADO, no «presente»: en las demás está por debajo del umbral relativo, que
        # no es lo mismo que valer cero — de ahí no hay medida.
        trozos.append(
            f"{sitio.kind} en construcción:{sitio.position} ({sitio.region}), hasta "
            f"{_coma(sitio.maximum)} = {sitio.top_fraction:.0%} del donante legítimo — "
            f"listado en {len(sitio.listed)} de {len(sitio.scores)}; en las demás por "
            f"debajo del umbral relativo, que NO es cero"
        )
    return f"{len(sitios)} sitio(s): " + "; ".join(trozos) + "."


def _modulacion_medida(modulacion) -> str:
    trozos = [
        f"{m.intron}: de {_coma(m.minimum)} ({m.lowest.split('__')[-1]}) a "
        f"{_coma(m.maximum)} ({m.highest.split('__')[-1]}), un {m.spread:.0%}"
        for m in modulacion
    ]
    return "MEDIDO — " + "; ".join(trozos) + "." if trozos else ""


def _coma(valor: float) -> str:
    """El castellano usa coma decimal, y estos números se leen en pantalla."""
    return f"{valor:.4f}".replace(".", ",")


def splice_guide_dependent_rows(scan):
    """Una fila por sitio que varía con la guía, CON las diez puntuaciones.

    Van las diez y no un máximo: sin ellas no se ve si es una sola construcción la que
    se sale o si el sitio sube poco a poco — y eso cambia qué se hace con el dato.
    """
    from .spliceai import guide_dependent_sites  # noqa: PLC0415

    # De qué candidato es cada construcción, PEDIDO a la corrida. Antes se sacaba
    # partiendo el nombre por la cadena «3utr» y volviendo a pegarle el prefijo, así
    # que una corrida sobre el transcrito salía etiquetada `3utr:` igual (errata
    # nº 121) y además el nombre tenía que seguir teniendo esa forma para siempre.
    de_la_construccion = {
        par.construction: coords.label(par.candidate_start, par.candidate_frame)
        for par in scan.pairs
    }

    return [
        {
            "posicion": s.position,
            "tipo": s.kind,
            "region": s.region,
            "intron": s.intron,
            "minimo": s.minimum,
            "maximo": s.maximum,
            "veces": s.spread,
            "fraccion_del_legitimo": s.top_fraction,
            # LISTADO, no presente: `None` es «por debajo del umbral relativo», no cero.
            "listado_en": len(s.listed),
            "por_construccion": {
                de_la_construccion.get(n, n): v for n, v in s.scores.items()
            },
        }
        for s in guide_dependent_sites(scan)
    ]


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


def _ultima_fecha(store) -> str:
    """La fecha del ultimo registro, o vacio si no hay ninguno."""
    registros = store.records()
    return str(registros[-1].date) if registros else ""


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
            # EL NOMBRE VISIBLE, que puede no ser el slug.
            "nombre": almacen.project.display_name,
            # LA ULTIMA ACTIVIDAD, que es lo que hace falta para decidir cual borrar.
            # VACIO si no hay ningun registro: poner ahi la fecha de CREACION mezclaria
            # «no se ha tocado» con «se toco el dia que se creo», que es justo lo que hay
            # que distinguir.
            "ultima": _ultima_fecha(almacen),
            "vacio": not almacen.records(),
        })
    return filas


# ══════════ GESTIONAR LOS PROYECTOS: renombrar, llevarse el registro, borrar ══════════
#
# Los tres tocan un log que este proyecto tiene decidido que es **append-only y
# auditable**, asi que ninguno se hace a la ligera.
#
# **BORRAR es lo unico de la app que DESTRUYE un registro**, y no se parece a borrar un
# fichero de referencia: aquel se vuelve a bajar de UCSC, y una corrida de BLAST son
# horas de computo fuera de aqui que no se pueden repetir sin volver a correrlas. Por eso
# va con el plan delante y con la DESCARGA al lado — mismo criterio que `gestor.download`:
# lo que hace que el registro sea tuyo y no de la app.
#
# **RENOMBRAR** cambia el nombre visible y no el slug, y queda apuntado en el log: ver
# `store.ProjectStore.rename`.


#: COMO SE LLAMA UNA LINEA DEL HISTORIAL DE UN PROYECTO, en un solo sitio.
#:
#: Se llamaba «registro(s)» —«3 registro(s) · última 2026-09-02»— y se preguntó qué era:
#: *«de qué sirve tener registros diferentes si solo se accede a uno»*. La pregunta es la
#: prueba de que el nombre estaba mal: «registro» suena a **otra cosa que se puede
#: abrir**, y no lo es. Un proyecto tiene UN historial, y esto cuenta sus LINEAS — una
#: corrida guardada, una selección, un renombrado, una nota—, que es lo que se pierde si
#: se borra el proyecto y lo que dice si alguien lo ha tocado.
#:
#: Y va en una constante, no en cuatro f-strings, porque estaba escrito en cuatro sitios:
#: el desplegable, el cartel del proyecto abierto, el plan de borrado y su confirmación.
PROJECT_ENTRY_WORD = "anotaciones"
PROJECT_ENTRY_WORD_ONE = "anotación"

#: Y qué es una, dicho donde se elige el proyecto. No es una definición de manual: es la
#: contestación a la pregunta de arriba, y por eso dice también lo que NO es.
PROJECT_ENTRY_HELP = (
    "Cada proyecto lleva un historial propio, y una **anotación** es una línea suya: una "
    "corrida guardada, una selección, un cambio de nombre o una nota. No es otro proyecto "
    "ni algo que se abra por separado — se abre el proyecto y su historial viene entero."
)


def project_entry_count(n: int) -> str:
    """«1 anotación» / «3 anotaciones». El singular no se deja para la página."""
    cuantas = int(n)
    palabra = PROJECT_ENTRY_WORD_ONE if cuantas == 1 else PROJECT_ENTRY_WORD
    return f"{cuantas} {palabra}"


def project_options(base) -> dict[str, object]:
    """Los proyectos para el desplegable, CON su etiqueta ya montada.

    La etiqueta la monta esta capa y no la página (regla 6): decidir qué se enseña de cada
    proyecto —y sobre todo que la ÚLTIMA ACTIVIDAD salga al lado, que es lo que hace falta
    para saber cuál se puede borrar— es una decisión, no pintar.
    """
    filas = project_list(base)
    etiquetas = {}
    for fila in filas:
        trozos = [str(fila["nombre"])]
        if fila["nombre"] != fila["slug"]:
            trozos.append(f"({fila['slug']})")
        trozos.append(f"· {project_entry_count(int(fila['corridas']))}")
        trozos.append(
            f"· última {fila['ultima']}" if fila["ultima"] else "· SIN tocar"
        )
        etiquetas[fila["slug"]] = " ".join(trozos)
    return {
        "slugs": [str(f["slug"]) for f in filas],
        "etiquetas": etiquetas,
        "filas": filas,
    }


#: QUE CAMBIA Y QUE NO al renombrar, dicho junto al campo. Se lee antes de escribir el
#: nombre, que es cuando importa: quien crea que esto mueve la carpeta no lo toca.
PROJECT_RENAME_HELP = (
    "Cambia el nombre VISIBLE. La carpeta se sigue llamando igual —es lo que identifica "
    "al proyecto— y el cambio queda apuntado en su historial, con la fecha de hoy."
)


def project_rename(store, title: str, *, date: str) -> dict[str, object]:
    """Cambia el nombre visible del proyecto. La página no escribe nada."""
    registro = store.rename(title, date=date)
    return {
        "nombre": store.project.display_name,
        "slug": store.project.slug,
        "cambio": registro is not None,
        "texto": (
            f"Ahora se llama «{store.project.display_name}» (carpeta "
            f"{store.project.slug}). Queda apuntado en el log."
            if registro is not None
            else "Ya se llamaba así: no se ha escrito nada en el log."
        ),
    }


def project_export(base, slug: str) -> str:
    """El proyecto entero como TEXTO, para llevárselo antes de borrarlo."""
    from .store import ProjectStore  # noqa: PLC0415

    return ProjectStore.open(base, check_project_slug(slug)).export()


def project_delete_plan(base, slug: str) -> dict[str, object]:
    """Qué se pierde si se borra. NO borra nada.

    Un proyecto VACÍO y uno con doce corridas no pueden sonar igual: el primero no pierde
    nada y el segundo se lleva veredictos que no se pueden volver a calcular aquí.

    **NO pasa por `verify()`, y es deliberado**: un log con la cadena rota tiene que poder
    DESCARGARSE y BORRARSE — es justo el que sobra— y sólo lo que ESCRIBE en él exige que
    la cadena esté sana. Abortar aquí dejaría un proyecto corrupto imposible de quitar.
    """
    from .store import ProjectStore  # noqa: PLC0415

    almacen = ProjectStore.open(base, check_project_slug(slug))
    registros = almacen.records()
    por_tipo: dict[str, int] = {}
    for registro in registros:
        por_tipo[registro.kind] = por_tipo.get(registro.kind, 0) + 1
    fechas = [r.date for r in registros if str(r.date).strip()]
    lineas = [
        f"Borrar «{almacen.project.display_name}» (carpeta {almacen.project.slug}, "
        f"creado {almacen.project.created})."
    ]
    if registros:
        lineas.append(
            f"Se lleva {project_entry_count(len(registros))}: "
            + ", ".join(f"{n} × {tipo}" for tipo, n in sorted(por_tipo.items()))
            + f"; del {min(fechas)} al {max(fechas)}." if fechas else "."
        )
        lineas.append(
            "NO SE PUEDE DESHACER y lo que se va NO SE PUEDE VOLVER A CALCULAR aquí: "
            "una corrida de BLAST son horas de cómputo fuera de esta app, y un veredicto "
            "guardado es la única prueba de con qué fichero se sacó. Descárgalo antes si "
            "hay alguna posibilidad de que haga falta."
        )
    else:
        lineas.append(
            "No tiene ningún registro: no se pierde ningún veredicto. Es el caso normal "
            "de un proyecto que se creó para probar."
        )
    return {
        "slug": almacen.project.slug,
        "nombre": almacen.project.display_name,
        "registros": len(registros),
        "por_tipo": dict(sorted(por_tipo.items())),
        "vacio": not registros,
        "texto": " ".join(lineas),
    }


def project_delete(base, slug: str) -> str:
    """Borra el proyecto entero. Devuelve lo que se fue.

    Borrar uno que no existe ABORTA: devolver «hecho» sobre algo que no estaba se leería
    como que se borró, y quien lo lea dejará de buscarlo.
    """
    import shutil  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    limpio = check_project_slug(slug)
    plan = project_delete_plan(base, limpio)
    ruta = Path(base) / limpio
    try:
        shutil.rmtree(ruta)
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo borrar {ruta} ({exc}); el proyecto sigue ahí. Se dice en vez de "
            f"dar por hecho un borrado que no ocurrió."
        ) from exc
    return (
        f"Borrado «{plan['nombre']}» (carpeta {limpio}) con sus "
        f"{project_entry_count(int(plan['registros']))}. No se puede deshacer."
    )


# ─────────────────────── la fecha, con calendario y con HOY ───────────────────────
#
# Una fecha tecleada se equivoca en SILENCIO —`2026-09-02` y `2026-09-20` se parecen— y
# ya produjo una salida falsa: ante un `run_id` repetido, la tentacion era cambiar la
# fecha para que entrara (errata nº 48). Un calendario quita esa via.
#
# El FORMATO lo pone esta capa y no la pagina (regla 6): la conversion de lo que devuelve
# el widget a la forma del log es una decision con casos —vacio, rango, texto ya escrito—
# y una de ellas mete en el log algo con la forma correcta y sin significado.

DATE_PICKER_NOTE = (
    "La fecha se elige en el calendario. Va en cada registro del log y es lo que hace "
    "auditable un veredicto dentro de un año, así que no se teclea: una fecha a mano se "
    "equivoca en silencio."
)


def today_text() -> str:
    """Hoy, en la forma del log. Se DERIVA: no hay ninguna fecha escrita en el código."""
    import datetime  # noqa: PLC0415

    return datetime.date.today().isoformat()


def date_text(value) -> str:
    """Lo que devuelve el calendario → la forma del log. Vacío si no hay fecha.

    **Vacío NO es hoy**: el núcleo aborta sin fecha, que es lo correcto, y poner la de hoy
    sería inventarse el dato — la fecha de descarga de un fichero no es hoy.

    Una TUPLA aborta: `st.date_input` devuelve dos fechas en modo rango, y un rango
    convertido a texto entra en el log con la forma correcta y sin significado.
    """
    import datetime  # noqa: PLC0415

    if value is None or value == "":
        return ""
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip()
    raise ShmirDesignError(
        f"{value!r} no es una fecha: se esperaba una sola fecha del calendario. Un rango "
        f"—dos fechas— convertido a texto entraría en el log con la forma correcta y sin "
        f"significar nada. Se aborta."
    )


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


#: LOS COLORES DE LA PAGINA, DECLARADOS AQUI. Un color elegido en la pagina es una
#: decision sin test —es la razon por la que `REFINEMENT_STATES` los trae— y ademas
#: estaban repartidos en tres sitios del CSS con tres grises distintos y ninguna regla.
#:
#: El gris de las explicaciones se cambia por AZUL MARINO a peticion del responsable
#: (2026-09-03). No es sólo gusto: las explicaciones son la mitad del producto de esta
#: app —la frase que dice por qué un frente sigue abierto pesa tanto como la tabla— y en
#: gris claro se leen como letra pequeña, que es justo lo contrario de lo que son.
PAGE_COLORS = {
    #: El cuerpo de las explicaciones (`st.caption`) y la entradilla de cada paso.
    "texto": "#12305c",
    #: El rotulo pequeño «PASO N». Mismo tono, mas claro, para que ordene sin gritar.
    "rotulo": "#3a5f9e",
}


#: LO QUE PASA CUANDO SE HA RETOMADO UN PROYECTO, dicho donde estaba la pregunta.
#:
#: Se preguntó con la captura delante: «¿tengo que darle a guardar esta corrida en un
#: proyecto, o viniendo de uno abierto asumo que los cambios que haga se irán guardando?»
#: Que la pregunta se pueda hacer YA ES EL FALLO — la app la estaba haciendo dos veces, y
#: la segunda con la casilla sin marcar. Aquí se contesta una y en el sitio donde estaba.
PROJECT_RESUMED_NOTE = (
    "Proyecto abierto: **todo lo que hagas a partir de aquí se guarda solo** — las "
    "corridas de los modales y la selección van a su registro, con la fecha de abajo. No "
    "hay nada que marcar."
)

#: LO QUE PASA CON UN PROYECTO ELEGIDO AL QUE LE FALTA LA ENTRADA. No contesta los
#: pasos 1 y 2 —no puede: no tiene la secuencia— pero sigue elegido, y se abre en cuanto
#: la haya. Sin esto habia que volver a elegirlo a mano aqui abajo: el aviso de arriba
#: nombraba el paso y la app no lo daba (erratas nº 80 y nº 83).
PROJECT_PENDING_NOTE = (
    "Proyecto elegido arriba. Le falta su secuencia de entrada, así que los pasos de "
    "arriba hay que contestarlos — pero **el proyecto ya está elegido**: en cuanto subas "
    "la secuencia se abre solo, y **su entrada se queda guardada** para la próxima."
)

#: Y lo mismo arriba, en la tarjeta del paso 0, porque es donde se decide.
PROJECT_RESUME_HELP = (
    "Un proyecto guarda la secuencia con la que se trabajó, su anatomía y todo lo que se "
    "decidió después. Al abrirlo salen los mismos candidatos sin volver a subir nada, y "
    "lo que hagas a partir de ahí se sigue guardando en él."
)


#: LOS DOS BOTONES DE ZIP, CON NOMBRES QUE NO SE PUEDEN CONFUNDIR. DECIDIDO
#: (2026-09-04). Se llamaban «Descargar todo (zip)» y «Descargar todo (.zip)» —**un punto
#: de diferencia**— y bajan cosas distintas: uno los ficheros que acaba de generar el
#: diseño, el otro la copia de seguridad del volumen entero.
#:
#: No es un detalle de estilo: con esos dos nombres, un reporte de «no me baja el zip» no
#: identifica cuál, y **yo reproduje el que no era** —de punta a punta y midiendo— antes
#: de darme cuenta. Que dos botones sólo se distingan por un signo de puntuación es un
#: problema de la interfaz antes que de quien los confunde.
#:
#: Cada uno se llama por LO QUE BAJA, no por «todo»: qué es «todo» depende de dónde estés.
DOWNLOAD_BUTTON_RESULTS = "Descargar los resultados del diseño (.zip)"
DOWNLOAD_BUTTON_BACKUP = "Descargar la copia de seguridad del depósito (.zip)"


def downloads_zip(ficheros, *, species: str, date: str) -> dict[str, object]:
    """El zip de los ficheros GENERADOS: si no hay ninguno, NO se ofrece.

    **Reportado dos veces sobre el mismo botón (2026-09-04).** Primero: bajaba
    `shmir-design (3).zip` y no contenía nada — porque `ficheros` está vacío hasta que se
    pulsa «Seguir: las comprobaciones que faltan», y la sección se pintaba igual. Un zip
    de cero entradas son **22 bytes** y se abre sin nada dentro: peor que no tener el
    botón, porque parece una descarga hecha.

    Y después: la descarga empieza y no llega. Eso es lo otro —el zip cambiaba de bytes en
    cada repintado— y lo cierra `gestor.deterministic_zip`. Ver
    `WHY_A_ZIP_MUST_NOT_CHANGE`.

    **El nombre lleva especie y fecha.** Era la constante `shmir-design.zip`, así que dos
    corridas de dos días distintos bajaban con el mismo nombre y el navegador las numeraba
    `(1)`, `(2)`, `(3)` — que es exactamente cómo llegó el reporte, y no dice de qué
    corrida es ninguna.
    """
    from .gestor import deterministic_zip
    from .species import resolve

    if not ficheros:
        return {
            "hay": False,
            "datos": None,
            "nombre": "",
            "texto": (
                "Todavía no hay nada que descargar: los ficheros del diseño —FASTA de "
                "guías, tablas y hoja de pedido— se generan al pulsar **«Seguir: las "
                "comprobaciones que faltan»**. Antes de eso el zip saldría vacío, y un "
                "zip vacío parece una descarga hecha."
            ),
        }
    slug = resolve(species).slug if species else "sin_especie"
    return {
        "hay": True,
        "datos": deterministic_zip(ficheros, date=date),
        "nombre": f"shmir-design_{slug}_{date}.zip",
        "texto": f"{len(ficheros)} fichero(s) del diseño.",
    }


def connected_panel(resources) -> dict[str, object]:
    """La lista de ficheros conectados y, APARTE, lo que no se ha podido conectar.

    **Iban juntos, y no son lo mismo.** `ResourceSet.format_text` metia los avisos al
    final del mismo bloque que la lista, y ese bloque se pinta dentro de un desplegable
    COLAPSADO cuando hay algo conectado. O sea que la unica linea accionable de la
    pantalla —«falta el gen diana, y sin el todo sitio parece un off-target»— quedaba
    escondida detras de un clic, debajo de la lista de lo que sí funcionó.

    La lista es PROCEDENCIA: dice con qué ficheros se va a correr, y ahí un desplegable
    está bien — se consulta cuando se duda. Un aviso es una TAREA PENDIENTE: dice que
    algo no va a correr y qué hacer para que corra. Colapsar el segundo con el primero es
    la forma de que no se lea.
    """
    conectados = tuple(getattr(resources, "connected", ()) or ())
    avisos = tuple(getattr(resources, "notes", ()) or ())
    return {
        "titulo": f"Ficheros de referencia conectados ({len(conectados)})",
        "texto": resources.format_text(notes=False) if resources is not None else "",
        "avisos": list(avisos),
        # Colapsado si hay algo conectado: si no hay nada, la lista ES la noticia.
        "expandido": not conectados,
    }


def anatomy_from_payload(payload, source: str):
    """La inversa de `anatomy_payload`. Reconstruye la anatomia GUARDADA, no una nueva.

    Existe para que un proyecto se pueda REABRIR sin volver a subir el GenBank. Es una
    lectura, no una deduccion: si el payload no trae la frontera del 3'UTR, aqui no se
    inventa ninguna —`Anatomy` ya se niega a construirse con `SIN_RESOLVER`, y esa
    negativa es justo la que impide que un tilado corra todas las coordenadas en
    silencio—. Sin anatomia se devuelve `None` y quien llame lo dira.
    """
    from .anatomy import Anatomy, RegionSource

    if not payload:
        return None
    utr3 = payload.get("utr3")
    longitud = payload.get("length")
    if not utr3 or not longitud:
        return None
    try:
        procedencia = RegionSource(source)
    except ValueError as exc:
        raise ShmirDesignError(
            f"El proyecto declara que su anatomía viene de {source!r}, que no es una "
            f"procedencia conocida ({', '.join(r.value for r in RegionSource)}). Se "
            f"aborta: de la procedencia cuelga cuánta confianza darle a los tercios, y "
            f"elegir una por nuestra cuenta sería inventarla."
        ) from exc
    if procedencia is RegionSource.SIN_RESOLVER:
        return None
    cds = payload.get("cds")
    return Anatomy(
        length=int(longitud),
        utr3=(int(utr3[0]), int(utr3[1])),
        cds=(int(cds[0]), int(cds[1])) if cds else None,
        source=procedencia,
    )


#: COMO SE LLAMA LA CASILLA QUE ABRE UN PROYECTO, en un solo sitio. La pinta la barra
#: lateral y la NOMBRA el aviso de aquí abajo, así que si cada uno escribiera su versión,
#: el día que cambie el control el aviso mandaría a buscar algo que no existe — con la
#: forma correcta y sin dar ningún error (principio nº 13).
PROJECT_SAVE_TOGGLE = "Guardar esta corrida en un proyecto"

#: LO QUE LE FALTA A UN PROYECTO DE ANTES para poder reabrirse solo, dicho donde se lee.
#: No es un fallo suyo: se creo cuando el proyecto no guardaba la entrada. Y no se
#: reconstruye nada — del md5 no sale la secuencia (regla 1).
#:
#: **Y DICE EL ULTIMO PASO, que es donde estaba el hueco** (2026-09-04): «súbela como
#: siempre y el proyecto se abrirá igual» describe el 80 % del camino y se calla dónde se
#: abre. Quien lo lee sube la secuencia y espera que el proyecto se abra solo; el momento
#: en que se abre —y en que su entrada queda guardada— es al elegirlo en la barra lateral.
PROJECT_WITHOUT_ENTRY = (
    "A este proyecto le falta guardada la secuencia de entrada, así que no se puede sacar "
    "su panel sin ella. **Qué hacer**: sigue por los pasos de abajo y sube la misma "
    "secuencia con la que se creó; después, en la **barra lateral**, marca "
    f"«{PROJECT_SAVE_TOGGLE}» y elígelo en el desplegable «Proyecto». Ahí es donde se "
    "abre, con todo su registro, y donde **su secuencia queda guardada**: a partir de esa "
    "vez se reabre solo desde aquí arriba. Del md5 que sí tiene apuntado NO se puede "
    "recuperar la secuencia, y no se inventa."
)

PROJECT_WITHOUT_ANATOMY = (
    "Este proyecto no tiene resuelta la frontera del 3'UTR, así que no se puede volver a "
    "tilar sin decirla: vuelve a subir la secuencia con su GenBank —o declarando el CDS— "
    "y el proyecto se abrirá igual. Tilar con una frontera supuesta corre todas las "
    "coordenadas sin dar ningún error."
)


def project_resume(base, slug: str) -> dict[str, object]:
    """Todo lo que hace falta para volver a sacar el panel de un proyecto guardado.

    **Pedido (2026-09-03)**: que lo primero que pregunte la app sea si hay un proyecto
    guardado, y que abrirlo enseñe directamente los candidatos.

    Devuelve la ENTRADA —secuencia, especie y anatomía— no el panel: el tilado se vuelve
    a calcular, porque es determinista y cuesta 0,33 s. Guardar lo derivado daría dos
    definiciones del panel y ninguna que mande, que es el patrón que este proyecto lleva
    persiguiendo desde `resolve.py`.
    """
    from .store import ProjectStore

    almacen = ProjectStore.open(base, slug)
    proyecto = almacen.project
    anatomia = anatomy_from_payload(proyecto.anatomy, proyecto.anatomy_source)
    if not proyecto.sequence:
        motivo = PROJECT_WITHOUT_ENTRY
    elif anatomia is None:
        motivo = PROJECT_WITHOUT_ANATOMY
    else:
        motivo = ""
    return {
        "reabrible": not motivo,
        "motivo": motivo,
        "slug": proyecto.slug,
        "nombre": proyecto.display_name,
        "especie": proyecto.species,
        "secuencia": proyecto.sequence or None,
        "anatomia": anatomia if not motivo else None,
        "almacen": almacen,
    }


def blast_run_from_upload(*, raw: str, query, params, declared_query_md5: str,
                          panel_names, database: dict, date: str, uploaded_by: str):
    """Valida el `-outfmt 6` y construye la corrida. La pagina no valida nada.

    Las DOS comprobaciones de `blast_store.validate_upload` abortan: el md5 del FASTA de
    consulta declarado tiene que ser el que genero la app, y toda `query` del resultado
    tiene que estar en el panel. Es el fallo del CSV de miRarchitect.

    EL `run_id` SE DERIVA aqui y no lo pasa la pagina (errata nº 48): lleva el md5 del
    resultado, asi que repetir la corrida el mismo dia entra sin chocar y subir dos veces
    el MISMO fichero si aborta. Que lo montara la pagina era ademas logica en la pagina
    —el id decide si una corrida entra o se rechaza— o sea regla 6.
    """
    from .blast_store import BlastDatabase, BlastRun, validate_upload
    from .identidad import result_fingerprint, run_id as _run_id

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
        run_id=_run_id(
            kind="corrida_blast", date=date, result_md5=result_fingerprint(raw),
        ),
        date=date, uploaded_by=uploaded_by, params=params,
        database=base, query=query, raw=raw,
    )


def seed_run_from_scan(scan, *, date: str, ran_by: str):
    """La corrida de colision de seed, lista para guardar. El id se DERIVA."""
    from .identidad import result_fingerprint, run_id as _run_id
    from .seed_store import SeedRun

    return SeedRun.create(
        run_id=_run_id(
            kind="corrida_seed", date=date, result_md5=result_fingerprint(scan.raw),
        ),
        date=date, ran_by=ran_by, scan=scan,
    )


def offtarget_run_from_scan(scan, *, date: str, ran_by: str):
    """La corrida de carga de off-targets, lista para guardar. El id se DERIVA."""
    from .identidad import result_fingerprint, run_id as _run_id
    from .offtarget_store import OfftargetRun

    return OfftargetRun.create(
        run_id=_run_id(
            kind="corrida_offtarget", date=date, result_md5=result_fingerprint(scan.raw),
        ),
        date=date, ran_by=ran_by, scan=scan,
    )


def splice_run_from_scan(scan, *, raw: str, date: str, ran_by: str,
                         executor: str, folding=None):
    """La corrida del cuarto modal, lista para guardar. La pagina no construye objetos.

    El id se DERIVA, igual que en los otros tres: el de este modal era el unico que ni
    siquiera llevaba el tipo (`especie-fecha` a secas), asi que ademas de no admitir dos
    corridas al dia habria chocado con cualquier otro modal que usara ese formato.
    """
    from .identidad import result_fingerprint, run_id as _run_id
    from .splice_store import SpliceRun

    return SpliceRun.create(
        run_id=_run_id(
            kind="corrida_empalme", date=date, result_md5=result_fingerprint(raw),
        ),
        date=date, ran_by=ran_by, executor=executor,
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


def library_note(env=None) -> str:
    """Qué le pasa a lo guardado, DERIVADO del estado y no una frase fija.

    La versión anterior era una cadena que explicaba el contrafactual —«dentro de la
    imagen desaparecería en el siguiente redespliegue»—, cierta como razón y falsa como
    descripción: quien la leía entendía que lo guardado se borra al desplegar, que es lo
    contrario de lo que hace la app. Cuál de las dos frases es verdad depende de si el
    directorio de trabajo está declarado, así que la decide quien lo sabe.
    """
    from .biblioteca import NOT_ON_A_VOLUME, SURVIVES, base_por_defecto  # noqa: PLC0415
    from .trabajo import is_declared, reference_dir  # noqa: PLC0415

    # La RUTA se deriva igual que la usa `biblioteca`, y con el mismo `env`: decir
    # dónde vive algo mirando otra variable que la que se usa para escribirlo es
    # cómo se llega a una pantalla que contradice al código.
    donde = reference_dir(env) / "biblioteca" if env is not None else base_por_defecto()
    cabeza = SURVIVES if is_declared(env) else NOT_ON_A_VOLUME
    return (
        f"{cabeza} Está en `{donde}`. Lo guardado aquí NO cierra ningún "
        f"frente y no entra en el manifiesto: es sólo para no volver a buscar el mismo "
        f"fichero en cada sesión."
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


def project_open(base, slug: str, *, expect_md5: str | None = None,
                 sequence: str | None = None):
    """Abre un proyecto. Si se declara `expect_md5` y NO cuadra, se RECHAZA.

    Es el fallo del CSV de miRarchitect por la puerta de la persistencia: seguir
    apuntando corridas de OTRA secuencia en el log de esta. El log quedaria coherente de
    forma, la cadena de md5 no se romperia, y el resultado seria un proyecto que mezcla
    dos entradas sin que nada lo delate.

    `sequence` es la entrada que quien abre ya tiene delante, y sirve para RELLENAR la de
    un proyecto de antes de que se guardara (`ProjectStore.open`). Se rellena solo si su
    md5 es el que el proyecto declara, que es la misma comprobacion que hay dos lineas
    mas abajo — asi, una secuencia que no sea la suya no puede escribirse ni entrar.
    """
    from .store import ProjectStore

    almacen = ProjectStore.open(base, check_project_slug(slug), sequence=sequence)
    # LA CADENA SE RECALCULA AL ABRIR, y hasta 2026-08-27 NO se recalculaba nunca:
    # `verify()` estaba escrita, testada, y sin ningún llamador fuera de sus tests. Es
    # el mismo patrón que `store.save_*` y que `page_run` — la cuarta vez— pero sobre un
    # GUARDIA, que es peor: no es trabajo que no llega a una salida, es una comprobación
    # que no comprueba. Y su momento natural es justo éste: el log se edita entre
    # sesiones, así que comprobarlo sólo al escribirlo no protege de nada.
    almacen.verify()
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


#: LOS ALMACENES QUE HAY, en un solo sitio. `load_stores` los construye de aqui y
#: `STORE_FOR_FRONT` se cruza contra esto: asi un quinto almacen no puede entrar sin que
#: el test note que no llega a ninguna columna — que es como `offtarget_seed` se quedo
#: sin la suya.
STORES = ("blast", "seed", "offtarget", "splice")


def load_stores(store) -> dict[str, object]:
    """Los almacenes de `STORES`, reconstruidos desde el log. Un solo sitio, no cuatro."""
    from .store import (
        load_blast_store,
        load_offtarget_store,
        load_seed_store,
        load_splice_store,
    )

    cargadores = {
        "blast": load_blast_store,
        "seed": load_seed_store,
        "offtarget": load_offtarget_store,
        "splice": load_splice_store,
    }
    if set(cargadores) != set(STORES):
        raise ShmirDesignError(
            f"`STORES` dice {sorted(STORES)} y aquí hay cargador para "
            f"{sorted(cargadores)}. Se aborta: un almacen que se carga sin estar "
            f"declarado no pasa por el cruce que le exige una columna."
        )
    return {nombre: cargadores[nombre](store) for nombre in STORES}


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


#: LOS AJUSTES SON DE SESION, Y ESO SE DICE. Los controles de la barra lateral son estado
#: de Streamlit: al recargar vuelven a su valor por defecto. NO se restauran desde el
#: proyecto a proposito —restaurarlos daria dos fuentes de verdad en la barra lateral, que
#: es la casilla global «Usar los de data/reference/» otra vez— pero callarlo hace creer
#: que se corrio con una configuracion cuando se corrio con otra.
SETTINGS_ARE_SESSION_ONLY = (
    "Los ajustes de la barra lateral son **de esta sesión**: al recargar la página "
    "vuelven a su valor por defecto y NO se restauran desde el proyecto. Lo que sí queda "
    "registrado es la configuración con la que se guardó cada selección, atada a ella."
)

#: LO QUE PASA CUANDO LA CONFIGURACION DE AHORA NO ES LA DE LA SELECCION GUARDADA. Mismo
#: caso que `OBSOLETO`: se hizo, y ya no vale con lo que hay ahora.
CONFIGURATION_DRIFTED = (
    "**La configuración de ahora NO es la que produjo la selección guardada.** El panel "
    "que se ve en pantalla se ha calculado con otros ajustes, así que ya no corresponde "
    "a lo registrado — y eso no da ningún error por sí solo. O se vuelve a la "
    "configuración de la selección, o se guarda una selección nueva con ésta."
)

#: Y lo que pasa con una seleccion de ANTES de que esto existiera.
CONFIGURATION_NOT_RECORDED = (
    "La selección guardada no registró con qué configuración se produjo: es anterior a "
    "que se guardara. NO se puede comprobar si coincide con la de ahora, y no haber "
    "podido comprobarlo no es que coincida."
)


def run_configuration(*, config, thresholds, accessibility: bool, scaffold,
                      resources=None) -> dict:
    """Lo que hay que saber para reproducir un panel, en una estructura serializable.

    Es lo que va atado a la seleccion. Todo lo que puede mover QUE candidatos salen o en
    que orden: los umbrales, la configuracion de seleccion, si se pidio la accesibilidad,
    el andamio, y los ficheros conectados CON SU md5 —un fichero cambiado debajo cambia
    el resultado igual que un umbral—.
    """
    from dataclasses import fields, is_dataclass  # noqa: PLC0415

    def _plano(objeto):
        if objeto is None:
            return None
        if not is_dataclass(objeto):
            return str(objeto)
        salida = {}
        for campo in fields(objeto):
            valor = getattr(objeto, campo.name)
            # Enums y tuplas de enums a texto: su `repr` cambiaria con el codigo.
            if isinstance(valor, tuple):
                valor = [
                    [getattr(x, "value", str(x)) for x in v]
                    if isinstance(v, tuple) else getattr(v, "value", v)
                    for v in valor
                ]
            else:
                valor = getattr(valor, "value", valor)
            salida[campo.name] = valor
        return salida

    return {
        "seleccion": _plano(config),
        "umbrales": _plano(thresholds),
        "accesibilidad": bool(accessibility),
        "andamio": {
            "nombre": getattr(scaffold, "name", ""),
            "verificado": bool(getattr(scaffold, "verified", False)),
        },
        # LOS FICHEROS CONECTADOS, con lo que los identifique. Se admite un mapa
        # nombre→md5 y tambien la lista de descripciones que ya trae `ResourceSet`
        # —`describe_connected` las emite con version y md5 dentro—, porque lo que hace
        # falta es que la huella cambie cuando cambie el fichero, no un formato concreto.
        "ficheros": _ficheros_de(resources),
    }


def _ficheros_de(resources) -> list[str] | dict[str, str]:
    if not resources:
        return []
    if hasattr(resources, "connected"):
        resources = resources.connected
    if isinstance(resources, dict):
        return dict(sorted((str(k), str(v)) for k, v in resources.items()))
    return sorted(str(x) for x in resources)


def selection_configuration_state(store, *, actual: dict | None) -> dict[str, object]:
    """¿La configuracion de ahora es la que produjo la seleccion guardada?

    Se DERIVA comparando huellas, igual que `insumos.obsoleta`. Guardar la configuracion
    al lado sin atarla no habria servido: la discrepancia seguiria siendo invisible.
    """
    from .identidad import configuration_fingerprint  # noqa: PLC0415
    from .store import selected_configuration  # noqa: PLC0415

    if store is None:
        return {"estado": "", "coincide": None, "texto": SETTINGS_ARE_SESSION_ONLY}
    guardada, huella = selected_configuration(store)
    if not huella:
        if not store.records("seleccion"):
            return {"estado": "", "coincide": None, "texto": SETTINGS_ARE_SESSION_ONLY}
        return {
            "estado": "NO_REGISTRADA",
            "coincide": None,
            "texto": f"{CONFIGURATION_NOT_RECORDED} {SETTINGS_ARE_SESSION_ONLY}",
        }
    if actual is None:
        return {
            "estado": "NO_REGISTRADA",
            "coincide": None,
            "texto": f"{CONFIGURATION_NOT_RECORDED} {SETTINGS_ARE_SESSION_ONLY}",
        }
    coincide = configuration_fingerprint(actual) == huella
    return {
        "estado": "" if coincide else "CAMBIADA",
        "coincide": coincide,
        "texto": (
            SETTINGS_ARE_SESSION_ONLY if coincide
            else f"{CONFIGURATION_DRIFTED} {SETTINGS_ARE_SESSION_ONLY}"
        ),
        "guardada": guardada,
    }


def save_selection(store, *, starts, date: str, by: str, configuration=None):
    """La seleccion manual. Una nueva NO pisa la vieja: la SUCEDE."""
    from .store import save_selection as _guardar

    return _guardar(
        store, starts=starts, date=date, by=by, configuration=configuration,
    )


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
    # LA PRIMERA PASADA NO CUENTA NINGUNA carga de seed: solo hace falta para SELECCIONAR,
    # y la seleccion no la mira. Contarlas aqui era el gasto entero —medido: 200 s con un
    # transcriptoma de 84 MB, contra 10 s acotando—; la segunda pasada la cuenta en el
    # panel, que es donde se lee. `frozenset()` es «en ninguna», que NO es lo mismo que
    # `None` («en todas»): son dos valores porque son dos cosas.
    tiling = tile_utr(
        sequence, anatomy=anatomy, seeds=seeds, thresholds=thresholds,
        accessibility=accessibility, species=species, tile_range=tile_range,
        seed_load_starts=frozenset(), **extra,
    )
    # `default_config()` es la configuracion DEL PROYECTO: panel de 10 y cuota de
    # inmunes emparejada con su frontera. `SelectionConfig()` a secas no la lleva, y
    # usarlo aqui dejaba el panel con tres inmunes sin decirlo.
    seleccion = select_from_report(
        tiling, config if config is not None else default_config()
    )
    # LA CARGA DE SEED SE CUENTA EN EL PANEL Y NO EN LAS 407 ELEGIBLES, y por eso se
    # tila DOS veces. Medido el 2026-09-02: cada ventana barre el transcriptoma entero
    # —0,4-0,7 s sobre 84 MB— asi que hacerlo en todas son 3-4 MINUTOS, y la pagina
    # rehace la corrida en CADA repintado: cada tecla, cada boton, cada subida. Con el
    # panel son diez, unos segundos.
    #
    # Dos tilados cuestan 0,33 s cada uno y el resultado es identico —la funcion es
    # determinista y las entradas son las mismas—; el segundo solo añade la columna.
    # No se cuela ningun criterio nuevo: la seleccion se rehace sobre el informe que YA
    # lleva la carga, con la misma configuracion.
    #
    # Y no se hace nada de esto si no hay transcriptoma cargado: sin el, `carga_seed`
    # ya salia `None` y la segunda pasada no aportaria nada.
    if extra.get("utr3_set") is not None:
        panel = frozenset(chosen_starts(seleccion))
        tiling = tile_utr(
            sequence, anatomy=anatomy, seeds=seeds, thresholds=thresholds,
            accessibility=accessibility, species=species, tile_range=tile_range,
            seed_load_starts=panel, **extra,
        )
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
        # DE LAS TARJETAS, que es lo que la página pinta. Salía de `front_help_rows`, que
        # era la segunda fuente y no sabía qué frentes cierra el panel: el golden de la
        # página podía decir NOT_RUN de una tarjeta pintada en verde (errata nº 103).
        *_tabla(
            [
                {
                    "frente": t["frente"],
                    "estado": "CERRADO" if t["estado"] == "HECHO" else "NOT_RUN",
                    "donde_se_cierra": t["donde_se_cierra"],
                    # LOS DOS, porque son EXCLUYENTES por construccion: el motivo de un
                    # frente cerrado vive en `resultado` (la tarjeta lo pinta en verde) y
                    # el de uno abierto en `motivo`. Leer solo uno dejaba la fila del
                    # cerrado SIN motivo en la instantanea — el arreglo de la errata
                    # nº 108 se llevaba por delante justo lo que este golden mira.
                    "motivo": t["resultado"] or t["motivo"],
                }
                for t in front_card_rows(corrida, species=species)
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
            # `utr3_position` acaba de convertir al 3'UTR: el marco es su resultado,
            # no un supuesto.
            posicion = coords.label(u, coords.Frame.UTR3)
            lineas.append(
                f"    {posicion:<11} {choice.asymmetry:+.2f}  "
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
    """Huella de lo que produjo una corrida. Ver `WHY_A_RUN_FINGERPRINT`.

    SOLO CALCULA. Quien decide si lo cacheado sigue valiendo es `cached_run`.
    """
    import hashlib

    crudo = "|".join(repr(p) for p in partes)
    return hashlib.md5(crudo.encode("utf-8")).hexdigest()


def cached_run(guardado, huella: str) -> dict:
    """¿Sirve todavía la corrida cacheada? El GUARDIA, y vive aquí, no en la página.

    Estaba en la página —`guardado[1] if guardado and guardado[0] == huella else None`—
    y **copiado en los dos modales**, así que la regla podía divergir entre ellos y no
    tenía test. Lo cazó la auditoría de guardias: `run_fingerprint` sólo calcula el
    resumen, y una entrada de la tabla en la que ninguna pieza abortaba señaló que la
    comprobación de verdad estaba en otro sitio.

    Devuelve el resultado si la huella cuadra, `None` si no, y el motivo cuando hay algo
    cacheado que ya no vale — que es lo que hay que enseñar para que un resultado viejo
    no se lea como el de la corrida que se está viendo.
    """
    if not guardado:
        return {"resultado": None, "caducado": False, "aviso": ""}
    caducado = guardado[0] != huella
    return {
        "resultado": None if caducado else guardado[1],
        "caducado": caducado,
        "aviso": WHY_A_RUN_FINGERPRINT if caducado else "",
    }


# ═══════════════════════════ los controles del experimento ═══════════════════════════
#
# Regla 6: la pagina no decide nada. Aqui se resuelve QUE candidato controla cada
# construccion, con que ficheros se cierran sus frentes y que columnas salen; la pagina
# pinta lo que sale de `control_panel`.

#: Cuantas construcciones se emiten por tipo en la pantalla. No es una eleccion entre
#: ellas —no se elige— sino cuantas caben para poder compararlas de un vistazo.
CONTROLES_POR_TIPO = 5


def control_choices(selection) -> list[dict[str, object]]:
    """Los candidatos del panel para los que se puede construir un control.

    La eleccion de CUAL se controla es del usuario y no de la app: cualquiera del panel
    vale, y el que se elija cambia las dos construcciones enteras.
    """
    marco = coords.tiled_frame(getattr(selection, "anatomy", None))
    return [
        {"inicio": choice.start, "etiqueta": coords.label(choice.start, marco),
         "guia": selection.window_of(choice).evaluation.guide}
        for choice in selection.selection.chosen
    ]


def control_panel(selection, *, start: int, target: str, target_label: str,
                  species: str = "", mature=None, abundance=None, transgene_db=None,
                  wanted: int = CONTROLES_POR_TIPO) -> dict[str, object]:
    """Todo lo que la pagina necesita para el bloque de controles, ya decidido.

    Un solo punto de entrada a proposito: si cada tabla llamara a `controles.py` por su
    cuenta, la de scrambled y la de seed-mismatch podrian acabar corriendo con ficheros
    distintos —una con `mature.fa` y otra sin el— y las dos parecerian medidas.
    """
    from .controles import (CUANTOS_CAMBIOS_SIN_DECIDIR, LOS_DOS_NO_SE_SUSTITUYEN,
                            ORDEN_NO_ES_RANKING, PLEGADO_NO_DISCRIMINA,
                            mismatch_comparison, scrambled_candidates,
                            seed_mismatch_candidates)

    marco = coords.tiled_frame(getattr(selection, "anatomy", None))
    elegido = next(
        (c for c in selection.selection.chosen if c.start == int(start)), None
    )
    if elegido is None:
        raise ShmirDesignError(
            f"{coords.requested(int(start), marco)} no está en el panel de esta "
            f"corrida, así que no se puede "
            f"construir un control para él. Se aborta en vez de emitir controles de un "
            f"candidato que nadie eligió."
        )
    guia = selection.window_of(elegido).evaluation.guide
    origen = coords.label(elegido.start, marco)
    comun = dict(
        origin_label=origen, target=target, target_label=target_label,
        mature=mature, abundance=abundance, transgene_db=transgene_db, species=species,
    )
    scrambled = scrambled_candidates(guia, wanted=wanted, **comun)
    mismatch = {
        cambios: seed_mismatch_candidates(guia, changes=cambios, wanted=wanted, **comun)
        for cambios in (2, 3)
    }
    return {
        "origen": origen,
        "guia": guia,
        "scrambled": [c.row() for c in scrambled],
        "seed_mismatch": {k: [c.row() for c in v] for k, v in mismatch.items()},
        "comparacion": mismatch_comparison(
            guia, origin_label=origen, target=target,
            target_label=target_label, mature=mature, species=species,
        ),
        "fichas": [c.render() for c in scrambled[:1]]
                  + [v[0].render() for v in mismatch.values()],
        "avisos": [
            ORDEN_NO_ES_RANKING, PLEGADO_NO_DISCRIMINA, CUANTOS_CAMBIOS_SIN_DECIDIR,
            LOS_DOS_NO_SE_SUSTITUYEN,
        ],
    }


def cassette_sequence(tiling) -> str | None:
    """La secuencia del casete conectado, o `None`. Vivía en la página y estaba ROTA.

    `_casete_de` hacía `records[0].sequence` sobre lo que devuelve
    `specificity.load_database`, que es un `dict[str, str]`: indexar un diccionario por
    `0` y pedirle `.sequence` a una cadena. La rama nunca había corrido porque el casete
    nunca se había conectado en la página, así que el `getattr(..., None)` de delante la
    tapaba entera — y el día que alguien subiera `aav_casete.fa` el cuarto modal moriría
    con un `KeyError: 0`. Es la regla de la errata nº 31: una combinación que ningún
    test recorre de punta a punta NO está probada, por muchos tests que tengan sus piezas.

    Y decidir CUÁL registro es el casete es una decisión, así que vive aquí y no en la
    página (regla 6). Con más de uno se ABORTA: el contexto de empalme tiene que salir
    de UNA molécula, y concatenar dos inventa una juntura que no existe.
    """
    base = getattr(tiling, "transgene_db", None)
    registros = getattr(base, "records", None) if base is not None else None
    if not registros:
        return None
    if len(registros) > 1:
        raise ShmirDesignError(
            f"El casete cargado trae {len(registros)} registros "
            f"({', '.join(list(registros)[:3])}…) y el contexto de empalme tiene que "
            f"salir de UNA molécula. Se aborta en vez de elegir uno por orden de "
            f"aparición o de concatenarlos, que inventaría una juntura."
        )
    return next(iter(registros.values()))


#: Los tres estados, PEDIDOS a `spliceai`, que es quien los lleva en la construcción.
#: Redefinirlos aquí daría dos listas que un día dicen cosas distintas.
from .spliceai import (  # noqa: E402,PLC0415
    CASETE_COINCIDE, CASETE_NO_COINCIDE, CASETE_SIN_COMPROBAR,
)

#: Por qué esta comprobación va AL EMITIR y no al validar.
WHY_THE_CASSETTE_IS_CHECKED_BEFORE = (
    "Entre emitir el FASTA y subir el resultado hay una corrida de SpliceAI, que es "
    "tiempo fuera de esta app. Si el casete con el que se emitió no es el del depósito, "
    "el resultado se rechaza al volver —correctamente— pero la corrida ya está gastada. "
    "La comprobación tiene que estar donde todavía sirve de algo."
)


def cassette_deposit_check(cassette, *, directory=None) -> dict[str, object]:
    """¿El casete que se va a usar es el que hay AHORA en el depósito?

    Lo compara por md5 de la secuencia NORMALIZADA, leyendo el depósito por el mismo
    cargador que usa el rol `transgen` —`specificity.load_database`— para que los dos
    lados hablen la misma normalización: comparar una lectura cruda con una normalizada
    daría «no coincide» siempre y por el motivo equivocado.

    El nombre del fichero se le PIDE a `manifest.ROLES`. Escribirlo aquí sería una
    segunda definición de la misma correspondencia, y el día que el rol apunte a otro
    fichero esta comprobación miraría el de antes sin dar ningún error (principio nº 13).

    Devuelve SIEMPRE los dos md5 y las dos longitudes cuando los tiene: «no coincide» a
    secas no se puede investigar, y lo que hace falta para investigarlo es exactamente
    lo que esta función ya ha calculado.
    """
    from .identidad import result_fingerprint  # noqa: PLC0415
    from .manifest import ROLES  # noqa: PLC0415
    from .specificity import load_database  # noqa: PLC0415
    from .trabajo import reference_dir  # noqa: PLC0415

    rol = next(r for r in ROLES if r.role == "transgen")
    carpeta = Path(directory) if directory is not None else reference_dir()
    ruta = carpeta / rol.filename

    en_uso = "".join(str(cassette).split()).upper() if cassette else ""
    ficha: dict[str, object] = {
        "fichero": rol.filename,
        "directorio": str(carpeta),
        "md5_en_uso": result_fingerprint(en_uso) if en_uso else "",
        "nt_en_uso": len(en_uso),
        "md5_deposito": "",
        "nt_deposito": 0,
    }
    if not en_uso:
        return {
            **ficha, "estado": CASETE_SIN_COMPROBAR,
            "motivo": (
                "No hay ningún casete conectado, así que no hay nada que comparar con "
                f"{rol.filename}. El contexto exónico saldrá de las piezas del plásmido "
                "y la cabecera lo dirá. NO se da por bueno: no comprobado no es "
                "comprobado."
            ),
        }
    if not ruta.is_file():
        return {
            **ficha, "estado": CASETE_SIN_COMPROBAR,
            "motivo": (
                f"No hay {rol.filename} en {carpeta}, así que no se puede comprobar si "
                f"el casete en uso es el del depósito. Se emite diciéndolo, no callando: "
                f"un silencio aquí se lee como «coincide»."
            ),
        }

    deposito = "".join(
        str(
            next(iter(load_database(
                str(ruta), name=rol.what, version="deposito",
            ).records.values()))
        ).split()
    ).upper()
    ficha["md5_deposito"] = result_fingerprint(deposito)
    ficha["nt_deposito"] = len(deposito)

    if ficha["md5_en_uso"] == ficha["md5_deposito"]:
        return {
            **ficha, "estado": CASETE_COINCIDE,
            "motivo": (
                f"El casete en uso es {rol.filename} del depósito "
                f"({ficha['nt_deposito']} nt, md5 {str(ficha['md5_deposito'])[:8]}…)."
            ),
        }
    return {
        **ficha, "estado": CASETE_NO_COINCIDE,
        "motivo": (
            f"El casete con el que se iban a montar las construcciones NO es el de "
            f"{rol.filename}: en uso {ficha['nt_en_uso']} nt "
            f"(md5 {str(ficha['md5_en_uso'])[:8]}…) y en el depósito "
            f"{ficha['nt_deposito']} nt (md5 {str(ficha['md5_deposito'])[:8]}…), "
            f"{abs(int(ficha['nt_en_uso']) - int(ficha['nt_deposito']))} nt de "
            f"diferencia. Las construcciones saldrían de un casete y el resultado se "
            f"validaría contra el otro, así que la corrida de SpliceAI se perdería. "
            f"{WHY_THE_CASSETTE_IS_CHECKED_BEFORE}"
        ),
    }


#: Los estados de una fila de la comparacion deposito ↔ versionado.
DEPOSITO_IGUAL = "IGUAL"
DEPOSITO_DISTINTO = "DISTINTO"
DEPOSITO_SOLO_DEPOSITO = "SOLO_EN_EL_DEPOSITO"
DEPOSITO_SOLO_VERSIONADO = "SOLO_VERSIONADO"
#: Estado del INFORME entero cuando no hay dos sitios que comparar (en local).
DEPOSITO_MISMO_DIRECTORIO = "MISMO_DIRECTORIO"

#: Por que esto es un INFORME y no un guardia.
WHY_THE_DEPOSIT_MAY_DIFFER = (
    "Que un fichero del depósito no sea el versionado NO ES UN FALLO: subir uno más "
    "nuevo por el gestor es exactamente para lo que existe el depósito, y lo versionado "
    "sólo se siembra la primera vez. Lo que no puede pasar es que no se vea. El número "
    "correcto aquí no es cero."
)

#: Por que nadie lo miraba hasta el 2026-09-06, con las palabras con que se dijo.
WHY_NOBODY_COMPARED = (
    "La siembra respeta lo que está, el rol valida contra el manifiesto del volumen, y "
    "nadie compara el depósito con lo versionado. Los dos autoconsistentes, el "
    "desajuste invisible por construcción."
)


def _secuencia_fasta(datos: bytes) -> str | None:
    """La secuencia de un FASTA de un solo registro, o `None` si no lo es.

    Existe para separar «otra molécula» de «otro formato»: un FASTA reenvuelto a otro
    ancho tiene otro md5 de fichero y la MISMA secuencia, y esa es la diferencia entre
    «hay que reemplazarlo» y «da igual». Para lo que no es FASTA devuelve `None` y no se
    inventa una respuesta.
    """
    try:
        texto = datos.decode("utf-8")
    except UnicodeDecodeError:
        # rule2-ok: no es un fallo que perder — un fichero binario simplemente no es un
        # FASTA, y eso es la respuesta `None` que el llamador ya sabe leer.
        return None
    if not texto.lstrip().startswith(">"):
        return None
    cuerpo = [l for l in texto.splitlines() if not l.startswith(">")]
    return "".join("".join(cuerpo).split()).upper() or None


def deposit_vs_versioned(*, directory=None) -> dict[str, object]:
    """Qué ficheros del DEPÓSITO no son los VERSIONADOS. Informe, no veredicto.

    Nace de la errata nº 129: el casete con el que se emitía no era el del depósito, y
    lo que permitía que eso viviera indefinidamente es que las dos comprobaciones que
    había son autoconsistentes —ver `WHY_NOBODY_COMPARED`—. Esto es el tercer eje: el
    único que mira los dos sitios a la vez.

    En local los dos directorios son EL MISMO, así que no hay nada que comparar y se
    dice (`MISMO_DIRECTORIO`) en vez de devolver «todos iguales», que sería un verde sin
    haber mirado (principio nº 51).

    El manifiesto queda fuera: el del depósito se REESCRIBE al subir un fichero, así que
    que difiera es lo normal y contarlo sería ruido permanente.
    """
    from .identidad import file_fingerprint  # noqa: PLC0415
    from .manifest import _NO_SON_DATOS  # noqa: PLC0415
    from .reference import PACKAGE_REFERENCE_DIR  # noqa: PLC0415
    from .trabajo import reference_dir  # noqa: PLC0415

    deposito = Path(directory) if directory is not None else reference_dir()
    versionado = Path(PACKAGE_REFERENCE_DIR)
    base = {
        "deposito": str(deposito),
        "versionado": str(versionado),
        "por_que": WHY_THE_DEPOSIT_MAY_DIFFER,
    }
    if deposito.resolve() == versionado.resolve():
        return {
            **base, "estado": DEPOSITO_MISMO_DIRECTORIO, "filas": [],
            "motivo": (
                f"El depósito y lo versionado son el MISMO directorio ({deposito}), así "
                f"que no hay dos cosas que comparar. Pasa en local, donde "
                f"`SHMIR_REFERENCE_DIR` no está declarado. No se da por bueno: no haber "
                f"podido comparar no es haber comparado."
            ),
        }

    def _datos(carpeta: Path) -> dict[str, bytes]:
        if not carpeta.is_dir():
            return {}
        return {
            p.name: p.read_bytes()
            for p in sorted(carpeta.iterdir())
            if p.is_file() and p.name not in _NO_SON_DATOS and p.suffix.lower() != ".md"
        }

    en_deposito, en_versionado = _datos(deposito), _datos(versionado)
    filas = []
    for nombre in sorted(set(en_deposito) | set(en_versionado)):
        a, b = en_deposito.get(nombre), en_versionado.get(nombre)
        fila = {
            "fichero": nombre,
            "md5_deposito": file_fingerprint(a) if a is not None else "",
            "md5_versionado": file_fingerprint(b) if b is not None else "",
            "bytes_deposito": len(a) if a is not None else 0,
            "bytes_versionado": len(b) if b is not None else 0,
            "misma_secuencia": None,
        }
        if a is None:
            fila["estado"] = DEPOSITO_SOLO_VERSIONADO
        elif b is None:
            fila["estado"] = DEPOSITO_SOLO_DEPOSITO
        elif fila["md5_deposito"] == fila["md5_versionado"]:
            fila["estado"] = DEPOSITO_IGUAL
        else:
            fila["estado"] = DEPOSITO_DISTINTO
            sa, sb = _secuencia_fasta(a), _secuencia_fasta(b)
            if sa is not None and sb is not None:
                fila["misma_secuencia"] = sa == sb
        filas.append(fila)

    distintos = [f for f in filas if f["estado"] == DEPOSITO_DISTINTO]
    return {
        **base, "estado": DEPOSITO_DISTINTO if distintos else DEPOSITO_IGUAL,
        "filas": filas,
        "motivo": (
            f"{len(distintos)} fichero(s) del depósito no son los versionados, de "
            f"{len(filas)} comparado(s). {WHY_THE_DEPOSIT_MAY_DIFFER}"
        ),
    }


def arms_rows(present=()) -> list[dict[str, object]]:
    """Los seis brazos, con QUE AISLA cada uno y si esta declarado."""
    from .controles import ARMS

    declarados = {str(clave) for clave in present}
    return [
        {"brazo": brazo.key, "nombre": brazo.label, "aisla": brazo.isolates,
         "declarado": brazo.key in declarados}
        for brazo in ARMS
    ]


def arms_warning(present=()) -> dict[str, object] | None:
    """El aviso de brazos que faltan. AVISO, no impedimento — como el del núcleo."""
    from .controles import arms_warning as _aviso

    return _aviso(present)


# ─── El proyecto abierto, y por que la pagina tiene que ACORDARSE ───────────────────

#: La opcion de «crear uno nuevo» del desplegable. Vive aqui y no en la pagina porque
#: `project_target` la compara: dos literales, uno en cada sitio, discreparian el dia que
#: alguien reescriba el texto — y la comparacion fallaria en silencio, eligiendo siempre
#: la rama de abrir.
PROJECT_NEW_OPTION = "— crear uno nuevo —"

#: POR QUE LA PAGINA RECUERDA EL PROYECTO. Un boton de Streamlit vale `True` UN SOLO
#: rerun. La pagina creaba el proyecto dentro de `if boton:`, asi que el siguiente
#: repintado —el que dispara escribir en cualquier `text_input`— devolvia `None` y el
#: proyecto desaparecia. Y el sitio donde se cobraba era el peor: el formulario de
#: guardar la corrida de BLAST pide fecha y quien la corrio, o sea que hay que ESCRIBIR
#: para completarlo, y escribir lo borraba. El formulario era imposible de rellenar
#: detras de horas de descarga y de corrida. Ver errata nº 42.
WHY_THE_PROJECT_IS_REMEMBERED = (
    "El proyecto abierto se recuerda entre reruns: un botón de Streamlit vale `True` un "
    "solo repintado, así que abrirlo dentro de un `if botón:` lo perdía en cuanto el "
    "usuario escribía en cualquier campo."
)

#: Lo que se recuerda es el SLUG, no el almacen. Un `ProjectStore` en `session_state`
#: sobreviviria igual, y ahi esta la trampa: el md5 de la secuencia y la cadena del log
#: se comprueban AL ABRIR, asi que un almacen guardado se quedaria con la comprobacion
#: del primer rerun para siempre. Es el principio nº 14 —haber comprobado una vez no es
#: seguir comprobando— aplicado a la persistencia de la interfaz.
WHY_THE_SLUG_AND_NOT_THE_STORE = (
    "Se recuerda el SLUG y se vuelve a abrir en cada rerun: guardar el almacén dejaría "
    "la comprobación del md5 y la de la cadena del log congeladas en el primer "
    "repintado."
)


def project_target(*, active: bool, chosen: str, new_name: str, date: str,
                   clicked: bool, remembered: str = "") -> dict[str, str]:
    """Que hacer con el panel de proyecto en ESTE rerun. La pagina no decide.

    Devuelve `accion` (`ninguna` / `crear` / `abrir`), el `slug` sobre el que actuar, el
    `aviso` que se pinta si no hay accion, y que hay que `recordar` para el rerun
    siguiente. Toda la logica del panel esta aqui para que tenga tests: en la pagina,
    una condicion sobre un booleano de widget no la prueba nadie (regla 6).
    """
    if not active:
        # OLVIDAR es parte de la decision: si no se olvidara, volver a marcar la casilla
        # reabriria un proyecto que el usuario habia cerrado a proposito.
        return {
            "accion": "ninguna", "slug": "", "recordar": "",
            "aviso": "Sin proyecto, lo que calculen los modales se pierde al cerrar la "
                     "pestaña.",
        }
    if chosen != PROJECT_NEW_OPTION:
        # El desplegable MANDA sobre lo recordado: elegir otro es una decision explicita.
        return {"accion": "abrir", "slug": chosen, "recordar": chosen, "aviso": ""}
    if clicked and new_name and date:
        # Crear tambien manda: el usuario puede tener uno abierto y querer otro.
        return {"accion": "crear", "slug": new_name, "recordar": new_name, "aviso": ""}
    if remembered:
        # AQUI ESTA EL ARREGLO. El desplegable sigue diciendo «crear uno nuevo» —su
        # valor es de widget y no se mueve solo— pero el proyecto ya existe y esta
        # abierto. Sin esta rama, el rerun siguiente a crearlo lo perdia.
        return {
            "accion": "abrir", "slug": remembered, "recordar": remembered, "aviso": "",
        }
    if not new_name or not date:
        return {
            "accion": "ninguna", "slug": "", "recordar": "",
            "aviso": "Hace falta un nombre y una fecha para crearlo.",
        }
    return {
        "accion": "ninguna", "slug": "", "recordar": "",
        "aviso": "Dale a «Crear proyecto» para abrirlo.",
    }


#: SIN PROYECTO NO SE ACEPTA EL FICHERO. Se aceptaba, con un aviso en gris de que no se
#: iba a guardar nada — y detras de ese fichero hay una descarga de decenas de GB y una
#: corrida de horas. Un sitio donde se puede soltar algo que no se guarda no informa: es
#: una trampa. Mismo criterio que la casilla global «Usar los de data/reference/», que se
#: quito porque su unico efecto posible al desmarcarla era dejarlo todo en NOT_RUN.
UPLOAD_NEEDS_PROJECT = (
    "**Abre un proyecto antes de subir el resultado.** Sin proyecto no hay dónde "
    "guardarlo, así que dejarlo caer aquí lo perdería — y detrás de este fichero hay una "
    "descarga y una corrida que no se repiten gratis. Se activa en la barra lateral, en "
    "«Guardar esta corrida en un proyecto»."
)


#: Lo mismo para CALCULAR. Los tres modales que ejecutan —colision de seed, carga de
#: off-targets y empalme— corrian sin proyecto y avisaban DESPUES con un `st.caption`, que
#: es el elemento mas silencioso que hay y aparece justo despues de un resultado. Quien lo
#: pasa por alto cierra la pestaña y pierde el trabajo sin enterarse.
#:
#: El de BLAST ya se negaba ANTES —no pinta el `file_uploader` sin proyecto—, y esa es la
#: forma correcta: no dejar empezar algo que no se va a poder guardar.
RUN_NEEDS_PROJECT = (
    "**Abre un proyecto antes de lanzar esta corrida.** Sin proyecto no hay dónde "
    "guardarla: se calcularía, se pintaría, y al cerrar la pestaña no quedaría nada — y "
    "el resultado no se distingue de uno guardado mientras está en pantalla. Se activa en "
    "la barra lateral, en «Guardar esta corrida en un proyecto»."
)


def run_allowed(project) -> dict[str, object]:
    """¿Se puede LANZAR una corrida ahora? Un booleano y su motivo, resueltos aqui.

    Misma forma que `upload_allowed` a proposito: son la misma decision sobre dos verbos,
    y tenerlas iguales es lo que evita que los cuatro modales vuelvan a divergir.
    """
    if project is None:
        return {"permitido": False, "motivo": RUN_NEEDS_PROJECT}
    return {"permitido": True, "motivo": ""}


def upload_allowed(project) -> dict[str, object]:
    """¿Se puede aceptar un fichero de resultado en este momento?

    Un booleano y su motivo, resueltos aqui: la pagina no decide, pinta.
    """
    if project is None:
        return {"permitido": False, "motivo": UPLOAD_NEEDS_PROJECT}
    return {"permitido": True, "motivo": ""}


def query_name(species: str, start: int, strand: str) -> str:
    """El identificador de UNA consulta del FASTA de BLAST.

    LLEVA EL SLUG Y NO EL NOMBRE QUE SE PINTA. Con el cientifico dentro salia
    `>Mus musculus_pos959_guia`, y **BLAST corta `qseqid` en el primer espacio**: las
    veinte consultas llegaban al `-outfmt 6` como `Mus`, indistinguibles entre si. El
    fichero no da ningun error —es un TSV con la forma correcta— y no se puede
    recuperar: no contiene de que consulta viene cada fila.

    Y el slug ademas NORMALIZA: `mouse`, `raton` y `Mus musculus` son la misma especie,
    asi que un nombre por alias haria incomparables dos corridas de lo mismo.
    """
    from .species import resolve

    return f"{resolve(species).slug}_pos{int(start)}_{strand}"


#: Las dos hebras que produce `query_name`, y NO son intercambiables en una comparacion
#: contra la diana: la guia es antisentido a su blanco POR DEFINICION —el mRNA lleva su
#: complemento inverso— y la pasajera lleva la MISMA secuencia que el blanco, asi que
#: acierta en sentido. Ver `specificity.EXPECTED_ORIENTATION`.
STRANDS = ("guia", "pasajera")


def strand_of(name: str) -> str:
    """La hebra de una consulta, PEDIDA a quien monta el nombre.

    Simetrica de `query_name`: el formato vive en un solo sitio. Transcribir el sufijo
    donde haga falta es la errata nº 49 —cinco copias del mismo formato, y dos tests que
    preguntaban por la clave que ellos mismos escribian—, con el agravante de que aqui de
    la hebra cuelga que orientacion se espera del acierto contra la propia diana.
    """
    texto = str(name)
    for hebra in STRANDS:
        if texto.endswith(f"_{hebra}"):
            return hebra
    raise ShmirDesignError(
        f"No se puede saber de que hebra es la consulta {name!r}: no acaba en ninguna de "
        f"{STRANDS}. Se aborta en vez de suponer «guía», que es lo que haría pasar por "
        f"buena una pasajera con la orientacion al reves."
    )


# ─── LENGUAJE LLANO: lo que lee quien NO ha estado en estas conversaciones ──────────
#
# El criterio de aceptacion de la primera pantalla ya decia «alguien que no haya estado
# en estas conversaciones tiene que poder abrir la app y llegar a un informe». Lo que
# faltaba es que el TEXTO lo cumpliera: «determina el prefijo de miRBase, el taxid y el
# ensamblaje» es correcto y no se entiende sin saber ya lo que son.
#
# LA REGLA ES ANTEPONER, NO SUSTITUIR. El detalle tecnico sigue estando, un clic mas
# adentro: quitarlo seria perder la procedencia, que es lo que este proyecto no hace.
# Y el idioma llano lleva TEST (`tests/test_lenguaje_llano.py`), porque si no se pudre:
# la proxima frase que alguien escriba volvera a ser tecnica si nada lo impide.

APP_PURPOSE = (
    "Esta herramienta diseña shmiR: pequeñas moléculas de ARN que, metidas en una "
    "célula, se pegan al mensajero de un gen y lo apagan. Tú dices a qué gen y de qué "
    "especie; ella recorre el mensajero entero, propone los mejores sitios donde "
    "atacarlo y va comprobando, uno a uno, todos los motivos por los que un sitio "
    "podría no servir."
)

WHAT_YOU_NEED = (
    "Para empezar sólo hacen falta dos cosas: saber de qué especie es tu gen, y tener "
    "su secuencia en un fichero. Todo lo demás se puede ir añadiendo después, y la "
    "herramienta te dice en cada momento qué falta y de dónde sacarlo."
)

#: Que se pide en cada paso y POR QUE, en el idioma de quien llega. El numero es la
#: clave; el orden y el titulo tecnico siguen viviendo en `steps_rows`.
_STEP_PLAIN = {
    1: {
        "titulo": "¿De qué especie es tu gen?",
        "que_se_pide": (
            "Elige el animal del que vas a apagar un gen: ratón, humano…"
        ),
        "por_que": (
            "Cada especie tiene sus propios catálogos —de genes, de moléculas "
            "parecidas a la tuya, de zonas conflictivas del genoma— y la herramienta "
            "necesita saber cuáles usar. Elegir mal aquí da un resultado con la forma "
            "correcta y las comprobaciones hechas contra el animal equivocado."
        ),
    },
    2: {
        "titulo": "¿Cuál es la secuencia de tu gen?",
        "que_se_pide": (
            "Sube el fichero con la secuencia del mensajero que quieres apagar. Si lo "
            "tienes en formato GenBank (.gb) mejor: ese trae marcado dónde empieza y "
            "acaba la parte que codifica la proteína."
        ),
        "por_que": (
            "Ahí es donde se buscan los sitios donde atacar. Y saber qué parte "
            "codifica la proteína importa: los mejores sitios suelen estar en la cola "
            "final del mensajero, y sin esa marca hay que decirle a mano dónde acaba."
        ),
    },
    3: {
        "titulo": "Buscar los candidatos",
        "que_se_pide": "Nada más. Dale al botón.",
        "por_que": (
            "Con la secuencia basta para proponer sitios: los primeros criterios miden "
            "propiedades de la propia secuencia y no necesitan ningún dato de fuera."
        ),
    },
    4: {
        "titulo": "Los candidatos, y lo que aún les falta",
        "que_se_pide": (
            "Mira la lista. Ninguno está aprobado todavía: son los que superan los "
            "primeros criterios."
        ),
        "por_que": (
            "Los criterios que quedan necesitan datos que hay que conseguir fuera, y "
            "cada uno descarta candidatos distintos. Por eso la lista es provisional."
        ),
    },
    5: {
        "titulo": "Las comprobaciones que faltan",
        "que_se_pide": (
            "Una tarjeta por comprobación. Cada una te dice qué mira, qué hace falta "
            "para hacerla y dónde conseguirlo."
        ),
        "por_que": (
            "Cuando estén todas hechas, y sólo entonces, la lista deja de ser "
            "provisional y se puede encargar la síntesis."
        ),
    },
}


def step_plain(number: int) -> dict[str, str]:
    """Que se pide en un paso y por que, en llano. Un paso sin explicacion ABORTA."""
    guia = _STEP_PLAIN.get(int(number))
    if guia is None:
        raise ShmirDesignError(
            f"El paso {number} no tiene explicacion en lenguaje llano. Se aborta en vez "
            f"de pintar un paso mudo: un formulario sin decir que se pide y por que es "
            f"exactamente lo que esta pantalla existe para no ser. Se añade en "
            f"`presentation._STEP_PLAIN`."
        )
    return dict(guia)


def species_plain(name: str) -> dict[str, str]:
    """La especie, explicada antes de dar sus codigos.

    «Mus musculus está declarada: prefijo de miRBase «mmu-», taxid txid10090,
    ensamblaje mm39» es cierto y no dice NADA a quien empieza. Lo llano va delante; los
    tres identificadores siguen estando, en `detalle`, que la pagina pinta plegado.
    """
    from .species import resolve

    nota = species_choice_note(name)
    if str(name).strip() == OTHER_SPECIES or nota["bloquea"]:
        return {
            "texto": (
                "Esa especie todavía no está preparada en la herramienta. Puedes "
                "diseñar igual y verás candidatos, pero varias de las comprobaciones "
                "no se podrán hacer: no existe el catálogo con el que compararlos."
            ),
            "detalle": nota["texto"],
            "bloquea": True,
        }
    especie = resolve(name)
    return {
        "texto": (
            f"Preparada. Se usarán los catálogos de {especie.scientific} para todas "
            f"las comprobaciones."
        ),
        "detalle": nota["texto"],
        "bloquea": False,
    }


def semaforo_plain(light) -> dict[str, str]:
    """El semaforo en tres piezas: titular corto, que hacer, y el detalle con cifras.

    Antes era un parrafo de siete lineas que empezaba por «Faltan 4 de 10 filtros» y
    metia dentro las tres cuentas de ventanas. Todo cierto y nadie lo lee entero: lo
    primero que se ve tiene que caber de un vistazo.
    """
    hechos = int(getattr(light, "ran", 0) or 0)
    total = int(getattr(light, "total", 0) or 0)
    faltan = max(total - hechos, 0)
    if not faltan:
        titular = "Todas las comprobaciones hechas."
        que_hacer = "La lista ya no es provisional."
    else:
        titular = (
            f"Hechas {hechos} de {total} comprobaciones. Ninguno de estos candidatos "
            f"está aprobado todavía."
        )
        que_hacer = (
            "Sigue abajo: hay una tarjeta por cada comprobación que falta, con lo que "
            "hace falta para hacerla."
        )
    return {
        "titular": titular,
        "que_hacer": que_hacer,
        "detalle": str(getattr(light, "detail", "") or getattr(light, "texto", "")),
    }


#: Los tres estados de una tarjeta y su color. El color lo pone `presentation`, no la
#: pagina: uno elegido en la pagina es una decision sin test (regla 6), y ya paso con
#: `REFINEMENT_STATES`.
CARD_STATES = {
    "HECHO": "green",
    "SIN_HACER": "grey",
    "NO_APLICA": "blue",
}


#: Lo que separa la tarjeta del banco de las demas, y va en su ENCABEZADO. No es un
#: adorno: es el unico frente BINARIO —si el intron no se escinde no hay proteina DN y
#: ninguno de los otros lo detecta— y el unico que no se cierra con nada de lo que hay
#: aqui. En la misma cuadricula se lee como una comprobacion pendiente mas, y de ahi a
#: concluir que sobra hay un paso.
BENCH_HEADING = (
    "Esta no se cierra aquí — se responde en el banco. No hay ningún fichero que "
    "conseguir ni ninguna corrida que subir: son lecturas de laboratorio."
)

#: El titulo del desplegable de la ficha, por estado. Un frente cerrado NO puede decir
#: «como se consigue»: manda a hacer algo ya hecho.
FICHA_TITLES = {
    "abierto": "Cómo se consigue",
    "cerrado": "Cómo se consiguió (referencia)",
    "banco": "Qué hay que medir en el banco",
}


def specificity_reading(stores, *, species: str) -> str:
    """LAS DOS FRASES JUNTAS, derivadas de la corrida guardada.

    La TASA sale del registro —cuantas consultas se juzgaron y cuantas cayeron— y la
    consecuencia de cada gen atrapado la declara `specificity.CONSEQUENCE_DECLARED`, que
    es lo unico que la app no puede derivar. Separadas se leen mal: la tasa suena a
    filtro inutil y la captura a filtro decisivo, y es las dos cosas.
    """
    from .specificity import discrimination_reading

    almacen = getattr(stores, "blast", None) if stores is not None else None
    corridas = list(getattr(almacen, "runs", ()) or ())
    if not corridas:
        return ""
    # SE PIDE EL VEREDICTO, no se recalcula: `verdict_for` ya sabe que corrida manda
    # entre varias (errata nº 45) y reimplementarlo aqui seria la segunda definicion del
    # mismo numero. De el sale la TASA; los genes atrapados salen de sus aciertos graves.
    consultas: set[str] = set()
    for corrida in corridas:
        consultas.update(corrida.query_names)
    atrapados: dict[str, tuple[str, ...]] = {}
    for consulta in sorted(consultas):
        veredicto = almacen.verdict_for(consulta, species=species)
        if veredicto.state is not FilterState.FAIL:
            continue
        candidato = consulta.rsplit("_", 1)[0]
        ultima, _ = almacen.deciding_run(consulta)
        if ultima is None:
            continue
        fallo = ultima.judged_call(consulta, species=species)
        if fallo is None:
            continue
        # POR CANDIDATO, no por hebra: las dos hebras del mismo candidato atrapan el
        # mismo gen y repetirlo lo lee como dos hallazgos.
        atrapados[candidato] = atrapados.get(candidato, ()) + tuple(
            h.transcript for h in fallo.graves
        )
    candidatos = {c.rsplit("_", 1)[0] for c in consultas}
    if not candidatos:
        return ""
    return discrimination_reading(
        total=len(candidatos), caidos=len(atrapados), atrapados=atrapados,
    )


def front_card_rows(run, *, species: str, stores=None) -> list[dict[str, object]]:
    """Una tarjeta por comprobacion, DERIVADA de `blocking_fronts`.

    Se derivan por la misma razon que las columnas de la tabla de sitios: una lista
    escrita a mano deja fuera al frente numero once sin que nadie lo note, y **lo que no
    se ve no existe**. El texto llano de cada una sale de su ficha, que es un fichero de
    datos versionado con test en las dos direcciones.

    Y LEE LOS ALMACENES (2026-09-02). Sin ellos, una corrida de BLAST guardada y valida
    dejaba la tarjeta en gris, el semaforo en «6 de 10» y el informe listando el frente
    como abierto — mientras la seccion de corridas guardadas decia `PASS` de esa misma
    corrida. Reportado con el proyecto delante; errata nº 51.
    """
    from .obtencion import CLOSED_AT_BENCH, resolve_ficha
    from .selection import blocking_fronts
    from .species import resolve

    especie = resolve(species)
    panel = chosen_starts(run.selection)
    vista = panel_states_by_front(
        run.tiling, run.selection, species=species, stores=stores
    )
    cobertura = run_coverage(
        vista["estados"], starts=panel, origins=vista["origenes"]
    )
    cerrados = {f: d["motivo"] for f, d in cobertura.items() if d["cerrado"]}
    tarjetas = []
    for frente in blocking_fronts(
        run.tiling, run.selection, closed_by_panel=cerrados
    ):
        ficha = resolve_ficha(frente.name, species=especie)
        estado = "HECHO" if not frente.blocking else "SIN_HACER"
        parcial = cobertura.get(frente.name)
        # ESTE FRENTE NO SE CIERRA AQUÍ, y no puede parecerse a los otros. Lo declara su
        # ficha (`se_cierra_en`), no una lista en el código ni en la página: el día que
        # haya un segundo de banco, entra solo.
        cierra_aqui = ficha.closed_at != CLOSED_AT_BENCH
        cerrado = estado == "HECHO"
        tarjetas.append(
            {
                "frente": frente.name,
                "titulo": ficha.plain_title,
                "en_cristiano": ficha.plain,
                "estado": estado,
                "color": CARD_STATES[estado],
                "cierra_aqui": cierra_aqui,
                "donde_se_cierra": ficha.closed_at,
                "encabezado": "" if cierra_aqui else BENCH_HEADING,
                "por_que_aparte": "" if cierra_aqui else ficha.why_no_file,
                # LO PRIMERO DE UN FRENTE CERRADO ES EL RESULTADO. Antes el motivo vivía
                # dentro del desplegable, junto a las instrucciones para conseguir lo que
                # ya estaba: un frente abierto y uno cerrado enseñaban lo mismo.
                "resultado": frente.reason if cerrado else "",
                # Y NO SE REPITE EN `motivo`: cerrado, el motivo ES el resultado y ya
                # esta pintado arriba. `motivo` es lo que se dice de un frente ABIERTO.
                "motivo": "" if cerrado else frente.reason,
                "ficha_titulo": FICHA_TITLES[ficha.heading_kind(closed=cerrado)],
                "ficha_texto": ficha.render(closed=cerrado),
                "fuente": ficha.source,
                "url": ficha.url,
                # LA COBERTURA PARCIAL SE VE. Un frente con corrida para 6 de 10 no
                # puede pintarse igual que uno que nadie ha tocado.
                "cubiertos": (parcial or {}).get("cubiertos", 0),
                "panel": (parcial or {}).get("panel", len(panel)),
                "avance": (parcial or {}).get("avance", ""),
                "que_hace_falta": [f.name for f in ficha.files],
                "donde": ficha.url,
            }
        )
    return tarjetas


def front_progress(cards) -> dict[str, object]:
    """Cuantas comprobaciones hay hechas. Se DERIVA de las tarjetas, no se cuenta aparte.

    Dos contadores del mismo suceso acaban discrepando —ya paso entre `seed_load` y
    `offtarget`— y aqui el que discrepara pintaria una barra que no corresponde a las
    tarjetas que hay debajo.
    """
    filas = list(cards)
    # SOLO LO QUE SE PUEDE CERRAR AQUÍ. Con el frente de banco dentro, el máximo era
    # INALCANZABLE —siempre bloquea, así que «8 de 8» no podía salir nunca— y además
    # mezclaba una lectura de laboratorio con frentes que se cierran con una descarga.
    aqui = [c for c in filas if c["cierra_aqui"]]
    banco = [c for c in filas if not c["cierra_aqui"]]
    hechas = sum(1 for c in aqui if c["estado"] == "HECHO")
    total = len(aqui)
    texto = f"{hechas} de {total} comprobaciones hechas"
    if banco:
        # El singular importa: con «(n)» la línea se lee como una plantilla sin rellenar,
        # y esta frase es justo la que tiene que leerse de un vistazo.
        una = len(banco) == 1
        texto += (
            f", y {len(banco)} que no se {'cierra' if una else 'cierran'} aquí — se "
            f"{'responde' if una else 'responden'} en el banco"
        )
    return {
        "hechas": hechas,
        "total": total,
        "en_el_banco": len(banco),
        "fraccion": (hechas / total) if total else 0.0,
        "texto": texto,
    }


#: EL PRIMER TRAMO TERMINA AQUI, y hasta ahora no lo decia: la lista de candidatos venia
#: seguida de todo lo demas, asi que se leia como el resultado. No lo es.
CANDIDATES_ARE_NOT_THE_END = (
    "**Hasta aquí, los candidatos.** Son los sitios del mensajero que superan los "
    "criterios que se pueden medir sobre la propia secuencia. Todavía falta lo más "
    "importante: comprobar que ninguno se pega donde no debe. Ninguno de estos está "
    "aprobado, y el orden en que salen todavía puede cambiar."
)

#: Los botones se llaman por lo que HACEN. «Diseñar» y «Estimar coste» no dicen que va a
#: aparecer en la pantalla, que es lo unico que quien lee necesita saber para pulsarlos.
BUTTON_DESIGN = "Buscar candidatos"
BUTTON_ESTIMATE = "¿Cuánto va a tardar?"
BUTTON_CONTINUE = "Seguir: las comprobaciones que faltan"


# ─── ViennaRNA: una CAPACIDAD del entorno, no un fichero que falte ──────────────────
#
# LA LECCION, y va al registro con esa forma: **un entorno sin una dependencia no falla,
# DEGRADA** — y aqui degrado a la regla que este proyecto ya habia descartado por
# escrito. La imagen de produccion no instala ViennaRNA; el nucleo esta preparado para
# eso y `check_fold` sale `NOT_RUN` en vez de `PASS`, que es correcto. Lo que NO se
# degrada igual es la regla de la PASAJERA: `passenger_from_guide` elige la base de la
# posicion 1 PLEGANDO contra SGEP, y sin plegado cae a la tabla por terminacion — la que
# fallaba con guias acabadas en G por el apareamiento tambaleante G:U, y que fue la
# primera errata del proyecto.
#
# Esa pasajera VA DENTRO DEL MODULO DE 149 nt, o sea dentro de lo que se manda a
# sintetizar. Un `NOT_RUN` que produce ADN sintetizable no es un `NOT_RUN`: es un `PASS`
# con letra pequeña. Por eso lo que se comprueba aqui no es que la dependencia este, sino
# que su ausencia IMPIDA lo que sin ella no se puede hacer.

NO_FOLDING_NOTE = (
    "**Este servidor no tiene instalado el motor de plegado (ViennaRNA).** Se pueden "
    "buscar candidatos y se puede correr todo lo demás, pero **no se emite ADN para "
    "sintetizar**: la hebra pasajera se elige plegando la horquilla y comparándola con "
    "la del plásmido de referencia, y sin ese cálculo se elegiría por una regla que "
    "este proyecto ya comprobó que falla con guías acabadas en G."
)

FOLDING_OK_NOTE = "Motor de plegado disponible: la hebra pasajera se elige plegando."


def folding_capability(available: bool | None = None) -> dict[str, object]:
    """¿Puede este entorno plegar? Es una capacidad AUSENTE, no un fichero que falte.

    Va en la CABECERA de la pagina y no en el campo de un veredicto: un fichero que
    falta se consigue, y esto no — se instala en la imagen. Confundirlos manda al
    usuario a buscar un fichero que no existe.
    """
    from .folding import VIENNA_AVAILABLE

    hay = VIENNA_AVAILABLE if available is None else bool(available)
    return {
        "disponible": hay,
        "texto": FOLDING_OK_NOTE if hay else NO_FOLDING_NOTE,
    }


def check_can_emit_dna(available: bool | None = None) -> None:
    """ABORTA si no se puede plegar. Se llama ANTES de emitir cualquier ADN.

    Acotado a la EMISION a proposito: el nucleo y los CLI tienen que seguir corriendo
    sin ViennaRNA —esta escrito en `docs/dependencias-autorizadas.md`— y abortar el
    pipeline entero dejaria la app sin hacer lo unico que hoy hace bien. Lo que se
    prohibe es lo que no se puede deshacer: pedir oligos.
    """
    from .folding import VIENNA_AVAILABLE

    hay = VIENNA_AVAILABLE if available is None else bool(available)
    if not hay:
        raise ShmirDesignError(
            "NO SE EMITE ADN SIN EL MOTOR DE PLEGADO. La hebra pasajera de este módulo "
            "se elige plegando el 97-mero y comparandolo con la estructura de SGEP; sin "
            "ViennaRNA se elegiria con la tabla por terminacion, que está COMPROBADA "
            "como incorrecta —le falta el apareamiento tambaleante G:U, así que con una "
            "guía acabada en G elige una base que deja un bulge de 2 nt en vez de 1—. "
            "Emitirlo con un `NOT_RUN` al lado no basta: lo que sale de aquí se manda a "
            "sintetizar. Instala ViennaRNA en el entorno (ver "
            "`docs/dependencias-autorizadas.md`)."
        )


# ─── UN INFORME QUE LEE ESTADO MUTABLE DECLARA CONTRA QUE ESTADO SE GENERO ───────────
#
# COROLARIO del responsable del proyecto (2026-09-01), y va a `docs/principios.md`:
# **la fecha no basta — dos corridas del mismo dia son dos documentos distintos.**
# Mientras el documento se calculaba solo del tilado, «generado el 1 de septiembre» lo
# identificaba: la entrada era la misma. En cuanto lee los almacenes, deja de hacerlo.

#: Los almacenes que un informe puede leer. Se enumeran aqui y no se recorre el dict a
#: ciegas: un almacen nuevo tiene que entrar TAMBIEN en la huella, y si se colara sin
#: entrar, dos informes distintos darian la misma huella — que es peor que no tenerla.
LOG_KINDS = ("blast", "seed", "offtarget", "splice")

FINGERPRINT_NOTE = (
    "La huella identifica el ESTADO DEL LOG con el que se generó este informe. Dos "
    "informes con la misma huella son el mismo documento; con huellas distintas, la "
    "diferencia está en las corridas que había al generarlos. La fecha no basta: dos "
    "corridas del mismo día son dos documentos distintos."
)


def _runs_of(store) -> list:
    """Las corridas de un almacen, sea del tipo que sea. Vacio si no hay almacen."""
    return list(getattr(store, "runs", ()) or ())


def log_fingerprint(stores) -> dict[str, object]:
    """md5 de la lista de `run_id` presentes. ORDENADA, porque el orden no es estado.

    Dos logs con las mismas corridas son el mismo estado: si el orden de llegada contara,
    dos informes identicos saldrian con huellas distintas y la señal dejaria de servir
    para lo unico que sirve — decir si dos documentos son el mismo.
    """
    import hashlib

    ids = sorted(
        f"{clave}:{corrida.run_id}"
        for clave in LOG_KINDS
        for corrida in _runs_of((stores or {}).get(clave))
    )
    return {
        "huella": hashlib.md5("\n".join(ids).encode("utf-8")).hexdigest(),
        "corridas": len(ids),
        "nota": FINGERPRINT_NOTE,
    }


def run_provenance_rows(stores) -> list[dict[str, str]]:
    """Por cada corrida: id, fecha, md5 del fichero SUBIDO y md5 de la base o catalogo.

    Es lo que ya se le exige a un fichero de referencia —nombre, version y md5— aplicado
    a un RESULTADO. Sin esto, un frente cerrado en el documento no se puede cotejar con
    nada: diria «PASS» y no habria forma de saber contra que.

    OJO con los DOS md5 de una corrida de BLAST: `query_md5` es el del FASTA que generó
    la app y `result_md5` el del fichero que llegó de fuera. El que hay que poder cotejar
    es el segundo — el primero ya se puede regenerar aquí.
    """
    filas = []
    for clave in LOG_KINDS:
        for corrida in _runs_of((stores or {}).get(clave)):
            base = getattr(corrida, "database", None)
            filas.append(
                {
                    "almacen": clave,
                    "run_id": str(getattr(corrida, "run_id", "")),
                    "fecha": str(getattr(corrida, "date", "")),
                    "md5_subido": str(getattr(corrida, "result_md5", "")),
                    "md5_base": str(getattr(base, "md5", "") if base else ""),
                }
            )
    return filas



def verdicts_changed(tiling, selection, *, species: str, before, after
                     ) -> dict[str, object]:
    """Que cambia una corrida al guardarla. Y DISTINGUE ganar un veredicto de no ganarlo.

    «Guardada en el log del proyecto» se leia como «hecho», y durante dias fue un guardado
    que no cambiaba ningun veredicto porque nadie consultaba el almacen. Pero contar
    CAMBIOS DE VALOR tampoco vale: una corrida que no cierra mueve los diez candidatos de
    `NOT_RUN` a `NO_CIERRA` —de **no comprobado a no comprobado por otro motivo**— y
    «10 veredictos actualizados» en verde hace creer que se cerro un frente.

    Asi que se cuentan DOS cosas: cuantos pasan a TENER veredicto (`PASS`/`FAIL`) y
    cuantos siguen sin el. El verde se reserva a los primeros.

    Se DERIVA comparando las dos tablas — no se cuenta aparte. Un contador propio seria
    otro contador del mismo suceso, y ya se sabe como acaban.
    """
    from .filters import FilterState

    decisivos = {FilterState.PASS.value, FilterState.FAIL.value}
    columnas = front_columns(tiling, selection)

    def _tabla(stores):
        return {
            (f["inicio"], c): f[c]
            for f in site_table_rows(tiling, selection, species=species, stores=stores)
            for c in columnas
        }

    # `SIN_CONSULTAR` y `NOT_RUN` son LO MISMO para esta cuenta: ninguno es un veredicto,
    # y el paso de uno a otro sólo afina la etiqueta —«hay corridas de este frente y
    # ninguna te miró» en vez de «no se ha corrido nada»—. Sin esto, la primera corrida
    # decía «270 cambios» porque las 260 filas que nadie consultó cambiaban de nombre:
    # el contador engañoso que este contador existe para no ser (errata nº 55).
    def _mismo(valor):
        return FilterState.NOT_RUN.value if valor == SIN_CONSULTAR else valor

    antes = {k: _mismo(v) for k, v in _tabla(before).items()}
    despues = {k: _mismo(v) for k, v in _tabla(after).items()}
    cambiados = [k for k, v in despues.items() if antes.get(k) != v]
    con_veredicto = sum(
        1 for k in cambiados
        if despues[k] in decisivos and antes.get(k) not in decisivos
    )
    sin_veredicto = len(cambiados) - con_veredicto

    if con_veredicto:
        texto = (
            f"Guardada. **{con_veredicto} candidato(s) pasan a tener veredicto** en "
            f"este frente."
        )
        if sin_veredicto:
            texto += (
                f" Otros {sin_veredicto} cambian de motivo pero **siguen sin "
                f"veredicto**."
            )
    elif sin_veredicto:
        texto = (
            f"Guardada, y **0 candidatos pasan a tener veredicto**. "
            f"{sin_veredicto} cambian de motivo y **siguen sin veredicto**: la corrida "
            f"se registró, pero no cierra nada. Mira la columna de ese frente — dirá si "
            f"fue `-remote`, si llevaba algún ajuste cambiado, o si sus consultas no son "
            f"las de este panel."
        )
    else:
        texto = (
            "Guardada, y **0 veredictos actualizados**. Si esperabas que cerrara un "
            "frente, algo no encaja: puede que sus consultas no sean las de este panel."
        )
    return {
        "cambiados": len(cambiados),
        "con_veredicto": con_veredicto,
        "sin_veredicto": sin_veredicto,
        "verde": bool(con_veredicto),
        "texto": texto,
    }
