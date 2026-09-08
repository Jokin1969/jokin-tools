"""Las banderas del fragmento y de la comprobación del montaje, de punta a punta.

Regla 5 y principio nº 17: una bandera que cambia un VEREDICTO —y éstas cambian qué ADN
se manda a sintetizar— tiene que recorrerse ENTERA en algún test. Que exista un test que
la nombre no basta: la errata nº 31 tenía llamador.

Aquí se corre `main()` de verdad, se comprueba que termina en 0 y se LEE lo que escribió.
"""

import tempfile
import unittest
from pathlib import Path

from tools.comprobar_montaje import main as montaje_main
from tools.design import main as design_main

RAIZ = Path(__file__).resolve().parent.parent
DIR = RAIZ / "data" / "reference"
CASETE = DIR / "aav_casete.fa"
RATON = DIR / "NM_011170.3.fa"
GENBANK = DIR / "NM_011170.3.gb"


@unittest.skipUnless(
    CASETE.is_file() and RATON.is_file() and GENBANK.is_file(),
    "NOT_RUN: faltan los ficheros de referencia del ratón o el casete",
)
class TestElFragmentoPorLineaDeOrdenes(unittest.TestCase):

    def correr(self, extra):
        salida = Path(tempfile.mkdtemp()) / "salida"
        codigo = design_main(
            ["--fasta", str(RATON), "--genbank", str(GENBANK), "--name", "mouse",
             "--out", str(salida), "--bloques",
             "--transgen", str(CASETE),
             "--transgen-version", "pAAV parental, fichero versionado"] + extra
        )
        return codigo, salida

    def test_por_defecto_el_fragmento_sale_SIN_los_sitios(self):
        codigo, salida = self.correr(["--fragmento-intron", "mvm_actual"])
        self.assertEqual(codigo, 0)
        fasta = (salida / "mouse_fragmentos.fasta").read_text(encoding="utf-8")
        self.assertIn("sitios=fuera", fasta)
        self.assertIn("longitud=294", fasta)
        self.assertIn("crece=202", fasta)
        # Y la hoja dice dónde se pega y con qué extremos.
        hoja = (salida / "mouse_fragmentos.txt").read_text(encoding="utf-8")
        self.assertIn("3129-3220", hoja)
        self.assertIn("AAGAGGTAAGGGTTT", hoja)

    def test_con_sitios_son_12_nt_mas(self):
        codigo, salida = self.correr(["--fragmento-con-sitios"])
        self.assertEqual(codigo, 0)
        fasta = (salida / "mouse_fragmentos.fasta").read_text(encoding="utf-8")
        self.assertIn("sitios=dentro", fasta)
        self.assertIn("longitud=306", fasta)
        self.assertIn("crece=214", fasta)


@unittest.skipUnless(
    CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa"
)
class TestLaComprobacionDelMontajePorLineaDeOrdenes(unittest.TestCase):

    def preparar(self):
        from shmir_design import fragmento
        from shmir_design.scaffold import build_hairpin

        crudo = CASETE.read_text(encoding="utf-8").splitlines()
        casete = "".join(l.strip() for l in crudo if not l.startswith(">")).upper()
        frag = fragmento.build_fragment(
            build_hairpin("TTTAGTACTGGATGGAACGGCC"),
            cassette=casete, label="3utr:1018",
        )
        directorio = Path(tempfile.mkdtemp())
        (directorio / "fragmentos.fasta").write_text(
            fragmento.fragments_fasta([frag], species="mouse"), encoding="utf-8"
        )
        (directorio / "montado.fa").write_text(
            ">montado\n" + frag.feature.paste(frag.sequence) + "\n", encoding="utf-8"
        )
        return directorio, frag

    def test_un_montaje_correcto_sale_en_cero(self):
        directorio, _ = self.preparar()
        codigo = montaje_main(
            ["--plasmido", str(directorio / "montado.fa"),
             "--fragmentos", str(directorio / "fragmentos.fasta")]
        )
        self.assertEqual(codigo, 0)

    def test_el_intron_previo_se_puede_declarar(self):
        """La bandera existe para un vector cuyo intrón anterior NO es el parental."""
        directorio, frag = self.preparar()
        codigo = montaje_main(
            ["--plasmido", str(directorio / "montado.fa"),
             "--fragmentos", str(directorio / "fragmentos.fasta"),
             "--intron-previo", "GTAAGTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTAG"]
        )
        self.assertEqual(codigo, 0)

    def test_antes_de_pegar_sobre_el_plasmido_QUE_TOCA_sale_en_cero(self):
        directorio, _ = self.preparar()
        codigo = montaje_main(
            ["--plasmido", str(CASETE),
             "--fragmentos", str(directorio / "fragmentos.fasta"),
             "--antes-de-pegar"]
        )
        self.assertEqual(codigo, 0)

    def test_y_la_cruzada_sin_declarar_sale_en_UNO(self):
        from shmir_design import fragmento, introns

        directorio, frag = self.preparar()
        feature = frag.feature
        (directorio / "receptor_quimerico.fa").write_text(
            ">receptor\n"
            + feature.paste(
                feature.exon5
                + introns.get("intron_quimerico").empty_sequence
                + feature.exon3
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(
            montaje_main(
                ["--plasmido", str(directorio / "receptor_quimerico.fa"),
                 "--fragmentos", str(directorio / "fragmentos.fasta"),
                 "--antes-de-pegar"]
            ),
            1,
        )
        # Declarado, la misma sustitución PASA: es cómo se cambia de arquitectura.
        self.assertEqual(
            montaje_main(
                ["--plasmido", str(directorio / "receptor_quimerico.fa"),
                 "--fragmentos", str(directorio / "fragmentos.fasta"),
                 "--antes-de-pegar", "--cambio-de-arquitectura"]
            ),
            0,
        )

    def test_un_montaje_con_el_intron_viejo_dentro_sale_en_UNO(self):
        directorio, frag = self.preparar()
        crudo = CASETE.read_text(encoding="utf-8").splitlines()
        casete = "".join(l.strip() for l in crudo if not l.startswith(">")).upper()
        mal = (
            casete[: frag.feature.end] + frag.sequence + casete[frag.feature.end :]
        )
        (directorio / "mal.fa").write_text(">mal\n" + mal + "\n", encoding="utf-8")
        codigo = montaje_main(
            ["--plasmido", str(directorio / "mal.fa"),
             "--fragmentos", str(directorio / "fragmentos.fasta")]
        )
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
