"""La tarjeta que dice quién falta los nombraba con un entero desnudo.

**Salió el 2026-09-07 contestando a esta pregunta**: *«¿qué frentes le faltan a
`3utr:359`? Lo que necesito saber para no gastar corridas de más»*. La respuesta está en
la tarjeta del frente —`run_coverage` dice cuántos del panel cubre y **nombra a los que
no**— y sobre un tilado del transcrito los nombraba así:

    Faltan: 1308, 2020

**1308 es `tx:1308`, o sea `3utr:359`**. Escrito a secas se lee como una posición del
3'UTR, que es otra ventana con otro veredicto — exactamente la conversación equivocada que
`coords` existe para impedir, y es lo que se leyó el 2026-09-07 al citar `3utr:959` en una
retirada que era de `3utr:10` (errata nº 133).

**Y es la OTRA forma de la errata nº 138, la que sus dos guardias no ven.** Allí la
etiqueta se fabricaba con el marco equivocado; aquí no se fabrica ninguna: `str(inicio)`
se salta `coords` entero. `Position` impide imprimir un entero desnudo **cuando es una
`Position`**; un `int` que cruza una frontera de función como `starts` no lo es, y `str()`
no pregunta nada. Es el principio nº 50: un literal —aquí, una conversión— no puede fallar.

**El barrido, medido** (principio nº 34): `join(str(` da **52** posiciones en el paquete y
casi todas son `"".join(str(x).split())`, o sea normalizar una secuencia. Las que nombran
posiciones del PANEL son **cinco**, y son las de aquí. Un guardia mecánico sobre esa forma
tendría que separar «lista para una persona» de «normalizar una cadena» y de listas que no
son posiciones —números de sección, cisteínas, longitudes en nt—, así que hoy **no lo
hay**: lo que hay es esta regresión sobre las cinco, y queda dicho que no hay red debajo.

Regla 5: escrito antes.
"""

import re
import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.coords import Frame, tiled_frame
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_reference

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: Un entero de tres o cuatro cifras suelto, sin `tx:` ni `3utr:` delante. Es lo que hay
#: que no encontrar: la etiqueta va PEGADA al número (`coords`), así que un número de
#: posición sin prefijo es el fallo.
DESNUDO = re.compile(r"(?<![\w:])\d{3,4}(?![\w])")


def _corrida():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    return presentation.page_run(species="raton", sequence=secuencia, anatomy=anatomia)


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaTarjetaNombraALosQueFaltanCONsuMarco(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = sorted(presentation.chosen_starts(cls.corrida.selection))
        cls.marco = tiled_frame(cls.corrida.selection.anatomy)

    def test_lo_tilado_es_el_TRANSCRITO(self):
        # Sobre el 3'UTR pelado los dos marcos coinciden y este test no probaría nada.
        self.assertIs(self.marco, Frame.TX)

    def test_los_que_faltan_van_ETIQUETADOS(self):
        # Cobertura a medias: el frente contesta a todos menos a los dos últimos, que es
        # la forma exacta del caso — una corrida del panel anterior.
        cubiertos = {inicio: "PASS" for inicio in self.panel[:-2]}
        fila = presentation.run_coverage(
            {"empalme_sitios": cubiertos}, starts=self.panel, frame=self.marco,
        )["empalme_sitios"]
        for inicio in self.panel[-2:]:
            with self.subTest(inicio):
                self.assertIn(f"tx:{inicio}", fila["avance"])

    def test_y_NINGUN_entero_desnudo(self):
        cubiertos = {inicio: "PASS" for inicio in self.panel[:-2]}
        fila = presentation.run_coverage(
            {"empalme_sitios": cubiertos}, starts=self.panel, frame=self.marco,
        )["empalme_sitios"]
        # Se quitan las etiquetas antes de buscar: lo que queda no puede tener números
        # de posición. Los recuentos («9 de 11») son de una cifra o dos.
        sin_etiquetas = re.sub(r"(tx|3utr):\d+", "", fila["avance"])
        self.assertEqual(DESNUDO.findall(sin_etiquetas), [])


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLosTresABORTOSquenombranElPanel(unittest.TestCase):
    """Los mensajes que listan el panel para decir que algo no está en él."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.marco = tiled_frame(cls.corrida.selection.anatomy)

    def _sin_etiquetas(self, texto: str) -> list[str]:
        return DESNUDO.findall(re.sub(r"(tx|3utr):\d+", "", texto))

    def test_candidate_fronts_de_uno_que_no_esta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            presentation.candidate_fronts(
                self.corrida.tiling, self.corrida.selection, start=99999,
                species="raton",
            )
        self.assertIn("tx:", str(caja.exception))
        self.assertEqual(self._sin_etiquetas(str(caja.exception)), [])

    def test_immune_replacements_de_uno_que_no_esta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            presentation.immune_replacements(
                self.corrida.tiling, self.corrida.selection, retire=99999,
            )
        self.assertIn("tx:", str(caja.exception))
        self.assertEqual(self._sin_etiquetas(str(caja.exception)), [])

    def test_choices_for_de_un_inicio_que_no_es_elegible(self):
        with self.assertRaises(ShmirDesignError) as caja:
            self.corrida.selection.choices_for({99999})
        motivo = str(caja.exception)
        self.assertIn("tx:", motivo)
        # Aquí se mira SÓLO el tramo que enumera posiciones: el resto del mensaje lleva
        # RECUENTOS de tres cifras («los 270 sitios elegibles») y un recuento no es una
        # posición. Un barrido que no los distinguiera daría un falso positivo, y un
        # guardia con falsos positivos se acaba apagando (principio nº 34).
        enumerado = motivo[motivo.index("empiece en ") : motivo.index(":")]
        self.assertEqual(self._sin_etiquetas(enumerado), [])


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaPaginaNoMontaLaLista(unittest.TestCase):
    """Regla 6: el texto de la selección guardada lo decide `presentation`."""

    def test_la_pagina_no_junta_inicios_a_mano(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("join(str(s) for s in guardada)", fuente)

    def test_y_presentation_la_da_ETIQUETADA(self):
        corrida = _corrida()
        texto = presentation.saved_selection_note(
            (1009, 1092), selection=corrida.selection
        )
        self.assertIn("tx:1009", texto)
        self.assertIn("tx:1092", texto)

    def test_sin_seleccion_guardada_NO_dice_nada(self):
        corrida = _corrida()
        self.assertEqual(
            presentation.saved_selection_note((), selection=corrida.selection), ""
        )


if __name__ == "__main__":
    unittest.main()
