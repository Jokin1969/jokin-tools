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


# ─── Que FICHEROS necesita esta especie ──────────────────────────────────────
#
# Esta es la vista POR FICHERO, y es la UNICA fuente de los nombres. `fixture_report`
# —la vista por FRENTE— se deriva de aqui. Tenerlas como dos listas independientes seria
# el patron de los dos contadores que discrepan: la barra lateral diria que falta un
# fichero y el informe de frentes diria que no, las dos con pinta de medida.


@dataclass(frozen=True)
class RequiredFile:
    """Un fichero de referencia que esta especie necesita, y para que."""

    #: El rol del manifiesto (`manifest.ROLES`). Es lo que conecta el fichero al filtro.
    role: str
    #: El nombre que se espera, YA resuelto para esta especie.
    filename: str
    #: Que desbloquea, en palabras.
    what: str
    #: El frente cuya ficha de obtencion explica de donde sale (`data/obtencion/`).
    ficha: str
    #: Los frentes que cierra. Son los nombres de `selection.blocking_fronts`.
    fronts: tuple[str, ...]
    #: El hermano OBLIGATORIO, si lo tiene: el `.tbl` de un `.out` de RepeatMasker.
    #: Sin el, el `.out` no se puede validar — la especie de la biblioteca vive ahi.
    companion: str = ""
    #: `False` = refina un frente que ya puede correr sin el, no lo cierra.
    required: bool = True
    #: Extensiones que se aceptan al subirlo por la interfaz.
    extensions: tuple[str, ...] = ()

    @property
    def filenames(self) -> tuple[str, ...]:
        """El fichero y su hermano, si lo tiene."""
        return (self.filename, self.companion) if self.companion else (self.filename,)


def _por_especie(base: str, extension: str, slug: str, *, sin_sufijo: tuple[str, ...]) -> str:
    """`refseq_rna.fa` para el raton, `refseq_rna_conejo.fa` para el conejo.

    El raton no lleva sufijo porque sus ficheros YA estan en el manifiesto con ese
    nombre desde antes de que la app supiera de especies, y renombrarlos aqui dejaria
    de detectar los que hay. El sufijo empieza donde empieza el problema.
    """
    return f"{base}{extension}" if slug in sin_sufijo else f"{base}_{slug}{extension}"


def required_files(species: Species) -> tuple[RequiredFile, ...]:
    """Los ficheros de referencia que necesita esta especie, uno por fila.

    Un fichero, una fila — aunque cierre dos frentes: quien tiene que conseguirlo lo
    busca una vez, no dos.
    """
    slug = species.slug
    return (
        RequiredFile(
            role="rmsk",
            filename=f"rmsk_{slug}.out",
            companion=f"rmsk_{slug}.tbl",
            what="elementos repetitivos y repeticiones polimorficas (paso 2)",
            ficha="repeticiones",
            fronts=("repeticiones", "repeticion_polimorfica"),
            extensions=("out", "tbl"),
        ),
        RequiredFile(
            role="mirbase",
            filename="mature.fa",
            what="colision de seed con un miARN endogeno (paso 10a)",
            ficha="seed_colision",
            fronts=("seed", "seed_colision"),
            extensions=("fa", "fasta", "txt"),
        ),
        RequiredFile(
            role="abundancia",
            filename=_por_especie(
                "mirgenedb_cerebro", ".txt", slug, sin_sufijo=("mouse",)
            ),
            what="la capa AMPLIADA de la colision de seed, a nivel AVISO",
            ficha="seed_colision",
            fronts=("seed_colision",),
            required=False,
            extensions=("txt", "tsv"),
        ),
        RequiredFile(
            role="transcriptoma",
            filename=_por_especie(
                "transcriptoma_3utr", ".fa", slug, sin_sufijo=("mouse",)
            ),
            what="carga de off-targets por seed (paso 10b)",
            ficha="offtarget_seed",
            fronts=("offtarget_seed",),
            extensions=("fa", "fasta", "txt"),
        ),
        RequiredFile(
            role="expresion",
            filename=_por_especie(
                "expresion_cerebro", ".tsv", slug, sin_sufijo=("mouse",)
            ),
            what="ponderar la carga de off-targets por expresion en el tejido",
            ficha="offtarget_seed",
            fronts=("offtarget_seed",),
            required=False,
            extensions=("tsv", "txt"),
        ),
        RequiredFile(
            role="refseq",
            filename=_por_especie("refseq_rna", ".fa", slug, sin_sufijo=("mouse",)),
            what="especificidad: la base contra la que se alinea (paso 12)",
            ficha="especificidad",
            fronts=("especificidad",),
            extensions=("fa", "fasta", "txt"),
        ),
        RequiredFile(
            role="transgen",
            # El casete LLEVA LA ESPECIE en el nombre fuera del raton, y no es cosmetico:
            # `aav_casete.fa` es pAAV con PrP MURINO, y `blocks.vector_applies_to` ya dice
            # que para otra especie no se parametriza — se SUSTITUYE por otro plasmido.
            # Sin sufijo, el casete murino contaria como presente para un conejo y su
            # frente saldria cerrado con el vector equivocado.
            filename=_por_especie("aav_casete", ".fa", slug, sin_sufijo=("mouse",)),
            what="el casete del vector, segunda base de especificidad (paso 12b)",
            ficha="transgen",
            fronts=("transgen",),
            extensions=("fa", "fasta", "txt", "gb"),
        ),
        RequiredFile(
            role="apa",
            filename=_por_especie("apa_medido", ".tsv", slug, sin_sufijo=("mouse",)),
            what="APA MEDIDO en vez de predicho, y con el el techo de knockdown",
            ficha="fraccion_isoforma_larga",
            fronts=("fraccion_isoforma_larga",),
            extensions=("tsv", "txt"),
        ),
    )


def file_for(species: Species, filename: str) -> RequiredFile | None:
    """La fila a la que pertenece un nombre de fichero, contando los hermanos."""
    for fila in required_files(species):
        if filename in fila.filenames:
            return fila
    return None


# ─── Que frentes puede cerrar esta especie ───────────────────────────────────


@dataclass(frozen=True)
class FrontAvailability:
    front: str
    available: bool
    missing: str
    note: str
    #: Los ficheros CONCRETOS de los que depende, derivados de `required_files`. Van
    #: aparte de `missing` porque ese texto es prosa —«datos de PolyA_DB para esta
    #: especie»— y un panel de subida necesita el nombre exacto, no la prosa.
    files: tuple[str, ...] = ()
    #: Los frentes de `selection.blocking_fronts` que cubre esta fila. Una fila puede
    #: cubrir dos —`repetitivos` cubre `repeticiones` y `repeticion_polimorfica`— y son
    #: LOS MISMOS nombres que usa `required_files`, para que las dos vistas se puedan
    #: cruzar por clave en vez de por la prosa del titulo.
    keys: tuple[str, ...] = ()

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
    prefijo = (
        f"«{species.mirbase_prefix}»" if species.mirbase_prefix
        else "su prefijo de miRBase, que para esta especie no esta declarado"
    )

    # Los nombres NO se escriben aqui: salen de `required_files`, que es la vista por
    # fichero. Dos listas independientes serian dos contadores del mismo suceso, y dos
    # contadores que discrepan son un fallo silencioso — la barra lateral diria que
    # falta un fichero y esta tabla diria que no.
    por_rol = {f.role: f for f in required_files(species)}
    rmsk = por_rol["rmsk"].filename
    rmsk_tbl = por_rol["rmsk"].companion
    refseq = por_rol["refseq"].filename
    transcriptoma = por_rol["transcriptoma"].filename
    apa = por_rol["apa"].filename
    casete = por_rol["transgen"].filename
    maduros = por_rol["mirbase"].filename

    def _nota_ajena(nombre_generico: str) -> str:
        ajenos = [n for n in presentes if n.startswith(nombre_generico) ]
        return _WRONG_SPECIES_NOTE if ajenos else ""

    filas = [
        FrontAvailability(
            front="barrido y filtros biofisicos", available=True, missing="",
            files=(), keys=("biofisicos",),
            note=(
                "GC, homopolimero, asimetria y G4 no dependen de ningun fichero ni de "
                "ninguna especie."
            ),
        ),
        FrontAvailability(
            front="repetitivos",
            # Los DOS. Un `.out` a solas no se puede validar: la especie de la
            # biblioteca vive en el `.tbl` y esta demostrado con md5 que dos corridas,
            # una buena y una contra la biblioteca equivocada, dan `.out` identicos.
            available=rmsk in presentes and rmsk_tbl in presentes,
            missing=rmsk if rmsk not in presentes else rmsk_tbl,
            files=(rmsk, rmsk_tbl),
            keys=("repeticiones", "repeticion_polimorfica"),
            note=_nota_ajena("rmsk_"),
        ),
        FrontAvailability(
            front="colision de seed",
            available=maduros in presentes and bool(species.mirbase_prefix),
            missing=(
                f"{maduros} filtrado a {prefijo}"
                if maduros in presentes or not species.mirbase_prefix
                else maduros
            ),
            files=(maduros,),
            keys=("seed", "seed_colision"),
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
            files=(transcriptoma,),
            keys=("offtarget_seed",),
            note=(
                "Es la busqueda de subcadena del heptamero 2-8 sobre los 3'UTR del "
                "transcriptoma de ESTA especie; el de otra no sirve."
            ),
        ),
        FrontAvailability(
            front="APA",
            available=False,
            missing="datos de PolyA_DB para esta especie",
            files=(apa,),
            keys=("fraccion_isoforma_larga",),
            note=(
                "La tabla que hay es de Prnp murino y se aplica por md5 del 3'UTR, asi "
                "que sobre otra secuencia devuelve None y no promueve nada. Eso esta "
                "bien: lo que falta es la tabla de esta especie."
            ),
        ),
        FrontAvailability(
            front="especificidad",
            available=refseq in presentes,
            missing=f"base de RefSeq de {species.scientific} ({refseq})",
            files=(refseq,),
            keys=("especificidad",),
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
            available=casete in presentes,
            missing=f"casete del vector de esta construccion ({casete})",
            files=(casete,),
            keys=("transgen",),
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
