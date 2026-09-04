"""La guía de una construcción SALE DE LA SELECCIÓN, no de re-recortar una secuencia.

**Reportado (2026-09-04)**, con el panel guardado delante:

    PARA — La guía mide 0 nt y el andamio miR-E lleva brazos de 22 nt

**Y el aborto era la mitad afortunada.** `build_constructions` sacaba la guía haciendo
`target[start - 1:end]`, y la página le pasaba el **3'UTR** (1242 nt) mientras los
`start` del panel están en el marco de **LO TILADO**, que es el transcrito (2191 nt).
Medido sobre el panel murino real:

| start | `utr3[start-1:end]` | ¿es la guía buena? |
|---|---|---|
| 959, 1009, 1092, 1149 | **22 nt** | **NO** — es otro sitio, con la forma correcta |
| 1398, 1502, 1601, 1684, 1768, 1967 | **0 nt** | aborta |

O sea: **cuatro de diez construcciones se habrían montado con la guía equivocada**, con su
md5 correcto, y habrían salido hacia SpliceAI sin que nada lo dijera. Sólo cayeron las
seis que se salen del 3'UTR. Si el panel hubiera estado entero dentro de los 1242 nt,
esto no habría dado ningún error nunca.

**La causa es el principio nº 13**: la guía YA está calculada en la ventana de la
selección, y volver a recortarla de una secuencia que pasa el llamador es una segunda
definición del mismo dato — con un `start` que no lleva marco, cualquier secuencia sirve
de argumento y ninguna se puede comprobar.

Ahora se PIDE a la ventana. El `target` deja de existir: un parámetro que sólo podía
estar mal no se arregla documentándolo.

Regla 5: escritos antes.
"""

import sys
import unittest
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.presentation import page_run  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _corrida():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return page_run(species="raton", sequence=tx, anatomy=anat)


def _sin_guia(seleccion, *, start: int):
    """La misma selección con la guía de UN candidato vaciada.

    No fabrica ninguna secuencia (regla 1): BORRA la que hay, que es exactamente lo que
    el fallo reportado producía de hecho.
    """
    ventanas = {
        etiqueta: (
            replace(v, evaluation=replace(v.evaluation, guide=""))
            if v.window.start == start else v
        )
        for etiqueta, v in seleccion.windows.items()
    }
    return replace(seleccion, windows=ventanas)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaGuiaSaleDeLaVENTANA(unittest.TestCase):
    """El caso REAL: transcrito entero tilado, que es lo que hace la página."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()

    def _construcciones(self):
        return spliceai.build_constructions(
            self.corrida.selection, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD,
        )

    def test_salen_las_DIEZ_con_el_transcrito_entero_tilado(self):
        self.assertEqual(len(self._construcciones()), 10)

    def test_cada_guia_es_la_de_SU_ventana(self):
        for construccion in self._construcciones():
            with self.subTest(construccion.candidate_start):
                ventana = next(
                    self.corrida.selection.window_of(c)
                    for c in self.corrida.selection.selection.chosen
                    if c.start == construccion.candidate_start
                )
                esperada = ventana.evaluation.guide.replace("U", "T")
                self.assertIn(esperada, construccion.sequence)

    def test_NO_existe_ya_el_parametro_que_solo_podia_estar_mal(self):
        import inspect

        firma = inspect.signature(spliceai.build_constructions)
        self.assertNotIn("target", firma.parameters)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestUnaSolaRotaNoTumbaLasDemas(unittest.TestCase):
    """Emitir 19 y decir cuál falta, en vez de abortar las 20 por una."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()

    def test_el_montaje_devuelve_lo_que_SI_pudo_y_lo_que_no(self):
        resultado = spliceai.build_panel(
            self.corrida.selection, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD,
        )
        self.assertEqual(len(resultado.constructions), 10)
        self.assertEqual(resultado.failed, ())

    def test_con_una_guia_VACIA_salen_las_demas_y_se_DICE_cual_falta(self):
        rota = _sin_guia(self.corrida.selection, start=1398)
        resultado = spliceai.build_panel(
            rota, intron_names=("mvm_actual",), scaffold=SGEP_SCAFFOLD,
        )
        self.assertEqual(len(resultado.constructions), 9)
        self.assertEqual(len(resultado.failed), 1)
        fallo = resultado.failed[0]
        # EL MENSAJE DICE DE QUE CANDIDATO Y DE DONDE SE LEYO. «La guía mide 0 nt»
        # invita a pensar que hay una guía mal; lo que hay es una que no ha llegado.
        self.assertEqual(fallo.candidate_start, 1398)
        self.assertIn("1398", fallo.reason)
        self.assertIn("ventana", fallo.reason.lower())

    def test_y_si_NINGUNA_se_puede_montar_ABORTA(self):
        """Cero construcciones no es una entrega parcial: no hay nada que consultar."""
        rotas = self.corrida.selection
        for candidato in rotas.selection.chosen:
            rotas = _sin_guia(rotas, start=candidato.start)
        with self.assertRaises(ShmirDesignError):
            spliceai.build_panel(
                rotas, intron_names=("mvm_actual",), scaffold=SGEP_SCAFFOLD,
            )


class TestElContextoPorDefecto(unittest.TestCase):
    """Un valor por defecto que la propia app desaconseja no puede ser el defecto."""

    def test_no_es_CERO(self):
        from shmir_design.presentation import SPLICE_CONTEXT_DEFAULT

        self.assertGreater(SPLICE_CONTEXT_DEFAULT, 0)

    def test_la_pagina_lo_PIDE_y_no_lo_escribe(self):
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text("utf-8")
        limpia = "\n".join(
            l for l in fuente.split("\n") if not l.lstrip().startswith("#")
        )
        bloque = limpia[limpia.index("Contexto exónico a cada lado"):]
        self.assertIn("SPLICE_CONTEXT_DEFAULT", bloque[:600])


if __name__ == "__main__":
    unittest.main()
