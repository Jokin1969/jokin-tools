"""Si se ha retomado un proyecto, la barra lateral NO vuelve a preguntar por él.

**Reportado con captura (2026-09-04)**: se abre `Intento_17` desde el paso 0 —«3
registro(s) · última 2026-09-02»— y la barra lateral sigue enseñando «Guardar esta
corrida en un proyecto» SIN marcar, con el aviso «Sin proyecto, lo que calculen los
modales se pierde al cerrar la pestaña». Y encima la app decía que ese proyecto no tenía
la corrida guardada, **que sí la tenía**.

### Son dos síntomas y UNA causa

La casilla nunca se marcaba, así que el almacén no se abría; sin almacén, `stores` llega
`None` a la tabla, a las tarjetas y al semáforo, y todas las corridas guardadas
desaparecen. O sea que el segundo síntoma —«no tenía la corrida»— **es el primero**, tres
consumidores más allá.

Y la causa del primero fue un `setdefault` mal elegido: la casilla ya había escrito
`False` en `session_state` en el primer repintado, antes de que hubiera nada que retomar,
así que `setdefault` no escribía nada. **Sembrar un valor por defecto no sirve cuando el
valor ya existe**, y el de un widget existe desde que se pinta por primera vez.

### Pero el arreglo NO es sembrarlo bien

Es que **no se pregunte dos veces**. La pregunta «¿en qué proyecto guardo esto?» ya la
contestó el paso 0; volver a hacerla abajo permite dar dos respuestas distintas a la
misma pregunta, y la que manda no la elige nadie. Es la misma razón por la que se quitó
la casilla global «Usar los de `data/reference/`»: una opción cuyo único efecto posible
es dejarlo todo en NOT_RUN sin decir por qué no es una opción, es una trampa.

Con un proyecto retomado, la barra lateral **enseña el proyecto abierto** —su historial,
sus corridas y si siguen valiendo— y no ofrece elegir otro ni crear uno.

Regla 5: escritos antes.
"""

import re
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference

FUENTE = (
    Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
).read_text(encoding="utf-8")

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _sin_comentarios(texto: str) -> str:
    """Los comentarios explican el mecanismo y lo NOMBRAN: buscar en ellos da verde falso.

    Es la errata nº 54 con el signo cambiado, y ya mordió una vez en este mismo fichero.
    """
    return "\n".join(l for l in texto.split("\n") if not l.lstrip().startswith("#"))


class TestLaBarraLateralNoVuelveAPreguntar(unittest.TestCase):
    def test_el_panel_de_proyecto_RECIBE_lo_retomado(self):
        # Sin esto no puede saber que ya está contestado, y es el argumento que faltaba:
        # la quinta vez de esa familia fue exactamente un `stores=` que no se pasaba.
        self.assertRegex(
            _sin_comentarios(FUENTE),
            r"_panel_proyecto\([^)]*retomado\s*=",
            "la barra lateral no recibe el proyecto retomado, así que vuelve a "
            "preguntar por él.",
        )

    def test_la_casilla_de_guardar_solo_existe_SIN_proyecto_retomado(self):
        limpia = _sin_comentarios(FUENTE)
        inicio = limpia.index("def _panel_proyecto")
        cuerpo = limpia[inicio : limpia.index("\ndef ", inicio + 10)]
        casilla = cuerpo.index("pr_activo_")
        antes = cuerpo[:casilla]
        self.assertIn(
            "retomado is None", antes,
            "la casilla «Guardar esta corrida en un proyecto» se pinta también con un "
            "proyecto ya retomado: son dos respuestas para la misma pregunta.",
        )

    def test_y_tampoco_se_ofrece_ELEGIR_otro_ni_crear_uno(self):
        limpia = _sin_comentarios(FUENTE)
        inicio = limpia.index("def _panel_proyecto")
        cuerpo = limpia[inicio : limpia.index("\ndef ", inicio + 10)]
        for clave in ("pr_slug_", "pr_crear_"):
            with self.subTest(clave=clave):
                antes = cuerpo[: cuerpo.index(clave)]
                self.assertIn("retomado is None", antes, clave)

    def test_NADIE_siembra_ya_el_estado_de_la_casilla(self):
        # `setdefault` sobre la clave de un widget no escribe nada en cuanto el widget se
        # ha pintado una vez, que es siempre. Era el mecanismo equivocado y no se deja.
        self.assertNotIn("pr_activo_{vuelta", FUENTE)
        self.assertNotIn('setdefault(f"pr_activo_', FUENTE)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElProyectoRETOMADOtraeSusCorridas(unittest.TestCase):
    """El segundo síntoma, en el núcleo: retomar tiene que devolver lo que hay escrito."""

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="proyectos_"))
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
        )
        payload, fuente = presentation.anatomy_payload(anatomia)
        almacen = presentation.project_create(
            self.raiz, slug="intento", date="2026-09-02", sequence=secuencia,
            species="raton", anatomy=payload, anatomy_source=fuente,
        )
        presentation.save_selection(
            almacen, starts=(10, 60, 143), date="2026-09-02", by="prueba",
        )

    def test_al_reabrir_vuelve_lo_que_se_habia_apuntado(self):
        vuelta = presentation.project_resume(self.raiz, "intento")
        self.assertTrue(vuelta["reabrible"])
        filas = presentation.project_rows(vuelta["almacen"])
        self.assertTrue(filas, "el proyecto vuelve VACÍO: lo apuntado no se recupera.")
        self.assertIn("seleccion", [f["tipo"] for f in filas])


if __name__ == "__main__":
    unittest.main()
