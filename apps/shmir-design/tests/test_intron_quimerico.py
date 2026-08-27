"""El intrón quimérico del plásmido de Addgene #198131, extraído POR LA ANOTACIÓN.

Nada de esto se teclea: el plásmido está en `data/reference/addgene_198131.gb` y todo
sale de él. Lo que se declaró en el encargo entra aquí como VALOR ESPERADO contra el que
se comprueba lo extraído — que es lo contrario de copiarlo. Si algo no cuadra, el test
falla y la carga aborta, que es lo que se pidió.

El punto de ramificación se mide con la MISMA convención que el MVM —`YURAY` 18-40— y
eso tiene un coste que se fija aquí para que nadie lo descubra por sorpresa: en este
intrón NO señala ningún candidato. `CTGAC`, el consenso de mamífero de manual, no casa
porque su segunda base es T. Se acepta a propósito: comparar dos intrones medidos con
criterios distintos no compara nada, y comparar es el motivo entero de tener un segundo
intrón. La consecuencia va a la vista, no escondida — sin candidato, la regla del módulo
aguas arriba sale `NOT_RUN` y no `PASS`.
"""

import hashlib
import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.introns import (
    BRANCH_WINDOW,
    INTRONS,
    insertion_window,
    locate_elements,
)

PLASMIDO = Path(__file__).resolve().parent.parent / "data" / "reference" / "addgene_198131.gb"

# Declarados en el encargo. Aquí son lo que se COMPRUEBA, no la fuente.
PLASMIDO_MD5 = "0da57dc0f4d15e661f2ffe82a82dd5c6"
INTRON_MD5 = "5cd85dcf763f8e7df6f4e84ada503be0"
RANGO = (1216, 1348)
LARGO = 133
CONTEXTO_5 = "TGAGGCACTGGGCAG"
CONTEXTO_3 = "GTGTCCACTCCCAGT"


def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8"), usedforsecurity=False).hexdigest()


@unittest.skipUnless(PLASMIDO.is_file(), f"falta {PLASMIDO}")
class TestLaExtraccionCUADRA(unittest.TestCase):

    def setUp(self):
        from shmir_design.genbank import load_plasmid_feature

        self.feature = load_plasmid_feature(
            PLASMIDO, key="intron", label="chimeric intron"
        )

    def test_el_plasmido_es_el_que_dice_ser(self):
        self.assertEqual(len(self.feature.plasmid), 9356)
        self.assertEqual(_md5(self.feature.plasmid), PLASMIDO_MD5)

    def test_la_feature_esta_donde_se_declaro(self):
        self.assertEqual((self.feature.start, self.feature.end), RANGO)

    def test_la_longitud_y_el_md5_del_INTRON_cuadran(self):
        self.assertEqual(len(self.feature.sequence), LARGO)
        self.assertEqual(_md5(self.feature.sequence), INTRON_MD5)

    def test_los_contextos_exonicos_salen_de_las_COORDENADAS(self):
        # No se piden aparte: se derivan del fichero y se contrastan con lo declarado.
        self.assertEqual(self.feature.context_5(15), CONTEXTO_5)
        self.assertEqual(self.feature.context_3(15), CONTEXTO_3)

    def test_una_feature_que_no_esta_ABORTA(self):
        from shmir_design.genbank import load_plasmid_feature

        with self.assertRaises(ShmirDesignError):
            load_plasmid_feature(PLASMIDO, key="intron", label="no existe")

    def test_y_un_md5_que_no_cuadra_ABORTA(self):
        from shmir_design.genbank import load_plasmid_feature

        with self.assertRaises(ShmirDesignError) as ctx:
            load_plasmid_feature(
                PLASMIDO, key="intron", label="chimeric intron",
                expected_md5="0" * 32,
            )
        self.assertIn("md5", str(ctx.exception))


@unittest.skipUnless(PLASMIDO.is_file(), f"falta {PLASMIDO}")
class TestLosElementos(unittest.TestCase):

    def setUp(self):
        self.secuencia = INTRONS["intron_quimerico"].require_sequence()
        self.elementos = locate_elements(self.secuencia, name="intron_quimerico")

    def test_el_donante_es_GTAAGT__consenso_perfecto(self):
        self.assertTrue(self.secuencia.startswith("GTAAGT"))

    def test_el_aceptor_es_AG_terminal(self):
        self.assertEqual(self.elementos.acceptor.sequence, "AG")
        self.assertEqual(self.elementos.acceptor.end, LARGO)

    def test_el_tracto_son_11_pirimidinas_en_119_129(self):
        # Frente a las 9 del MVM. Se localiza por secuencia, no se teclea. Y NO pega con
        # el aceptor: hay un `AC` en medio, que es lo que rompía la regla anterior.
        self.assertEqual(self.elementos.ppt.sequence, "CCTTTCTCTCC")
        self.assertEqual((self.elementos.ppt.start, self.elementos.ppt.end), (119, 129))
        self.assertEqual(len(self.elementos.ppt.sequence), 11)

    def test_NO_lleva_GTGAGCG__no_aporta_segundo_donante_criptico(self):
        self.assertNotIn("GTGAGCG", self.secuencia)

    def test_con_la_convencion_UNICA_no_sale_ningun_candidato(self):
        # El coste declarado de medir los tres con el mismo criterio. Se fija aquí para
        # que cambiarlo tenga que pasar por este test y no se descubra en una corrida.
        self.assertEqual(self.elementos.branch_candidates, ())
        self.assertIsNone(self.elementos.branch_point)

    def test_y_el_resumen_dice_que_NO_ES_que_no_lo_haya(self):
        texto = "\n".join(self.elementos.describe())
        self.assertIn("NINGÚN candidato", texto)
        self.assertIn("no se ha podido señalar", texto)


class TestLaCONVENCIONUnica(unittest.TestCase):
    """Un solo criterio para los tres, y su coste medido."""

    def test_la_ventana_declarada_es_18_40(self):
        self.assertEqual(BRANCH_WINDOW, (18, 40))

    def test_el_MVM_tiene_su_candidato(self):
        elementos = locate_elements(
            INTRONS["mvm_actual"].empty_sequence, name="mvm_actual"
        )
        self.assertEqual(len(elementos.branch_candidates), 1)
        self.assertEqual(elementos.branch_candidates[0].sequence, "TAATT")

    def test_el_criterio_se_declara_como_CONVENCION_y_no_como_cita(self):
        from shmir_design.introns import BRANCH_CRITERION, WHY_ONE_CRITERION

        self.assertIn("CONVENCIÓN DECLARADA", BRANCH_CRITERION)
        self.assertIn("NO una cita", BRANCH_CRITERION)
        self.assertIn("convención declarada", WHY_ONE_CRITERION.lower())

    @unittest.skipUnless(PLASMIDO.is_file(), f"falta {PLASMIDO}")
    def test_el_COSTE_esta_medido_y_escrito(self):
        # `YTNAY` habría dado dos candidatos aquí. Se descartó, y el número queda
        # registrado para que la decisión se pueda revisar con datos y no de memoria.
        secuencia = INTRONS["intron_quimerico"].require_sequence()
        pirimidinas = set("CT")
        a = len(secuencia) - 1
        otros = [
            (j, secuencia[j - 1:j + 4])
            for d in range(20, 41)
            if (j := a - d) >= 1 and j + 4 <= len(secuencia)
            and secuencia[j - 1] in pirimidinas
            and secuencia[j] == "T"
            and secuencia[j + 2] == "A"
            and secuencia[j + 4 - 1] in pirimidinas
        ]
        self.assertEqual(sorted(otros), [(100, "CTTAC"), (104, "CTGAC")])


@unittest.skipUnless(PLASMIDO.is_file(), f"falta {PLASMIDO}")
class TestDondeCabeElModulo(unittest.TestCase):

    def setUp(self):
        self.elementos = locate_elements(
            INTRONS["intron_quimerico"].require_sequence(), name="intron_quimerico"
        )
        self.ventana = insertion_window(self.elementos, module_length=149)

    def test_empieza_tras_el_donante_y_acaba_antes_del_tracto(self):
        self.assertEqual(self.ventana.ranges[0][0], self.elementos.donor.end + 1)
        self.assertEqual(self.ventana.ranges[-1][1], self.elementos.ppt.start - 1)

    def test_sin_candidato_la_regla_de_AGUAS_ARRIBA_no_se_puede_comprobar(self):
        # NOT_RUN y no PASS: no haber podido comprobarlo no es que se cumpla.
        from shmir_design.filters import FilterState
        from shmir_design.introns import check_module_upstream

        resultado = check_module_upstream(
            self.elementos, after=self.ventana.ranges[0][0]
        )
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("NOT_RUN, no PASS", resultado.reason)

    def test_hay_MAS_margen_que_en_el_MVM(self):
        # El número que decide si la opción 3 necesita espaciadores o un intrón más
        # largo. Con 133 pb hay margen; con 82 casi no lo había.
        mvm = insertion_window(
            locate_elements(INTRONS["mvm_actual"].empty_sequence, name="mvm"),
            module_length=149,
        )
        self.assertGreater(len(self.ventana.options), len(mvm.options))


if __name__ == "__main__":
    unittest.main()
