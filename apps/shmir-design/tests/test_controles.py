"""Los dos controles del experimento: `shmir_scrambled` y `shmir_seed_mismatch`.

Regla 5: escritos ANTES del modulo y contra datos reales — la guia de `3utr:1018` del
panel murino y el 3'UTR verificado por md5. Ninguna secuencia de este fichero esta
inventada: todas salen de la referencia o se derivan de ella.

**Lo que un control tiene que ser, y por que no basta con «que no tenga diana».** Un
scrambled al azar no es un control: si su tallo es mas debil se carga peor en AGO2, asi
que la comparacion mide dos cosas a la vez —la diana y el procesamiento— y no separa
ninguna. Por eso la permutacion conserva la composicion EXACTA y por eso la asimetria
entra como filtro y no como adorno.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.mirna import SEED_END, SEED_START
from shmir_design.presencia import hay_fichero
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.trabajo import reference_dir

HAY_UTR3 = fixture_available(REFERENCES["NM_011170.3"])
HAY_MADUROS = hay_fichero(reference_dir() / "mature.fa")

#: La guia de `3utr:1018` del panel murino, en ADN. Sale de la corrida real; no se
#: teclea aqui como dato nuevo — `test_la_guia_es_la_del_panel` la contrasta.
GUIA = "TTTAGTACTGGATGGAACGGCC"
ORIGEN = "3utr:1018"


def _utr3():
    return load_3utr(REFERENCES["NM_011170.3"])


def _maduros():
    from shmir_design.mirna import load_mature_fa

    return load_mature_fa(reference_dir() / "mature.fa", version="23")


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestLaGuiaDeReferencia(unittest.TestCase):
    """Antes de nada: que la guia de la que cuelga todo esto sea la del panel."""

    def test_la_guia_es_la_del_panel(self):
        from shmir_design.hard_filters import guide_from_target

        utr3 = _utr3()
        diana = utr3[1018 - 1 : 1018 - 1 + 22]
        self.assertEqual(guide_from_target(diana).replace("U", "T"), GUIA)


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestLaPermutacionCONSERVAlaComposicion(unittest.TestCase):
    """Un scrambled al azar no es un control. Este conserva la composicion EXACTA."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import scrambled_candidates

        cls.candidatos = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=4,
        )

    def test_salen_varios(self):
        self.assertEqual(len(self.candidatos), 4)

    def test_cada_uno_tiene_la_MISMA_composicion_que_el_original(self):
        for control in self.candidatos:
            self.assertEqual(
                sorted(control.guide), sorted(GUIA),
                f"{control.guide} no es una permutacion de {GUIA}",
            )

    def test_y_por_tanto_el_MISMO_GC(self):
        from shmir_design.hard_filters import gc_fraction

        for control in self.candidatos:
            self.assertEqual(gc_fraction(control.guide), gc_fraction(GUIA))

    def test_la_posicion_1_NO_se_permuta_porque_es_CONVENIO(self):
        """La T/U de la posicion 1 la fuerza el pipeline para que AGO2 cargue la hebra.

        Permutarla cambiaria el control en algo que no es su secuencia diana.
        """
        for control in self.candidatos:
            self.assertEqual(control.guide[0], GUIA[0])

    def test_y_ninguno_es_el_original(self):
        for control in self.candidatos:
            self.assertNotEqual(control.guide, GUIA)

    def test_son_distintos_entre_si(self):
        self.assertEqual(
            len({c.guide for c in self.candidatos}), len(self.candidatos)
        )

    def test_la_corrida_es_DETERMINISTA(self):
        from shmir_design.controles import scrambled_candidates

        otra = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=4,
        )
        self.assertEqual(
            [c.guide for c in otra], [c.guide for c in self.candidatos]
        )


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestElScrambledNOtieneDIANA(unittest.TestCase):
    """Dos preguntas y ninguna cubre a la otra: apareamiento extenso y sitio de seed."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import scrambled_candidates

        cls.utr3 = _utr3()
        cls.candidatos = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=cls.utr3, target_label="3'UTR de Prnp",
            wanted=4,
        )

    def test_ninguno_llega_al_maximo_contiguo_declarado(self):
        from shmir_design.controles import MAX_CONTIGUO

        for control in self.candidatos:
            self.assertLess(control.max_contiguous, MAX_CONTIGUO)

    def test_ninguno_tiene_sitio_de_seed_en_el_3utr(self):
        for control in self.candidatos:
            self.assertEqual(control.seed_sites, ())

    def test_CONTROL_ADVERSARIO_la_guia_ORIGINAL_si_los_tiene(self):
        """Sin esto, «cero sitios» y «la medida no distingue nada» serian lo mismo.

        Es la leccion de `intron_folding`: un criterio que da el mismo resultado a todo
        el mundo no es un criterio. La guia original tiene su propia diana entera y sus
        sitios de seed, asi que las dos medidas SI discriminan.
        """
        from shmir_design.controles import longest_contiguous, seed_sites_in

        self.assertEqual(longest_contiguous(GUIA, self.utr3), 22)
        self.assertTrue(seed_sites_in(GUIA, self.utr3))

    def test_el_frente_del_transcriptoma_queda_NOT_RUN(self):
        """Sin `refseq_rna.fa` no se puede decir que no tenga diana EN NINGUN SITIO."""
        for control in self.candidatos:
            estados = {f.name: f.state for f in control.filters}
            self.assertEqual(estados["especificidad"], FilterState.NOT_RUN)
            self.assertIn("refseq", estados_motivo(control, "especificidad").lower())


def estados_motivo(control, nombre):
    return next(f.reason for f in control.filters if f.name == nombre)


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestElScrambledPASAlosMISMOSfiltros(unittest.TestCase):
    """Un scrambled con off-targets propios contamina lo que viene a controlar."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import scrambled_candidates

        cls.candidatos = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=4,
        )

    def test_los_tres_biofisicos_estan_y_PASAN(self):
        for control in self.candidatos:
            estados = {f.name: f.state for f in control.filters}
            for nombre in ("GC", "homopolimero", "asimetria"):
                self.assertEqual(estados[nombre], FilterState.PASS, nombre)

    def test_el_GC_no_puede_fallar_y_eso_va_DICHO(self):
        """La permutacion conserva la composicion, asi que el GC es el del original.

        Un PASS que no puede fallar no es informacion: es la definicion. Se dice, para
        que un semaforo verde no se lea como evidencia.
        """
        from shmir_design.controles import GC_NO_DISCRIMINA

        self.assertIn("composici", GC_NO_DISCRIMINA.lower())
        for control in self.candidatos:
            self.assertIn(GC_NO_DISCRIMINA, estados_motivo(control, "GC"))

    def test_la_asimetria_es_la_que_SI_discrimina(self):
        """Y va con la del original al lado: lo que se busca es PARECERSE, no maximizar."""
        for control in self.candidatos:
            self.assertIsNotNone(control.asymmetry)
            self.assertIsNotNone(control.asymmetry_origin)

    @unittest.skipUnless(HAY_MADUROS, "falta mature.fa")
    def test_con_maduros_corre_el_NUCLEO_y_la_capa_ampliada_sigue_NOT_RUN(self):
        """Y esa distincion es la que el control necesita que se vea.

        El nucleo va en codigo y corre siempre que haya maduros; la capa AMPLIADA
        necesita la lista de abundancia con su referencia y su umbral. Sin ella el
        frente sigue en NOT_RUN — que no es PASS — aunque el nucleo haya corrido limpio.
        Dar el frente por cerrado porque «el nucleo no dio nada» seria exactamente el
        control aprobado a medias.
        """
        from shmir_design.controles import scrambled_candidates

        candidatos = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            mature=_maduros(), wanted=2,
        )
        for control in candidatos:
            estados = {f.name: f.state for f in control.filters}
            self.assertEqual(estados["seed_colision"], FilterState.NOT_RUN)
            motivo = estados_motivo(control, "seed_colision")
            self.assertIn("NÚCLEO", motivo)
            self.assertIn("ampliada", motivo)


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestUnControlAprobadoAmediasEsPEORqueNinguno(unittest.TestCase):
    """El veredicto no puede salir PASS con frentes sin correr. Y se dice cuales."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import scrambled_candidates

        cls.control = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=1,
        )[0]

    def test_el_veredicto_es_INCOMPLETE(self):
        self.assertEqual(self.control.verdict.value, "INCOMPLETE")

    def test_los_NOT_RUN_salen_NOMBRADOS(self):
        self.assertIn("especificidad", self.control.not_run_names)

    def test_y_hay_una_frase_que_lo_dice_con_esas_palabras(self):
        from shmir_design.controles import APROBADO_A_MEDIAS

        self.assertIn("medias", APROBADO_A_MEDIAS.lower())
        self.assertIn(APROBADO_A_MEDIAS, self.control.render())

    def test_la_ficha_nombra_los_frentes_sin_correr(self):
        texto = self.control.render()
        for nombre in self.control.not_run_names:
            self.assertIn(nombre, texto)


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestLaAppNOelige(unittest.TestCase):

    def test_no_hay_ninguna_funcion_que_elija_un_scrambled(self):
        from shmir_design import controles

        for prohibido in ("best_scrambled", "choose_scrambled", "mejor_scrambled"):
            self.assertFalse(hasattr(controles, prohibido), prohibido)

    def test_el_orden_NO_es_un_ranking_y_se_dice(self):
        from shmir_design.controles import ORDEN_NO_ES_RANKING

        self.assertIn("no es un ranking", ORDEN_NO_ES_RANKING.lower())


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestElSeedMismatchSOLOtocaLaSeed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import seed_mismatch_candidates

        cls.dos = seed_mismatch_candidates(
            GUIA, origin_label=ORIGEN, changes=2, target=_utr3(),
            target_label="3'UTR de Prnp", wanted=5,
        )

    def test_fuera_de_la_seed_no_se_toca_ni_una_base(self):
        for control in self.dos:
            self.assertEqual(control.guide[:SEED_START - 1], GUIA[:SEED_START - 1])
            self.assertEqual(control.guide[SEED_END:], GUIA[SEED_END:])

    def test_se_cambian_EXACTAMENTE_los_pedidos(self):
        for control in self.dos:
            distintas = [
                i for i, (a, b) in enumerate(zip(GUIA, control.guide, strict=True))
                if a != b
            ]
            self.assertEqual(len(distintas), 2)
            self.assertEqual(len(control.changes), 2)

    def test_las_posiciones_van_en_la_salida_y_son_1_based(self):
        for control in self.dos:
            for posicion in control.changes:
                self.assertTrue(SEED_START <= posicion <= SEED_END, posicion)

    def test_emite_el_heptamero_VIEJO_y_el_NUEVO(self):
        for control in self.dos:
            self.assertEqual(control.heptamer_origin, GUIA[SEED_START - 1 : SEED_END])
            self.assertNotEqual(control.heptamer, control.heptamer_origin)

    def test_la_pasajera_se_RECALCULA_con_la_regla_del_andamio(self):
        from shmir_design.scaffold import passenger_from_guide

        original = passenger_from_guide(GUIA).sequence
        for control in self.dos:
            self.assertEqual(
                control.passenger, passenger_from_guide(control.guide).sequence
            )
            self.assertNotEqual(control.passenger, original)

    def test_la_horquilla_se_conserva(self):
        for control in self.dos:
            estados = {f.name: f.state for f in control.filters}
            self.assertIn(estados["plegado"], {FilterState.PASS, FilterState.NOT_RUN})

    def test_emite_la_RACHA_INTACTA_de_la_seed(self):
        """Lo que decide entre 2 y 3 no es el numero de cambios: es DONDE caen."""
        for control in self.dos:
            self.assertGreaterEqual(control.intact_run, 1)
            self.assertLessEqual(control.intact_run, SEED_END - SEED_START + 1)


@unittest.skipUnless(HAY_UTR3 and HAY_MADUROS, "faltan el 3'UTR o mature.fa")
class TestElHeptameroNuevoNOchocaConElNUCLEO(unittest.TestCase):
    """Si el mismatch crea una seed de miR-124, el control es peor que el original."""

    def test_ninguno_de_los_emitidos_choca(self):
        from shmir_design.controles import seed_mismatch_candidates
        from shmir_design.mirna import core_hits

        maduros = _maduros()
        for k in (2, 3):
            for control in seed_mismatch_candidates(
                GUIA, origin_label=ORIGEN, changes=k, target=_utr3(),
                target_label="3'UTR de Prnp", mature=maduros, wanted=5,
            ):
                self.assertEqual(
                    core_hits(maduros.names_for(control.heptamer), species="mouse"), ()
                )

    def test_y_con_k_3_hay_variantes_que_SI_chocan_o_sea_que_el_filtro_MUERDE(self):
        """Control adversario del filtro: si no rechazara ninguna, no probaria nada."""
        from shmir_design.controles import seed_mismatch_variants
        from shmir_design.mirna import core_hits

        maduros = _maduros()
        chocan = [
            guia for guia in seed_mismatch_variants(GUIA, changes=3)
            if core_hits(maduros.names_for(guia[SEED_START - 1 : SEED_END]),
                         species="mouse")
        ]
        self.assertTrue(chocan, "con k=3 tiene que haber alguna que choque")


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestSeEmitenLasDOSversiones(unittest.TestCase):
    """2 o 3 cambios es una decision del responsable, y se decide con la tabla."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import mismatch_comparison

        cls.tabla = mismatch_comparison(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
        )

    def test_estan_las_dos(self):
        self.assertEqual([fila["cambios"] for fila in self.tabla], [2, 3])

    def test_cada_una_con_sus_metricas(self):
        for fila in self.tabla:
            for columna in ("variantes", "limpias", "racha_minima", "chocan_nucleo"):
                self.assertIn(columna, fila)

    def test_la_app_NO_decide_entre_las_dos(self):
        from shmir_design.controles import CUANTOS_CAMBIOS_SIN_DECIDIR

        self.assertIn("no se elige", CUANTOS_CAMBIOS_SIN_DECIDIR.lower())

    def test_con_2_la_racha_minima_es_PEOR_que_con_3(self):
        """El residuo de reconocimiento medido, que es lo que hace falta para decidir."""
        dos, tres = self.tabla
        self.assertGreater(dos["racha_minima"], tres["racha_minima"])


class TestElPLEGADOnoDISCRIMINAyEsoVaDICHO(unittest.TestCase):
    """Hallazgo medido: la notacion punto-parentesis del 97-mero no separa nada.

    `passenger_from_guide` ELIGE la base de la posicion 1 para que el 97-mero reproduzca
    la estructura de SGEP, y ABORTA si ninguna lo consigue. O sea que la comprobacion
    posterior vuelve a preguntar algo que ya es condicion para haber montado la
    horquilla. Medido: 0 de 2000 permutaciones y 0 de 1134 variantes de seed dan una
    estructura distinta — y tampoco la da una guia DERIVADA del propio andamio para que
    compita con el loop.
    """

    def test_hay_una_constante_que_lo_dice(self):
        from shmir_design.controles import PLEGADO_NO_DISCRIMINA

        self.assertIn("no discrimina", PLEGADO_NO_DISCRIMINA.lower())

    def test_y_dice_QUE_es_lo_que_si_discrimina(self):
        from shmir_design.controles import PLEGADO_NO_DISCRIMINA

        self.assertIn("asimetr", PLEGADO_NO_DISCRIMINA.lower())

    def test_el_control_adversario_esta_DERIVADO_del_andamio_no_inventado(self):
        from shmir_design.controles import adversarial_guide
        from shmir_design.scaffold import SGEP_SCAFFOLD

        guia = adversarial_guide()
        self.assertEqual(len(guia), 22)
        # Sale del loop del andamio, no de la nada: es la regla 1.
        from shmir_design.scaffold import reverse_complement

        self.assertIn(reverse_complement(guia)[:19], SGEP_SCAFFOLD.loop + SGEP_SCAFFOLD.flank3)


class TestLosSEISbrazos(unittest.TestCase):
    """Aviso, no impedimento — como el del nucleo compartido."""

    def test_son_seis_y_estan_los_seis(self):
        from shmir_design.controles import ARMS

        self.assertEqual(len(ARMS), 6)
        self.assertEqual(
            {a.key for a in ARMS},
            {"vehiculo", "shmir_scrambled", "shmir_seed_mismatch", "shmir_only",
             "dn_only", "completa"},
        )

    def test_cada_brazo_dice_QUE_AISLA(self):
        from shmir_design.controles import ARMS

        for brazo in ARMS:
            self.assertTrue(brazo.isolates.strip(), brazo.key)

    def test_falta_uno_y_sale_AVISO(self):
        from shmir_design.controles import missing_arms

        faltan = missing_arms({"vehiculo", "completa"})
        self.assertEqual(len(faltan), 4)

    def test_el_aviso_NO_impide(self):
        from shmir_design.controles import arms_warning

        aviso = arms_warning({"vehiculo", "completa"})
        self.assertTrue(aviso["rojo"])
        self.assertNotIn("bloquea", aviso)
        self.assertIn("shmir_only", aviso["texto"])

    def test_con_los_seis_no_hay_aviso(self):
        from shmir_design.controles import ARMS, arms_warning

        self.assertIsNone(arms_warning({a.key for a in ARMS}))

    def test_scrambled_y_seed_mismatch_NO_son_intercambiables_y_se_dice(self):
        """Controlan cosas distintas; quedarse con uno deja viva una explicacion."""
        from shmir_design.controles import LOS_DOS_NO_SE_SUSTITUYEN

        texto = LOS_DOS_NO_SE_SUSTITUYEN.lower()
        self.assertIn("scrambled", texto)
        self.assertIn("seed", texto)


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestLaFICHAdeUnControl(unittest.TestCase):
    """Un control sin veredictos no es un control, es una secuencia."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import scrambled_candidates

        cls.control = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=1,
        )[0]
        cls.texto = cls.control.render()

    def test_lleva_su_PROCEDENCIA_de_que_candidato_sale(self):
        self.assertIn(ORIGEN, self.texto)

    def test_lleva_la_marca_de_GENERADA(self):
        from shmir_design.controles import GENERATED_MARK

        self.assertIn(GENERATED_MARK, self.texto)

    def test_lleva_un_estado_POR_FRENTE(self):
        nombres = {f.name for f in self.control.filters}
        for esperado in ("GC", "homopolimero", "asimetria", "plegado",
                         "sin_diana", "especificidad", "seed_colision"):
            self.assertIn(esperado, nombres)

    def test_y_la_horquilla_montada(self):
        self.assertIn(self.control.hairpin, self.texto)
        self.assertEqual(len(self.control.hairpin), 97)


class TestLaAUTORIZACION(unittest.TestCase):
    """La regla 1 prohibe generar secuencia. Aqui hay excepcion, y va acotada."""

    def test_esta_escrita_y_dice_QUE_cubre(self):
        from shmir_design.controles import AUTHORIZATION

        texto = AUTHORIZATION.lower()
        self.assertIn("permutaci", texto)
        self.assertIn("2-8", AUTHORIZATION)

    def test_y_dice_QUE_NO_cubre(self):
        from shmir_design.controles import AUTHORIZATION

        texto = AUTHORIZATION.lower()
        self.assertIn("no cubre", texto)
        self.assertIn("andamio", texto)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(
    HAY_UTR3 and hay_fichero(reference_dir() / "aav_casete.fa"),
    "faltan el 3'UTR o el casete AAV",
)
class TestElCASETEsiSeCarga(unittest.TestCase):
    """Un control con diana dentro de la construcción terapéutica la apagaría."""

    def test_con_el_casete_el_frente_del_transgen_CORRE(self):
        from shmir_design.controles import scrambled_candidates
        from shmir_design.specificity import load_database

        casete = load_database(
            reference_dir() / "aav_casete.fa", name="casete del transgén",
            version="fixture del repositorio",
        )
        for control in scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            transgene_db=casete, wanted=2,
        ):
            estados = {f.name: f.state for f in control.filters}
            self.assertEqual(estados["transgen"], FilterState.PASS)

    def test_y_sin_el_sigue_NOT_RUN(self):
        from shmir_design.controles import scrambled_candidates

        control = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=1,
        )[0]
        estados = {f.name: f.state for f in control.filters}
        self.assertEqual(estados["transgen"], FilterState.NOT_RUN)


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestLaFilaNOsePISAaSiMisma(unittest.TestCase):
    """Un filtro con el nombre de una métrica se la come, y no da ningún error.

    Pasó: `asimetria` era a la vez el número en kcal/mol —el que se compara con el del
    original— y el estado del filtro. La fila salía con «PASS» donde tenía que ir el
    valor. Misma familia que la tabla descuadrada de `Block.__post_init__`.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import scrambled_candidates

        cls.control = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=1,
        )[0]

    def test_el_numero_de_asimetria_SOBREVIVE_a_la_fila(self):
        fila = self.control.row()
        self.assertIsInstance(fila["asimetria_kcal"], float)
        self.assertIsInstance(fila["asimetria_kcal_original"], float)
        self.assertEqual(fila["asimetria"], "PASS")

    def test_y_hay_una_columna_por_filtro_sin_perder_ninguna(self):
        fila = self.control.row()
        for filtro in self.control.filters:
            self.assertIn(filtro.name, fila)
        self.assertEqual(
            len({f.name for f in self.control.filters}), len(self.control.filters)
        )


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestLaEQUIVALENCIAesOtraPreguntaQueElFILTRO(unittest.TestCase):
    """Pasar el filtro de asimetría no es procesarse como el original.

    Medido: la mediana de las permutaciones de `3utr:1018` es 0,67 y el original está
    en 7,65. Casi todas PASAN el umbral del pipeline —que dice si la hebra se carga— y
    están a 6 o 7 kcal/mol. Un control así pasa todo y se procesa de otra manera, con lo
    que la comparación deja de medir la diana.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.controles import _biophysical, scrambled_candidates

        cls.original = _biophysical(GUIA)[1]
        cls.candidatos = scrambled_candidates(
            GUIA, origin_label=ORIGEN, target=_utr3(), target_label="3'UTR de Prnp",
            wanted=3,
        )

    def test_los_emitidos_estan_DENTRO_de_la_tolerancia(self):
        from shmir_design.controles import MAX_DELTA_ASIMETRIA

        for control in self.candidatos:
            self.assertLessEqual(
                abs(control.asymmetry - self.original), MAX_DELTA_ASIMETRIA
            )

    def test_y_lleva_su_propio_frente_para_que_se_vea(self):
        for control in self.candidatos:
            estados = {f.name: f.state for f in control.filters}
            self.assertEqual(
                estados["equivalencia_asimetria"], FilterState.PASS
            )

    def test_EL_CRITERIO_MUERDE_la_mayoria_de_permutaciones_lo_incumplen(self):
        """Control adversario: si no rechazara casi nada, no estaria haciendo nada."""
        from shmir_design.controles import (MAX_DELTA_ASIMETRIA, _biophysical,
                                            scrambled_permutations)

        lejos = cerca = 0
        for guia in scrambled_permutations(GUIA, draws=500):
            if abs(_biophysical(guia)[1] - self.original) > MAX_DELTA_ASIMETRIA:
                lejos += 1
            else:
                cerca += 1
        self.assertGreater(lejos, cerca * 5, f"cerca={cerca} lejos={lejos}")

    def test_y_el_umbral_del_pipeline_NO_habria_bastado(self):
        """Casi todas las que estan lejos del original SI pasan el minimo del pipeline."""
        from shmir_design.hard_filters import DEFAULT_THRESHOLDS
        from shmir_design.controles import MAX_DELTA_ASIMETRIA

        self.assertLess(DEFAULT_THRESHOLDS.min_asymmetry, MAX_DELTA_ASIMETRIA)
        self.assertGreater(self.original, DEFAULT_THRESHOLDS.min_asymmetry * 5)


@unittest.skipUnless(
    hay_fichero(reference_dir() / "aav_casete.fa"), "falta el casete AAV"
)
class TestElCASETEqueLaPaginaLEE(unittest.TestCase):
    """Regresión: `_casete_de` hacía `records[0].sequence` sobre un `dict[str, str]`.

    La rama nunca había corrido —el casete no se había conectado nunca en la página—,
    así que el `KeyError: 0` esperaba a que alguien subiera el fichero. Es la errata
    nº 31 otra vez: una combinación que ningún test recorre de punta a punta no está
    probada. Ahora la decisión vive en `presentation` (regla 6) y tiene este test.
    """

    def test_devuelve_la_SECUENCIA_del_casete(self):
        from shmir_design.presentation import cassette_sequence
        from shmir_design.specificity import load_database

        class _Tiling:
            transgene_db = load_database(
                reference_dir() / "aav_casete.fa", name="casete", version="fixture",
            )

        secuencia = cassette_sequence(_Tiling())
        self.assertIsInstance(secuencia, str)
        self.assertGreater(len(secuencia), 5000)
        self.assertEqual(set(secuencia) - set("ACGTN"), set())

    def test_sin_casete_devuelve_None_y_no_revienta(self):
        from shmir_design.presentation import cassette_sequence

        class _Sin:
            transgene_db = None

        self.assertIsNone(cassette_sequence(_Sin()))
        self.assertIsNone(cassette_sequence(object()))

    def test_con_VARIOS_registros_ABORTA_en_vez_de_elegir_uno(self):
        from shmir_design.errors import ShmirDesignError
        from shmir_design.presentation import cassette_sequence
        from shmir_design.specificity import load_database

        base = load_database(
            reference_dir() / "aav_casete.fa", name="casete", version="fixture",
        )

        class _Dos:
            transgene_db = type(base)(
                name=base.name, version=base.version, checksum=base.checksum,
                # El SEGUNDO registro es una copia del real con otro nombre: no hay
                # ninguna secuencia inventada aqui, sólo el mismo casete dos veces.
                records={**base.records,
                         "copia": next(iter(base.records.values()))},
            )

        with self.assertRaises(ShmirDesignError):
            cassette_sequence(_Dos())


@unittest.skipUnless(HAY_UTR3, "falta el fixture del 3'UTR murino")
class TestElGCesINVARIANTEyPorEsoSeDEMUESTRA(unittest.TestCase):
    """`3utr:449` no admite scrambled, y eso se prueba en un paso y no en 4000 sorteos.

    La permutación conserva la composición, así que el GC es invariante: si el original
    no pasa el filtro, ninguna permutación lo pasará nunca. Descubrirlo sorteando daría
    un cero que se lee como una medida.

    Y la CAUSA importa tanto como el hecho: los umbrales biofísicos están definidos sobre
    la DIANA, y una guía no es su diana — difieren en la posición 1, que es convenio. La
    guía de `3utr:449` empezaba por G y al forzarse la T su GC baja de 0,318 a 0,273. El
    candidato es legítimo; lo que no admite es un scrambled por permutación.
    """

    #: La guía de `3utr:449`, en ADN. `test_es_la_del_panel` la contrasta.
    GUIA_449 = "TTTAGTAAAGAAAGAATTCCAC"

    def test_es_la_del_panel(self):
        from shmir_design.hard_filters import guide_from_target

        utr3 = _utr3()
        diana = utr3[449 - 1 : 449 - 1 + 22]
        self.assertEqual(guide_from_target(diana).replace("U", "T"), self.GUIA_449)

    def test_la_diana_PASA_el_GC_y_la_guia_NO(self):
        from shmir_design.hard_filters import gc_fraction

        utr3 = _utr3()
        diana = utr3[449 - 1 : 449 - 1 + 22]
        self.assertGreater(gc_fraction(diana), gc_fraction(self.GUIA_449))
        self.assertGreaterEqual(gc_fraction(diana), 0.30)
        self.assertLess(gc_fraction(self.GUIA_449), 0.30)

    def test_y_la_diferencia_es_EXACTAMENTE_la_posicion_de_convenio(self):
        from shmir_design.controles import reverse_complement

        utr3 = _utr3()
        diana = utr3[449 - 1 : 449 - 1 + 22]
        virtual = reverse_complement(self.GUIA_449)
        distintas = [
            i for i, (a, b) in enumerate(zip(diana, virtual, strict=True)) if a != b
        ]
        self.assertEqual(distintas, [len(diana) - 1])

    def test_ABORTA_diciendo_que_es_imposible_y_no_devuelve_una_lista_vacia(self):
        from shmir_design.controles import (GC_ES_INVARIANTE, GUIA_NO_ES_DIANA,
                                            scrambled_candidates)
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError) as caja:
            scrambled_candidates(
                self.GUIA_449, origin_label="3utr:449", target=_utr3(),
                target_label="3'UTR de Prnp", wanted=5,
            )
        mensaje = str(caja.exception)
        self.assertIn(GC_ES_INVARIANTE, mensaje)
        self.assertIn(GUIA_NO_ES_DIANA, mensaje)

    def test_y_el_seed_mismatch_de_449_SI_se_puede_porque_cambia_la_composicion(self):
        """No es el candidato el que no admite controles: es esta VÍA la que no puede."""
        from shmir_design.controles import seed_mismatch_candidates

        salen = seed_mismatch_candidates(
            self.GUIA_449, origin_label="3utr:449", changes=2, target=_utr3(),
            target_label="3'UTR de Prnp", wanted=3,
        )
        self.assertEqual(len(salen), 3)
