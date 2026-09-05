"""La procedencia de un fichero que YA está se declara sin volver a subirlo.

**Reportado (2026-09-04)** con el modal de carga de off-targets abortando:
`transcriptoma_3utr.fa` está en el depósito, es válido y tiene su md5 — y le faltan las
cuatro columnas de procedencia de tabla, **porque se subió el 2026-09-02 y esas columnas
entraron ese mismo día, más tarde** (errata nº 62). El aviso decía la verdad y la única
salida que ofrecía era **reemplazarlo por el gestor**: 88 MB otra vez por cuatro
metadatos.

**Eso es desproporcionado y es del diseño, no de quien lo sufre.** Lo que falta no es el
fichero —está, y ya pasó su validación al entrar— sino cuatro campos de su LÍNEA. Así que
se declaran sobre la línea, y el fichero no se toca.

Lo que hace que esto sea seguro y no un atajo: **se comprueba que el fichero de disco
siga siendo el que la fila registra**. Declarar procedencia sobre una fila cuyo fichero
ha cambiado debajo pegaría el ensamblaje de una tabla a otra distinta — con la forma
correcta y sin dar ningún error, que es la familia de fallo que este proyecto persigue.

Regla 5: escritos antes.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design import deposito
from shmir_design.errors import ShmirDesignError
from shmir_design.identidad import file_fingerprint
from shmir_design.manifest import (
    MANIFEST_COLUMNS,
    MANIFEST_NAME,
    ManifestEntry,
    entry_row,
)
from shmir_design.species import resolve

RATON = resolve("raton")

#: El catálogo real son decenas de MB y no está en el repositorio. Aquí se prueba la
#: LÍNEA del manifiesto, no el contenido: `declare_provenance` no vuelve a validar el
#: fichero —para eso ya pasó la validación al entrar, y revalidar 88 MB para añadir
#: cuatro metadatos es justo el coste que esto quita—. Declarado en
#: `data/fixtures_sinteticos.toml`.
CONTENIDO = b">t1\nACGTACGTACGTACGTACGTACGT\n"


def _escribir(raiz: Path, entrada: ManifestEntry) -> None:
    """Un manifiesto con su cabecera y UNA fila. Sólo con cabecera, `parse` aborta."""
    (raiz / MANIFEST_NAME).write_text(
        "\t".join(MANIFEST_COLUMNS) + "\n" + entry_row(entrada) + "\n",
        encoding="utf-8",
    )


class TestSeDeclaraSobreLaLinea(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="deposito_"))
        self.nombre = "transcriptoma_3utr.fa"
        (self.raiz / self.nombre).write_bytes(CONTENIDO)
        # Una fila COMO LAS DE ANTES: con md5, tamaño y origen, y sin las cuatro nuevas.
        # La fila la monta `entry_row`, que DERIVA su ancho de `MANIFEST_COLUMNS`: una
        # escrita a mano con tabuladores contados se queda corta y el manifiesto deja de
        # parsearse (lección de las tres columnas de anatomía).
        _escribir(self.raiz, ManifestEntry(
            name=self.nombre, filter_name="carga de off-targets por seed",
            size=len(CONTENIDO), md5=file_fingerprint(CONTENIDO),
            date="2026-09-02", origin="JCC",
        ))

    def _fila(self):
        return deposito.read_deposit("transcriptoma", species=RATON, directory=self.raiz)

    def test_antes_le_faltan_los_cuatro(self):
        self.assertEqual(len(self._fila().missing_provenance), 4)

    def test_al_declararlos_la_fila_queda_completa(self):
        deposito.declare_provenance(
            self.raiz, filename=self.nombre, species=RATON,
            assembly="mm39", table="RefSeq All / 3' UTR Exons",
            table_date="2026-09-02", representative="sin filtrar isoformas",
        )
        self.assertEqual(self._fila().missing_provenance, ())

    def test_y_el_FICHERO_no_se_toca(self):
        antes = (self.raiz / self.nombre).stat().st_mtime_ns
        deposito.declare_provenance(
            self.raiz, filename=self.nombre, species=RATON,
            assembly="mm39", table="RefSeq All", table_date="2026-09-02",
            representative="sin filtrar",
        )
        fila = self._fila()
        self.assertEqual((self.raiz / self.nombre).stat().st_mtime_ns, antes)
        self.assertEqual((self.raiz / self.nombre).read_bytes(), CONTENIDO)
        # Y lo que describe al FICHERO tampoco: md5, tamaño y fecha de registro son
        # suyos, no de esta declaración.
        self.assertEqual(fila.entry.md5, file_fingerprint(CONTENIDO))
        self.assertEqual(fila.entry.size, len(CONTENIDO))
        self.assertEqual(fila.entry.date, "2026-09-02")

    def test_si_falta_uno_de_los_cuatro_ABORTA_y_no_escribe(self):
        with self.assertRaises(ShmirDesignError) as caja:
            deposito.declare_provenance(
                self.raiz, filename=self.nombre, species=RATON,
                assembly="mm39", table="RefSeq All", table_date="", representative="x",
            )
        self.assertIn("fecha", str(caja.exception).lower())
        self.assertEqual(len(self._fila().missing_provenance), 4)

    def test_si_el_fichero_YA_NO_es_el_de_su_fila_ABORTA(self):
        # El md5 es lo que ata la procedencia a un fichero concreto. Con el fichero
        # cambiado debajo, declarar el ensamblaje se lo pegaría a OTRA tabla.
        (self.raiz / self.nombre).write_bytes(b">t1\nACGTACGTACGTACGTACGTACGTAC\n")
        with self.assertRaises(ShmirDesignError) as caja:
            deposito.declare_provenance(
                self.raiz, filename=self.nombre, species=RATON,
                assembly="mm39", table="RefSeq All", table_date="2026-09-02",
                representative="sin filtrar",
            )
        self.assertIn("md5", str(caja.exception).lower())

    def test_un_fichero_que_no_esta_ABORTA(self):
        (self.raiz / self.nombre).unlink()
        with self.assertRaises(ShmirDesignError):
            deposito.declare_provenance(
                self.raiz, filename=self.nombre, species=RATON,
                assembly="mm39", table="RefSeq All", table_date="2026-09-02",
                representative="sin filtrar",
            )


class TestSoloDondeLaProcedenciaHACEfalta(unittest.TestCase):
    """Un casete de AAV no sale de ninguna tabla: ahí la columna vacía es la VERDAD."""

    def test_declararla_en_un_rol_que_no_la_pide_ABORTA(self):
        raiz = Path(tempfile.mkdtemp(prefix="deposito_"))
        (raiz / "aav_casete.fa").write_bytes(CONTENIDO)
        _escribir(raiz, ManifestEntry(
            name="aav_casete.fa", filter_name="transgen", size=len(CONTENIDO),
            md5=file_fingerprint(CONTENIDO), date="2026-09-02", origin="JCC",
        ))
        with self.assertRaises(ShmirDesignError) as caja:
            deposito.declare_provenance(
                raiz, filename="aav_casete.fa", species=RATON,
                assembly="mm39", table="x", table_date="2026-09-02", representative="x",
            )
        self.assertIn("no sale de ninguna tabla", str(caja.exception).lower())


if __name__ == "__main__":
    unittest.main()
