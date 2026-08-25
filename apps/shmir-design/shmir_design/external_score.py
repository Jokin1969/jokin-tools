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

#: La direccion que el informe le da a una PERSONA para que la abra a mano. No la llama
#: ningun codigo. Es la que aparece en el preprint de febrero de 2026 segun quien pidio
#: esta columna; desde este entorno no se ha podido comprobar que responda.
MANUAL_URL = "https://mirarchitect.org"

#: El andamio que hay que seleccionar en el formulario. Es el del proyecto.
MANUAL_SCAFFOLD = "miR-E"

#: Las dos columnas que viajan en la tabla comparativa, al lado de `knockdown_medido`.
SCORE_COLUMNS = ("score_externo", "fuente_score")


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


@dataclass(frozen=True)
class ExternalScore:
    """Un score ajeno con su procedencia, o nada en absoluto."""

    value: float | None = None
    source: ScoreSource | None = None

    def __post_init__(self) -> None:
        if (self.value is None) != (self.source is None):
            raise ShmirDesignError(
                f"Un score externo se declara entero o no se declara: llego "
                f"value={self.value!r} con source={self.source!r}. Un numero sin "
                f"procedencia no es auditable y una procedencia sin numero no dice "
                f"nada; se aborta en vez de escribir media columna."
            )

    def as_columns(self) -> dict[str, str]:
        """Vacio significa 'nadie lo ha puntuado', nunca cero (regla 3)."""
        if self.value is None:
            return {"score_externo": "", "fuente_score": ""}
        return {
            "score_externo": f"{self.value:.3f}",
            "fuente_score": str(self.source.value),
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
            f"La guia mide {len(limpia)} nt y las features de SplashRNA llegan hasta la "
            f"posicion {SEED_END}; se abortan las features en vez de rellenar las "
            f"posiciones que faltan o dejarlas a cero."
        )
    desconocidas = set(limpia) - set("ACGU")
    if desconocidas:
        raise ShmirDesignError(
            f"La guia trae {sorted(desconocidas)}, que no son bases: no se calculan "
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
        f"  No hay ninguna API de score externo verificada, asi que la columna "
        f"`score_externo`",
        "  de la tabla comparativa va VACIA, igual que `knockdown_medido`. No se ha "
        "puesto",
        "  ningun numero calculado aqui: eso seria un score propio con etiqueta ajena.",
        "",
        f"  Se comprobo el {VERIFICACION} y **no se ha podido comprobar** si "
        f"miRarchitect y",
        "  SplashRNA tienen API: las cuatro direcciones dieron 403 en el proxy de este",
        "  entorno, que es una denegacion de politica de red y no una respuesta del "
        "servicio.",
        "  Puede que existan; desde aqui no se sabe, asi que no se cablea ninguna URL.",
        "",
        "  Para puntuarlas a mano:",
        f"    1. Abre {MANUAL_URL} (direccion del preprint, no verificada desde aqui).",
        f"    2. Pega la guia de 22 nt y elige el andamio {MANUAL_SCAFFOLD}.",
        "    3. Copia del resultado el score y su escala (el rango posible), una linea",
        "       por guia, en un TSV de dos columnas: `guia<TAB>score`.",
        "    4. Importalo:",
        f"         {IMPORT_COMMAND}",
        "       La columna `fuente_score` quedara en `manual_mirarchitect`.",
        "",
        "  El score es INFORMATIVO: no es un filtro, no da PASS y no da FAIL. Ningun",
        "  candidato se descarta ni se aprueba por el.",
    ]
    if guides:
        # Sin repetir y en el orden en que llegaron: dos candidatos pueden compartir
        # guia en un 3'UTR con repeticiones, y pegar la misma dos veces es tiempo de
        # alguien. No se ordenan: el orden es el de la seleccion.
        unicas = list(dict.fromkeys(g.upper().replace("U", "T") for g in guides))
        lineas.extend(["", "  Guias que hay que pegar (en ADN, como las pide el "
                       "formulario):"])
        lineas.extend(f"    {guia}" for guia in unicas)
    return "\n".join(lineas)


@dataclass(frozen=True)
class MergeResult:
    """La tabla con los scores dentro, y que filas se quedaron sin uno."""

    text: str
    filled: tuple[str, ...]
    untouched: tuple[str, ...]
    source: ScoreSource

    def format_text(self) -> str:
        total = len(self.filled) + len(self.untouched)
        lineas = [
            f"Scores importados: {len(self.filled)} de {total} candidato(s), "
            f"fuente {self.source.value}."
        ]
        if self.untouched:
            lineas.append(
                f"Siguen sin score {len(self.untouched)}: su columna se queda VACIA, "
                f"no a cero."
            )
            lineas.extend(f"  · {guia}" for guia in self.untouched)
        lineas.append(
            "El score es informativo: no cambia ningun veredicto ni descarta a nadie."
        )
        return "\n".join(lineas)


def _rna(guide: str) -> str:
    return "".join(guide.split()).upper().replace("T", "U")


def _parse_results(results: str, *, source_name: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for numero, cruda in enumerate(results.splitlines(), start=1):
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        campos = linea.split("\t")
        if len(campos) < 2:
            raise ShmirDesignError(
                f"{source_name}, linea {numero}: se esperaban dos columnas "
                f"`guia<TAB>score` y llego {linea!r}. Se aborta la importacion entera "
                f"en vez de dejar la tabla a medias."
            )
        guia, bruto = _rna(campos[0]), campos[1].strip()
        if guia in ("GUIA", "GUIDE"):
            continue
        try:
            valor = float(bruto)
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source_name}, linea {numero}: el score {bruto!r} de {guia} no es un "
                f"numero. Se aborta: un score que no se ha podido leer no se convierte "
                f"en un hueco silencioso."
            ) from exc
        if guia in scores:
            raise ShmirDesignError(
                f"{source_name}, linea {numero}: la guia {guia} aparece dos veces "
                f"({scores[guia]} y {valor}). Se aborta en vez de elegir uno."
            )
        scores[guia] = valor
    if not scores:
        raise ShmirDesignError(
            f"{source_name} no trae ningun score legible. Se aborta: importar nada y "
            f"decir que fue bien dejaria creer que la tabla lleva scores."
        )
    return scores


def merge_scores(
    table: str, results: str, *, source: ScoreSource, source_name: str = "el TSV de scores"
) -> MergeResult:
    """Mete los scores puntuados fuera en la tabla comparativa, por guia.

    Aborta ante cualquier cosa que huela a fichero equivocado —una guia que no esta en
    la tabla, un score ilegible, una guia repetida— porque un score en la fila de otro
    candidato es peor que no tener score.
    """
    scores = _parse_results(results, source_name=source_name)

    lineas = table.splitlines()
    comentarios = [l for l in lineas if l.startswith("#")]
    cuerpo = [l for l in lineas if l.strip() and not l.startswith("#")]
    if not cuerpo:
        raise ShmirDesignError(
            "La tabla comparativa no tiene ninguna fila; no hay donde meter los scores."
        )
    cabecera = cuerpo[0].split("\t")
    faltan = [c for c in ("guia", *SCORE_COLUMNS) if c not in cabecera]
    if faltan:
        raise ShmirDesignError(
            f"A la tabla comparativa le faltan las columnas {faltan}: no es una tabla "
            f"de shmir-design, o es de una version anterior a la columna "
            f"`score_externo`. Se aborta sin escribir nada."
        )
    i_guia = cabecera.index("guia")
    i_score = cabecera.index("score_externo")
    i_fuente = cabecera.index("fuente_score")

    salida = [cuerpo[0]]
    rellenas: list[str] = []
    intactas: list[str] = []
    presentes: set[str] = set()
    for fila_cruda in cuerpo[1:]:
        campos = fila_cruda.split("\t")
        guia = _rna(campos[i_guia])
        presentes.add(guia)
        if guia in scores:
            columnas = ExternalScore(scores[guia], source).as_columns()
            campos[i_score] = columnas["score_externo"]
            campos[i_fuente] = columnas["fuente_score"]
            rellenas.append(campos[i_guia])
        else:
            intactas.append(campos[i_guia])
        salida.append("\t".join(campos))

    sobran = sorted(set(scores) - presentes)
    if sobran:
        raise ShmirDesignError(
            f"{source_name} trae scores de guias que no estan en la tabla "
            f"comparativa: {', '.join(sobran)}. Eso significa que los dos ficheros no "
            f"son de la misma corrida; se aborta en vez de pegar numeros a ciegas."
        )

    return MergeResult(
        text="\n".join([*comentarios, *salida]) + "\n",
        filled=tuple(rellenas),
        untouched=tuple(intactas),
        source=source,
    )
