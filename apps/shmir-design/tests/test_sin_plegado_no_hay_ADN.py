"""Sin ViennaRNA, la app NO emite ADN sintetizable.

**El fallo, y su forma.** La imagen de produccion no instala ViennaRNA. El nucleo esta
escrito para eso —`check_fold` devuelve `NOT_RUN`, nunca `PASS`, y el diseño sigue— pero
la regla de la PASAJERA no se degrada igual: `passenger_from_guide` elige la base de la
posicion 1 PLEGANDO contra SGEP, y sin plegado cae a la regla de reserva, que es
**exactamente la tabla por terminacion que este proyecto descarto por escrito** (le
faltaba el apareamiento tambaleante G:U, asi que con guia acabada en G elige mal).

Y esa pasajera **va dentro del modulo de 149 nt**, que es lo que se manda a sintetizar.
Un `NOT_RUN` que produce ADN sintetizable no es un `NOT_RUN`: es un `PASS` con letra
pequeña.

**La regla que deja**: un entorno sin una dependencia no falla, DEGRADA — y aqui degrado
a la regla que el proyecto ya habia descartado. Lo que se comprueba no es que la
dependencia este: es que su ausencia **impida** lo que no se puede hacer sin ella.
"""

import builtins
import unittest

from shmir_design import folding, presentation
from shmir_design.errors import ShmirDesignError


class _SinVienna:
    """Simula la imagen de produccion: el import de `RNA` falla."""

    def __enter__(self):
        self._real = builtins.__import__

        def sin_rna(name, *a, **k):
            if name == "RNA" or name.startswith("RNA."):
                raise ImportError("simulado: la imagen no instala ViennaRNA")
            return self._real(name, *a, **k)

        builtins.__import__ = sin_rna
        return self

    def __exit__(self, *exc):
        builtins.__import__ = self._real
        return False


class TestLaCAPACIDADseDECLARA(unittest.TestCase):
    """Es una capacidad AUSENTE DEL ENTORNO, no un fichero que falte."""

    def test_aqui_esta_disponible(self):
        self.assertTrue(presentation.folding_capability()["disponible"])

    def test_y_cuando_no_lo_esta_se_DICE(self):
        with _SinVienna():
            estado = presentation.folding_capability(available=False)
        self.assertFalse(estado["disponible"])
        self.assertTrue(estado["texto"])

    def test_el_texto_dice_QUE_SE_PIERDE_no_solo_que_falta(self):
        texto = presentation.folding_capability(available=False)["texto"].lower()
        self.assertIn("pasajera", texto)

    def test_y_la_pagina_lo_pinta_en_la_CABECERA(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("folding_capability", fuente)


class TestSinPLEGADOnoSeEMITEelMODULO(unittest.TestCase):

    def test_el_gBlock_ABORTA_sin_ViennaRNA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            presentation.check_can_emit_dna(available=False)
        mensaje = str(caja.exception).lower()
        self.assertIn("pasajera", mensaje)

    def test_y_con_ViennaRNA_no_aborta(self):
        presentation.check_can_emit_dna(available=True)

    def test_por_defecto_mira_el_ENTORNO(self):
        # Sin argumento decide `folding.VIENNA_AVAILABLE`, que es lo que hay de verdad.
        presentation.check_can_emit_dna()
        self.assertTrue(folding.VIENNA_AVAILABLE)

    def test_el_DISEÑO_sigue_funcionando_sin_plegado(self):
        """Lo que se prohibe es EMITIR ADN, no diseñar.

        El nucleo esta escrito para correr sin ViennaRNA y eso no se toca: si abortara
        el pipeline entero, la app dejaria de servir para lo unico que hoy hace bien.
        """
        with _SinVienna():
            from shmir_design.hard_filters import Thresholds

            self.assertTrue(Thresholds())


if __name__ == "__main__":
    unittest.main()
