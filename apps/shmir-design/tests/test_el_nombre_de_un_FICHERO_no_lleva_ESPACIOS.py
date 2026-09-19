"""El nombre de un fichero de salida no se monta con una f-string en la pagina.

**De donde sale.** Reportado el 2026-09-11 con la captura del modal de BLAST delante:
`Homo sapiens_consulta.fasta`, con el espacio dentro. La especie que llega de la pagina
es el nombre CIENTIFICO —`species_options` pone `especie.scientific`— y tres emisores lo
pegaban a mano:

    ruta = f"{nombre}_consulta.fasta"
    nombre_seed = f"{nombre}_colision_seed.txt"
    nombre_ot = f"{nombre}_carga_offtarget_{fondo}.txt"

**Y el primero NO es solo un nombre feo**: la misma cadena entra en la ORDEN de BLAST que
la pagina da para copiar y pegar en una consola, donde el espacio la parte en dos
argumentos. Medido antes de arreglar nada: `blastn` recibia `-query Homo` y
`sapiens_consulta.fasta` como un argumento suelto, o sea una orden que no corre y cuyo
error no nombra la causa.

**`output_stem` existia desde la errata nº 60** y se barrio «la familia entera» — el zip,
el boton suelto, los bloques, los fragmentos y la linea de BLAST del informe—, y estos
tres se quedaron fuera porque **no son entradas del zip**: el guardia de entonces exige
que ninguna entrada del zip lleve un espacio, y estos ficheros no pasan por ahi. Un
guardia que mira un artefacto no cubre a quien no entra en ese artefacto (principio
nº 31).

**EL CRITERIO ESTA CALIBRADO MIDIENDO** (principio nº 34), sobre `ui/streamlit_app.py`:

    6  toda f-string con una extension de fichero          <- inservible
    6  ... y ademas con alguna interpolacion               <- 2 falsos positivos
    4  ... y ademas interpolando `nombre` o `especie`      <- 4 aciertos, 4 reales

Los dos que el criterio ancho marca de mas usan el **slug del proyecto**, que ya pasa por
`check_project_slug` y no puede traer espacios. Un guardia con falsos positivos se acaba
apagando, asi que manda el fino.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import ast
import pathlib
import re
import shlex
import unittest

from shmir_design.blast import BlastParams
from shmir_design.errors import ShmirDesignError
from shmir_design.outputs import output_name, output_stem
from shmir_design.presentation import blast_command_text
from shmir_design import species as sp

PAGINA = pathlib.Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"

#: Las extensiones que emite esta app. `output_bundle` las escribe y el barrido las busca
#: para reconocer que una f-string monta un NOMBRE DE FICHERO y no una frase.
EXTENSIONES = re.compile(r"\.(fasta|fa|tsv|txt|csv|zip|md|docx|pdf|gb|json)\b")

#: Las variables que en la pagina llevan el nombre CIENTIFICO de la especie. Son las que
#: pueden traer un espacio; el slug del proyecto no.
CON_ESPECIE = {"nombre", "especie"}


def nombres_montados_a_mano(fuente: str) -> list[tuple[int, str]]:
    """Las f-strings de `fuente` que montan un nombre de fichero con la especie dentro."""
    hallazgos = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, ast.JoinedStr):
            continue
        literal = "".join(
            p.value for p in nodo.values if isinstance(p, ast.Constant)
        )
        if not EXTENSIONES.search(literal):
            continue
        interpolado = {
            x.id
            for p in nodo.values
            if isinstance(p, ast.FormattedValue)
            for x in ast.walk(p)
            if isinstance(x, ast.Name)
        }
        if interpolado & CON_ESPECIE:
            hallazgos.append((nodo.lineno, literal))
    return hallazgos


class TestLaPaginaNoMontaNingunNombre(unittest.TestCase):

    def test_cero_nombres_montados_a_mano(self):
        hallazgos = nombres_montados_a_mano(PAGINA.read_text(encoding="utf-8"))
        self.assertEqual(
            hallazgos, [],
            "la pagina monta un nombre de fichero con la especie dentro: "
            + "; ".join(f"linea {l}: {t!r}" for l, t in hallazgos)
            + ". El nombre lo pone `outputs.output_name`, que quita los espacios.",
        )

    def test_Y_EL_DETECTOR_MUERDE_sobre_el_codigo_de_ANTES(self):
        """Control adversario. Sin esto, «cero» y «no mira nada» dan el mismo verde.

        La forma es la REAL, sacada del codigo que habia (principio nº 18 sobre el propio
        comprobador): una asignacion con la f-string y `nombre` dentro.
        """
        antes = 'ruta = f"{nombre}_consulta.fasta"\n'
        self.assertEqual(
            [t for _, t in nombres_montados_a_mano(antes)], ["_consulta.fasta"]
        )

    def test_y_NO_muerde_sobre_el_slug_del_proyecto(self):
        """La otra mitad de la calibracion: los dos que el criterio ancho marcaba de mas.

        `slug` sale de `check_project_slug` y no puede traer un espacio, asi que exigirle
        `output_name` seria un falso positivo — y un guardia con falsos positivos se
        acaba apagando.
        """
        legitimo = 'st.download_button("x", file_name=f"{slug}.txt")\n'
        self.assertEqual(nombres_montados_a_mano(legitimo), [])


class TestLaOrdenDeBlastSOBREVIVEaUnaConsola(unittest.TestCase):
    """Es lo que el espacio rompia de verdad, y por eso se comprueba con `shlex`.

    El nombre feo se ve; una orden partida en dos argumentos NO se ve: `blastn` contesta
    que no encuentra el fichero «Homo», que manda a mirar el sitio equivocado.
    """

    def test_query_recibe_UN_argumento_en_todas_las_especies_declaradas(self):
        for nombre in sp.SPECIES:
            especie = sp.resolve(nombre)
            with self.subTest(especie=especie.slug):
                ruta = output_name(especie.scientific, "consulta.fasta")
                orden = blast_command_text(
                    BlastParams.for_species(especie),
                    query_path=ruta,
                    out_path=output_name(especie.scientific, "blast.tsv"),
                )
                linea = next(l for l in orden.splitlines() if "-query" in l)
                trozos = shlex.split(linea)
                self.assertEqual(
                    trozos[trozos.index("-query") + 1], ruta,
                    f"la consola parte la orden: {trozos!r}",
                )

    def test_y_el_nombre_CIENTIFICO_es_el_que_lo_rompia(self):
        """El control de que la comprobacion anterior distingue algo.

        Con el nombre pegado a mano, `shlex` devuelve otro argumento. Si esto dejara de
        pasar, el test de arriba pasaria sin comprobar nada.
        """
        crudo = f"{sp.resolve('human').scientific}_consulta.fasta"
        self.assertEqual(shlex.split(crudo)[0], "Homo")


class TestOutputName(unittest.TestCase):

    def test_quita_los_espacios_de_la_especie(self):
        self.assertEqual(
            output_name("Homo sapiens", "consulta.fasta"),
            "Homo_sapiens_consulta.fasta",
        )

    def test_y_lo_hace_por_el_MISMO_camino_que_el_zip(self):
        """Una segunda forma de quitar espacios seria una segunda definicion del nombre."""
        self.assertTrue(
            output_name("Mus musculus", "blast.tsv").startswith(
                output_stem("Mus musculus")
            )
        )

    def test_un_sufijo_CON_espacios_aborta(self):
        """Si el espacio lo trae el sufijo, arreglar solo la especie deja el nombre roto."""
        with self.assertRaises(ShmirDesignError):
            output_name("Homo sapiens", "mi consulta.fasta")

    def test_un_sufijo_con_RUTA_aborta(self):
        with self.assertRaises(ShmirDesignError):
            output_name("Homo sapiens", "../consulta.fasta")

    def test_una_especie_vacia_aborta(self):
        with self.assertRaises(ShmirDesignError):
            output_name("   ", "consulta.fasta")

    def test_un_sufijo_vacio_aborta(self):
        with self.assertRaises(ShmirDesignError):
            output_name("Homo sapiens", "")


if __name__ == "__main__":
    unittest.main()
