"""Carga de off-targets mediada por seed: el TERCER modal.

Es el frente `offtarget_seed` — el que estuvo invisible hasta que se contaron los frentes
uno a uno, porque `carga_seed` era un numero y no un veredicto, asi que no aparecia en
ninguna lista. Se cierra con `transcriptoma_3utr.fa`, que HOY NO ESTA.

Que hace este modulo y que NO hace:

  - **Cuenta sitios** de complementariedad de seed sobre los 3'UTR del transcriptoma.
    Es busqueda de SUBCADENA, igual que la colision de seed y por la misma razon: 7 nt
    contiguos no dan un alineamiento puntuable, asi que ningun BLAST los devuelve.
  - **No predice represion.** Un sitio contado no es un sitio funcional, y las tres
    limitaciones de `LIMITATIONS` empujan todas en la misma direccion: lo que sale es un
    LIMITE SUPERIOR.

Cuatro decisiones que son las que hacen el numero legible:

1. **CUATRO clases, nunca un total** (`SITE_CLASSES`). La represion esperada de un 8mer
   y la de un 6mer no se parecen; sumarlas mezcla señal con ruido. `Counts` no tiene
   —a proposito— ningun atributo que sume las cuatro.
2. **Percentil contra una nula de composicion equivalente** (`null_distribution`). Un
   conteo a secas no es interpretable: una seed rica en A/T tiene mas sitios por pura
   composicion. El numero accionable es el percentil.
3. **Controles biologicos en la misma corrida** (`CONTROL_NAMES`), con sus seeds sacadas
   de `mature.fa` y nunca escritas aqui (regla 1). Su conteo es lo que dice que significa
   «muchos sitios», y eso viene de la biologia, no del codigo.
4. **Autoconteo sobre la propia diana** (`self_count`). Deberia ser 1. Si es mas, hay
   varias dianas en el mismo mensajero y eso hay que saberlo ANTES de interpretar una
   cinetica.

Uso: DESEMPATE, nunca filtro (`USE_NOTE`).

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import bisect
import hashlib
import random
import re
import textwrap
from collections import Counter
from dataclasses import dataclass, replace

from .coords import Frame, label
from .errors import ShmirDesignError
from .seed_load import FRONT_NAME, WHY_NOT_BLAST  # noqa: F401  (el frente es el mismo)

SEED_START = 2
SEED_END = 8

#: Las cuatro clases, en orden de especificidad decreciente. El orden importa: la
#: clasificacion asigna cada aparicion del nucleo a la PRIMERA que encaje, y asi son
#: excluyentes por construccion.
SITE_CLASSES = ("8mer", "7mer-m8", "7mer-A1", "6mer")

#: La geometria de cada clase sobre la DIANA, leida 5'→3'. Va escrita porque de aqui
#: sale todo lo demas y un lector tiene que poder comprobarlo sin abrir el codigo.
CLASS_GEOMETRY = {
    "8mer": (
        "complemento inverso de las posiciones 2-8 de la guía, más una A en la posición "
        "1 de la diana"
    ),
    "7mer-m8": (
        "complemento inverso de las posiciones 2-8 de la guía, SIN la A"
    ),
    "7mer-A1": (
        "complemento inverso de las posiciones 2-7 de la guía, más la A"
    ),
    "6mer": (
        "complemento inverso de las posiciones 2-7 de la guía, sola"
    ),
}

WHY_NOT_SUMMED = (
    "LAS CUATRO CLASES NO SE SUMAN, y no es una preferencia de formato: la represion "
    "esperada de un 8mer y la de un 6mer no se parecen en nada, así que un total mezcla "
    "SEÑAL CON RUIDO y el número resultante no se refiere a nada. Van en columnas "
    "separadas siempre. `Counts` no tiene ningún atributo que las sume: si existiera, "
    "alguien acabaria imprimiendolo."
)

MISSING_FILE = "transcriptoma_3utr.fa"

#: La ruta de descarga, para que la interfaz la enseñe en vez de que haya que
#: preguntarla. La aporto el responsable del proyecto.
#: La ruta de descarga, CON MARCADOR. No se lee tal cual: se resuelve con
#: `ucsc_route(especie)` contra `species.ucsc_assembly`.
#:
#: Antes ponia `mm39` DENTRO del texto. No daba ningun error —el resto de la ruta es la
#: misma para cualquier especie— y por eso es el caso peligroso: quien cargara conejo
#: leia una instruccion correcta de principio a fin con el ensamblaje del raton, y el
#: fichero que bajara habria salido con la forma correcta y las coordenadas de otro
#: organismo. Mismo patron que `rmsk_mouse.out` conectado por rol.
UCSC_ROUTE_TEMPLATE = (
    "COMO CONSEGUIR EL FICHERO: Table Browser de UCSC, ensamblaje {ensamblaje}, grupo «Genes "
    "and Gene Predictions», track «NCBI RefSeq», tabla «RefSeq All» o «RefSeq Curated», "
    "y en «output format» se elige «sequence». Al dar a «get output» pregunta que región "
    "se quiere: ahi se marca «3' UTR Exons» y se desmarca TODO lo demas. "
    "APUNTA EL ENSAMBLAJE Y LA FECHA DE LA TABLA al descargarlo: sin esas dos cosas el "
    "conteo no es reproducible, igual que pasa con la versión de miRBase y la de Dfam. "
    "Son unas decenas de megas, así que NO va a git: en el manifiesto quedan solo "
    "nombre, tamaño y md5, como con `refseq_rna.fa`."
)


def ucsc_route(species) -> str:
    """La ruta de descarga para ESTA especie, con su ensamblaje puesto.

    Si la especie no tiene ensamblaje declarado, el texto lo DICE y dice donde se
    declara — no se deduce ni se deja el del raton. Misma regla que las fichas de
    obtencion, y con la misma redaccion: `obtencion.undeclared_note`.
    """
    from .obtencion import undeclared_note  # noqa: PLC0415
    from .species import resolve  # noqa: PLC0415

    especie = resolve(species) if isinstance(species, str) else species
    ensamblaje = especie.ucsc_assembly
    if not ensamblaje:
        ensamblaje = undeclared_note("ensamblaje", cientifico=especie.scientific)
    return UCSC_ROUTE_TEMPLATE.format(ensamblaje=ensamblaje)


#: Los tres controles biologicos. Son una DECLARACION del proyecto, no un dato de
#: fichero: ver `WHY_THE_CONTROLS_STAY_IN_CODE`.
CONTROL_NAMES = ("miR-124-3p", "miR-9-5p", "let-7a-5p")

#: POR QUE LOS TRES NOMBRES SE QUEDAN EN EL CODIGO. DECIDIDO 2026-08-27.
#:
#: La auditoria los habia clasificado como DATO —«su eleccion viene de la biologia, no
#: del codigo»— y esa frase es cierta y no es el criterio. El criterio es el otro: un
#: dato es lo que CAMBIA al cambiar de especie o de gen y entra por el gestor; una
#: eleccion del proyecto sobre que se toma como referencia va en codigo, porque en un
#: fichero se podria cambiar SIN QUE SE VIERA EN EL DIFF. Y cambiar el patron de medida
#: cambia lo que significa «muchos sitios» en todos los informes a la vez.
#:
#: Es exactamente la razon de `mirna.CORE_ABUNDANT`, y va con la misma consecuencia:
#: fuera de cerebro murino la eleccion no esta justificada, asi que lo que hay que
#: hacer no es sacarla a un fichero — es MARCARLA, como se marca `LISTA_DE_OTRA_ESPECIE`.
#:
#: Lo que si es dato son sus SECUENCIAS, y ya salen de `mature.fa` (regla 1).
WHY_THE_CONTROLS_STAY_IN_CODE = (
    "Los tres controles son una DECISIÓN del proyecto sobre qué se toma como patrón de "
    "«muchos sitios», no una medida que venga de un fichero. En un fichero se podrían "
    "cambiar sin que se viera en el diff, y con ellos cambiaría la lectura de todos los "
    "informes a la vez: misma razón que `mirna.CORE_ABUNDANT`. Sus SECUENCIAS sí son "
    "dato y salen de `mature.fa`. Fuera de cerebro murino la elección no está "
    "justificada, y eso se resuelve MARCÁNDOLA, no sacándola a un fichero."
)

CONTROLS_NOTE = (
    "CONTROLES BIOLOGICOS, en la misma corrida y sobre el mismo fichero. Su conteo es la "
    "REFERENCIA de que significa «muchos sitios»: son miARN abundantes de cerebro con "
    "redes de dianas caracterizadas, así que el valor esperado viene de la BIOLOGIA y no "
    "del código. Sus seeds salen de `mature.fa`, nunca escritas aquí. "
    "NO se les da percentil: un percentil se calcula contra una nula de LA COMPOSICIÓN "
    "DE CADA UNO, así que el de un control contra la nula de nuestra guía no querria "
    "decir nada. Lo que aportan es MAGNITUD, no posición."
)

#: Como se sortea la nula. DECLARADO como parametro de este analisis, no citado.
NULL_CRITERION = (
    "DISTRIBUCIÓN NULA: permutaciones de la composición del propio heptamero, contadas "
    "sobre EL MISMO fichero. Se sortea barajando las siete bases de la seed, así que "
    "cada sorteo tiene exactamente la misma composición que la consulta. "
    "La alternativa —heptameros uniformes al azar— queda DESCARTADA con su motivo: una "
    "nula uniforme mide sobre todo el contenido de A/T, así que declararia «cargada» a "
    "cualquier seed rica en A/T por pura composición y no por sus sitios."
)

PERCENTILE_RULE = (
    "PERCENTIL = 100 × (sorteos por debajo + medio empate) / sorteos. Los empates van a "
    "medias a propósito: con conteos enteros hay muchos, y contarlos todos por debajo o "
    "todos por encima corre el percentil varios puntos segun cual se elija."
)

MIN_NULL_DRAWS = 10_000

USE_NOTE = (
    "USO: DESEMPATE, NUNCA FILTRO. Un percentil alto de carga es motivo para preferir "
    "otro candidato entre dos que empatan — no para excluir a nadie. La POTENCIA sobre "
    "la diana sigue mandando, y esto no la predice: son dos preguntas distintas y esta "
    "no contesta la primera."
)

UPPER_BOUND_NOTE = (
    "LAS TRES LIMITACIONES EMPUJAN EN LA MISMA DIRECCIÓN, así que el número es un "
    "LÍMITE SUPERIOR: cuenta SITIOS, no sitios probablemente funcionales. No se compensa "
    "con un factor ni se corrige a ojo — se dice."
)


@dataclass(frozen=True)
class Limitation:
    key: str
    title: str
    text: str
    direction: str = "sobrestima"


LIMITATIONS = (
    Limitation(
        key="conservacion",
        title="Sin ponderación por conservación",
        text=(
            "No tenemos alineamientos multiespecie; TargetScan si. Nuestro número cuenta "
            "SITIOS, no sitios probablemente funcionales: un sitio que no está conservado "
            "en ninguna otra especie pesa aquí lo mismo que uno conservado en todas. "
            "Sobrestima."
        ),
    ),
    Limitation(
        key="apa",
        title="Sin ponderación por APA",
        text=(
            "Un sitio en la parte DISTAL de un 3'UTR con poliadenilación alternativa no "
            "está en todos los mensajeros de ese gen: la isoforma corta no lo lleva. Lo "
            "sabemos por Prnp, donde la fracción de isoforma larga está medida en 0,86, y "
            "aplica a los demas genes igual — solo que ahi no lo hemos medido. Sobrestima."
        ),
    ),
    Limitation(
        key="expresion",
        title="Sin ponderación por expresión",
        text=(
            "Un sitio en un gen que la neurona no expresa no cuenta como off-target. Si "
            "algun día hay `expresion_cerebro.tsv` con su referencia y su umbral, esto se "
            "refina; hoy no lo hay y todos los genes del fichero pesan igual. Sobrestima."
        ),
    ),
)


def limitation(key: str) -> Limitation:
    for lim in LIMITATIONS:
        if lim.key == key:
            return lim
    raise KeyError(
        f"No hay ninguna limitacion registrada con clave {key!r}; las que hay son "
        f"{', '.join(l.key for l in LIMITATIONS)}."
    )


# ─────────────────────────────────── geometria ────────────────────────────────────

_COMPLEMENT = str.maketrans("ACGT", "TGCA")

#: Relleno de bordes. Ni es una base ni puede serlo, asi que nunca casa con la posicion
#: 8 de una guia ni con la A de la posicion 1 de la diana: un sitio al principio o al
#: final de un 3'UTR se clasifica bien en vez de perderse.
PAD = "."

_NOT_DNA = re.compile(r"[^ACGT]")


def _normalize(sequence: str) -> str:
    """Mayusculas, U→T, y todo lo que no sea una base a relleno.

    Una `N` no puede casar con nada, y dejarla tal cual haria que el indice y el barrido
    directo dieran numeros distintos — y entonces la nula, que sale del indice, no seria
    comparable con el conteo, que sale del barrido.
    """
    limpia = "".join(str(sequence).split()).upper().replace("U", "T")
    return _NOT_DNA.sub(PAD, limpia)


def _revcomp(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


@dataclass(frozen=True)
class SitePatterns:
    """Lo que hay que buscar en los 3'UTR, en coordenadas de DIANA.

    Las cuatro clases comparten el mismo NUCLEO de 6 nt; lo que las distingue es la base
    de delante (la que aparea con la posicion 8 de la guia) y la de detras (la A de la
    posicion 1 de la diana). Por eso se busca el nucleo UNA vez y se mira el contexto:
    asi las cuatro clases son excluyentes por construccion y no hace falta descontar
    unas de otras.
    """

    heptamer: str
    core: str
    m8_base: str

    @property
    def sites(self) -> dict[str, str]:
        return {
            "8mer": self.m8_base + self.core + "A",
            "7mer-m8": self.m8_base + self.core,
            "7mer-A1": self.core + "A",
            "6mer": self.core,
        }

    @property
    def self_overlapping(self) -> bool:
        """¿El nucleo se solapa consigo mismo? Entonces el conteo puede inflarse."""
        return any(
            self.core[i:] == self.core[: len(self.core) - i]
            for i in range(1, len(self.core))
        )

    def describe(self) -> str:
        piezas = ", ".join(f"{c}={self.sites[c]}" for c in SITE_CLASSES)
        aviso = (
            "  ⚠ el núcleo se solapa consigo mismo: las apariciones contiguas se cuentan "
            "todas y el número puede estar inflado."
            if self.self_overlapping else ""
        )
        return f"seed {self.heptamer} → {piezas}{aviso}"


def patterns_from_heptamer(heptamer: str) -> SitePatterns:
    """Heptamero = posiciones 2-8 de la guia, en ADN."""
    limpio = "".join(str(heptamer).split()).upper().replace("U", "T")
    if len(limpio) != SEED_END - SEED_START + 1:
        raise ValueError(
            f"El heptamero mide {len(limpio)} nt y las posiciones {SEED_START}-{SEED_END} "
            f"son {SEED_END - SEED_START + 1}; se aborta en vez de buscar media seed."
        )
    if set(limpio) - set("ACGT"):
        raise ValueError(
            f"El heptamero {limpio} tiene bases que no son A/C/G/T: no se puede "
            f"construir su sitio complementario. Se aborta."
        )
    return SitePatterns(
        heptamer=limpio,
        core=_revcomp(limpio[: SEED_END - SEED_START]),
        m8_base=limpio[-1].translate(_COMPLEMENT),
    )


def site_patterns(strand: str) -> SitePatterns:
    """De una hebra (guia o pasajera) a sus cuatro patrones."""
    limpia = "".join(str(strand).split()).upper().replace("U", "T")
    if len(limpia) < SEED_END:
        raise ValueError(
            f"La hebra mide {len(limpia)} nt y la seed son las posiciones {SEED_START}-"
            f"{SEED_END}; se aborta en vez de buscar media seed."
        )
    return patterns_from_heptamer(limpia[SEED_START - 1 : SEED_END])


# ──────────────────────────────────── conteo ──────────────────────────────────────


@dataclass(frozen=True)
class Counts:
    """Sitios y transcritos tocados, POR CLASE. Sin total, y es a proposito."""

    sites: dict[str, int]
    transcripts: dict[str, int]

    def __post_init__(self) -> None:
        for nombre, tabla in (("sites", self.sites), ("transcripts", self.transcripts)):
            ajenas = sorted(set(tabla) - set(SITE_CLASSES))
            if ajenas:
                raise ValueError(
                    f"`Counts.{nombre}` trae clase(s) desconocida(s): "
                    f"{', '.join(ajenas)}. Las que hay son {', '.join(SITE_CLASSES)}. "
                    f"Se aborta."
                )
            faltan = sorted(set(SITE_CLASSES) - set(tabla))
            if faltan:
                raise ValueError(
                    f"`Counts.{nombre}` no trae {', '.join(faltan)}. Una clase ausente de "
                    f"la salida es indistinguible de una clase con cero sitios, y eso es "
                    f"justo lo que la regla 3 prohibe. Se aborta."
                )


def count_in(sequence: str, patterns: SitePatterns) -> dict[str, int]:
    """Las cuatro clases en UNA secuencia. Cada aparicion del nucleo cae en una sola."""
    seq = _normalize(sequence)
    core = patterns.core
    largo = len(core)
    conteo = {c: 0 for c in SITE_CLASSES}
    i = seq.find(core)
    while i != -1:
        anterior = seq[i - 1] if i > 0 else PAD
        siguiente = seq[i + largo] if i + largo < len(seq) else PAD
        if anterior == patterns.m8_base:
            conteo["8mer" if siguiente == "A" else "7mer-m8"] += 1
        else:
            conteo["7mer-A1" if siguiente == "A" else "6mer"] += 1
        i = seq.find(core, i + 1)
    return conteo


def core_occurrences(sequence: str, patterns: SitePatterns) -> int:
    """Cuantas veces aparece el NUCLEO. No es un total de clases: es otra magnitud."""
    seq = _normalize(sequence)
    core = patterns.core
    total = 0
    i = seq.find(core)
    while i != -1:
        total += 1
        i = seq.find(core, i + 1)
    return total


def count_over(records, patterns: SitePatterns) -> Counts:
    """Barrido directo sobre los registros: sitios y transcritos tocados, por clase."""
    sitios = {c: 0 for c in SITE_CLASSES}
    tocados = {c: 0 for c in SITE_CLASSES}
    for _, secuencia in records:
        conteo = count_in(secuencia, patterns)
        for clase, n in conteo.items():
            if n:
                sitios[clase] += n
                tocados[clase] += 1
    return Counts(sites=sitios, transcripts=tocados)


@dataclass(frozen=True)
class KmerIndex:
    """Cuenta de 8-meros con relleno en los bordes: el atajo que hace viable la nula.

    Con 10.000 sorteos, barrer el fichero entero por cada uno seria inviable. El indice
    se construye UNA vez —una pasada por el fichero— y despues cada consulta son 25
    busquedas en un diccionario. Se comprueba con un test que el indice y el barrido
    directo dan lo mismo: si no coincidieran, el percentil no seria comparable con el
    conteo.
    """

    counts: dict[str, int]
    positions: int

    def class_counts(self, patterns: SitePatterns) -> dict[str, int]:
        alfabeto = "ACGT" + PAD
        core = patterns.core
        resultado = {c: 0 for c in SITE_CLASSES}
        for anterior in alfabeto:
            for siguiente in alfabeto:
                n = self.counts.get(anterior + core + siguiente, 0)
                if not n:
                    continue
                if anterior == patterns.m8_base:
                    resultado["8mer" if siguiente == "A" else "7mer-m8"] += n
                else:
                    resultado["7mer-A1" if siguiente == "A" else "6mer"] += n
        return resultado


def build_index(records) -> KmerIndex:
    blob = PAD + PAD.join(_normalize(s) for _, s in records) + PAD
    ancho = len(PAD) + 6 + len(PAD)
    contador = Counter(
        blob[i : i + ancho] for i in range(len(blob) - ancho + 1)
    )
    return KmerIndex(counts=dict(contador), positions=len(blob))


# ───────────────────────────── procedencia y auditoria ────────────────────────────


@dataclass(frozen=True)
class Provenance:
    """De donde sale el fichero. Sin esto el conteo no es reproducible."""

    source: str
    assembly: str
    table: str
    table_date: str
    representative: str
    version: str
    md5: str

    def __post_init__(self) -> None:
        for campo in (
            "source", "assembly", "table", "table_date", "representative",
            "version", "md5",
        ):
            if not str(getattr(self, campo)).strip():
                raise ValueError(
                    f"El catalogo de 3'UTR necesita {campo}: sin ensamblaje, tabla, "
                    f"fecha y criterio de representante el conteo NO es reproducible — "
                    f"es la misma lección que la versión de miRBase y la biblioteca de "
                    f"Dfam. Se aborta."
                )

    def describe(self) -> list[str]:
        return [
            f"fuente: {self.source}",
            f"ensamblaje: {self.assembly}   tabla: {self.table} ({self.table_date})",
            f"representante por gen: {self.representative}",
            f"version {self.version} · md5 {self.md5}",
        ]


@dataclass(frozen=True)
class IsoformAudit:
    """¿El conteo esta inflado por llevar varias entradas del mismo gen?

    Tres comprobaciones, y la tercera solo si hay mapa de genes:

      - identificadores REPETIDOS: la salida del Table Browser da un registro por EXON
        de 3'UTR, asi que un 3'UTR de tres exones aparece tres veces;
      - secuencias DUPLICADAS exactas: dos isoformas que comparten 3'UTR;
      - varios transcritos por GEN, que es la pregunta de verdad y que **no se puede
        contestar sin mapa**: de un accession no se deduce el gen. Sin mapa queda
        NO COMPROBADO, que no es lo mismo que «no las hay».
    """

    records: int
    distinct_ids: int
    repeated_ids: tuple[tuple[str, int], ...] = ()
    duplicate_sequence_groups: int = 0
    records_in_duplicates: int = 0
    genes: int | None = None
    multi_isoform_genes: tuple[tuple[str, int], ...] = ()

    @property
    def checked_by_gene(self) -> bool:
        return self.genes is not None

    @property
    def inflated(self) -> bool:
        return bool(
            self.repeated_ids
            or self.duplicate_sequence_groups
            or self.multi_isoform_genes
        )

    def warning(self) -> str:
        piezas: list[str] = []
        if self.repeated_ids:
            total = sum(n for _, n in self.repeated_ids)
            piezas.append(
                f"{len(self.repeated_ids)} identificador(es) repetido(s) en "
                f"{total} registro(s): el conteo está INFLADO. La salida de «3' UTR "
                f"Exons» da un registro POR EXON, así que un 3'UTR troceado aparece "
                f"varias veces."
            )
        if self.duplicate_sequence_groups:
            piezas.append(
                f"{self.duplicate_sequence_groups} grupo(s) de secuencia IDÉNTICA "
                f"({self.records_in_duplicates} registro(s)): el conteo está INFLADO. "
                f"Dos isoformas que comparten 3'UTR aportan sus sitios dos veces."
            )
        if self.multi_isoform_genes:
            extra = sum(n - 1 for _, n in self.multi_isoform_genes)
            piezas.append(
                f"{len(self.multi_isoform_genes)} gen(es) con más de un transcrito "
                f"({extra} registro(s) de más): el conteo está INFLADO."
            )
        if not self.checked_by_gene:
            piezas.append(
                "VARIAS ISOFORMAS POR GEN: NO SE HA PODIDO COMPROBAR. De un accession no "
                "se deduce el gen, y aquí no se adivina: hace falta un mapa "
                "transcrito→gen. No haber podido comprobarlo NO es «no las hay»."
            )
        elif not self.multi_isoform_genes:
            piezas.append(
                f"Un transcrito por gen en los {self.genes} gen(es) del mapa: el criterio "
                f"de representante se cumple."
            )
        return " ".join(piezas)

    def describe(self) -> list[str]:
        return [
            f"{self.records} registro(s), {self.distinct_ids} identificador(es) distinto(s)",
            self.warning(),
        ]


@dataclass(frozen=True)
class Catalog:
    """El fichero cargado: registros, procedencia, auditoria e indice."""

    records: tuple[tuple[str, str], ...]
    provenance: Provenance
    audit: IsoformAudit
    index: KmerIndex

    @property
    def total_nt(self) -> int:
        return sum(len(s) for _, s in self.records)

    def describe(self) -> list[str]:
        lineas = list(self.provenance.describe())
        lineas.append(f"{len(self.records)} registro(s), {self.total_nt} nt en total")
        lineas.extend(self.audit.describe())
        return lineas


def audit_records(records, gene_map=None) -> IsoformAudit:
    nombres = [n for n, _ in records]
    repetidos = tuple(
        sorted((n, c) for n, c in Counter(nombres).items() if c > 1)
    )
    por_secuencia = Counter(s for _, s in records)
    grupos = [n for s, n in por_secuencia.items() if n > 1]

    genes: int | None = None
    multi: tuple[tuple[str, int], ...] = ()
    if gene_map is not None:
        faltan = sorted({n for n in nombres if n not in gene_map})
        if faltan:
            raise ShmirDesignError(
                f"El mapa transcrito→gen no cubre {len(faltan)} identificador(es) del "
                f"fichero ({', '.join(faltan[:5])}...). Se aborta en vez de contarlos "
                f"como genes distintos: eso es exactamente el error que el mapa venia a "
                f"evitar."
            )
        por_gen = Counter(gene_map[n] for n in nombres)
        genes = len(por_gen)
        multi = tuple(sorted((g, c) for g, c in por_gen.items() if c > 1))

    return IsoformAudit(
        records=len(records),
        distinct_ids=len(set(nombres)),
        repeated_ids=repetidos,
        duplicate_sequence_groups=len(grupos),
        records_in_duplicates=sum(grupos),
        genes=genes,
        multi_isoform_genes=multi,
    )


def build_catalog(records, *, provenance: Provenance, gene_map=None) -> Catalog:
    registros = tuple((str(n), str(s).upper()) for n, s in records)
    if not registros:
        raise ShmirDesignError(
            f"El catalogo de 3'UTR está vacío; se aborta en vez de informar de una carga "
            f"de cero, que pareceria una buena noticia y sería un fichero mal leido."
        )
    return Catalog(
        records=registros,
        provenance=provenance,
        audit=audit_records(registros, gene_map),
        index=build_index(registros),
    )


def parse_fasta_pairs(text: str, *, source: str) -> tuple[tuple[str, str], ...]:
    """FASTA → pares (nombre, secuencia), CONSERVANDO los repetidos.

    No se reutiliza `seed_load.parse_fasta_records` a proposito: aquel ABORTA con un
    identificador repetido, y aqui repetirse es un caso legitimo y esperado — la salida
    de «3\' UTR Exons» del Table Browser da un registro POR EXON, asi que un 3\'UTR
    troceado aparece varias veces con el mismo accession. Abortar esconderia justo lo
    que hay que auditar; lo que se hace es CONTARLO y avisar de que el conteo se infla.
    """
    pares: list[tuple[str, str]] = []
    nombre: str | None = None
    partes: list[str] = []

    def cerrar() -> None:
        nonlocal nombre, partes
        if nombre is not None:
            pares.append((nombre, "".join(partes).upper()))
        nombre, partes = None, []

    for linea in text.splitlines():
        if linea.startswith(">"):
            cerrar()
            cabecera = linea[1:].strip()
            nombre = cabecera.split()[0] if cabecera else ""
            continue
        if nombre is not None:
            partes.append(linea.strip())
    cerrar()

    if not pares:
        raise ShmirDesignError(
            f"{source}: no hay ninguna entrada FASTA; se RECHAZA en vez de contar sobre "
            f"un conjunto vacío."
        )
    vacias = [n for n, s in pares if not s]
    if vacias:
        raise ShmirDesignError(
            f"{source}: {len(vacias)} entrada(s) con cabecera y SIN secuencia "
            f"({', '.join(vacias[:5])}). Se RECHAZA: una entrada vacía cuenta como "
            f"transcrito y aporta cero sitios, así que baja la tasa sin que se vea."
        )
    return tuple(pares)


@dataclass(frozen=True)
class UploadReport:
    """Lo que se comprueba AL RECIBIR el fichero, antes de dejarlo entrar."""

    records: int
    total_nt: int
    md5: str
    audit: IsoformAudit
    parsed: tuple[tuple[str, str], ...]

    def describe(self) -> list[str]:
        return [
            f"{self.records} secuencia(s), {self.total_nt} nt, md5 {self.md5}",
            self.audit.warning(),
        ]


def validate_upload(raw: str, *, declared_md5: str | None = None,
                    gene_map=None) -> UploadReport:
    """Valida el FASTA subido. Si algo no cuadra, RECHAZA y dice por que."""
    texto = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    if not texto.strip():
        raise ShmirDesignError(
            "El fichero subido está vacío; se RECHAZA. Un fichero vacío y un "
            "transcriptoma sin sitios dan el mismo cero y no son lo mismo."
        )
    md5 = hashlib.md5(texto.encode("utf-8"), usedforsecurity=False).hexdigest()
    if declared_md5 is not None and str(declared_md5).strip().lower() != md5:
        raise ShmirDesignError(
            f"El md5 del fichero subido es {md5} y se declaro "
            f"{str(declared_md5).strip().lower()}. Se RECHAZA: el fichero NO es el que "
            f"dice ser, y un conteo sobre otro fichero no es comparable con nada de lo "
            f"que ya está guardado."
        )
    if not texto.lstrip().startswith(">"):
        raise ShmirDesignError(
            "El fichero subido no empieza por «>»: no es un FASTA. Se RECHAZA en vez de "
            "intentar adivinar el formato."
        )

    pares = parse_fasta_pairs(texto, source="fichero subido")
    for nombre, secuencia in pares:
        letras = sorted(set(secuencia) - set("ACGTN"))
        if letras:
            raise ShmirDesignError(
                f"La entrada {nombre!r} trae caracteres que no son A/C/G/T (ni N): "
                f"{', '.join(letras)}. Se RECHAZA: esto no es una secuencia de 3'UTR — "
                f"comprueba que no sea un FASTA de proteina o una salida con anotación."
            )
    return UploadReport(
        records=len(pares),
        total_nt=sum(len(s) for _, s in pares),
        md5=md5,
        audit=audit_records(pares, gene_map),
        parsed=pares,
    )


# ───────────────────────────────── nula y controles ───────────────────────────────


@dataclass(frozen=True)
class Null:
    draws: int
    seed: int
    criterion: str
    by_class: dict[str, tuple[int, ...]]
    distinct_heptamers: tuple[str, ...]

    def percentile(self, site_class: str, value: int) -> float:
        if site_class not in self.by_class:
            raise ValueError(
                f"Clase {site_class!r} desconocida; las que hay son "
                f"{', '.join(SITE_CLASSES)}. Se aborta."
            )
        datos = self.by_class[site_class]
        menores = bisect.bisect_left(datos, value)
        iguales = bisect.bisect_right(datos, value) - menores
        return 100.0 * (menores + 0.5 * iguales) / len(datos)

    def median(self, site_class: str) -> float:
        datos = self.by_class[site_class]
        mitad = len(datos) // 2
        if len(datos) % 2:
            return float(datos[mitad])
        return (datos[mitad - 1] + datos[mitad]) / 2

    def describe(self) -> list[str]:
        return [
            f"nula: {self.draws} sorteos, semilla {self.seed}, "
            f"{len(self.distinct_heptamers)} heptamero(s) distinto(s)",
            f"medianas: "
            + ", ".join(f"{c}={self.median(c):g}" for c in SITE_CLASSES),
            self.criterion,
            PERCENTILE_RULE,
        ]


def null_distribution(index: KmerIndex, patterns: SitePatterns, *,
                      draws: int = MIN_NULL_DRAWS, seed: int = 0) -> Null:
    """Sortea `draws` heptameros de la MISMA composicion y los cuenta en el indice."""
    if draws < MIN_NULL_DRAWS:
        raise ValueError(
            f"La nula pide al menos {MIN_NULL_DRAWS} sorteos y se han pedido {draws}; "
            f"con menos, el percentil de la cola —que es justo el que interesa— no tiene "
            f"resolución. Se aborta."
        )
    rnd = random.Random(seed)
    bases = list(patterns.heptamer)
    cache: dict[str, dict[str, int]] = {}
    orden: list[str] = []
    por_clase: dict[str, list[int]] = {c: [] for c in SITE_CLASSES}
    for _ in range(draws):
        rnd.shuffle(bases)
        hepta = "".join(bases)
        cuentas = cache.get(hepta)
        if cuentas is None:
            cuentas = index.class_counts(patterns_from_heptamer(hepta))
            cache[hepta] = cuentas
            orden.append(hepta)
        for clase in SITE_CLASSES:
            por_clase[clase].append(cuentas[clase])
    return Null(
        draws=draws,
        seed=seed,
        criterion=NULL_CRITERION,
        by_class={c: tuple(sorted(v)) for c, v in por_clase.items()},
        distinct_heptamers=tuple(orden),
    )


@dataclass(frozen=True)
class Control:
    """Un control biologico. Conteo, no percentil: ver `CONTROLS_NOTE`."""

    name: str
    heptamer: str
    sites: dict[str, int]

    def describe(self) -> str:
        piezas = "  ".join(f"{c}={self.sites[c]}" for c in SITE_CLASSES)
        return f"{self.name:<20} {self.heptamer}  {piezas}"


def controls_from_mature(mature, index: KmerIndex, *, prefix: str,
                         names: tuple[str, ...] = CONTROL_NAMES) -> tuple[Control, ...]:
    """Las seeds de los controles salen de `mature.fa`. Aqui no se escribe ninguna."""
    if mature is None:
        raise ShmirDesignError(
            "No hay `mature.fa` cargado, así que las seeds de los controles biologicos "
            "no se pueden resolver. NO se escriben a mano (regla 1): se aborta."
        )
    por_nombre: dict[str, str] = {}
    for seed, lista in mature.seeds.items():
        for nombre in lista:
            por_nombre.setdefault(nombre, seed)

    controles = []
    for corto in names:
        completo = f"{prefix}{corto}"
        seed = por_nombre.get(completo)
        if seed is None:
            raise ShmirDesignError(
                f"El control {completo!r} no está en {mature.source}: no se puede sacar "
                f"su seed. NO se escribe a mano — el valor esperado de un control tiene "
                f"que venir de la biologia, no del código. Se aborta."
            )
        controles.append(
            Control(
                name=completo,
                heptamer=seed,
                sites=index.class_counts(patterns_from_heptamer(seed)),
            )
        )
    return tuple(controles)


@dataclass(frozen=True)
class SelfSite:
    """UN sitio en la propia diana, con su CLASE. Sin clase no se puede interpretar.

    Un 8mer en la propia diana da cooperatividad real —dos sitios fuertes en el mismo
    mensajero— y explicaria un rendimiento por encima de lo esperado. Un 6mer es
    marginal. Dar solo el nucleo y el conteo deja al lector sin poder distinguirlos.
    """

    position: int
    site_class: str
    own_window: bool
    #: En qué región del `target` cae. Vacío cuando no se ha declarado la anatomía: no
    #: haberlo podido decir NO es «está en el 3'UTR» (regla 3 aplicada a una etiqueta).
    region: str = ""
    #: El marco de `position`, que es el de la secuencia que se pasó como `target`. NO
    #: se pone `3utr` a pelo: con el transcrito entero delante eso etiquetaba `tx:1164`
    #: como `3utr:1164` — una posición válida, sólo que de otro sitio.
    frame: Frame = Frame.UTR3

    def describe(self) -> str:
        marca = "el suyo" if self.own_window else "SEGUNDO SITIO"
        region = f" [{self.region}]" if self.region else ""
        return f"{label(self.position, self.frame)} {self.site_class}{region} ({marca})"


#: POR QUE NO SE SUMAN LAS REGIONES, y es `WHY_NOT_SUMMED` por otro eje. Allí no se
#: suman las CLASES porque la represión esperada de un 8mer y la de un 6mer no se
#: parecen; aquí no se pueden mezclar las REGIONES por la misma razón: la represión
#: mediada por seed opera **sobre todo en el 3'UTR**, así que un 6mer en el CDS no es
#: comparable con uno en el 3'UTR aunque el conteo los sume.
#:
#: Y aquí se lee peor, porque la región no sale en el número: dos fichas con «2 sitios»
#: pueden ser 2 en el 3'UTR o 1 y 1, y sólo una de las dos lecturas dice algo del
#: knockdown. Sin esta frase, alguien compara dos números que no miden lo mismo.
SITES_OUTSIDE_UTR3 = (
    "OJO: hay sitios FUERA del 3'UTR (CDS o 5'UTR). Son reales y son de OTRA "
    "naturaleza: la represión mediada por seed opera sobre todo en el 3'UTR, así que "
    "no se suman con los del 3'UTR ni se comparan con ellos — el conteo total mezclaría "
    "dos cosas que no miden lo mismo. Misma regla que las cuatro clases de sitio, por "
    "el eje de la REGIÓN."
)


def self_sites(
    strand: str, *, target: str, window=None, frame: Frame = Frame.UTR3,
    anatomy=None,
) -> tuple[SelfSite, ...]:
    """Los sitios de esta hebra en su propia diana, con posicion y CLASE.

    `window` es el intervalo (inicio, fin) de la ventana del candidato, para poder decir
    cual de los sitios es EL SUYO. Sin ella no se marca ninguno: inventar cual es el
    propio a partir del orden seria un supuesto.
    """
    patrones = site_patterns(strand)
    seq = _normalize(target)
    core = patrones.core
    largo = len(core)
    sitios = []
    i = seq.find(core)
    while i != -1:
        anterior = seq[i - 1] if i > 0 else PAD
        siguiente = seq[i + largo] if i + largo < len(seq) else PAD
        if anterior == patrones.m8_base:
            clase = "8mer" if siguiente == "A" else "7mer-m8"
        else:
            clase = "7mer-A1" if siguiente == "A" else "6mer"
        posicion = i + 1
        propio = bool(window) and window[0] <= posicion <= window[1]
        sitios.append(
            SelfSite(
                position=posicion, site_class=clase, own_window=propio, frame=frame,
                region=(
                    str(getattr(anatomy.region_of(posicion), "value", ""))
                    if anatomy is not None
                    else ("3'UTR" if frame is Frame.UTR3 else "")
                ),
            )
        )
        i = seq.find(core, i + 1)
    return tuple(sitios)


#: CUANTOS SITIOS ESPERA CADA HEBRA EN SU PROPIA DIANA, y no es el mismo número.
#:
#: La **guía** es ANTISENTIDO a la diana: su seed encuentra su sitio ahí **por
#: construcción**, así que 1 es lo esperado y un 0 significa que la secuencia analizada no
#: es la que se cree.
#:
#: La **pasajera** es SENTIDO — lleva la misma secuencia que la diana, no la
#: complementaria — así que su seed **no tiene por qué encontrar nada** ahí. **CERO ES SU
#: RESULTADO ESPERADO**, y lo que merece mirarse es una pasajera que SÍ tenga sitio.
#:
#: Valía 1 para las dos, y eso daba **siete avisos falsos de once** sobre las pasajeras
#: del panel murino (errata nº 125). Es `ANTISENSE` en el BLAST otra vez: un criterio
#: correcto movido a la otra hebra sin el supuesto que lo sostenía.
EXPECTED_SELF_COUNT = {"guia": 1, "pasajera": 0}

WHY_THE_EXPECTED_DIFFERS = (
    "El esperado NO es el mismo para las dos hebras. La guía es antisentido a la diana, "
    "así que su seed cae ahí por construcción y lo esperado es 1. La pasajera es "
    "sentido —la misma secuencia que la diana, no la complementaria—, así que lo "
    "esperado es 0 y lo que hay que mirar es que SÍ tenga sitio."
)


def expected_self_count(strand_name: str) -> int:
    """Cuántos sitios espera esa hebra en su propia diana.

    Una hebra que no esté declarada ABORTA: son dos geometrías distintas y una tercera
    no tiene valor por defecto que valga — poner 1 o 0 sería elegir una de las dos por
    nuestra cuenta.
    """
    try:
        return EXPECTED_SELF_COUNT[str(strand_name)]
    except KeyError as exc:
        raise ShmirDesignError(
            f"No hay autoconteo esperado declarado para la hebra {strand_name!r}; las "
            f"que hay son {', '.join(sorted(EXPECTED_SELF_COUNT))}. No se elige uno por "
            f"nuestra cuenta: {WHY_THE_EXPECTED_DIFFERS}"
        ) from exc


@dataclass(frozen=True)
class SelfCount:
    """Cuantos sitios tiene la hebra en su PROPIA diana. Deberia ser 1."""

    query: str
    target_label: str
    occurrences: int
    sites: dict[str, int]
    detail: tuple[SelfSite, ...] = ()
    expected: int = 1

    @property
    def anomalous(self) -> bool:
        return self.occurrences != self.expected

    def describe(self) -> str:
        if self.occurrences == self.expected:
            return (
                f"{self.query}: {self.occurrences} sitio(s) en {self.target_label}, que "
                f"es lo esperado para esta hebra."
            )
        if self.occurrences == 0:
            # Sólo se llega aquí con `expected != 0`, o sea con una GUIA: para una
            # pasajera el cero es lo esperado y sale por la rama de arriba.
            return (
                f"{self.query}: 0 sitios en {self.target_label}. ANOMALO, y hacia el "
                f"otro lado: si la hebra no tiene su propio sitio en la diana, esa hebra "
                f"NO sale de esa diana. Comprueba que la secuencia analizada es la que "
                f"se cree."
            )
        if self.expected == 0:
            detalle = "; ".join(s.describe() for s in self.detail)
            return (
                f"{self.query}: {self.occurrences} sitio(s) en {self.target_label}"
                f"{f' [{detalle}]' if detalle else ''}. MERECE MIRARSE: esta hebra es "
                f"SENTIDO respecto de la diana, así que lo esperado era 0 — su seed no "
                f"tiene por qué caer ahí. Que caiga significa que la propia diana lleva "
                f"el núcleo de la pasajera, y entonces la pasajera cargada reprimiría "
                f"también el mensajero que se quiere medir."
            )
        detalle = "; ".join(s.describe() for s in self.detail)
        return (
            f"{self.query}: {self.occurrences} sitios en {self.target_label} "
            f"[{detalle}]. ANOMALO: hay MULTIPLES DIANAS en el mismo mensajero, así que "
            f"la cinetica de knockdown no se lee igual — el efecto no es de un solo "
            f"sitio. La CLASE de cada uno decide como se lee: un 8mer o un 7mer-m8 de "
            f"más dan cooperatividad real; un 6mer es marginal."
        )


def self_count(strand: str, *, target: str, target_label: str,
               query: str = "", window=None, strand_name: str = "guia",
               frame=None, anatomy=None) -> SelfCount:
    """El autoconteo de una hebra, CON el esperado que le corresponde.

    `strand_name` no tiene un valor por defecto neutro: `guia` es el caso mayoritario y
    el histórico, y lo que NO puede pasar es que una pasajera se cuente con el esperado
    de una guía — que es lo que daba siete avisos falsos de once.
    """
    patrones = site_patterns(strand)
    extra = {}
    if frame is not None:
        extra["frame"] = frame
    return SelfCount(
        query=query or patrones.heptamer,
        target_label=target_label,
        occurrences=core_occurrences(target, patrones),
        sites=count_in(target, patrones),
        detail=self_sites(
            strand, target=target, window=window, anatomy=anatomy, **extra
        ),
        expected=expected_self_count(strand_name),
    )


@dataclass(frozen=True)
class SharedNetwork:
    """Cuanto se solapan las redes de off-target de DOS hebras, por clase.

    Dos candidatos con el MISMO NUCLEO de 6 nt no son independientes en este eje aunque
    su heptamero difiera: comparten el nucleo, asi que comparten sitios. Lo que decide
    cuanto es la CLASE en que cae cada sitio compartido, y eso depende de la posicion 8,
    que es justo lo que los distingue.

    `positions_shared` cuenta POSICIONES, no clases: la misma posicion puede ser 8mer
    para uno y 6mer para el otro, y eso es informacion, no un empate.
    """

    a: str
    b: str
    same_core: bool
    positions_shared: int
    positions_a: int
    positions_b: int
    #: (clase en A, clase en B) → cuantas posiciones compartidas caen asi.
    by_class: dict[tuple[str, str], int]
    source: str

    @property
    def jaccard(self) -> float:
        union = self.positions_a + self.positions_b - self.positions_shared
        return self.positions_shared / union if union else 0.0

    def describe(self) -> list[str]:
        lineas = [
            f"{self.a} vs {self.b}: núcleo {'COMPARTIDO' if self.same_core else 'distinto'}",
            f"  posiciones con sitio: {self.positions_a} y {self.positions_b}; "
            f"COMPARTIDAS {self.positions_shared} (Jaccard {self.jaccard:.2f})",
            f"  fuente: {self.source}",
        ]
        for (clase_a, clase_b), n in sorted(self.by_class.items()):
            lineas.append(f"    {n} posicion(es): {clase_a} en {self.a} / {clase_b} en {self.b}")
        return lineas


def shared_network(strand_a: str, strand_b: str, *, catalog: "Catalog | None",
                   label_a: str = "A", label_b: str = "B") -> SharedNetwork | None:
    """La interseccion REAL de las dos listas de sitios, por clase. Sin catalogo: None.

    `None` significa NO CALCULADO, y quien lo reciba tiene que decirlo con esas palabras:
    no es cero, y dos redes que no se han comparado no son dos redes independientes.
    """
    if catalog is None:
        return None
    patrones_a = site_patterns(strand_a)
    patrones_b = site_patterns(strand_b)

    def posiciones(hebra: str) -> dict[tuple[str, int], str]:
        """(registro, posicion) → clase. La CLAVE es la posicion, no la clase."""
        tabla: dict[tuple[str, int], str] = {}
        for nombre, secuencia in catalog.records:
            for sitio in self_sites(hebra, target=secuencia):
                tabla[(nombre, sitio.position)] = sitio.site_class
        return tabla

    posiciones_a = posiciones(strand_a)
    posiciones_b = posiciones(strand_b)
    compartidas = set(posiciones_a) & set(posiciones_b)
    por_clase: dict[tuple[str, str], int] = {}
    for clave in compartidas:
        par = (posiciones_a[clave], posiciones_b[clave])
        por_clase[par] = por_clase.get(par, 0) + 1
    return SharedNetwork(
        a=label_a, b=label_b,
        same_core=patrones_a.core == patrones_b.core,
        positions_shared=len(compartidas),
        positions_a=len(posiciones_a),
        positions_b=len(posiciones_b),
        by_class=por_clase,
        source=f"{catalog.provenance.source} ({catalog.provenance.assembly})",
    )


# ─────────────────────── consecuencia para el MULTIPLEXADO ────────────────────────

MULTIPLEX_NOTE = (
    "CONSECUENCIA PARA EL MULTIPLEXADO. Dos candidatos que comparten el NÚCLEO de 6 nt "
    "no son dos apuestas independientes en el eje de off-targets, aunque su heptamero "
    "difiera y aunque el espaciado los de por buenos: las cuatro clases de sitio se "
    "construyen sobre ese núcleo, así que casi toda su red de dianas accesorias es la "
    "misma. Y el espaciado no lo ve — mide DISTANCIA en el 3'UTR, no parecido de seed. "
    "El caso murino es exactamente ese: `3utr:449` y `3utr:1018` son la pareja que el "
    "espaciado sugeriria —extremos opuestos del 3'UTR y los dos con buena asimetría— y "
    "en este eje serían la PEOR elección posible."
)


@dataclass(frozen=True)
class CoreConflict:
    """Dos candidatos SELECCIONADOS que comparten nucleo. Aviso, no veto."""

    a: int
    b: int
    core: str
    heptamer_a: str
    heptamer_b: str

    @property
    def same_heptamer(self) -> bool:
        return self.heptamer_a == self.heptamer_b

    def describe(self, *, label_a: str, label_b: str) -> str:
        """Las DOS etiquetas se reciben ya hechas, y no hay valor por defecto.

        Poner `3utr:` aqui dentro es exactamente el fallo que este proyecto lleva
        cazando: sobre un informe del transcrito completo salio `3utr:1398` y `3utr:1967`
        —posiciones validas del transcrito etiquetadas como 3'UTR— sin dar ningun error.
        El marco se RECIBE, sacado de la anatomia por quien escribe.
        """
        eje = (
            "y además el mismo heptamero, así que tampoco son independientes en la "
            "colisión con miARN endogeno"
            if self.same_heptamer
            else f"con heptameros DISTINTOS ({self.heptamer_a} y {self.heptamer_b}): "
                 f"difieren solo en la posición 8, así que la colisión de seed no los "
                 f"empareja y este eje si"
        )
        return f"{label_a} y {label_b} comparten el núcleo {self.core} {eje}."


def core_conflicts(selection) -> tuple[CoreConflict, ...]:
    """Pares de candidatos ELEGIDOS que comparten nucleo de 6 nt.

    Mismo papel que el aviso de espaciado, en otro eje: no descarta a nadie — dice que
    esos dos no compran la independencia que el panel cree estar comprando.
    """
    elegidos = list(selection.selection.chosen)
    por_inicio = {}
    for elegido in elegidos:
        guia = selection.window_of(elegido).evaluation.guide
        patrones = site_patterns(guia)
        por_inicio[elegido.start] = patrones
    conflictos = []
    inicios = sorted(por_inicio)
    for i, uno in enumerate(inicios):
        for otro in inicios[i + 1 :]:
            if por_inicio[uno].core == por_inicio[otro].core:
                conflictos.append(
                    CoreConflict(
                        a=uno, b=otro, core=por_inicio[uno].core,
                        heptamer_a=por_inicio[uno].heptamer,
                        heptamer_b=por_inicio[otro].heptamer,
                    )
                )
    return tuple(conflictos)


# ────────────────────────────────── la corrida ────────────────────────────────────


@dataclass(frozen=True)
class OfftargetParams:
    null_draws: int = MIN_NULL_DRAWS
    null_seed: int = 0
    species_prefix: str = "mmu-"
    normalize_u_t: bool = True

    def __post_init__(self) -> None:
        if self.null_draws < MIN_NULL_DRAWS:
            raise ValueError(
                f"`null_draws` pide al menos {MIN_NULL_DRAWS} y se han pedido "
                f"{self.null_draws}. Se aborta: con menos sorteos el percentil de la "
                f"cola no tiene resolución, y es el único número accionable."
            )
        if not self.normalize_u_t:
            raise ValueError(
                "La normalización U↔T no se puede apagar: sin ella una guía en ADN y un "
                "3'UTR en ARN darian CERO sitios, y cero parece una buena noticia."
            )

    def with_changes(self, **cambios) -> "OfftargetParams":
        return replace(self, **cambios)

    def modified(self) -> tuple[str, ...]:
        base = OfftargetParams()
        return tuple(
            campo for campo in ("null_draws", "null_seed", "species_prefix")
            if getattr(self, campo) != getattr(base, campo)
        )

    @property
    def is_standard(self) -> bool:
        return not self.modified()

    def describe(self) -> list[str]:
        lineas = [
            f"sorteos de la nula={self.null_draws}  semilla={self.null_seed}  "
            # Misma distincion que en la tasa base: `None` no es `""`. Errata nº 18.
            "  controles="
            + (
                "SIN DECLARAR" if self.species_prefix is None
                else (self.species_prefix or "TODAS")
            ),
            "U↔T: siempre, y no se puede apagar.",
        ]
        tocados = self.modified()
        if tocados:
            lineas.append(
                "AJUSTES MODIFICADOS: " + ", ".join(tocados)
                + ". Viajan con el resultado: una nula con otra semilla o con otro "
                "número de sorteos NO es la misma nula."
            )
        else:
            lineas.append("Todos los ajustes en su valor por defecto.")
        return lineas


DEFAULTS = OfftargetParams()


@dataclass(frozen=True)
class LoadResult:
    start: int
    strand: str
    query: str
    sequence: str
    patterns: SitePatterns
    counts: Counts
    percentiles: dict[str, float]

    def describe(self) -> str:
        piezas = "  ".join(
            f"{c}={self.counts.sites[c]} (p{self.percentiles[c]:.1f})"
            for c in SITE_CLASSES
        )
        return f"3utr:{self.start:<6} {self.strand:<10} {self.patterns.heptamer}  {piezas}"


@dataclass(frozen=True)
class OfftargetScan:
    params: OfftargetParams
    source: str
    provenance: Provenance
    audit: IsoformAudit
    results: tuple[LoadResult, ...]
    nulls: dict[str, Null]
    controls: tuple[Control, ...]
    self_counts: dict[str, SelfCount]
    raw: str
    #: Esta corrida consume DOS ficheros. `provenance.md5` es el del catalogo de 3'UTR;
    #: este es el del fichero de MADUROS, del que salen los controles y la tasa base.
    #: Faltaba, y lo tapaba que el del catalogo si estuviera — la misma forma de la
    #: errata nº 12. Ver `insumos.CONSUMIDOS`.
    mature_md5: str = ""
    mature_version: str = ""

    def for_strand(self, strand: str) -> tuple[LoadResult, ...]:
        return tuple(r for r in self.results if r.strand == strand)

    def result_for(self, query: str) -> LoadResult | None:
        return next((r for r in self.results if r.query == query), None)

    @property
    def anomalous_self_counts(self) -> tuple[SelfCount, ...]:
        return tuple(s for s in self.self_counts.values() if s.anomalous)

    def export_block(self) -> str:
        """Material para defender la seleccion. Se lee SIN la app delante."""
        lineas = [
            "═══ Carga de off-targets mediada por seed ═══",
            "",
            "  PREGUNTA: ¿cuántos mensajeros llevan un sitio para la seed de esta hebra?",
            "",
            "  FICHERO:",
        ]
        lineas.extend(f"    {l}" for l in self.provenance.describe())
        lineas.append(f"    {self.audit.warning()}")
        lineas.extend(["", "  PARÁMETROS EFECTIVOS:"])
        lineas.extend(f"    {l}" for l in self.params.describe())
        lineas.extend(["", "  GEOMETRIA DE LAS CUATRO CLASES:"])
        lineas.extend(f"    {c}: {CLASS_GEOMETRY[c]}" for c in SITE_CLASSES)
        lineas.extend(["", f"  {WHY_NOT_SUMMED}", ""])

        for hebra in ("guia", "pasajera"):
            filas = self.for_strand(hebra)
            if not filas:
                continue
            lineas.append(f"  ── {hebra.upper()} ({len(filas)}) ──")
            lineas.extend(f"    {r.describe()}" for r in filas)
            lineas.append("")

        lineas.append("  LIMITACIONES — las tres van AQUÍ, no en un pie:")
        for lim in LIMITATIONS:
            lineas.append(f"    · {lim.title} [{lim.direction}]")
            lineas.append(f"      {lim.text}")
        lineas.extend(["", f"  {UPPER_BOUND_NOTE}", ""])

        lineas.append("  CONTROLES BIOLOGICOS (referencia de magnitud):")
        lineas.extend(f"    {c.describe()}" for c in self.controls)
        lineas.extend(["", f"  {CONTROLS_NOTE}", ""])

        lineas.append("  AUTOCONTEO SOBRE LA PROPIA DIANA:")
        lineas.extend(f"    {l}" for l in textwrap.wrap(
            WHY_THE_EXPECTED_DIFFERS, 86))
        lineas.extend(f"    {s.describe()}" for s in self.self_counts.values())
        lineas.append("")

        for clave, nula in self.nulls.items():
            lineas.append(f"  NULA para composición {clave}:")
            lineas.extend(f"    {l}" for l in nula.describe())
        lineas.extend(["", f"  {USE_NOTE}", "", f"  {WHY_NOT_BLAST}"])
        return "\n".join(lineas) + "\n"


def run_scan(selection, *, catalog: Catalog | None, mature,
             params: OfftargetParams = DEFAULTS, species: str, starts,
             guides: bool, passengers: bool, target: str,
             target_label: str) -> OfftargetScan:
    """Corre el conteo. Ejecuta: es subcadena contra un fichero ya cargado."""
    if catalog is None:
        raise ShmirDesignError(
            f"No hay catalogo de 3'UTR cargado, así que la carga de off-targets por seed "
            f"no se puede contar. Falta `{MISSING_FILE}`. El frente queda NOT_RUN — que "
            f"no es PASS y sobre todo NO ES CERO: no saber cuántos sitios hay no es lo "
            f"mismo que no haber ninguno."
        )
    if not guides and not passengers:
        raise ShmirDesignError(
            "No se ha marcado ni guía ni pasajera: son dos consultas y hace falta al "
            "menos una. Se aborta."
        )
    pedidos = list(dict.fromkeys(int(s) for s in starts))
    if not pedidos:
        raise ShmirDesignError(
            "No se ha marcado ningún candidato; se aborta en vez de emitir una corrida "
            "vacía que parezca haber corrido."
        )

    # Las hebras salen de `seed_scan` a proposito: los dos modales tienen que comparar
    # EXACTAMENTE las mismas secuencias, y una segunda construccion de la pasajera aqui
    # acabaria divergiendo de la del otro modal sin que nadie lo notara.
    from .seed_scan import _strands

    # La ventana de cada candidato EN COORDENADAS DE 3'UTR, que es el marco de `target`.
    # Es lo unico que permite decir cual de los sitios de la propia diana es EL SUYO; sin
    # ella no se marca ninguno, porque deducirlo del orden seria un supuesto.
    # DE LOS PEDIDOS, no del panel: con el alcance grande, un candidato de fuera se
    # quedaba sin ventana y por tanto sin poder marcar CUAL de los sitios de la propia
    # diana es el suyo — el autoconteo perderia justo su referencia (errata nº 107).
    ventanas = {
        c.start: (
            selection.window_of(c).inicio_3utr, selection.window_of(c).fin_3utr
        )
        for c in selection.choices_for(pedidos)
    }
    nulas: dict[str, Null] = {}
    resultados: list[LoadResult] = []
    autoconteos: dict[str, SelfCount] = {}
    crudas: list[str] = []

    for inicio, hebra, secuencia in _strands(
        selection, species, pedidos, guides, passengers
    ):
        patrones = site_patterns(secuencia)
        composicion = "".join(sorted(patrones.heptamer))
        nula = nulas.get(composicion)
        if nula is None:
            nula = null_distribution(
                catalog.index, patrones,
                draws=params.null_draws, seed=params.null_seed,
            )
            nulas[composicion] = nula
        cuentas = count_over(catalog.records, patrones)
        percentiles = {
            clase: nula.percentile(clase, cuentas.sites[clase])
            for clase in SITE_CLASSES
        }
        # LA CLAVE SE DERIVA. Habia CUATRO sitios armando este identificador —el
        # FASTA de consulta, la ficha, este scan y el de off-targets— y al pasar el
        # FASTA al slug (errata nº 42) los demas se quedaron atras. Una corrida
        # guardada con una clave y buscada con otra no se encuentra, y el sintoma es
        # identico al de no haberla guardado. Principio nº 13 sobre una CLAVE.
        from .presentation import query_name

        consulta = query_name(species, inicio, hebra)
        resultados.append(
            LoadResult(
                start=inicio, strand=hebra, query=consulta, sequence=secuencia,
                patterns=patrones, counts=cuentas, percentiles=percentiles,
            )
        )
        # LA HEBRA VIAJA, y de ella sale el ESPERADO. Sin pasarla, la pasajera se
        # contaba con el esperado de la guia y su cero —que es lo normal, porque es
        # SENTIDO respecto de la diana— salia como anomalia: siete falsos de once.
        autoconteos[consulta] = self_count(
            secuencia, target=target, target_label=target_label, query=consulta,
            window=ventanas.get(inicio), strand_name=hebra,
        )
        crudas.append(
            "\t".join(
                [consulta, patrones.heptamer]
                + [
                    f"{clase}={cuentas.sites[clase]}:p{percentiles[clase]:.1f}"
                    for clase in SITE_CLASSES
                ]
            )
        )

    return OfftargetScan(
        params=params,
        source=f"{catalog.provenance.source} ({catalog.provenance.assembly})",
        provenance=catalog.provenance,
        audit=catalog.audit,
        results=tuple(resultados),
        nulls=nulas,
        controls=controls_from_mature(
            mature, catalog.index, prefix=params.species_prefix
        ),
        self_counts=autoconteos,
        raw="\n".join(crudas) + "\n",
        mature_md5=mature.checksum, mature_version=mature.version,
    )
