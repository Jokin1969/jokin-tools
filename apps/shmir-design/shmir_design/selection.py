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

from dataclasses import dataclass, field, replace
from types import MappingProxyType

from .accessibility import CONTEXT_WINDOWS as _CTX
from .anatomy import Anatomy, Region
from .coords import Frame, frame_of, label
from .filters import FilterState, Verdict
from .hard_filters import gc_fraction
from .polya import CLEAVAGE_MAX, CLEAVAGE_MIN, PolyASignal, Tercio
from .tiling import TiledWindow, TilingReport

#: El panel del proyecto son DIEZ, no seis. El 6 venia de antes de que se fijaran las
#: cuotas y ya no coincidia con nada: con 6 se quedan fuera `3utr:10`, `143`, `200` y
#: `735` — tres de los cuatro inmunes—, asi que el valor por defecto de la interfaz
#: producia un panel que contradecia lo decidido sin que nadie lo dijera.
DEFAULT_CANDIDATES = 10

#: Minimo de candidatos INMUNES al truncamiento por la señal proximal. Valia 0, o sea
#: que por defecto NO habia cuota de inmunes y solo mandaba la de tercios — y entonces
#: `3utr:359` (+4,82) desplazaba a `3utr:200` (+3,80) por asimetria, dejando el panel con
#: TRES inmunes en vez de cuatro.
#:
#: Por que cuatro y por que es una cuota y no una preferencia: los inmunes son la UNICA
#: reserva si el APA de `3utr:288` resulta funcional, y los sitios elegibles por delante
#: del corte estan **20/0/0** por tercio —todos en el proximal—, asi que si se pierden no
#: hay de donde rebalancear. Cuatro es lo que cabe con el espaciado de 50 nt, medido, no
#: elegido. Ver la entrada de `CLAUDE.md` sobre por que el espaciado no se baja para
#: meter un quinto.
DEFAULT_IMMUNE_QUOTA = 4
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
    #: Minimo de candidatos POR TERCIO del 3'UTR. Generaliza `require_one_per_tercio`,
    #: que sigue mandando: con `require_one_per_tercio=False` no hay cuota por tercio.
    #: Existe porque las causas de fallo son REGIONALES, no puntuales: cinco candidatos
    #: en el mismo tramo comparten modo de fallo aunque tengan asimetrias distintas.
    min_per_tercio: int = 1
    #: Minimo de candidatos INMUNES al truncamiento por la señal proximal, y la posicion
    #: por delante de la cual hay que empezar para serlo (el corte mas tardio de esa
    #: señal, en el marco de LO TILADO). Las dos van juntas: pedir «cinco inmunes» sin
    #: decir inmunes A QUE no significa nada.
    apa_immune_quota: int = 0
    apa_immune_before: int | None = None
    #: Cuota EXPLICITA por tercio, del tipo ((PROXIMAL, 4), (MEDIO, 3), (DISTAL, 2)).
    #: Manda sobre `min_per_tercio`. Existe para poder REASIGNAR una plaza a un tercio
    #: concreto y que quede escrito cual y por que, en vez de que el reparto salga de
    #: la asimetria y parezca deliberado.
    tercio_quota: tuple[tuple[Tercio, int], ...] | None = None
    #: Cuota por TRAMO DE INICIO, en coordenadas explicitas del 3'UTR:
    #: ((829, 1242, 2),) = «al menos 2 candidatos que EMPIECEN en 3utr:829-1242».
    #: No depende de ninguna definicion de tercio, que es justo el problema que
    #: resuelve: `Tercio` etiqueta por punto MEDIO de la ventana y la particion simple
    #: va por INICIO, asi que 3utr:819 sale «distal» etiquetado y «medio» por inicio.
    start_window_quota: tuple[tuple[int, int, int], ...] | None = None

    def __post_init__(self) -> None:
        if self.n_candidates < 1:
            raise ValueError(
                f"n_candidates={self.n_candidates}: hay que pedir al menos 1 candidato; "
                f"se aborta la selección."
            )
        if self.min_spacing < 0:
            raise ValueError(
                f"min_spacing={self.min_spacing} invalido; se aborta la selección."
            )
        if self.min_per_tercio < 0:
            raise ValueError(
                f"min_per_tercio={self.min_per_tercio}: una cuota negativa no significa "
                f"nada; se aborta la selección."
            )
        # Solo cuando alguien PIDE mas de uno por tercio. Con el valor por defecto (1)
        # y un panel de menos de tres, el comportamiento de siempre se mantiene: nota y
        # `quota_unfilled`, no abortar — hay tests que dependen de que un panel de 2
        # salga con su aviso.
        if (
            self.require_one_per_tercio
            and self.min_per_tercio > 1
            and self.min_per_tercio * len(TERCIOS) > self.n_candidates
        ):
            raise ValueError(
                f"min_per_tercio={self.min_per_tercio} sobre {len(TERCIOS)} tercios "
                f"pide {self.min_per_tercio * len(TERCIOS)} candidatos y el panel es de "
                f"{self.n_candidates}. Se aborta en vez de recortar la cuota en "
                f"silencio: cuántos candidatos por tercio es una decisión de diseño."
            )
        if self.tercio_quota is not None:
            tercios = [t for t, _ in self.tercio_quota]
            if len(set(tercios)) != len(tercios):
                raise ValueError(
                    f"La cuota por tercio repite alguno ({tercios}); se aborta en vez "
                    f"de quedarse con una de las dos cifras."
                )
            if any(n < 0 for _, n in self.tercio_quota):
                raise ValueError(
                    f"La cuota por tercio {self.tercio_quota} tiene alguna cifra "
                    f"negativa; se aborta."
                )
            total = sum(n for _, n in self.tercio_quota)
            if total > self.n_candidates:
                raise ValueError(
                    f"La cuota por tercio suma {total} y el panel es de "
                    f"{self.n_candidates}. Se aborta en vez de recortarla por nuestra "
                    f"cuenta: que tercio pierde la plaza es una decisión de diseño."
                )
        for inicio, fin, plazas in self.start_window_quota or ():
            if fin < inicio:
                raise ValueError(
                    f"Tramo {inicio}-{fin} invertido en start_window_quota; se aborta."
                )
            if plazas < 0 or plazas > self.n_candidates:
                raise ValueError(
                    f"start_window_quota pide {plazas} candidato(s) en {inicio}-{fin} y "
                    f"el panel es de {self.n_candidates}; se aborta."
                )
        if self.apa_immune_quota < 0:
            raise ValueError(
                f"apa_immune_quota={self.apa_immune_quota} invalida; se aborta."
            )
        # `apa_immune_before=None` con cuota NO es «sin decir a que»: es «sacalo del
        # informe» (`derive_immune_cut`), que ademas es mejor que teclearlo. Lo que no
        # puede pasar es llegar a `choose()` sin resolverlo, y eso lo comprueba `choose`.
        if self.apa_immune_quota > self.n_candidates:
            raise ValueError(
                f"Se piden {self.apa_immune_quota} inmunes en un panel de "
                f"{self.n_candidates}; se aborta."
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
                    f"La cuota por región repite alguna región ({regiones}); se aborta "
                    f"en vez de quedarse con una de las dos cifras."
                )
            if any(n < 0 for _, n in self.region_quota):
                raise ValueError(
                    f"La cuota por región {self.region_quota} tiene alguna cifra "
                    f"negativa; se aborta."
                )
            total = sum(n for _, n in self.region_quota)
            if total != self.n_candidates:
                raise ValueError(
                    f"La cuota por región suma {total} y se piden "
                    f"{self.n_candidates} candidatos. Se aborta en vez de decidir por "
                    f"nuestra cuenta que región se lleva la diferencia."
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
            raise KeyError(f"No hay ningún candidato elegido que empiece en {start}.")
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


def respects_spacing(a: int, b: int, *, spacing: int) -> bool:
    """El criterio del espaciado, en UN solo sitio.

    `spacing` es el minimo EXIGIDO entre dos posiciones de inicio, asi que exactamente
    esa distancia lo cumple. `spacing.same_site` es su negacion exacta y lo importa de
    aqui: tener las dos definiciones por separado ya hizo que un par a 50 nt fuera dos
    candidatos para la seleccion y el mismo sitio para el analisis de espaciado.
    """
    return abs(a - b) >= spacing


def _respects_spacing(candidate: Choice, chosen: list[Choice], min_spacing: int) -> bool:
    return all(
        respects_spacing(candidate.start, c.start, spacing=min_spacing) for c in chosen
    )


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
                f"tercio {tercio.value}: no hay ningún sitio elegible en ese tercio."
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
                "No habia ningún sitio elegible: la selección está vacía. Revisa "
                "cuántas ventanas superan los filtros antes de buscar el fallo en la "
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
                    f"esa región; los que faltan no cumplen el espaciado de "
                    f"{config.min_spacing} nt o no existen. No se rellena con "
                    f"candidatos de otra región."
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
            "No habia ningún sitio elegible: la selección está vacía. Revisa cuántas "
            "ventanas superan los filtros antes de buscar el fallo en la selección."
        )

    ordenados = [s for s in ordenados if s.best.region is Region.UTR3]

    # La cuota de INMUNES va primero: es la mas restrictiva —solo la cumple un tramo
    # concreto del 3'UTR— y dejarla para el final la haria imposible de llenar en
    # cuanto el espaciado se hubiera gastado en otra parte.
    if config.apa_immune_quota:
        if config.apa_immune_before is None:
            raise ValueError(
                f"Se piden {config.apa_immune_quota} candidatos inmunes pero no se dice "
                f"inmunes A QUE: `apa_immune_before` sigue en None y aquí ya no hay "
                f"informe del que sacarlo. Se aborta antes de elegir a ciegas."
            )
        inmunes = [
            s for s in ordenados
            if s.best.start <= config.apa_immune_before and id(s) not in usados
        ]
        puestos = 0
        for sitio in inmunes:
            if puestos >= config.apa_immune_quota:
                break
            if not _respects_spacing(sitio.best, chosen, config.min_spacing):
                continue
            chosen.append(sitio.best)
            usados.add(id(sitio))
            puestos += 1
        if puestos < config.apa_immune_quota:
            quota_unfilled.append(
                f"inmunes al corte: se pedian {config.apa_immune_quota} candidato(s) "
                f"que empezaran por delante de {config.apa_immune_before} y solo salen "
                f"{puestos}. Habia {len(inmunes)} sitio(s) elegible(s) en ese tramo; "
                f"los que faltan no cumplen el espaciado de {config.min_spacing} nt. "
                f"No se rellena con candidatos de más abajo: serían otro riesgo, no el "
                f"que la cuota compra."
            )

    for inicio, fin, plazas in config.start_window_quota or ():
        ya = sum(1 for c in chosen if inicio <= c.start <= fin)
        for _ in range(max(0, plazas - ya)):
            elegido = next(
                (
                    s for s in ordenados
                    if inicio <= s.best.start <= fin and id(s) not in usados
                    and _respects_spacing(s.best, chosen, config.min_spacing)
                ),
                None,
            )
            if elegido is None or len(chosen) >= config.n_candidates:
                quota_unfilled.append(
                    f"tramo de inicio {inicio}-{fin}: se pedian {plazas} candidato(s) y "
                    f"salen {sum(1 for c in chosen if inicio <= c.start <= fin)}. "
                    f"O no quedan plazas del panel, o los sitios que faltan no cumplen "
                    f"el espaciado de {config.min_spacing} nt."
                )
                break
            chosen.append(elegido.best)
            usados.add(id(elegido))

    if config.tercio_quota is not None:
        for tercio, plazas in config.tercio_quota:
            ya = sum(1 for c in chosen if c.tercio is tercio)
            for _ in range(max(0, plazas - ya)):
                if len(chosen) >= config.n_candidates:
                    quota_unfilled.append(
                        f"tercio {tercio.value}: no quedaban plazas "
                        f"({config.n_candidates} pedidas)."
                    )
                    break
                elegido = next(
                    (
                        s for s in ordenados
                        if s.best.tercio is tercio and id(s) not in usados
                        and _respects_spacing(s.best, chosen, config.min_spacing)
                    ),
                    None,
                )
                if elegido is None:
                    quota_unfilled.append(
                        f"tercio {tercio.value}: se pedian {plazas} y no hay más sitios "
                        f"elegibles que cumplan el espaciado de {config.min_spacing} nt."
                    )
                    break
                chosen.append(elegido.best)
                usados.add(id(elegido))
    elif config.require_one_per_tercio:
        if config.n_candidates < len(TERCIOS):
            notes.append(
                f"Se piden {config.n_candidates} candidatos y los tercios son "
                f"{len(TERCIOS)}: la cuota de uno por tercio no cabe entera."
            )
        for tercio in TERCIOS:
            ya = sum(1 for c in chosen if c.tercio is tercio)
            for _ in range(max(0, config.min_per_tercio - ya)):
                if len(chosen) >= config.n_candidates:
                    quota_unfilled.append(
                        f"tercio {tercio.value}: no quedaban plazas "
                        f"({config.n_candidates} pedidas)."
                    )
                    break
                del_tercio = [
                    s for s in ordenados
                    if s.best.tercio is tercio and id(s) not in usados
                ]
                if not del_tercio:
                    quota_unfilled.append(
                        f"tercio {tercio.value}: no hay ningún sitio elegible en ese "
                        f"tercio."
                    )
                    break
                elegido = next(
                    (
                        s for s in del_tercio
                        if _respects_spacing(s.best, chosen, config.min_spacing)
                    ),
                    None,
                )
                if elegido is None:
                    quota_unfilled.append(
                        f"tercio {tercio.value}: hay {len(del_tercio)} sitio(s) "
                        f"elegible(s), pero todos quedan a menos de "
                        f"{config.min_spacing} nt de un candidato ya elegido "
                        f"(espaciado)."
                    )
                    break
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
            f"no hay más sitios elegibles que respeten el espaciado de "
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
                f"asimetría: no se puede ordenar por un número que no existe. Se aborta "
                f"la selección en vez de inventar un orden."
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


def default_config(n_candidates: int = DEFAULT_CANDIDATES, **extra) -> SelectionConfig:
    """La configuracion DEL PROYECTO: panel de 10 y cuota de inmunes.

    Las dos cuotas no compiten, hacen cosas distintas y las dos hacen falta. Con solo la
    de tercios, `3utr:359` (+4,82) desplaza a `3utr:200` (+3,80) por asimetria y el panel
    se queda con TRES inmunes en vez de cuatro — sin que nada lo diga, porque los dos son
    del tercio proximal y la cuota de tercios se cumple igual.

    Y eso importa porque los inmunes son la UNICA reserva si el APA de `3utr:288` resulta
    funcional: los sitios elegibles por delante del corte estan **20/0/0** por tercio, asi
    que si se pierden no hay de donde rebalancear.

    La cuota se ACOTA al tamaño del panel: pedir cuatro inmunes en un panel de tres es
    imposible, y abortar por un defecto que el que llama no ha pedido seria peor que no
    tenerlo. Con un panel pequeño se pide lo que cabe y se sigue diciendo cuantos son.
    """
    return SelectionConfig(
        n_candidates=n_candidates,
        apa_immune_quota=min(DEFAULT_IMMUNE_QUOTA, n_candidates),
        **extra,
    )


def select_from_report(
    report: TilingReport,
    config: SelectionConfig | None = None,
) -> ReportSelection:
    """Pasos 3, 4 y 5 sobre un informe de tiling ya filtrado.

    NO inventa cuotas. La de inmunes se pide con `default_config()`, que es donde se
    empareja con su frontera: meterla aqui por defecto hacia abortar a cualquiera que
    pidiera un panel de tres —«se piden 4 inmunes en un panel de 3»—, y un valor por
    defecto implicito que revienta segun el tamaño del panel es una trampa, no un
    defecto.
    """
    config = config or SelectionConfig()
    if config.apa_immune_quota and config.apa_immune_before is None:
        # De donde sale la frontera: del informe, no de un numero tecleado. Un corte
        # escrito a mano no se entera de que un sitio de corte medido lo adelante.
        derivado = derive_immune_cut(report)
        if derivado is None:
            raise ValueError(
                f"Se piden {config.apa_immune_quota} candidatos inmunes al truncamiento "
                f"por APA, pero este informe no tiene ninguna señal APA_POSIBLE: no hay "
                f"corte al que ser inmune. Se aborta en vez de dar la cuota por "
                f"cumplida con cualquiera."
            )
        config = replace(config, apa_immune_before=derivado)
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
                "Ninguna ventana lleva bandera de poliadenilación debil: la "
                "penalizacion no afecta a nada en este 3'UTR."
            )
        if self.stable:
            return (
                f"Los seleccionados NO cambian entre {min(self.values)} y "
                f"{max(self.values)} kcal/mol: el valor exacto es irrelevante aquí."
            )
        return (
            f"Los seleccionados CAMBIAN dentro del rango {min(self.values)}–"
            f"{max(self.values)} kcal/mol: el valor no es inocuo, decidelo a propósito."
        )


def penalty_sensitivity(
    report: TilingReport,
    config: SelectionConfig | None = None,
    values: tuple[float, ...] = DEFAULT_PENALTY_SWEEP,
) -> PenaltySensitivity:
    """Repite la seleccion con varias penalizaciones y compara quien sale elegido."""
    if not values:
        raise ValueError(
            "No hay ningún valor de penalizacion que barrer; se aborta en vez de "
            "devolver un análisis vacío que parezca concluyente."
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
                "de polyA no decide nada aquí, así que el debate sobre el ±10 nt es "
                "irrelevante para esta selección."
            )
        else:
            lines.append(
                "  Los tres modos NO eligen lo mismo: aquí el criterio de polyA SI "
                "cambia quien entra, así que la elección de modo es una decisión de "
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
                f"{sangria}No se comprobo si la piscina de elegibles daba de si, así "
                f"que no se puede decir si es cosa de la selección o del 3'UTR."
            ]
        if estudiable:
            rango = datos.get("rango_piscina")
            detalle = (
                f" (la piscina va de {rango[0]:.2f} a {rango[1]:.2f})" if rango else ""
            )
            return [
                f"{sangria}Pero SI habia candidatos elegibles en los dos "
                f"extremos{detalle}: es la selección la que no los ha repartido. "
                f"Prueba --reparto-rango o más candidatos.",
            ]
        rango = datos.get("rango_piscina")
        minimo = MIN_SPAN.get(eje)
        if rango and minimo is not None:
            recorrido = rango[1] - rango[0]
            detalle = (
                f" — TODOS los elegibles caen entre {rango[0]:.2f} y {rango[1]:.2f}, "
                f"{recorrido:.2f} de recorrido, por debajo del mínimo de {minimo:.2f} "
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
            f"{sangria}Eso NO ES UN FALLO de la app ni de la selección: es INFORMACIÓN.",
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


# ─── Cuanto panel condiciona cada señal de APA ───────────────────────────────
#
# Una señal `APA_POSIBLE` no tumba nada: pone un TECHO a lo que quede por detras de su
# corte. La pregunta util no es «¿hay APA?» sino QUE FRACCION DEL PANEL POSIBLE queda
# condicionada por cada una — y se cuenta sobre las ventanas ELEGIBLES, no sobre las
# 1585 del tilado, porque las que no pasan los filtros no eran candidatos de todas
# formas.


def derive_immune_cut(report: TilingReport) -> int | None:
    """El corte MAS TEMPRANO de las señales `APA_POSIBLE`, en el marco de lo tilado.

    Es la frontera de la inmunidad bajo el criterio ESTRICTO —el unico que vale: por
    delante de aqui la ventana se conserva en las dos isoformas; por delante del corte
    mas TARDIO entrarian ventanas de dentro de la banda de 20 nt, que `polya_risk`
    clasifica `PENALIZADO` y llamarlas inmunes seria inventarse precision.

    Existe para que ese numero no se teclee. Estaba puesto a mano (`--inmunes-antes
    1252`) y cuando un tercer sitio de corte medido adelanto la frontera de 3utr:303 a
    3utr:251, la cifra tecleada siguio ahi sin dar ningun error.
    """
    from .polya import CLEAVAGE_MIN, SignalClass

    posibles = [
        s for s in report.signals if s.classification is SignalClass.APA_POSSIBLE
    ]
    if not posibles:
        return None
    return min(s.end for s in posibles) + CLEAVAGE_MIN


# ─── Lo que CUESTA promover una señal por medida ─────────────────────────────
#
# Subir un hexamero a APA_POSIBLE no es solo poner un techo: `is_hard_block` se vuelve
# cierto, y bajo el criterio escalonado toda ventana que lo SOLAPE pasa a FAIL. Eso
# tumba candidatos.
#
# En el raton tumba `3utr:221`, que era uno de los cuatro inmunes del panel. Y el modo
# en que lo tumba importa: `3utr:221` NO pierde su inmunidad al truncamiento —empieza en
# 221 y el corte mas temprano cae en 251, asi que se conserva en las dos isoformas—, la
# pierde por el OTRO riesgo, el ESTERICO: su ventana contiene el hexamero y compite con
# CPSF/CstF por un sitio del que ahora se sabe que SE USA. Son dos ejes distintos y el
# informe no los mezcla.
#
# Sin esta cuenta, la unica huella de la decision seria que la piscina de elegibles es
# mas pequeña, que es exactamente la forma que tiene un candidato de desaparecer sin que
# nadie lo vea.


@dataclass(frozen=True)
class PromotionCost:
    windows: tuple = ()
    signals: tuple = ()
    frame: object = None

    @property
    def window_starts(self) -> tuple[int, ...]:
        return tuple(w.window.start for w in self.windows)

    def describe(self) -> str:
        from .coords import Frame, label

        if not self.windows:
            return ""
        marco = self.frame or Frame.UTR3
        cuales = ", ".join(
            f"{s.motif} en {label(s.position, marco)}" for s in self.signals
        )
        # Solo las que TIENEN coordenada de 3'UTR. `None` es «no cae en el 3'UTR», y
        # sustituirla por la de lo tilado la etiquetaria `3utr:` siendo del transcrito.
        # Las que no la tienen se cuentan aparte en vez de desaparecer. Errata nº 18.
        en_utr3 = [w for w in self.windows if w.inicio_3utr is not None]
        fuera = len(self.windows) - len(en_utr3)
        posiciones = ", ".join(
            label(w.inicio_3utr, Frame.UTR3) for w in en_utr3
        ) + (f" (y {fuera} fuera del 3'UTR)" if fuera else "")
        return (
            f"LO QUE CUESTA LA PROMOCION: {len(self.windows)} ventana(s) que superaban "
            f"todos los demas filtros pasan a FAIL por SOLAPAR una señal que la medida "
            f"acaba de subir a APA_POSIBLE ({cuales}). En 3'UTR: {posiciones}. "
            f"OJO CON EL EJE: esas ventanas NO pierden su inmunidad al TRUNCAMIENTO "
            f"—empiezan por delante del corte, así que su diana se conserva en las dos "
            f"isoformas—, la pierden por el riesgo ESTERICO, que es el otro: la ventana "
            f"contiene el hexámero y compite con CPSF/CstF por un sitio del que ahora se "
            f"sabe que SE USA. Mientras la señal era una variante rara sin datos, el "
            f"solape valia una penalizacion de ranking; con uso medido, no. Es una "
            f"decisión, y esta es su factura."
        )


def measured_promotion_cost(report: TilingReport) -> PromotionCost:
    """Las ventanas que tumba la promocion por medida, y solo esas.

    Solo cuentan las que fallan UNICAMENTE el filtro de polyA: una ventana que ya fallaba
    GC no la tumba la promocion, y contarla inflaria la factura.
    """
    from .coords import Frame, frame_of
    from .polya import SignalClass

    # Solo las que la medida SUBIO. Una señal canonica ya era APA_POSIBLE por la
    # cascada de prediccion, asi que las ventanas que la solapan ya fallaban: la medida
    # solo le cambia la evidencia. Cobrarle esas ventanas a la promocion seria pasar una
    # factura por algo que ya estaba pagado.
    from .polya import classify_signal

    promovidas = tuple(
        s for s in report.signals
        if s.evidence == "medida"
        and s.classification is SignalClass.APA_POSSIBLE
        and classify_signal(
            s.motif, s.position, s.utr_length, flank=s.flank
        ).classification is not SignalClass.APA_POSSIBLE
    )
    if not promovidas:
        return PromotionCost()

    marco = frame_of(report.anatomy) if report.anatomy is not None else Frame.UTR3
    caidas = []
    for ventana in report.windows:
        fallos = [f for f in ventana.filters if f.state is FilterState.FAIL]
        if len(fallos) != 1 or fallos[0].name != "zona_prohibida_polyA":
            continue
        if not any(
            s.motif in fallos[0].reason and str(s.position) in fallos[0].reason
            for s in promovidas
        ):
            continue
        caidas.append(ventana)
    return PromotionCost(
        windows=tuple(caidas), signals=promovidas, frame=marco
    )


# ─── Lo que SE SALVA, y por cuanto ───────────────────────────────────────────
#
# `measured_promotion_cost` dice a quien tumba la promocion. Falta lo otro: quien pasa
# CERCA y sobrevive. `3utr:200` ocupa la plaza que perdio `3utr:221` y su ventana
# 200-221 no contiene el hexamero — pero para saberlo hay que hacer una resta, y el
# lector no tiene por que hacerla. El veredicto se emite, con la holgura y con el flanco
# al que cambiaria: sin la sensibilidad, un «PASA» parece mas solido de lo que es.

#: Hasta que distancia de la zona prohibida se considera que un candidato pasa CERCA.
#: Mas alla es ruido: `3utr:1018` no tiene nada que ver con una señal de `3utr:236`.
CLEARANCE_WINDOW = 30


@dataclass(frozen=True)
class ClearanceRow:
    """Todas las coordenadas van YA en el 3'UTR, convertidas una vez y no aqui.

    Guardar la señal entera y etiquetar `Frame.UTR3` su `position` es lo que produjo
    `3utr:1185` sobre un 3'UTR de 1242 nt en la primera version de este bloque: la
    ventana venia convertida y la señal no. El techo global de `coords` no lo caza
    —1185 cabe en el 3'UTR humano— y por eso la fila lleva `utr3_length` y se comprueba
    contra ella.
    """

    start: int
    end: int
    motif: str
    signal_start: int
    flank: int
    forbidden: tuple[int, int]
    clearance: int
    distance_to_hexamer: int
    flip_flank: int | None
    utr3_length: int | None = None
    #: El corte MAS TEMPRANO de las señales medidas, en el marco del 3'UTR. Es lo que
    #: decide el eje geometrico, y va guardado para no recalcularlo al imprimir.
    earliest_cut: int | None = None

    @property
    def passes(self) -> bool:
        return self.clearance > 0

    @property
    def immune_truncation(self) -> bool:
        """Eje GEOMETRICO: por delante del corte mas temprano, la diana se conserva.

        No depende de ninguna convencion — ni del flanco, ni de un umbral. O empiezas
        antes del corte o no.
        """
        return self.earliest_cut is not None and self.start <= self.earliest_cut

    @property
    def steric(self) -> str:
        """Eje ESTERICO: nunca `INMUNE`. Es un gradiente y el umbral es convencional."""
        return "PASS" if self.clearance > self.flank else "PENALIZADO"

    @property
    def signal(self):
        """Compatibilidad: `fila.signal.position` sigue funcionando en el 3'UTR."""
        from types import SimpleNamespace

        return SimpleNamespace(
            motif=self.motif, position=self.signal_start, flank=self.flank,
            forbidden_start=self.forbidden[0], forbidden_end=self.forbidden[1],
        )

    def describe(self) -> str:
        from .coords import Frame, label, span

        tope = self.utr3_length
        cambio = (
            f"con un flanco de {self.flip_flank} en vez de {self.flank} también caeria"
            if self.flip_flank is not None
            else "ningún flanco razonable lo tumbaria"
        )
        # Los DOS ejes, siempre, y nunca «inmune» a secas: uno es geometrico y el otro
        # es un gradiente con un umbral convencional. Colapsarlos en una palabra es
        # exactamente lo que hace que un PASS parezca una medida.
        return (
            f"{label(self.start, Frame.UTR3, limit=tope)} "
            f"({span(self.start, self.end, Frame.UTR3, limit=tope)}): "
            f"inmune_truncamiento = "
            + ("SI" if self.immune_truncation else "NO")
            + (
                f" (empieza en {self.start}, el corte más temprano está en "
                f"{self.earliest_cut}; es GEOMÉTRICO y no depende de ninguna convención)"
                if self.earliest_cut is not None
                else " (sin corte medido con el que compararlo)"
            )
            + f" | esterico = {self.steric}. No contiene el {self.motif} de "
            f"{label(self.signal_start, Frame.UTR3, limit=tope)} —acaba "
            f"{self.distance_to_hexamer} nt antes— y queda {self.clearance} nt por "
            f"delante de su zona prohibida "
            f"({span(*self.forbidden, Frame.UTR3, limit=tope)}); {cambio}. "
            f"OJO: el flanco de ±{self.flank} nt no tiene base medida y la huella real "
            f"de CPSF/CstF es mayor, así que estos {self.distance_to_hexamer} nt están "
            f"probablemente DENTRO de la zona de competencia."
        )


@dataclass(frozen=True)
class Clearance:
    rows: tuple[ClearanceRow, ...] = ()

    def describe(self) -> str:
        from .polya import STERIC_IS_A_GRADIENT

        if not self.rows:
            return ""
        return (
            "LO QUE SE SALVA, Y POR CUANTO. Son los candidatos elegidos que pasan a "
            "menos de "
            f"{CLEARANCE_WINDOW} nt de una señal que la medida acaba de subir a "
            "APA_POSIBLE. Se declara el veredicto en vez de "
            "dejarlo deducir de una resta, y en LOS DOS EJES: "
            + " ".join(f.describe() for f in self.rows)
            + " "
            + STERIC_IS_A_GRADIENT
        )


def promotion_clearance(
    report: TilingReport, selection: ReportSelection, *, window: int = CLEARANCE_WINDOW
) -> Clearance:
    """Los elegidos que sobreviven CERCA de una señal promovida por medida."""
    from .coords import bound_of
    from .polya import STERIC_IS_A_GRADIENT, SignalClass, classify_signal

    promovidas = [
        s for s in report.signals
        if s.evidence == "medida"
        and s.classification is SignalClass.APA_POSSIBLE
        and classify_signal(
            s.motif, s.position, s.utr_length, flank=s.flank
        ).classification is not SignalClass.APA_POSSIBLE
    ]
    if not promovidas or not selection.selection.chosen:
        return Clearance()

    desfase = 0
    if report.anatomy is not None and report.anatomy.utr3:
        desfase = report.anatomy.utr3[0] - 1

    filas: list[ClearanceRow] = []
    for eleccion in selection.selection.chosen:
        ventana = selection.window_of(eleccion)
        inicio, fin = ventana.window.start, ventana.window.end
        for señal in promovidas:
            holgura = señal.forbidden_start - fin - 1
            if not 0 < holgura <= window:
                continue
            # A partir de que flanco la zona prohibida alcanzaria a esta ventana. Se
            # BUSCA, no se calcula a mano: es el mismo `classify_signal` que decide.
            salto = None
            for flanco in range(señal.flank, señal.flank + window + 1):
                otra = classify_signal(
                    señal.motif, señal.position, señal.utr_length, flank=flanco
                )
                if inicio <= otra.forbidden_end and fin >= otra.forbidden_start:
                    salto = flanco
                    break
            filas.append(
                ClearanceRow(
                    start=inicio - desfase,
                    end=fin - desfase,
                    motif=señal.motif,
                    signal_start=señal.position - desfase,
                    flank=señal.flank,
                    forbidden=(
                        señal.forbidden_start - desfase, señal.forbidden_end - desfase
                    ),
                    clearance=holgura,
                    distance_to_hexamer=señal.position - fin - 1,
                    flip_flank=salto,
                    utr3_length=bound_of(report.anatomy),
                    earliest_cut=(
                        min(s2.end + CLEAVAGE_MIN for s2 in promovidas) - desfase
                    ),
                )
            )
    filas.sort(key=lambda f: f.start)
    return Clearance(rows=tuple(filas))


@dataclass(frozen=True)
class ApaCeilingRow:
    signal: "PolyASignal"
    eligible_total: int
    behind: int
    in_band: int
    ahead: int
    #: El techo del tramo que hay JUSTO detras de esta señal, cuando esta medido.
    #: `None` = sin medir, y entonces se dice «indeterminado», no un numero.
    ceiling: float | None = None
    #: El espacio de `signal.position`: el de LO TILADO. Con un mRNA completo NO es el
    #: del 3'UTR, y etiquetarlo `3utr:` da un numero que no existe en ese espacio.
    frame: object = None

    @property
    def fraction(self) -> float:
        return self.behind / self.eligible_total if self.eligible_total else 0.0

    def describe(self) -> str:
        from .coords import Frame, label, span

        from .polya import SignalClass, classify_signal

        marco = self.frame or Frame.UTR3
        # TRES casos, no dos. Una canonica MEDIDA no es lo mismo que una variante rara
        # que solo esta aqui por la medida: la primera ya estaba, la segunda entro. Y
        # ninguna de las dos es una canonica sin ningun dato de uso, que es un SUPUESTO.
        predicha = classify_signal(
            self.signal.motif, self.signal.position, self.signal.utr_length,
            flank=self.signal.flank,
        ).classification is SignalClass.APA_POSSIBLE
        if self.signal.evidence == "medida":
            via = (
                "por canonicidad, CONFIRMADA por medida de uso"
                if predicha
                else "SUBIDA aquí por MEDIDA de uso: por predicción saldria OTRA"
            )
        else:
            via = "por CANONICIDAD, sin dato de uso"
        techo = (
            f"Techo INDETERMINADO en las tres: fraccion_isoforma_larga sin medir."
            if self.ceiling is None
            else f"Techo del tramo de detrás: {self.ceiling:.2f}."
        )
        return (
            # La etiqueta lleva la PROCEDENCIA pegada: `APA_POSIBLE (medido, PolyA_DB
            # v4.1)` frente a `APA_POSIBLE (canónico, asumido)`. Sin ella las dos se
            # llaman igual, y `via` —que ya distinguia— queda cinco palabras mas alla,
            # donde no la lee quien copia la linea a un correo.
            f"{self.signal.classification_label}: "
            f"{self.signal.motif} en {label(self.signal.position, marco)} "
            f"({via}) "
            f"(corte {span(self.signal.end + CLEAVAGE_MIN, self.signal.end + CLEAVAGE_MAX, marco)}): "
            f"TECHO sobre {self.behind} de {self.eligible_total} ventanas elegibles "
            f"({self.fraction:.1%}); {self.in_band} en la banda de corte "
            f"(PENALIZADO, no se sabe de que lado caen); {self.ahead} por delante, "
            f"inmunes. {techo}"
        )


def apa_ceiling_table(
    report: TilingReport, config: SelectionConfig | None = None
) -> list[ApaCeilingRow]:
    """Una fila por señal `APA_POSIBLE`, con cuanto panel condiciona.

    Las coordenadas de las señales van en el marco de LO TILADO, igual que las ventanas,
    asi que la cuenta es directa y no hay conversion que equivocar.
    """
    from .polya import SignalClass

    from .coords import Frame, frame_of

    elegibles = [w.window.start for w in report.windows if is_eligible(w, config)]
    medido = getattr(report, "measured_apa", None)
    marco = frame_of(report.anatomy) if report.anatomy is not None else Frame.UTR3
    filas: list[ApaCeilingRow] = []
    for señal in report.signals:
        if señal.classification is not SignalClass.APA_POSSIBLE:
            continue
        pronto, tarde = señal.end + CLEAVAGE_MIN, señal.end + CLEAVAGE_MAX
        techo = None
        if medido is not None and tarde < report.utr_length:
            techo = medido.layer_for(tarde + 1).ceiling
        filas.append(
            ApaCeilingRow(
                signal=señal,
                eligible_total=len(elegibles),
                behind=sum(1 for p in elegibles if p > tarde),
                in_band=sum(1 for p in elegibles if pronto < p <= tarde),
                ahead=sum(1 for p in elegibles if p <= pronto),
                ceiling=techo,
                frame=marco,
            )
        )
    return filas


# ─── Los tercios: dos definiciones, y hay que decir cual ─────────────────────
#
# `Tercio` etiqueta por el PUNTO MEDIO de la ventana. La particion simple del 3'UTR va
# por la POSICION DE INICIO. Con ventanas de 22 nt las dos discrepan en el borde: en el
# raton, 3utr:819-840 empieza en el segundo tercio (819 <= 828) y su punto medio (829,5)
# cae en el tercero. Ninguna es incorrecta; lo que no vale es no decir cual se usa.


@dataclass(frozen=True)
class TercioCounts:
    utr_length: int
    bounds: tuple[tuple[int, int], ...]
    by_midpoint: dict[str, int]
    by_start: dict[str, int]
    sites_by_start: dict[str, int]
    #: Sitios elegibles por tramo que quedan POR DELANTE del corte mas temprano de la
    #: señal proximal — los unicos hacia los que se puede rebalancear el panel si el
    #: APA resulta funcional.
    sites_immune: dict[str, int] = field(default_factory=dict)
    immune_cut: int | None = None

    def describe(self) -> list[str]:
        from .coords import Frame, span

        lineas = [
            "Tercios del 3'UTR: "
            + ", ".join(span(a, b, Frame.UTR3) for a, b in self.bounds)
            + ".",
            "  La columna `tercio` etiqueta por el PUNTO MEDIO de la ventana; la "
            "particion de arriba va",
            "  por POSICIÓN DE INICIO. Con ventanas de 22 nt discrepan en el borde, así "
            "que se dan las dos.",
        ]
        for titulo, cuenta in (
            ("ventanas elegibles, por punto medio (así se etiqueta)", self.by_midpoint),
            ("ventanas elegibles, por inicio", self.by_start),
            ("SITIOS elegibles, por inicio", self.sites_by_start),
        ):
            lineas.append(
                f"  {titulo}: "
                + ", ".join(f"{k} {v}" for k, v in cuenta.items())
            )
        if self.immune_cut is not None:
            lineas.append(
                f"  SITIOS INMUNES por tramo (empiezan por delante de "
                f"{label(self.immune_cut, Frame.UTR3)}, el corte más temprano de la "
                f"señal proximal):"
            )
            lineas.append(
                "    "
                + ", ".join(f"{k} {v}" for k, v in self.sites_immune.items())
            )
            lineas.append(
                "    Es hacia donde se puede REBALANCEAR el panel si el APA resulta "
                "funcional. Un tramo con"
            )
            lineas.append(
                "    cero no admite rebalanceo: ahi no hay nada que no lleve techo."
            )
        return lineas


def tercio_counts(
    report: TilingReport, config: SelectionConfig | None = None
) -> TercioCounts:
    """Cuantos elegibles hay por tercio, con las dos definiciones y los sitios."""
    # Los tercios se cuentan SOBRE EL 3'UTR, no sobre lo tilado. Con un mRNA completo
    # `report.utr_length` es la longitud tilada (2191 en el raton) y los limites salian
    # del transcrito: el reparto decia «medio 20» de unos sitios que estan todos en el
    # tercio PROXIMAL del 3'UTR. Las posiciones se convierten antes de contar.
    anatomia = report.anatomy
    desfase = anatomia.utr3[0] - 1 if anatomia is not None and anatomia.utr3 else 0
    largo = (
        anatomia.utr3_length
        if anatomia is not None and anatomia.utr3
        else report.utr_length
    )
    limites = (
        (1, largo // 3),
        (largo // 3 + 1, 2 * largo // 3),
        (2 * largo // 3 + 1, largo),
    )
    nombres = ("proximal", "medio", "distal")

    def por_inicio(posicion: int) -> str:
        for nombre, (a, b) in zip(nombres, limites):
            if a <= posicion <= b:
                return nombre
        return nombres[-1]

    elegibles = [w for w in report.windows if is_eligible(w, config)]
    sitios = [s.best.start for s in group_choices(eligible_choices(report, config))]
    medio: dict[str, int] = {n: 0 for n in nombres}
    inicio: dict[str, int] = {n: 0 for n in nombres}
    for ventana in elegibles:
        if ventana.tercio is not None:
            medio[ventana.tercio.value] += 1
        inicio[por_inicio(ventana.window.start - desfase)] += 1
    inmunes: dict[str, int] = {n: 0 for n in nombres}
    corte = derive_immune_cut(report)
    if corte is not None:
        for posicion in sitios:
            if posicion <= corte:
                inmunes[por_inicio(posicion - desfase)] += 1
        corte -= desfase

    return TercioCounts(
        utr_length=largo,
        bounds=limites,
        by_midpoint=medio,
        by_start=inicio,
        sites_by_start={
            n: sum(1 for p in sitios if por_inicio(p - desfase) == n) for n in nombres
        },
        sites_immune=inmunes,
        immune_cut=corte,
    )


# ─── Los frentes que bloquean el pedido de oligo ─────────────────────────────
#
# No son «los filtros en NOT_RUN». Hay uno mas que no es un filtro de ventana y bloquea
# igual: la fraccion de isoforma larga. DECIDIDO el 2026-08-26 con la cuenta delante —
# sitios inmunes por tramo 20/0/0 y tope de cuatro por espaciado—, porque con un panel
# de diez eso deja SEIS candidatos compartiendo un unico modo de fallo.
#
# Y la razon por la que bloquea no es que sea importante: es que un techo alto y un
# shmiR que no funciona dan LA MISMA LECTURA en la placa. Cribar sin medirlo gasta el
# experimento en no poder distinguirlos.


def _estado_medida(measured=None) -> str:
    """Que se sabe hoy de la fraccion, y por que sigue (o no) bloqueando."""
    from .apa import POLYA_DB_PRNP

    if measured is None:
        return (
            f"HAY UNA MEDIDA —{POLYA_DB_PRNP.source} {POLYA_DB_PRNP.version}, fracción "
            f"larga {POLYA_DB_PRNP.working_value:.2f} ponderada / "
            f"{POLYA_DB_PRNP.unweighted_value:.2f} sin ponderar— PERO NO ENTRA EN ESTA "
            f"CORRIDA: la tabla es de Prnp murino y se aplica por md5 del 3'UTR, así que "
            f"sobre otra secuencia no se ancla nada. Aquí el techo sigue INDETERMINADO y "
            f"este frente sigue bloqueando."
        )
    tramos = [c for c in measured.layers if c.ceiling is not None]
    cifras = ", ".join(f"{c.ceiling:.2f}" for c in tramos)
    return (
        f"MEDIDO. {measured.source}, fracción larga "
        f"{POLYA_DB_PRNP.working_value:.2f} ponderada / "
        f"{POLYA_DB_PRNP.unweighted_value:.2f} sin ponderar. El mapeo "
        f"genomico↔transcrito que bloqueaba está RESUELTO sin coordenadas genomicas y "
        f"sobre {measured.anchor.total} puntos de apoyo, no sobre una resta. Y el techo "
        f"no es uno: va POR TRAMOS ({cifras}), porque depende de por detrás de cuántos "
        f"cortes está cada candidato. Con eso deja de cumplirse lo que hacia bloquear a "
        f"este frente: un techo de {min(c.ceiling for c in tramos):.2f} NO es "
        f"indistinguible de un shmiR malo en la placa. RESERVA QUE SE MANTIENE: el dato "
        f"es de {POLYA_DB_PRNP.tissue}, y las neuronas alargan los 3'UTR, así que estas "
        f"cifras son un LÍMITE INFERIOR conservador para el nuestro. La RT-qPCR de los "
        f"dos amplicones sigue en pie y puede MEJORARLAS."
    )


@dataclass(frozen=True)
class BlockingFront:
    name: str
    reason: str
    #: Un frente CERRADO no desaparece de la lista: quien lea el informe tiene que
    #: ver que existio y por que se cerro. Lo que cambia es que no cuenta para el
    #: «no se pide oligo hasta que los N tengan veredicto».
    blocking: bool = True


def blocking_fronts(
    report: TilingReport, selection: ReportSelection
) -> list[BlockingFront]:
    """Los frentes abiertos: los filtros que no han corrido POR FALTA DE RECURSO.

    NO todo `NOT_RUN` es un frente, y confundirlos costo un aborto en la segunda corrida
    real de la pagina. Con la mascara puesta, 66 ventanas quedan con `N` y sus filtros de
    secuencia salen `NOT_RUN` — correcto, regla 3: una ventana con `N` no es evaluable.
    Pero eso no abre ningun frente: `GC` no se cierra con ningun fichero, asi que
    ponerlo en la lista de frentes hacia que la app pidiera su **ficha de obtencion** y
    abortara al no encontrarla.

    Y el motivo era peor que el aborto: decia **«falta el recurso»** de un filtro que no
    tiene recurso ninguno. Es la tercera vez que un mensaje de esta app explica una causa
    que nadie ha comprobado —despues del «comprueba que Streamlit esta instalado» y del
    «Alu 0 %» obtenido sin buscar Alu—, y por eso hay un principio escrito sobre ello.

    Un frente es un filtro que **se cierra consiguiendo algo**: un fichero, o una lectura
    de banco. Lo demas se cuenta en el semaforo, con las ventanas tiladas.
    """
    from .coords import Frame, frame_of, label
    from .filters import BIOPHYSICAL_FILTERS
    from .polya import CLEAVAGE_MIN, SignalClass

    # Lo que NO abre frente, y por que cada uno:
    #   - los BIOFISICOS: no dependen de ningun recurso. Si salen NOT_RUN es porque la
    #     ventana tiene `N`, y eso es una propiedad de la ventana, no un frente;
    #   - los que estan PENDIENTES DE DECISION (`G4_*`): tampoco se cierran con un
    #     fichero. Lo que les falta es que alguien decida su criterio, y eso no tiene
    #     ficha de obtencion — tiene una entrada en `justificacion.py`.
    sin_frente = BIOPHYSICAL_FILTERS
    frentes = [
        BlockingFront(
            name=nombre,
            reason=(
                f"NOT_RUN en {cuenta} de {selection.total} ventanas: falta el recurso. "
                f"NOT_RUN no es PASS."
                + (
                    " Y OJO: este frente NO cubre los off-targets mediados por seed. "
                    "Eso es `offtarget_seed`, un frente APARTE, porque 7 nt contiguos no "
                    "dan alineamiento y ningún BLAST los devuelve."
                    if nombre == "especificidad"
                    else ""
                )
            ),
        )
        for nombre, cuenta in selection.not_run_filters.items()
        if nombre not in sin_frente
    ]

    # El off-target por SEED es un frente PROPIO, no una parte de `especificidad`.
    # `carga_seed` es un numero comparativo y por eso nunca estuvo en `not_run_filters`,
    # asi que este frente era INVISIBLE: se contaba «especificidad» y parecia que la
    # pregunta estaba cubierta. No lo esta — ningun alineador la contesta.
    from .seed_load import FRONT_NAME as _SEED_FRONT, WHY_NOT_BLAST

    carga = getattr(report, "utr3_set", None)
    if carga is None:
        frentes.append(
            BlockingFront(
                name=_SEED_FRONT,
                reason=(
                    f"NOT_RUN: falta `transcriptoma_3utr.fa`, así que los sitios de seed "
                    f"no se han contado. NOT_RUN no es PASS. {WHY_NOT_BLAST}"
                ),
            )
        )

    # El QUINTO frente, y va SIEMPRE: no depende de ningun fichero ni de ningun
    # candidato. Es un riesgo de la ARQUITECTURA —si el intron no se escinde no hay
    # proteina DN en absoluto— y aparecer solo cuando alguien pasa --transgen lo
    # convertiria en un detalle de la linea de ordenes.
    from .splicing import plan_from_records, splicing_front

    plan, _ = plan_from_records(
        report.transgene_db.records if report.transgene_db is not None else None
    )
    empalme = splicing_front(plan)
    frentes.append(
        BlockingFront(name=empalme.name, reason=empalme.reason, blocking=True)
    )

    # El CUARTO modal. Va SIEMPRE y no depende de ningun fichero de referencia: su
    # unidad es el par candidato x intron, asi que existe en cuanto hay candidatos. Sin
    # corrida sale NOT_RUN, que es lo que es — no haber consultado no es salir limpio.
    from .splice_store import FILTER_NAME as _EMPALME_SITIOS

    frentes.append(
        BlockingFront(
            name=_EMPALME_SITIOS,
            reason=(
                "NOT_RUN: no se ha consultado la predicción de sitios de splicing sobre "
                "ningún cassette montado. La unidad de este frente es el PAR candidato x "
                "intrón, no el candidato. Es DESEMPATE Y ALERTA, nunca filtro: no puede "
                "excluir a nadie, y por eso su veredicto solo puede ser NOT_RUN o PASS. "
                "Lo accionable es que guías introducen crípticos que las otras no."
            ),
        )
    )

    apa = [s for s in report.signals if s.classification is SignalClass.APA_POSSIBLE]
    if not apa or not selection.selection.chosen:
        return frentes
    corte = min(s.end for s in apa) + CLEAVAGE_MIN
    con_techo = [c for c in selection.selection.chosen if c.start > corte]
    if not con_techo:
        return frentes

    cuenta = tercio_counts(report)
    tramos = ("proximal", "medio", "distal")
    reparto = "/".join(str(cuenta.sites_immune[n]) for n in tramos)
    con_inmunes = [n for n in tramos if cuenta.sites_immune[n]]
    donde = (
        f"todos en el {con_inmunes[0]}"
        if len(con_inmunes) == 1
        else f"repartidos entre {', '.join(con_inmunes)}"
        if con_inmunes
        else "ninguno en ningún tramo"
    )
    marco = frame_of(report.anatomy) if report.anatomy is not None else Frame.UTR3
    inmunes = len(selection.selection.chosen) - len(con_techo)
    medido = getattr(report, "measured_apa", None)
    frentes.append(
        BlockingFront(
            name="fraccion_isoforma_larga",
            blocking=medido is None,
            reason=(
                (
                    "CERRADO. " if medido is not None else "NO MEDIDA, y bloquea. "
                )
                + f"{len(con_techo)} de "
                f"{len(selection.selection.chosen)} candidatos quedan por detrás del "
                f"corte de {label(min(s.position for s in apa), marco)}: comparten "
                f"UN ÚNICO MODO DE FALLO. Y el rebalanceo tiene tope: los sitios inmunes "
                f"por tramo son {reparto} —{donde}— y el espaciado deja "
                f"meter cuatro, que son los {inmunes} que ya están. "
                f"POR QUE BLOQUEABA: si la fracción de isoforma corta es alta, esos "
                f"{len(con_techo)} candidatos entran al cribado con un TECHO "
                f"INDISTINGUIBLE DE UN shmiR MALO — un techo de 0,3 y una guía que no "
                f"funciona dan la misma lectura en la placa, y el experimento se gasta "
                f"en no poder separarlos. "
                f"ESTADO: {_estado_medida(medido)}"
            ),
        )
    )
    return frentes
