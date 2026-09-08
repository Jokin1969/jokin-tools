"""El «QUÉ NO MIDE» no puede depender de que el distal ATRAVIESE algo.

Regla 5: escrito antes.

**Pedido el 2026-09-08, y el motivo es la mitad que importa**: *«la limitación del tramo
intermedio queda aunque el informe deje de imprimirla. Que vaya como nota permanente, no
sólo cuando el distal la atraviese — porque si el informe la calla cuando no hay cruce,
alguien puede leerlo como que el problema desapareció»*.

### Cómo se llegó aquí

`_lineas_de_cruce` salía **sólo si `distal_crosses`**, y eso era correcto cuando el
distal declarado (`3utr:282-401`) atravesaba la banda del `AATAAA` de `3utr:288`. Al
moverse el panel (errata nº 144) el distal que emite el informe pasa a `3utr:850-969`,
que queda **entero por detrás de las dos bandas** y no atraviesa ninguna — así que la
pareja «QUÉ MIDE / QUÉ NO MIDE» dejó de imprimirse.

**Y la limitación no había cambiado nada.** Un amplicón entero por detrás de una banda
está tan ausente de esa isoforma corta como uno partido por ella: en los dos casos la
razón mide la fracción que sobrevive a TODOS los cortes y no separa uno del otro.
Atravesar era **una** de las dos formas de no separar, y el emisor la trataba como la
única.

### Lo que este test fija

Que la condición sea **no separar**, derivada de la geometría —el distal no queda entero
por delante de la banda de la otra señal—, y no **atravesar**. Y que la frase que
describe el motivo diga cuál de los dos casos es, porque no se arreglan igual: uno se
mueve, el otro no cabe en ninguna parte.
"""

import unittest

from shmir_design.coords import Frame
from shmir_design.polya import CLEAVAGE_MIN, SignalClass, rtqpcr_amplicons
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestNoSepararNoEsAtravesar(unittest.TestCase):
    """Los DOS distales de hoy, el declarado y el que emite el informe."""

    @classmethod
    def setUpClass(cls):
        cls.utr3 = load_3utr(RATON)
        cls.informe = tile_utr(cls.utr3)
        cls.seleccion = select_from_report(cls.informe, default_config())
        cls.señales = [
            s for s in cls.informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]

    def _plan(self, *, con_panel: bool):
        avoid = (
            [
                (self.seleccion.window_of(c).window.start,
                 self.seleccion.window_of(c).window.end)
                for c in self.seleccion.selection.chosen
            ]
            if con_panel
            else []
        )
        return rtqpcr_amplicons(
            self.señales[0], utr_length=self.informe.utr_length, frame=Frame.UTR3,
            others=tuple(self.señales[1:]), avoid=avoid,
        )

    def test_el_caso_existe_los_DOS_distales_son_distintos(self):
        """Control adversario: si los dos planes dieran lo mismo, esto no mide nada."""
        sin, con = self._plan(con_panel=False), self._plan(con_panel=True)
        self.assertNotEqual(
            (sin.distal.start, sin.distal.end), (con.distal.start, con.distal.end)
        )
        # Y el declarado ATRAVIESA mientras el emitido NO: son los dos casos.
        self.assertTrue(sin.distal_crosses)
        self.assertFalse(con.distal_crosses)

    def test_los_DOS_dejan_de_separar_las_dos_señales(self):
        """La geometría: el distal no queda entero por delante de la otra banda.

        Se deriva de la posición, no de si cruza. Un amplicón por DETRÁS de una banda
        está tan ausente de esa isoforma corta como uno partido por ella.
        """
        otra = self.señales[1]
        for etiqueta, plan in (("declarado", self._plan(con_panel=False)),
                               ("emitido", self._plan(con_panel=True))):
            with self.subTest(etiqueta):
                self.assertGreaterEqual(plan.distal.end, otra.end + CLEAVAGE_MIN)
                self.assertEqual(plan.distal_behind, (otra,))
                self.assertTrue(plan.measures_all_cuts)

    def test_y_los_DOS_imprimen_QUE_MIDE_y_QUE_NO_MIDE(self):
        for etiqueta, plan in (("declarado", self._plan(con_panel=False)),
                               ("emitido", self._plan(con_panel=True))):
            with self.subTest(etiqueta):
                texto = "\n".join(plan.describe())
                self.assertIn("QUÉ MIDE ESTE PAR", texto)
                self.assertIn("QUÉ NO MIDE", texto)
                self.assertIn("INTERMEDIO", texto)

    def test_pero_DICEN_cual_de_los_dos_casos_es(self):
        """No se arreglan igual, así que no se describen igual.

        Un distal que ATRAVIESA una banda podría, en principio, moverse; uno que queda
        POR DETRÁS ya está donde tiene que estar y lo que no cabe es nada en medio.
        Fundir los dos motivos daría una frase correcta y una instrucción equivocada.
        """
        atraviesa = "\n".join(self._plan(con_panel=False).describe())
        detras = "\n".join(self._plan(con_panel=True).describe())
        self.assertIn("atraviesa", atraviesa.lower())
        self.assertIn("por detrás", detras.lower())
        self.assertNotIn("atraviesa esa otra banda", detras.lower())

    def test_y_los_DOS_dicen_que_NO_se_arregla_moviendolo(self):
        """El hueco entre las dos bandas se emite en los dos casos.

        Es la respuesta a «¿y por qué no lo mueves?», y esa pregunta se le hace igual al
        distal que atraviesa que al que está detrás. Salía sólo con el que atraviesa.
        """
        for etiqueta, plan in (("declarado", self._plan(con_panel=False)),
                               ("emitido", self._plan(con_panel=True))):
            with self.subTest(etiqueta):
                self.assertIsNotNone(plan.gap_between)
                texto = "\n".join(plan.describe())
                self.assertIn("NO CABE", texto)
                self.assertIn("nt para un amplicón de", texto)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestUnDistalQueSISEPARAnoDiceNada(unittest.TestCase):
    """Control adversario del emisor: si saliera siempre, no estaría midiendo nada."""

    def test_con_UNA_SOLA_señal_no_hay_nada_que_separar(self):
        utr3 = load_3utr(RATON)
        informe = tile_utr(utr3)
        señales = [
            s for s in informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        # `others=()` es «no hay otras», no «no se miraron»: aquí se pasa a propósito
        # para comprobar que sin nada que separar el emisor CALLA. Sin este control,
        # «siempre lo dice» y «lo dice cuando toca» darían el mismo verde.
        plan = rtqpcr_amplicons(
            señales[0], utr_length=informe.utr_length, frame=Frame.UTR3, others=(),
        )
        texto = "\n".join(plan.describe())
        self.assertEqual(plan.distal_behind, ())
        self.assertFalse(plan.measures_all_cuts)
        self.assertNotIn("QUÉ NO MIDE", texto)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElRegistroLaDeclaraComoNOTA_PERMANENTE(unittest.TestCase):
    """«SI VAS AL BANCO» la lleva SIEMPRE, y sus cifras se recalculan aquí.

    Un informe puede dejar de imprimir algo por una condición; el registro es lo que
    alguien abre para saber qué mide su ensayo. Pedido el 2026-09-08: *«que vaya en Si
    vas al banco como nota permanente»*.

    Y las cifras NO se dan por buenas por estar escritas: se derivan del mismo plan que
    las emite (principio nº 13), igual que las de la mordida de la máscara.
    """

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.texto = (Path(__file__).resolve().parents[1] / "CLAUDE.md").read_text("utf-8")
        cls.banco = cls.texto.split("## Reglas innegociables")[0]
        utr3 = load_3utr(RATON)
        informe = tile_utr(utr3)
        señales = [
            s for s in informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        cls.plan = rtqpcr_amplicons(
            señales[0], utr_length=informe.utr_length, frame=Frame.UTR3,
            others=tuple(señales[1:]),
        )

    def test_la_limitacion_esta_en_el_bloque_del_BANCO(self):
        self.assertIn("tramo", self.banco.lower())
        self.assertIn("INTERMEDIO", self.banco.upper())
        self.assertIn("NOTA PERMANENTE", self.banco.upper())

    def test_y_el_HUECO_que_declara_es_el_que_sale_del_plan(self):
        """11 nt para un amplicón de 120, recalculado. No transcrito."""
        bajo, alto = self.plan.gap_between
        cabe = alto - bajo + 1
        largo = self.plan.distal.end - self.plan.distal.start + 1
        self.assertIn(f"`3utr:{bajo}-{alto}`", self.banco)
        self.assertIn(f"**{cabe} nt** para un amplicón de {largo}", self.banco)

    def test_el_control_adversario_el_hueco_NO_da_para_un_amplicon(self):
        """Sin esto, «no cabe» y «no se miró» dirían lo mismo."""
        bajo, alto = self.plan.gap_between
        self.assertLess(
            alto - bajo + 1, self.plan.distal.end - self.plan.distal.start + 1
        )
