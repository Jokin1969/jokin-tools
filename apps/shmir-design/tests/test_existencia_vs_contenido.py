"""Un estado nunca se deriva de que algo EXISTA; se deriva de que tenga CONTENIDO.

Regla 5: escrito antes.

Sale de la errata nº 15. `provided` era `True` porque la ENTRADA estaba en el registro,
no porque hubiera secuencia: fichero ausente, `raw_sequence=""`, y aun así PASS. Cerrado
allí por derivación, el patrón queda abierto en todas partes donde una PRESENCIA decide
un estado — y en este proyecto eso es sobre todo `Path.is_file()`.

Un fichero de 0 bytes existe. Pasa `is_file()`. Y no contiene nada:

  - el panel de ficheros lo pinta PRESENTE, con sus cuatro acciones;
  - `fixture_available` dice que sí, así que los tests que dependen de él dejan de
    SALTARSE de forma visible y pasan a fallar por dentro;
  - el frente que ese fichero cierra sale como cerrable.

Los tres son la misma frase: «existe» leído como «lo tenemos». Se cierra con UNA
función, `presencia.hay_fichero`, y este test la exige en todos los sitios que deciden.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design import presencia


class TestLaFuncion(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_un_fichero_con_contenido_SI(self):
        ruta = self.dir / "lleno.fa"
        ruta.write_text(">x\nACGT\n", encoding="utf-8")
        self.assertTrue(presencia.hay_fichero(ruta))

    def test_un_fichero_de_CERO_BYTES_no(self):
        ruta = self.dir / "vacio.fa"
        ruta.write_bytes(b"")
        self.assertTrue(ruta.is_file(), "el fichero existe: ese es justo el problema")
        self.assertFalse(presencia.hay_fichero(ruta))

    def test_uno_que_no_esta_tampoco(self):
        self.assertFalse(presencia.hay_fichero(self.dir / "no_esta.fa"))

    def test_un_directorio_no_es_un_fichero(self):
        (self.dir / "carpeta").mkdir()
        self.assertFalse(presencia.hay_fichero(self.dir / "carpeta"))

    def test_solo_espacios_en_blanco_TAMPOCO(self):
        # Un fichero con un salto de linea tiene 1 byte y no tiene nada dentro. Es el
        # mismo caso que el de 0 bytes, y separarlos seria dejar medio agujero.
        ruta = self.dir / "blanco.fa"
        ruta.write_bytes(b"\n   \n\t\n")
        self.assertFalse(presencia.hay_fichero(ruta))

    def test_el_listado_de_un_directorio_aplica_el_mismo_criterio(self):
        (self.dir / "lleno.fa").write_text("ACGT\n", encoding="utf-8")
        (self.dir / "vacio.fa").write_bytes(b"")
        (self.dir / "sub").mkdir()
        self.assertEqual(presencia.ficheros_con_contenido(self.dir), {"lleno.fa"})

    def test_un_directorio_que_no_esta_da_conjunto_vacio_y_no_revienta(self):
        self.assertEqual(presencia.ficheros_con_contenido(self.dir / "no"), set())


class TestLosSitiosQueDECIDEN(unittest.TestCase):
    """Comportamiento, no forma: un fichero de 0 bytes sale AUSENTE en los tres.

    Se comprueba lo que dicen, no cómo está escrito. Un test que buscara `is_file()` en
    el fuente pasaría con el contenido mal —errata nº 14— y además marcaría los sitios
    donde existir SÍ es la pregunta: abrir, borrar, comprobar la pareja de un `.out`.
    """

    NOMBRE = "mature.fa"

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.dir / self.NOMBRE).write_bytes(b"")

    def test_el_panel_de_ficheros_lo_da_por_AUSENTE(self):
        from shmir_design.presentation import reference_panel_rows

        filas = {f["nombre"]: f for f in reference_panel_rows("mouse", directory=self.dir)}
        self.assertIn(self.NOMBRE, filas)
        self.assertFalse(filas[self.NOMBRE]["presente"])

    def test_el_GESTOR_tambien_y_le_ofrece_SUBIR_no_borrar(self):
        from shmir_design.presentation import reference_manager_rows

        filas = {f["nombre"]: f for f in reference_manager_rows("mouse", directory=self.dir)}
        self.assertEqual(filas[self.NOMBRE]["estado"], "ausente")

    def test_fixture_available_dice_que_NO(self):
        from shmir_design.reference import REFERENCES, fixture_available, fixture_filename

        raton = REFERENCES["NM_011170.3"]
        (self.dir / fixture_filename(raton)).write_bytes(b"")
        self.assertFalse(fixture_available(raton, data_dir=self.dir))

    def test_y_con_contenido_los_tres_dicen_que_SI(self):
        from shmir_design.presentation import reference_manager_rows
        from shmir_design.presentation import reference_panel_rows

        (self.dir / self.NOMBRE).write_text(">mmu-x\nACGUACGU\n", encoding="utf-8")
        filas = {f["nombre"]: f for f in reference_panel_rows("mouse", directory=self.dir)}
        self.assertTrue(filas[self.NOMBRE]["presente"])
        gestor = {f["nombre"]: f for f in reference_manager_rows("mouse", directory=self.dir)}
        self.assertEqual(gestor[self.NOMBRE]["estado"], "presente")


class TestElRegistroDeIntronesYaNoPuedeMentir(unittest.TestCase):
    """El caso que abrió todo esto, comprobado desde el otro lado."""

    def test_un_plasmido_de_cero_bytes_deja_el_intron_en_NOT_RUN(self):
        from shmir_design import introns

        with TemporaryDirectory() as tmp:
            (Path(tmp) / introns.QUIMERICO_PLASMID).write_bytes(b"")
            # La carga devuelve cadena vacia, y `provided` se deriva de eso.
            huerfano = introns.Intron(
                name="quimerico_de_prueba", description="", source="", raw_sequence=""
            )
            self.assertFalse(huerfano.provided)


if __name__ == "__main__":
    unittest.main()
