"""Guardarrailes de poliadenilacion sobre el 3'UTR.

Tres cosas, en el orden en que se pidieron:

A. Localiza la señal canonica AATAAA y sus variantes principales, con posicion y
   distancia al extremo 3'. Clasifica cada una como señal terminal probable (10-40 nt
   del final) o como posible sitio de poliadenilacion alternativa (AATAAA canonica a
   mas de 100 nt del final). Toda ventana que solape una señal ±10 nt queda EXCLUIDA.
B. Si aparece un APA proximal, emite un AVISO destacado: los candidatos corriente
   abajo podrian no capturar la isoforma corta. No se excluyen; se anotan con
   `riesgo_APA=True`. El limite del riesgo es la SEÑAL, no el sitio de corte —que cae
   10-30 nt aguas abajo—, asi que sobre-marca del orden de 25 ventanas. Es conservador
   a proposito, y no debe leerse como una prediccion del extremo de la isoforma corta:
   para eso harian falta datos de un atlas de poliadenilacion, no un motivo.
C. Anota cada ventana con el tercio del 3'UTR en que cae (proximal / medio / distal),
   para las cuotas de seleccion posteriores.

Convenio de coordenadas: posiciones 1-based sobre el 3'UTR, `position` es el primer
nucleotido del motivo y `distance_to_3p` son los nucleotidos que quedan entre el ultimo
nucleotido del motivo y el extremo 3'. Con el 3'UTR de raton de 1242 nt, la AATAAA que
empieza en 288 termina en 293 y deja 949 nt por delante.

Este modulo no toca la red: no depende de ningun recurso externo (regla 4). Python
3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from .coords import Frame, frame_of, label, span
from .errors import InvalidSequenceError, MissingSequenceError
from .filters import FilterResult, FilterState, Verdict, overall_verdict

# ─── Parametros del guardarrail ──────────────────────────────────────────────
CANONICAL_SIGNAL = "AATAAA"
VARIANT_SIGNALS = (
    "ATTAAA",
    "TATAAA",
    "AGTAAA",
    "AATACA",
    "CATAAA",
    "AATATA",
    "GATAAA",
    "ACTAAA",
    "AATAGA",
)
ALL_SIGNALS = (CANONICAL_SIGNAL,) + VARIANT_SIGNALS

#: Señales FUERTES: la canonica y su variante mas frecuente. Son las unicas que pueden
#: clasificarse como APA posible y las unicas que producen FAIL duro lejos del extremo.
#: El resto de variantes son raras y solo generan bandera y penalizacion de ranking.
STRONG_SIGNALS = frozenset({CANONICAL_SIGNAL, "ATTAAA"})

SIGNAL_FLANK = 10           # nt a cada lado de la señal que quedan prohibidos
TERMINAL_MIN_DISTANCE = 10  # señal terminal probable: 10-40 nt del extremo 3'
TERMINAL_MAX_DISTANCE = 40
APA_MIN_DISTANCE = 100      # APA posible: AATAAA canonica a MAS de 100 nt del extremo

VALID_BASES = frozenset("ACGTN")
FILTER_NAME = "zona_prohibida_polyA"


class SignalClass(StrEnum):
    TERMINAL_PROBABLE = "SEÑAL_TERMINAL_PROBABLE"
    APA_POSSIBLE = "APA_POSIBLE"
    OTHER = "OTRA"


class Tercio(StrEnum):
    PROXIMAL = "proximal"
    MEDIO = "medio"
    DISTAL = "distal"


# ─── Secuencia ───────────────────────────────────────────────────────────────
def normalize_sequence(sequence: str | None, *, name: str = "secuencia") -> str:
    """Valida y normaliza una secuencia sin inventar ni completar nada.

    Quita espacios y saltos de linea, pasa a mayusculas y trata U como T (misma
    secuencia en notacion ARN). Cualquier otro caracter aborta el paso.
    """
    if sequence is None:
        raise MissingSequenceError(
            f"No hay {name}: se aborta la busqueda de señales de poliadenilacion. "
            f"Regla 1: no se reconstruye una secuencia ausente."
        )
    if not isinstance(sequence, str):
        raise TypeError(
            f"{name} debe ser str, no {type(sequence).__name__}; "
            f"se aborta la busqueda de señales de poliadenilacion."
        )

    cleaned = "".join(sequence.split()).upper().replace("U", "T")
    if not cleaned:
        raise MissingSequenceError(
            f"La {name} esta vacia: se aborta la busqueda de señales de "
            f"poliadenilacion. Regla 1: no se genera una secuencia de relleno."
        )

    for index, base in enumerate(cleaned, start=1):
        if base not in VALID_BASES:
            raise InvalidSequenceError(
                f"{name}: caracter {base!r} no valido en la posicion {index} "
                f"(se esperaba A, C, G, T/U o N); se aborta la busqueda de señales "
                f"de poliadenilacion sobre esta secuencia."
            )
    return cleaned


def read_fasta_sequence(path: Path | str) -> str:
    """Lee un FASTA de un unico registro. Cualquier problema aborta el paso."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MissingSequenceError(
            f"No se pudo leer el FASTA {path} ({exc}); se aborta la busqueda de "
            f"señales de poliadenilacion: sin secuencia no hay analisis."
        ) from exc

    records: list[list[str]] = []
    for line in raw.splitlines():
        if line.startswith(">"):
            records.append([])
        elif line.strip():
            if not records:
                raise MissingSequenceError(
                    f"{path} empieza con secuencia sin cabecera '>'; no es un FASTA "
                    f"valido y se aborta la busqueda de señales de poliadenilacion."
                )
            records[-1].append(line.strip())

    if len(records) != 1:
        raise MissingSequenceError(
            f"{path} contiene {len(records)} registros y se esperaba exactamente 1; "
            f"se aborta la busqueda de señales de poliadenilacion para no analizar "
            f"la secuencia equivocada."
        )
    return normalize_sequence("".join(records[0]), name=f"secuencia de {path.name}")


# ─── A. Señales de poliadenilacion ───────────────────────────────────────────
@dataclass(frozen=True)
class PolyASignal:
    motif: str
    position: int          # 1-based, primer nucleotido del motivo
    utr_length: int
    distance_to_3p: int
    classification: SignalClass
    #: nt prohibidos a cada lado de la señal. Umbral ajustable, no constante escondida.
    flank: int = SIGNAL_FLANK

    @property
    def end(self) -> int:
        return self.position + len(self.motif) - 1

    @property
    def is_canonical(self) -> bool:
        """Solo el hexamero canonico AATAAA."""
        return self.motif == CANONICAL_SIGNAL

    @property
    def is_strong(self) -> bool:
        """AATAAA o ATTAAA: las dos que tumban una ventana lejos del extremo."""
        return self.motif in STRONG_SIGNALS

    @property
    def is_hard_block(self) -> bool:
        """¿Esta señal excluye por si sola una ventana que la solape?"""
        return self.classification in (
            SignalClass.TERMINAL_PROBABLE,
            SignalClass.APA_POSSIBLE,
        )

    @property
    def forbidden_start(self) -> int:
        return max(1, self.position - self.flank)

    @property
    def forbidden_end(self) -> int:
        return min(self.utr_length, self.end + self.flank)

    def describe(self, *, frame: Frame = Frame.UTR3) -> str:
        """`frame` es el espacio de `position`: el de LO TILADO.

        Por defecto `3utr` porque las coordenadas de una señal son 1-based sobre el
        3'UTR cuando nadie dice otra cosa —es el contrato de este modulo—, pero el
        camino de produccion (`tile_utr` → informe) pasa siempre el marco real sacado
        de la anatomia. Sin etiqueta, un `1237` no dice de que espacio es.
        """
        return (
            f"{self.motif} en {span(self.position, self.end, frame)} "
            f"(a {self.distance_to_3p} nt del extremo 3') → {self.classification}"
        )


def classify_signal(
    motif: str,
    position: int,
    utr_length: int,
    flank: int = SIGNAL_FLANK,
) -> PolyASignal:
    """Clasifica una señal por sus coordenadas, sin necesitar la secuencia."""
    motif = motif.upper()
    if motif not in ALL_SIGNALS:
        raise ValueError(
            f"{motif!r} no es una señal de poliadenilacion conocida "
            f"(canonica {CANONICAL_SIGNAL} o variantes {', '.join(VARIANT_SIGNALS)}); "
            f"se aborta la clasificacion."
        )
    if flank < 0:
        raise ValueError(
            f"flank={flank} invalido: la zona prohibida no puede ser negativa; "
            f"se aborta la clasificacion."
        )
    if position < 1:
        raise ValueError(
            f"Posicion {position} invalida para {motif}: las coordenadas son 1-based; "
            f"se aborta la clasificacion."
        )
    end = position + len(motif) - 1
    if end > utr_length:
        raise ValueError(
            f"{motif} en {position} termina en {end}, fuera del 3'UTR de {utr_length} "
            f"nt; se aborta la clasificacion para no reportar una señal inexistente."
        )

    distance = utr_length - end
    if TERMINAL_MIN_DISTANCE <= distance <= TERMINAL_MAX_DISTANCE:
        classification = SignalClass.TERMINAL_PROBABLE
    elif motif in STRONG_SIGNALS and distance > APA_MIN_DISTANCE:
        classification = SignalClass.APA_POSSIBLE
    else:
        classification = SignalClass.OTHER

    return PolyASignal(
        motif=motif,
        position=position,
        utr_length=utr_length,
        distance_to_3p=distance,
        classification=classification,
        flank=flank,
    )


def find_polya_signals(
    sequence: str | None,
    *,
    first_position: int = 1,
    utr_length: int | None = None,
    flank: int = SIGNAL_FLANK,
) -> list[PolyASignal]:
    """Busca todas las señales sobre `sequence`, solapamientos incluidos.

    `first_position` es la coordenada 1-based que ocupa el primer nucleotido de
    `sequence` dentro del 3'UTR; `utr_length` es la longitud del 3'UTR completo. Asi se
    puede analizar un fragmento verificado y seguir midiendo distancias al extremo 3'
    reales, sin reconstruir el resto de la secuencia.
    """
    cleaned = normalize_sequence(sequence)
    if first_position < 1:
        raise ValueError(
            f"first_position={first_position} invalido: las coordenadas del 3'UTR son "
            f"1-based; se aborta la busqueda de señales."
        )

    last_position = first_position + len(cleaned) - 1
    if utr_length is None:
        utr_length = last_position
    elif utr_length < last_position:
        raise ValueError(
            f"El fragmento llega a la posicion {last_position} pero el 3'UTR declarado "
            f"mide {utr_length} nt; se aborta la busqueda de señales por coordenadas "
            f"incoherentes."
        )

    signals: list[PolyASignal] = []
    for motif in ALL_SIGNALS:
        index = cleaned.find(motif)
        while index != -1:
            signals.append(
                classify_signal(motif, first_position + index, utr_length, flank=flank)
            )
            index = cleaned.find(motif, index + 1)

    signals.sort(key=lambda s: (s.position, s.motif))
    return signals


# ─── B y C. Anotacion de ventanas ────────────────────────────────────────────
@dataclass(frozen=True)
class Window:
    start: int             # 1-based
    length: int
    label: str | None = None

    @property
    def end(self) -> int:
        return self.start + self.length - 1

    @property
    def name(self) -> str:
        return self.label or f"ventana@{self.start}"


@dataclass(frozen=True)
class AnnotatedWindow:
    window: Window
    zona_prohibida: FilterResult
    #: None si la ventana no cae en el 3'UTR (los tercios se calculan sobre el 3'UTR).
    tercio: Tercio | None
    riesgo_APA: bool
    apa_upstream: tuple[PolyASignal, ...] = ()
    #: Variantes raras solapadas: no excluyen, penalizan y dejan bandera.
    senales_debiles: tuple[PolyASignal, ...] = ()
    #: ¿Pasaria el criterio ESTRICTO (±flanco para los doce hexameros por igual)?
    #: Se conserva para poder enseñar las dos cifras y que la decision sea visible.
    estricto_ok: bool = True

    @property
    def bandera_polyA_debil(self) -> bool:
        return bool(self.senales_debiles)

    @property
    def name(self) -> str:
        return self.window.name

    @property
    def verdict(self) -> Verdict:
        return overall_verdict([self.zona_prohibida])


@dataclass(frozen=True)
class Aviso:
    """Aviso destacado del informe.

    `affected` guarda la lista completa de ventanas porque el TSV la necesita, pero el
    mensaje NUNCA la enumera: con un APA proximal las afectadas son casi todas (del
    orden de 900 de 1221 en el 3'UTR de raton) y una lista de 900 nombres es ruido.
    El mensaje da cuantas son, en que rango de posiciones y que porcentaje del total.
    """

    code: str
    message: str
    affected: tuple[str, ...] = ()
    affected_count: int = 0
    affected_total: int = 0
    position_range: tuple[int, int] | None = None
    affected_pct: float = 0.0


@dataclass(frozen=True)
class Report:
    utr_length: int
    signals: tuple[PolyASignal, ...]
    windows: tuple[AnnotatedWindow, ...]
    avisos: tuple[Aviso, ...] = field(default=())
    signals_available: bool = True
    #: Espacio de coordenadas de las posiciones de este informe.
    frame: Frame = Frame.UTR3

    def format_text(self) -> str:
        lines = [f"3'UTR de {self.utr_length} nt"]

        lines.append("")
        if not self.signals_available:
            lines.append(
                "Señales de poliadenilacion: NO CALCULADAS — el filtro "
                f"{FILTER_NAME} no llego a correr."
            )
        elif self.signals:
            lines.append(f"Señales de poliadenilacion ({len(self.signals)}):")
            lines.extend(f"  · {s.describe(frame=self.frame)}" for s in self.signals)
        else:
            lines.append("Señales de poliadenilacion: ninguna encontrada.")

        for aviso in self.avisos:
            lines.append("")
            lines.append(f"  ⚠  AVISO [{aviso.code}]")
            lines.append(f"     {aviso.message}")

        lines.append("")
        lines.append("Ventanas:")
        for annotated in self.windows:
            window = annotated.window
            riesgo = " riesgo_APA=True" if annotated.riesgo_APA else ""
            lines.append(
                f"  {window.name} [{span(window.start, window.end, self.frame)}] "
                f"{(annotated.tercio.value if annotated.tercio else '—'):<8} "
                f"{FILTER_NAME}={annotated.zona_prohibida.state.value:<7} "
                f"veredicto={annotated.verdict.value}{riesgo}"
            )
            lines.append(f"      motivo: {annotated.zona_prohibida.reason}")
        return "\n".join(lines)

    def format_tsv(self) -> str:
        """Una fila por ventana, con todos los estados y motivos. Sin omitir ninguna."""
        columns = (
            "ventana",
            "inicio",
            "fin",
            "tercio",
            FILTER_NAME,
            "motivo",
            "riesgo_APA",
            "apa_upstream",
            "veredicto",
        )
        rows = [columns]
        for annotated in self.windows:
            window = annotated.window
            rows.append(
                (
                    window.name,
                    label(window.start, self.frame),
                    label(window.end, self.frame),
                    annotated.tercio.value if annotated.tercio else "",
                    annotated.zona_prohibida.state.value,
                    annotated.zona_prohibida.reason,
                    str(annotated.riesgo_APA),
                    ",".join(
                        label(s.position, self.frame) for s in annotated.apa_upstream
                    ),
                    annotated.verdict.value,
                )
            )
        return "\n".join("\t".join(_tsv_safe(field) for field in row) for row in rows)


def _tsv_safe(field: str) -> str:
    """Ningun campo puede romper el TSV con tabuladores o saltos de linea."""
    return field.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def tercio_of(window: Window, utr_length: int) -> Tercio:
    """Tercio del 3'UTR en que cae el punto medio de la ventana.

    Proximal es el extremo 5' del 3'UTR (junto al codon de parada); distal, el extremo
    poli(A).
    """
    middle = (window.start + window.end) / 2
    index = math.floor((middle - 1) * 3 / utr_length)
    index = min(2, max(0, index))
    return (Tercio.PROXIMAL, Tercio.MEDIO, Tercio.DISTAL)[index]


def _validate_window(window: Window, utr_length: int) -> None:
    if window.length < 1:
        raise ValueError(
            f"La ventana {window.name} tiene longitud {window.length}; "
            f"se aborta la anotacion del 3'UTR."
        )
    if window.start < 1 or window.end > utr_length:
        raise ValueError(
            f"La ventana {window.name} ocupa {window.start}-{window.end}, fuera del "
            f"3'UTR de {utr_length} nt; se aborta la anotacion para no anotar "
            f"coordenadas inexistentes."
        )


def _zona_prohibida(
    window: Window, signals: list[PolyASignal]
) -> tuple[FilterResult, tuple[PolyASignal, ...], tuple[PolyASignal, ...]]:
    """Filtro escalonado. Devuelve (resultado, señales fuertes, señales debiles).

    FAIL duro solo para la señal terminal y para las APA posibles (AATAAA y ATTAAA).
    Las variantes raras —las que se clasifican OTRA— no tumban la ventana: dejan
    bandera y penalizacion de ranking, porque un ACTAAA a 200 nt del extremo no es
    motivo para descartar un candidato.
    """
    flank = signals[0].flank if signals else SIGNAL_FLANK
    solapadas = tuple(
        s for s in signals
        if window.start <= s.forbidden_end and window.end >= s.forbidden_start
    )
    fuertes = tuple(s for s in solapadas if s.is_hard_block)
    debiles = tuple(s for s in solapadas if not s.is_hard_block)

    if fuertes:
        detalle = "; ".join(
            f"{s.motif} en {s.position} ({s.classification.value}, zona prohibida "
            f"{s.forbidden_start}-{s.forbidden_end})"
            for s in fuertes
        )
        return (
            FilterResult(
                name=FILTER_NAME,
                state=FilterState.FAIL,
                reason=f"Solapa señal fuerte de poliadenilacion ±{flank} nt: {detalle}.",
            ),
            fuertes,
            debiles,
        )

    if debiles:
        detalle = "; ".join(f"{s.motif} en {s.position}" for s in debiles)
        return (
            FilterResult(
                name=FILTER_NAME,
                state=FilterState.PASS,
                reason=(
                    f"Solapa variante(s) rara(s) de poliadenilacion ±{flank} nt "
                    f"({detalle}), clasificadas {SignalClass.OTHER.value}: no excluye, "
                    f"se penaliza en el ranking y queda con bandera."
                ),
            ),
            (),
            debiles,
        )

    return (
        FilterResult(
            name=FILTER_NAME,
            state=FilterState.PASS,
            reason=(
                f"Sin solape con ninguna de las {len(signals)} señal(es) detectadas "
                f"(±{flank} nt)."
            ),
        ),
        (),
        (),
    )


def annotate_3utr(
    windows: list[Window],
    signals: list[PolyASignal] | None,
    utr_length: int,
    anatomy=None,
) -> Report:
    """Anota las ventanas con zona prohibida, tercio y riesgo de APA.

    `signals=None` significa que la busqueda de señales NO llego a correr: el filtro
    queda en NOT_RUN y ninguna ventana puede darse por aprobada (regla 3). Una lista
    vacia es otra cosa: la busqueda corrio y no encontro señales.
    """
    if utr_length < 1:
        raise ValueError(
            f"Longitud de 3'UTR invalida ({utr_length}); se aborta la anotacion."
        )

    for signal in signals or ():
        if signal.utr_length != utr_length:
            raise ValueError(
                f"La señal {signal.motif} en {signal.position} se clasifico sobre un "
                f"3'UTR de {signal.utr_length} nt y aqui se anota uno de {utr_length} "
                f"nt; se aborta la anotacion por coordenadas incoherentes."
            )

    annotated: list[AnnotatedWindow] = []
    for window in windows:
        _validate_window(window, utr_length)
        tercio = (
            tercio_of(window, utr_length)
            if anatomy is None
            else anatomy.tercio_of(window.start, window.end)
        )

        if signals is None:
            annotated.append(
                AnnotatedWindow(
                    window=window,
                    zona_prohibida=FilterResult(
                        name=FILTER_NAME,
                        state=FilterState.NOT_RUN,
                        reason=(
                            "La busqueda de señales de poliadenilacion no llego a "
                            "correr; la ventana no puede darse por aprobada."
                        ),
                    ),
                    tercio=tercio,
                    riesgo_APA=False,
                )
            )
            continue

        apa_upstream = tuple(
            s for s in signals
            if s.classification is SignalClass.APA_POSSIBLE and window.start > s.end
        )
        resultado, fuertes, debiles = _zona_prohibida(window, signals)
        annotated.append(
            AnnotatedWindow(
                window=window,
                zona_prohibida=resultado,
                tercio=tercio,
                riesgo_APA=bool(apa_upstream),
                apa_upstream=apa_upstream,
                senales_debiles=debiles,
                estricto_ok=not (fuertes or debiles),
            )
        )

    # Sin anatomia, quien llama ha declarado que lo que analiza ES un 3'UTR: es el
    # contrato de este modulo (`utr_length`, posiciones 1-based sobre el 3'UTR). Con
    # anatomia, el marco sale de ella.
    marco = Frame.UTR3 if anatomy is None else frame_of(anatomy)
    return Report(
        utr_length=utr_length,
        signals=tuple(signals or ()),
        windows=tuple(annotated),
        avisos=tuple(_avisos_apa(signals, annotated, marco)),
        signals_available=signals is not None,
        frame=marco,
    )


def _avisos_apa(
    signals: list[PolyASignal] | None,
    annotated: list[AnnotatedWindow],
    frame: Frame = Frame.UTR3,
) -> list[Aviso]:
    """Un AVISO destacado por cada APA proximal detectado (apartado B).

    Resume: cuantas ventanas afecta, en que rango de posiciones y que porcentaje del
    total. La lista completa va al TSV.
    """
    avisos: list[Aviso] = []
    total = len(annotated)
    for signal in signals or ():
        if signal.classification is not SignalClass.APA_POSSIBLE:
            continue
        afectadas = [
            a for a in annotated
            if any(s.position == signal.position for s in a.apa_upstream)
        ]
        count = len(afectadas)
        pct = (count / total * 100) if total else 0.0
        rango = (
            (min(a.window.start for a in afectadas), max(a.window.end for a in afectadas))
            if afectadas
            else None
        )
        alcance = f"Afecta a {count} de {total} ventana(s) corriente abajo ({pct:.1f}%)"
        if rango is not None:
            alcance += f", posiciones {span(rango[0], rango[1], frame)}"

        avisos.append(
            Aviso(
                code="APA_PROXIMAL",
                message=(
                    f"Posible poliadenilacion alternativa: {signal.motif} canonica en "
                    f"{label(signal.position, frame)} (a {signal.distance_to_3p} nt del "
                    f"extremo 3'). "
                    f"{alcance}. Podrian no capturar la isoforma corta. NO se excluyen: "
                    f"quedan anotadas con riesgo_APA=True y la lista completa esta en "
                    f"el TSV. La decision es del responsable. El limite de riesgo es la "
                    f"SEÑAL ({label(signal.position, frame)}), no el sitio de corte, que "
                    f"cae 10-30 nt "
                    f"aguas abajo: el marcado es conservador a proposito y NO es una "
                    f"prediccion del extremo de la isoforma corta."
                ),
                affected=tuple(a.name for a in afectadas),
                affected_count=count,
                affected_total=total,
                position_range=rango,
                affected_pct=pct,
            )
        )
    return avisos


def analyze_3utr(
    sequence: str | None,
    windows: list[Window],
    *,
    first_position: int = 1,
    utr_length: int | None = None,
) -> Report:
    """Busca las señales sobre la secuencia y anota las ventanas de una vez."""
    signals = find_polya_signals(
        sequence, first_position=first_position, utr_length=utr_length
    )
    resolved_length = signals[0].utr_length if signals else None
    if resolved_length is None:
        cleaned = normalize_sequence(sequence)
        resolved_length = utr_length or (first_position + len(cleaned) - 1)
    return annotate_3utr(windows, signals, resolved_length)


# ─── polyA como ANOTACION, no como veredicto (bloque 3) ──────────────────────
#
# El umbral simetrico de ±SIGNAL_FLANK no sale de ningun articulo, y debajo habia tres
# preocupaciones distintas metidas en un solo PASS/FAIL. Aqui se separan en cinco campos
# de los que solo uno es un veredicto.
#
# La geometria importa y es contraintuitiva: el corte NO ocurre en el hexamero, ocurre
# 10-30 nt aguas abajo. El hexamero se queda DENTRO del ARNm maduro, asi que una ventana
# que lo contiene sigue existiendo en el transcrito. La que desaparece es la que empieza
# despues del sitio de corte. Por eso la zona prohibida por esta razon es asimetrica y
# esta desplazada aguas abajo, no centrada en el hexamero.

CLEAVAGE_MIN = 10   # nt aguas abajo del final del hexamero
CLEAVAGE_MAX = 30

#: Hasta que distancia se ANOTA una señal en los campos descriptivos de la ventana.
#: Es una convencion de presentacion, no un umbral de decision: el veredicto mira todas
#: las señales pase lo que pase. Existe porque, sin ella, una ventana en la posicion 50
#: salia anotada con el hexamero terminal de la posicion 1200 — cierto, pero ilegible.
ANNOTATION_RADIUS = 100

#: Las posiciones 2-8 de la guia (la seed) emparejan con el extremo 3' de la ventana
#: diana: la guia es el complemento inverso, asi que su posicion i emparejta con la
#: posicion (longitud + 1 - i) de la diana. Para una ventana de 22 nt, la seed cae en
#: las posiciones 15-21.
SEED_GUIDE_START = 2
SEED_GUIDE_END = 8
TARGET_WINDOW_SIZE = 22
SEED_TARGET_START = TARGET_WINDOW_SIZE + 1 - SEED_GUIDE_END   # 15
SEED_TARGET_END = TARGET_WINDOW_SIZE + 1 - SEED_GUIDE_START   # 21

#: Un hexamero solo casi nunca es un sitio funcional: hace falta un elemento GU-rico o
#: U-rico 10-30 nt aguas abajo. Estas dos fracciones son convencion nuestra, no un valor
#: publicado, asi que van como parametros y se barren en el informe.
DSE_GU_FRACTION = 0.60
DSE_U_FRACTION = 0.50


class RelativePosition(StrEnum):
    AGUAS_ARRIBA = "aguas arriba"
    SOLAPANDO = "solapando"
    DENTRO = "dentro"
    AGUAS_ABAJO = "aguas abajo"


class PolyAMode(StrEnum):
    """Los tres criterios, para poder enseñar el top-N bajo los tres.

    Si los tres coinciden, el debate sobre el umbral es irrelevante y queda documentado.
    """

    ESTRICTO = "estricto"        # ±flanco para los doce hexameros por igual
    ESCALONADO = "escalonado"    # FAIL solo para las señales fuertes
    PERMISIVO = "permisivo"      # FAIL solo por detras del corte de la terminal


def seed_target_span(window: Window) -> tuple[int, int]:
    """Tramo absoluto de la diana con el que empareja la seed (posiciones 2-8)."""
    if window.length != TARGET_WINDOW_SIZE:
        raise ValueError(
            f"La geometria de la seed esta calculada para ventanas de "
            f"{TARGET_WINDOW_SIZE} nt y esta mide {window.length}; se aborta en vez de "
            f"devolver un tramo que no corresponde."
        )
    return (
        window.start + SEED_TARGET_START - 1,
        window.start + SEED_TARGET_END - 1,
    )


def _distance(window: Window, signal: PolyASignal) -> int:
    """Hueco entre la ventana y la señal; 0 si se tocan o se solapan."""
    if signal.end < window.start:
        return window.start - signal.end - 1
    if signal.position > window.end:
        return signal.position - window.end - 1
    return 0


def _relative_position(window: Window, signal: PolyASignal) -> tuple[RelativePosition, int]:
    """Donde cae la señal respecto a la ventana, y a cuantos nt."""
    if signal.end < window.start:
        return RelativePosition.AGUAS_ARRIBA, window.start - signal.end - 1
    if signal.position > window.end:
        return RelativePosition.AGUAS_ABAJO, signal.position - window.end - 1
    if window.start <= signal.position and signal.end <= window.end:
        return RelativePosition.DENTRO, 0
    return RelativePosition.SOLAPANDO, 0


def _dse_context(
    signal: PolyASignal,
    sequence: str | None,
    *,
    gu_fraction: float = DSE_GU_FRACTION,
    u_fraction: float = DSE_U_FRACTION,
) -> bool | None:
    """¿Hay elemento GU-rico o U-rico 10-30 nt aguas abajo? `None` si no se puede mirar.

    Sin secuencia no se puede responder, y `None` significa exactamente eso: no es un
    "no" disfrazado.
    """
    if sequence is None:
        return None
    inicio = signal.end + CLEAVAGE_MIN
    fin = signal.end + CLEAVAGE_MAX
    if fin > len(sequence):
        return None
    tramo = sequence[inicio:fin].upper()
    if not tramo:
        return None
    gu = sum(1 for b in tramo if b in "GT") / len(tramo)
    u = sum(1 for b in tramo if b == "T") / len(tramo)
    return gu >= gu_fraction or u >= u_fraction


#: Los cinco campos, en el orden en que salen en las tablas.
POLYA_COLUMNS = (
    "polyA_hexamero",
    "polyA_clase",
    "polyA_posicion_rel",
    # Donde esta el hexamero sobre el 3'UTR y cuanto le queda al extremo 3'. Con la
    # posicion relativa sola no se puede juzgar una señal: `detras, 40 nt` no dice si
    # eso pasa a 100 nt del final o a 900.
    "polyA_hexamero_pos",
    "polyA_dist_extremo3",
    "polyA_solapa_seed",
    # El veredicto del modo con el que se CORRIO...
    "polyA_veredicto",
    # ...y el de las DOS reglas siempre, se haya corrido con la que se haya corrido.
    # Se emiten las dos y la decision se toma con la tabla delante, no eligiendo un
    # modo antes de ver los datos.
    "polyA_estricto",
    "polyA_escalonado",
    # Los DOS riesgos, separados. La regla de ±flanco los mezclaba y son distintos:
    # el truncamiento es sobre la EXISTENCIA de la diana, el esterico sobre su
    # ACCESIBILIDAD, y un mismo hexamero nunca produce los dos en la misma ventana.
    "polyA_truncamiento",
    "polyA_truncamiento_propio",
    "polyA_esterico",
    "polyA_dist_corte",
    # El techo de knockdown que impone el APA, o vacio mientras no se mida. Vacio no es
    # cero: es que nadie lo ha medido.
    "polyA_fraccion_isoforma_larga",
)


@dataclass(frozen=True)
class PolyAAnnotation:
    """Los cinco campos, mas el contexto y la banda de incertidumbre del corte."""

    hexamero: str
    clase: str
    posicion_rel: RelativePosition | None
    distancia: int
    solapa_seed: bool
    veredicto: FilterResult
    signal: PolyASignal | None = None
    contexto_gu_rico: bool | None = None
    tras_corte_posible: bool = False
    tras_corte_seguro: bool = False
    #: El veredicto bajo CADA regla, con independencia del modo con el que se corrio.
    #: Vacio solo si nadie las calculo, que no deberia pasar: `annotate_polya` las
    #: rellena siempre porque salen de la misma funcion pura y cuestan lo mismo.
    por_regla: dict[str, FilterState] = field(default_factory=dict)
    utr_length: int = 0
    riesgo: "PolyARisk | None" = None

    def as_columns(self) -> dict[str, str]:
        if self.posicion_rel is None:
            posicion = ""
        elif self.posicion_rel in (RelativePosition.DENTRO, RelativePosition.SOLAPANDO):
            posicion = self.posicion_rel.value
        else:
            posicion = f"{self.posicion_rel.value}, {self.distancia} nt"
        return {
            "polyA_hexamero": self.hexamero,
            "polyA_clase": self.clase,
            "polyA_posicion_rel": posicion,
            # Vacio, no cero: no haber encontrado hexamero y encontrarlo en la posicion
            # 0 son cosas distintas.
            "polyA_hexamero_pos": str(self.signal.position) if self.signal else "",
            "polyA_dist_extremo3": (
                str(self.utr_length - self.signal.end)
                if self.signal and self.utr_length
                else ""
            ),
            "polyA_solapa_seed": "si" if self.solapa_seed else "no",
            "polyA_veredicto": self.veredicto.state.value,
            "polyA_estricto": self.por_regla.get(
                PolyAMode.ESTRICTO.value, FilterState.NOT_RUN
            ).value,
            "polyA_escalonado": self.por_regla.get(
                PolyAMode.ESCALONADO.value, FilterState.NOT_RUN
            ).value,
            **(
                self.riesgo.as_columns()
                if self.riesgo is not None
                else {
                    "polyA_truncamiento": FilterState.NOT_RUN.value,
                    "polyA_truncamiento_propio": FilterState.NOT_RUN.value,
                    "polyA_esterico": FilterState.NOT_RUN.value,
                    "polyA_dist_corte": "",
                    "polyA_fraccion_isoforma_larga": "",
                }
            ),
        }


#: Orden de gravedad para elegir que hexamero manda cuando hay varios.
_GRAVEDAD = {
    SignalClass.TERMINAL_PROBABLE: 0,
    SignalClass.APA_POSSIBLE: 1,
    SignalClass.OTHER: 2,
}


class RiskState(StrEnum):
    """Los cinco estados de un riesgo de polyA. Ni `PENALIZADO` ni `TECHO` son `FAIL`.

    `PENALIZADO` hace falta porque la banda de corte tiene 20 nt de ancho: entre 10 y
    30 nt aguas abajo del hexamero no se sabe si el corte cae antes o despues de la
    ventana. Colapsarlo a PASS o a FAIL seria inventarse una precision que no hay.

    `TECHO` hace falta porque el APA no corta el transcrito en dos: produce una MEZCLA
    de isoformas. Un candidato por detras del corte de un sitio proximal usado en una
    fraccion f sigue teniendo diana en la isoforma larga —el (1 - f) restante—, asi que
    lo que corre es un TECHO de knockdown de (1 - f), no un veto. Y ese techo no se
    puede escribir mientras no se mida: ver `PolyARisk.fraccion_isoforma_larga`.

    `FAIL` queda para la señal TERMINAL: por detras de SU corte no hay transcrito en
    ninguna isoforma, no hay mezcla de la que hablar y la diana no existe.
    """

    NO_APLICA = "NO_APLICA"
    PASS = "PASS"
    PENALIZADO = "PENALIZADO"
    TECHO = "TECHO"
    FAIL = "FAIL"


@dataclass(frozen=True)
class PolyARisk:
    """Los DOS riesgos que la regla de ±flanco mezclaba, cada uno con su motivo.

    Nunca los produce el mismo hexamero sobre la misma ventana: o la ventana esta
    ENCIMA de la señal —y entonces hay riesgo esterico y no de truncamiento, porque se
    conserva en las dos isoformas— o esta POR DETRAS del corte, y entonces es al reves.
    """

    #: El riesgo de truncamiento que de verdad corre la ventana, mirando TODAS las
    #: señales funcionales que quedan por delante. Es el que manda.
    truncamiento: RiskState
    truncamiento_motivo: str
    esterico: RiskState
    esterico_motivo: str
    #: Fraccion de transcritos que conservan el 3'UTR completo, o sea la isoforma
    #: LARGA. Es el techo de knockdown de un candidato por detras del corte proximal:
    #: si el sitio proximal se usa en una fraccion f, queda (1 - f) de diana.
    #:
    #: OBLIGATORIO y sin valor por defecto a proposito: ningun camino puede omitirlo y
    #: dejar el techo mudo. `None` significa NO MEDIDA —igual que
    #: `transfer.divergent_positions=None` significa que nadie miro—, y no es 0 (todo
    #: isoforma corta, techo cero) ni 1 (todo isoforma larga, sin techo). Son tres
    #: cosas distintas y la salida tiene que poder distinguirlas.
    fraccion_isoforma_larga: float | None
    #: El riesgo de truncamiento RESPECTO DEL HEXAMERO QUE LA VENTANA SOLAPA, que es
    #: siempre NO_APLICA por construccion: si estas encima de la señal, estas aguas
    #: arriba de su corte y te conservas en las dos isoformas. Se emite aparte porque
    #: es la afirmacion que hay que poder leer sin que se confunda con la de arriba —
    #: y sobre todo para que NO se confunda: un candidato puede no tener truncamiento
    #: por su propio hexamero y tenerlo por otro que quede mas arriba.
    truncamiento_propio: RiskState = RiskState.NO_APLICA
    truncamiento_propio_motivo: str = ""
    #: Cuantos nt hay de la ventana al corte MAS TEMPRANO que dirigiria la señal que
    #: manda en el truncamiento. `None` si no aplica.
    distancia_corte: int | None = None
    truncamiento_signal: PolyASignal | None = None
    esterico_signal: PolyASignal | None = None

    def __post_init__(self) -> None:
        fraccion = self.fraccion_isoforma_larga
        if fraccion is None:
            return
        if not isinstance(fraccion, (int, float)) or isinstance(fraccion, bool):
            raise TypeError(
                f"fraccion_isoforma_larga debe ser un numero o None (no medida), no "
                f"{type(fraccion).__name__}; se aborta la anotacion de polyA."
            )
        if not 0.0 <= float(fraccion) <= 1.0:
            raise ValueError(
                f"fraccion_isoforma_larga={fraccion} fuera de [0, 1]: es una fraccion "
                f"de transcritos, no un recuento; se aborta la anotacion de polyA."
            )
        if self.truncamiento not in (RiskState.TECHO, RiskState.PENALIZADO):
            raise ValueError(
                f"Se ha dado fraccion_isoforma_larga={fraccion} a una ventana con "
                f"truncamiento={self.truncamiento.value}: el techo solo significa algo "
                f"donde hay riesgo de truncamiento por APA. Se aborta en vez de emitir "
                f"un techo que no se refiere a nada."
            )

    @property
    def techo_knockdown(self) -> float | None:
        """Techo de knockdown alcanzable, o `None` si no se ha medido.

        Es la MISMA cantidad que `fraccion_isoforma_larga`: si el sitio proximal se usa
        en una fraccion f, la diana solo existe en el (1 - f) de isoforma larga, y por
        mucho que la horquilla funcione al 100 % sobre lo que alcanza, el descenso
        total no puede pasar de ahi. `None` es no medido, no cero.
        """
        return self.fraccion_isoforma_larga

    def describe_techo(self) -> str:
        """Una linea para el informe. Sin medida no se emite veredicto, se dice que no."""
        if self.truncamiento not in (RiskState.TECHO, RiskState.PENALIZADO):
            return "sin riesgo de truncamiento por APA: no hay techo del que hablar."
        if self.fraccion_isoforma_larga is None:
            return (
                "techo indeterminado: fraccion_isoforma_larga NO MEDIDA. No es 0 ni 1; "
                "es que nadie la ha medido, y hasta que se mida el techo de knockdown "
                "de este candidato no se puede escribir."
            )
        return (
            f"techo de knockdown ≤ {self.fraccion_isoforma_larga:.2f} "
            f"(fraccion_isoforma_larga = {self.fraccion_isoforma_larga:.2f}, medida)."
        )

    def as_columns(self) -> dict[str, str]:
        return {
            "polyA_truncamiento": self.truncamiento.value,
            "polyA_truncamiento_propio": self.truncamiento_propio.value,
            "polyA_esterico": self.esterico.value,
            "polyA_dist_corte": (
                "" if self.distancia_corte is None else str(self.distancia_corte)
            ),
            # Vacia, nunca "0": no haber medido y haber medido cero son cosas distintas.
            "polyA_fraccion_isoforma_larga": (
                "" if self.fraccion_isoforma_larga is None
                else f"{self.fraccion_isoforma_larga:.2f}"
            ),
        }


#: Clases de señal que se dan por funcionales a efectos de truncamiento. Una variante
#: rara no se supone que corte: penaliza, no elimina.
_FUNCIONALES = (SignalClass.TERMINAL_PROBABLE, SignalClass.APA_POSSIBLE)


def polya_risk(
    window: Window,
    signals: list[PolyASignal],
    *,
    utr_length: int,
    fraccion_isoforma_larga: float | None = None,
) -> PolyARisk:
    """Evalua los dos riesgos por separado. No aplica ninguna regla de ±flanco.

    Truncamiento: la ventana esta por detras del corte que dirigiria una señal
    funcional. Con el corte entre +10 y +30 nt del hexamero, hay tres tramos —delante
    del corte mas temprano, dentro de la banda, y detras del corte mas tardio— y tres
    estados. Por detras del corte de un APA el estado es `TECHO`, no `FAIL`: el APA
    produce una mezcla de isoformas y la diana sigue existiendo en la larga. Por detras
    del corte de la señal TERMINAL si es `FAIL`: ahi no hay isoforma que la conserve.

    `fraccion_isoforma_larga` es la medida que convierte el techo en un numero. Va a
    `None` mientras no se mida, y darla donde no hay truncamiento por APA aborta.

    Esterico: la ventana solapa el hexamero, asi que compite con CPSF/CstF por el mismo
    tramo. Una canonica en `APA_POSIBLE` es FAIL; una variante `OTRA`, penalizacion.
    """
    solapadas = [
        s for s in signals if s.position <= window.end and s.end >= window.start
    ]
    esterico, esterico_motivo, esterico_signal = RiskState.NO_APLICA, (
        "La ventana no solapa ningun hexamero, asi que no compite con la maquinaria de "
        "corte por ningun tramo."
    ), None
    if solapadas:
        principal = min(solapadas, key=lambda s: _GRAVEDAD[s.classification])
        esterico_signal = principal
        if principal.classification in _FUNCIONALES:
            esterico = RiskState.FAIL
            esterico_motivo = (
                f"La ventana solapa {principal.motif} en "
                f"{principal.position}-{principal.end}, clase "
                f"{principal.classification.value}: es una señal que se da por "
                f"funcional, asi que la horquilla competiria con CPSF/CstF por ese "
                f"tramo."
            )
        else:
            esterico = RiskState.PENALIZADO
            esterico_motivo = (
                f"La ventana solapa {principal.motif} en "
                f"{principal.position}-{principal.end}, clase "
                f"{principal.classification.value}: es una variante rara, asi que el "
                f"riesgo esterico solo existe si esa señal se usa. Penaliza el ranking, "
                f"no elimina."
            )

    propio_motivo = (
        "La ventana no solapa ningun hexamero: no hay «hexamero propio» del que hablar."
    )
    if esterico_signal is not None:
        propio_motivo = (
            f"Respecto de {esterico_signal.motif} en {esterico_signal.position}-"
            f"{esterico_signal.end}, que es el hexamero que la ventana SOLAPA: no hay "
            f"riesgo de truncamiento. Solaparlo la deja aguas ARRIBA de su corte "
            f"({esterico_signal.end + CLEAVAGE_MIN}-{esterico_signal.end + CLEAVAGE_MAX}), "
            f"asi que se conserva en las dos isoformas. OJO: esto NO dice nada sobre "
            f"otras señales que queden mas arriba."
        )

    #: Solo las funcionales dirigen un corte. Se toma la que deje la ventana MAS lejos
    #: por detras, que es la que manda.
    detras = [
        s for s in signals
        if s.classification in _FUNCIONALES and window.start > s.end + CLEAVAGE_MIN
    ]
    if not detras:
        candidatas = [
            s for s in signals
            if s.classification in _FUNCIONALES and s.end < window.start
        ]
        motivo = (
            "La ventana esta aguas arriba del corte mas temprano de toda señal "
            "funcional (o lo solapa), asi que se conserva en las dos isoformas: no hay "
            "riesgo de truncamiento."
            if candidatas or not signals
            else "No hay ninguna señal funcional por delante de la ventana."
        )
        return PolyARisk(
            truncamiento=RiskState.NO_APLICA,
            truncamiento_motivo=motivo,
            fraccion_isoforma_larga=fraccion_isoforma_larga,
            esterico=esterico,
            esterico_motivo=esterico_motivo,
            esterico_signal=esterico_signal,
            truncamiento_propio_motivo=propio_motivo,
        )

    manda = max(detras, key=lambda s: window.start - s.end)
    distancia = window.start - (manda.end + CLEAVAGE_MIN)
    if window.start > manda.end + CLEAVAGE_MAX:
        # TECHO para un APA, FAIL para la terminal. La diferencia no es de grado: por
        # detras de un APA la diana sigue existiendo en la isoforma larga y lo que hay
        # es un limite al knockdown alcanzable; por detras de la terminal no hay
        # isoforma que la conserve.
        terminal = manda.classification is SignalClass.TERMINAL_PROBABLE
        estado = RiskState.FAIL if terminal else RiskState.TECHO
        detalle = (
            f"a {window.start - (manda.end + CLEAVAGE_MAX)} nt POR DETRAS del corte mas "
            f"tardio ({manda.end + CLEAVAGE_MAX}): "
            + (
                "ese tramo no esta en el ARNm maduro en ninguna isoforma, asi que la "
                "diana no existe"
                if terminal
                else "en la isoforma corta este tramo no esta, pero en la larga si. El "
                "APA reparte los transcritos entre las dos, asi que esto es un TECHO de "
                "knockdown —la fraccion de isoforma larga—, no un veto"
            )
        )
    else:
        estado = RiskState.PENALIZADO
        detalle = (
            f"dentro de la banda de corte ({manda.end + CLEAVAGE_MIN}-"
            f"{manda.end + CLEAVAGE_MAX}): no se sabe si el corte cae antes o despues "
            f"de la ventana"
        )
    return PolyARisk(
        truncamiento=estado,
        fraccion_isoforma_larga=fraccion_isoforma_larga,
        truncamiento_motivo=(
            f"{manda.motif} en {manda.position}-{manda.end} "
            f"({manda.classification.value}) dirige un corte 10-30 nt aguas abajo; la "
            f"ventana empieza en {window.start}, {detalle}."
        ),
        esterico=esterico,
        esterico_motivo=esterico_motivo,
        distancia_corte=distancia,
        truncamiento_signal=manda,
        esterico_signal=esterico_signal,
        truncamiento_propio_motivo=propio_motivo,
    )


def annotate_polya(
    window: Window,
    signals: list[PolyASignal],
    *,
    utr_length: int,
    sequence: str | None = None,
    mode: PolyAMode = PolyAMode.ESCALONADO,
    fraccion_isoforma_larga: float | None = None,
) -> PolyAAnnotation:
    """Anota una ventana: cinco campos, y solo uno es un veredicto.

    `fraccion_isoforma_larga` es el techo MEDIDO, que en el pipeline viene de
    `apa.ApaAssessment.knockdown_ceiling` cuando hay tabla de sitios (`--apa-medido`).
    Se adjunta solo donde significa algo —donde hay riesgo de truncamiento por APA—:
    los dos analisis son independientes (uno mira hexameros predichos, el otro sitios
    medidos) y pueden no coincidir. Donde no coinciden, la columna se queda vacia en
    vez de pegar un techo a una ventana que este analisis considera inmune.
    """
    terminales = [
        s for s in signals if s.classification is SignalClass.TERMINAL_PROBABLE
    ]
    tras_posible = any(window.start > s.end + CLEAVAGE_MIN for s in terminales)
    tras_seguro = any(window.start > s.end + CLEAVAGE_MAX for s in terminales)

    #: Solo se ANOTA lo que esta CERCA de esta ventana, mas la señal terminal que la
    #: deja por detras del corte (esa importa aunque este lejos, porque es la que
    #: produce el FAIL). Coger la señal mas grave de toda la secuencia llenaria la
    #: columna `polyA_hexamero` de hexameros a mil nt, y la tabla comparativa se lee de
    #: un vistazo. El VEREDICTO sigue mirandolas TODAS: esto solo decide que se enseña.
    relevantes = [
        s for s in signals
        if _distance(window, s) <= ANNOTATION_RADIUS
        or (
            s.classification is SignalClass.TERMINAL_PROBABLE
            and window.start > s.end + CLEAVAGE_MIN
        )
    ]
    cercanas = sorted(
        relevantes,
        key=lambda s: (
            _GRAVEDAD[s.classification],
            abs(s.position - window.start),
        ),
    )
    principal = cercanas[0] if cercanas else None

    solapa_seed = False
    if window.length == TARGET_WINDOW_SIZE:
        seed_inicio, seed_fin = seed_target_span(window)
        solapa_seed = any(
            s.position <= seed_fin and s.end >= seed_inicio for s in signals
        )

    posicion, distancia = (
        _relative_position(window, principal) if principal else (None, 0)
    )

    veredicto = _veredicto_polya(
        window,
        signals,
        mode=mode,
        tras_seguro=tras_seguro,
        tras_posible=tras_posible,
        terminales=terminales,
    )

    riesgo = polya_risk(window, signals, utr_length=utr_length)
    if fraccion_isoforma_larga is not None and riesgo.truncamiento in (
        RiskState.TECHO,
        RiskState.PENALIZADO,
    ):
        riesgo = replace(riesgo, fraccion_isoforma_larga=fraccion_isoforma_larga)

    por_regla = {
        otro.value: _veredicto_polya(
            window, signals, mode=otro, tras_seguro=tras_seguro,
            tras_posible=tras_posible, terminales=terminales,
        ).state
        for otro in (PolyAMode.ESTRICTO, PolyAMode.ESCALONADO)
    }

    return PolyAAnnotation(
        hexamero=principal.motif if principal else "",
        clase=principal.classification.value if principal else "",
        posicion_rel=posicion,
        distancia=distancia,
        solapa_seed=solapa_seed,
        veredicto=veredicto,
        signal=principal,
        contexto_gu_rico=_dse_context(principal, sequence) if principal else None,
        tras_corte_posible=tras_posible,
        tras_corte_seguro=tras_seguro,
        por_regla=por_regla,
        utr_length=utr_length,
        riesgo=riesgo,
    )


def _veredicto_polya(
    window: Window,
    signals: list[PolyASignal],
    *,
    mode: PolyAMode,
    tras_seguro: bool,
    tras_posible: bool,
    terminales: list[PolyASignal],
) -> FilterResult:
    """El unico campo que es un veredicto. El modo va siempre escrito en el motivo."""
    def resultado(state: FilterState, texto: str) -> FilterResult:
        return FilterResult(
            name=FILTER_NAME, state=state, reason=f"[modo {mode.value}] {texto}"
        )

    if tras_seguro:
        detalle = "; ".join(
            f"{s.motif} en {s.position}-{s.end} (corte como mucho en "
            f"{s.end + CLEAVAGE_MAX})"
            for s in terminales
        )
        return resultado(
            FilterState.FAIL,
            f"La ventana empieza en {window.start}, por detras del sitio de corte de la "
            f"señal terminal: {detalle}. Ese tramo no esta en el ARNm maduro, asi que "
            f"la diana no existe.",
        )

    solapadas = tuple(
        s for s in signals
        if window.start <= s.forbidden_end and window.end >= s.forbidden_start
    )
    fuertes = tuple(s for s in solapadas if s.is_hard_block)

    if mode is PolyAMode.ESTRICTO and solapadas:
        detalle = "; ".join(f"{s.motif} en {s.position}" for s in solapadas)
        return resultado(
            FilterState.FAIL,
            f"Solapa {len(solapadas)} hexamero(s) ±{solapadas[0].flank} nt ({detalle}). "
            f"El criterio estricto no distingue entre hexameros.",
        )

    if mode is PolyAMode.ESCALONADO and fuertes:
        detalle = "; ".join(
            f"{s.motif} en {s.position} ({s.classification.value})" for s in fuertes
        )
        return resultado(
            FilterState.FAIL,
            f"Solapa señal fuerte de poliadenilacion ±{fuertes[0].flank} nt: {detalle}.",
        )

    avisos = []
    if tras_posible:
        avisos.append(
            f"La ventana cae en la banda incierta del corte ({CLEAVAGE_MIN}-"
            f"{CLEAVAGE_MAX} nt tras el hexamero): puede quedar fuera del ARNm maduro."
        )
    if solapadas and mode is not PolyAMode.ESTRICTO:
        avisos.append(
            f"Solapa {len(solapadas)} hexamero(s), "
            + "; ".join(f"{s.motif} en {s.position}" for s in solapadas)
            + "."
        )
    return resultado(
        FilterState.PASS,
        " ".join(avisos)
        or f"Sin solape con ninguna de las {len(signals)} señal(es) detectadas.",
    )


# ─── El experimento que convierte el techo en un numero ──────────────────────
#
# `fraccion_isoforma_larga` no se deduce de un motivo: se mide. El experimento minimo es
# una RT-qPCR de dos amplicones sobre el mismo 3'UTR, normalizados contra una CURVA
# ESTANDAR COMUN (el mismo amplicon clonado o un gBlock de la region, diluido en serie),
# porque sin curva comun las dos eficiencias no son comparables y la razon no significa
# nada:
#
#   · amplicon PROXIMAL, entero por delante del hexamero. Esta en las DOS isoformas, asi
#     que mide el total de transcritos.
#   · amplicon DISTAL, entero por detras de la banda de corte. Solo esta en la isoforma
#     larga.
#
# La razon distal/proximal es la fraccion de isoforma larga, y esa fraccion es el techo.
#
# Aqui se emiten COORDENADAS y nada mas. Los cebadores se diseñan aparte, con Tm,
# especificidad y comprobacion de horquillas; escribirlos aqui seria generar secuencia
# (regla 1) y ademas sin ninguna de esas comprobaciones.

RTQPCR_AMPLICON_LENGTH = 120   # nt; rango habitual de qPCR (70-150)
RTQPCR_MARGIN = 10             # nt de holgura entre el amplicon y lo que debe esquivar


@dataclass(frozen=True)
class Amplicon:
    """Un amplicon propuesto. Las coordenadas se derivan; el invariante se comprueba."""

    role: str
    start: int
    end: int
    length: int
    rationale: str
    #: Tramos con los que solapa pese a todo, cuando no cabia en ningun otro sitio.
    overlaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # El mismo invariante de `audit.Span`: un intervalo escrito a mano es la errata
        # del desplazamiento de 3 nt otra vez.
        if self.end - self.start + 1 != self.length:
            raise ValueError(
                f"Amplicon {self.role}: {self.start}-{self.end} no mide {self.length} "
                f"nt sino {self.end - self.start + 1}; se aborta la propuesta en vez de "
                f"emitir unas coordenadas que no cuadran."
            )

    def describe(self, *, frame: Frame, offset: int = 0) -> str:
        """Una linea con el espacio de coordenadas PEGADO, y las dos parejas si hay dos."""
        aviso = f"  ⚠  solapa {', '.join(self.overlaps)}" if self.overlaps else ""
        # Un amplicon puede caer POR DELANTE del 3'UTR —es una diana valida para medir
        # el total, esta en las dos isoformas— y entonces NO tiene coordenada de 3'UTR:
        # restarle el desfase daria un numero negativo, que es una posicion inventada.
        if offset and self.start - offset < 1:
            doble = " (POR DELANTE del 3'UTR: no tiene coordenada de 3'UTR)"
        elif offset:
            doble = f" ({span(self.start - offset, self.end - offset, Frame.UTR3)})"
        else:
            doble = ""
        return (
            f"{self.role}: {span(self.start, self.end, frame)}{doble} "
            f"({self.length} nt). {self.rationale}{aviso}"
        )


@dataclass(frozen=True)
class AmpliconPlan:
    signal: PolyASignal
    proximal: Amplicon
    distal: Amplicon
    cut_band: tuple[int, int]
    utr_length: int
    #: Espacio en que van TODAS las coordenadas de este plan. Un 334 no dice por si
    #: solo si es del transcrito o del 3'UTR, y esa confusion ya costo una tanda.
    frame: Frame = Frame.UTR3

    def describe(self, *, offset: int = 0) -> list[str]:
        """`offset` = primera posicion del 3'UTR menos 1, para dar las dos parejas."""
        doble = (
            f" ({span(self.signal.position - offset, self.signal.end - offset, Frame.UTR3)})"
            if offset
            else ""
        )
        return [
            f"EXPERIMENTO QUE RESUELVE EL TECHO — RT-qPCR de dos amplicones sobre el "
            f"3'UTR",
            f"  Señal en cuestion: {self.signal.motif} en "
            f"{span(self.signal.position, self.signal.end, self.frame)}{doble}; "
            f"banda de corte {span(self.cut_band[0], self.cut_band[1], self.frame)}.",
            f"  {self.proximal.describe(frame=self.frame, offset=offset)}",
            f"  {self.distal.describe(frame=self.frame, offset=offset)}",
            "  Los dos se cuantifican contra una CURVA ESTANDAR COMUN: sin ella las dos "
            "eficiencias",
            "  no son comparables y la razon no significa nada.",
            "  RETROTRANSCRIPCION CON HEXAMEROS ALEATORIOS. Con oligo-dT NO, y el sesgo "
            "tiene direccion",
            f"  conocida: el oligo-dT ceba en la cola de poli(A) y la RT avanza 3'→5', "
            f"asi que una RT",
            f"  incompleta cubre lo que esta cerca de la cola y pierde lo de lejos. En "
            f"la isoforma LARGA",
            f"  el amplicon proximal queda a {self.utr_length - self.proximal.end} nt "
            f"de la cola y el distal a "
            f"{self.utr_length - self.distal.end} nt:",
            "  la larga se subrepresenta MAS en el proximal que en el distal, y la "
            "razon distal/proximal",
            "  sale sesgada HACIA MAS ISOFORMA LARGA — que es justo el resultado que se "
            "esta buscando.",
            "  Con hexameros aleatorios el cebado no depende de la distancia a la cola.",
            "  RNA con RIN DOCUMENTADO: la degradacion produce el mismo sesgo por la "
            "misma razon.",
            "  CONTROL POSITIVO DE ENSAYO, obligatorio: un gen con APA caracterizado en "
            "el mismo tejido,",
            "  medido en las MISMAS muestras y con la MISMA arquitectura de amplicones "
            "(uno delante de su",
            "  señal proximal, otro detras de su banda de corte). Sin el, un «casi todo "
            "isoforma larga» no",
            "  se distingue de un ensayo CIEGO a las isoformas cortas: los dos dan la "
            "misma cifra.",
            "  Ese gen se elige con su cita — aqui no se propone ninguno, porque "
            "nombrarlo de memoria",
            "  seria inventarse la referencia que lo respalda.",
            "    control_positivo_ensayo: NOT_RUN — falta el gen de control con su "
            "cita. NOT_RUN no es",
            "    PASS: mientras no lo aporte alguien, el ensayo no se puede leer, "
            "porque su resultado",
            "    esperado y el de un ensayo averiado son el mismo.",
            "  fraccion_isoforma_larga = razon distal/proximal. Ese numero ES el techo "
            "de knockdown",
            "  de los candidatos que quedan por detras del corte.",
            "  Se mide sobre tejido SIN tratar: en muestras tratadas un amplicon que "
            "solape una diana",
            "  mide corte por RNAi, no isoformas.",
            "  Se emiten COORDENADAS: no se emiten cebadores. El diseño de cebadores "
            "necesita Tm,",
            "  especificidad y comprobacion de horquillas, y eso no se improvisa aqui.",
        ]


def _place_amplicon(
    *,
    role: str,
    earliest: int,
    latest: int,
    length: int,
    downstream: bool,
    avoid: tuple[tuple[int, int], ...],
    rationale: str,
) -> Amplicon:
    """Coloca un amplicon de `length` nt entre `earliest` y `latest`, esquivando `avoid`.

    Recorre las posiciones de inicio posibles —alejandose de la señal— y devuelve la
    primera que no solapa nada. Si no hay ninguna, devuelve la primera posicion legal
    y ANOTA con que solapa: callarlo dejaria una propuesta que mide otra cosa.
    """
    if latest < earliest:
        raise ValueError(
            f"No cabe un amplicon {role} de {length} nt entre {earliest} y {latest} "
            f"dentro del 3'UTR; se aborta en vez de proponer coordenadas fuera de la "
            f"secuencia."
        )
    posiciones = range(earliest, latest + 1) if downstream else range(latest, earliest - 1, -1)
    for start in posiciones:
        end = start + length - 1
        choques = [f"{a}-{b}" for a, b in avoid if start <= b and end >= a]
        if not choques:
            return Amplicon(
                role=role, start=start, end=end, length=length, rationale=rationale
            )
    start = earliest if downstream else latest
    end = start + length - 1
    return Amplicon(
        role=role,
        start=start,
        end=end,
        length=length,
        rationale=rationale,
        overlaps=tuple(f"{a}-{b}" for a, b in avoid if start <= b and end >= a),
    )


def rtqpcr_amplicons(
    signal: PolyASignal,
    *,
    utr_length: int,
    frame: Frame = Frame.UTR3,
    first_position: int = 1,
    avoid: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
    length: int = RTQPCR_AMPLICON_LENGTH,
    margin: int = RTQPCR_MARGIN,
) -> AmpliconPlan:
    """Propone las coordenadas de los dos amplicones. Solo coordenadas.

    `avoid` son tramos que conviene no tocar —tipicamente las ventanas diana de los
    candidatos—; si no cabe fuera de ellos, la propuesta sale con el solape ESCRITO.
    """
    if length < 1:
        raise ValueError(f"length={length} invalido para un amplicon; se aborta.")
    if margin < 0:
        raise ValueError(f"margin={margin} invalido; se aborta.")
    banda = (signal.end + CLEAVAGE_MIN, signal.end + CLEAVAGE_MAX)
    # La holgura vale tambien para lo que hay que esquivar: un amplicon que empieza a 1
    # nt de una diana no deja sitio ni para el cebador.
    evitar = tuple((int(a) - margin, int(b) + margin) for a, b in avoid)

    if first_position < 1:
        raise ValueError(
            f"first_position={first_position} invalido: es la primera posicion de la "
            f"region en la que se puede poner un amplicon, 1-based; se aborta."
        )
    proximal = _place_amplicon(
        role="proximal",
        earliest=first_position,
        latest=signal.position - margin - length,
        length=length,
        downstream=False,
        avoid=evitar,
        rationale=(
            f"entero por delante de {signal.motif}@{label(signal.position, frame)} "
            f"(holgura {margin} nt) y dentro de la region analizada: presente en las "
            f"DOS isoformas, mide el total."
        ),
    )
    distal = _place_amplicon(
        role="distal",
        earliest=banda[1] + margin + 1,
        latest=utr_length - length + 1,
        length=length,
        downstream=True,
        avoid=evitar,
        rationale=(
            f"entero por detras de la banda de corte "
            f"{span(banda[0], banda[1], frame)} (holgura {margin} nt): solo presente en "
            f"la isoforma LARGA."
        ),
    )
    return AmpliconPlan(
        signal=signal,
        proximal=proximal,
        distal=distal,
        cut_band=banda,
        utr_length=utr_length,
        frame=frame,
    )


# ─── ¿Esta conservada la señal en la otra especie? ───────────────────────────
#
# La pregunta se contesta con lo que se PUEDE contestar sin alinear dos especies: si el
# 3'UTR de la otra especie no contiene NI UNA vez el hexamero, la señal no tiene homologo
# posible. Es mas fuerte que un alineamiento y no depende de donde caiga.
#
# Lo que no se hace es alinear raton contra humano con `alignment.py`: ese modulo usa
# difflib sobre dos versiones casi identicas de la MISMA secuencia. Entre especies daria
# un alineamiento sin sentido con pinta de resultado.


@dataclass(frozen=True)
class SignalConservation:
    motif: str
    other_name: str
    other_length: int
    occurrences: tuple[PolyASignal, ...]
    apa_elsewhere: tuple[PolyASignal, ...]

    @property
    def conserved(self) -> bool:
        """¿Aparece el hexamero, aunque sea una vez, en la otra especie?"""
        return bool(self.occurrences)

    def prior_note(self) -> str:
        """Que dice la AUSENCIA sobre la probabilidad a priori. Vacia si aparece.

        Las dos clausulas van juntas y ninguna sobra: rebaja, no descarta.
        """
        if self.conserved:
            return ""
        return (
            f"Y esto no es solo ausencia de homologo: el gen de {self.other_name} ha "
            f"PRESCINDIDO del hexamero canonico por completo — ni una {self.motif} en "
            f"{self.other_length} nt de 3'UTR. Un APA proximal FUNCIONAL es un elemento "
            f"regulador, y los elementos reguladores tienden a conservarse. Eso REBAJA "
            f"la probabilidad a priori de que la señal de esta especie se use. NO LO "
            f"DESCARTA: puede ser una diferencia real de especie, y mientras "
            f"fraccion_isoforma_larga siga sin medir el techo sigue indeterminado. "
            f"Rebaja, no descarta."
        )

    def describe(self) -> str:
        cabecera = (
            f"COMPROBADO sobre {self.other_name}, {self.other_length} nt: "
            f"{len(self.occurrences)} aparicion(es) de {self.motif}."
        )
        if self.conserved:
            cuerpo = (
                " La señal SI aparece en la otra especie: "
                + ", ".join(label(s.position, Frame.UTR3) for s in self.occurrences)
                + ". Que aparezca no dice que sea la MISMA señal —eso necesitaria un"
                " alineamiento— pero descarta que no exista."
            )
        else:
            cuerpo = (
                f" La señal NO esta conservada: el 3'UTR de {self.other_name} no "
                f"contiene {self.motif} ni una sola vez, asi que no hay homologo "
                f"posible. No hace falta alinear para decirlo."
            )
        matiz = ""
        if self.apa_elsewhere:
            matiz = (
                " OJO: eso NO SIGNIFICA QUE la otra especie este libre de "
                "poliadenilacion alternativa. Tiene "
                + ", ".join(
                    f"{s.motif} en {label(s.position, Frame.UTR3)}"
                    for s in self.apa_elsewhere
                )
                + f" clasificada(s) {SignalClass.APA_POSSIBLE.value}: el riesgo no esta "
                f"conservado COMO ESE HEXAMERO, que es otra cosa."
            )
        return cabecera + cuerpo + matiz


def signal_conservation(
    motif: str, other_utr3: str | None, *, other_name: str
) -> SignalConservation:
    """¿Aparece `motif` en el 3'UTR de la otra especie? Y que APA tiene ella."""
    if motif.upper() not in ALL_SIGNALS:
        raise ValueError(
            f"{motif!r} no es una señal de poliadenilacion conocida; se aborta la "
            f"comprobacion de conservacion."
        )
    if not other_name or not other_name.strip():
        raise ValueError(
            "Hay que decir en QUE secuencia se comprueba la conservacion: «no esta "
            "conservada» sin nombrar la otra especie no es un resultado. Se aborta."
        )
    limpia = normalize_sequence(other_utr3, name=f"3'UTR de {other_name}")
    señales = find_polya_signals(limpia)
    return SignalConservation(
        motif=motif.upper(),
        other_name=other_name,
        other_length=len(limpia),
        occurrences=tuple(s for s in señales if s.motif == motif.upper()),
        apa_elsewhere=tuple(
            s for s in señales if s.classification is SignalClass.APA_POSSIBLE
        ),
    )
