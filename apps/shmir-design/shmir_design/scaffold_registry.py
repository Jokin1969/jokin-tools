"""Registro de ANDAMIOS de primera clase, con la disciplina del de intrones.

**Por qué existe.** Cambiar de andamio no es sustituir un flanco: es rediseñar el módulo
entero. Hasta hoy `blocks.PIECES` sólo tenía miR-E y `verify_contexts_against_plasmid`
comparaba contra el plásmido de SGEP; con cuatro andamios sobre la mesa eso deja de valer.

**Lo que se registra por andamio**, y las cuatro cosas son independientes:

1. la SECUENCIA verificada, extraída de un fichero — nunca tecleada (regla 1);
2. los CONTEXTOS 5' y 3', derivados de las coordenadas de la feature;
3. la REGLA DE PASAJERA con su criterio, que es **propiedad del andamio** y no una
   constante global;
4. el PLÁSMIDO de referencia con su md5.

**La regla de la pasajera es distinta en cada andamio, y está medido cuánto.** En miR-E
es revcomp de la guía con desapareamiento en la posición 1, elegido **plegando contra
SGEP**. En miR-30a, la que emite miRarchitect es
`revcomp(guía)[0:9] + revcomp(guía)[11:22] + "GC"` — dos nucleótidos borrados tras la
posición 9 y un `GC` terminal. No se parecen en nada. Por eso un andamio sin su propia
regla **no monta nada**: montarlo con la prestada saldría con la forma correcta, que es
peor que no salir.

**Estado**: `PASS` sólo con secuencia verificada Y regla propia. Lo demás es `NOT_RUN`
—no se ha corrido nada con ese andamio—, nunca `FAIL` (regla 3).

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .errors import ShmirDesignError
from .filters import FilterState
from .scaffold import SGEP_SCAFFOLD, PASSENGER_RULE_SOURCE, ScaffoldSpec


@dataclass(frozen=True)
class PassengerRule:
    """Cómo sale la pasajera EN ESTE ANDAMIO, y de dónde salió ese criterio."""

    name: str
    #: El criterio, en prosa. No es decorado: es lo que distingue una regla derivada de
    #: una transcrita, y lo unico que permite decidir si vale para otro andamio.
    criterion: str
    #: De donde se derivo: el plasmido o la publicacion contra la que se pleg'o.
    derived_from: str


@dataclass(frozen=True)
class RegisteredScaffold:
    """Un andamio del registro. Lo que tiene se DERIVA; no se declara."""

    name: str
    description: str
    #: El andamio en si. `None` mientras no haya secuencia verificada de fichero.
    spec: ScaffoldSpec | None = None
    passenger_rule: PassengerRule | None = None
    #: Plasmido de referencia y su md5 de SECUENCIA (no el del fichero: un export nuevo
    #: de SnapGene cambia las cabeceras y no cambia el ADN).
    plasmid: str = ""
    plasmid_md5: str = ""
    #: (clave, etiqueta) de la feature que traeria el ANDAMIO. `None` = el plasmido esta
    #: y NO lo anota.
    scaffold_feature: tuple[str, str] | None = None
    #: (clave, etiqueta) de una feature relacionada que el plasmido SI anota, cuando no
    #: es el andamio entero. Se registra porque es un dato verificado, no porque sirva
    #: para montar nada.
    loop_feature: tuple[str, str] | None = None
    why_missing: str = ""
    como_conseguirlo: str = ""
    #: Precedente MEDIDO, cuando lo hay. No es una regla adoptable.
    precedent: str = ""

    @property
    def sequence_verified(self) -> bool:
        """Se DERIVA de si hay `spec` verificado. Nunca es un campo declarado: eso ya
        dio un PASS falso una vez, en el intrón quimérico."""
        return self.spec is not None and self.spec.verified

    @property
    def state(self) -> FilterState:
        """PASS = se puede MONTAR. Son dos ejes distintos y conviene no fundirlos.

        Montar pide secuencia verificada y regla propia. El plásmido de referencia
        verifica otra cosa —los CONTEXTOS— y su ausencia deja
        `verify_contexts_against_plasmid` en NOT_RUN sin impedir el montaje: es
        exactamente el caso de miR-E hoy. Fundir los dos ejes daría un `mir_e` en
        NOT_RUN y la app dejaría de emitir lo único que hoy emite bien.
        """
        if self.sequence_verified and self.passenger_rule is not None:
            return FilterState.PASS
        return FilterState.NOT_RUN

    @property
    def missing(self) -> list[str]:
        """Qué le falta, DERIVADO de lo que tiene."""
        falta = []
        if not self.sequence_verified:
            falta.append("secuencia verificada del andamio")
        if self.passenger_rule is None:
            falta.append("regla de pasajera propia, con su criterio")
        if not self.plasmid:
            falta.append("plásmido de referencia (los contextos quedan sin contrastar)")
        elif not self.plasmid_md5:
            falta.append("md5 del plásmido de referencia")
        return falta

    @property
    def has(self) -> list[str]:
        tiene = []
        if self.plasmid:
            tiene.append(f"plásmido {self.plasmid} (md5 {self.plasmid_md5[:8]}…)")
        if self.loop_feature is not None:
            tiene.append(f"feature «{self.loop_feature[1]}» verificada del fichero")
        if self.sequence_verified:
            tiene.append(f"andamio verificado ({self.spec.length} nt con guía de 22)")
        if self.passenger_rule is not None:
            tiene.append(f"regla de pasajera: {self.passenger_rule.name}")
        return tiene


#: Los md5 son de la SECUENCIA leida del fichero, calculados al depositarlo. Estan aqui
#: para que un fichero cambiado se note; no son una fuente de secuencia.
_MD5_20670 = "14eab980202d1256a5356374000b7d2c"
_MD5_78126 = "1991fb428c67a2407e027cbd0c1319e8"
_MD5_111170 = "b15d809181d72c78c815755442c188fd"


SCAFFOLDS: dict[str, RegisteredScaffold] = {
    "mir_e": RegisteredScaffold(
        name="mir_e",
        description=(
            "miR-E / SGEP, el andamio de hoy. Es el único completo: 97-mero verificado "
            "y regla de pasajera derivada de plegar contra el plásmido."
        ),
        spec=SGEP_SCAFFOLD,
        passenger_rule=PassengerRule(
            name="revcomp con desapareamiento en la posición 1, elegido por PLEGADO",
            criterion=PASSENGER_RULE_SOURCE,
            derived_from="SGEP #111170 y LT3GEPIR #111177",
        ),
        # CERRADO 2026-08-30: llego SGEP #111170 y los dos contextos declarados
        # COINCIDEN EXACTAMENTE en sus coordenadas — `contexto5` en 1739-1758 y
        # `contexto3` en 1856-1875, contrastados contra la secuencia del fichero. Hasta
        # hoy eran coordenadas que ningun fichero confirmaba: el test las probaba contra
        # un plasmido SINTETICO de N's con los dos contextos dentro, que prueba el
        # COMPROBADOR y no las coordenadas (principio nº 18). Ahora hay test contra el
        # plasmido real.
        plasmid="addgene_111170.gb",
        plasmid_md5=_MD5_111170,
        loop_feature=("ncRNA", "miR-30a loop"),
    ),
    "mir30_original": RegisteredScaffold(
        name="mir30_original",
        description=(
            "miR-30a original, el andamio del que deriva miR-E. Dos hebras compitiendo, "
            "así que la asimetría sigue significando lo mismo y el panel de diez valdría "
            "tal cual — en cuanto haya secuencia."
        ),
        plasmid="addgene_20670.gb",
        plasmid_md5=_MD5_20670,
        # EL HALLAZGO, y por eso `scaffold_feature` es None y no una coordenada: el
        # fichero anota el LOOP, 15 nt, y su propia nota dice que es «loop from the
        # 71-nt precursor». El andamio —tallo, brazos, flancos— no esta anotado.
        scaffold_feature=None,
        loop_feature=("ncRNA", "miR-30a loop"),
        why_missing=(
            "El plásmido #20670 está depositado y verificado, pero NO TRAE EL ANDAMIO "
            "COMO FEATURE: la única feature de miARN que anota es «miR-30a loop», 15 nt "
            "en 154..168, y su propia nota dice que es el loop del precursor de 71 nt. "
            "El andamio —tallo, brazos y flancos— no está anotado en ninguna parte del "
            "fichero. Buscarlo por secuencia contra una que hubiéramos construido "
            "nosotros es exactamente lo que prohíbe la regla 1. Además, el export son "
            "771 pb LINEALES con 10 bases ambiguas desde la posición 710: es un "
            "fragmento de baja calidad en el extremo, no el plásmido entero."
        ),
        como_conseguirlo=(
            "MEDIDO, y el resultado es favorable: centrando el loop anotado en una "
            "ventana de 71 nt —126..196, DERIVADA de las coordenadas del loop, no "
            "adivinada— sale UNA horquilla de ΔG −34,70 kcal/mol con el 73 % de las "
            "bases emparejadas y UN solo bucle terminal, contra el control positivo de "
            "SGEP (−35,10 y 82 %, también un bucle) medido con el mismo método. Las 10 "
            "bases ambiguas del fichero empiezan en la 710, fuera de la ventana. Eso NO "
            "lo declara andamio —sigue sin estar anotado— pero da base para pedir la "
            "anotación del precursor o un export del plásmido entero. La otra vía es "
            "`hairpin.fa` de miRBase. Con cualquiera de las dos, de fichero y sin teclear."
        ),
        precedent=(
            "PRECEDENTE MEDIDO, y no se adopta: la pasajera que emite miRarchitect para "
            "miR-30a es `revcomp(guía)[0:9] + revcomp(guía)[11:22] + \"GC\"` — dos "
            "nucleótidos borrados tras la posición 9 y un `GC` terminal—, verificada "
            "contra las 26 filas del export en `mirarchitect.passenger_of`. Está ahí "
            "para PODER DESCARTARLA, no para diseñar: es la medida del tamaño de la "
            "diferencia entre andamios, no una regla que se pueda prestar."
        ),
    ),
    "mir155": RegisteredScaffold(
        name="mir155",
        description=(
            "miR-155, arquitectura de tallo distinta. También con dos hebras "
            "compitiendo: la asimetría sigue aplicando."
        ),
        plasmid="addgene_78126.gb",
        plasmid_md5=_MD5_78126,
        scaffold_feature=None,
        loop_feature=None,
        why_missing=(
            "El plásmido #78126 está depositado, completo (5504 pb circulares, sin "
            "bases ambiguas) y verificado por md5 — pero NO ANOTA NINGUNA FEATURE DE "
            "miARN. Sus 34 features son todas del esqueleto de pcDNA3.1: CMV, T7, BGH "
            "poli(A), f1 ori, SV40, NeoR/KanR, lac, ori y AmpR. Que el título diga "
            "«miR155 in pcDNA3.1» y la DEFINITION «Mammalian expression of miR155» no "
            "es una anotación: es un texto. El inserto no está delimitado en el fichero."
        ),
        como_conseguirlo=(
            "MEDIDO, y el resultado DESCARTA este fichero: el único intervalo sin anotar "
            "del casete son 215 nt en 883..1097, entre el promotor T7 (863..881) y el "
            "cebador BGH-rev (1098..1115). Plegando TODAS sus ventanas de 71 nt —el "
            "tamaño del control positivo— la mejor da ΔG −26,00 con el 65 % emparejado, "
            "contra −35,10 y 82 % del control. Sí cierra un solo bucle, o sea que "
            "topológicamente es una horquilla, y eso no significa nada: cualquier tramo "
            "rico en GC pliega algo. Lo que decide es otra medida: ese intervalo contiene "
            "15 DIANAS DE RESTRICCIÓN canónicas distintas, una cada 12,6 nt, con una "
            "densidad 105 veces la del resto del plásmido. Es un POLILINKER VACÍO, no un "
            "inserto. Hace falta OTRO plásmido, o `hairpin.fa` para saber qué buscar."
        ),
    ),
    "mir451": RegisteredScaffold(
        name="mir451",
        description=(
            "miR-451, y NO se procesa como los demás: Drosha da un pre-miR de ~42 nt "
            "con el tallo demasiado corto para Dicer, Ago2 lo carga entero y corta él "
            "mismo el brazo 3'. Sin Dicer y SIN HEBRA PASAJERA — el brazo 3' es la "
            "complementaria de la propia guía. HIPÓTESIS DECLARADA, no criterio "
            "validado: como andamio de expresión está mucho menos caracterizado que "
            "miR-E, y lo que se calcule con él es mecanismo aplicado."
        ),
        why_missing=(
            "No hay plásmido ni fichero: falta la secuencia del pre-miR-451 nativo, que "
            "es a la vez el andamio Y la referencia contra la que se comparan los diez "
            "candidatos. `mature.fa` trae `mmu-miR-451a-5p` —el MADURO— y eso no basta: "
            "para montar la geometría del pre-miR hace falta el PRECURSOR. Reconstruirlo "
            "a partir del maduro es exactamente lo que prohíbe la regla 1."
        ),
        como_conseguirlo=(
            "FALTA `hairpin.fa` de miRBase — los PRECURSORES; el que hay es `mature.fa`, "
            "los maduros. Misma fuente (mirbase.org → Downloads) y **la misma release**: "
            "hoy el manifiesto declara la 23 para `mature.fa` y "
            "`mirbase_release.comprobar_release` ABORTA si no coinciden. No es una "
            "recomendación: entre releases miRBase añade, retira y RENOMBRA entradas, así "
            "que un maduro buscado dentro de un precursor de otra versión puede no "
            "aparecer o aparecer donde no toca — y eso no daría un error, daría una "
            "geometría plausible. Si sólo hay una release más nueva, se reemplazan LOS "
            "DOS a la vez. Con él salen `mmu-mir-451a` y su geometría, y con eso corren "
            "los tres cálculos; sin él, el pre-miR-451 nativo —el valor esperado que "
            "viene de la biología y no del código— no existe, y una comparación sin "
            "referencia no dice nada. De paso da la vía que no depende de Addgene para "
            "localizar los precursores de miR-30a y miR-155 en sus plásmidos, por su "
            "secuencia REAL en vez de por una construida por nosotros (regla 1)."
        ),
    ),
}


def require_verified(name: str) -> RegisteredScaffold:
    """El GUARDIA: no se monta un módulo con un andamio incompleto.

    Montarlo con la regla de pasajera de otro andamio saldría **con la forma correcta**,
    que es peor que no salir — la misma razón por la que `VECTOR_SPECIES` no se
    parametriza. Aborta diciendo qué falta, no sólo que falta.
    """
    andamio = SCAFFOLDS.get(name)
    if andamio is None:
        raise ShmirDesignError(
            f"No hay ningún andamio {name!r} en el registro; los que hay son "
            f"{', '.join(sorted(SCAFFOLDS))}. Se aborta."
        )
    if andamio.state is FilterState.PASS:
        return andamio
    raise ShmirDesignError(
        f"El andamio {name!r} está en NOT_RUN y no se puede montar un módulo con él. "
        f"Le falta: {'; '.join(andamio.missing)}. {andamio.why_missing} "
        f"QUÉ LO CERRARÍA: {andamio.como_conseguirlo}"
    )


def inventory() -> list[dict]:
    """Qué tiene y qué le falta a cada andamio. Las dos columnas, derivadas."""
    return [
        {
            "andamio": nombre,
            "estado": andamio.state.value,
            "descripcion": andamio.description,
            "tiene": andamio.has,
            "falta": andamio.missing,
            "por_que": andamio.why_missing,
            "como": andamio.como_conseguirlo,
            "precedente": andamio.precedent,
        }
        for nombre, andamio in SCAFFOLDS.items()
    ]


# ═══════ DÓNDE CAE EL ANDAMIO EN SU PLÁSMIDO: derivado, no tecleado ═══════
#
# **El fallo que cierra.** `gblock.verify_contexts_against_plasmid` leia el plasmido en
# `1739-1758` y `1856-1875` —COORDENADAS ESCRITAS— y comparaba lo que hubiera ahi con
# nuestros contextos. Eso comprueba menos de lo que parece:
#
#   - si las coordenadas estuvieran corridas, la comprobacion fallaria contra un plasmido
#     CORRECTO, y el arreglo obvio seria mover las coordenadas hasta que cuadraran —con lo
#     que pasaria siempre y no comprobaria nada;
#   - y un numero escrito NO PUEDE VALIDAR el fichero del que salio (principio nº 13).
#
# **Las dos vias, y tienen que coincidir.** El ANCLA es la anotacion del propio fichero
# —la feature que el andamio declara en `loop_feature`— y el andamio se localiza POR
# SECUENCIA a su alrededor; se exige que la anotacion caiga DENTRO de lo localizado. La
# anotacion dice donde mirar y la secuencia dice que hay; si discrepan, una de las dos
# esta mal y no se elige por nuestra cuenta.
#
# **Los contextos son lo que FLANQUEA al 97-mero**, y su longitud sale de la del propio
# contexto del modulo — que es la pregunta de verdad: ¿lo que nuestro modulo lleva como
# contexto es lo que SGEP tiene ahi de forma nativa?
#
# Las coordenadas dejan de ser una ENTRADA y pasan a ser un RESULTADO.


@dataclass(frozen=True)
class PlasmidAnchor:
    """Dónde cae el andamio dentro de su plásmido, todo DERIVADO del fichero."""

    scaffold: str
    plasmid: str
    #: (inicio, fin) 1-based inclusivos del 97-mero completo: flanco 5' → flanco 3'.
    scaffold_span: tuple[int, int]
    #: Lo que la ANOTACIÓN del fichero dice, para poder contrastarlo. `None` si el
    #: andamio no declara ninguna feature de la que anclarse.
    annotated_loop: tuple[int, int] | None
    context_5: str
    context_5_span: tuple[int, int]
    context_3: str
    context_3_span: tuple[int, int]

    def describe(self) -> list[str]:
        return [
            f"{self.scaffold} en su plásmido ({len(self.plasmid)} pb):",
            f"  andamio    {self.scaffold_span[0]}-{self.scaffold_span[1]}"
            + (
                f"  (anotación «loop» {self.annotated_loop[0]}-{self.annotated_loop[1]},"
                f" dentro)"
                if self.annotated_loop
                else "  (sin feature anotada de la que anclarse)"
            ),
            f"  contexto 5' {self.context_5_span[0]}-{self.context_5_span[1]}  "
            f"{self.context_5}",
            f"  contexto 3' {self.context_3_span[0]}-{self.context_3_span[1]}  "
            f"{self.context_3}",
        ]


def _unica(secuencia: str, aguja: str, *, que: str, donde: str) -> tuple[int, int]:
    """Dónde está `aguja`, exigiendo que esté UNA sola vez. 1-based inclusivo."""
    encontradas = []
    desde = 0
    while True:
        i = secuencia.find(aguja, desde)
        if i < 0:
            break
        encontradas.append(i + 1)
        desde = i + 1
    if not encontradas:
        raise ShmirDesignError(
            f"{donde}: no aparece {que} ({len(aguja)} nt). Se aborta: sin él no se sabe "
            f"dónde está el andamio, y buscarlo de otra forma sería elegir un sitio por "
            f"nuestra cuenta."
        )
    if len(encontradas) > 1:
        raise ShmirDesignError(
            f"{donde}: {que} aparece {len(encontradas)} veces (en "
            f"{', '.join(str(p) for p in encontradas)}). Elegir una sería inventarse "
            f"cuál; se aborta."
        )
    inicio = encontradas[0]
    return inicio, inicio + len(aguja) - 1


def anchor_scaffold(entry: "RegisteredScaffold", text: str, *,
                    context_length: int) -> PlasmidAnchor:
    """Localiza el andamio en su plásmido y DERIVA sus contextos. Ver el bloque de arriba.

    `text` es el GenBank entero. `context_length` es lo que mide el contexto del módulo:
    la pregunta es si ESE tramo es el nativo del plásmido, así que la longitud la pone
    quien pregunta y no hay ningún número escrito aquí.
    """
    from .genbank import parse_plasmid_feature  # noqa: PLC0415

    if entry.spec is None:
        raise ShmirDesignError(
            f"El andamio {entry.name!r} no tiene secuencia verificada, así que no hay "
            f"nada que localizar en su plásmido. {entry.why_missing or ''}".strip()
        )
    if entry.loop_feature is None:
        raise ShmirDesignError(
            f"El andamio {entry.name!r} no declara ninguna feature de la que anclarse en "
            f"su plásmido. Buscarlo sólo por secuencia dejaría la anotación del fichero "
            f"sin contrastar, que es justo la mitad que hace que esto valga."
        )

    clave, etiqueta = entry.loop_feature
    anotada = parse_plasmid_feature(
        text, key=clave, label=etiqueta, source=str(entry.plasmid or "GenBank")
    )
    plasmido = anotada.plasmid
    donde = f"{entry.plasmid or 'el plásmido'} de {entry.name}"

    flanco5 = _unica(plasmido, entry.spec.flank5, que="el flanco 5' del andamio", donde=donde)
    flanco3 = _unica(plasmido, entry.spec.flank3, que="el flanco 3' del andamio", donde=donde)
    if flanco3[0] <= flanco5[1]:
        raise ShmirDesignError(
            f"{donde}: el flanco 3' empieza en {flanco3[0]} y el 5' acaba en "
            f"{flanco5[1]}, o sea que van al revés. Se aborta en vez de emitir un "
            f"intervalo dado la vuelta."
        )
    span = (flanco5[0], flanco3[1])

    # LA ANOTACION TIENE QUE CAER DENTRO. Es lo que ata las dos vias: si el fichero
    # anota el loop en otro sitio, o el andamio localizado no lo contiene, una de las
    # dos esta mal y no se elige por nuestra cuenta.
    if not (span[0] < anotada.start and anotada.end < span[1]):
        raise ShmirDesignError(
            f"{donde}: la feature {clave} «{etiqueta}» está anotada en "
            f"{anotada.start}-{anotada.end} y el andamio localizado por secuencia va de "
            f"{span[0]} a {span[1]}: la anotación NO cae dentro. Una de las dos está "
            f"mal y no se elige por nuestra cuenta. Se aborta."
        )

    if context_length <= 0:
        raise ShmirDesignError(
            "Un contexto de longitud cero no es un contexto: se aborta en vez de "
            "devolver dos cadenas vacías que cuadrarían con cualquier cosa."
        )
    if span[0] - 1 < context_length:
        raise ShmirDesignError(
            f"{donde}: el andamio empieza en {span[0]} y no caben {context_length} nt "
            f"de contexto por delante. Se aborta en vez de dar menos sin decirlo."
        )
    if span[1] + context_length > len(plasmido):
        raise ShmirDesignError(
            f"{donde}: el andamio acaba en {span[1]} de {len(plasmido)} y no caben "
            f"{context_length} nt de contexto por detrás. Se aborta."
        )
    return PlasmidAnchor(
        scaffold=entry.name,
        plasmid=plasmido,
        scaffold_span=span,
        annotated_loop=(anotada.start, anotada.end),
        context_5=plasmido[span[0] - 1 - context_length:span[0] - 1],
        context_5_span=(span[0] - context_length, span[0] - 1),
        context_3=plasmido[span[1]:span[1] + context_length],
        context_3_span=(span[1] + 1, span[1] + context_length),
    )
