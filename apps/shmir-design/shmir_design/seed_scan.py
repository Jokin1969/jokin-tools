"""Colision de seed: el modal que SI ejecuta.

A diferencia del de BLAST, aqui no hay red de por medio ni orden que copiar. El calculo
es **busqueda de subcadena** contra `mature.fa`, que ya esta cargado y verificado con su
md5. Boton → resultado.

Lo que este modulo cuida no es el calculo —que es trivial— sino que el resultado NO SE
PUEDA LEER MAL:

  - la ventana de seed **viaja con cada resultado**: una corrida de 2-7 no puede
    presentarse como 2-8, y la tasa base de las dos ni se parece;
  - **guia y pasajera nunca se funden** en un veredicto: son dos consultas y salen en
    dos filas;
  - la **tasa base** va siempre pegada al resultado, porque sin ella un `AVISO` parece
    mas grave de lo que es;
  - la normalizacion `U`↔`T` es **siempre** y va **declarada**: un desajuste de alfabeto
    daria cero colisiones y parece una buena noticia.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import ShmirDesignError
from .mirna import MIR30_FAMILY, core_hits

#: Las dos ventanas que se admiten, y su longitud. Nada mas: una ventana inventada
#: cambiaria el espacio de seeds y la tasa base sin que nadie lo note.
SEED_WINDOWS = {"2-8": (2, 8), "2-7": (2, 7)}

LEVELS = ("nucleo", "ampliado", "ambos")

NORMALIZATION_NOTE = (
    "Normalización U↔T: SIEMPRE, y no se puede apagar. miRBase da los maduros en ARN y "
    "nuestras guías van en ADN; sin normalizar, la comparación daria CERO COLISIONES en "
    "todas — y cero colisiones parece una buena noticia. Es un desajuste de alfabeto "
    "disfrazado de resultado limpio."
)

MIR30_NOTE = (
    "COLISIÓN CON LA FAMILIA miR-30: lectura distinta y PEOR. Nuestro andamio es miR-E, "
    "derivado de miR-30a, así que aquí no se compite solo por la red de dianas de ese "
    "miARN — la horquilla que se construye SE PARECE a un miARN endogeno abundante del "
    "mismo tejido. Se marca aparte a propósito."
)

WHAT_THIS_DOES_NOT_ANSWER = (
    "LO QUE ESTE MODAL NO CONTESTA. Contesta «¿mi seed es la de un miARN conocido?». NO "
    "contesta «¿cuántos mensajeros llevan mi seed?», que es la CARGA de off-targets y "
    "necesita `transcriptoma_3utr.fa`. Son dos preguntas y DOS FRENTES: este cierra "
    "`seed_colision`, el otro es `offtarget_seed` y sigue en NOT_RUN mientras falte ese "
    "fichero."
)


@dataclass(frozen=True)
class SeedParams:
    window: str = "2-8"
    #: Prefijo de miRBase. `None` = NO DECLARADO, que NO es lo mismo que `""` = todas
    #: las especies del fichero, y por eso son dos valores y no uno. El unico origen es
    #: `species.mirbase_prefix()`: un `mmu-` por defecto sobre una guia de conejo daba
    #: CERO colisiones, que parece una buena noticia.
    species_prefix: str | None = None
    level: str = "ambos"
    normalize_u_t: bool = True

    def __post_init__(self) -> None:
        if self.window not in SEED_WINDOWS:
            raise ValueError(
                f"Ventana de seed {self.window!r} desconocida; las que hay son "
                f"{', '.join(sorted(SEED_WINDOWS))}. Se aborta: otra ventana cambia el "
                f"espacio de seeds y la tasa base sin que nadie lo note."
            )
        if self.level not in LEVELS:
            raise ValueError(
                f"Nivel {self.level!r} desconocido; los que hay son "
                f"{', '.join(LEVELS)}. Se aborta."
            )
        if not self.normalize_u_t:
            raise ValueError(
                f"La normalización U↔T no se puede apagar. {NORMALIZATION_NOTE}"
            )

    @classmethod
    def for_species(cls, name: str, **cambios) -> "SeedParams":
        """Los parametros de UNA especie. El prefijo sale de `species`, no se teclea."""
        from .species import mirbase_prefix

        return cls(species_prefix=mirbase_prefix(name), **cambios)

    def with_changes(self, **cambios) -> "SeedParams":
        return replace(self, **cambios)

    @property
    def declared(self) -> bool:
        return self.species_prefix is not None

    def require_prefix(self) -> str:
        if self.species_prefix is None:
            raise ShmirDesignError(
                "No hay prefijo de especie declarado para esta corrida de colisión de "
                "seed. NO se pone `mmu-` por defecto: con el prefijo equivocado la "
                "comparación da CERO colisiones y eso parece una buena noticia. El "
                "prefijo sale de `species.mirbase_prefix(nombre)`, que aborta si esa "
                "especie no lo tiene declarado. Usa `SeedParams.for_species(nombre)`. "
                "Si lo que quieres es NO filtrar por especie, eso se dice con `\"\"`, "
                "que es otro valor y significa otra cosa."
            )
        return self.species_prefix

    @property
    def length(self) -> int:
        inicio, fin = SEED_WINDOWS[self.window]
        return fin - inicio + 1

    @property
    def space(self) -> int:
        return 4 ** self.length

    def modified(self) -> tuple[str, ...]:
        # La ESPECIE no cuenta como ajuste modificado: es la identidad de la corrida.
        # Si contara, toda corrida que no fuera de raton saldria marcada en rojo y el
        # rojo dejaria de significar «alguien toco esto».
        base = SeedParams(species_prefix=self.species_prefix)
        return tuple(
            campo for campo in ("window", "level")
            if getattr(self, campo) != getattr(base, campo)
        )

    @property
    def is_standard(self) -> bool:
        return not self.modified()

    def seed_of(self, sequence: str) -> str:
        inicio, fin = SEED_WINDOWS[self.window]
        limpia = "".join(str(sequence).split()).upper().replace("U", "T")
        if len(limpia) < fin:
            raise ShmirDesignError(
                f"La hebra mide {len(limpia)} nt y la ventana {self.window} necesita "
                f"llegar a la posición {fin}; se aborta en vez de comparar media seed."
            )
        return limpia[inicio - 1:fin]

    def describe(self) -> list[str]:
        lineas = [
            f"window={self.window} ({self.length} nt, espacio {self.space})  "
            f"especie="
            + (
                "SIN DECLARAR" if self.species_prefix is None
                else (self.species_prefix or "TODAS")
            )
            + f"  nivel={self.level}",
            f"U↔T: siempre. {NORMALIZATION_NOTE}",
        ]
        tocados = self.modified()
        if tocados:
            lineas.append(
                "AJUSTES MODIFICADOS: " + ", ".join(tocados)
                + ". Viajan con el resultado: una corrida de "
                f"{self.window} no puede leerse como una de 2-8."
            )
        else:
            lineas.append("Todos los ajustes en su valor por defecto.")
        return lineas


DEFAULTS = SeedParams()


@dataclass(frozen=True)
class PreviewRow:
    """Lo que se va a comparar, ANTES de correr nada. Es la mitad del valor."""

    start: int
    strand: str
    sequence: str
    heptamer: str
    shared_with: tuple[int, ...] = ()
    #: Los que comparten el NUCLEO de 6 nt sin compartir heptamero. Es otro eje: dos
    #: candidatos que difieren solo en la posicion 8 tienen heptameros distintos —asi
    #: que la colision con miARN no los empareja— y sin embargo comparten casi toda su
    #: red de off-targets, porque las cuatro clases de sitio se construyen sobre ese
    #: nucleo. Hasta hoy eso no se veia en ninguna parte.
    shared_core_with: tuple[int, ...] = ()
    core: str = ""
    checked: bool = True

    def describe(self) -> str:
        compartido = (
            "  ⚠ COMPARTE heptamero con 3utr:"
            + ", 3utr:".join(str(s) for s in self.shared_with)
            if self.shared_with else ""
        )
        if self.shared_core_with:
            compartido += (
                "  ⚠ COMPARTE NÚCLEO de 6 nt con 3utr:"
                + ", 3utr:".join(str(s) for s in self.shared_core_with)
            )
        return (
            f"3utr:{self.start:<6} {self.strand:<10} {self.sequence:<24} "
            f"{self.heptamer}{compartido}"
        )


def _strands(selection, species: str, starts, guides: bool, passengers: bool):
    from .blocks import build_block
    from .scaffold import SGEP_SCAFFOLD

    # Panel MAS sitios elegibles, resuelto por el UNICO sitio que lo hace. Aqui se
    # resolvia contra `chosen` y se abortaba, asi que este modal y el de off-targets
    # —que usa estas mismas hebras— rechazaban el alcance grande que la propia app
    # ofrece (errata nº 107). Un inicio que no sea de ninguna ventana elegible sigue
    # abortando, y lo dice `choices_for`.
    por_inicio = {c.start: c for c in selection.choices_for(starts)}
    for inicio in starts:
        ventana = selection.window_of(por_inicio[inicio])
        guia = ventana.evaluation.guide
        if guides:
            yield inicio, "guia", guia.replace("U", "T")
        if passengers:
            yield inicio, "pasajera", build_block(
                guia, scaffold=SGEP_SCAFFOLD
            ).passenger.replace("U", "T")


def preview_rows(selection, *, species: str, params: SeedParams = DEFAULTS, starts=None,
                 guides: bool = True, passengers: bool = True) -> tuple[PreviewRow, ...]:
    """La tabla de lo que se va a comparar, con los heptameros COMPARTIDOS marcados.

    Dos candidatos con la misma seed no son dos apuestas independientes en este eje, y
    eso tiene que verse ANTES de correr, no despues.
    """
    if not params.declared:
        params = SeedParams.for_species(
            species, window=params.window, level=params.level
        )
    if starts is None:
        starts = tuple(c.start for c in selection.selection.chosen)
    from .offtarget import site_patterns

    crudas = [
        (
            inicio, hebra, secuencia, params.seed_of(secuencia),
            site_patterns(secuencia).core,
        )
        for inicio, hebra, secuencia in _strands(
            selection, species, starts, guides, passengers
        )
    ]
    por_hepta: dict[str, list[int]] = {}
    por_nucleo: dict[str, list[int]] = {}
    for inicio, _, _, hepta, nucleo in crudas:
        por_hepta.setdefault(hepta, []).append(inicio)
        por_nucleo.setdefault(nucleo, []).append(inicio)
    return tuple(
        PreviewRow(
            start=inicio, strand=hebra, sequence=secuencia, heptamer=hepta,
            core=nucleo,
            shared_with=tuple(sorted(set(por_hepta[hepta]) - {inicio})),
            # Solo los que comparten NUCLEO y NO heptamero: si comparten heptamero ya
            # sale en la otra columna, y repetirlo haria que la nueva pareciera
            # redundante justo cuando dice algo distinto.
            shared_core_with=tuple(
                sorted(set(por_nucleo[nucleo]) - set(por_hepta[hepta]))
            ),
        )
        for inicio, hebra, secuencia, hepta, nucleo in crudas
    )


@dataclass(frozen=True)
class BaseRate:
    """La tasa base, DERIVADA del fichero cargado. No se teclea."""

    matures: int
    distinct: int
    space: int
    window: str
    species_prefix: str

    @property
    def fraction(self) -> float:
        return self.distinct / self.space

    @property
    def short(self) -> str:
        """La tasa base en UNA CELDA, para que viaje con la fila y con el CSV.

        `describe()` es el parrafo que se pinta encima de la tabla; ese se lee una vez y
        no viaja en la descarga. La fila se lee siempre, y sin la tasa al lado un LIMPIO
        no dice si es notable o es lo que predice el azar.
        """
        return f"{self.fraction * 100:.0f}% ({self.distinct}/{self.space}, {self.window})"

    def describe(self) -> str:
        return (
            f"TASA BASE: {self.matures} maduro(s) "
            # `None` y `""` NO son lo mismo y estaba escrito que no lo eran: el primero
            # es «nadie declaro la especie» y el segundo «todas, a proposito». El `or`
            # los daba los dos por el segundo. Errata nº 18.
            + (
                "con la especie SIN DECLARAR"
                if self.species_prefix is None
                else (
                    self.species_prefix
                    or "de todas las especies del fichero (elegido a propósito)"
                )
            )
            + f" dan "
            f"{self.distinct} seed(s) distinta(s) de {self.window} sobre un espacio de "
            f"{self.space}, así que cerca del {self.fraction:.0%} de las guías colisiona "
            f"con alguna POR AZAR. Sin esta cifra al lado, un AVISO parece más grave de "
            f"lo que es. Sale del fichero cargado y del filtro de especie que se use: no "
            f"está tecleada."
        )


def base_rate(mature, params: SeedParams = DEFAULTS) -> BaseRate:
    prefijo = params.require_prefix()
    largo = params.length
    nombres = 0
    seeds = set()
    for seed, lista in mature.seeds.items():
        propios = [n for n in lista if not prefijo or n.startswith(prefijo)]
        if not propios:
            continue
        nombres += len(propios)
        seeds.add(seed[:largo])
    return BaseRate(
        matures=nombres, distinct=len(seeds), space=params.space,
        window=params.window, species_prefix=prefijo,
    )


@dataclass(frozen=True)
class SeedCollision:
    name: str
    core: bool
    mir30: bool


@dataclass(frozen=True)
class SeedResult:
    start: int
    strand: str
    query: str
    sequence: str
    heptamer: str
    window: str
    collisions: tuple[SeedCollision, ...]
    level: str

    @property
    def mir30(self) -> bool:
        return any(c.mir30 for c in self.collisions)

    def describe(self) -> str:
        if not self.collisions:
            return (
                f"3utr:{self.start:<6} {self.strand:<10} {self.heptamer}  LIMPIO — "
                f"ninguna colisión entre los maduros del filtro."
            )
        nombres = ", ".join(c.name for c in self.collisions)
        marca = "  ⚠ miR-30" if self.mir30 else ""
        return (
            f"3utr:{self.start:<6} {self.strand:<10} {self.heptamer}  {self.level}"
            f"{marca} — {len(self.collisions)}: {nombres}"
        )


@dataclass(frozen=True)
class SeedScan:
    params: SeedParams
    source: str
    results: tuple[SeedResult, ...]
    base_rate: BaseRate
    raw: str
    #: md5 del fichero de maduros que se uso, como CAMPO y no dentro de `source`.
    #: `source` es `MatureSet.provenance`, que lleva el checksum en medio de una frase:
    #: se lee, pero no se compara. OBSOLETO se deriva comparando md5, asi que un md5 en
    #: prosa no sirve — y este es el frente cuyo fichero mas se va a reemplazar, porque
    #: miRBase publica versiones. Ver `insumos.CONSUMIDOS`.
    mature_md5: str = ""
    mature_version: str = ""

    def for_strand(self, strand: str) -> tuple[SeedResult, ...]:
        return tuple(r for r in self.results if r.strand == strand)

    @property
    def mir30_results(self) -> tuple[SeedResult, ...]:
        return tuple(r for r in self.results if r.mir30)

    def export_block(self) -> str:
        """Material para defender la seleccion. Se lee SIN la app delante."""
        lineas = [
            "═══ Colisión de seed con miARN endogeno ═══",
            "",
            "  PREGUNTA: ¿la seed de esta hebra es la de un miARN maduro conocido?",
            f"  FUENTE: {self.source}",
            "",
            "  PARÁMETROS EFECTIVOS:",
        ]
        lineas.extend(f"    {l}" for l in self.params.describe())
        lineas.extend(["", f"  {self.base_rate.describe()}", ""])
        for hebra in ("guia", "pasajera"):
            filas = self.for_strand(hebra)
            if not filas:
                continue
            lineas.append(f"  ── {hebra.upper()} ({len(filas)}) ──")
            lineas.extend(f"    {r.describe()}" for r in filas)
            lineas.append("")
        lineas.append(
            "  Guía y pasajera van SEPARADAS y no se suman en un veredicto: la pasajera "
            "se carga a RISC"
        )
        lineas.append(
            "  en alguna proporción, así que sus off-targets son igual de reales, pero "
            "son otra consulta."
        )
        if self.mir30_results:
            lineas.extend(["", f"  ⚠ {MIR30_NOTE}"])
        lineas.extend(["", f"  {WHAT_THIS_DOES_NOT_ANSWER}"])
        return "\n".join(lineas) + "\n"


def run_scan(
    selection, *, mature, params: SeedParams = DEFAULTS, species: str,
    starts, guides: bool, passengers: bool,
) -> SeedScan:
    """Corre la busqueda. Esto SI ejecuta: es subcadena contra un fichero ya cargado."""
    if mature is None:
        raise ShmirDesignError(
            "No hay tabla de maduros cargada (`mature.fa`), así que no hay contra que "
            "comparar. NOT_RUN no es PASS: se aborta en vez de devolver cero colisiones."
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

    # Si los parametros no traen especie declarada, se resuelve con la de la CORRIDA —
    # que ya viene por parametro— pasando por `species`. Asi no hay ningun camino que
    # acabe usando `mmu-` sin haber preguntado, y una especie sin prefijo declarado
    # aborta aqui en vez de dar cero colisiones.
    if not params.declared:
        params = SeedParams.for_species(
            species, window=params.window, level=params.level
        )
    prefijo = params.require_prefix()
    largo = params.length
    # Indice por la ventana pedida: con 2-7 una colision es cualquier maduro cuya seed
    # 2-8 EMPIECE por esas 6 bases. No se re-parsea el fichero: se agrupa el indice.
    indice: dict[str, list[str]] = {}
    for seed, nombres in mature.seeds.items():
        propios = [n for n in nombres if not prefijo or n.startswith(prefijo)]
        if propios:
            indice.setdefault(seed[:largo], []).extend(propios)

    resultados = []
    crudas = []
    for inicio, hebra, secuencia in _strands(
        selection, species, pedidos, guides, passengers
    ):
        hepta = params.seed_of(secuencia)
        nombres = sorted(set(indice.get(hepta, ())))
        nucleo = {h.name for h in core_hits(nombres)}
        colisiones = tuple(
            SeedCollision(
                name=n, core=n in nucleo, mir30=MIR30_FAMILY in n,
            )
            for n in nombres
        )
        if params.level == "nucleo":
            colisiones = tuple(c for c in colisiones if c.core)
        elif params.level == "ampliado":
            colisiones = tuple(c for c in colisiones if not c.core)
        nivel = (
            "FAIL" if any(c.core for c in colisiones)
            else "AVISO" if colisiones else "LIMPIO"
        )
        # LA CLAVE SE DERIVA. Habia CUATRO sitios armando este identificador —el
        # FASTA de consulta, la ficha, este scan y el de off-targets— y al pasar el
        # FASTA al slug (errata nº 42) los demas se quedaron atras. Una corrida
        # guardada con una clave y buscada con otra no se encuentra, y el sintoma es
        # identico al de no haberla guardado. Principio nº 13 sobre una CLAVE.
        from .presentation import query_name

        consulta = query_name(species, inicio, hebra)
        resultados.append(
            SeedResult(
                start=inicio, strand=hebra, query=consulta, sequence=secuencia,
                heptamer=hepta, window=params.window, collisions=colisiones,
                level=nivel,
            )
        )
        crudas.append(f"{consulta}\t{hepta}\t{nivel}\t{','.join(nombres)}")

    return SeedScan(
        params=params, source=mature.provenance, results=tuple(resultados),
        base_rate=base_rate(mature, params), raw="\n".join(crudas) + "\n",
        mature_md5=mature.checksum, mature_version=mature.version,
    )
