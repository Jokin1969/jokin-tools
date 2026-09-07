"""Lo que se ejecuta dentro de un `except` no puede PODER fallar. Principio nº 57.

**El caso (2026-09-07), y es el arreglo de la errata anterior.** Para la errata nº 135, el
`except` de `_guardar_corrida` paso a llamar a `pending_after_duplicate` —que dice que del
panel sigue sin contestar— y a pintarlo debajo del mensaje rojo. Esa funcion mira el panel
y **puede abortar**. Cuando aborta, la excepcion sube, `main()` la recoge y hace `return`,
y la pagina se corta **por debajo del mensaje que se acaba de pintar**: o sea, se borra la
salida que ese bloque existe para dar. La errata nº 137 dentro del arreglo de la nº 135, el
mismo dia.

**Por que no es un caso mas del principio nº 47.** Aquel dice que la salida va donde esta
el bloqueo; este dice que **una salida puesta en el sitio correcto puede borrarse a si
misma**. Un `except` es, por construccion, el ultimo sitio donde algo puede ir mal antes de
que el usuario se entere de nada: si lo de dentro levanta, la excepcion nueva SUSTITUYE a
la que se estaba explicando.

**Por que el guardia se acota a `ui/`, y va declarado.** Ahi el `except` es la ULTIMA
frontera —debajo no hay nadie que recoja nada, solo el `try` de `main()` que corta la
pagina—, asi que la regla es mecanica: dentro de un manejador solo se pinta, y lo que
calcule algo va en su propio `try`. En el nucleo un `except` que relanza con contexto es lo
normal y lo correcto (regla 2), asi que el mismo criterio daria falsos positivos — y un
guardia con falsos positivos se acaba apagando (principio nº 34).

**LO QUE NO CUBRE, declarado**: una f-string interpola llamando a `__format__`, y eso no
es un `ast.Call` — asi que `f"{exc}"` pasa. Es deliberado: lo que persigue esta regla son
las funciones NUESTRAS, que son las que abortan por lo que acaba de pasar. Y no mira
`ui/` entero por composicion: un manejador que llame a una funcion local que a su vez
llame a otra nuestra se le escapa. Dice lo que ve, no que no haya nada.

Regla 5: escrito antes.
"""

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "ui" / "streamlit_app.py"

#: Lo unico que se puede llamar dentro de un `except` sin protegerlo: PINTAR. Streamlit
#: escribe en su buffer y no calcula nada nuestro, asi que no puede fallar por lo que
#: haya pasado. Cualquier otra cosa es una funcion nuestra que puede abortar.
SOLO_PINTAR = "st"


def _raiz_de(nodo: ast.AST) -> str:
    """El nombre del objeto sobre el que se llama: `st` en `st.sidebar.error(...)`."""
    while isinstance(nodo, ast.Attribute):
        nodo = nodo.value
    return getattr(nodo, "id", "")


def _sin_proteger(handler: ast.ExceptHandler) -> list[tuple[int, str]]:
    """Llamadas del manejador que NO son de pintar y NO estan dentro de un `try` suyo."""
    protegidas: set[int] = set()
    for nodo in ast.walk(handler):
        if isinstance(nodo, ast.Try):
            for dentro in ast.walk(nodo):
                if isinstance(dentro, ast.Call):
                    protegidas.add(id(dentro))
    salida = []
    for nodo in ast.walk(handler):
        if not isinstance(nodo, ast.Call) or id(nodo) in protegidas:
            continue
        if _raiz_de(nodo.func) == SOLO_PINTAR:
            continue
        salida.append((nodo.lineno, ast.unparse(nodo.func)))
    return salida


def auditar(fuente: str) -> list[tuple[int, str]]:
    arbol = ast.parse(fuente)
    hallazgos: list[tuple[int, str]] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ExceptHandler):
            hallazgos.extend(_sin_proteger(nodo))
    return sorted(hallazgos)


class TestLaPaginaEstaACero(unittest.TestCase):

    def test_ningun_except_llama_a_algo_que_pueda_fallar(self):
        culpables = [
            f"streamlit_app.py:{linea}  {llamada}"
            for linea, llamada in auditar(PAGINA.read_text(encoding="utf-8"))
        ]
        self.assertEqual(
            culpables, [],
            "Dentro de un `except` de la página sólo se pinta. Lo que calcule algo va en "
            "su propio `try`: si levanta, se lleva por delante el mensaje que ese bloque "
            "existe para dar (principio nº 57).\n" + "\n".join(culpables),
        )

    def test_y_el_detector_ENCUENTRA_manejadores(self):
        # Principio nº 51: «no falló» y «no miró» dan el mismo cero.
        arbol = ast.parse(PAGINA.read_text(encoding="utf-8"))
        cuantos = sum(
            1 for n in ast.walk(arbol) if isinstance(n, ast.ExceptHandler)
        )
        self.assertGreater(cuantos, 10, "no ha encontrado manejadores: no ha mirado")


class TestCazaElCasoREAL(unittest.TestCase):
    """El control adversario es el codigo que hubo, no uno parecido (principio nº 18)."""

    ANTES = (
        "def guardar(proyecto, construir, guardar, frente, tiling, seleccion, nombre):\n"
        "    try:\n"
        "        guardar(proyecto, construir())\n"
        "    except (ShmirDesignError, ValueError, OSError) as exc:\n"
        "        st.error(f'**PARA** — {exc}')\n"
        "        if frente and tiling is not None:\n"
        "            pendiente = pending_after_duplicate(\n"
        "                tiling, seleccion, species=nombre, front=frente,\n"
        "                stores=load_stores(proyecto),\n"
        "            )\n"
        "            st.warning(pendiente['texto'])\n"
    )

    DESPUES = (
        "def guardar(proyecto, construir, guardar, frente, tiling, seleccion, nombre):\n"
        "    try:\n"
        "        guardar(proyecto, construir())\n"
        "    except (ShmirDesignError, ValueError, OSError) as exc:\n"
        "        st.error(f'**PARA** — {exc}')\n"
        "        if frente and tiling is not None:\n"
        "            try:\n"
        "                pendiente = pending_after_duplicate(\n"
        "                    tiling, seleccion, species=nombre, front=frente,\n"
        "                    stores=load_stores(proyecto),\n"
        "                )\n"
        "            except (ShmirDesignError, ValueError, OSError) as otro:\n"
        "                st.caption(f'(No se ha podido calcular: {otro})')\n"
        "            else:\n"
        "                st.warning(pendiente['texto'])\n"
    )

    def test_con_el_codigo_de_ANTES_muerde(self):
        hallado = [llamada for _, llamada in auditar(self.ANTES)]
        self.assertIn("pending_after_duplicate", hallado)
        self.assertIn("load_stores", hallado)

    def test_y_con_el_de_DESPUES_calla(self):
        self.assertEqual(auditar(self.DESPUES), [])

    def test_pintar_NUNCA_cuenta(self):
        # Sin esto el guardia señalaría los veinticinco `st.error` de la página y lo
        # primero que se haría sería apagarlo.
        self.assertEqual(
            auditar(
                "try:\n    x()\nexcept ValueError as exc:\n"
                "    st.sidebar.error(f'PARA — {exc}')\n"
                "    st.session_state.pop('k', None)\n"
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
