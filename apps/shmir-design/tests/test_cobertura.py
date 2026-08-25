"""Tests de la seleccion por cobertura de rango (bloque 6).

Regla 5: escritos antes de implementarla.

Por que no los N mejores por asimetria: la asimetria predice SELECCION DE HEBRA, no
potencia. Si el objetivo de llevar diez candidatos es correlacionar cada parametro
contra el knockdown medido y averiguar cuales predicen algo, los puntos tienen que
estar repartidos. Diez candidatos todos con GC 0,50 y accesibilidad alta no dicen nada
sobre el GC ni sobre la accesibilidad.

Los ejes que se reparten son los parametros DUDOSOS: GC, accesibilidad, posicion
respecto al APA y bandera de polyA.
"""

import unittest

from shmir_design.anatomy import Region
from shmir_design.polya import Tercio
from shmir_design.selection import (
    COVERAGE_AXES,
    Choice,
    SelectionConfig,
    Site,
    choose,
    coverage_report,
)


def _sitio(start, *, gc, acceso=None, apa=False, bandera=False, asimetria=1.0):
    return Site(
        choices=(
            Choice(
                start=start,
                end=start + 21,
                tercio=Tercio.PROXIMAL,
                asymmetry=asimetria,
                label=f"w{start}",
                asymmetry_raw=asimetria,
                region=Region.UTR3,
                gc=gc,
                accessibility=acceso,
                apa_risk=apa,
                weak_polya=bandera,
            ),
        )
    )


#: Seis sitios que cubren los extremos de cada eje, separados >50 nt.
SITIOS = [
    _sitio(100, gc=0.30, acceso=0.20, apa=False, bandera=False, asimetria=2.0),
    _sitio(200, gc=0.65, acceso=0.90, apa=True, bandera=True, asimetria=1.9),
    _sitio(300, gc=0.32, acceso=0.25, apa=False, bandera=False, asimetria=1.8),
    _sitio(400, gc=0.34, acceso=0.22, apa=False, bandera=False, asimetria=1.7),
    _sitio(500, gc=0.36, acceso=0.28, apa=False, bandera=False, asimetria=1.6),
    _sitio(600, gc=0.38, acceso=0.24, apa=False, bandera=False, asimetria=1.5),
]


class TestConfiguracion(unittest.TestCase):

    def test_por_defecto_no_se_reparte(self):
        self.assertFalse(SelectionConfig().spread_coverage)

    def test_los_ejes_son_los_parametros_dudosos(self):
        self.assertEqual(
            set(COVERAGE_AXES), {"GC", "accesibilidad", "APA", "polyA_debil"}
        )


class TestReparto(unittest.TestCase):

    def _elegir(self, n, spread):
        return choose(
            list(SITIOS),
            SelectionConfig(
                n_candidates=n,
                require_one_per_tercio=False,
                spread_coverage=spread,
                min_spacing=50,
            ),
        )

    def test_sin_reparto_manda_la_asimetria(self):
        elegidos = [c.start for c in self._elegir(2, False).chosen]
        self.assertEqual(elegidos, [100, 200])

    def test_con_reparto_entran_los_dos_extremos_de_cada_eje(self):
        seleccion = self._elegir(2, True)
        gcs = [c.gc for c in seleccion.chosen]
        self.assertTrue(min(gcs) < 0.4 < max(gcs))

    def test_el_reparto_no_se_salta_el_espaciado(self):
        juntos = [
            _sitio(100, gc=0.30, acceso=0.10),
            _sitio(110, gc=0.70, acceso=0.90),
        ]
        seleccion = choose(
            juntos,
            SelectionConfig(
                n_candidates=2, require_one_per_tercio=False,
                spread_coverage=True, min_spacing=50,
            ),
        )
        self.assertEqual(len(seleccion.chosen), 1)

    def test_pedir_mas_de_los_que_hay_no_revienta(self):
        seleccion = self._elegir(20, True)
        self.assertEqual(len(seleccion.chosen), len(SITIOS))

    def test_con_reparto_se_eligen_tantos_como_se_piden(self):
        self.assertEqual(len(self._elegir(4, True).chosen), 4)

    def test_a_igualdad_de_cobertura_manda_la_asimetria(self):
        """Cuando ya no queda celda nueva que cubrir, se ordena por asimetria."""
        seleccion = self._elegir(6, True)
        restantes = [c for c in seleccion.chosen if c.start not in (100, 200)]
        self.assertEqual(
            [c.start for c in sorted(restantes, key=lambda c: -c.asymmetry)][0], 300
        )


class TestInformeDeCobertura(unittest.TestCase):

    def test_dice_que_rango_cubre_cada_eje(self):
        seleccion = choose(
            list(SITIOS),
            SelectionConfig(
                n_candidates=2, require_one_per_tercio=False, spread_coverage=True
            ),
        )
        texto = coverage_report(seleccion).format_text()
        for eje in COVERAGE_AXES:
            self.assertIn(eje, texto)

    def test_dice_el_minimo_y_el_maximo_de_GC(self):
        seleccion = choose(
            list(SITIOS),
            SelectionConfig(
                n_candidates=2, require_one_per_tercio=False, spread_coverage=True
            ),
        )
        texto = coverage_report(seleccion).format_text()
        self.assertIn("0.30", texto)
        self.assertIn("0.65", texto)

    def test_avisa_de_los_ejes_que_no_se_cubren(self):
        """Si todos los candidatos caen del mismo lado, ese eje no dice nada."""
        planos = [
            _sitio(100 * i, gc=0.40, acceso=0.50, apa=False, bandera=False)
            for i in range(1, 5)
        ]
        seleccion = choose(
            planos,
            SelectionConfig(
                n_candidates=3, require_one_per_tercio=False, spread_coverage=True
            ),
        )
        texto = coverage_report(seleccion).format_text()
        self.assertIn("no se cubre", texto.lower())

    def test_un_eje_sin_dato_se_dice_que_no_se_pudo_repartir(self):
        sin_acceso = [
            _sitio(100 * i, gc=0.30 + 0.1 * i, acceso=None) for i in range(1, 5)
        ]
        seleccion = choose(
            sin_acceso,
            SelectionConfig(
                n_candidates=3, require_one_per_tercio=False, spread_coverage=True
            ),
        )
        texto = coverage_report(seleccion).format_text()
        self.assertIn("sin dato", texto.lower())

    def test_sin_reparto_el_informe_lo_dice_igual(self):
        """El rango cubierto interesa aunque no se haya repartido a proposito."""
        seleccion = choose(
            list(SITIOS),
            SelectionConfig(n_candidates=3, require_one_per_tercio=False),
        )
        self.assertTrue(coverage_report(seleccion).format_text())


if __name__ == "__main__":
    unittest.main()


class TestElRepartoCambiaLaEleccion(unittest.TestCase):
    """Test discriminante: sin el, los anteriores podrian pasar por casualidad."""

    #: El de mejor asimetria y el segundo caen en la MISMA celda de todos los ejes;
    #: el tercero es el unico que cubre las celdas contrarias.
    SITIOS = [
        _sitio(100, gc=0.30, acceso=0.10, apa=False, bandera=False, asimetria=3.0),
        _sitio(200, gc=0.31, acceso=0.11, apa=False, bandera=False, asimetria=2.9),
        _sitio(300, gc=0.80, acceso=0.95, apa=True, bandera=True, asimetria=0.1),
    ]

    def _elegir(self, spread):
        return [
            c.start
            for c in choose(
                list(self.SITIOS),
                SelectionConfig(
                    n_candidates=2,
                    require_one_per_tercio=False,
                    spread_coverage=spread,
                    min_spacing=50,
                ),
            ).chosen
        ]

    def test_sin_reparto_salen_los_dos_mejores_por_asimetria(self):
        self.assertEqual(self._elegir(False), [100, 200])

    def test_con_reparto_entra_el_que_cubre_el_otro_extremo(self):
        self.assertEqual(self._elegir(True), [100, 300])

    def test_y_los_dos_repartos_son_distintos(self):
        self.assertNotEqual(self._elegir(False), self._elegir(True))


class TestEjeNoEstudiable(unittest.TestCase):
    """Distinguir «la seleccion no reparte» de «este 3'UTR no da para estudiarlo».

    Si TODOS los candidatos que sobreviven a los filtros tienen el GC entre 0,41 y 0,50,
    que la seleccion no cubra el rango no es un fallo: es que ese eje no se puede
    estudiar con este 3'UTR, y hay que dejar de tratarlo como variable.
    """

    #: Piscina entera con el GC apretado: no hay de donde sacar un extremo bajo.
    APRETADOS = [
        _sitio(100 * i, gc=0.41 + 0.01 * i, acceso=0.5, asimetria=2.0 - 0.1 * i)
        for i in range(1, 6)
    ]
    #: Piscina con los dos extremos disponibles.
    ANCHOS = [
        _sitio(100, gc=0.30, acceso=0.2, asimetria=2.0),
        _sitio(200, gc=0.31, acceso=0.2, asimetria=1.9),
        _sitio(300, gc=0.70, acceso=0.9, asimetria=0.1),
    ]

    def _cobertura(self, sitios, n=2, spread=True):
        config = SelectionConfig(
            n_candidates=n, require_one_per_tercio=False,
            spread_coverage=spread, min_spacing=50,
        )
        return coverage_report(choose(list(sitios), config), sites=sitios)

    def _lineas_del_eje(self, cobertura, eje="GC"):
        """Solo las lineas de un eje: cada eje tiene su propio diagnostico."""
        texto = cobertura.format_text().splitlines()
        recogiendo, salida = False, []
        for linea in texto:
            if linea.strip().startswith(eje):
                recogiendo, salida = True, [linea]
                continue
            if recogiendo:
                if linea.startswith("  ") and linea.strip() and not linea.startswith("      "):
                    break
                salida.append(linea)
        return "\n".join(salida)

    def test_si_la_piscina_entera_esta_apretada_el_eje_no_es_estudiable(self):
        texto = self._lineas_del_eje(self._cobertura(self.APRETADOS))
        self.assertIn("no se puede estudiar", texto.lower())

    def test_y_lo_dice_con_el_rango_real_de_la_piscina(self):
        texto = self._lineas_del_eje(self._cobertura(self.APRETADOS))
        self.assertIn("0.42", texto)
        self.assertIn("0.46", texto)

    def test_y_dice_que_deje_de_tratarse_como_variable(self):
        texto = self._lineas_del_eje(self._cobertura(self.APRETADOS))
        self.assertIn("variable", texto.lower())

    def test_no_lo_llama_fallo_de_la_app(self):
        texto = self._lineas_del_eje(self._cobertura(self.APRETADOS))
        self.assertIn("no es un fallo", texto.lower())

    def test_si_la_piscina_daba_de_si_el_diagnostico_es_otro(self):
        """Aqui si es la seleccion la que no ha repartido, y se dice distinto."""
        texto = self._lineas_del_eje(
            self._cobertura(self.ANCHOS, n=2, spread=False)
        )
        self.assertIn("si habia", texto.lower())
        self.assertNotIn("no se puede estudiar", texto.lower())

    def test_con_reparto_la_piscina_ancha_si_cubre_el_GC(self):
        texto = self._lineas_del_eje(self._cobertura(self.ANCHOS, n=2, spread=True))
        self.assertNotIn("NO SE CUBRE", texto)

    def test_sin_la_piscina_no_se_puede_distinguir_y_se_dice(self):
        """Compatibilidad: llamar sin `sites` sigue valiendo, pero no diagnostica."""
        config = SelectionConfig(
            n_candidates=2, require_one_per_tercio=False, spread_coverage=False,
            min_spacing=50,
        )
        cobertura = coverage_report(choose(list(self.ANCHOS), config))
        self.assertIn("no se comprobo", self._lineas_del_eje(cobertura).lower())

    def test_un_recorrido_corto_no_pasa_por_cubierto(self):
        """El caso real: GC de 0,41 a 0,50 cruza el corte pero son 0,09 de recorrido."""
        apretados = [
            _sitio(100, gc=0.41, acceso=0.5, asimetria=2.0),
            _sitio(200, gc=0.50, acceso=0.5, asimetria=1.9),
        ]
        cobertura = coverage_report(
            choose(
                list(apretados),
                SelectionConfig(
                    n_candidates=2, require_one_per_tercio=False, min_spacing=50
                ),
            ),
            sites=apretados,
        )
        texto = self._lineas_del_eje(cobertura)
        self.assertIn("recorrido es demasiado corto", texto)
        self.assertIn("no se puede estudiar", texto.lower())

    def test_dice_el_minimo_que_se_esta_pidiendo(self):
        apretados = [
            _sitio(100, gc=0.41, acceso=0.5),
            _sitio(200, gc=0.50, acceso=0.5),
        ]
        cobertura = coverage_report(
            choose(
                list(apretados),
                SelectionConfig(
                    n_candidates=2, require_one_per_tercio=False, min_spacing=50
                ),
            ),
            sites=apretados,
        )
        self.assertIn("0.10", self._lineas_del_eje(cobertura))

    def test_el_eje_estudiable_se_marca_como_tal(self):
        cobertura = self._cobertura(self.ANCHOS)
        self.assertTrue(cobertura.axes["GC"]["estudiable"])

    def test_el_eje_no_estudiable_tambien(self):
        cobertura = self._cobertura(self.APRETADOS)
        self.assertFalse(cobertura.axes["GC"]["estudiable"])
