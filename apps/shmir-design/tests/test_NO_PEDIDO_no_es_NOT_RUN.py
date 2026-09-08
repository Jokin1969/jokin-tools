"""«No se midió por coste» no es «falta un recurso», y el motivo tampoco puede decirlo.

Regla 5: escrito antes.

**Pedido el 2026-09-08**, leyendo la columna `filtros_sin_correr` del export: decía
`homopolimero_molecula (1780 ventana(s))` **en todas las filas**, al lado de una columna
`homopolimero_molecula` que para ese candidato dice `PASS`. *«La distinción es correcta:
"no se midió por coste" no es un recurso que falte»*. Es la errata nº 91 aplicada a un
filtro que se añadió dos días antes sin ella.

### Y al ir a arreglarlo salió que eran DOS causas con UN estado

`escaneable` es `asymmetry is not None AND biophysical_ok(...)`, o sea que mezcla:

- **una ventana con `N`** — no hay guía que medir. Eso es una LAGUNA: `NOT_RUN`, y se
  arregla con otra secuencia o quitando la máscara;
- **una ventana que ya cayó por los biofísicos** — no se gasta en ella. Eso es una
  DECISIÓN: `NO_PEDIDO`, y no hay nada que conseguir.

Y el motivo las tapaba a las dos con la misma frase, «por coste»: sobre una ventana con
`N` eso es un **diagnóstico equivocado**, que es lo que el principio nº 3 prohíbe — manda
a mirar un presupuesto cuando lo que hay es una base desconocida. Con la máscara murina
puesta son **66 ventanas** las que reciben esa frase.
"""

import unittest
from pathlib import Path

from shmir_design import masking
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.filters import FilterState, biophysical_ok
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.scaffold import MOLECULE_HOMOPOLYMER
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
RAIZ = Path(__file__).resolve().parent.parent / "data" / "reference"
HAY = fixture_available(RATON)
HAY_MASCARA = (RAIZ / "rmsk_mouse.out").is_file() and (RAIZ / "rmsk_mouse.tbl").is_file()


def _anatomia(secuencia):
    return Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaVentanaQueNoSePIDE(unittest.TestCase):
    """Sin máscara no hay ninguna `N`: todas las que no se miran son por DECISIÓN."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        cls.informe = tile_utr(secuencia, anatomy=_anatomia(secuencia))
        cls.seleccion = select_from_report(cls.informe, default_config())

    def _sin_mirar(self):
        return [
            w for w in self.informe.windows
            if not biophysical_ok(list(w.evaluation.filters) + [w.zona_prohibida])
        ]

    def test_el_caso_existe_y_no_hay_ninguna_N(self):
        """Control adversario: si hubiera `N`, este fichero probaría otra cosa."""
        self.assertEqual(
            [w for w in self.informe.windows if w.evaluation.asymmetry is None], []
        )
        self.assertEqual(len(self._sin_mirar()), 1780)

    def test_salen_NO_PEDIDO_y_no_NOT_RUN(self):
        for ventana in self._sin_mirar():
            with self.subTest(ventana.window.start):
                self.assertIs(
                    ventana.homopolimero_molecula.state, FilterState.NO_PEDIDO
                )

    def test_y_el_motivo_NO_manda_a_conseguir_nada(self):
        """Un `NOT_RUN` manda a por un recurso; aquí no hay ninguno que conseguir."""
        motivo = self._sin_mirar()[0].homopolimero_molecula.reason
        self.assertIn("coste", motivo.lower())
        self.assertIn("decisión", motivo.lower())
        for palabra in ("falta", "no está disponible", "consigue"):
            self.assertNotIn(palabra, motivo.lower(), motivo)

    def test_deja_de_contarse_como_filtro_SIN_CORRER(self):
        """Es lo que se reportó: la columna del export decía que no corrió."""
        self.assertNotIn(MOLECULE_HOMOPOLYMER, self.seleccion.not_run_filters)

    def test_pero_SIGUE_teniendo_veredicto_de_verdad_en_el_panel(self):
        """Control adversario del arreglo: no se ha vuelto NO_PEDIDO para todos."""
        estados = {
            self.seleccion.window_of(c).homopolimero_molecula.state
            for c in self.seleccion.selection.chosen
        }
        self.assertEqual(estados, {FilterState.PASS})


@unittest.skipUnless(HAY and HAY_MASCARA, "faltan el fixture murino o su máscara")
class TestLaVentanaQueNoSePUEDE(unittest.TestCase):
    """Con la máscara puesta hay 66 ventanas con `N`, y ésas SÍ son una laguna."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        mascara = masking.load_rmsk(
            RAIZ / "rmsk_mouse.out", version="test",
            expected_species=RATON.organism, summary_path=RAIZ / "rmsk_mouse.tbl",
        )
        cls.informe = tile_utr(
            secuencia, anatomy=_anatomia(secuencia), mask=mascara,
        )
        cls.con_n = [
            w for w in cls.informe.windows if w.evaluation.asymmetry is None
        ]

    def test_el_caso_existe(self):
        self.assertEqual(len(self.con_n), 66)

    def test_una_ventana_con_N_sigue_siendo_NOT_RUN(self):
        """No se pudo, no es que no se pidiera: sin guía no hay nada que medir."""
        for ventana in self.con_n:
            with self.subTest(ventana.window.start):
                self.assertIs(ventana.homopolimero_molecula.state, FilterState.NOT_RUN)

    def test_y_su_motivo_NO_dice_que_sea_por_COSTE(self):
        """El diagnóstico equivocado que había: «por coste» sobre una base desconocida.

        Principio nº 3 — un mensaje que explica una causa tiene que haberla comprobado.
        Aquí mandaba a mirar un presupuesto cuando lo que hay es una `N`.
        """
        motivo = self.con_n[0].homopolimero_molecula.reason
        self.assertNotIn("coste", motivo.lower(), motivo)
        self.assertIn("N", motivo)
        self.assertIn("NOT_RUN no es PASS", motivo)

    def test_los_DOS_estados_conviven_en_la_MISMA_corrida(self):
        """Que sean dos causas se ve en que dan dos estados sobre el mismo informe."""
        estados = {
            w.homopolimero_molecula.state
            for w in self.informe.windows
            if not biophysical_ok(list(w.evaluation.filters) + [w.zona_prohibida])
        }
        self.assertEqual(estados, {FilterState.NOT_RUN, FilterState.NO_PEDIDO})


if __name__ == "__main__":
    unittest.main()
