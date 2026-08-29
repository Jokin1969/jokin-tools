"""`EVIDENCE` deja de transcribir numeros: los LEE del export versionado.

Por que hay un test propio para esto. Los pares (puesto, score) de
`external_score.EVIDENCE` estaban escritos a mano en el modulo, y el fichero del que
salian tambien esta en el repositorio: dos definiciones del mismo dato, que es el cuarto
par duplicado del proyecto. Y al cruzarlas se vio lo que un par duplicado siempre acaba
enseñando — que NO coincidian:

  - los cinco pares transcritos cuadran, uno a uno, con `mirarchitect_prnp_raton.tsv`;
  - ese fichero lo marca el manifiesto con «NO USAR»: se puntuo sobre el 3'UTR
    FABRICADO de 1246 nt, que es la errata nº 5 del registro;
  - `mirarchitect_prnp_export_buena.csv` —la corrida sobre el 3'UTR VERIFICADO— da
    otros numeros en esos mismos puestos.

O sea que la evidencia de la direccion de la escala estaba anclada a una corrida
retirada, y nadie lo iba a ver porque la copia de codigo es la que se lee. La DIRECCION
no se mueve —los tres ficheros vienen crecientes en el score— pero eso es suerte, no
argumento: si la corrida retirada hubiera venido al reves, la constante habria
registrado la direccion contraria con cinco pares de aval.

Estos tests fijan las tres cosas: de que fichero sale, que sale de LEERLO, y que la
direccion derivada del fichero es la registrada.
"""

import csv
import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.external_score import (
    EVIDENCE,
    MANUAL_EVIDENCE_FILE,
    ScoreSource,
    file_order_direction,
    read_evidence_pairs,
)
from shmir_design.manifest import MANIFEST_NAME, load_manifest

REFERENCIA = Path(__file__).resolve().parent.parent / "data" / "reference"

#: El fichero al que apuntaban los pares transcritos, y que NO puede volver a ser el
#: ancla. Se nombra aqui para que quitarlo del manifiesto haga fallar este test.
RETIRADO = "mirarchitect_prnp_raton.tsv"

#: Los cinco pares que estaban escritos a mano en `EVIDENCE` hasta 2026-08-27.
PARES_TRANSCRITOS = ((3, 10.01), (7, 10.89), (12, 12.99), (13, 13.09), (22, 62.59))


def _scores_del_csv(nombre: str) -> list[float]:
    with (REFERENCIA / nombre).open(newline="", encoding="utf-8") as fh:
        return [float(fila["Score"]) for fila in csv.DictReader(fh)]


def _scores_del_tsv(nombre: str) -> list[float]:
    lineas = (REFERENCIA / nombre).read_text(encoding="utf-8").splitlines()
    return [float(l.split("\t")[1]) for l in lineas[1:] if l.strip()]


class TestDeDondeSaleLaEvidencia(unittest.TestCase):

    def test_el_ancla_es_el_export_de_la_corrida_BUENA(self):
        self.assertEqual(MANUAL_EVIDENCE_FILE, "mirarchitect_prnp_export_buena.csv")

    def test_el_ancla_esta_en_el_manifiesto(self):
        # Sin linea en el manifiesto no hay md5 ni procedencia, y entonces la evidencia
        # vuelve a ser un numero sin origen comprobable.
        manifiesto = load_manifest(REFERENCIA / MANIFEST_NAME)
        manifiesto.entry(MANUAL_EVIDENCE_FILE)

    def test_los_pares_SALEN_del_fichero_y_no_de_una_transcripcion(self):
        esperados = tuple(
            (puesto, score)
            for puesto, score in enumerate(_scores_del_csv(MANUAL_EVIDENCE_FILE), 1)
        )
        self.assertEqual(EVIDENCE[ScoreSource.MANUAL_MIRARCHITECT].pairs, esperados)

    def test_salen_TODAS_las_filas_no_una_muestra(self):
        self.assertEqual(
            len(EVIDENCE[ScoreSource.MANUAL_MIRARCHITECT].pairs),
            len(_scores_del_csv(MANUAL_EVIDENCE_FILE)),
        )

    def test_una_fuente_sin_evidencia_propia_da_cero_pares_y_no_inventa(self):
        evidencia = EVIDENCE[ScoreSource.MIRARCHITECT_API]
        self.assertIsNone(evidencia.evidence_file)
        self.assertEqual(evidencia.pairs, ())

    def test_un_fichero_que_no_esta_ABORTA_en_vez_de_devolver_vacio(self):
        with self.assertRaises(ShmirDesignError) as caja:
            read_evidence_pairs("no_existe_este_export.csv")
        self.assertIn("no_existe_este_export.csv", str(caja.exception))


class TestLaRegresionQueLoHabriaCazado(unittest.TestCase):
    """Lo que se transcribio no era del fichero que se creia. Queda fijado."""

    def test_los_pares_transcritos_cuadraban_con_el_fichero_RETIRADO(self):
        scores = _scores_del_tsv(RETIRADO)
        self.assertEqual(
            tuple((p, scores[p - 1]) for p, _ in PARES_TRANSCRITOS), PARES_TRANSCRITOS
        )

    def test_y_NO_cuadraban_con_el_export_de_la_corrida_buena(self):
        scores = _scores_del_csv(MANUAL_EVIDENCE_FILE)
        self.assertNotEqual(
            tuple((p, scores[p - 1]) for p, _ in PARES_TRANSCRITOS), PARES_TRANSCRITOS
        )

    def test_el_manifiesto_sigue_marcando_NO_USAR_el_fichero_retirado(self):
        entrada = load_manifest(REFERENCIA / MANIFEST_NAME).entry(RETIRADO)
        self.assertIn("NO USAR", entrada.origin)

    def test_la_direccion_NO_se_movio_al_corregir_el_ancla(self):
        # Los tres ficheros vienen crecientes, asi que la conclusion es la misma. Eso
        # es suerte y no argumento: se fija para que se vea que lo que cambio fue de
        # donde sale la evidencia, no que dice.
        for nombre, lector in (
            (MANUAL_EVIDENCE_FILE, _scores_del_csv),
            (RETIRADO, _scores_del_tsv),
            ("mirarchitect_prnp_export.csv", _scores_del_csv),
        ):
            with self.subTest(fichero=nombre):
                pares = [(str(i), s) for i, s in enumerate(lector(nombre))]
                self.assertTrue(file_order_direction(pares))

    def test_la_direccion_derivada_del_ancla_es_la_registrada(self):
        pares = [(str(i), s) for i, s in enumerate(_scores_del_csv(MANUAL_EVIDENCE_FILE))]
        self.assertEqual(
            file_order_direction(pares),
            EVIDENCE[ScoreSource.MANUAL_MIRARCHITECT].lower_is_better,
        )


if __name__ == "__main__":
    unittest.main()
