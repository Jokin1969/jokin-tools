"""Una corrida que cubre el panel CIERRA su frente. Para todos, no para el que probamos.

**Errata nº 71, y es la sexta vez del patrón** —trabajo escrito, probado y que no llega a
donde tenía que llegar— pero **la primera sobre una DIMENSIÓN ENTERA del modelo** y no
sobre un consumidor:

  1. `masking.triple_motive_rows` — calculado y sin emitir en ninguna salida;
  2. `intron_folding` — igual;
  3. `store.save_*` — la capa de persistencia entera, sin llamador;
  4. `page_run` — escrita para que la página no divergiera, y la página no la llamaba;
  5. `site_table_rows` — la capacidad cableada y probada, y faltaba el `stores=` en la
     única llamada que se ejecuta (errata nº 51);
  6. **`store_states_by_front` con los frentes POR HEBRA** — aquí.

Lo que lo hace distinto: las cinco anteriores dejaban un artefacto sin actualizar. Ésta
dejaba **el eje guía/pasajera entero sin contestar**, así que una corrida de colisión de
seed o de carga de off-targets **no podía cerrar su frente nunca**, cubriera lo que
cubriera. Sólo BLAST podía, que es el único frente que no va por hebra.

### Y las dos mitades eran correctas por separado

`_store_state` devuelve `None` para un frente por hebra al que se pregunta **sin hebra**, y
eso es DELIBERADO y sigue siendo lo correcto: fundir las dos daría por buena la de la
pasajera con el estado de la guía, que es lo que la ficha parte en dos filas para no hacer.
Y `store_states_by_front` preguntaba por el nombre del frente, que es su clave natural.
Ninguna de las dos está mal mirada de cerca; lo que estaba mal es la **junta**, y su
producto era `None` — «los almacenes no dicen nada», indistinguible de «no hay corrida».

### Por eso este test se DERIVA de `STORE_FOR_FRONT` y no prueba un frente

Un test de `seed_colision` habría pasado igual el día que entre un cuarto almacén por
hebra. Lo que se comprueba es la propiedad, para **todos** los frentes declarados: si una
corrida contesta a todas las columnas de un frente en todo el panel, ese frente se cierra.
Con su mitad adversaria: quitando UNA columna, no se cierra.

Regla 5: escritos antes.
"""

import unittest

from shmir_design import presentation
from shmir_design.filters import FilterResult, FilterState


class _CorridaFalsa:
    """Con la forma que `_store_state` usa: `verdict_for(consulta)` y `history`."""

    def __init__(self, consultas, *, frente):
        self._consultas = frozenset(consultas)
        self._frente = frente

    def contesta(self, consulta):
        return consulta in self._consultas


class _AlmacenFalso:
    """La superficie mínima de un almacén: `runs`, `history` y `verdict_for`."""

    def __init__(self, consultas, *, frente):
        self._consultas = frozenset(consultas)
        self._frente = frente
        self.runs = ("una corrida",)

    def history(self, consulta):
        return ("x",) if consulta in self._consultas else ()

    def verdict_for(self, consulta):
        return FilterResult(
            name=self._frente, state=FilterState.PASS, reason="corrida de prueba",
        )


PANEL = (10, 60, 143)


def _columnas_de(frente: str) -> tuple[str, ...]:
    """Las columnas de un frente, DERIVADAS de su declaración. Una, o una por hebra."""
    declarado = presentation.STORE_FOR_FRONT[frente]
    if declarado["por_hebra"]:
        return tuple(f"{frente}:{hebra}" for hebra in presentation.STRANDS)
    return (frente,)


def _hebras_de(frente: str) -> tuple[str, ...]:
    declarado = presentation.STORE_FOR_FRONT[frente]
    return presentation.STRANDS if declarado["por_hebra"] else ("guia",)


def _almacenes(frente: str, *, hebras, starts=PANEL):
    declarado = presentation.STORE_FOR_FRONT[frente]
    consultas = [
        presentation.query_name("raton", inicio, hebra)
        for inicio in starts for hebra in hebras
    ]
    return {declarado["almacen"]: _AlmacenFalso(consultas, frente=frente)}


class TestTodoFrenteConAlmacenSePuedeCerrar(unittest.TestCase):
    """La propiedad, para TODOS los frentes declarados. No para el que se probó."""

    def test_hay_frentes_declarados_y_alguno_es_POR_HEBRA(self):
        # CONTROL: sin esto, una tabla vacía —o sin ningún frente por hebra— dejaría el
        # resto de la clase pasando sin comprobar nada. Es el fallo que dejó
        # `STORE_FOR_FRONT` con una sola fila leyéndose como «decidida».
        self.assertTrue(presentation.STORE_FOR_FRONT)
        self.assertTrue(
            any(d["por_hebra"] for d in presentation.STORE_FOR_FRONT.values()),
            "ningún frente declara `por_hebra`: este test dejó de cubrir el eje que lo "
            "motivó y hay que mirar por qué.",
        )

    def test_una_corrida_que_cubre_el_panel_CIERRA_su_frente(self):
        for frente in presentation.STORE_FOR_FRONT:
            with self.subTest(frente=frente):
                estados = presentation.store_states_by_front(
                    _almacenes(frente, hebras=_hebras_de(frente)),
                    species="raton", starts=PANEL,
                )
                self.assertIn(
                    frente, estados,
                    f"{frente}: la corrida cubre el panel entero y los almacenes no "
                    f"contestan nada. Es el fallo de los frentes por hebra.",
                )
                self.assertIn(
                    frente,
                    presentation.fronts_closed_over_panel(estados, starts=PANEL),
                    f"{frente}: contesta a todo el panel y aun así no se cierra.",
                )

    def test_QUITANDO_UNA_COLUMNA_el_frente_NO_se_cierra(self):
        """La mitad adversaria: sin ella, «cierra» y «no mira nada» dan el mismo verde."""
        for frente in presentation.STORE_FOR_FRONT:
            columnas = _columnas_de(frente)
            if len(columnas) < 2:
                # Un frente de una sola columna no tiene ninguna que quitar; su caso
                # adversario es el de abajo, el del candidato sin cubrir.
                continue
            with self.subTest(frente=frente):
                estados = presentation.store_states_by_front(
                    _almacenes(frente, hebras=_hebras_de(frente)[:1]),
                    species="raton", starts=PANEL,
                )
                self.assertNotIn(
                    frente,
                    presentation.fronts_closed_over_panel(estados, starts=PANEL),
                    f"{frente}: se cierra con una sola de sus {len(columnas)} columnas. "
                    f"Fundirlas daría por buena la de la pasajera con el estado de la "
                    f"guía.",
                )

    def test_y_dejando_un_CANDIDATO_sin_cubrir_tampoco(self):
        for frente in presentation.STORE_FOR_FRONT:
            with self.subTest(frente=frente):
                estados = presentation.store_states_by_front(
                    _almacenes(frente, hebras=_hebras_de(frente), starts=PANEL[:-1]),
                    species="raton", starts=PANEL,
                )
                self.assertNotIn(
                    frente,
                    presentation.fronts_closed_over_panel(estados, starts=PANEL),
                    f"{frente}: cierra con {len(PANEL) - 1} de {len(PANEL)} candidatos.",
                )


class TestLasDosMitadesSIGUENsiendoCorrectas(unittest.TestCase):
    """Lo que NO se arregló, porque no estaba roto. Y hay que fijarlo.

    `_store_state` tiene que seguir devolviendo `None` para un frente por hebra
    preguntado SIN hebra. Si alguien lo «arreglara» ahí —devolviendo el de la guía— la
    pasajera desaparecería de la tabla sin dar ningún error, que es peor que el fallo que
    esto cerró.
    """

    def test_un_frente_por_hebra_preguntado_SIN_hebra_sigue_sin_contestar(self):
        por_hebra = [
            f for f, d in presentation.STORE_FOR_FRONT.items() if d["por_hebra"]
        ]
        for frente in por_hebra:
            with self.subTest(frente=frente):
                self.assertIsNone(
                    presentation._store_state(
                        _almacenes(frente, hebras=presentation.STRANDS),
                        frente, "raton", PANEL[0],
                    ),
                    f"{frente}: contesta sin que se le diga la hebra. Fundir las dos es "
                    f"lo que la ficha parte en dos filas para no hacer.",
                )


if __name__ == "__main__":
    unittest.main()
