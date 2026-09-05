"""El fragmento de síntesis: el intrón COMPLETO, con su contexto exónico.

Regla 5: escritos antes que `shmir_design/fragmento.py`.

## De qué va

Los sitios NheI y SacI existían para digerir y ligar. El fragmento se manda a
sintetizar ENTERO, así que dentro del intrón no cortan nada: son 12 nt inertes en un
tramo donante→punto de ramificación que ya está por encima del rango típico. Salen, y se
quedan como OPCIÓN DECLARADA.

Lo que se emite pasa a ser el intrón entero listo para pegar SOBRE LA FEATURE del intrón
en SnapGene: el plásmido crece exactamente lo que crece el intrón, sin ligar ni ensamblar
nada.

## El desajuste que había que resolver ANTES

En el `.dna` del casete la feature del intrón MVM va de 3129 a 3220 — 92 nt — y el intrón
vacío del proyecto son 82 de GT a AG. Diez de diferencia. La hipótesis era «contexto
exónico anotado dentro de la feature», y aquí se COMPRUEBA sobre el casete versionado:
los diez son exactamente `exon5` (5 nt) y `exon3` (5 nt) de `blocks.PIECES`, una pieza
versionada a cada lado.

Que salga de una comprobación y no de una suposición es lo que hace que el fragmento
pueda llevarlos: pegar 82 sobre una selección de 92 borraría 10 nt de exón, sin ningún
error hasta secuenciar.
"""

import hashlib
import unittest
from pathlib import Path

from shmir_design import blocks, fragmento, introns, splicing
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.scaffold import build_hairpin

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DIR / "aav_casete.fa"
QUIMERICO = DIR / introns.QUIMERICO_PLASMID

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"


def _casete() -> str:
    crudo = CASETE.read_text(encoding="utf-8").splitlines()
    return "".join(l.strip() for l in crudo if not l.startswith(">")).upper()


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLaFeatureAnotadaSonNoventaYDos(unittest.TestCase):
    """Los diez nt de diferencia se DERIVAN; no se dan por supuestos."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.feature = fragmento.locate_feature(cls.casete, name="aav_casete.fa")

    def test_el_intron_de_GT_a_AG_son_82(self):
        sitio = splicing.locate_intron(self.casete, name="aav_casete.fa")
        self.assertEqual(sitio.length, 82)
        self.assertEqual((sitio.donor_start, sitio.acceptor_end), (3134, 3215))

    def test_la_feature_son_92_y_empieza_5_antes(self):
        self.assertEqual(self.feature.length, 92)
        self.assertEqual((self.feature.start, self.feature.end), (3129, 3220))

    def test_los_diez_de_mas_son_las_dos_piezas_de_exon(self):
        self.assertEqual(self.feature.exon5, blocks.PIECES["exon5"].sequence)
        self.assertEqual(self.feature.exon3, blocks.PIECES["exon3"].sequence)
        self.assertEqual(len(self.feature.exon5) + len(self.feature.exon3), 10)

    def test_la_feature_es_exon5_mas_intron_mas_exon3(self):
        vacio = introns.get("mvm_actual").empty_sequence
        self.assertEqual(
            self.feature.sequence,
            self.feature.exon5 + vacio + self.feature.exon3,
        )

    def test_el_tramo_declarado_del_dna_coincide_con_el_derivado(self):
        """La coordenada reportada del `.dna` se CRUZA con la derivada del casete."""
        comprobacion = fragmento.check_declared_span(self.feature)
        self.assertIs(comprobacion.state, FilterState.PASS)
        self.assertIn("3129", comprobacion.reason)
        self.assertIn("3220", comprobacion.reason)

    def test_si_el_exon_no_esta_pegado_al_intron_ABORTA(self):
        """Sin las piezas de exón flanqueando, no se sabe qué cubre la feature."""
        i = self.casete.index(blocks.PIECES["exon5"].sequence + "GTAAGG")
        roto = self.casete[:i] + "TTTTT" + self.casete[i + 5:]
        with self.assertRaises(ShmirDesignError) as cm:
            fragmento.locate_feature(roto, name="roto")
        self.assertIn("exon5", str(cm.exception))


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElFragmentoSinSitios(unittest.TestCase):
    """Lo que se pide a sintetizar por defecto: sin NheI ni SacI."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.horquilla = build_hairpin(GUIA_1018)
        cls.frag = fragmento.build_fragment(
            cls.horquilla, cassette=cls.casete, intron="mvm_actual"
        )

    def test_por_defecto_los_sitios_NO_van(self):
        self.assertFalse(self.frag.with_sites)
        for enzima in ("NheI", "SacI"):
            self.assertNotIn(blocks.PIECES[enzima].sequence, self.frag.sequence)

    def test_tampoco_van_los_del_casete(self):
        for enzima in ("MluI", "AgeI"):
            self.assertNotIn(blocks.PIECES[enzima].sequence, self.frag.sequence)

    def test_longitudes_derivadas(self):
        # exón 5 + [MVM5 40 + esp5 20 + ctx5 20 + horquilla 97 + ctx3 20 + esp3 45
        # + MVM3 42] + exón 5 = 294. Sin los 12 nt de los dos sitios.
        self.assertEqual(len(self.frag.intron), 284)
        self.assertEqual(len(self.frag.sequence), 294)
        self.assertEqual(self.frag.growth, 294 - 92)
        self.assertEqual(self.frag.growth, 202)

    def test_los_extremos_son_los_de_la_feature_anotada(self):
        self.assertTrue(self.frag.sequence.startswith(self.frag.feature.exon5))
        self.assertTrue(self.frag.sequence.endswith(self.frag.feature.exon3))
        comprobacion = self.frag.check("extremos_vs_feature")
        self.assertIs(comprobacion.state, FilterState.PASS)

    def test_pegarlo_sobre_la_feature_no_descoloca_nada(self):
        """La prueba de verdad: sustituir la feature y volver a localizar el intrón."""
        nuevo = (
            self.casete[: self.frag.feature.start - 1]
            + self.frag.sequence
            + self.casete[self.frag.feature.end :]
        )
        self.assertEqual(len(nuevo), len(self.casete) + self.frag.growth)
        sitio = splicing.locate_intron(nuevo, name="pegado")
        self.assertEqual(sitio.length, len(self.frag.intron))
        self.assertEqual(sitio.donor, "GT")
        self.assertEqual(sitio.acceptor, "AG")
        # Y el contexto exónico sigue entero: nada de exón borrado.
        self.assertIn(
            blocks.PIECES["MluI"].sequence + blocks.PIECES["exon5"].sequence, nuevo
        )
        self.assertIn(
            blocks.PIECES["exon3"].sequence + blocks.PIECES["AgeI"].sequence, nuevo
        )

    def test_la_horquilla_entera_va_dentro(self):
        self.assertIn(self.horquilla.sequence, self.frag.sequence)

    def test_los_15_de_cada_extremo_se_emiten(self):
        self.assertEqual(self.frag.head(), self.frag.sequence[:15])
        self.assertEqual(self.frag.tail(), self.frag.sequence[-15:])
        self.assertEqual(len(self.frag.head()), 15)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLosSitiosSiguenSiendoUnaOpcion(unittest.TestCase):
    """Retirarlos por defecto no es borrarlos: se piden y salen."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, with_sites=True
        )

    def test_con_sitios_mide_12_mas(self):
        self.assertEqual(len(self.frag.intron), blocks.INTRON_LENGTH)
        self.assertEqual(len(self.frag.sequence), 306)
        self.assertEqual(self.frag.growth, 214)

    def test_y_lleva_los_dos_sitios_una_vez_cada_uno(self):
        for enzima in ("NheI", "SacI"):
            self.assertEqual(
                self.frag.sequence.count(blocks.PIECES[enzima].sequence), 1
            )

    def test_el_motivo_de_que_no_sea_lo_de_por_defecto_esta_escrito(self):
        self.assertIn("sintetiza", fragmento.WHY_THE_SITES_LEAVE.lower())
        comprobacion = self.frag.check("sitios")
        self.assertIn("declarada", comprobacion.reason)


@unittest.skipUnless(
    CASETE.is_file() and QUIMERICO.is_file(),
    "NOT_RUN: falta aav_casete.fa o el plásmido del quimérico",
)
class TestElQuimericoUsaLOS_MISMOS_EXTREMOS(unittest.TestCase):
    """El módulo es el mismo en las dos arquitecturas y los flancos NO."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.mvm = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, intron="mvm_actual"
        )
        cls.qui = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, intron="intron_quimerico"
        )

    def test_los_extremos_son_LOS_MISMOS(self):
        self.assertEqual(self.qui.sequence[:5], self.mvm.sequence[:5])
        self.assertEqual(self.qui.sequence[-5:], self.mvm.sequence[-5:])

    def test_y_los_15_nt_NO_lo_son(self):
        self.assertNotEqual(self.qui.head(), self.mvm.head())
        self.assertNotEqual(self.qui.tail(), self.mvm.tail())

    def test_el_quimerico_no_lleva_espaciadores(self):
        # 133 del intrón aportado + 137 del módulo sin sitios.
        self.assertEqual(len(self.qui.intron), 133 + 137)
        self.assertEqual(len(self.qui.sequence), 280)
        self.assertEqual(self.qui.growth, 188)

    def test_tambien_se_pega_sin_descolocar(self):
        self.assertIs(self.qui.check("pegado").state, FilterState.PASS)
        nuevo = (
            self.casete[: self.qui.feature.start - 1]
            + self.qui.sequence
            + self.casete[self.qui.feature.end :]
        )
        self.assertEqual(len(nuevo), len(self.casete) + self.qui.growth)
        self.assertEqual(nuevo.count(self.qui.sequence), 1)

    def test_pero_la_app_YA_NO_LO_LOCALIZA_y_lo_dice(self):
        """El localizador busca las mitades del MVM: con otro intrón NO_APLICA.

        No es un fallo del fragmento — es la consecuencia de cambiar de arquitectura, y
        de ese localizador salen las ventanas de cebador del frente del empalme. El
        MVM sí sale PASS por el mismo camino, que es lo que hace que la diferencia
        signifique algo.
        """
        self.assertIs(self.mvm.check("localizable").state, FilterState.PASS)
        aviso = self.qui.check("localizable")
        self.assertIs(aviso.state, FilterState.NO_APLICA)
        self.assertIn("eficiencia de empalme", aviso.reason)

    def test_un_intron_retirado_NO_se_emite(self):
        with self.assertRaises(ShmirDesignError):
            fragmento.build_fragment(
                build_hairpin(GUIA_1018),
                cassette=self.casete,
                intron="mvm_sin_criptico",
            )


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLaHojaDePedido(unittest.TestCase):
    """Lo que hay que poder mirar de un vistazo antes de pegar."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, label="3utr:1018"
        )
        cls.hoja = fragmento.fragment_order_sheet(cls.frag)

    def test_dice_la_longitud_total(self):
        self.assertIn("294", self.hoja)

    def test_dice_cuanto_crece_el_plasmido(self):
        self.assertIn("202", self.hoja)
        self.assertIn(str(len(self.casete)), self.hoja)
        self.assertIn(str(len(self.casete) + 202), self.hoja)

    def test_dice_de_que_intron_viene_y_con_que_md5(self):
        self.assertIn("mvm_actual", self.hoja)
        md5 = hashlib.md5(
            introns.get("mvm_actual").empty_sequence.encode("ascii")
        ).hexdigest()
        self.assertIn(md5, self.hoja)

    def test_destaca_los_15_de_cada_extremo(self):
        self.assertIn(self.frag.head(), self.hoja)
        self.assertIn(self.frag.tail(), self.hoja)

    def test_dice_donde_se_pega(self):
        self.assertIn("3129", self.hoja)
        self.assertIn("3220", self.hoja)

    def test_avisa_de_que_los_sitios_NO_van(self):
        self.assertIn("NheI", self.hoja)
        self.assertIn("SacI", self.hoja)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElPaqueteQueSaleDeLaCorrida(unittest.TestCase):
    """`fragment_bundle` y `fragment_rows`, que son lo que llaman el CLI y la página.

    Estaban sin recorrer y ahí vivía un fallo: la etiqueta del candidato se pedía a
    `selection.report.frame` —un atributo que `ReportSelection` NO tiene— y el marco
    caía a `3utr` sobre un tilado del TRANSCRITO, así que `coords` abortaba la corrida
    entera con `3utr:1684`. Es la errata nº 31 otra vez: las piezas tenían tests y la
    combinación no la recorría nadie.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.presentation import (
            FRAGMENT_NEEDS_CASSETTE,
            fragment_bundle,
            fragment_rows,
            page_run,
        )
        from shmir_design.scaffold import SGEP_SCAFFOLD

        ruta = DIR / "NM_011170.3.fa"
        if not ruta.is_file():
            raise unittest.SkipTest("NOT_RUN: falta NM_011170.3.fa")
        crudo = ruta.read_text(encoding="utf-8").splitlines()
        secuencia = "".join(l.strip() for l in crudo if not l.startswith(">"))
        from shmir_design.resolve import resolve_anatomy

        anat = resolve_anatomy(
            sequence=secuencia,
            name="NM_011170.3",
            genbank=DIR / "NM_011170.3.gb",
        )
        cls.corrida = page_run(
            species="mouse", sequence=secuencia, anatomy=anat,
        )
        cls.casete = _casete()
        cls.scaffold = SGEP_SCAFFOLD
        cls.bundle = staticmethod(fragment_bundle)
        cls.rows = staticmethod(fragment_rows)
        cls.sin_casete = FRAGMENT_NEEDS_CASSETTE

    def test_la_etiqueta_del_candidato_LLEVA_su_marco(self):
        filas = self.rows(
            self.corrida.selection, self.scaffold, cassette=self.casete
        )
        self.assertTrue(filas)
        for fila in filas:
            self.assertRegex(str(fila["candidato"]), r"^(tx|3utr):\d+$")

    def test_el_paquete_trae_el_FASTA_y_la_hoja(self):
        paquete = self.bundle(
            self.corrida.selection, self.scaffold, species="mouse",
            cassette=self.casete,
        )
        self.assertIn("mouse_fragmentos.fasta", paquete)
        self.assertIn("mouse_fragmentos.txt", paquete)
        self.assertEqual(
            paquete["mouse_fragmentos.fasta"].count(">"),
            len(self.corrida.selection.selection.chosen),
        )

    def test_sin_casete_la_hoja_SALE_IGUAL_diciendo_por_que(self):
        paquete = self.bundle(
            self.corrida.selection, self.scaffold, species="mouse", cassette=None,
        )
        self.assertEqual(paquete, {"mouse_fragmentos.txt": self.sin_casete})
        self.assertIn("NOT_RUN", self.sin_casete)
