"""El panel de referencia como GESTOR: una tabla, presentes y ausentes juntos.

**El problema que cierra.** Hoy hay dos sitios: una lista de conectados y otra de lo que
falta, y hay que mirar dos veces para saber en qué punto estás. Y sobre lo que ya está no
se puede hacer nada — ni verlo, ni reemplazarlo, ni borrarlo, ni recuperarlo. El fichero
entra y deja de ser tuyo.

**El criterio:** entro al panel y sé exactamente qué tengo, qué me falta y qué puedo hacer
con cada cosa, sin leer documentación ni abrir una terminal.

Una fila por fichero, ordenadas por FRENTE, con el estado a la vista. Sobre las presentes,
cuatro acciones; sobre las ausentes, subir con su ficha.

**Lo que de verdad importa aquí es REEMPLAZAR.** Cambiar `mature.fa` invalida las corridas
de seed hechas con el anterior, y dejar que convivan en silencio es peor que no poder
reemplazarlo: el veredicto viejo sigue en pantalla, con la misma pinta, calculado contra
un fichero que ya no está.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design import gestor
from shmir_design.errors import ShmirDesignError

RMSK_OUT = b"""   SW  perc perc  perc  query
score  div. del.  ins.  sequence
  283  14.9  0.0   0.0  NM_011170.3   1000  1100
"""


class TestUnaSolaTABLA(unittest.TestCase):

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def filas(self):
        return gestor.manager_rows("Mus musculus", directory=self.dir)

    def test_presentes_y_ausentes_en_la_MISMA_lista(self):
        (self.dir / "rmsk_mouse.out").write_bytes(RMSK_OUT)
        filas = self.filas()
        estados = {f["estado"] for f in filas}
        self.assertIn("presente", estados)
        self.assertIn("ausente", estados)

    def test_ordenadas_por_FRENTE(self):
        frentes = [f["frente"] for f in self.filas()]
        self.assertEqual(frentes, sorted(frentes))

    def test_cada_fila_trae_lo_que_la_tabla_pinta(self):
        for fila in self.filas():
            for clave in ("nombre", "frente", "estado", "obligatorio", "acciones"):
                self.assertIn(clave, fila, fila.get("nombre"))

    def test_las_ACCIONES_dependen_del_estado(self):
        (self.dir / "rmsk_mouse.out").write_bytes(RMSK_OUT)
        por_nombre = {f["nombre"]: f for f in self.filas()}
        self.assertEqual(
            por_nombre["rmsk_mouse.out"]["acciones"],
            ["ver", "reemplazar", "borrar", "descargar"],
        )
        ausente = next(f for f in self.filas() if f["estado"] == "ausente")
        self.assertEqual(ausente["acciones"], ["subir"])

    def test_una_fila_AUSENTE_trae_su_ficha_de_obtencion(self):
        ausente = next(f for f in self.filas() if f["estado"] == "ausente")
        self.assertTrue(ausente["ficha"])

    def test_y_una_PRESENTE_trae_sus_metadatos(self):
        (self.dir / "rmsk_mouse.out").write_bytes(RMSK_OUT)
        fila = next(f for f in self.filas() if f["nombre"] == "rmsk_mouse.out")
        for clave in ("md5", "bytes", "fecha", "origen"):
            self.assertIn(clave, fila)
        self.assertEqual(fila["bytes"], len(RMSK_OUT))


class TestVER(unittest.TestCase):
    """Con un `.out` o un `.tsv`, diez líneas dicen más que cualquier metadato."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.dir / "rmsk_mouse.out").write_bytes(RMSK_OUT)

    def test_devuelve_las_primeras_lineas(self):
        vista = gestor.preview("rmsk_mouse.out", directory=self.dir, lines=10)
        self.assertIn("SW", vista.text)
        self.assertLessEqual(len(vista.text.splitlines()), 10)

    def test_dice_cuantas_lineas_tiene_EN_TOTAL(self):
        vista = gestor.preview("rmsk_mouse.out", directory=self.dir, lines=2)
        self.assertEqual(vista.total_lines, 3)
        self.assertTrue(vista.truncated)

    def test_un_fichero_BINARIO_no_se_pinta_como_texto(self):
        (self.dir / "raro.out").write_bytes(b"\x00\x01\x02\xff\xfe")
        vista = gestor.preview("raro.out", directory=self.dir)
        self.assertFalse(vista.is_text)
        self.assertIn("binario", vista.text.lower())

    def test_ver_algo_que_no_esta_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            gestor.preview("no_existe.out", directory=self.dir)


class TestREEMPLAZAR_Y_LO_QUE_INVALIDA(unittest.TestCase):
    """La acción que de verdad importa: qué veredictos dejan de valer."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.dir / "mature.fa").write_bytes(b">mmu-miR-1\nACGUACGUACGUACGUACGUAC\n")

    def test_el_plan_enseña_el_md5_VIEJO_y_el_NUEVO_antes_de_confirmar(self):
        plan = gestor.plan_replace(
            "mature.fa", directory=self.dir, payload=b">otra\nACGU\n"
        )
        self.assertNotEqual(plan.old_md5, plan.new_md5)
        self.assertTrue(plan.old_md5)
        self.assertTrue(plan.new_md5)

    def test_y_dice_QUE_CORRIDAS_quedan_invalidadas(self):
        plan = gestor.plan_replace(
            "mature.fa", directory=self.dir, payload=b">otra\nACGU\n"
        )
        self.assertIn("corrida_seed", plan.invalidates)
        self.assertIn("seed", plan.describe().lower())

    def test_reemplazar_por_EL_MISMO_fichero_no_invalida_nada(self):
        mismo = (self.dir / "mature.fa").read_bytes()
        plan = gestor.plan_replace("mature.fa", directory=self.dir, payload=mismo)
        self.assertEqual(plan.old_md5, plan.new_md5)
        self.assertEqual(plan.invalidates, ())
        self.assertIn("el mismo", plan.describe().lower())

    def test_el_mapa_de_INVALIDACION_esta_declarado_en_UN_SITIO(self):
        # Principio nº 7: los componentes de una comprobación compuesta se declaran una
        # vez y hay test de que están todos.
        from shmir_design.store import RECORD_KINDS

        for rol, corridas in gestor.ROLE_INVALIDATES.items():
            for corrida in corridas:
                self.assertIn(corrida, RECORD_KINDS, f"{rol} → {corrida}")

    def test_TODO_rol_declara_que_invalida__aunque_sea_nada(self):
        # Un rol que falta en el mapa no es «no invalida nada»: es un rol sin decidir, y
        # se leería como lo primero. Por eso el test exige que estén todos.
        from shmir_design.manifest import ROLES

        # `ROLES` es una tupla de objetos `Role`; la clave es su campo `.role`.
        declarados = set(gestor.ROLE_INVALIDATES)
        self.assertEqual({r.role for r in ROLES}, declarados)


class TestBORRAR(unittest.TestCase):

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.dir / "rmsk_mouse.out").write_bytes(RMSK_OUT)

    def test_el_plan_dice_QUE_FRENTE_vuelve_a_NOT_RUN(self):
        plan = gestor.plan_delete(
            "rmsk_mouse.out", species="Mus musculus", directory=self.dir
        )
        self.assertIn("repeticiones", plan.fronts)
        self.assertIn("NOT_RUN", plan.describe())

    def test_borrar_de_verdad_lo_QUITA(self):
        gestor.delete("rmsk_mouse.out", directory=self.dir)
        self.assertFalse((self.dir / "rmsk_mouse.out").is_file())

    def test_borrar_algo_que_no_esta_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            gestor.delete("no_existe.out", directory=self.dir)


class TestDESCARGAR(unittest.TestCase):

    def test_devuelve_los_bytes_TAL_COMO_SE_SUBIERON(self):
        with TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / "rmsk_mouse.out").write_bytes(RMSK_OUT)
            self.assertEqual(
                gestor.download("rmsk_mouse.out", directory=carpeta), RMSK_OUT
            )

    def test_y_ABORTA_si_no_esta(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ShmirDesignError):
                gestor.download("no_existe.out", directory=Path(tmp))


class TestElNombreNoSALE_del_directorio(unittest.TestCase):
    """Las cuatro acciones reciben un nombre y ninguna puede salirse."""

    def test_todas_pasan_por_upload_path(self):
        with TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            for accion in (gestor.preview, gestor.download):
                with self.subTest(accion.__name__):
                    with self.assertRaises(ShmirDesignError):
                        accion("../fuera.out", directory=carpeta)


if __name__ == "__main__":
    unittest.main()
