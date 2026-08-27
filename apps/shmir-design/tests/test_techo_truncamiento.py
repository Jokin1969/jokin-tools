"""El truncamiento por APA es un TECHO, no un veto.

Regla 5: escritos antes de tocar `polya.py`.

El APA no corta el transcrito en dos mitades limpias: produce una MEZCLA de isoformas.
Un candidato situado por detras del corte de un sitio proximal usado en una fraccion f
sigue teniendo diana en la isoforma larga, que es el (1 - f) restante. Su knockdown
maximo alcanzable es ese (1 - f): un TECHO, no un FAIL.

Y ese techo no se puede escribir mientras no se mida. `fraccion_isoforma_larga = None`
significa NO MEDIDA, igual que `divergent_positions=None` significa que nadie miro las
diferencias. No es 0 (todo isoforma corta, techo 0) ni 1 (todo isoforma larga, sin
techo): son tres cosas distintas y la salida tiene que poder distinguirlas.

La señal terminal es otra cosa y sigue siendo FAIL: por detras de SU corte no hay
transcrito en ninguna isoforma, no hay mezcla de la que hablar.

Datos reales: el 3'UTR verificado de NM_011170.3 (1242 nt, md5 canonico 19f5fa2a...).
"""

import unittest
from pathlib import Path

from shmir_design.polya import (
    CLEAVAGE_MAX,
    CLEAVAGE_MIN,
    POLYA_COLUMNS,
    PolyARisk,
    RiskState,
    SignalClass,
    Window,
    find_polya_signals,
    polya_risk,
    rtqpcr_amplicons,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElTruncamientoPorAPAEsUnTecho(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)

    def _solo(self, posicion):
        return [s for s in self.signals if s.position == posicion]

    def _riesgo(self, inicio, señales=None, **kwargs):
        return polya_risk(
            Window(start=inicio, length=22),
            list(self.signals) if señales is None else list(señales),
            utr_length=len(self.utr3),
            **kwargs,
        )

    def test_por_detras_del_corte_de_un_APA_el_estado_es_TECHO(self):
        señal = self._solo(288)[0]
        self.assertIs(señal.classification, SignalClass.APA_POSSIBLE)
        riesgo = self._riesgo(señal.end + CLEAVAGE_MAX + 5, self._solo(288))
        self.assertIs(riesgo.truncamiento, RiskState.TECHO)

    def test_y_TECHO_no_es_FAIL(self):
        self.assertIsNot(RiskState.TECHO, RiskState.FAIL)

    def test_los_cinco_candidatos_del_panel_salen_TECHO_no_FAIL(self):
        for inicio in (449, 553, 652, 819, 1018):
            with self.subTest(inicio):
                self.assertIs(self._riesgo(inicio).truncamiento, RiskState.TECHO)

    def test_en_la_banda_de_corte_sigue_siendo_PENALIZADO(self):
        # El TECHO sustituye al FAIL, no al PENALIZADO: dentro de la banda de 20 nt
        # sigue sin saberse de que lado cae la ventana.
        señal = self._solo(288)[0]
        riesgo = self._riesgo(señal.end + CLEAVAGE_MIN + 5, self._solo(288))
        self.assertIs(riesgo.truncamiento, RiskState.PENALIZADO)

    def test_en_este_3utr_ninguna_ventana_cae_por_detras_del_corte_TERMINAL(self):
        # Hecho geometrico del dato real, y por eso el reparto TECHO/FAIL no cambia
        # ningun veredicto de esta corrida: una señal terminal esta a 10-40 nt del
        # extremo y su corte mas tardio cae +30, asi que detras no cabe nada.
        terminales = [
            s for s in self.signals
            if s.classification is SignalClass.TERMINAL_PROBABLE
        ]
        self.assertTrue(terminales, "el 3'UTR de raton tiene señal terminal")
        for señal in terminales:
            with self.subTest(señal.position):
                self.assertGreater(
                    señal.end + CLEAVAGE_MAX + 1, len(self.utr3) - 21
                )

    def test_la_regla_reserva_FAIL_para_la_TERMINAL(self):
        # Caso de COORDENADAS sobre la longitud real (`classify_signal` clasifica por
        # coordenadas, sin secuencia): una terminal lo bastante adelantada como para
        # que quepa algo detras de su corte. Por detras del corte terminal no hay
        # transcrito en NINGUNA isoforma, asi que no es un techo: la diana no existe.
        from shmir_design.polya import classify_signal

        señal = classify_signal("AATAAA", 1200, len(self.utr3))
        self.assertIs(señal.classification, SignalClass.TERMINAL_PROBABLE)
        riesgo = polya_risk(
            Window(start=señal.end + CLEAVAGE_MAX + 1, length=5),
            [señal],
            utr_length=len(self.utr3),
        )
        self.assertIs(riesgo.truncamiento, RiskState.FAIL)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaFraccionDeIsoformaLarga(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)

    def _riesgo(self, **kwargs):
        return polya_risk(
            Window(start=449, length=22),
            list(self.signals),
            utr_length=len(self.utr3),
            **kwargs,
        )

    def test_el_campo_es_obligatorio_en_la_estructura(self):
        # Sin valor por defecto: ningun camino puede omitirlo y dejar el techo mudo.
        with self.assertRaises(TypeError):
            PolyARisk(
                truncamiento=RiskState.TECHO,
                truncamiento_motivo="",
                esterico=RiskState.NO_APLICA,
                esterico_motivo="",
            )

    def test_sin_medir_vale_None(self):
        self.assertIsNone(self._riesgo().fraccion_isoforma_larga)

    def test_None_no_es_cero_ni_uno(self):
        sin_medir = self._riesgo()
        todo_corta = self._riesgo(fraccion_isoforma_larga=0.0)
        todo_larga = self._riesgo(fraccion_isoforma_larga=1.0)
        self.assertIsNone(sin_medir.techo_knockdown)
        self.assertEqual(todo_corta.techo_knockdown, 0.0)
        self.assertEqual(todo_larga.techo_knockdown, 1.0)

    def test_el_techo_es_la_fraccion_de_isoforma_larga(self):
        # Un sitio proximal usado en f = 0,4 deja un techo de 1 - f = 0,6, que es
        # exactamente la fraccion de isoforma larga.
        self.assertAlmostEqual(
            self._riesgo(fraccion_isoforma_larga=0.6).techo_knockdown, 0.6
        )

    def test_sin_medir_el_texto_dice_indeterminado_y_no_da_veredicto(self):
        texto = self._riesgo().describe_techo().lower()
        self.assertIn("indeterminado", texto)
        self.assertNotIn("fail", texto)

    def test_medido_el_texto_da_la_cifra(self):
        self.assertIn("0.60", self._riesgo(fraccion_isoforma_larga=0.6).describe_techo())

    def test_una_fraccion_fuera_de_0_1_aborta(self):
        for valor in (-0.1, 1.5):
            with self.subTest(valor), self.assertRaises(ValueError):
                self._riesgo(fraccion_isoforma_larga=valor)

    def test_sin_truncamiento_no_se_admite_fraccion(self):
        # Una ventana inmune no tiene techo que medir: aceptar el numero ahi seria
        # emitir un techo que no significa nada.
        with self.assertRaises(ValueError):
            polya_risk(
                Window(start=60, length=22),
                list(self.signals),
                utr_length=len(self.utr3),
                fraccion_isoforma_larga=0.6,
            )

    def test_la_columna_existe_y_va_vacia_sin_medir(self):
        self.assertIn("polyA_fraccion_isoforma_larga", POLYA_COLUMNS)
        columnas = self._riesgo().as_columns()
        # Vacia, NUNCA "0": no haber medido y haber medido cero son cosas distintas.
        self.assertEqual(columnas["polyA_fraccion_isoforma_larga"], "")

    def test_la_columna_trae_la_cifra_cuando_se_mide(self):
        columnas = self._riesgo(fraccion_isoforma_larga=0.6).as_columns()
        self.assertEqual(columnas["polyA_fraccion_isoforma_larga"], "0.60")

    def test_la_columna_del_truncamiento_dice_TECHO(self):
        self.assertEqual(self._riesgo().as_columns()["polyA_truncamiento"], "TECHO")


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElExperimentoQueLoResuelve(unittest.TestCase):
    """RT-qPCR de dos amplicones: uno por delante de la señal, otro por detras del corte.

    Normalizados sobre una curva comun, la razon distal/proximal ES la fraccion de
    isoforma larga: el amplicon proximal esta en las DOS isoformas y el distal solo en
    la larga.
    """

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)
        cls.señal = [s for s in cls.signals if s.position == 288][0]
        cls.plan = rtqpcr_amplicons(cls.señal, utr_length=len(cls.utr3))

    def test_el_proximal_termina_antes_del_hexamero(self):
        self.assertLess(self.plan.proximal.end, self.señal.position)

    def test_el_distal_empieza_por_detras_de_la_banda_de_corte(self):
        self.assertGreater(self.plan.distal.start, self.señal.end + CLEAVAGE_MAX)

    def test_los_dos_caben_en_el_3utr(self):
        for amplicon in (self.plan.proximal, self.plan.distal):
            with self.subTest(amplicon.role):
                self.assertGreaterEqual(amplicon.start, 1)
                self.assertLessEqual(amplicon.end, len(self.utr3))

    def test_las_coordenadas_se_derivan_no_se_escriben(self):
        # El invariante de audit.Span, aqui tambien: fin - inicio + 1 == longitud.
        for amplicon in (self.plan.proximal, self.plan.distal):
            with self.subTest(amplicon.role):
                self.assertEqual(
                    amplicon.end - amplicon.start + 1, amplicon.length
                )

    def test_puede_esquivar_las_ventanas_de_los_candidatos(self):
        # Si se mide sobre muestras tratadas, un amplicon que solape la diana de un
        # candidato mide corte por RNAi, no isoformas.
        estorbo = (self.plan.distal.start, self.plan.distal.start + 21)
        plan = rtqpcr_amplicons(
            self.señal, utr_length=len(self.utr3), avoid=[estorbo]
        )
        self.assertFalse(
            plan.distal.start <= estorbo[1] and plan.distal.end >= estorbo[0]
        )

    def test_si_no_puede_esquivar_lo_DICE_en_vez_de_callarlo(self):
        todo = [(1, len(self.utr3))]
        plan = rtqpcr_amplicons(self.señal, utr_length=len(self.utr3), avoid=todo)
        self.assertTrue(plan.distal.overlaps)
        self.assertTrue(plan.proximal.overlaps)

    def test_no_emite_secuencia_de_cebadores(self):
        # Regla 1: aqui se emiten COORDENADAS. Los cebadores se diseñan aparte, con Tm
        # y especificidad, y eso no se inventa.
        texto = "\n".join(self.plan.describe())
        for base in ("ACGTACGT", "GGGGGGGG"):
            self.assertNotIn(base, texto)
        self.assertIn("no se emiten cebadores", texto.lower())

    def test_el_texto_nombra_la_curva_comun_y_la_razon(self):
        texto = "\n".join(self.plan.describe()).lower()
        self.assertIn("curva", texto)
        self.assertIn("distal/proximal", texto)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLoQueDiceElInforme(unittest.TestCase):
    """El bloque de polyA del informe: techo, supuesto, inmunes y experimento."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        cls.utr3 = _utr3()
        tiling = tile_utr(cls.utr3)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
        cls.texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )

    def test_dice_techo_indeterminado_y_no_un_veredicto(self):
        self.assertIn("techo indeterminado", self.texto.lower())

    def test_no_presenta_el_truncamiento_como_un_veto(self):
        # El APA produce una MEZCLA. Un candidato por detras del corte conserva su
        # diana en la isoforma larga: tiene techo, no veto.
        bloque = self.texto.lower()
        self.assertIn("no es un veto", bloque)
        self.assertIn("mezcla de isoformas", bloque)

    def test_distingue_canonicidad_de_evidencia_de_uso(self):
        # La señal DOMINANTE pasó a ser el `AATATA` de 236, que entra por MEDIDA de uso
        # y no por canonicidad — el caso inverso al del `AATAAA` de 288. Lo que este test
        # protege sigue siendo lo mismo: que el informe diga por CUÁL de las dos vías
        # entró, y no las confunda.
        bloque = self.texto.lower()
        self.assertIn("medida de uso", bloque)
        self.assertIn("canonicidad", bloque)

    def test_sin_otra_especie_la_conservacion_va_NOT_RUN(self):
        # ACTUALIZADO 2026-08-26: dejo de ser «declarado y sin comprobar aqui» cuando
        # llego el 3'UTR humano. Ahora hay dos estados y ninguno es una declaracion:
        # sin --fasta-b, NOT_RUN; con el, COMPROBADO. Esta corrida es de una sola
        # especie, asi que NOT_RUN — y NOT_RUN no dice que no este conservada.
        bloque = self.texto.lower()
        self.assertIn("conservada en otra especie: not_run", bloque)
        self.assertNotIn("no está conservada", bloque)

    def test_y_con_la_otra_especie_lo_COMPRUEBA(self):
        from shmir_design.polya import signal_conservation
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr

        if not fixture_available(REFERENCES["NM_000311.5"]):
            self.skipTest("NOT_RUN: falta el fixture humano")
        resultado = signal_conservation(
            "AATAAA", load_3utr(REFERENCES["NM_000311.5"]), other_name="humano"
        )
        self.assertFalse(resultado.conserved)
        self.assertIn("COMPROBADO", resultado.describe())

    def test_los_tres_inmunes_salen_nombrados(self):
        # Con un solo inmune el panel depende de un supuesto; con tres, no.
        inmunes = [
            l for l in self.texto.splitlines() if "INMUNES" in l or "inmune" in l
        ]
        texto = " ".join(inmunes)
        # 200, no 221: con la medida aplicada `3utr:221` solapa el `AATATA` de 236 y
        # cae por riesgo ESTÉRICO. Su plaza proximal la ocupa `3utr:200`.
        for posicion in ("60", "143", "200"):
            with self.subTest(posicion):
                self.assertIn(posicion, texto)

    def test_el_informe_trae_el_experimento_con_las_dos_coordenadas(self):
        bloque = self.texto
        self.assertIn("RT-qPCR", bloque)
        self.assertIn("proximal", bloque.lower())
        self.assertIn("distal", bloque.lower())
        self.assertIn("fraccion_isoforma_larga", bloque)

    def test_el_experimento_no_trae_cebadores(self):
        self.assertIn("no se emiten cebadores", self.texto.lower())


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestConSitiosMedidosElTechoDejaDeSerNone(unittest.TestCase):
    """Con `--apa-medido` la cantidad ya existe: es `ApaAssessment.knockdown_ceiling`.

    Son el MISMO numero con dos nombres —la fraccion de transcritos que conservan la
    diana—, asi que emitir uno relleno y el otro vacio seria decir dos cosas distintas
    del mismo dato. Se ata aqui.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.apa import ApaSite, ApaSites

        cls.utr3 = _utr3()
        cls.sitios = ApaSites(
            sites=(ApaSite(288, 0.35, "proximal"), ApaSite(1242, 0.65, "distal")),
            source="tabla de sonda para el test",
            version="sonda",
            checksum="0" * 32,
            coords="3utr",
        )

    def _ventana(self, inicio, **kwargs):
        from shmir_design.tiling import tile_utr

        tiling = tile_utr(self.utr3, **kwargs)
        return [w for w in tiling.windows if w.window.start == inicio][0]

    def test_sin_tabla_medida_la_fraccion_va_a_None(self):
        ventana = self._ventana(449)
        self.assertIsNone(ventana.polya.riesgo.fraccion_isoforma_larga)

    def test_con_tabla_medida_la_fraccion_es_el_techo_del_APA(self):
        ventana = self._ventana(449, apa_sites=self.sitios)
        self.assertAlmostEqual(ventana.apa.knockdown_ceiling, 0.65)
        self.assertAlmostEqual(ventana.polya.riesgo.fraccion_isoforma_larga, 0.65)

    def test_y_entonces_la_columna_trae_la_cifra(self):
        ventana = self._ventana(449, apa_sites=self.sitios)
        self.assertEqual(
            ventana.polya.as_columns()["polyA_fraccion_isoforma_larga"], "0.65"
        )

    def test_una_ventana_inmune_no_recibe_techo_aunque_haya_tabla(self):
        # 60 esta por delante del sitio proximal: no tiene truncamiento, asi que no
        # tiene techo. Colarle el numero ahi seria emitir un techo que no se refiere a
        # nada.
        ventana = self._ventana(60, apa_sites=self.sitios)
        self.assertIsNone(ventana.polya.riesgo.fraccion_isoforma_larga)


@unittest.skipUnless(
    (DIR / "NM_011170.3.fa").is_file() and (DIR / "NM_011170.3.gb").is_file(),
    "NOT_RUN: faltan los ficheros de NM_011170.3 en data/reference/",
)
class TestElBloqueNoMezclaMarcosDeCoordenadas(unittest.TestCase):
    """Sobre el transcrito ENTERO las dos parejas no coinciden, y ahi se ve el fallo.

    Las lineas de inmunes del panel van en coordenadas de 3'UTR; la de inmunes
    elegibles salia del objeto `Choice`, que las lleva en coordenadas de LO TILADO. Con
    el 3'UTR suelto las dos parejas coinciden y no se nota; con el mRNA de 2191 nt, el
    143 salia impreso como 1092 — y peor, habia un «1018» que era el 69 del 3'UTR, con
    un candidato elegido que se llama 1018.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.outputs import text_report
        from shmir_design.polya import normalize_sequence
        from shmir_design.resolve import resolve_anatomy
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        _, bruta = parse_fasta_payload(
            (DIR / "NM_011170.3.fa").read_text(encoding="utf-8"), source="fa"
        )
        secuencia = normalize_sequence(bruta, name="NM_011170.3")
        anatomia = resolve_anatomy(
            name="raton", sequence=secuencia, genbank=DIR / "NM_011170.3.gb"
        )
        tiling = tile_utr(secuencia, anatomy=anatomia)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
        cls.texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        cls.linea = [
            l for l in cls.texto.splitlines() if "inmunes también" in l
        ][0]

    def test_los_inmunes_elegibles_van_en_coordenadas_de_3utr(self):
        for posicion in ("143", "200"):
            with self.subTest(posicion):
                self.assertIn(posicion, self.linea)

    def test_y_no_en_coordenadas_del_transcrito(self):
        for posicion in ("1092", "1170"):
            with self.subTest(posicion):
                self.assertNotIn(posicion, self.linea)

    def test_el_experimento_da_las_DOS_parejas(self):
        # Con desfase, cada amplicon lleva su coordenada de lo tilado y la del 3'UTR.
        # COORDENADAS NUEVAS (2026-08-27), y no es cosmético: el experimento se diseña
        # contra la señal de corte MÁS TEMPRANA, y con la promoción por medida aplicada
        # siempre ésa pasó a ser el `AATATA` de `3utr:236` en vez del `AATAAA` de
        # `3utr:288`. Los amplicones se mueven en consecuencia. Quien vaya al banco tiene
        # que usar ÉSTOS.
        bloque = self.texto.split("EXPERIMENTO QUE RESUELVE")[1]
        self.assertIn("tx:1055-1174", bloque)
        self.assertIn("(3utr:106-225)", bloque)
        self.assertIn("tx:1231-1350", bloque)
        self.assertIn("(3utr:282-401)", bloque)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElCebadoDelEnsayo(unittest.TestCase):
    """Con oligo-dT la razon sale sesgada, y el sesgo tiene direccion conocida.

    La RT con oligo-dT ceba en la cola de poli(A) y avanza 3'→5'. Una RT incompleta
    cubre lo que esta CERCA de la cola y pierde lo que esta lejos. En la isoforma LARGA
    el amplicon proximal queda a ~1.000 nt de la cola y el distal a ~440, asi que la
    larga se subrepresenta MAS en el proximal que en el distal — y la razon
    distal/proximal, que es la fraccion de isoforma larga, sale inflada.

    Con hexameros aleatorios el cebado no depende de la distancia a la cola.
    """

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)
        cls.señal = [s for s in cls.signals if s.position == 288][0]
        cls.plan = rtqpcr_amplicons(cls.señal, utr_length=len(cls.utr3))
        cls.texto = "\n".join(cls.plan.describe())

    def test_pide_hexameros_aleatorios_y_descarta_oligo_dT(self):
        bajo = self.texto.lower()
        self.assertIn("hexámeros aleatorios", bajo)
        self.assertIn("oligo-dt", bajo)
        self.assertIn("no", bajo)

    def test_dice_la_DIRECCION_del_sesgo_no_solo_que_lo_hay(self):
        # Un «puede sesgar» no sirve: hay que saber hacia donde, porque el resultado
        # esperado —«casi todo larga»— es justo el que produciria el sesgo.
        bajo = self.texto.lower()
        self.assertIn("hacia más isoforma larga", bajo)

    def test_da_las_dos_distancias_a_la_cola_calculadas(self):
        # ~1.000 nt el proximal y ~440 el distal, sobre la isoforma larga.
        larga_prox = len(self.utr3) - self.plan.proximal.end
        larga_dist = len(self.utr3) - self.plan.distal.end
        self.assertIn(str(larga_prox), self.texto)
        self.assertIn(str(larga_dist), self.texto)

    def test_exige_RIN_documentado(self):
        self.assertIn("RIN", self.texto)

    def test_exige_control_positivo_de_ensayo(self):
        bajo = self.texto.lower()
        self.assertIn("control positivo", bajo)
        self.assertIn("misma", bajo)

    def test_dice_QUE_pasa_sin_el_control_positivo(self):
        bajo = self.texto.lower()
        self.assertIn("ciego", bajo)

    def test_no_nombra_ningun_gen_de_control(self):
        # Nombrar aqui un gen «con APA caracterizado» de memoria seria inventarse una
        # referencia. Se pide el gen con su cita; no se propone uno.
        self.assertIn("con su cita", self.texto)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestPrimeroLoPublicadoYLuegoElBanco(unittest.TestCase):
    """Si la fraccion esta publicada, el experimento es CONFIRMACION, no descubrimiento."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        tiling = tile_utr(_utr3())
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
        cls.texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )

    def test_el_informe_manda_mirar_PolyA_DB_antes_que_el_banco(self):
        bloque = self.texto.split("── Riesgo de polyA")[1]
        antes = bloque.index("PolyA_DB")
        banco = bloque.index("RT-qPCR")
        self.assertLess(antes, banco, "lo publicado va ANTES del experimento")

    def test_nombra_los_datos_de_3_end_seq_de_cerebro_murino(self):
        self.assertIn("3'-end seq", self.texto)
        self.assertIn("cerebro", self.texto.lower())

    def test_dice_que_entonces_el_experimento_seria_CONFIRMACION(self):
        self.assertIn("confirmación", self.texto.lower())


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElAmpliconNoSeSaleDeLaRegionAnalizada(unittest.TestCase):
    """Regresion: esquivar las dianas empujaba el proximal fuera del 3'UTR.

    Con un panel de 10 y cinco inmunes, la region proximal se llena de dianas y el
    amplicon proximal se iba deslizando aguas arriba hasta meterse en el CDS. Ahi ya no
    hay coordenada de 3'UTR: restar el desfase daba `-120`. Lo cazo el invariante de
    `coords.Position` (1-based), no un test.
    """

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)
        cls.señal = [s for s in cls.signals if s.position == 288][0]

    def test_con_la_region_llena_el_amplicon_se_queda_dentro(self):
        estorbo = [(p, p + 21) for p in range(1, 288, 25)]
        plan = rtqpcr_amplicons(
            self.señal, utr_length=len(self.utr3), avoid=estorbo, first_position=1
        )
        self.assertGreaterEqual(plan.proximal.start, 1)

    def test_y_lo_dice_cuando_no_puede_esquivar(self):
        estorbo = [(p, p + 21) for p in range(1, 288, 25)]
        plan = rtqpcr_amplicons(
            self.señal, utr_length=len(self.utr3), avoid=estorbo, first_position=1
        )
        self.assertTrue(plan.proximal.overlaps)

    def test_first_position_corre_el_limite(self):
        plan = rtqpcr_amplicons(
            self.señal, utr_length=len(self.utr3), first_position=30
        )
        self.assertGreaterEqual(plan.proximal.start, 30)

    def test_si_el_limite_no_deja_sitio_ABORTA(self):
        # Con first_position=200 el amplicon de 120 nt tendria que acabar en 319, y el
        # hexamero esta en 288: no cabe. Se aborta en vez de proponer un tramo que pisa
        # la señal.
        with self.assertRaises(ValueError):
            rtqpcr_amplicons(
                self.señal, utr_length=len(self.utr3), first_position=200
            )

    def test_un_first_position_invalido_aborta(self):
        with self.assertRaises(ValueError):
            rtqpcr_amplicons(
                self.señal, utr_length=len(self.utr3), first_position=0
            )
