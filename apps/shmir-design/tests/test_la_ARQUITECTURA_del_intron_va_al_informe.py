"""La comparación de arquitecturas de intrón llega al informe, no sólo a la página.

**Corrección de Joaquín Castilla (2026-09-05)**, anotada con su nombre a petición suya y
por la misma razón que la predicción refutada de la carrera de A: si sólo se anotan las
rectificaciones ajenas, el registro deja de ser un registro y pasa a ser un argumento.

Dio como contrapeso del quimérico que su donante→punto de ramificación es de 314-318 nt
frente a 256 del MVM, y **lo retiró entero** al medirse: *«apliqué al quimérico los 214 nt
del MVM sin comprobar que el quimérico se monta sin espaciadores. La diferencia era
exactamente 65 = 20 + 45 — la errata 35, cometida por mí esta vez»*.

**Consecuencia, y es la que tiene que llegar al informe**: *«el quimérico gana en todo lo
medido, sin contrapeso conocido»*. Eso decide qué se sintetiza, así que no puede vivir
sólo en un desplegable de la interfaz — es el patrón que este proyecto lleva once veces
arreglando (principio nº 23).

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import introns, presentation  # noqa: E402


class TestLaLECTURA_esta_corregida(unittest.TestCase):

    def test_ya_NO_dice_que_el_quimerico_sea_peor_en_ese_eje(self):
        texto = introns.THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES
        self.assertNotIn("es PEOR que el MVM", texto)

    def test_da_los_DOS_numeros_montados(self):
        texto = introns.THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES
        self.assertIn("256", texto)
        self.assertIn("249", texto)

    def test_y_dice_que_ese_eje_NO_DISCRIMINA(self):
        self.assertIn("NO DISCRIMINA", introns.THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES)

    def test_los_dos_siguen_FUERA_del_rango_tipico(self):
        # Lo que sí se sostiene del contrapeso: no lo arregla cambiar de intrón.
        self.assertIn("rango típico", introns.THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES)


class TestLaCORRECCION_va_ATRIBUIDA(unittest.TestCase):
    """Misma regla que la predicción refutada de la carrera de A."""

    def test_lleva_el_nombre_de_quien_la_hizo(self):
        self.assertIn("Joaquín Castilla", introns.WHY_THE_COUNTERWEIGHT_WAS_RETIRED)

    def test_y_la_fecha(self):
        self.assertIn("2026-09-05", introns.WHY_THE_COUNTERWEIGHT_WAS_RETIRED)

    def test_dice_QUE_se_retiro_y_POR_QUE(self):
        texto = introns.WHY_THE_COUNTERWEIGHT_WAS_RETIRED
        self.assertIn("314", texto)      # el número que se retira
        self.assertIn("65", texto)       # la firma que lo delató
        self.assertIn("espaciador", texto.lower())

    def test_y_llega_a_la_CONSECUENCIA(self):
        texto = introns.WHY_THE_COUNTERWEIGHT_WAS_RETIRED
        self.assertIn("sin contrapeso conocido", texto.lower())


class TestLaARQUITECTURA_llega_al_informe(unittest.TestCase):
    """No basta con que esté en `introns.py`: tiene que salir en lo que se entrega."""

    def test_presentation_la_emite(self):
        texto = presentation.intron_architecture_note()
        self.assertIn("sin contrapeso conocido", texto.lower())
        self.assertIn("Joaquín Castilla", texto)

    def test_y_lleva_los_dos_ejes_medidos(self):
        texto = presentation.intron_architecture_note()
        # el que gana el quimérico y el que no discrimina
        self.assertIn("1,8", texto)     # dispersión del donante del quimérico
        self.assertIn("18,1", texto)    # la del MVM
        self.assertIn("249", texto)     # donante→punto montado

    def test_la_PAGINA_no_lo_formatea(self):
        # Regla 6: lo que decide qué se lee vive en `presentation`, con test.
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("intron_architecture_note", fuente)
        self.assertNotIn("sin contrapeso conocido", fuente)


class TestLaSECCION_sale_en_el_DOCUMENTO(unittest.TestCase):
    """No basta con que `presentation` la monte: tiene que estar en lo que se descarga.

    Es la comprobación que faltó once veces —la capacidad escrita y sin llamador en el
    camino de verdad—, así que se hace sobre el documento generado y no sobre el fuente.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.informe_doc import build_document
        from shmir_design.reference import (
            REFERENCES, fixture_available, load_reference,
        )

        raton = REFERENCES["NM_011170.3"]
        if not fixture_available(raton):
            raise unittest.SkipTest("falta data/reference/NM_011170.3.fa")
        tx = load_reference(raton)
        anat = Anatomy.from_cds(
            cds=raton.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
        )
        corrida = presentation.page_run(species="raton", sequence=tx, anatomy=anat)
        cls.doc = build_document(
            species="raton", tiling=corrida.tiling, selection=corrida.selection,
            generated="2026-09-05", anatomy=anat,
            dossier_starts=(corrida.selection.selection.chosen[0].start,),
        )

    def test_hay_una_seccion_de_arquitecturas(self):
        titulos = [s.title for s in self.doc.sections]
        self.assertIn("Arquitecturas de intrón", titulos)

    def test_y_lleva_la_lectura_y_la_atribucion(self):
        seccion = next(
            s for s in self.doc.sections if s.title == "Arquitecturas de intrón"
        )
        texto = "\n".join(b.text for b in seccion.blocks)
        self.assertIn("sin contrapeso conocido", texto.lower())
        self.assertIn("Joaquín Castilla", texto)

    def test_y_la_tabla_trae_los_CINCO_ejes(self):
        seccion = next(
            s for s in self.doc.sections if s.title == "Arquitecturas de intrón"
        )
        tablas = [b for b in seccion.blocks if b.kind == "table"]
        self.assertEqual(len(tablas), 1)
        self.assertEqual(len(tablas[0].rows), len(presentation.INTRON_AXES_MEASURED))

    def test_las_secciones_siguen_numeradas_SIN_repetir(self):
        numeros = [s.number for s in self.doc.sections]
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)))


if __name__ == "__main__":
    unittest.main()
