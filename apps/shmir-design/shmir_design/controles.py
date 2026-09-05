"""Los dos controles del experimento: `shmir_scrambled` y `shmir_seed_mismatch`.

## AUTORIZACION

La regla 1 prohibe generar secuencia. Aqui hay una excepcion **escrita y acotada**,
concedida explicitamente el 2026-08-31 para construir los dos controles negativos del
experimento. Cubre **dos cosas y nada mas**:

  1. **permutacion** de las bases de una guia ya existente, posiciones 2-22. No se
     inventa ninguna base: el multiconjunto es EXACTAMENTE el de la guia original;
  2. **sustitucion** de 2 o 3 bases dentro de las posiciones **2-8** de esa misma guia.

NO cubre el andamio, ni los contextos de SGEP, ni el loop, ni los espaciadores, ni el
intron, ni ninguna guia nueva. La pasajera **no se genera**: se DERIVA con la regla del
propio andamio (`scaffold.passenger_from_guide`), igual que para cualquier candidato.

Todo lo que sale de aqui va **marcado** en toda la salida (`GENERATED_MARK`), como un
cassette con espaciadores de novo: un control es una construccion generada y no puede
ser indistinguible de una guia que salio del transcrito.

## La posicion 1 NO se permuta, y no es un detalle

Es CONVENIO y no dato: el pipeline fuerza ahi una T/U para que AGO2 cargue la hebra
(`comparative.CONVENTION_NOTE`). Permutarla cambiaria el control en algo que no es su
secuencia diana — o sea, en justo lo que el control existe para mantener igual. Se
permutan las 21 restantes, y como la posicion 1 ya era T, la composicion total se
conserva exactamente.

## Lo que se midio antes de escribir esto (2026-08-31, guia de `3utr:1018`)

Sobre 2000 permutaciones, con el 3'UTR murino verificado delante:

  - **GC**: 2000/2000 PASS, y **no puede fallar** — la permutacion conserva la
    composicion, asi que el GC del control es el del original. Ver `GC_NO_DISCRIMINA`.
  - **homopolimero**: 1763/2000 PASS. La permutacion SI puede juntar bases iguales.
  - **asimetria**: 1064/2000 PASS. **Es la que discrimina**, y es justo la propiedad
    que hace que un scrambled valga: un tallo mas debil se carga peor en AGO2 y la
    comparacion deja de medir la diana.
  - los tres a la vez: **925/2000 (46 %)**. Un filtro que no puede pasar nadie es peor
    que no tener filtro; este no es el caso.
  - **sitio de seed en el 3'UTR**: 451/2000 lo tienen. O sea que ese filtro **muerde**.
  - **tramo contiguo mas largo** contra el 3'UTR: moda 6, cola hasta 12 en 1 de 2000.
    La guia ORIGINAL da **22** — su diana entera. Es el control adversario de la medida:
    sin el, «cero» y «esto no mide nada» serian el mismo resultado.

Y el hallazgo que cambia como se lee la salida: **el plegado del 97-mero no discrimina
NADA**. Ver `PLEGADO_NO_DISCRIMINA`.

Python 3.11+, solo libreria estandar; ViennaRNA es opcional y sin el el plegado sale
`NOT_RUN` — que no es PASS.
"""

from __future__ import annotations

import hashlib
import itertools
import random
from dataclasses import dataclass

from .errors import ShmirDesignError
from .filters import FilterResult, FilterState, Verdict, overall_verdict
from .mirna import SEED_END, SEED_START

#: La autorizacion, en corto y en una constante para que un test la pueda exigir.
AUTHORIZATION = (
    "AUTORIZACIÓN ESCRITA Y ACOTADA (2026-08-31), regla 1. Cubre DOS cosas: la "
    "permutación de las bases de una guía existente (posiciones 2-22, composición "
    "conservada exactamente) y la sustitución de 2 o 3 bases dentro de las posiciones "
    "2-8 de esa misma guía. NO CUBRE el andamio, ni el loop, ni los contextos de SGEP, "
    "ni los espaciadores, ni el intrón, ni ninguna guía nueva. La pasajera no se genera: "
    "se deriva con la regla del propio andamio."
)

#: Marca que viaja con toda construccion de este modulo. No hay parametro para quitarla.
GENERATED_MARK = "SECUENCIA GENERADA — control, no candidato"

#: Los dos tipos de construccion.
KIND_SCRAMBLED = "shmir_scrambled"
KIND_SEED_MISMATCH = "shmir_seed_mismatch"

GC_ES_INVARIANTE = (
    "EL GC ES INVARIANTE BAJO PERMUTACIÓN, y de ahí sale una demostración en vez de un "
    "sorteo: si la guía original no pasa el filtro de GC, NINGUNA de sus permutaciones lo "
    "pasará nunca, porque todas tienen exactamente su composición. No hace falta sortear "
    "para saberlo, y sortear cuatro mil veces para acabar en cero daría un cero que se lee "
    "como una medida."
)

#: Y OJO CON POR QUE PUEDE PASAR ESO, que es lo que enseñó el caso real. Los umbrales
#: biofisicos estan definidos sobre la DIANA —una ventana de 22 nt del transcrito— y una
#: guia NO es la diana: se diferencia justo en la posicion 1, que es CONVENIO (la T que
#: fuerza el pipeline para que AGO2 cargue la hebra). En `3utr:449` esa T sustituye a una
#: G, asi que el GC de la guia es 0,273 y el de su diana 0,318: la diana pasa el filtro y
#: la guia no. El candidato es legitimo; lo que no se puede es construirle un scrambled
#: POR PERMUTACION bajo estos umbrales, y eso se dice en vez de devolver una lista vacia.
GUIA_NO_ES_DIANA = (
    "Los umbrales biofísicos están definidos sobre la DIANA y una guía no es su diana: "
    "difieren en la posición 1, que es convenio y no dato. Una guía cuya posición 1 "
    "original era G o C pierde ese nucleótido al forzarse la T, así que su GC baja y "
    "puede quedar por debajo del mínimo aunque su diana lo pase. El candidato sigue "
    "siendo válido; lo que no admite es un scrambled por permutación bajo estos umbrales."
)

GC_NO_DISCRIMINA = (
    "El GC de un scrambled es EXACTAMENTE el del original porque la permutación "
    "conserva la composición: este PASS no es información, es la definición."
)

PLEGADO_NO_DISCRIMINA = (
    "EL PLEGADO DEL 97-MERO NO DISCRIMINA, y por eso un PASS aquí no es evidencia de "
    "que el control se procese como el original. `passenger_from_guide` ELIGE la base de "
    "la posición 1 de la pasajera para que el 97-mero reproduzca la estructura de SGEP, "
    "y ABORTA si ninguna de las cuatro lo consigue: la comprobación posterior vuelve a "
    "preguntar algo que ya era condición para haber montado la horquilla. Medido el "
    "2026-08-31: 0 de 2000 permutaciones y 0 de 1134 variantes de seed dan una notación "
    "distinta, y tampoco la da una guía derivada del propio andamio para que compita con "
    "el loop. Lo que SÍ discrimina es la ASIMETRÍA —falla el 47 % de las permutaciones—, "
    "que además es la propiedad que decide qué hebra carga AGO2: un tallo más débil se "
    "procesa peor y entonces la comparación no mide la diana, mide el procesamiento."
)

APROBADO_A_MEDIAS = (
    "UN CONTROL APROBADO A MEDIAS ES PEOR QUE NINGUNO: se usa como si estuviera limpio. "
    "Mientras quede un frente en NOT_RUN el veredicto es INCOMPLETE y los frentes que "
    "faltan van nombrados aquí, uno a uno."
)

ORDEN_NO_ES_RANKING = (
    "EL ORDEN NO ES UN RANKING. Se emiten varios y no se elige: lo que hace bueno a un "
    "control es PARECERSE al original, no maximizar ninguna columna — y en particular "
    "una asimetría MÁS ALTA que la del original no es mejor, es otra cosa. Por eso va "
    "la del original al lado."
)

CUANTOS_CAMBIOS_SIN_DECIDIR = (
    "2 o 3 CAMBIOS: no se elige aquí. Se emiten las dos versiones con sus métricas y lo "
    "decide quien lee, con la tabla delante. Lo que la medida añade a la intuición es "
    "que el número de cambios importa MENOS que dónde caen: lo que deja residuo de "
    "reconocimiento es la RACHA de seed que queda intacta, no cuántas bases se tocaron."
)

LOS_DOS_NO_SE_SUSTITUYEN = (
    "SCRAMBLED Y SEED-MISMATCH NO SON INTERCAMBIABLES, y quedarse con uno deja viva una "
    "explicación alternativa. El scrambled controla «tener un shmiR» —saturación de la "
    "maquinaria, respuesta a ARN de doble cadena, carga viral— con una guía que no se "
    "parece a la nuestra. El seed-mismatch controla «tener ESTA guía»: misma "
    "composición, misma estructura, mismo sitio del andamio y la seed rota, así que lo "
    "único que cambia es el reconocimiento de la diana."
)

#: Tramo contiguo maximo admitido entre la diana virtual del control y la secuencia
#: analizada. DECLARADO como parametro de este analisis, NO citado de ningun sitio.
#:
#: Por que 11 y no otro: es la mitad de la guia, queda por encima del heptamero de seed
#: —que se comprueba aparte y con su propia medida, porque son dos mecanismos— y por
#: debajo de lo que haria falta para un corte por AGO2. Y la distribucion medida dice
#: que es un guardia de la COLA y no un filtro que moldee la piscina: sobre 2000
#: permutaciones la moda es 6 y solo 1 llega a 12. La guia original da 22.
MAX_CONTIGUO = 11

#: Cuanto puede ALEJARSE la asimetria del control de la del original, en kcal/mol.
#: DECLARADO como parametro de este analisis, NO citado de ningun sitio.
#:
#: POR QUE HACE FALTA UN SEGUNDO UMBRAL, que es lo que enseño medirlo: `MIN_ASYMMETRY`
#: (0,5) contesta «¿se carga esta hebra?» y un control necesita ademas «¿se carga IGUAL
#: que el original?». Son dos preguntas y la primera no implica la segunda. Sobre la
#: guia de `3utr:1018` —asimetria 7,65— las permutaciones tienen MEDIANA 0,67 y rango
#: de -6,45 a 8,05: casi todas PASAN el filtro y estan a 6 o 7 kcal/mol del original.
#: Emitirlas seria entregar un control que pasa todo y que se procesa de otra manera —
#: o sea, la comparacion midiendo el procesamiento en vez de la diana, que es
#: exactamente lo que un scrambled existe para evitar.
#:
#: POR QUE 1,5 y no otro: de 1380 permutaciones admisibles en 4000 sorteos hay 1 a
#: |delta| <= 0,5, 4 a <= 1,0, 17 a <= 1,5 y 38 a <= 2,0. Con 1,5 la piscina no se
#: vacia —un filtro que no puede pasar nadie es peor que no tener filtro— y el hueco se
#: queda en el 20 % del valor del original. No sale de ningun articulo.
MAX_DELTA_ASIMETRIA = 1.5

EQUIVALENCIA_NO_ES_ADMISION = (
    "PASAR EL FILTRO DE ASIMETRÍA NO ES SER EQUIVALENTE. El umbral del pipeline dice si "
    "una hebra se carga; un control necesita además cargarse IGUAL que la guía que "
    "controla, y eso es una distancia, no un mínimo. Medido sobre `3utr:1018`: la "
    "mediana de las permutaciones es 0,67 frente a 7,65 del original, así que casi todas "
    "pasan el filtro y ninguna sería comparable."
)

#: Cuantas permutaciones se sortean como mucho antes de rendirse.
DEFAULT_DRAWS = 4000

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _dna(sequence: str) -> str:
    """Normaliza a ADN. La guia circula en ARN por la app y en ADN por el andamio."""
    limpia = "".join(str(sequence).split()).upper().replace("U", "T")
    if not limpia or set(limpia) - set("ACGT"):
        raise ShmirDesignError(
            f"La guía {sequence!r} tiene caracteres que no son ADN ni ARN; se aborta "
            f"en vez de construir un control sobre una secuencia que no se entiende."
        )
    return limpia


def reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def longest_contiguous(guide: str, target: str) -> int:
    """El tramo CONTIGUO mas largo de la diana de `guide` que aparece en `target`.

    Es la pregunta del apareamiento EXTENSO —la que decide si algo puede cortarse—, y
    es distinta de la del sitio de seed, que son 6-7 nt y otro mecanismo. Las dos van
    por separado: juntarlas daria un «sin diana: PASS» que esconde una de las dos.
    """
    objetivo = reverse_complement(_dna(guide))
    diana = _dna(target)
    for largo in range(len(objetivo), 0, -1):
        for inicio in range(len(objetivo) - largo + 1):
            if objetivo[inicio : inicio + largo] in diana:
                return largo
    return 0


def seed_sites_in(guide: str, target: str) -> tuple:
    """Los sitios de seed de `guide` en `target`, con su clase. Cero es lo que se busca."""
    from .offtarget import self_sites

    return self_sites(_dna(guide).replace("T", "U"), target=_dna(target))


def adversarial_guide() -> str:
    """Una guia DERIVADA del andamio para que compita con el loop. Regla 1.

    No esta inventada: es el complementario reverso del loop de SGEP mas los tres
    primeros nucleotidos de su flanco 3'. Existe para poder comprobar que el criterio de
    plegado NO muerde ni siquiera aqui — sin un caso adversario, «todos pasan» y «esto
    no mide nada» son el mismo resultado.
    """
    from .scaffold import SGEP_SCAFFOLD

    return reverse_complement(SGEP_SCAFFOLD.loop + SGEP_SCAFFOLD.flank3[:3])


# ───────────────────────────── la construccion ─────────────────────────────


@dataclass(frozen=True)
class Control:
    """Una construccion de control, con la misma disciplina que un candidato.

    Un control sin veredictos no es un control, es una secuencia: por eso lleva un
    estado POR FRENTE y no un booleano, y por eso su veredicto es `INCOMPLETE` mientras
    quede uno sin correr.
    """

    kind: str
    guide: str
    passenger: str
    hairpin: str
    origin_guide: str
    origin_label: str
    heptamer: str
    heptamer_origin: str
    filters: tuple[FilterResult, ...]
    max_contiguous: int
    seed_sites: tuple
    asymmetry: float | None
    asymmetry_origin: float | None
    target_label: str
    #: Posiciones 1-based de la guia que se han cambiado. Vacio en un scrambled: ahi no
    #: se cambia ninguna base, se reordenan todas.
    changes: tuple[int, ...] = ()
    #: El tramo CONTIGUO mas largo de la seed que queda intacto. Solo tiene sentido en
    #: el seed-mismatch; en un scrambled la seed entera es otra.
    intact_run: int = 0

    @property
    def guide_rna(self) -> str:
        return self.guide.replace("T", "U")

    @property
    def verdict(self) -> Verdict:
        return overall_verdict(list(self.filters))

    @property
    def not_run_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.filters if f.state is FilterState.NOT_RUN)

    def row(self) -> dict[str, object]:
        """Una fila de tabla, con un estado POR FRENTE en su propia columna."""
        fila: dict[str, object] = {
            "tipo": self.kind,
            "origen": self.origin_label,
            "guia": self.guide_rna,
            "heptamero": self.heptamer,
            "heptamero_original": self.heptamer_origin,
            "cambios": len(self.changes),
            "posiciones": ", ".join(str(p) for p in self.changes),
            "racha_intacta": self.intact_run if self.changes else "",
            "max_contiguo": self.max_contiguous,
            "sitios_seed": len(self.seed_sites),
            # `asimetria_kcal` y no `asimetria`: el NUMERO y el ESTADO del filtro son
            # dos cantidades distintas, y con el mismo nombre la segunda pisaba a la
            # primera — la fila salia con «PASS» donde tenia que ir el valor con el que
            # se compara contra el original, sin dar ningun error. Es el mismo nombre
            # que usa `candidate_rows` para el numero. Hay test de que ningun filtro
            # comparte nombre con una metrica.
            "asimetria_kcal": "" if self.asymmetry is None else round(self.asymmetry, 2),
            "asimetria_kcal_original": (
                "" if self.asymmetry_origin is None else round(self.asymmetry_origin, 2)
            ),
            "veredicto": self.verdict.value,
        }
        for filtro in self.filters:
            if filtro.name in fila:
                raise ShmirDesignError(
                    f"El filtro {filtro.name!r} tiene el mismo nombre que una columna de "
                    f"métrica de la fila, así que la pisaría sin dar ningún error. Se "
                    f"aborta: una columna que cambia de significado a mitad de tabla es "
                    f"peor que una columna que falta."
                )
            fila[filtro.name] = filtro.state.value
        return fila

    def render(self) -> str:
        ancho = max([len("frente")] + [len(f.name) for f in self.filters])
        lineas = [
            f"═══ Control {self.kind} — derivado de {self.origin_label} ═══",
            "",
            f"  {GENERATED_MARK}",
            "",
            f"  guía        {self.guide_rna}",
            f"  original    {self.origin_guide.replace('T', 'U')}",
            f"  pasajera    {self.passenger}",
            f"  heptámero   {self.heptamer}  (el del original: {self.heptamer_origin})",
        ]
        if self.changes:
            lineas.append(
                f"  cambios     {len(self.changes)} en las posiciones "
                f"{', '.join(str(p) for p in self.changes)}; racha de seed intacta "
                f"{self.intact_run} nt"
            )
        lineas += [
            f"  horquilla   {self.hairpin}",
            "",
            f"── Sin diana en {self.target_label} ──",
            f"  tramo contiguo más largo   {self.max_contiguous} nt "
            f"(máximo admitido {MAX_CONTIGUO})",
            f"  sitios de seed             {len(self.seed_sites)}"
            + ("" if not self.seed_sites
               else ": " + ", ".join(s.describe() for s in self.seed_sites)),
            "",
            f"── Frentes ({len(self.filters)}) ──",
            f"  {'frente':<{ancho}} estado",
        ]
        lineas += [f"  {f.name:<{ancho}} {f.state.value}" for f in self.filters]
        lineas += ["", f"  veredicto  {self.verdict.value}"]
        if self.not_run_names:
            lineas += [
                "",
                f"  {APROBADO_A_MEDIAS}",
                "  Sin correr: " + ", ".join(self.not_run_names),
            ]
        lineas += ["", f"  {PLEGADO_NO_DISCRIMINA}"]
        for filtro in self.filters:
            if filtro.state is not FilterState.PASS or filtro.name == "GC":
                lineas.append(f"    · {filtro.name}: {filtro.reason}")
        return "\n".join(lineas)


# ───────────────────────────── los filtros ─────────────────────────────


def _biophysical(guide: str) -> tuple[tuple[FilterResult, ...], float | None]:
    """Los mismos filtros que un candidato, sobre la diana virtual de esta guia.

    Se evalua la DIANA —el complementario reverso— y no la guia, porque los umbrales del
    proyecto estan definidos sobre la ventana de 22 nt del transcrito. Da lo mismo para
    GC y homopolimero (son simetricos) y para la asimetria, que `evaluate_window`
    calcula sobre la guia que deriva de esa diana; hacerlo por el mismo camino garantiza
    que un control y un candidato se midan con la misma vara.
    """
    from .hard_filters import evaluate_window

    evaluacion = evaluate_window(reverse_complement(guide))
    return evaluacion.filters, evaluacion.asymmetry


def _fold_filter(hairpin) -> FilterResult:
    from .folding import check_fold

    resultado = check_fold(hairpin)
    return FilterResult(
        name=resultado.name,
        state=resultado.state,
        reason=f"{resultado.reason} {PLEGADO_NO_DISCRIMINA}",
    )


def _target_filter(guide: str, target: str, target_label: str) -> FilterResult:
    contiguo = longest_contiguous(guide, target)
    sitios = seed_sites_in(guide, target)
    if contiguo >= MAX_CONTIGUO or sitios:
        motivo = (
            f"Tiene diana en {target_label}: tramo contiguo de {contiguo} nt "
            f"(máximo admitido {MAX_CONTIGUO}) y {len(sitios)} sitio(s) de seed. "
            f"Un control con diana no controla nada."
        )
        return FilterResult(name="sin_diana", state=FilterState.FAIL, reason=motivo)
    return FilterResult(
        name="sin_diana",
        state=FilterState.PASS,
        reason=(
            f"Sin diana en {target_label}: el tramo contiguo más largo son {contiguo} nt "
            f"(máximo admitido {MAX_CONTIGUO}) y no hay ningún sitio de seed. Son DOS "
            f"mecanismos distintos y por eso van los dos números: el apareamiento "
            f"extenso, que es el que permite un corte, y el sitio de seed, que reprime "
            f"con 6-7 nt y ningún alineamiento lo ve."
        ),
    )


def _equivalence_filter(asymmetry, origin_asymmetry) -> FilterResult:
    """La asimetria del control contra la del ORIGINAL. Distancia, no minimo."""
    if asymmetry is None or origin_asymmetry is None:
        return FilterResult(
            name="equivalencia_asimetria",
            state=FilterState.NOT_RUN,
            reason=(
                "No se ha calculado la asimetría de una de las dos hebras, así que no "
                "se puede decir si el control se procesa como el original. NOT_RUN no "
                "es PASS."
            ),
        )
    delta = asymmetry - origin_asymmetry
    if abs(delta) > MAX_DELTA_ASIMETRIA:
        return FilterResult(
            name="equivalencia_asimetria",
            state=FilterState.FAIL,
            reason=(
                f"Asimetría {asymmetry:+.2f} frente a {origin_asymmetry:+.2f} del "
                f"original: {delta:+.2f} kcal/mol, por encima de los "
                f"{MAX_DELTA_ASIMETRIA} admitidos. {EQUIVALENCIA_NO_ES_ADMISION}"
            ),
        )
    return FilterResult(
        name="equivalencia_asimetria",
        state=FilterState.PASS,
        reason=(
            f"Asimetría {asymmetry:+.2f} frente a {origin_asymmetry:+.2f} del original: "
            f"{delta:+.2f} kcal/mol, dentro de los {MAX_DELTA_ASIMETRIA} admitidos."
        ),
    )


def _specificity_filter() -> FilterResult:
    return FilterResult(
        name="especificidad",
        state=FilterState.NOT_RUN,
        reason=(
            "No hay `refseq_rna.fa`, así que sólo se ha comprobado que no tenga diana en "
            "la secuencia analizada. Que no la tenga AHÍ no es que no la tenga en el "
            "transcriptoma: NOT_RUN no es PASS."
        ),
    )


def _seed_filter(guide: str, passenger: str, mature, abundance, species: str):
    from .mirna import filter_seed_collision

    return filter_seed_collision(
        guide.replace("T", "U"), mature, abundance,
        passenger.replace("T", "U"), species=species,
    ).as_filter()


#: QUE HABRA QUE HACER cuando llegue `transcriptoma_3utr.fa`, escrito ahora para que no
#: se resuelva mal despues. La carga de off-targets de un control NO se lee contra cero:
#: se lee contra la del ORIGINAL. Un control con MENOS off-targets que la guia que
#: controla tampoco sirve —deja de ser equivalente en ese eje— y un umbral absoluto no
#: puede decir eso. Ademas la carga es un numero COMPARATIVO y nunca un veredicto
#: (`offtarget.USE_NOTE`), asi que este frente no podra dar FAIL ni siquiera entonces.
OFFTARGET_CUANDO_LLEGUE = (
    "Cuando llegue `transcriptoma_3utr.fa`, la carga de off-targets del control se "
    "compara con la del ORIGINAL, no con cero: lo que hace válido a un control es "
    "PARECERSE, y una carga mucho menor lo hace tan poco comparable como una mucho "
    "mayor. Sigue siendo un número comparativo y no un veredicto."
)


def _offtarget_filter() -> FilterResult:
    """Hoy siempre NOT_RUN: el fichero no existe, y no se escribe la rama que no corre.

    La alternativa era dejar escrita una rama que ningun test puede recorrer con datos
    reales — la categoria `[sin_camino]` de `data/guardias.toml`—, y este proyecto ya
    sabe lo que cuesta: se lee en el codigo y se cree que corre.
    """
    return FilterResult(
        name="offtarget_seed",
        state=FilterState.NOT_RUN,
        reason=(
            "No hay `transcriptoma_3utr.fa`, así que no se sabe cuántos mensajeros "
            "llevan la seed de este control. Un control con off-targets propios "
            "contamina justo lo que viene a controlar. NOT_RUN no es PASS. "
            + OFFTARGET_CUANDO_LLEGUE
        ),
    )


def _transgene_filter(guide: str, transgene_db) -> FilterResult:
    """Contra el casete AAV, REGISTRO A REGISTRO y nunca sobre su concatenacion.

    Concatenar los registros inventa junturas que no existen en ninguna molecula, y un
    tramo contiguo que cruzara una de ellas seria un hallazgo falso. Es el mismo motivo
    por el que los bloques conservados se miran CONTENIDOS y no solapando.
    """
    if transgene_db is None:
        return FilterResult(
            name="transgen",
            state=FilterState.NOT_RUN,
            reason=(
                "No hay casete AAV cargado, así que no se ha comprobado que el control "
                "no tenga diana dentro de la construcción terapéutica. NOT_RUN no es "
                "PASS."
            ),
        )
    peor = max(
        (longest_contiguous(guide, secuencia)
         for secuencia in transgene_db.records.values()),
        default=0,
    )
    if peor >= MAX_CONTIGUO:
        return FilterResult(
            name="transgen",
            state=FilterState.FAIL,
            reason=(
                f"El control tiene {peor} nt contiguos contra {transgene_db.name}: "
                f"apagaría la construcción terapéutica, que es el fallo silencioso que "
                f"este filtro existe para impedir."
            ),
        )
    return FilterResult(
        name="transgen",
        state=FilterState.PASS,
        reason=(
            f"Sin apareamiento extenso contra {transgene_db.name} "
            f"({len(transgene_db.records)} registro(s)): {peor} nt contiguos como mucho, "
            f"por debajo de los {MAX_CONTIGUO} admitidos."
        ),
    )


def _build(
    *, kind, guide, origin_guide, origin_label, target, target_label,
    mature, abundance, transgene_db, species, changes=(), intact_run=0,
) -> Control:
    from .scaffold import build_hairpin

    horquilla = build_hairpin(guide)
    pasajera = horquilla.passenger.sequence
    biofisicos, asimetria = _biophysical(guide)
    _, asimetria_origen = _biophysical(origin_guide)
    if kind == KIND_SCRAMBLED:
        # El GC de una PERMUTACION no puede fallar si el original pasaba, asi que su
        # PASS no es informacion. Se dice PEGADO al motivo y no en una nota aparte:
        # quien lee una columna verde no va a buscar la aclaracion a otro sitio. En el
        # seed-mismatch NO se dice, porque ahi la composicion SI cambia y el filtro SI
        # puede fallar — la misma marca en los dos casos la haria invisible.
        biofisicos = tuple(
            f if f.name != "GC"
            else FilterResult(name=f.name, state=f.state,
                              reason=f"{f.reason} {GC_NO_DISCRIMINA}")
            for f in biofisicos
        )
    filtros = (
        *biofisicos,
        _fold_filter(horquilla),
        _equivalence_filter(asimetria, asimetria_origen),
        _target_filter(guide, target, target_label),
        _specificity_filter(),
        _seed_filter(guide, pasajera, mature, abundance, species),
        _offtarget_filter(),
        _transgene_filter(guide, transgene_db),
    )
    return Control(
        kind=kind,
        guide=guide,
        passenger=pasajera,
        hairpin=horquilla.sequence,
        origin_guide=origin_guide,
        origin_label=origin_label,
        heptamer=guide[SEED_START - 1 : SEED_END],
        heptamer_origin=origin_guide[SEED_START - 1 : SEED_END],
        filters=filtros,
        max_contiguous=longest_contiguous(guide, target),
        seed_sites=seed_sites_in(guide, target),
        asymmetry=asimetria,
        asymmetry_origin=asimetria_origen,
        target_label=target_label,
        changes=tuple(changes),
        intact_run=intact_run,
    )


# ───────────────────────────── scrambled ─────────────────────────────


def _seed_for(guide: str) -> int:
    """Semilla DERIVADA de la guia: la misma guia da siempre los mismos controles.

    Sin esto, dos corridas del mismo diseño pedirian oligos distintos. Es la misma
    disciplina que `spacers.py`.
    """
    return int(hashlib.sha256(guide.encode("ascii")).hexdigest()[:8], 16)


def scrambled_permutations(guide: str, *, draws: int = DEFAULT_DRAWS):
    """Sortea permutaciones de las posiciones 2-22. La 1 es CONVENIO y no se toca."""
    limpia = _dna(guide)
    rnd = random.Random(_seed_for(limpia))
    resto = list(limpia[1:])
    vistas = set()
    for _ in range(draws):
        rnd.shuffle(resto)
        candidata = limpia[0] + "".join(resto)
        if candidata == limpia or candidata in vistas:
            continue
        vistas.add(candidata)
        yield candidata


def scrambled_candidates(
    guide: str,
    *,
    origin_label: str,
    target: str,
    target_label: str,
    mature=None,
    abundance=None,
    transgene_db=None,
    species: str = "",
    wanted: int = 5,
    draws: int = DEFAULT_DRAWS,
) -> tuple[Control, ...]:
    """Varios scrambled con sus metricas. NO elige: ver `ORDEN_NO_ES_RANKING`.

    Se admite una permutacion cuando pasa los filtros que NO dependen de ningun fichero
    —los tres biofisicos y la ausencia de diana en la secuencia analizada—. Los que si
    dependen de un fichero salen en su columna, en `NOT_RUN` si el fichero no esta:
    filtrar por ellos dejaria la piscina vacia por una laguna, que es otra cosa.
    """
    limpia = _dna(guide)
    objetivo = _dna(target)
    biofisicos_origen, asimetria_origen = _biophysical(limpia)
    # DEMOSTRACION, no sorteo: el GC es invariante bajo permutacion. Si el original no lo
    # pasa, ninguna permutacion lo pasara — y descubrirlo con 4000 sorteos daria un cero
    # que se lee como una medida en vez de como una imposibilidad.
    gc_origen = next(f for f in biofisicos_origen if f.name == "GC")
    if gc_origen.state is not FilterState.PASS:
        raise ShmirDesignError(
            f"La guía de {origin_label} no pasa el filtro de GC evaluada como su propia "
            f"diana ({gc_origen.reason}), así que NINGUNA de sus permutaciones lo pasará. "
            f"{GC_ES_INVARIANTE} {GUIA_NO_ES_DIANA}"
        )
    elegidas: list[Control] = []
    sorteadas = biofisicos_ok = equivalentes = 0
    for candidata in scrambled_permutations(limpia, draws=draws):
        sorteadas += 1
        biofisicos, _ = _biophysical(candidata)
        if any(f.state is not FilterState.PASS for f in biofisicos):
            continue
        biofisicos_ok += 1
        # La EQUIVALENCIA, no solo el minimo: ver `EQUIVALENCIA_NO_ES_ADMISION`. Sin
        # esto salian scrambled a 6 kcal/mol del original, con todos los filtros en
        # verde y sin ser comparables con nada.
        if abs(_biophysical(candidata)[1] - asimetria_origen) > MAX_DELTA_ASIMETRIA:
            continue
        equivalentes += 1
        if longest_contiguous(candidata, objetivo) >= MAX_CONTIGUO:
            continue
        if seed_sites_in(candidata, objetivo):
            continue
        elegidas.append(_build(
            kind=KIND_SCRAMBLED, guide=candidata, origin_guide=limpia,
            origin_label=origin_label, target=objetivo, target_label=target_label,
            mature=mature, abundance=abundance, transgene_db=transgene_db,
            species=species,
        ))
        if len(elegidas) == wanted:
            return tuple(elegidas)
    raise ShmirDesignError(
        f"Sólo salen {len(elegidas)} scrambled de los {wanted} pedidos en {sorteadas} "
        f"sorteos: {biofisicos_ok} pasaron los biofísicos y {equivalentes} de ésos "
        f"quedaron a menos de {MAX_DELTA_ASIMETRIA} kcal/mol del original. Se aborta en vez de "
        f"devolver menos de los pedidos sin decirlo: un panel de controles más corto de "
        f"lo que se pidió es exactamente la forma que tiene un brazo de desaparecer sin "
        f"que nadie lo vea."
    )


# ───────────────────────────── seed mismatch ─────────────────────────────


def _seed_positions() -> tuple[int, ...]:
    """Las posiciones de la seed, 0-based. Se DERIVAN de `mirna`, no se teclean."""
    return tuple(range(SEED_START - 1, SEED_END))


def seed_mismatch_variants(guide: str, *, changes: int):
    """TODAS las variantes con `changes` cambios en 2-8. Enumeracion, no sorteo.

    Son 189 con 2 cambios y 945 con 3: caben enteras, asi que no hace falta muestrear y
    el resultado no depende de ninguna semilla.
    """
    limpia = _dna(guide)
    if changes not in (2, 3):
        raise ShmirDesignError(
            f"Se piden {changes} cambios y la autorización cubre 2 o 3. Se aborta: "
            f"cambiar más bases de las autorizadas es generar una guía nueva."
        )
    for sitios in itertools.combinations(_seed_positions(), changes):
        for bases in itertools.product("ACGT", repeat=changes):
            if any(base == limpia[sitio] for sitio, base in zip(sitios, bases, strict=True)):
                continue
            variante = list(limpia)
            for sitio, base in zip(sitios, bases, strict=True):
                variante[sitio] = base
            yield "".join(variante)


def intact_run(guide: str, variant: str) -> int:
    """El tramo CONTIGUO mas largo de la seed que queda sin tocar.

    Es lo que mide el RESIDUO DE RECONOCIMIENTO, y es mejor medida que el numero de
    cambios: dos cambios pegados dejan una racha de 5 nt y dos cambios repartidos dejan
    2. Lo que importa no es cuantas bases se tocaron, sino donde.
    """
    limpia, otra = _dna(guide), _dna(variant)
    mejor = actual = 0
    for posicion in _seed_positions():
        actual = 0 if limpia[posicion] != otra[posicion] else actual + 1
        mejor = max(mejor, actual)
    return mejor


def _changed_positions(guide: str, variant: str) -> tuple[int, ...]:
    return tuple(
        i + 1 for i, (a, b) in enumerate(zip(guide, variant, strict=True)) if a != b
    )


def _is_clean(variant, *, target, mature, species) -> bool:
    """Limpio en los tres ejes que NO dependen de plegar: seed propia, nucleo, biofisicos."""
    from .mirna import core_hits

    biofisicos, _ = _biophysical(variant)
    if any(f.state is not FilterState.PASS for f in biofisicos):
        return False
    if seed_sites_in(variant, target):
        return False
    if mature is not None and core_hits(
        mature.names_for(variant[SEED_START - 1 : SEED_END]), species=species or "mouse"
    ):
        return False
    return True


def seed_mismatch_candidates(
    guide: str,
    *,
    origin_label: str,
    changes: int,
    target: str,
    target_label: str,
    mature=None,
    abundance=None,
    transgene_db=None,
    species: str = "",
    wanted: int = 5,
) -> tuple[Control, ...]:
    """Las variantes limpias, ordenadas por RACHA INTACTA. El orden es el criterio.

    Aqui el orden SI declara un criterio, y va escrito: menos racha intacta es menos
    residuo de reconocimiento. Lo que la app no hace es elegir UNA, ni decidir entre 2 y
    3 cambios — para eso esta `mismatch_comparison`.
    """
    limpia = _dna(guide)
    objetivo = _dna(target)
    limpias = [
        variante for variante in seed_mismatch_variants(limpia, changes=changes)
        if _is_clean(variante, target=objetivo, mature=mature, species=species)
    ]
    if not limpias:
        raise ShmirDesignError(
            f"Ninguna de las variantes con {changes} cambios pasa los filtros. Se "
            f"aborta: un control que no pasa lo que se le exige a un candidato no es un "
            f"control."
        )
    limpias.sort(key=lambda v: (intact_run(limpia, v), v))
    return tuple(
        _build(
            kind=KIND_SEED_MISMATCH, guide=variante, origin_guide=limpia,
            origin_label=origin_label, target=objetivo, target_label=target_label,
            mature=mature, abundance=abundance, transgene_db=transgene_db,
            species=species, changes=_changed_positions(limpia, variante),
            intact_run=intact_run(limpia, variante),
        )
        for variante in limpias[:wanted]
    )


def mismatch_comparison(
    guide: str,
    *,
    origin_label: str,
    target: str,
    target_label: str,
    mature=None,
    species: str = "",
) -> list[dict[str, object]]:
    """Las DOS versiones con sus metricas, para decidir con la tabla delante.

    No pliega: el plegado esta medido y no discrimina (`PLEGADO_NO_DISCRIMINA`), asi que
    plegar 1134 horquillas para obtener 1134 respuestas iguales seria justo el trabajo
    que ese hallazgo ahorra.
    """
    from .mirna import core_hits

    limpia = _dna(guide)
    objetivo = _dna(target)
    filas: list[dict[str, object]] = []
    for cambios in (2, 3):
        variantes = list(seed_mismatch_variants(limpia, changes=cambios))
        limpias = [
            v for v in variantes
            if _is_clean(v, target=objetivo, mature=mature, species=species)
        ]
        chocan = (
            None if mature is None
            else sum(
                1 for v in variantes
                if core_hits(
                    mature.names_for(v[SEED_START - 1 : SEED_END]),
                    species=species or "mouse",
                )
            )
        )
        rachas = [intact_run(limpia, v) for v in limpias]
        filas.append({
            "cambios": cambios,
            "origen": origin_label,
            "diana": target_label,
            "variantes": len(variantes),
            "limpias": len(limpias),
            "racha_minima": min(rachas) if rachas else None,
            "con_la_racha_minima": (
                sum(1 for r in rachas if r == min(rachas)) if rachas else 0
            ),
            "chocan_nucleo": chocan,
            "sin_sitio_seed": sum(
                1 for v in variantes if not seed_sites_in(v, objetivo)
            ),
        })
    return filas


# ───────────────────────────── los seis brazos ─────────────────────────────


@dataclass(frozen=True)
class ExperimentArm:
    key: str
    label: str
    #: QUE AISLA este brazo. Sin esto la lista es una checklist y no dice que se pierde
    #: al quitar uno — que es justo lo que hay que saber para decidir si se quita.
    isolates: str


ARMS = (
    ExperimentArm(
        key="vehiculo",
        label="vehículo",
        isolates=(
            "el procedimiento: inyección, cirugía y formulación, sin vector. Es la línea "
            "de base contra la que se lee todo lo demás."
        ),
    ),
    ExperimentArm(
        key="shmir_scrambled",
        label="shmiR scrambled",
        isolates=(
            "tener UN shmiR: saturación de la maquinaria de miARN, respuesta a ARN de "
            "doble cadena y carga viral, con una guía sin diana. Lo que quede de efecto "
            "aquí no es del silenciamiento."
        ),
    ),
    ExperimentArm(
        key="shmir_seed_mismatch",
        label="shmiR con la seed rota",
        isolates=(
            "tener ESTA guía: misma composición, misma estructura y mismo sitio, con el "
            "reconocimiento de la diana roto. Lo que quede de efecto aquí es off-target "
            "de esta secuencia, no del knockdown."
        ),
    ),
    ExperimentArm(
        key="shmir_only",
        label="sólo shmiR",
        isolates=(
            "la contribución del knockdown sin la proteína dominante negativa."
        ),
    ),
    ExperimentArm(
        key="dn_only",
        label="sólo DN",
        isolates=(
            "la contribución de la dominante negativa sin knockdown. Es además el techo "
            "de expresión con el que se lee la construcción completa."
        ),
    ),
    ExperimentArm(
        key="completa",
        label="construcción completa",
        isolates=(
            "el efecto terapéutico que se quiere demostrar. Sin los otros cinco no se "
            "puede atribuir a nada en concreto."
        ),
    ),
)


def missing_arms(present) -> tuple[ExperimentArm, ...]:
    """Que brazos faltan. `present` son las claves declaradas."""
    declarados = {str(clave) for clave in present}
    return tuple(brazo for brazo in ARMS if brazo.key not in declarados)


def arms_warning(present) -> dict[str, object] | None:
    """AVISO, no impedimento — como el del núcleo de seed compartido.

    Devuelve `None` cuando estan los seis. La app avisa y deja seguir: quien monta un
    experimento puede tener una razon para dejar fuera un brazo, y lo que no puede es
    dejarlo fuera sin enterarse.
    """
    faltan = missing_arms(present)
    if not faltan:
        return None
    detalle = "; ".join(f"{b.key} (aísla {b.isolates})" for b in faltan)
    return {
        "rojo": True,
        "texto": (
            f"Faltan {len(faltan)} de los {len(ARMS)} brazos del experimento: {detalle} "
            f"{LOS_DOS_NO_SE_SUSTITUYEN}"
        ),
    }
