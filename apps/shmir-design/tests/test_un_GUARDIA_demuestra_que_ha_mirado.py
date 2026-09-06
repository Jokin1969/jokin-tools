"""Cada auditoría publica CUÁNTO recorrió, y algo comprueba que no es cero.

**De dónde sale.** Del guardia del calendario del hub, que daba **verde en 175
milisegundos**: relanzaba la suite entera con el reloj adelantado y comprobaba que el hijo
saliera con `status === 0`, pero el hijo heredaba las variables `NODE_TEST_*` del runner,
se creía un fichero de test lanzado por un padre, **no descubría nada** y salía con 0. La
única señal fue el **tiempo**. Con las palabras del responsable del proyecto:

    «Verde sin haber mirado, y sólo se vio porque cronometraste. Que la comprobación de
    "ha corrido al menos tantas pruebas como ficheros hay" quede como patrón: un guardia
    tiene que demostrar que hizo trabajo, no sólo que no falló.»

**La clase.** `hallazgos == 0` contesta *«¿falló?»*, y esa no es la pregunta. La pregunta
es *«¿lo comprobó?»* — y **«no falló» y «no miró» dan exactamente el mismo cero**. Es el
«Alu 0 %» (errata nº 29) aplicado al comprobador en vez de al dato, y es peor ahí: un
guardia existe para que nadie tenga que volver a mirar, así que uno que aprueba sin mirar
no deja el problema como estaba — lo deja tapado con un verde.

**Medido antes de escribir esto (2026-09-06):** de las trece auditorías con `auditar()`,
**doce** publicaban ya un inventario que sería cero si no hubieran leído nada, y ninguna lo
comprobaba; **una** —`auditar_condiciones`— ni siquiera lo publicaba: emitía hallazgos y
nada más. Ésa se arregló (`ficheros`, `condiciones`); las otras doce las cierra este test.

Regla 5: escrito con el caso real que lo motivó delante.
"""

import dataclasses
import importlib
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (RAIZ, RAIZ / "tools"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

#: Auditoría → el campo de su informe que es la PRUEBA DE QUE MIRÓ.
#:
#: No es el campo de hallazgos: ése vale cero cuando todo está bien, que es lo normal. Es
#: el INVENTARIO — lo que recorrió — y sólo vale cero si no leyó nada. El campo se elige
#: por auditoría porque cada una recorre otra cosa: ficheros, guardias, banderas, tablas.
INVENTARIO = {
    "auditar_banderas": "filas",             # banderas de CLI encontradas
    "auditar_condiciones": "condiciones",    # condiciones miradas
    "auditar_datos": "entradas",             # datos de especie en código
    "auditar_estados": "filas",              # estados de la interfaz
    "auditar_fixtures": "filas",             # fixtures examinados
    "auditar_guardias": "guardias",          # guardias encontrados
    "auditar_homonimos": "homonimos",        # magnitudes con nombre compartido
    "auditar_marcos": "ficheros",            # ficheros leídos
    "auditar_navegacion": "total",           # caminos de navegación
    "auditar_pares": "emparejados",          # `zip` con `strict=True`
    "auditar_piezas": "filas",               # piezas del módulo
    "auditar_truncamiento": "tablas",        # tablas exportadas que corrió
    "auditar_umbrales": "umbrales",          # umbrales encontrados
}

#: Módulos `auditar_*` que NO exponen `auditar()`: se entran por otra puerta y los cubren
#: sus propios tests. Van por nombre para que uno nuevo no se cuele sin decidir.
SIN_AUDITAR = {
    "auditar_claves": "se entra por `digestos`, `formulas_repetidas` y "
                      "`exenciones_caducadas`, cada una con su test",
    "auditar_geometria": "no es una auditoría de código: mide la geometría del intrón "
                         "y se llama desde `check_data`",
}


def _modulos():
    for ruta in sorted((RAIZ / "tools").glob("auditar_*.py")):
        yield ruta.stem


def _valor(informe, campo):
    dato = informe[campo] if isinstance(informe, dict) else getattr(informe, campo)
    return len(dato) if hasattr(dato, "__len__") else dato


class TestTodasLasAuditoriasEstanClasificadas(unittest.TestCase):

    def test_ninguna_auditoria_se_queda_fuera_de_la_tabla(self):
        """Descubiertas del disco: una auditoría nueva entra sola y obliga a decidir."""
        clasificadas = set(INVENTARIO) | set(SIN_AUDITAR)
        self.assertEqual(sorted(set(_modulos()) - clasificadas), [])

    def test_y_ninguna_entrada_de_la_tabla_se_ha_quedado_sin_auditoria(self):
        """Una lista con entradas muertas deja de leerse y tapa el siguiente hallazgo."""
        existen = set(_modulos())
        self.assertEqual(sorted((set(INVENTARIO) | set(SIN_AUDITAR)) - existen), [])

    def test_las_exentas_de_verdad_NO_tienen_auditar(self):
        """Si les creciera un `auditar()`, la exención sobraría y habría que quitarla."""
        for nombre, motivo in SIN_AUDITAR.items():
            with self.subTest(nombre):
                self.assertFalse(hasattr(importlib.import_module(nombre), "auditar"))
                self.assertGreater(len(motivo), 30)


class TestCadaAuditoriaDemuestraQueHaMirado(unittest.TestCase):

    def test_su_inventario_no_es_cero(self):
        for nombre, campo in sorted(INVENTARIO.items()):
            with self.subTest(nombre):
                informe = importlib.import_module(nombre).auditar()
                self.assertGreater(
                    _valor(informe, campo), 0,
                    f"`{nombre}.{campo}` vale cero: esta auditoría no ha recorrido nada, "
                    f"así que su veredicto no distingue «limpio» de «no he mirado».",
                )

    def test_y_el_campo_del_inventario_EXISTE_en_el_informe(self):
        """Si alguien renombra el campo, esto falla en vez de leer un cero implícito."""
        for nombre, campo in sorted(INVENTARIO.items()):
            with self.subTest(nombre):
                informe = importlib.import_module(nombre).auditar()
                campos = (
                    set(informe) if isinstance(informe, dict)
                    else {f.name for f in dataclasses.fields(informe)}
                )
                self.assertIn(campo, campos)

    def test_el_inventario_NO_es_el_campo_de_hallazgos(self):
        """El campo de hallazgos vale cero cuando todo está bien: no prueba nada.

        Sin esto, alguien podría 'cumplir' la regla apuntando la tabla al campo de
        violaciones, que es exactamente el cero que este test existe para no aceptar.
        """
        sospechosos = {"hallazgos", "sin_declarar", "muertas", "muertos", "mudos",
                       "sin_clasificar", "sin_justificar", "sin_cubrir", "fantasmas"}
        for nombre, campo in INVENTARIO.items():
            with self.subTest(nombre):
                self.assertNotIn(campo, sospechosos)


class TestElControlAdversario(unittest.TestCase):
    """Que el detector vea el caso que persigue, sobre una auditoría de verdad."""

    def test_con_CERO_ficheros_auditar_marcos_no_da_verde(self):
        """Su tabla de excepciones hace de sonda: reclama lo que no encontró."""
        import auditar_marcos

        vacio = auditar_marcos.analizar_fuentes({}, auditar_marcos.declaraciones())
        self.assertEqual(vacio.fabrican, [])          # ningún hallazgo…
        self.assertEqual(vacio.ficheros, 0)           # …porque no leyó nada
        self.assertGreater(len(vacio.muertas), 0)     # y por eso NO pasa

    def test_y_con_CERO_ficheros_auditar_condiciones_lo_DICE(self):
        """El caso que había que arreglar: antes publicaba cero hallazgos y ya está."""
        import auditar_condiciones

        hallazgos, miradas, _ = auditar_condiciones.analizar_fuentes({})
        self.assertEqual(hallazgos, [])
        self.assertEqual(miradas, 0, "sin ficheros no puede haber mirado condiciones")
        self.assertGreater(auditar_condiciones.auditar().condiciones, 100)


if __name__ == "__main__":
    unittest.main()
