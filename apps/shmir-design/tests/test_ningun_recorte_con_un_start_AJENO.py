"""Ninguna función recorta una secuencia con una posición de OTRO objeto que recibe.

**El barrido que pidió el responsable del proyecto (2026-09-04)**, inmediatamente después
de la errata nº 94: *«si `build_constructions` recortaba con el marco equivocado, busca
todos los sitios donde se recorte una secuencia con un start del panel»*.

**Y había uno más, vivo.** `presentation.splice_module_of` hacía exactamente lo mismo —
`target[construction.candidate_start - 1 : +22]` con `target` pasado por la página— así
que la tabla de accesibilidad estructural del modal montaba el módulo con la guía de otro
sitio, por el mismo camino y con el mismo silencio.

## El criterio, y por qué éste distingue

Los recortes 1-based del paquete son **50**, y casi todos son correctos: la seed sobre su
propia guía, el 3'UTR sobre su propio transcrito, un plásmido sobre sus propias
coordenadas. Lo que separa al fallo no es la forma `x[start - 1:end]` sino **de dónde
vienen las dos cosas**: en los correctos, la posición se DERIVA de la secuencia que se
recorta (`Span.of` sobre lo que se acaba de buscar ahí, o dos campos del mismo objeto);
en el fallo, **la secuencia y la posición llegan como DOS PARÁMETROS DISTINTOS de la misma
función**, y entonces nada obliga a que compartan marco.

Medido sobre el paquete entero: el criterio ancho —cualquier recorte indexado por un
`.start` ajeno— da **10** hallazgos y **9 son correctos**; el criterio de los dos
parámetros da **1**, que es el fallo. Cero falsos positivos.

**Guardia, no trinquete**: el número correcto es cero. Un `start` sin marco declarado no
puede indexar una secuencia que llega por otro lado — es el corolario del principio nº 13
que pidió el responsable: `coords.Position` ya impide **imprimir** un entero desnudo, y
esto impide **indexar** con uno.

Regla 5: escritos antes.
"""

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DIRECTORIOS = ("shmir_design", "tools", "ui")


def _recortes_con_indice_ajeno(arbol: ast.AST) -> list[tuple[int, str]]:
    """Recortes donde la secuencia y la posición son DOS parámetros distintos."""
    fuera = []
    for fn in ast.walk(arbol):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in fn.args.args + fn.args.kwonlyargs} - {"self", "cls"}
        for nodo in ast.walk(fn):
            if not isinstance(nodo, ast.Subscript):
                continue
            if not isinstance(nodo.slice, ast.Slice):
                continue
            if not (isinstance(nodo.value, ast.Name) and nodo.value.id in params):
                continue
            duenos = {
                n.value.id for n in ast.walk(nodo.slice)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            }
            ajenos = (duenos & params) - {nodo.value.id}
            if ajenos:
                fuera.append((
                    nodo.lineno,
                    f"{fn.name}: {nodo.value.id}[{sorted(ajenos)[0]}...]",
                ))
    return fuera


def _barrido():
    hallazgos = []
    for carpeta in DIRECTORIOS:
        for ruta in sorted((RAIZ / carpeta).glob("*.py")):
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for linea, texto in _recortes_con_indice_ajeno(arbol):
                hallazgos.append(f"{carpeta}/{ruta.name}:{linea}  {texto}")
    return hallazgos


class TestNingunRecorteConIndiceAjeno(unittest.TestCase):

    def test_a_cero(self):
        hallazgos = _barrido()
        self.assertEqual(
            hallazgos, [],
            "Estas funciones recortan una secuencia con la posición de OTRO parámetro, "
            "así que nada obliga a que compartan marco — y con un `start` del panel "
            f"sobre la secuencia equivocada NO hay error, hay otra secuencia: "
            f"{hallazgos}",
        )

    def test_MUERDE_sobre_el_codigo_de_ANTES(self):
        """La forma EXACTA que tenían las dos, no una parecida (principio nº 18)."""
        antes = ast.parse(
            "def splice_module_of(construction, *, target, scaffold):\n"
            "    guia = target[construction.candidate_start - 1:\n"
            "                  construction.candidate_start - 1 + 22]\n"
            "    return build_block(guia, scaffold=scaffold).module\n"
        )
        self.assertTrue(_recortes_con_indice_ajeno(antes))

    def test_y_NO_muerde_donde_la_posicion_se_DERIVA_de_lo_recortado(self):
        """El caso legítimo y mayoritario: la posición sale de la propia secuencia."""
        bien = ast.parse(
            "def _restaura(guide, utr3):\n"
            "    inicio = utr3.find(guide)\n"
            "    ventana = Span.of(inicio, guide)\n"
            "    return utr3[ventana.start - 1:ventana.end]\n"
        )
        self.assertEqual(_recortes_con_indice_ajeno(bien), [])

    def test_el_barrido_MIRA_de_verdad(self):
        """Control adversario del control: si no leyera ficheros, saldría a cero igual."""
        total = 0
        for carpeta in DIRECTORIOS:
            total += len(list((RAIZ / carpeta).glob("*.py")))
        self.assertGreater(total, 40)


class TestElModuloDelModalSaleDeLaVENTANA(unittest.TestCase):
    """`splice_module_of` pide la guía, no la recorta."""

    def test_ya_no_recibe_una_secuencia_suelta(self):
        import inspect

        from shmir_design.presentation import splice_module_of

        firma = inspect.signature(splice_module_of)
        self.assertNotIn("target", firma.parameters)
        self.assertIn("selection", firma.parameters)


if __name__ == "__main__":
    unittest.main()
