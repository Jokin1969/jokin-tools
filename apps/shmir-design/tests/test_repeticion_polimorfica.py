"""`repeticion_polimorfica` es OTRO motivo, no una etiqueta del mismo.

Regla 5: escritos antes.

Los dos salen del mismo hallazgo y apuntan a cosas distintas:

  `repetitivo`               → ESTABILIDAD DEL GENOMA AAV (y, en la diana, una guia con
                               miles de sitios perfectos).
  `repeticion_polimorfica`   → VIABILIDAD CLINICA. Un microsatelite varia en NUMERO DE
                               REPETICIONES entre individuos, asi que una guia ahi
                               tendria respondedores y no respondedores por variacion de
                               LONGITUD.

Y hay un hueco que no cubre nadie: **gnomAD anota sustituciones y capta mal la variacion
de longitud**, asi que el filtro de variacion NO cubre este riesgo. Decirlo importa,
porque «gnomAD limpio» invita a creer que la ventana esta comprobada.

El caso real: el `(TA)n` humano de `3utr:1268-1301` solapa cinco ventanas elegibles, y
esas cinco caen por TRES motivos a la vez.
"""

import unittest
from pathlib import Path

from shmir_design import masking
from shmir_design.filters import FilterState

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
PRESENTES = (DIR / "rmsk_human.out").is_file() and (DIR / "rmsk_human.tbl").is_file()


def _mascara_humana():
    return masking.parse_rmsk_out(
        (DIR / "rmsk_human.out").read_text(encoding="utf-8"),
        source="rmsk_human.out", version="4.0.9",
        checksum="bcc33dbc7a65e74690f5f9d1fb270035",
        expected_species="homo sapiens", library="Dfam_3.0",
        summary=(DIR / "rmsk_human.tbl").read_text(encoding="utf-8"),
    )


class TestSonDosMotivosDistintos(unittest.TestCase):

    def test_el_filtro_tiene_su_propio_nombre(self):
        self.assertEqual(masking.POLYMORPHIC_FILTER_NAME, "repeticion_polimorfica")
        self.assertNotEqual(masking.POLYMORPHIC_FILTER_NAME, masking.FILTER_NAME)

    def test_cada_uno_declara_a_QUE_aplica(self):
        self.assertIn("genoma aav", masking.WHY_REPEAT.lower())
        self.assertIn("clinica", masking.WHY_POLYMORPHIC.lower())

    def test_el_polimorfico_habla_de_respondedores(self):
        texto = masking.WHY_POLYMORPHIC.lower()
        self.assertIn("respondedores", texto)
        self.assertIn("longitud", texto)

    def test_y_dice_que_gnomAD_NO_lo_cubre(self):
        texto = masking.WHY_POLYMORPHIC
        self.assertIn("gnomAD", texto)
        self.assertIn("sustituciones", texto.lower())

    def test_la_clase_polimorfica_va_DECLARADA(self):
        self.assertIn("Simple_repeat", masking.POLYMORPHIC_FAMILIES)
        self.assertIn("declarad", masking.POLYMORPHIC_CRITERION.lower())


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_human")
class TestSobreElTAnHumano(unittest.TestCase):

    def setUp(self):
        self.mascara = _mascara_humana()

    def test_el_elemento_es_de_familia_polimorfica(self):
        self.assertTrue(
            masking.is_polymorphic(self.mascara.elements[0]),
            "el (TA)n es un microsatelite: varia en número de repeticiones",
        )

    def test_una_ventana_que_lo_solapa_falla_los_DOS(self):
        # tx:2097-2130. Una ventana que lo toque cae por repetitivo Y por polimorfico.
        repetitivo = masking.filter_repeats(2100, 2121, self.mascara)
        polimorfico = masking.filter_polymorphic(2100, 2121, self.mascara)
        self.assertIs(repetitivo.state, FilterState.FAIL)
        self.assertIs(polimorfico.state, FilterState.FAIL)

    def test_y_los_motivos_son_DISTINTOS(self):
        r = masking.filter_repeats(2100, 2121, self.mascara).reason
        p = masking.filter_polymorphic(2100, 2121, self.mascara).reason
        self.assertNotEqual(r, p)
        self.assertIn("respondedores", p.lower())
        self.assertNotIn("respondedores", r.lower())

    def test_una_ventana_lejos_pasa_los_dos(self):
        self.assertIs(
            masking.filter_repeats(100, 121, self.mascara).state, FilterState.PASS
        )
        self.assertIs(
            masking.filter_polymorphic(100, 121, self.mascara).state, FilterState.PASS
        )

    def test_sin_mascara_los_dos_son_NOT_RUN(self):
        self.assertIs(masking.filter_repeats(1, 22, None).state, FilterState.NOT_RUN)
        self.assertIs(
            masking.filter_polymorphic(1, 22, None).state, FilterState.NOT_RUN
        )

    def test_un_elemento_NO_polimorfico_solo_dispara_el_primero(self):
        # Un SINE es disperso, no varia en longitud entre individuos: repetitivo si,
        # polimorfico no. Se comprueba sobre un elemento construido con la MISMA clase
        # que usa el parser, no sobre una secuencia inventada.
        from dataclasses import replace

        sine = replace(self.mascara.elements[0], name="AluSx", family="SINE/Alu")
        self.assertFalse(masking.is_polymorphic(sine))


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_human")
class TestElTRIPLEMotivoDeLasCinco(unittest.TestCase):
    """Las cinco ventanas humanas caen por tres cosas a la vez, y se anota asi."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr
        from shmir_design.tiling import tile_utr

        if not fixture_available(REFERENCES["NM_000311.5"]):
            raise unittest.SkipTest("falta NM_000311.5.fa")
        cls.informe = tile_utr(load_3utr(REFERENCES["NM_000311.5"]))
        # El informe tila el 3'UTR y la mascara viene en coordenadas del transcrito:
        # `mask_offset=829` para BUSCAR, `label_offset=0` porque las etiquetas ya son
        # del 3'UTR. Son dos desfases distintos y meterlos en uno marcaba ventanas a
        # 800 nt del elemento.
        cls.filas = masking.triple_motive_rows(
            cls.informe, _mascara_humana(), mask_offset=829, label_offset=0
        )

    def test_son_las_CINCO(self):
        self.assertEqual(
            [f.start for f in self.filas], [1247, 1249, 1250, 1251, 1252]
        )

    def test_cada_una_trae_los_TRES_motivos(self):
        for fila in self.filas:
            self.assertEqual(len(fila.motives), 3)

    def test_y_se_llaman_asi(self):
        self.assertEqual(
            sorted(self.filas[0].motives),
            sorted([masking.FILTER_NAME, "repeticion_polimorfica", "techo_apa"]),
        )

    def test_el_tercero_es_estar_por_detras_de_las_DOS_ATTAAA(self):
        texto = self.filas[0].describe()
        self.assertIn("3utr:955", texto)
        self.assertIn("3utr:1167", texto)

    def test_el_texto_dice_que_son_TRES_ejes_distintos(self):
        texto = masking.describe_triple(self.filas)
        self.assertIn("TRES", texto.upper())
        self.assertIn("gnomAD", texto)

    def test_sin_filas_no_se_dice_nada(self):
        self.assertEqual(masking.describe_triple(()), "")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_human")
class TestLosDOSDesfasesNoSonElMismo(unittest.TestCase):
    """Meterlos en uno marcaba ventanas a 800 nt del elemento, y sin dar ningun error.

    Es el caso del principio: `3utr:1275` es una posicion valida, asi que ningun
    invariante de rango la caza. Lo unico que la caza es mirar la salida —o un test que
    fije QUE ventanas, no cuantas.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.reference import (
            REFERENCES, fixture_available, load_3utr, load_reference,
        )
        from shmir_design.tiling import tile_utr

        r = REFERENCES["NM_000311.5"]
        if not fixture_available(r):
            raise unittest.SkipTest("falta NM_000311.5.fa")
        cls.mascara = _mascara_humana()
        cls.sobre_3utr = tile_utr(load_3utr(r))
        cls.sobre_tx = tile_utr(
            load_reference(r),
            anatomy=Anatomy(
                length=r.length, utr5=r.utr5, cds=r.cds, utr3=r.utr3,
                source=RegionSource.ANOTACION_GENBANK,
            ),
        )

    def test_sobre_el_3UTR_van_829_y_0(self):
        filas = masking.triple_motive_rows(
            self.sobre_3utr, self.mascara, mask_offset=829, label_offset=0
        )
        self.assertEqual([f.start for f in filas], [1247, 1249, 1250, 1251, 1252])

    def test_sobre_el_TRANSCRITO_van_0_y_829_y_dan_LO_MISMO(self):
        filas = masking.triple_motive_rows(
            self.sobre_tx, self.mascara, mask_offset=0, label_offset=829
        )
        self.assertEqual([f.start for f in filas], [1247, 1249, 1250, 1251, 1252])

    def test_intercambiarlos_da_OTRAS_ventanas_sin_dar_ningun_error(self):
        # La demostracion de por que hacen falta dos: con los desfases cruzados salen
        # ventanas plausibles, etiquetadas sin problema, y equivocadas.
        malas = masking.triple_motive_rows(
            self.sobre_tx, self.mascara, mask_offset=829, label_offset=829
        )
        self.assertNotEqual(
            [f.start for f in malas], [1247, 1249, 1250, 1251, 1252]
        )
