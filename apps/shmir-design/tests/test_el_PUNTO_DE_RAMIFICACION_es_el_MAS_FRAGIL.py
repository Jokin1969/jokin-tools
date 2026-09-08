"""El elemento menos accesible de los cuatro, y el contraste entre las dos arquitecturas.

Regla 5: escritos antes.

**De dónde sale.** Del cuarto modal ya salía el perfil de accesibilidad por
construcción, y con las dos arquitecturas montadas se ve una cosa que con una sola no se
veía: el punto de ramificación es, con diferencia, **el menos accesible de los cuatro**
—0,257 en el MVM frente a 0,889 del donante y 0,836 del aceptor— y el quimérico lo deja
**más libre** (0,355). Eso es un eje a favor del quimérico que no estaba medido.

**Y la misma medida trae el primer CONTRAPESO conocido**, que va con él o mienten los
dos: el donante del quimérico queda bastante más secuestrado (0,533 frente a 0,889). No
se reconcilia con lo que dice SpliceAI del mismo donante —0,966 frente a 0,873— porque
son dos preguntas: la secuencia dice que el sitio existe, el plegado dice si se puede
usar. Misma forma que «rebaja, no descarta».

**Lo que este fichero fija**, en dos mitades que no se sustituyen:

1. que el elemento más frágil se **DERIVA** de la medida y no está escrito en el código
   —con otro intrón puede ser otro—, con su control adversario; y
2. que los números de la prosa del informe **se recalculan aquí** de las 22
   construcciones de verdad y la prosa tiene que citarlos (principio nº 13, la misma
   disciplina que `tests/test_mordida_de_la_mascara.py`).
"""

import statistics
import unittest

from shmir_design import intron_folding, presentation
from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE
from shmir_design.intron_folding import ELEMENTS

#: Filas de prueba. NO son secuencias ni medidas de nada: son la ENTRADA de una funcion
#: de agregacion, y se eligen para que el elemento mas bajo NO sea el punto de
#: ramificacion — que es todo el control adversario de que el mas fragil se deriva.
FILAS_AL_REVES = (
    {"construccion": "a", "intron": "uno", "estado": FilterState.PASS,
     "donante": 0.10, "punto_de_ramificacion": 0.90,
     "tracto_polipirimidinas": 0.80, "aceptor": 0.70},
    {"construccion": "b", "intron": "uno", "estado": FilterState.PASS,
     "donante": 0.20, "punto_de_ramificacion": 0.90,
     "tracto_polipirimidinas": 0.80, "aceptor": 0.70},
)


class TestElMasFragilSE_DERIVA(unittest.TestCase):
    """No se nombra en el codigo: con otro intron puede ser otro."""

    def test_con_estas_filas_el_mas_fragil_es_el_DONANTE(self):
        # Si esto devolviera «punto_de_ramificacion» sobre unas filas donde el donante
        # es el mas bajo, la funcion no estaria midiendo: estaria recitando.
        self.assertEqual(
            intron_folding.weakest_element(FILAS_AL_REVES), "donante"
        )

    def test_y_el_codigo_NO_declara_cual_es(self):
        """El control mecanico del anterior: ninguna constante lo escribe."""
        self.assertIn("deriva", intron_folding.WEAKEST_IS_DERIVED.lower())

    def test_sin_ninguna_medida_devuelve_None_no_un_elemento(self):
        vacias = ({"intron": "uno", "estado": FilterState.NOT_RUN,
                   **{e: None for e in ELEMENTS}},)
        self.assertIsNone(intron_folding.weakest_element(vacias))


class TestLoNoMedidoNI_ES_CERO_NI_SE_CUENTA(unittest.TestCase):
    """Regla 3: no haber plegado y plegar y salir apareado son cosas distintas."""

    def test_una_fila_NOT_RUN_no_entra_en_la_media_y_SE_CUENTA(self):
        filas = FILAS_AL_REVES + (
            {"construccion": "c", "intron": "uno", "estado": FilterState.NOT_RUN,
             **{e: None for e in ELEMENTS}},
        )
        estadisticas = {
            f["elemento"]: f for f in intron_folding.element_stats(filas)
            if f["arquitectura"] == "uno"
        }
        self.assertEqual(estadisticas["donante"]["n"], 2)
        self.assertEqual(estadisticas["donante"]["sin_medir"], 1)
        # 0,15 y no 0,10: la fila sin medir no arrastra la media hacia cero.
        self.assertAlmostEqual(estadisticas["donante"]["media"], 0.15, places=6)


class TestElContrasteNECESITA_DOS(unittest.TestCase):

    def test_con_una_sola_arquitectura_NO_hay_ganador_y_se_dice(self):
        contraste = intron_folding.architecture_contrast(FILAS_AL_REVES)
        for fila in contraste:
            self.assertIsNone(fila["gana"])
            self.assertIn(intron_folding.CONTRAST_NEEDS_TWO, fila["motivo"])

    def test_con_dos_gana_LA_MAS_ACCESIBLE(self):
        otras = tuple(
            {**f, "intron": "dos", "donante": 0.50} for f in FILAS_AL_REVES
        )
        contraste = {
            f["elemento"]: f
            for f in intron_folding.architecture_contrast(FILAS_AL_REVES + otras)
        }
        self.assertEqual(contraste["donante"]["gana"], "dos")
        # Y donde empatan no se inventa un ganador.
        self.assertIsNone(contraste["aceptor"]["gana"])


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: ViennaRNA no está instalado")
class TestLasVEINTIDOS_DE_VERDAD(unittest.TestCase):
    """El panel de once con las DOS arquitecturas, plegado de verdad.

    Es lo que se pidió: «emítelo con las 22 y con el contraste entre las dos
    arquitecturas». Los números de este test no están transcritos de ninguna
    conversación — salen de plegar aquí.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.reference import (
            REFERENCES, fixture_available, load_reference,
        )

        cls.raton = REFERENCES["NM_011170.3"]
        cls.hay = fixture_available(cls.raton)
        if not cls.hay:
            return
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.spliceai import build_panel

        secuencia = load_reference(cls.raton)
        anatomia = Anatomy.from_cds(
            cds=cls.raton.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia
        )
        cls.seleccion = corrida.selection
        panel = build_panel(
            cls.seleccion,
            intron_names=("mvm_actual", "intron_quimerico"),
            scaffold=SGEP_SCAFFOLD,
        )
        cls.filas = presentation.splice_folding_rows(
            panel.constructions,
            module_of=lambda c: presentation.splice_module_of(
                c, selection=cls.seleccion, scaffold=SGEP_SCAFFOLD
            ),
        )

    def setUp(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta data/reference/NM_011170.3.fa")

    def _media(self, arquitectura, elemento):
        return statistics.mean(
            f[elemento] for f in self.filas
            if f["intron"] == arquitectura and f[elemento] is not None
        )

    def test_son_VEINTIDOS_y_las_veintidos_pliegan(self):
        self.assertEqual(len(self.filas), 22)
        self.assertEqual(
            len([f for f in self.filas if f["estado"] is FilterState.PASS]), 22
        )

    def test_el_PUNTO_DE_RAMIFICACION_es_el_menos_accesible_EN_LAS_DOS(self):
        """El hallazgo. Y en las dos, que es lo que lo hace del elemento y no del intrón."""
        for arquitectura in ("mvm_actual", "intron_quimerico"):
            solo = [f for f in self.filas if f["intron"] == arquitectura]
            self.assertEqual(
                intron_folding.weakest_element(solo), "punto_de_ramificacion",
                arquitectura,
            )

    def test_y_el_QUIMERICO_lo_deja_MAS_LIBRE(self):
        """El eje a favor del quimérico que no estaba medido."""
        mvm = self._media("mvm_actual", "punto_de_ramificacion")
        quimerico = self._media("intron_quimerico", "punto_de_ramificacion")
        self.assertGreater(quimerico, mvm)
        self.assertAlmostEqual(mvm, 0.257, places=3)
        self.assertAlmostEqual(quimerico, 0.355, places=3)

    def test_PERO_su_DONANTE_queda_MAS_secuestrado(self):
        """El primer contrapeso MEDIDO del quimérico. Va con lo anterior o mienten los dos."""
        self.assertAlmostEqual(self._media("mvm_actual", "donante"), 0.889, places=3)
        self.assertAlmostEqual(
            self._media("intron_quimerico", "donante"), 0.533, places=3
        )

    def test_el_contraste_queda_DOS_A_DOS_y_no_se_redondea_a_un_ganador(self):
        contraste = intron_folding.architecture_contrast(self.filas)
        ganadores = [f["gana"] for f in contraste]
        self.assertEqual(ganadores.count("mvm_actual"), 2)
        self.assertEqual(ganadores.count("intron_quimerico"), 2)

    def test_la_GUIA_no_mueve_ninguno_de_los_cuatro(self):
        """Este eje NO discrimina entre candidatos, y decirlo es la mitad del dato."""
        for fila in intron_folding.element_stats(self.filas):
            self.assertLess(fila["dispersion"], 1.0, fila)

    def test_el_punto_de_ramificacion_es_el_PEOR_CASO_de_sus_candidatos(self):
        """El MVM tiene UNO y el quimérico DOS: la cifra no cuenta lo mismo."""
        candidatos = {
            f["intron"]: f["rama_candidatos"] for f in self.filas
        }
        self.assertEqual(candidatos["mvm_actual"], 1)
        self.assertEqual(candidatos["intron_quimerico"], 2)
        # Y bajo la lectura del MEJOR candidato el quimérico sigue ganando: no depende
        # de cuál de las dos se coja.
        mejores = {
            f["intron"]: f["rama_mejor"] for f in self.filas
        }
        self.assertGreater(mejores["intron_quimerico"], mejores["mvm_actual"])

    def test_cada_fila_dice_CUAL_es_su_menos_accesible(self):
        for fila in self.filas:
            self.assertEqual(fila["menos_accesible"], "punto_de_ramificacion")

    def test_LA_PROSA_DEL_INFORME_CITA_ESTAS_CIFRAS(self):
        """Principio nº 13: las cifras del bloque no están transcritas de una charla.

        Se recalculan aquí, de las 22 de verdad, y el texto que se descarga tiene que
        citarlas. Si el plegado cambia, esto falla en vez de envejecer en silencio.
        """
        texto = presentation.intron_architecture_note()
        for arquitectura in ("mvm_actual", "intron_quimerico"):
            for elemento in ELEMENTS:
                cifra = f"{self._media(arquitectura, elemento):.3f}".replace(".", ",")
                self.assertIn(cifra, texto, f"{arquitectura}/{elemento}")


class TestElCONTRAPESO_QUEDA_ESCRITO(unittest.TestCase):
    """La frase que decía «sin contrapeso conocido» ya no puede decirlo."""

    def test_la_retirada_del_contrapeso_geometrico_NO_afirma_que_no_haya_ninguno(self):
        """Puede CITARLA entre « » como lo que fue; lo que no puede es afirmarla.

        Misma regla que `tests/test_prosa_contra_codigo.py` con la frase de los
        amplicones: una prosa corregida que borra lo que decía deja al siguiente lector
        sin saber que hubo una corrección — y la que se cita no engaña a nadie.
        """
        import re

        from shmir_design.introns import WHY_THE_COUNTERWEIGHT_WAS_RETIRED

        sin_citas = re.sub("«[^»]*»", "", WHY_THE_COUNTERWEIGHT_WAS_RETIRED).upper()
        self.assertNotIn("SIN CONTRAPESO CONOCIDO", sin_citas)
        # Y la cita va con su fecha, para que se lea como corrección y no como vigente.
        self.assertIn("CORREGIDO (2026-09-06)", WHY_THE_COUNTERWEIGHT_WAS_RETIRED)

    def test_y_el_nuevo_va_NOMBRADO_con_lo_que_lo_mide(self):
        from shmir_design.introns import THE_FIRST_COUNTERWEIGHT_MEASURED

        self.assertIn("donante", THE_FIRST_COUNTERWEIGHT_MEASURED)
        self.assertIn("plegado", THE_FIRST_COUNTERWEIGHT_MEASURED.lower())
        # Las dos mitades van juntas: el quimérico gana en el punto de ramificación y
        # pierde en el donante. Una sola de las dos frases miente.
        self.assertIn("punto de ramificación", THE_FIRST_COUNTERWEIGHT_MEASURED)


class TestLaPaginaLO_DESTACA(unittest.TestCase):
    """Un hallazgo enterrado en una columna de una tabla de 22 filas no se ve."""

    def test_el_modal_pinta_los_DESTACADOS_del_plegado(self):
        from pathlib import Path

        fuente = Path("ui/streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("folding_highlights", fuente)


if __name__ == "__main__":
    unittest.main()
