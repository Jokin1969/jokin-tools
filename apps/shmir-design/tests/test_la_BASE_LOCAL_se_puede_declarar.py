"""Si la base no está en el depósito, sus dos campos SE PIDEN. Si está, no.

Regla 5: escrito con el bucle delante.

**EL CASO (2026-09-09).** Se sube el `-outfmt 6` de una corrida local y sale:

    PARA — La base local 'refseq_rna_human.fa' necesita versión y md5: sin ellos la
    corrida no es reproducible

**y el modal no tiene esos campos.** No hay forma de salir: la salida no está donde está
el bloqueo (principio nº 47).

**Y el docstring prometía EXACTAMENTE lo que no pasa** — principio nº 11 en su peor
forma: «sin fichero en el depósito la corrida se sigue pudiendo guardar […] el md5 va
VACÍO, que es la verdad». Es falso: `BlastDatabase.__post_init__` ABORTA con el md5 vacío
si la corrida es local. Esa frase es la razón de que nadie mirara si los campos estaban.

**Por qué el caso es legítimo y no un descuido del usuario.** La decisión de la errata
nº 62 —la procedencia de un FICHERO es del depósito, no se teclea por corrida— es
correcta y no se toca. Lo que no estaba modelado es el estado en que **la base no está en
el depósito Y AUN ASÍ la corrida es válida**, que aquí no es raro: es el caso normal de
este frente. El BLAST se ejecuta FUERA (`blast.Disabled`) y una base de RefSeq de verdad
**no cabe en el escáner por ventana** —techo medido en 5,45 MB (errata nº 84)—, así que
subir cientos de MB para obtener 32 caracteres no es una vía.

Lo que se fija:

  · con el fichero en el depósito, los campos NO se piden (los deriva, errata nº 62);
  · sin él y en local, se piden, y la corrida se puede guardar con lo tecleado;
  · en `-remote` no se piden nunca: ahí no hay veredicto que dar.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import deposito, presentation, species
from shmir_design.blast_store import BlastDatabase

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIA = RAIZ / "data" / "reference"


def _deposito_sin_refseq() -> Path:
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(REFERENCIA / "manifest.tsv", tmp / "manifest.tsv")
    return tmp


class TestElHechoQueLoMotiva(unittest.TestCase):

    def test_una_base_local_SIN_md5_aborta(self):
        # No se relaja: sin md5 la corrida no es reproducible y no puede dar veredicto.
        # Lo que cambia es que ahora hay dónde escribirlo.
        with self.assertRaises(ValueError):
            BlastDatabase(name="x.fa", version="", md5=None, remote=False)

    def test_y_una_REMOTA_no_los_necesita(self):
        base = BlastDatabase(name="refseq_rna", version="", md5=None, remote=True)
        self.assertFalse(base.reproducible)


class TestLaFilaDiceSiHaPODIDOderivarlos(unittest.TestCase):

    def test_sin_fichero_en_el_deposito_NO_los_deriva_y_lo_dice(self):
        fila = presentation.blast_database_from_deposit(
            species="human", directory=_deposito_sin_refseq(), remote=False
        )
        self.assertFalse(fila["derivada"])
        self.assertEqual(sorted(fila["faltan"]), ["md5", "version"])
        self.assertTrue(fila["pedir"], "hay que pedirlos: si no, no hay salida")

    def test_con_fichero_SI_los_deriva_y_NO_los_pide(self):
        # La decision de la errata nº 62 no se toca: si el fichero esta, la procedencia
        # sale de su linea y teclearla seria la segunda copia del mismo dato.
        #
        # EL DEPOSITO SE MONTA POR EL CAMINO REAL DE SUBIDA, no escribiendo la linea a
        # mano: escribirla probaria el comparador y no el camino (principio nº 18). Y el
        # contenido es una REFERENCIA DE VERDAD del repositorio —no una secuencia
        # fabricada (regla 1)—; lo unico prestado es el NOMBRE, porque una base de RefSeq
        # de verdad no esta versionada en ninguna especie: son cientos de MB.
        tmp = _deposito_sin_refseq()
        deposito.accept_upload(
            tmp,
            filename="refseq_rna.fa",
            payload=(REFERENCIA / "NM_011170.3.fa").read_bytes(),
            species=species.resolve("mouse"),
            origin="prueba: una referencia del repositorio con el nombre del rol",
            date="2026-09-09",
        )
        fila = presentation.blast_database_from_deposit(
            species="mouse", directory=tmp, remote=False
        )
        self.assertTrue(fila["derivada"])
        self.assertFalse(fila["pedir"])
        self.assertTrue(fila["md5"])
        self.assertTrue(fila["version"])

    def test_en_REMOTE_no_se_piden_nunca(self):
        fila = presentation.blast_database_from_deposit(
            species="human", directory=_deposito_sin_refseq(), remote=True
        )
        self.assertFalse(fila["pedir"])

    def test_y_dice_QUE_compra_un_md5_tecleado_y_que_no(self):
        fila = presentation.blast_database_from_deposit(
            species="human", directory=_deposito_sin_refseq(), remote=False
        )
        self.assertIn("aviso", fila)
        self.assertTrue(str(fila["aviso"]).strip())


class TestConLoTecleadoLaCorridaSEGUARDA(unittest.TestCase):
    """El criterio de aceptación: se sale del bucle."""

    def test_la_base_se_construye_con_lo_declarado(self):
        fila = presentation.blast_database_from_deposit(
            species="human", directory=_deposito_sin_refseq(), remote=False
        )
        fila = dict(fila)
        fila["version"] = "UCSC hg38 RefSeq Curated, 2026-09-09, 93.563 secuencias"
        fila["md5"] = "eb0f940402ea047f3fe1c7761c75386b"
        base = BlastDatabase(
            name=str(fila["nombre"]), version=str(fila["version"]),
            md5=str(fila["md5"]) or None, remote=False,
        )
        self.assertTrue(base.reproducible)
        self.assertIn("eb0f9404", base.describe())


class TestLaPaginaPINTAlosCampos(unittest.TestCase):
    """Que la fila lo diga no basta: el modal tiene que pintarlos (principio nº 23)."""

    def test_el_modal_de_blast_los_pinta(self):
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
        modal = fuente.split("def _modal_blast")[1].split("\ndef ")[0]
        self.assertIn('base["pedir"]', modal,
                      "el modal no mira si hay que pedirlos: es la mitad del arreglo")
        self.assertIn("blast_dbver_", modal)
        self.assertIn("blast_dbmd5_", modal)


if __name__ == "__main__":
    unittest.main()
