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
        # LOS CONOCIDOS SE DERIVAN de `CONFIGURACION`, que desde 2026-09-06 es la unica
        # tabla que enumera los goldens —cada uno con la entrada sobre la que se genera—.
        # Escritos a mano aqui, una variante nueva salia como «huerfana» y el arreglo
        # obvio era añadirla al test en vez de declararla donde se declara todo.
        from tools.regenerar_golden import CONFIGURACION

        conocidos = set(CONFIGURACION)
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


# ──────────────────────────── la regla de los INERTES ────────────────────────────


class TestNingunGeneradorPONEunParametro(unittest.TestCase):
    """La regla de los inertes, comprobada sobre TODOS los generadores.

    No se ponen parámetros en un artefacto de verificación **ni siquiera los que
    coinciden con el defecto**. De los cuatro que llevaba el golden por defecto, tres
    eran inertes —`--candidates 10` es el defecto, `--min-block 22` daba lo mismo que 15
    en ese par y `--sin-manifiesto` no cambiaba nada— y sólo `--inmunes 4` tenía efecto.
    Eso es exactamente el problema: **un parámetro que no hace nada no se distingue de
    uno que sí**, así que nadie los volvió a mirar y el que rompía viajó de polizón entre
    los otros tres.

    La clase anterior cubre los generadores que llaman al CLI. Ésta cubre los que
    construyen EN PROCESO —la ficha, el documento y la página—, donde el parámetro no se
    teclea como bandera sino como argumento: `SelectionConfig(n_candidates=10)` es
    `--candidates 10` con otra forma.
    """

    FUENTE = Path(__file__).resolve().parent.parent / "tools" / "regenerar_golden.py"

    def setUp(self):
        import ast

        self.arbol = ast.parse(self.FUENTE.read_text(encoding="utf-8"))
        self.ast = ast

    def _llamadas(self, nombre):
        return [
            n
            for n in self.ast.walk(self.arbol)
            if isinstance(n, self.ast.Call)
            and isinstance(n.func, self.ast.Name)
            and n.func.id == nombre
        ]

    def test_default_config_se_llama_SIN_NADA(self):
        """Con un solo argumento deja de ser «la configuración del proyecto» y pasa a ser
        una configuración de este fichero, que es lo que nadie mira."""
        llamadas = self._llamadas("default_config")
        self.assertTrue(llamadas, "ningún generador usa `default_config()`")
        for llamada in llamadas:
            self.assertEqual(llamada.args, [], self.ast.unparse(llamada))
            self.assertEqual(llamada.keywords, [], self.ast.unparse(llamada))

    def test_NINGUN_generador_construye_un_SelectionConfig_a_mano(self):
        self.assertEqual(
            [self.ast.unparse(c) for c in self._llamadas("SelectionConfig")], []
        )

    #: Lo UNICO que `tile_utr` puede recibir aqui ademas de la secuencia. NO es una
    #: relajacion del guardia: es la distincion que le faltaba. Todo lo demas que acepta
    #: es CONFIGURACION o un RECURSO —umbrales, mascara, maduros, tabla de APA— y pasarlo
    #: abre el segundo camino que la errata nº 32 describe: el golden generado con lo
    #: tecleado mientras la app lee el fichero del gestor.
    #:
    #: La `anatomy` no es ninguna de las dos cosas: es una propiedad de LA ENTRADA, la
    #: pasan la pagina y el CLI, y sin ella `tile_utr` no puede saber donde empieza el
    #: 3'UTR — que es justo lo que `resolve.py` prohibe adivinar. La variante sobre el
    #: transcrito no puede existir sin pasarla, y esa variante es la que caza los fallos
    #: de marco (errata nº 122).
    TILADO_PERMITIDO = {"anatomy"}

    def test_tile_utr_no_recibe_CONFIGURACION_ni_RECURSOS(self):
        """La lista de lo prohibido se DERIVA de la firma de `tile_utr` menos lo
        permitido, asi que un parametro nuevo queda cubierto sin que nadie se acuerde."""
        import inspect

        from shmir_design.tiling import tile_utr

        prohibidos = {
            n for n, p in inspect.signature(tile_utr).parameters.items()
            if p.kind is inspect.Parameter.KEYWORD_ONLY
        } - self.TILADO_PERMITIDO
        self.assertTrue(prohibidos, "la firma de tile_utr no tiene nada que prohibir")
        llamadas = self._llamadas("tile_utr")
        self.assertTrue(llamadas, "ningún generador tila")
        for llamada in llamadas:
            self.assertEqual(len(llamada.args), 1, self.ast.unparse(llamada))
            puestos = sorted(
                k.arg for k in llamada.keywords if k.arg in prohibidos
            )
            self.assertEqual(puestos, [], self.ast.unparse(llamada))

    def test_y_lo_permitido_es_CORTO_y_esta_justificado(self):
        """Un permiso que crece deja de ser un permiso. Si esta lista se alarga, lo que
        hay que revisar es por que, no ampliarla."""
        self.assertEqual(self.TILADO_PERMITIDO, {"anatomy"})

    def test_ningun_campo_de_la_CONFIGURACION_aparece_como_argumento(self):
        """El trinquete derivado (principio nº 13): la lista de lo prohibido sale de los
        campos de `SelectionConfig`, así que un ajuste nuevo queda cubierto sin que nadie
        se acuerde de añadirlo aquí."""
        from shmir_design.selection import SelectionConfig

        prohibidos = set(SelectionConfig.__dataclass_fields__)
        puestos = sorted(
            {
                n.arg
                for n in self.ast.walk(self.arbol)
                if isinstance(n, self.ast.keyword) and n.arg in prohibidos
            }
        )
        self.assertEqual(
            puestos,
            [],
            f"Los generadores teclean {puestos}. Aunque coincida con el defecto: un "
            f"parámetro inerte no se distingue de uno con efecto.",
        )

    def test_y_tampoco_como_BANDERA_en_ninguno_de_los_argv(self):
        """La misma prohibición del otro lado: `apa_immune_quota` es `--inmunes`.

        Lo permitido en una VARIANTE no es una lista escrita aquí —eso sería un permiso
        que crece solo—: sale de su propio NOMBRE. Una variante puede llevar la bandera
        que declara y ninguna más, así que ninguna otra puede viajar de polizón dentro
        del artefacto que existe para fijar otra cosa.
        """
        from tools.regenerar_golden import ARGV, VARIANTES

        de_entrada = {"--fasta", "--fasta-b", "--name", "--name-b", "--genbank",
                      "--genbank-b", "--out"}
        for nombre, argv in [(None, ARGV), *VARIANTES.items()]:
            etiqueta = nombre or "el golden por defecto"
            with self.subTest(etiqueta):
                # El de por defecto no declara NINGUNA: no tiene nombre donde hacerlo.
                declaradas = {
                    a
                    for a in argv
                    if nombre and a.lstrip("-").replace("-", "_") in nombre
                }
                sobran = [
                    a
                    for a in argv
                    if a.startswith("--") and a not in de_entrada | declaradas
                ]
                self.assertEqual(sobran, [], f"{etiqueta} lleva {sobran} a mano")
