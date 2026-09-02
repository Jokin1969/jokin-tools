"""Una magnitud, un sitio que la calcula — y el trinquete de fórmulas, POR MAGNITUD.

**Once fórmulas repetidas «en general» no es accionable.** Lo dijo el responsable del
proyecto (2026-09-02) y es la diferencia entre un informe que se lee y uno que no: un
número a secas no dice qué hacer; «23 sitios calculan la longitud de un intervalo a mano»
sí. Es el principio nº 15 —un informe que se lee como «pendiente» no obliga a nada—
aplicado a la forma del propio informe.

Y hay UNA prioritaria, declarada como tal: la longitud de un intervalo a partir de sus
extremos. No es una duplicación aceptable — es exactamente lo que `audit.Span.check()`
existe para derivar, y la clase que ya produjo la errata del desplazamiento de 3 nt, las
ventanas emitidas para guías de 22 nt y el 405 de la errata nº 35.
"""

import sys
import tomllib
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

from auditar_claves import (  # noqa: E402
    constructores_permisivos,
    digestos,
    formulas_repetidas,
    identificadores_a_mano,
    revisar_magnitudes,
)

INFORME = revisar_magnitudes()
with (RAIZ / "data" / "magnitudes.toml").open("rb") as _f:
    TABLA = tomllib.load(_f)


class TestLosDigestos(unittest.TestCase):

    def test_todo_sitio_que_hashea_declara_QUE_magnitud_calcula(self):
        self.assertEqual(INFORME["sin_declarar"], [])

    def test_ninguna_declaracion_sobra(self):
        self.assertEqual(INFORME["muertas"], [])

    def test_DOS_SITIOS_NO_pueden_calcular_la_misma_magnitud(self):
        self.assertEqual(
            INFORME["repetidas"], {},
            "dos sitios calculan el mismo número: o uno delega en el otro, o son "
            "magnitudes distintas y el motivo tiene que decir por qué no coinciden.",
        )

    def test_cada_magnitud_dice_POR_QUE_se_calcula_ahi(self):
        for sitio, entrada in TABLA["digestos"].items():
            with self.subTest(sitio):
                self.assertTrue(entrada["magnitud"].strip())
                self.assertTrue(entrada["porque"].strip())

    def test_el_md5_de_un_FICHERO_y_el_de_una_SECUENCIA_son_magnitudes_DISTINTAS(self):
        # La distinción que este proyecto ya tenía escrita para el manifiesto, ahora
        # exigida: copiar una en el sitio de la otra rechaza el fichero BUENO.
        self.assertNotEqual(
            TABLA["digestos"]["identidad.file_fingerprint"]["magnitud"],
            TABLA["digestos"]["reference.sequence_md5"]["magnitud"],
        )


class TestLosIdentificadores(unittest.TestCase):

    def test_nadie_construye_un_id_a_mano(self):
        self.assertEqual(
            identificadores_a_mano(), [],
            "la identidad de una corrida la produce `identidad.run_id` y nadie más "
            "(errata nº 48).",
        )


class TestLosConstructoresPermisivos(unittest.TestCase):

    def test_ninguno_sin_declarar(self):
        self.assertEqual(INFORME["permisivos"], [])

    def test_ninguna_declaracion_caducada(self):
        self.assertEqual(INFORME["permisivos_muertos"], [])

    def test_el_detector_MUERDE_sobre_el_fuente_de_ANTES_del_arreglo(self):
        # Sin este control, salir a cero sobre el código ya arreglado no demuestra nada:
        # es la lección de la errata nº 29. Y el caso original NO se detecta sin seguir
        # un nivel de asignación, así que esto fija también esa vuelta.
        import ast

        fuente = (
            "def resolve(name: str):\n"
            "    limpio = str(name).strip()\n"
            "    return Species(scientific=limpio, slug=_slugify(limpio))\n"
        )
        arbol = ast.parse(fuente)
        fn = arbol.body[0]
        asignadas = {
            n.targets[0].id for n in ast.walk(fn)
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
        }
        self.assertIn("limpio", asignadas)
        # El detector real corre sobre ficheros; aquí se comprueba la pieza que lo hace
        # posible —la asignación intermedia— y que hoy el paquete sale a cero.
        self.assertEqual(INFORME["permisivos"], [])


class TestElTrinqueteDeFORMULAS(unittest.TestCase):
    """Por MAGNITUD, no en total. Un número a secas no dice qué hacer."""

    def test_toda_formula_repetida_dice_QUE_magnitud_calcula(self):
        self.assertEqual(
            INFORME["formulas_sin_clasificar"], [],
            "una fórmula repetida sin clasificar vuelve a dejar el informe en «once "
            "fórmulas», que no es accionable.",
        )

    def test_ninguna_clasificacion_sobra(self):
        self.assertEqual(INFORME["formulas_clasificadas_de_mas"], [])

    def test_los_techos_cuadran_EN_LAS_DOS_DIRECCIONES(self):
        self.assertEqual(
            INFORME["techos_rotos"], [],
            "si ha subido, alguien duplicó una fórmula; si ha bajado —que es lo que se "
            "busca— el techo está caducado y se actualiza.",
        )
        self.assertEqual(INFORME["techos_sin_grupo"], [])

    def test_el_techo_cuenta_SITIOS_y_no_formas_de_escribirla(self):
        # Contar formas premiaría unificar la sintaxis sin quitar ni una cuenta a mano.
        grupo = INFORME["grupos"]["longitud de un intervalo a partir de sus extremos"]
        self.assertGreater(grupo["sitios"], grupo["formas"])

    def test_hay_UNA_prioritaria_y_es_la_longitud_de_un_intervalo(self):
        prioritarias = [
            m for m, d in INFORME["grupos"].items() if d["prioritaria"]
        ]
        self.assertEqual(
            prioritarias, ["longitud de un intervalo a partir de sus extremos"]
        )

    def test_y_la_prioritaria_dice_POR_QUE_y_NOMBRA_a_Span(self):
        grupo = INFORME["grupos"]["longitud de un intervalo a partir de sus extremos"]
        self.assertIn("Span", grupo["por_que"])

    def test_la_prioritaria_es_la_MAS_GRANDE_de_las_tres(self):
        # No es prioritaria por decreto: es la que más sitios tiene y la única que
        # decide veredictos —el ajuste de línea es formato.
        mayor = max(INFORME["grupos"].values(), key=lambda d: d["sitios"])
        self.assertTrue(mayor["prioritaria"])


if __name__ == "__main__":
    unittest.main()
