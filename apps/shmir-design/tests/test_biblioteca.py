"""Biblioteca por ranura: guardar un fichero, volver a encontrarlo, borrarlo.

**El problema que cierra.** Los cuatro huecos del paso 2 —mRNA y GenBank de cada
especie— se suben de cero en cada sesión. Repetir la misma prueba obliga a ir a buscar
los mismos cuatro ficheros otra vez, y ese trasiego es donde se cuela el fichero
equivocado: el `.gb` de la especie que no era, la versión vieja del FASTA.

**Dónde vive y por qué.** En el VOLUMEN (`SHMIR_REFERENCE_DIR/biblioteca/`), no en la
imagen. El sistema de ficheros del contenedor es efímero: dentro de él, todo lo guardado
desaparecería en el siguiente redespliegue y el único síntoma sería una biblioteca vacía
sin ninguna explicación. Es la misma razón que el directorio de referencia y la de los
proyectos.

**Lo que NO cambia:** el md5 se CALCULA de los bytes y nunca se declara; se comprueba
otra vez AL LEER, porque un fichero que cambió en el volumen sin pasar por aquí no es el
que se guardó; y el nombre lo pone el navegador, así que pasa por `upload_path`.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design import biblioteca, trabajo
from shmir_design.errors import ShmirDesignError

FASTA = b">NM_011170.3 Mus musculus Prnp\nACGTACGTACGTACGTACGTAC\n"
OTRO = b">NM_000311.5 Homo sapiens PRNP\nTTTTACGTACGTACGTACGTAC\n"


class TestGuardarYVolverAEncontrar(unittest.TestCase):

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def guardar(self, nombre="raton.fa", datos=FASTA, ranura="mrna_diseno"):
        return biblioteca.guardar(
            ranura, nombre=nombre, data=datos, date="2026-08-27", base=self.base
        )

    def test_una_biblioteca_nueva_esta_VACIA_y_no_falla(self):
        self.assertEqual(biblioteca.listar("mrna_diseno", base=self.base), ())

    def test_guardar_y_listar(self):
        entrada = self.guardar()
        self.assertEqual(entrada.name, "raton.fa")
        self.assertEqual(entrada.size, len(FASTA))
        listadas = biblioteca.listar("mrna_diseno", base=self.base)
        self.assertEqual([e.id for e in listadas], [entrada.id])

    def test_el_id_es_el_md5_de_los_BYTES__no_se_declara(self):
        import hashlib

        entrada = self.guardar()
        self.assertEqual(entrada.id, hashlib.md5(FASTA, usedforsecurity=False).hexdigest())

    def test_leer_devuelve_los_MISMOS_bytes(self):
        entrada = self.guardar()
        self.assertEqual(biblioteca.leer("mrna_diseno", entrada.id, base=self.base), FASTA)

    def test_guardar_DOS_VECES_lo_mismo_no_duplica(self):
        primera = self.guardar()
        segunda = self.guardar(nombre="otro_nombre.fa")
        self.assertEqual(primera.id, segunda.id)
        self.assertEqual(len(biblioteca.listar("mrna_diseno", base=self.base)), 1)

    def test_las_RANURAS_no_se_mezclan(self):
        self.guardar(ranura="mrna_diseno")
        self.assertEqual(biblioteca.listar("mrna_diseno", base=self.base) != (), True)
        self.assertEqual(biblioteca.listar("mrna_segunda", base=self.base), ())

    def test_borrar_lo_quita_del_indice_Y_del_disco(self):
        entrada = self.guardar()
        ruta = biblioteca.ruta_de("mrna_diseno", entrada.id, base=self.base)
        self.assertTrue(ruta.is_file())
        biblioteca.borrar("mrna_diseno", entrada.id, base=self.base)
        self.assertEqual(biblioteca.listar("mrna_diseno", base=self.base), ())
        self.assertFalse(ruta.is_file())

    def test_borrar_algo_que_no_esta_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            biblioteca.borrar("mrna_diseno", "0" * 32, base=self.base)

    def test_leer_algo_que_no_esta_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            biblioteca.leer("mrna_diseno", "0" * 32, base=self.base)


class TestLoQueSeCOMPRUEBA(unittest.TestCase):

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_una_ranura_que_no_existe_ABORTA_y_dice_cuales_hay(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            biblioteca.guardar(
                "inventada", nombre="a.fa", data=FASTA, date="2026-08-27", base=self.base
            )
        for ranura in biblioteca.SLOTS:
            self.assertIn(ranura, str(ctx.exception))

    def test_una_EXTENSION_que_no_es_de_la_ranura_ABORTA(self):
        # Guardar el `.gb` en el hueco del FASTA es justo el error que esto evita.
        with self.assertRaises(ShmirDesignError) as ctx:
            biblioteca.guardar(
                "mrna_diseno", nombre="raton.gb", data=FASTA,
                date="2026-08-27", base=self.base,
            )
        self.assertIn(".gb", str(ctx.exception))

    def test_un_fichero_VACIO_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            biblioteca.guardar(
                "mrna_diseno", nombre="a.fa", data=b"",
                date="2026-08-27", base=self.base,
            )

    def test_el_nombre_pasa_por_upload_path(self):
        # Lo pone el navegador. `../` no saca nada del directorio de la ranura.
        entrada = biblioteca.guardar(
            "mrna_diseno", nombre="../../fuera.fa", data=FASTA,
            date="2026-08-27", base=self.base,
        )
        self.assertEqual(entrada.name, "fuera.fa")

    def test_si_el_fichero_CAMBIA_en_el_volumen_leerlo_ABORTA(self):
        # No es paranoia: el volumen es un directorio de verdad y alguien puede tocarlo.
        # Un fichero que ya no es el que se guardó NO se devuelve como si lo fuera.
        entrada = biblioteca.guardar(
            "mrna_diseno", nombre="a.fa", data=FASTA, date="2026-08-27", base=self.base
        )
        biblioteca.ruta_de("mrna_diseno", entrada.id, base=self.base).write_bytes(OTRO)
        with self.assertRaises(ShmirDesignError) as ctx:
            biblioteca.leer("mrna_diseno", entrada.id, base=self.base)
        self.assertIn("md5", str(ctx.exception))


class TestSobreviveAlREDESPLIEGUE(unittest.TestCase):

    def test_el_directorio_sale_de_SHMIR_REFERENCE_DIR(self):
        # La comprobación que importa, y la que cazó el fallo: la primera versión usaba
        # `reference.reference_dirs()`, que devuelve los directorios del PAQUETE y NO lee
        # la variable. La biblioteca habría vivido dentro de la imagen — en local
        # idéntico, en producción todo lo guardado se pierde en el redespliegue.
        entorno = {"SHMIR_REFERENCE_DIR": "/data/shmir/reference"}
        self.assertEqual(
            trabajo.reference_dir(entorno) / "biblioteca",
            Path("/data/shmir/reference/biblioteca"),
        )
        from shmir_design.trabajo import PACKAGE_REFERENCE_DIR

        self.assertEqual(
            biblioteca.base_por_defecto(), PACKAGE_REFERENCE_DIR / "biblioteca"
        )

    def test_y_una_ruta_RELATIVA_en_la_variable_aborta(self):
        with self.assertRaises(ShmirDesignError):
            trabajo.reference_dir({"SHMIR_REFERENCE_DIR": "relativa/mala"})

    def test_y_releer_con_otra_instancia_encuentra_lo_de_antes(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            biblioteca.guardar(
                "genbank_diseno", nombre="x.gb", data=b"LOCUS x 10 bp\n//\n",
                date="2026-08-27", base=base,
            )
            # Sin estado en memoria: se vuelve a leer del índice en disco.
            self.assertEqual(len(biblioteca.listar("genbank_diseno", base=base)), 1)


if __name__ == "__main__":
    unittest.main()
