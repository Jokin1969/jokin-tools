"""El informe ENTERO, contra un fichero de referencia versionado.

Regla 5: escrito antes que el fichero golden.

Los demas tests comprueban que aparezcan los fragmentos que cada uno espera. Eso no
detecta lo que FALTA: en esta misma sesion se borraron 127 lineas del informe —el bloque
del TECHO y los inmunes enteros— reordenando un bloque, y los 1700 tests siguieron en
verde porque cada uno miraba su trozo y nadie miraba el conjunto.

Este test compara la salida COMPLETA. Criterio de aceptacion: aquel borrado habria
fallado aqui.

Se regenera a mano con `python3 tools/regenerar_golden.py`, y el diff entra en la
revision. Si el fichero cambia sin que nadie haya tocado el informe a proposito, eso es
justo lo que hay que ver.
"""

import difflib
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GOLDEN = RAIZ / "tests" / "golden" / "raton_informe.txt"
FIXTURES = [
    RAIZ / "data" / "reference" / n
    for n in (
        "NM_011170.3.fa",
        "NM_011170.3.gb",
        "NM_000311.5.fa",
        "NM_000311.5.gb",
        "mirarchitect_prnp_export_buena.csv",
    )
]

sys.path.insert(0, str(RAIZ))


@unittest.skipUnless(
    all(f.is_file() for f in FIXTURES),
    "NOT_RUN: faltan fixtures versionados; sin ellos el informe no se puede regenerar",
)
@unittest.skipUnless(GOLDEN.is_file(), f"NOT_RUN: falta {GOLDEN}")
class TestElInformeEntero(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from tools.regenerar_golden import generar

        cls.actual = generar(GOLDEN)
        cls.esperado = GOLDEN.read_text(encoding="utf-8")

    def test_el_informe_es_IGUAL_al_de_referencia(self):
        if self.actual == self.esperado:
            return
        diff = "\n".join(
            difflib.unified_diff(
                self.esperado.splitlines(),
                self.actual.splitlines(),
                fromfile="tests/golden/raton_informe.txt",
                tofile="salida actual",
                lineterm="",
                n=2,
            )
        )
        self.fail(
            "El informe ha cambiado respecto al de referencia.\n"
            "Si el cambio es deliberado: python3 tools/regenerar_golden.py, y el diff "
            "entra en la revisión.\n"
            "Si no lo es, aquí esta lo que se ha movido:\n" + diff
        )

    def test_no_se_ha_encogido(self):
        # Red de seguridad explicita del caso que lo motiva: un bloque entero borrado.
        self.assertGreaterEqual(
            len(self.actual.splitlines()),
            len(self.esperado.splitlines()),
            "El informe tiene MENOS líneas que el de referencia: se ha borrado algo.",
        )

    def test_la_referencia_no_esta_vacia_ni_es_un_muñon(self):
        # Un golden truncado convertiria este test en decoracion.
        self.assertGreater(len(self.esperado.splitlines()), 150)
        for bloque in (
            "── Riesgo de polyA",
            "con TECHO (por detrás del corte)",
            "INMUNES al TRUNCAMIENTO por ser proximales",
            "EXPERIMENTO QUE RESUELVE EL TECHO",
            "── Cobertura por tercios ──",
            "── FILTROS QUE NO SE EJECUTARON ──",
        ):
            with self.subTest(bloque):
                self.assertIn(bloque, self.esperado)
