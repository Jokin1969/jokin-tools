"""Score externo de la horquilla: de donde viene el numero y por que hoy no hay ninguno.

**Este modulo no puntua nada.** No hay clasificador propio, no hay modelo entrenado con
cifras sacadas de la literatura y ningun numero calculado aqui sale con la etiqueta de
miRarchitect ni de SplashRNA. Lo que hay es:

1. `ExternalScore`, que transporta un score AJENO junto con su procedencia. Sin
   procedencia no se acepta un valor, y sin valor la columna va vacia — no a cero.
2. `splashrna_features`, que calcula las features que describe el paper de SplashRNA y
   las emite **como columnas separadas**, sin combinarlas. Una feature no es un score.
3. `manual_instructions`, el bloque que el informe imprime para puntuar a mano cuando
   no hay API.

Estado de los dos servicios (regla 4, comprobado el 2026-08-25):

    $ curl -sS --max-time 20 https://mirarchitect.org
    curl: (56) CONNECT tunnel failed, response 403
    $ curl -sS --max-time 20 https://www.mirarchitect.org      → mismo 403
    $ curl -sS --max-time 20 https://splashrna.mskcc.org       → mismo 403
    $ curl -sS --max-time 20 https://splashrna.org             → mismo 403

El proxy de este entorno responde `connect_rejected — gateway answered 403 to CONNECT
(policy denial or upstream failure)` a los cuatro. Eso significa **que no se ha podido
comprobar**, no que no existan: la denegacion es de la politica de red de aqui, y la
diferencia importa demasiado para redondearla. Por eso `MIRARCHITECT_API` y
`SPLASHRNA_API` valen `None` y ninguna URL de este modulo se usa como endpoint: la
unica que aparece es la que el informe le da a una persona para que la abra en su
navegador, marcada como no verificada desde aqui.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import ShmirDesignError
from .hard_filters import gc_fraction
from .mirna import SEED_END, SEED_START
from .scaffold import SGEP_SCAFFOLD, ScaffoldSpec
from .thermo import turner_asymmetry

#: Fecha de la comprobacion de los endpoints. Viaja al informe: una comprobacion sin
#: fecha no dice nada dentro de seis meses.
VERIFICACION = "2026-08-25"

#: Endpoints verificados. `None` **no** significa "no existe": significa que desde aqui
#: no se ha podido comprobar (403 del proxy) y la regla 4 prohibe escribir una URL como
#: endpoint sin verificarla. El dia que una responda, se anota en
#: `docs/endpoints-verificados.md` con su peticion exacta y se pone aqui.
MIRARCHITECT_API = None
SPLASHRNA_API = None

#: Las direcciones de los dos servicios, dadas por el responsable del proyecto. Son
#: para que las abra una PERSONA: no las llama ningun codigo y no son endpoints
#: verificados (ver `docs/endpoints-verificados.md` — desde aqui las dos dan 403 del
#: proxy). Si algun dia se llaman desde el codigo, se verifican antes (regla 4).
MIRARCHITECT_URL = "https://mirarchitect.cs.put.poznan.pl/"
#: Ojo, esta va por `http://`, sin cifrar: el navegador avisara. Es la que hay.
SPLASHRNA_URL = "http://splashrna.mskcc.org/"
#: Portal de la Genetic Perturbation Platform del Broad. No da `score_externo`: es
#: contraste, no una fuente de la columna.
GPP_URL = "https://portals.broadinstitute.org/gpp/public/"

#: La de las instrucciones de puntuacion manual, que son las de miRarchitect.
MANUAL_URL = MIRARCHITECT_URL

#: El andamio que hay que seleccionar en el formulario. Es el del proyecto.
MANUAL_SCAFFOLD = "miR-E"


@dataclass(frozen=True)
class ExternalTool:
    """Un servicio externo al que se manda a una persona, con que pegarle."""

    name: str
    url: str
    what: str
    paste: str

    @property
    def tooltip(self) -> str:
        """El texto de ayuda ya montado: la pagina no compone nada (regla 6)."""
        return f"{self.what}. Que pegar: {self.paste}."


EXTERNAL_TOOLS = (
    ExternalTool(
        name="miRarchitect",
        url=MIRARCHITECT_URL,
        what="puntua el diseño de la horquilla; es la fuente de `score_externo`",
        paste="la guía de 22 nt en ADN y el andamio miR-E",
    ),
    ExternalTool(
        name="SplashRNA",
        url=SPLASHRNA_URL,
        what="predice potencia de shRNA; sus features salen aquí en columnas feat_*",
        paste="la guía de 22 nt en ADN",
    ),
    ExternalTool(
        name="GPP Web Portal",
        url=GPP_URL,
        what=(
            "portal de la Genetic Perturbation Platform del Broad, con sus "
            "herramientas de diseño; sirve para contrastar, NO alimenta score_externo"
        ),
        paste="el gen diana",
    ),
)

#: Las dos columnas que viajan en la tabla comparativa, al lado de `knockdown_medido`.
SCORE_COLUMNS = ("score_externo", "fuente_score")

#: Banderas del cruce con miRarchitect. La tercera no la pidio el encargo —pedia dos—
#: pero la distancia de desplazamiento es un NUMERO y meterlo dentro de una etiqueta
#: (`ventana_desplazada_9nt`) la haria imposible de filtrar. Va en su columna.
MIRARCH_COLUMNS = ("mirarch_confirmado", "mirarch_rank", "mirarch_shift_nt")

#: Mas alla de esto no se asigna score: no es la misma ventana. Con guias de 22 nt, 15
#: de desplazamiento dejan 7 nt de solapamiento.
MAX_SHIFT = 15
#: Minimo solapamiento exacto para dar dos ventanas por la misma. Sale del limite
#: de arriba: 22 nt de guia menos 15 de desplazamiento.
MIN_OVERLAP = 7
#: Hasta aqui la ventana se considera la misma; por encima, `ventana_desplazada`.
DISPLACED_SHIFT = 5
#: Por DEBAJO de esto miRarchitect da la guia por buena. Ojo: su escala esta INVERTIDA.
CONFIRMED_BELOW = 20.0

def guide_shift(ours: str, theirs: str, *, max_shift: int = MAX_SHIFT) -> int | None:
    """Cuantos nt esta corrida una ventana respecto de la otra, o `None`.

    Se cruza por SECUENCIA y no por coordenada a proposito: miRarchitect numera sus
    ventanas con un convenio que no es el nuestro —para la misma guia da a veces una
    posicion y a veces otra— asi que cruzar por numero pegaria un score en la fila del
    candidato de al lado.

    **La posicion 1 no se compara.** Los dos lados fuerzan ahi una T —la U de la
    posicion 1 que quiere AGO2— asi que esa base es un convenio, no un dato: en la
    ventana 3'UTR 819 la base real es una C en los dos casos y la T forzada era el
    unico desapareamiento de un solapamiento de 19 nt. Compararla dejaba sin cruzar
    ventanas que son la misma.

    El solapamiento tiene que ser EXACTO y de al menos `MIN_OVERLAP` nt: sin ese minimo,
    tres bases sueltas emparejan con cualquier cosa.
    """
    a = "".join(ours.split()).upper().replace("U", "T")[1:]
    b = "".join(theirs.split()).upper().replace("U", "T")[1:]
    if not a or not b:
        return None
    for desplazamiento in sorted(range(-max_shift, max_shift + 1), key=abs):
        ia = max(0, desplazamiento)
        ib = max(0, -desplazamiento)
        solape = min(len(a) - ia, len(b) - ib)
        if solape < MIN_OVERLAP:
            continue
        if a[ia : ia + solape] == b[ib : ib + solape]:
            return desplazamiento
    return None


class ScoreSource(StrEnum):
    """De donde salio el numero. Nunca se deduce: se declara al construir el score."""

    MIRARCHITECT_API = "mirarchitect_api"
    SPLASHRNA_API = "splashrna_api"
    #: Reservada. Hoy NO se emite: las features se calculan y se publican, pero de
    #: ellas no sale ningun score, porque entrenar un modelo aqui esta prohibido. Sera
    #: la etiqueta correcta el dia que alguien pase estas features por el clasificador
    #: publicado de SplashRNA.
    SPLASHRNA_FEATURES = "splashrna_features"
    MANUAL_MIRARCHITECT = "manual_mirarchitect"


#: El fichero VERSIONADO del que salen los pares de la corrida manual. Lo que se
#: declara aqui es CUAL es el ancla —eso es una decision— y los NUMEROS se leen de el.
#:
#: Antes los pares estaban TRANSCRITOS en `EVIDENCE`, y estaban transcritos del fichero
#: EQUIVOCADO: los cinco cuadraban con `mirarchitect_prnp_raton.tsv`, que el manifiesto
#: marca «NO USAR» por haberse puntuado sobre el 3'UTR fabricado de 1246 nt (errata
#: nº 5). Dos definiciones del mismo dato, y la copia de codigo apuntando a un fichero
#: retirado: la que nadie vuelve a mirar es la que se queda mal.
MANUAL_EVIDENCE_FILE = "mirarchitect_prnp_export_buena.csv"


@dataclass(frozen=True)
class ScoreEvidence:
    """La direccion de una escala, con el dato del que se saco. No es una opinion."""

    lower_is_better: bool
    #: Fichero versionado del que se LEEN los pares. `None` para una fuente que hereda
    #: la direccion de otra y no tiene evidencia propia.
    evidence_file: str | None
    note: str

    @property
    def pairs(self) -> tuple[tuple[int, float], ...]:
        """Pares (puesto, score) LEIDOS del fichero. Si la escala fuera de
        mayor-es-mejor, el puesto 3 no podria tener un score menor que el puesto 22.

        Salen TODAS las filas, no una muestra: elegir cinco vuelve a ser transcribir a
        mano, que es exactamente lo que esto deja de hacer.
        """
        if self.evidence_file is None:
            return ()
        return read_evidence_pairs(self.evidence_file)


def read_evidence_pairs(filename: str) -> tuple[tuple[int, float], ...]:
    """Lee los pares (puesto, score) del export versionado, o aborta.

    El puesto es el ORDEN DE LAS FILAS: estos ficheros no traen columna de rank, y
    sacarlo de otro sitio seria inventarselo.
    """
    from pathlib import Path  # noqa: PLC0415

    from .mirarchitect import parse_export  # noqa: PLC0415
    from .presencia import hay_fichero  # noqa: PLC0415

    ruta = Path(__file__).resolve().parent.parent / "data" / "reference" / filename
    if not hay_fichero(ruta):
        raise ShmirDesignError(
            f"No hay contenido en {ruta}, que es de donde salen los pares (puesto, "
            f"score) que registran la dirección de la escala de miRarchitect. Se "
            f"aborta el paso 'evidencia de la dirección del score': transcribirlos a "
            f"mano es lo que dejo la constante apuntando a un fichero retirado."
        )
    export = parse_export(ruta.read_text(encoding="utf-8"), source=filename)
    return tuple((puesto, fila.score) for puesto, fila in enumerate(export.rows, 1))


#: Direccion de cada escala CON su evidencia. Perder esto es leer el ranking al reves y
#: llevarse a sintesis justo las peores.
EVIDENCE = {
    ScoreSource.MANUAL_MIRARCHITECT: ScoreEvidence(
        lower_is_better=True,
        evidence_file=MANUAL_EVIDENCE_FILE,
        note=(
            "Corrida de miRarchitect sobre el 3'UTR VERIFICADO de Prnp murino (1242 nt, "
            "md5 canónico 19f5fa2a). Los pares se LEEN de "
            f"{MANUAL_EVIDENCE_FILE}: el fichero NO trae columna de rank, así que el "
            "puesto es el del ORDEN DE SUS FILAS, estrictamente creciente en el score "
            "a lo largo de las 24.\n"
            "OJO CON EL ALCANCE DE ESA PRUEBA: que 24 filas salgan ordenadas demuestra "
            "que el fichero ESTÁ ordenado, no en que dirección. Que la primera fila sea "
            "la MEJOR sigue siendo un SUPUESTO sobre el convenio de la fuente. Se "
            "confirma leyendo el puesto que muestra la propia interfaz de miRarchitect "
            "en el re-export; hasta entonces, esto es una hipotesis de trabajo con la "
            "que se ha decidido operar, no un hecho comprobado.\n"
            "CORREGIDO 2026-08-27: los pares iban transcritos a mano y salían de "
            "mirarchitect_prnp_raton.tsv, que el manifiesto marca «NO USAR» — se "
            "puntuó sobre el 3'UTR fabricado de 1246 nt (errata nº 5). La DIRECCIÓN no "
            "se mueve —los tres ficheros vienen crecientes— pero la evidencia estaba "
            "anclada a una corrida retirada."
        ),
    ),
    ScoreSource.MIRARCHITECT_API: ScoreEvidence(
        lower_is_better=True,
        evidence_file=None,
        note=(
            "Se hereda de la corrida manual: es el mismo servicio. Sin endpoint "
            "verificado no hay evidencia propia."
        ),
    ),
}


def lower_is_better(source: ScoreSource) -> bool:
    """¿Menor es mejor en esta escala? Se aborta antes que suponerlo."""
    if source not in EVIDENCE:
        raise ShmirDesignError(
            f"No está registrado si la escala de {source.value} es de menor-es-mejor o "
            f"de mayor-es-mejor. Se aborta: ordenar por un score cuya dirección no se "
            f"conoce llevaria a síntesis justo los peores candidatos."
        )
    return EVIDENCE[source].lower_is_better


def file_order_direction(scores: list[tuple[str, float]]) -> bool:
    """Deriva la direccion del ORDEN DE LAS FILAS del fichero, o aborta.

    No hay ninguna columna que declare si menor es mejor. Lo que si se puede comprobar
    es que las filas vengan ordenadas por score: si lo estan, el fichero viene en el
    orden de ranking de la fuente y ese orden fija la direccion. Si no lo estan, el
    orden de las filas no es un ranking y sacar un puesto de el seria inventarselo.
    """
    valores = [s for _, s in scores]
    if len(valores) < 2:
        raise ShmirDesignError(
            "Con una sola fila no se puede derivar la dirección de la escala del orden "
            "del fichero. Se aborta en vez de suponerla."
        )
    sube = all(a <= b for a, b in zip(valores, valores[1:]))
    baja = all(a >= b for a, b in zip(valores, valores[1:]))
    if not sube and not baja:
        raise ShmirDesignError(
            "El orden de las filas del fichero no es monótono en el score, así que no "
            "es un ranking: no se puede derivar de el ni la dirección de la escala ni "
            "el puesto de cada guía. Se aborta en vez de ordenar a ciegas."
        )
    if sube and baja:
        raise ShmirDesignError(
            "Todos los scores del fichero son iguales: el orden de las filas no dice "
            "nada sobre la dirección de la escala. Se aborta."
        )
    return sube


def _same_scaffold(a: str, b: str) -> bool:
    """¿Son el mismo andamio? `miR-E` y `miR-E / SGEP` lo son; `miR-30a` no.

    Se comparan los tokens, no la cadena: el nombre del andamio del proyecto lleva
    ademas el del plasmido. Un nombre que no sea un subconjunto del otro es OTRO
    andamio, y ahi no se acerca nada por parecido.
    """
    import re  # noqa: PLC0415

    def tokens(x: str) -> set[str]:
        return {t for t in re.split(r"[^0-9a-z]+", x.lower()) if t}

    ta, tb = tokens(a), tokens(b)
    return bool(ta) and bool(tb) and (ta <= tb or tb <= ta)


def check_orderable(
    source: ScoreSource,
    *,
    derived_lower_is_better: bool,
    file_scaffold: str | None,
    design_scaffold: str,
) -> None:
    """¿Se puede ORDENAR candidatos por este score? Aborta si no, diciendo por que.

    Dos motivos para que no:

    - La direccion derivada del fichero no coincide con la registrada. Uno de los dos
      esta mal y no se elige por nuestra cuenta.
    - El andamio del fichero no es el del diseño. Un score de PROCESAMIENTO medido
      sobre miR-30a no ordena candidatos de miR-E: miR-E existe precisamente porque
      procesa distinto (Fellmann 2013), asi que el sesgo cae justo sobre lo que el
      score dice medir. El numero sigue sirviendo como convergencia de sitio —dos
      metodos independientes señalan la misma region— pero no para ordenar.
    """
    registrada = lower_is_better(source)
    if registrada != derived_lower_is_better:
        raise ShmirDesignError(
            f"La dirección de la escala derivada del fichero "
            f"({'menor' if derived_lower_is_better else 'mayor'} es mejor) no coincide "
            f"con la registrada para {source.value} "
            f"({'menor' if registrada else 'mayor'} es mejor). Uno de los dos está mal; "
            f"se aborta en vez de elegir por nuestra cuenta."
        )
    if file_scaffold is None:
        raise ShmirDesignError(
            f"No se ha declarado con que andamio se puntuo el fichero. Se aborta en vez "
            f"de suponer que es el del diseño ({design_scaffold}): un score de "
            f"procesamiento medido sobre otro andamio no ordena estos candidatos."
        )
    if not _same_scaffold(file_scaffold, design_scaffold):
        raise ShmirDesignError(
            f"El fichero se puntuo con el andamio {file_scaffold} y el diseño usa "
            f"{design_scaffold}. Este score es de PROCESAMIENTO, y {design_scaffold} "
            f"existe porque procesa distinto de {file_scaffold} (Fellmann 2013): el "
            f"sesgo cae justo sobre lo que el score dice medir. Vale como convergencia "
            f"de sitio, NO para ordenar."
        )


@dataclass(frozen=True)
class ExternalScore:
    """Un score ajeno con su procedencia, o nada en absoluto."""

    value: float | None = None
    source: ScoreSource | None = None
    #: Se pega detras de la fuente en `fuente_score`. Aqui viaja el offset de
    #: coordenadas: un score cruzado con +949 y otro sin cruzar NO son el mismo dato.
    annotation: str = ""

    def __post_init__(self) -> None:
        if (self.value is None) != (self.source is None):
            raise ShmirDesignError(
                f"Un score externo se declara entero o no se declara: llego "
                f"value={self.value!r} con source={self.source!r}. Un número sin "
                f"procedencia no es auditable y una procedencia sin número no dice "
                f"nada; se aborta en vez de escribir media columna."
            )

    def as_columns(self) -> dict[str, str]:
        """Vacio significa 'nadie lo ha puntuado', nunca cero (regla 3)."""
        if self.value is None:
            return {"score_externo": "", "fuente_score": ""}
        return {
            "score_externo": f"{self.value:.3f}",
            "fuente_score": f"{self.source.value}{self.annotation}",
        }


#: Una columna por feature, en el orden en que se emiten. Separadas a proposito: el
#: paper de SplashRNA las combina con un modelo entrenado, y entrenar aqui uno propio
#: —o copiar unos pesos de memoria— seria inventarse el resultado.
FEATURE_COLUMNS = (
    "feat_asimetria",
    "feat_GC_guia",
    "feat_pos1",
    "feat_pos2",
    "feat_pos3",
    "feat_pos4",
    "feat_pos5",
    "feat_pos6",
    "feat_pos7",
    "feat_seed",
    "feat_GC_seed",
    "feat_AU_seed",
    "feat_GC_bucle",
)

#: Hasta que posicion hacen falta bases sueltas. Con la seed (2-8) marca el minimo.
_POSICIONES = range(1, 8)


def splashrna_features(
    guide: str, *, scaffold: ScaffoldSpec = SGEP_SCAFFOLD
) -> dict[str, str]:
    """Las features del paper de SplashRNA, cada una en su columna y sin combinar.

    Son las que ya calcula el pipeline (asimetria, GC, posicion 1) mas las que añade
    SplashRNA: las bases de las posiciones 2-7, la composicion de la seed y el GC del
    bucle. Con el andamio miR-E fijo el GC del bucle es el mismo para todos los
    candidatos: es un hecho del diseño, no un descuido, y cambia si cambia el andamio.
    """
    limpia = "".join(guide.split()).upper().replace("T", "U")
    if len(limpia) < SEED_END:
        raise ShmirDesignError(
            f"La guía mide {len(limpia)} nt y las features de SplashRNA llegan hasta la "
            f"posicion {SEED_END}; se abortan las features en vez de rellenar las "
            f"posiciones que faltan o dejarlas a cero."
        )
    desconocidas = set(limpia) - set("ACGU")
    if desconocidas:
        raise ShmirDesignError(
            f"La guía trae {sorted(desconocidas)}, que no son bases: no se calculan "
            f"features sobre una secuencia que no se ha podido leer."
        )
    seed = limpia[SEED_START - 1 : SEED_END]
    gc_seed = gc_fraction(seed)
    features = {
        "feat_asimetria": f"{turner_asymmetry(limpia):+.2f}",
        "feat_GC_guia": f"{gc_fraction(limpia):.3f}",
        **{f"feat_pos{i}": limpia[i - 1] for i in _POSICIONES},
        "feat_seed": seed,
        "feat_GC_seed": f"{gc_seed:.3f}",
        "feat_AU_seed": f"{1 - gc_seed:.3f}",
        "feat_GC_bucle": f"{gc_fraction(scaffold.loop):.3f}",
    }
    return {columna: features[columna] for columna in FEATURE_COLUMNS}


IMPORT_COMMAND = (
    "python3 tools/import_scores.py --fuente mirarchitect --tsv resultados.tsv "
    "--comparativa <especie>_comparativa.tsv"
)


def manual_instructions(guides: list[str] | tuple[str, ...]) -> str:
    """Como puntuar estas guias a mano y como meter los numeros en la tabla.

    Se imprime SIEMPRE que no haya API, que es hoy. No sustituye a un score: la columna
    sigue vacia hasta que alguien la rellene con esto.
    """
    lineas = [
        f"  No hay ninguna API de score externo verificada, así que la columna "
        f"`score_externo`",
        "  de la tabla comparativa va VACÍA, igual que `knockdown_medido`. No se ha "
        "puesto",
        "  ningún número calculado aquí: eso sería un score propio con etiqueta ajena.",
        "",
        f"  Se comprobo el {VERIFICACION} y **no se ha podido comprobar** si "
        f"miRarchitect y",
        "  SplashRNA tienen API: las cuatro direcciones dieron 403 en el proxy de este",
        "  entorno, que es una denegacion de politica de red y no una respuesta del "
        "servicio.",
        "  Puede que existan; desde aquí no se sabe, así que no se cablea ninguna URL.",
        "",
        "  Los dos servicios (direcciones dadas por el responsable del proyecto, no",
        "  verificadas desde aquí):",
        *(f"    · {h.name:<13} {h.url}\n      {h.what}; pegar {h.paste}"
          for h in EXTERNAL_TOOLS),
        "",
        "  Para puntuarlas a mano:",
        f"    1. Abre {MANUAL_URL}.",
        f"    2. Pega la guía de 22 nt y elige el andamio {MANUAL_SCAFFOLD}.",
        "    3. Copia del resultado el score y su escala (el rango posible), una línea",
        "       por guía, en un TSV de dos columnas: `guia<TAB>score`.",
        "    4. Importalo:",
        f"         {IMPORT_COMMAND}",
        "       La columna `fuente_score` quedara en `manual_mirarchitect`.",
        "",
        "  El score es INFORMATIVO: no es un filtro, no da PASS y no da FAIL. Ningún",
        "  candidato se descarta ni se aprueba por el.",
    ]
    if guides:
        # Sin repetir y en el orden en que llegaron: dos candidatos pueden compartir
        # guia en un 3'UTR con repeticiones, y pegar la misma dos veces es tiempo de
        # alguien. No se ordenan: el orden es el de la seleccion.
        unicas = list(dict.fromkeys(g.upper().replace("U", "T") for g in guides))
        lineas.extend(["", "  Guías que hay que pegar (en ADN, como las pide el "
                       "formulario):"])
        lineas.extend(f"    {guia}" for guia in unicas)
    return "\n".join(lineas)


@dataclass(frozen=True)
class GuideMatch:
    """Que guia de la fuente externa le toca a un candidato nuestro, y a que distancia."""

    ours: str
    theirs: str
    score: float
    rank: int
    shift: int

    @property
    def displaced(self) -> bool:
        return abs(self.shift) > DISPLACED_SHIFT

    def flags(self, *, lower_better: bool) -> dict[str, str]:
        """Las tres banderas. Ninguna es un veredicto: no dan PASS ni FAIL."""
        buena = self.score < CONFIRMED_BELOW if lower_better else self.score > CONFIRMED_BELOW
        if self.displaced:
            estado = "ventana_desplazada"
        else:
            estado = "si" if buena else "no"
        return {
            "mirarch_confirmado": estado,
            "mirarch_rank": str(self.rank),
            "mirarch_shift_nt": str(self.shift),
        }


#: Lo que se escribe cuando la fuente externa no encontro nada para ese candidato. El
#: rank y la distancia van VACIOS, no a cero: no haber aparecido y aparecer el primero
#: a distancia cero son cosas opuestas (regla 3).
SIN_MATCH = {"mirarch_confirmado": "no", "mirarch_rank": "", "mirarch_shift_nt": ""}


@dataclass(frozen=True)
class MergeResult:
    """La tabla con los scores dentro, y que filas se quedaron sin uno."""

    text: str
    filled: tuple[str, ...]
    untouched: tuple[str, ...]
    source: ScoreSource
    matches: tuple[GuideMatch, ...] = ()
    #: Guias de la fuente que no corresponden a ningun candidato nuestro. Con un barrido
    #: de todo el 3'UTR esto es lo NORMAL, no un fallo.
    unmatched: tuple[str, ...] = ()
    offset: int | None = None
    #: ¿Se puede ORDENAR candidatos por este score? Falso cuando el andamio del fichero
    #: no es el del diseño: el numero vale como convergencia de sitio, no como ranking.
    orderable: bool = True
    not_orderable_reason: str = ""

    def format_text(self) -> str:
        total = len(self.filled) + len(self.untouched)
        direccion = "menor es mejor" if lower_is_better(self.source) else "mayor es mejor"
        lineas = [
            f"Scores importados: {len(self.filled)} de {total} candidato(s), "
            f"fuente {self.source.value}.",
            f"ESCALA: {direccion}. No la inviertas al ordenar.",
        ]
        if not self.orderable:
            lineas.append("NO ORDENAR POR ESTA COLUMNA. " + self.not_orderable_reason)
            lineas.append(
                "El número se queda como CONVERGENCIA DE SITIO: dice que otro metodo "
                "señaló la misma región, no que un candidato sea mejor que otro."
            )
        if self.offset is not None:
            lineas.append(
                f"Las coordenadas de la fuente van con offset {self.offset:+d} respecto "
                f"de las del transcrito; queda escrito en fuente_score."
            )
        for m in sorted(self.matches, key=lambda x: x.rank):
            marca = f" — VENTANA DESPLAZADA {m.shift:+d} nt" if m.displaced else (
                "" if m.shift == 0 else f" — corrida {m.shift:+d} nt"
            )
            lineas.append(
                f"  · {m.ours}  score {m.score:.2f}  rank {m.rank}{marca}"
            )
        if self.untouched:
            lineas.append(
                f"Siguen sin score {len(self.untouched)}: su columna se queda VACÍA, "
                f"no a cero."
            )
            lineas.extend(f"  · {guia}" for guia in self.untouched)
        if self.unmatched:
            lineas.append(
                f"{len(self.unmatched)} guía(s) de la fuente no corresponden a ningún "
                f"candidato nuestro. Con un barrido de todo el 3'UTR eso es lo normal."
            )
        lineas.append(
            "El score es informativo: no cambia ningún veredicto ni descarta a nadie."
        )
        return "\n".join(lineas)


def _rna(guide: str) -> str:
    return "".join(guide.split()).upper().replace("T", "U")


def _parse_results(results: str, *, source_name: str) -> list[tuple[str, float]]:
    """`guia<TAB>score`, en el orden del fichero. Se aborta ante cualquier rareza."""
    scores: list[tuple[str, float]] = []
    vistas: set[str] = set()
    for numero, cruda in enumerate(results.splitlines(), start=1):
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        campos = linea.split("\t")
        if len(campos) < 2:
            raise ShmirDesignError(
                f"{source_name}, línea {numero}: se esperaban dos columnas "
                f"`guia<TAB>score` y llego {linea!r}. Se aborta la importacion entera "
                f"en vez de dejar la tabla a medias."
            )
        crudo, bruto = "".join(campos[0].split()).upper(), campos[1].strip()
        if crudo in ("GUIA", "GUIDE", "GUIA_DNA", "GUIDE_DNA"):
            continue
        guia = crudo.replace("U", "T")
        try:
            valor = float(bruto)
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source_name}, línea {numero}: el score {bruto!r} de {guia} no es un "
                f"número. Se aborta: un score que no se ha podido leer no se convierte "
                f"en un hueco silencioso."
            ) from exc
        if guia in vistas:
            raise ShmirDesignError(
                f"{source_name}, línea {numero}: la guía {guia} aparece dos veces. "
                f"Se aborta en vez de elegir uno."
            )
        vistas.add(guia)
        scores.append((guia, valor))
    if not scores:
        raise ShmirDesignError(
            f"{source_name} no trae ningún score legible. Se aborta: importar nada y "
            f"decir que fue bien dejaria creer que la tabla lleva scores."
        )
    return scores


def _ranked(scores: list[tuple[str, float]], *, lower_better: bool) -> dict[str, int]:
    """Puesto de cada guia, 1 = mejor. La direccion de la escala manda."""
    orden = sorted(scores, key=lambda par: par[1], reverse=not lower_better)
    return {guia: puesto for puesto, (guia, _) in enumerate(orden, start=1)}


def _best_match(
    ours: str, scores: list[tuple[str, float]], ranks: dict[str, int]
) -> GuideMatch | None:
    """La ventana de la fuente mas cercana a la nuestra, o `None` si ninguna lo esta."""
    mejor: GuideMatch | None = None
    for guia, valor in scores:
        desplazamiento = guide_shift(ours, guia)
        if desplazamiento is None:
            continue
        if mejor is None or abs(desplazamiento) < abs(mejor.shift):
            mejor = GuideMatch(
                ours=ours, theirs=guia, score=valor,
                rank=ranks[guia], shift=desplazamiento,
            )
    return mejor


def merge_scores(
    table: str,
    results: str,
    *,
    source: ScoreSource,
    source_name: str = "el TSV de scores",
    offset: int | None = None,
    file_scaffold: str | None = None,
    design_scaffold: str = "",
) -> MergeResult:
    """Cruza los scores de una fuente externa con la tabla comparativa, POR SECUENCIA.

    No por coordenada: los convenios de numeracion no coinciden y un score en la fila
    del candidato de al lado es peor que no tener score. `offset` no se usa para cruzar
    —solo se anota en `fuente_score`— precisamente por eso.

    Una ventana corrida hasta `MAX_SHIFT` nt se asigna al candidato mas cercano y la
    distancia queda escrita. Mas alla, no se asigna: la columna se queda vacia.
    """
    scores = _parse_results(results, source_name=source_name)
    # La direccion NO se supone: se deriva del orden de las filas y se contrasta con la
    # registrada. Si el fichero no viene ordenado, `file_order_direction` aborta.
    derivada = file_order_direction(scores)
    lower_better = lower_is_better(source)
    ordenable, motivo = True, ""
    try:
        check_orderable(
            source,
            derived_lower_is_better=derivada,
            file_scaffold=file_scaffold,
            design_scaffold=design_scaffold,
        )
    except ShmirDesignError as exc:
        # rule2-ok: no es un fallo del proceso, es un VEREDICTO sobre el dato. No se
        # traga: se propaga entero a la salida y a la columna `fuente_score`, y el
        # resumen empieza diciendo NO ORDENAR.
        if "direccion" in str(exc).lower():
            raise
        ordenable, motivo = False, str(exc)
    # El puesto sale del ORDEN DEL FICHERO, que es el de la fuente. Reordenarlo por
    # nuestra cuenta seria fabricar un ranking que la fuente no dio.
    ranks = {guia: puesto for puesto, (guia, _) in enumerate(scores, start=1)}
    anotacion = "" if offset is None else f"_offset{offset:+d}"
    if not ordenable:
        # Viaja en CADA fila: quien abra el TSV dentro de un año tiene que verlo sin
        # leer ningun informe.
        anotacion += f"_andamio_{file_scaffold or 'SIN_DECLARAR'}_NO_ORDENAR"

    lineas = table.splitlines()
    comentarios = [l for l in lineas if l.startswith("#")]
    cuerpo = [l for l in lineas if l.strip() and not l.startswith("#")]
    if not cuerpo:
        raise ShmirDesignError(
            "La tabla comparativa no tiene ninguna fila; no hay donde meter los scores."
        )
    cabecera = cuerpo[0].split("\t")
    faltan = [
        c for c in ("guia", *SCORE_COLUMNS, *MIRARCH_COLUMNS) if c not in cabecera
    ]
    if faltan:
        raise ShmirDesignError(
            f"A la tabla comparativa le faltan las columnas {faltan}: es de una versión "
            f"anterior al cruce con miRarchitect. Relanza el diseño y vuelve a "
            f"importar; no se escribe una tabla a medias."
        )
    indices = {nombre: cabecera.index(nombre) for nombre in cabecera}

    salida = [cuerpo[0]]
    rellenas: list[str] = []
    intactas: list[str] = []
    encontrados: list[GuideMatch] = []
    usadas: set[str] = set()
    for fila_cruda in cuerpo[1:]:
        campos = fila_cruda.split("\t")
        guia = _rna(campos[indices["guia"]]).replace("U", "T")
        emparejada = _best_match(guia, scores, ranks)
        if emparejada is None:
            columnas = {**ExternalScore().as_columns(), **SIN_MATCH}
            intactas.append(campos[indices["guia"]])
        else:
            columnas = {
                **ExternalScore(
                    emparejada.score, source, annotation=anotacion
                ).as_columns(),
                **emparejada.flags(lower_better=lower_better),
            }
            encontrados.append(emparejada)
            usadas.add(emparejada.theirs)
            rellenas.append(campos[indices["guia"]])
        for nombre, valor in columnas.items():
            campos[indices[nombre]] = valor
        salida.append("\t".join(campos))

    if not rellenas:
        raise ShmirDesignError(
            f"Ninguna de las {len(cuerpo) - 1} guías de la tabla aparece en "
            f"{source_name}, ni siquiera con la ventana corrida. Los dos ficheros no "
            f"son de la misma corrida; se aborta en vez de escribir una tabla vacía."
        )

    return MergeResult(
        text="\n".join([*comentarios, *salida]) + "\n",
        filled=tuple(rellenas),
        untouched=tuple(intactas),
        source=source,
        matches=tuple(encontrados),
        orderable=ordenable,
        not_orderable_reason=motivo,
        unmatched=tuple(g for g, _ in scores if g not in usadas),
        offset=offset,
    )
