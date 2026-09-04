"""El CUARTO modal: prediccion de sitios de splicing sobre el cassette montado.

## En que se diferencia de los otros tres

**La unidad de analisis NO es el candidato.** Los otros tres preguntan sobre una guia de
22 nt; este pregunta sobre el **cassette montado**: intron completo, con su modulo dentro,
con la guia y la pasajera de ESE candidato, y con contexto exonico a los dos lados. Diez
candidatos y tres intrones son **treinta consultas**, no una lista de diez.

## SpliceAI NO fue entrenado para esto, y eso manda sobre todo lo demas

Se entreno sobre secuencia **genomica humana** con ventana de **10.000 nt** para predecir
el **efecto de variantes**. Un cassette de AAV no se le parece: no hay contexto genomico,
las longitudes son atipicas y la composicion tambien. Consecuencias, y van ANTES del
boton, no al pie:

  - las puntuaciones **absolutas no son interpretables**. No hay umbral que aplicar;
  - solo vale la comparacion **relativa** contra un referente **interno**: el donante
    legitimo del mismo intron, en la misma corrida. Es el mismo criterio que ya se uso
    para descartar los 13 aceptores cripticos comparandolos contra el tracto de 9
    pirimidinas del legitimo;
  - un modulo cuyo mejor criptico se **acerque** al legitimo es sospechoso; uno donde el
    legitimo **domine**, no. **Nada de esto es un veredicto.**

## Y sobre la orden: no se inventa

Este proyecto no ha verificado la invocacion de SpliceAI (regla 4 generalizada: si no lo
has comprobado, no lo escribas — pregunta). Asi que `LocalCommand` **recibe** la orden y
aborta sin ella, igual que `blast.RemoteApi` con su endpoint. Lo que si define este modulo
es el **formato del resultado que acepta**, que es nuestro.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .blocks import PIECES, build_block
from .errors import ShmirDesignError
from .filters import FilterState
from .introns import get as get_intron
from .introns import locate_elements
from .splicing import CRYPTIC_DONOR

# ─────────────────────────── lo que se dice ANTES del boton ───────────────────────────

NOT_TRAINED_FOR_THIS = (
    "SpliceAI NO fue entrenado para esto. Se entreno sobre secuencia GENOMICA HUMANA con "
    "una ventana de 10.000 nt, para predecir el efecto de VARIANTES. Un cassette de AAV "
    "no se le parece: no hay contexto genomico, las longitudes son atipicas y la "
    "composición también. Lo que devuelve aquí no es «lo mismo peor»: es un número "
    "calculado sobre una entrada de otra clase."
)

NO_ABSOLUTE_THRESHOLD = (
    "LAS PUNTUACIONES ABSOLUTAS NO SON INTERPRETABLES, y no hay ningún umbral que "
    "aplicar. Un 0,8 aquí no significa lo que significa un 0,8 en el genoma humano, y no "
    "existe un valor por encima del cual algo sea «un sitio». Cualquier corte que se "
    "pusiera sería inventado."
)

RELATIVE_ONLY = (
    "Lo único que vale es la comparación RELATIVA contra un referente INTERNO: el donante "
    "legítimo del mismo intrón, en la misma corrida. Es el mismo criterio que ya se uso "
    "para descartar los aceptores crípticos —el tracto de pirimidinas de cada uno "
    "comparado contra las nueve del legítimo— y funciona por la misma razón: el veredicto "
    "no depende de ningún umbral traido de fuera. Un módulo cuyo mejor críptico se ACERQUE "
    "al legítimo es sospechoso; uno donde el legítimo DOMINE, no."
)

CONTEXT_MATTERS = (
    "LA VENTANA DE CONTEXTO CAMBIA EL RESULTADO, así que va declarada y viaja con cada "
    "consulta. SpliceAI mira miles de nucleótidos a cada lado; aquí hay lo que da el "
    "casete. Dos corridas con contextos distintos no son comparables, y sin registrarlo "
    "nadie podría saberlo."
)

USE_NOTE = (
    "USO: DESEMPATE Y ALERTA, NUNCA FILTRO. Ni esto ni la accesibilidad estructural "
    "pueden excluir un candidato — NO ES UN VEREDICTO. Lo que pueden hacer es señalar que "
    "una construcción concreta tiene un perfil peor que sus hermanas, y eso es motivo "
    "para preferir otra o para llevar las dos."
)

WHAT_IS_ACTIONABLE = (
    "LO ACCIONABLE es que guías introducen crípticos que las otras NO. Si nueve dan un "
    "perfil limpio y una no, esa una se CAMBIA. Es una comparación ENTRE CONSTRUCCIONES, "
    "no contra un umbral absoluto — que es justo lo que aquí no se puede usar."
)

#: Umbral RELATIVO por debajo del cual un sitio no se lista. DECLARADO como parametro de
#: este analisis, NO citado: no sale de ninguna publicacion. Existe para que la tabla no
#: se llene de ruido, no para decidir nada.
RELATIVE_THRESHOLD = 0.05

RELATIVE_THRESHOLD_NOTE = (
    f"Solo se listan los sitios cuya puntuación llega al {RELATIVE_THRESHOLD:.0%} de la "
    f"del donante legítimo. Es un umbral RELATIVO y va DECLARADO como parámetro de este "
    f"análisis, no citado: no sale de ninguna publicacion y no decide nada — solo evita "
    f"que la tabla se llene de ruido. El absoluto sigue sin existir."
)


def warning_blocks() -> list[dict[str, object]]:
    """Los avisos que van ANTES del boton. Todos activos: ninguno es opcional."""
    return [
        {"clave": "entrenamiento", "texto": NOT_TRAINED_FOR_THIS, "activo": True},
        {"clave": "sin_umbral", "texto": NO_ABSOLUTE_THRESHOLD, "activo": True},
        {"clave": "relativo", "texto": RELATIVE_ONLY, "activo": True},
        {"clave": "contexto", "texto": CONTEXT_MATTERS, "activo": True},
        {"clave": "uso", "texto": USE_NOTE, "activo": True},
    ]


# ─────────────────────────── la construccion: candidato x intron ───────────────────────


def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode("ascii"), usedforsecurity=False).hexdigest()


@dataclass(frozen=True)
class Construction:
    """UN par candidato x intron, montado y listo para consultar."""

    name: str
    candidate_start: int
    intron: str
    sequence: str
    md5: str
    #: Contexto exonico a cada lado, en nt. DECLARADO: cambia el resultado.
    context_5: int
    context_3: int
    #: Posiciones 1-based DENTRO de la construccion.
    donor_position: int
    acceptor_position: int
    #: El donante criptico conocido del andamio, si esta.
    cryptic_position: int
    #: `True` si el andamio de esta construccion NO es el miR-E verificado.
    scaffold_modified: bool = False

    @property
    def intron_offset(self) -> int:
        """Donde empieza el intron dentro de la construccion (1-based)."""
        return self.context_5 + 1

    def describe(self) -> str:
        lineas = [
            f"{self.name}  ({len(self.sequence)} nt, md5 {self.md5})",
            f"  candidato 3utr:{self.candidate_start} x intrón {self.intron}",
            f"  contexto exonico declarado: {self.context_5} nt por el 5' y "
            f"{self.context_3} nt por el 3'",
            f"  donante legítimo en construcción:{self.donor_position}, "
            f"aceptor en construcción:{self.acceptor_position}",
        ]
        if self.cryptic_position:
            lineas.append(
                f"  donante críptico conocido ({CRYPTIC_DONOR}) en "
                f"construccion:{self.cryptic_position}"
            )
        if self.scaffold_modified:
            lineas.append(
                "  ANDAMIO MODIFICADO: esta construcción NO lleva el miR-E verificado."
            )
        return "\n".join(lineas)


def intron_report(names) -> list[dict[str, object]]:
    """Estado de cada intron pedido. Los que faltan salen VISIBLES, no se omiten."""
    filas = []
    for nombre in names:
        intron = get_intron(nombre)
        filas.append({
            "intron": nombre,
            "estado": intron.state,
            "descripcion": intron.description,
            "motivo": "" if intron.provided else intron.why_missing,
            "ficha": intron.ficha,
        })
    return filas


def context_note(constructions) -> str:
    """Que contexto exonico se ha dado, y si es poco lo DICE.

    Sin casete, lo unico que hay son las piezas `exon5`/`exon3` del plasmido: **5 nt por
    lado**, que para un modelo que mira miles es esencialmente NINGUN contexto. No se
    rellena con nada (regla 1) y no se esconde: se dice, y se dice como conseguir mas.
    """
    if not constructions:
        return "No hay construcciones."
    anchos = {(c.context_5, c.context_3) for c in constructions}
    if len(anchos) > 1:
        raise ShmirDesignError(
            f"Las construcciones de esta corrida no comparten la misma ventana de "
            f"contexto ({sorted(anchos)}), así que sus puntuaciones NO son comparables "
            f"entre si — y comparar entre construcciones es todo lo que este frente "
            f"puede hacer. Se aborta."
        )
    cinco, tres = anchos.pop()
    base = (
        f"Ventana de contexto exonico declarada: {cinco} nt por el 5' y {tres} nt por el "
        f"3'. {CONTEXT_MATTERS}"
    )
    if cinco <= len(PIECES["exon5"].sequence):
        base += (
            " AVISO: eso es lo que dan las piezas del plásmido y es esencialmente NINGÚN "
            "contexto para un modelo entrenado con ventana de 10.000 nt. Para dar más "
            "hace falta el CASETE (`aav_casete.fa`): entonces el contexto sale de "
            "secuencia real y no se rellena con nada."
        )
    return base


@dataclass(frozen=True)
class FailedConstruction:
    """Un par que NO se pudo montar, con de quien es y por que."""

    candidate_start: int
    intron: str
    reason: str


@dataclass(frozen=True)
class ConstructionPanel:
    """Lo que se pudo montar y lo que no. Las dos mitades, siempre."""

    constructions: tuple[Construction, ...]
    failed: tuple[FailedConstruction, ...] = ()

    @property
    def partial(self) -> bool:
        return bool(self.failed)


def _guia_de(selection, elegido) -> str:
    """La guia de ESTE candidato, PEDIDA a su ventana.

    **Antes se recortaba de una secuencia que pasaba el llamador**
    —`target[start - 1:end]`— y esa es la causa entera de la errata nº 94: los `start`
    van en el marco de LO TILADO y la pagina pasaba el 3'UTR, asi que cuatro de las diez
    salian con la guia de OTRO SITIO —22 nt, md5 correcto, sin ningun error— y las seis
    que se salen del 3'UTR daban una cadena vacia. El aborto era la mitad afortunada.

    La guia ya esta calculada en la ventana. Volver a derivarla de una secuencia que
    puede ser cualquiera es una segunda definicion del mismo dato (principio nº 13), y
    con un `start` que no lleva marco no hay forma de comprobar cual es la buena.
    """
    ventana = selection.window_of(elegido)
    guia = "".join(str(ventana.evaluation.guide).split()).upper().replace("U", "T")
    if not guia:
        raise ShmirDesignError(
            f"El candidato 3utr:{elegido.start} llega SIN GUÍA: su ventana de la "
            f"selección trae la guía vacía, así que no hay "
            f"nada con lo que montar la horquilla. No es una guía mal formada — es una "
            f"guía que no ha llegado, y el sitio donde mirar es la ventana de ese "
            f"candidato en el tilado, no el andamio."
        )
    return guia


def build_panel(
    selection,
    *,
    intron_names=("mvm_actual",),
    scaffold=None,
    starts=None,
    cassette: str | None = None,
    context_nt: int = 0,
) -> ConstructionPanel:
    """Monta todos los pares y dice CUALES no pudo. No aborta por uno.

    **Un fallo en el montaje de UNA construccion no puede impedir las otras
    diecinueve**: el error salia antes del FASTA, asi que un candidato sin guia
    bloqueaba la corrida entera. Se emite lo que se puede y se dice lo que falta, que es
    la misma regla que rige los frentes.

    Lo que si aborta es que no salga NINGUNA: cero construcciones no es una entrega
    parcial — no hay nada que consultar, y un FASTA vacio no se podria validar despues.
    """
    hechas: list[Construction] = []
    fallidas: list[FailedConstruction] = []
    for nombre in intron_names:
        try:
            hechas.extend(build_constructions(
                selection, intron_names=(nombre,), scaffold=scaffold, starts=starts,
                cassette=cassette, context_nt=context_nt, _failures=fallidas,
            ))
        except ShmirDesignError as exc:
            # rule2-ok: no se traga — el motivo entero viaja en `failed` y la pagina lo
            # pinta. Lo que se evita es que un intron que no se puede montar impida los
            # demas. Si al final no queda ninguna construccion, se aborta abajo.
            for elegido in selection.selection.chosen:
                if starts is None or elegido.start in set(starts):
                    fallidas.append(FailedConstruction(
                        candidate_start=elegido.start, intron=nombre, reason=str(exc),
                    ))
    if not hechas:
        raise ShmirDesignError(
            "No se pudo montar NINGUNA construcción, así que no hay nada que consultar "
            "y no se emite ningún FASTA:\n"
            + "\n".join(f"  · 3utr:{f.candidate_start} × {f.intron}: {f.reason}"
                         for f in fallidas)
        )
    return ConstructionPanel(
        constructions=tuple(hechas), failed=tuple(fallidas),
    )


def build_constructions(
    selection,
    *,
    intron_names=("mvm_actual",),
    scaffold=None,
    starts=None,
    cassette: str | None = None,
    context_nt: int = 0,
    _failures: list | None = None,
) -> tuple[Construction, ...]:
    """Monta un cassette POR PAR candidato x intron. La unidad de este modal.

    `cassette` + `context_nt` sacan el contexto exonico de la SECUENCIA REAL del
    plasmido en vez de las dos piezas de 5 nt. Si se pide mas del que hay, se da lo que
    hay: nunca se rellena (regla 1).

    **La guia se PIDE a la ventana** (`_guia_de`), no se recorta de ninguna secuencia
    que pase el llamador: ver la errata nº 94.
    """
    elegidos = [
        c for c in selection.selection.chosen
        if starts is None or c.start in set(starts)
    ]
    if not elegidos:
        raise ShmirDesignError(
            "No hay ningún candidato seleccionado para consultar; se aborta en vez de "
            "emitir un FASTA vacío que luego no se podría validar."
        )

    construcciones: list[Construction] = []
    for nombre in intron_names:
        intron = get_intron(nombre)
        if not intron.provided:
            raise ShmirDesignError(
                f"El intrón {nombre!r} no está disponible, así que no hay cassette que "
                f"montar. {intron.why_missing} Se aborta en vez de emitir consultas de "
                f"un intrón que no tenemos."
            )
        contexto5, contexto3 = _flancos(
            intron, cassette=cassette, context_nt=context_nt
        )
        for elegido in elegidos:
            try:
                guia = _guia_de(selection, elegido)
            except ShmirDesignError as exc:
                if _failures is None:
                    raise
                # rule2-ok: el motivo entero se conserva y viaja al panel; lo que se
                # evita es que un candidato tumbe a los otros diecinueve.
                _failures.append(FailedConstruction(
                    candidate_start=elegido.start, intron=nombre, reason=str(exc),
                ))
                continue
            bloque = build_block(guia, scaffold=scaffold)
            montado = intron.with_module(bloque.module)
            elementos = locate_elements(montado, name=nombre)
            secuencia = contexto5 + montado + contexto3
            desplazamiento = len(contexto5)
            criptico = montado.find(CRYPTIC_DONOR)
            construcciones.append(
                Construction(
                    name=f"{nombre}__3utr{elegido.start}",
                    candidate_start=elegido.start,
                    intron=nombre,
                    sequence=secuencia,
                    md5=_md5(secuencia),
                    context_5=len(contexto5),
                    context_3=len(contexto3),
                    donor_position=desplazamiento + elementos.donor.start,
                    acceptor_position=desplazamiento + elementos.acceptor.start,
                    cryptic_position=(
                        desplazamiento + criptico + 1 if criptico >= 0 else 0
                    ),
                    scaffold_modified=bool(
                        scaffold is not None and not getattr(scaffold, "verified", True)
                    ),
                )
            )
    return tuple(construcciones)


def _flancos(intron, *, cassette, context_nt) -> tuple[str, str]:
    """El contexto exonico. Del casete si lo hay; si no, las piezas."""
    piezas = (
        PIECES[intron.exon5_piece].sequence if intron.exon5_piece else "",
        PIECES[intron.exon3_piece].sequence if intron.exon3_piece else "",
    )
    if not cassette or context_nt <= 0:
        return piezas

    from .splicing import locate_intron

    limpio = "".join(str(cassette).split()).upper()
    sitio = locate_intron(limpio, name="casete para el contexto de splicing")
    # `locate_intron` da posiciones 1-based: `donor_start` es el primer nt del intron y
    # `acceptor_end` el ultimo. El contexto es lo que hay FUERA de ese intervalo.
    inicio = sitio.donor_start - 1
    fin = sitio.acceptor_end
    # Se recorta a lo que el casete da. Pedir 100.000 no inventa 100.000.
    return (
        limpio[max(0, inicio - context_nt):inicio],
        limpio[fin:fin + context_nt],
    )


FASTA_WRAP = 60


def constructions_fasta(constructions) -> str:
    """El FASTA que se entrega. El md5 va EN LA CABECERA: es lo que ata el resultado."""
    if not constructions:
        raise ShmirDesignError(
            "No hay construcciones que exportar; se aborta en vez de escribir un FASTA "
            "vacio."
        )
    lineas = []
    for c in constructions:
        lineas.append(
            f">{c.name} md5={c.md5} longitud={len(c.sequence)} "
            f"contexto5={c.context_5} contexto3={c.context_3} "
            f"donante={c.donor_position} aceptor={c.acceptor_position}"
        )
        for i in range(0, len(c.sequence), FASTA_WRAP):
            lineas.append(c.sequence[i:i + FASTA_WRAP])
    return "\n".join(lineas) + "\n"


# ─────────────────────────── el ejecutor ───────────────────────────


class Executor:
    """Interfaz. La de hoy es `Disabled`, igual que en el modal de especificidad."""

    name = "interfaz"
    runs_here = False
    why = ""

    def prepare(self, *, fasta_path: str) -> str:
        raise NotImplementedError

    def run(self, *, constructions):
        raise NotImplementedError


class Disabled(Executor):
    """La de HOY. No ejecuta y dice exactamente por que."""

    name = "deshabilitado"
    runs_here = False
    why = (
        "Este software no ejecuta SpliceAI y no puede: este backend no tiene red saliente "
        "y la invocación de SpliceAI no se ha verificado desde este proyecto, así que "
        "tampoco se escribe (regla 4). Lo que hace es PREPARAR el FASTA de las "
        "construcciones con su md5 y RECOGER el resultado. No es una limitacion "
        "escondida: es la arquitectura."
    )

    def prepare(self, *, fasta_path: str) -> str:
        return (
            f"Descarga {fasta_path}, pasalo por SpliceAI en tu máquina y sube el "
            f"resultado en el formato que describe la ficha. La orden concreta depende "
            f"de como lo tengas instalado y este proyecto NO la inventa."
        )

    def run(self, *, constructions):
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» NO EJECUTA. {self.why}"
        )


class LocalCommand(Executor):
    """Da una orden para ejecutar EN LOCAL. La orden se le PASA: no se escribe aqui."""

    name = "orden_local"
    runs_here = False
    why = (
        "La orden se ejecuta en la máquina de quien la copia. Este módulo no trae ninguna "
        "escrita porque la invocación de SpliceAI no se ha verificado desde este proyecto "
        "(regla 4): se comprueba, se anota, y entonces se pasa."
    )

    def __init__(self, *, command: str | None):
        if not command or not str(command).strip():
            raise ValueError(
                "LocalCommand necesita una orden VERIFICADA. Aquí no hay ninguna escrita "
                "a propósito: la invocación de SpliceAI no se ha comprobado desde este "
                "proyecto, y escribirla de memoria es lo mismo que inventar una URL de "
                "API a partir de un patron. Se aborta."
            )
        self.command = str(command).strip()

    def prepare(self, *, fasta_path: str) -> str:
        return self.command.replace("{fasta}", fasta_path)

    def run(self, *, constructions):
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» prepara la orden pero no la lanza desde aquí. "
            f"{self.why}"
        )


# ─────────────────────────── recoger el resultado ───────────────────────────

#: El formato que este modulo ACEPTA. Es nuestro, asi que si se define.
RESULT_COLUMNS = ("construccion", "md5", "posicion", "tipo", "puntuacion")
RESULT_HEADER = "\t".join(RESULT_COLUMNS)

SITE_KINDS = ("donante", "aceptor")


@dataclass(frozen=True)
class SiteScore:
    construction: str
    position: int
    kind: str
    score: float


def parse_result(text: str, *, constructions) -> tuple[SiteScore, ...]:
    """Lee el resultado y lo VALIDA contra lo que se entrego. Rechaza lo de otra corrida."""
    por_nombre = {c.name: c for c in constructions}
    filas = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not filas:
        raise ShmirDesignError(
            "El resultado está vacío del todo: ni cabecera. Se aborta."
        )
    cabecera = tuple(filas[0].split("\t"))
    if cabecera != RESULT_COLUMNS:
        raise ShmirDesignError(
            f"La cabecera del resultado es {cabecera} y se esperaba {RESULT_COLUMNS}; se "
            f"aborta en vez de leer las columnas por posición."
        )
    if len(filas) == 1:
        raise ShmirDesignError(
            "El resultado solo trae cabecera. Se aborta: CERO SITIOS y «la corrida no "
            "llego a correr» son cosas distintas y este fichero NO DISTINGUE entre las "
            "dos. Es la misma razón por la que un `-outfmt 6` vacío también se rechaza."
        )

    sitios: list[SiteScore] = []
    for numero, fila in enumerate(filas[1:], start=2):
        campos = fila.split("\t")
        if len(campos) != len(RESULT_COLUMNS):
            raise ShmirDesignError(
                f"fila {numero}: tiene {len(campos)} campo(s) y la cabecera declara "
                f"{len(RESULT_COLUMNS)}; se aborta en vez de saltarse la fila."
            )
        nombre, md5, posicion, tipo, puntuacion = (c.strip() for c in campos)
        construccion = por_nombre.get(nombre)
        if construccion is None:
            raise ShmirDesignError(
                f"fila {numero}: la construcción {nombre!r} no es ninguna de las que "
                f"genero esta corrida ({', '.join(sorted(por_nombre))}). Se rechaza el "
                f"fichero entero: es el fallo del CSV de miRarchitect —un fichero de "
                f"OTRA CORRIDA pegado por error, que entra, cuadra de forma y produce un "
                f"análisis entero sobre el dato equivocado."
            )
        if md5 != construccion.md5:
            raise ShmirDesignError(
                f"fila {numero}: {nombre} declara md5 {md5!r} y la construcción que se "
                f"entrego tiene {construccion.md5!r}. Se rechaza: un resultado de OTRA "
                f"CORRIDA no puede entrar, aunque encaje de forma."
            )
        if tipo not in SITE_KINDS:
            raise ShmirDesignError(
                f"fila {numero}: tipo {tipo!r} desconocido; los que hay son "
                f"{SITE_KINDS}. Se aborta."
            )
        try:
            entero = int(posicion)
            valor = float(puntuacion)
        except ValueError as exc:
            raise ShmirDesignError(
                f"fila {numero}: posición o puntuación no numericas ({exc}); se aborta."
            ) from exc
        if not 1 <= entero <= len(construccion.sequence):
            raise ShmirDesignError(
                f"fila {numero}: la posición {entero} se sale de la construcción "
                f"{nombre} ({len(construccion.sequence)} nt); se aborta."
            )
        sitios.append(
            SiteScore(construction=nombre, position=entero, kind=tipo, score=valor)
        )
    return tuple(sitios)


# ─────────────────────────── el analisis ───────────────────────────


@dataclass(frozen=True)
class Cryptic:
    position: int
    kind: str
    score: float
    fraction: float
    note: str = ""


@dataclass(frozen=True)
class PairResult:
    """Un par candidato x intron, ya interpretado CONTRA SU PROPIO REFERENTE."""

    construction: str
    candidate_start: int
    intron: str
    legit_donor: float
    legit_acceptor: float
    cryptics: tuple[Cryptic, ...]
    known_cryptic: Cryptic | None
    context_5: int
    context_3: int

    @property
    def best_cryptic(self) -> Cryptic | None:
        return self.cryptics[0] if self.cryptics else None

    def describe(self) -> list[str]:
        lineas = [
            f"{self.construction}  (3utr:{self.candidate_start} x {self.intron})",
            f"  REFERENTE INTERNO — donante legítimo {self.legit_donor:.3f}, "
            f"aceptor legítimo {self.legit_acceptor:.3f}",
            f"  contexto declarado: {self.context_5} nt / {self.context_3} nt",
        ]
        if self.best_cryptic is None:
            lineas.append(
                f"  Ningún sitio críptico llega al {RELATIVE_THRESHOLD:.0%} del legítimo."
            )
        else:
            mejor = self.best_cryptic
            lineas.append(
                f"  MEJOR CRÍPTICO — construcción:{mejor.position} ({mejor.kind}) "
                f"{mejor.score:.3f} = {mejor.fraction:.0%} del legítimo"
            )
            for otro in self.cryptics[1:]:
                lineas.append(
                    f"    construcción:{otro.position} ({otro.kind}) {otro.score:.3f} "
                    f"= {otro.fraction:.0%}"
                )
        if self.known_cryptic is not None:
            lineas.append(
                f"  {CRYPTIC_DONOR} (el críptico CONOCIDO del andamio, y el motivo por "
                f"el que existe este modal) — construcción:"
                f"{self.known_cryptic.position} {self.known_cryptic.score:.3f} "
                f"= {self.known_cryptic.fraction:.0%} del legítimo"
            )
        else:
            lineas.append(
                f"  {CRYPTIC_DONOR}: SIN PUNTUAR en este resultado. No es «no puntua»: "
                f"es que el fichero no trae ninguna fila para esa posición."
            )
        return lineas


@dataclass(frozen=True)
class SpliceScan:
    pairs: tuple[PairResult, ...]
    threshold: float = RELATIVE_THRESHOLD

    def for_candidate(self, start: int, intron: str) -> PairResult | None:
        for par in self.pairs:
            if par.candidate_start == start and par.intron == intron:
                return par
        return None


def scan_from_result(text: str, *, constructions) -> SpliceScan:
    """Del resultado crudo al analisis, siempre contra el referente INTERNO."""
    sitios = parse_result(text, constructions=constructions)
    por_construccion: dict[str, list[SiteScore]] = {}
    for sitio in sitios:
        por_construccion.setdefault(sitio.construction, []).append(sitio)

    pares: list[PairResult] = []
    for construccion in constructions:
        suyos = por_construccion.get(construccion.name, [])
        if not suyos:
            continue
        legitimo_donante = next(
            (s.score for s in suyos
             if s.position == construccion.donor_position and s.kind == "donante"),
            0.0,
        )
        legitimo_aceptor = next(
            (s.score for s in suyos
             if s.position == construccion.acceptor_position and s.kind == "aceptor"),
            0.0,
        )
        if legitimo_donante <= 0:
            raise ShmirDesignError(
                f"{construccion.name}: el donante legítimo "
                f"(construccion:{construccion.donor_position}) no viene puntuado o vale "
                f"cero, así que NO HAY REFERENTE interno contra el que comparar. Y sin "
                f"referente no hay nada: las puntuaciones absolutas de este modelo no "
                f"son interpretables sobre un cassette de AAV. Se aborta. "
                f"{RELATIVE_ONLY}"
            )

        cripticos = []
        conocido = None
        for sitio in suyos:
            legitimo = (
                sitio.position == construccion.donor_position and sitio.kind == "donante"
            ) or (
                sitio.position == construccion.acceptor_position
                and sitio.kind == "aceptor"
            )
            if legitimo:
                continue
            fraccion = sitio.score / legitimo_donante
            entrada = Cryptic(
                position=sitio.position, kind=sitio.kind, score=sitio.score,
                fraction=fraccion,
                note=(
                    f"{CRYPTIC_DONOR}: donante críptico del flanco 5' de miR-E. Viaja "
                    f"con CUALQUIER candidato porque está dentro del andamio, y compite "
                    f"por el aceptor legítimo del intrón."
                    if sitio.position == construccion.cryptic_position else ""
                ),
            )
            if sitio.position == construccion.cryptic_position and sitio.kind == "donante":
                conocido = entrada
            if fraccion >= RELATIVE_THRESHOLD:
                cripticos.append(entrada)

        cripticos.sort(key=lambda c: c.score, reverse=True)
        pares.append(
            PairResult(
                construction=construccion.name,
                candidate_start=construccion.candidate_start,
                intron=construccion.intron,
                legit_donor=legitimo_donante,
                legit_acceptor=legitimo_aceptor,
                cryptics=tuple(cripticos),
                known_cryptic=conocido,
                context_5=construccion.context_5,
                context_3=construccion.context_3,
            )
        )
    return SpliceScan(pairs=tuple(pares))


def exclusive_rows(scan: SpliceScan) -> list[dict[str, object]]:
    """Que guias introducen cripticos que las OTRAS no. Es lo accionable.

    Se compara ENTRE CONSTRUCCIONES del mismo intron: mezclar intrones distintos aqui
    daria «exclusivos» que solo dicen que los intrones son distintos, que ya se sabe.
    """
    filas = []
    for par in scan.pairs:
        hermanas = [
            p for p in scan.pairs
            if p.intron == par.intron and p.construction != par.construction
        ]
        compartidas = set()
        for hermana in hermanas:
            compartidas |= {(c.position, c.kind) for c in hermana.cryptics}
        exclusivos = [
            c for c in par.cryptics if (c.position, c.kind) not in compartidas
        ]
        filas.append({
            "construccion": par.construction,
            "candidato": par.candidate_start,
            "intron": par.intron,
            "exclusivos": [
                {"posicion": c.position, "tipo": c.kind, "fraccion": c.fraction}
                for c in exclusivos
            ],
            "hermanas": len(hermanas),
        })
    return filas


def verdict_state(scan: SpliceScan | None) -> FilterState:
    """NUNCA FAIL. Desempate y alerta: no puede excluir a nadie."""
    return FilterState.PASS if scan and scan.pairs else FilterState.NOT_RUN
