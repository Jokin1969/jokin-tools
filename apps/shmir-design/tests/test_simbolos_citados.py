"""Todo símbolo citado en un texto que ve el usuario tiene que EXISTIR.

Sale de la errata nº 13. `intron_design.design_variant` estaba citada en el `why_missing`
del registro de intrones como si existiera, y NO existía. Y ésa es la peor de la familia:

  · una función que falta y SE DICE es un `NOT_RUN` — sabes que no está y qué te falta;
  · una citada como EXISTENTE es un `PASS` falso — crees que hay un camino, lo buscas, y
    lo que encuentras es que el texto mentía.

Esto recorre los textos que ve el usuario —`why_missing` del registro de intrones, las
fichas de obtención y las constantes de mensajes— y comprueba que todo `modulo.simbolo`
que citen exista de verdad.

**Y la segunda mitad, que es la variante que esto NO cazaba (añadida tras la errata
nº 15):** un símbolo puede EXISTIR y estar vacío. `intron_quimerico` estaba en el
registro, se importaba, tenía todos sus campos — y su secuencia era `""`, porque el
plásmido del que sale quedaba fuera de git. Citado y existente, y aun así un PASS falso.
Que exista el nombre no basta: si lo que se anuncia es contenido, el contenido tiene que
estar.
"""

import ast
import importlib
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "shmir_design"

#: `modulo.simbolo`, con el modulo en minusculas. Deja fuera las extensiones de fichero.
_CITA = re.compile(r"\b([a-z_][a-z0-9_]{2,})\.([A-Za-z_][A-Za-z0-9_]*)\b")

#: Modulos del paquete. Una cita a algo que NO es modulo nuestro no se comprueba: no
#: podemos decir si `st.button` existe sin importar Streamlit, y no es nuestro contrato.
_MODULOS = {p.stem for p in PAQUETE.glob("*.py") if not p.name.startswith("_")}

#: Lo que NO es una cita aunque lo parezca: extensiones de fichero y dominios.
_NO_SON_CITAS = frozenset(
    """py fa fasta gb gbk tsv txt out tbl toml md json csv bed dna gbff
    org com es io net gov edu""".split()
)


def _textos_del_paquete():
    for ruta in sorted(PAQUETE.glob("*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                yield ruta.name, nodo.lineno, nodo.value


#: Una cita seguida de `*` es una FAMILIA (`store.save_*`), no un simbolo: se refiere a
#: varios a la vez y ninguno se llama asi. Y una seguida de `.` es un DOMINIO
#: (`mirarchitect.cs.put.poznan.pl`), que no es una cita a nada nuestro. Los dos casos
#: salieron en la primera corrida de este guardia: un guardia con falsos positivos se
#: acaba apagando, que es la leccion del de la regla 6.
def _citas(texto):
    for encaje in _CITA.finditer(texto):
        modulo, simbolo = encaje.group(1), encaje.group(2)
        siguiente = texto[encaje.end():encaje.end() + 1]
        if siguiente in ("*", "."):
            continue
        if modulo in _MODULOS and simbolo not in _NO_SON_CITAS:
            yield modulo, simbolo


class TestTodoLoCitadoEXISTE(unittest.TestCase):

    def test_ningun_texto_del_paquete_cita_un_simbolo_inexistente(self):
        faltan = []
        cache = {}
        for fichero, linea, texto in _textos_del_paquete():
            for modulo, simbolo in _citas(texto):
                if modulo not in cache:
                    try:
                        cache[modulo] = importlib.import_module(f"shmir_design.{modulo}")
                    except ImportError:
                        # rule2-ok: un modulo que no importa aqui NO se comprueba, y eso
                        # se dice con `None` en vez de tragarse el fallo: la alternativa
                        # seria marcar como inexistente todo lo que vive en un modulo con
                        # una dependencia opcional, que es un falso positivo garantizado.
                        cache[modulo] = None
                objeto = cache[modulo]
                if objeto is not None and not hasattr(objeto, simbolo):
                    faltan.append(f"{fichero}:{linea} cita {modulo}.{simbolo}")
        self.assertEqual(
            faltan, [],
            "Símbolos citados en textos que ve el usuario y que NO existen. Una función "
            "citada como existente es un PASS falso: quien la busca descubre que el "
            "texto mentía. Ver la errata nº 13.\n  " + "\n  ".join(faltan),
        )

    def test_el_caso_que_lo_MOTIVO_esta_cubierto(self):
        faltan = list(_citas("se genera con `intron_design.no_existe_esta`"))
        self.assertEqual(faltan, [("intron_design", "no_existe_esta")])
        import shmir_design.intron_design as modulo

        self.assertFalse(hasattr(modulo, "no_existe_esta"))
        self.assertTrue(hasattr(modulo, "design_variant"))

    def test_y_NO_marca_lo_que_no_es_una_cita(self):
        self.assertEqual(list(_citas("el fichero manifest.tsv del directorio")), [])
        self.assertEqual(list(_citas("mira store.py para verlo")), [])
        # Los dos falsos positivos de la primera corrida, fijados:
        self.assertEqual(list(_citas("la familia `store.save_*` entera")), [])
        self.assertEqual(list(_citas("en mirarchitect.cs.put.poznan.pl")), [])


class TestLosTEXTOS_del_registro(unittest.TestCase):
    """El sitio exacto donde apareció: `why_missing` y las fichas."""

    def test_los_why_missing_del_registro_no_citan_nada_inexistente(self):
        from shmir_design.introns import INTRONS

        for nombre, entrada in INTRONS.items():
            for modulo, simbolo in _citas(entrada.why_missing or ""):
                with self.subTest(f"{nombre}: {modulo}.{simbolo}"):
                    objeto = importlib.import_module(f"shmir_design.{modulo}")
                    self.assertTrue(hasattr(objeto, simbolo), f"{modulo}.{simbolo}")


class TestExistirNoBastaSiLoQueSeANUNCIAEsCONTENIDO(unittest.TestCase):
    """La variante de la errata nº 15: el símbolo existe y está vacío.

    El guardia de arriba comprueba que un nombre citado se pueda resolver. Eso no dice
    nada de si tiene algo dentro, y un registro que anuncia una secuencia disponible con
    la secuencia vacía es exactamente el fallo que la regla 1 existe para impedir.
    """

    def test_todo_intron_PROVISTO_tiene_secuencia_de_verdad(self):
        from shmir_design import introns

        vacios = [
            i.name for i in introns.INTRONS.values()
            if i.provided and not i.empty_sequence.strip()
        ]
        self.assertEqual(
            vacios, [],
            f"Intrones anunciados como disponibles y SIN secuencia: {vacios}. "
            f"Es la errata nº 15: existir en el registro no es tenerlo.",
        )

    def test_y_el_que_NO_esta_provisto_dice_POR_QUE(self):
        from shmir_design import introns

        mudos = [
            i.name for i in introns.INTRONS.values()
            if not i.provided and not i.why_missing.strip()
        ]
        self.assertEqual(
            mudos, [],
            f"Intrones en NOT_RUN sin `why_missing`: {mudos}. Un NOT_RUN mudo no se "
            f"distingue de uno que nadie miró.",
        )

    def test_toda_pieza_que_un_intron_NOMBRA_existe_en_PIECES(self):
        # La otra mitad del `KeyError('')`: `five_piece` con un nombre que no esta en
        # `blocks.PIECES` moriria con un KeyError que ningun `except ShmirDesignError`
        # recoge. Que las piezas nombradas existan se comprueba aqui, no en caliente.
        from shmir_design import blocks, introns

        for intron in introns.INTRONS.values():
            for campo in ("five_piece", "three_piece", "exon5_piece", "exon3_piece"):
                nombre = getattr(intron, campo)
                if nombre:
                    with self.subTest(f"{intron.name}.{campo}"):
                        self.assertIn(nombre, blocks.PIECES)


if __name__ == "__main__":
    unittest.main()
