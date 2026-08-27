"""Que fichero consume cada corrida, y donde vive su md5 en el registro.

Existe por un hallazgo de auditoria: `SeedScan` guardaba la procedencia del fichero de
maduros como PROSA —`mature.provenance`, con el md5 en medio de una frase— mientras
BLAST guardaba `database.md5` y off-target `provenance.md5` como CAMPO. La diferencia
no es cosmetica: OBSOLETO se deriva COMPARANDO md5, y un md5 dentro de una frase no se
compara, se lee.

Y al mirarlo salio lo que el primer vistazo tapaba: off-target consume DOS ficheros —el
catalogo de 3'UTR y el de maduros— y solo llevaba el md5 del primero. No era un campo
que faltaba en uno de cuatro; faltaba en dos, y en el segundo lo escondia que el
primero si estuviera. Es la misma forma de la errata nº 12: una comprobacion que se
llamaba «los TRES elementos» y contaba en vez de identificar.

Por eso esto es una TABLA y no cuatro `if`. Un quinto modal que no declare sus insumos
falla en `tests/test_insumos_de_cada_corrida.py`, no el dia que alguien busque por que
su corrida no se marco obsoleta.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError

__all__ = [
    "CONSUMIDOS", "Insumo", "insumos_de", "md5_de", "md5s_de_corrida", "obsoleta",
]


@dataclass(frozen=True)
class Insumo:
    """Un fichero que una corrida consume, y donde esta su md5 dentro del registro."""

    #: Nombre con el que se le habla al usuario. Es la CLAVE de `actuales` en
    #: `obsoleta()`: quien pregunta tiene que usar el mismo nombre.
    fichero: str
    #: Camino de claves dentro del payload guardado, p. ej. ("database", "md5").
    ruta: tuple[str, ...]
    #: Por que se registra. Sin esto la tabla es una lista y no una decision.
    porque: str
    #: Un insumo opcional puede no estar; su ausencia no marca nada obsoleto.
    opcional: bool = False
    #: Campos del registro que NO son md5 de un insumo pero acompañan (version, etc.).
    contexto: tuple[str, ...] = field(default_factory=tuple)


CONSUMIDOS: dict[str, tuple[Insumo, ...]] = {
    "corrida_blast": (
        Insumo(
            fichero="base de datos de BLAST",
            ruta=("database", "md5"),
            porque=(
                "Es la base contra la que se contaron los impactos. Una base distinta "
                "da otra cuenta con la misma consulta, así que sin su md5 el veredicto "
                "no es auditable dentro de un año."
            ),
        ),
    ),
    "corrida_seed": (
        Insumo(
            fichero="mature.fa",
            ruta=("mature_md5",),
            porque=(
                "Es el único fichero que este frente consume, y el que más se va a "
                "reemplazar: miRBase pública versiones. Estaba solo dentro de la prosa "
                "de `source`, que no se puede comparar."
            ),
        ),
    ),
    "corrida_offtarget": (
        Insumo(
            fichero="transcriptoma_3utr.fa",
            ruta=("provenance", "md5"),
            porque=(
                "El catalogo sobre el que se cuentan los sitios. Su ensamblaje y su "
                "fecha van al lado, pero lo que compara la app es el md5."
            ),
        ),
        Insumo(
            fichero="mature.fa",
            ruta=("mature_md5",),
            porque=(
                "Esta corrida también lo consume: los controles y la tasa base salen "
                "de los maduros. Faltaba, y lo tapaba que el md5 del catalogo si "
                "estuviera."
            ),
        ),
    ),
    "corrida_empalme": (),
}

#: Lo que la tabla NO lleva, y por que. `query_md5` (BLAST) y `result_md5` (los cuatro)
#: son md5 de cosas que la app GENERA o RECIBE, no de ficheros de referencia que alguien
#: pueda reemplazar por el gestor. Siguen guardandose donde estaban y siguen atando el
#: resultado a su consulta; lo que no hacen es responder a esta pregunta, que es «¿ha
#: cambiado bajo mis pies un fichero del que dependia este veredicto?».
QUE_NO_ENTRA = (
    "Los md5 de lo que la app genera (`query_md5`) o recibe (`result_md5`) no son "
    "insumos: nadie los reemplaza por el gestor de referencia. Se siguen guardando, "
    "pero no marcan una corrida obsoleta."
)

#: Por que `corrida_empalme` esta VACIA y no ausente. Una entrada vacia es una decision
#: tomada; una ausente es una que nadie miro — y la tabla no distingue las dos si no se
#: dice. Esta corrida no consume ningun fichero de referencia: monta el cassette con
#: piezas versionadas del propio paquete y entrega la peticion a SpliceAI, cuyo
#: resultado se identifica con `result_md5`, que es SALIDA y no insumo.
POR_QUE_EMPALME_NO_TIENE = (
    "La corrida de empalme no consume ningún fichero de referencia: monta el cassette "
    "con piezas versionadas del paquete y lo que vuelve de SpliceAI se identifica con "
    "`result_md5`, que es salida y no insumo. La entrada está VACÍA a propósito, no "
    "ausente: vacía dice «se miró y no hay»; ausente diría «nadie lo miró»."
)


def insumos_de(tipo: str) -> tuple[Insumo, ...]:
    """Los insumos de un tipo de corrida. Un tipo desconocido ABORTA.

    Devolver `()` para un tipo que no esta en la tabla lo haria indistinguible de
    `corrida_empalme`, que si tiene la entrada y esta vacia a proposito.
    """
    if tipo not in CONSUMIDOS:
        raise ShmirDesignError(
            f"No hay ninguna corrida {tipo!r} en la tabla de insumos; las que hay son "
            f"{', '.join(sorted(CONSUMIDOS))}. Se aborta en vez de devolver una lista "
            f"vacía, que se leería como «esta corrida no consume nada»."
        )
    return CONSUMIDOS[tipo]


def md5_de(payload, insumo: Insumo) -> str | None:
    """El md5 de ese insumo dentro del registro, o `None` si no esta."""
    actual = payload
    for clave in insumo.ruta:
        if not isinstance(actual, dict) or clave not in actual:
            return None
        actual = actual[clave]
    return actual if isinstance(actual, str) and actual else None


def md5s_de_corrida(tipo: str, payload) -> dict[str, str | None]:
    """Fichero → md5 registrado. `None` donde el registro no lo trae."""
    return {i.fichero: md5_de(payload, i) for i in insumos_de(tipo)}


def obsoleta(tipo: str, payload, *, actuales: dict[str, str]) -> tuple[str, ...]:
    """¿Sigue valiendo esta corrida? Devuelve el motivo por cada insumo que no.

    Tupla vacia = todos los ficheros que consumio siguen siendo los mismos. `actuales`
    se indexa por el NOMBRE del insumo.

    Un fichero del que no se conoce el md5 de hoy NO se da por vigente: se dice que no
    se ha podido comprobar. Es la misma distincion que NOT_RUN frente a PASS, y la
    razon por la que esta funcion no devuelve un booleano.
    """
    motivos = []
    for ins in insumos_de(tipo):
        registrado = md5_de(payload, ins)
        de_hoy = actuales.get(ins.fichero)
        if registrado is None:
            if ins.opcional:
                continue
            motivos.append(
                f"{ins.fichero}: la corrida no guardó su md5, así que no se ha podido "
                f"comprobar si sigue siendo el mismo fichero."
            )
        elif de_hoy is None:
            motivos.append(
                f"{ins.fichero}: no se ha podido comprobar — no hay md5 de hoy con el "
                f"que comparar el {registrado} que se registró."
            )
        elif de_hoy != registrado:
            motivos.append(
                f"{ins.fichero}: se corrió con md5 {registrado} y el de hoy es "
                f"{de_hoy}. El fichero ha cambiado."
            )
    return tuple(motivos)
