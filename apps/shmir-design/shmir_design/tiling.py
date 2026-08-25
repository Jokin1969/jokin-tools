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
    Aviso,
    PolyASignal,
    Tercio,
    Window,
    annotate_3utr,
    find_polya_signals,
    normalize_sequence,
)
from .seeds import SeedSet, filter_seed
from .thermo import turner_asymmetry


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
    tercio: Tercio
    riesgo_APA: bool
    apa_upstream: tuple[PolyASignal, ...] = ()

    @property
    def filters(self) -> tuple[FilterResult, ...]:
        return self.evaluation.filters + (
            self.zona_prohibida,
            self.repeticiones,
            self.seed,
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
    avisos: tuple[Aviso, ...]
    seeds: SeedSet | None
    mask: RepeatMask | None = None
    thresholds: Thresholds = DEFAULT_THRESHOLDS

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
            ["inicio", "fin", "diana", "guia", "tercio"]
            + filtros
            + ["biofisicos_ok", "riesgo_APA", "veredicto", "motivos"]
        )
        rows = [columns]
        for tiled in self.windows:
            rows.append(
                [
                    str(tiled.window.start),
                    str(tiled.window.end),
                    tiled.evaluation.sequence,
                    tiled.evaluation.guide,
                    tiled.tercio.value,
                ]
                + [r.state.value for r in tiled.filters]
                + [
                    str(tiled.biofisicos_ok),
                    str(tiled.riesgo_APA),
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
    asymmetry_model: AsymmetryModel | None = turner_asymmetry,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> TilingReport:
    """Enmascara, RETILA y evalua todas las ventanas. Ninguna se omite del informe.

    El orden importa: primero se enmascara y despues se trocea, para que una ventana
    parcialmente repetitiva se reevalue entera en vez de tacharse de una lista ya hecha.
    Las señales de poliadenilacion se buscan sobre la secuencia SIN enmascarar.
    """
    original = normalize_sequence(sequence, name="3'UTR")
    signals = find_polya_signals(original, flank=thresholds.polya_flank)
    cleaned = apply_mask(original, mask)
    windows = [
        Window(start, window_size, label=f"w{start}")
        for start in tile_positions(len(cleaned), window_size)
    ]
    annotated = annotate_3utr(windows, signals, len(cleaned))

    tiled: list[TiledWindow] = []
    for anotada in annotated.windows:
        start = anotada.window.start
        evaluation = evaluate_window(
            cleaned[start - 1 : start - 1 + window_size],
            asymmetry_model=asymmetry_model,
            offset=start,
            thresholds=thresholds,
        )
        tiled.append(
            TiledWindow(
                window=anotada.window,
                evaluation=evaluation,
                zona_prohibida=anotada.zona_prohibida,
                seed=filter_seed(evaluation.guide, seeds),
                repeticiones=filter_repeats(start, anotada.window.end, mask),
                tercio=anotada.tercio,
                riesgo_APA=anotada.riesgo_APA,
                apa_upstream=anotada.apa_upstream,
            )
        )

    return TilingReport(
        utr_length=len(cleaned),
        window_size=window_size,
        windows=tuple(tiled),
        signals=tuple(signals),
        avisos=annotated.avisos,
        seeds=seeds,
        mask=mask,
        thresholds=thresholds,
    )
