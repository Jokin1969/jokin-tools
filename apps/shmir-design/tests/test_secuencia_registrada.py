"""Ninguna secuencia entra al pipeline sin su md5, y ninguna longitud se anuncia sin
comprobarla sobre la cadena entregada.

Regla 5: escritos antes.

Origen: un 3'UTR anunciado como «1242 nt verificados» que en realidad traia 1246. La
comprobacion que lo habria parado es de una linea —contar la cadena que de verdad se
entrega, no la que se pretendia entregar— y no existia. Es la errata nº 4 del registro.

Y el corolario operativo: cuando el pipeline emite un 3'UTR para pegarlo en una
herramienta externa, lo escribe a FICHERO con su md5, nunca a stdout para copiar. Lo
que se pega es el fichero.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.errors import ShmirDesignError
from shmir_design.reference import (
    check_declared_length,
    sequence_md5,
    write_sequence_file,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


class TestLongitudAnunciada(unittest.TestCase):

    def test_una_longitud_que_cuadra_pasa(self):
        check_declared_length("ACGT" * 3, 12, name="sonda")

    def test_una_longitud_que_no_cuadra_aborta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            check_declared_length("ACGT" * 3, 11, name="sonda")
        self.assertIn("12", str(caja.exception))
        self.assertIn("11", str(caja.exception))

    def test_el_mensaje_dice_que_se_cuenta_lo_ENTREGADO(self):
        with self.assertRaises(ShmirDesignError) as caja:
            check_declared_length("ACGT" * 3, 11, name="sonda")
        self.assertIn("entregada", str(caja.exception).lower())

    def test_el_caso_real_de_la_errata(self):
        # 1246 entregados anunciados como 1242. Cuatro de mas.
        with self.assertRaises(ShmirDesignError) as caja:
            check_declared_length("A" * 1246, 1242, name="3'UTR de Prnp")
        self.assertIn("1246", str(caja.exception))
        self.assertIn("1242", str(caja.exception))

    def test_no_se_puede_declarar_una_longitud_negativa(self):
        with self.assertRaises(ShmirDesignError):
            check_declared_length("ACGT", -1, name="sonda")


class TestFicheroConMd5(unittest.TestCase):
    """Lo que se pega en una herramienta externa es un FICHERO, no un pegado."""

    def test_el_md5_va_en_el_nombre_del_fichero(self):
        with TemporaryDirectory() as tmp:
            ruta = write_sequence_file(
                "ACGT" * 300, directory=tmp, stem="NM_prueba_3utr"
            )
            self.assertIn(sequence_md5("ACGT" * 300)[:12], ruta.name)

    def test_y_tambien_en_la_cabecera_de_dentro(self):
        with TemporaryDirectory() as tmp:
            ruta = write_sequence_file("ACGT" * 300, directory=tmp, stem="s")
            texto = ruta.read_text(encoding="utf-8")
            self.assertIn(sequence_md5("ACGT" * 300), texto)
            self.assertIn("1200 nt", texto)

    def test_la_secuencia_sale_entera_y_sin_tocar(self):
        with TemporaryDirectory() as tmp:
            ruta = write_sequence_file("ACGT" * 300, directory=tmp, stem="s")
            cuerpo = "".join(
                l.strip() for l in ruta.read_text(encoding="utf-8").splitlines()
                if not l.startswith(">") and not l.startswith("#")
            )
            self.assertEqual(cuerpo, "ACGT" * 300)

    def test_se_puede_comprobar_lo_escrito_releyendolo(self):
        with TemporaryDirectory() as tmp:
            ruta = write_sequence_file("ACGT" * 300, directory=tmp, stem="s")
            cuerpo = "".join(
                l.strip() for l in ruta.read_text(encoding="utf-8").splitlines()
                if not l.startswith(">") and not l.startswith("#")
            )
            self.assertEqual(sequence_md5(cuerpo), sequence_md5("ACGT" * 300))

    def test_no_se_sobrescribe_un_fichero_con_otro_contenido(self):
        with TemporaryDirectory() as tmp:
            write_sequence_file("ACGT" * 300, directory=tmp, stem="s")
            # Mismo contenido: es el mismo fichero, no pasa nada.
            write_sequence_file("ACGT" * 300, directory=tmp, stem="s")
            self.assertEqual(len(list(Path(tmp).glob("*.txt"))), 1)

    def test_dos_secuencias_distintas_dan_dos_ficheros_distintos(self):
        with TemporaryDirectory() as tmp:
            a = write_sequence_file("ACGT" * 300, directory=tmp, stem="s")
            b = write_sequence_file("ACGA" * 300, directory=tmp, stem="s")
            self.assertNotEqual(a.name, b.name)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestSobreElTranscritoReal(unittest.TestCase):

    def test_el_3utr_que_se_emitiria_lleva_su_md5_verdadero(self):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
        utr3 = normalize_sequence(bruta, name="NM_011170.3")[949:]
        check_declared_length(utr3, 1242, name="3'UTR de NM_011170.3")
        self.assertEqual(sequence_md5(utr3), "19f5fa2a77a87892770e2affdc90e0e4")


if __name__ == "__main__":
    unittest.main()
