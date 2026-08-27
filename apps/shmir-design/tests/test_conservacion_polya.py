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


@unittest.skipUnless(
    fixture_available(HUMANO) and fixture_available(RATON),
    "NOT_RUN: faltan los fixtures de los dos 3'UTR",
)
class TestElDatoHumanoRebajaLaProbabilidadAPriori(unittest.TestCase):
    """No es solo ausencia de homologo: el gen humano ha PRESCINDIDO del hexamero.

    Un APA proximal funcional es un elemento regulador, y los elementos reguladores
    tienden a conservarse. Que el 3'UTR humano no tenga NI UNA `AATAAA` en 1606 nt
    rebaja la probabilidad a priori de que la murina sea funcional. Las dos clausulas
    van juntas y ninguna sobra: REBAJA, NO DESCARTA — puede ser diferencia real de
    especie.

    Y va pegado al TECHO de los candidatos distales, no en una seccion aparte: quien
    lee «techo indeterminado» tiene que leer ahi mismo lo que se sabe del a priori.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.polya import signal_conservation

        cls.resultado = signal_conservation(
            "AATAAA", load_3utr(HUMANO), other_name="humano"
        )

    def test_hay_una_nota_de_probabilidad_a_priori(self):
        self.assertTrue(self.resultado.prior_note())

    def test_dice_que_REBAJA(self):
        self.assertIn("rebaja", self.resultado.prior_note().lower())

    def test_y_dice_que_NO_DESCARTA(self):
        nota = self.resultado.prior_note().lower()
        self.assertIn("no lo descarta", nota)
        self.assertIn("diferencia real de especie", nota)

    def test_da_el_argumento_y_no_solo_la_conclusion(self):
        nota = self.resultado.prior_note().lower()
        self.assertIn("elemento regulador", nota)
        self.assertIn("tienden a conservarse", nota)

    def test_no_es_ausencia_de_homologo_a_secas(self):
        self.assertIn("prescindido", self.resultado.prior_note().lower())

    def test_si_la_señal_SI_estuviera_conservada_no_hay_nota(self):
        from shmir_design.polya import signal_conservation

        # Con el propio 3'UTR de raton como «otra especie», la AATAAA aparece: entonces
        # no hay nada que rebajar y la nota va vacia en vez de inventar un argumento.
        conservada = signal_conservation(
            "AATAAA", load_3utr(RATON), other_name="raton (control)"
        )
        self.assertTrue(conservada.conserved)
        self.assertEqual(conservada.prior_note(), "")

    def test_el_informe_lo_pone_PEGADO_al_techo(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        tiling = tile_utr(load_3utr(RATON))
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
        texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD, polya_conservation=self.resultado,
        )
        bloque = texto.split("── Riesgo de polyA")[1].split("── Que se ha")[0]
        self.assertIn("rebaja", bloque.lower())
        # En el MISMO bloque que el techo, y despues de el. Se ancla en «TECHO» y ya no
        # en «techo indeterminado»: con la medida aplicada siempre, el techo del ratón
        # SÍ está determinado (0,91 y 0,86 por tramos). Lo que este test protege es la
        # colocación de la nota, no que el techo sea desconocido.
        self.assertLess(bloque.index("TECHO"), bloque.lower().index("rebaja"))
