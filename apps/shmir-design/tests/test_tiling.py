"""Tests del tiling y del contador de referencia (pasos 3 y 15).

Regla 5: escritos antes que `shmir_design/tiling.py`.

`biofisicos_ok` cuenta las ventanas que superan TODOS los filtros biofisicos —GC,
homopolimero, asimetria, G4 diana, G4 guia y zona prohibida de poliadenilacion— y solo
esos. No incluye la seed ni ningun filtro que dependa de un recurso externo, asi que es
comprobable sin miRBase y sin red. Es distinto del veredicto final: una ventana con
`biofisicos_ok=True` y la seed en NOT_RUN sigue siendo INCOMPLETE, nunca apta.

Los conteos sobre los 3'UTR reales estan al final y se saltan hasta que existan los
fixtures. Lo que si se comprueba hoy: la aritmetica del tiling, la agrupacion en sitios
y la ventana humana en 1237, que es un dato real verificado.
"""

import unittest

from shmir_design.filters import FilterState, Verdict
from shmir_design.masking import RepeatMask
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.seeds import BOOTSTRAP_SEEDS
from shmir_design.polya import PolyAMode
from shmir_design.tiling import (
    independent_sites,
    tile_positions,
    tile_utr,
)

MOUSE_UTR_LENGTH, HUMAN_UTR_LENGTH = 1242, 1606
DIANA_1237 = "GTTATTATTGGCTTGCACTTTG"


class TestAritmeticaDelTiling(unittest.TestCase):

    def test_un_3utr_de_1242_da_1221_ventanas(self):
        self.assertEqual(len(tile_positions(MOUSE_UTR_LENGTH)), 1221)

    def test_un_3utr_de_1606_da_1585_ventanas(self):
        self.assertEqual(len(tile_positions(HUMAN_UTR_LENGTH)), 1585)

    def test_las_posiciones_van_de_1_al_final(self):
        posiciones = tile_positions(MOUSE_UTR_LENGTH)
        self.assertEqual(posiciones[0], 1)
        self.assertEqual(posiciones[-1], MOUSE_UTR_LENGTH - 21)

    def test_un_3utr_mas_corto_que_la_ventana_no_da_ninguna(self):
        self.assertEqual(tile_positions(21), [])

    def test_longitud_invalida_es_error(self):
        with self.assertRaises(ValueError):
            tile_positions(0)


class TestSitiosIndependientes(unittest.TestCase):
    """Sitios = bloques de posiciones contiguas entre las que pasan."""

    def test_posiciones_contiguas_son_un_solo_sitio(self):
        self.assertEqual(independent_sites([10, 11, 12]), [(10, 12)])

    def test_un_hueco_separa_dos_sitios(self):
        self.assertEqual(independent_sites([10, 11, 20, 21]), [(10, 11), (20, 21)])

    def test_posiciones_sueltas(self):
        self.assertEqual(len(independent_sites([1, 5, 9])), 3)

    def test_sin_posiciones_no_hay_sitios(self):
        self.assertEqual(independent_sites([]), [])

    def test_el_orden_de_entrada_da_igual(self):
        self.assertEqual(independent_sites([21, 10, 20, 11]), [(10, 11), (20, 21)])

    def test_las_repetidas_no_inflan_el_conteo(self):
        self.assertEqual(independent_sites([10, 10, 11]), [(10, 11)])


class TestVentanaHumana1237(unittest.TestCase):
    """Dato real: pasa todos los biofisicos y solo cae por la seed."""

    def tiled(self, seeds=None):
        # Andamio de N con la diana real en su posicion real: la N no aporta GC ni
        # homopolimero, y ninguna ventana de N puede pasar los filtros.
        secuencia = "N" * 1236 + DIANA_1237 + "N" * (HUMAN_UTR_LENGTH - 1236 - 22)
        report = tile_utr(secuencia, seeds=seeds)
        return next(w for w in report.windows if w.window.start == 1237)

    def test_pasa_todos_los_biofisicos(self):
        self.assertTrue(self.tiled().biofisicos_ok)

    def test_sin_seeds_el_veredicto_es_incompleto_no_apto(self):
        ventana = self.tiled()
        self.assertIs(ventana.filter("seed").state, FilterState.NOT_RUN)
        self.assertIs(ventana.verdict, Verdict.INCOMPLETE)

    def test_con_la_lista_de_arranque_cae_por_la_seed(self):
        ventana = self.tiled(seeds=BOOTSTRAP_SEEDS)
        seed = ventana.filter("seed")
        self.assertIs(seed.state, FilterState.FAIL)
        self.assertIn("AAAGTGC", seed.reason)
        self.assertIn("miR-17/20/93/106", seed.reason)

    def test_la_seed_no_cuenta_como_biofisico(self):
        """Cae por la seed pero los biofisicos siguen en verde: son contadores distintos."""
        ventana = self.tiled(seeds=BOOTSTRAP_SEEDS)
        self.assertTrue(ventana.biofisicos_ok)
        self.assertIs(ventana.verdict, Verdict.FAIL)


class TestEnmascarado(unittest.TestCase):
    """Paso 1: enmascarar y RETILAR, nunca tachar a posteriori."""

    def secuencia(self):
        return "N" * 1236 + DIANA_1237 + "N" * 348

    def test_sin_mascara_el_filtro_queda_en_not_run(self):
        report = tile_utr(self.secuencia())
        estados = {w.filter("repeticiones").state for w in report.windows}
        self.assertEqual(estados, {FilterState.NOT_RUN})

    def test_el_filtro_de_repeticiones_no_es_biofisico(self):
        """Si contara, el contador biofisico dependeria de un recurso externo."""
        ventana = next(
            w for w in tile_utr(self.secuencia()).windows if w.window.start == 1237
        )
        self.assertIs(ventana.filter("repeticiones").state, FilterState.NOT_RUN)
        self.assertTrue(ventana.biofisicos_ok)

    def test_una_ventana_sobre_una_repeticion_falla_y_no_es_evaluable(self):
        mask = RepeatMask(intervals=((1240, 1260),), source="rmsk de prueba")
        report = tile_utr(self.secuencia(), mask=mask)
        ventana = next(w for w in report.windows if w.window.start == 1237)
        self.assertIs(ventana.filter("repeticiones").state, FilterState.FAIL)
        self.assertIs(ventana.filter("GC").state, FilterState.NOT_RUN)
        self.assertFalse(ventana.biofisicos_ok)

    def test_se_retila_sobre_la_secuencia_enmascarada(self):
        """La ventana enmascarada trae N en su secuencia: se reevaluo, no se tacho."""
        mask = RepeatMask(intervals=((1250, 1252),), source="rmsk de prueba")
        report = tile_utr(self.secuencia(), mask=mask)
        ventana = next(w for w in report.windows if w.window.start == 1237)
        self.assertIn("N", ventana.evaluation.sequence)

    def test_las_señales_de_polyA_se_buscan_sin_enmascarar(self):
        """Una señal dentro de un repetitivo sigue siendo una señal."""
        secuencia = "ACGT" * 20 + "AATAAA" + "ACGT" * 20
        mask = RepeatMask(intervals=((81, 86),), source="rmsk de prueba")
        report = tile_utr(secuencia, mask=mask)
        self.assertEqual([s.position for s in report.signals], [81])


class TestInforme(unittest.TestCase):

    def report(self):
        return tile_utr("N" * 1236 + DIANA_1237 + "N" * 348)

    def test_cuenta_todas_las_ventanas(self):
        self.assertEqual(len(self.report().windows), 1585)

    def test_el_contador_biofisico_es_distinto_del_de_aptas(self):
        report = self.report()
        self.assertEqual(report.biofisicos_ok(), 1)
        self.assertEqual(report.aptas(), 0)  # la seed en NOT_RUN lo impide

    def test_el_tsv_lleva_una_fila_por_ventana(self):
        lineas = self.report().format_tsv().splitlines()
        self.assertEqual(len(lineas), 1586)
        self.assertIn("biofisicos_ok", lineas[0])
        self.assertIn("seed", lineas[0])

    def test_el_texto_cuenta_en_cuantas_ventanas_no_corrio_cada_filtro(self):
        """El resumen mira todas las ventanas, no la primera."""
        texto = self.report().format_text()
        self.assertIn("seed: NOT_RUN en 1585/1585", texto)  # sin lista cargada
        self.assertIn("GC: NOT_RUN en 1584/1585", texto)

    def test_con_seeds_la_N_solo_bloquea_si_cae_dentro_de_la_seed(self):
        """La seed son las posiciones 2-8 de la guia, o sea 15-21 de la diana: hay 16
        ventanas cuyo tramo 15-21 cae entero dentro de la diana real, y en esas la seed
        SI se puede comparar aunque el resto de la ventana sea desconocido."""
        texto = tile_utr(
            "N" * 1236 + DIANA_1237 + "N" * 348, seeds=BOOTSTRAP_SEEDS
        ).format_text()
        self.assertIn("seed: NOT_RUN en 1569/1585", texto)

    def test_el_texto_avisa_de_que_la_lista_de_arranque_no_es_un_filtro_real(self):
        texto = tile_utr(
            "N" * 1236 + DIANA_1237 + "N" * 348, seeds=BOOTSTRAP_SEEDS
        ).format_text()
        self.assertIn("arranque", texto.lower())


@unittest.skipUnless(
    all(fixture_available(ref) for ref in REFERENCES.values()),
    "NOT_RUN: faltan los fixtures de data/reference/; sin ellos los conteos de "
    "referencia no se pueden comprobar y no se inventan (regla 1)",
)
class TestConteosDeReferencia(unittest.TestCase):
    """Contadores sobre los 3'UTR reales, verificados por el responsable."""

    #: Los conteos que verifico el responsable —302/96 en raton y 323/97 en humano—
    #: salen con el criterio de polyA PERMISIVO, que es el que habia cuando se
    #: verificaron: FAIL solo por detras del corte de la señal terminal, sin zona
    #: prohibida de ±flanco. Coinciden EXACTAMENTE con la columna `permisivo` de la
    #: tabla de los tres modos, en las dos especies, asi que no hay ninguna duda de con
    #: que se calcularon.
    #:
    #: El defecto del proyecto es ESCALONADO desde el 2026-08-26, y con el salen 287/90
    #: y 309/95. Los dos juegos de cifras se fijan aqui: el de referencia con su
    #: criterio escrito, y el vigente. Cambiar los numeros de referencia para que pasen
    #: con el criterio nuevo habria borrado la unica prueba de que el cambio de criterio
    #: es lo que los mueve.
    #: Estos tests no corrian: la clase se salta si falta CUALQUIER fixture, y el humano
    #: no estaba. Llegaron los dos el 2026-08-26 y aparecio el desajuste.
    def raton(self, seeds=None, modo=None):
        return tile_utr(
            load_3utr(REFERENCES["NM_011170.3"]), seeds=seeds,
            **({"polya_mode": modo} if modo else {}),
        )

    def humano(self, seeds=None, modo=None):
        return tile_utr(
            load_3utr(REFERENCES["NM_000311.5"]), seeds=seeds,
            **({"polya_mode": modo} if modo else {}),
        )

    def test_raton_solo_biofisicos_criterio_de_referencia(self):
        report = self.raton(modo=PolyAMode.PERMISIVO)
        self.assertEqual(len(report.windows), 1221)
        self.assertEqual(report.biofisicos_ok(), 302)
        self.assertEqual(len(report.sites_biofisicos()), 96)

    def test_humano_solo_biofisicos_criterio_de_referencia(self):
        report = self.humano(modo=PolyAMode.PERMISIVO)
        self.assertEqual(len(report.windows), 1585)
        self.assertEqual(report.biofisicos_ok(), 323)
        self.assertEqual(len(report.sites_biofisicos()), 97)

    def test_con_el_criterio_VIGENTE_las_cifras_son_otras(self):
        raton, humano = self.raton(), self.humano()
        # 270/86, no 287/90: la promoción por medida entra SIEMPRE desde 2026-08-27 y
        # eso cuesta 17 ventanas y 4 sitios — exactamente `measured_promotion_cost`, que
        # `CLAUDE.md` ya registraba como «elegibles 287 → 270, sitios 90 → 86».
        self.assertEqual((raton.biofisicos_ok(), len(raton.sites_biofisicos())), (270, 86))
        self.assertEqual((humano.biofisicos_ok(), len(humano.sites_biofisicos())), (309, 95))

    def test_lo_que_separa_los_dos_juegos_es_SOLO_el_criterio_de_polyA(self):
        # Si esto falla, el cambio de cifras NO es el criterio de polyA y hay que buscar
        # una regresion de verdad en los otros cinco filtros biofisicos.
        for especie in (self.raton, self.humano):
            with self.subTest(especie.__name__):
                permisivo = {
                    w.window.start for w in especie(modo=PolyAMode.PERMISIVO).windows
                    if w.biofisicos_ok
                }
                escalonado = {
                    w.window.start for w in especie().windows if w.biofisicos_ok
                }
                self.assertTrue(escalonado < permisivo)
                for inicio in permisivo - escalonado:
                    ventana = [
                        w for w in especie().windows if w.window.start == inicio
                    ][0]
                    fallan = [
                        r.name for r in ventana.filters
                        if r.state is FilterState.FAIL
                    ]
                    self.assertEqual(fallan, ["zona_prohibida_polyA"])

    #: OJO con `aptas()`: hoy vale 0 en las dos especies, y ESO ES LA REGLA 3
    #: funcionando, no una regresion. `aptas` cuenta veredicto PASS, y con
    #: especificidad, repeticiones, colision de seed y transgen en NOT_RUN ningun
    #: candidato puede aprobar. Cuando estos conteos se verificaron, el pipeline tenia
    #: menos filtros externos. Lo que aquellas cifras querian fijar —cuantas ventanas
    #: sobreviven a la lista de arranque de seeds— se mide sobre el contador biofisico
    #: y el filtro de seed, que es lo que de verdad estaban contando.
    def _pasan_seed(self, report) -> int:
        return sum(
            1 for w in report.windows
            if w.biofisicos_ok and w.filter("seed").state is not FilterState.FAIL
        )

    def test_el_raton_no_cambia_con_la_lista_de_arranque(self):
        report = self.raton(seeds=BOOTSTRAP_SEEDS, modo=PolyAMode.PERMISIVO)
        self.assertEqual(self._pasan_seed(report), 302)
        self.assertEqual(report.aptas(), 0)   # regla 3: hay filtros en NOT_RUN

    def test_el_humano_pierde_exactamente_una_ventana(self):
        sin_seeds = self.humano(modo=PolyAMode.PERMISIVO)
        con_seeds = self.humano(seeds=BOOTSTRAP_SEEDS, modo=PolyAMode.PERMISIVO)
        self.assertEqual(self._pasan_seed(con_seeds), 322)
        self.assertEqual(sin_seeds.biofisicos_ok() - self._pasan_seed(con_seeds), 1)

    def test_la_ventana_que_cae_es_la_de_1237(self):
        report = self.humano(seeds=BOOTSTRAP_SEEDS)
        caidas = [
            w for w in report.windows
            if w.biofisicos_ok and w.filter("seed").state is FilterState.FAIL
        ]
        self.assertEqual([w.window.start for w in caidas], [1237])
        self.assertEqual(caidas[0].evaluation.sequence, DIANA_1237)


if __name__ == "__main__":
    unittest.main()
