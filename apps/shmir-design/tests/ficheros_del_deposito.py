"""¿Está en `data/reference/` lo que este test necesita? La pregunta, EN UN SOLO SITIO.

Un fichero de referencia que no está NO puede hacer fallar un test: tiene que SALTARLO
de forma visible. Es la regla 3 aplicada a la propia suite — «no se pudo comprobar» y
«no lo supera» son cosas distintas, y ese es justo el motivo por el que se distinguen
`NOT_RUN` y `FAIL` en un veredicto. Un rojo permanente por un fichero ausente acaba
costando más que el fichero: una suite con un rojo fijo no dice «hay un fallo», dice
«hay un rojo», y a partir de ahí ningún rojo se atiende.

**El idioma ya existía y sólo cubría los transcritos.** `reference.fixture_available` lo
usan ~80 ficheros de test, y pregunta por un `ReferenceTranscript` de
`reference.REFERENCES` — o sea por `NM_011170.3.fa` y `NM_000311.5.fa`, que SÍ están
versionados. Lo que no tenía forma de preguntarse era el RESTO del depósito:
`mature.fa`, los plásmidos de Addgene, los catálogos. Cada test que los necesita los
abría directamente, así que su ausencia salía como `FileNotFoundError`, `KeyError` o —
peor— como una aserción numérica sobre un panel calculado sin ellos.

**Por qué aquí y no en cada test.** Un nombre de fichero escrito en cada sitio es un
dato transcrito, y un dato transcrito no se desincroniza en un sitio: se desincroniza en
todos los que lo copiaron (errata nº 28). Y escrito con `Path.is_file()` sería además la
errata nº 15: un fichero de 0 bytes existe, pasa `is_file()`, y no contiene nada — la
descarga cortada a medias, el `touch` de prueba, el volumen sin espacio.

**No se añade una tercera definición de «está»**: esto DELEGA en
`shmir_design.presencia.hay_fichero`, que es la única del proyecto, y la que lleva la
lección de los 0 bytes dentro.

Python 3.11+, solo librería estándar (regla 6).
"""

from __future__ import annotations

from pathlib import Path

from shmir_design.presencia import hay_fichero

__all__ = ["DATOS", "hay", "falta"]

#: El depósito versionado. El de TRABAJO puede ser otro (`SHMIR_REFERENCE_DIR`), y esa
#: no es la pregunta de aquí: estos tests leen los ficheros del repositorio.
DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"


def hay(*nombres: str) -> bool:
    """¿Están TODOS los que se piden, y con contenido? Para `@unittest.skipUnless`.

    Se exigen todos y no alguno: un test que necesita dos ficheros y corre con uno mide
    otra cosa. Sin nombres ABORTA — `all(())` es `True`, así que una llamada vacía daría
    un «están todos» sobre ninguno, que es el peor de los verdes.
    """
    if not nombres:
        raise ValueError(
            "hay() sin ningún nombre: `all(())` es True, así que esto habría dicho "
            "que están todos sin mirar ninguno. Nombra el fichero que hace falta."
        )
    return all(hay_fichero(DATOS / n) for n in nombres)


def falta(*nombres: str) -> str:
    """El motivo del salto, NOMBRANDO los que no están.

    «NOT_RUN: falta un fichero» manda a averiguar cuál. Se nombran los AUSENTES y no
    todos los pedidos: los que sí están no hay que conseguirlos, y decir lo contrario
    manda a bajar de nuevo algo que ya se tiene.
    """
    if not nombres:
        raise ValueError("falta() sin ningún nombre: no hay motivo que escribir.")
    ausentes = [n for n in nombres if not hay_fichero(DATOS / n)] or list(nombres)
    return "NOT_RUN: falta " + ", ".join(f"data/reference/{n}" for n in ausentes)
