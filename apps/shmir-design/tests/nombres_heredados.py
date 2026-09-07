"""El nombre que llevaban las construcciones ANTES del 2026-09-07.

Los ficheros de `data/medido/` son corridas REALES de SpliceAI, versionadas con su
procedencia, y sus filas nombran cada construcción con la forma de entonces:
`mvm_actual__3utr959`. Ese nombre llevaba el prefijo del marco TECLEADO sobre una
coordenada del transcrito —la construcción es la del candidato `3utr:10`— y por eso se
arregló (errata nº 133).

**Los ficheros no se reescriben.** Son la evidencia de una corrida que este proyecto no
ejecuta, y editarlos para que cuadren con el código de hoy es exactamente lo que un
fixture no puede hacer. Lo que se hace es LEERLOS con la forma que tienen, y para eso
hace falta un solo sitio que sepa cuál era — transcrita en cinco tests, la primera que
se despistara daría cero filas y un análisis vacío que se lee como «limpio».

Vive en `tests/` a propósito: **la app no puede volver a emitir esta forma**, y el
guardia de `tools/auditar_marcos.py` lo impide en `shmir_design/` y en `tools/`. Aquí el
literal está permitido por la misma razón que un test puede exigir `3utr:449` en una
salida — es el control de la regla, no su violación.
"""

#: La forma de entonces. `3utr` sin dos puntos y pegado al número, que es justo lo que
#: se lee como una coordenada sin serlo. Vive en una constante porque la LEE quien
#: reconstruye el panel de aquel día: escrita dos veces, la lectura y la escritura se
#: separarían y el fichero dejaría de cruzar sin dar ningún error.
PREFIJO_HEREDADO = "3utr"


def nombre_heredado(construccion) -> str:
    return f"{construccion.intron}__{PREFIJO_HEREDADO}{construccion.candidate_start}"


def por_nombre_heredado(construcciones) -> dict:
    """`{nombre de entonces: construcción}`, para releer un fichero de `data/medido/`."""
    return {nombre_heredado(c): c for c in construcciones}


def starts_del_medido(ruta) -> tuple[int, ...]:
    """Los inicios de candidato que nombra un fichero de `data/medido/`.

    Una corrida guardada es la de UN PANEL, el de aquel día, y el panel de hoy puede ser
    otro: el 2026-09-07 se retiró `3utr:10` y entró `3utr:359`. Reconstruir el panel de
    entonces desde el fichero —y no desde la selección de hoy— es lo que permite seguir
    leyendo la evidencia sin reescribirla ni volver a correr SpliceAI.

    Se derivan del propio fichero: transcribirlos aquí sería la lista del panel escrita
    en un sitio más, y la primera que se despistara daría cero filas.
    """
    inicios: list[int] = []
    with open(ruta, encoding="utf-8") as f:
        next(f)
        for fila in f:
            if not fila.strip() or fila.startswith("#"):
                continue
            nombre = fila.split("\t")[0]
            inicio = start_del_nombre_heredado(nombre)
            if inicio not in inicios:
                inicios.append(inicio)
    if not inicios:
        raise ValueError(
            f"{ruta} no nombra ninguna construccion con la forma de entonces "
            f"(`<intron>__{PREFIJO_HEREDADO}<inicio>`); se aborta la reconstruccion del "
            f"panel de aquel dia."
        )
    return tuple(sorted(inicios))


def start_del_nombre_heredado(nombre: str) -> int:
    """El inicio que lleva dentro un nombre de entonces.

    **No se sacan «los digitos del nombre»**: `mvm_actual__3utr959` los tiene tambien en
    el propio prefijo, asi que juntarlos da `3959` — un numero con la forma correcta, en
    rango, y que no cruza con nada. Se exige la forma entera y se lee lo que va DETRAS
    del prefijo.
    """
    cola = nombre.split("__")[-1]
    if not cola.startswith(PREFIJO_HEREDADO):
        raise ValueError(
            f"{nombre!r} no lleva el prefijo {PREFIJO_HEREDADO!r} de los nombres de "
            f"entonces; no se adivina de que candidato es."
        )
    resto = cola[len(PREFIJO_HEREDADO):]
    if not resto.isdigit():
        raise ValueError(
            f"{nombre!r} no termina en un inicio de candidato: detras de "
            f"{PREFIJO_HEREDADO!r} hay {resto!r}."
        )
    return int(resto)


def starts_disponibles_hoy(ruta, seleccion) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Los inicios del fichero medido que HOY siguen siendo ventanas elegibles.

    Devuelve `(disponibles, caidos)` y **las dos mitades importan**: la evidencia no se
    reescribe, así que un candidato que aquel día se consultó y hoy ya no es elegible
    sigue nombrado en el fichero — lo que cambia es que esta corrida no puede montar su
    construcción. Pasarlo a `build_panel` haría abortar la corrida entera, y con razón:
    ese guardia existe para no emitir menos consultas de las que la etiqueta anuncia.

    **Por qué hace falta desde el 2026-09-07**: al medir el homopolímero sobre la guía y
    la pasajera (errata nº 144) caen `3utr:143`, `652`, `735` y `819`, que estaban en el
    panel del 2026-09-05 y por tanto en aquella corrida de SpliceAI.

    Quien llama tiene que DECIR cuántos usa y cuántos no: un subconjunto silencioso es
    exactamente lo que convierte una corrida parcial en una que parece completa.
    """
    del_fichero = starts_del_medido(ruta)
    # `choices_for` es quien resuelve un inicio contra el alcance de la corrida —panel
    # MAS sitios elegibles—, asi que se le pregunta a el y no a una segunda definicion
    # (errata nº 107).
    # Acepta la corrida de la pagina (`PageRun`) o su `ReportSelection`: quien llama
    # tiene una u otra, y el alcance lo resuelve siempre el mismo objeto.
    reporte = seleccion if hasattr(seleccion, "resolvable_choices") else seleccion.selection
    resolubles = set(reporte.resolvable_choices())
    disponibles = tuple(s for s in del_fichero if s in resolubles)
    caidos = tuple(s for s in del_fichero if s not in resolubles)
    if not disponibles:
        raise ValueError(
            f"Ningun inicio de {ruta} sigue siendo una ventana elegible: la corrida "
            f"medida no se puede releer contra este panel. Caidos: {caidos}."
        )
    return disponibles, caidos
