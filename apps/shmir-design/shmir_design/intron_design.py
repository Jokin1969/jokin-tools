"""`mvm_sin_criptico`: la variante del intron que DISEÑA la app.

## AUTORIZACION

La regla 1 prohibe generar secuencia. Aqui hay una excepcion **escrita y acotada**,
concedida explicitamente el 2026-08-26 para diseñar una variante del intron MVM sin el
donante criptico del andamio y con espaciadores nuevos.

La autorizacion cubre **dos cosas y nada mas**:

  1. **una sola base** del motivo `GTGAGCG`, para romperlo;
  2. los **espaciadores** de 20-30 nt entre el donante y el modulo y entre el modulo y el
     punto de ramificacion.

NO cubre **guias**, ni **pasajeras**, ni el resto del andamio, ni los contextos de SGEP,
ni ninguna otra pieza. Esas siguen copiandose literal o derivandose de la entrada.

## Y ojo con DONDE esta el criptico

`GTGAGCG` son los **ultimos 7 nt de `SGEP_SCAFFOLD.flank5`** (`TGCTGTTGACA|GTGAGCG`), o
sea que esta **dentro del ANDAMIO**, no en un espaciador. Romperlo no es lo mismo que
generar un espaciador: **muta el andamio verificado contra la publicacion**. Por eso toda
construccion que salga de aqui deja de llevar miR-E verificado y sale **marcada** en toda
la salida, igual que un cassette con espaciadores de novo.

## Los dos criterios, y ninguno se decide por nuestra cuenta

  1. **Cuanto degrada el contexto de donante** — un conteo declarado, no un modelo. Se
     dice expresamente que **no es SpliceAI**: el numero de verdad sale del modal, y esto
     solo sirve para GENERAR candidatos.
  2. **Si el 97-mero sigue plegando como en SGEP** — el mismo criterio estructural que
     decide la posicion 1 de la pasajera. Una alternativa que baje mucho el criptico y
     rompa el plegado NO sirve.

**Si empatan, no se elige.** Se emiten las alternativas con sus dos metricas y lo decide
quien lee. Y sin ViennaRNA el criterio estructural no se puede aplicar, asi que no se
propone ninguna: elegir «por lo que baja el criptico» sin comprobar el plegado es
exactamente el fallo de la tabla por terminacion que este proyecto ya cometio con la
pasajera.

Lo que sale es una **PROPUESTA**, no una construccion aprobada: pasa por el mismo modal
que las demas antes de ir a sintesis.

Python 3.11+, solo libreria estandar; ViennaRNA es opcional y sin el esto sale `NOT_RUN`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import ShmirDesignError
from .filters import FilterState
from .hard_filters import gc_fraction
from .hard_filters import longest_homopolymer as _longest_homopolymer
from .spacers import spacer_rejections as _spacer_rejections
from .splicing import CRYPTIC_DONOR

AUTHORIZATION = (
    "AUTORIZACIÓN ESCRITA Y ACOTADA (2026-08-26). La regla 1 prohibe generar secuencia; "
    "aquí se autoriza generar DOS cosas y nada más: (1) UNA SOLA BASE del motivo "
    f"{CRYPTIC_DONOR}, para romperlo, y (2) los ESPACIADORES de 20-30 nt entre el donante "
    "y el módulo y entre el módulo y el punto de ramificacion. NO cubre guías, ni "
    "pasajeras, ni el resto del andamio, ni los contextos de SGEP, ni ninguna otra pieza. "
    f"OJO: {CRYPTIC_DONOR} son los últimos 7 nt de `SGEP_SCAFFOLD.flank5`, o sea que esta "
    "dentro del ANDAMIO y no en un espaciador — romperlo muta el andamio verificado "
    "contra la publicacion."
)

SCAFFOLD_MODIFIED_MARK = (
    "ANDAMIO MODIFICADO: esta construcción NO lleva el miR-E verificado. Se le ha roto el "
    f"donante críptico {CRYPTIC_DONOR} cambiando una base del flanco 5', así que no es "
    "intercambiable con el andamio estándar y su comportamiento de procesamiento no esta "
    "contrastado contra la publicacion original."
)

TIE_NOTE = (
    "Si varias alternativas empatan en las dos métricas, la app NO ELIGE: las emite "
    "todas y lo decide QUIEN LEE. Es la misma regla que la posición 1 de la pasajera."
)

#: Como se mide «cuanto degrada el contexto de donante». DECLARADO, no citado.
DONOR_CONTEXT_CRITERION = (
    "Cuanto degrada el contexto de donante se mide como el número de posiciones que "
    "siguen coincidiendo con el consenso `GT[AG]AG` en las cinco primeras del motivo: "
    "menos coincidencias, más degradado. Es un criterio DECLARADO como parámetro de este "
    "análisis y NO ES UNA CITA — no sale de ninguna publicacion ni de ningún modelo. "
    "SOBRE TODO: NO ES SpliceAI. La puntuación de verdad del sitio críptico sale del "
    "cuarto modal, sobre la construcción montada; esto solo sirve para GENERAR "
    "candidatos que después se puntuan como cualquier otra construcción."
)

#: Consenso de donante contra el que se cuenta. Va como parametro, no como cita.
DONOR_CONSENSUS = ("G", "T", "AG", "A", "G")

#: Longitudes autorizadas de los espaciadores nuevos.
SPACER_RANGE = (20, 30)

#: Tracto de pirimidinas contiguas a partir del cual un espaciador COMPITE con el
#: legitimo. Se compara contra las nueve del MVM: la mitad ya es competir.
MAX_PYRIMIDINE_RUN = 5


@dataclass(frozen=True)
class CrypticSite:
    """Donde esta el criptico DENTRO del flanco 5'. Se localiza, no se teclea."""

    motif: str
    start: int
    end: int


def locate_cryptic(scaffold, *, motif: str = CRYPTIC_DONOR) -> CrypticSite:
    """Busca el motivo en el flanco 5' del andamio. Si no esta, ABORTA."""
    flanco = str(scaffold.flank5).upper()
    posicion = flanco.find(motif)
    if posicion < 0:
        raise ShmirDesignError(
            f"El flanco 5' del andamio {scaffold.name!r} no contiene {motif!r}. Se "
            f"aborta en vez de dar el riesgo por ausente: o el andamio no es el que se "
            f"cree, o el motivo está en otro sitio, y las dos cosas invalidan este "
            f"diseño entero."
        )
    return CrypticSite(motif=motif, start=posicion + 1, end=posicion + len(motif))


def _donor_score(motivo: str) -> int:
    """Cuantas posiciones siguen coincidiendo con el consenso. Menos = mas degradado."""
    return sum(
        1 for base, esperado in zip(motivo, DONOR_CONSENSUS) if base in esperado
    )


@dataclass(frozen=True)
class BreakCandidate:
    """Una alternativa: el andamio con UNA base cambiada, y su metrica de degradacion."""

    position: int          # 1-based dentro del motivo
    original: str
    replacement: str
    flank5: str
    motif: str
    donor_score: int


def break_candidates(scaffold, *, motif: str = CRYPTIC_DONOR) -> tuple[BreakCandidate, ...]:
    """Las cuatro bases en cada posicion del motivo. Las que lo dejan intacto no cuentan."""
    sitio = locate_cryptic(scaffold, motif=motif)
    flanco = str(scaffold.flank5).upper()
    salida = []
    for indice in range(len(motif)):
        original = motif[indice]
        for base in "ACGT":
            if base == original:
                continue
            nuevo_motivo = motif[:indice] + base + motif[indice + 1:]
            nuevo_flanco = (
                flanco[:sitio.start - 1] + nuevo_motivo + flanco[sitio.end:]
            )
            salida.append(
                BreakCandidate(
                    position=indice + 1,
                    original=original,
                    replacement=base,
                    flank5=nuevo_flanco,
                    motif=nuevo_motivo,
                    donor_score=_donor_score(nuevo_motivo),
                )
            )
    return tuple(salida)


@dataclass(frozen=True)
class BreakChoice:
    """Las alternativas con sus DOS metricas. `chosen=None` si empatan o si no se pudo."""

    state: FilterState
    candidates: tuple[BreakCandidate, ...] = ()
    folding_ok: tuple[bool, ...] = ()
    chosen: BreakCandidate | None = None
    tied: tuple[BreakCandidate, ...] = ()
    reason: str = ""

    @property
    def tie(self) -> bool:
        return len(self.tied) > 1

    def rows(self) -> list[dict[str, object]]:
        elegibles = self._eligible_set()
        return [
            {
                "posicion": c.position,
                "cambio": f"{c.original}->{c.replacement}",
                "motivo": c.motif,
                "donor_score": c.donor_score,
                "plegado_ok": ok,
                "elegible": c in elegibles,
            }
            for c, ok in zip(self.candidates, self.folding_ok)
        ]

    def _eligible_set(self):
        if self.state is not FilterState.PASS:
            return set()
        minimo = min(
            (c.donor_score for c, ok in zip(self.candidates, self.folding_ok) if ok),
            default=None,
        )
        if minimo is None:
            return set()
        return {
            c for c, ok in zip(self.candidates, self.folding_ok)
            if ok and c.donor_score == minimo
        }

    def describe(self) -> list[str]:
        lineas = [f"Romper {CRYPTIC_DONOR} — {self.state.value}"]
        if self.state is not FilterState.PASS:
            lineas.append(f"  {self.reason}")
            return lineas
        for fila in self.rows():
            marca = "  <- ELEGIBLE" if fila["elegible"] else ""
            lineas.append(
                f"  pos {fila['posicion']} {fila['cambio']}  {fila['motivo']}  "
                f"consenso={fila['donor_score']}  "
                f"plegado={'OK' if fila['plegado_ok'] else 'ROTO'}{marca}"
            )
        if self.tie:
            lineas.append(f"  EMPATE entre {len(self.tied)}. {TIE_NOTE}")
        elif self.chosen is not None:
            lineas.append(
                f"  Elegida: pos {self.chosen.position} "
                f"{self.chosen.original}->{self.chosen.replacement}"
            )
        lineas.append(f"  {DONOR_CONTEXT_CRITERION}")
        lineas.append(f"  {SCAFFOLD_MODIFIED_MARK}")
        return lineas


def choose_break(scaffold, *, guide: str, motif: str = CRYPTIC_DONOR,
                 available: bool | None = None) -> BreakChoice:
    """Las alternativas con sus dos metricas. Si empatan, NO elige."""
    from .folding import VIENNA_AVAILABLE, check_fold
    from .scaffold import build_hairpin

    candidatos = break_candidates(scaffold, motif=motif)
    usable = VIENNA_AVAILABLE if available is None else available
    if not usable:
        return BreakChoice(
            state=FilterState.NOT_RUN,
            candidates=candidatos,
            folding_ok=tuple(False for _ in candidatos),
            reason=(
                "Sin ViennaRNA no se puede aplicar el criterio ESTRUCTURAL, así que no "
                "se propone ninguna alternativa. Elegir la base «por lo que baja el "
                "críptico» sin comprobar el plegado es exactamente el fallo de la tabla "
                "por terminacion que este proyecto ya cometio con la PASAJERA: la tabla "
                "olvidaba el apareamiento G:U y elegia mal sin dar ningún error."
            ),
        )

    plegados = []
    for candidato in candidatos:
        modificado = replace(scaffold, flank5=candidato.flank5, verified=False)
        try:
            horquilla = build_hairpin(guide, scaffold=modificado)
            resultado = check_fold(horquilla)
            plegados.append(resultado.state is FilterState.PASS)
        except ShmirDesignError:
            # rule2-ok: una alternativa que no se puede construir NO es un fallo del
            # diseño — es una alternativa que no vale, y eso es informacion. No se
            # esconde: sale como `plegado_ok=False` en su fila.
            plegados.append(False)

    eleccion = BreakChoice(
        state=FilterState.PASS,
        candidates=candidatos,
        folding_ok=tuple(plegados),
    )
    elegibles = sorted(
        eleccion._eligible_set(), key=lambda c: (c.position, c.replacement)
    )
    if len(elegibles) == 1:
        return replace(eleccion, chosen=elegibles[0], tied=())
    return replace(eleccion, chosen=None, tied=tuple(elegibles))


# ─────────────────────── los espaciadores nuevos ───────────────────────


def spacer_rejections(sequence: str) -> tuple[str, ...]:
    """Los filtros de `spacers.py` MAS los propios de este intron.

    Los propios salen de lo que este espaciador tiene al lado: va entre el donante y el
    modulo, o entre el modulo y el punto de ramificacion, asi que un `GT` o un `AG` suyo
    compite con los legitimos y un tracto de pirimidinas compite con el del aceptor.
    """
    limpia = "".join(str(sequence).split()).upper()
    motivos = list(_spacer_rejections(limpia))

    if "GT" in limpia:
        motivos.append(
            "Lleva un GT: en este intrón el espaciador va pegado al donante legítimo, "
            "así que un GT suyo es un 5'SS alternativo en contexto utilizable."
        )
    if "AG" in limpia:
        motivos.append(
            "Lleva un AG: el espaciador 3' va pegado al punto de ramificacion, así que "
            "un AG suyo es un 3'SS alternativo en contexto utilizable."
        )
    carrera, mayor = 0, 0
    for base in limpia:
        carrera = carrera + 1 if base in "CT" else 0
        mayor = max(mayor, carrera)
    if mayor > MAX_PYRIMIDINE_RUN:
        motivos.append(
            f"Tracto de {mayor} pirimidinas contiguas: compite con el del aceptor "
            f"LEGÍTIMO, que en el MVM tiene nueve. Un tracto propio de más de "
            f"{MAX_PYRIMIDINE_RUN} le da a un AG críptico un sitio 3' comparable."
        )
    return tuple(motivos)


def is_acceptable(sequence: str) -> bool:
    return not spacer_rejections(sequence)
