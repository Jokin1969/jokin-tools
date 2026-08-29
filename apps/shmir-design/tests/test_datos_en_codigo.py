"""Qué datos concretos de Prnp o de ratón siguen viviendo en el código.

Regla 5: escrito antes.

Sale de una pregunta del responsable, y es la generalización de lo que ya pasó tres
veces: `rmsk_mouse.out` conectado por rol, `txid10090` por defecto, `mmu-` por defecto.
El patrón es el mismo — **un dato de UNA especie escrito en el código funciona callado y
sobre otra produce un resultado con la forma correcta**.

Lo que este barrido separa, y son tres cosas distintas:

  · **DATO** — una medida, una tabla o una lista de una especie concreta. Debería estar
    en un fichero del gestor, con su md5 y su procedencia. Si no lo está, no es
    auditable dentro de un año y no se puede cambiar sin tocar el código.
  · **DECLARACIÓN** — un valor que el proyecto DECIDE y que no sale de ninguna medida
    (el prefijo de miRBase de una especie, el taxid, un umbral de convenio). Va en
    código a propósito: es la fuente única, y en un fichero se podría cambiar sin que
    se viera en el diff.
  · **PROSA** — el razonamiento, los avisos y los motivos. Van pegados a lo que
    explican; sacarlos a un fichero los alejaría de donde hacen falta.

La tabla vive en `data/datos_en_codigo.toml` y este test la ata a lo que hay: una
constante nueva que parezca dato y no esté clasificada hace fallar la suite, y una
entrada de la tabla que ya no exista, también. Igual que `alcanzabilidad.toml`.
"""

import importlib.util
import unittest
from pathlib import Path


def _auditar():
    """Carga `tools/auditar_datos.py` POR RUTA. `tools/` no es un paquete, y duplicar
    aquí el barrido sería el cuarto par duplicado: dos definiciones del mismo análisis."""
    ruta = Path(__file__).resolve().parents[1] / "tools" / "auditar_datos.py"
    spec = importlib.util.spec_from_file_location("auditar_datos", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.auditar()


class TestLaTablaCubreLoQueHAY(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe = _auditar()

    def test_ninguna_constante_sospechosa_se_queda_SIN_clasificar(self):
        self.assertEqual(
            sorted(self.informe["sin_clasificar"]), [],
            "Constantes con pinta de dato de una especie y sin entrada en "
            "`data/datos_en_codigo.toml`. O se clasifican, o se sacan a un fichero.",
        )

    def test_ninguna_entrada_de_la_tabla_esta_MUERTA(self):
        self.assertEqual(
            sorted(self.informe["huerfanas"]), [],
            "Entradas de la tabla que ya no existen en el código. Una lista con "
            "entradas muertas deja de leerse, y el siguiente hallazgo se pierde dentro.",
        )

    def test_las_tres_categorias_y_solo_esas(self):
        self.assertEqual(
            set(self.informe["por_categoria"]), {"dato", "declaracion", "prosa"}
        )

    def test_toda_entrada_dice_POR_QUE(self):
        for entrada in self.informe["entradas"]:
            with self.subTest(entrada["simbolo"]):
                self.assertTrue(entrada["motivo"].strip())

    def test_y_toda_la_categoria_DATO_dice_a_que_fichero_iria(self):
        # Sin eso, «debería estar en un fichero» es una queja y no una tarea.
        for entrada in self.informe["entradas"]:
            if entrada["categoria"] != "dato":
                continue
            with self.subTest(entrada["simbolo"]):
                self.assertTrue(entrada["fichero"].strip())


class TestLosQueYaSABEMOSQueSonDATO(unittest.TestCase):
    """Los tres que el propio proyecto ya tenía anotados como pendientes."""

    @classmethod
    def setUpClass(cls):
        cls.por_simbolo = {e["simbolo"]: e for e in _auditar()["entradas"]}

    def test_la_tabla_de_PolyA_DB_del_raton_ya_NO_esta_en_el_codigo(self):
        # Era la mas importante de la lista: 15 PAS con su PSE y su AvgRPM, y de ella
        # cuelgan el techo por tramos, la promocion del AATATA y el panel de diez. Vive
        # en `data/reference/polya_db_mouse.tsv`, con su md5 en el manifiesto. Que el
        # auditor ya no la vea ES la comprobacion de que la mudanza esta hecha.
        self.assertNotIn("apa.POLYA_DB_PRNP", self.por_simbolo)

    def test_la_lista_de_arranque_de_seeds(self):
        entrada = self.por_simbolo["seeds.BOOTSTRAP_SEED_TABLE"]
        self.assertEqual(entrada["categoria"], "dato")

    def test_los_controles_biologicos_del_off_target_son_DECLARACION(self):
        # RECLASIFICADA 2026-08-27. Estaba como DATO porque «la eleccion viene de la
        # biologia», y eso es cierto y no es el criterio: el criterio es si CAMBIARIA al
        # cambiar de especie o de gen (dato, al gestor) o si es una decision del
        # proyecto sobre como tratar el dato (codigo). Los tres nombres son el PATRON de
        # que significa «muchos sitios»: en un fichero se cambiarian sin verse en el
        # diff, igual que `CORE_ABUNDANT`.
        entrada = self.por_simbolo["offtarget.CONTROL_NAMES"]
        self.assertEqual(entrada["categoria"], "declaracion")

    def test_la_ruta_de_UCSC_ya_NO_esta_en_la_tabla(self):
        # Sale de la tabla porque dejo de nombrar `mm39` dentro del texto: ahora el
        # ensamblaje se resuelve contra `species.ucsc_assembly`. Que el auditor ya no la
        # vea ES la comprobacion de que la tarea esta hecha.
        self.assertNotIn("offtarget.UCSC_ROUTE_TEMPLATE", self.por_simbolo)
        self.assertNotIn("offtarget.UCSC_ROUTE", self.por_simbolo)

    def test_y_el_nucleo_de_abundancia_NO_es_dato_sino_declaracion(self):
        # Tiene autorizacion escrita y fechada: es una DECISION del proyecto, no una
        # medida. Sacarla a un fichero permitiria cambiarla sin que se viera en el diff,
        # que es justo lo contrario de lo que su autorizacion pide.
        entrada = self.por_simbolo["mirna.CORE_ABUNDANT"]
        self.assertEqual(entrada["categoria"], "declaracion")


if __name__ == "__main__":
    unittest.main()
