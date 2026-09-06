"""Las cuatro casillas: qué fragmento se pega sobre qué intrón.

Regla 5: escritos antes que `montaje.check_before_pasting`.

## El guardia que daba PASS a las cuatro

Señalado por el responsable del proyecto (2026-09-06):

> *«Un guardia que da PASS a las cuatro casillas no está midiendo lo que dice medir, y
> eso es peor que no tenerlo — porque el nombre promete algo que no hace.»*

Y es literal, MEDIDO: `verify_assembly` daba `PASS` a las cuatro combinaciones de
fragmento × plásmido receptor. Y no por descuido — **el módulo es el mismo en las dos
arquitecturas**: misma horquilla, mismos contextos de SGEP, mismos espaciadores. Mirando
el módulo, una sustitución cruzada y una correcta son indistinguibles.

## El criterio que sí discrimina: LOS EXTREMOS

Lo que cambia entre arquitecturas son los flancos, porque son de intrones distintos. Se
comparan los extremos del fragmento contra los del **intrón donde se va a pegar**, no
contra el módulo. Y hay que medir CUÁNTOS nucleótidos hacen falta, porque no es obvio:

  - los dos donantes empiezan por `GTAAG` y el exón aporta otros 5, así que los
    **primeros 10 nt son IDÉNTICOS** — divergen en el 11;
  - por el otro lado el aceptor `AG` más los 5 del exón dan 8 iguales — divergen en el 9.

Con 5 nt no se distinguen; con 10 tampoco. Los 15 que destaca la hoja de pedido cubren
los dos casos, y eso deja de ser una preferencia: está medido.

## Y la cuarta casilla no es un error

Pegar el fragmento del quimérico sobre un plásmido que lleva el MVM **es** cómo se cambia
de arquitectura. El trabajo del guardia no es prohibir una casilla: es DECIR EN CUÁL SE
ESTÁ, para que quien pega confirme que es la que quería. Por eso el cambio se DECLARA
—`architecture_change=True`— y sin declararlo la sustitución cruzada es `FAIL`. Con él
declarado, la matriz se invierte: lo que falla es no cambiar nada.
"""

import pathlib
import unittest

from shmir_design import blocks, fragmento, introns, montaje
from shmir_design.filters import FilterState
from shmir_design.scaffold import build_hairpin

DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DIR / "aav_casete.fa"
QUIMERICO = DIR / introns.QUIMERICO_PLASMID
GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"


def _casete() -> str:
    crudo = CASETE.read_text(encoding="utf-8").splitlines()
    return "".join(l.strip() for l in crudo if not l.startswith(">")).upper()


@unittest.skipUnless(
    CASETE.is_file() and QUIMERICO.is_file(),
    "NOT_RUN: falta aav_casete.fa o el plásmido del quimérico",
)
class TestLasCuatroCasillas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        horquilla = build_hairpin(GUIA_1018)
        cls.f_mvm = fragmento.build_fragment(
            horquilla, cassette=cls.casete, intron="mvm_actual", label="3utr:1018"
        )
        cls.f_qui = fragmento.build_fragment(
            horquilla, cassette=cls.casete, intron="intron_quimerico",
            label="3utr:1018",
        )
        feature = cls.f_mvm.feature
        # El plásmido receptor con el quimérico VACÍO en el sitio de la feature. No se
        # reconstruye nada: son dos piezas versionadas —el casete y el intrón extraído
        # de Addgene #198131— pegadas por el mismo camino que usa la app.
        cls.p_mvm = cls.casete
        cls.p_qui = feature.paste(
            feature.exon5
            + introns.get("intron_quimerico").empty_sequence
            + feature.exon3
        )

    def _fasta(self, fragmento_):
        return fragmento.fragments_fasta([fragmento_], species="mouse")

    def _celda(self, fragmento_, plasmido, **kwargs):
        informe = montaje.check_before_pasting(
            plasmido, self._fasta(fragmento_), **kwargs
        )
        return informe.check("arquitectura")

    # ── La medida que justifica los 15 ──────────────────────────────────────
    def test_los_primeros_DIEZ_nucleotidos_son_IDENTICOS(self):
        self.assertEqual(self.f_mvm.head(10), self.f_qui.head(10))
        self.assertEqual(self.f_mvm.head(10), "AAGAGGTAAG")

    def test_divergen_en_el_11_por_delante_y_en_el_9_por_detras(self):
        self.assertEqual(montaje.divergence_point(self.f_mvm.head(), self.f_qui.head()), 11)
        self.assertEqual(
            montaje.divergence_point(self.f_mvm.tail()[::-1], self.f_qui.tail()[::-1]), 9
        )

    def test_por_eso_quince_y_no_cinco_ni_diez(self):
        self.assertNotEqual(self.f_mvm.head(), self.f_qui.head())
        self.assertNotEqual(self.f_mvm.tail(), self.f_qui.tail())
        self.assertIn("11", montaje.WHY_FIFTEEN)
        self.assertIn("9", montaje.WHY_FIFTEEN)

    # ── Lo que NO discrimina, medido ────────────────────────────────────────
    def test_el_MODULO_es_el_mismo_en_las_dos(self):
        """Por eso mirar el módulo no separa nada: es la misma secuencia."""
        self.assertEqual(self.f_mvm.module, self.f_qui.module)

    def test_la_comprobacion_de_presencia_da_PASS_a_las_CUATRO(self):
        """La regresión: el guardia que prometía y no medía.

        Se deja escrito porque es el motivo de que exista `arquitectura`, y porque un
        `PASS` de `fragmento_presente` sigue siendo correcto — lo que no puede es
        leerse como «el fragmento va donde tenía que ir».
        """
        for fragmento_ in (self.f_mvm, self.f_qui):
            for plasmido in (self.p_mvm, self.p_qui):
                pegado = self._pegar(fragmento_, plasmido)
                informe = montaje.verify_assembly(pegado, self._fasta(fragmento_))
                self.assertIs(
                    informe.check("fragmento_presente").state, FilterState.PASS
                )

    def _pegar(self, fragmento_, plasmido):
        feature = fragmento_.feature
        largo = feature.length + (len(plasmido) - len(self.casete))
        return (
            plasmido[: feature.start - 1]
            + fragmento_.sequence
            + plasmido[feature.start - 1 + largo :]
        )

    # ── La matriz ───────────────────────────────────────────────────────────
    def test_la_diagonal_PASA(self):
        for fragmento_, plasmido in ((self.f_mvm, self.p_mvm), (self.f_qui, self.p_qui)):
            resultado = self._celda(fragmento_, plasmido)
            self.assertIs(resultado.state, FilterState.PASS, resultado.reason)

    def test_la_CRUZADA_sin_declarar_FALLA_y_NOMBRA_las_dos(self):
        for fragmento_, plasmido, lleva in (
            (self.f_mvm, self.p_qui, "intron_quimerico"),
            (self.f_qui, self.p_mvm, "mvm_actual"),
        ):
            resultado = self._celda(fragmento_, plasmido)
            self.assertIs(resultado.state, FilterState.FAIL, resultado.reason)
            self.assertIn(lleva, resultado.reason)
            self.assertIn(fragmento_.intron_name, resultado.reason)

    def test_declarando_el_cambio_la_matriz_se_INVIERTE(self):
        """Un cambio de arquitectura es una decisión, no un hallazgo del comprobador."""
        for fragmento_, plasmido in ((self.f_mvm, self.p_qui), (self.f_qui, self.p_mvm)):
            resultado = self._celda(fragmento_, plasmido, architecture_change=True)
            self.assertIs(resultado.state, FilterState.PASS, resultado.reason)
        for fragmento_, plasmido in ((self.f_mvm, self.p_mvm), (self.f_qui, self.p_qui)):
            resultado = self._celda(fragmento_, plasmido, architecture_change=True)
            self.assertIs(resultado.state, FilterState.FAIL, resultado.reason)

    def test_las_cuatro_casillas_dan_CUATRO_respuestas_distintas(self):
        motivos = {
            self._celda(f, p).reason
            for f in (self.f_mvm, self.f_qui)
            for p in (self.p_mvm, self.p_qui)
        }
        self.assertEqual(len(motivos), 4)


@unittest.skipUnless(
    CASETE.is_file() and QUIMERICO.is_file(),
    "NOT_RUN: falta aav_casete.fa o el plásmido del quimérico",
)
class TestIdentificarElIntronDelPlasmido(unittest.TestCase):
    """Se identifica por los FLANCOS versionados, que no dependen de la arquitectura."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        feature = fragmento.locate_feature(cls.casete, name="aav_casete.fa")
        cls.p_qui = feature.paste(
            feature.exon5
            + introns.get("intron_quimerico").empty_sequence
            + feature.exon3
        )

    def test_las_anclas_son_UNICAS_en_el_casete(self):
        for ancla in (montaje.FLANK_5, montaje.FLANK_3):
            self.assertEqual(self.casete.count(ancla), 1, ancla)

    def test_el_parental_lleva_el_MVM_vacio(self):
        cual = montaje.intron_in_plasmid(self.casete)
        self.assertEqual(cual.name, "mvm_actual")
        self.assertTrue(cual.empty)
        self.assertEqual(cual.length, 82)

    def test_y_el_otro_lleva_el_QUIMERICO(self):
        cual = montaje.intron_in_plasmid(self.p_qui)
        self.assertEqual(cual.name, "intron_quimerico")
        self.assertEqual(cual.length, 133)

    def test_con_el_MODULO_dentro_sigue_identificandolo(self):
        """El módulo cambia el interior y no los extremos: por eso los extremos."""
        frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=self.casete, intron="mvm_actual"
        )
        cual = montaje.intron_in_plasmid(frag.feature.paste(frag.sequence))
        self.assertEqual(cual.name, "mvm_actual")
        self.assertFalse(cual.empty)

    def test_un_intron_que_NO_esta_en_el_registro_se_dice_SIN_adivinar(self):
        feature = fragmento.locate_feature(self.casete, name="aav_casete.fa")
        ajeno = "GTAAGCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCAG"
        raro = feature.paste(feature.exon5 + ajeno + feature.exon3)
        cual = montaje.intron_in_plasmid(raro)
        self.assertEqual(cual.name, "")
        self.assertEqual(cual.length, len(ajeno))
        self.assertIn("no coincide", cual.describe().lower())

    def test_sin_las_anclas_sale_NOT_RUN_y_NO_pasa(self):
        informe = montaje.check_before_pasting(
            "ACGT" * 500,
            fragmento.fragments_fasta(
                [fragmento.build_fragment(
                    build_hairpin(GUIA_1018), cassette=self.casete
                )],
                species="mouse",
            ),
        )
        resultado = informe.check("arquitectura")
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIsNot(resultado.state, FilterState.PASS)


@unittest.skipUnless(
    CASETE.is_file() and QUIMERICO.is_file(),
    "NOT_RUN: falta aav_casete.fa o el plásmido del quimérico",
)
class TestElIntronPrevioYaNoSuponeCUAL(unittest.TestCase):
    """`sin_intron_previo` barría SÓLO el MVM: con otro intrón detrás daba PASS falso."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, intron="mvm_actual"
        )

    def test_el_quimerico_olvidado_dentro_tambien_se_caza(self):
        feature = self.frag.feature
        con_quimerico = feature.paste(
            feature.exon5
            + introns.get("intron_quimerico").empty_sequence
            + feature.exon3
        )
        # Pegado AL LADO: el quimérico vacío se queda y el fragmento entra detrás.
        mal = con_quimerico + self.frag.sequence
        informe = montaje.verify_assembly(
            mal, fragmento.fragments_fasta([self.frag], species="mouse")
        )
        aviso = informe.check("sin_intron_previo")
        self.assertIs(aviso.state, FilterState.FAIL)
        self.assertIn("intron_quimerico", aviso.reason)

    def test_un_montaje_limpio_sigue_pasando(self):
        informe = montaje.verify_assembly(
            self.frag.feature.paste(self.frag.sequence),
            fragmento.fragments_fasta([self.frag], species="mouse"),
        )
        self.assertIs(informe.check("sin_intron_previo").state, FilterState.PASS)


if __name__ == "__main__":
    unittest.main()
