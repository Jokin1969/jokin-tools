"""Un candidato «nuevo» de una fuente externa puede ser un sitio ya cogido.

Regla 5: escritos antes.

223 y 221 son dos ventanas corridas 2 nt. Bajo la regla de espaciado del proyecto —50 nt
entre posiciones de inicio— son EL MISMO SITIO, aunque las guias sean distintas y la
fuente externa las liste como dos entradas. Presentar 223 como un candidato nuevo seria
contar dos veces la misma plaza del panel.

El agrupador tiene que detectarlo y avisar, no descartarlo en silencio: puede que
interese cambiar 221 por 223, y para eso hay que ver que compiten.
"""

import unittest
from pathlib import Path

from shmir_design.spacing import SITE_SPACING, same_site, site_conflicts

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


class TestMismoSitio(unittest.TestCase):

    def test_dos_ventanas_a_2_nt_son_el_mismo_sitio(self):
        self.assertTrue(same_site(221, 223, spacing=SITE_SPACING))

    def test_dos_ventanas_a_50_nt_todavia_lo_son(self):
        # El espaciado es el MINIMO exigido: a exactamente 50 no se cumple.
        self.assertTrue(same_site(221, 271, spacing=50))

    def test_a_51_nt_ya_son_sitios_distintos(self):
        self.assertFalse(same_site(221, 272, spacing=50))

    def test_da_igual_el_orden(self):
        self.assertEqual(same_site(221, 223, spacing=50), same_site(223, 221, spacing=50))

    def test_el_espaciado_por_defecto_es_el_del_proyecto(self):
        self.assertEqual(SITE_SPACING, 50)


class TestConflictos(unittest.TestCase):

    def test_detecta_el_choque_de_223_con_221(self):
        conflictos = site_conflicts(
            candidates={223: "TGTTATATTCTTATTGGCCCGG"},
            selected={221: "TTATATTCTTATTGGCCCGGTG"},
        )
        self.assertEqual(len(conflictos), 1)
        self.assertEqual(conflictos[0].candidate_start, 223)
        self.assertEqual(conflictos[0].selected_start, 221)
        self.assertEqual(conflictos[0].distance, 2)

    def test_no_inventa_conflictos_donde_no_los_hay(self):
        self.assertEqual(
            site_conflicts(candidates={765: "x"}, selected={221: "y"}), ()
        )

    def test_un_candidato_puede_chocar_con_varios(self):
        conflictos = site_conflicts(
            candidates={230: "x"}, selected={221: "a", 260: "b"}
        )
        self.assertEqual(len(conflictos), 2)

    def test_el_aviso_dice_que_NO_es_un_descarte(self):
        conflicto = site_conflicts(
            candidates={223: "TGTTATATTCTTATTGGCCCGG"},
            selected={221: "TTATATTCTTATTGGCCCGGTG"},
        )[0]
        self.assertIn("no se descarta", conflicto.message.lower())

    def test_y_dice_las_dos_guias_para_poder_elegir(self):
        conflicto = site_conflicts(
            candidates={223: "TGTTATATTCTTATTGGCCCGG"},
            selected={221: "TTATATTCTTATTGGCCCGGTG"},
        )[0]
        self.assertIn("TGTTATATTCTTATTGGCCCGG", conflicto.message)
        self.assertIn("TTATATTCTTATTGGCCCGGTG", conflicto.message)


@unittest.skipUnless(
    (DIR / "mirarchitect_prnp_export_buena.csv").is_file()
    and (DIR / "NM_011170.3.fa").is_file(),
    "NOT_RUN: faltan los fixtures",
)
class TestSobreLaCorridaReal(unittest.TestCase):

    def test_223_choca_con_221_en_el_dato_de_verdad(self):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.mirarchitect import parse_export
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(
            (DIR / "NM_011170.3.fa").read_text(encoding="utf-8"), source="fa"
        )
        utr3 = normalize_sequence(bruta, name="NM_011170.3")[949:]
        export = parse_export(
            (DIR / "mirarchitect_prnp_export_buena.csv").read_text(encoding="utf-8-sig")
        )
        sitios = {
            utr3.find(f.target) + 1: f.guide
            for f in export.rows
            if utr3.find(f.target) >= 0
        }
        conflictos = site_conflicts(candidates=sitios, selected={221: sitios[221]})
        chocan = {c.candidate_start for c in conflictos}
        self.assertIn(223, chocan)
        self.assertNotIn(765, chocan)


if __name__ == "__main__":
    unittest.main()
