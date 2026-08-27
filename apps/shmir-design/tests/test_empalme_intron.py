"""El empalme del intron MVM: el quinto frente, y el unico BINARIO.

Regla 5: escritos antes.

Es el unico fallo del diseño que es catastrofico y no gradual. Si el intron no se
escinde, la horquilla se queda dentro del mRNA maduro, **en el 5'UTR**, y no hay proteina
DN en absoluto. No hay «un poco de proteina»: la lectura de exito es dicotomica y decide
si la arquitectura intronica sigue viva.

Y las lecturas que ya habia NO lo cogen. `small RNA-seq` puede salir perfecto con el
empalme fallando: Drosha procesa el pri-miR **cotranscripcionalmente**, antes del
splicing, asi que un shmiR correcto no es evidencia de que haya proteina. Son dos sucesos
en orden y solo se mide el primero.

Lo que se comprueba aqui no es la biologia, es que el codigo no se invente NADA:

  - el intron se LOCALIZA sobre el plasmido buscando las piezas de `blocks.PIECES`, no
    con coordenadas tecleadas;
  - los dinucleotidos GT/AG se LEEN de la secuencia y se comprueban;
  - las ventanas de cebador se derivan de la union, y se comprueba que sean UNICAS en el
    plasmido — un cebador que aparece dos veces no mide nada;
  - no se emite ni un cebador: se emiten VENTANAS donde buscarlos, igual que en
    `polya.rtqpcr_amplicons`. Tm, especificidad y horquillas no se improvisan.
"""

import unittest
from pathlib import Path

from shmir_design import splicing
from shmir_design.blocks import INTRON_LENGTH, PIECES
from shmir_design.filters import FilterState

CASETE = Path(__file__).resolve().parent.parent / "data" / "reference" / "aav_casete.fa"


def _plasmido() -> str:
    raw = CASETE.read_text(encoding="utf-8")
    return "".join(
        l.strip() for l in raw.splitlines() if not l.startswith(">")
    ).upper()


class TestLoQueSeDeclara(unittest.TestCase):
    """El encuadre va escrito, porque es lo que decide como se lee el resultado."""

    def test_es_un_riesgo_BINARIO_y_lo_dice_con_esa_palabra(self):
        texto = splicing.BINARY_NOT_GRADUAL.upper()
        self.assertIn("BINARIO", texto)
        self.assertIn("NO ES UN PARÁMETRO DE CALIDAD", texto)

    def test_dice_que_decide_la_ARQUITECTURA_no_un_candidato(self):
        self.assertIn("arquitectura", splicing.BINARY_NOT_GRADUAL.lower())

    def test_explica_por_que_el_small_RNA_seq_NO_lo_cubre(self):
        texto = splicing.WHY_SMALL_RNA_SEQ_MISSES_IT
        self.assertIn("Drosha", texto)
        self.assertIn("cotranscripcional", texto.lower())
        self.assertIn("antes", texto.lower())

    def test_y_lo_dice_con_la_frase_que_importa(self):
        self.assertIn(
            "no es evidencia", splicing.WHY_SMALL_RNA_SEQ_MISSES_IT.lower()
        )


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLocalizarElIntron(unittest.TestCase):

    def setUp(self):
        self.sitio = splicing.locate_intron(_plasmido(), name="aav_casete.fa")

    def test_el_donante_esta_en_3134(self):
        self.assertEqual(self.sitio.donor_start, 3134)

    def test_el_aceptor_acaba_en_3215(self):
        self.assertEqual(self.sitio.acceptor_end, 3215)

    def test_los_dinucleotidos_se_LEEN_y_son_GT_AG(self):
        self.assertEqual(self.sitio.donor, "GT")
        self.assertEqual(self.sitio.acceptor, "AG")

    def test_el_intron_del_PARENTAL_mide_82_nt_y_esta_VACIO(self):
        # MVM5 (40) + MVM3 (42), sin espaciadores ni modulo entre medias.
        self.assertEqual(self.sitio.length, 82)
        self.assertTrue(self.sitio.empty)
        self.assertEqual(
            self.sitio.length,
            len(PIECES["MVM5"].sequence) + len(PIECES["MVM3"].sequence),
        )

    def test_el_TERAPEUTICO_mide_296_y_por_eso_NO_son_el_mismo_intron(self):
        self.assertEqual(INTRON_LENGTH, 296)
        self.assertNotEqual(self.sitio.length, INTRON_LENGTH)

    def test_si_las_piezas_no_estan_ABORTA_y_no_devuelve_None(self):
        with self.assertRaises(Exception) as ctx:
            splicing.locate_intron("ACGT" * 50, name="inventado")
        self.assertIn("MVM", str(ctx.exception))

    def test_si_el_aceptor_va_ANTES_que_el_donante_ABORTA(self):
        alreves = PIECES["MVM3"].sequence + ("ACGT" * 10) + PIECES["MVM5"].sequence
        with self.assertRaises(Exception):
            splicing.locate_intron(alreves, name="invertido")


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElIntronCaeEnEl5UTR(unittest.TestCase):
    """No se da por bueno que la horquilla retenida quede en el 5'UTR: se comprueba."""

    def setUp(self):
        self.plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")

    def test_el_ATG_del_ORF_esta_POR_DETRAS_del_aceptor(self):
        self.assertGreater(self.plan.orf_start, self.plan.location.acceptor_end)

    def test_y_a_37_nt(self):
        self.assertEqual(self.plan.orf_start, 3253)
        self.assertEqual(self.plan.utr5_after_acceptor, 37)

    def test_el_ORF_es_PrP_con_las_DOS_mutaciones_del_nombre(self):
        # Comprobacion de identidad del constructo por traduccion, no por el nombre del
        # fichero: G130E y W144Y son las que anuncia pAAV_G130E_W144Y.
        self.assertEqual(self.plan.protein_length, 254)
        self.assertTrue(self.plan.protein.startswith("MANLGYWLLALFVTMW"))
        self.assertEqual(self.plan.protein[129], "E")
        self.assertEqual(self.plan.protein[143], "Y")

    def test_un_intron_retenido_mete_296_nt_DELANTE_del_codon_de_inicio(self):
        self.assertEqual(self.plan.retained_insert, INTRON_LENGTH)

    def test_y_ese_tramo_trae_uATG_que_es_el_mecanismo_concreto(self):
        # Cinco en las piezas FIJAS del intron; la horquilla puede añadir mas.
        self.assertGreaterEqual(self.plan.upstream_atgs, 5)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLasVentanasDeCebador(unittest.TestCase):

    def setUp(self):
        self.plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")

    def test_la_de_aguas_arriba_va_3064_3123(self):
        self.assertEqual(
            (self.plan.upstream.start, self.plan.upstream.end), (3064, 3123)
        )

    def test_la_de_aguas_abajo_va_3226_3285(self):
        self.assertEqual(
            (self.plan.downstream.start, self.plan.downstream.end), (3226, 3285)
        )

    def test_NINGUNA_toca_la_union_ni_el_intron(self):
        sitio = self.plan.location
        self.assertLess(self.plan.upstream.end, sitio.donor_start)
        self.assertGreater(self.plan.downstream.start, sitio.acceptor_end)

    def test_y_guardan_el_MARGEN_declarado(self):
        sitio = self.plan.location
        self.assertEqual(
            sitio.donor_start - self.plan.upstream.end - 1, splicing.JUNCTION_MARGIN
        )
        self.assertEqual(
            self.plan.downstream.start - sitio.acceptor_end - 1,
            splicing.JUNCTION_MARGIN,
        )

    def test_un_cebador_que_cruce_la_union_NO_vale_y_se_dice_por_que(self):
        # Solo amplificaria la forma empalmada, asi que no puede dar una PROPORCION.
        self.assertIn("proporción", splicing.WHY_NOT_JUNCTION_SPANNING.lower())

    def test_las_DOS_ventanas_son_UNICAS_en_el_plasmido(self):
        self.assertEqual(self.plan.upstream.occurrences, 1)
        self.assertEqual(self.plan.downstream.occurrences, 1)
        self.assertTrue(self.plan.upstream.usable)
        self.assertTrue(self.plan.downstream.usable)

    def test_no_se_emite_NI_UN_cebador(self):
        texto = "\n".join(self.plan.describe())
        for pieza in ("MVM5", "MVM3"):
            self.assertNotIn(PIECES[pieza].sequence, texto)
        self.assertIn("no se emiten cebadores", texto.lower())


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLasBandas(unittest.TestCase):

    def setUp(self):
        self.plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")

    def test_la_DIFERENCIA_es_exacta_y_no_depende_del_cebador(self):
        # Es la unica cifra que no depende de donde caiga el cebador dentro de su
        # ventana, y es justo la que se lee en el gel.
        self.assertEqual(self.plan.difference, INTRON_LENGTH)

    def test_la_del_parental_es_su_propio_intron_de_82(self):
        self.assertEqual(self.plan.parental_difference, 82)

    def test_banda_corta_igual_a_empalmado_banda_larga_igual_a_retenido(self):
        bajo, alto = self.plan.spliced_range
        rbajo, ralto = self.plan.retained_range
        self.assertEqual(rbajo - bajo, INTRON_LENGTH)
        self.assertEqual(ralto - alto, INTRON_LENGTH)
        self.assertLess(alto, rbajo)

    def test_las_bandas_se_dan_como_RANGO_porque_el_cebador_no_esta_puesto(self):
        bajo, alto = self.plan.spliced_range
        self.assertLess(bajo, alto)

    def test_el_texto_dice_cual_es_cual(self):
        texto = "\n".join(self.plan.describe()).lower()
        self.assertIn("banda corta", texto)
        self.assertIn("banda larga", texto)
        self.assertIn("eficiencia", texto)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLaEspecificidadDeVector(unittest.TestCase):
    """El par tiene que ser especifico del vector, y solo un lado lo garantiza."""

    def setUp(self):
        self.plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")

    def test_la_ventana_de_aguas_abajo_cae_DENTRO_del_ORF_de_PrP(self):
        self.assertGreaterEqual(self.plan.downstream.end, self.plan.orf_start)

    def test_asi_que_el_cebador_de_aguas_ARRIBA_es_el_que_da_la_especificidad(self):
        texto = self.plan.describe()
        self.assertTrue(
            any("endogeno" in l.lower() for l in texto),
            "hay que avisar de que un par entero dentro de PrP amplificaria el endogeno",
        )


class TestLasTresLecturas(unittest.TestCase):

    def setUp(self):
        self.lecturas = {l.name: l for l in splicing.splicing_readouts()}

    def test_son_CUATRO(self):
        # La cuarta —secuenciar la union— es la que de verdad cierra el frente: sin
        # ella, la presencia de la banda corta no descarta el donante criptico.
        self.assertEqual(len(self.lecturas), 4)

    def test_y_se_llaman_asi(self):
        self.assertEqual(
            sorted(self.lecturas),
            [
                "parental_sin_intron", "rtpcr_empalme", "secuencia_union_exon_exon",
                "western_L42_por_vg",
            ],
        )

    def test_TODAS_salen_NOT_RUN_porque_ninguna_la_corre_el_software(self):
        for nombre, lectura in self.lecturas.items():
            self.assertIs(lectura.state, FilterState.NOT_RUN, nombre)

    def test_el_western_separa_NO_EMPALMO_de_NO_LLEGO_EL_VECTOR(self):
        motivo = self.lecturas["western_L42_por_vg"].requirement
        self.assertIn("vg-qPCR", motivo)
        self.assertIn("no llego el vector", motivo.lower())

    def test_el_parental_sin_intron_es_un_TECHO_de_expresion(self):
        motivo = self.lecturas["parental_sin_intron"].requirement
        self.assertIn("techo", motivo.lower())
        self.assertIn("misma tanda", motivo.lower())

    def test_y_AVISA_de_que_el_casete_que_hay_NO_es_ese(self):
        # `aav_casete.fa` es el parental SIN MODULO, pero CON el intron vacio de 82 nt.
        # Cogerlo por el parental sin intron daria un techo que no es un techo.
        motivo = self.lecturas["parental_sin_intron"].requirement
        self.assertIn("82", motivo)
        self.assertIn("aav_casete.fa", motivo)


class TestElQuintoFrente(unittest.TestCase):

    def test_el_frente_existe_y_se_llama_empalme_intron(self):
        frente = splicing.splicing_front()
        self.assertEqual(frente.name, "empalme_intron")

    def test_BLOQUEA_y_el_software_no_puede_cerrarlo(self):
        self.assertTrue(splicing.splicing_front().blocking)

    def test_su_motivo_trae_las_TRES_lecturas(self):
        motivo = splicing.splicing_front().reason
        for pieza in ("RT-PCR", "L42", "vg-qPCR", "SIN INTRÓN"):
            self.assertIn(pieza, motivo)

    def test_y_el_argumento_de_por_que_no_estaba_en_la_lista(self):
        motivo = splicing.splicing_front().reason
        self.assertIn("Drosha", motivo)


if __name__ == "__main__":
    unittest.main()


class TestElPlanSaleDeLaBaseDelTransgen(unittest.TestCase):
    """El casete ya viaja en el informe (`transgene_db`): no hace falta pasarlo aparte."""

    def test_sin_base_no_hay_plan_pero_TAMPOCO_excepcion(self):
        plan, motivo = splicing.plan_from_records(None)
        self.assertIsNone(plan)
        self.assertIn("--transgen", motivo)

    def test_una_base_SIN_el_intron_da_motivo_concreto_y_no_revienta(self):
        plan, motivo = splicing.plan_from_records({"cualquiera": "ACGT" * 100})
        self.assertIsNone(plan)
        self.assertIn("MVM", motivo)

    @unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta aav_casete.fa")
    def test_con_el_casete_de_verdad_SI_hay_plan(self):
        plan, motivo = splicing.plan_from_records({"aav_casete.fa": _plasmido()})
        self.assertIsNotNone(plan)
        self.assertEqual(plan.location.donor_start, 3134)
        self.assertEqual(motivo, "")


class TestElFrenteEntraEnLaLista(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.reference import REFERENCES, load_3utr, fixture_available
        from shmir_design.selection import SelectionConfig, blocking_fronts, select_from_report
        from shmir_design.tiling import tile_utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            raise unittest.SkipTest("falta data/reference/NM_011170.3.fa")
        informe = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
        cls.frentes = blocking_fronts(
            informe, select_from_report(informe, SelectionConfig(n_candidates=10))
        )

    def test_empalme_intron_esta_entre_los_frentes(self):
        self.assertIn("empalme_intron", [f.name for f in self.frentes])

    def test_y_BLOQUEA(self):
        frente = next(f for f in self.frentes if f.name == "empalme_intron")
        self.assertTrue(frente.blocking)

    def test_sale_aunque_no_haya_casete_cargado(self):
        # Es un riesgo de la ARQUITECTURA, no de un fichero: no aparece y desaparece
        # segun lo que se haya pasado por la linea de ordenes.
        frente = next(f for f in self.frentes if f.name == "empalme_intron")
        self.assertIn("--transgen", frente.reason)


class TestElInformeLoDeclara(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.reference import REFERENCES, load_3utr, fixture_available
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            raise unittest.SkipTest("falta data/reference/NM_011170.3.fa")
        informe = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
        cls.texto = text_report(
            species="raton",
            tiling=informe,
            selection=select_from_report(informe, SelectionConfig(n_candidates=10)),
            scaffold=SGEP_SCAFFOLD,
        )

    def test_hay_un_bloque_propio(self):
        self.assertIn("Empalme del intrón", self.texto)

    def test_lo_declara_BINARIO_y_no_parametro_de_calidad(self):
        self.assertIn("RIESGO BINARIO", self.texto)
        self.assertIn("NO ES UN PARÁMETRO DE CALIDAD", self.texto)

    def test_y_dice_por_que_el_small_RNA_seq_no_lo_cubre(self):
        self.assertIn("Drosha", self.texto)

    def test_las_TRES_lecturas_salen_con_su_estado(self):
        for nombre in ("rtpcr_empalme", "western_L42_por_vg", "parental_sin_intron"):
            self.assertIn(nombre, self.texto)
        self.assertIn("NOT_RUN", self.texto)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestNoSeEmiteUnAmpliconImposible(unittest.TestCase):
    """El extremo bajo del rango NO es una banda: le faltan los dos cebadores.

    Dandolo tal cual salia «banda corta ~22 pb», que es geometricamente imposible: un
    cebador tiene que caber entero dentro de su ventana. Y la salida no se arregla
    inventandose una longitud de cebador — se arregla diciendo la formula.
    """

    def setUp(self):
        self.plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")

    def test_el_extremo_bajo_es_SOLO_los_dos_margenes(self):
        self.assertEqual(self.plan.spliced_range[0], 2 * splicing.JUNCTION_MARGIN)

    def test_y_el_texto_lo_da_como_FORMULA_no_como_banda(self):
        texto = "\n".join(self.plan.describe())
        self.assertIn("+ F + R", texto)
        self.assertIn("longitudes de los dos cebadores", texto)

    def test_no_aparece_ninguna_banda_de_menos_de_50_pb(self):
        for linea in self.plan.describe():
            if "banda" in linea.lower():
                self.assertNotIn("~22", linea)


class TestNoSeCierraConNingunFichero(unittest.TestCase):
    """Los demas frentes se cierran consiguiendo datos. Este no, y el informe lo separa."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.reference import REFERENCES, load_3utr, fixture_available
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            raise unittest.SkipTest("falta data/reference/NM_011170.3.fa")
        informe = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
        cls.texto = text_report(
            species="raton",
            tiling=informe,
            selection=select_from_report(informe, SelectionConfig(n_candidates=10)),
            scaffold=SGEP_SCAFFOLD,
        )

    def test_lo_dice_con_esas_palabras(self):
        self.assertIn("NO SE CIERRA CON NINGÚN FICHERO", self.texto)

    def test_y_que_es_el_unico_BINARIO(self):
        self.assertIn("el único BINARIO", self.texto)

    def test_y_que_los_demas_degradan_y_este_ANULA(self):
        self.assertIn("los demas degradan", self.texto)
        self.assertIn("no hay proteina DN en absoluto", self.texto)


class TestElAvisoNoLlamaCanonicaAUnaVarianteRara(unittest.TestCase):
    """Desde que una variante rara puede ser APA_POSIBLE por medida, «canonica» miente."""

    def test_una_variante_rara_promovida_NO_sale_como_canonica(self):
        from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
        from shmir_design.reference import REFERENCES, load_3utr, fixture_available
        from shmir_design.tiling import tile_utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            self.skipTest("falta data/reference/NM_011170.3.fa")
        utr3 = load_3utr(REFERENCES["NM_011170.3"])
        informe = tile_utr(utr3)
        avisos = [a.message for a in informe.avisos if a.code == "APA_PROXIMAL"]
        rara = next(m for m in avisos if "AATATA" in m)
        self.assertNotIn("AATATA canónica", rara)
        self.assertIn("(medida)", rara)
        canonica = next(m for m in avisos if "AATAAA" in m)
        self.assertIn("AATAAA canónica", canonica)
