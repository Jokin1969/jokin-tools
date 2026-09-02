"""Como se identifica una corrida, y por que el id lleva el md5 del resultado.

**Reportado tres veces en un solo dia (2026-09-02), errata nº 48.** El id era
`especie + tipo + fecha`, asi que `Mus musculus-blast-02/09/2026` ya existia y la segunda
corrida del dia abortaba. Y repetir el mismo dia **es lo normal**: quien lo reporto corrio
el BLAST cuatro veces, todas por fallos de la app. La salida que quedaba era inventarse
una fecha o abrir un proyecto nuevo, y lo segundo **tira el historial que el log existe
para conservar**: por que se volvio a correr.

LA PIEZA QUE FALTABA es el `result_md5`, y la propiedad es exactamente la que hace falta:

  · dos resultados DISTINTOS no chocan — se puede repetir cuantas veces haga falta;
  · dos resultados IDENTICOS si — que es cuando abortar es lo correcto, porque eso no es
    repetir una corrida: es subir dos veces el mismo fichero.

LA ESPECIE SALE DEL ID. El log es de UN proyecto y el proyecto ya declara su especie en
`proyecto.json`; repetirla en cada linea no identificaba nada mas.

Y EL MD5 SE CALCULA EN UN SOLO SITIO (`result_fingerprint`). Los cuatro almacenes tenian
su propio `hashlib.md5(raw)` — cuatro definiciones del mismo numero, que es el patron de
las cinco copias de la clave de consulta (errata nº 44). Aqui ademas importa porque el id
TERMINA en ese md5: si se calcularan por separado, una corrida podria tener dos
identidades y nada obligaria a que coincidieran.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib

from .errors import ShmirDesignError

__all__ = ["ETIQUETAS", "mensaje_de_id_repetido", "result_fingerprint", "run_id"]


#: Tipo de registro (`store.RECORD_KINDS`) → la etiqueta corta que va en el id. El
#: conjunto es CERRADO y se cruza con `RECORD_KINDS` en `tests/test_id_de_corrida.py`:
#: un quinto modal que no la declare falla ahi, no el dia que dos corridas de tipos
#: distintos se pisen por tener la misma salida.
ETIQUETAS: dict[str, str] = {
    "corrida_blast": "blast",
    "corrida_seed": "seed",
    "corrida_offtarget": "ot",
    "corrida_empalme": "empalme",
}


def result_fingerprint(raw) -> str:
    """El md5 del CRUDO, tal cual. UN solo sitio para los cuatro almacenes y el id."""
    return hashlib.md5(str(raw).encode("utf-8"), usedforsecurity=False).hexdigest()


def run_id(*, kind: str, date: str, result_md5: str) -> str:
    """El identificador de una corrida: tipo, fecha y md5 del resultado.

    La fecha se conserva porque es lo que se lee de un vistazo en el historial; lo que
    hace unico al id es el md5, no ella.
    """
    if kind not in ETIQUETAS:
        raise ShmirDesignError(
            f"No hay ninguna corrida {kind!r} en la tabla de identidades; las que hay "
            f"son {', '.join(sorted(ETIQUETAS))}. Se aborta en vez de inventar una "
            f"etiqueta: dos tipos de corrida con la misma etiqueta se pisarian el id."
        )
    for campo, valor in (("date", date), ("result_md5", result_md5)):
        if not str(valor).strip():
            raise ShmirDesignError(
                f"Un identificador de corrida necesita {campo}: sin el el registro no "
                f"es auditable. Se aborta."
            )
    return f"{ETIQUETAS[kind]}-{date}-{result_md5}"


def mensaje_de_id_repetido(
    *, run_id: str, date: str, by: str, que_es: str, como_repetir: str,
) -> str:
    """El mensaje de un id repetido, y DICE COMO SALIR.

    Un mensaje que solo dice que aborta empuja a inventarse una fecha falsa o a abrir un
    proyecto que nadie necesita — que es lo que acaba de pasar tres veces. Con el md5
    dentro del id, un choque significa UNA sola cosa y se puede decir sin adivinar: el
    fichero que se acaba de soltar es **byte a byte** el que ya esta guardado.
    """
    return (
        f"ESTE RESULTADO YA ESTÁ GUARDADO. No es una corrida nueva: el fichero que "
        f"acabas de soltar es **byte a byte** el de la corrida {run_id!r} ({que_es}), "
        f"del {date}, subida por {by}. El id lleva el md5 del resultado, así que dos "
        f"corridas DISTINTAS del mismo día entran las dos sin problema — sólo choca "
        f"subir dos veces lo mismo.\n"
        f"\n"
        f"QUÉ HACER:\n"
        f"· Si querías guardar ESTA corrida: ya está guardada. Mírala en el historial "
        f"del proyecto y en la ficha del candidato; su veredicto ya cuenta.\n"
        f"· Si querías registrar OTRA corrida: el resultado es idéntico al anterior, "
        f"así que no hay nada nuevo que guardar todavía. {como_repetir}\n"
        f"\n"
        f"LO QUE NO HAY QUE HACER, y se dice porque es lo que invita a hacer un aborto "
        f"a secas: NO cambies la fecha y NO abras un proyecto nuevo. Ninguna de las dos "
        f"arregla nada aquí y la segunda parte en dos el historial, que es justo lo que "
        f"el log existe para conservar. Y no hay nada que borrar: el log es "
        f"**append-only** a propósito, así que la corrida anterior no se puede pisar — "
        f"ni hace falta."
    )
