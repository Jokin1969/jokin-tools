"""82, 92, 294: tres magnitudes que en la conversación se llaman igual.

Regla 5: escritos antes que `fragmento.lengths`.

Pedido por el responsable del proyecto (2026-09-06):

> *«Son tres magnitudes con el mismo nombre coloquial y ya nos costó una vez — que cada
> una salga siempre con su etiqueta, como las coordenadas.»*

## Y no son tres: son CINCO, que es justo el problema

Al escribirlas sale que «el intrón» son dos números y «el fragmento» otros dos:

  - **intrón vacío**, 82 nt — el del parental, de `GT` a `AG`. Es el que se compara con
    el mínimo del espliceosoma y con el rango típico de mamífero;
  - **intrón montado**, 284 nt — con el módulo dentro. Es el que se compara entre
    arquitecturas (donante→punto de ramificación);
  - **feature anotada**, 92 nt — lo que se SELECCIONA en SnapGene, contexto exónico
    incluido;
  - **fragmento de síntesis**, 294 nt — lo que se manda a sintetizar;
  - **crecimiento**, 202 pb — lo que crece el plásmido al pegar.

Con los sitios de restricción DENTRO —la opción declarada— el intrón montado son 296 y
el fragmento 306, así que el mismo nombre da dos números más. Ninguno de los cinco es
intercambiable con otro y todos se llaman «lo del intrón» al hablar.
"""

import pathlib
import unittest

from shmir_design import fragmento, introns
from shmir_design.scaffold import build_hairpin

DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DIR / "aav_casete.fa"
GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"


def _casete() -> str:
    crudo = CASETE.read_text(encoding="utf-8").splitlines()
    return "".join(l.strip() for l in crudo if not l.startswith(">")).upper()


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLasCincoMagnitudes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, label="3utr:1018"
        )
        cls.con_sitios = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, with_sites=True
        )

    def test_los_cinco_numeros_del_MVM_sin_sitios(self):
        tabla = {m.key: m.value for m in fragmento.lengths(self.frag)}
        self.assertEqual(
            tabla,
            {
                "intron_vacio": 82,
                "intron_montado": 284,
                "feature": 92,
                "fragmento": 294,
                "crecimiento": 202,
            },
        )

    def test_con_los_sitios_dentro_cambian_DOS(self):
        tabla = {m.key: m.value for m in fragmento.lengths(self.con_sitios)}
        self.assertEqual(tabla["intron_vacio"], 82)
        self.assertEqual(tabla["feature"], 92)
        self.assertEqual(tabla["intron_montado"], 296)
        self.assertEqual(tabla["fragmento"], 306)
        self.assertEqual(tabla["crecimiento"], 214)

    def test_cada_una_dice_QUE_ES_y_CON_QUE_se_compara(self):
        for magnitud in fragmento.lengths(self.frag):
            self.assertTrue(magnitud.label.strip(), magnitud.key)
            self.assertTrue(magnitud.what.strip(), magnitud.key)
            self.assertTrue(magnitud.compared_with.strip(), magnitud.key)

    def test_la_del_rango_tipico_es_el_VACIO_y_lo_dice(self):
        vacio = next(
            m for m in fragmento.lengths(self.frag) if m.key == "intron_vacio"
        )
        self.assertIn("mamífero", vacio.compared_with)
        montado = next(
            m for m in fragmento.lengths(self.frag) if m.key == "intron_montado"
        )
        self.assertNotIn("mamífero", montado.compared_with)

    def test_la_que_se_manda_a_sintetizar_es_el_FRAGMENTO(self):
        sintesis = next(
            m for m in fragmento.lengths(self.frag) if m.key == "fragmento"
        )
        self.assertIn("sintetiza", sintesis.what.lower())

    def test_se_DERIVAN_de_las_piezas_y_no_se_teclean(self):
        """Con otro intrón salen otros cinco números, sin tocar la tabla."""
        registro = introns.get("intron_quimerico")
        if not registro.provided:
            self.skipTest("NOT_RUN: falta el plásmido del intrón quimérico")
        quimerico = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=self.casete,
            intron="intron_quimerico",
        )
        tabla = {m.key: m.value for m in fragmento.lengths(quimerico)}
        self.assertEqual(tabla["intron_vacio"], 133)
        self.assertEqual(tabla["intron_montado"], 270)
        self.assertEqual(tabla["feature"], 92)
        self.assertEqual(tabla["fragmento"], 280)
        self.assertEqual(tabla["crecimiento"], 188)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestNingunNumeroSALE_SOLO(unittest.TestCase):
    """En la hoja de pedido cada número va pegado a su etiqueta, no en una columna."""

    @classmethod
    def setUpClass(cls):
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=_casete(), label="3utr:1018"
        )
        cls.hoja = fragmento.fragment_order_sheet(cls.frag)

    def test_las_cinco_salen_en_la_hoja_con_su_etiqueta(self):
        for magnitud in fragmento.lengths(self.frag):
            self.assertIn(magnitud.label, self.hoja, magnitud.key)
            self.assertIn(str(magnitud.value), self.hoja, magnitud.key)

    def test_la_hoja_DISTINGUE_el_intron_vacio_del_montado(self):
        self.assertIn("82", self.hoja)
        self.assertIn("284", self.hoja)

    def test_y_el_motivo_de_que_haga_falta_esta_escrito(self):
        self.assertIn("mismo nombre", fragmento.WHY_EACH_LENGTH_IS_LABELLED.lower())


if __name__ == "__main__":
    unittest.main()
