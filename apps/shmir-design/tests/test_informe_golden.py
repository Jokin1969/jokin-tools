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


# ─────────────────────── las VARIANTES, cada una con su nombre ───────────────────────


@unittest.skipUnless(
    all(f.is_file() for f in FIXTURES),
    "NOT_RUN: faltan fixtures versionados",
)
class TestLasVariantesTambienSeComparanENTERAS(unittest.TestCase):
    """Un golden por configuración, y el nombre dice cuál (principio nº 18).

    El golden por defecto se genera con la configuración por defecto **sin excepciones**.
    Lo que necesite otra configuración va en un artefacto APARTE cuyo nombre la declara —
    nunca en el de por defecto con parámetros puestos a mano, que es lo que hizo que la
    única corrida del CLI que alguien miraba llevara `--inmunes 4` y validara un panel
    que el CLI por defecto no producía (errata nº 32).
    """

    def test_cada_variante_declarada_tiene_su_fichero(self):
        from tools.regenerar_golden import VARIANTES

        for nombre in VARIANTES:
            with self.subTest(nombre):
                self.assertTrue((GOLDEN.parent / nombre).is_file(), nombre)

    def test_y_ninguna_se_ha_quedado_sin_declarar(self):
        """Un golden huérfano en la carpeta es un artefacto que nadie regenera."""
        from tools.regenerar_golden import DOCUMENTO, FICHA, PAGINA, VARIANTES

        conocidos = {GOLDEN.name, FICHA.name, DOCUMENTO.name, PAGINA.name} | set(VARIANTES)
        sobran = sorted(
            p.name for p in GOLDEN.parent.iterdir() if p.name not in conocidos
        )
        self.assertEqual(sobran, [])

    def test_el_nombre_de_cada_variante_DICE_que_lleva(self):
        """No vale `raton_informe_2.txt`: quien lo abre dentro de un año tiene que saber
        con qué configuración se generó sin ir a leer el generador."""
        from tools.regenerar_golden import ARGV, VARIANTES

        for nombre, argv in VARIANTES.items():
            with self.subTest(nombre):
                distintos = [a for a in argv if a.startswith("--") and a not in ARGV]
                self.assertTrue(distintos, f"{nombre} no se distingue del de por defecto")
                for bandera in distintos:
                    self.assertIn(
                        bandera.lstrip("-").replace("-", "_"),
                        nombre,
                        f"{nombre} no nombra {bandera}",
                    )

    def test_las_variantes_se_comparan_ENTERAS_igual_que_el_de_por_defecto(self):
        from tools.regenerar_golden import VARIANTES, generar

        for nombre, argv in VARIANTES.items():
            with self.subTest(nombre):
                destino = GOLDEN.parent / nombre
                self.assertEqual(
                    generar(destino, argv),
                    destino.read_text(encoding="utf-8"),
                    f"{nombre} ha cambiado. Si es deliberado: "
                    f"python3 tools/regenerar_golden.py, y el diff entra en la revisión.",
                )

    def test_el_de_por_defecto_NO_lleva_ningun_parametro_puesto_a_mano(self):
        """La contramedida del principio nº 18, comprobada sobre el propio generador.

        Sólo se admiten las banderas que declaran QUÉ se analiza —la entrada y su
        anatomía—. Cualquier otra es una configuración, y una configuración en el golden
        por defecto es una configuración fantasma.
        """
        from tools.regenerar_golden import ARGV

        de_entrada = {"--fasta", "--fasta-b", "--name", "--name-b", "--genbank",
                      "--genbank-b", "--out"}
        puestas = [a for a in ARGV if a.startswith("--") and a not in de_entrada]
        self.assertEqual(
            puestas, [],
            f"El golden por defecto lleva {puestas} puesto a mano. Si hace falta esa "
            f"configuración, va en una VARIANTE que la declare en su nombre.",
        )
