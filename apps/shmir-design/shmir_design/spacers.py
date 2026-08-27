"""Espaciadores del intron: los estandar, y generacion de novo cuando no valen.

## AUTORIZACION

La regla 1 prohibe generar secuencia. Aqui hay una excepcion **escrita y acotada**,
concedida explicitamente: cuando el 97-mero no conserva su estructura dentro del intron
con los espaciadores estandar, se pueden generar espaciadores nuevos PARA ESA GUIA.

La autorizacion cubre **solo los espaciadores**. No cubre guias, ni pasajeras, ni
contextos de SGEP, ni el andamio, ni ninguna otra pieza. Esas siguen copiandose literal o
derivandose de la entrada, y ninguna funcion de este modulo las toca.

Condiciones, las mismas que se usaron para los originales:

  - sin donantes cripticos GTRAGT (GTAAGT / GTGAGT), GTAAGG ni GTGAGG
  - sin señales de poliadenilacion AATAAA ni ATTAAA
  - sin homopolimeros de 4 o mas, y en particular sin GGGG ni CCCC
  - sin duplicar ninguno de los sitios del cassette
  - GC entre 0,28 y 0,45

Criterio de seleccion, **uno solo**: entre los que pasan los filtros, el que hace que el
97-mero dentro del intron pliegue identico a como pliega aislado. Si varios lo cumplen,
el de menor MFE del intron completo.

Longitudes FIJAS: 20 nt el espaciador 5' y 45 nt el 3'. No se tocan — son las que dejan
la horquilla a 86 nt del 5'SS y a 62 del punto de ramificacion.

## Como se busca, y por que asi

Los estandar son el **caso base**: se prueban primero y, si funcionan, se devuelven sin
buscar nada mas. Eso garantiza la propiedad que pide la autorizacion — para una guia
conocida el algoritmo elige exactamente los espaciadores que ya estan fijos — y hace que
el generador no pueda "mejorar" un diseño validado por su cuenta.

Cuando no funcionan, se busca por **desviacion creciente**: primero cambiando solo el 5',
luego solo el 3', y solo despues los dos. Asi el resultado se queda lo mas cerca posible
del diseño original.

La generacion es **determinista**: la semilla sale de la propia horquilla, asi que la
misma guia da siempre los mismos espaciadores. Sin eso, dos corridas del mismo diseño
pedirian bloques distintos.

Python 3.11+, solo libreria estandar; ViennaRNA es opcional pero sin el no hay criterio
que aplicar (regla 6).
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from dataclasses import dataclass

from .blocks import PIECES
from .errors import ShmirDesignError
from .hard_filters import gc_fraction
from .hard_filters import longest_homopolymer as _longest_homopolymer

SPACER5_LENGTH = 20
SPACER3_LENGTH = 45

#: POR QUE LAS LONGITUDES ESTAN FIJAS Y NO SE EXPLORAN (2026-08-27, RECORRIDO tras
#: arreglar el punto 0). Tres razones, y la primera es la que sale de medir:
#:
#: 1. NINGUNA LONGITUD MAS CORTA ES ADMISIBLE. El barrido esta hecho
#:    (`tools/barrer_espaciadores.py`, 0-45 en los dos lados, 5 replicas, ViennaRNA
#:    presente) y en LOS DOS LADOS el unico largo admisible es el punto de partida. El
#:    criterio es relativo —«no peor que 20/45 en los tres elementos fragiles»—, asi que
#:    eso dice literalmente que recortar no sale gratis en ninguno.
#:    Y el POR QUE no es el mismo en los dos lados, que es lo que cambio al medir el 0
#:    de verdad (hasta entonces la fila «0 nt» devolvia los ESTANDAR, errata nº 16):
#:      - lado 5': el criterio NO DISCRIMINA. Recorridos entre longitudes 0,09 / 0,29 /
#:        0,01 contra dispersiones dentro de una longitud de 0,21 / 0,46 / 0,02. Los
#:        tres por debajo: lo que mueve la accesibilidad es la SECUENCIA.
#:      - lado 3': SI discrimina en dos de los tres —donante 0,58 contra 0,54 y punto de
#:        ramificacion 0,40 contra 0,36— y lo que dice es que 45 gana. Por poco (7 % y
#:        11 % de margen con 5 replicas), asi que tampoco sostiene una optimizacion fina.
#:    La frase anterior, «el barrido no discrimino» a secas, era cierta de la corrida con
#:    el 0 mal medido y es FALSA de esta para el lado 3'. La decision no cambia; el
#:    motivo, si.
#: 2. DISEÑO EXPERIMENTAL. Si cada intron lleva su longitud «optima», los tres dejan de
#:    ser comparables. Espaciador CONSTANTE, intron VARIABLE: eso es lo que hace la
#:    matriz interpretable.
#: 3. 20/45 no tiene respaldo, pero cambiarlo por otro numero igual de arbitrario no
#:    compra nada.
#:
#: LO QUE SI SE ELIGE es la SECUENCIA, que es donde la accesibilidad si discrimina.
#:
#: Y LA PALANCA, para cuando haya que atacar donante→punto: NO son los espaciadores, y
#: ahora esta MEDIDO en vez de estimado. Quitando los DOS espaciadores enteros la
#: distancia baja de 256 a 191 nt — 65 nt, y sigue muy por encima del rango tipico
#: (18-100). El MODULO son 149 de los 214 nt intercalados.
WHY_FIXED_LENGTHS = (
    "Las longitudes 20/45 están FIJAS y no se exploran. El barrido se hizo (0-45 en los "
    "dos lados, 5 réplicas) y en LOS DOS LADOS el único largo admisible es el punto de "
    "partida: ninguna longitud más corta queda no peor en los tres elementos frágiles. "
    "El motivo difiere por lado — en el 5' el criterio NO discrimina (lo que mueve la "
    "accesibilidad es la secuencia, no la longitud), y en el 3' sí discrimina por poco "
    "y lo que dice es que 45 gana. Con espaciador constante e intrón variable los tres "
    "intrones son comparables, que es lo que hace la matriz interpretable. Y la palanca "
    "de donante→punto no son los espaciadores: quitando los dos enteros la distancia "
    "baja de 256 a 191 nt y sigue fuera del rango típico. Es el módulo, 149 de los 214 "
    "nt intercalados."
)

WHY_THE_COUNT_IS_EMITTED = (
    "La búsqueda dice sobre cuántos candidatos válidos descansa su elección. Si sólo uno "
    "conserva la estructura, «el mejor» es el único, y un caso no distingue que funcione "
    "de que acierte por suerte. Es la errata nº 10 aplicada a la elección de secuencia."
)

STANDARD_5 = PIECES["espaciador5"].sequence
STANDARD_3 = PIECES["espaciador3"].sequence

#: DONANTES PROHIBIDOS EN UN ESPACIADOR. El nombre declara el ALCANCE, y no es cosmetico:
#: la lista contiene `GTAAGT` y `GTAAGG`, que son los donantes LEGITIMOS del intron
#: quimerico y del MVM. Aplicada a secuencia de INTRON marcaria el donante real como
#: criptico; sobre un espaciador es correcta, porque ahi un GT canonico no tiene nada que
#: hacer. Se llamaba `CRYPTIC_DONORS` y era correcta POR ACCIDENTE DE CONTEXTO —por donde
#: se aplicaba, no por lo que decia—, que es el mismo patron que un `rmsk_mouse.out`
#: conectado por rol. La auditoria de geometria lo lista como RIESGO.
DONORS_FORBIDDEN_IN_SPACERS = ("GTAAGT", "GTGAGT", "GTAAGG", "GTGAGG")

#: Tope de longitud de un espaciador. NO es un criterio de diseño: es la frontera que
#: hace COMPROBABLE que lo que llega sea un espaciador. El barrido explora 0-45 y el
#: punto de partida es 20/45, asi que 60 deja margen de sobra y sigue estando lejisimos
#: de cualquier intron.
MAX_SPACER_LENGTH = 60

SPACER_SCOPE = (
    "Esta lista vale SOLO para espaciadores. Contiene donantes canónicos, que en un "
    "intrón son los legítimos: aplicada a secuencia de intrón marcaría el donante real "
    "como críptico."
)
POLYA_SIGNALS = ("AATAAA", "ATTAAA")
CASSETTE_SITES = ("GCTAGC", "GAGCTC", "ACGCGT", "ACCGGT", "CTCGAG", "GAATTC")
FORBIDDEN_RUNS = ("GGGG", "CCCC")
MAX_HOMOPOLYMER = 3
GC_MIN = 0.28
GC_MAX = 0.45

#: Cuantos candidatos se llegan a plegar como mucho. Cada plegado del intron cuesta
#: ~14 ms, asi que 300 son unos 4 s. Es un tope, no un objetivo.
DEFAULT_BUDGET = 300

#: Composicion con la que se generan los candidatos. Uniforme daria GC ~0,50 y casi todo
#: caeria fuera de la ventana 0,28-0,45; con esto la mayoria entra a la primera. Es un
#: detalle de generacion, no un filtro: el filtro sigue siendo `spacer_rejections`.
_BASE_WEIGHTS = (("A", 32), ("T", 32), ("G", 18), ("C", 18))


def spacer_rejections(sequence: str) -> tuple[str, ...]:
    """Motivos por los que un espaciador NO vale. Vacio = pasa todos los filtros.

    ABORTA si lo que se le pasa NO ES UN ESPACIADOR. Ver `SPACER_SCOPE`: la lista de
    donantes prohibidos contiene los canonicos, que en un intron son los LEGITIMOS, asi
    que aplicarla a otra cosa da un veredicto invertido y con muy buena pinta. Antes esto
    era correcto por accidente de contexto —por donde se llamaba, no por lo que decia— y
    eso es lo que se desactiva aqui.

    El guardia es LA LONGITUD y nada mas. Se probo tambien «empieza por GT y acaba en
    AG», y tiene FALSOS POSITIVOS: un espaciador generado al azar da eso una vez de cada
    256, y la busqueda empezo a abortar sobre candidatos legitimos. Un guardia que salta
    donde no hay nada que guardar se acaba apagando —es la leccion del guardia de la
    regla 6— asi que se queda solo el que no se equivoca: por debajo de
    `MIN_INTRON_LENGTH` (80) no hay ningun intron, y 60 deja margen.
    """
    limpia = "".join(str(sequence).split()).upper()
    if not limpia:
        return ("El espaciador está vacío.",)
    if len(limpia) > MAX_SPACER_LENGTH:
        raise ShmirDesignError(
            f"Se han pasado {len(limpia)} nt a `spacer_rejections`, y un espaciador no "
            f"pasa de {MAX_SPACER_LENGTH}. Esto NO es un espaciador. {SPACER_SCOPE} Se "
            f"aborta en vez de devolver un veredicto invertido con buena pinta."
        )

    motivos: list[str] = []
    for donante in DONORS_FORBIDDEN_IN_SPACERS:
        if donante in limpia:
            motivos.append(
                f"Lleva el donante críptico de splicing {donante}: podría abrir un 5'SS "
                f"dentro del intrón."
            )
    for señal in POLYA_SIGNALS:
        if señal in limpia:
            motivos.append(
                f"Lleva la señal de poliadenilación {señal}: podría cortar el "
                f"transcrito antes de tiempo."
            )
    base, largo = _longest_homopolymer(limpia)
    if largo > MAX_HOMOPOLYMER:
        motivos.append(
            f"Homopolimero de {largo} {base}: el límite es {MAX_HOMOPOLYMER}."
        )
    for tramo in FORBIDDEN_RUNS:
        if tramo in limpia:
            motivos.append(f"Lleva {tramo}.")
    for sitio in CASSETTE_SITES:
        if sitio in limpia:
            motivos.append(
                f"Lleva el sitio {sitio}, que ya está en el cassette: duplicarlo "
                f"romperia el clonaje."
            )
    gc = gc_fraction(limpia)
    if not GC_MIN <= gc <= GC_MAX:
        motivos.append(
            f"GC {gc:.3f}, fuera de la ventana {GC_MIN:.2f}-{GC_MAX:.2f}."
        )
    return tuple(motivos)


def is_acceptable(sequence: str) -> bool:
    return not spacer_rejections(sequence)


@dataclass(frozen=True)
class SpacerChoice:
    spacer5: str
    spacer3: str
    standard: bool
    structure: str
    mfe: float

    def format_text(self) -> str:
        lineas = [
            "Espaciadores del intrón:",
            f"  5' ({len(self.spacer5)} nt)  {self.spacer5}",
            f"  3' ({len(self.spacer3)} nt)  {self.spacer3}",
            "",
            f"  Plegado del intrón completo ({len(self.structure)} nt), "
            f"MFE {self.mfe:+.2f} kcal/mol:",
        ]
        lineas.extend(
            f"    {self.structure[i : i + 60]}"
            for i in range(0, len(self.structure), 60)
        )
        lineas.append("")
        if self.standard:
            lineas.append(
                "  Son los espaciadores ESTÁNDAR del proyecto, sin tocar: el 97-mero "
                "conserva su estructura dentro del intrón con ellos."
            )
        else:
            lineas.extend(
                [
                    "  ⚠  ESPACIADORES GENERADOS DE NOVO. Son ESPECÍFICOS DE ESTA GUÍA "
                    "y NO SON LOS ESTÁNDAR:",
                    "     con los estándar el 97-mero no conserva su estructura dentro "
                    "del intrón.",
                    "  ⚠  Un cassette MluI-AgeI montado con estos espaciadores NO es "
                    "intercambiable con",
                    "     el módulo NheI-SacI estándar: el intrón es otro. Si cambias la "
                    "horquilla de ese",
                    "     cassette por un módulo estándar, vuelves a tener el problema "
                    "que estos espaciadores",
                    "     resuelven — y al reves.",
                ]
            )
        return "\n".join(lineas)


@dataclass(frozen=True)
class SpacerSearch:
    choice: SpacerChoice | None
    evaluated: int
    #: Cuantos candidatos descarto el filtro duro ANTES de plegarlos.
    rejected: int
    note: str
    #: Cuantos pares CONSERVARON la estructura. Cero si ganaron los estandar: ahi no se
    #: busco nada, y confundir «no hizo falta buscar» con «apenas se encontro» seria
    #: emitir un aviso donde no hay nada que avisar.
    valid_count: int = 0

    @property
    def single_candidate(self) -> bool:
        """¿La eleccion descansa en UN SOLO candidato valido?"""
        return self.valid_count == 1

    @property
    def thinness_warning(self) -> str:
        """El aviso, o cadena vacia. Ver `WHY_THE_COUNT_IS_EMITTED`."""
        if not self.single_candidate:
            return ""
        return (
            f"⚠ La elección descansa en UN solo candidato válido de {self.evaluated} "
            f"plegado(s): con uno no se distingue «esto funciona» de «esto acierta por "
            f"suerte». Sube el presupuesto o cambia de candidato antes de fiarte."
        )

    def format_text(self) -> str:
        aviso = f"\n  {self.thinness_warning}" if self.thinness_warning else ""
        if self.choice is None:
            return f"Espaciadores — NO HAY\n  {self.note}{aviso}"
        return self.choice.format_text() + f"\n  {self.note}{aviso}"


def _random_spacer(rng: random.Random, length: int) -> str:
    bases = [b for b, _ in _BASE_WEIGHTS]
    pesos = [w for _, w in _BASE_WEIGHTS]
    return "".join(rng.choices(bases, weights=pesos, k=length))


def _candidates(
    rng: random.Random, length: int, cuantos: int
) -> tuple[list[str], int]:
    """Candidatos que YA pasan los filtros duros. Los que no, ni se pliegan.

    Devuelve tambien cuantos se descartaron. Si se agotan los intentos y salen menos de
    los pedidos, quien llama tiene que poder decirlo: un presupuesto que no se gasta
    entero y no se menciona parece una busqueda completa.
    """
    salida: list[str] = []
    descartados = 0
    intentos = 0
    tope = cuantos * 200
    while len(salida) < cuantos and intentos < tope:
        intentos += 1
        sonda = _random_spacer(rng, length)
        if is_acceptable(sonda):
            salida.append(sonda)
        else:
            descartados += 1
    return salida, descartados


def choose_spacers(
    *,
    hairpin: str,
    structure_alone: str,
    assemble: Callable[[str, str], str],
    budget: int = DEFAULT_BUDGET,
) -> SpacerSearch:
    """Elige los espaciadores. Los estandar son el caso base y ganan si funcionan.

    `assemble(espaciador5, espaciador3)` devuelve el intron completo montado.
    """
    from .folding import VIENNA_AVAILABLE, dot_bracket  # noqa: PLC0415

    if not VIENNA_AVAILABLE:
        return SpacerSearch(
            choice=None,
            evaluated=0,
            rejected=0,
            note=(
                "ViennaRNA no está instalado, así que no hay criterio que aplicar: el "
                "único criterio de selección es el plegado. No se generan espaciadores "
                "a ciegas. `pip install ViennaRNA`."
            ),
        )
    if budget < 1:
        raise ValueError(
            f"budget={budget}: hay que dejar evaluar al menos el caso base; se aborta."
        )

    evaluados = 0

    def evaluar(e5: str, e3: str) -> tuple[bool, str, float]:
        nonlocal evaluados
        evaluados += 1
        intron = assemble(e5, e3)
        estructura, mfe = dot_bracket(intron)
        inicio = intron.index(hairpin)
        dentro = estructura[inicio : inicio + len(hairpin)]
        return dentro == structure_alone, estructura, mfe

    # ── Caso base ────────────────────────────────────────────────────────────
    vale, estructura, mfe = evaluar(STANDARD_5, STANDARD_3)
    if vale:
        return SpacerSearch(
            choice=SpacerChoice(
                spacer5=STANDARD_5, spacer3=STANDARD_3, standard=True,
                structure=estructura, mfe=mfe,
            ),
            evaluated=evaluados,
            rejected=0,
            note=(
                "Los espaciadores estándar funcionan con esta guía; no se ha generado "
                "nada."
            ),
        )

    # ── Busqueda por desviacion creciente ────────────────────────────────────
    semilla = int(hashlib.md5(hairpin.encode("ascii"), usedforsecurity=False).hexdigest()[:8], 16)
    rng = random.Random(semilla)
    restante = budget - evaluados
    por_etapa = max(1, restante // 3)

    cinco, descartados5 = _candidates(rng, SPACER5_LENGTH, por_etapa)
    tres, descartados3 = _candidates(rng, SPACER3_LENGTH, por_etapa)
    descartados = descartados5 + descartados3
    corto = ""
    if len(cinco) < por_etapa or len(tres) < por_etapa:
        corto = (
            f" AVISO: no se pudieron generar todos los candidatos pedidos "
            f"({len(cinco)}/{por_etapa} de 5' y {len(tres)}/{por_etapa} de 3'): los "
            f"filtros duros dejan poco sitio. La busqueda es más corta de lo que dice "
            f"el presupuesto."
        )

    parejas: list[tuple[str, str]] = []
    parejas.extend((c, STANDARD_3) for c in cinco)
    parejas.extend((STANDARD_5, t) for t in tres)
    parejas.extend(zip(cinco, tres))

    validos: list[SpacerChoice] = []
    for e5, e3 in parejas:
        if evaluados >= budget:
            break
        vale, estructura, mfe = evaluar(e5, e3)
        if vale:
            validos.append(
                SpacerChoice(
                    spacer5=e5, spacer3=e3, standard=False,
                    structure=estructura, mfe=mfe,
                )
            )

    if not validos:
        return SpacerSearch(
            choice=None,
            evaluated=evaluados,
            rejected=descartados,
            note=(
                f"No se encontro ningún par de espaciadores que conserve la estructura "
                f"del 97-mero dentro del intrón, en {evaluados} candidato(s) plegados "
                f"(presupuesto {budget}; {descartados} descartado(s) por los filtros "
                f"duros antes de plegar). No se inventa uno peor: sube el presupuesto o "
                f"cambia de candidato.{corto}"
            ),
        )

    #: Criterio unico. A igualdad de MFE manda el orden de generacion, que es
    #: determinista, para que dos corridas no pidan bloques distintos.
    mejor = min(validos, key=lambda c: (c.mfe, c.spacer5, c.spacer3))
    return SpacerSearch(
        choice=mejor,
        evaluated=evaluados,
        rejected=descartados,
        valid_count=len(validos),
        note=(
            f"Los estándar NO conservan la estructura con esta guía. De "
            f"{evaluados} candidato(s) plegados, {len(validos)} la conservan; se ha "
            f"elegido el de menor MFE del intrón completo.{corto}"
        ),
    )
