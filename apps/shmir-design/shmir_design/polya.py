"""Guardarrailes de poliadenilacion sobre el 3'UTR.

Tres cosas, en el orden en que se pidieron:

A. Localiza la señal canonica AATAAA y sus variantes principales, con posicion y
   distancia al extremo 3'. Clasifica cada una como señal terminal probable (10-40 nt
   del final) o como posible sitio de poliadenilacion alternativa (AATAAA canonica a
   mas de 100 nt del final). Toda ventana que solape una señal ±10 nt queda EXCLUIDA.
B. Si aparece un APA proximal, emite un AVISO destacado: los candidatos corriente
   abajo podrian no capturar la isoforma corta. No se excluyen; se anotan con
   `riesgo_APA=True`.
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
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

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

    @property
    def end(self) -> int:
        return self.position + len(self.motif) - 1

    @property
    def is_canonical(self) -> bool:
        return self.motif == CANONICAL_SIGNAL

    @property
    def forbidden_start(self) -> int:
        return max(1, self.position - SIGNAL_FLANK)

    @property
    def forbidden_end(self) -> int:
        return min(self.utr_length, self.end + SIGNAL_FLANK)

    def describe(self) -> str:
        return (
            f"{self.motif} en {self.position}-{self.end} "
            f"(a {self.distance_to_3p} nt del extremo 3') → {self.classification}"
        )


def classify_signal(motif: str, position: int, utr_length: int) -> PolyASignal:
    """Clasifica una señal por sus coordenadas, sin necesitar la secuencia."""
    motif = motif.upper()
    if motif not in ALL_SIGNALS:
        raise ValueError(
            f"{motif!r} no es una señal de poliadenilacion conocida "
            f"(canonica {CANONICAL_SIGNAL} o variantes {', '.join(VARIANT_SIGNALS)}); "
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
    elif motif == CANONICAL_SIGNAL and distance > APA_MIN_DISTANCE:
        classification = SignalClass.APA_POSSIBLE
    else:
        classification = SignalClass.OTHER

    return PolyASignal(
        motif=motif,
        position=position,
        utr_length=utr_length,
        distance_to_3p=distance,
        classification=classification,
    )


def find_polya_signals(
    sequence: str | None,
    *,
    first_position: int = 1,
    utr_length: int | None = None,
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
            signals.append(classify_signal(motif, first_position + index, utr_length))
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
    tercio: Tercio
    riesgo_APA: bool
    apa_upstream: tuple[PolyASignal, ...] = ()

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
            lines.extend(f"  · {s.describe()}" for s in self.signals)
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
                f"  {window.name} [{window.start}-{window.end}] "
                f"{annotated.tercio.value:<8} "
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
                    str(window.start),
                    str(window.end),
                    annotated.tercio.value,
                    annotated.zona_prohibida.state.value,
                    annotated.zona_prohibida.reason,
                    str(annotated.riesgo_APA),
                    ",".join(str(s.position) for s in annotated.apa_upstream),
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


def _zona_prohibida(window: Window, signals: list[PolyASignal]) -> FilterResult:
    solapadas = [
        s for s in signals
        if window.start <= s.forbidden_end and window.end >= s.forbidden_start
    ]
    if solapadas:
        detalle = "; ".join(
            f"{s.motif} en {s.position} (zona prohibida "
            f"{s.forbidden_start}-{s.forbidden_end})"
            for s in solapadas
        )
        return FilterResult(
            name=FILTER_NAME,
            state=FilterState.FAIL,
            reason=f"Solapa señal de poliadenilacion ±{SIGNAL_FLANK} nt: {detalle}.",
        )
    return FilterResult(
        name=FILTER_NAME,
        state=FilterState.PASS,
        reason=(
            f"Sin solape con ninguna de las {len(signals)} señal(es) detectadas "
            f"(±{SIGNAL_FLANK} nt)."
        ),
    )


def annotate_3utr(
    windows: list[Window],
    signals: list[PolyASignal] | None,
    utr_length: int,
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
        tercio = tercio_of(window, utr_length)

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
        annotated.append(
            AnnotatedWindow(
                window=window,
                zona_prohibida=_zona_prohibida(window, signals),
                tercio=tercio,
                riesgo_APA=bool(apa_upstream),
                apa_upstream=apa_upstream,
            )
        )

    return Report(
        utr_length=utr_length,
        signals=tuple(signals or ()),
        windows=tuple(annotated),
        avisos=tuple(_avisos_apa(signals, annotated)),
        signals_available=signals is not None,
    )


def _avisos_apa(
    signals: list[PolyASignal] | None,
    annotated: list[AnnotatedWindow],
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
            alcance += f", posiciones {rango[0]}-{rango[1]}"

        avisos.append(
            Aviso(
                code="APA_PROXIMAL",
                message=(
                    f"Posible poliadenilacion alternativa: {signal.motif} canonica en "
                    f"{signal.position} (a {signal.distance_to_3p} nt del extremo 3'). "
                    f"{alcance}. Podrian no capturar la isoforma corta. NO se excluyen: "
                    f"quedan anotadas con riesgo_APA=True y la lista completa esta en "
                    f"el TSV. La decision es del responsable."
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
