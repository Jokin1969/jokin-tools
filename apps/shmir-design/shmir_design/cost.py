"""Estimacion del coste de una corrida, ANTES de lanzarla.

Con `--accesibilidad` y `--transcriptoma-3utr` a la vez, el 3'UTR murino son unas 300
ventanas elegibles por dos plegados de 340 nt mas un barrido del transcriptoma cada una.
Eso son minutos, y sin esto no hay forma de saberlo hasta que ya esta corriendo — que es
cuando aparece la duda de si se ha colgado.

**No adivina.** Mide UNA invocacion real de cada filtro caro sobre una ventana de verdad
y multiplica por cuantas van a pasar por el. Si alguien optimiza un filtro, o si la
maquina es otra, la estimacion se ajusta sola. Un numero cableado envejeceria mintiendo.

Lo que NO estima: el tiempo de cargar las bases de datos, porque para medirlo habria que
cargarlas — y entonces ya no seria una estimacion previa. Cuando la base ya esta cargada
(el CLI la carga antes de estimar), su coste de carga ya se ha pagado y se dice.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .anatomy import Anatomy, TileRange
from .hard_filters import DEFAULT_THRESHOLDS, Thresholds
from .tiling import tile_utr


@dataclass(frozen=True)
class CostItem:
    """Una partida del presupuesto: un filtro caro y lo que va a costar."""

    name: str
    per_window: float
    windows: int
    note: str = ""

    @property
    def total_seconds(self) -> float:
        return self.per_window * self.windows


@dataclass(frozen=True)
class CostEstimate:
    windows: int
    eligible: int
    tiling_seconds: float
    items: tuple[CostItem, ...] = ()

    @property
    def total_seconds(self) -> float:
        return self.tiling_seconds + sum(i.total_seconds for i in self.items)

    def format_text(self) -> str:
        lineas = [
            "── Estimación de coste (no se ha diseñado nada) ──",
            f"  ventanas a tilar:        {self.windows}",
            f"  ventanas elegibles:      {self.eligible}  "
            f"(son las que pasan por los filtros caros)",
            "",
        ]
        if not self.eligible:
            lineas.append(
                "  No hay ninguna ventana elegible con estos umbrales, así que ningún "
                "filtro caro"
            )
            lineas.append(
                "  llegaria a correr. Antes de esperar nada, revisa los umbrales."
            )
            lineas.append("")

        lineas.append(f"  {'partida':<22} {'por ventana':>12} {'ventanas':>9} {'total':>10}")
        lineas.append(f"  {'tilado y filtros duros':<22} {'':>12} {'':>9} "
                      f"{_dur(self.tiling_seconds):>10}")
        for item in self.items:
            lineas.append(
                f"  {item.name:<22} {item.per_window * 1000:>9.1f} ms "
                f"{item.windows:>9} {_dur(item.total_seconds):>10}"
            )
        lineas.append(f"  {'':<22} {'':>12} {'TOTAL':>9} {_dur(self.total_seconds):>10}")
        lineas.append("")
        lineas.append(
            "  Es una estimación: el coste por ventana está MEDIDO sobre una invocación "
            "real de cada"
        )
        lineas.append(
            f"  filtro sobre {SAMPLES} ventanas repartidas por el tramo en esta "
            f"máquina, no cableado. No incluye"
        )
        lineas.append(
            "  cargar las bases de datos, que ya se ha pagado antes de llegar aquí."
        )
        lineas.append(
            "  Sirve para distinguir segundos de minutos, no para cronometrar: en la "
            "comprobacion"
        )
        lineas.append(
            "  hecha sobre una sonda de 660 nt se quedo un ~20% por encima del tiempo "
            "real."
        )
        return "\n".join(lineas)


def _dur(segundos: float) -> str:
    if segundos < 1:
        return f"{segundos * 1000:.0f} ms"
    if segundos < 90:
        return f"{segundos:.1f} s"
    return f"{segundos / 60:.1f} min"


#: Cuantas ventanas se cronometran por filtro. Pocas a proposito: la estimacion tiene
#: que ser barata o no sirve para decidir si merece la pena correr.
SAMPLES = 3


def _sample_windows(elegibles: list, cuantas: int = SAMPLES) -> list:
    """Ventanas REPARTIDAS por el tramo, no las primeras.

    Importa mas de lo que parece. La primera version media sobre `elegibles[0]`, la
    ventana mas a la izquierda — y ahi el contexto de la accesibilidad (±150 nt) esta
    recortado contra el extremo, asi que el plegado sale barato. La estimacion salia a
    la MITAD del coste real. Se muestrea a lo largo del tramo para que el coste medido
    incluya las ventanas caras del centro.
    """
    if not elegibles:
        return []
    cuantas = min(cuantas, len(elegibles))
    if cuantas == 1:
        return [elegibles[len(elegibles) // 2]]
    paso = (len(elegibles) - 1) / (cuantas - 1)
    return [elegibles[round(i * paso)] for i in range(cuantas)]


def _measure(fn, muestras: list) -> float:
    """Segundos por ventana: cronometra `fn(muestra)` en cada una y promedia."""
    if not muestras:
        return 0.0
    inicio = perf_counter()
    for muestra in muestras:
        fn(muestra)
    return (perf_counter() - inicio) / len(muestras)


def estimate_cost(
    *,
    sequence: str,
    anatomy: Anatomy,
    tile_range: TileRange | None = None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    specificity_db=None,
    specificity_target: str | None = None,
    transgene_db=None,
    mature=None,
    abundance=None,
    utr3_set=None,
    accessibility: bool = False,
) -> CostEstimate:
    """Tila sin filtros caros, cuenta, y mide una invocacion de cada uno."""
    inicio = perf_counter()
    barato = tile_utr(
        sequence,
        anatomy=anatomy,
        tile_range=tile_range,
        thresholds=thresholds,
    )
    tilado = perf_counter() - inicio

    elegibles = [w for w in barato.windows if w.biofisicos_ok]
    cuantas = len(elegibles)
    items: list[CostItem] = []

    if cuantas:
        from .accessibility import accessibility_of  # noqa: PLC0415
        from .mirna import filter_seed_collision  # noqa: PLC0415
        from .scaffold import passenger_from_guide  # noqa: PLC0415
        from .seed_load import seed_load  # noqa: PLC0415
        from .specificity import (  # noqa: PLC0415
            filter_specificity,
            filter_transgene,
        )

        muestras = _sample_windows(elegibles)

        def _guia(w) -> str:
            return w.evaluation.guide.replace("U", "T")

        def _pasajera(w) -> str:
            return passenger_from_guide(w.evaluation.guide).sequence

        if specificity_db is not None and specificity_target:
            items.append(
                CostItem(
                    name="especificidad",
                    per_window=_measure(
                        lambda w: filter_specificity(
                            _guia(w), _pasajera(w), specificity_db,
                            target=specificity_target,
                        ),
                        muestras,
                    ),
                    windows=cuantas,
                )
            )
        if transgene_db is not None:
            items.append(
                CostItem(
                    name="transgen",
                    per_window=_measure(
                        lambda w: filter_transgene(
                            _guia(w), _pasajera(w), transgene_db
                        ),
                        muestras,
                    ),
                    windows=cuantas,
                )
            )
        if mature is not None:
            items.append(
                CostItem(
                    name="seed_colision",
                    per_window=_measure(
                        lambda w: filter_seed_collision(
                            _guia(w), mature, abundance, passenger=_pasajera(w)
                        ),
                        muestras,
                    ),
                    windows=cuantas,
                )
            )
        if utr3_set is not None:
            items.append(
                CostItem(
                    name="carga_seed",
                    per_window=_measure(
                        lambda w: seed_load(_guia(w), utr3_set), muestras
                    ),
                    windows=cuantas,
                )
            )
        if accessibility:
            items.append(
                CostItem(
                    name="accesibilidad",
                    per_window=_measure(
                        lambda w: accessibility_of(
                            sequence,
                            start=w.window.start,
                            length=barato.window_size,
                        ),
                        muestras,
                    ),
                    windows=cuantas,
                    note="dos plegados por ventana (±80 y ±150 nt)",
                )
            )

    return CostEstimate(
        windows=len(barato.windows),
        eligible=cuantas,
        tiling_seconds=tilado,
        items=tuple(items),
    )
