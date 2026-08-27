"""`mvm_sin_criptico`: la variante que DISEÑA la app. Dos criterios computables.

Regla 5: escritos antes.

Esto GENERA SECUENCIA, asi que lleva autorizacion escrita y acotada, igual que
`spacers.py`. Y con una diferencia que hay que tener delante: **`GTGAGCG` esta en el
ANDAMIO**, no en los espaciadores — son los ultimos 7 nt de `SGEP_SCAFFOLD.flank5`. Asi
que romperlo NO es tocar un espaciador: muta el andamio verificado contra la publicacion,
y toda construccion que salga de aqui deja de llevar miR-E verificado y sale MARCADA.

Los dos criterios:

  1. **Romper el criptico**: se prueban las cuatro bases en cada posicion que degrade el
     contexto de donante. Se elige la que mas baje la puntuacion del sitio criptico SIN
     alterar el plegado del 97-mero contra SGEP — el mismo criterio estructural que la
     posicion 1 de la pasajera. **Si empatan, NO se elige.**
  2. **Espaciadores de 20-30 nt** entre donante y modulo y entre modulo y punto de
     ramificacion, plegando el intron completo y quedandose con los que dejan los tres
     elementos desapareados.
"""

import unittest

from shmir_design import intron_design, introns
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.splicing import CRYPTIC_DONOR

# Una guia REAL del panel murino, no inventada (regla 1).
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _guia():
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    seleccion = select_from_report(tile_utr(utr3), SelectionConfig(n_candidates=1))
    elegido = seleccion.selection.chosen[0]
    return utr3[elegido.start - 1:elegido.end]


class TestLaAutorizacionVA_ESCRITA(unittest.TestCase):

    def test_existe_y_dice_QUE_cubre(self):
        texto = intron_design.AUTHORIZATION
        self.assertIn("espaciador", texto.lower())
        self.assertIn(CRYPTIC_DONOR, texto)

    def test_y_QUE_NO_cubre(self):
        texto = intron_design.AUTHORIZATION.lower()
        for prohibido in ("guia", "pasajera"):
            self.assertIn(prohibido, texto)

    def test_dice_que_el_criptico_esta_en_el_ANDAMIO_no_en_un_espaciador(self):
        texto = intron_design.AUTHORIZATION
        self.assertIn("andamio", texto.lower())
        self.assertIn("flank5", texto)

    def test_y_que_lo_que_salga_deja_de_ser_miR_E_verificado(self):
        self.assertIn("verificado", intron_design.SCAFFOLD_MODIFIED_MARK.lower())


class TestDondeEstaElCriptico(unittest.TestCase):

    def test_se_LOCALIZA_en_el_andamio_no_se_teclea(self):
        sitio = intron_design.locate_cryptic(SGEP_SCAFFOLD)
        self.assertEqual(sitio.motif, CRYPTIC_DONOR)
        self.assertEqual(SGEP_SCAFFOLD.flank5[sitio.start - 1:sitio.end], CRYPTIC_DONOR)

    def test_y_esta_al_FINAL_del_flanco_5(self):
        sitio = intron_design.locate_cryptic(SGEP_SCAFFOLD)
        self.assertEqual(sitio.end, len(SGEP_SCAFFOLD.flank5))

    def test_un_andamio_SIN_el_criptico_aborta_en_vez_de_dar_por_ausente_el_riesgo(self):
        from dataclasses import replace

        limpio = replace(SGEP_SCAFFOLD, flank5="TGCTGTTGACAGTCTCGA")
        with self.assertRaises(ShmirDesignError):
            intron_design.locate_cryptic(limpio)


class TestRomperElCriptico(unittest.TestCase):

    def test_se_prueban_LAS_CUATRO_bases_en_CADA_posicion(self):
        alternativas = intron_design.break_candidates(SGEP_SCAFFOLD)
        # 7 posiciones x 3 bases distintas de la original.
        self.assertEqual(len(alternativas), len(CRYPTIC_DONOR) * 3)

    def test_cada_una_cambia_UNA_sola_base(self):
        for alt in intron_design.break_candidates(SGEP_SCAFFOLD):
            diferencias = sum(
                1 for a, b in zip(alt.flank5, SGEP_SCAFFOLD.flank5) if a != b
            )
            self.assertEqual(diferencias, 1, alt.flank5)

    def test_y_ninguna_deja_el_motivo_intacto(self):
        for alt in intron_design.break_candidates(SGEP_SCAFFOLD):
            self.assertNotIn(CRYPTIC_DONOR, alt.flank5, alt.flank5)

    def test_cada_alternativa_trae_SU_METRICA_de_degradacion(self):
        for alt in intron_design.break_candidates(SGEP_SCAFFOLD):
            self.assertIsInstance(alt.donor_score, int)

    def test_el_criterio_de_degradacion_va_DECLARADO_no_citado(self):
        texto = intron_design.DONOR_CONTEXT_CRITERION
        self.assertIn("declarado", texto.lower())
        self.assertIn("no es una cita", texto.lower())

    def test_y_dice_que_NO_es_SpliceAI(self):
        """El numero de verdad sale del modal; esto solo GENERA candidatos."""
        self.assertIn("spliceai", intron_design.DONOR_CONTEXT_CRITERION.lower())


@unittest.skipUnless(HAY and VIENNA_AVAILABLE,
                     "NOT_RUN: falta el fixture del raton o ViennaRNA")
class TestLaSegundaMetrica_EL_PLEGADO(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.guia = _guia()
        cls.eleccion = intron_design.choose_break(SGEP_SCAFFOLD, guide=cls.guia)

    def test_cada_alternativa_dice_si_el_97mero_SIGUE_plegando_como_SGEP(self):
        for fila in cls_filas(self.eleccion):
            self.assertIn("plegado_ok", fila)

    def test_una_que_ROMPE_el_plegado_no_puede_elegirse(self):
        elegibles = [f for f in cls_filas(self.eleccion) if f["elegible"]]
        for fila in elegibles:
            self.assertTrue(fila["plegado_ok"], fila)

    def test_si_EMPATAN_no_se_elige(self):
        if self.eleccion.tie:
            self.assertIsNone(self.eleccion.chosen)
            self.assertGreater(len(self.eleccion.tied), 1)

    def test_y_se_dice_que_lo_decide_QUIEN_LEE(self):
        self.assertIn("quien lee", intron_design.TIE_NOTE.lower())

    def test_las_alternativas_salen_TODAS_con_sus_dos_metricas(self):
        filas = cls_filas(self.eleccion)
        self.assertEqual(len(filas), len(CRYPTIC_DONOR) * 3)
        for fila in filas:
            self.assertIn("donor_score", fila)
            self.assertIn("plegado_ok", fila)


def cls_filas(eleccion):
    return eleccion.rows()


@unittest.skipUnless(HAY and VIENNA_AVAILABLE,
                     "NOT_RUN: falta el fixture del raton o ViennaRNA")
class TestLoQueSALE_DE_VERDAD(unittest.TestCase):
    """Medido el 2026-08-26 sobre el andamio SGEP y la guia de `3utr:60`.

    Tres hechos, y los tres importan:

      - de las **21** alternativas, solo **4** conservan el plegado del 97-mero. O sea:
        el criterio estructural es el que manda, no el de degradacion.
      - de esas cuatro, **dos EMPATAN** en degradacion (`GTGCGCG` y `GTGTGCG`, las dos
        en la posicion 4), asi que la app **NO elige**. Es el caso que la regla preve.
      - `GTAAGCG` pliega bien y aun asi NO es elegible, porque hace el contexto de
        donante MAS canonico (consenso 5 frente a 4): romper el motivo no es lo mismo
        que degradarlo, y sin la primera metrica esta se colaria.
    """

    @classmethod
    def setUpClass(cls):
        cls.eleccion = intron_design.choose_break(SGEP_SCAFFOLD, guide=_guia())

    def test_son_VEINTIUNA_alternativas(self):
        self.assertEqual(len(self.eleccion.rows()), 21)

    def test_solo_CUATRO_conservan_el_plegado(self):
        self.assertEqual(sum(1 for f in self.eleccion.rows() if f["plegado_ok"]), 4)

    def test_y_DOS_de_ellas_EMPATAN_asi_que_no_se_elige(self):
        self.assertTrue(self.eleccion.tie)
        self.assertIsNone(self.eleccion.chosen)
        self.assertEqual(
            sorted(c.motif for c in self.eleccion.tied), ["GTGCGCG", "GTGTGCG"]
        )

    def test_GTAAGCG_pliega_bien_y_AUN_ASI_no_es_elegible(self):
        """Hace el contexto MAS canonico. Sin la metrica de degradacion se colaria."""
        fila = next(f for f in self.eleccion.rows() if f["motivo"] == "GTAAGCG")
        self.assertTrue(fila["plegado_ok"])
        self.assertFalse(fila["elegible"])
        self.assertEqual(fila["donor_score"], 5)


class TestSinViennaRNA_NO_SE_ELIGE(unittest.TestCase):

    def test_sale_NOT_RUN_y_no_se_propone_ninguna(self):
        eleccion = intron_design.choose_break(
            SGEP_SCAFFOLD, guide="A" * 22, available=False
        )
        self.assertIs(eleccion.state, FilterState.NOT_RUN)
        self.assertIsNone(eleccion.chosen)

    def test_y_el_motivo_dice_por_que_NO_basta_con_bajar_el_criptico(self):
        eleccion = intron_design.choose_break(
            SGEP_SCAFFOLD, guide="A" * 22, available=False
        )
        self.assertIn("pasajera", eleccion.reason.lower())


class TestLosEspaciadoresNuevos(unittest.TestCase):

    def test_las_longitudes_van_entre_20_y_30(self):
        self.assertEqual(intron_design.SPACER_RANGE, (20, 30))

    def test_los_filtros_son_LOS_MISMOS_de_spacers_mas_los_propios(self):
        propios = intron_design.spacer_rejections("GT" * 12)
        self.assertTrue(any("GT" in m for m in propios), propios)

    def test_un_tramo_de_polipirimidinas_que_COMPITA_con_el_legitimo_se_rechaza(self):
        motivos = intron_design.spacer_rejections("CTTTTTTTTTCTCTCTCTCTCT")
        self.assertTrue(any("pirimidin" in m.lower() for m in motivos), motivos)

    def test_y_se_dice_CONTRA_QUE_compite(self):
        motivos = intron_design.spacer_rejections("CTTTTTTTTTCTCTCTCTCTCT")
        self.assertTrue(any("legitimo" in m.lower() for m in motivos), motivos)

    def test_un_AG_en_contexto_utilizable_se_rechaza(self):
        motivos = intron_design.spacer_rejections("AG" * 11)
        self.assertTrue(motivos)

    def test_una_secuencia_limpia_no_da_motivos(self):
        # Sale del propio generador (secuencia autorizada, no inventada a mano).
        limpia = "TCATACTAACACACTCCACAACACC"
        self.assertEqual(intron_design.spacer_rejections(limpia), ())

    def test_LOS_FILTROS_SON_SATISFACIBLES(self):
        """Un filtro que no puede pasar nadie es PEOR que no tener filtro: parece que
        comprueba algo y lo que hace es vaciar la piscina.

        Medido el 2026-08-26 sobre 200.000 sorteos con la composicion de `spacers.py`:
        pasan unos 3.900, o sea cerca del 2 %. Exigente y alcanzable. Los dos motivos
        que mas rechazan son los propios de este intron —«lleva un AG» y «lleva un GT»—,
        que es lo esperado: son los que compiten con los sitios legitimos.
        """
        import random

        rng = random.Random(7)
        pasan = 0
        for _ in range(20000):
            n = rng.randint(*intron_design.SPACER_RANGE)
            candidato = "".join(rng.choices("ACGT", weights=(32, 32, 18, 18), k=n))
            if intron_design.is_acceptable(candidato):
                pasan += 1
        self.assertGreater(pasan, 100, "los filtros no dejan pasar practicamente nada")
        self.assertLess(pasan, 20000 // 2, "los filtros no estan filtrando")


class TestElSueloDE_80_SE_APLICA_TAMBIEN_AQUI(unittest.TestCase):

    def test_una_combinacion_que_lo_incumple_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            introns.check_length("GT" + "A" * 30 + "CTTTTTTTCAG", name="corto")


if __name__ == "__main__":
    unittest.main()
