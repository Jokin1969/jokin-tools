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
#: Los CUATRO que se miden. El tracto entró el 2026-08-27: faltaba, y sin él el criterio
#: de aceptación de los espaciadores —que donante, punto de ramificación y TRACTO sigan
#: desapareados— no se podía evaluar. Se estaba midiendo el aceptor, que es la frontera,
#: en vez del tracto, que es lo que el espliceosoma lee. El aceptor se queda: no sobra,
#: sólo no era uno de los tres frágiles.
ELEMENTS = (
    "donante", "punto_de_ramificacion", "tracto_polipirimidinas", "aceptor",
)

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
    spacer5: str | None = None,
    spacer3: str | None = None,
    available: bool | None = None,
) -> IntronFolding:
    """Pliega el intron CON el modulo dentro y mide los cuatro elementos.

    `available=False` fuerza el camino sin ViennaRNA, para poder probarlo.

    Los espaciadores siguen el centinela de `Intron.with_module`: `None` es el
    ESTANDAR y `""` es NINGUNO. No son lo mismo, y confundirlos hizo que el punto 0
    del barrido midiera el estandar creyendo medir la ausencia.
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
        # EL TRACTO, que faltaba. Es uno de los TRES elementos frágiles —donante, punto
        # de ramificación y tracto— y sin él el criterio de aceptación de los
        # espaciadores no se puede evaluar: se estaba midiendo el aceptor, que es la
        # frontera, en vez del tracto, que es lo que el espliceosoma lee.
        "tracto_polipirimidinas": _unpaired(
            probabilidades, elementos.ppt.start, elementos.ppt.end
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


#: EL ELEMENTO MENOS ACCESIBLE SE DERIVA DE LA MEDIDA, no se escribe en el codigo.
#: Hoy es el punto de ramificacion en las dos arquitecturas que hay, y por bastante; con
#: un intron distinto puede ser otro. Una constante que dijera «el punto de ramificacion
#: es el mas fragil» seria cierta hoy y falsa sin avisar el dia que entre un tercero —el
#: principio nº 13 sobre una conclusion en vez de sobre un dato—. Se calcula, y el
#: control adversario esta escrito: con unas filas donde el mas bajo es el donante,
#: `weakest_element` tiene que decir «donante».
WEAKEST_IS_DERIVED = (
    "Cuál es el elemento menos accesible se DERIVA de lo plegado, no está escrito en el "
    "código: con otro intrón puede ser otro, y una constante que lo nombrara sería "
    "cierta hoy y falsa sin avisar."
)

#: LA CIFRA DEL PUNTO DE RAMIFICACION ES EL PEOR CASO DE SUS CANDIDATOS, y las dos
#: arquitecturas no tienen los mismos: el MVM tiene UNO (`TTAAT`) y el quimerico DOS
#: (`CTTAC` y `CTGAC`). `fold_intron` da el minimo —elegir el mejor seria elegir por
#: nuestra cuenta justo donde el criterio dice que no se elige— asi que comparar los dos
#: numeros es comparar un unico candidato contra el peor de dos. Decirlo importa porque
#: **bajo la otra lectura el resultado no cambia**: con el mejor de cada uno el quimerico
#: sigue por delante. Que el sentido de la comparacion no dependa de cual se coja es
#: exactamente lo que hay que poder afirmar, y no se puede afirmar sin contar los
#: candidatos.
BRANCH_IS_A_WORST_CASE = (
    "La cifra del punto de ramificación es el PEOR de sus candidatos, y las dos "
    "arquitecturas no tienen los mismos: por eso sale también cuántos hay y cuál es el "
    "mejor de cada una. El sentido de la comparación no depende de cuál de las dos "
    "lecturas se coja."
)

#: LA GUIA NO MUEVE ESTOS NUMEROS, y decirlo es la mitad del dato. Medido sobre las 22:
#: la dispersion entre las once guias es del 0,8 % en el peor caso —el punto de
#: ramificacion del MVM— y CERO en el quimerico. O sea que este eje **no discrimina entre
#: candidatos** y venderlo como desempate seria dar por criterio algo que da el mismo
#: numero a todos. Lo que si discrimina es la ARQUITECTURA, que es la comparacion para la
#: que sirve. Y no es que el analisis sea ciego: el control adversario esta medido y
#: escrito —un modulo complementario al extremo 5' del intron lleva el donante de 0,89 a
#: 0,00—, asi que cazaria una guia que secuestrara un elemento; lo que dicen estos
#: numeros es que ninguna de las once lo hace.
THE_GUIDE_DOES_NOT_MOVE_IT = (
    "La guía NO mueve la accesibilidad de ninguno de los cuatro elementos: entre las "
    "construcciones de una misma arquitectura la dispersión se queda por debajo del "
    "1 %. Este eje NO discrimina entre candidatos — lo que compara son las "
    "ARQUITECTURAS. Y no es que sea ciego: un módulo complementario al extremo 5' del "
    "intrón lleva el donante de 0,89 a 0,00, así que cazaría una guía que secuestrara "
    "un elemento. Lo que dice esta medida es que ninguna lo hace."
)

CONTRAST_NEEDS_TWO = (
    "Con una sola arquitectura no hay contraste que emitir: este número compara "
    "intrones, no candidatos. No se elige ganador."
)

#: TOLERANCIA DE EMPATE, declarada como parametro y NO citada. Por debajo de esto las dos
#: arquitecturas no se distinguen en ese elemento y declarar un ganador seria inventar
#: una precision que el plegado no tiene: media centesima es ya el ultimo digito que este
#: proyecto imprime de una fraccion de apareamiento. No decide ningun veredicto — decide
#: si se escribe un nombre en la columna «gana» o se deja vacia.
TIE_TOLERANCE = 0.005


def _medidos(rows, element: str) -> list[float]:
    """Los valores de ese elemento que SE MIDIERON. Lo no medido no es cero (regla 3)."""
    return [
        float(fila[element]) for fila in rows
        if fila.get(element) is not None
    ]


def _arquitecturas(rows) -> list[str]:
    """En orden de aparicion, no alfabetico: el orden lo pone quien monto el panel."""
    vistas: list[str] = []
    for fila in rows:
        nombre = fila.get("intron")
        if nombre is not None and nombre not in vistas:
            vistas.append(nombre)
    return vistas


def weakest_element(rows) -> str | None:
    """El elemento MENOS accesible sobre las filas dadas. Derivado, nunca escrito.

    Devuelve `None` si no hay ni una medida: sin plegar, no hay elemento mas fragil que
    nombrar — y decir uno seria justo lo que la regla 3 prohibe.
    """
    medias = {}
    for elemento in ELEMENTS:
        valores = _medidos(rows, elemento)
        if valores:
            medias[elemento] = sum(valores) / len(valores)
    if not medias:
        return None
    return min(medias, key=lambda e: (medias[e], e))


def element_stats(rows) -> tuple[dict[str, object], ...]:
    """Por elemento y arquitectura: cuantas se midieron, el rango y la dispersion.

    `sin_medir` va aparte de `n` a proposito: una construccion que no se pudo plegar no
    baja la media, y no contarla en ningun sitio la haria invisible.
    """
    salida = []
    for arquitectura in _arquitecturas(rows):
        suyas = [f for f in rows if f.get("intron") == arquitectura]
        for elemento in ELEMENTS:
            valores = _medidos(suyas, elemento)
            media = sum(valores) / len(valores) if valores else None
            salida.append({
                "elemento": elemento,
                "arquitectura": arquitectura,
                "n": len(valores),
                "sin_medir": len(suyas) - len(valores),
                "min": min(valores) if valores else None,
                "max": max(valores) if valores else None,
                "media": media,
                # En PORCENTAJE de la media, que es lo que hace comparable la dispersion
                # de un elemento que ronda 0,25 con la de uno que ronda 0,99.
                "dispersion": (
                    (max(valores) - min(valores)) / media * 100
                    if valores and media else None
                ),
            })
    return tuple(salida)


def architecture_contrast(rows) -> tuple[dict[str, object], ...]:
    """Elemento a elemento: que arquitectura lo deja MAS accesible.

    Mas desapareado es mejor: un elemento secuestrado dentro de un tallo no esta
    disponible para el espliceosoma. Con una sola arquitectura no se elige ganador, y
    con dos que empatan por debajo de `TIE_TOLERANCE` tampoco.
    """
    arquitecturas = _arquitecturas(rows)
    salida = []
    for elemento in ELEMENTS:
        medias = {}
        for arquitectura in arquitecturas:
            valores = _medidos(
                [f for f in rows if f.get("intron") == arquitectura], elemento
            )
            if valores:
                medias[arquitectura] = sum(valores) / len(valores)
        gana, motivo, diferencia = None, "", None
        if len(medias) < 2:
            motivo = CONTRAST_NEEDS_TWO
        else:
            mejor = max(medias, key=lambda a: (medias[a], a))
            peor = min(medias, key=lambda a: (medias[a], a))
            diferencia = medias[mejor] - medias[peor]
            if diferencia < TIE_TOLERANCE:
                motivo = (
                    f"Empatan por debajo de {TIE_TOLERANCE}: no se elige ganador, que "
                    f"sería inventar una precisión que el plegado no tiene."
                )
            else:
                gana = mejor
                motivo = f"{mejor} lo deja más accesible que {peor}."
        salida.append({
            "elemento": elemento,
            "medias": medias,
            "gana": gana,
            "diferencia": diferencia,
            "motivo": motivo,
        })
    return tuple(salida)


def contrast_reading(rows) -> dict[str, object]:
    """La LECTURA del contraste, con sus dos mitades pegadas.

    Que una arquitectura gane en el elemento mas fragil es un eje a su favor; que pierda
    en otro es un CONTRAPESO, y las dos frases van juntas o mienten las dos. Es la misma
    forma que «rebaja, no descarta» y que el «QUE MIDE / QUE NO MIDE» del ensayo de
    RT-qPCR: sola, la primera deja la decision pareciendo tomada.
    """
    contraste = architecture_contrast(rows)
    fragil = weakest_element(rows)
    por_elemento = {f["elemento"]: f for f in contraste}
    gana_el_fragil = por_elemento[fragil]["gana"] if fragil else None
    # SIN GANADOR EN EL ELEMENTO MAS FRAGIL NO HAY CONTRAPESOS QUE NOMBRAR: un
    # contrapeso lo es DE ALGO, y sin eje a favor la lista serian los ganadores sueltos
    # de los demas elementos presentados como si compensaran una ventaja que nadie ha
    # medido.
    contrapesos = tuple(
        f["elemento"] for f in contraste
        if gana_el_fragil is not None
        and f["gana"] is not None and f["gana"] != gana_el_fragil
    )
    return {
        "mas_fragil": fragil,
        "gana_el_mas_fragil": gana_el_fragil,
        "contrapesos": contrapesos,
        "empates": tuple(f["elemento"] for f in contraste if f["gana"] is None),
        "contraste": contraste,
    }
