"""Tests de las funciones que alimentan la interfaz.

Regla 5: escritos antes que `shmir_design/presentation.py`.

La UI no puede tener logica: todo lo que decide algo —el semaforo, las filas de la
tabla, el mapa— vive aqui y se prueba aqui, sin Streamlit de por medio.
"""

import unittest

from shmir_design.conservation import Utr3, build_conservation_report
from shmir_design.masking import RepeatMask
from shmir_design.presentation import (
    anatomy_rows,
    candidate_rows,
    map_svg,
    output_bundle,
    status_light,
    window_rows,
)
from shmir_design.reference import REFERENCES
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.seeds import BOOTSTRAP_SEEDS
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.tiling import tile_utr

SONDA = "GCGTCAGTACGATCGAATTACT" * 30
BLOQUE = "TTTTCTATATTTGTAACTTTGCATGT"


def piezas(seeds=None, mask=None):
    tiling = tile_utr(SONDA, seeds=seeds, mask=mask)
    return tiling, select_from_report(tiling, SelectionConfig(n_candidates=3))


class TestSemaforo(unittest.TestCase):
    """El semaforo mira los CANDIDATOS SELECCIONADOS, que son los que se pedirian.

    Mirar todas las ventanas dejaria el verde inalcanzable en cuanto se enmascara algo:
    una ventana con N nunca se evalua, y eso no significa que un filtro no haya corrido.
    Lo que importa es si lo que vas a encargar esta filtrado del todo.
    """

    def test_ambar_si_algun_filtro_quedo_en_not_run(self):
        _, seleccion = piezas()
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "ambar")
        self.assertIn("seed", luz.pending)
        self.assertIn("repeticiones", luz.pending)

    def test_el_ambar_dice_cuales_faltan_en_el_titular(self):
        _, seleccion = piezas()
        luz = status_light(seleccion)
        self.assertIn("seed", luz.headline + luz.detail)
        self.assertIn("repeticiones", luz.headline + luz.detail)

    def test_verde_solo_si_corrieron_todos(self):
        mask = RepeatMask(intervals=((1, 5),), source="prueba")
        _, seleccion = piezas(seeds=BOOTSTRAP_SEEDS, mask=mask)
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "verde")
        self.assertEqual(luz.pending, ())

    def test_el_ambar_recuerda_que_not_run_no_es_pass(self):
        _, seleccion = piezas()
        self.assertIn("NOT_RUN", status_light(seleccion).detail)

    def test_las_ventanas_no_evaluables_se_cuentan_aparte_del_semaforo(self):
        """Enmascarar deja ventanas con N sin evaluar; eso no es un filtro sin correr."""
        mask = RepeatMask(intervals=((1, 5),), source="prueba")
        _, seleccion = piezas(seeds=BOOTSTRAP_SEEDS, mask=mask)
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "verde")
        self.assertIn("no evaluable", luz.detail.lower())

    def test_sin_candidatos_no_hay_verde(self):
        tiling = tile_utr("N" * 200)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "ambar")
        self.assertIn("ningun candidato", luz.headline.lower())


class TestFilasDeTabla(unittest.TestCase):

    def test_una_fila_por_candidato_con_una_columna_por_filtro(self):
        _, seleccion = piezas()
        filas = candidate_rows(seleccion)
        self.assertEqual(len(filas), len(seleccion.selection.chosen))
        for filtro in ("GC", "homopolimero", "asimetria", "G4_diana", "G4_guia",
                       "zona_prohibida_polyA", "repeticiones", "seed"):
            with self.subTest(filtro):
                self.assertIn(filtro, filas[0])

    def test_la_fila_lleva_posicion_tercio_veredicto_y_secuencias(self):
        _, seleccion = piezas()
        fila = candidate_rows(seleccion)[0]
        for columna in ("rango", "inicio", "fin", "tercio", "asimetria", "diana",
                        "guia", "veredicto"):
            with self.subTest(columna):
                self.assertIn(columna, fila)

    def test_los_estados_son_texto_no_booleanos(self):
        _, seleccion = piezas()
        self.assertIn(candidate_rows(seleccion)[0]["seed"], ("PASS", "FAIL", "NOT_RUN"))

    def test_todas_las_ventanas_caben_en_window_rows(self):
        tiling, _ = piezas()
        self.assertEqual(len(window_rows(tiling)), len(tiling.windows))


class TestAnatomia(unittest.TestCase):

    def test_con_transcrito_verificado_da_los_tres_tramos(self):
        filas = anatomy_rows(REFERENCES["NM_011170.3"])
        tramos = {f["tramo"] for f in filas}
        self.assertEqual(tramos, {"5'UTR", "CDS", "3'UTR"})
        utr3 = next(f for f in filas if f["tramo"] == "3'UTR")
        self.assertEqual(utr3["longitud"], 1242)
        self.assertEqual(utr3["origen"], "verificado")

    def test_sin_transcrito_lo_dice_en_vez_de_adivinar(self):
        filas = anatomy_rows(None, utr3_length=660)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["tramo"], "3'UTR")
        self.assertIn("declarad", filas[0]["origen"])


class TestMapa(unittest.TestCase):

    def test_es_un_svg(self):
        tiling, seleccion = piezas()
        svg = map_svg(tiling, seleccion)
        self.assertTrue(svg.strip().startswith("<svg"))
        self.assertTrue(svg.strip().endswith("</svg>"))

    def test_marca_cada_candidato(self):
        tiling, seleccion = piezas()
        svg = map_svg(tiling, seleccion)
        for choice in seleccion.selection.chosen:
            with self.subTest(choice.start):
                self.assertIn(f'data-candidato="{choice.start}"', svg)

    def test_marca_las_señales_de_poliadenilacion(self):
        secuencia = "ACGT" * 20 + "AATAAA" + "ACGT" * 20
        tiling = tile_utr(secuencia)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=1))
        svg = map_svg(tiling, seleccion)
        self.assertIn('data-senal="81"', svg)

    def test_marca_las_zonas_enmascaradas(self):
        mask = RepeatMask(intervals=((100, 200),), source="prueba")
        tiling, seleccion = piezas(mask=mask)
        svg = map_svg(tiling, seleccion)
        self.assertIn('data-mascara="100-200"', svg)

    def test_marca_los_bloques_conservados(self):
        tiling, seleccion = piezas()
        conservacion = build_conservation_report(
            Utr3("a", "N" * 100 + BLOQUE + "N" * 100),
            Utr3("b", "N" * 50 + BLOQUE + "N" * 150),
        )
        svg = map_svg(tiling, seleccion, conservation=conservacion, species="a")
        self.assertIn("data-bloque=", svg)

    def test_sin_bloques_no_falla(self):
        tiling, seleccion = piezas()
        self.assertIn("<svg", map_svg(tiling, seleccion, conservation=None))

    def test_las_coordenadas_no_se_salen_del_lienzo(self):
        tiling, seleccion = piezas()
        svg = map_svg(tiling, seleccion)
        self.assertNotIn("x=\"-", svg)


class TestDescargas(unittest.TestCase):

    def test_el_paquete_trae_las_cinco_salidas(self):
        tiling, seleccion = piezas()
        bundle = output_bundle(
            species="sonda",
            tiling=tiling,
            selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        self.assertEqual(
            sorted(bundle),
            [
                "sonda_guias.fasta",
                "sonda_informe.txt",
                "sonda_oligos.tsv",
                "sonda_seleccionados.tsv",
                "sonda_ventanas.tsv",
            ],
        )

    def test_todo_el_contenido_es_texto_no_vacio(self):
        tiling, seleccion = piezas()
        bundle = output_bundle(
            species="sonda", tiling=tiling, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        for nombre, contenido in bundle.items():
            with self.subTest(nombre):
                self.assertIsInstance(contenido, str)
                self.assertTrue(contenido.strip())


if __name__ == "__main__":
    unittest.main()
