"""Cruce de dos exports de miRarchitect por SITIO sobre la referencia.

Regla 5: escritos antes que `mirarchitect.compare_exports`.

Sirve para dos preguntas distintas, y el eje que cambia se declara para que el informe
diga cual de las dos se esta contestando:

- **Sensibilidad a la entrada.** Mismo andamio, secuencia de entrada distinta: la
  fabricada de 1246 nt frente a la buena de 1242. Es una perturbacion del 0,3 % con el
  resto de variables identicas. Si el solapamiento de sitios es alto, la puntuacion es
  robusta; si es bajo, hay que degradar la confianza que se le da y decirlo.
- **Magnitud del andamio.** Misma entrada, andamio distinto (miR-30a frente a miR-E):
  mismo sitio, dos puntuaciones, y la diferencia atribuible al andamio. Con eso el
  `NO_ORDENAR` deja de ser una prohibicion a ciegas.

El cruce va por la coordenada del MATCH sobre la referencia, no por la guia ni por la
coordenada declarada: una ventana corrida da otra guia, y cruzar por guia perderia justo
los casos interesantes.
"""

import unittest
from pathlib import Path

from shmir_design.mirarchitect import compare_exports, parse_export

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
CSV, RATON = DIR / "mirarchitect_prnp_export.csv", DIR / "NM_011170.3.fa"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestConsigoMismo(unittest.TestCase):
    """El caso degenerado, que es el que fija el significado de las cifras."""

    @classmethod
    def setUpClass(cls):
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        cls.comparacion = compare_exports(
            export, export, _utr3(), axis="ninguno (control)"
        )

    def test_todos_los_sitios_reaparecen(self):
        self.assertEqual(len(self.comparacion.only_a), 0)
        self.assertEqual(len(self.comparacion.only_b), 0)

    def test_ninguno_cambia_de_puesto(self):
        self.assertEqual(self.comparacion.moved, ())

    def test_el_solapamiento_es_del_100_por_cien(self):
        self.assertEqual(self.comparacion.overlap, 1.0)

    def test_las_filas_sin_sitio_se_cuentan_aparte(self):
        # Las 5 que no existen en la referencia no tienen sitio con el que cruzar.
        self.assertEqual(self.comparacion.without_site_a, 5)
        self.assertEqual(self.comparacion.without_site_b, 5)

    def test_el_informe_nombra_el_eje(self):
        self.assertIn("ninguno (control)", self.comparacion.format_text())

    def test_el_informe_NO_da_una_cifra_agregada(self):
        # `overlap` se sigue calculando para quien lo pida, pero no se imprime: un
        # porcentaje global mezcla los dos estratos y con eso no se decide nada.
        texto = self.comparacion.format_text()
        self.assertNotIn("100.0%", texto)
        self.assertIn("CRITERIO DIRECTO", texto)
        self.assertIn("CRITERIO POSICIONAL", texto)


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestConUnaPerturbacion(unittest.TestCase):
    """Perturbaciones sobre el dato real: un intercambio de puestos y una baja."""

    @classmethod
    def setUpClass(cls):
        cls.export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        cls.utr3 = _utr3()

    def _con_filas(self, filas):
        from dataclasses import replace

        return replace(self.export, rows=tuple(filas))

    def test_intercambiar_dos_puestos_mueve_solo_esos_dos(self):
        filas = list(self.export.rows)
        filas[0], filas[2] = filas[2], filas[0]      # las dos tienen sitio
        comparacion = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        )
        self.assertEqual(comparacion.overlap, 1.0)
        self.assertEqual(
            {m.guide for m in comparacion.moved},
            {self.export.rows[0].guide, self.export.rows[2].guide},
        )

    def test_y_el_desplazamiento_es_simetrico(self):
        filas = list(self.export.rows)
        filas[0], filas[2] = filas[2], filas[0]
        comparacion = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        )
        saltos = sorted(m.rank_shift for m in comparacion.moved)
        self.assertEqual(saltos, [-2, 2])

    def test_quitar_una_fila_con_sitio_baja_el_solapamiento(self):
        # Y ademas corre el puesto de todas las de debajo: eso es lo que pasa de verdad
        # al comparar dos rankings de distinto tamaño, y el informe lo enseña.
        comparacion = compare_exports(
            self.export, self._con_filas(self.export.rows[1:]), self.utr3, axis="prueba"
        )
        self.assertEqual(len(comparacion.only_a), 1)
        self.assertEqual(len(comparacion.only_b), 0)
        self.assertLess(comparacion.overlap, 1.0)

    def test_quitar_una_fila_SIN_sitio_no_cambia_el_solapamiento(self):
        # Las 5 que no existen en la referencia no participan del cruce.
        sin_sitio = self.export.rows[1]
        filas = [f for f in self.export.rows if f is not sin_sitio]
        comparacion = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        )
        self.assertEqual(comparacion.overlap, 1.0)
        self.assertEqual(comparacion.without_site_a, 5)
        self.assertEqual(comparacion.without_site_b, 4)

    def test_el_informe_lista_los_que_se_mueven(self):
        filas = list(self.export.rows)
        filas[0], filas[2] = filas[2], filas[0]
        texto = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        ).format_text()
        self.assertIn("puesto", texto.lower())


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestLoQueNoDecideLaHerramienta(unittest.TestCase):

    def test_hay_que_declarar_que_eje_cambia(self):
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        with self.assertRaises(TypeError):
            compare_exports(export, export, _utr3())

    def test_el_informe_nunca_dice_robusto(self):
        # El umbral de "alto" o "bajo" no lo pone el codigo: lo pone quien lee.
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        texto = compare_exports(export, export, _utr3(), axis="x").format_text()
        self.assertNotIn("robusto", texto.lower())

    def test_pero_si_el_test_binario_falla_dice_DEGRADAR(self):
        from dataclasses import replace

        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        filas = list(export.rows)
        filas[0] = replace(filas[0], score=filas[0].score + 1.0)
        texto = compare_exports(
            export, replace(export, rows=tuple(filas)), _utr3(), axis="x"
        ).format_text()
        self.assertIn("degradar", texto.lower())


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestEstratificacion(unittest.TestCase):
    """Un porcentaje global de solapamiento es debil. Los dos estratos no lo son.

    Con las posiciones divergentes localizadas, cada sitio cae en uno de dos:

    (a) su ventana de 22 nt NO contiene ninguna diferencia — las dos corridas vieron
        exactamente la misma ventana;
    (b) su ventana solapa al menos una.

    Para los sitios del estrato (a) presentes en las dos listas la expectativa es score
    IDENTICO, y eso es un test binario, no un umbral. Si alguno difiere, el score no es
    funcion local de la ventana: arrastra contexto global, y entonces NINGUNA puntuacion
    calculada sobre una entrada imperfecta sirve — incluidas las 21 del grupo 2.
    """

    @classmethod
    def setUpClass(cls):
        cls.export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        cls.utr3 = _utr3()

    def _comparar(self, otro, divergentes):
        return compare_exports(
            self.export, otro, self.utr3, axis="prueba",
            divergent_positions=divergentes,
        )

    def test_sin_posiciones_divergentes_todo_cae_en_el_estrato_limpio(self):
        c = self._comparar(self.export, frozenset())
        self.assertEqual(len(c.clean), len(c.shared))
        self.assertEqual(c.dirty, ())

    def test_una_posicion_divergente_ensucia_solo_las_ventanas_que_la_tocan(self):
        # La ventana 1200-1221 contiene la posicion 1210; ninguna otra del fichero.
        c = self._comparar(self.export, frozenset({1210}))
        sucias = {s.start for s in c.dirty}
        self.assertEqual(sucias, {1200})

    def test_el_estrato_limpio_con_scores_identicos_pasa_el_test_binario(self):
        c = self._comparar(self.export, frozenset({1210}))
        self.assertTrue(c.clean_scores_match)
        self.assertEqual(c.clean_mismatches, ())

    def test_si_un_sitio_limpio_cambia_de_score_el_test_binario_falla(self):
        from dataclasses import replace

        filas = list(self.export.rows)
        filas[0] = replace(filas[0], score=filas[0].score + 1.0)
        c = self._comparar(replace(self.export, rows=tuple(filas)), frozenset())
        self.assertFalse(c.clean_scores_match)
        self.assertEqual(len(c.clean_mismatches), 1)

    def test_y_entonces_el_informe_dice_que_NADA_es_utilizable(self):
        from dataclasses import replace

        filas = list(self.export.rows)
        filas[0] = replace(filas[0], score=filas[0].score + 1.0)
        texto = self._comparar(
            replace(self.export, rows=tuple(filas)), frozenset()
        ).format_text()
        self.assertIn("contexto global", texto.lower())
        self.assertIn("ninguna puntuacion", texto.lower())

    def test_no_se_da_ninguna_cifra_agregada_de_solapamiento(self):
        # Estratificado significa estratificado: el porcentaje global desaparece.
        texto = self._comparar(self.export, frozenset({1210})).format_text()
        self.assertNotIn("SOLAPAMIENTO DE SITIOS", texto)

    def test_los_dos_estratos_se_reportan_por_separado(self):
        texto = self._comparar(self.export, frozenset({1210})).format_text()
        self.assertIn("estrato (a) limpio", texto.lower())
        self.assertIn("estrato (b) tocado", texto.lower())

    def test_sigue_sin_decir_robusto(self):
        texto = self._comparar(self.export, frozenset({1210})).format_text()
        self.assertNotIn("robusto", texto.lower())


BUENA = DIR / "mirarchitect_prnp_export_buena.csv"
FABRICADO = DIR / "prnp_3utr_fabricado_1246nt.txt"


@unittest.skipUnless(
    CSV.is_file() and BUENA.is_file() and FABRICADO.is_file() and RATON.is_file(),
    "NOT_RUN: faltan los fixtures de las dos corridas",
)
class TestCasoDeReferencia(unittest.TestCase):
    """Las dos corridas de verdad. Este es EL caso de referencia del proyecto.

    Misma herramienta, mismo andamio, mismo gen; dos entradas que difieren en 18
    sucesos sobre 1242 nt. Es una caracterizacion de miRarchitect, no un subproducto de
    una errata: contesta si el score es funcion local de la ventana de 22 nt.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.alignment import align

        utr3 = _utr3()
        fabricado = FABRICADO.read_text(encoding="ascii").strip()
        cls.comparacion = compare_exports(
            parse_export(CSV.read_text(encoding="utf-8-sig"), source="fabricada"),
            parse_export(BUENA.read_text(encoding="utf-8-sig"), source="buena"),
            utr3,
            axis="secuencia de entrada",
            divergent_positions=align(utr3, fabricado).ref_positions,
        )

    def test_veintiun_sitios_compartidos(self):
        self.assertEqual(len(self.comparacion.shared), 21)

    def test_ninguno_exclusivo_de_la_corrida_fabricada(self):
        self.assertEqual(len(self.comparacion.only_a), 0)

    def test_tres_exclusivos_de_la_buena(self):
        self.assertEqual(len(self.comparacion.only_b), 3)

    def test_la_estratificacion_posicional_da_veinte_limpios(self):
        self.assertEqual(len(self.comparacion.clean), 20)
        self.assertEqual(len(self.comparacion.dirty), 1)

    def test_pero_los_21_vieron_LITERALMENTE_la_misma_ventana(self):
        # El criterio directo: si las dos corridas emitieron la MISMA diana, vieron la
        # misma ventana, y eso no admite discusion. El posicional marca 221 como sucio
        # porque una posicion divergente cae en su intervalo — pero ese indel esta
        # dentro de una carrera de A y su posicion exacta es ambigua: la ventana real
        # no lo contiene.
        self.assertEqual(len(self.comparacion.identical_window), 21)

    def test_y_los_21_tienen_score_IDENTICO(self):
        self.assertTrue(self.comparacion.window_scores_match)
        self.assertEqual(self.comparacion.window_mismatches, ())

    def test_luego_el_score_ES_funcion_local_de_la_ventana(self):
        self.assertIn("es funcion local", self.comparacion.format_text().lower())

    def test_el_informe_dice_que_los_dos_criterios_discrepan_y_por_que(self):
        texto = self.comparacion.format_text()
        self.assertIn("carrera", texto.lower())
        self.assertIn("221", texto)

    def test_el_PUESTO_en_cambio_NO_es_transferible(self):
        # 20 de 21 cambian de puesto teniendo el score identico: el rank depende del
        # tamaño de la lista, no del sitio. Confundirlo seria transferir un ranking.
        self.assertEqual(len(self.comparacion.moved), 20)
        for sitio in self.comparacion.moved:
            with self.subTest(sitio.start):
                self.assertEqual(sitio.score_delta, 0.0)

    def test_y_el_informe_lo_dice(self):
        self.assertIn("el puesto no", self.comparacion.format_text().lower())
