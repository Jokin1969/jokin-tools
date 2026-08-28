"""La tabla de PolyA_DB es un FICHERO del gestor, no una constante del código.

Regla 5: escrito antes.

Corrección del responsable (2026-08-27), y la distinción que hace falta:

> Nada de lo que dependa de datos se decide en el código. Los datos entran por el
> gestor. Lo que sí vive en el código son las REGLAS sobre qué hacer con ellos.

La promoción del `AATATA` —si un hexámero con uso medido se trata como funcional— es una
**regla**, y por eso va en código y sin bandera. Eso está bien.

Lo que estaba mal son **los valores**: los tres PAS con su PSE y su AvgRPM llegaron por
conversación y se cablearon en `apa.TABLA`. Consecuencias, y ninguna es teórica:

  · en otra especie **no hay forma de meterlos** sin editar el módulo;
  · cambiar de versión de PolyA_DB es tocar código;
  · su md5 **no está en el manifiesto**, así que una corrida de hace tres meses no es
    auditable — que es justo lo que el manifiesto existe para impedir.

**Y un hallazgo al ir a hacerlo**: el hueco `apa_medido.tsv` SÍ existe en el gestor, con
su rol y su ficha… pero su cargador (`parse_apa_sites`) espera
`posicion<TAB>fraccion<TAB>nombre`, mientras que **su propia ficha de obtención describe
PolyA_DB** —«PAS Summary», «PAS Expression», `PSE_3'READS`, `AvgRPM_3READS`—. La pantalla
pedía un fichero y el código esperaba otro. Son DOS tablas distintas y se separan con dos
nombres distintos, en vez de fundirlas: fundirlas sería el patrón de los dos contadores
que discrepan.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.errors import ShmirDesignError

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
FICHERO = DIR / "polya_db_mouse.tsv"


class TestElFicheroEXISTEYEstaVersionado(unittest.TestCase):
    def test_esta_en_data_reference(self):
        self.assertTrue(FICHERO.is_file(), f"falta {FICHERO}")

    def test_y_git_NO_lo_ignora(self):
        import subprocess

        salida = subprocess.run(
            ["git", "check-ignore", "-q", str(FICHERO)], capture_output=True, check=False
        )
        self.assertNotEqual(
            salida.returncode, 0,
            "la tabla de PolyA_DB tiene que estar versionada: son 4 filas de una base "
            "pública, y sin ella la corrida murina de referencia no se reproduce",
        )

    def test_y_esta_en_el_manifiesto_con_su_md5(self):
        from shmir_design.manifest import load_manifest

        entrada = next(
            e for e in load_manifest(DIR / "manifest.tsv").entries
            if e.name == "polya_db_mouse.tsv"
        )
        self.assertRegex(entrada.md5, r"^[0-9a-f]{32}$")


class TestElFormatoESTADeclarado(unittest.TestCase):
    def test_hay_una_constante_que_lo_describe(self):
        from shmir_design.apa import POLYADB_FORMAT

        self.assertIn("pas_id", POLYADB_FORMAT)
        self.assertIn("pse", POLYADB_FORMAT)

    def test_y_las_columnas_obligatorias_estan_declaradas(self):
        from shmir_design.apa import POLYADB_COLUMNS

        self.assertEqual(
            POLYADB_COLUMNS,
            ("pas_id", "coordenada", "clase", "pse", "avgrpm", "distal", "nota"),
        )


class TestSeCargaYDaLoMISMOQueLaConstante(unittest.TestCase):
    """La comprobación que hace segura la mudanza: mismo dato, otra procedencia."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.apa import load_polyadb

        cls.tabla = load_polyadb(FICHERO)

    def test_la_cabecera(self):
        self.assertEqual(self.tabla.source, "PolyA_DB")
        self.assertEqual(self.tabla.version, "v4.1")
        self.assertEqual(self.tabla.assembly, "mm10")
        self.assertEqual(self.tabla.gene, "Prnp")
        self.assertEqual(self.tabla.utr3_md5, "19f5fa2a77a87892770e2affdc90e0e4")

    def test_los_TRES_sitios_con_expresion(self):
        self.assertEqual(len(self.tabla.sites), 3)
        self.assertEqual(
            [(s.pse, s.avg_rpm) for s in self.tabla.sites],
            [(0.211, 0.55), (0.235, 0.34), (0.705, 1.65)],
        )

    def test_los_CUATRO_anclajes_incluido_el_que_no_tiene_expresion(self):
        self.assertEqual(len(self.tabla.anchors), 4)
        self.assertEqual(
            [a.expression for a in self.tabla.anchors], [True, True, True, False]
        )

    def test_y_las_dos_fracciones_salen_iguales(self):
        # Es LA comprobacion de la mudanza: si el fichero diera otro numero, el techo
        # del panel cambiaria sin que nadie lo hubiera decidido.
        self.assertAlmostEqual(self.tabla.working_value, 0.86, places=2)
        self.assertAlmostEqual(self.tabla.unweighted_value, 0.65, places=2)


class TestValidacionAlSubir(unittest.TestCase):
    def _escribe(self, texto: str) -> Path:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ruta = Path(self.tmp.name) / "polya_db_mouse.tsv"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def test_sin_utr3_md5_ABORTA(self):
        from shmir_design.apa import load_polyadb

        with self.assertRaises(ShmirDesignError) as caja:
            load_polyadb(self._escribe(
                "# fuente\tPolyA_DB\n"
                "pas_id\tcoordenada\tclase\tpse\tavgrpm\tdistal\tnota\n"
            ))
        self.assertIn("utr3_md5", str(caja.exception))

    def test_sin_version_ABORTA(self):
        from shmir_design.apa import load_polyadb

        with self.assertRaises(ShmirDesignError):
            load_polyadb(self._escribe(
                "# fuente\tPolyA_DB\n# utr3_md5\t" + "a" * 32 + "\n"
                "pas_id\tcoordenada\tclase\tpse\tavgrpm\tdistal\tnota\n"
            ))

    def test_una_columna_de_menos_ABORTA_diciendo_cual(self):
        from shmir_design.apa import load_polyadb

        cabecera = (
            "# fuente\tPolyA_DB\n# version\tv4.1\n# ensamblaje\tmm10\n"
            "# gen\tPrnp\n# tejido\tprueba\n# utr3_md5\t" + "a" * 32 + "\n"
        )
        with self.assertRaises(ShmirDesignError) as caja:
            load_polyadb(self._escribe(
                cabecera + "pas_id\tcoordenada\tclase\tpse\tavgrpm\tdistal\n"
            ))
        self.assertIn("nota", str(caja.exception))

    def test_un_pse_que_no_es_fraccion_ABORTA(self):
        from shmir_design.apa import load_polyadb

        cabecera = (
            "# fuente\tPolyA_DB\n# version\tv4.1\n# ensamblaje\tmm10\n"
            "# gen\tPrnp\n# tejido\tprueba\n# utr3_md5\t" + "a" * 32 + "\n"
            "pas_id\tcoordenada\tclase\tpse\tavgrpm\tdistal\tnota\n"
        )
        with self.assertRaises(ShmirDesignError):
            load_polyadb(self._escribe(cabecera + "x\t100\tOther\t21.1\t0.5\tno\t\n"))


class TestSinFicheroElFrenteQuedaNOT_RUN(unittest.TestCase):
    def test_la_tabla_no_se_resuelve_desde_un_directorio_vacio(self):
        from shmir_design.apa import find_polyadb

        with TemporaryDirectory() as tmp:
            self.assertIsNone(find_polyadb(directory=tmp))

    def test_y_desde_el_de_verdad_SI(self):
        from shmir_design.apa import find_polyadb

        self.assertIsNotNone(find_polyadb(directory=DIR))


class TestElHuecoDelGESTOR(unittest.TestCase):
    def test_hay_una_fila_por_especie(self):
        from shmir_design.species import required_files, resolve

        for especie, nombre in (("mouse", "polya_db_mouse.tsv"),
                                ("human", "polya_db_human.tsv")):
            with self.subTest(especie):
                fila = next(
                    f for f in required_files(resolve(especie)) if f.role == "polyadb"
                )
                self.assertEqual(fila.filename, nombre)

    def test_y_cierra_el_frente_del_APA(self):
        from shmir_design.species import required_files, resolve

        fila = next(f for f in required_files(resolve("mouse")) if f.role == "polyadb")
        self.assertIn("fraccion_isoforma_larga", fila.fronts)

    def test_el_rol_esta_en_el_manifiesto(self):
        from shmir_design.manifest import ROLES

        self.assertIn("polyadb", [r.role for r in ROLES])

    def test_y_NO_se_confunde_con_apa_medido_que_es_OTRA_tabla(self):
        # Dos formatos distintos, dos nombres distintos. Fundirlos seria el patron de
        # los dos contadores que discrepan.
        from shmir_design.species import required_files, resolve

        nombres = {f.role: f.filename for f in required_files(resolve("mouse"))}
        self.assertNotEqual(nombres["polyadb"], nombres.get("apa"))


if __name__ == "__main__":
    unittest.main()
