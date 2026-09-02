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
#:
#: **NO es una lista blanca.** Lo era, y con ella el frente estaba cerrado a raton y
#: humano por una razon que no es del frente: cualquier especie con taxid DECLARADO
#: puede correr. El unico origen de estos valores es `species.resolve()`, que no los
#: deduce del nombre; este diccionario queda como ATAJO de compatibilidad para los dos
#: nombres castellanos que el proyecto ya usaba, y `taxid_for()` es lo que manda.
TAXIDS = {"raton": "txid10090", "humano": "txid9606"}
NCBI_SUBMISSION_INTERVAL_S = 10
NCBI_POLL_INTERVAL_S = 60

SEED_CAVEAT = (
    "Este filtro NO cubre los off-targets mediados por seed: un sitio complementario "
    "a las posiciones 2-8 aparece por azar cada ~16 kb, hay miles en el transcriptoma "
    "y ningún alineador los devuelve. Eso se cuenta aparte (sitios 7mer-m8/8mer en "
    "3'UTR ponderados por expresión cerebral, o siSPOTR/POTS) y es el hueco más "
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
                f"Caracter {base!r} no válido en la posición {index} de la sonda "
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

    @property
    def antisense(self) -> bool:
        """En ESTE escaner, «la sonda puede aparearse con este transcrito».

        OJO: NO es la misma cantidad que el signo de `sstart`→`send` de `-outfmt 6`,
        aunque coincidan para una guia. Aqui lo pone nuestro escaner segun haya casado el
        complemento inverso de la sonda o la sonda tal cual; alli es la hebra del sujeto
        tal como esta depositado. Confundirlas es la errata nº 57.
        """
        return self.strand is Strand.ANTISENSE

    @property
    def aligned(self) -> int:
        """Siempre la sonda ENTERA: `_scan_one` casa ventanas de `len(pattern)`.

        Por eso este lado nunca tuvo el fallo de los parciales — y por eso el supuesto no
        viajo con el criterio cuando se llevo a la corrida de BLAST.

        La longitud se le PIDE a `Span`, que es quien la deriva: restarla aqui a mano
        seria el sitio 24 de la formula que el trinquete de `data/magnitudes.toml` tiene
        marcada como PRIORITARIA, y ese techo solo puede bajar.
        """
        from .audit import Span  # noqa: PLC0415

        return Span(self.start, self.end).length

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
                f"La base {self.name!r} no tiene ningún transcrito; se aborta en vez de "
                f"dar por específica una guía contra una base vacía."
            )

    @property
    def provenance(self) -> str:
        return (
            f"{self.name}, versión {self.version}, checksum {self.checksum}, "
            f"{len(self.records)} transcrito(s)"
        )


def _count_mismatches(pattern: str, window: str, limit: int) -> int | None:
    """Desapareamientos, o None si pasan del limite o hay una base desconocida."""
    total = 0
    # Una ventana mas corta que el patron contaria MENOS desapareamientos, o sea
    # un impacto que parece mejor de lo que es — y de ahi sale un veredicto de
    # especificidad. El unico llamador recorta a `largo` exacto; esto lo exige.
    for a, b in zip(pattern, window, strict=True):
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
                    "  Procedencia y parámetros:",
                    f"    base            {self.database.provenance}",
                    f"    sonda           {self.query_length} nt "
                    f"(guía y pasajera por separado)",
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


# ─── EL CRITERIO, EN UN SOLO SITIO ──────────────────────────────────────────────
#
# HABIA DOS IMPLEMENTACIONES DEL MISMO FRENTE con criterios distintos, y la que daba el
# veredicto de la corrida SUBIDA era la que NO tenia el concepto de diana (errata nº 56).
# Las tres diferencias, medidas:
#
#   · `filter_specificity` descarta los hits en SENTIDO —«un hit en la misma orientacion
#     que la sonda no es un off-target»— y `BlastRun.verdict` no miraba la orientacion;
#   · `filter_specificity` exige `target` y ABORTA sin el; `verdict` no miraba `subject`
#     siquiera, comprobado sobre su bytecode;
#   · `filter_specificity` falla con CUALQUIER acierto grave fuera de la diana; `verdict`
#     fallaba con MAS DE UNO.
#
# El coste ya se habia materializado: diez `FAIL` falsos, uno por candidato, porque la
# diana tiene dos variantes de transcrito y las dos aciertan.
#
# Asi que el criterio vive aqui y las dos lo LLAMAN. No se arreglan por separado: eso es
# lo que produce el cuarto par duplicado del proyecto.


@dataclass(frozen=True)
class SpecificityCall:
    """Lo que dice el criterio, sin prosa: los dos lados lo visten a su manera."""

    state: FilterState
    graves: tuple = ()
    leves: tuple = ()
    exentos: tuple = ()
    #: Aciertos descartados por ser PARCIALES. Ver `WHY_LENGTH_AND_NOT_MISMATCHES`.
    parciales: int = 0
    #: Ningun acierto contra la propia diana. Ver `NO_TARGET_HIT_NOTE`.
    sin_diana: bool = False
    #: Aciertos contra la propia diana con la orientacion que esa hebra NO puede dar.
    #: Ver `EXPECTED_ORIENTATION`: es una comprobacion, no un descarte.
    orientacion_rara: tuple = ()


#: `ALLOWED_TRUNCATION` es lo unico que se le perdona a un alineamiento para seguir
#: contando: un extremo recortado. El minimo NO se escribe —seria un `21` con el supuesto
#: «la sonda mide 22» metido dentro, que es la errata nº 56 exacta— sino que se DERIVA de
#: la sonda de cada consulta (principio nº 13).
ALLOWED_TRUNCATION = 1


#: LA COLUMNA `mismatch` DE `-outfmt 6` NO DICE QUE EL ACIERTO SEA PERFECTO: dice que es
#: perfecto EN EL SEGMENTO QUE ALINEO. Un parcial de 13 nt clavado trae `mismatches = 0`,
#: y con `blastn-short`, `word_size 7` y `evalue 1000` la corrida esta llena de ellos.
#: Sin mirar la longitud, ese ruido entraba como acierto grave y tumbaba el panel entero
#: (errata nº 57).
#:
#: POR QUE `filter_specificity` NO LO TENIA aunque comparta el criterio: su escaner casa
#: ventanas de EXACTAMENTE `len(sonda)`, asi que todos sus hits son de longitud completa
#: y la condicion se cumplia sola. Al mover el criterio a la corrida de BLAST —que
#: devuelve alineamientos LOCALES— no viajo el supuesto que lo sostenia.
WHY_LENGTH_AND_NOT_MISMATCHES = (
    "Un acierto cuenta si alinea casi la sonda ENTERA: `mismatch` de `-outfmt 6` sólo "
    "cuenta desapareamientos dentro del segmento alineado, así que un parcial de 13 nt "
    "clavado trae 0 y no es un off-target."
)


#: LA ORIENTACION ES LA FIRMA DE QUE HEBRA ES, NO UN FILTRO. Correccion del responsable
#: del proyecto (2026-09-02), y da un invariante mas fuerte que descartar:
#:
#:   guia      → ANTISENTIDO contra su diana (el mRNA lleva su complemento inverso);
#:   pasajera  → SENTIDO (lleva la misma secuencia que el blanco).
#:
#: Descartar los hits en sentido tiraba, en la PASAJERA, su acierto legitimo contra la
#: propia diana — y con el la exencion de variantes, que no llegaba a aplicarse. Como
#: comprobacion en cambio caza algo que ningun otro guardia ve: una guia cuyo acierto
#: contra su diana salga en sentido esta MAL MONTADA (guia y pasajera intercambiadas).
EXPECTED_ORIENTATION = {"guia": True, "pasajera": False}

WRONG_ORIENTATION_NOTE = (
    "OJO: el acierto contra la propia diana sale con la ORIENTACIÓN que esta hebra no "
    "puede dar. Una guía es antisentido a su blanco por definición y una pasajera lleva "
    "su misma secuencia, así que esto no es un off-target: es que la construcción está "
    "MAL MONTADA —guía y pasajera intercambiadas, o el FASTA de consulta montado al "
    "revés—. No cambia el veredicto de este frente, que mide otra cosa. Y NO ES UN "
    "PROBLEMA DE ESTE CANDIDATO: es un fallo de CONSTRUCCIÓN, así que se arregla "
    "rehaciendo el FASTA de consulta y volviendo a correr, no cambiando de candidato — "
    "el que hay puede estar perfectamente bien y no se sabrá hasta rehacerlo."
)


#: EL SUPUESTO QUE ESTABA ESCONDIDO EN UN NUMERO. `verdict` fallaba con «mas de un»
#: acierto grave, y ese `> 1` significaba «uno es tuyo» — un supuesto sobre los datos que
#: no estaba escrito en ninguna parte. Falla en DOS direcciones y las dos son invisibles:
#: con dos variantes del gen cuenta la segunda como off-target (lo que paso), y con una
#: guia que NO acierta a su propia diana da PASS a algo que quiza no reconoce su blanco.
#:
#: El criterio ya no lleva ningun supuesto dentro: la diana se DECLARA y el umbral es
#: «ningun acierto grave fuera de ella», que es lo que dice que es.
WHY_NOT_MORE_THAN_ONE = (
    "El criterio NO es «más de un acierto»: ese umbral escondía el supuesto de que la "
    "diana produce exactamente UN acierto, y con dos variantes del mismo gen contaba la "
    "segunda como off-target. La diana se declara y el umbral es «ningún acierto grave "
    "fuera de ella»."
)

#: Que no haya NINGUN acierto contra la propia diana no es un off-target y no veta: es
#: informacion sobre la CORRIDA. Se dice porque el umbral viejo la daba por buena en
#: silencio — una guia que no reconoce su blanco salia `PASS` por no tener con que
#: compararse. Que funcione o no es el frente de POTENCIA, que este software no mide.
NO_TARGET_HIT_NOTE = (
    "OJO: esta consulta no tiene NINGÚN acierto contra su propia diana. Eso no es un "
    "off-target y no veta este frente —la potencia es otra pregunta y este software no "
    "la mide—, pero sí dice que algo raro pasa con la corrida o con la base: la diana "
    "declarada tendría que estar ahí."
)


def judge_hits(
    hits, *, target_accessions, min_aligned, expected_antisense=None,
) -> SpecificityCall:
    """El veredicto de especificidad a partir de los aciertos. UN solo criterio.

    `hits` son objetos con `transcript`, `aligned`, `mismatches`, `antisense` y
    `describe()`; cada implementacion adapta los suyos. `target_accessions` son TODAS
    las variantes de transcrito de la diana: un gen tiene varias y todas son la diana.

    `min_aligned` es cuantos nucleotidos tiene que alinear un acierto para contar, y lo
    DERIVA quien llama de la sonda de esa consulta — no se escribe aqui (errata nº 57).

    `expected_antisense` es la orientacion que esa hebra tiene que dar contra su PROPIA
    diana. Es una COMPROBACION y no un filtro: no descarta ningun acierto y no cambia el
    estado. `None` = no se comprueba, y eso NO es «coincide».
    """
    diana = {str(a).strip() for a in target_accessions if str(a).strip()}
    if not diana:
        raise ValueError(
            "Hay que declarar las variantes de transcrito de la diana: sin ellas, un "
            "acierto perfecto contra el propio blanco se cuenta como off-target y el "
            "filtro no significa nada. Se aborta."
        )
    todos = list(hits)
    # LA LONGITUD PRIMERO, Y LA ORIENTACION NO ENTRA. Un parcial no es un off-target
    # mire a donde mire; y descartar por orientacion tiraba el acierto legitimo de la
    # pasajera contra su propia diana. Ver `WHY_LENGTH_AND_NOT_MISMATCHES` y
    # `EXPECTED_ORIENTATION`.
    completos = [h for h in todos if h.aligned >= min_aligned]
    exentos = [h for h in completos if h.transcript in diana]
    fuera = [h for h in completos if h.transcript not in diana]
    graves = [h for h in fuera if h.mismatches <= 1]
    leves = [h for h in fuera if h.mismatches == 2]
    raras = (
        [h for h in exentos if h.antisense is not expected_antisense]
        if expected_antisense is not None else []
    )
    return SpecificityCall(
        state=FilterState.FAIL if graves else FilterState.PASS,
        graves=tuple(graves),
        leves=tuple(leves),
        exentos=tuple(exentos),
        parciales=len(todos) - len(completos),
        sin_diana=not exentos,
        orientacion_rara=tuple(raras),
    )


def target_accessions(species) -> tuple[str, ...]:
    """Las variantes de transcrito declaradas para la diana de esa especie.

    ABORTA si la especie no las declara. Es la condicion sin la cual esta exencion seria
    un colador: nunca un `PASS` por una lista vacia.
    """
    import tomllib  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from .species import resolve  # noqa: PLC0415

    ruta = Path(__file__).resolve().parent.parent / "data" / "diana" / "variantes.toml"
    with ruta.open("rb") as f:
        tabla = tomllib.load(f)
    slug = resolve(species).slug
    entrada = tabla.get(slug)
    if not entrada or not entrada.get("accessions"):
        raise ShmirDesignError(
            f"No hay variantes de transcrito declaradas para {slug!r} en "
            f"{ruta.parent.name}/{ruta.name}. Sin ellas no se puede dar veredicto de "
            f"especificidad: un acierto perfecto contra el propio blanco se contaría "
            f"como off-target y todos los candidatos fallarían contra su propia diana. "
            f"Se declaran ahí, con su procedencia — nunca se deducen."
        )
    return tuple(entrada["accessions"])


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
                "No hay base de RefSeq RNA cargada, así que el filtro de especificidad "
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
    # EL CRITERIO ES EL MISMO QUE EL DE LA CORRIDA SUBIDA, y se llama, no se repite:
    # habia dos y la que daba el veredicto de la corrida no tenia concepto de diana
    # (errata nº 56). `target` sigue siendo un accession aqui; el criterio acepta el
    # conjunto de variantes.
    antisentido = [h for h in todos if h.strand is Strand.ANTISENSE]
    sentido = [h for h in todos if h.strand is Strand.SENSE]
    # SE LE SOMETEN SOLO LOS APAREABLES, y eso NO es «filtrar por orientacion»: en ESTE
    # escaner un hit en SENTIDO es un transcrito que contiene la sonda TAL CUAL, con la
    # que la sonda no puede aparearse — no es un off-target suyo, y esta medido, no
    # supuesto (`_scan_one` casa el complemento inverso para ANTISENTIDO y la sonda para
    # SENTIDO). En `-outfmt 6` el signo de `sstart`→`send` NO es esta cantidad, y por eso
    # alli se le someten TODOS. La orientacion no entra en el criterio; lo que entra es
    # que cada llamador declare que puede probar.
    #
    # `expected_antisense=None`: aqui la etiqueta es «aparea», no «que hebra es», asi que
    # el invariante de montaje no aplica — y no haberlo comprobado no es que coincida.
    fallo = judge_hits(
        antisentido,
        target_accessions=(target,),
        # De la sonda MAS CORTA de las que se escanearon: aqui todo hit mide lo que su
        # sonda, asi que este minimo no puede descartar ninguno legitimo — y sigue
        # derivandose en vez de escribirse.
        min_aligned=min(
            len("".join(str(x).split())) for x in (guide, passenger) if x
        ) - ALLOWED_TRUNCATION,
        expected_antisense=None,
    )
    graves, leves = list(fallo.graves), list(fallo.leves)

    orientacion = (
        f" Descartados {len(sentido)} hit(s) en orientacion SENTIDO (misma hebra que "
        f"la sonda): no son off-targets de la guía."
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


def taxid_for(species: str) -> str:
    """El taxid de una especie. UNICO origen: `species.resolve()`.

    La validacion NO es «esta en una lista blanca» sino «esta especie tiene taxid
    DECLARADO»: son dos cosas distintas y la primera cerraba el frente a dos especies
    por una razon que no es del frente. Una especie sin taxid declarado aborta diciendo
    donde se declara — que es lo contrario de deducirlo del nombre.
    """
    from .species import resolve

    resuelta = resolve(species)
    if resuelta.taxid:
        return resuelta.taxid
    raise ShmirDesignError(
        f"La especie {species!r} ({resuelta.scientific}) NO tiene taxid declarado en "
        f"este proyecto, así que no se puede filtrar el BLAST por organismo. Se mira en "
        f"el Taxonomy Browser del NCBI y se AÑADE a `species.SPECIES` — no se deduce "
        f"del nombre ni se toma el de otra especie: un taxid equivocado devuelve los "
        f"aciertos de OTRO organismo y el resultado tiene la forma correcta."
    )


def blast_command(query_fasta: str, species: str) -> str:
    """Orden exacta del BLAST remoto de inspeccion. Este modulo NO la lanza."""
    return (
        f'blastn -task blastn-short -db refseq_rna -remote '
        f'-entrez_query "{taxid_for(species)}[ORGN]" -query {query_fasta}'
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
            f"{path} no es UTF-8 válido ({exc}); se aborta la carga."
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
                    f"{path}, línea {numero}: cabecera sin identificador; se aborta."
                )
            if identificador in records:
                raise ShmirDesignError(
                    f"{path}, línea {numero}: el identificador {identificador} esta "
                    f"repetido; se aborta en vez de quedarse con uno de los dos."
                )
            trozos = []
        elif linea.strip():
            if identificador is None:
                raise ShmirDesignError(
                    f"{path}, línea {numero}: secuencia antes de la primera cabecera; "
                    f"no es un FASTA válido y se aborta."
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
    "que silencia el transgén produce un fallo silencioso — knockdown global bonito y "
    "ningún beneficio en el ratio — porque apaga la misma proteina que se quiere "
    "expresar."
)

TRANSGENE_ORIENTATION_NOTE = (
    "El FASTA del casete se lee como la hebra sentido de lo que se transcribe, así que "
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
        lines = [f"Transgén — {self.state.value}", f"  {self.reason}", ""]
        if self.database is not None:
            lines.extend(
                [
                    "  Procedencia y parámetros:",
                    f"    casete          {self.database.provenance}",
                    f"    sonda           {self.query_length} nt "
                    f"(guía y pasajera por separado)",
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
                "No hay casete del transgén cargado, así que el filtro contra el "
                "transgén no se ejecuta y queda sin comprobar si el candidato apaga la "
                "propia construcción terapeutica. NOT_RUN no es PASS: una base ausente "
                "nunca se convierte en PASS."
            ),
        )

    for nombre, sonda in (("guia", guide), ("pasajera", passenger)):
        if sonda is None:
            continue
        if not sonda.strip():
            raise ValueError(
                f"La {nombre} está vacía: no se puede escanear el casete con una sonda "
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
                f"transgen: {detalle}. Este candidato apagaria la construcción que se "
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
            f"Sin sitios de 0 ni 1 desapareamiento en el casete del transgén."
            f"{aviso}{orientacion}{procedencia}"
        ),
        hits=tuple(antisentido),
        sense_hits=tuple(sentido),
        warnings=avisos,
        database=cassette,
        query_length=len(guide),
    )
