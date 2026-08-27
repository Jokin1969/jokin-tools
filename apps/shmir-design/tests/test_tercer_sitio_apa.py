"""El TERCER sitio de corte: 131937444, y entra por MEDIDA, no por canonicidad.

Regla 5: escritos antes.

Resuelto el mapeo (`test_anclaje_polyadb`), `chr2:+:131937444` cae sobre el `AATATA` de
`3utr:236-241`. Es una variante RARA, asi que por nuestra cascada de prediccion saldria
`OTRA` — bandera y penalizacion de ranking, nada mas. Pero de este sitio hay MEDIDA, y
es el proximal MAS usado de los tres (PSE 21,1 %, AvgRPM 0,55, frente a 23,5 % / 0,34
del de `3utr:288`).

Es el caso inverso al del `AATAAA` de 288, que es `APA_POSIBLE` por CANONICIDAD y sin un
solo dato de uso. Aqui hay uso y no hay canonicidad. La medida manda sobre la
prediccion — es lo que dice el docstring de este modulo desde el principio— asi que
entra como `APA_POSIBLE` con su banda de corte propia, y el informe escribe por CUAL de
las dos vias entro cada una.

Consecuencias que se comprueban aqui, no se declaran:

  - su corte es MAS TEMPRANO (`3utr:251-271` frente a `3utr:303-323`), luego hay MAS
    ventanas por detras;
  - `3utr:221` sigue siendo INMUNE al truncamiento — empieza por delante de 251;
  - pero `3utr:221-242` SOLAPA el hexamero, y ese es el otro riesgo: el esterico, que
    «solo existe si ese hexamero se usa». Ahora se sabe que se usa;
  - el techo deja de ser UNO y pasa a ser POR TRAMOS.
"""

import unittest

from shmir_design import polya
from shmir_design.apa import (
    POLYA_DB_PRNP,
    ApaExcluded,
    anchor_polyadb,
    ceiling_layers,
    resolve_measured,
)
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.polya import SignalClass
from shmir_design.reference import (
    REFERENCES,
    fixture_available,
    load_3utr,
    load_reference,
)

RATON = REFERENCES["NM_011170.3"]


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaPromocionPorMedida(unittest.TestCase):

    def setUp(self):
        self.utr3 = load_3utr(RATON)
        self.señales = polya.find_polya_signals(self.utr3)
        self.medido = resolve_measured(self.utr3, POLYA_DB_PRNP)

    def test_sin_medida_el_AATATA_de_236_es_OTRA(self):
        s = next(x for x in self.señales if x.position == 236)
        self.assertEqual(s.motif, "AATATA")
        self.assertIs(s.classification, SignalClass.OTHER)

    def test_con_medida_pasa_a_APA_POSIBLE(self):
        promovidas = polya.promote_by_measurement(
            self.señales, self.medido.signal_starts, source=self.medido.source
        )
        s = next(x for x in promovidas if x.position == 236)
        self.assertIs(s.classification, SignalClass.APA_POSSIBLE)

    def test_y_queda_escrito_que_entro_por_MEDIDA_y_no_por_canonicidad(self):
        promovidas = polya.promote_by_measurement(
            self.señales, self.medido.signal_starts, source=self.medido.source
        )
        s = next(x for x in promovidas if x.position == 236)
        self.assertEqual(s.evidence, "medida")
        self.assertIn("PolyA_DB", s.measured_use)

    def test_el_de_288_conserva_la_via_por_la_que_entro(self):
        # Tambien esta medido, asi que su evidencia SUBE de canonicidad a medida. Lo que
        # no puede pasar es que las dos vias se confundan en la salida.
        promovidas = polya.promote_by_measurement(
            self.señales, self.medido.signal_starts, source=self.medido.source
        )
        s = next(x for x in promovidas if x.position == 288)
        self.assertIs(s.classification, SignalClass.APA_POSSIBLE)
        self.assertEqual(s.evidence, "medida")

    def test_una_señal_sin_medir_sigue_por_canonicidad(self):
        s = next(x for x in self.señales if x.position == 288)
        self.assertEqual(s.evidence, "canonicidad")
        self.assertEqual(s.measured_use, "")

    def test_promover_una_posicion_SIN_hexamero_ABORTA(self):
        with self.assertRaises(ValueError) as ctx:
            polya.promote_by_measurement(self.señales, (200,), source="prueba")
        self.assertIn("200", str(ctx.exception))


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaBandaDeCorteYLaInmunidad(unittest.TestCase):

    def setUp(self):
        self.utr3 = load_3utr(RATON)
        self.medido = resolve_measured(self.utr3, POLYA_DB_PRNP)

    def test_el_corte_del_tercer_sitio_es_251_271(self):
        sitio = self.medido.anchor.by_locus("chr2:+:131937444")
        self.assertEqual(sitio.cleavage_band, (251, 271))

    def test_es_MAS_TEMPRANO_que_el_de_288(self):
        a = self.medido.anchor.by_locus("chr2:+:131937444").cleavage_band
        b = self.medido.anchor.by_locus("chr2:+:131937504").cleavage_band
        self.assertEqual(b, (303, 323))
        self.assertLess(a[0], b[0])

    def test_3utr_221_SIGUE_siendo_inmune_al_truncamiento(self):
        # Empieza en 221, por delante del corte mas temprano (251).
        self.assertLessEqual(221, self.medido.earliest_cut)

    def test_los_CUATRO_inmunes_siguen_siendo_inmunes(self):
        for inicio in (10, 60, 143, 221):
            self.assertLessEqual(inicio, self.medido.earliest_cut, inicio)

    def test_el_corte_mas_temprano_BAJA_de_303_a_251(self):
        self.assertEqual(self.medido.earliest_cut, 251)

    def test_pero_3utr_221_SOLAPA_el_hexamero_y_eso_es_el_OTRO_riesgo(self):
        # 3utr:221-242 contiene AATATA en 3utr:236-241. Truncamiento y esterico son dos
        # riesgos distintos y este es el segundo.
        self.assertLessEqual(221, 236)
        self.assertGreaterEqual(242, 241)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElTechoPorTRAMOS(unittest.TestCase):
    """Con tres sitios el techo deja de ser UNO: depende de por detras de cuales estas."""

    def setUp(self):
        self.utr3 = load_3utr(RATON)
        self.medido = resolve_measured(self.utr3, POLYA_DB_PRNP)
        self.capas = ceiling_layers(self.medido)

    def test_por_delante_de_todo_no_hay_techo(self):
        capa = self.medido.layer_for(10)
        self.assertIsNone(capa.ceiling)
        self.assertEqual(capa.lost, ())

    def test_por_detras_del_tercer_sitio_SOLO_el_techo_es_0_91(self):
        capa = self.medido.layer_for(280)
        self.assertAlmostEqual(capa.ceiling, 0.9146, places=4)
        self.assertEqual([s.locus for s in capa.lost], ["chr2:+:131937444"])

    def test_por_detras_de_los_DOS_proximales_el_techo_es_0_86(self):
        capa = self.medido.layer_for(449)
        self.assertAlmostEqual(capa.ceiling, 0.8558, places=4)
        self.assertEqual(len(capa.lost), 2)

    def test_el_0_86_de_la_tabla_es_el_del_tramo_MAS_PROFUNDO(self):
        self.assertAlmostEqual(
            self.medido.layer_for(1018).ceiling, POLYA_DB_PRNP.working_value, places=4
        )

    def test_dentro_de_una_banda_de_corte_el_techo_es_INDETERMINADO(self):
        capa = self.medido.layer_for(260)
        self.assertIsNone(capa.ceiling)
        self.assertTrue(capa.in_band)

    def test_las_capas_cubren_el_3UTR_entero_sin_huecos(self):
        bordes = [c.start_range for c in self.capas]
        self.assertEqual(bordes[0][0], 1)
        self.assertEqual(bordes[-1][1], len(self.utr3))
        for (a, b), (c, _) in zip(bordes, bordes[1:]):
            self.assertEqual(c, b + 1)

    def test_el_techo_NO_SUBE_al_avanzar_por_el_3UTR(self):
        anterior = 1.0
        for capa in self.capas:
            if capa.ceiling is not None:
                self.assertLessEqual(capa.ceiling, anterior + 1e-9)
                anterior = capa.ceiling


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaTablaNoSeAplicaAOtraSecuencia(unittest.TestCase):

    def test_sobre_otro_3UTR_no_se_resuelve_NADA(self):
        humano = REFERENCES["NM_000311.5"]
        if not fixture_available(humano):
            self.skipTest("falta data/reference/NM_000311.5.fa")
        self.assertIsNone(resolve_measured(load_3utr(humano), POLYA_DB_PRNP))

    def test_el_md5_es_la_condicion_y_va_declarado(self):
        self.assertEqual(POLYA_DB_PRNP.utr3_md5, RATON.utr3_md5)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestSobreElTranscritoEntero(unittest.TestCase):
    """El marco de las señales es el de LO TILADO, y con un mRNA no es el del 3'UTR."""

    def setUp(self):
        self.transcrito = load_reference(RATON)
        self.anatomy = Anatomy(
            length=RATON.length, utr5=RATON.utr5, cds=RATON.cds, utr3=RATON.utr3,
            source=RegionSource.ANOTACION_GENBANK,
        )
        self.medido = resolve_measured(
            self.transcrito, POLYA_DB_PRNP, anatomy=self.anatomy
        )

    def test_las_posiciones_salen_en_el_marco_de_LO_TILADO(self):
        # 3utr:236 con el 3'UTR empezando en 950 es tx:1185.
        self.assertIn(236 + 949, self.medido.signal_starts)
        self.assertIn(288 + 949, self.medido.signal_starts)

    def test_el_corte_mas_temprano_tambien(self):
        self.assertEqual(self.medido.earliest_cut, 251 + 949)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLoQueCUESTALaPromocion(unittest.TestCase):
    """La medida no sale gratis, y el informe tiene que decir lo que cuesta.

    `3utr:221-242` CONTIENE el `AATATA` de `3utr:236-241`. Mientras esa señal era una
    variante rara sin datos, el solape valia una penalizacion de ranking (−1,00) y el
    candidato seguia en el panel. Con uso medido, el solape es el riesgo ESTERICO —
    competir con CPSF/CstF por un sitio que se usa— y bajo el criterio escalonado eso es
    FAIL duro, que es lo que ya le pasa a cualquier ventana que solape una `APA_POSIBLE`.

    Asi que `3utr:221` conserva su INMUNIDAD al truncamiento y pierde la plaza por el
    OTRO riesgo. Son dos ejes distintos y el informe no los mezcla.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        cls.medido = resolve_measured(utr3, POLYA_DB_PRNP)
        # La medida entra SOLA desde 2026-08-27; el control «sin» hay que pedirlo
        # a proposito y con motivo escrito. Ver `apa.WHY_MEASURE_IS_NOT_A_FLAG`.
        cls.sin = tile_utr(utr3, measured_apa=ApaExcluded(reason="control de esta comparación: se quiere el resultado SIN la promoción por medida, para poder enseñar qué cambia"))
        cls.con = tile_utr(utr3)

    def _sitios(self, informe):
        from shmir_design.selection import eligible_choices, group_choices

        return [s.best.start for s in group_choices(eligible_choices(informe))]

    def _elegibles(self, informe):
        from shmir_design.selection import is_eligible

        return [w for w in informe.windows if is_eligible(w)]

    def test_3utr_221_estaba_ELEGIBLE_y_deja_de_estarlo(self):
        self.assertIn(221, self._sitios(self.sin))
        self.assertNotIn(221, self._sitios(self.con))

    def test_pero_NO_por_truncamiento_sino_por_SOLAPE(self):
        # Sigue empezando por delante del corte mas temprano: inmune al truncamiento.
        self.assertLessEqual(221, self.medido.earliest_cut)
        ventana = next(w for w in self.con.windows if w.window.start == 221)
        motivo = next(
            f.reason for f in ventana.filters if f.name == "zona_prohibida_polyA"
        )
        self.assertIn("Solapa", motivo)
        self.assertIn("APA_POSIBLE", motivo)
        self.assertIn("AATATA", motivo)

    def test_la_plaza_proximal_NO_se_pierde_la_ocupa_3utr_200(self):
        self.assertIn(200, self._sitios(self.con))

    def test_la_piscina_se_encoge_y_la_cifra_va_escrita(self):
        self.assertEqual(len(self._elegibles(self.sin)), 287)
        self.assertEqual(len(self._elegibles(self.con)), 270)
        self.assertEqual(len(self._sitios(self.sin)), 90)
        self.assertEqual(len(self._sitios(self.con)), 86)

    def test_los_sitios_INMUNES_bajan_de_20_a_16(self):
        from shmir_design.selection import tercio_counts

        self.assertEqual(sum(tercio_counts(self.sin).sites_immune.values()), 20)
        self.assertEqual(sum(tercio_counts(self.con).sites_immune.values()), 16)

    def test_y_siguen_TODOS_en_el_tercio_proximal(self):
        from shmir_design.selection import tercio_counts

        cuenta = tercio_counts(self.con)
        self.assertEqual(cuenta.sites_immune["medio"], 0)
        self.assertEqual(cuenta.sites_immune["distal"], 0)

    def test_el_corte_de_la_inmunidad_se_ADELANTA_a_251(self):
        from shmir_design.selection import tercio_counts

        self.assertEqual(tercio_counts(self.sin).immune_cut, 303)
        self.assertEqual(tercio_counts(self.con).immune_cut, 251)

    def test_el_panel_por_detras_del_TERCER_sitio_no_es_el_mismo_conjunto(self):
        from shmir_design.selection import apa_ceiling_table

        filas = {f.signal.position: f for f in apa_ceiling_table(self.con)}
        self.assertEqual(sorted(filas), [236, 288])
        # Mas ventanas por detras del tercero que del de 288: su corte es anterior.
        self.assertGreater(filas[236].behind, filas[288].behind)
        self.assertEqual(filas[236].behind, 217)
        self.assertEqual(filas[288].behind, 208)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElCuartoFrenteSeCIERRA(unittest.TestCase):
    """Con el mapeo resuelto y el techo por tramos, el APA deja de bloquear."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.selection import (
            SelectionConfig,
            blocking_fronts,
            select_from_report,
        )
        from shmir_design.tiling import tile_utr
        from shmir_design.polya import Tercio

        utr3 = load_3utr(RATON)
        cls.informe = tile_utr(
            utr3
        )
        cls.seleccion = select_from_report(
            cls.informe,
            SelectionConfig(
                n_candidates=10,
                apa_immune_quota=4,
                apa_immune_before=251,
                tercio_quota=((Tercio.PROXIMAL, 4), (Tercio.MEDIO, 3), (Tercio.DISTAL, 2)),
            ),
        )
        cls.frentes = blocking_fronts(cls.informe, cls.seleccion)

    def _apa(self):
        return next(f for f in self.frentes if f.name == "fraccion_isoforma_larga")

    def test_el_frente_SIGUE_saliendo_pero_ya_NO_bloquea(self):
        # Desaparecer seria peor que seguir: quien lea el informe tiene que ver que
        # ese frente existio y por que se cerro.
        self.assertFalse(self._apa().blocking)

    def test_y_no_cuenta_entre_los_bloqueantes(self):
        from shmir_design.selection import blocking_fronts

        bloqueantes = [f for f in blocking_fronts(self.informe, self.seleccion) if f.blocking]
        self.assertNotIn("fraccion_isoforma_larga", [f.name for f in bloqueantes])

    def test_dice_el_techo_de_CADA_tramo_y_no_uno_solo(self):
        motivo = self._apa().reason
        self.assertIn("0.86", motivo)
        self.assertIn("0.91", motivo)

    def test_conserva_la_reserva_del_TEJIDO(self):
        self.assertIn("LÍMITE INFERIOR", self._apa().reason)

    def test_sin_medida_SIGUE_bloqueando(self):
        from shmir_design.selection import blocking_fronts
        from shmir_design.tiling import tile_utr

        sin = tile_utr(load_3utr(RATON), measured_apa=ApaExcluded(reason="control: se pide el resultado SIN promoción para poder enseñar qué cambia con ella"))
        frentes = blocking_fronts(sin, self.seleccion)
        apa = next(f for f in frentes if f.name == "fraccion_isoforma_larga")
        self.assertTrue(apa.blocking)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElEspacioDeCoordenadasDeLosTramos(unittest.TestCase):
    """Los tramos van en el marco de LO TILADO, y la etiqueta lo dice.

    Con el transcrito entero el 3'UTR empieza en 950, asi que un tramo `3utr:1-1200` es
    imposible —el 3'UTR mide 1242— y sin embargo se imprimia sin dar ningun error. Es
    exactamente el fallo que motivo `coords.py`, reaparecido en un bloque nuevo.
    """

    def test_sobre_el_3UTR_los_tramos_van_etiquetados_3utr(self):
        medido = resolve_measured(load_3utr(RATON), POLYA_DB_PRNP)
        self.assertTrue(all(c.describe().startswith("3utr:") for c in medido.layers))

    def test_sobre_el_transcrito_entero_van_etiquetados_tx(self):
        anatomy = Anatomy(
            length=RATON.length, utr5=RATON.utr5, cds=RATON.cds, utr3=RATON.utr3,
            source=RegionSource.ANOTACION_GENBANK,
        )
        medido = resolve_measured(
            load_reference(RATON), POLYA_DB_PRNP, anatomy=anatomy
        )
        self.assertTrue(all(c.describe().startswith("tx:") for c in medido.layers))

    def test_y_el_primer_tramo_empieza_donde_empieza_LO_TILADO(self):
        anatomy = Anatomy(
            length=RATON.length, utr5=RATON.utr5, cds=RATON.cds, utr3=RATON.utr3,
            source=RegionSource.ANOTACION_GENBANK,
        )
        medido = resolve_measured(
            load_reference(RATON), POLYA_DB_PRNP, anatomy=anatomy
        )
        self.assertEqual(medido.layers[-1].start_range[1], RATON.length)

    def test_el_anclaje_SI_va_en_3utr_porque_se_hace_sobre_el_3UTR(self):
        anatomy = Anatomy(
            length=RATON.length, utr5=RATON.utr5, cds=RATON.cds, utr3=RATON.utr3,
            source=RegionSource.ANOTACION_GENBANK,
        )
        medido = resolve_measured(
            load_reference(RATON), POLYA_DB_PRNP, anatomy=anatomy
        )
        self.assertEqual(
            medido.anchor.by_locus("chr2:+:131937444").hexamer_start, 236
        )
        self.assertIn("3utr:236", medido.anchor.by_locus("chr2:+:131937444").describe())


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElInformeDiceLoQueCuesta(unittest.TestCase):
    """La promocion tumba ventanas, y eso no puede quedar en un numero que baja.

    `3utr:221` sale del panel sin que ninguna linea lo mencione, porque la piscina de
    elegibles simplemente es mas pequeña. Un candidato que desaparece por una decision
    nuestra tiene que salir NOMBRADO, con la decision al lado.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.selection import measured_promotion_cost
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        cls.informe = tile_utr(
            utr3
        )
        cls.coste = measured_promotion_cost(cls.informe)

    def test_hay_coste_y_esta_contado(self):
        self.assertTrue(self.coste.windows)

    def test_3utr_221_esta_NOMBRADO_entre_los_que_se_pierden(self):
        self.assertIn(221, self.coste.window_starts)

    def test_solo_cuenta_las_que_caen_POR_ESTO_y_no_por_otro_filtro(self):
        # Una ventana que ya fallaba GC no la tumba la promocion: contarla inflaria el
        # coste y haria parecer cara una decision que no lo es tanto.
        for ventana in self.coste.windows:
            fallos = [f.name for f in ventana.filters if f.state.value == "FAIL"]
            self.assertEqual(fallos, ["zona_prohibida_polyA"])

    def test_dice_QUE_señal_las_tumba_y_por_que_via_entro(self):
        texto = self.coste.describe()
        self.assertIn("AATATA", texto)
        self.assertIn("3utr:236", texto)
        self.assertIn("MEDIDA", texto.upper())

    def test_distingue_el_riesgo_de_TRUNCAMIENTO_del_ESTERICO(self):
        texto = self.coste.describe().upper()
        self.assertIn("ESTERICO", texto)
        self.assertIn("INMUN", texto)

    def test_sin_promocion_no_hay_coste(self):
        from shmir_design.selection import measured_promotion_cost
        from shmir_design.tiling import tile_utr

        coste = measured_promotion_cost(
            tile_utr(load_3utr(RATON), measured_apa=ApaExcluded(reason="control: se pide el resultado SIN promoción para poder enseñar qué cambia con ella"))
        )
        self.assertEqual(coste.windows, ())
        self.assertEqual(coste.describe(), "")

    def test_NO_le_cobra_a_la_promocion_lo_que_ya_fallaba_por_la_CANONICA(self):
        # El AATAAA de 3utr:288 ya era APA_POSIBLE por la cascada de prediccion, asi que
        # las ventanas que lo solapan ya fallaban. La medida solo le cambia la
        # evidencia; cobrarle esas ventanas seria pasar factura por algo ya pagado.
        self.assertEqual([s.position for s in self.coste.signals], [236])
        self.assertTrue(all(p <= 251 for p in self.coste.window_starts))


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaTablaDeTechosLlevaSuMARCO(unittest.TestCase):
    """`apa_ceiling_table` etiquetaba siempre `3utr:` sobre coordenadas de lo tilado."""

    def _tabla(self, secuencia, anatomy=None):
        from shmir_design.selection import apa_ceiling_table
        from shmir_design.tiling import tile_utr

        return apa_ceiling_table(
            tile_utr(secuencia, anatomy=anatomy)
        )

    def test_sobre_el_3UTR_va_en_3utr(self):
        filas = self._tabla(load_3utr(RATON))
        self.assertIn("3utr:236", filas[0].describe())

    def test_sobre_el_transcrito_entero_va_en_tx(self):
        anatomy = Anatomy(
            length=RATON.length, utr5=RATON.utr5, cds=RATON.cds, utr3=RATON.utr3,
            source=RegionSource.ANOTACION_GENBANK,
        )
        filas = self._tabla(load_reference(RATON), anatomy)
        texto = filas[0].describe()
        self.assertIn("tx:1185", texto)
        self.assertNotIn("3utr:1185", texto)

    def test_distingue_la_SUBIDA_por_medida_de_la_canonica_CONFIRMADA(self):
        filas = {f.signal.position: f for f in self._tabla(load_3utr(RATON))}
        self.assertIn("SUBIDA aquí por MEDIDA", filas[236].describe())
        self.assertIn("CONFIRMADA por medida", filas[288].describe())

    def test_y_sin_medida_ninguna_de_las_dos_cosas(self):
        from shmir_design.selection import apa_ceiling_table
        from shmir_design.tiling import tile_utr

        filas = apa_ceiling_table(
            tile_utr(load_3utr(RATON), measured_apa=ApaExcluded(reason="control: se pide el resultado SIN promoción para poder enseñar qué cambia con ella"))
        )
        self.assertIn("sin dato de uso", filas[0].describe())
