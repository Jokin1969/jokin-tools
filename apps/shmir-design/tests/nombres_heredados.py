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
#: se lee como una coordenada sin serlo.
def nombre_heredado(construccion) -> str:
    return f"{construccion.intron}__3utr{construccion.candidate_start}"


def por_nombre_heredado(construcciones) -> dict:
    """`{nombre de entonces: construcción}`, para releer un fichero de `data/medido/`."""
    return {nombre_heredado(c): c for c in construcciones}
