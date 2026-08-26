"""Toda salida que nombre una referencia imprime su longitud Y su md5, juntos.

Regla 5: escritos antes.

Contramedida de una linea a un fallo que fue invisible: el comparador alineaba las dos
entradas entre si en vez de contra la referencia, y la cabecera decia «referencia 1246
nt». Eso PARECE razonable. `referencia 1246 nt / 328cfa07…` no: el md5 delata que lo que
se esta llamando referencia es el bloque fabricado.

La regla es que las dos cifras van pegadas, en la misma etiqueta. Separadas no sirven:
el fallo esta justamente en que la longitud sola no identifica nada.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.reference import describe_sequence, sequence_md5

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON, FABRICADO = DIR / "NM_011170.3.fa", DIR / "prnp_3utr_fabricado_1246nt.txt"


class TestLaEtiqueta(unittest.TestCase):

    def test_lleva_el_nombre_la_longitud_y_el_md5(self):
        etiqueta = describe_sequence("ACGT" * 3, name="sonda")
        self.assertIn("sonda", etiqueta)
        self.assertIn("12 nt", etiqueta)
        self.assertIn(sequence_md5("ACGT" * 3)[:8], etiqueta)

    def test_las_dos_cifras_van_JUNTAS(self):
        # Separadas no delatan nada: el fallo era que la longitud sola parecia
        # razonable. Se comprueba que no hay mas de un puñado de caracteres entre ellas.
        etiqueta = describe_sequence("ACGT" * 3, name="sonda")
        hueco = etiqueta.index(sequence_md5("ACGT" * 3)[:8]) - (
            etiqueta.index("12 nt") + len("12 nt")
        )
        self.assertLess(hueco, 6)

    def test_el_md5_va_recortado_pero_reconocible(self):
        etiqueta = describe_sequence("ACGT" * 3, name="s")
        completo = sequence_md5("ACGT" * 3)
        self.assertIn(completo[:8], etiqueta)
        self.assertNotIn(completo, etiqueta)

    def test_se_puede_pedir_entero(self):
        etiqueta = describe_sequence("ACGT" * 3, name="s", full=True)
        self.assertIn(sequence_md5("ACGT" * 3), etiqueta)

    def test_una_secuencia_vacia_aborta(self):
        with self.assertRaises(ShmirDesignError):
            describe_sequence("", name="s")


@unittest.skipUnless(
    RATON.is_file() and FABRICADO.is_file(), "NOT_RUN: faltan los fixtures"
)
class TestElFalloQueDelata(unittest.TestCase):
    """Con la etiqueta puesta, confundir las dos secuencias se ve a simple vista."""

    def _utr3(self):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
        return normalize_sequence(bruta, name="NM_011170.3")[949:]

    def test_la_buena_y_la_fabricada_dan_etiquetas_distintas(self):
        buena = describe_sequence(self._utr3(), name="referencia")
        mala = describe_sequence(
            FABRICADO.read_text(encoding="ascii").strip(), name="referencia"
        )
        self.assertNotEqual(buena, mala)
        self.assertIn("1242 nt", buena)
        self.assertIn("19f5fa2a", buena)
        self.assertIn("1246 nt", mala)
        self.assertIn("328cfa07", mala)


@unittest.skipUnless(
    RATON.is_file() and FABRICADO.is_file(), "NOT_RUN: faltan los fixtures"
)
class TestDondeSeAplica(unittest.TestCase):

    def _cadenas(self):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
        return (
            normalize_sequence(bruta, name="NM_011170.3")[949:],
            FABRICADO.read_text(encoding="ascii").strip(),
        )

    def test_el_perfil_de_diferencias_lleva_las_dos_etiquetas(self):
        from shmir_design.alignment import align

        ref, otra = self._cadenas()
        texto = align(ref, otra).format_text()
        self.assertIn("1242 nt", texto)
        self.assertIn("19f5fa2a", texto)
        self.assertIn("1246 nt", texto)
        self.assertIn("328cfa07", texto)

    def test_el_informe_del_diseño_ya_la_llevaba(self):
        # Este camino se cerro antes; el test lo fija para que no se abra.
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        ref, _ = self._cadenas()
        tiling = tile_utr(ref)
        texto = text_report(
            species="raton", tiling=tiling,
            selection=select_from_report(tiling, SelectionConfig(n_candidates=2)),
            scaffold=SGEP_SCAFFOLD,
        )
        self.assertIn("1242 nt", texto)
        self.assertIn("19f5fa2a77a87892770e2affdc90e0e4", texto)


if __name__ == "__main__":
    unittest.main()
