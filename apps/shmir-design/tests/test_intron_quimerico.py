"""El intrón quimérico del plásmido de Addgene #198131, extraído POR LA ANOTACIÓN.

Nada de esto se teclea: el plásmido está en `data/reference/addgene_198131.gb` y todo
sale de él. Lo que se declaró en el encargo entra aquí como VALOR ESPERADO contra el que
se comprueba lo extraído — que es lo contrario de copiarlo. Si algo no cuadra, el test
falla y la carga aborta, que es lo que se pidió.

El punto de ramificación se mide con la MISMA convención que el MVM, y esa convención
está CALIBRADA contra los dos: `YTNAY` con la A de ramificación en la ventana 18-40. La
prueba que la eligió vive en `test_calibracion_ramificacion.py` y es la justificación —
el motivo anterior, `YURAY`, perdía `CTGAC`, el punto canónico de mamífero que este
intrón lleva dentro.
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

    def test_salen_LOS_DOS_candidatos_y_no_se_elige(self):
        self.assertEqual(
            {(c.start, c.sequence) for c in self.elementos.branch_candidates},
            {(100, "CTTAC"), (104, "CTGAC")},
        )
        self.assertTrue(self.elementos.branch_ambiguous)

    def test_el_CANONICO_de_mamifero_esta_dentro(self):
        # `CTGAC`. Que aparezca es la prueba de que el motivo está bien calibrado: el
        # anterior lo perdía y por eso se cambió.
        self.assertIn("CTGAC", {c.sequence for c in self.elementos.branch_candidates})

    def test_cada_uno_trae_su_A_y_su_distancia(self):
        por_motivo = {c.sequence: c for c in self.elementos.branch_candidates}
        self.assertEqual((por_motivo["CTGAC"].branch_a, por_motivo["CTGAC"].to_acceptor), (107, 25))
        self.assertEqual((por_motivo["CTTAC"].branch_a, por_motivo["CTTAC"].to_acceptor), (103, 29))

    def test_punto_ACEPTOR_es_un_INTERVALO(self):
        # Con dos candidatos no hay «el» número. 25-29 nt, frente a los 36 del MVM.
        self.assertEqual(self.elementos.branch_to_acceptor_range, (25, 29))

    def test_y_el_resumen_saca_los_dos_y_el_intervalo(self):
        texto = "\n".join(self.elementos.describe())
        self.assertIn("CTGAC", texto)
        self.assertIn("CTTAC", texto)
        self.assertIn("25-29 nt", texto)
        self.assertIn("no se elige", texto.lower())


class TestLaCONVENCIONUnica(unittest.TestCase):
    """Un solo criterio para los tres, y CALIBRADO contra los dos casos conocidos."""

    def test_la_ventana_declarada_es_18_40(self):
        self.assertEqual(BRANCH_WINDOW, (18, 40))

    def test_el_MVM_tiene_su_candidato(self):
        elementos = locate_elements(
            INTRONS["mvm_actual"].empty_sequence, name="mvm_actual"
        )
        self.assertEqual(len(elementos.branch_candidates), 1)
        self.assertEqual(elementos.branch_candidates[0].sequence, "TTAAT")

    def test_el_criterio_se_declara_como_CONVENCION_y_dice_que_esta_calibrado(self):
        from shmir_design.introns import BRANCH_CRITERION, WHY_YTNAY_CALIBRADO

        self.assertIn("CONVENCIÓN DECLARADA", BRANCH_CRITERION)
        self.assertIn("NO una cita", BRANCH_CRITERION)
        self.assertIn("CALIBRADA", BRANCH_CRITERION)
        self.assertIn("calibración", WHY_YTNAY_CALIBRADO.lower())
        self.assertIn("CTGAC", WHY_YTNAY_CALIBRADO)

    def test_la_prueba_de_calibracion_EXISTE_y_es_la_justificacion(self):
        # No basta con que el criterio esté escrito: tiene que estar la prueba que lo
        # eligió, porque sin ella «YTNAY» es otra preferencia entre cadenas.
        from pathlib import Path

        prueba = Path(__file__).resolve().parent / "test_calibracion_ramificacion.py"
        self.assertTrue(prueba.is_file())


@unittest.skipUnless(PLASMIDO.is_file(), f"falta {PLASMIDO}")
class TestDondeCabeElModulo(unittest.TestCase):

    def setUp(self):
        self.elementos = locate_elements(
            INTRONS["intron_quimerico"].require_sequence(), name="intron_quimerico"
        )
        self.ventana = insertion_window(self.elementos, module_length=149)

    def test_empieza_tras_el_donante_y_acaba_antes_del_PRIMER_candidato(self):
        primero = min(c.start for c in self.elementos.branch_candidates)
        self.assertEqual(self.ventana.ranges[0][0], self.elementos.donor.end + 1)
        self.assertEqual(self.ventana.ranges[-1][1], primero - 1)
        self.assertEqual(self.ventana.ranges, ((3, 99),))

    def test_la_regla_de_AGUAS_ARRIBA_ahora_SI_se_puede_comprobar(self):
        # Con el motivo recalibrado hay candidatos, así que la regla pasa de NOT_RUN a
        # PASS. Era el coste que se pagaba por el motivo mal calibrado.
        from shmir_design.filters import FilterState
        from shmir_design.introns import check_module_upstream

        resultado = check_module_upstream(
            self.elementos, after=self.ventana.ranges[0][0]
        )
        self.assertIs(resultado.state, FilterState.PASS)

    def test_y_ninguna_opcion_invade_a_los_candidatos(self):
        prohibidas = {
            p for c in self.elementos.branch_candidates
            for p in range(c.start, c.end + 1)
        }
        for opcion in self.ventana.options:
            self.assertNotIn(opcion.after, prohibidas)

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
