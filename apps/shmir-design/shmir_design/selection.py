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
from types import MappingProxyType

from .accessibility import CONTEXT_WINDOWS as _CTX
from .anatomy import Anatomy, Region
from .coords import Frame, frame_of, label
from .filters import FilterState, Verdict
from .hard_filters import gc_fraction
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
    #: Reparte los elegidos por los extremos de los parametros dudosos en vez de coger
    #: los N mejores por asimetria. Ver `COVERAGE_AXES`.
    spread_coverage: bool = False

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
    #: Parametros DUDOSOS, los que se reparten cuando se pide cobertura de rango.
    gc: float | None = None
    accessibility: float | None = None
    apa_risk: bool = False
    weak_polya: bool = False


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
            rellenar = _spread if config.spread_coverage else _rellenar
            rellenar(
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

    if config.spread_coverage:
        _spread(
            ordenados, config.n_candidates,
            chosen=chosen, usados=usados, config=config,
        )
    else:
        _rellenar(
            ordenados, config.n_candidates,
            chosen=chosen, usados=usados, config=config,
        )

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
    #: La anatomia del informe del que salio esta seleccion. Viaja con ella porque de
    #: ella sale el ESPACIO DE COORDENADAS de todo lo que se imprima: sin anatomia, un
    #: `1018` no dice si es del transcrito o del 3'UTR. Antes cada escritor la recibia
    #: por su cuenta —o no la recibia— y `comparative_text` llamaba a
    #: `comparative_rows` sin ella.
    anatomy: "Anatomy | None" = None

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
                gc=gc_fraction(window.evaluation.sequence),
                accessibility=(
                    window.accesibilidad.unpaired_fraction.get(
                        ACCESSIBILITY_COLUMN_WINDOW
                    )
                    if window.accesibilidad is not None
                    else None
                ),
                apa_risk=window.riesgo_APA,
                weak_polya=window.bandera_polyA_debil,
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
        anatomy=report.anatomy,
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
    #: Espacio de las posiciones de `selections`: el de LO TILADO.
    frame: Frame = Frame.UTR3

    def format_text(self) -> str:
        lines = [
            "  Modo        elegibles   candidatos elegidos",
        ]
        for modo, elegidos in self.selections.items():
            posiciones = (
                ", ".join(label(p, self.frame) for p in elegidos) or "ninguno"
            )
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
        frame=frame_of(report.anatomy) if report.anatomy is not None else Frame.UTR3,
    )


# ─── Cobertura de rango (bloque 6) ───────────────────────────────────────────
#
# Por que no los N mejores por asimetria: la asimetria predice SELECCION DE HEBRA, no
# potencia. Si el objetivo de llevar diez candidatos es correlacionar cada parametro
# contra el knockdown medido y averiguar cuales predicen algo, los puntos tienen que
# estar repartidos. Diez candidatos todos con GC 0,50 no dicen nada sobre el GC.
#
# Los ejes son los parametros DUDOSOS. Los que ya se sabe que hay que respetar (la
# especificidad, el transgen, la colision de seed) no se reparten: se cumplen.

ACCESSIBILITY_COLUMN_WINDOW = _CTX[0]

COVERAGE_AXES = ("GC", "accesibilidad", "APA", "polyA_debil")

#: Corte de los ejes continuos. Es una convencion nuestra, y por eso el informe imprime
#: el rango REAL que cubre la seleccion y no solo la etiqueta del bin.
GC_SPLIT = 0.45
ACCESSIBILITY_SPLIT = 0.50

#: Recorrido MINIMO que tiene que tener la piscina de elegibles en un eje continuo para
#: que ese eje se pueda estudiar. Contar solo los bins engaña: una piscina con el GC
#: entre 0,41 y 0,50 cruza el corte de 0,45 y "cubre" los dos bins, pero son 0,09 de
#: recorrido — no hay contraste que correlacionar contra el knockdown.
#:
#: Los valores son convencion nuestra, no una cifra publicada, asi que se IMPRIMEN en el
#: informe junto al recorrido real para que quien lo lea pueda discrepar con criterio.
#: Referencia para el GC: el filtro duro deja pasar 0,30-0,52, o sea 0,22 de recorrido
#: total; se pide al menos la mitad.
MIN_SPAN = MappingProxyType({"GC": 0.10, "accesibilidad": 0.30})


def _bins(choice: Choice) -> dict[str, str | None]:
    """Celda de cada eje. `None` cuando no hay dato: un eje sin dato no se reparte."""
    return {
        "GC": None if choice.gc is None else ("bajo" if choice.gc < GC_SPLIT else "alto"),
        "accesibilidad": (
            None
            if choice.accessibility is None
            else ("baja" if choice.accessibility < ACCESSIBILITY_SPLIT else "alta")
        ),
        "APA": "detras" if choice.apa_risk else "delante",
        "polyA_debil": "con_bandera" if choice.weak_polya else "sin_bandera",
    }


def _spread(
    disponibles: list[Site],
    tope: int,
    *,
    chosen: list[Choice],
    usados: set[int],
    config: SelectionConfig,
) -> None:
    """Voraz por COBERTURA: en cada paso, el que cubre mas celdas todavia vacias.

    A igualdad de celdas nuevas manda la asimetria, asi que cuando ya no queda nada que
    cubrir el comportamiento vuelve a ser el de siempre.
    """
    cubiertas: set[tuple[str, str]] = set()
    for elegido in chosen:
        for eje, celda in _bins(elegido).items():
            if celda is not None:
                cubiertas.add((eje, celda))

    while len(chosen) < tope:
        mejor, mejor_clave = None, None
        for site in disponibles:
            if id(site) in usados:
                continue
            if not _respects_spacing(site.best, chosen, config.min_spacing):
                continue
            nuevas = sum(
                1
                for eje, celda in _bins(site.best).items()
                if celda is not None and (eje, celda) not in cubiertas
            )
            clave = (nuevas, site.best.asymmetry, -site.best.start)
            if mejor_clave is None or clave > mejor_clave:
                mejor, mejor_clave = site, clave
        if mejor is None:
            break
        chosen.append(mejor.best)
        usados.add(id(mejor))
        for eje, celda in _bins(mejor.best).items():
            if celda is not None:
                cubiertas.add((eje, celda))


@dataclass(frozen=True)
class CoverageReport:
    """Que rango cubre la seleccion en cada eje dudoso, y si el eje da para estudiarlo.

    La distincion importa y no es cosmetica. Que la seleccion no cubra un eje puede
    significar dos cosas muy distintas:

      - La piscina de candidatos elegibles SI tenia los dos extremos y la seleccion no
        los cogio. Eso se arregla pidiendo `--reparto-rango` o mas candidatos.
      - La piscina entera esta apretada — p. ej. todos los supervivientes con GC entre
        0,41 y 0,50. Entonces **no es un fallo de la app**: es informacion. Ese eje no
        se puede estudiar con este 3'UTR, y hay que dejar de tratarlo como variable.

    Distinguirlas necesita mirar la piscina, no solo los elegidos; por eso
    `coverage_report` acepta `sites`. Sin ella no se diagnostica, y se dice.
    """

    axes: dict[str, dict[str, object]]

    def format_text(self) -> str:
        lines = []
        for eje, datos in self.axes.items():
            if datos["sin_dato"]:
                lines.append(
                    f"  {eje:<14} sin dato en {datos['sin_dato']} de "
                    f"{datos['total']} candidato(s): ese eje no se pudo repartir."
                )
                continue
            celdas = datos["celdas"]
            rango = datos.get("rango")
            detalle = f" (de {rango[0]:.2f} a {rango[1]:.2f})" if rango else ""
            if len(celdas) < 2:
                unica = next(iter(celdas)) if celdas else "?"
                lines.append(
                    f"  {eje:<14} NO SE CUBRE el rango: los {datos['total']} "
                    f"candidato(s) caen todos en {unica!r}."
                )
                lines.extend(self._diagnostico(eje, datos))
                continue
            if datos.get("estudiable") is False:
                lines.append(
                    f"  {eje:<14} cubre {', '.join(sorted(celdas))}{detalle}, pero el "
                    f"recorrido es demasiado corto."
                )
                lines.extend(self._diagnostico(eje, datos))
                continue
            linea = f"  {eje:<14} cubre {', '.join(sorted(celdas))}{detalle}"
            if datos.get("estudiable") is None and eje in MIN_SPAN:
                linea += (
                    "  [no se comprobo el recorrido de la piscina de elegibles]"
                )
            lines.append(linea)
        return "\n".join(lines)

    def _sangria(self) -> str:
        return " " * 17

    def _diagnostico(self, eje: str, datos: dict[str, object]) -> list[str]:
        estudiable = datos.get("estudiable")
        sangria = self._sangria()
        if estudiable is None:
            return [
                f"{sangria}No se comprobo si la piscina de elegibles daba de si, asi "
                f"que no se puede decir si es cosa de la seleccion o del 3'UTR."
            ]
        if estudiable:
            rango = datos.get("rango_piscina")
            detalle = (
                f" (la piscina va de {rango[0]:.2f} a {rango[1]:.2f})" if rango else ""
            )
            return [
                f"{sangria}Pero SI habia candidatos elegibles en los dos "
                f"extremos{detalle}: es la seleccion la que no los ha repartido. "
                f"Prueba --reparto-rango o mas candidatos.",
            ]
        rango = datos.get("rango_piscina")
        minimo = MIN_SPAN.get(eje)
        if rango and minimo is not None:
            recorrido = rango[1] - rango[0]
            detalle = (
                f" — TODOS los elegibles caen entre {rango[0]:.2f} y {rango[1]:.2f}, "
                f"{recorrido:.2f} de recorrido, por debajo del minimo de {minimo:.2f} "
                f"que pedimos para dar un eje por estudiable"
            )
        elif rango:
            detalle = (
                f" — todos los elegibles caen entre {rango[0]:.2f} y {rango[1]:.2f}"
            )
        else:
            detalle = " — no hay elegibles en el otro extremo"
        sangria = self._sangria()
        return [
            f"{sangria}Y no hay de donde sacarlos{detalle}.",
            f"{sangria}Eso NO ES UN FALLO de la app ni de la seleccion: es INFORMACION.",
            f"{sangria}Este eje NO SE PUEDE ESTUDIAR con este 3'UTR. Deja de tratarlo "
            f"como variable del experimento:",
            f"{sangria}no habra contraste que correlacionar contra el knockdown medido, "
            f"por muchos candidatos que se pidan.",
        ]


def _celdas_y_rango(choices: list[Choice], eje: str) -> tuple[set[str], tuple | None, int]:
    celdas: set[str] = set()
    sin_dato = 0
    for choice in choices:
        celda = _bins(choice)[eje]
        if celda is None:
            sin_dato += 1
        else:
            celdas.add(celda)
    valores = {
        "GC": [c.gc for c in choices],
        "accesibilidad": [c.accessibility for c in choices],
    }.get(eje)
    rango = None
    if valores is not None:
        presentes = [v for v in valores if v is not None]
        if presentes:
            rango = (min(presentes), max(presentes))
    return celdas, rango, sin_dato


def coverage_report(
    selection: Selection, sites: list[Site] | None = None
) -> CoverageReport:
    """Rango cubierto por los elegidos, eje por eje. Se imprime siempre.

    `sites` es la piscina de sitios elegibles. Con ella se puede distinguir "la
    seleccion no reparte" de "este 3'UTR no da para estudiar ese eje", que es una
    diferencia de interpretacion, no de grado. Sin ella no se diagnostica y se dice.
    """
    elegidos = list(selection.chosen)
    piscina = [s.best for s in (sites if sites is not None else selection.sites)] if (
        sites is not None or selection.sites
    ) else []
    ejes: dict[str, dict[str, object]] = {}

    for eje in COVERAGE_AXES:
        celdas, rango, sin_dato = _celdas_y_rango(elegidos, eje)
        datos: dict[str, object] = {
            "celdas": celdas,
            "sin_dato": sin_dato,
            "total": len(elegidos),
        }
        if rango is not None:
            datos["rango"] = rango
        if sites is not None:
            celdas_piscina, rango_piscina, _ = _celdas_y_rango(piscina, eje)
            #: Un eje continuo necesita ADEMAS recorrido: dos bins que se tocan a los
            #: lados de un corte arbitrario no son contraste.
            minimo = MIN_SPAN.get(eje)
            bastante = True
            if minimo is not None:
                bastante = (
                    rango_piscina is not None
                    and (rango_piscina[1] - rango_piscina[0]) >= minimo
                )
            datos["estudiable"] = len(celdas_piscina) >= 2 and bastante
            datos["celdas_piscina"] = celdas_piscina
            if rango_piscina is not None:
                datos["rango_piscina"] = rango_piscina
        ejes[eje] = datos
    return CoverageReport(axes=ejes)
