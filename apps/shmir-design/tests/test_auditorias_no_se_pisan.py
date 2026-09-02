"""Dos auditorias no pueden opinar del mismo hecho con criterios distintos.

**Pedido por el responsable del proyecto (2026-09-02)** con el caso delante y con la
prediccion: *«con tres auditorias ya conviviendo, esto va a volver a pasar»*.

LO QUE PASO. `auditar_fixtures` reconocia que un test FABRICA un artefacto por el
**nombre del fichero escrito en el test**; `auditar_claves`, estrenada ese mismo dia,
**prohibe escribirlo** —hay que pedirselo al gestor—. Dos guardias con reglas opuestas
sobre la misma evidencia. Al derivar el nombre, la fabricacion siguio existiendo y su
justificacion, viva, paso a leerse como **caducada**: el guardia dejo de ver lo que si
estaba, que es el fallo hacia el silencio.

LA CONTRAMEDIDA NO ES COORDINARLAS A MANO. Cada auditoria declara en
`data/auditorias.toml` sobre que EVIDENCIA opina, y dos que compartan `lee` tienen que
declarar un `cruce` — este fichero — que compruebe que siguen de acuerdo.

Y el cruce no es una declaracion: son DOS comprobaciones reales, una por cada par que
hoy comparte evidencia.
"""

import tomllib
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "auditorias.toml"

with TABLA.open("rb") as _f:
    AUDITORIAS = tomllib.load(_f)["auditoria"]


class TestLaTablaOBLIGAaCruzar(unittest.TestCase):
    """El mecanismo: si dos comparten evidencia, hay que atarlas."""

    def test_toda_auditoria_declara_sobre_que_opina(self):
        for entrada in AUDITORIAS:
            with self.subTest(entrada["nombre"]):
                for campo in ("lee", "opina", "reconoce_por", "instrumento"):
                    self.assertTrue(entrada.get(campo), campo)

    def test_dos_que_comparten_EVIDENCIA_declaran_un_CRUCE(self):
        por_evidencia = {}
        for entrada in AUDITORIAS:
            por_evidencia.setdefault(entrada["lee"], []).append(entrada)
        for evidencia, entradas in por_evidencia.items():
            if len(entradas) < 2:
                continue
            with self.subTest(evidencia):
                for entrada in entradas:
                    self.assertTrue(
                        entrada.get("cruce"),
                        f"{entrada['nombre']} comparte evidencia con "
                        f"{[e['nombre'] for e in entradas if e is not entrada]} y no "
                        f"declara qué test comprueba que siguen de acuerdo. Dos "
                        f"criterios sobre el mismo hecho se separan sin que nadie lo "
                        f"note — ya pasó.",
                    )
                self.assertEqual(
                    len({e["cruce"] for e in entradas}), 1,
                    "las que comparten evidencia tienen que cruzarse en el MISMO test: "
                    "dos cruces separados vuelven a ser dos criterios sueltos.",
                )

    def test_el_cruce_declarado_EXISTE(self):
        for entrada in AUDITORIAS:
            if entrada.get("cruce"):
                with self.subTest(entrada["nombre"]):
                    self.assertTrue((RAIZ / entrada["cruce"]).is_file())

    def test_el_instrumento_es_uno_de_los_tres(self):
        for entrada in AUDITORIAS:
            with self.subTest(entrada["nombre"]):
                self.assertIn(
                    entrada["instrumento"], {"GUARDIA", "TRINQUETE", "INFORME"}
                )

    def test_ninguna_auditoria_del_repositorio_se_queda_SIN_DECLARAR(self):
        # Derivado del directorio, no de una lista: una auditoria nueva que no se declare
        # hace fallar aqui, que es el unico momento en que alguien va a mirar si pisa a
        # otra.
        vivas = {
            p.stem for p in (RAIZ / "tools").glob("auditar_*.py")
        } | {"check_alcance"}
        declaradas = {e["nombre"].split(":")[0] for e in AUDITORIAS}
        self.assertEqual(vivas - declaradas, set())


class TestElCruceDeLaEVIDENCIA_nombre_de_artefacto(unittest.TestCase):
    """`auditar_fixtures` y `auditar_claves` sobre el nombre de un fichero en un test.

    El caso real: al derivar el nombre, una de las dos dejo de reconocerlo. El cruce
    exige que las DOS formas de escribirlo —literal y derivada— den el MISMO veredicto.
    """

    LITERAL = '''
def test_algo(tmp):
    (tmp / "aav_casete.fa").write_text(">x\\nACGT\\n")
'''
    DERIVADA = '''
from shmir_design import species as _species

_DEPOSITO = {f.role: f.filename for f in _species.required_files(_species.resolve("mouse"))}
CASETE_FA = _DEPOSITO["transgen"]

def test_algo(tmp):
    (tmp / CASETE_FA).write_text(">x\\nACGT\\n")
'''

    def _detecta(self, fuente):
        import sys

        sys.path.insert(0, str(RAIZ / "tools"))
        from auditar_fixtures import _alias_por_rol  # noqa: PLC0415

        alias = _alias_por_rol(fuente)
        lineas = fuente.splitlines()
        escrituras = [i for i, l in enumerate(lineas) if "write_text" in l]
        formas = ["aav_casete.fa"] + [
            a for a, v in alias.items() if "aav_casete.fa" in v
        ]
        return any(
            abs(i - j) <= 2
            for i, l in enumerate(lineas)
            if any(f in l for f in formas)
            for j in escrituras
        )

    def test_las_dos_formas_de_escribirlo_dan_el_MISMO_veredicto(self):
        self.assertTrue(self._detecta(self.LITERAL), "el literal no se reconoce")
        self.assertTrue(
            self._detecta(self.DERIVADA),
            "el nombre DERIVADO no se reconoce: es exactamente el fallo del 2026-09-02, "
            "con la justificación viva leyéndose como caducada.",
        )


class TestElCruceDeLaEVIDENCIA_digestos(unittest.TestCase):
    """`auditar_guardias` y `auditar_claves:digestos` sobre quién calcula un digesto.

    Las dos llevan su propia tabla —`guardias.toml` y `magnitudes.toml`— y las dos hay
    que actualizarlas al añadir un sitio que hashea. Eso ya se olvidó DOS veces en un
    día (`result_fingerprint` y `file_fingerprint`), y las dos se cazaron por casualidad
    al correr la suite. El cruce lo convierte en una comprobación.
    """

    def _tabla(self, nombre):
        with (RAIZ / "data" / nombre).open("rb") as f:
            return tomllib.load(f)

    def test_todo_sitio_que_HASHEA_esta_en_las_DOS_tablas(self):
        import sys

        sys.path.insert(0, str(RAIZ / "tools"))
        from auditar_claves import digestos  # noqa: PLC0415

        magnitudes = set(self._tabla("magnitudes.toml")["digestos"])
        guardias = self._tabla("guardias.toml")
        # Los simbolos viven de DOS formas en esa tabla: como clave de una seccion
        # (`[solo_calculan]`) y como lista dentro de un `[[guardia]]`. Mirar solo una de
        # las dos daria nueve falsos positivos — un cruce que se equivoca hacia el ruido
        # se apaga igual que uno que se equivoca hacia el silencio.
        clasificados = set()
        for valor in guardias.values():
            if isinstance(valor, dict):
                clasificados |= set(valor)
            elif isinstance(valor, list):
                for entrada in valor:
                    for campo in (entrada or {}).values():
                        if isinstance(campo, list):
                            clasificados |= {c for c in campo if isinstance(c, str)}
                        elif isinstance(campo, str):
                            clasificados.add(campo)

        def _corto(nombre):
            partes = nombre.split(".")
            return f"{partes[0]}.{partes[-1]}"

        cortos = {_corto(c) for c in clasificados}
        for sitio in digestos():
            with self.subTest(sitio):
                self.assertIn(sitio, magnitudes, "falta en data/magnitudes.toml")
                self.assertIn(
                    _corto(sitio), cortos,
                    "falta en data/guardias.toml: las dos tablas opinan sobre el mismo "
                    "hecho y hay que actualizar las dos.",
                )


if __name__ == "__main__":
    unittest.main()
