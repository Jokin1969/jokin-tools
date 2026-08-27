"""Colision de la seed de la guia con miARN endogenos (bloque 1a).

La pregunta: ¿las posiciones 2-8 de la guia coinciden con las de un miARN maduro que la
neurona expresa? Compartir seed con un miARN abundante no produce off-targets dispersos,
reprime su red de dianas entera.

**Dos niveles, y la razon es aritmetica.** El espacio de 7-meros son 4^7 = 16.384
combinaciones y hay del orden de 2.000 maduros murinos anotados, asi que por puro azar
cerca del 10 % de las guias colisionara con alguno. Un "cualquier colision = FAIL"
tiraria uno de cada diez candidatos, casi todos por chocar con miARN que ni siquiera se
expresan en cerebro. Por eso:

  FAIL  colision con un miARN abundante en cerebro. La lista corta viene de un fichero
        con procedencia — MirGeneDB, porque buena parte de lo anotado en miRBase no es
        un miARN real y para un FAIL duro hace falta la fuente curada.
  WARN  colision con cualquier otro anotado en miRBase: se lista, no se descarta.

**Y la abundancia son DOS CAPAS desde el 2026-08-26**, no una lista:

  NUCLEO    diez familias de consenso del campo, EN CODIGO y sin cita, con FAIL duro.
            Autorizado por el responsable del proyecto (`CORE_AUTHORIZATION`): revierte
            de forma acotada la regla anterior de que ninguna lista de miARN se escribe
            aqui. Corre SIEMPRE, porque no necesita fichero.
  AMPLIADA  el resto de mmu- por encima de un umbral, de FICHERO, con nivel de aviso. El
            fichero lleva en cabecera la REFERENCIA y el UMBRAL; sin ellos la capa queda
            NOT_RUN — un aviso sin umbral parece un veredicto y no lo es.

Lo que sigue sin escribirse en el codigo es una SECUENCIA: las seeds salen de
`mature.fa`, y un test lo comprueba sobre el propio fuente.

Regla 4: ninguna URL. Los ficheros se descargan a mano y se versionan con checksum.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import ChecksumMismatchError, ShmirDesignError
from .filters import FilterResult, FilterState

FILTER_NAME = "seed_colision"

#: Las mismas posiciones que en `seeds.py`: la seed son las 2-8 del maduro y de la guia.
SEED_START = 2
SEED_END = 8

#: Prefijos de especie de miRBase que interesan a este proyecto.
#: Que prefijos se INDEXAN al leer `mature.fa`. `()` = TODOS los del fichero, y ese es
#: el defecto a proposito: `("mmu-", "hsa-")` dejaba fuera del indice a cualquier otra
#: especie SIN AVISAR, asi que una guia de conejo salia limpia por no haber contra que
#: compararla. El filtro por especie es cosa de quien PREGUNTA (`seed_scan`, via
#: `species.mirbase_prefix`), no de quien carga el fichero.
DEFAULT_PREFIXES: tuple[str, ...] = ()

#: Los dos que el proyecto tenia indexados. Se conserva con nombre propio porque el
#: manifiesto y las cifras de tasa base publicadas se calcularon con ellos.
HISTORICAL_PREFIXES = ("mmu-", "hsa-")

#: Cuantos 7-meros hay. Se usa para explicar en el informe por que hay dos niveles.
SEED_SPACE = 4 ** (SEED_END - SEED_START + 1)


def _require_provenance(source: str, version: str, checksum: str, *, what: str) -> None:
    for campo, valor in (("source", source), ("version", version), ("checksum", checksum)):
        if not valor or not str(valor).strip():
            raise ValueError(
                f"{what} necesita {campo}: sin procedencia el veredicto no es auditable "
                f"y no vale. Se aborta."
            )


@dataclass(frozen=True)
class MatureSet:
    """Maduros de miRBase, indexados por seed. Con procedencia o no vale."""

    #: seed en ADN → nombres de los maduros que la llevan
    seeds: dict[str, tuple[str, ...]]
    source: str
    version: str
    checksum: str
    prefixes: tuple[str, ...] = DEFAULT_PREFIXES

    @property
    def provenance(self) -> str:
        return (
            f"{self.source}, versión {self.version}, checksum {self.checksum}, "
            f"{sum(len(n) for n in self.seeds.values())} maduro(s) "
            f"({'/'.join(self.prefixes)}), {len(self.seeds)} seed(s) distintas"
        )

    def names_for(self, seed: str) -> tuple[str, ...]:
        return self.seeds.get(seed.upper(), ())


@dataclass(frozen=True)
class AbundanceList:
    """Capa AMPLIADA de abundancia: nivel AVISO, y de fichero.

    El nivel FAIL ya no depende de ella: eso es el NUCLEO (`CORE_ABUNDANT`), que va en
    codigo. Esta capa es «el resto de mmu- por encima de un umbral», y por eso necesita
    saber DE DONDE sale el umbral: sin referencia y sin umbral en la cabecera, la capa
    no se usa y queda NOT_RUN. Un aviso sin umbral parece un veredicto y no lo es.
    """

    names: frozenset[str]
    source: str
    version: str
    checksum: str
    reference: str = ""
    threshold: str = ""
    missing_reason: str = ""

    @property
    def usable(self) -> bool:
        return not self.missing_reason

    @property
    def provenance(self) -> str:
        if not self.usable:
            return (
                f"{self.source}, versión {self.version}, checksum {self.checksum} — "
                f"NO UTILIZABLE: {self.missing_reason}"
            )
        return (
            f"{self.source}, versión {self.version}, checksum {self.checksum}, "
            f"{len(self.names)} miARN por encima de {self.threshold}; "
            f"referencia: {self.reference}"
        )


# ─── Capa 1: el NUCLEO, en codigo y con FAIL duro ────────────────────────────
#
# AUTORIZACION EXPLICITA. Este proyecto tenia la regla contraria —«no hay ninguna lista
# de miARN escrita en el codigo, y un test lo comprueba»— y se REVIERTE aqui, acotada a
# esta lista y con el motivo escrito. Lo que NO cambia: la capa ampliada sigue
# necesitando su fichero con referencia y umbral.

CORE_AUTHORIZATION = (
    "Núcleo de miARN abundantes en cerebro, autorizado por el responsable del proyecto "
    "el 2026-08-26 para ir EN CÓDIGO y SIN CITA, por ser consenso del campo. Revierte "
    "de forma acotada la regla anterior de que ninguna lista de miARN se escribe en el "
    "código. La capa AMPLIADA no entra en esta autorización: sigue viniendo de fichero "
    "con referencia y umbral."
)

CORE_REASON = (
    "Compartir seed con uno de estos no produce off-targets dispersos: SECUESTRA UN "
    "PROGRAMA REGULADOR NEURONAL COMPLETO."
)

#: La familia del andamio. Una colision aqui se lee distinto y peor.
MIR30_FAMILY = "miR-30"
LET7_FAMILY = "let-7"

MIR30_REASON = (
    "Y además es de la familia miR-30, que es de donde sale NUESTRO ANDAMIO: miR-E "
    "deriva de miR-30a. Una colisión aquí no es solo competencia por la red de dianas "
    "de ese miARN — es que la horquilla que se construye se parece a un miARN endogeno "
    "abundante en el mismo tejido. Lectura distinta y peor: revisala aparte."
)


@dataclass(frozen=True)
class CoreMember:
    """Una entrada del nucleo. `family` no vacio = casa con toda la familia."""

    label: str
    exact: str = ""
    family: str = ""

    def matches(self, name: str) -> bool:
        """`name` viene de miRBase con prefijo de especie: `mmu-miR-124-3p`."""
        sin_prefijo = name.split("-", 1)[1] if "-" in name else name
        bajo = sin_prefijo.lower()
        if self.exact:
            return bajo == self.exact.lower()
        # Familia: `let-7a-5p`, `miR-30c-5p`. Detras del nombre de familia tiene que
        # venir una LETRA de miembro, para que `miR-30` no se coma a `miR-300` ni
        # `let-7` a `miR-7`.
        prefijo = self.family.lower()
        if not bajo.startswith(prefijo):
            return False
        resto = bajo[len(prefijo) :]
        return bool(resto) and resto[0].isalpha()


CORE_ABUNDANT: tuple[CoreMember, ...] = (
    CoreMember("miR-124-3p", exact="miR-124-3p"),
    CoreMember("miR-9-5p", exact="miR-9-5p"),
    CoreMember("let-7 (familia)", family=LET7_FAMILY),
    CoreMember("miR-128-3p", exact="miR-128-3p"),
    CoreMember("miR-181a-5p", exact="miR-181a-5p"),
    CoreMember("miR-125b-5p", exact="miR-125b-5p"),
    CoreMember("miR-30 (familia)", family=MIR30_FAMILY),
    CoreMember("miR-26a-5p", exact="miR-26a-5p"),
    CoreMember("miR-99a-5p", exact="miR-99a-5p"),
    CoreMember("miR-138-5p", exact="miR-138-5p"),
)


#: La especie de la que habla la autorizacion escrita de `CORE_ABUNDANT`. La lista es de
#: consenso del campo en cerebro MURINO, y eso acota lo que puede afirmar.
CORE_SPECIES = "mouse"

BORROWED_LIST_MARK = "LISTA_DE_OTRA_ESPECIE"

UNDECLARED_SPECIES_MARK = "ESPECIE_NO_DECLARADA"

UNDECLARED_SPECIES_WARNING = (
    f"{UNDECLARED_SPECIES_MARK}: esta corrida no declara especie, así que NO SE HA "
    f"PODIDO COMPROBAR si el núcleo de abundancia —autorizado para cerebro murino— es "
    f"el de esta. No haber podido comprobarlo no es que coincida."
)

BORROWED_LIST_WARNING = (
    f"{BORROWED_LIST_MARK}: el núcleo de abundancia que ha producido este FAIL esta "
    f"autorizado para CEREBRO MURINO, y la especie de este diseño es otra. "
    f"`CoreMember.matches` compara SIN el prefijo, así que la lista casa igual y el "
    f"filtro corre — pero eso no la convierte en una lista de esta especie. "
    f"Puede que acierte: let-7, miR-124 y miR-9 son abundantes en cerebro de "
    f"practicamente cualquier mamifero. Excluir por una lista PRESTADA es defendible; "
    f"no decirlo, no. Para cerrarlo bien hace falta la lista de abundancia de ESTA "
    f"especie, con su referencia y su umbral."
)


@dataclass(frozen=True)
class CoreHit:
    name: str
    member: CoreMember
    #: Especie del DISEÑO (no la del maduro). Vacio = NO DECLARADA, que es un tercer
    #: estado y no un sinonimo de «coincide».
    species: str = ""

    @property
    def family(self) -> str:
        return self.member.family

    @property
    def declared(self) -> bool:
        return bool(self.species)

    @property
    def borrowed(self) -> bool:
        """La lista es de OTRA especie declarada. El FAIL sigue siendo FAIL — y lo dice."""
        return self.declared and self.species != CORE_SPECIES

    @property
    def reason(self) -> str:
        texto = f"{self.name} casa con {self.member.label} del núcleo. {CORE_REASON}"
        if self.member.family == MIR30_FAMILY:
            texto += f" {MIR30_REASON}"
        if self.borrowed:
            texto += f" {BORROWED_LIST_WARNING}"
        elif not self.declared:
            texto += f" {UNDECLARED_SPECIES_WARNING}"
        return texto


def core_hits(names, *, species: str = "") -> tuple[CoreHit, ...]:
    """Que nombres de la lista caen en el nucleo. Sin fichero: no lo necesita.

    `species` es la especie del DISEÑO, no la del nombre del maduro. Si no es aquella
    para la que la lista esta autorizada, el veredicto sale igual —excluir por una lista
    prestada es defendible— pero MARCADO `LISTA_DE_OTRA_ESPECIE`: lo que no es
    defendible es no decirlo.
    """
    from .species import resolve

    slug = resolve(species).slug if species else species
    return tuple(
        CoreHit(name=nombre, member=miembro, species=slug)
        for nombre in names
        for miembro in CORE_ABUNDANT
        if miembro.matches(nombre)
    )


def _seed_of_mature(sequence: str, *, name: str, source: str) -> str:
    limpia = "".join(sequence.split()).upper().replace("U", "T")
    if len(limpia) < SEED_END:
        raise ShmirDesignError(
            f"{source}: el maduro {name} mide {len(limpia)} nt y la seed son las "
            f"posiciones {SEED_START}-{SEED_END}. Se aborta en vez de completar la "
            f"secuencia o saltarse la entrada en silencio."
        )
    return limpia[SEED_START - 1 : SEED_END]


def parse_mature_fa(
    text: str,
    *,
    source: str,
    version: str,
    checksum: str,
    prefixes: tuple[str, ...] = DEFAULT_PREFIXES,
) -> MatureSet:
    """Lee `mature.fa` de miRBase y saca la seed de cada maduro de las especies dadas."""
    _require_provenance(source, version, checksum, what="La tabla de maduros")
    if not text.strip():
        raise ShmirDesignError(
            f"{source}: el fichero de maduros está vacío; el filtro de colisión de seed "
            f"queda sin ejecutar."
        )

    seeds: dict[str, list[str]] = {}
    nombre: str | None = None
    partes: list[str] = []
    total = 0

    def cerrar() -> None:
        nonlocal nombre, partes, total
        if nombre is None:
            return
        # Sin prefijos declarados se indexa TODO el fichero: filtrar por especie es
        # cosa de quien pregunta, y un filtro aqui dejaria fuera del indice —sin
        # avisar— a las especies que no estuvieran en la lista.
        if not prefixes or any(nombre.startswith(p) for p in prefixes):
            seed = _seed_of_mature("".join(partes), name=nombre, source=source)
            seeds.setdefault(seed, []).append(nombre)
            total += 1
        nombre, partes = None, []

    for linea in text.splitlines():
        if linea.startswith(">"):
            cerrar()
            nombre = linea[1:].split()[0] if linea[1:].strip() else ""
            continue
        if nombre is not None:
            partes.append(linea.strip())
    cerrar()

    if not seeds:
        cuales = "/".join(prefixes) if prefixes else "ninguna especie"
        raise ShmirDesignError(
            f"{source}: no hay ni un maduro de {cuales} en el fichero. Se aborta en vez "
            f"de dar por limpia una guía contra una tabla vacía."
        )

    return MatureSet(
        seeds={s: tuple(n) for s, n in seeds.items()},
        source=source,
        version=version,
        checksum=checksum,
        prefixes=prefixes,
    )


def parse_abundance_list(
    text: str, *, source: str, version: str, checksum: str
) -> AbundanceList:
    """Lee la lista curada de miARN abundantes. Un nombre por linea, `#` es comentario."""
    _require_provenance(source, version, checksum, what="La lista de abundancia")
    referencia = umbral = ""
    for linea in text.splitlines():
        limpia = linea.strip()
        if not limpia.startswith("#"):
            continue
        etiqueta, _, valor = limpia.lstrip("#").strip().partition(":")
        if etiqueta.strip().lower() == "referencia":
            referencia = valor.strip()
        elif etiqueta.strip().lower() == "umbral":
            umbral = valor.strip()

    faltan = [
        nombre
        for nombre, valor in (("referencia", referencia), ("umbral", umbral))
        if not valor
    ]
    if faltan:
        return AbundanceList(
            names=frozenset(),
            source=source,
            version=version,
            checksum=checksum,
            reference=referencia,
            threshold=umbral,
            missing_reason=(
                f"a la cabecera le falta {' y '.join(faltan)}. La capa ampliada dice "
                f"«el resto de mmu- por encima de un umbral»: sin saber que umbral ni "
                f"de que dataset sale, un aviso de esta capa parece un veredicto y no "
                f"lo es. La capa queda NOT_RUN; el NÚCLEO sigue corriendo."
            ),
        )

    nombres = frozenset(
        linea.strip()
        for linea in text.splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    )
    if not nombres:
        raise ShmirDesignError(
            f"{source}: la lista de abundancia no tiene ningún nombre. Se aborta: una "
            f"lista vacía convertiria el nivel de aviso en un PASS silencioso."
        )
    return AbundanceList(
        names=nombres,
        source=source,
        version=version,
        checksum=checksum,
        reference=referencia,
        threshold=umbral,
    )


def _read(path: Path, *, what: str, expected_md5: str | None) -> tuple[str, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer {what} {path} ({exc}); el filtro de colisión de seed queda "
            f"sin ejecutar."
        ) from exc
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de usarlo para ningún veredicto."
        )
    try:
        return raw.decode("utf-8"), md5
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(f"{path}: no es UTF-8 ({exc}); se aborta.") from exc


def load_mature_fa(
    path: Path | str,
    *,
    version: str,
    expected_md5: str | None = None,
    prefixes: tuple[str, ...] = DEFAULT_PREFIXES,
) -> MatureSet:
    path = Path(path)
    texto, md5 = _read(path, what="el fichero de maduros", expected_md5=expected_md5)
    return parse_mature_fa(
        texto, source=str(path), version=version, checksum=md5, prefixes=prefixes
    )


def load_abundance_list(
    path: Path | str, *, version: str, expected_md5: str | None = None
) -> AbundanceList:
    path = Path(path)
    texto, md5 = _read(
        path, what="la lista de abundancia", expected_md5=expected_md5
    )
    return parse_abundance_list(texto, source=str(path), version=version, checksum=md5)


@dataclass(frozen=True)
class SeedCollisionResult:
    state: FilterState
    reason: str
    warnings: tuple[str, ...] = ()
    hits: tuple[str, ...] = ()
    abundant_hits: tuple[str, ...] = ()
    mature: MatureSet | None = None
    abundance: AbundanceList | None = None

    def as_filter(self) -> FilterResult:
        return FilterResult(name=FILTER_NAME, state=self.state, reason=self.reason)

    def format_text(self) -> str:
        lines = [f"Colisión de seed — {self.state.value}", f"  {self.reason}", ""]
        lines.append("  Procedencia:")
        lines.append(
            f"    maduros     {self.mature.provenance if self.mature else 'ausente'}"
        )
        lines.append(
            f"    abundancia  "
            f"{self.abundance.provenance if self.abundance else 'ausente (nivel FAIL en NOT_RUN)'}"
        )
        if self.warnings:
            lines.append("")
            lines.append("  Colisiones que NO descartan (miARN no marcados abundantes):")
            lines.extend(f"    {w}" for w in self.warnings)
        return "\n".join(lines)


def _seed_of(sequence: str, *, what: str) -> str:
    limpia = "".join(str(sequence).split()).upper().replace("U", "T")
    if len(limpia) < SEED_END:
        raise ValueError(
            f"La {what} mide {len(limpia)} nt y la seed son las posiciones {SEED_START}-"
            f"{SEED_END}; se aborta en vez de comparar media seed."
        )
    return limpia[SEED_START - 1 : SEED_END]


def filter_seed_collision(
    guide: str,
    mature: MatureSet | None,
    abundance: AbundanceList | None,
    passenger: str | None = None,
    *,
    species: str = "",
) -> SeedCollisionResult:
    """Colision de seed, en dos niveles. Sin maduros: NOT_RUN entero.

    La pasajera se mira POR SEPARADO y con la misma vara: si escapa del andamio, su
    seed reprime igual que la de la guia, y el origen queda marcado en cada colision.
    """
    if mature is None:
        return SeedCollisionResult(
            state=FilterState.NOT_RUN,
            reason=(
                "No hay tabla de maduros de miRBase cargada, así que no se puede saber "
                "si la seed de esta guía coincide con la de un miARN endogeno. NOT_RUN "
                "no es PASS."
            ),
        )

    sondas = [("guia", _seed_of(guide, what="guia"))]
    if passenger:
        sondas.append(("pasajera", _seed_of(passenger, what="pasajera")))

    for origen, seed in sondas:
        if "N" in seed:
            return SeedCollisionResult(
                state=FilterState.NOT_RUN,
                reason=(
                    f"La seed de la {origen} ({seed}) tiene una base desconocida: no se "
                    f"puede comparar con nada. NOT_RUN no es PASS."
                ),
                mature=mature,
                abundance=abundance,
            )

    seed = sondas[0][1]
    #: nombre del maduro → de que sonda vino la colision
    origenes: dict[str, list[str]] = {}
    for origen, sonda in sondas:
        for nombre in mature.names_for(sonda):
            origenes.setdefault(nombre, []).append(origen)
    colisiones = tuple(origenes)

    def etiqueta(nombre: str) -> str:
        return f"{nombre} (seed de la {'/'.join(origenes[nombre])})"
    contexto = (
        f" Contexto: hay {SEED_SPACE} 7-meros posibles y "
        f"{sum(len(n) for n in mature.seeds.values())} maduro(s) en la tabla, así que "
        f"una colisión por azar no es rara — por eso el FAIL solo lo da la lista curada "
        f"de abundantes."
    )
    procedencia = f" Maduros: {mature.provenance}."

    # CAPA 1 — el nucleo va en codigo y no necesita fichero: corre siempre.
    nucleo = core_hits(colisiones, species=species)
    if nucleo:
        de_30 = [h for h in nucleo if h.family == MIR30_FAMILY]
        aparte = (
            f" AVISO APARTE: {', '.join(h.name for h in de_30)} es de la familia del "
            f"ANDAMIO. {MIR30_REASON}"
            if de_30
            else ""
        )
        return SeedCollisionResult(
            state=FilterState.FAIL,
            reason=(
                f"Colisión con el NÚCLEO de abundantes en cerebro: "
                + "; ".join(f"{etiqueta(h.name)} → {h.member.label}" for h in nucleo)
                + f". {CORE_REASON}{aparte} {CORE_AUTHORIZATION}{procedencia}"
            ),
            warnings=tuple(
                etiqueta(n) for n in colisiones
                if n not in {h.name for h in nucleo}
            ),
            hits=colisiones,
            abundant_hits=tuple(h.name for h in nucleo),
            mature=mature,
            abundance=abundance,
        )

    # CAPA 2 — la ampliada, de fichero. Sin ella (o sin su cabecera) queda NOT_RUN.
    if abundance is None or not abundance.usable:
        detalle = (
            "No hay lista ampliada de abundancia cargada"
            if abundance is None
            else f"La lista ampliada no es utilizable: {abundance.missing_reason}"
        )
        avisos = tuple(etiqueta(n) for n in colisiones)
        return SeedCollisionResult(
            state=FilterState.NOT_RUN,
            reason=(
                f"{detalle}, así que la capa AMPLIADA del filtro no se puede ejecutar: "
                f"sin ella no se sabe cuales de las {len(colisiones)} colisión(es) "
                f"restantes están por encima del umbral. El NÚCLEO si ha corrido y no "
                f"hay ninguna colisión con el. NOT_RUN no es PASS.{procedencia}"
            ),
            warnings=avisos,
            hits=colisiones,
            mature=mature,
        )

    abundantes = tuple(n for n in colisiones if n in abundance.names)
    otros = tuple(n for n in colisiones if n not in abundance.names)
    avisos = tuple(etiqueta(n) for n in otros)

    if abundantes:
        return SeedCollisionResult(
            state=FilterState.FAIL,
            reason=(
                f"Colisión con {', '.join(etiqueta(n) for n in abundantes)}, "
                f"marcado(s) abundante(s) en cerebro. Eso no produce off-targets "
                f"dispersos: reprime su red de dianas entera. Abundancia: "
                f"{abundance.provenance}.{procedencia}"
            ),
            warnings=avisos,
            hits=colisiones,
            abundant_hits=abundantes,
            mature=mature,
            abundance=abundance,
        )

    if otros:
        return SeedCollisionResult(
            state=FilterState.PASS,
            reason=(
                f"Colisión con {len(otros)} miARN anotado(s) que no "
                f"están en la lista de abundantes en cerebro: se listan y no "
                f"descartan.{contexto}{procedencia}"
            ),
            warnings=avisos,
            hits=colisiones,
            mature=mature,
            abundance=abundance,
        )

    return SeedCollisionResult(
        state=FilterState.PASS,
        reason=(
            f"Ni la seed de la guía ({seed}) ni la de la pasajera coinciden con la de "
            f"ningún maduro de la tabla."
            if passenger
            else f"La seed {seed} de la guía no coincide con la de ningún maduro de la "
            f"tabla."
            f"{procedencia}"
        ),
        mature=mature,
        abundance=abundance,
    )
