"""El auditor de claves MUERDE donde hay que morder y CALLA donde no.

Un auditor sin este test es un auditor que se equivoca hacia el silencio —la leccion de
la alcanzabilidad, que con la clave mal puesta habia dejado de ver el caso que la
motivo—. Y uno con falsos positivos se acaba apagando, asi que las dos mitades van.

Se le da fuente SINTETICA a proposito: aqui la pregunta no es que dice el repositorio de
hoy —eso lo contesta `npm run check:shmir`— sino si el detector distingue el patron.
"""

import unittest

from tools.auditar_claves import (
    cargar_tabla,
    exenciones_caducadas,
    revisar,
    revisar_fuente,
)

TABLA = cargar_tabla()

# El nombre lo pone el gestor: aqui SI se escribe, y es correcto, porque lo que se esta
# probando es el detector y hace falta un caso malo que detectar.
MALO_VALORES = '''
def test_algo():
    cargar({"refseq_rna.fa": "contenido"})
'''

BUENO_VALORES = '''
from shmir_design.species import required_files, resolve

def test_algo():
    nombre = next(f.filename for f in required_files(resolve("mouse")))
    cargar({nombre: "contenido"})
'''

# Un literal suelto NO es una clave: abrir el fichero real por su nombre es lo correcto.
BUENO_LITERAL_SUELTO = '''
def test_algo():
    ruta = DATOS / "refseq_rna.fa"
'''

MALO_FORMATO = '''
def test_algo():
    assert almacen.verdict_for("raton_pos200_guia")
'''

BUENO_FORMATO = '''
from shmir_design.presentation import query_name

def test_algo():
    assert almacen.verdict_for(query_name("mouse", 200, "guia"))
'''

MALO_RUN_ID = '''
def test_algo():
    assert corrida.run_id == "blast-2026-09-02-aaaa"
'''


class TestMuerde(unittest.TestCase):

    def test_una_clave_de_fichero_escrita_a_mano(self):
        hallazgos = revisar_fuente(MALO_VALORES, "test_x.py", TABLA)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]["productor"], "species.required_files")

    def test_el_formato_del_nombre_de_consulta(self):
        hallazgos = revisar_fuente(MALO_FORMATO, "test_x.py", TABLA)
        self.assertEqual(
            [h["productor"] for h in hallazgos], ["presentation.query_name"]
        )

    def test_el_formato_de_un_run_id(self):
        hallazgos = revisar_fuente(MALO_RUN_ID, "test_x.py", TABLA)
        self.assertEqual([h["productor"] for h in hallazgos], ["identidad.run_id"])


class TestCalla(unittest.TestCase):

    def test_si_el_test_LLAMA_al_productor(self):
        self.assertEqual(revisar_fuente(BUENO_VALORES, "test_x.py", TABLA), [])
        self.assertEqual(revisar_fuente(BUENO_FORMATO, "test_x.py", TABLA), [])

    def test_un_literal_suelto_NO_es_una_clave(self):
        # Es la distincion que hace aplicable la regla: 294 literales del repositorio
        # nombran un fichero del deposito y casi todos son correctos —abren el fichero
        # real—. Sin esta distincion el auditor daria 294 hallazgos y se apagaria.
        self.assertEqual(revisar_fuente(BUENO_LITERAL_SUELTO, "test_x.py", TABLA), [])

    def test_un_docstring_que_CITA_el_formato_no_cuenta(self):
        fuente = '"""La clave es `raton_pos200_guia`, y se pide, no se escribe."""\n'
        self.assertEqual(revisar_fuente(fuente, "test_x.py", TABLA), [])


class TestLaTablaRespondeAlCodigo(unittest.TestCase):

    def test_los_modos_declarados_son_los_dos_que_hay(self):
        self.assertEqual(
            {p["modo"] for p in TABLA["productor"]}, {"VALORES", "FORMATO"}
        )

    def test_ninguna_exencion_sobra(self):
        self.assertEqual(exenciones_caducadas(tabla=TABLA), [])

    def test_el_repositorio_esta_a_CERO(self):
        # El numero correcto es cero: un test que no puede fallar no es deuda pendiente,
        # es una comprobacion que no comprueba (errata nº 29).
        self.assertEqual(revisar(tabla=TABLA), [])


if __name__ == "__main__":
    unittest.main()
