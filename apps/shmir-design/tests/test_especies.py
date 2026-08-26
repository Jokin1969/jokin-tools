"""Especies: los fixtures se DECLARAN, nunca se suponen.

Regla 5: escritos antes.

Al cargar una secuencia de una especie sin fixtures —conejo, oveja, ciervo— la app tiene
que decir en pantalla que frentes puede cerrar y cuales no, CON EL FICHERO CONCRETO que
falta en cada caso. No una nota al pie: una tabla, porque un frente que no se ve no
existe — es exactamente lo que pasó con `offtarget_seed`.

Y el fixture de una especie NO se puede usar con otra. Ya apareció con `rmsk_mouse.out`
sobre el transcrito humano: el intervalo cabia y no saltaba ninguna alarma.
"""

import unittest

from shmir_design import species as sp
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState


class TestElRegistroDeEspecies(unittest.TestCase):

    def test_estan_las_dos_que_hay(self):
        self.assertIn("mouse", sp.SPECIES)
        self.assertIn("human", sp.SPECIES)

    def test_cada_una_declara_su_prefijo_de_miRBase_y_su_taxid(self):
        raton = sp.SPECIES["mouse"]
        self.assertEqual(raton.mirbase_prefix, "mmu-")
        self.assertEqual(raton.taxid, "txid10090")

    def test_una_especie_desconocida_se_reconoce_como_tal(self):
        conejo = sp.resolve("Oryctolagus cuniculus")
        self.assertFalse(conejo.known)

    def test_y_NO_se_le_inventa_ni_prefijo_ni_taxid(self):
        conejo = sp.resolve("Oryctolagus cuniculus")
        self.assertEqual(conejo.mirbase_prefix, "")
        self.assertEqual(conejo.taxid, "")

    def test_pero_SI_se_le_deriva_un_slug_para_nombrar_ficheros(self):
        self.assertEqual(sp.resolve("Oryctolagus cuniculus").slug, "oryctolagus_cuniculus")

    def test_el_nombre_cientifico_se_reconoce_para_las_conocidas(self):
        self.assertEqual(sp.resolve("Mus musculus").slug, "mouse")
        self.assertTrue(sp.resolve("Mus musculus").known)

    def test_sin_especie_declarada_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            sp.resolve("")


class TestElInformeDeFixtures(unittest.TestCase):

    def setUp(self):
        self.conejo = sp.fixture_report(sp.resolve("Oryctolagus cuniculus"), have=())

    def test_el_barrido_SIEMPRE_esta_disponible(self):
        fila = next(f for f in self.conejo.rows if "barrido" in f.front)
        self.assertTrue(fila.available)

    def test_porque_los_filtros_biofisicos_no_dependen_de_ningun_fichero(self):
        fila = next(f for f in self.conejo.rows if "barrido" in f.front)
        self.assertIn("no depende", fila.note.lower())

    def test_los_demas_FALTAN_y_dicen_QUE_fichero(self):
        for fila in self.conejo.rows:
            if fila.available:
                continue
            self.assertTrue(fila.missing, fila.front)

    def test_repetitivos_pide_el_rmsk_DE_ESA_ESPECIE(self):
        fila = next(f for f in self.conejo.rows if f.front.startswith("repetitivos"))
        self.assertIn("oryctolagus_cuniculus", fila.missing)
        self.assertTrue(fila.missing.endswith(".out"))

    def test_colision_de_seed_pide_mature_fa_FILTRADO_a_su_prefijo(self):
        fila = next(f for f in self.conejo.rows if "seed" in f.front)
        self.assertIn("mature.fa", fila.missing)
        # No hay prefijo miRBase conocido para el conejo: se dice, no se inventa.
        self.assertIn("prefijo", fila.missing.lower())

    def test_APA_pide_datos_de_esa_especie_y_no_los_del_raton(self):
        fila = next(f for f in self.conejo.rows if f.front.startswith("APA"))
        self.assertIn("PolyA_DB", fila.missing)
        self.assertIn("esta especie", fila.missing)

    def test_especificidad_pide_la_base_de_RefSeq_de_esa_especie(self):
        fila = next(f for f in self.conejo.rows if "especificidad" in f.front)
        self.assertIn("RefSeq", fila.missing)

    def test_el_render_se_parece_al_que_se_pidio(self):
        texto = self.conejo.render()
        self.assertIn("Especie detectada: Oryctolagus cuniculus", texto)
        self.assertIn("......", texto)
        self.assertIn("disponible", texto)
        self.assertIn("FALTA", texto)

    def test_con_el_raton_y_sus_ficheros_hay_frentes_DISPONIBLES(self):
        raton = sp.fixture_report(
            sp.resolve("Mus musculus"),
            have=("rmsk_mouse.out", "mature.fa", "aav_casete.fa"),
        )
        disponibles = [f.front for f in raton.rows if f.available]
        self.assertTrue(any("repetitivos" in f for f in disponibles))

    def test_pero_el_rmsk_del_RATON_no_cuenta_para_el_conejo(self):
        conejo = sp.fixture_report(
            sp.resolve("Oryctolagus cuniculus"), have=("rmsk_mouse.out",)
        )
        fila = next(f for f in conejo.rows if f.front.startswith("repetitivos"))
        self.assertFalse(fila.available)

    def test_y_el_motivo_lo_dice_con_el_caso_real(self):
        conejo = sp.fixture_report(
            sp.resolve("Oryctolagus cuniculus"), have=("rmsk_mouse.out",)
        )
        fila = next(f for f in conejo.rows if f.front.startswith("repetitivos"))
        self.assertIn("otra especie", fila.note.lower())


class TestLosFrentesQuedanEnNOT_RUN_VISIBLE(unittest.TestCase):

    def test_cada_fila_da_un_estado_de_filtro(self):
        conejo = sp.fixture_report(sp.resolve("Oryctolagus cuniculus"), have=())
        for fila in conejo.rows:
            self.assertIn(fila.state, (FilterState.PASS, FilterState.NOT_RUN))

    def test_un_conejo_sin_nada_tiene_MAS_NOT_RUN_que_un_raton_completo(self):
        conejo = sp.fixture_report(sp.resolve("Oryctolagus cuniculus"), have=())
        raton = sp.fixture_report(
            sp.resolve("Mus musculus"),
            have=("rmsk_mouse.out", "mature.fa", "aav_casete.fa", "refseq_rna.fa"),
        )
        self.assertGreater(
            sum(1 for f in conejo.rows if f.state is FilterState.NOT_RUN),
            sum(1 for f in raton.rows if f.state is FilterState.NOT_RUN),
        )

    def test_el_resumen_cuenta_cuantos_puede_cerrar(self):
        conejo = sp.fixture_report(sp.resolve("Oryctolagus cuniculus"), have=())
        self.assertIn(str(conejo.closable), conejo.render())
        self.assertIn(str(len(conejo.rows)), conejo.render())


class TestElTECHO_DeCoordenadasNoPuedeSerDelRATON(unittest.TestCase):
    """`coords.max_utr3()` sale de REFERENCES, que hoy son raton y humano.

    Un 3'UTR de conejo de 1900 nt ABORTABA al etiquetarlo, y eso no es un error del
    conejo: es la app teniendo dentro la anatomia del raton.
    """

    def test_el_techo_se_puede_AMPLIAR_declarando_la_especie(self):
        from shmir_design import coords

        self.assertGreaterEqual(coords.max_utr3(), 1606)
        coords.declare_utr3_length(1900, species="Oryctolagus cuniculus")
        try:
            self.assertEqual(coords.label(1900, coords.Frame.UTR3), "3utr:1900")
        finally:
            coords.reset_declared_lengths()

    def test_y_al_olvidarla_vuelve_a_abortar(self):
        from shmir_design import coords

        coords.declare_utr3_length(1900, species="conejo")
        coords.reset_declared_lengths()
        with self.assertRaises(ValueError):
            coords.label(1900, coords.Frame.UTR3)

    def test_declarar_una_longitud_absurda_ABORTA(self):
        from shmir_design import coords

        with self.assertRaises(ValueError):
            coords.declare_utr3_length(0, species="x")

    def test_sin_especie_no_se_declara_nada(self):
        from shmir_design import coords

        with self.assertRaises(ValueError):
            coords.declare_utr3_length(1900, species="")


if __name__ == "__main__":
    unittest.main()
