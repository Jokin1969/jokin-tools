"""Alineamiento global y PERFIL de diferencias por clase.

Regla 5: escritos antes que `shmir_design/alignment.py`.

El perfil no es decoracion: distingue dos investigaciones distintas. Un trasvase —copiar
de una pantalla— solo puede PERDER caracteres. Si el perfil trae sustituciones o
transposiciones, la secuencia no se copio mal: se genero. Son dos causas, dos culpables
y dos remedios.

Datos reales: el 3'UTR de NM_011170.3 contra el bloque fabricado de 1246 nt.
"""

import unittest
from pathlib import Path

from shmir_design.alignment import DiffClass, align

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON, FABRICADO = DIR / "NM_011170.3.fa", DIR / "prnp_3utr_fabricado_1246nt.txt"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


class TestCasosMinimos(unittest.TestCase):

    def test_dos_iguales_no_tienen_diferencias(self):
        self.assertEqual(align("ACGTACGT", "ACGTACGT").differences, ())

    def test_una_sustitucion(self):
        perfil = align("ACGTACGT", "ACGAACGT").profile
        self.assertEqual(perfil[DiffClass.SUSTITUCION], 1)

    def test_una_delecion(self):
        perfil = align("ACGTACGT", "ACGACGT").profile
        self.assertEqual(perfil[DiffClass.DELECION], 1)

    def test_una_insercion(self):
        perfil = align("ACGTACGT", "ACGTTACGT").profile
        self.assertEqual(perfil[DiffClass.INSERCION], 1)

    def test_una_transposicion_no_se_cuenta_como_dos_sustituciones(self):
        # `CT` -> `TC` son dos bases cambiadas, pero es UN suceso y de otra clase.
        perfil = align("AACTGG", "AATCGG").profile
        self.assertEqual(perfil[DiffClass.TRANSPOSICION], 1)
        self.assertEqual(perfil.get(DiffClass.SUSTITUCION, 0), 0)

    def test_dos_sustituciones_adyacentes_que_NO_son_transposicion(self):
        perfil = align("AACTGG", "AAGAGG").profile
        self.assertEqual(perfil.get(DiffClass.TRANSPOSICION, 0), 0)
        self.assertEqual(perfil[DiffClass.SUSTITUCION], 2)


class TestReglaDeLectura(unittest.TestCase):
    """El perfil dice de QUE investigacion se trata."""

    def test_solo_deleciones_es_compatible_con_trasvase(self):
        lectura = align("ACGTACGTAA", "ACGTACGTA").reading
        self.assertIn("trasvase", lectura.lower())

    def test_con_una_sustitucion_ya_no_lo_es(self):
        lectura = align("ACGTACGT", "ACGAACGT").reading
        self.assertIn("no se copio mal", lectura.lower())
        self.assertIn("genero", lectura.lower())

    def test_con_inserciones_tampoco(self):
        # Copiar de una pantalla no AÑADE caracteres.
        self.assertIn("genero", align("ACGTACGT", "ACGTTACGT").reading.lower())

    def test_sin_diferencias_no_hay_nada_que_leer(self):
        self.assertEqual(align("ACGT", "ACGT").reading, "")

    def test_la_regla_viaja_en_el_texto_del_informe(self):
        texto = align("ACGTACGT", "ACGAACGT").format_text()
        self.assertIn("trasvase", texto.lower())


@unittest.skipUnless(
    RATON.is_file() and FABRICADO.is_file(), "NOT_RUN: faltan los fixtures"
)
class TestRegresionDelAlineadorSobreEsteParDeFicheros(unittest.TestCase):
    """REGRESION DE ESTE ALINEADOR sobre un par de ficheros concreto.

    Lo que fija NO es una propiedad de las dos secuencias. **El recuento por clase
    depende del alineador**: el reparto de huecos lo decide la penalizacion de gap y no
    hay descomposicion canonica. `difflib` alinea las mismas dos cadenas y da 7
    deleciones, 10 inserciones y 1 sustitucion — otras 18 operaciones, tambien +4 nt
    netos, igual de validas.

    Si alguien toca `alignment.MATCH/MISMATCH/GAP` o el algoritmo, estos numeros cambian
    y este test falla. Eso es lo que tiene que pasar, y por eso el nombre dice
    «regresion del alineador» y no «perfil de las secuencias»: un fallo aqui significa
    que ha cambiado el alineador, NO que hayan cambiado los ficheros. Para eso estan los
    md5, que se comprueban en `tests/test_fixture_negativo.py`.
    """

    @classmethod
    def setUpClass(cls):
        cls.alineamiento = align(
            _utr3(), FABRICADO.read_text(encoding="ascii").strip()
        )

    def test_este_alineador_da_este_reparto(self):
        # 20 operaciones crudas (5 del + 9 ins + 6 sust) son 18 SUCESOS, porque cuatro
        # de esas sustituciones se agrupan en dos transposiciones. Sumar las seis y las
        # dos por separado seria contar cuatro cambios dos veces.
        perfil = self.alineamiento.profile
        self.assertEqual(perfil[DiffClass.DELECION], 5)
        self.assertEqual(perfil[DiffClass.INSERCION], 9)
        self.assertEqual(perfil[DiffClass.SUSTITUCION], 2)
        self.assertEqual(perfil[DiffClass.TRANSPOSICION], 2)

    def test_difflib_reparte_los_huecos_de_otra_forma(self):
        """El contraejemplo, en el test: dos descomposiciones validas del mismo cambio."""
        import difflib
        from collections import Counter

        recuento = Counter(
            tag
            for tag, *_ in difflib.SequenceMatcher(
                None, _utr3(), FABRICADO.read_text(encoding="ascii").strip(),
                autojunk=False,
            ).get_opcodes()
            if tag != "equal"
        )
        self.assertEqual(dict(recuento), {"delete": 7, "insert": 10, "replace": 1})
        self.assertEqual(sum(recuento.values()), len(self.alineamiento.differences))

    def test_pero_la_REGLA_DE_LECTURA_no_depende_del_alineador(self):
        # Se apoya en las CLASES PRESENTES, no en las frecuencias. Con el reparto de
        # difflib —inserciones y una sustitucion— la lectura es la misma: se genero.
        self.assertIn("genero", self.alineamiento.reading.lower())
        self.assertFalse(self.alineamiento.only_deletions)

    def test_y_suman_18_sucesos_no_20(self):
        self.assertEqual(len(self.alineamiento.differences), 18)
        self.assertEqual(sum(self.alineamiento.profile.values()), 18)

    def test_hay_sustituciones_luego_esto_se_genero(self):
        self.assertIn("genero", self.alineamiento.reading.lower())

    def test_las_dos_transposiciones_estan_donde_se_dijo(self):
        posiciones = sorted(
            d.ref_start
            for d in self.alineamiento.differences
            if d.kind is DiffClass.TRANSPOSICION
        )
        self.assertEqual(posiciones, [1142, 1169])

    def test_las_posiciones_divergentes_sobre_la_referencia(self):
        # Es lo que necesita el estratificador: que posiciones del 3'UTR real estan
        # tocadas. Las inserciones no ocupan posicion en la referencia.
        self.assertTrue(self.alineamiento.ref_positions)
        self.assertIn(1142, self.alineamiento.ref_positions)
        self.assertIn(1143, self.alineamiento.ref_positions)


if __name__ == "__main__":
    unittest.main()
