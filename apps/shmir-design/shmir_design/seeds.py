"""Seed de la guia y colision con familias de miRNA (paso 10).

La seed son las posiciones 2-8 de la guia. Si coincide con la seed de un miRNA, la
guia puede reprimir sus dianas: es una colision que descarta el candidato.

**La lista de arranque de este modulo NO es un filtro real.** Son 12 seeds para probar
la mecanica; el filtro real necesita `mature.fa` de miRBase completo, descargado a mano
y versionado con su checksum (ver `docs/fixtures.md`). Cribar candidatos de verdad con
12 seeds daria una falsa sensacion de haber filtrado: la mayoria de las colisiones
seguirian ahi, sin marcar.

Sin lista cargada el filtro devuelve NOT_RUN, que no es PASS (regla 3): ninguna ventana
puede declararse apta mientras miRBase no este.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidSequenceError
from .filters import FilterResult, FilterState

SEED_START = 2   # 1-based, inclusive
SEED_END = 8     # 1-based, inclusive
SEED_LENGTH = SEED_END - SEED_START + 1
RNA_BASES = frozenset("ACGU")
DNA_BASES = frozenset("ACGT")

#: Lista de ARRANQUE para tests. No es un filtro real: ver el docstring del modulo.
BOOTSTRAP_SEED_TABLE = """
# seed<espacio>familia — lista de arranque, NO es un filtro real
AAGGCAC miR-124-3p
CTTTGGT miR-9-5p
GAGGTAG let-7
CACAGTG miR-128-3p
AGCAGCA miR-16/15
TCAAGTA miR-26a-5p
AGCACCA miR-29a-3p
CCCTGAG miR-125b-5p
AACAGTC miR-132-3p
GGAATGT miR-137
GTAAACA miR-30
AAAGTGC miR-17/20/93/106
"""

#: Cuantas seeds trae. Se DERIVA de la tabla: escribir «doce» a mano en los avisos es
#: lo que deja un mensaje diciendo doce cuando alguien añade la trece.
BOOTSTRAP_COUNT = sum(
    1 for l in BOOTSTRAP_SEED_TABLE.splitlines() if l.strip() and not l.startswith("#")
)

BOOTSTRAP_SOURCE = (
    "lista de arranque de 12 seeds para probar la mecanica; NO es un filtro real, "
    "el filtro real necesita mature.fa de miRBase completo"
)

#: El fichero que jubila a la lista de arranque. Se nombra aqui porque la caducidad de
#: esta tabla es exactamente «ya esta el de verdad».
REPLACED_BY = "mature.fa"

#: POR QUE LA LISTA DE ARRANQUE TIENE FECHA DE CADUCIDAD, y no basta con el aviso de
#: siempre.
#:
#: El aviso que ya sale —«es una lista de arranque, NO un filtro real»— dice lo que ES,
#: y con eso se convive: mientras `mature.fa` no este, correr con doce seeds es lo unico
#: que hay y el informe lo declara. Lo que NO dice es que el fichero de verdad ya este
#: ahi al lado sin usarse, que es otra cosa: entonces no se esta conviviendo con una
#: limitacion, se esta corriendo con la tabla equivocada teniendo la buena en el
#: deposito. Los dos casos daban el MISMO aviso, asi que el segundo era invisible.
WHY_AN_EXPIRY = (
    "Un aviso que sale igual con el fichero bueno delante y sin el no distingue «no lo "
    "tenemos» de «lo tenemos y no se está usando». Son dos situaciones distintas y la "
    "segunda es un fallo, no una limitación."
)


def bootstrap_expiry_note(directory=None) -> str | None:
    """¿Está ya `mature.fa` mientras se corre con la lista de arranque?

    Devuelve el aviso de CADUCIDAD, o `None` si el fichero de verdad no está — que es
    el caso en que la lista de arranque sigue siendo lo unico que hay.

    No lee el fichero ni lo valida: eso es del cargador de `mirna.py`, que es quien
    sabe. Aqui solo se contesta «¿está y tiene algo dentro?» (`presencia.hay_fichero`,
    principio nº 9: existir no es contener).
    """
    from .presencia import hay_fichero  # noqa: PLC0415
    from .trabajo import reference_dir  # noqa: PLC0415

    carpeta = Path(directory) if directory is not None else reference_dir()
    ruta = carpeta / REPLACED_BY
    if not hay_fichero(ruta):
        return None
    return (
        f"CADUCADA: se está corriendo con la lista de ARRANQUE de {BOOTSTRAP_COUNT} "
        f"seeds teniendo {REPLACED_BY} en {carpeta}. El fichero de verdad está y no se "
        f"está usando: esto ya no es una limitación, es la tabla equivocada. Conecta "
        f"miRBase (`--usar-manifiesto` o el panel de ficheros) o di por escrito por qué "
        f"no se usa."
    )


@dataclass(frozen=True)
class SeedSet:
    seeds: dict[str, str]      # seed en ADN → familia
    source: str
    is_bootstrap: bool = False

    def __post_init__(self) -> None:
        if not self.seeds:
            raise ValueError(
                f"El conjunto de seeds de {self.source!r} está vacío; se aborta en vez "
                f"de dejar correr un filtro que no puede descartar nada."
            )

    def family_of(self, seed: str) -> str | None:
        return self.seeds.get(seed.upper().replace("U", "T"))


def seed_of(guide: str) -> str:
    """Seed de la guia (posiciones 2-8), en notacion ADN para comparar con miRBase.

    Solo mira ese tramo: una N en el resto de la guia no impide comparar la seed, y la
    posicion 1 ni siquiera forma parte de ella (es la U forzada del paso 6).
    """
    cleaned = "".join(str(guide).split()).upper()
    if not cleaned:
        raise ValueError("La guía está vacía; se aborta el calculo de la seed.")
    if len(cleaned) < SEED_END:
        raise ValueError(
            f"La guía mide {len(cleaned)} nt y la seed son las posiciones "
            f"{SEED_START}-{SEED_END}; se aborta el calculo de la seed."
        )

    seed = cleaned[SEED_START - 1 : SEED_END]
    for offset, base in enumerate(seed):
        if base not in RNA_BASES:
            raise InvalidSequenceError(
                f"guía: carácter {base!r} no válido en la posición "
                f"{SEED_START + offset} (se esperaba A, C, G o U; la guía va en "
                f"notacion ARN); se aborta el calculo de la seed."
            )
    return seed.replace("U", "T")


def parse_seed_table(text: str, *, source: str, is_bootstrap: bool = False) -> SeedSet:
    """Lee una tabla `seed familia`. Cualquier linea mal formada aborta la carga."""
    seeds: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError(
                f"{source}, línea {number}: se esperaban 2 campos (seed y familia) y "
                f"hay {len(parts)}; se aborta la carga de seeds."
            )
        seed, family = parts[0].upper().replace("U", "T"), parts[1].strip()
        if len(seed) != SEED_LENGTH:
            raise ValueError(
                f"{source}, línea {number}: la seed {seed!r} mide {len(seed)} nt y "
                f"deben ser {SEED_LENGTH}; se aborta la carga de seeds."
            )
        for base in seed:
            if base not in DNA_BASES:
                raise InvalidSequenceError(
                    f"{source}, línea {number}: la seed {seed!r} tiene el carácter "
                    f"{base!r}, que no es A, C, G, T ni U; se aborta la carga de seeds."
                )
        if seed in seeds and seeds[seed] != family:
            raise ValueError(
                f"{source}, línea {number}: la seed {seed} ya estaba asignada a "
                f"{seeds[seed]!r} y ahora a {family!r}; se aborta la carga en vez de "
                f"quedarse con una de las dos."
            )
        seeds[seed] = family

    if not seeds:
        raise ValueError(
            f"{source}: no habia ninguna seed que cargar; se aborta en vez de dejar "
            f"correr un filtro vacío."
        )
    return SeedSet(seeds=seeds, source=source, is_bootstrap=is_bootstrap)


BOOTSTRAP_SEEDS = parse_seed_table(
    BOOTSTRAP_SEED_TABLE, source=BOOTSTRAP_SOURCE, is_bootstrap=True
)


def filter_seed(guide: str, seeds: SeedSet | None = None) -> FilterResult:
    """Colision de la seed de la guia con una familia de miRNA."""
    if seeds is None:
        return FilterResult(
            name="seed",
            state=FilterState.NOT_RUN,
            reason=(
                "No hay lista de seeds cargada (miRBase ausente), así que el filtro no "
                "se ejecuta. NOT_RUN no es PASS: la ventana no puede declararse apta."
            ),
        )

    cleaned = "".join(str(guide).split()).upper()
    desconocida = cleaned[SEED_START - 1 : SEED_END].find("N")
    if desconocida != -1:
        return FilterResult(
            name="seed",
            state=FilterState.NOT_RUN,
            reason=(
                f"La seed (posiciones {SEED_START}-{SEED_END} de la guía) tiene una "
                f"base desconocida (N) en la posición {SEED_START + desconocida}: no se "
                f"puede comparar con nada. NOT_RUN no es PASS."
            ),
        )

    seed = seed_of(guide)
    family = seeds.family_of(seed)
    aviso = (
        " AVISO: lista de arranque, no es un filtro real; el filtro real necesita "
        "mature.fa de miRBase completo."
        if seeds.is_bootstrap
        else ""
    )
    if family is not None:
        return FilterResult(
            name="seed",
            state=FilterState.FAIL,
            reason=f"La seed {seed} colisiona con la familia {family}.{aviso}",
        )
    return FilterResult(
        name="seed",
        state=FilterState.PASS,
        reason=(
            f"La seed {seed} no está entre las {len(seeds.seeds)} de "
            f"{seeds.source}.{aviso}"
        ),
    )
