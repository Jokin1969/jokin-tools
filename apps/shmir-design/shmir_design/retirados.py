"""Candidatos retirados del panel por una DECISIÓN, con su motivo y su frente.

Un candidato puede salir del panel de dos formas y no se parecen en nada: porque un
FILTRO lo tumba —y entonces su motivo está en su fila— o porque alguien DECIDE no
llevarlo. Lo segundo no lo apunta nadie por su cuenta, y sin apuntarlo la única huella
dentro de un año es una piscina más pequeña: la forma exacta que tiene un candidato de
desaparecer sin que nadie lo vea, que es lo que `selection.measured_promotion_cost`
existe para impedir un nivel más abajo.

**Se aplica por el md5 canónico del 3'UTR**, igual que la tabla de APA medido. Sobre
cualquier otra secuencia no retira nada: quitar «3utr:10» de otro gen sería quitar una
ventana que nadie ha mirado, y es el mismo agujero que `rmsk_mouse.out` conectado por su
rol.

**Y la posición va declarada en el marco del 3'UTR**, que es donde se toman las
decisiones; se convierte al marco de lo tilado al aplicarla. La errata nº 133 es
exactamente esto sin declarar: `959` es una posición válida en los dos marcos y sólo en
uno es la ventana que se quiso retirar.

Python 3.11+, sólo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from .errors import ShmirDesignError

TABLA = Path(__file__).resolve().parent.parent / "data" / "candidatos_retirados.toml"

#: Los campos que una entrada TIENE que traer. Sin motivo y sin frente, una retirada es
#: un candidato que desapareció — que es justo lo que esta tabla existe para que no pase.
CAMPOS = ("md5_utr3", "posicion", "motivo", "frente", "fecha", "quien")


def declarados() -> tuple[dict, ...]:
    """Las entradas de la tabla, validadas. Sin tabla, ninguna."""
    if not TABLA.exists():
        return ()
    with TABLA.open("rb") as f:
        crudo = tomllib.load(f)
    entradas = []
    for i, entrada in enumerate(crudo.get("retirado", ()), start=1):
        faltan = [c for c in CAMPOS if not entrada.get(c)]
        if faltan:
            raise ShmirDesignError(
                f"La entrada {i} de {TABLA.name} no trae {', '.join(faltan)}. Una "
                f"retirada sin motivo, sin frente o sin fecha es un candidato que "
                f"desapareció: se aborta en vez de aplicarla."
            )
        entradas.append(dict(entrada))
    return tuple(entradas)


def para(md5_utr3: str) -> tuple[dict, ...]:
    """Las retiradas que hablan de ESTE 3'UTR. Sobre otro, ninguna."""
    return tuple(e for e in declarados() if e["md5_utr3"] == md5_utr3)


def aplicar(starts, *, entradas, offset: int, md5_utr3: str) -> tuple[set[int], tuple[str, ...]]:
    """Qué inicios (en el marco de LO TILADO) se retiran, y qué se dice de cada uno.

    `offset` es el desfase 3'UTR→lo tilado: 0 cuando lo tilado ya es el 3'UTR.

    **Una entrada que no case con ningún inicio ABORTA.** Una retirada que no retira nada
    es una decisión perdida —la posición cambió, o la corrida es otra— y darla por
    aplicada deja el panel con el candidato dentro y la decisión escrita: las dos cosas a
    la vez, que es peor que cualquiera de ellas.
    """
    disponibles = set(starts)
    fuera: set[int] = set()
    notas: list[str] = []
    for entrada in entradas:
        if entrada["md5_utr3"] != md5_utr3:
            continue
        objetivo = int(entrada["posicion"]) + offset
        if objetivo not in disponibles:
            raise ShmirDesignError(
                f"La retirada declarada de la posición {entrada['posicion']} del 3'UTR "
                f"(fecha {entrada['fecha']}) no corresponde a ninguna ventana elegible "
                f"de esta corrida, y su md5 de 3'UTR SÍ es el de esta secuencia. Se "
                f"aborta: una retirada que no retira nada es una decisión perdida, y "
                f"aplicarla a medias dejaría el candidato dentro y la decisión escrita."
            )
        fuera.add(objetivo)
        notas.append(nota(entrada))
    return fuera, tuple(notas)


def nota(entrada: dict) -> str:
    """Lo que se dice de una retirada. El motivo ENTERO: es lo que se lee dentro de un año."""
    from .coords import Frame, label

    return (
        f"RETIRADO del panel: {label(int(entrada['posicion']), Frame.UTR3)} — por el "
        f"frente {entrada['frente']}, {entrada['fecha']}, {entrada['quien']}. "
        f"{entrada['motivo']}"
    )
