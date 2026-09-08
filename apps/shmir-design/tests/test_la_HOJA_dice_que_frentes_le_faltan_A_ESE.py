"""Cada fragmento dice EN SU FILA que frentes tiene sin correr.

Pedido por el responsable del proyecto (2026-09-06) con el caso delante: el undecimo del
panel, `tx:2020`, entro DESPUES de las corridas de BLAST, de empalme y de seed. Con sus
palabras:

    «Un candidato sin BLAST en una hoja de once verificados es exactamente el hueco
     donde se cuela algo asi.»

Y «asi» tiene nombre: `tx:1746` contra **Adar**, el unico candidato que ha caido nunca por
un motivo real, y lo atrapo justamente el frente de especificidad. Una nota general al
principio de la hoja NO sirve: se lee una vez, y la fila de cada fragmento se lee y se
copia por separado — es el mismo motivo por el que el estado del panel viaja DENTRO del
FASTA y en cada linea `>` (principio nº 35: un nombre se pierde en el primer `mv`).

LA DISTINCION QUE NO SE PUEDE COLAPSAR: `fronts=None` es «nadie ha preguntado» y
`fronts=()` es «se pregunto y no falta ninguno». Con un `= ()` por defecto las dos darian
la MISMA hoja —sin ninguna linea de aviso— y la que no se comprobo se leeria como la
limpia. Es la trampa de `BreakChoice.folding_ok` (principio nº 19) sobre lo que se manda a
sintetizar.
"""

import unittest
from pathlib import Path

from shmir_design import fragmento, presentation, reference, resolve
from shmir_design.scaffold import SGEP_SCAFFOLD, build_hairpin

RAIZ = Path(__file__).resolve().parents[1]
FASTA = RAIZ / "data" / "reference" / "NM_011170.3.fa"
GB = RAIZ / "data" / "reference" / "NM_011170.3.gb"
CASETE = RAIZ / "data" / "reference" / "aav_casete.fa"

#: El undecimo del panel, el que motiva todo esto.
UNDECIMO = 2020


def _corrida():
    _, secuencia = reference.parse_fasta_payload(
        FASTA.read_text(encoding="utf-8"), source=FASTA.name
    )
    anatomia = resolve.resolve_anatomy(name="raton", sequence=secuencia, genbank=GB)
    return presentation.page_run(species="raton", sequence=secuencia, anatomy=anatomia)


@unittest.skipUnless(
    FASTA.is_file() and GB.is_file() and CASETE.is_file(), "faltan fixtures"
)
class TestLosFrentesDeCadaCandidato(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.frentes = presentation.candidate_fronts(
            cls.corrida.tiling, cls.corrida.selection,
            species="raton", start=UNDECIMO,
        )

    def test_el_undecimo_tiene_frentes_sin_correr(self):
        """Control adversario del propio dato: si saliera vacio, la hoja no probaria
        nada — «ninguno abierto» y «no se miro» darian la misma linea."""
        self.assertTrue(self.frentes)

    def test_y_especificidad_es_uno_de_ellos(self):
        # Es el frente que atrapo a `tx:1746` contra Adar. Sin `refseq_rna.fa` ni corrida
        # guardada, ningun candidato lo tiene contestado — el undecimo tampoco.
        self.assertIn("especificidad", {f["frente"] for f in self.frentes})

    def test_cada_uno_dice_su_estado_y_su_motivo(self):
        for frente in self.frentes:
            self.assertTrue(frente["estado"], frente)
            self.assertTrue(frente["motivo"], frente)

    def test_los_ONCE_se_pueden_preguntar_uno_a_uno(self):
        """No es una vista del panel: es POR CANDIDATO, que es la unidad de la fila."""
        for eleccion in self.corrida.selection.selection.chosen:
            frentes = presentation.candidate_fronts(
                self.corrida.tiling, self.corrida.selection,
                species="raton", start=eleccion.start,
            )
            self.assertIsInstance(frentes, tuple)


@unittest.skipUnless(
    FASTA.is_file() and GB.is_file() and CASETE.is_file(), "faltan fixtures"
)
class TestLaHojaLoDICE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        _, cls.casete = reference.parse_fasta_payload(
            CASETE.read_text(encoding="utf-8"), source=CASETE.name
        )
        eleccion = next(
            c for c in cls.corrida.selection.selection.chosen if c.start == UNDECIMO
        )
        ventana = cls.corrida.selection.window_of(eleccion)
        cls.horquilla = build_hairpin(
            ventana.evaluation.guide.replace("U", "T"),
            scaffold=SGEP_SCAFFOLD,
        )
        cls.frentes = presentation.candidate_fronts(
            cls.corrida.tiling, cls.corrida.selection,
            species="raton", start=UNDECIMO,
        )

    def _hoja(self, fronts):
        # La hoja va ajustada a 92 columnas, asi que una frase larga sale partida: se
        # compara con los blancos normalizados. Lo que se prueba es que la frase ESTA,
        # no como quedo maquetada.
        hoja = fragmento.fragment_order_sheet(
            fragmento.build_fragment(
                self.horquilla, cassette=self.casete,
                label="tx:2020", fronts=fronts,
            )
        )
        return " ".join(hoja.split())

    def test_con_los_frentes_la_hoja_los_NOMBRA(self):
        hoja = self._hoja(self.frentes)
        for frente in self.frentes:
            self.assertIn(frente["frente"], hoja)

    def test_SIN_preguntar_la_hoja_NO_dice_que_esten_limpios(self):
        """`None` es «nadie ha preguntado» y tiene que verse como tal."""
        hoja = self._hoja(None)
        self.assertIn(" ".join(fragmento.FRONTS_NOT_ASKED.split()), hoja)

    def test_y_con_CERO_frentes_abiertos_lo_dice_CON_OTRA_frase(self):
        """`()` es «se preguntó y no falta ninguno». Si las dos frases fueran la misma,
        no haberlo comprobado y haberlo comprobado limpio darian la misma hoja."""
        hoja = self._hoja(())
        self.assertNotIn(" ".join(fragmento.FRONTS_NOT_ASKED.split()), hoja)
        self.assertIn(" ".join(fragmento.FRONTS_ALL_ANSWERED.split()), hoja)

    def test_las_dos_frases_son_DISTINTAS(self):
        self.assertNotEqual(fragmento.FRONTS_NOT_ASKED, fragmento.FRONTS_ALL_ANSWERED)


if __name__ == "__main__":
    unittest.main()
