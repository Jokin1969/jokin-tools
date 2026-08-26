"""Tests del generador de espaciadores de novo (autorizado explicitamente).

Regla 5: escritos antes que `shmir_design/spacers.py`.

AUTORIZACION. La regla 1 prohibe generar secuencia. Aqui hay una excepcion **escrita y
acotada**: cuando el 97-mero no conserva su estructura dentro del intron con los
espaciadores estandar, se pueden generar espaciadores nuevos para ESA guia, con las
condiciones que se usaron para los originales. No cubre nada mas: ni guias, ni pasajeras,
ni contextos, ni andamio.

Condiciones (filtros duros, iguales a los actuales):
  sin donantes cripticos GTRAGT / GTAAGG / GTGAGG, sin AATAAA/ATTAAA, sin homopolimeros
  >=4, sin GGGG/CCCC, sin duplicar ningun sitio del cassette, GC entre 0,28 y 0,45.

Criterio de seleccion, uno solo: entre los que pasan, el que hace que el 97-mero dentro
del intron pliegue identico a aislado. Si varios lo cumplen, el de menor MFE del intron.

Longitudes FIJAS: 20 nt el 5' y 45 nt el 3'. Son las que dejan la horquilla a 86 nt del
5'SS y a 62 del punto de ramificacion.
"""

import unittest

from shmir_design.blocks import PIECES, build_block
from shmir_design.folding import VIENNA_AVAILABLE, dot_bracket
from shmir_design.spacers import (
    CASSETTE_SITES,
    CRYPTIC_DONORS,
    GC_MAX,
    GC_MIN,
    SPACER3_LENGTH,
    SPACER5_LENGTH,
    STANDARD_3,
    STANDARD_5,
    SpacerChoice,
    choose_spacers,
    spacer_rejections,
)

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"


class TestLongitudesFijas(unittest.TestCase):

    def test_son_20_y_45(self):
        self.assertEqual((SPACER5_LENGTH, SPACER3_LENGTH), (20, 45))

    def test_coinciden_con_los_originales(self):
        self.assertEqual(len(STANDARD_5), SPACER5_LENGTH)
        self.assertEqual(len(STANDARD_3), SPACER3_LENGTH)

    def test_los_estandar_son_los_del_cassette(self):
        self.assertEqual(STANDARD_5, PIECES["espaciador5"].sequence)
        self.assertEqual(STANDARD_3, PIECES["espaciador3"].sequence)


class TestFiltrosDuros(unittest.TestCase):

    def test_los_espaciadores_estandar_pasan_sus_propios_filtros(self):
        """Caso base: si los originales no pasaran, el filtro estaria mal."""
        self.assertEqual(spacer_rejections(STANDARD_5), ())
        self.assertEqual(spacer_rejections(STANDARD_3), ())

    def test_un_donante_criptico_se_rechaza(self):
        for donante in CRYPTIC_DONORS:
            sonda = donante + "TACAATGATCCAAATCA"[: SPACER5_LENGTH - 6]
            self.assertTrue(
                any("donante" in m for m in spacer_rejections(sonda)), donante
            )

    def test_GTRAGT_cubre_las_dos_variantes(self):
        self.assertIn("GTAAGT", CRYPTIC_DONORS)
        self.assertIn("GTGAGT", CRYPTIC_DONORS)

    def test_una_señal_de_poliadenilacion_se_rechaza(self):
        for señal in ("AATAAA", "ATTAAA"):
            sonda = "TACAATGATCCAAA" + señal
            self.assertTrue(any("polia" in m.lower() for m in spacer_rejections(sonda)))

    def test_un_homopolimero_de_4_se_rechaza(self):
        sonda = "TACAATGATCCAAAATCAAGA"[:SPACER5_LENGTH]
        self.assertTrue(
            any("homopolimero" in m.lower() for m in spacer_rejections(sonda))
        )

    def test_GGGG_y_CCCC_se_rechazan(self):
        for tramo in ("GGGG", "CCCC"):
            sonda = ("TACAAT" + tramo + "GATCCAAATCAAGA")[:SPACER5_LENGTH]
            self.assertTrue(spacer_rejections(sonda), tramo)

    def test_un_sitio_del_cassette_se_rechaza(self):
        for sitio in CASSETTE_SITES:
            sonda = (sitio + "TACAATGATCCAAATCAAGA")[:SPACER5_LENGTH]
            self.assertTrue(any("sitio" in m for m in spacer_rejections(sonda)), sitio)

    def test_el_GC_fuera_de_rango_se_rechaza(self):
        alto = "GCGCGCGCGCGATCTATCAT"[:SPACER5_LENGTH]
        bajo = "ATATATATATATATATATAT"[:SPACER5_LENGTH]
        self.assertTrue(any("GC" in m for m in spacer_rejections(alto)))
        self.assertTrue(any("GC" in m for m in spacer_rejections(bajo)))

    def test_el_rango_de_GC_es_el_declarado(self):
        self.assertEqual((GC_MIN, GC_MAX), (0.28, 0.45))

    def test_el_motivo_del_rechazo_dice_cual_es(self):
        motivos = spacer_rejections("GTAAGTGATCCAAATCAAGA")
        self.assertTrue(motivos)
        self.assertIn("GTAAGT", " ".join(motivos))


@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no esta instalado")
class TestCasoBase(unittest.TestCase):
    """Los estandar son la PRIMERA opcion, no una mas del monton."""

    def _piezas(self, guia=GUIA_1018):
        bloque = build_block(guia)
        return bloque, dot_bracket(bloque.hairpin.sequence)[0]

    def _buscar(self, guia=GUIA_1018, assemble=None):
        bloque, estructura = self._piezas(guia)
        if assemble is None:
            def assemble(e5, e3):
                return (
                    PIECES["MVM5"].sequence + e5 + bloque.module
                    + e3 + PIECES["MVM3"].sequence
                )
        return choose_spacers(
            hairpin=bloque.hairpin.sequence,
            structure_alone=estructura,
            assemble=assemble,
        )

    def test_con_una_guia_que_funciona_devuelve_los_estandar(self):
        eleccion = self._buscar().choice
        self.assertEqual(eleccion.spacer5, STANDARD_5)
        self.assertEqual(eleccion.spacer3, STANDARD_3)

    def test_y_los_marca_como_estandar(self):
        self.assertTrue(self._buscar().choice.standard)

    def test_no_gasta_presupuesto_buscando_si_el_caso_base_vale(self):
        self.assertEqual(self._buscar().evaluated, 1)

    def test_las_cuatro_guias_reales_eligen_los_estandar(self):
        """Plausibilidad: si para una guia conocida saliera otra cosa, el algoritmo
        estaria mal. (Solo hay 4 de las 24 en el repositorio.)"""
        for guia in (
            GUIA_1018,
            "TAGATAAGCATTATAATTCCTA",
            "TAATTGAAAGAGCTACAGGTGG",
            "TAAAGGAATGCCACATATAGGG",
        ):
            with self.subTest(guia=guia):
                eleccion = self._buscar(guia).choice
                self.assertTrue(eleccion.standard)
                self.assertEqual(eleccion.spacer5, STANDARD_5)
                self.assertEqual(eleccion.spacer3, STANDARD_3)


@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no esta instalado")
class TestBusqueda(unittest.TestCase):
    """Cuando el caso base NO vale. Sonda de mecanismo: un contexto que lo rompe."""

    def _buscar_forzado(self, budget=120):
        bloque = build_block(GUIA_1018)
        estructura = dot_bracket(bloque.hairpin.sequence)[0]
        #: Cola complementaria del tallo: captura la horquilla desde fuera.
        from shmir_design.scaffold import reverse_complement

        veneno = reverse_complement(bloque.hairpin.sequence[:40])

        def assemble(e5, e3):
            return veneno + e5 + bloque.module + e3 + PIECES["MVM3"].sequence

        return choose_spacers(
            hairpin=bloque.hairpin.sequence,
            structure_alone=estructura,
            assemble=assemble,
            budget=budget,
        )

    def test_si_el_caso_base_falla_se_busca(self):
        busqueda = self._buscar_forzado()
        self.assertGreater(busqueda.evaluated, 1)

    def test_lo_que_devuelva_respeta_las_longitudes(self):
        eleccion = self._buscar_forzado().choice
        if eleccion is not None:
            self.assertEqual(len(eleccion.spacer5), SPACER5_LENGTH)
            self.assertEqual(len(eleccion.spacer3), SPACER3_LENGTH)

    def test_lo_que_devuelva_pasa_los_filtros_duros(self):
        eleccion = self._buscar_forzado().choice
        if eleccion is not None:
            self.assertEqual(spacer_rejections(eleccion.spacer5), ())
            self.assertEqual(spacer_rejections(eleccion.spacer3), ())

    def test_lo_que_devuelva_NO_se_marca_como_estandar(self):
        eleccion = self._buscar_forzado().choice
        if eleccion is not None:
            self.assertFalse(eleccion.standard)

    def test_la_busqueda_es_determinista(self):
        a = self._buscar_forzado().choice
        b = self._buscar_forzado().choice
        self.assertEqual(
            (a.spacer5, a.spacer3) if a else None,
            (b.spacer5, b.spacer3) if b else None,
        )

    def test_si_no_encuentra_nada_lo_dice_y_no_devuelve_nada(self):
        busqueda = self._buscar_forzado(budget=2)
        if busqueda.choice is None:
            self.assertIn("no se encontro", busqueda.note.lower())

    def test_el_presupuesto_se_respeta(self):
        busqueda = self._buscar_forzado(budget=30)
        self.assertLessEqual(busqueda.evaluated, 31)


class TestSalidaObligatoria(unittest.TestCase):
    """Los tres elementos que la autorizacion exige que salgan."""

    ELECCION = SpacerChoice(
        spacer5="A" * 20,
        spacer3="C" * 45,
        standard=False,
        structure="." * 296,
        mfe=-99.9,
    )

    def test_saca_las_dos_secuencias(self):
        texto = self.ELECCION.format_text()
        self.assertIn("A" * 20, texto)
        self.assertIn("C" * 45, texto)

    def test_saca_el_plegado_del_intron_completo(self):
        """Va partido en lineas de 60 para que se pueda leer; se comprueba entero."""
        texto = self.ELECCION.format_text()
        plegado = "".join(
            l.strip() for l in texto.splitlines() if set(l.strip()) <= set(".()")
            and l.strip()
        )
        self.assertEqual(plegado, "." * 296)

    def test_saca_el_MFE(self):
        self.assertIn("-99.9", self.ELECCION.format_text())

    def test_avisa_de_que_son_especificos_de_esta_guia(self):
        texto = self.ELECCION.format_text().lower()
        self.assertIn("especificos de esta guia", texto)
        self.assertIn("no son los estandar", texto)

    def test_avisa_de_que_el_cassette_no_es_intercambiable(self):
        texto = self.ELECCION.format_text()
        self.assertIn("NO es intercambiable", texto)
        self.assertIn("NheI", texto)

    def test_los_estandar_no_llevan_ese_aviso(self):
        estandar = SpacerChoice(
            spacer5=STANDARD_5, spacer3=STANDARD_3, standard=True,
            structure="." * 296, mfe=-1.0,
        )
        self.assertNotIn("NO es intercambiable", estandar.format_text())

    def test_los_estandar_lo_dicen_igualmente(self):
        estandar = SpacerChoice(
            spacer5=STANDARD_5, spacer3=STANDARD_3, standard=True,
            structure="." * 296, mfe=-1.0,
        )
        self.assertIn("estandar", estandar.format_text().lower())


class TestLaAutorizacionEsAcotada(unittest.TestCase):

    def test_el_modulo_no_genera_nada_que_no_sea_un_espaciador(self):
        """La autorizacion cubre espaciadores y nada mas."""
        import inspect

        import shmir_design.spacers as modulo

        fuente = inspect.getsource(modulo)
        for prohibido in ("guide", "passenger", "pasajera"):
            self.assertNotIn(f"def generate_{prohibido}", fuente)

    def test_el_modulo_deja_escrita_la_autorizacion(self):
        import shmir_design.spacers as modulo

        self.assertIn("AUTORIZACION", modulo.__doc__)


if __name__ == "__main__":
    unittest.main()
