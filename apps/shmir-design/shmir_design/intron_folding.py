"""Accesibilidad estructural del intron: el analisis del cuarto modal que SI corre entero.

Es la otra mitad del modal, y es de otra naturaleza que la primera. La prediccion de
sitios de splicing usa un modelo entrenado para otra cosa —secuencia genomica humana,
ventana de 10.000 nt, efecto de variantes— asi que sus puntuaciones absolutas no son
interpretables aqui. **Esto no**: se pliega el intron completo con el modulo dentro y se
mira si el donante, el punto de ramificacion y el aceptor quedan apareados. Es un numero
PROPIO, calculado sobre la construccion real, no prestado.

La pregunta que contesta: **un elemento secuestrado dentro de un tallo no esta disponible
para el espliceosoma.** El sitio puede ser perfecto de secuencia y no servir.

Los dos analisis van juntos en el modal y **separados en el resultado**: prediccion de
sitios y accesibilidad estructural son dos preguntas y mezclarlas seria dar por medido lo
que se ha predicho.

Uso, como la accesibilidad de la diana: **DESEMPATE Y ALERTA, NUNCA FILTRO**. No puede
excluir a ningun candidato.

Python 3.11+, solo libreria estandar; ViennaRNA es opcional y sin el esto sale `NOT_RUN`
(regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError
from .filters import FilterState
from .folding import VIENNA_AVAILABLE, dot_bracket, unpaired_probabilities
from .introns import Intron, locate_elements

#: Los tres que decide el espliceosoma. El tracto de polipirimidinas NO entra aqui: es
#: la referencia contra la que se compara un sitio criptico, no un elemento que se
#: aparee o no por su cuenta.
ELEMENTS = ("donante", "punto_de_ramificacion", "aceptor")

WHY_IT_MATTERS = (
    "Un elemento de splicing secuestrado dentro de un TALLO no está disponible para el "
    "espliceosoma. El sitio puede ser perfecto de secuencia y no servir: la secuencia "
    "dice que el sitio existe, el plegado dice si se puede usar. Son dos preguntas y "
    "esta es la segunda."
)

WHY_ITS_OURS = (
    "Este número es PROPIO: sale de plegar la construcción real con ViennaRNA, no de un "
    "modelo entrenado sobre otra cosa. Por eso, a diferencia de las puntuaciones de "
    "predicción de sitios, no hace falta compararlo contra un referente interno para que "
    "signifique algo — aunque sigue siendo un número comparativo entre construcciones y "
    "no un veredicto."
)

USE_NOTE = (
    "DESEMPATE Y ALERTA, NUNCA FILTRO. Ninguno de los dos análisis de este modal puede "
    "excluir un candidato. Lo que pueden hacer es señalar que una construcción concreta "
    "tiene un perfil peor que sus hermanas, y eso es motivo para preferir otra o para "
    "llevar las dos."
)


def _unpaired(probabilities: tuple[float, ...], start: int, end: int) -> float:
    """Probabilidad media de estar sin aparear en un tramo 1-based inclusivo.

    Por FUNCION DE PARTICION, no por la estructura de MFE. La diferencia no es cosmetica:
    la de MFE es UNA estructura, asi que cada posicion sale apareada o no y el resultado
    es un 0 o un 1 disfrazado de probabilidad. Con la de MFE, los seis candidatos del
    panel murino daban donante 1,00 y aceptor 0,00 los seis — un numero que no distingue
    nada, que es exactamente lo contrario de lo que este analisis existe para hacer.
    """
    tramo = probabilities[start - 1:end]
    if not tramo:
        raise ShmirDesignError(
            f"El tramo {start}-{end} queda fuera de una secuencia de "
            f"{len(probabilities)} nt; se aborta en vez de promediar sobre nada."
        )
    return sum(tramo) / len(tramo)


@dataclass(frozen=True)
class IntronFolding:
    """El plegado del intron montado. Numero comparativo, nunca veredicto."""

    state: FilterState
    intron: str
    length: int = 0
    structure: str = ""
    energy: float | None = None
    #: Fraccion sin aparear de cada uno de los tres elementos. VACIO si no se plego:
    #: no haber plegado y plegar y salir apareado son cosas distintas.
    unpaired: dict[str, float] = field(default_factory=dict)
    #: Una fila por CANDIDATO a punto de ramificacion. Si caben varios no se elige.
    branch_detail: tuple[dict[str, object], ...] = ()
    reason: str = ""

    def describe(self) -> str:
        if self.state is not FilterState.PASS:
            return (
                f"Accesibilidad estructural del intrón {self.intron!r} — NOT_RUN\n"
                f"  {self.reason}"
            )
        lineas = [
            f"Accesibilidad estructural del intrón {self.intron!r} "
            f"({self.length} nt, dG {self.energy:+.2f} kcal/mol):"
        ]
        for nombre in ELEMENTS:
            lineas.append(
                f"  {nombre:<24} {self.unpaired[nombre]:.2f} sin aparear"
            )
        if len(self.branch_detail) > 1:
            lineas.append(
                f"  El punto de ramificacion tiene {len(self.branch_detail)} candidatos "
                f"y NO se elige por nuestra cuenta; salen todos:"
            )
            for fila in self.branch_detail:
                lineas.append(
                    f"    intrón:{fila['posicion']} {fila['motivo']} — "
                    f"{fila['desapareado']:.2f} sin aparear"
                )
        lineas.append(f"  {WHY_IT_MATTERS}")
        lineas.append(f"  {USE_NOTE}")
        return "\n".join(lineas)


def fold_intron(
    intron: Intron,
    *,
    module: str,
    spacer5: str = "",
    spacer3: str = "",
    available: bool | None = None,
) -> IntronFolding:
    """Pliega el intron CON el modulo dentro y mide los tres elementos.

    `available=False` fuerza el camino sin ViennaRNA, para poder probarlo.
    """
    usable = VIENNA_AVAILABLE if available is None else available
    if not usable:
        return IntronFolding(
            state=FilterState.NOT_RUN,
            intron=intron.name,
            reason=(
                "ViennaRNA no está instalado, así que no se ha plegado nada. NOT_RUN no "
                "es PASS y no haber plegado NO es «los elementos están accesibles»: las "
                "probabilidades van vacías, nunca a cero."
            ),
        )

    montado = intron.with_module(module, spacer5=spacer5, spacer3=spacer3)
    elementos = locate_elements(montado, name=intron.name)
    estructura, energia = dot_bracket(montado)
    probabilidades = unpaired_probabilities(montado)

    desapareado = {
        "donante": _unpaired(
            probabilidades, elementos.donor.start, elementos.donor.end
        ),
        "aceptor": _unpaired(
            probabilidades, elementos.acceptor.start, elementos.acceptor.end
        ),
    }
    detalle = tuple(
        {
            "posicion": c.start,
            "motivo": c.sequence,
            "desapareado": _unpaired(probabilidades, c.start, c.end),
        }
        for c in elementos.branch_candidates
    )
    if detalle:
        # Con varios candidatos se da el PEOR caso —el menos accesible— y ademas salen
        # todos: elegir el mejor seria elegir por nuestra cuenta justo donde el criterio
        # dice que no se elige.
        desapareado["punto_de_ramificacion"] = min(
            float(f["desapareado"]) for f in detalle
        )
    else:
        raise ShmirDesignError(
            f"El intrón {intron.name!r} montado no tiene ningún candidato a punto de "
            f"ramificacion con el criterio declarado, así que no hay nada que medir ahi. "
            f"Se aborta en vez de emitir dos elementos de tres como si fueran los tres."
        )

    return IntronFolding(
        state=FilterState.PASS,
        intron=intron.name,
        length=len(montado),
        structure=estructura,
        energy=energia,
        unpaired=desapareado,
        branch_detail=detalle,
    )
