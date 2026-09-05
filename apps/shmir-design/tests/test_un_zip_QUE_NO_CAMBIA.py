"""Un zip que se reconstruye igual: mismos ficheros, mismos bytes.

**Reportado (2026-09-04)**: «Aún no he logrado descargarme el zip. Empieza lo que parece
la descarga pero luego parece que no llega porque da un error de internet, cuando no lo
hay.» Y antes, del mismo botón: bajaba `shmir-design (3).zip` **y no contenía nada**.

### Primero, el botón: era OTRO del que yo di por supuesto

`shmir-design (3).zip` sale de `file_name="shmir-design.zip"`, que es el botón
**«Descargar todo (zip)»** de la sección *Descargas* — el que empaqueta los ficheros
GENERADOS (FASTA, TSV, oligos). No el de la copia de seguridad, que se llama «Descargar
todo (.zip)» y baja `shmir_copia_<fecha>.zip`. Dos botones con el mismo nombre a un punto
de distancia, y diagnostiqué el que no era. Principio nº 3, cometido por mí.

### Y son DOS fallos distintos en ese botón

**1. Vacío.** `ficheros` está vacío hasta que se pulsa «Seguir: las comprobaciones que
faltan» —`bloque_especie` devuelve `{}` antes—, y la sección *Descargas* pintaba el botón
igual. Un zip de cero entradas son **22 bytes** y se abre sin nada dentro. Medido.

**2. La descarga que empieza y no llega**, y aquí el mecanismo está comprobado en el
código de Streamlit, no supuesto:

  - `zipfile` estampa **la hora actual** en cada entrada, así que los MISMOS ficheros dan
    bytes DISTINTOS en cada construcción — medido: dos llamadas seguidas, dos md5;
  - `MemoryMediaFileStorage.load_and_get_id` deriva el id del fichero **del contenido**
    (`_calculate_file_id(file_data, ...)`), así que bytes distintos son un id distinto;
  - pulsar un `download_button` provoca un rerun; al acabar, `clear_session_refs` +
    `remove_orphaned_files` **borran el id que ya no referencia nadie** — que es justo el
    que el navegador está descargando.

O sea: el fichero desaparece del servidor mientras se baja. Cuanto más grande, más
probable — por eso «empieza y no llega» en vez de fallar del todo.

**La contramedida es que el zip no cambie**: fecha fija en cada entrada. Con el mismo
contenido, el id es el mismo y no hay nada que quede huérfano.

Regla 5: escritos antes.
"""

import io
import time
import unittest
import zipfile


class TestElZipSeRECONSTRUYEigual(unittest.TestCase):
    """La propiedad que impide que el fichero desaparezca a media descarga."""

    ENTRADAS = {"b.tsv": "col\t1\n", "a.fa": ">x\nACGT\n"}

    def _dos_veces(self, construir):
        uno = construir()
        # Más de un segundo: la marca de tiempo de un zip tiene resolución de 2 s, así
        # que sin esperar el fallo no se ve — y un test que no espera pasaría en verde
        # con el bug dentro.
        time.sleep(2.2)
        return uno, construir()

    def test_los_MISMOS_ficheros_dan_los_MISMOS_bytes(self):
        from shmir_design.gestor import deterministic_zip

        uno, dos = self._dos_veces(
            lambda: deterministic_zip(self.ENTRADAS, date="2026-09-04")
        )
        self.assertEqual(uno, dos)

    def test_y_la_COPIA_DE_SEGURIDAD_tambien(self):
        import shutil
        import tempfile
        from pathlib import Path

        from shmir_design import gestor

        origen = Path("data/reference")
        destino = Path(tempfile.mkdtemp())
        for fichero in sorted(p for p in origen.iterdir() if p.is_file())[:4]:
            shutil.copy(fichero, destino / fichero.name)
        try:
            uno, dos = self._dos_veces(
                lambda: gestor.export_all(destino, projects=None, date="2026-09-04")
            )
            self.assertEqual(uno, dos)
        finally:
            shutil.rmtree(destino)

    def test_el_contenido_SIGUE_SIENDO_el_que_se_le_da(self):
        # CONTROL: un zip determinista y VACÍO también sería determinista. Lo que se fija
        # es que la fecha deje de mandar, no que el zip deje de llevar cosas.
        from shmir_design.gestor import deterministic_zip

        datos = deterministic_zip(self.ENTRADAS, date="2026-09-04")
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            self.assertEqual(sorted(z.namelist()), ["a.fa", "b.tsv"])
            self.assertEqual(z.read("a.fa").decode(), ">x\nACGT\n")

    def test_una_fecha_DISTINTA_si_da_un_zip_distinto(self):
        # La otra mitad: si la fecha no llegara al zip, dos copias de días distintos
        # serían el mismo fichero y no habría forma de distinguirlas.
        from shmir_design.gestor import deterministic_zip

        self.assertNotEqual(
            deterministic_zip(self.ENTRADAS, date="2026-09-04"),
            deterministic_zip(self.ENTRADAS, date="2026-09-05"),
        )


class TestNoSeOfreceUnZipVACIO(unittest.TestCase):
    """22 bytes que parecen una descarga hecha es peor que no tener el botón."""

    def test_sin_ficheros_NO_hay_descarga_y_se_dice_por_que(self):
        from shmir_design.presentation import downloads_zip

        vista = downloads_zip({}, species="raton", date="2026-09-04")
        self.assertFalse(vista["hay"])
        self.assertIsNone(vista["datos"])
        self.assertIn("Seguir", vista["texto"])

    def test_con_ficheros_el_nombre_LLEVA_especie_y_fecha(self):
        from shmir_design.presentation import downloads_zip

        from shmir_design.species import resolve

        vista = downloads_zip(
            {"a.fa": ">x\nACGT\n"}, species="raton", date="2026-09-04",
        )
        self.assertTrue(vista["hay"])
        # El slug se PIDE, no se escribe: el de «raton» es `mouse`, y transcribirlo aquí
        # sería un test que coincide consigo mismo (principio nº 25).
        self.assertIn(resolve("raton").slug, vista["nombre"])
        self.assertIn("2026-09-04", vista["nombre"])
        self.assertTrue(vista["nombre"].endswith(".zip"))


if __name__ == "__main__":
    unittest.main()
