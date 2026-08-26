"""Lo que el autoconteo encontro, explotado: clase, interseccion y multiplexado.

Regla 5: escritos antes.

El autoconteo dijo que cuatro del panel tienen un segundo sitio en su propia diana. Con
el NUCLEO a secas no se puede interpretar: un 8mer o un 7mer-m8 de mas dan cooperatividad
real y explicarian un rendimiento por encima de lo esperado; un 6mer es marginal. Aqui se
fija la CLASE de cada uno, la interseccion real de dos redes, y la consecuencia para el
multiplexado — que es la que el espaciado no puede ver, porque mide distancia y no
parecido de seed.
"""

import unittest

from shmir_design import offtarget
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(RATON)
HAY_DOS = HAY and fixture_available(HUMANO)


def _piezas():
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    informe = tile_utr(utr3)
    seleccion = select_from_report(informe, SelectionConfig(n_candidates=10))
    guias = {
        c.start: seleccion.window_of(c).evaluation.guide
        for c in seleccion.selection.chosen
    }
    return utr3, informe, seleccion, guias


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaClaseDeCadaSegundoSitio(unittest.TestCase):
    """El conteo sin clase no es interpretable. Valores con su procedencia."""

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion, cls.guias = _piezas()

    def _sitios(self, inicio):
        elegido = next(
            c for c in self.seleccion.selection.chosen if c.start == inicio
        )
        return offtarget.self_sites(
            self.guias[inicio], target=self.utr3,
            window=(elegido.start, elegido.end),
        )

    def test_449_su_sitio_es_7mer_m8_y_el_segundo_un_7mer_A1(self):
        sitios = self._sitios(449)
        self.assertEqual(
            [(s.position, s.site_class, s.own_window) for s in sitios],
            [(464, "7mer-m8", True), (1033, "7mer-A1", False)],
        )

    def test_553_su_segundo_sitio_es_un_6mer_o_sea_MARGINAL(self):
        sitios = self._sitios(553)
        self.assertEqual(
            [(s.position, s.site_class, s.own_window) for s in sitios],
            [(460, "6mer", False), (568, "7mer-m8", True)],
        )

    def test_819_es_el_PEOR_dos_7mer_m8_en_el_mismo_mensajero(self):
        """Cooperatividad real: el segundo sitio es de la MISMA clase que el suyo."""
        sitios = self._sitios(819)
        self.assertEqual(
            [(s.position, s.site_class, s.own_window) for s in sitios],
            [(148, "7mer-m8", False), (834, "7mer-m8", True)],
        )

    def test_1018_tiene_un_8mer_en_SU_diana_y_un_6mer_de_mas(self):
        """Su propio sitio es la clase mas fuerte: eso juega A FAVOR, no en contra."""
        sitios = self._sitios(1018)
        self.assertEqual(
            [(s.position, s.site_class, s.own_window) for s in sitios],
            [(464, "6mer", False), (1033, "8mer", True)],
        )

    def test_los_otros_seis_tienen_un_solo_sitio(self):
        for inicio in (10, 60, 143, 359, 652, 735):
            self.assertEqual(len(self._sitios(inicio)), 1, inicio)

    def test_sin_ventana_no_se_marca_NINGUNO_como_propio(self):
        """Deducir cual es el suyo por el orden seria un supuesto. No se hace."""
        sitios = offtarget.self_sites(self.guias[819], target=self.utr3)
        self.assertFalse(any(s.own_window for s in sitios))

    def test_el_autoconteo_imprime_la_clase_junto_a_la_posicion(self):
        elegido = next(
            c for c in self.seleccion.selection.chosen if c.start == 819
        )
        propio = offtarget.self_count(
            self.guias[819], target=self.utr3, target_label="Prnp",
            window=(elegido.start, elegido.end),
        )
        texto = propio.describe()
        self.assertIn("7mer-m8", texto)
        self.assertIn("3utr:148", texto)
        self.assertIn("8mer", texto)  # la explicacion de por que la clase importa


@unittest.skipUnless(HAY_DOS, "NOT_RUN: faltan los dos fixtures")
class TestLaInterseccionDeDosRedes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion, cls.guias = _piezas()
        cls.catalogo = offtarget.build_catalog(
            [("raton_3utr", cls.utr3), ("humano_3utr", load_3utr(HUMANO))],
            provenance=offtarget.Provenance(
                source="fixtures del proyecto (NO es el transcriptoma)",
                assembly="n/a — dos 3'UTR de referencia",
                table="NM_011170.3 + NM_000311.5", table_date="2026-08-26",
                representative="uno por gen", version="fixtures", md5="0" * 32,
            ),
        )

    def test_sin_catalogo_devuelve_None_y_eso_NO_es_cero(self):
        self.assertIsNone(
            offtarget.shared_network(
                self.guias[449], self.guias[1018], catalog=None
            )
        )

    def test_449_y_1018_comparten_el_nucleo_y_la_funcion_lo_dice(self):
        red = offtarget.shared_network(
            self.guias[449], self.guias[1018], catalog=self.catalogo,
            label_a="3utr:449", label_b="3utr:1018",
        )
        self.assertTrue(red.same_core)

    def test_comparten_TODAS_sus_posiciones_sobre_este_catalogo(self):
        """Mismo nucleo → mismas posiciones. Lo que cambia es la CLASE de cada una."""
        red = offtarget.shared_network(
            self.guias[449], self.guias[1018], catalog=self.catalogo,
            label_a="3utr:449", label_b="3utr:1018",
        )
        self.assertEqual(red.positions_shared, red.positions_a)
        self.assertEqual(red.positions_shared, red.positions_b)
        self.assertEqual(red.jaccard, 1.0)

    def test_y_la_CLASE_de_una_misma_posicion_puede_ser_distinta_en_cada_uno(self):
        red = offtarget.shared_network(
            self.guias[449], self.guias[1018], catalog=self.catalogo,
            label_a="3utr:449", label_b="3utr:1018",
        )
        distintas = {
            par for par in red.by_class if par[0] != par[1]
        }
        self.assertTrue(
            distintas,
            "Difieren en la posicion 8, asi que la misma posicion cae en clases "
            "distintas para cada uno. Si salieran todas iguales, algo no se esta "
            "mirando.",
        )

    def test_dos_candidatos_con_nucleos_DISTINTOS_no_comparten_casi_nada(self):
        red = offtarget.shared_network(
            self.guias[449], self.guias[819], catalog=self.catalogo,
            label_a="3utr:449", label_b="3utr:819",
        )
        self.assertFalse(red.same_core)
        self.assertEqual(red.positions_shared, 0)

    def test_la_fuente_del_catalogo_VIAJA_con_el_resultado(self):
        red = offtarget.shared_network(
            self.guias[449], self.guias[1018], catalog=self.catalogo
        )
        self.assertIn("fixtures del proyecto", " ".join(red.describe()))

    def test_ESTE_numero_NO_es_el_del_transcriptoma_y_hay_que_decirlo(self):
        """Sobre dos 3'UTR no es la carga real: la fuente lo dice en cada linea."""
        red = offtarget.shared_network(
            self.guias[449], self.guias[1018], catalog=self.catalogo
        )
        self.assertIn("NO es el transcriptoma", " ".join(red.describe()))


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestElAvisoDeMultiplexado(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion, cls.guias = _piezas()

    def test_el_panel_murino_tiene_UNA_pareja_que_comparte_nucleo(self):
        conflictos = offtarget.core_conflicts(self.seleccion)
        self.assertEqual([(c.a, c.b) for c in conflictos], [(449, 1018)])

    def test_y_NO_comparten_heptamero_que_es_lo_que_lo_hace_invisible(self):
        conflicto = offtarget.core_conflicts(self.seleccion)[0]
        self.assertFalse(conflicto.same_heptamer)

    def test_describe_EXIGE_las_dos_etiquetas_sin_valor_por_defecto(self):
        """Poner `3utr:` dentro imprimio `3utr:1398` sobre un transcrito. Nunca mas."""
        conflicto = offtarget.core_conflicts(self.seleccion)[0]
        with self.assertRaises(TypeError):
            conflicto.describe()

    def test_la_consecuencia_para_el_multiplexado_va_ESCRITA(self):
        texto = offtarget.MULTIPLEX_NOTE
        self.assertIn("3utr:449", texto)
        self.assertIn("3utr:1018", texto)
        self.assertIn("PEOR eleccion", texto)
        self.assertIn("espaciado no lo ve", texto)

    def test_el_informe_lo_saca_AUNQUE_no_haya_conflicto(self):
        """Su ausencia se leeria como que nadie lo miro."""
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report

        uno = select_from_report(self.informe, SelectionConfig(n_candidates=1))
        texto = text_report(
            species="raton", tiling=self.informe, selection=uno,
            scaffold=SGEP_SCAFFOLD,
        )
        self.assertIn("Multiplexado: nucleos de seed compartidos", texto)
        self.assertIn("Ninguna pareja del panel comparte", texto)

    def test_y_con_conflicto_lo_marca_con_las_coordenadas_del_MARCO_del_informe(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD

        texto = text_report(
            species="raton", tiling=self.informe, selection=self.seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        # Este informe tila el 3'UTR, asi que el marco ES 3utr.
        self.assertIn("3utr:449 y 3utr:1018 comparten el nucleo", texto)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestElTripleMotivoYaVIVE_EN_LA_APP(unittest.TestCase):
    """Era el unico analisis que existia solo porque alguien lo corria a mano."""

    def test_el_informe_tiene_su_bloque_aunque_no_haya_mascara(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        informe = tile_utr(load_3utr(RATON))
        seleccion = select_from_report(informe, SelectionConfig(n_candidates=10))
        texto = text_report(
            species="raton", tiling=informe, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        self.assertIn("Triple motivo", texto)
        self.assertIn("NOT_RUN", texto)

    def test_los_DOS_desfases_son_obligatorios_y_van_por_nombre(self):
        """Llamarla con uno solo tiene que ser IMPOSIBLE, no improbable."""
        import inspect

        from shmir_design.masking import triple_motive_rows

        firma = inspect.signature(triple_motive_rows)
        for nombre in ("mask_offset", "label_offset"):
            parametro = firma.parameters[nombre]
            self.assertIs(
                parametro.default, inspect.Parameter.empty,
                f"{nombre} no puede tener valor por defecto: una constante que sirve "
                f"para dos preguntas son DOS constantes, y un cero por defecto deja que "
                f"el fallo vuelva sin dar ningun error.",
            )
            self.assertIs(parametro.kind, inspect.Parameter.KEYWORD_ONLY)

    def test_design_py_lo_calcula_y_se_lo_pasa_al_informe(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "tools" / "design.py"
        ).read_text(encoding="utf-8")
        self.assertIn("triple_motive_rows(", fuente)
        self.assertIn("triple_motive=triple", fuente)

    def test_y_lo_hace_sobre_un_informe_tilado_SIN_mascara(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "tools" / "design.py"
        ).read_text(encoding="utf-8")
        self.assertIn("sin_mascara", fuente)


if __name__ == "__main__":
    unittest.main()
