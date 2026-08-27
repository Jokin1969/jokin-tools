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
    "composicion tambien. Lo que devuelve aqui no es «lo mismo peor»: es un numero "
    "calculado sobre una entrada de otra clase."
)

NO_ABSOLUTE_THRESHOLD = (
    "LAS PUNTUACIONES ABSOLUTAS NO SON INTERPRETABLES, y no hay ningun umbral que "
    "aplicar. Un 0,8 aqui no significa lo que significa un 0,8 en el genoma humano, y no "
    "existe un valor por encima del cual algo sea «un sitio». Cualquier corte que se "
    "pusiera seria inventado."
)

RELATIVE_ONLY = (
    "Lo unico que vale es la comparacion RELATIVA contra un referente INTERNO: el donante "
    "legitimo del mismo intron, en la misma corrida. Es el mismo criterio que ya se uso "
    "para descartar los aceptores cripticos —el tracto de pirimidinas de cada uno "
    "comparado contra las nueve del legitimo— y funciona por la misma razon: el veredicto "
    "no depende de ningun umbral traido de fuera. Un modulo cuyo mejor criptico se ACERQUE "
    "al legitimo es sospechoso; uno donde el legitimo DOMINE, no."
)

CONTEXT_MATTERS = (
    "LA VENTANA DE CONTEXTO CAMBIA EL RESULTADO, asi que va declarada y viaja con cada "
    "consulta. SpliceAI mira miles de nucleotidos a cada lado; aqui hay lo que da el "
    "casete. Dos corridas con contextos distintos no son comparables, y sin registrarlo "
    "nadie podria saberlo."
)

USE_NOTE = (
    "USO: DESEMPATE Y ALERTA, NUNCA FILTRO. Ni esto ni la accesibilidad estructural "
    "pueden excluir un candidato — NO ES UN VEREDICTO. Lo que pueden hacer es señalar que "
    "una construccion concreta tiene un perfil peor que sus hermanas, y eso es motivo "
    "para preferir otra o para llevar las dos."
)

WHAT_IS_ACTIONABLE = (
    "LO ACCIONABLE es que guias introducen cripticos que las otras NO. Si nueve dan un "
    "perfil limpio y una no, esa una se CAMBIA. Es una comparacion ENTRE CONSTRUCCIONES, "
    "no contra un umbral absoluto — que es justo lo que aqui no se puede usar."
)

#: Umbral RELATIVO por debajo del cual un sitio no se lista. DECLARADO como parametro de
#: este analisis, NO citado: no sale de ninguna publicacion. Existe para que la tabla no
#: se llene de ruido, no para decidir nada.
RELATIVE_THRESHOLD = 0.05

RELATIVE_THRESHOLD_NOTE = (
    f"Solo se listan los sitios cuya puntuacion llega al {RELATIVE_THRESHOLD:.0%} de la "
    f"del donante legitimo. Es un umbral RELATIVO y va DECLARADO como parametro de este "
    f"analisis, no citado: no sale de ninguna publicacion y no decide nada — solo evita "
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
            f"  candidato 3utr:{self.candidate_start} x intron {self.intron}",
            f"  contexto exonico declarado: {self.context_5} nt por el 5' y "
            f"{self.context_3} nt por el 3'",
            f"  donante legitimo en construccion:{self.donor_position}, "
            f"aceptor en construccion:{self.acceptor_position}",
        ]
        if self.cryptic_position:
            lineas.append(
                f"  donante criptico conocido ({CRYPTIC_DONOR}) en "
                f"construccion:{self.cryptic_position}"
            )
        if self.scaffold_modified:
            lineas.append(
                "  ANDAMIO MODIFICADO: esta construccion NO lleva el miR-E verificado."
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
            f"contexto ({sorted(anchos)}), asi que sus puntuaciones NO son comparables "
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
            " AVISO: eso es lo que dan las piezas del plasmido y es esencialmente NINGUN "
            "contexto para un modelo entrenado con ventana de 10.000 nt. Para dar mas "
            "hace falta el CASETE (`aav_casete.fa`): entonces el contexto sale de "
            "secuencia real y no se rellena con nada."
        )
    return base


def build_constructions(
    selection,
    *,
    target: str,
    intron_names=("mvm_actual",),
    scaffold=None,
    starts=None,
    cassette: str | None = None,
    context_nt: int = 0,
) -> tuple[Construction, ...]:
    """Monta un cassette POR PAR candidato x intron. La unidad de este modal.

    `cassette` + `context_nt` sacan el contexto exonico de la SECUENCIA REAL del
    plasmido en vez de las dos piezas de 5 nt. Si se pide mas del que hay, se da lo que
    hay: nunca se rellena (regla 1).
    """
    elegidos = [
        c for c in selection.selection.chosen
        if starts is None or c.start in set(starts)
    ]
    if not elegidos:
        raise ShmirDesignError(
            "No hay ningun candidato seleccionado para consultar; se aborta en vez de "
            "emitir un FASTA vacio que luego no se podria validar."
        )

    construcciones: list[Construction] = []
    for nombre in intron_names:
        intron = get_intron(nombre)
        if not intron.provided:
            raise ShmirDesignError(
                f"El intron {nombre!r} no esta disponible, asi que no hay cassette que "
                f"montar. {intron.why_missing} Se aborta en vez de emitir consultas de "
                f"un intron que no tenemos."
            )
        contexto5, contexto3 = _flancos(
            intron, cassette=cassette, context_nt=context_nt
        )
        for elegido in elegidos:
            guia = target[elegido.start - 1:elegido.end]
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
        "y la invocacion de SpliceAI no se ha verificado desde este proyecto, asi que "
        "tampoco se escribe (regla 4). Lo que hace es PREPARAR el FASTA de las "
        "construcciones con su md5 y RECOGER el resultado. No es una limitacion "
        "escondida: es la arquitectura."
    )

    def prepare(self, *, fasta_path: str) -> str:
        return (
            f"Descarga {fasta_path}, pasalo por SpliceAI en tu maquina y sube el "
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
        "La orden se ejecuta en la maquina de quien la copia. Este modulo no trae ninguna "
        "escrita porque la invocacion de SpliceAI no se ha verificado desde este proyecto "
        "(regla 4): se comprueba, se anota, y entonces se pasa."
    )

    def __init__(self, *, command: str | None):
        if not command or not str(command).strip():
            raise ValueError(
                "LocalCommand necesita una orden VERIFICADA. Aqui no hay ninguna escrita "
                "a proposito: la invocacion de SpliceAI no se ha comprobado desde este "
                "proyecto, y escribirla de memoria es lo mismo que inventar una URL de "
                "API a partir de un patron. Se aborta."
            )
        self.command = str(command).strip()

    def prepare(self, *, fasta_path: str) -> str:
        return self.command.replace("{fasta}", fasta_path)

    def run(self, *, constructions):
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» prepara la orden pero no la lanza desde aqui. "
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
            "El resultado esta vacio del todo: ni cabecera. Se aborta."
        )
    cabecera = tuple(filas[0].split("\t"))
    if cabecera != RESULT_COLUMNS:
        raise ShmirDesignError(
            f"La cabecera del resultado es {cabecera} y se esperaba {RESULT_COLUMNS}; se "
            f"aborta en vez de leer las columnas por posicion."
        )
    if len(filas) == 1:
        raise ShmirDesignError(
            "El resultado solo trae cabecera. Se aborta: CERO SITIOS y «la corrida no "
            "llego a correr» son cosas distintas y este fichero NO DISTINGUE entre las "
            "dos. Es la misma razon por la que un `-outfmt 6` vacio tambien se rechaza."
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
                f"fila {numero}: la construccion {nombre!r} no es ninguna de las que "
                f"genero esta corrida ({', '.join(sorted(por_nombre))}). Se rechaza el "
                f"fichero entero: es el fallo del CSV de miRarchitect —un fichero de "
                f"OTRA CORRIDA pegado por error, que entra, cuadra de forma y produce un "
                f"analisis entero sobre el dato equivocado."
            )
        if md5 != construccion.md5:
            raise ShmirDesignError(
                f"fila {numero}: {nombre} declara md5 {md5!r} y la construccion que se "
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
                f"fila {numero}: posicion o puntuacion no numericas ({exc}); se aborta."
            ) from exc
        if not 1 <= entero <= len(construccion.sequence):
            raise ShmirDesignError(
                f"fila {numero}: la posicion {entero} se sale de la construccion "
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
            f"  REFERENTE INTERNO — donante legitimo {self.legit_donor:.3f}, "
            f"aceptor legitimo {self.legit_acceptor:.3f}",
            f"  contexto declarado: {self.context_5} nt / {self.context_3} nt",
        ]
        if self.best_cryptic is None:
            lineas.append(
                f"  Ningun sitio criptico llega al {RELATIVE_THRESHOLD:.0%} del legitimo."
            )
        else:
            mejor = self.best_cryptic
            lineas.append(
                f"  MEJOR CRIPTICO — construccion:{mejor.position} ({mejor.kind}) "
                f"{mejor.score:.3f} = {mejor.fraction:.0%} del legitimo"
            )
            for otro in self.cryptics[1:]:
                lineas.append(
                    f"    construccion:{otro.position} ({otro.kind}) {otro.score:.3f} "
                    f"= {otro.fraction:.0%}"
                )
        if self.known_cryptic is not None:
            lineas.append(
                f"  {CRYPTIC_DONOR} (el criptico CONOCIDO del andamio, y el motivo por "
                f"el que existe este modal) — construccion:"
                f"{self.known_cryptic.position} {self.known_cryptic.score:.3f} "
                f"= {self.known_cryptic.fraction:.0%} del legitimo"
            )
        else:
            lineas.append(
                f"  {CRYPTIC_DONOR}: SIN PUNTUAR en este resultado. No es «no puntua»: "
                f"es que el fichero no trae ninguna fila para esa posicion."
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
                f"{construccion.name}: el donante legitimo "
                f"(construccion:{construccion.donor_position}) no viene puntuado o vale "
                f"cero, asi que NO HAY REFERENTE interno contra el que comparar. Y sin "
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
                    f"{CRYPTIC_DONOR}: donante criptico del flanco 5' de miR-E. Viaja "
                    f"con CUALQUIER candidato porque esta dentro del andamio, y compite "
                    f"por el aceptor legitimo del intron."
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
