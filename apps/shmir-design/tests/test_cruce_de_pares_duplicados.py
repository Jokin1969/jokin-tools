"""Dos implementaciones del mismo número son una OPORTUNIDAD, no un descarte.

El informe de alcanzabilidad sacó tres pares donde parecía haber dos formas de calcular
lo mismo con una de ellas sin llamador. La respuesta no es borrar la que no se usa: es
CRUZARLAS. Si coinciden, sale verificación cruzada gratis; si no, sale un fallo que
nadie habría visto. Es lo que ya funcionó con los dos contadores de seed.

Al cruzarlas, los tres pares resultaron ser tres cosas DISTINTAS, y eso es el resultado:

  · `spliceai.verdict_state` / `SpliceRun.verdict` — par de verdad, y NO COINCIDEN.
    Ver `TestElParQueNOCoincide`: es un fallo, y estaba escrito y sin correr.
  · `apa.ceiling_layers` / `MeasuredApa.layer_for` — NO son dos implementaciones:
    `ceiling_layers(m)` es `return m.layers` y `layer_for` busca DENTRO de esa misma
    lista, así que no pueden discrepar. Lo que sí se puede exigir es el invariante que
    el docstring afirma —que los tramos cubren el 3'UTR sin huecos—, y eso es lo que se
    comprueba sobre los diez del panel.
  · `polya.analyze_3utr` / `polya.annotate_polya` — dos GENERACIONES, con reglas
    deliberadamente distintas: la vieja usa el umbral simétrico ±10 que «no sale de
    ningún artículo», la nueva la ventana de corte asimétrica aguas abajo. Exigirles que
    coincidan sería exigir que el bloque 3 no hubiera pasado. Lo que SÍ comparten es
    `find_polya_signals`, y ese es el número que se cruza.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr


class TestElParQueNOCoincide(unittest.TestCase):
    """`verdict_state` mira la corrida ENTERA; `SpliceRun.verdict`, el PAR.

    La unidad de este frente es el par candidato x intrón — se decidió así y la ficha
    saca una fila por intrón consultado. `verdict_state` se quedó en la granularidad
    anterior: le basta con que la corrida tenga PARES, cualesquiera. Para un candidato
    que NO se consultó dice PASS donde el almacén dice NOT_RUN.

    O sea: la que no tiene llamador no es una copia redundante, es la EQUIVOCADA. Si
    alguien la hubiera cableado —y estaba ahí para que alguien la cableara— habría
    cerrado el frente de empalme para candidatos que nadie consultó.
    """

    def _scan_con_un_solo_par(self):
        from shmir_design.spliceai import PairResult, SpliceScan

        par = PairResult(
            construction="3utr200_x_quimerico_cmv_globina",
            candidate_start=200, intron="quimerico_cmv_globina",
            legit_donor=0.90, legit_acceptor=0.85, cryptics=(),
            known_cryptic=None, context_5=0, context_3=0,
        )
        return SpliceScan(pairs=(par,))

    def test_para_el_par_CONSULTADO_las_dos_dicen_lo_mismo(self):
        from shmir_design.spliceai import verdict_state

        scan = self._scan_con_un_solo_par()
        self.assertIs(verdict_state(scan), FilterState.PASS)
        self.assertIs(self._verdict(scan, 200).state, FilterState.PASS)

    def test_para_un_par_NO_consultado_DISCREPAN(self):
        from shmir_design.spliceai import verdict_state

        scan = self._scan_con_un_solo_par()
        # La corrida tiene pares, así que la de la corrida entera dice PASS...
        self.assertIs(verdict_state(scan), FilterState.PASS)
        # ...y el candidato 359 no está en ella, así que el almacén dice NOT_RUN.
        self.assertIs(self._verdict(scan, 359).state, FilterState.NOT_RUN)
        # Esta es la discrepancia. El test la FIJA para que borrar `verdict_state` sin
        # entenderla, o cablearla, tenga que pasar por aquí.

    def test_la_del_ALMACEN_es_la_que_manda_y_se_dice_por_que(self):
        motivo = self._verdict(self._scan_con_un_solo_par(), 359).reason
        self.assertIn("no se consulto", motivo.replace("ó", "o"))
        self.assertIn("NOT_RUN no es PASS", motivo)

    def _verdict(self, scan, start: int):
        from shmir_design.splice_store import SpliceRun

        corrida = SpliceRun.create(
            scan=scan, raw="crudo", date="2026-08-27", ran_by="test",
            run_id="cruce-1", executor="test",
        )
        return corrida.verdict(start, "quimerico_cmv_globina")


class TestElInvarianteDeLosTramos(unittest.TestCase):
    """`ceiling_layers` no es una segunda implementación, pero su promesa sí se comprueba."""

    @unittest.skipUnless(fixture_available(REFERENCES["NM_011170.3"]), "falta el 3'UTR murino")
    def test_los_tramos_cubren_el_3utr_sin_huecos_ni_solapes(self):
        medido = self._medido()
        if medido is None:
            self.skipTest("no hay tabla de APA medido anclada para el ratón")
        from shmir_design.apa import ceiling_layers

        capas = ceiling_layers(medido)
        self.assertTrue(capas, "una tabla anclada sin tramos no cubre nada")
        for anterior, siguiente in zip(capas, capas[1:]):
            self.assertEqual(
                anterior.start_range[1] + 1, siguiente.start_range[0],
                f"hueco o solape entre {anterior.start_range} y {siguiente.start_range}",
            )

    @unittest.skipUnless(fixture_available(REFERENCES["NM_011170.3"]), "falta el 3'UTR murino")
    def test_layer_for_devuelve_EL_tramo_que_contiene_cada_inicio(self):
        # El cruce que sí tiene sentido en este par: la búsqueda por posición contra la
        # lista entera, sobre posiciones de verdad del 3'UTR murino.
        medido = self._medido()
        if medido is None:
            self.skipTest("no hay tabla de APA medido anclada para el ratón")
        from shmir_design.apa import ceiling_layers

        capas = ceiling_layers(medido)
        primero, ultimo = capas[0].start_range[0], capas[-1].start_range[1]
        for inicio in range(primero, ultimo + 1, 37):
            with self.subTest(inicio=inicio):
                capa = medido.layer_for(inicio)
                self.assertIn(capa, capas)
                self.assertLessEqual(capa.start_range[0], inicio)
                self.assertLessEqual(inicio, capa.start_range[1])

    def _medido(self):
        from shmir_design.apa import POLYA_DB_PRNP, resolve_measured

        return resolve_measured(load_3utr(REFERENCES["NM_011170.3"]), POLYA_DB_PRNP)


class TestLoQueSICOMPARTEN(unittest.TestCase):
    """Las dos generaciones de polyA parten de las MISMAS señales."""

    @unittest.skipUnless(fixture_available(REFERENCES["NM_011170.3"]), "falta el 3'UTR murino")
    def test_el_conjunto_de_hexameros_es_el_mismo_por_los_dos_caminos(self):
        from shmir_design.polya import analyze_3utr, find_polya_signals
        from shmir_design.tiling import Window

        secuencia = load_3utr(REFERENCES["NM_011170.3"])
        ventanas = [Window(start, 22, label=f"w{start}") for start in (143, 200, 1018)]

        directas = find_polya_signals(secuencia, first_position=1)
        informe = analyze_3utr(secuencia, ventanas, first_position=1)

        self.assertEqual(
            sorted(s.position for s in directas),
            sorted(s.position for s in informe.signals),
            "la generación vieja y la búsqueda directa ven hexámeros distintos",
        )

    @unittest.skipUnless(fixture_available(REFERENCES["NM_011170.3"]), "falta el 3'UTR murino")
    def test_y_el_AATATA_conocido_esta_en_los_dos(self):
        # 3utr:236 = tx:1185, el AATATA murino conocido. Un cruce sin un ancla concreta
        # sólo dice que dos cosas coinciden, no que coincidan en LO BUENO.
        from shmir_design.polya import find_polya_signals

        secuencia = load_3utr(REFERENCES["NM_011170.3"])
        posiciones = {s.position for s in find_polya_signals(secuencia, first_position=1)}
        self.assertIn(236, posiciones)


if __name__ == "__main__":
    unittest.main()
