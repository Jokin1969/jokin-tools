"""La matriz INTRÓN × ANDAMIO: los dos bloques no son independientes.

**El problema que resuelve.** 3 intrones × 4 andamios se venían tratando como 12
combinaciones independientes. No lo son: `mvm_sin_criptico` existe **sólo** para romper
el `GTGAGCG` del flanco 5' de miR-E, así que con un andamio que no lleve ese motivo esa
variante no resuelve nada — es la misma construcción con otro nombre.

**Cómo se busca**, y es lo que separa esto de una tabla de familias: los motivos se
buscan en la **secuencia real del módulo montado**, y el criterio es el mismo con el que
se cazó el `GTGAGCG` — el contexto de donante se puntúa contra el **donante legítimo del
propio intrón**, que es la referencia interna. Ningún umbral traído de fuera.

**Las tres preguntas, y van en las dos direcciones:**

1. ¿Qué donantes crípticos aporta el andamio? No sólo el que ya conocemos: cualquier GT
   del módulo que empate con el legítimo.
2. ¿Aporta un ACEPTOR utilizable? Un `AG` con tracto de pirimidinas dentro del módulo
   permitiría un empalme que corta **por dentro de la horquilla**. Se compara con el
   tracto del aceptor legítimo del mismo intrón.
3. ¿Aporta un PUNTO DE RAMIFICACIÓN competidor? Es el peor caso: con donante, punto y
   aceptor los tres dentro, el módulo define **un intrón propio**.

**Lo que NO se hace**: evaluar por analogía un andamio sin secuencia verificada. Van a
`NOT_RUN` con el nombre del fichero que falta.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

from .filters import FilterState
from .introns import INTRONS
from .scaffold_registry import SCAFFOLDS

#: La ventana punto→aceptor, la misma que usan los intrones. No se redeclara aqui: se
#: importa, para que no puedan separarse.
from .splicing import BRANCH_POINT_WINDOW  # noqa: E402

COMO_SE_BUSCA = (
    "Los motivos se buscan en la SECUENCIA REAL del módulo montado, nunca por familia ni "
    "por analogía con miR-30. El contexto de donante se puntúa contra el DONANTE "
    "LEGÍTIMO del propio intrón —referencia interna, no un umbral de fuera— con el mismo "
    "criterio que cazó el GTGAGCG. Lo que este análisis NO PUEDE HACER, declarado: no "
    "dice cuál de dos donantes gana, que eso no lo dice la secuencia; no evalúa un "
    "andamio sin secuencia verificada, ni siquiera «probablemente como miR-30»; y sus "
    "hallazgos dentro de los brazos DEPENDEN DE LA GUÍA —otra guía da otros—, mientras "
    "que los del flanco 5', el loop y el flanco 3' viajan con cualquier candidato."
)

#: LAS DOS FRASES VAN JUNTAS, y por eso es una sola constante: separarlas es lo que
#: convierte un hallazgo en un riesgo cerrado que no lo está.
LO_QUE_EL_ACEPTOR_NO_CIERRA = (
    "Que no haya ningún aceptor utilizable DENTRO del módulo cierra una familia concreta: "
    "los empalmes que cortarían por dentro de la horquilla. NO CIERRA EL RIESGO DEL "
    "DONANTE CRÍPTICO, y es lo importante: ese donante NO NECESITA un aceptor críptico. "
    "El aceptor LEGÍTIMO del intrón está aguas abajo y es perfectamente bueno, así que un "
    "empalme desde el críptico hasta él deja los primeros nt del intrón dentro del mRNA — "
    "la banda INTERMEDIA, la que se confunde en un gel con la correcta. Leer «no hay "
    "aceptor utilizable» a solas suena a riesgo cerrado y no lo es."
)

#: Por que el criptico compite, en un numero que se entiende sin conocer el proyecto.
POR_QUE_COMPITE = (
    "El donante críptico no es «un GT sospechoso»: con el criterio de consenso de "
    "donante EMPATA con el donante legítimo del propio intrón — los dos puntúan 5 sobre "
    "5. Ésa es la justificación retrospectiva de que `mvm_sin_criptico` exista, y no "
    "necesita ningún umbral traído de fuera: la referencia es el donante bueno de la "
    "misma construcción."
)

#: EL METODO del orden, y aplica a los tres andamios que faltan.
ORDEN_ANTES_QUE_PRESENCIA = (
    "PRESENCIA SIN GEOMETRÍA NO SIGNIFICA NADA. Un YTNAY dentro del módulo no es un punto "
    "de ramificación competidor por estar: para serlo tiene que caer ENTRE un donante y un "
    "aceptor, y a la distancia del punto al aceptor que usan los intrones. En miR-E hay un "
    "YTNAY y va AGUAS ARRIBA del donante críptico —el orden contrario al que haría falta—, "
    "así que no define nada. El mismo método se aplicará a miR-30 original, miR-155 y "
    "miR-451 cuando tengan secuencia: contar motivos sin comprobar el orden habría dado "
    "tres falsos positivos."
)

REDUNDANCIA = (
    "Un intrón cuya única diferencia con otro es romper un motivo que ESE ANDAMIO NO "
    "TIENE es la misma construcción con otro nombre. Se MARCA y no se elimina: la "
    "decisión de no sintetizarla es de quien diseña, no del programa."
)


def _piezas_del_modulo(bloque, andamio) -> list[tuple[str, int, int]]:
    """Dónde empieza y acaba cada pieza dentro del módulo. Derivado de sus longitudes."""
    from .blocks import PIECES

    horquilla = bloque.hairpin.sequence
    inicio = bloque.module.find(horquilla) + 1
    especificacion = andamio.spec
    brazo = (len(horquilla) - len(especificacion.flank5) - len(especificacion.loop)
             - len(especificacion.flank3)) // 2
    tramos = [
        ("NheI", len(PIECES["NheI"].sequence)),
        ("contexto5", len(PIECES["contexto5"].sequence)),
    ]
    interior = [
        ("flanco5", len(especificacion.flank5)),
        ("brazo_pasajera" if especificacion.guide_arm == "3p" else "brazo_guia", brazo),
        ("loop", len(especificacion.loop)),
        ("brazo_guia" if especificacion.guide_arm == "3p" else "brazo_pasajera", brazo),
        ("flanco3", len(especificacion.flank3)),
    ]
    tramos.extend(interior)
    tramos.extend([("contexto3", len(PIECES["contexto3"].sequence)),
                   ("SacI", len(PIECES["SacI"].sequence))])
    salida, cursor = [], 0
    for nombre, largo in tramos:
        salida.append((nombre, cursor + 1, cursor + largo))
        cursor += largo
    del inicio
    return salida


#: Las piezas cuyo contenido NO depende de la guia. Un motivo que caiga aqui viaja con
#: cualquier candidato; uno de los brazos, no.
_DEL_ANDAMIO = ("NheI", "contexto5", "flanco5", "loop", "flanco3", "contexto3", "SacI")


def _pieza_de(posicion: int, piezas) -> str:
    for nombre, desde, hasta in piezas:
        if desde <= posicion <= hasta:
            return nombre
    return "?"


def _tracto(secuencia: str, posicion: int) -> int:
    """Pirimidinas CONTIGUAS inmediatamente aguas arriba. Contiguas, no porcentaje."""
    cuantas, indice = 0, posicion - 1
    while indice >= 0 and secuencia[indice] in "CT":
        cuantas += 1
        indice -= 1
    return cuantas


def _ytnay(secuencia: str) -> list[tuple[int, str]]:
    """YTNAY anclado en la A, el mismo motivo calibrado que usan los intrones."""
    return [
        (i + 1, secuencia[i : i + 5])
        for i in range(len(secuencia) - 4)
        if secuencia[i] in "CT"
        and secuencia[i + 1] == "T"
        and secuencia[i + 3] == "A"
        and secuencia[i + 4] in "CT"
    ]


def fila(intron: str, andamio: str, *, guide: str) -> dict:
    """Una celda de la matriz. `NOT_RUN` sin secuencia verificada, y dice qué falta."""
    from .intron_design import DONOR_CONSENSUS, _donor_score

    registrado = SCAFFOLDS[andamio]
    entrada = INTRONS[intron]
    base = {
        "intron": intron,
        "andamio": andamio,
        "estado": registrado.state.value,
        "falta": "; ".join(registrado.missing),
        "donantes": None,
        "aceptores": None,
        "ramificaciones": None,
        "redundante": None,
        "intron_autodefinido": None,
        "score_legitimo": None,
        "tracto_legitimo": None,
        "mejor_tracto": None,
        "longitud_modulo": None,
        "longitud_intron": None,
        "donante_a_punto": None,
        "causa": "",
        "como": COMO_SE_BUSCA,
    }
    if registrado.state is not FilterState.PASS:
        # NO se declara nada sobre sus motivos. «No se ha mirado» no es «no tiene».
        base["causa"] = "andamio"
        base["falta"] = (
            f"{'; '.join(registrado.missing)}. {registrado.como_conseguirlo}"
        )
        return base

    # LA SEGUNDA CAUSA DE `NOT_RUN`, y no es la del andamio: hay intrones que no se
    # pueden montar con NINGUNO. Fundir las dos en un solo NOT_RUN diria «falta un
    # fichero de andamio» sobre algo que ningun fichero de andamio arregla. El motivo lo
    # da el propio intron —no se transcribe aqui— y son dos distintos:
    #
    #   · `mvm_sin_criptico` se DISEÑA por candidato y hoy el primer paso EMPATA, asi
    #     que la app no elige y no hay secuencia;
    #   · `intron_quimerico` llega ENTERO de la anotacion de su plasmido y no tiene
    #     declarados sus puntos de insercion, asi que no se sabe DONDE va el modulo.
    if not entrada.provided:
        base["estado"] = FilterState.NOT_RUN.value
        base["causa"] = "intron"
        base["falta"] = (
            f"El intrón {intron!r} no tiene secuencia en esta corrida, así que no se "
            f"puede montar con NINGÚN andamio: {entrada.why_missing}"
        )
        return base
    if entrada.raw_sequence:
        base["estado"] = FilterState.NOT_RUN.value
        base["causa"] = "intron"
        base["falta"] = (
            f"El intrón {intron!r} llega ENTERO y no tiene declarados sus puntos de "
            f"inserción, así que no se puede montar un módulo dentro con NINGÚN "
            f"andamio. Esto no lo arregla ningún fichero de andamio: hace falta declarar "
            f"dónde va el módulo dentro de ese intrón."
        )
        return base

    from .blocks import build_block

    bloque = build_block(guide=guide, scaffold=registrado.spec, available=False)
    modulo = bloque.module
    piezas = _piezas_del_modulo(bloque, registrado)
    elementos = entrada.elements(modulo)
    montado = entrada.with_module(modulo)

    ancho = len(DONOR_CONSENSUS) + 2
    contexto_legitimo = montado[
        elementos.donor.start - 1 : elementos.donor.start - 1 + ancho
    ]
    score_legitimo = _donor_score(contexto_legitimo)

    donantes = []
    for i in range(len(modulo) - ancho + 1):
        if modulo[i : i + 2] != "GT":
            continue
        motivo = modulo[i : i + ancho]
        score = _donor_score(motivo)
        if score < score_legitimo:
            continue
        pieza = _pieza_de(i + 1, piezas)
        donantes.append({
            "posicion": i + 1, "motivo": motivo, "score": score, "pieza": pieza,
            "independiente_de_la_guia": pieza in _DEL_ANDAMIO,
        })

    tracto_legitimo = len(elementos.ppt.sequence)
    tractos = [
        (i + 1, _tracto(modulo, i))
        for i in range(len(modulo) - 1)
        if modulo[i : i + 2] == "AG"
    ]
    mejor_tracto = max((t for _, t in tractos), default=0)
    aceptores = [
        {"posicion": p, "tracto": t, "pieza": _pieza_de(p, piezas)}
        for p, t in tractos
        if t >= tracto_legitimo
    ]

    ramas = [
        {"posicion": p, "motivo": m, "pieza": _pieza_de(p, piezas)}
        for p, m in _ytnay(modulo)
    ]
    # EL PEOR CASO: donante, punto y aceptor los TRES dentro del modulo, y EN ESE ORDEN
    # —el punto va entre el donante y el aceptor—. Sin las tres cosas no hay intron que
    # se defina solo, y decirlo requiere comprobar el ORDEN, no sólo la presencia.
    autodefinido = any(
        d["posicion"] < r["posicion"] < a["posicion"]
        and BRANCH_POINT_WINDOW[0] <= a["posicion"] - r["posicion"] <= BRANCH_POINT_WINDOW[1]
        for d in donantes for r in ramas for a in aceptores
    )

    lleva = entrada.breaks_motif and entrada.breaks_motif in modulo
    redundante = bool(entrada.breaks_motif) and not lleva

    # DONANTE→PUNTO, MEDIDO sobre el intrón montado. La primera versión lo reconstruía
    # con `donor_to_branch` y daba 405 en vez de 256, por DOS errores que se sumaron:
    #
    #   1. le pasaba los elementos del intrón YA MONTADO, cuyo campo `empty` vale ya la
    #      distancia montada (256), y la función le sumaba la inserción otra vez;
    #   2. y le pasaba `inserted=len(modulo)`. `inserted` es TODO lo que se inserta —el
    #      módulo MÁS los dos espaciadores, 149+20+45=214—, no el módulo.
    #
    # Ninguno de los dos solo daba 405: con (1) y el 214 bueno habrían salido 470, y con
    # (2) sobre el vacío, 191. Lo que enseña es que un número plausible puede ser la suma
    # de dos equivocaciones, así que aquí se MIDE sobre la secuencia y se contrasta con la
    # ruta aritmética en el test — dos derivaciones independientes que tienen que coincidir.
    distancias = [
        candidato.branch_a - elementos.donor.end - 1
        for candidato in elementos.branch_candidates
        if candidato.branch_a is not None
    ]
    salto = (min(distancias), max(distancias)) if distancias else None
    base.update({
        "causa": "",
        "donantes": donantes,
        "aceptores": aceptores,
        "ramificaciones": ramas,
        "redundante": redundante,
        "por_que_redundante": (
            f"{intron} existe para romper {entrada.breaks_motif!r}, y el módulo montado "
            f"con {andamio} NO lo contiene. Es la misma construcción que "
            f"{entrada.derived_from!r} con otro nombre. {REDUNDANCIA}"
        ) if redundante else "",
        "intron_autodefinido": autodefinido,
        # Las dos frases SIEMPRE juntas: el hallazgo y lo que NO cierra.
        "aceptores_no_cierran": LO_QUE_EL_ACEPTOR_NO_CIERRA,
        "por_que_compite": POR_QUE_COMPITE if donantes else "",
        "metodo_del_orden": ORDEN_ANTES_QUE_PRESENCIA,
        "score_legitimo": score_legitimo,
        "tracto_legitimo": tracto_legitimo,
        "mejor_tracto": mejor_tracto,
        "longitud_modulo": len(modulo),
        "longitud_intron": len(montado),
        "donante_a_punto": salto,
    })
    return base


def matriz(*, guide: str) -> list[dict]:
    """Todas las combinaciones. Ninguna se elimina: las redundantes se MARCAN."""
    return [
        fila(intron, andamio, guide=guide)
        for intron in INTRONS
        for andamio in SCAFFOLDS
    ]


def condicional_a_andamio(entrada) -> bool:
    """¿Este intrón sólo tiene sentido con andamios que lleven cierto motivo?

    Se DERIVA de que declare un motivo que rompe. Un intrón que no rompe nada vale con
    cualquier andamio; uno que existe para romper `GTGAGCG` no aporta nada donde ese
    motivo no está.
    """
    return bool(entrada.breaks_motif)


def aviso_de_par(intron: str, andamio: str, *, guide: str) -> str:
    """Lo que la app dice AL MONTAR un par. Cadena vacía = nada que avisar.

    No impide nada, por lo mismo que el aviso de núcleo de seed compartido no impide
    elegir dos candidatos: la decisión es de quien diseña. Lo que no puede pasar es que
    se monte en silencio.

    Y NO declara redundancia sobre un andamio sin evaluar. «No se ha mirado» no es «no
    tiene el motivo»: ahí el aviso dice que la combinación **no se puede comprobar**, que
    es otra cosa y lleva a otra acción — conseguir el fichero, no descartar el par.
    """
    entrada = INTRONS[intron]
    if not condicional_a_andamio(entrada):
        return ""
    # LA PREGUNTA ES SOLO DEL ANDAMIO. El modulo se monta con el andamio y la guia; el
    # intron lo envuelve, no lo cambia. Preguntarselo al PAR ataba el aviso a que el
    # intron estuviera diseñado —y `mvm_sin_criptico` se diseña por candidato— asi que
    # avisaba «no se puede comprobar» sobre miR-E, donde el motivo esta y esta medido.
    lleva = lleva_motivo(andamio, entrada.breaks_motif, guide=guide)
    if lleva is True:
        return ""
    if lleva is False:
        return (
            f"{intron!r} existe para romper {entrada.breaks_motif!r}, y el módulo montado "
            f"con {andamio!r} NO lo contiene. Es la misma construcción que "
            f"{entrada.derived_from!r} con otro nombre. {REDUNDANCIA}"
        )
    return (
        f"{intron!r} existe para romper {entrada.breaks_motif!r}, así que sólo aporta "
        f"algo con un andamio que LO LLEVE — y con {andamio!r} eso NO SE PUEDE COMPROBAR "
        f"todavía: {'; '.join(SCAFFOLDS[andamio].missing)}. Montar el par no está "
        f"prohibido; lo que no vale es montarlo dando por hecho que resuelve algo."
    )


def lleva_motivo(andamio: str, motivo: str, *, guide: str) -> bool | None:
    """¿El módulo montado con ese andamio contiene el motivo? `None` = no se ha mirado.

    `None` no es `False`, y la diferencia decide qué se hace: `False` descarta el par,
    `None` manda a conseguir el fichero.
    """
    registrado = SCAFFOLDS[andamio]
    if registrado.state is not FilterState.PASS:
        return None
    from .blocks import build_block

    return motivo in build_block(
        guide=guide, scaffold=registrado.spec, available=False
    ).module
