"""Tests del CLI que importa scores puntuados a mano.

Regla 5: escritos antes que `tools/import_scores.py`.

Es la otra mitad del bloque de instrucciones del informe: sin un importador, decirle a
alguien que puntue diez guias a mano es decirle que las pegue a mano en un TSV, y ahi es
donde un score acaba en la fila del candidato de al lado.

Sin `--out` no toca el fichero de entrada: escribe en la salida estandar.
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.import_scores import main  # noqa: E402

GUIA = "UAGAUAAGCAUUAUAAUUCCUA"
OTRA = "UAGAUAAGCAUUAUAAUUCCUG"
TABLA = (
    "# cabecera de comentario\n"
    "guia\tveredicto\tscore_externo\tfuente_score\tmirarch_confirmado\t"
    "mirarch_rank\tmirarch_shift_nt\tknockdown_medido\n"
    f"{GUIA}\tINCOMPLETE\t\t\t\t\t\t\n"
    f"{OTRA}\tINCOMPLETE\t\t\t\t\t\t\n"
)


class TestImportScores(unittest.TestCase):

    def setUp(self):
        self.dir = TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.tabla = Path(self.dir.name) / "raton_comparativa.tsv"
        self.tabla.write_text(TABLA, encoding="utf-8")
        self.resultados = Path(self.dir.name) / "resultados.tsv"
        self.resultados.write_text(f"{GUIA}\t0.91\n", encoding="utf-8")

    def corre(self, *extra):
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = main([
                "--fuente", "mirarchitect",
                "--tsv", str(self.resultados),
                "--comparativa", str(self.tabla),
                *extra,
            ])
        return codigo, salida.getvalue()

    def test_escribe_en_la_salida_estandar_y_no_toca_la_entrada(self):
        codigo, salida = self.corre()
        self.assertEqual(codigo, 0)
        self.assertIn("0.910", salida)
        self.assertEqual(self.tabla.read_text(encoding="utf-8"), TABLA)

    def test_con_out_escribe_el_fichero(self):
        destino = Path(self.dir.name) / "con_scores.tsv"
        codigo, _ = self.corre("--out", str(destino))
        self.assertEqual(codigo, 0)
        self.assertIn("manual_mirarchitect", destino.read_text(encoding="utf-8"))

    def test_la_fuente_manual_es_la_que_se_escribe(self):
        _, salida = self.corre()
        self.assertIn("manual_mirarchitect", salida)

    def test_una_guia_que_no_esta_en_la_tabla_falla_sin_escribir_nada(self):
        self.resultados.write_text("UAAAAAAAAAAAAAAAAAAAAA\t0.5\n", encoding="utf-8")
        destino = Path(self.dir.name) / "con_scores.tsv"
        codigo, _ = self.corre("--out", str(destino))
        self.assertEqual(codigo, 2)
        self.assertFalse(destino.exists())

    def test_un_fichero_que_no_existe_falla(self):
        self.resultados.unlink()
        codigo, _ = self.corre()
        self.assertEqual(codigo, 2)

    def test_no_hay_ninguna_fuente_que_no_sea_manual(self):
        # `splashrna_features` no es una fuente importable: seria etiquetar de
        # SplashRNA un numero calculado aqui, que es justo lo prohibido.
        with self.assertRaises(SystemExit):
            main(["--fuente", "splashrna_features", "--tsv", str(self.resultados),
                  "--comparativa", str(self.tabla)])


if __name__ == "__main__":
    unittest.main()
