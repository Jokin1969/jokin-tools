"""La tabla de guardias responde al código, en las dos direcciones.

Sale de la errata nº 27 y de lo que más enseña de ella: `file_order_direction` era el
único guardia que habría saltado, **y sólo al importar un fichero**. La contramedida
existía y estaba en el sitio equivocado del flujo; nada la revalidaba después.

Generalizado: para cada guardia, **cuándo corre**. Un guardia que sólo corre en la
ingesta no protege de nada que se degrade más tarde, y este proyecto ya ha visto que se
degradan. Es el complemento del principio nº 9 — existir no es contener, y **haber
comprobado una vez no es seguir comprobando**.

La tabla la ata esto igual que `alcanzabilidad.toml` y `datos_en_codigo.toml`:

  · una entrada que nombra un símbolo que **ya no existe** hace fallar la suite;
  · una que nombra uno que **ya no aborta** también — un guardia que dejó de abortar es
    un aviso, y un aviso no protege nada;
  · y nada de la clase que se **deriva del código** —todo lo que compara una identidad
    declarada contra lo entregado— puede quedarse fuera sin declararlo.
"""

import importlib.util
import unittest
from pathlib import Path


def _modulo():
    """Carga `tools/auditar_guardias.py` POR RUTA, como hacen los otros dos auditores.

    `tools/` no es un paquete —son programas de línea de órdenes— y rehacer aquí el
    barrido sería otro par duplicado: dos definiciones del mismo análisis.
    """
    ruta = Path(__file__).resolve().parents[1] / "tools" / "auditar_guardias.py"
    spec = importlib.util.spec_from_file_location("auditar_guardias", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


auditar_guardias = _modulo()
MOMENTOS = auditar_guardias.MOMENTOS


class TestLaTablaRespondeAlCodigo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe = auditar_guardias.auditar()

    def test_ninguna_entrada_nombra_un_simbolo_que_ya_no_existe(self):
        self.assertEqual(
            self.informe["fantasmas"], [],
            "La tabla nombra código que ya no está. Una lista con entradas muertas "
            "deja de leerse, y el siguiente hallazgo se pierde dentro.",
        )

    def test_ningun_guardia_de_la_tabla_ha_dejado_de_ABORTAR(self):
        # Va por ENTRADA y no por símbolo: un guardia se implementa con varias piezas y
        # no todas abortan —`resources._refseq` PASA el md5 esperado y quien aborta es
        # `specificity.load_database`—. Exigirlo pieza a pieza daría falsos positivos
        # sobre la fontanería, y un guardia con falsos positivos se acaba apagando.
        self.assertEqual(
            self.informe["mudos"], [],
            "Hay un guardia en la tabla del que ya no aborta NINGUNA pieza. Un guardia "
            "que no aborta es un aviso, y un aviso no protege nada (regla 2).",
        )

    def test_nada_que_compare_una_identidad_se_queda_FUERA(self):
        self.assertEqual(
            self.informe["sin_cubrir"], [],
            "Hay código que compara una identidad declarada contra lo entregado y no "
            "está en la tabla. O es un guardia y se clasifica, o sólo calcula un "
            "resumen y se declara en [solo_calculan] con su motivo.",
        )

    def test_y_los_calculadores_declarados_siguen_existiendo(self):
        self.assertEqual(self.informe["calculadores_muertos"], [])


class TestCadaEntradaEstaCOMPLETA(unittest.TestCase):
    """Las cuatro columnas, y ninguna se puede dejar vacía: sin `momento` no hay
    pregunta que contestar, y sin `revalida` la respuesta se da por supuesta."""

    @classmethod
    def setUpClass(cls):
        cls.guardias = auditar_guardias.auditar()["guardias"]

    def test_hay_guardias_declarados(self):
        # Si la tabla se vaciara, todo lo de arriba pasaría sin comprobar nada.
        self.assertGreaterEqual(len(self.guardias), 20)

    def test_cada_uno_dice_QUE_protege_y_CON_QUE(self):
        for guardia in self.guardias:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertTrue(guardia["protege"].strip())
                self.assertTrue(guardia["implementa"])

    def test_como_actua_es_una_de_las_acciones_DECLARADAS(self):
        # `RECHAZA` existe porque abortar no siempre es lo correcto: una página que se
        # cae al cambiar un ajuste no protege a nadie. Pero se declara — «no aborta» a
        # secas es justo lo que separa un guardia de un aviso.
        for guardia in self.guardias:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertIn(
                    guardia.get("como_actua", "ABORTA"), auditar_guardias.ACCIONES
                )

    def test_el_momento_es_uno_de_los_DECLARADOS(self):
        for guardia in self.guardias:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertIn(guardia["momento"], MOMENTOS)

    def test_cada_uno_dice_si_puede_degradarse_y_COMO(self):
        for guardia in self.guardias:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertIn("puede_degradar", guardia)
                self.assertTrue(guardia["degrada_como"].strip())

    def test_y_QUE_lo_revalida_o_que_no_lo_revalida_nada(self):
        for guardia in self.guardias:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertTrue(guardia.get("revalida", "").strip())


class TestLaClaseDeRiesgo(unittest.TestCase):
    """Lo que este informe existe para señalar."""

    @classmethod
    def setUpClass(cls):
        cls.informe = auditar_guardias.auditar()

    def test_el_riesgo_es_la_INTERSECCION_de_las_tres_cosas(self):
        for guardia in self.informe["riesgo"]:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertEqual(guardia["momento"], "INGESTA")
                self.assertTrue(guardia["puede_degradar"])
                self.assertEqual(guardia["revalida"].upper(), "NADA")

    def test_el_guardia_de_la_errata_27_SIGUE_saliendo_señalado(self):
        # No es una curiosidad histórica: mientras nada lo revalide, sigue siendo el
        # siguiente en fallar. Si alguien lo cablea, este test cambia con él.
        nombres = {g["guardia"] for g in self.informe["riesgo"]}
        self.assertIn(
            "La dirección derivada del fichero cuadra con la registrada", nombres
        )

    def test_la_segunda_clase_distingue_SUITE_de_revalidacion_de_verdad(self):
        # Protege el repositorio y no protege una corrida: en producción el directorio
        # de referencia vive en un volumen que la suite no mira.
        for guardia in self.informe["solo_suite"]:
            with self.subTest(guardia=guardia["guardia"]):
                self.assertTrue(guardia["revalida"].upper().startswith("SUITE"))
                self.assertNotIn(guardia, self.informe["riesgo"])

    def test_un_guardia_en_riesgo_NO_sale_ademas_como_solo_suite(self):
        self.assertEqual(
            [g for g in self.informe["riesgo"] if g in self.informe["solo_suite"]], []
        )


class TestLaCadenaDelLogYaSeCOMPRUEBA(unittest.TestCase):
    """El hallazgo de esta tanda, cableado y con regresión.

    `store.ProjectStore.verify()` estaba escrita, testada y **sin ningún llamador fuera
    de sus tests**: la cadena de md5 no se recalculaba nunca en la app. Es el patrón de
    `store.save_*` y `page_run` por cuarta vez, pero sobre un GUARDIA — no es trabajo
    que no llega a una salida, es una comprobación que no comprueba.
    """

    def test_project_open_recalcula_la_cadena(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "shmir_design" / "presentation.py"
        ).read_text(encoding="utf-8")
        inicio = fuente.index("def project_open(")
        fin = fuente.index("def load_stores(")
        self.assertIn("almacen.verify()", fuente[inicio:fin])

    def test_y_la_tabla_lo_declara_asi(self):
        guardias = auditar_guardias.auditar()["guardias"]
        cadena = next(
            g for g in guardias if "cadena de md5" in g["guardia"].lower()
        )
        self.assertEqual(cadena["momento"], "AL_ABRIR")
        self.assertTrue(cadena["puede_degradar"])
        self.assertIn("project_open", cadena["revalida"])


if __name__ == "__main__":
    unittest.main()
