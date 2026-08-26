"""Tests de `tools/check_rules.py`, el verificador de la regla 2.

Regla 5: estos tests se escribieron antes que el verificador. Los datos reales de
este test son código Python — el sujeto que el verificador analiza — no secuencias
biológicas: los datos de referencia viven en `data/reference/` (ver su PROCEDENCIA.md).
"""

import unittest

from tools.check_rules import scan_source


def codes(source):
    return sorted(v.code for v in scan_source(source, "ejemplo.py"))


class TestManejoProhibido(unittest.TestCase):
    """Casos que la regla 2 prohíbe explícitamente."""

    def test_except_desnudo(self):
        source = (
            "def f(path):\n"
            "    try:\n"
            "        return open(path).read()\n"
            "    except:\n"
            "        return None\n"
        )
        self.assertIn("BARE_EXCEPT", codes(source))

    def test_except_exception_pass(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except Exception:\n"
            "        pass\n"
        )
        self.assertIn("SWALLOWED_EXCEPT", codes(source))

    def test_except_exception_return_none(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        return fetch(url)\n"
            "    except Exception:\n"
            "        return None\n"
        )
        self.assertIn("SWALLOWED_EXCEPT", codes(source))

    def test_except_concreto_que_traga_el_fallo(self):
        """Un `except` concreto tampoco puede tragarse el fallo sin justificarlo."""
        source = (
            "import json\n"
            "def f(raw):\n"
            "    try:\n"
            "        return json.loads(raw)\n"
            "    except json.JSONDecodeError:\n"
            "        return None\n"
        )
        self.assertIn("SWALLOWED_EXCEPT", codes(source))

    def test_except_con_continue_en_bucle(self):
        source = (
            "def f(urls):\n"
            "    for url in urls:\n"
            "        try:\n"
            "            fetch(url)\n"
            "        except OSError:\n"
            "            continue\n"
        )
        self.assertIn("SWALLOWED_EXCEPT", codes(source))

    def test_except_que_solo_loguea(self):
        """Loguear y seguir es tragarse el fallo: el paso queda sin ejecutar."""
        source = (
            "import logging\n"
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except OSError as exc:\n"
            "        logging.warning('fallo: %s', exc)\n"
        )
        self.assertIn("SWALLOWED_EXCEPT", codes(source))

    def test_suppress_amplio(self):
        source = (
            "import contextlib\n"
            "def f(path):\n"
            "    with contextlib.suppress(Exception):\n"
            "        os.remove(path)\n"
        )
        self.assertIn("BROAD_SUPPRESS", codes(source))

    def test_suppress_importado_directamente(self):
        source = (
            "from contextlib import suppress\n"
            "def f(path):\n"
            "    with suppress(BaseException):\n"
            "        os.remove(path)\n"
        )
        self.assertIn("BROAD_SUPPRESS", codes(source))


class TestManejoPermitido(unittest.TestCase):
    """Casos que la regla 2 sí admite: el fallo se propaga o está justificado."""

    def test_capturar_para_anadir_contexto_y_relanzar(self):
        source = (
            "import json\n"
            "def f(raw, url):\n"
            "    try:\n"
            "        return json.loads(raw)\n"
            "    except json.JSONDecodeError as exc:\n"
            "        raise ParseError(\n"
            "            f'Respuesta de {url} no es JSON valido ({exc}); '\n"
            "            'se aborta el filtro de conservacion.'\n"
            "        ) from exc\n"
        )
        self.assertEqual(codes(source), [])

    def test_reraise_desnudo(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except OSError:\n"
            "        registrar_intento(url)\n"
            "        raise\n"
        )
        self.assertEqual(codes(source), [])

    def test_except_concreto_justificado_con_marca(self):
        """`pass` admisible: excepcion concreta + motivo documentado en el bloque."""
        source = (
            "def f(path):\n"
            "    try:\n"
            "        os.mkdir(path)\n"
            "    except FileExistsError:\n"
            "        # rule2-ok: el directorio ya existe, que es el estado deseado;\n"
            "        # no hay ningun paso que quede sin ejecutar.\n"
            "        pass\n"
        )
        self.assertEqual(codes(source), [])

    def test_la_marca_no_salva_a_un_except_amplio(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except Exception:\n"
            "        # rule2-ok: no cuela\n"
            "        pass\n"
        )
        self.assertIn("SWALLOWED_EXCEPT", codes(source))

    def test_la_marca_no_salva_a_un_except_desnudo(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except:\n"
            "        # rule2-ok: no cuela\n"
            "        pass\n"
        )
        self.assertIn("BARE_EXCEPT", codes(source))

    def test_suppress_concreto(self):
        source = (
            "from contextlib import suppress\n"
            "def f(path):\n"
            "    with suppress(FileNotFoundError):\n"
            "        os.remove(path)\n"
        )
        self.assertEqual(codes(source), [])

    def test_except_exception_que_relanza(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except Exception as exc:\n"
            "        raise DescargaError(f'fallo {url}; se aborta el paso') from exc\n"
        )
        self.assertEqual(codes(source), [])


class TestInformeDeViolaciones(unittest.TestCase):

    def test_violacion_indica_fichero_linea_y_motivo(self):
        source = (
            "def f(url):\n"
            "    try:\n"
            "        fetch(url)\n"
            "    except Exception:\n"
            "        pass\n"
        )
        violations = scan_source(source, "apps/shmir-design/red.py")
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v.filename, "apps/shmir-design/red.py")
        self.assertEqual(v.line, 4)
        self.assertTrue(v.message)

    def test_fichero_no_parseable_no_se_ignora(self):
        """Regla 2 aplicada al propio verificador: un fallo de parseo se propaga."""
        with self.assertRaises(SyntaxError):
            scan_source("def f(:\n", "roto.py")


if __name__ == "__main__":
    unittest.main()
