"""Dos secuencias que van emparejadas: o `strict`, o el motivo por escrito.

Regla 5: escrito antes que el detector.

**De dónde sale.** Del principio nº 19, del lado que NO lleva ninguna condición. `zip`
trunca al más corto **en silencio**: no hay `if` que buscar, y el resultado no es un error
sino un informe más corto que se lee como un resultado. Es la forma más callada de leer el
continente en vez del contenido.

**La regla, y por qué tiene dos salidas.** Un `zip` de dos secuencias distintas es una de
dos cosas, y sólo quien lo escribe sabe cuál:

- **van en paralelo** —una fila y su ancho, un candidato y su veredicto— y entonces que
  tengan distinta longitud es un fallo: `strict=True`, que es de la biblioteca estándar
  desde 3.10 y aborta;
- **la truncación ES la intención** —cinco columnas de layout para tres herramientas, un
  motivo de 7 nt contra un consenso de 5— y entonces se escribe `# zip-ok: <motivo>`,
  igual que `# rule2-ok`.

Lo que no vale es la tercera: dejarlo implícito y que el lector adivine.
"""

import unittest
from pathlib import Path

from tools import auditar_pares as auditoria

RAIZ = Path(__file__).resolve().parent.parent


class TestNingunParSeQuedaSinDECLARAR(unittest.TestCase):

    def test_todo_zip_de_dos_secuencias_dice_CUAL_de_las_dos_cosas_es(self):
        mudos = auditoria.auditar().mudos
        self.assertEqual(
            [f"{m['fichero']}:{m['linea']}  {m['fuente']}" for m in mudos],
            [],
            "Un `zip` sin `strict=` y sin `# zip-ok:` no dice si las dos secuencias "
            "van emparejadas o si la truncación es a propósito.",
        )

    def test_todo_zip_ok_lleva_un_motivo_ESCRITO(self):
        for fila in auditoria.auditar().exentos:
            with self.subTest(f"{fila['fichero']}:{fila['linea']}"):
                self.assertGreater(
                    len(fila["motivo"]), 25,
                    f"`# zip-ok:` sin motivo en {fila['fichero']}:{fila['linea']}",
                )


class TestElDetectorSEPARAloQueHayQueSEPARAR(unittest.TestCase):
    """Contrastado, porque un auditor con falsos positivos se acaba apagando."""

    def test_una_VENTANA_sobre_una_sola_secuencia_no_es_un_par(self):
        """`zip(x, x[1:])` recorre parejas consecutivas de UNA lista. No hay dos cosas
        que emparejar, así que exigirle `strict` sería ruido — y encima imposible: la
        segunda es más corta a propósito."""
        fuente = "def f(bordes):\n    return list(zip(bordes, bordes[1:]))\n"
        informe = auditoria.analizar_fuentes({"v.py": fuente})
        self.assertEqual(informe.mudos, [])

    def test_un_zip_con_strict_ya_esta_declarado(self):
        fuente = "def f(a, b):\n    return list(zip(a, b, strict=True))\n"
        self.assertEqual(auditoria.analizar_fuentes({"s.py": fuente}).mudos, [])

    def test_y_uno_SIN_declarar_se_señala(self):
        fuente = "def f(a, b):\n    return list(zip(a, b))\n"
        informe = auditoria.analizar_fuentes({"m.py": fuente})
        self.assertEqual(len(informe.mudos), 1, informe.mudos)

    def test_map_de_DOS_iterables_cuenta_igual(self):
        """`map(f, a, b)` trunca exactamente igual y no tiene `strict`. Se declara con
        `# zip-ok:` o se convierte en un `zip(..., strict=True)`."""
        fuente = "def f(a, b):\n    return list(map(max, a, b))\n"
        self.assertEqual(len(auditoria.analizar_fuentes({"p.py": fuente}).mudos), 1)

    def test_map_de_UNO_no(self):
        fuente = "def f(a):\n    return list(map(str, a))\n"
        self.assertEqual(auditoria.analizar_fuentes({"u.py": fuente}).mudos, [])


class TestLosDosCASOSreales(unittest.TestCase):
    """Anclados: uno de cada, para que la regla no se lea como «pon strict en todo»."""

    def test_el_de_los_candidatos_y_sus_veredictos_va_EMPAREJADO(self):
        from shmir_design.errors import ShmirDesignError
        from shmir_design.filters import FilterState
        from shmir_design.intron_design import BreakChoice, break_candidates
        from shmir_design.scaffold import SGEP_SCAFFOLD

        with self.assertRaises(ShmirDesignError):
            BreakChoice(
                state=FilterState.PASS, candidates=break_candidates(SGEP_SCAFFOLD)
            )

    def test_y_el_del_motivo_contra_el_consenso_TRUNCA_a_proposito(self):
        """El motivo críptico son 7 nt y el consenso del donante son 5 posiciones. Que
        se puntúen cinco no es un descuido: es lo que mide un consenso de donante."""
        from shmir_design.intron_design import DONOR_CONSENSUS, _donor_score
        from shmir_design.splicing import CRYPTIC_DONOR

        self.assertEqual(len(CRYPTIC_DONOR), 7)
        self.assertEqual(len(DONOR_CONSENSUS), 5)
        self.assertEqual(_donor_score(CRYPTIC_DONOR), 5)
        # Y la consecuencia MEDIDA: cambiar una base fuera del consenso no baja la
        # puntuación. Son alternativas que no degradan nada, y por eso no se eligen.
        fuera = CRYPTIC_DONOR[:6] + "A"
        self.assertEqual(_donor_score(fuera), _donor_score(CRYPTIC_DONOR))


class TestElDetectorSeEquivocóDOSveces(unittest.TestCase):
    """Las dos quedan fijadas, porque las dos fallaban HACIA EL SILENCIO: no marcaban de
    más, dejaban sin reconocer los motivos que sí estaban escritos — y un exento que no
    se reconoce empuja a quitar el comentario y poner `strict` donde no toca."""

    def test_la_marca_vale_en_TODO_el_bloque_de_comentario(self):
        """Un motivo que merece escribirse ocupa varias líneas y `# zip-ok:` va en la
        primera. Mirando sólo dos líneas no se encontraba ninguno de los cuatro."""
        fuente = (
            "def f(a, b):\n"
            "    # zip-ok: un motivo largo que ocupa\n"
            "    # dos lineas mas\n"
            "    # y una tercera\n"
            "    return list(zip(a, b))\n"
        )
        informe = auditoria.analizar_fuentes({"b.py": fuente})
        self.assertEqual(informe.mudos, [])
        self.assertEqual(len(informe.exentos), 1)

    def test_y_se_ancla_a_la_SENTENCIA_no_a_la_llamada(self):
        """El caso real: el `zip` vive dentro de un `return sum(...)` que empieza una
        línea antes, así que encima de la LLAMADA no hay comentario — hay código."""
        fuente = (
            "def f(a, b):\n"
            "    # zip-ok: motivo de peso escrito aqui arriba del return\n"
            "    return sum(\n"
            "        1 for x, y in zip(a, b) if x == y\n"
            "    )\n"
        )
        informe = auditoria.analizar_fuentes({"s.py": fuente})
        self.assertEqual(informe.mudos, [])

    def test_pero_NO_vale_un_comentario_de_otra_parte_de_la_funcion(self):
        """El otro lado: si valiera cualquier `# zip-ok:` del fichero, la marca dejaría
        de decir nada. Tiene que estar pegada a lo que declara."""
        fuente = (
            "def f(a, b):\n"
            "    # zip-ok: esto declara OTRA cosa\n"
            "    primero = list(zip(a, b, strict=True))\n"
            "    segundo = a[0]\n"
            "    return list(zip(a, b)), primero, segundo\n"
        )
        informe = auditoria.analizar_fuentes({"o.py": fuente})
        self.assertEqual(len(informe.mudos), 1, informe)
