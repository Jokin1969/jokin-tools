"""Un clic en «Buscar candidatos» busca los candidatos. Sin esto hacían falta DOS.

Regla 5: escrito con el fallo delante y MEDIDO en un navegador de verdad.

**EL CASO (2026-09-10), errata nº 161.** Salió intentando medir en Chromium, por el
proxy del hub, los dos botones nuevos de las tablas: se elegía especie, se subían el
`.fa` y el `.gb`, se pulsaba «Buscar candidatos»… y **no aparecía ninguna tabla**. Con la
misma sesión y un segundo clic, cuatro.

Medido, no razonado::

    1 clic : {"tablas": 0, "sigue_el_boton": 1, "dice_todo_listo": true}
    2 clics: {"tablas": 4, "dice_todo_listo": false}

**LA CAUSA es de una línea y la anatomía es conocida.** `accion` se resuelve ARRIBA
(`design_action(st.session_state.get("accion"), …)`), y los dos botones que la escriben
se pintan MUCHO más abajo. En el repintado que pulsa el botón, `accion` ya se leyó y vale
`None`, así que la página vuelve a decir «Todo listo» y no corre nada; la acción queda
guardada y sólo se ve en el repintado SIGUIENTE, que lo provoca cualquier otra
interacción. Escribir en `session_state` **no repinta lo que ya se pintó** — es
exactamente la pieza de la errata nº 54, donde la confirmación de una corrida guardada
salía sobre la pantalla de antes.

**Por qué no lo veía nadie.** No da ningún error: la página se repinta entera, el aviso
de «trabajando» aparece —hay rerun— y lo que se lee debajo es el texto de siempre. Y a la
segunda funciona, así que desde fuera parece que el primer clic «no se registró». Los
tests de la página (`AppTest`) tampoco pueden verlo: allí se llama a `.run()` otra vez
después de tocar el widget, que es justo el segundo repintado que aquí faltaba. **Un
cliente que no se parece al real no prueba nada.**

**El arreglo es `st.rerun()` en los dos botones**, y va en los DOS a propósito: arreglar
sólo el que se reportó es una costumbre, no un mecanismo (principio nº 31). Lo que lo
convierte en mecanismo es este fichero: la regla se DERIVA —cualquier botón que escriba
la acción tiene que repintar— así que un tercer botón queda cubierto sin que nadie se
acuerde.
"""

import ast
import pathlib
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "ui" / "streamlit_app.py"
FUENTE = PAGINA.read_text(encoding="utf-8")
ARBOL = ast.parse(FUENTE)

#: La clave de sesión que decide si la corrida se ejecuta. Se resuelve una sola vez, y
#: arriba: ver `presentation.design_action`.
CLAVE = "accion"


def _escrituras_de_la_accion():
    """Dónde se escribe `st.session_state["accion"]`, con su sentencia `if` alrededor.

    Se DERIVAN del fuente en vez de enumerarse: el fallo fue que había dos botones y el
    razonamiento se hizo sobre uno.
    """
    sitios = []
    for n in ast.walk(ARBOL):
        if not isinstance(n, ast.If):
            continue
        escribe = False
        for hijo in ast.walk(n):
            if (isinstance(hijo, ast.Assign)
                    and len(hijo.targets) == 1
                    and isinstance(hijo.targets[0], ast.Subscript)
                    and isinstance(hijo.targets[0].slice, ast.Constant)
                    and hijo.targets[0].slice.value == CLAVE):
                escribe = True
        if escribe:
            sitios.append(n)
    return sitios


def _repinta(nodo) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "rerun"
        for n in ast.walk(nodo)
    )


class TestTodoBotonQueFijaLaAccionREPINTA(unittest.TestCase):

    def test_CONTROL_el_detector_encuentra_los_botones(self):
        # Sin esto, «ninguno se olvida de repintar» y «no miré» darían el mismo verde
        # (principio nº 51). Hoy son dos: «Buscar candidatos» y «Estimar coste».
        self.assertGreaterEqual(
            len(_escrituras_de_la_accion()), 2,
            "el detector no encuentra los botones que fijan la acción: no está mirando "
            "lo que dice mirar.",
        )

    def test_y_TODOS_repintan(self):
        sin = [n.lineno for n in _escrituras_de_la_accion() if not _repinta(n)]
        self.assertEqual(
            sin, [],
            "estos botones fijan la acción y NO repintan, así que su primer clic no "
            "hace nada visible y hace falta un segundo (errata nº 161):\n  "
            + "\n  ".join(f"línea {ln}" for ln in sin),
        )


class TestLaCAUSA_sigue_ahi_y_por_eso_hace_falta_el_guardia(unittest.TestCase):
    """El fallo no es que faltara un `rerun`: es que la acción se LEE antes de escribirse.

    Mientras eso siga siendo cierto —y es deliberado, `design_action` es una sola
    definición para los dos consumidores— cualquier botón nuevo que escriba la acción
    nace con el mismo fallo. Este test fija esa condición: si algún día la lectura pasa a
    estar por debajo de los botones, el guardia de arriba deja de hacer falta y **esto se
    entera**, en vez de quedarse como una regla sin motivo.
    """

    def _linea_de(self, predicado):
        for n in ast.walk(ARBOL):
            if predicado(n):
                return n.lineno
        return None

    def test_la_accion_se_lee_ANTES_de_los_botones_que_la_escriben(self):
        lectura = self._linea_de(
            lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "design_action"
        )
        self.assertIsNotNone(lectura, "no se encuentra la lectura de la acción")
        escrituras = [n.lineno for n in _escrituras_de_la_accion()]
        self.assertTrue(
            all(linea > lectura for linea in escrituras),
            "la acción ya no se lee antes que los botones: revisa si el `rerun` sigue "
            "haciendo falta antes de quitarlo.",
        )


if __name__ == "__main__":
    unittest.main()
