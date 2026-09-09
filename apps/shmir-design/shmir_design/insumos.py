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

Y CADA INSUMO DECLARA SU ROL, NO SU NOMBRE (2026-09-02, errata nº 47). El nombre lo pone
`species.required_files`, que es la unica fuente de los nombres del deposito. Hasta hoy
el de BLAST estaba escrito en PROSA —«base de datos de BLAST»— y `actuales` viene
indexado por el nombre del fichero (`refseq_rna.fa`), asi que la comparacion NO PODIA
DARSE NUNCA: toda corrida de BLAST salia «no se ha podido comprobar» con el fichero
delante y el md5 correcto. Los otros dos acertaban por casualidad —`mature.fa` no lleva
sufijo de especie y `transcriptoma_3utr.fa` es el nombre murino—, o sea que en humano
fallaban igual. Derivar del rol no arregla tres nombres: hace que el cuarto no se pueda
escribir mal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError
from .species import ROL_CATALOGO_DIANA

__all__ = [
    "CONSUMIDOS", "Insumo", "fichero_de", "insumos_de", "md5_de", "md5s_de_corrida",
    "obsoleta", "rol_de", "roles_de",
]


@dataclass(frozen=True)
class Insumo:
    """Un fichero que una corrida consume, y donde esta su md5 dentro del registro."""

    #: El ROL del fichero en `species.required_files`. De ahi sale su NOMBRE, que es la
    #: clave de `actuales` en `obsoleta()`. No se escribe el nombre: un nombre escrito
    #: aqui y otro en el gestor no dan un error, dan un «no se ha podido comprobar»
    #: perpetuo — que es exactamente lo que paso (errata nº 47).
    rol: str
    #: Camino de claves dentro del payload guardado, p. ej. ("database", "md5").
    ruta: tuple[str, ...]
    #: Por que se registra. Sin esto la tabla es una lista y no una decision.
    porque: str
    #: Un insumo opcional puede no estar; su ausencia no marca nada obsoleto.
    opcional: bool = False
    #: De donde sale, DENTRO DEL REGISTRO, el slug del catalogo contra el que se corrio.
    #: Con esto el rol se DERIVA de la propia corrida en vez de escribirse.
    #:
    #: Existe porque desde el eje de catalogo (2026-09-09) una corrida de carga de
    #: off-targets consume UN catalogo —el que declara— y no los dos: son DOS corridas.
    #: Declarar los dos ficheros para la misma corrida marcaria la del catalogo de la
    #: diana como OBSOLETA en cuanto alguien reemplazara el del fondo, con la forma
    #: correcta y sin que nadie lo decidiera.
    catalogo_desde: tuple[str, ...] = ()
    #: Campos del registro que NO son md5 de un insumo pero acompañan (version, etc.).
    contexto: tuple[str, ...] = field(default_factory=tuple)


CONSUMIDOS: dict[str, tuple[Insumo, ...]] = {
    "corrida_blast": (
        Insumo(
            rol="refseq",
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
            rol="mirbase",
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
            rol=ROL_CATALOGO_DIANA,
            ruta=("provenance", "md5"),
            catalogo_desde=("background",),
            porque=(
                "El catalogo sobre el que se cuentan los sitios. Su ensamblaje y su "
                "fecha van al lado, pero lo que compara la app es el md5. CUAL de los "
                "dos catalogos es se DERIVA del `background` de la propia corrida: una "
                "corrida barre UNO —el de la especie diana o el del fondo genetico del "
                "modelo— y son dos corridas, no una con dos ficheros. Sus conteos no se "
                "suman: un gen conservado aparece en los dos, y cada percentil sale de "
                "una nula de SU catalogo (`species.WHY_TWO_CATALOGUES`)."
            ),
        ),
        Insumo(
            rol="mirbase",
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


def rol_de(insumo: Insumo, payload, especie) -> str:
    """El ROL de ese insumo PARA ESA CORRIDA. Casi siempre el declarado; a veces derivado.

    Un insumo con `catalogo_desde` no tiene un rol fijo: lo decide contra que catalogo
    se corrio, que la propia corrida declara. Sin payload no se puede preguntar y se
    ABORTA — un defecto ahi nombraria el fichero de la especie diana para una corrida
    que pudo ser del fondo (principio nº 58).
    """
    if not insumo.catalogo_desde:
        return insumo.rol
    from .species import catalogue_role  # noqa: PLC0415

    actual = payload
    for clave in insumo.catalogo_desde:
        if not isinstance(actual, dict) or clave not in actual:
            actual = ""
            break
        actual = actual[clave]
    return catalogue_role(especie, str(actual or ""))


def roles_de(tipo: str, especie) -> tuple[str, ...]:
    """Los roles de fichero que ESE tipo de corrida puede consumir en ESA especie.

    No es lo mismo que `rol_de`, y la diferencia es la del eje entero: `rol_de` contesta
    «¿cuál consumió ESTA corrida?» —uno— y esto contesta «¿cuáles hacen falta para que
    el frente se pueda cerrar?» —los que la especie declare—. Con el humano son DOS
    catálogos y dos corridas; con el ratón, uno.

    Lo usa el panel del modal, que tiene que enseñar los dos ficheros: enseñar sólo el
    de la corrida que ya se hizo dejaría el segundo sin pedir, y el frente sin poder
    cerrarse por un fichero que nadie ha nombrado.
    """
    from .species import catalogue_role, off_target_catalogue_slugs  # noqa: PLC0415

    roles: list[str] = []
    for insumo in insumos_de(tipo):
        if not insumo.catalogo_desde:
            candidatos = [insumo.rol]
        else:
            candidatos = [
                catalogue_role(especie, slug)
                for slug in off_target_catalogue_slugs(especie)
            ] or [insumo.rol]
        for rol in candidatos:
            if rol not in roles:
                roles.append(rol)
    return tuple(roles)


def fichero_de(insumo: Insumo, especie, payload=None) -> str:
    """El NOMBRE del fichero de ese insumo para esa especie. Se deriva, no se escribe.

    La unica fuente de los nombres del deposito es `species.required_files`, y esta
    funcion es la que ata la tabla de insumos a ella. Un rol que el gestor no declare
    ABORTA: devolver un nombre inventado dejaria la comparacion de md5 preguntando por
    una clave que nunca esta, que es literalmente la errata nº 47.

    `payload` sólo hace falta para un insumo cuyo rol se DERIVA de la corrida
    (`catalogo_desde`); para los demas se ignora.
    """
    from .species import required_files, resolve  # noqa: PLC0415

    resuelta = resolve(especie) if isinstance(especie, str) else especie
    rol = rol_de(insumo, payload, resuelta)
    for pedido in required_files(resuelta):
        if pedido.role == rol:
            return pedido.filename
    raise ShmirDesignError(
        f"El insumo declara el rol {rol!r} y `species.required_files` no lo pide "
        f"para {resuelta.scientific}; los roles que hay son "
        f"{', '.join(sorted(p.role for p in required_files(resuelta)))}. Se aborta en "
        f"vez de inventar un nombre de fichero: uno inventado no da un error, deja la "
        f"corrida en «no se ha podido comprobar» para siempre."
    )


def md5s_de_corrida(tipo: str, payload, *, especie) -> dict[str, str | None]:
    """Fichero → md5 registrado. `None` donde el registro no lo trae."""
    return {
        fichero_de(i, especie, payload): md5_de(payload, i) for i in insumos_de(tipo)
    }


def obsoleta(
    tipo: str, payload, *, actuales: dict[str, str], especie,
) -> tuple[str, ...]:
    """¿Sigue valiendo esta corrida? Devuelve el motivo por cada insumo que no.

    Tupla vacia = todos los ficheros que consumio siguen siendo los mismos. `actuales`
    se indexa por el NOMBRE DEL FICHERO en el deposito, y ese nombre lo resuelve
    `fichero_de` contra el gestor: los dos lados de la comparacion salen de la misma
    fuente, asi que no se pueden desincronizar.

    Se recalcula en CADA consulta, a proposito: aparecer o desaparecer un fichero tiene
    que reflejarse solo. No hay nada guardado que revalidar (principio nº 14).

    Un fichero del que no se conoce el md5 de hoy NO se da por vigente: se dice que no
    se ha podido comprobar. Es la misma distincion que NOT_RUN frente a PASS, y la
    razon por la que esta funcion no devuelve un booleano.
    """
    motivos = []
    for ins in insumos_de(tipo):
        fichero = fichero_de(ins, especie, payload)
        registrado = md5_de(payload, ins)
        de_hoy = actuales.get(fichero)
        if registrado is None:
            if ins.opcional:
                continue
            motivos.append(
                f"{fichero}: la corrida no guardó su md5, así que no se ha podido "
                f"comprobar si sigue siendo el mismo fichero."
            )
        elif de_hoy is None:
            motivos.append(
                f"{fichero}: no se ha podido comprobar — no hay md5 de hoy con el "
                f"que comparar el {registrado} que se registró."
            )
        elif de_hoy != registrado:
            motivos.append(
                f"{fichero}: se corrió con md5 {registrado} y el de hoy es "
                f"{de_hoy}. El fichero ha cambiado."
            )
    return tuple(motivos)
