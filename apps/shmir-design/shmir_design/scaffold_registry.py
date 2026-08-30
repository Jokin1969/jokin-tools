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
        # EL PLASMIDO DE SGEP NO ESTA EN EL REPOSITORIO, y salio al montar este
        # registro. El 97-mero si esta verificado —contra la publicacion y contra el
        # plegado— y por eso se puede MONTAR; lo que no esta verificado contra un
        # fichero son los CONTEXTOS 5' y 3', que hoy son coordenadas declaradas
        # (1739-1758 y 1856-1875) que ningun fichero del repositorio confirma:
        # `gblock.verify_contexts_against_plasmid` queda en NOT_RUN en toda corrida
        # real, y su test monta un plasmido sintetico de N's con los dos contextos
        # dentro — que prueba el COMPROBADOR, no las coordenadas.
        plasmid="",
        why_missing=(
            "miR-E monta: su 97-mero está verificado contra la publicación y contra el "
            "plegado, y tiene su regla de pasajera propia. Lo que le falta es el "
            "PLÁSMIDO de referencia: SGEP #111170 no está en el directorio, así que los "
            "contextos 5' y 3' siguen siendo coordenadas declaradas que ningún fichero "
            "confirma, y `verify_contexts_against_plasmid` queda en NOT_RUN en toda "
            "corrida real."
        ),
        como_conseguirlo=(
            "El `.dna` o el `.gb` de SGEP #111170. Con él, los contextos de "
            "`blocks.PIECES` —posiciones 1739-1758 y 1856-1875— se contrastan de "
            "verdad en vez de quedarse en NOT_RUN, que es lo que hacen hoy."
        ),
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
            "Hacen falta las COORDENADAS del precursor de 71 nt dentro de #20670, o un "
            "export del plásmido entero con el precursor anotado como feature. La otra "
            "vía que no depende de Addgene es `hairpin.fa` de miRBase, que trae los "
            "precursores y del que hoy sólo tenemos `mature.fa` (los maduros). Con "
            "cualquiera de las dos, la secuencia sale de un fichero y no se teclea."
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
            "MEDIDO sobre las anotaciones del fichero: el único intervalo sin anotar "
            "del casete de expresión son 215 nt en 883..1097, entre el promotor T7 "
            "(863..881) y el cebador BGH-rev (1098..1115), donde por fuerza vive el "
            "inserto. Eso lo dicen las propias anotaciones y no una secuencia construida "
            "por nosotros, pero NO delimita el andamio dentro de esos 215 nt. Hace falta "
            "un export con el inserto "
            "anotado, o `hairpin.fa` de miRBase para localizar el precursor de miR-155 "
            "por su secuencia REAL —de fichero— dentro de ese intervalo."
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
            "FALTA `hairpin.fa` de miRBase (los precursores; el que hay es `mature.fa`, "
            "los maduros). Con él salen `mmu-mir-451a` y su geometría, y con eso se "
            "pueden correr los tres cálculos. Sin él, el pre-miR-451 nativo —el valor "
            "esperado que viene de la biología y no del código— no existe, y una "
            "comparación sin referencia no dice nada."
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
