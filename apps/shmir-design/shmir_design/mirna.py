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

Sin fichero de abundancia el nivel FAIL queda NOT_RUN y el WARN corre igual. **No hay
ninguna lista escrita en el codigo**, ni de maduros ni de abundancia: inventarla seria
la regla 1 por otra puerta, y ademas un FAIL duro apoyado en una lista sin procedencia
no es auditable. Un test comprueba sobre el propio fuente que aqui no hay nombres.

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
DEFAULT_PREFIXES = ("mmu-", "hsa-")

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
            f"{self.source}, version {self.version}, checksum {self.checksum}, "
            f"{sum(len(n) for n in self.seeds.values())} maduro(s) "
            f"({'/'.join(self.prefixes)}), {len(self.seeds)} seed(s) distintas"
        )

    def names_for(self, seed: str) -> tuple[str, ...]:
        return self.seeds.get(seed.upper(), ())


@dataclass(frozen=True)
class AbundanceList:
    """miARN abundantes en el tejido. Es la unica fuente del nivel FAIL."""

    names: frozenset[str]
    source: str
    version: str
    checksum: str

    @property
    def provenance(self) -> str:
        return (
            f"{self.source}, version {self.version}, checksum {self.checksum}, "
            f"{len(self.names)} miARN"
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
            f"{source}: el fichero de maduros esta vacio; el filtro de colision de seed "
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
        if any(nombre.startswith(p) for p in prefixes):
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
        raise ShmirDesignError(
            f"{source}: no hay ni un maduro de {'/'.join(prefixes)} en el fichero. Se "
            f"aborta en vez de dar por limpia una guia contra una tabla vacia."
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
    nombres = frozenset(
        linea.strip()
        for linea in text.splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    )
    if not nombres:
        raise ShmirDesignError(
            f"{source}: la lista de abundancia no tiene ningun nombre. Se aborta: una "
            f"lista vacia convertiria el nivel FAIL en un PASS silencioso."
        )
    return AbundanceList(
        names=nombres, source=source, version=version, checksum=checksum
    )


def _read(path: Path, *, what: str, expected_md5: str | None) -> tuple[str, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer {what} {path} ({exc}); el filtro de colision de seed queda "
            f"sin ejecutar."
        ) from exc
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de usarlo para ningun veredicto."
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
        lines = [f"Colision de seed — {self.state.value}", f"  {self.reason}", ""]
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
) -> SeedCollisionResult:
    """Colision de seed, en dos niveles. Sin maduros: NOT_RUN entero.

    La pasajera se mira POR SEPARADO y con la misma vara: si escapa del andamio, su
    seed reprime igual que la de la guia, y el origen queda marcado en cada colision.
    """
    if mature is None:
        return SeedCollisionResult(
            state=FilterState.NOT_RUN,
            reason=(
                "No hay tabla de maduros de miRBase cargada, asi que no se puede saber "
                "si la seed de esta guia coincide con la de un miARN endogeno. NOT_RUN "
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
        f"{sum(len(n) for n in mature.seeds.values())} maduro(s) en la tabla, asi que "
        f"una colision por azar no es rara — por eso el FAIL solo lo da la lista curada "
        f"de abundantes."
    )
    procedencia = f" Maduros: {mature.provenance}."

    if abundance is None:
        avisos = tuple(etiqueta(n) for n in colisiones)
        return SeedCollisionResult(
            state=FilterState.NOT_RUN,
            reason=(
                f"No hay lista de abundancia en cerebro cargada, asi que el nivel FAIL "
                f"del filtro no se puede ejecutar: sin ella no se sabe cuales de las "
                f"{len(colisiones)} colision(es) importan. El nivel de aviso si ha "
                f"corrido y las lista. NOT_RUN no es PASS.{procedencia}"
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
                f"Colision con {', '.join(etiqueta(n) for n in abundantes)}, "
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
                f"Colision con {len(otros)} miARN anotado(s) que no "
                f"estan en la lista de abundantes en cerebro: se listan y no "
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
            f"Ni la seed de la guia ({seed}) ni la de la pasajera coinciden con la de "
            f"ningun maduro de la tabla."
            if passenger
            else f"La seed {seed} de la guia no coincide con la de ningun maduro de la "
            f"tabla."
            f"{procedencia}"
        ),
        mature=mature,
        abundance=abundance,
    )
