"""En humano estamos en MODO ASUMIDO, y la app tiene que decirlo.

Regla 5: escrito antes.

Sale de una consecuencia del cambio de hoy que no era obvia: con el ratón las DOS
señales `APA_POSIBLE` están MEDIDAS —el `AATATA` de `3utr:236` y el `AATAAA` de
`3utr:288` son dos de los tres sitios anclados de PolyA_DB—, así que el caso «canónico,
asumido» **no existe en esta especie**.

Sólo existe en el **humano**, y no por casualidad: la tabla murina se aplica **por md5
del 3'UTR**, así que sobre el humano devuelve `None` y sus dos `ATTAAA` (`3utr:955` y
`3utr:1167`) se quedan clasificadas por **canonicidad y sin un solo dato de uso**.

Eso significa que **cuando llegue el panel humano estaremos donde estábamos con el ratón
antes de mirar PolyA_DB**: con un supuesto en vez de una medida, y con el defecto
tratando esos hexámeros como no funcionales — la hipótesis menos conservadora, que en el
ratón resultó ser la falsa.

PolyA_DB v4 tiene entrada para **hg38 / PRNP** y quedó pendiente desde que se miró la
murina. El fichero se llama `apa_medido_human.tsv` y ya lo pide el gestor; lo que faltaba
es que la app dijera **qué se pierde mientras no esté**, en vez de listarlo como un
fichero más.
"""

import unittest

from shmir_design.polya import SignalClass
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.species import required_files, resolve
from shmir_design.tiling import tile_utr

HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(HUMANO)


class TestElGestorLoPIDE(unittest.TestCase):
    def test_hay_una_fila_de_APA_para_el_humano_y_lleva_su_especie(self):
        fila = next(f for f in required_files(resolve("human")) if f.role == "apa")
        self.assertEqual(fila.filename, "apa_medido_human.tsv")

    def test_y_el_del_raton_NO_sirve_para_el(self):
        # No es una precaucion teorica: la tabla se aplica por md5 del 3'UTR.
        murino = next(f for f in required_files(resolve("mouse")) if f.role == "apa")
        humano = next(f for f in required_files(resolve("human")) if f.role == "apa")
        self.assertNotEqual(murino.filename, humano.filename)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture humano")
class TestSusDosSeñalesSonSUPUESTOS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe = tile_utr(load_3utr(HUMANO))

    def test_la_tabla_murina_NO_se_aplica(self):
        self.assertIsNone(self.informe.measured_apa)

    def test_y_no_es_porque_se_excluyera(self):
        # `None` aqui significa «esta tabla no habla de esta secuencia», que es distinto
        # de «alguien la excluyo». Si fueran lo mismo, no se sabria cual es.
        self.assertEqual(self.informe.apa_excluded_reason, "")

    def test_sus_dos_APA_POSIBLE_entran_por_CANONICIDAD(self):
        apa = [
            s for s in self.informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        self.assertEqual([s.position for s in apa], [955, 1167])
        for s in apa:
            with self.subTest(s.position):
                self.assertEqual(s.evidence, "canonicidad")

    def test_y_la_etiqueta_lo_dice_con_esa_palabra(self):
        apa = next(
            s for s in self.informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        )
        self.assertIn("asumido", apa.classification_label)


class TestLaFichaDICEQueEsta_PENDIENTE(unittest.TestCase):
    def test_nombra_hg38_y_PRNP(self):
        from shmir_design.obtencion import resolve_ficha

        texto = resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("human")
        ).render()
        self.assertIn("hg38", texto)
        self.assertIn("PRNP", texto)

    def test_y_dice_QUE_SE_PIERDE_mientras_no_este(self):
        from shmir_design.obtencion import resolve_ficha

        texto = resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("human")
        ).render().lower()
        self.assertIn("asumido", texto)

    def test_la_del_raton_no_habla_de_hg38(self):
        from shmir_design.obtencion import resolve_ficha

        texto = resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("mouse")
        ).render()
        self.assertNotIn("hg38", texto)


if __name__ == "__main__":
    unittest.main()
