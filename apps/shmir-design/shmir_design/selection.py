"""Seleccion voraz de los candidatos finales (paso 15).

Orden de operaciones, que no se cambia:

  1. enmascarar repeticiones y RETILAR      → `masking.py` + `tiling.tile_utr`
  2. aplicar todos los filtros duros        → `tiling.tile_utr`
  3. ordenar los supervivientes por asimetria
  4. agrupar ventanas contiguas en sitios independientes
  5. seleccion voraz con espaciado y cuota

Restricciones:

- **Espaciado minimo de 50 nt entre sitios elegidos.** Es la regla que convierte N
  apuestas correlacionadas en N apuestas independientes: las causas de fallo
  —estructura local, RBPs, repeticiones no anotadas, APA— son REGIONALES, no puntuales.
  Se mide entre las posiciones de inicio de los candidatos elegidos: dos candidatos a
  50 nt exactos valen, a 49 no.
- **Cuota por tercio**: al menos un candidato de cada tercio del 3'UTR, aunque el tercio
  medio puntue peor. Si un tercio no puede cubrirse, se dice por que; no se rellena con
  nada ni se calla.
- **Numero de candidatos configurable**, 6 por especie por defecto.

Un candidato elegido NO es un candidato aprobado: mientras haya filtros en NOT_RUN su
veredicto es INCOMPLETE, y la seleccion es provisional. El informe lo dice.

El nucleo (`choose`) trabaja sobre datos minimos —posicion, tercio, asimetria— para que
se pueda probar entero sin secuencias.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .anatomy import Region
from .filters import FilterState, Verdict
from .polya import Tercio
from .tiling import TiledWindow, TilingReport

DEFAULT_CANDIDATES = 6
DEFAULT_MIN_SPACING = 50
#: Penalizacion de ranking, en kcal/mol, para una ventana que solapa una variante rara
#: de poliadenilacion. No excluye: la baja en la lista. El valor es una convencion.
DEFAULT_WEAK_POLYA_PENALTY = 1.0
TERCIOS = (Tercio.PROXIMAL, Tercio.MEDIO, Tercio.DISTAL)


@dataclass(frozen=True)
class SelectionConfig:
    n_candidates: int = DEFAULT_CANDIDATES
    min_spacing: int = DEFAULT_MIN_SPACING
    require_one_per_tercio: bool = True
    weak_polya_penalty: float = DEFAULT_WEAK_POLYA_PENALTY
    #: Cuota por region, del tipo ((Region.UTR3, 7), (Region.CDS, 3)). Sin ella, solo
    #: entran candidatos del 3'UTR: una ventana del ORF nunca se cuela por accidente,
    #: solo si alguien la pide. La suma tiene que ser exactamente `n_candidates`.
    region_quota: tuple[tuple[Region, int], ...] | None = None

    def __post_init__(self) -> None:
        if self.n_candidates < 1:
            raise ValueError(
                f"n_candidates={self.n_candidates}: hay que pedir al menos 1 candidato; "
                f"se aborta la seleccion."
            )
        if self.min_spacing < 0:
            raise ValueError(
                f"min_spacing={self.min_spacing} invalido; se aborta la seleccion."
            )
        if self.weak_polya_penalty < 0:
            raise ValueError(
                f"weak_polya_penalty={self.weak_polya_penalty}: una penalizacion "
                f"negativa premiaria a la ventana marcada; se aborta."
            )
        if self.region_quota is not None:
            regiones = [r for r, _ in self.region_quota]
            if len(set(regiones)) != len(regiones):
                raise ValueError(
                    f"La cuota por region repite alguna region ({regiones}); se aborta "
                    f"en vez de quedarse con una de las dos cifras."
                )
            if any(n < 0 for _, n in self.region_quota):
                raise ValueError(
                    f"La cuota por region {self.region_quota} tiene alguna cifra "
                    f"negativa; se aborta."
                )
            total = sum(n for _, n in self.region_quota)
            if total != self.n_candidates:
                raise ValueError(
                    f"La cuota por region suma {total} y se piden "
                    f"{self.n_candidates} candidatos. Se aborta en vez de decidir por "
                    f"nuestra cuenta que region se lleva la diferencia."
                )


@dataclass(frozen=True)
class Choice:
    """Lo minimo que la seleccion necesita saber de una ventana elegible."""

    start: int
    end: int
    #: `None` fuera del 3'UTR: los tercios se calculan sobre el 3'UTR y no significan
    #: nada sobre el ORF.
    tercio: Tercio | None
    #: Puntuacion con la que se ordena: asimetria menos la penalizacion.
    asymmetry: float
    label: str
    asymmetry_raw: float = 0.0
    penalty: float = 0.0
    region: Region = Region.UTR3


@dataclass(frozen=True)
class Site:
    """Bloque de ventanas elegibles contiguas."""

    choices: tuple[Choice, ...]

    @property
    def start(self) -> int:
        return self.choices[0].start

    @property
    def end(self) -> int:
        return self.choices[-1].start

    @property
    def best(self) -> Choice:
        return max(self.choices, key=lambda c: (c.asymmetry, -c.start))


@dataclass(frozen=True)
class Selection:
    chosen: tuple[Choice, ...]
    sites: tuple[Site, ...]
    config: SelectionConfig
    quota_unfilled: tuple[str, ...] = field(default=())
    notes: tuple[str, ...] = field(default=())
    _ranked: tuple[int, ...] = field(default=())

    def rank_of(self, start: int) -> int:
        """Puesto por asimetria (1 = mejor) del candidato que empieza en `start`."""
        if start not in self._ranked:
            raise KeyError(f"No hay ningun candidato elegido que empiece en {start}.")
        return self._ranked.index(start) + 1


def group_choices(choices: list[Choice]) -> list[Site]:
    """Agrupa ventanas elegibles contiguas en sitios independientes (paso 4)."""
    ordenadas = sorted(choices, key=lambda c: c.start)
    if not ordenadas:
        return []
    sites: list[Site] = []
    bloque = [ordenadas[0]]
    for actual in ordenadas[1:]:
        if actual.start == bloque[-1].start + 1:
            bloque.append(actual)
            continue
        sites.append(Site(choices=tuple(bloque)))
        bloque = [actual]
    sites.append(Site(choices=tuple(bloque)))
    return sites


def _respects_spacing(candidate: Choice, chosen: list[Choice], min_spacing: int) -> bool:
    return all(abs(candidate.start - c.start) >= min_spacing for c in chosen)


def _cuota_por_tercio(
    disponibles: list[Site],
    plazas: int,
    *,
    chosen: list[Choice],
    usados: set[int],
    config: SelectionConfig,
    quota_unfilled: list[str],
) -> None:
    """Reparte hasta `plazas` entre los tres tercios del 3'UTR, uno cada uno."""
    for tercio in TERCIOS:
        if len(chosen) >= plazas:
            quota_unfilled.append(
                f"tercio {tercio.value}: no quedaban plazas ({plazas} pedidas)."
            )
            continue
        del_tercio = [
            s for s in disponibles
            if s.best.tercio is tercio and id(s) not in usados
        ]
        if not del_tercio:
            quota_unfilled.append(
                f"tercio {tercio.value}: no hay ningun sitio elegible en ese tercio."
            )
            continue
        elegido = next(
            (
                s for s in del_tercio
                if _respects_spacing(s.best, chosen, config.min_spacing)
            ),
            None,
        )
        if elegido is None:
            quota_unfilled.append(
                f"tercio {tercio.value}: hay {len(del_tercio)} sitio(s) elegible(s), "
                f"pero todos quedan a menos de {config.min_spacing} nt de un "
                f"candidato ya elegido (espaciado)."
            )
            continue
        chosen.append(elegido.best)
        usados.add(id(elegido))


def _rellenar(
    disponibles: list[Site],
    tope: int,
    *,
    chosen: list[Choice],
    usados: set[int],
    config: SelectionConfig,
) -> None:
    """Coge por asimetria hasta llegar a `tope`, respetando el espaciado."""
    for site in disponibles:
        if len(chosen) >= tope:
            break
        if id(site) in usados:
            continue
        if not _respects_spacing(site.best, chosen, config.min_spacing):
            continue
        chosen.append(site.best)
        usados.add(id(site))


def choose(sites: list[Site], config: SelectionConfig) -> Selection:
    """Seleccion voraz: cuota por tercio primero, y el resto por asimetria (paso 5).

    Con `region_quota` la seleccion se hace region por region: cada una se lleva
    exactamente las plazas que se le pidieron, y si no puede llenarlas se dice — no se
    rellenan con candidatos de otra region, porque el reparto es una decision de diseño
    y no un cupo que se pueda mover solo.
    """
    ordenados = sorted(sites, key=lambda s: (-s.best.asymmetry, s.best.start))
    chosen: list[Choice] = []
    usados: set[int] = set()
    quota_unfilled: list[str] = []
    notes: list[str] = []

    if config.region_quota is not None:
        if not sites:
            notes.append(
                "No habia ningun sitio elegible: la seleccion esta vacia. Revisa "
                "cuantas ventanas superan los filtros antes de buscar el fallo en la "
                "seleccion."
            )
        for region, plazas in config.region_quota:
            if plazas == 0:
                continue
            de_region = [s for s in ordenados if s.best.region is region]
            antes = len(chosen)
            if region is Region.UTR3 and config.require_one_per_tercio:
                _cuota_por_tercio(
                    de_region,
                    antes + plazas,
                    chosen=chosen,
                    usados=usados,
                    config=config,
                    quota_unfilled=quota_unfilled,
                )
            _rellenar(
                de_region, antes + plazas,
                chosen=chosen, usados=usados, config=config,
            )
            puestos = len(chosen) - antes
            if puestos < plazas:
                quota_unfilled.append(
                    f"region {region.value}: se pedian {plazas} candidato(s) y solo "
                    f"salen {puestos}. Habia {len(de_region)} sitio(s) elegible(s) en "
                    f"esa region; los que faltan no cumplen el espaciado de "
                    f"{config.min_spacing} nt o no existen. No se rellena con "
                    f"candidatos de otra region."
                )
        por_asimetria = sorted(chosen, key=lambda c: (-c.asymmetry, c.start))
        return Selection(
            chosen=tuple(sorted(chosen, key=lambda c: c.start)),
            sites=tuple(sites),
            config=config,
            quota_unfilled=tuple(quota_unfilled),
            notes=tuple(notes),
            _ranked=tuple(c.start for c in por_asimetria),
        )

    if not sites:
        notes.append(
            "No habia ningun sitio elegible: la seleccion esta vacia. Revisa cuantas "
            "ventanas superan los filtros antes de buscar el fallo en la seleccion."
        )

    ordenados = [s for s in ordenados if s.best.region is Region.UTR3]

    if config.require_one_per_tercio:
        if config.n_candidates < len(TERCIOS):
            notes.append(
                f"Se piden {config.n_candidates} candidatos y los tercios son "
                f"{len(TERCIOS)}: la cuota de uno por tercio no cabe entera."
            )
        for tercio in TERCIOS:
            if len(chosen) >= config.n_candidates:
                quota_unfilled.append(
                    f"tercio {tercio.value}: no quedaban plazas "
                    f"({config.n_candidates} pedidas)."
                )
                continue
            del_tercio = [
                s for s in ordenados
                if s.best.tercio is tercio and id(s) not in usados
            ]
            if not del_tercio:
                quota_unfilled.append(
                    f"tercio {tercio.value}: no hay ningun sitio elegible en ese tercio."
                )
                continue
            elegido = next(
                (
                    s for s in del_tercio
                    if _respects_spacing(s.best, chosen, config.min_spacing)
                ),
                None,
            )
            if elegido is None:
                quota_unfilled.append(
                    f"tercio {tercio.value}: hay {len(del_tercio)} sitio(s) elegible(s), "
                    f"pero todos quedan a menos de {config.min_spacing} nt de un "
                    f"candidato ya elegido (espaciado)."
                )
                continue
            chosen.append(elegido.best)
            usados.add(id(elegido))

    for site in ordenados:
        if len(chosen) >= config.n_candidates:
            break
        if id(site) in usados:
            continue
        if not _respects_spacing(site.best, chosen, config.min_spacing):
            continue
        chosen.append(site.best)
        usados.add(id(site))

    if sites and len(chosen) < config.n_candidates:
        notes.append(
            f"Se pedian {config.n_candidates} candidatos y solo salen {len(chosen)}: "
            f"no hay mas sitios elegibles que respeten el espaciado de "
            f"{config.min_spacing} nt."
        )

    por_asimetria = sorted(chosen, key=lambda c: (-c.asymmetry, c.start))
    return Selection(
        chosen=tuple(sorted(chosen, key=lambda c: c.start)),
        sites=tuple(sites),
        config=config,
        quota_unfilled=tuple(quota_unfilled),
        notes=tuple(notes),
        _ranked=tuple(c.start for c in por_asimetria),
    )


# ─── De un informe de tiling a candidatos ────────────────────────────────────
@dataclass(frozen=True)
class ReportSelection:
    selection: Selection
    windows: dict[str, TiledWindow]
    eligible: int
    total: int
    not_run_filters: dict[str, int]
    #: Elegibles con el criterio ESTRICTO, para poder comparar las dos cifras.
    eligible_strict: int = 0

    def window_of(self, choice: Choice) -> TiledWindow:
        return self.windows[choice.label]

    @property
    def provisional(self) -> bool:
        """¿Hay filtros sin correr? Entonces la seleccion no es definitiva."""
        return bool(self.not_run_filters)


def is_eligible(window: TiledWindow, config: SelectionConfig | None = None) -> bool:
    """Elegible = supera los seis biofisicos y no falla ningun filtro conocido.

    Un filtro en NOT_RUN no descarta la ventana, pero tampoco la aprueba: su veredicto
    seguira siendo INCOMPLETE y la seleccion entera sera provisional.

    Fuera del 3'UTR hace falta ademas que alguien haya pedido esa region con una cuota
    (`SelectionConfig.region_quota`). Sin cuota, una ventana del ORF no entra: puede ser
    una diana perfectamente valida, pero es una decision de diseño, no un descuido.
    """
    regiones_pedidas = (
        {r for r, n in config.region_quota if n > 0}
        if config is not None and config.region_quota is not None
        else {Region.UTR3}
    )
    if window.region not in regiones_pedidas:
        return False
    if window.region is Region.UTR3 and window.tercio is None:
        return False
    if not window.biofisicos_ok:
        return False
    return all(r.state is not FilterState.FAIL for r in window.filters)


def is_eligible_strict(
    window: TiledWindow, config: SelectionConfig | None = None
) -> bool:
    """Elegible con el criterio ESTRICTO: ±flanco para los doce hexameros por igual."""
    return is_eligible(window, config) and window.estricto_ok


def eligible_choices(
    report: TilingReport, config: SelectionConfig | None = None
) -> list[Choice]:
    """Paso 3: supervivientes, con su puntuacion, listos para ordenar.

    La puntuacion es la asimetria menos la penalizacion por solapar una variante rara
    de poliadenilacion. Se guardan las dos cifras para que el informe pueda enseñar
    cuanto se ha penalizado y por que.
    """
    config = config or SelectionConfig()
    choices: list[Choice] = []
    for window in report.windows:
        if not is_eligible(window, config):
            continue
        asymmetry = window.evaluation.asymmetry
        if asymmetry is None:
            raise ValueError(
                f"La ventana {window.window.name} es elegible pero no tiene valor de "
                f"asimetria: no se puede ordenar por un numero que no existe. Se aborta "
                f"la seleccion en vez de inventar un orden."
            )
        penalty = config.weak_polya_penalty if window.bandera_polyA_debil else 0.0
        choices.append(
            Choice(
                start=window.window.start,
                end=window.window.end,
                tercio=window.tercio,
                asymmetry=asymmetry - penalty,
                label=window.window.name,
                asymmetry_raw=asymmetry,
                penalty=penalty,
                region=window.region,
            )
        )
    return choices


def select_from_report(
    report: TilingReport,
    config: SelectionConfig | None = None,
) -> ReportSelection:
    """Pasos 3, 4 y 5 sobre un informe de tiling ya filtrado."""
    config = config or SelectionConfig()
    choices = eligible_choices(report, config)
    sites = group_choices(choices)
    selection = choose(sites, config)
    return ReportSelection(
        selection=selection,
        windows={w.window.name: w for w in report.windows},
        eligible=len(choices),
        total=len(report.windows),
        not_run_filters=report.not_run_counts(),
        eligible_strict=sum(1 for w in report.windows if is_eligible_strict(w)),
    )


# ─── Sensibilidad de la penalizacion ─────────────────────────────────────────
DEFAULT_PENALTY_SWEEP = (0.5, 1.0, 1.5, 2.0)


@dataclass(frozen=True)
class PenaltySensitivity:
    """¿Importa el valor de la penalizacion, o da igual?

    La penalizacion por solapar una variante rara de poliadenilacion no tiene un valor
    con base biologica. En vez de fijarla a ciegas, se barre un rango y se mira si
    cambia QUIEN entra. Si no cambia, el valor es irrelevante y se documenta asi; si
    cambia, es una decision con consecuencias y hay que tomarla a proposito.
    """

    values: tuple[float, ...]
    selections: dict[float, tuple[int, ...]]
    flagged: int
    stable: bool

    def describe(self) -> str:
        if self.flagged == 0:
            return (
                "Ninguna ventana lleva bandera de poliadenilacion debil: la "
                "penalizacion no afecta a nada en este 3'UTR."
            )
        if self.stable:
            return (
                f"Los seleccionados NO cambian entre {min(self.values)} y "
                f"{max(self.values)} kcal/mol: el valor exacto es irrelevante aqui."
            )
        return (
            f"Los seleccionados CAMBIAN dentro del rango {min(self.values)}–"
            f"{max(self.values)} kcal/mol: el valor no es inocuo, decidelo a proposito."
        )


def penalty_sensitivity(
    report: TilingReport,
    config: SelectionConfig | None = None,
    values: tuple[float, ...] = DEFAULT_PENALTY_SWEEP,
) -> PenaltySensitivity:
    """Repite la seleccion con varias penalizaciones y compara quien sale elegido."""
    if not values:
        raise ValueError(
            "No hay ningun valor de penalizacion que barrer; se aborta en vez de "
            "devolver un analisis vacio que parezca concluyente."
        )
    base = config or SelectionConfig()
    selections: dict[float, tuple[int, ...]] = {}
    for value in values:
        variante = SelectionConfig(
            n_candidates=base.n_candidates,
            min_spacing=base.min_spacing,
            require_one_per_tercio=base.require_one_per_tercio,
            weak_polya_penalty=value,
            region_quota=base.region_quota,
        )
        seleccion = select_from_report(report, variante)
        selections[value] = tuple(c.start for c in seleccion.selection.chosen)

    return PenaltySensitivity(
        values=tuple(values),
        selections=selections,
        flagged=sum(1 for w in report.windows if w.bandera_polyA_debil),
        stable=len(set(selections.values())) == 1,
    )


# ─── Los tres criterios de polyA, lado a lado (bloque 3) ─────────────────────


@dataclass(frozen=True)
class PolyAModeComparison:
    """Top-N bajo los tres modos. Si coinciden, el debate del umbral es irrelevante."""

    selections: dict[str, tuple[int, ...]]
    eligible: dict[str, int]
    stable: bool

    def format_text(self) -> str:
        lines = [
            "  Modo        elegibles   candidatos elegidos",
        ]
        for modo, elegidos in self.selections.items():
            posiciones = ", ".join(str(p) for p in elegidos) or "ninguno"
            lines.append(f"  {modo:<11} {self.eligible[modo]:>9}   {posiciones}")
        if self.stable:
            lines.append(
                "  Los tres modos eligen exactamente los mismos candidatos: el umbral "
                "de polyA no decide nada aqui, asi que el debate sobre el ±10 nt es "
                "irrelevante para esta seleccion."
            )
        else:
            lines.append(
                "  Los tres modos NO eligen lo mismo: aqui el criterio de polyA SI "
                "cambia quien entra, asi que la eleccion de modo es una decision de "
                "diseño y no un detalle."
            )
        return "\n".join(lines)


def polya_mode_comparison(
    report: TilingReport, config: SelectionConfig | None = None
) -> PolyAModeComparison:
    """Rehace la seleccion bajo los tres criterios de polyA y compara quien sale.

    Mismo patron que el barrido de la penalizacion: si mover el criterio no cambia el
    top-N, se dice y se olvida el asunto; si lo cambia, se dice con esas palabras.
    """
    from dataclasses import replace

    from .anatomy import Region
    from .polya import PolyAMode, annotate_polya

    base = config or SelectionConfig()
    selections: dict[str, tuple[int, ...]] = {}
    elegibles: dict[str, int] = {}

    for modo in PolyAMode:
        ventanas = []
        for window in report.windows:
            if window.region is not Region.UTR3:
                # Fuera del 3'UTR el filtro sale NO_APLICA en los tres modos.
                ventanas.append(window)
                continue
            anotacion = annotate_polya(
                window.window,
                list(report.signals),
                utr_length=report.utr_length,
                mode=modo,
            )
            ventanas.append(
                replace(
                    window, zona_prohibida=anotacion.veredicto, polya=anotacion
                )
            )
        variante = replace(report, windows=tuple(ventanas), polya_mode=modo)
        seleccion = select_from_report(variante, base)
        selections[modo.value] = tuple(c.start for c in seleccion.selection.chosen)
        elegibles[modo.value] = sum(1 for w in ventanas if is_eligible(w, base))

    return PolyAModeComparison(
        selections=selections,
        eligible=elegibles,
        stable=len(set(selections.values())) == 1,
    )
