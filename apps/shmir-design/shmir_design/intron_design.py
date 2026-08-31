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
from .spacers import WHY_FIXED_LENGTHS
from .spacers import spacer_rejections as _spacer_rejections
from .introns import BRANCH_A_OFFSET
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
    # zip-ok: el motivo criptico son 7 nt y el consenso del donante son 5
    # posiciones; se puntuan las cinco A PROPOSITO, que es lo que mide un consenso.
    # Consecuencia MEDIDA, y va escrita porque no es obvia: cambiar una base en la
    # posicion 6 o la 7 NO baja la puntuacion, asi que esas alternativas salen con
    # el mismo numero que el motivo intacto y nunca se eligen — el minimo gana.
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

    def __post_init__(self) -> None:
        """Las dos tuplas van EN PARALELO, y eso no se puede dejar a la buena fe.

        `rows()`, `_eligible_set()` y el minimo recorren `zip(candidates, folding_ok)`, y
        **`zip` trunca al mas corto sin decir nada**. Con `folding_ok` en su defecto —una
        tupla vacia— el informe saldria SIN NINGUNA FILA y sin ningun error: se leeria
        como «no hay alternativas» cuando lo que pasa es que no se midio ninguna.

        Los dos sitios que construyen esto hoy rellenan los dos campos. El guardia esta
        para el tercero. Es el principio nº 19 en su version silenciosa: un valor
        legitimo —la tupla vacia del defecto— tiene la forma de otra cosa, y quien lo lee
        mira el contenedor.
        """
        if len(self.folding_ok) != len(self.candidates):
            raise ShmirDesignError(
                f"BreakChoice: {len(self.candidates)} alternativa(s) y "
                f"{len(self.folding_ok)} veredicto(s) de plegado. Van en paralelo y `zip`"
                f" truncaría al más corto EN SILENCIO, dejando alternativas fuera del "
                f"informe sin decirlo. Se aborta: cada alternativa lleva su `folding_ok`,"
                f" y si no se pudo medir el plegado va `False` con su motivo en `reason`."
            )

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
            for c, ok in zip(self.candidates, self.folding_ok, strict=True)
        ]

    def _eligible_set(self):
        if self.state is not FilterState.PASS:
            return set()
        minimo = min(
            (
                c.donor_score
                for c, ok in zip(self.candidates, self.folding_ok, strict=True)
                if ok
            ),
            default=None,
        )
        if minimo is None:
            return set()
        return {
            c
            for c, ok in zip(self.candidates, self.folding_ok, strict=True)
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

# ──────────────────────── el desempate, que NO lo mide la app ────────────────────────
#
# Las dos alternativas que quedaron empatadas —`C` y `T` en la posicion 4— bajan el
# donante igual y las dos conservan el plegado del 97-mero. La app NO puede desempatarlas:
# con lo que mide, empatan de verdad.
#
# EL DESEMPATE ES UNA DECISION DEL RESPONSABLE DEL PROYECTO, con un criterio que ESTA APP
# NO MIDE, y por eso se registra aparte de todo lo que sale de un calculo. Distinguirlas
# no es cosmetico: una decision tomada con datos se revisa cambiando los datos, y una
# tomada por criterio se revisa discutiendo el criterio.

TIEBREAK_DECISION = "T"
TIEBREAK_POSITION = 4
TIEBREAK_MOTIF = "GTGTGCG"

#: El criterio, con las palabras de quien lo decidio (2026-08-27).
TIEBREAK_RATIONALE = (
    "Decisión del responsable del proyecto, con un criterio que esta app NO MIDE. "
    "`GTGCGCG` sube el GC de un flanco basal de miR-E, que es justo donde Drosha ancla "
    "el corte, y el GC local influye en el PROCESAMIENTO además de en el plegado — que "
    "es lo único que la app comprueba. `GTGTGCG` conserva la composición AT del "
    "original. Y el argumento de fondo: `GTGAGCG` es la secuencia NATIVA del flanco de "
    "miR-30a, así que cualquier cambio se aleja de lo que hay en la naturaleza; con dos "
    "alternativas que empatan en lo medido, gana la que menos se aleja en lo NO medido. "
    "A→T conserva composición; A→C añade un par G-C."
)

#: La DESCARTADA, registrada con su motivo. Si `GTGTGCG` da problemas, esta esta a un
#: gBlock de distancia y no hay que volver a razonarla.
TIEBREAK_REJECTED = "GTGCGCG"
TIEBREAK_REJECTED_WHY = (
    "`GTGCGCG` (C en la posición 4) queda DESCARTADA, no eliminada: empata con la "
    "elegida en todo lo que la app mide —baja el donante igual y conserva el plegado— y "
    "pierde sólo en el criterio no medido (sube el GC de un flanco basal donde Drosha "
    "ancla, y añade un par G-C donde el original tiene AT). Si `GTGTGCG` da problemas, "
    "ésta está a un gBlock de distancia."
)


def tiebreak_note() -> str:
    """El desempate entero, para que viaje con la propuesta."""
    return (
        f"DESEMPATE (no lo mide la app): {TIEBREAK_DECISION} en la posición "
        f"{TIEBREAK_POSITION} → {TIEBREAK_MOTIF}. {TIEBREAK_RATIONALE} "
        f"{TIEBREAK_REJECTED_WHY}"
    )


def apply_tiebreak(choice: "BreakChoice") -> "BreakCandidate | None":
    """La alternativa elegida por el desempate, si esta entre las que empatan.

    ABORTA si el desempate ya no aplica: si las que empatan cambian —otra guia, otro
    andamio— la decision de hoy puede no estar entre ellas, y aplicarla a ciegas seria
    imponer una eleccion sobre un conjunto distinto del que se decidio.
    """
    if choice.chosen is not None:
        return choice.chosen
    if not choice.tied:
        return None
    elegida = next(
        (
            c for c in choice.tied
            if c.position == TIEBREAK_POSITION and c.replacement == TIEBREAK_DECISION
        ),
        None,
    )
    if elegida is None:
        raise ShmirDesignError(
            f"El desempate registrado ({TIEBREAK_DECISION} en {TIEBREAK_POSITION} → "
            f"{TIEBREAK_MOTIF}) NO está entre las {len(choice.tied)} alternativas que "
            f"empatan aquí: "
            + ", ".join(f"{c.replacement}@{c.position}" for c in choice.tied)
            + ". Se aborta: la decisión se tomó sobre otro conjunto y aplicarla a éste "
            "sería imponerla sobre alternativas que nadie ha comparado."
        )
    return elegida


# ─────────────────── la variante entera: las dos decisiones ───────────────────


@dataclass(frozen=True)
class IntronVariant:
    """`mvm_sin_criptico`: la PROPUESTA, con las dos decisiones y sus dos estados.

    NO es una construccion aprobada. Pasa por el mismo modal que las demas antes de ir a
    sintesis, y sale marcada como propuesta en todo lo que emite.
    """

    state: FilterState
    break_choice: "BreakChoice | None" = None
    spacer_search: object | None = None
    scaffold: object | None = None
    reason: str = ""

    def describe_text(self) -> str:
        lineas = ["Variante «mvm_sin_criptico» — PROPUESTA, no una construcción aprobada"]
        if self.reason:
            lineas.append(f"  {self.reason}")
        if self.break_choice is not None:
            lineas.append("")
            lineas.append("  1) Romper el donante críptico GTGAGCG")
            elegida = self.break_choice.chosen or next(
                (
                    c for c in self.break_choice.tied
                    if c.position == TIEBREAK_POSITION
                    and c.replacement == TIEBREAK_DECISION
                ),
                None,
            )
            if elegida is not None:
                lineas.append(
                    f"     ELEGIDA: {elegida.replacement} en la posición "
                    f"{elegida.position} del flanco 5' → {elegida.motif}"
                )
                if self.break_choice.chosen is None:
                    # Salio de un EMPATE que la app no puede desempatar. Que se vea de
                    # donde viene la eleccion: no la calculo nadie.
                    lineas.append(f"     {tiebreak_note()}")
            elif self.break_choice.tied:
                lineas.append(
                    f"     EMPATAN {len(self.break_choice.tied)} alternativas y NO se "
                    f"elige por nuestra cuenta: "
                    + ", ".join(
                        f"{c.replacement} en {c.position} → {c.motif}"
                        for c in self.break_choice.tied
                    )
                )
                lineas.append(
                    "     Las dos bajan el donante igual y las dos conservan el "
                    "plegado. La decisión es de quien firma la construcción."
                )
            else:
                lineas.append(f"     SIN alternativa. {self.break_choice.reason}")
        if self.spacer_search is not None:
            lineas.append("")
            lineas.append(
                f"  2) Espaciadores por PLEGADO, longitudes FIJAS. {WHY_FIXED_LENGTHS}"
            )
            lineas.append(f"     {self.spacer_search.format_text()}")
        return "\n".join(lineas)


def design_variant(
    *, guide: str, scaffold, available: bool | None = None
) -> IntronVariant:
    """Diseña `mvm_sin_criptico` con las DOS decisiones. Ver `IntronVariant`.

    Necesita el 97-mero del candidato —de ahi la `guide`— porque las dos decisiones son
    ESTRUCTURALES y la estructura depende de la guia: no hay una variante «del proyecto»,
    hay una por candidato.
    """
    if not str(guide).strip():
        raise ShmirDesignError(
            "Sin guía no hay 97-mero, y sin 97-mero las dos decisiones de la variante "
            "son estructurales sobre nada. Se aborta en vez de proponer un intrón "
            "derivado de un plegado que no existe."
        )

    from .blocks import PIECES  # noqa: PLC0415
    from .folding import VIENNA_AVAILABLE, dot_bracket  # noqa: PLC0415
    from .scaffold import build_hairpin  # noqa: PLC0415
    from .spacers import choose_spacers  # noqa: PLC0415

    usable = VIENNA_AVAILABLE if available is None else available
    if not usable:
        return IntronVariant(
            state=FilterState.NOT_RUN,
            reason=(
                "Sin ViennaRNA NO se diseña nada: las dos decisiones son estructurales y "
                "tomarlas sin plegar sería inventarse la variante. NOT_RUN no es PASS."
            ),
        )

    corte = choose_break(scaffold, guide=guide, motif=CRYPTIC_DONOR, available=usable)
    # El desempate del responsable, que la app NO mide. Aborta si ya no aplica.
    elegida = apply_tiebreak(corte)
    if elegida is None:
        return IntronVariant(
            state=FilterState.NOT_RUN,
            break_choice=corte,
            reason=(
                "El primer paso no quedó resuelto, así que no se pasa al segundo: unos "
                "espaciadores elegidos sobre un andamio que aún no está decidido no "
                "valen para el andamio que salga."
            ),
        )

    derivado = replace(scaffold, flank5=elegida.flank5, verified=False)
    horquilla = build_hairpin(guide, scaffold=derivado)
    estructura_sola, _ = dot_bracket(horquilla.sequence)

    def montar(espaciador5: str, espaciador3: str) -> str:
        modulo = (
            PIECES["NheI"].sequence + PIECES["contexto5"].sequence
            + horquilla.sequence
            + PIECES["contexto3"].sequence + PIECES["SacI"].sequence
        )
        return (
            PIECES["MVM5"].sequence + espaciador5 + modulo + espaciador3
            + PIECES["MVM3"].sequence
        )

    busqueda = choose_spacers(
        hairpin=horquilla.sequence,
        structure_alone=estructura_sola,
        assemble=montar,
    )
    resuelta = busqueda.choice is not None
    return IntronVariant(
        state=FilterState.PASS if resuelta else FilterState.NOT_RUN,
        break_choice=corte,
        spacer_search=busqueda,
        scaffold=derivado,
        reason=(
            "" if resuelta
            else "El corte está decidido y los espaciadores NO: la variante queda a medias "
                 "y no se propone entera."
        ),
    )


# ─── DONDE VA EL MODULO dentro de un intron que llega ENTERO ──────────────────
#
# `intron_quimerico` sale de la anotacion de su plasmido y no declara sus puntos de
# insercion, asi que no se puede montar con ningun andamio. Eso NO es un fichero que
# falte: es una decision con criterio, y el criterio es computable.

VENTANA_ADMISIBLE = (
    "El módulo va DESPUÉS del donante y ANTES del primer candidato a punto de "
    "ramificación: los dos límites salen de los elementos del propio intrón, no de un "
    "número escrito. Y dentro de esa ventana hay dos criterios que NO coinciden — la "
    "separación de los elementos y la conservación de la horquilla— así que se emiten "
    "las posiciones con sus dos medidas y se decide mirándolas."
)


@dataclass(frozen=True)
class InsertionCandidate:
    """Una posición de inserción con TODAS sus distancias. No trae veredicto."""

    position: int
    to_donor: int
    to_branch: int
    to_tract: int
    dg: float
    hairpin_intact: bool

    @property
    def min_separation(self) -> int:
        """La separación MÍNIMA de los dos extremos: el criterio de «máxima separación»
        es maximizar este número, no la suma — una suma alta puede esconder un extremo
        pegado."""
        return min(self.to_donor, self.to_branch)


def insertion_candidates(
    intron, module: str, *, hairpin: str
) -> tuple[InsertionCandidate, ...]:
    """Toda la ventana admisible, medida. Sin elegir: quien decide mira la tabla.

    `hairpin` va EXPLÍCITO porque el criterio estructural del proyecto es sobre la
    HORQUILLA, no sobre el módulo entero. La primera versión comparaba el módulo y daba
    CERO posiciones que conservan la estructura — un cero que se lee como «ninguna vale»
    cuando lo que pasaba es que se medía otra cosa. El módulo lleva sitios de restricción
    y contextos a los dos lados que replegan con el intrón; los 97 nt de la horquilla son
    lo que tiene que sobrevivir.
    """
    from .folding import VIENNA_AVAILABLE, dot_bracket

    if not intron.raw_sequence:
        raise ShmirDesignError(
            f"El intrón {intron.name!r} no llega entero, así que sus puntos de "
            f"inserción salen de sus piezas y no hay nada que elegir. Se aborta."
        )
    if not VIENNA_AVAILABLE:
        raise ShmirDesignError(
            "Sin ViennaRNA no se puede decir si la horquilla conserva su estructura "
            "dentro del intrón, y ése es uno de los dos criterios. Se aborta en vez de "
            "emitir media tabla que se leería como la tabla entera."
        )
    secuencia = intron.raw_sequence
    elementos = intron.elements()
    fin_donante = elementos.donor.end
    ramas = [c.branch_a for c in elementos.branch_candidates if c.branch_a is not None]
    if not ramas:
        raise ShmirDesignError(
            f"El intrón {intron.name!r} no tiene ningún candidato a punto de "
            f"ramificación, así que no hay límite superior para la ventana. Se aborta: "
            f"insertar aguas abajo del punto es lo que la regla del módulo prohíbe."
        )
    primera_rama, tracto = min(ramas), elementos.ppt.start
    # El limite superior es el INICIO DEL MOTIVO, no la A: invadir el motivo lo rompe.
    tope = min(primera_rama - BRANCH_A_OFFSET, tracto) - 1
    horquilla_sola = None
    salida = []
    for posicion in range(fin_donante + 1, tope + 1):
        montado = secuencia[:posicion] + module + secuencia[posicion:]
        estructura, energia = dot_bracket(montado)
        if horquilla_sola is None:
            horquilla_sola = dot_bracket(hairpin)[0]
        inicio = posicion + module.find(hairpin)
        dentro = estructura[inicio : inicio + len(hairpin)]
        salida.append(InsertionCandidate(
            position=posicion,
            to_donor=posicion - fin_donante,
            to_branch=primera_rama - posicion,
            to_tract=tracto - posicion,
            dg=energia,
            hairpin_intact=dentro == horquilla_sola,
        ))
    return tuple(salida)
