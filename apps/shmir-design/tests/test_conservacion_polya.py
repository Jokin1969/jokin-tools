"""¿Esta conservada en humano la señal de poliadenilacion del raton?

Regla 5: escritos antes.

Quedo declarado por el responsable y SIN COMPROBAR mientras no hubiera 3'UTR humano en
`data/reference/`. Ya lo hay (NM_000311.5, 1606 nt, md5 f7fdb4a8…), asi que se comprueba.

La comprobacion que SI se puede hacer sin alinear dos especies: contar los hexameros
canonicos del 3'UTR humano. Si no hay NINGUNA `AATAAA` en sus 1606 nt, la señal murina
no tiene homologo posible — y eso es mas fuerte que un alineamiento, porque no depende
de donde caiga el alineamiento.

Lo que NO se hace aqui es alinear raton contra humano con `alignment.py`: ese modulo
esta hecho para dos versiones casi identicas de la MISMA secuencia (difflib), y usarlo
entre especies daria un alineamiento sin sentido con pinta de resultado.
"""

import unittest

from shmir_design.polya import (
    SignalClass,
    find_polya_signals,
    signal_conservation,
)
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

HUMANO = REFERENCES["NM_000311.5"]
RATON = REFERENCES["NM_011170.3"]


@unittest.skipUnless(
    fixture_available(HUMANO) and fixture_available(RATON),
    "NOT_RUN: faltan los fixtures de los dos 3'UTR",
)
class TestLaSeñalMurinaNoTieneHomologoCanonico(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raton = load_3utr(RATON)
        cls.humano = load_3utr(HUMANO)

    def test_el_raton_tiene_su_AATAAA_en_288(self):
        canonicas = [
            s for s in find_polya_signals(self.raton) if s.motif == "AATAAA"
        ]
        self.assertEqual([s.position for s in canonicas], [288])

    def test_el_3utr_humano_no_tiene_NINGUNA_AATAAA(self):
        canonicas = [
            s for s in find_polya_signals(self.humano) if s.motif == "AATAAA"
        ]
        self.assertEqual(canonicas, [])

    def test_asi_que_la_señal_NO_esta_conservada(self):
        resultado = signal_conservation(
            "AATAAA", self.humano, other_name="NM_000311.5 (humano)"
        )
        self.assertFalse(resultado.conserved)

    def test_y_el_texto_lo_dice_con_la_cifra_y_no_como_declaracion(self):
        texto = signal_conservation(
            "AATAAA", self.humano, other_name="NM_000311.5 (humano)"
        ).describe()
        self.assertIn("COMPROBADO", texto)
        self.assertIn("1606", texto)
        self.assertIn("0 ", texto)
        self.assertNotIn("declarado", texto.lower())

    def test_pero_el_humano_NO_esta_libre_de_APA(self):
        # Matiz que no se puede omitir: el humano no tiene la canonica, pero si dos
        # ATTAAA clasificadas APA_POSIBLE. El riesgo no esta conservado COMO ESE
        # HEXAMERO; no es que el 3'UTR humano no tenga riesgo de APA.
        apa = [
            s for s in find_polya_signals(self.humano)
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        self.assertEqual([(s.motif, s.position) for s in apa],
                         [("ATTAAA", 955), ("ATTAAA", 1167)])

    def test_y_el_texto_trae_ese_matiz(self):
        texto = signal_conservation(
            "AATAAA", self.humano, other_name="NM_000311.5 (humano)"
        ).describe()
        self.assertIn("ATTAAA", texto)
        self.assertIn("3utr:955", texto)

    def test_no_dice_que_el_humano_este_libre_de_riesgo(self):
        texto = signal_conservation(
            "AATAAA", self.humano, other_name="NM_000311.5 (humano)"
        ).describe().lower()
        self.assertIn("no significa que", texto)


class TestLaFuncionSeNiegaALoQueNoPuedeHacer(unittest.TestCase):

    def test_un_motivo_que_no_es_señal_aborta(self):
        with self.assertRaises(ValueError):
            signal_conservation("GGGGGG", "ACGT" * 10, other_name="sonda")

    def test_sin_secuencia_aborta(self):
        from shmir_design.errors import MissingSequenceError

        with self.assertRaises(MissingSequenceError):
            signal_conservation("AATAAA", None, other_name="sonda")

    def test_sin_nombre_de_la_otra_especie_aborta(self):
        # «No esta conservada» sin decir en QUE no lo esta no es un resultado.
        with self.assertRaises(ValueError):
            signal_conservation("AATAAA", "ACGT" * 10, other_name="")


if __name__ == "__main__":
    unittest.main()
