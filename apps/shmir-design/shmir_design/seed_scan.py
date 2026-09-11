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

from dataclasses import dataclass, field, replace

from .coords import Frame, label, tiled_frame
from .errors import ShmirDesignError
from .mirna import MIR30_FAMILY, core_hits

#: Las dos ventanas que se admiten, y su longitud. Nada mas: una ventana inventada
#: cambiaria el espacio de seeds y la tasa base sin que nadie lo note.
SEED_WINDOWS = {"2-8": (2, 8), "2-7": (2, 7)}

#: La ventana ESTÁNDAR. Se DERIVA de aquí en los dos sitios que la necesitan —el
#: veredicto y el valor por defecto de `SeedParams`— en vez de escribirse dos veces: dos
#: literales acabarían diciendo «2-8» sobre una corrida de 2-7.
STANDARD_WINDOW = "2-8"

WHY_2_8_IS_THE_SEED = (
    "La seed son las posiciones 2-8 POR DEFINICIÓN del bolsillo de Ago2, no por "
    "convención de este proyecto. Con 2-7 el espacio de seeds pasa de 16.384 a 4.096, "
    "así que la tasa base sube y un LIMPIO SIGNIFICA MUCHO MENOS: hay cuatro veces más "
    "sitio donde no chocar. Por eso la ventana no estándar viaja en el VEREDICTO y no "
    "sólo en la cabecera de parámetros — la cabecera se lee una vez y el veredicto se "
    "lee siempre, y además se descarga."
)

WHY_THE_RATE_FOLLOWS_THE_LEVEL = (
    "La tasa base se calcula sobre EL CONJUNTO QUE SE CONSULTA, no sobre el fichero "
    "entero. Con `level=nucleo` el veredicto sólo se emite contra los del núcleo, así "
    "que una tasa calculada sobre todos los maduros de la especie NO DESCRIBE lo que el "
    "resultado mide — y se equivoca hacia el lado cómodo: hace parecer excepcionalmente "
    "limpio algo que sólo se comparó contra diez secuencias. Reportado con la corrida "
    "delante el 2026-09-06: cabecera del 31 % y resultado de 1 de 176."
)

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

def what_this_does_not_answer(species: str = "") -> str:
    """Lo que este modal NO contesta, con el fichero que falta nombrado PARA ESA especie.

    Era una constante con `transcriptoma_3utr.fa` escrito, o sea el nombre MURINO: en
    humano el gestor pide `transcriptoma_3utr_human.fa`, asi que el bloque exportable
    —«material para defender la seleccion»— mandaba a conseguir un fichero que nadie
    pide (errata nº 157). El nombre se le pide a `species.required_files` por su ROL.

    Sin especie NO se inventa un nombre: `missing_file("")` nombra el rol, que es lo
    que el gestor entiende.
    """
    from .offtarget import missing_file_text  # noqa: PLC0415

    return (
        f"LO QUE ESTE MODAL NO CONTESTA. Contesta «¿mi seed es la de un miARN "
        f"conocido?». NO contesta «¿cuántos mensajeros llevan mi seed?», que es la "
        f"CARGA de off-targets y necesita {missing_file_text(species)}. Son dos "
        f"preguntas "
        f"y DOS FRENTES: este cierra `seed_colision`, el otro es `offtarget_seed` y "
        f"sigue en NOT_RUN mientras falte ese fichero."
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
    #: El marco de `start` y de los compartidos, DERIVADO de la anatomia de la corrida.
    #: Aqui iba `3utr:` escrito a mano — el quinto y sexto sitio de la errata nº 121.
    frame: Frame = field(kw_only=True)

    def describe(self) -> str:
        def etiquetas(starts) -> str:
            return ", ".join(label(s, self.frame) for s in starts)

        compartido = (
            "  ⚠ COMPARTE heptamero con " + etiquetas(self.shared_with)
            if self.shared_with else ""
        )
        if self.shared_core_with:
            compartido += (
                "  ⚠ COMPARTE NÚCLEO de 6 nt con "
                + etiquetas(self.shared_core_with)
            )
        etiqueta = label(self.start, self.frame)
        return (
            f"{etiqueta:<12} {self.strand:<10} {self.sequence:<24} "
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
    marco = tiled_frame(getattr(selection, "anatomy", None))
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
            frame=marco,
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
    #: EL CONJUNTO sobre el que se ha contado, que es el mismo contra el que se emite el
    #: veredicto. Ver `WHY_THE_RATE_FOLLOWS_THE_LEVEL`.
    level: str = "ambos"
    #: Los prefijos que se han UNIDO, cuando esta tasa es la de la union de los ejes.
    #: Vacio = es la de un solo eje, que es la que va pegada a un veredicto. Es un campo
    #: y no un `+` dentro de `species_prefix` porque de el depende QUE PREGUNTA contesta
    #: esta cifra, y eso no se deduce mirando si una cadena trae un signo.
    union_of: tuple[str, ...] = ()

    @property
    def is_union(self) -> bool:
        return bool(self.union_of)

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
        return (
            f"{self.fraction * 100:.0f}% ({self.distinct}/{self.space}, "
            f"{self.window}, {self.level})"
        )

    def describe(self) -> str:
        if self.is_union:
            # LA DE LA UNION CONTESTA OTRA PREGUNTA, y lo dice con esas palabras: sin
            # eso, dos tasas distintas en la misma pantalla se leen como una
            # discrepancia y alguien promedia. Ver `union_base_rate`.
            return (
                f"TASA BASE DE LA UNIÓN ({' + '.join(self.union_of)}): "
                f"{self.matures} maduro(s) dan {self.distinct} seed(s) distinta(s) de "
                f"{self.window} sobre un espacio de {self.space}, así que cerca del "
                f"{self.fraction:.0%} de las guías colisiona con algo EN ALGUNO DE LOS "
                f"DOS EJES por azar. NO es la tasa de ningún veredicto —cada eje lleva "
                f"la suya— y no la sustituye: ésta es la referencia de un «limpio en "
                f"los dos», que es la pregunta del CANDIDATO. Pegarla a un veredicto de "
                f"un solo eje describiría un conjunto contra el que ese veredicto no se "
                f"ha medido. {WHY_THE_RATE_FOLLOWS_THE_LEVEL}"
            )
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
            + f" DEL CONJUNTO CONSULTADO ({_LEVEL_LABELS[self.level]}) dan "
            f"{self.distinct} seed(s) distinta(s) de {self.window} sobre un espacio de "
            f"{self.space}, así que cerca del {self.fraction:.0%} de las guías colisiona "
            f"con alguna POR AZAR. Sin esta cifra al lado, un AVISO parece más grave de "
            f"lo que es. Sale del fichero cargado, del filtro de especie y DEL NIVEL: no "
            f"está tecleada. " + WHY_THE_RATE_FOLLOWS_THE_LEVEL
        )


#: Como se llama cada conjunto al imprimirlo. En un solo sitio: la etiqueta viaja en el
#: parrafo y en la celda, y dos literales acabarian discrepando.
_LEVEL_LABELS = {
    "nucleo": "el NÚCLEO de abundantes en cerebro",
    "ampliado": "los maduros de la especie FUERA del núcleo",
    "ambos": "todos los maduros de la especie",
}


def union_base_rate(mature, params: SeedParams, prefixes) -> BaseRate:
    """La tasa base de la UNION de los ejes. Contesta OTRA pregunta, y por eso va aparte.

    **NO sustituye a la de cada eje, y confundirlas es la errata nº 118.** La tasa de un
    veredicto tiene que describir EL CONJUNTO QUE SE CONSULTA
    (`WHY_THE_RATE_FOLLOWS_THE_LEVEL`), y con los veredictos separados por organismo cada
    uno se compara contra los maduros de SU prefijo: una tasa de la union pegada al
    veredicto `hsa-` describiria un conjunto contra el que ese veredicto no se ha medido,
    y lo haria hacia el lado comodo —hace parecer excepcionalmente limpio algo que solo
    se comparo contra la mitad—.

    Lo que SI contesta es la pregunta del CANDIDATO, que es otra: «¿cual es la
    probabilidad de que una guia cualquiera choque con algo en ALGUNO de los dos ejes?».
    Esa es la referencia de un «limpio en los dos», y sin ella un candidato que pasa los
    dos ejes parece el doble de notable de lo que es.

    Con un solo prefijo devuelve exactamente lo mismo que `base_rate`: la union de uno
    es el, y asi no hay dos numeros donde hay uno.
    """
    from .mirna import core_hits  # noqa: PLC0415

    limpios = [str(p) for p in prefixes]
    if not limpios:
        raise ShmirDesignError(
            "No hay ningún prefijo de miRBase en el eje, así que no hay unión que "
            "calcular. Se aborta en vez de devolver una tasa de cero, que se leería "
            "como «no colisiona nada por azar»."
        )
    largo = params.length
    nombres = 0
    seeds = set()
    for seed, lista in mature.seeds.items():
        propios = [
            n for n in lista
            if any(not prefijo or n.startswith(prefijo) for prefijo in limpios)
        ]
        if params.level != "ambos":
            del_nucleo = {h.name for h in core_hits(propios)}
            propios = [
                n for n in propios
                if (n in del_nucleo) == (params.level == "nucleo")
            ]
        if not propios:
            continue
        nombres += len(propios)
        seeds.add(seed[:largo])
    return BaseRate(
        matures=nombres, distinct=len(seeds), space=params.space,
        window=params.window, species_prefix="+".join(limpios), level=params.level,
        # `union_of` SOLO CON MAS DE UNO, y no es un detalle de formato: de ese campo
        # depende QUE PREGUNTA dice contestar esta cifra. Con un solo eje no hay una
        # segunda pregunta —«¿es notable estar limpio en los DOS?» no existe— y
        # marcarla como union haria que la app pintara dos veces el mismo numero, una
        # de ellas diciendo que no es la de ningun veredicto. Que es justo al reves.
        union_of=tuple(limpios) if len(limpios) > 1 else (),
    )


def base_rate(mature, params: SeedParams = DEFAULTS) -> BaseRate:
    """La tasa base DEL CONJUNTO QUE SE CONSULTA. Ver `WHY_THE_RATE_FOLLOWS_THE_LEVEL`.

    El nivel entra en la cuenta por el mismo camino por el que entra en el veredicto
    —`mirna.core_hits`—, no por una segunda definición de qué es el núcleo: si fueran
    dos, la tasa podría describir un conjunto y el veredicto otro, que es exactamente el
    defecto que esto cierra.
    """
    from .mirna import core_hits  # noqa: PLC0415

    prefijo = params.require_prefix()
    largo = params.length
    nombres = 0
    seeds = set()
    for seed, lista in mature.seeds.items():
        propios = [n for n in lista if not prefijo or n.startswith(prefijo)]
        if params.level != "ambos":
            del_nucleo = {h.name for h in core_hits(propios)}
            propios = [
                n for n in propios
                if (n in del_nucleo) == (params.level == "nucleo")
            ]
        if not propios:
            continue
        nombres += len(propios)
        seeds.add(seed[:largo])
    return BaseRate(
        matures=nombres, distinct=len(seeds), space=params.space,
        window=params.window, species_prefix=prefijo, level=params.level,
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
    #: El marco de `start`, DERIVADO de la anatomía de la corrida (errata nº 121).
    frame: Frame = field(kw_only=True)
    #: La marca de que el nucleo de abundancia es una lista PRESTADA. Va en la FILA y no
    #: solo en la cabecera, por el mismo motivo que la ventana y el marco: la cabecera se
    #: lee una vez y el veredicto se lee siempre — quien copia una linea a un correo se
    #: lleva el FAIL sin la cabecera. Vacia cuando la lista es de la especie del diseño:
    #: un aviso que sale siempre deja de leerse.
    core_mark: str = field(default="", kw_only=True)

    @property
    def mir30(self) -> bool:
        return any(c.mir30 for c in self.collisions)

    @property
    def window_standard(self) -> bool:
        """Se DERIVA de la ventana de la corrida; no es un campo que alguien rellene."""
        return self.window == STANDARD_WINDOW

    @property
    def verdict(self) -> str:
        """El veredicto CON la ventana pegada cuando no es la estándar.

        `level` sigue siendo el estado a secas —lo leen los almacenes y el semáforo— y
        esto es lo que se PINTA. Que la ventana viaje aquí y no sólo en la cabecera es
        el mismo criterio que puso la tasa base en la fila: la cabecera se lee una vez
        y el veredicto se lee siempre. Ver `WHY_2_8_IS_THE_SEED`.
        """
        if self.window_standard:
            return self.level
        return f"{self.level} (ventana {self.window}, NO ESTÁNDAR)"

    def describe(self) -> str:
        etiqueta = label(self.start, self.frame)
        if not self.collisions:
            return (
                f"{etiqueta:<12} {self.strand:<10} {self.heptamer}  "
                f"{self.verdict} — ninguna colisión entre los maduros del filtro."
            )
        nombres = ", ".join(c.name for c in self.collisions)
        marca = "  ⚠ miR-30" if self.mir30 else ""
        # SOLO donde el veredicto lo produce el NUCLEO: pegarla a un AVISO de la capa
        # ampliada seria marcar filas que esa lista no decide.
        if self.core_mark and any(c.core for c in self.collisions):
            marca += f"  {self.core_mark}"
        return (
            f"{etiqueta:<12} {self.strand:<10} {self.heptamer}  {self.verdict}"
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
    #: La nota ENTERA del nucleo prestado. Va en la corrida —no en cada fila— porque es
    #: propiedad de la LISTA y de la especie del diseño; la fila lleva la marca corta.
    #: Vacia cuando la lista es de la especie que se esta diseñando: un aviso que sale
    #: siempre deja de leerse.
    core_note: str = ""
    #: LA ESPECIE DEL DISEÑO, que NO es `params.species_prefix` —ese es el filtro de
    #: miRBase—. De ella sale el nombre del fichero que el bloque exportable dice que
    #: falta: el bloque se lee sin la app delante y no puede nombrar el de otra especie.
    species: str = ""
    #: EL ORGANISMO DEL EJE: contra los maduros de QUIEN se ha comparado. Es el slug, no
    #: el prefijo —el prefijo se DERIVA de el y vive en `params.species_prefix`—, y es lo
    #: que nombra la columna. Con el humano hay dos corridas: `human` mide al PACIENTE y
    #: `mouse` mide el EXPERIMENTO en el Tg650. Ver `species.WHY_TWO_MIRNA_SETS`.
    #:
    #: VACIO significa «esta corrida es ANTERIOR al eje», no «es la de la diana»: un
    #: veredicto no se puede pedir sobre ella y `SeedStore.verdict_for` lo dice.
    organism: str = ""
    #: La tasa base de la UNION de los ejes. Contesta la pregunta del CANDIDATO —«¿es
    #: notable estar limpio en los DOS?»— y NO sustituye a `base_rate`, que es la del
    #: conjunto contra el que se emite ESTE veredicto. Ver `union_base_rate`.
    union_rate: BaseRate | None = None

    def for_strand(self, strand: str) -> tuple[SeedResult, ...]:
        return tuple(r for r in self.results if r.strand == strand)

    def axis_line(self) -> str:
        """CONTRA QUIEN se ha medido esta corrida, y que NO cubre. Una frase, siempre.

        Va en el bloque exportable —que se lee sin la app delante— porque con el eje
        dual el resultado de una corrida no se puede interpretar sin saber de cual es:
        un `LIMPIO` contra `hsa-` no dice nada del `mmu-`, y la pantalla que lo
        distinguia no viaja con el texto (principio nº 55).
        """
        from .species import WHY_TWO_MIRNA_SETS, mirna_axis, resolve  # noqa: PLC0415

        if not self.organism:
            return (
                "EJE: SIN DECLARAR. Esta corrida es anterior al eje de organismo, así "
                "que no dice contra los maduros de quién se comparó — y no haberlo "
                "declarado no es «es el de la especie diana». No se puede pedir un "
                "veredicto sobre ella: se vuelve a correr."
            )
        ejes = dict(mirna_axis(self.species)) if self.species else {}
        otros = [s for s in ejes if s != self.organism]
        cual = resolve(self.organism).scientific
        linea = (
            f"EJE: {cual} ({self.params.species_prefix}). Esta corrida mide SÓLO ese "
            f"conjunto de maduros."
        )
        if otros:
            nombres = ", ".join(resolve(s).scientific for s in otros)
            linea += (
                f" NO cubre {nombres}, que es otra corrida y otra columna. "
                f"{WHY_TWO_MIRNA_SETS}"
            )
        return linea

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
        lineas.extend(["", f"  {self.axis_line()}"])
        lineas.extend(["", f"  {self.base_rate.describe()}", ""])
        if self.union_rate is not None and self.union_rate.is_union:
            lineas.extend([f"  {self.union_rate.describe()}", ""])
        for hebra in ("guia", "pasajera"):
            filas = self.for_strand(hebra)
            if not filas:
                continue
            lineas.append(f"  ── {hebra.upper()} ({len(filas)}) ──")
            lineas.extend(f"    {r.describe()}" for r in filas)
            lineas.append("")
        if self.core_note:
            lineas.extend(["", f"  {self.core_note}", ""])
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
        lineas.extend(["", f"  {what_this_does_not_answer(self.species)}"])
        return "\n".join(lineas) + "\n"


def run_scan(
    selection, *, mature, params: SeedParams = DEFAULTS, species: str,
    starts, guides: bool, passengers: bool, organism: str,
) -> SeedScan:
    """Corre la busqueda. Esto SI ejecuta: es subcadena contra un fichero ya cargado.

    `organism` es el SLUG del organismo del eje —contra los maduros de quien se compara—
    y va **sin valor por defecto** (principio nº 58). De el sale el prefijo de miRBase,
    asi que no hay ningun camino que acabe filtrando por un prefijo que nadie eligio:
    filtrar con el equivocado da CERO colisiones, que parece una buena noticia.

    **Una corrida es de UN organismo.** El panel humano necesita DOS, una por eje, y no
    se funden: ver `species.WHY_TWO_MIRNA_SETS`.
    """
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

    from .eje_organismo import exige_organismo  # noqa: PLC0415
    from .species import mirna_axis  # noqa: PLC0415

    eje = exige_organismo(organism, frente="seed_colision", que_es="la colisión de seed")
    declarados = dict(mirna_axis(species))
    if eje not in declarados:
        raise ShmirDesignError(
            f"El organismo {eje!r} no está en el eje de {species!r}, que es "
            f"{', '.join(declarados) or 'ninguno — esa especie no está declarada'}. "
            f"Comparar contra los maduros de un organismo que este diseño no mide es "
            f"inventarse la procedencia de un veredicto. Se aborta."
        )
    # EL PREFIJO SE DERIVA DEL ORGANISMO DEL EJE, no de la especie del diseño. Antes
    # salia de `species` —correcto cuando el eje era uno solo— y con el eje dual eso
    # dejaria las dos corridas filtrando por `hsa-`: dos columnas, el mismo numero, y
    # ninguna forma de verlo. Principio nº 13 sobre el filtro de una corrida.
    params = params.with_changes(species_prefix=declarados[eje])
    prefijo = params.require_prefix()
    largo = params.length
    # Indice por la ventana pedida: con 2-7 una colision es cualquier maduro cuya seed
    # 2-8 EMPIECE por esas 6 bases. No se re-parsea el fichero: se agrupa el indice.
    indice: dict[str, list[str]] = {}
    for seed, nombres in mature.seeds.items():
        propios = [n for n in nombres if not prefijo or n.startswith(prefijo)]
        if propios:
            indice.setdefault(seed[:largo], []).extend(propios)

    marco = tiled_frame(getattr(selection, "anatomy", None))
    # LA NOTA DEL NUCLEO, una vez por corrida: es propiedad de la LISTA y de la especie
    # del diseño, no de cada fila. Se DERIVA (`mirna.core_list_note`), y sale vacia
    # cuando la lista es de la especie que se esta diseñando.
    from .mirna import CORE_LIST_MARK, core_list_note  # noqa: PLC0415

    # LA NOTA SE PREGUNTA POR EL ORGANISMO DEL EJE, no por la especie del diseño, y eso
    # cambia lo que dice: el nucleo de abundantes esta autorizado para cerebro MURINO,
    # asi que en el eje `mouse` de un diseño humano la lista NO es prestada — es
    # exactamente la de su especie, porque ese eje mide el experimento en el Tg650. Con
    # la especie del diseño, ese eje saldria marcado «lista de OTRA ESPECIE» sobre el
    # unico caso en que la lista es la correcta. El eje `human` sigue marcado, que es lo
    # cierto.
    nota_nucleo = core_list_note(eje)
    resultados = []
    crudas = []
    for inicio, hebra, secuencia in _strands(
        selection, species, pedidos, guides, passengers
    ):
        hepta = params.seed_of(secuencia)
        nombres = sorted(set(indice.get(hepta, ())))
        # LA ESPECIE SE PASA. Sin ella `CoreHit` no puede decir si la lista es
        # PRESTADA, y este es el camino que ESCRIBE en el almacen y produce el bloque
        # exportable: el aviso llegaba al filtro del tilado y no aqui (principio nº 33).
        # POR EL ORGANISMO DEL EJE, por lo mismo que la nota de arriba: es quien
        # decide si la lista del nucleo es la de esa especie o una prestada.
        nucleo = {h.name for h in core_hits(nombres, species=eje)}
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
                level=nivel, frame=marco,
                core_mark=CORE_LIST_MARK if nota_nucleo else "",
            )
        )
        crudas.append(f"{consulta}\t{hepta}\t{nivel}\t{','.join(nombres)}")

    # EL ORGANISMO DEL EJE VA DENTRO DEL CRUDO, y no es decoracion. El `run_id` es
    # `seed-<fecha>-<md5 del crudo>` (errata nº 48), asi que dos corridas del mismo
    # panel que salieran LIMPIAS en los dos ejes tendrian el mismo crudo, el mismo md5 y
    # el mismo id: la segunda se rechazaria como «el mismo fichero subido dos veces» y
    # el eje que se venia a cubrir se quedaria sin corrida — con un mensaje que ademas
    # manda a mirar otra cosa. Y sirve para lo de siempre: el crudo se relee del log y
    # tiene que decir por si solo contra que se midio (principio nº 35).
    crudas.insert(0, f"# organismo\t{eje}\t{prefijo}")

    return SeedScan(
        params=params, source=mature.provenance, results=tuple(resultados),
        base_rate=base_rate(mature, params), raw="\n".join(crudas) + "\n",
        core_note=nota_nucleo, species=species, organism=eje,
        # LA DE LA UNION, calculada AQUI y no en la vista: sale del mismo fichero ya
        # cargado y viaja con la corrida al log, asi que el informe la lee en vez de
        # recalcularla sobre 69.020 maduros en cada repintado (errata nº 59).
        union_rate=union_base_rate(
            mature, params, [p for _, p in mirna_axis(species)],
        ),
        mature_md5=mature.checksum, mature_version=mature.version,
    )
