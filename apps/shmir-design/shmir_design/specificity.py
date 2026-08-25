"""Especificidad: sitios fuera del gen diana (paso 12).

Motor primario: **escaneo exhaustivo local** sobre una base de RefSeq RNA de la especie,
descargada a mano y versionada con su checksum (ver `docs/fixtures.md`). Enumera todos
los sitios con 0, 1 y 2 desapareamientos.

Veredicto:

  FAIL     hay algun sitio de 0 o 1 desapareamiento FUERA del gen diana
  PASS     no lo hay; si hay sitios de 2, salen listados como aviso en el motivo
  NOT_RUN  no hay base de datos cargada. **NOT_RUN no es PASS**: un fallo de red, un
           timeout o una base ausente jamas se convierten en PASS

## Orientacion (el error de lectura facil de cometer)

Un ARNm solo es diana si contiene el **complemento inverso** de la guia. Por eso se
busca `reverse_complement(query)` en cada transcrito: eso es un hit ANTISENTIDO y es un
off-target de verdad. Un hit en la MISMA orientacion que la guia no lo es, y aqui se
busca aparte, se cuenta aparte y **no entra en el veredicto**; el motivo del filtro dice
cuantos se han descartado por eso.

## Guia y pasajera por separado

Son dos especies distintas con off-targets distintos. Se escanean por separado y los
hits se deduplican por (transcrito, posicion, hebra), marcando de cual vienen.

## Exhaustividad del escaneo

Con 22 nt y como mucho 2 desapareamientos, si se parte la sonda en 3 bloques al menos
uno casa exacto (principio del palomar). Se buscan los tres bloques con `str.find` y
solo se verifican esas posiciones candidatas, contando desapareamientos. No hay falsos
negativos: el resultado es el mismo que comparar posicion a posicion, pero sin recorrer
la base entera nucleotido a nucleotido en Python.

La `N` nunca casa: una base desconocida no confirma ni descarta un off-target.

## Lo que este filtro NO resuelve

Los off-targets **mediados por seed**. La seed de la guia 1018 es `TTAGTAC` y su sitio
complementario `GTACTAA` aparece por azar cada ~16 kb: hay miles en el transcriptoma y
**ningun alineador los devuelve**, porque no son alineamientos, son coincidencias de 7
nt. Eso es un filtro aparte —contar sitios 7mer-m8/8mer en 3'UTR ponderados por
expresion cerebral, o usar siSPOTR/POTS— y es el hueco mas importante que queda. El
filtro `seed` de `seeds.py`, hoy en NOT_RUN, es justo eso.

## Motor secundario (BLAST remoto)

Solo inspeccion, nunca fuente del veredicto: `blast_command()` genera la orden exacta
para pegarla, con el taxid de la especie. Respeta la etiqueta de NCBI (una sumision cada
~10 s, polling >= 60 s) y se pasa solo a los candidatos que sobrevivan al filtro
exhaustivo. Este modulo no lo lanza: no hay endpoint verificado desde el proyecto
(regla 4) y el veredicto no depende de el.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import InvalidSequenceError, ShmirDesignError
from .filters import FilterResult, FilterState

MAX_MISMATCHES = 2
BLOCKS = MAX_MISMATCHES + 1          # principio del palomar
DNA_BASES = frozenset("ACGT")
COMPLEMENT = str.maketrans("ACGTN", "TGCAN")

#: Taxones para el BLAST remoto de inspeccion.
TAXIDS = {"raton": "txid10090", "humano": "txid9606"}
NCBI_SUBMISSION_INTERVAL_S = 10
NCBI_POLL_INTERVAL_S = 60

SEED_CAVEAT = (
    "Este filtro NO cubre los off-targets mediados por seed: un sitio complementario "
    "a las posiciones 2-8 aparece por azar cada ~16 kb, hay miles en el transcriptoma "
    "y ningun alineador los devuelve. Eso se cuenta aparte (sitios 7mer-m8/8mer en "
    "3'UTR ponderados por expresion cerebral, o siSPOTR/POTS) y es el hueco mas "
    "importante que queda abierto."
)


class Strand(StrEnum):
    ANTISENSE = "antisentido"
    SENSE = "sentido"


def reverse_complement(sequence: str) -> str:
    cleaned = "".join(str(sequence).split()).upper()
    for index, base in enumerate(cleaned, start=1):
        if base not in DNA_BASES:
            raise InvalidSequenceError(
                f"Caracter {base!r} no valido en la posicion {index} de la sonda "
                f"(se esperaba A, C, G o T); se aborta el escaneo de especificidad."
            )
    return cleaned.translate(COMPLEMENT)[::-1]


@dataclass(frozen=True)
class Hit:
    transcript: str
    start: int                 # 1-based sobre el transcrito
    end: int
    mismatches: int
    strand: Strand
    queries: tuple[str, ...] = ()

    def describe(self) -> str:
        origen = "+".join(self.queries) if self.queries else "?"
        return (
            f"{self.transcript}:{self.start}-{self.end} "
            f"({self.mismatches} desapareamiento(s), {self.strand.value}, {origen})"
        )


@dataclass(frozen=True)
class SpecificityDatabase:
    """Base local de transcritos, con su procedencia. Sin procedencia no vale."""

    name: str
    version: str
    checksum: str
    records: dict[str, str]

    def __post_init__(self) -> None:
        for campo, valor in (
            ("name", self.name),
            ("version", self.version),
            ("checksum", self.checksum),
        ):
            if not valor or not str(valor).strip():
                raise ValueError(
                    f"La base de especificidad necesita {campo}: sin procedencia el "
                    f"veredicto no es auditable y no vale. Se aborta."
                )
        if not self.records:
            raise ShmirDesignError(
                f"La base {self.name!r} no tiene ningun transcrito; se aborta en vez de "
                f"dar por especifica una guia contra una base vacia."
            )

    @property
    def provenance(self) -> str:
        return (
            f"{self.name}, version {self.version}, checksum {self.checksum}, "
            f"{len(self.records)} transcrito(s)"
        )


def _count_mismatches(pattern: str, window: str, limit: int) -> int | None:
    """Desapareamientos, o None si pasan del limite o hay una base desconocida."""
    total = 0
    for a, b in zip(pattern, window):
        if b == "N" or a == "N":
            return None
        if a != b:
            total += 1
            if total > limit:
                return None
    return total


def _scan_one(pattern: str, transcript: str, sequence: str, strand: Strand) -> list[Hit]:
    """Todas las posiciones donde `pattern` casa con <= MAX_MISMATCHES."""
    largo = len(pattern)
    if largo < BLOCKS or len(sequence) < largo:
        return []

    corte = largo // BLOCKS
    bloques = [
        (indice * corte, pattern[indice * corte : (indice + 1) * corte])
        if indice < BLOCKS - 1
        else ((BLOCKS - 1) * corte, pattern[(BLOCKS - 1) * corte :])
        for indice in range(BLOCKS)
    ]

    candidatas: set[int] = set()
    for offset, bloque in bloques:
        if "N" in bloque:
            continue
        desde = 0
        while True:
            encontrado = sequence.find(bloque, desde)
            if encontrado == -1:
                break
            inicio = encontrado - offset
            if 0 <= inicio <= len(sequence) - largo:
                candidatas.add(inicio)
            desde = encontrado + 1

    hits: list[Hit] = []
    for inicio in sorted(candidatas):
        fallos = _count_mismatches(
            pattern, sequence[inicio : inicio + largo], MAX_MISMATCHES
        )
        if fallos is not None:
            hits.append(
                Hit(
                    transcript=transcript,
                    start=inicio + 1,
                    end=inicio + largo,
                    mismatches=fallos,
                    strand=strand,
                )
            )
    return hits


def scan_database(query: str, database: SpecificityDatabase) -> list[Hit]:
    """Escanea la base entera. Antisentido = off-target real; sentido = no lo es."""
    antisentido = reverse_complement(query)
    sentido = "".join(str(query).split()).upper()

    hits: list[Hit] = []
    for transcript, sequence in database.records.items():
        limpia = "".join(str(sequence).split()).upper()
        hits.extend(_scan_one(antisentido, transcript, limpia, Strand.ANTISENSE))
        hits.extend(_scan_one(sentido, transcript, limpia, Strand.SENSE))
    return sorted(hits, key=lambda h: (h.transcript, h.start, h.strand))


@dataclass(frozen=True)
class SpecificityResult:
    state: FilterState
    reason: str
    hits: tuple[Hit, ...] = ()
    sense_hits: tuple[Hit, ...] = ()
    database: SpecificityDatabase | None = None
    query_length: int = 0

    def as_filter(self) -> FilterResult:
        return FilterResult(name="especificidad", state=self.state, reason=self.reason)

    def format_text(self) -> str:
        lines = [f"Especificidad — {self.state.value}", f"  {self.reason}", ""]
        if self.database is not None:
            lines.extend(
                [
                    "  Procedencia y parametros:",
                    f"    base            {self.database.provenance}",
                    f"    sonda           {self.query_length} nt "
                    f"(guia y pasajera por separado)",
                    f"    desapareamientos hasta {MAX_MISMATCHES} desapareamientos, "
                    f"escaneo exhaustivo local",
                    f"    orientacion     solo cuentan los hits antisentido "
                    f"(el mRNA contiene el complemento inverso de la sonda)",
                    "",
                ]
            )
        if self.hits:
            lines.append("  Sitios antisentido:")
            lines.extend(f"    {h.describe()}" for h in self.hits)
            lines.append("")
        if self.sense_hits:
            lines.append(
                f"  Descartados por orientacion (misma hebra que la sonda, NO son "
                f"off-targets): {len(self.sense_hits)}"
            )
            lines.append("")
        lines.append(f"  ⚠  {SEED_CAVEAT}")
        return "\n".join(lines)


def _dedupe(hits: list[tuple[str, Hit]]) -> list[Hit]:
    agrupados: dict[tuple[str, int, int, Strand], list[str]] = {}
    detalle: dict[tuple[str, int, int, Strand], Hit] = {}
    for origen, hit in hits:
        clave = (hit.transcript, hit.start, hit.end, hit.strand)
        agrupados.setdefault(clave, []).append(origen)
        anterior = detalle.get(clave)
        if anterior is None or hit.mismatches < anterior.mismatches:
            detalle[clave] = hit
    return [
        Hit(
            transcript=hit.transcript,
            start=hit.start,
            end=hit.end,
            mismatches=hit.mismatches,
            strand=hit.strand,
            queries=tuple(dict.fromkeys(agrupados[clave])),
        )
        for clave, hit in sorted(detalle.items(), key=lambda item: item[0][:3])
    ]


def filter_specificity(
    guide: str,
    passenger: str | None,
    database: SpecificityDatabase | None,
    *,
    target: str,
) -> SpecificityResult:
    """Filtro de especificidad. Sin base de datos: NOT_RUN, nunca PASS."""
    if database is None:
        return SpecificityResult(
            state=FilterState.NOT_RUN,
            reason=(
                "No hay base de RefSeq RNA cargada, asi que el filtro de especificidad "
                "no se ejecuta. NOT_RUN no es PASS: un fallo de red, un timeout o una "
                f"base ausente nunca se convierten en PASS. {SEED_CAVEAT}"
            ),
        )
    if not target or not target.strip():
        raise ValueError(
            "Hay que declarar el gen diana: sin el, todo sitio parece un off-target y "
            "el filtro no significa nada. Se aborta."
        )

    crudos: list[tuple[str, Hit]] = []
    for origen, sonda in (("guia", guide), ("pasajera", passenger)):
        if sonda:
            crudos.extend((origen, hit) for hit in scan_database(sonda, database))

    todos = _dedupe(crudos)
    antisentido = [h for h in todos if h.strand is Strand.ANTISENSE]
    sentido = [h for h in todos if h.strand is Strand.SENSE]
    fuera = [h for h in antisentido if h.transcript != target]
    graves = [h for h in fuera if h.mismatches <= 1]
    leves = [h for h in fuera if h.mismatches == 2]

    orientacion = (
        f" Descartados {len(sentido)} hit(s) en orientacion SENTIDO (misma hebra que "
        f"la sonda): no son off-targets de la guia."
        if sentido
        else ""
    )
    procedencia = f" Base: {database.provenance}."

    if graves:
        detalle = "; ".join(h.describe() for h in graves)
        return SpecificityResult(
            state=FilterState.FAIL,
            reason=(
                f"{len(graves)} sitio(s) de 0 o 1 desapareamiento fuera de {target}: "
                f"{detalle}.{orientacion}{procedencia}"
            ),
            hits=tuple(antisentido),
            sense_hits=tuple(sentido),
            database=database,
            query_length=len(guide),
        )

    aviso = (
        f" AVISO: {len(leves)} sitio(s) con 2 desapareamientos fuera de {target}: "
        + "; ".join(h.describe() for h in leves)
        + "."
        if leves
        else ""
    )
    return SpecificityResult(
        state=FilterState.PASS,
        reason=(
            f"Sin sitios de 0 o 1 desapareamiento fuera de {target}."
            f"{aviso}{orientacion}{procedencia}"
        ),
        hits=tuple(antisentido),
        sense_hits=tuple(sentido),
        database=database,
        query_length=len(guide),
    )


def blast_command(query_fasta: str, species: str) -> str:
    """Orden exacta del BLAST remoto de inspeccion. Este modulo NO la lanza."""
    if species not in TAXIDS:
        raise ValueError(
            f"Especie {species!r} sin taxid declarado; conocidas: "
            f"{', '.join(sorted(TAXIDS))}. Se aborta en vez de inventar un taxid."
        )
    return (
        f'blastn -task blastn-short -db refseq_rna -remote '
        f'-entrez_query "{TAXIDS[species]}[ORGN]" -query {query_fasta}'
    )


def load_database(
    path: Path | str,
    *,
    name: str,
    version: str,
    expected_md5: str | None = None,
) -> SpecificityDatabase:
    """Carga un FASTA multi-registro de RefSeq RNA y anota su procedencia.

    Si se declara `expected_md5` y no cuadra, ABORTA: una base que no es la que dice
    ser invalida cualquier veredicto de especificidad.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise ShmirDesignError(
            f"No existe la base de especificidad {path}; se aborta. Sin base, el filtro "
            f"queda en NOT_RUN, pero no se puede fingir que se ha cargado una."
        ) from exc
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer la base de especificidad {path} ({exc}); se aborta."
        ) from exc

    checksum = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 and checksum != expected_md5:
        raise ShmirDesignError(
            f"{path}: md5 {checksum} y se esperaba {expected_md5}. La base NO es la que "
            f"dice ser; PARA, porque el veredicto de especificidad no valdria nada."
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(
            f"{path} no es UTF-8 valido ({exc}); se aborta la carga."
        ) from exc

    records: dict[str, str] = {}
    identificador: str | None = None
    trozos: list[str] = []
    for numero, linea in enumerate(text.splitlines(), start=1):
        if linea.startswith(">"):
            if identificador is not None:
                records[identificador] = "".join(trozos)
            identificador = linea[1:].split()[0] if linea[1:].split() else ""
            if not identificador:
                raise ShmirDesignError(
                    f"{path}, linea {numero}: cabecera sin identificador; se aborta."
                )
            if identificador in records:
                raise ShmirDesignError(
                    f"{path}, linea {numero}: el identificador {identificador} esta "
                    f"repetido; se aborta en vez de quedarse con uno de los dos."
                )
            trozos = []
        elif linea.strip():
            if identificador is None:
                raise ShmirDesignError(
                    f"{path}, linea {numero}: secuencia antes de la primera cabecera; "
                    f"no es un FASTA valido y se aborta."
                )
            trozos.append(linea.strip().upper())
    if identificador is not None:
        records[identificador] = "".join(trozos)

    return SpecificityDatabase(
        name=name, version=version, checksum=checksum, records=records
    )


# ─── El transgen terapeutico como segunda base (bloque 10) ───────────────────

TRANSGENE_FILTER_NAME = "transgen"

TRANSGENE_CAVEAT = (
    "En el casete no hay gen diana que excluir: cualquier sitio es malo. Un candidato "
    "que silencia el transgen produce un fallo silencioso — knockdown global bonito y "
    "ningun beneficio en el ratio — porque apaga la misma proteina que se quiere "
    "expresar."
)

TRANSGENE_ORIENTATION_NOTE = (
    "El FASTA del casete se lee como la hebra sentido de lo que se transcribe, asi que "
    "el sitio que cuenta es el ANTISENTIDO, igual que contra el transcriptoma. Los hits "
    "en sentido se cuentan y se listan, pero no condenan. En los tramos no transcritos "
    "(ITR, promotor) la orientacion no significa lo mismo: ahi el hit es una "
    "coincidencia que hay que mirar a mano, no un veredicto."
)


@dataclass(frozen=True)
class TransgeneResult:
    """Resultado del filtro contra el casete AAV completo."""

    state: FilterState
    reason: str
    hits: tuple[Hit, ...] = ()
    sense_hits: tuple[Hit, ...] = ()
    warnings: tuple[str, ...] = ()
    database: SpecificityDatabase | None = None
    query_length: int = 0

    def as_filter(self) -> FilterResult:
        return FilterResult(
            name=TRANSGENE_FILTER_NAME, state=self.state, reason=self.reason
        )

    def format_text(self) -> str:
        lines = [f"Transgen — {self.state.value}", f"  {self.reason}", ""]
        if self.database is not None:
            lines.extend(
                [
                    "  Procedencia y parametros:",
                    f"    casete          {self.database.provenance}",
                    f"    sonda           {self.query_length} nt "
                    f"(guia y pasajera por separado)",
                    f"    desapareamientos hasta {MAX_MISMATCHES}, escaneo exhaustivo "
                    f"local (principio del palomar, {BLOCKS} bloques)",
                    f"    veredicto       FAIL con 0 o 1; con 2, aviso y lista",
                    "",
                ]
            )
        if self.hits:
            lines.append("  Sitios antisentido en el casete:")
            lines.extend(f"    {h.describe()}" for h in self.hits)
            lines.append("")
        if self.sense_hits:
            lines.append(
                f"  Descartados por orientacion (misma hebra que la sonda): "
                f"{len(self.sense_hits)}"
            )
            lines.extend(f"    {h.describe()}" for h in self.sense_hits)
            lines.append("")
        lines.append(f"  ⚠  {TRANSGENE_CAVEAT}")
        lines.append(f"  ⚠  {TRANSGENE_ORIENTATION_NOTE}")
        return "\n".join(lines)


def filter_transgene(
    guide: str,
    passenger: str | None,
    cassette: SpecificityDatabase | None,
) -> TransgeneResult:
    """¿La guia o la pasajera apagan el propio transgen? Sin casete: NOT_RUN.

    Misma maquinaria que `filter_specificity` —mismo escaneo exhaustivo, misma
    deduplicacion, mismo chequeo de orientacion— con dos diferencias: aqui no hay gen
    diana que excluir, y el umbral es mas duro, porque un solo desapareamiento basta
    para silenciar el transgen casi igual que la diana perfecta.
    """
    if cassette is None:
        return TransgeneResult(
            state=FilterState.NOT_RUN,
            reason=(
                "No hay casete del transgen cargado, asi que el filtro contra el "
                "transgen no se ejecuta y queda sin comprobar si el candidato apaga la "
                "propia construccion terapeutica. NOT_RUN no es PASS: una base ausente "
                "nunca se convierte en PASS."
            ),
        )

    for nombre, sonda in (("guia", guide), ("pasajera", passenger)):
        if sonda is None:
            continue
        if not sonda.strip():
            raise ValueError(
                f"La {nombre} esta vacia: no se puede escanear el casete con una sonda "
                f"que no existe. Se aborta en vez de dar el filtro por superado."
            )

    crudos: list[tuple[str, Hit]] = []
    for origen, sonda in (("guia", guide), ("pasajera", passenger)):
        if sonda:
            crudos.extend((origen, hit) for hit in scan_database(sonda, cassette))

    todos = _dedupe(crudos)
    antisentido = [h for h in todos if h.strand is Strand.ANTISENSE]
    sentido = [h for h in todos if h.strand is Strand.SENSE]
    graves = [h for h in antisentido if h.mismatches <= 1]
    leves = [h for h in antisentido if h.mismatches == 2]

    avisos = tuple(
        f"{h.describe()} — 2 desapareamiento(s) contra el casete: mirar a mano."
        for h in leves
    )
    orientacion = (
        f" Descartados {len(sentido)} hit(s) en orientacion SENTIDO."
        if sentido
        else ""
    )
    procedencia = f" Casete: {cassette.provenance}."

    if graves:
        detalle = "; ".join(h.describe() for h in graves)
        return TransgeneResult(
            state=FilterState.FAIL,
            reason=(
                f"{len(graves)} sitio(s) de 0 o 1 desapareamiento en el casete del "
                f"transgen: {detalle}. Este candidato apagaria la construccion que se "
                f"quiere expresar.{orientacion}{procedencia}"
            ),
            hits=tuple(antisentido),
            sense_hits=tuple(sentido),
            warnings=avisos,
            database=cassette,
            query_length=len(guide),
        )

    aviso = (
        f" AVISO: {len(leves)} sitio(s) con 2 desapareamientos en el casete: "
        + "; ".join(h.describe() for h in leves)
        + "."
        if leves
        else ""
    )
    return TransgeneResult(
        state=FilterState.PASS,
        reason=(
            f"Sin sitios de 0 ni 1 desapareamiento en el casete del transgen."
            f"{aviso}{orientacion}{procedencia}"
        ),
        hits=tuple(antisentido),
        sense_hits=tuple(sentido),
        warnings=avisos,
        database=cassette,
        query_length=len(guide),
    )
