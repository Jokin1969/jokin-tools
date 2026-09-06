"""El tiempo entra por un parámetro; se lee del reloj en UN sitio y con nombre.

**De dónde sale.** De un fallo del hub, no de aquí: el 1 de septiembre de 2026 se puso
roja sola una prueba de Asignación cuyo valor esperado era cierto mientras «el mes en
curso» fuese el mes que tenía escrito. Nadie la rompió — **caducó**. Es el principio
nº 11 aplicado a los tests: la prosa envejece y los valores esperados también.

**Por qué aquí no ha pasado, y qué lo sostiene.** En este paquete las fechas ENTRAN como
parámetro —`date=` en cada almacén, `generated=` en el documento— y sólo hay un sitio que
mire el reloj: `presentation.today_text()`, que existe para eso y se llama así. Mientras
eso siga siendo verdad, ninguna corrida depende de cuándo se corre. Este test es lo que
lo mantiene: un segundo `date.today()` en cualquier módulo del paquete lo rompe.

**Medido, no leído (2026-09-06):** la suite entera —4796 pruebas— corre en verde con el
reloj adelantado 40, 400 y 4000 días. El experimento está descrito en
`test/calendario.test.js` del hub, que lo hace en cada `npm test` sobre la suite Node.
Aquí no se corre en cada tanda porque son cinco minutos por pasada; lo que se comprueba
en cada tanda es la PROPIEDAD que hace que ese experimento salga en verde.

Regla 5: escrito con el caso real que lo motivó delante.
"""

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402

#: Las formas de preguntarle la hora al sistema.
RELOJES = (
    ("date", "today"),
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("time", "time"),
    ("time", "monotonic"),
)

#: El ÚNICO sitio del paquete que puede mirar el reloj, y cómo se llama lo que lo hace.
UNICO = ("shmir_design/presentation.py", "today_text")

#: Tests que miran el reloj A PROPÓSITO: comprueban `today_text` misma. Van por nombre —
#: un test nuevo que lo mire tendrá que entrar aquí y decir por qué.
#:
#: Aquí había una tercera entrada, `test_una_descarga_ROTA_no_tumba_la_pagina.py`, y la
#: quitó el cruce de abajo: ese test llama a `presentation.today_text()`, que NO es leer
#: el reloj — es pedírselo al único que puede. La tabla se escribió con una búsqueda de
#: texto y el detector mira el AST; el que tenía razón era el detector.
TESTS_QUE_MIRAN_EL_RELOJ = {
    "tests/test_gestion_de_proyectos.py": "comprueba que `today_text` devuelve HOY",
    "tests/test_el_TIEMPO_llega_por_PARAMETRO.py": "es este mismo, y lo dice",
}


def _lecturas(fuente: str, arbol: ast.AST):
    """`(linea, simbolo)` de cada llamada que le pregunta la hora al sistema."""
    funciones = [
        n for n in ast.walk(arbol)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    salida = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        f = nodo.func
        if not isinstance(f, ast.Attribute):
            continue
        for modulo, metodo in RELOJES:
            # `datetime.date.today()` y `date.today()` valen los dos: lo que importa es
            # el par (tipo, metodo), venga con el paquete delante o sin el.
            if f.attr != metodo:
                continue
            dueño = f.value
            nombre = (
                dueño.attr if isinstance(dueño, ast.Attribute)
                else dueño.id if isinstance(dueño, ast.Name) else ""
            )
            if nombre != modulo:
                continue
            dentro = [
                (n.lineno, n.name) for n in funciones
                if n.lineno <= nodo.lineno <= (n.end_lineno or n.lineno)
            ]
            salida.append((nodo.lineno, max(dentro)[1] if dentro else "<modulo>"))
    return salida


def _fuentes(subdir: str):
    for ruta in sorted((RAIZ / subdir).rglob("*.py")):
        yield str(ruta.relative_to(RAIZ)), ruta.read_text(encoding="utf-8")


class TestElRelojSeMiraEnUnSoloSitio(unittest.TestCase):

    def test_solo_today_text_le_pregunta_la_hora_al_sistema(self):
        encontrados = []
        for nombre, fuente in _fuentes("shmir_design"):
            for linea, simbolo in _lecturas(fuente, ast.parse(fuente, filename=nombre)):
                if (nombre, simbolo) != UNICO:
                    encontrados.append(f"{nombre}:{linea} en {simbolo}()")
        self.assertEqual(
            encontrados, [],
            "Estos sitios leen el reloj por su cuenta. El tiempo entra por parámetro "
            "(`date=`, `generated=`); lo que necesite HOY se lo pide a "
            "`presentation.today_text()`.",
        )

    def test_y_ese_sitio_EXISTE_y_devuelve_hoy(self):
        """Si `today_text` desapareciera, la regla de arriba se cumpliría vacía."""
        import datetime

        self.assertEqual(presentation.today_text(), datetime.date.today().isoformat())

    def test_la_exencion_nombra_al_dueño_y_al_dueño_de_verdad(self):
        fichero, simbolo = UNICO
        fuente = (RAIZ / fichero).read_text(encoding="utf-8")
        self.assertIn(f"def {simbolo}(", fuente)


class TestNingunTestSacaSuValorEsperadoDelReloj(unittest.TestCase):
    """El fallo del hub, en su forma general: un esperado que depende de cuándo corres."""

    def test_los_que_miran_el_reloj_estan_declarados(self):
        sin_declarar = []
        for nombre, fuente in _fuentes("tests"):
            if not _lecturas(fuente, ast.parse(fuente, filename=nombre)):
                continue
            if nombre not in TESTS_QUE_MIRAN_EL_RELOJ:
                sin_declarar.append(nombre)
        self.assertEqual(
            sin_declarar, [],
            "Un test que lee el reloj saca de él su valor esperado, y entonces pasa hoy "
            "y puede no pasar mañana. Si es a propósito, dilo en "
            "TESTS_QUE_MIRAN_EL_RELOJ con el motivo.",
        )

    def test_y_ninguna_declaracion_se_ha_quedado_sin_test(self):
        """Una lista con entradas muertas deja de leerse y tapa el siguiente hallazgo."""
        vivos = {
            nombre for nombre, fuente in _fuentes("tests")
            if _lecturas(fuente, ast.parse(fuente, filename=nombre))
        }
        self.assertEqual(sorted(set(TESTS_QUE_MIRAN_EL_RELOJ) - vivos), [])

    def test_cada_declaracion_dice_POR_QUE(self):
        for nombre, motivo in TESTS_QUE_MIRAN_EL_RELOJ.items():
            with self.subTest(nombre):
                self.assertGreater(len(motivo), 20)


class TestElDetectorVeLoQuePersigue(unittest.TestCase):
    """Control adversario: si no cazara estas cuatro formas, diría cero sin buscar."""

    def _lineas(self, fuente: str):
        return _lecturas(fuente, ast.parse(fuente))

    def test_caza_date_today_con_el_paquete_delante(self):
        self.assertEqual(
            len(self._lineas("import datetime\ndef f():\n    return datetime.date.today()\n")), 1
        )

    def test_y_sin_el_paquete_delante(self):
        self.assertEqual(
            len(self._lineas("from datetime import date\ndef f():\n    return date.today()\n")), 1
        )

    def test_y_datetime_now_y_time_time(self):
        self.assertEqual(
            len(self._lineas(
                "import datetime, time\n"
                "def f():\n"
                "    return datetime.datetime.now(), time.time()\n"
            )),
            2,
        )

    def test_y_dice_DENTRO_DE_QUE_funcion(self):
        lineas = self._lineas("import datetime\ndef hoy():\n    return datetime.date.today()\n")
        self.assertEqual(lineas[0][1], "hoy")

    def test_y_no_confunde_un_metodo_que_se_llama_igual(self):
        """`self.time()` de otra clase no es el reloj del sistema."""
        self.assertEqual(
            self._lineas("def f(reloj):\n    return reloj.time()\n"), []
        )


if __name__ == "__main__":
    unittest.main()
