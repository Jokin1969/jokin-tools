"""El APA sube a FRENTE BLOQUEANTE. DECIDIDO (2026-08-26).

Regla 5: escritos antes.

La cuenta que lo decide: los sitios inmunes por tramo son 20/0/0 —todos en el tercio
proximal— y el espaciado deja meter cuatro. Con un panel de diez, eso significa que
SEIS DE LOS DIEZ candidatos comparten un unico modo de fallo, y el rebalanceo tiene tope
en cuatro plazas.

La consecuencia, que va escrita con esas palabras: si la fraccion de isoforma corta es
alta, seis de diez candidatos entran al cribado con un TECHO INDISTINGUIBLE DE UN shmiR
MALO. Un candidato con techo 0,3 y uno que simplemente no funciona dan la misma lectura
en la placa.

Por eso `fraccion_isoforma_larga` deja de ser «importante» y pasa a ser el CUARTO frente
bloqueante, junto a especificidad, repetitivos y seed a nivel FAIL. Y lo publicado va
antes que el banco, con la palabra confirmacion.
"""

import unittest
from pathlib import Path

from shmir_design.polya import Tercio
from shmir_design.selection import SelectionConfig, blocking_fronts, select_from_report

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _piezas(candidatos=10):
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.tiling import tile_utr

    tiling = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
    seleccion = select_from_report(
        tiling,
        SelectionConfig(
            n_candidates=candidatos,
            apa_immune_quota=4,
            apa_immune_before=303,
            tercio_quota=(
                (Tercio.PROXIMAL, 4), (Tercio.MEDIO, 3), (Tercio.DISTAL, 2),
            ),
        ),
    )
    return tiling, seleccion


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElAPAEsUnFrenteBloqueante(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.frentes = blocking_fronts(cls.tiling, cls.seleccion)

    def test_el_APA_se_SUMA_a_los_filtros_en_NOT_RUN(self):
        # Cuantos frentes de recurso haya depende de que ficheros se hayan cargado; lo
        # que fija este test es que el APA es UNO MAS, no uno de ellos.
        self.assertEqual(
            len(self.frentes), len(self.seleccion.not_run_filters) + 1
        )

    def test_y_uno_de_ellos_es_el_APA(self):
        self.assertIn("fraccion_isoforma_larga", [f.name for f in self.frentes])

    def test_los_demas_son_los_filtros_en_NOT_RUN(self):
        de_recurso = {f.name for f in self.frentes} - {"fraccion_isoforma_larga"}
        self.assertEqual(de_recurso, set(self.seleccion.not_run_filters))

    def test_con_los_tres_ficheros_cargados_quedarian_CUATRO(self):
        # especificidad, repeticiones, seed_colision y el APA. Los otros dos frentes de
        # esta corrida (seed y transgen) se cierran con mature.fa y el casete, que no se
        # versionan; por eso la cuenta se comprueba asi y no con un 4 clavado.
        de_recurso = {f.name for f in self.frentes} - {"fraccion_isoforma_larga"}
        pendientes = de_recurso - {"seed", "transgen"}
        self.assertEqual(
            sorted(pendientes | {"fraccion_isoforma_larga"}),
            ["especificidad", "fraccion_isoforma_larga", "repeticiones", "seed_colision"],
        )

    def test_el_frente_del_APA_trae_la_cuenta_que_lo_justifica(self):
        apa = [f for f in self.frentes if f.name == "fraccion_isoforma_larga"][0]
        self.assertIn("6 de 10", apa.reason)
        self.assertIn("20/0/0", apa.reason)
        self.assertIn("cuatro", apa.reason.lower())

    def test_y_la_frase_que_explica_POR_QUE_bloquea(self):
        apa = [f for f in self.frentes if f.name == "fraccion_isoforma_larga"][0]
        self.assertIn("INDISTINGUIBLE DE UN shmiR MALO", apa.reason)

    def test_dice_que_lo_publicado_va_ANTES_y_es_confirmacion(self):
        apa = [f for f in self.frentes if f.name == "fraccion_isoforma_larga"][0]
        self.assertIn("PolyA_DB", apa.reason)
        self.assertIn("confirmacion", apa.reason.lower())
        self.assertLess(apa.reason.index("PolyA_DB"), apa.reason.index("RT-qPCR"))

    def test_sin_candidatos_con_techo_el_frente_NO_existe(self):
        # Si todos fueran inmunes, la fraccion no bloquearia nada. El frente sale del
        # dato, no de una lista fija.
        from shmir_design.reference import REFERENCES, load_3utr
        from shmir_design.tiling import tile_utr

        tiling = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
        solo_inmunes = select_from_report(
            tiling,
            SelectionConfig(
                n_candidates=4, apa_immune_quota=4, apa_immune_before=303,
                require_one_per_tercio=False,
            ),
        )
        nombres = [f.name for f in blocking_fronts(tiling, solo_inmunes)]
        self.assertNotIn("fraccion_isoforma_larga", nombres)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLoQueDiceElInforme(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD

        tiling, seleccion = _piezas()
        cls.texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )

    def test_el_informe_cuenta_los_frentes_e_incluye_el_APA(self):
        self.assertIn("PROVISIONAL EN 6 FRENTE(S)", self.texto)
        self.assertIn("fraccion_isoforma_larga:", self.texto)

    def test_y_el_APA_esta_entre_ellos_con_su_cifra(self):
        self.assertIn("fraccion_isoforma_larga", self.texto)
        self.assertIn("6 de 10", self.texto)

    def test_no_se_pide_oligo_hasta_que_TODOS_tengan_veredicto(self):
        self.assertIn("NO SE PIDE OLIGO", self.texto)
        self.assertIn("tengan veredicto", self.texto)
