"""EL EJE DE ORGANISMO, y sus reglas en UN sitio para los DOS frentes que lo tienen.

**De donde sale.** El 2026-09-08 se decidio que los candidatos humanos pasan off-targets
contra los dos transcriptomas —el de la diana y el del fondo genetico del modelo— sin
fundir el veredicto, y el 2026-09-09 se implemento ese eje **dentro de
`offtarget_store`**. El 2026-09-11 se decide lo mismo para `seed_colision`: el shmiR se
expresa en neuronas de raton humanizado, cuya maquinaria endogena de miARN es murina.

Ahi habia dos caminos y uno es el que este proyecto ya ha pagado cinco veces: copiar las
reglas del eje al segundo almacen. Son las mismas cuatro y ninguna es obvia —

  1. **el organismo va SIN valor por defecto** (principio nº 58): con uno, una corrida
     contra un conjunto contestaria por el otro sin que nadie lo decidiera;
  2. **una corrida que NO declara organismo no contesta por ninguno.** No haberlo
     declarado no es «es el de la diana»: es que no se sabe, y suponerlo es justo lo que
     el eje existe para impedir. Son las corridas guardadas ANTES del eje;
  3. **sin eje derivable no se pregunta**, y la respuesta honesta es un `NOT_RUN` que
     dice que el hueco esta en la DECLARACION de la especie y no en un fichero que
     conseguir;
  4. **el frente solo cierra con TODAS sus columnas**, que es la regla que ya tenia
     `fronts_closed_over_panel` y por eso no hace falta ninguna aqui.

— y copiadas serian dos sitios donde arreglarlas la proxima vez. **Un comentario protege
su clase; un mecanismo protege la siguiente** (principio nº 31).

Lo que NO vive aqui es el RECURSO, que es lo unico que de verdad difiere: el eje de
off-targets es UN FICHERO POR ORGANISMO —dos descargas— y el de colision de seed son DOS
SUBCONJUNTOS DE UN FICHERO (`species.MIRNA_AXIS_IS_ONE_FILE`). Cada almacen dice el suyo
y esta capa no lo sabe.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

from __future__ import annotations

from .errors import ShmirDesignError
from .filters import FilterResult, FilterState


def exige_organismo(valor, *, frente: str, que_es: str) -> str:
    """El slug del organismo del eje, o ABORTA. Nunca hay defecto (principio nº 58).

    `que_es` es lo que ese frente mide contra el organismo —«la carga de off-targets»,
    «la colision de seed»— y va en el mensaje: un aborto que no dice de que corrida
    habla manda a mirar el sitio equivocado.
    """
    if not isinstance(valor, str):
        # EL SLUG ES UNA CADENA. `str()` sobre otra cosa fabrica un organismo de su
        # `repr`, con la forma correcta y sin ningun error — errata nº 50.
        raise ShmirDesignError(
            f"El eje de organismo de `{frente}` espera el SLUG —una cadena— y ha "
            f"recibido un {type(valor).__name__}. Se aborta en vez de resolver sobre su "
            f"texto: eso nombraria un organismo inventado con la forma correcta."
        )
    limpio = valor.strip()
    if not limpio:
        raise ShmirDesignError(
            f"Un veredicto de {que_es} se pide CONTRA UN ORGANISMO: sin él, una corrida "
            f"contra el conjunto del fondo genético contestaría a la pregunta de la "
            f"especie diana —y al revés— sin que nadie lo decidiera. Es el mismo "
            f"colapso que fundir guía y pasajera, un eje más allá. Se aborta."
        )
    return limpio


def sin_eje_declarado(species, *, frente: str, que_es: str) -> FilterResult:
    """`NOT_RUN` cuando NO SE SABE contra que organismos hay que medir.

    Pasa con una especie sin declarar: el eje sale vacio, asi que no hay ningun
    organismo que nombrar y el veredicto no se puede pedir —aborta a proposito, y con
    razon—. Lo que NO puede hacer ese aborto es tumbar la tabla o la ficha: la respuesta
    honesta es que el hueco esta en la DECLARACION, no en un fichero.

    Vive aqui, y no en cada consumidor, porque la ficha y la tabla tienen que decir lo
    mismo (principio nº 23).
    """
    from .species import HOW_TO_DECLARE_BACKGROUND, resolve  # noqa: PLC0415

    nombre = resolve(species).scientific if str(species).strip() else "la especie"
    return FilterResult(
        name=frente, state=FilterState.NOT_RUN,
        reason=(
            f"No se sabe contra qué organismos hay que medir {que_es} de {nombre}: no "
            f"declara en qué fondo genético se prueban sus candidatos, así que no hay "
            f"ninguno que nombrar. No es que falte un fichero — es que falta la "
            f"declaración, y suponer que el fondo es la propia especie es medir la "
            f"mitad sin decirlo. {HOW_TO_DECLARE_BACKGROUND}"
        ),
    )


def motivo_corridas_sin_organismo(
    query_name: str, organismo: str, *, que_es: str,
) -> str:
    """Lo que se dice de una corrida guardada ANTES del eje. NO es «es la de la diana».

    Es el caso de una corrida que existe, se lee y cubre a ese candidato, y aun asi no
    puede contestar: no dice contra que conjunto se midio. Se vuelve a correr.
    """
    return (
        f"La(s) corrida(s) de {que_es} que hay para {query_name} NO DECLARAN contra qué "
        f"organismo se midieron, así que no contestan por {organismo!r} ni por ningún "
        f"otro. No haberlo declarado no es «es el de la especie diana»: es que no se "
        f"sabe, y suponerlo es lo que este eje existe para impedir. Se vuelve a correr "
        f"declarando el organismo."
    )
