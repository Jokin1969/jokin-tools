"""Especies: los fixtures se DECLARAN, nunca se suponen.

Cargar una secuencia de una especie para la que no hay fixtures no es un error — es lo
normal en cuanto se sale del raton. Lo que si es un error es que la app siga adelante
como si los tuviera, o que los frentes que no puede cerrar acaben en una nota al pie.

Un frente que no se ve NO EXISTE. Es lo que pasó con `offtarget_seed`, invisible durante
semanas porque `carga_seed` era un numero y no un veredicto. Aqui la salida es una tabla
con una fila por frente y el FICHERO CONCRETO que falta en cada uno.

**Y el fixture de una especie no se puede usar con otra.** Ya apareció con
`rmsk_mouse.out` sobre el transcrito humano: el intervalo cabia, no se salia de rango y
no saltaba ninguna alarma. La regla es la misma que la de la especie declarada del
`.out`: se comprueba, y si no coincide se aborta.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ShmirDesignError
from .filters import FilterState


@dataclass(frozen=True)
class Species:
    """Lo que se sabe de una especie. Vacio = no se sabe, y no se rellena."""

    scientific: str
    slug: str
    #: Prefijo de miRBase (`mmu-`). Vacio si no se conoce: NO se deriva del nombre.
    mirbase_prefix: str = ""
    #: Taxid para Entrez. Vacio si no se conoce.
    taxid: str = ""
    #: Ensamblaje de UCSC (`mm39`). Vacio si no se conoce: dos ensamblajes distintos dan
    #: coordenadas distintas, asi que este NO se adivina tampoco.
    ucsc_assembly: str = ""

    @property
    def known(self) -> bool:
        return bool(self.mirbase_prefix or self.taxid or self.ucsc_assembly)


#: Las que este proyecto conoce. Añadir una especie es añadir una linea AQUI con sus
#: identificadores verificados, no deducirlos del nombre.
SPECIES: dict[str, Species] = {
    "mouse": Species("Mus musculus", "mouse", "mmu-", "txid10090", "mm39"),
    "human": Species("Homo sapiens", "human", "hsa-", "txid9606", "hg38"),
}

#: Como se llama cada especie EN ESTE PROYECTO, ademas de por su nombre cientifico.
#: Van DECLARADOS, no deducidos: sin esto, `raton` no seria `mouse` y el nucleo de
#: abundancia saldria marcado como lista de otra especie en la corrida murina.
ALIASES: dict[str, str] = {
    "raton": "mouse", "ratón": "mouse", "mus musculus": "mouse", "mouse": "mouse",
    "humano": "human", "homo sapiens": "human", "human": "human",
}

_BY_NAME = {s.scientific.lower(): s for s in SPECIES.values()}


def _slugify(nombre: str) -> str:
    limpio = re.sub(r"[^a-z0-9]+", "_", nombre.strip().lower()).strip("_")
    return limpio or "sin_nombre"


def resolve(name: str) -> Species:
    """La especie a partir de su nombre. Si no se conoce, se dice — no se inventa."""
    if not str(name).strip():
        raise ShmirDesignError(
            "No hay especie declarada. Sin ella no se puede decir que fixtures faltan "
            "ni comprobar que los que hay son de esta especie; se aborta en vez de "
            "suponer raton, que es lo que este proyecto lleva dentro por historia."
        )
    limpio = str(name).strip()
    alias = ALIASES.get(limpio.lower())
    conocida = (
        SPECIES.get(alias) if alias
        else _BY_NAME.get(limpio.lower()) or SPECIES.get(limpio.lower())
    )
    if conocida is not None:
        return conocida
    return Species(scientific=limpio, slug=_slugify(limpio))


# ─── Que frentes puede cerrar esta especie ───────────────────────────────────


@dataclass(frozen=True)
class FrontAvailability:
    front: str
    available: bool
    missing: str
    note: str

    @property
    def state(self) -> FilterState:
        return FilterState.PASS if self.available else FilterState.NOT_RUN

    def describe(self, width: int = 34) -> str:
        puntos = "." * max(1, width - len(self.front))
        estado = "disponible" if self.available else f"FALTA {self.missing}"
        return f"  {self.front} {puntos} {estado}"


@dataclass(frozen=True)
class FixtureReport:
    species: Species
    rows: tuple[FrontAvailability, ...]

    @property
    def closable(self) -> int:
        return sum(1 for f in self.rows if f.available)

    def render(self) -> str:
        lineas = [f"Especie detectada: {self.species.scientific}"]
        if not self.species.known:
            lineas.append(
                "  (sin identificadores declarados: ni prefijo de miRBase ni taxid. No "
                "se deducen del nombre.)"
            )
        lineas.extend(f.describe() for f in self.rows)
        lineas.append("")
        lineas.append(
            f"  {self.closable} de {len(self.rows)} frente(s) pueden cerrarse con lo que "
            f"hay. Los demas quedan en NOT_RUN"
        )
        lineas.append(
            "  VISIBLE en la tabla de candidatos, no en una nota: un candidato con "
            "cinco frentes sin correr"
        )
        lineas.append(
            "  no debe parecerse a uno con seis cerrados."
        )
        for fila in self.rows:
            if not fila.available and fila.note:
                lineas.append(f"    · {fila.front}: {fila.note}")
        return "\n".join(lineas) + "\n"


_WRONG_SPECIES_NOTE = (
    "El fixture que hay es de OTRA ESPECIE y no vale: ya pasó con `rmsk_mouse.out` "
    "sobre el transcrito humano — el intervalo cabia, no se salia de rango y no saltaba "
    "ninguna alarma."
)


def fixture_report(species: Species, *, have) -> FixtureReport:
    """Que frentes puede cerrar esta especie con los ficheros que hay.

    `have` son los nombres de fichero presentes. Se comprueba que sean LOS DE ESTA
    ESPECIE: un `rmsk_mouse.out` no cuenta para un conejo.
    """
    presentes = set(have)
    slug = species.slug
    prefijo = (
        f"«{species.mirbase_prefix}»" if species.mirbase_prefix
        else "su prefijo de miRBase, que para esta especie no esta declarado"
    )

    rmsk = f"rmsk_{slug}.out"
    refseq = f"refseq_rna_{slug}.fa" if slug not in ("mouse",) else "refseq_rna.fa"
    transcriptoma = f"transcriptoma_3utr_{slug}.fa" if slug != "mouse" else "transcriptoma_3utr.fa"

    def _nota_ajena(nombre_generico: str) -> str:
        ajenos = [n for n in presentes if n.startswith(nombre_generico) ]
        return _WRONG_SPECIES_NOTE if ajenos else ""

    filas = [
        FrontAvailability(
            front="barrido y filtros biofisicos", available=True, missing="",
            note=(
                "GC, homopolimero, asimetria y G4 no dependen de ningun fichero ni de "
                "ninguna especie."
            ),
        ),
        FrontAvailability(
            front="repetitivos",
            available=rmsk in presentes,
            missing=rmsk,
            note=_nota_ajena("rmsk_"),
        ),
        FrontAvailability(
            front="colision de seed",
            available="mature.fa" in presentes and bool(species.mirbase_prefix),
            missing=(
                f"mature.fa filtrado a {prefijo}"
                if "mature.fa" in presentes or not species.mirbase_prefix
                else "mature.fa"
            ),
            note=(
                ""
                if species.mirbase_prefix
                else (
                    "miRBase usa un prefijo de tres letras por especie y el de esta no "
                    "esta declarado en `species.SPECIES`. Correr con «mmu-» compararia "
                    "contra miARN de RATON y daria un resultado plausible y equivocado."
                )
            ),
        ),
        FrontAvailability(
            front="off-target por seed",
            available=transcriptoma in presentes,
            missing=transcriptoma,
            note=(
                "Es la busqueda de subcadena del heptamero 2-8 sobre los 3'UTR del "
                "transcriptoma de ESTA especie; el de otra no sirve."
            ),
        ),
        FrontAvailability(
            front="APA",
            available=False,
            missing="datos de PolyA_DB para esta especie",
            note=(
                "La tabla que hay es de Prnp murino y se aplica por md5 del 3'UTR, asi "
                "que sobre otra secuencia devuelve None y no promueve nada. Eso esta "
                "bien: lo que falta es la tabla de esta especie."
            ),
        ),
        FrontAvailability(
            front="especificidad",
            available=refseq in presentes,
            missing=f"base de RefSeq de {species.scientific}",
            note=(
                ""
                if species.taxid
                else (
                    "Ademas no hay taxid declarado para esta especie, asi que la orden "
                    "de BLAST no se puede construir: `blast_command` aborta en vez de "
                    "inventarlo."
                )
            ),
        ),
        FrontAvailability(
            front="transgen",
            available="aav_casete.fa" in presentes,
            missing="casete del vector de esta construccion",
            note=(
                "El casete de hoy es pAAV con PrP MURINO: para otra especie es otro "
                "plasmido, y con el cambian el modulo de 149 nt y el cassette de 318."
            ),
        ),
    ]
    return FixtureReport(species=species, rows=tuple(filas))


# ─────────── el UNICO origen de los tres valores que estaban por defecto ───────────
#
# `mirna.DEFAULT_PREFIXES`, el `mmu-` de `seed_scan` y el `txid10090` de `blast` eran
# valores por defecto que NADIE avisaba si no se cambiaban: el mismo patron que
# `rmsk_mouse.out` conectado por rol. Un `txid10090` sobre una secuencia de conejo tiene
# que ser IMPOSIBLE, no improbable, asi que ahora esos tres salen de aqui — y una
# especie sin el valor declarado ABORTA diciendo donde se declara.


def mirbase_prefix(name: str) -> str:
    """El prefijo de miRBase de una especie. No se deduce del nombre."""
    especie = resolve(name)
    if especie.mirbase_prefix:
        return especie.mirbase_prefix
    raise ShmirDesignError(
        f"La especie {name!r} ({especie.scientific}) NO tiene prefijo de miRBase "
        f"declarado en este proyecto. Se mira en mirbase.org —la especie va en el "
        f"nombre de cada maduro— y se AÑADE a `species.SPECIES`. No se deduce del "
        f"nombre: para Oryctolagus cuniculus, `ocu-`, `oc-` y `ory-` son todos "
        f"plausibles y solo uno existe. Filtrar con el prefijo equivocado da CERO "
        f"colisiones, que parece una buena noticia."
    )


def taxid(name: str) -> str:
    """El taxid de una especie. No se deduce del nombre."""
    from .specificity import taxid_for

    return taxid_for(name)
