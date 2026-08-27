"""Dos cosas que hay que DECLARAR, no deducir.

Regla 5: escritos antes.

1. `3utr:200` contra el `AATATA` de `3utr:236`. La ventana `200-221` no contiene el
   hexamero, pero pasa cerca de la zona prohibida y el lector no tiene por que hacer la
   resta. El veredicto se emite, con la holgura y con el flanco al que cambiaria.

2. `chr2:+:131938392`. Es el PAS con MAS expresion de los tres y es el NUMERADOR de la
   fraccion larga, y su lectura no esta resuelta:
     (a) es el racimo del terminal → 0,86 es correcto;
     (b) es un corte propio → hay un tercer corte por delante del terminal.
   Cerrar hacia (a) porque es la lectura que sostiene el numero que ya tenemos seria
   exactamente lo que no se puede hacer.
"""

import unittest

from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElVeredictoDe3utr200(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.selection import (
            SelectionConfig, promotion_clearance, select_from_report,
        )
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        cls.informe = tile_utr(utr3)
        cls.seleccion = select_from_report(
            cls.informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
        )
        cls.holguras = promotion_clearance(cls.informe, cls.seleccion)

    def _fila(self, inicio):
        return next(f for f in self.holguras.rows if f.start == inicio)

    def test_3utr_200_esta_en_la_tabla(self):
        self.assertIn(200, [f.start for f in self.holguras.rows])

    def test_su_veredicto_es_PASA(self):
        self.assertTrue(self._fila(200).passes)

    def test_la_ventana_NO_contiene_el_hexamero(self):
        fila = self._fila(200)
        self.assertEqual((fila.start, fila.end), (200, 221))
        self.assertLess(fila.end, fila.signal.position)

    def test_y_la_holgura_a_la_ZONA_PROHIBIDA_es_de_4_nt(self):
        self.assertEqual(self._fila(200).clearance, 4)

    def test_la_holgura_al_HEXAMERO_es_de_14(self):
        self.assertEqual(self._fila(200).distance_to_hexamer, 14)

    def test_se_emite_a_partir_de_QUE_flanco_cambiaria(self):
        # Con el flanco por defecto de 10 pasa; con 15 caeria. Es la sensibilidad de la
        # decision, y sin ella «PASA» parece mas solido de lo que es.
        self.assertEqual(self._fila(200).flip_flank, 15)

    def test_el_texto_lo_DECLARA_y_no_lo_deja_deducir(self):
        texto = self.holguras.describe()
        self.assertIn("3utr:200", texto)
        self.assertIn("AATATA", texto)
        self.assertIn("4 nt", texto)
        self.assertIn("15", texto)

    def test_los_que_estan_MUY_lejos_no_ensucian_la_tabla(self):
        # 3utr:1018 no tiene nada que ver con esta señal; sacarlo aqui seria ruido.
        self.assertNotIn(1018, [f.start for f in self.holguras.rows])

    def test_sin_promocion_no_hay_tabla(self):
        from shmir_design.selection import (
            SelectionConfig, promotion_clearance, select_from_report,
        )
        from shmir_design.tiling import tile_utr

        sin = tile_utr(load_3utr(RATON))
        vacio = promotion_clearance(
            sin, select_from_report(sin, SelectionConfig(n_candidates=10))
        )
        self.assertEqual(vacio.rows, ())
        self.assertEqual(vacio.describe(), "")


class TestElCaboSueltoDe131938392(unittest.TestCase):

    def setUp(self):
        from shmir_design.apa import CLUSTER_READING

        self.cabo = CLUSTER_READING

    def test_esta_declarado_como_NO_RESUELTO(self):
        self.assertFalse(self.cabo.resolved)
        self.assertIn("NO RESUELTO", self.cabo.describe()[0].upper())

    def test_dice_que_es_el_PAS_con_mas_expresion_y_el_NUMERADOR(self):
        texto = "\n".join(self.cabo.describe())
        self.assertIn("numerador", texto.lower())
        self.assertIn("70,5", texto.replace(".", ","))

    def test_trae_las_DOS_lecturas_con_su_consecuencia(self):
        texto = "\n".join(self.cabo.describe())
        self.assertIn("(a)", texto)
        self.assertIn("(b)", texto)
        self.assertIn("0.86", texto)

    def test_la_b_dice_donde_caeria_el_tercer_corte(self):
        texto = "\n".join(self.cabo.describe())
        # Anclado, la banda es 3utr:1199-1207 — mas estrecha que la estimacion previa.
        self.assertIn("3utr:1199-1207", texto)

    def test_y_que_el_bloque_conservado_queda_POR_DELANTE(self):
        texto = "\n".join(self.cabo.describe())
        self.assertIn("1138-1163", texto)
        self.assertIn("delante", texto.lower())

    def test_y_que_3utr_1200_de_la_lista_externa_cae_EN_LA_BANDA(self):
        texto = "\n".join(self.cabo.describe())
        self.assertIn("3utr:1200", texto)

    def test_NO_se_cierra_hacia_a_por_conveniencia_y_lo_dice(self):
        texto = "\n".join(self.cabo.describe()).lower()
        self.assertIn("conveniencia", texto)

    def test_pero_dice_POR_QUE_el_frente_sigue_cerrado_igual(self):
        # La honestidad no es dejarlo todo en el aire: bajo las DOS lecturas el techo
        # del panel es >= 0,86, y eso se demuestra, no se asume.
        texto = "\n".join(self.cabo.describe())
        self.assertIn("bajo las dos", texto.lower())
        self.assertIn(">=", texto)

    def test_dice_QUE_lo_resolveria(self):
        texto = "\n".join(self.cabo.describe()).lower()
        self.assertTrue("3'-end seq" in texto or "3-end seq" in texto)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLosDosSalenEnElINFORME(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        informe = tile_utr(utr3)
        cls.texto = text_report(
            species="raton", tiling=informe,
            selection=select_from_report(
                informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
            ),
            scaffold=SGEP_SCAFFOLD,
        )

    def test_el_veredicto_de_200_esta_escrito(self):
        self.assertIn("3utr:200", self.texto)
        self.assertIn("holgura", self.texto.lower())

    def test_el_cabo_suelto_esta_escrito(self):
        self.assertIn("131938392", self.texto)
        self.assertIn("NO RESUELTO", self.texto)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElBloqueNuevoNoVuelveARepetirElFallo(unittest.TestCase):
    """Tercera reaparicion del mismo fallo, cazada al regenerar el golden.

    La ventana venia convertida al 3'UTR y la señal no, asi que salia `3utr:1185` sobre
    un 3'UTR de 1242 nt. El techo global de `coords` NO lo caza —1185 cabe en el 3'UTR
    humano— y por eso hace falta el limite por especie.
    """

    def _texto(self, con_transcrito: bool) -> str:
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.reference import load_reference
        from shmir_design.selection import (
            SelectionConfig, promotion_clearance, select_from_report,
        )
        from shmir_design.tiling import tile_utr

        if con_transcrito:
            secuencia = load_reference(RATON)
            anatomy = Anatomy(
                length=RATON.length, utr5=RATON.utr5, cds=RATON.cds, utr3=RATON.utr3,
                source=RegionSource.ANOTACION_GENBANK,
            )
        else:
            secuencia, anatomy = load_3utr(RATON), None
        informe = tile_utr(
            secuencia, anatomy=anatomy,
        )
        return promotion_clearance(
            informe,
            select_from_report(
                informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
            ),
        ).describe()

    def test_sobre_el_3UTR_la_señal_sale_en_3utr_236(self):
        self.assertIn("3utr:236", self._texto(False))

    def test_sobre_el_TRANSCRITO_ENTERO_tambien(self):
        # Aqui es donde salia 3utr:1185. Las coordenadas de la fila van TODAS en el
        # 3'UTR, convertidas una vez.
        texto = self._texto(True)
        self.assertIn("3utr:236", texto)
        self.assertNotIn("3utr:1185", texto)
        self.assertNotIn("3utr:1175", texto)

    def test_y_este_caso_NO_lo_caza_NINGUN_invariante_de_rango(self):
        """El limite de la contramedida, dicho donde se ve.

        `3utr:1185` es una posicion perfectamente valida del 3'UTR murino (1242 nt): no
        es imposible, es EQUIVOCADA. El invariante de rango caza lo imposible —`3utr:1784`
        sobre 1606 nt, `3utr:2191` sobre cualquiera— y este no lo es, ni con el techo
        global ni con el limite por especie.

        Lo que lo cazo fue el GOLDEN, al regenerarlo y leer el diff. Por eso el golden no
        es un test mas: es el unico que ve la salida entera, y un numero plausible en el
        sitio equivocado solo se ve leyendola.
        """
        from shmir_design import coords

        self.assertEqual(coords.label(1185, coords.Frame.UTR3), "3utr:1185")
        self.assertEqual(
            coords.label(1185, coords.Frame.UTR3, limit=1242), "3utr:1185"
        )
        # Lo IMPOSIBLE si: los dos casos de la semana pasada.
        for valor, tope in ((1784, None), (2191, 1242)):
            with self.assertRaises(ValueError):
                coords.label(valor, coords.Frame.UTR3, limit=tope)
