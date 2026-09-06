"""Comprobar el plásmido montado a mano. NO se genera: se verifica.

## Por qué no se generan los `.dna` completos

Un plásmido de 5.400 pb ensamblado por código es demasiada superficie para un error
silencioso, y el módulo, el casete y el fragmento ya se emiten. Lo que faltaba era el
otro extremo: **entre lo que la app emite y lo que acaba en el vector no había ninguna
comprobación**. Es el último eslabón sin red, y es exactamente el criterio de
`gblock.verify_contexts_against_plasmid` con SGEP — se comprueba lo que se construyó, no
se construye.

## Por SECUENCIA, no por coordenadas

Un número escrito no puede validar el fichero del que salió (principio nº 13). Esto busca
el fragmento DENTRO del plásmido y compara secuencia con secuencia; no mira la posición
3129 de nada. Una feature corrida un nucleótido no lo engaña, y un plásmido con el intrón
en otro sitio pasa igual — que es lo correcto: la pregunta es «¿está dentro lo que
emitimos?», no «¿está donde yo creía?».

## Lo que NO hace, y va dicho

No dice si el plásmido «funciona», ni comprueba el resto del vector: comprueba el
fragmento. Y cuando algo falla, dice **qué encontró**, no por qué — un diagnóstico
equivocado cuesta más que ninguno (principio nº 3, y la lección del «Alu 0 %» obtenido
sin buscar Alu).

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from .errors import ShmirDesignError
from .filters import FilterResult, FilterState
from .reference import sequence_md5

#: Lo que se admite como base en un plásmido. IUPAC completo: un `.dna` de laboratorio
#: puede traer ambigüedades, y rechazarlas sería confundir «no es ADN» con «no es ADN
#: sin ambigüedad».
DNA_ALPHABET = frozenset("ACGTUNRYSWKMBDHV")

#: Cabecera del `.dna` de SnapGene: byte de tipo 0x09 y la palabra `SnapGene` dentro del
#: primer segmento.
SNAPGENE_MAGIC = b"\x09"
SNAPGENE_COOKIE = b"SnapGene"
#: El segmento que lleva la secuencia de ADN.
SNAPGENE_DNA_SEGMENT = 0

SNAPGENE_FORMAT_DECLARED = (
    "El formato `.dna` de SnapGene está DECLARADO aquí a partir de su descripción "
    "pública —cabecera con la palabra «SnapGene», y segmentos de tipo (1 byte) más "
    "longitud (4 bytes, big-endian), con el segmento 0 llevando un byte de banderas y la "
    "secuencia en ASCII— y NO está verificado contra ningún `.dna` real de este "
    "repositorio: aquí no hay ninguno. Por eso el lector no se fía de la descripción, la "
    "INTERROGA: comprueba la cabecera, comprueba que la longitud declarada de cada "
    "segmento cabe en el fichero y comprueba que lo que lee es ADN. Si algo no cuadra "
    "ABORTA diciendo qué, en vez de devolver una secuencia plausible — que es el peor "
    "resultado posible de este software (regla 1). El día que llegue un `.dna` real, ese "
    "fichero es la prueba y esta nota se sustituye por la medida."
)


#: Mismo criterio que en `fragmento`: el md5 lo calcula `reference.sequence_md5` y no
#: este módulo. Los dos lados de esta comprobación —el número que viaja en la cabecera
#: del FASTA y el que se recalcula aquí— tienen que salir de la MISMA definición, o el
#: cruce dejaría de significar nada (principio nº 24).
_md5 = sequence_md5


# ─── Leer el plásmido, venga como venga ──────────────────────────────────────


def snapgene_sequence(data: bytes) -> str:
    """La secuencia de un `.dna` de SnapGene, comprobando lo que lee.

    Ver `SNAPGENE_FORMAT_DECLARED`: el formato está descrito, no medido, así que cada
    afirmación del fichero se comprueba antes de usarla.
    """
    if not data.startswith(SNAPGENE_MAGIC):
        raise ShmirDesignError(
            f"No parece un `.dna` de SnapGene: el primer byte es {data[:1]!r} y se "
            f"esperaba {SNAPGENE_MAGIC!r}. Se aborta en vez de interpretar bytes a ver "
            f"qué sale."
        )
    if SNAPGENE_COOKIE not in data[:64]:
        raise ShmirDesignError(
            f"No parece un `.dna` de SnapGene: no aparece {SNAPGENE_COOKIE!r} en la "
            f"cabecera. Se aborta. {SNAPGENE_FORMAT_DECLARED}"
        )
    posicion = 0
    total = len(data)
    while posicion + 5 <= total:
        tipo = data[posicion]
        (longitud,) = struct.unpack(">I", data[posicion + 1 : posicion + 5])
        inicio = posicion + 5
        if inicio + longitud > total:
            raise ShmirDesignError(
                f"El `.dna` declara un segmento de tipo {tipo} y {longitud} bytes en la "
                f"posición {posicion}, y el fichero sólo tiene {total}. La longitud "
                f"declarada no cabe: se aborta en vez de leer lo que haya."
            )
        if tipo == SNAPGENE_DNA_SEGMENT:
            if longitud < 2:
                raise ShmirDesignError(
                    f"El segmento de ADN del `.dna` declara {longitud} bytes y hacen "
                    f"falta al menos dos (banderas + secuencia). Se aborta."
                )
            crudo = data[inicio + 1 : inicio + longitud]
            try:
                secuencia = crudo.decode("ascii").upper()
            except UnicodeDecodeError as error:
                raise ShmirDesignError(
                    f"El segmento de ADN del `.dna` no es ASCII: {error}. Se aborta."
                ) from error
            malas = sorted(set(secuencia) - DNA_ALPHABET)
            if malas:
                raise ShmirDesignError(
                    f"El segmento de ADN del `.dna` trae caracteres fuera del alfabeto "
                    f"del ADN ({', '.join(repr(c) for c in malas[:5])}). O el fichero no "
                    f"es lo que dice o el formato no es el descrito; se aborta. "
                    f"{SNAPGENE_FORMAT_DECLARED}"
                )
            return secuencia
        posicion = inicio + longitud
    raise ShmirDesignError(
        "El `.dna` no trae ningún segmento de ADN (tipo "
        f"{SNAPGENE_DNA_SEGMENT}). Se aborta en vez de devolver una secuencia vacía, "
        "que se leería como «el plásmido no lleva el fragmento»."
    )


_ORIGIN = re.compile(r"^ORIGIN", re.MULTILINE)


def plasmid_sequence(source: str | bytes) -> str:
    """La secuencia del plásmido, venga en GenBank, FASTA, pelada o en `.dna`.

    El formato se DERIVA de lo que hay dentro, no de la extensión: un `.gb` renombrado a
    `.dna` es exactamente el caso en el que una extensión miente.
    """
    if isinstance(source, (bytes, bytearray)):
        if bytes(source[:1]) == SNAPGENE_MAGIC:
            return snapgene_sequence(bytes(source))
        try:
            source = bytes(source).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ShmirDesignError(
                f"El fichero no es texto y tampoco es un `.dna` de SnapGene "
                f"(empieza por {bytes(source[:1])!r}): {error}. Se aborta."
            ) from error

    texto = str(source)
    if _ORIGIN.search(texto):
        cuerpo = texto[_ORIGIN.search(texto).end() :]
        letras = [c for c in cuerpo.split("//", 1)[0] if c.isalpha()]
        return "".join(letras).upper()
    lineas = [
        l.strip() for l in texto.splitlines() if l.strip() and not l.startswith(">")
    ]
    secuencia = "".join(lineas).upper()
    malas = sorted(set(secuencia) - DNA_ALPHABET)
    if malas:
        raise ShmirDesignError(
            f"Lo que se ha dado no se lee como una secuencia de ADN: trae "
            f"{', '.join(repr(c) for c in malas[:5])}. Se admite GenBank, FASTA, "
            f"secuencia pelada o un `.dna` de SnapGene; se aborta en vez de comparar "
            f"contra un texto que no es ADN."
        )
    return secuencia


# ─── Leer lo que la app emitió ───────────────────────────────────────────────


@dataclass(frozen=True)
class EmittedFragment:
    """Un fragmento del FASTA que emitió la app, con lo que su cabecera DECLARA."""

    name: str
    sequence: str
    declared: dict[str, str]

    @property
    def md5(self) -> str:
        return _md5(self.sequence)

    @property
    def growth(self) -> int | None:
        crudo = self.declared.get("crece", "")
        return int(crudo) if crudo.lstrip("-").isdigit() else None


def parse_fragments_fasta(text: str) -> tuple[EmittedFragment, ...]:
    """Relee el FASTA de fragmentos y CRUZA cada md5 con su secuencia.

    Un fichero que viaja solo tiene que poder validarse solo: si alguien retocó una base
    por el camino, el md5 de la cabecera deja de cuadrar y esto aborta AQUÍ, antes de
    comparar nada con el plásmido. Sin este cruce, un FASTA editado a mano compararía
    mal contra un montaje correcto y el diagnóstico saldría del lado equivocado.
    """
    registros: list[EmittedFragment] = []
    nombre, campos, piezas = "", {}, []

    def cerrar() -> None:
        if not nombre:
            return
        secuencia = "".join(piezas).upper()
        if not secuencia:
            raise ShmirDesignError(
                f"El registro {nombre!r} del FASTA de fragmentos no trae secuencia. "
                f"Se aborta."
            )
        declarado = campos.get("md5", "")
        if declarado and declarado != _md5(secuencia):
            raise ShmirDesignError(
                f"El registro {nombre!r} declara md5 {declarado} y su secuencia da "
                f"{_md5(secuencia)}: el FASTA no es el que emitió la app. Se aborta "
                f"antes de compararlo con ningún plásmido — comparar con un fragmento "
                f"retocado echaría la culpa al montaje."
            )
        registros.append(
            EmittedFragment(name=nombre, sequence=secuencia, declared=dict(campos))
        )

    for linea in str(text).splitlines():
        if linea.startswith(">"):
            cerrar()
            cabecera = linea[1:].split()
            nombre = cabecera[0] if cabecera else ""
            campos = {}
            for trozo in cabecera[1:]:
                if "=" in trozo:
                    clave, valor = trozo.split("=", 1)
                    campos[clave] = valor
            piezas = []
        elif linea.strip():
            piezas.append(linea.strip())
    cerrar()
    if not registros:
        raise ShmirDesignError(
            "El FASTA de fragmentos no trae ningún registro. Se aborta en vez de "
            "devolver «todo correcto» sobre cero comprobaciones."
        )
    return tuple(registros)


# ─── Qué intrón lleva el plásmido, y si el fragmento va ahí ──────────────────
#
# EL GUARDIA QUE DABA PASS A LAS CUATRO CASILLAS. Señalado por el responsable del
# proyecto (2026-09-06): `verify_assembly` aprobaba las cuatro combinaciones de
# fragmento x plasmido receptor. Y no por descuido — **el modulo es el mismo en las dos
# arquitecturas**: misma horquilla, mismos contextos de SGEP, mismos espaciadores.
# Mirando el modulo, una sustitucion cruzada y una correcta son la misma secuencia.
#
# Lo que discrimina son los EXTREMOS, porque los flancos son de intrones distintos. Y no
# valen cinco: hay que medir cuantos hacen falta.

#: Los flancos versionados del casete, que NO dependen de la arquitectura del intron:
#: son del vector. Se derivan de `blocks.PIECES` — nadie los teclea — y son las anclas
#: con las que se localiza el intron en un plasmido que lleva CUALQUIER arquitectura.
#: `splicing.locate_intron` no sirve para esto: busca las dos mitades del MVM.
def _flanco(a: str, b: str) -> str:
    from .blocks import PIECES  # noqa: PLC0415

    return PIECES[a].sequence + PIECES[b].sequence


FLANK_5 = _flanco("MluI", "exon5")
FLANK_3 = _flanco("exon3", "AgeI")

#: Cuantos nucleotidos de cada extremo se comparan. Es el mismo numero que destaca la
#: hoja de pedido, y por el mismo motivo — ver `WHY_FIFTEEN`.
COMPARED_ENDS = 15


def divergence_point(a: str, b: str) -> int | None:
    """En qué nucleótido (1-based) empiezan a diferir dos secuencias. `None` = no difieren.

    Existe para que los números de `WHY_FIFTEEN` se MIDAN y no se afirmen: el día que
    entre un tercer intrón, la longitud que hace falta se vuelve a medir con esto en vez
    de heredarse.
    """
    # zip-ok: trunca al mas corto A PROPOSITO. Se comparan PREFIJOS que pueden medir
    # distinto —el extremo de un intron corto contra el de uno largo—, y lo que se busca
    # es el primer nucleotido en que difieren, que si existe esta dentro del comun. La
    # diferencia de longitud NO se pierde: la trata el `return` de abajo, que devuelve
    # el primer nucleotido que ya no tiene pareja.
    for i, (x, y) in enumerate(zip(a, b), start=1):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b)) + 1


WHY_FIFTEEN = (
    "Se comparan 15 nt de cada extremo y no 5, y está MEDIDO sobre los dos intrones del "
    "registro: los dos donantes empiezan por GTAAG y el contexto exónico aporta otros 5, "
    "así que los primeros 10 nt del fragmento son IDÉNTICOS en las dos arquitecturas y "
    "divergen en el 11. Por el otro extremo el aceptor AG más los 5 del exón dan 8 "
    "iguales, y divergen en el 9. Con 5 nt las dos arquitecturas son indistinguibles; "
    "con 10 también. Los 15 cubren los dos casos con margen, y eso deja de ser una "
    "preferencia. Con un intrón nuevo se vuelve a medir con `divergence_point`."
)

WHY_THE_MODULE_CANNOT_TELL = (
    "El MÓDULO es el mismo en las dos arquitecturas —misma horquilla, mismos contextos "
    "de SGEP, mismos espaciadores—, así que mirándolo una sustitución cruzada y una "
    "correcta son la misma secuencia. Un guardia que se apoye en el módulo da PASS a las "
    "cuatro casillas, y un guardia que aprueba todo no mide lo que su nombre promete."
)

WHY_THE_CHANGE_IS_DECLARED = (
    "Pegar el fragmento del quimérico sobre un plásmido que lleva el MVM ES cómo se "
    "cambia de arquitectura: no es un error. El trabajo de esta comprobación no es "
    "prohibir una casilla, es DECIR EN CUÁL SE ESTÁ para que quien pega confirme que es "
    "la que quería. Por eso el cambio se DECLARA (`architecture_change`), igual que "
    "`--reoptimizar-espaciadores`: una decisión se toma a propósito, no se descubre en "
    "un comprobador."
)


@dataclass(frozen=True)
class IntronInPlasmid:
    """Qué intrón lleva un plásmido, identificado POR SUS EXTREMOS."""

    #: Nombre en el registro. Cadena vacía = ninguno coincide, y NO se adivina.
    name: str
    sequence: str
    empty: bool
    head: str
    tail: str

    @property
    def length(self) -> int:
        return len(self.sequence)

    def describe(self) -> str:
        if not self.name:
            return (
                f"El plásmido lleva un intrón de {self.length} nt cuyos extremos "
                f"({self.head}… / …{self.tail}) NO COINCIDEN con ninguno del registro "
                f"({', '.join(sorted(_registry_ends()))}). No se adivina cuál es: se "
                f"dice lo que hay."
            )
        que = "vacío" if self.empty else "con el módulo dentro"
        return (
            f"El plásmido lleva {self.name} ({self.length} nt, {que}), identificado por "
            f"sus extremos: {self.head}… / …{self.tail}."
        )


def _registry_ends() -> dict[str, tuple[str, str]]:
    """Los extremos de cada intrón del registro, CON el contexto exónico del vector.

    Se derivan del registro y de `blocks.PIECES`; no hay ninguna tabla que mantener. Un
    intrón sin secuencia no aparece: no se puede identificar por unos extremos que no
    tenemos.
    """
    from .blocks import PIECES  # noqa: PLC0415
    from .introns import INTRONS  # noqa: PLC0415

    exon5, exon3 = PIECES["exon5"].sequence, PIECES["exon3"].sequence
    extremos: dict[str, tuple[str, str]] = {}
    for nombre, intron in INTRONS.items():
        if not intron.provided:
            continue
        vacio = intron.empty_sequence
        extremos[nombre] = (
            (exon5 + vacio)[:COMPARED_ENDS],
            (vacio + exon3)[-COMPARED_ENDS:],
        )
    return extremos


def intron_in_plasmid(plasmid: str | bytes) -> IntronInPlasmid:
    """El intrón que lleva un plásmido HOY, sea de la arquitectura que sea.

    Se ancla en los FLANCOS del vector (`MluI+exon5` y `exon3+AgeI`), que son los mismos
    con cualquier intrón dentro, y luego identifica por los extremos. Aborta si los
    flancos no están o no son únicos: sobre otra cosa no se emite ninguna identidad.
    """
    secuencia = plasmid_sequence(plasmid)
    for etiqueta, ancla in (("5'", FLANK_5), ("3'", FLANK_3)):
        cuantas = secuencia.count(ancla)
        if cuantas != 1:
            raise ShmirDesignError(
                f"El flanco {etiqueta} del casete ({ancla}) aparece {cuantas} veces en "
                f"el plásmido y tiene que aparecer UNA. Sin un ancla única no se puede "
                f"decir qué intrón lleva; se aborta en vez de identificar el de otro "
                f"sitio."
            )
    inicio = secuencia.index(FLANK_5) + len(FLANK_5)
    fin = secuencia.index(FLANK_3)
    if fin <= inicio:
        raise ShmirDesignError(
            "En este plásmido el flanco 3' del casete va por delante del 5': eso no "
            "delimita ningún intrón y se aborta."
        )
    from .blocks import PIECES  # noqa: PLC0415

    exon5, exon3 = PIECES["exon5"].sequence, PIECES["exon3"].sequence
    con_exones = exon5 + secuencia[inicio:fin] + exon3
    cuerpo = secuencia[inicio:fin]
    cabeza, cola = con_exones[:COMPARED_ENDS], con_exones[-COMPARED_ENDS:]

    from .introns import INTRONS  # noqa: PLC0415

    for nombre, (h, t) in _registry_ends().items():
        if (cabeza, cola) == (h, t):
            return IntronInPlasmid(
                name=nombre,
                sequence=cuerpo,
                empty=cuerpo == INTRONS[nombre].empty_sequence,
                head=cabeza,
                tail=cola,
            )
    return IntronInPlasmid(
        name="", sequence=cuerpo, empty=False, head=cabeza, tail=cola
    )


# ─── La comprobación ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AssemblyReport:
    """Lo que se ha podido comprobar del plásmido montado, y lo que no."""

    plasmid_name: str
    plasmid_length: int
    plasmid_md5: str
    checks: tuple[FilterResult, ...]
    #: QUÉ pregunta se ha contestado. Los dos informes tienen la misma forma y NO dicen
    #: lo mismo: uno mira el plásmido receptor —«¿va este fragmento aquí?»— y el otro el
    #: ya montado —«¿está dentro lo que emitimos?»—. Un encabezado que no distinga los
    #: dos deja al que lo pega leyendo el informe de la otra pregunta.
    title: str = "El plásmido montado contra lo que emitió la app"

    @property
    def verdict_state(self) -> FilterState:
        if any(r.state is FilterState.FAIL for r in self.checks):
            return FilterState.FAIL
        if any(r.state is FilterState.NOT_RUN for r in self.checks):
            return FilterState.NOT_RUN
        return FilterState.PASS

    def check(self, name: str) -> FilterResult:
        for resultado in self.checks:
            if resultado.name == name:
                return resultado
        disponibles = ", ".join(r.name for r in self.checks)
        raise KeyError(f"No hay comprobación {name!r}; las que hay: {disponibles}.")

    def render(self) -> str:
        lineas = [
            f"═══ {self.title} ═══",
            "",
            f"  Plásmido : {self.plasmid_name}, {self.plasmid_length} pb, "
            f"md5 {self.plasmid_md5}",
            "",
        ]
        for resultado in self.checks:
            lineas.append(f"  [{resultado.state.value}] {resultado.name}")
            lineas.append(f"      {resultado.reason}")
        lineas.extend(["", f"  Veredicto: {self.verdict_state.value}"])
        return "\n".join(lineas)


#: Cuánto contexto se enseña alrededor de lo que se encontró. No sirve para juzgar: es
#: para que quien lea el fallo pueda mirarlo en su propio fichero.
CONTEXT_SHOWN = 20


def verify_assembly(
    plasmid: str | bytes,
    fragments_fasta_text: str,
    *,
    name: str = "el plásmido montado",
    previous_intron: str = "",
) -> AssemblyReport:
    """¿Lleva el plásmido montado EXACTAMENTE el fragmento que emitió la app?

    `previous_intron` es el intrón que había ANTES (vacío = se deriva del registro, el
    del casete parental). Encontrarlo todavía dentro es el fallo real que esto caza: se
    pegó al lado en vez de encima, y el plásmido lleva los dos.
    """
    secuencia = plasmid_sequence(plasmid)
    emitidos = parse_fragments_fasta(fragments_fasta_text)

    presentes = [f for f in emitidos if f.sequence in secuencia]
    ausentes = [f for f in emitidos if f.sequence not in secuencia]

    if ausentes:
        detalle = "; ".join(
            f"{f.name} ({len(f.sequence)} nt, md5 {f.md5}) no aparece"
            for f in ausentes
        )
        presencia = FilterResult(
            name="fragmento_presente",
            state=FilterState.FAIL,
            reason=(
                f"De los {len(emitidos)} fragmento(s) emitidos, {len(ausentes)} NO "
                f"están en {name} ({len(secuencia)} pb): {detalle}. Se dice lo que se "
                f"ha encontrado y no por qué: la comprobación busca la secuencia "
                f"exacta y no puede distinguir una base cambiada de un fragmento "
                f"distinto ni de un plásmido equivocado."
            ),
        )
    else:
        presencia = FilterResult(
            name="fragmento_presente",
            state=FilterState.PASS,
            reason=(
                f"{len(emitidos)} fragmento(s) emitido(s) están en {name} "
                f"({len(secuencia)} pb), letra por letra: "
                + "; ".join(f"{f.name} md5 {f.md5}" for f in emitidos)
                + ". Buscados POR SECUENCIA: ninguna coordenada interviene."
            ),
        )

    repetidos = {
        f.name: secuencia.count(f.sequence) for f in presentes
        if secuencia.count(f.sequence) > 1
    }
    if repetidos:
        unicidad = FilterResult(
            name="fragmento_unico",
            state=FilterState.FAIL,
            reason=(
                f"Hay fragmento(s) que aparecen más de una vez en {name}: "
                + ", ".join(f"{n} × {c}" for n, c in sorted(repetidos.items()))
                + ". Un plásmido con dos copias no es el que se diseñó."
            ),
        )
    elif presentes:
        unicidad = FilterResult(
            name="fragmento_unico",
            state=FilterState.PASS,
            reason=f"Cada fragmento aparece UNA sola vez en {name}.",
        )
    else:
        unicidad = FilterResult(
            name="fragmento_unico",
            state=FilterState.NOT_RUN,
            reason="No se ha encontrado ningún fragmento, así que no hay nada que contar.",
        )

    # BARRE TODO EL REGISTRO, no sólo el que se declare. Antes el valor por defecto era
    # el MVM vacío, así que un plásmido que llevara el QUIMÉRICO detrás daba PASS: el
    # guardia miraba el intrón equivocado y aprobaba. Un centinela que sólo busca lo que
    # ya esperabas no es un centinela.
    from .introns import INTRONS  # noqa: PLC0415

    candidatos: dict[str, str] = {}
    if previous_intron:
        candidatos["el declarado"] = previous_intron
    else:
        candidatos.update(
            {n: i.empty_sequence for n, i in INTRONS.items() if i.provided}
        )
    encontrados = {
        nombre: secuencia.count(vacio)
        for nombre, vacio in candidatos.items()
        if vacio and secuencia.count(vacio)
    }
    if encontrados:
        primero = sorted(encontrados)[0]
        i = secuencia.index(candidatos[primero])
        contexto = secuencia[max(0, i - CONTEXT_SHOWN) : i + CONTEXT_SHOWN]
        previo = FilterResult(
            name="sin_intron_previo",
            state=FilterState.FAIL,
            reason=(
                f"Hay intrón(es) ANTERIOR(es) todavía en {name}: "
                + ", ".join(
                    f"{n} ({len(candidatos[n])} nt, md5 {_md5(candidatos[n])}) × {c}"
                    for n, c in sorted(encontrados.items())
                )
                + f". Contexto del primero: …{contexto}… Si el fragmento también está, "
                f"el plásmido lleva LOS DOS: se pegó al lado en vez de encima. Se dice "
                f"lo que hay; la causa la decide quien mire el fichero."
            ),
        )
    else:
        previo = FilterResult(
            name="sin_intron_previo",
            state=FilterState.PASS,
            reason=(
                f"Ninguno de los intrones vacíos que se han buscado está en {name} "
                f"({', '.join(sorted(candidatos))}): la sustitución los reemplazó en vez "
                f"de añadirse al lado."
            ),
        )

    declarados = [f for f in presentes if f.growth is not None]
    if not declarados:
        crecimiento = FilterResult(
            name="crecimiento",
            state=FilterState.NOT_RUN,
            reason=(
                "Ningún fragmento presente declara cuánto crece el plásmido, así que "
                "no se ha podido cruzar la longitud. NOT_RUN no es PASS."
            ),
        )
    else:
        crecimiento = FilterResult(
            name="crecimiento",
            state=FilterState.PASS,
            reason=(
                f"{name} mide {len(secuencia)} pb. Los fragmentos presentes declaran un "
                f"crecimiento de "
                + ", ".join(f"{f.name} +{f.growth}" for f in declarados)
                + " sobre el casete de referencia: la longitud del montaje se compara "
                "con la del casete DEL QUE SE PARTIÓ, que esta comprobación no tiene "
                "delante — por eso el número se emite y no se juzga."
            ),
        )

    return AssemblyReport(
        plasmid_name=name,
        plasmid_length=len(secuencia),
        plasmid_md5=_md5(secuencia),
        checks=(presencia, unicidad, previo, crecimiento),
    )


def _check_architecture(
    plasmid: str, emitidos, *, architecture_change: bool, name: str
) -> FilterResult:
    """La casilla de la matriz: qué fragmento se pega sobre qué intrón.

    Ver `WHY_THE_MODULE_CANNOT_TELL`, `WHY_FIFTEEN` y `WHY_THE_CHANGE_IS_DECLARED`.
    """
    try:
        lleva = intron_in_plasmid(plasmid)
    except ShmirDesignError as error:
        # rule2-ok: el fallo NO se traga — se convierte en el `FilterResult` con estado
        # NOT_RUN y el mensaje original dentro. NOT_RUN no es PASS, que es justo lo que
        # esta comprobación existe para no dar.
        return FilterResult(
            name="arquitectura",
            state=FilterState.NOT_RUN,
            reason=(
                f"No se ha podido decir qué intrón lleva {name}, así que NO se ha "
                f"comprobado si el fragmento va ahí: {error}"
            ),
        )

    del_fragmento = sorted({f.declared.get("intron", "") for f in emitidos} - {""})
    if len(del_fragmento) != 1:
        return FilterResult(
            name="arquitectura",
            state=FilterState.NOT_RUN,
            reason=(
                f"El FASTA declara {len(del_fragmento)} arquitectura(s) de intrón "
                f"({', '.join(del_fragmento) or 'ninguna'}) y la comparación necesita "
                f"UNA. No se ha comprobado."
            ),
        )
    trae = del_fragmento[0]

    if not lleva.name:
        return FilterResult(
            name="arquitectura",
            state=FilterState.NOT_RUN,
            reason=(
                f"El fragmento trae {trae}. {lleva.describe()} Sin saber qué hay "
                f"debajo no se puede decir si la sustitución es la de la misma "
                f"arquitectura o una cruzada. NOT_RUN no es PASS."
            ),
        )

    misma = lleva.name == trae
    if misma and not architecture_change:
        return FilterResult(
            name="arquitectura",
            state=FilterState.PASS,
            reason=(
                f"MISMA ARQUITECTURA: el fragmento trae {trae}. {lleva.describe()} "
                f"Comparado por los {COMPARED_ENDS} nt de cada extremo, que es lo único "
                f"que distingue las dos. {WHY_THE_MODULE_CANNOT_TELL}"
            ),
        )
    if misma and architecture_change:
        return FilterResult(
            name="arquitectura",
            state=FilterState.FAIL,
            reason=(
                f"Se ha DECLARADO un cambio de arquitectura y no lo hay: el fragmento "
                f"trae {trae}. {lleva.describe()} Se avisa en vez de dejarlo pasar — "
                f"una declaración que no se corresponde con lo que se pega es "
                f"exactamente lo que hace que la siguiente no se lea."
            ),
        )
    if architecture_change:
        return FilterResult(
            name="arquitectura",
            state=FilterState.PASS,
            reason=(
                f"CAMBIO DE ARQUITECTURA DECLARADO: el plásmido lleva {lleva.name} y el "
                f"fragmento trae {trae}. {lleva.describe()} Es la sustitución con la que "
                f"se cambia de intrón, y sale PASS porque se pidió. "
                f"{WHY_THE_CHANGE_IS_DECLARED}"
            ),
        )
    return FilterResult(
        name="arquitectura",
        state=FilterState.FAIL,
        reason=(
            f"SUSTITUCIÓN CRUZADA SIN DECLARAR: el plásmido lleva {lleva.name} y el "
            f"fragmento trae {trae}. {lleva.describe()} Puede ser lo que se quiere —así "
            f"es como se cambia de arquitectura— pero entonces se declara: "
            f"`--cambio-de-arquitectura`. {WHY_THE_CHANGE_IS_DECLARED}"
        ),
    )


def check_before_pasting(
    plasmid: str | bytes,
    fragments_fasta_text: str,
    *,
    architecture_change: bool = False,
    name: str = "el plásmido receptor",
) -> AssemblyReport:
    """ANTES de pegar: ¿va este fragmento en este plásmido?

    `verify_assembly` mira el plásmido YA montado y contesta «¿está dentro lo que
    emitimos?». Esto mira el plásmido de destino y contesta otra pregunta —«¿es éste su
    sitio?»—, que es la que hay que hacerse mientras todavía se puede no pegar.

    Y son dos preguntas de verdad: sobre el montado, el intrón anterior ya no está, así
    que la casilla de la matriz no se puede reconstruir a posteriori.
    """
    secuencia = plasmid_sequence(plasmid)
    emitidos = parse_fragments_fasta(fragments_fasta_text)
    return AssemblyReport(
        plasmid_name=name,
        plasmid_length=len(secuencia),
        plasmid_md5=_md5(secuencia),
        title="ANTES DE PEGAR: ¿va este fragmento en este plásmido?",
        checks=(
            _check_architecture(
                secuencia, emitidos,
                architecture_change=architecture_change, name=name,
            ),
        ),
    )
