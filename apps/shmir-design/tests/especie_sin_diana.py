"""Una especie SIN diana declarada, DERIVADA de la tabla — nunca escrita a mano.

**De donde sale.** El 2026-09-11 se declaro el humano en `data/diana/variantes.toml`, y
`test_la_diana_no_es_un_offtarget` se puso rojo: usaba `species="human"` como su «especie
sin declarar». El test no estaba mal escrito para lo que probaba — estaba **atado a que
nadie declarara esa especie**, que es justo lo que el propio fichero dice que va a pasar
(«se añade cuando haya una corrida humana»).

Y el rojo es el caso AFORTUNADO. Si el orden hubiera sido el contrario —declarar una
especie que un test usa como control y que ese control siguiera pasando por otra razon—
el guardia de «nunca un `PASS` por una lista vacia» se habria quedado sin ejercitar **en
silencio**, que es el `verify()` de la errata nº 29: una comprobacion que no comprueba.

La condicion que protege no es cosmetica: sin la lista de variantes, un acierto perfecto
contra el propio blanco se cuenta como off-target y **los candidatos fallan contra su
propia diana** — diez FAIL falsos de diez, errata nº 56.

Asi que la especie de control **se deriva de la tabla**: es un slug que la tabla NO
declara. El dia que se declaren todas, esto lo dice en vez de pasar de largo.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import tomllib
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.specificity import target_accessions

TABLA = (
    Path(__file__).resolve().parent.parent / "data" / "diana" / "variantes.toml"
)

#: Candidatas a especie de control, en orden. No son «especies del proyecto»: son nombres
#: que `species.resolve` acepta —fabrica un `Species` con el slug puesto— y que la tabla
#: de dianas no declara. `conejo` va primero porque es la que este proyecto ya usa como
#: ejemplo de especie no declarada en `species.py`.
CANDIDATAS = ("conejo", "oryctolagus_cuniculus", "sin_declarar_para_el_test")


def declaradas() -> frozenset[str]:
    """Los slugs que la tabla SI declara. Se leen de ella, no se transcriben."""
    with TABLA.open("rb") as f:
        tabla = tomllib.load(f)
    return frozenset(
        slug for slug, entrada in tabla.items()
        if isinstance(entrada, dict) and entrada.get("accessions")
    )


def una() -> str:
    """Una especie que la tabla NO declara. ABORTA si no queda ninguna.

    Abortar no es un capricho: si algun dia todas las candidatas estuvieran declaradas,
    devolver una cualquiera dejaria a los tests de este control comprobando el camino
    CONTRARIO al que creen —el de «si hay diana»— y pasando igual. Es preferible un rojo
    que diga que hay que elegir otra.
    """
    ya = declaradas()
    for nombre in CANDIDATAS:
        if nombre in ya:
            continue
        try:
            target_accessions(nombre)
        except ShmirDesignError:
            # rule2-ok: el aborto ES la respuesta que se busca. `target_accessions`
            # aborta exactamente cuando la especie no tiene diana declarada, que es la
            # condicion que este ayudante existe para encontrar, asi que aqui no se
            # esta tragando ningun fallo: se esta LEYENDO el veredicto. Y se comprueba
            # ademas de `declaradas()` a proposito —dos caminos que tienen que estar de
            # acuerdo—: si algun dia la tabla dijera una cosa y el cargador otra, la
            # especie de control se elegiria con el que no manda.
            return nombre
    raise AssertionError(
        "Todas las especies candidatas tienen diana declarada, asi que el control de "
        f"«sin diana declarada» ya no se puede ejercitar con ninguna de {CANDIDATAS}. "
        "Añade una que la tabla no declare — si no, los tests que dependen de este "
        "control pasarian comprobando el camino contrario."
    )
