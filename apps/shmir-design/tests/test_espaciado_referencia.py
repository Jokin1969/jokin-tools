"""Contra QUE se compara una plaza «nueva» — y que la salida lo diga.

Regla 5: escritos antes de tocar `spacing.py`.

Las «7 plazas nuevas» que salieron del cruce con miRarchitect se calcularon contra los
SEIS candidatos elegidos, no contra la tabla completa de candidatos. Con esa referencia,
casi cualquier sitio externo parece nuevo: seis posiciones no cubren 1242 nt. Contra el
conjunto completo la cuenta es otra, y el numero no significa nada si no se dice contra
que se ha medido.

Asi que la referencia es OBLIGATORIA y se ETIQUETA: la salida nombra el conjunto y su
tamaño. Un «4 plazas nuevas» sin eso no es un resultado, es una cifra suelta.

Datos reales: el 3'UTR verificado de NM_011170.3 y el export bueno de miRarchitect.
"""

import unittest
from pathlib import Path

from shmir_design.coords import Frame
from shmir_design.spacing import (
    SITE_SPACING,
    ReferenceSet,
    compare_sites,
    same_site,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"
EXPORT = DIR / "mirarchitect_prnp_export_buena.csv"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


class TestLaReferenciaEsObligatoria(unittest.TestCase):

    def test_un_conjunto_de_referencia_sin_etiqueta_aborta(self):
        with self.assertRaises(ValueError):
            ReferenceSet(label="", starts={221: "x"}, frame=Frame.UTR3)

    def test_la_etiqueta_sale_en_la_salida(self):
        referencia = ReferenceSet(
            label="los 6 candidatos elegidos", starts={221: "x"}, frame=Frame.UTR3
        )
        comparacion = compare_sites(candidates={223: "y"}, reference=referencia)
        self.assertIn("los 6 candidatos elegidos", comparacion.describe())

    def test_la_salida_dice_cuantos_hay_en_la_referencia(self):
        referencia = ReferenceSet(
            label="los 6 candidatos elegidos",
            starts={221: "x", 449: "z"},
            frame=Frame.UTR3,
        )
        comparacion = compare_sites(candidates={223: "y"}, reference=referencia)
        self.assertIn("2", comparacion.describe())

    def test_las_posiciones_van_con_su_espacio(self):
        referencia = ReferenceSet(
            label="referencia", starts={221: "x"}, frame=Frame.UTR3
        )
        comparacion = compare_sites(candidates={223: "y"}, reference=referencia)
        self.assertIn("3utr:223", comparacion.describe())
        self.assertIn("3utr:221", comparacion.describe())


@unittest.skipUnless(
    RATON.is_file() and EXPORT.is_file(),
    "NOT_RUN: faltan los fixtures de la corrida murina",
)
class TestLasPlazasNuevasDependenDeLaReferencia(unittest.TestCase):
    """El mismo cruce da 7 plazas o ninguna segun contra que se compare."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.mirarchitect import parse_export
        from shmir_design.selection import (
            SelectionConfig,
            select_from_report,
        )
        from shmir_design.tiling import tile_utr

        cls.utr3 = _utr3()
        tiling = tile_utr(cls.utr3)
        cls.seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
        export = parse_export(EXPORT.read_text(encoding="utf-8"), source="buena")
        tabla = str.maketrans("ACGT", "TGCA")
        cls.externos = {}
        for fila in export.rows:
            diana = fila.guide.translate(tabla)[::-1]
            indice = cls.utr3.find(diana)
            if indice != -1:
                cls.externos[indice + 1] = fila.guide

    def _referencia(self, label, starts):
        return ReferenceSet(label=label, starts=starts, frame=Frame.UTR3)

    def test_contra_los_6_elegidos_salen_7_plazas(self):
        elegidos = {
            c.start: self.seleccion.window_of(c).evaluation.guide
            for c in self.seleccion.selection.chosen
        }
        comparacion = compare_sites(
            candidates=self.externos,
            reference=self._referencia("los 6 candidatos elegidos", elegidos),
        )
        self.assertEqual(len(comparacion.new_plazas), 7)

    def test_contra_la_tabla_COMPLETA_solo_sobrevive_1200(self):
        # 90 sitios elegibles cubren el 3'UTR mucho mas densamente que 6 posiciones: de
        # las 7 plazas que salian contra los elegidos no queda ninguna, y el unico
        # externo sin choque es el 1200 — que no tiene ningun sitio nuestro cerca
        # porque ahi NO HAY ninguna ventana elegible: la zona esta tumbada por polyA.
        todos = {
            sitio.best.start: self.seleccion.windows[sitio.best.label].evaluation.guide
            for sitio in self.seleccion.selection.sites
        }
        comparacion = compare_sites(
            candidates=self.externos,
            reference=self._referencia("los 90 sitios elegibles", todos),
        )
        self.assertEqual(comparacion.new_plazas, (1200,))

    def test_y_el_1200_no_pasa_nuestros_filtros_duros(self):
        # Asi que «plaza nueva» no significa «plaza utilizable»: son dos preguntas y el
        # espaciado solo contesta la primera.
        from shmir_design.selection import is_eligible

        ventana = [
            w for w in self.seleccion.windows.values() if w.window.start == 1200
        ][0]
        self.assertFalse(is_eligible(ventana))
        fallos = [r.name for r in ventana.filters if r.state.value == "FAIL"]
        self.assertIn("zona_prohibida_polyA", fallos)

    def test_735_es_EXACTAMENTE_una_ventana_nuestra(self):
        # No es que este cerca: es la misma ventana, base a base.
        self.assertIn(735, self.externos)
        self.assertEqual(self.utr3[734:756], self.externos_diana(735))

    def externos_diana(self, inicio):
        tabla = str.maketrans("ACGT", "TGCA")
        return self.externos[inicio].translate(tabla)[::-1]

    def test_337_choca_con_329_y_765_con_735(self):
        todos = {
            sitio.best.start: self.seleccion.windows[sitio.best.label].evaluation.guide
            for sitio in self.seleccion.selection.sites
        }
        comparacion = compare_sites(
            candidates={337: self.externos[337], 765: self.externos[765]},
            reference=self._referencia("los 90 sitios elegibles", todos),
        )
        choques = {
            (c.candidate_start, c.reference_start, c.distance)
            for c in comparacion.conflicts
        }
        self.assertIn((337, 329, 8), choques)
        self.assertIn((765, 735, 30), choques)

    def test_la_salida_no_da_una_cifra_sin_decir_contra_que(self):
        comparacion = compare_sites(
            candidates=self.externos,
            reference=self._referencia("los 6 candidatos elegidos", {60: "x"}),
        )
        texto = comparacion.describe()
        self.assertIn("los 6 candidatos elegidos", texto)
        # Y avisa de que la cifra depende de la referencia.
        self.assertIn("referencia", texto.lower())


if __name__ == "__main__":
    unittest.main()
