"""Ninguna clase que emita conteos POR CLASE puede tener un atributo que los sume.

**El hallazgo (2026-09-04), y es la razón de que esto sea un mecanismo y no un
comentario.** `offtarget.WHY_NOT_SUMMED` termina con esta frase, escrita hace semanas:

    «`Counts` no tiene ningún atributo que las sume: si existiera, alguien acabaría
    imprimiéndolo.»

El guardia se puso sobre `offtarget.Counts`. **Y el atributo existía en la clase de al
lado** —`seed_load.SeedLoad.total`, `sum(counts.values())`— **y se estaba imprimiendo**,
en la única columna visible de ese eje. La profecía se cumplió al pie de la letra, en la
clase que el guardia no miraba.

**Un comentario protege su clase; un mecanismo protege la siguiente.** Así que esto no
pregunta por `Counts` ni por `SeedLoad`: **descubre** qué clases del paquete emiten
conteos por clase y se lo exige a todas. Una quinta clase de sitio, o un contador nuevo,
quedan cubiertos sin que nadie se acuerde.

**Guardia, no trinquete**: el número correcto es cero. Un total de clases que no se suman
no es deuda pendiente — es una cantidad que este proyecto tiene decidido que no se
refiere a nada.

Regla 5: escritos antes.
"""

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

PAQUETE = RAIZ / "shmir_design"

#: Los nombres de campo que llevan un conteo POR CLASE. Se declaran —son dos— porque lo
#: que define a esta familia no es el tipo (`dict[str, int]` lo es cualquier tabla) sino
#: que sus claves sean CLASES DE SITIO, que es lo que hace que sumarlas mezcle señal con
#: ruido. Si mañana hay un tercero, se añade aquí y queda cubierto.
CAMPOS_POR_CLASE = ("counts", "sites")

#: NOMBRES QUE SON UN TOTAL. Hacen falta ADEMAS de mirar cuerpos, y el caso real lo
#: demuestra: el `total` viejo de `SeedLoad` era un CAMPO —`total: int | None = None`— y
#: la suma ocurria en el constructor, `SeedLoad(..., total=sum(totales.values()))`. Un
#: guardia que solo mirara cuerpos de metodos NO lo habria cazado, que es justo lo que
#: hay que evitar: un guardia que sale a cero sobre el fallo que existe.
NOMBRES_DE_TOTAL = ("total", "totales", "suma", "sum", "overall", "agregado")


#: Lo que hace un total: recorrer los valores de ese campo y sumarlos.
def _es_una_suma(nodo: ast.AST, campo: str) -> bool:
    for hijo in ast.walk(nodo):
        if not (isinstance(hijo, ast.Call) and getattr(hijo.func, "id", "") == "sum"):
            continue
        for dentro in ast.walk(hijo):
            if (
                isinstance(dentro, ast.Attribute)
                and dentro.attr in ("values", campo)
            ):
                return True
            if isinstance(dentro, ast.Name) and dentro.id == campo:
                return True
    return False


def _culpables(clases) -> list[str]:
    """Los que suman, por NOMBRE o por CUERPO. Las dos vias, porque las dos han pasado."""
    fuera = []
    for fichero, clase, campo in clases:
        for hijo in clase.body:
            nombre = ""
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nombre = hijo.name
                if _es_una_suma(hijo, campo):
                    fuera.append(f"{fichero}:{clase.name}.{nombre}")
                    continue
            elif isinstance(hijo, ast.AnnAssign) and isinstance(hijo.target, ast.Name):
                nombre = hijo.target.id
                if hijo.value is not None and _es_una_suma(hijo.value, campo):
                    fuera.append(f"{fichero}:{clase.name}.{nombre}")
                    continue
            if nombre and nombre.lower().lstrip("_") in NOMBRES_DE_TOTAL:
                fuera.append(f"{fichero}:{clase.name}.{nombre}")
    return fuera


def _clases_con_conteos():
    """Las clases del paquete que llevan un conteo por clase, DESCUBIERTAS."""
    encontradas = []
    for ruta in sorted(PAQUETE.glob("*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ClassDef):
                continue
            campos = {
                hijo.target.id
                for hijo in nodo.body
                if isinstance(hijo, ast.AnnAssign)
                and isinstance(hijo.target, ast.Name)
            }
            for campo in CAMPOS_POR_CLASE:
                if campo in campos:
                    encontradas.append((ruta.name, nodo, campo))
    return encontradas


class TestNingunaSumaDeClases(unittest.TestCase):

    def setUp(self):
        self.clases = _clases_con_conteos()

    def test_el_detector_ENCUENTRA_las_clases(self):
        """Control adversario: sin esto, «ninguna suma» y «no he mirado» dan igual.

        Es la errata nº 29 — una comprobación que no comprueba produce silencio, que es
        exactamente lo que se ve cuando todo está bien.
        """
        nombres = {clase.name for _, clase, _ in self.clases}
        self.assertIn("Counts", nombres)
        self.assertIn("SeedLoad", nombres)

    def test_ninguna_tiene_un_atributo_que_las_sume(self):
        culpables = sorted(_culpables(self.clases))
        self.assertEqual(
            culpables, [],
            f"Estas clases emiten conteos POR CLASE y además los suman: {culpables}. "
            f"La represión esperada de un 8mer y la de un 6mer no se parecen en nada, "
            f"así que el total mezcla señal con ruido — y acaba siendo lo único que se "
            f"imprime. Ver `offtarget.WHY_NOT_SUMMED`.",
        )

    def test_MUERDE_sobre_el_CODIGO_REAL_DE_ANTES(self):
        """La forma EXACTA que tenía `SeedLoad`, no una parecida.

        El total viejo era un **campo** —`total: int | None = None`— y la suma vivía en
        el constructor. Un control adversario con un método `def total()` habría pasado
        y no habría demostrado nada sobre el fallo que de verdad hubo: es el principio
        nº 18 aplicado al propio comprobador.
        """
        antes = ast.parse(
            "class SeedLoad:\n"
            "    state: object\n"
            "    counts: dict[str, int] = field(default_factory=dict)\n"
            "    total: int | None = None\n"
            "    def as_column(self) -> str:\n"
            "        return '' if self.total is None else str(self.total)\n"
        )
        clase = antes.body[0]
        culpables = _culpables([("seed_load.py", clase, "counts")])
        self.assertTrue(
            culpables, "el guardia NO caza la forma que tenía el fallo real"
        )

    def test_y_tambien_muerde_la_suma_ESCRITA_en_un_metodo(self):
        antes = ast.parse(
            "class Counts:\n"
            "    sites: dict[str, int]\n"
            "    def todo(self):\n"
            "        return sum(self.sites.values())\n"
        )
        clase = antes.body[0]
        self.assertTrue(_culpables([("offtarget.py", clase, "sites")]))


class TestLaProfeciaQueSeCUMPLIO(unittest.TestCase):
    """El comentario decía lo que iba a pasar, y pasó en la clase de al lado."""

    def test_WHY_NOT_SUMMED_sigue_diciendolo(self):
        from shmir_design.offtarget import WHY_NOT_SUMMED

        self.assertIn("ningún atributo que las sume", WHY_NOT_SUMMED)

    def test_y_ahora_hay_un_mecanismo_ademas_del_comentario(self):
        from shmir_design.seed_load import WHERE_THE_TOTAL_WENT

        # La direccion: sin ella, quien busque `carga_seed` y no la encuentre pensara
        # que el dato se perdio. Mismo criterio que `apa.WHERE_THE_MOUSE_TABLE_LIVES`.
        self.assertIn("carga_seed", WHERE_THE_TOTAL_WENT)
        self.assertIn("tilado_8mer", WHERE_THE_TOTAL_WENT)


if __name__ == "__main__":
    unittest.main()
