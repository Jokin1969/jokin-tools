"""Un umbral que decide no puede esconder un supuesto sobre los datos.

**Categoria propia, pedida por el responsable del proyecto (2026-09-02)** con el caso
delante: *«no es un umbral flojo: es un umbral que codifica un supuesto y lo esconde en
un numero»*. Es **distinto** de lo que ya cubre `justificacion.py` —umbrales SIN base
medida, numeros sin respaldo—. Estos tienen respaldo aparente y **significan otra cosa de
la que parecen**.

EL CASO (errata nº 56):

    estado = FilterState.FAIL if len(fuera) > 1 else FilterState.PASS

Ese `> 1` decia **«uno es tuyo»** sin escribirlo, y fallaba en las dos direcciones y las
dos invisibles: con dos variantes de transcrito del mismo gen, la segunda contaba como
off-target perfecto y **cada candidato fallaba contra su propia diana**; y con una guia
que no acierta a su blanco, daba `PASS`.

EL CONTROL ADVERSARIO ES LA MITAD DEL TEST. Salir a cero sobre el codigo ya arreglado no
demuestra que el guardia muerda — es la errata nº 29 otra vez. Se le da el fuente de
ANTES y se exige que lo señale.
"""

import sys
import tomllib
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

from auditar_umbrales import auditar, umbrales, umbrales_de_fuentes  # noqa: E402

#: El fuente de `BlastRun.verdict` TAL COMO ESTABA, recortado a lo que lo hacia fallar.
#: No es un fixture inventado: es la linea 144 de `blast_store.py` en HEAD~1.
ANTES_DE_LA_ERRATA_56 = '''
class BlastRun:
    def verdict(self, query_name=None):
        hits = self.hits if query_name is None else self.hits_for(query_name)
        fuera = [h for h in hits if h.mismatches <= 1]
        estado = FilterState.FAIL if len(fuera) > 1 else FilterState.PASS
        return FilterResult(name=FILTER_NAME, state=estado, reason="...")
'''


class TestElGuardiaMUERDE(unittest.TestCase):
    """Control adversario. Sin esto, «cero hallazgos» y «no mira nada» dan lo mismo."""

    def test_señala_el_umbral_de_la_errata_56(self):
        encontrados = umbrales_de_fuentes({"blast_store": ANTES_DE_LA_ERRATA_56})
        self.assertIn(
            "blast_store.verdict:len(fuera) > 1", encontrados,
            "el `> 1` que codificaba «uno es tuyo» tiene que salir: si el detector no lo "
            "ve sobre el fuente de antes, su cero sobre el de ahora no dice nada.",
        )

    def test_y_NO_señala_una_comparacion_fuera_de_un_veredicto(self):
        # El recorte es lo que hace aplicable el guardia: el barrido ancho da 123
        # comparaciones en el paquete y casi todas son formato o guardias de entrada.
        # Un auditor con falsos positivos se apaga el primer dia.
        fuera = '''
def formatea(filas):
    if len(filas) > 1:
        return "varias"
    return "una"
'''
        self.assertEqual(umbrales_de_fuentes({"outputs": fuera}), [])


class TestElCodigoDeHOY(unittest.TestCase):

    def test_ningun_umbral_que_decide_se_queda_SIN_DECLARAR(self):
        informe = auditar()
        self.assertEqual(
            informe["sin_declarar"], [],
            "un umbral dentro de algo que emite veredicto declara en "
            "`data/umbrales_con_supuesto.toml` de QUÉ supuesto depende su lectura. "
            "Si no se puede escribir, el umbral está mal planteado.",
        )

    def test_ninguna_declaracion_se_queda_CADUCADA(self):
        # Misma disciplina que `alcanzabilidad.toml` y `datos_en_codigo.toml`: una tabla
        # con entradas muertas deja de leerse, y el siguiente hallazgo se pierde dentro.
        self.assertEqual(auditar()["muertos"], [])

    def test_el_umbral_de_la_errata_YA_NO_EXISTE(self):
        # Regresion directa: la comparacion se sustituyo por «ningun acierto grave FUERA
        # de la diana», que dice lo que es en vez de suponerlo.
        self.assertNotIn("blast_store.verdict:len(fuera) > 1", umbrales())

    def test_cada_declaracion_dice_las_TRES_cosas(self):
        with (RAIZ / "data" / "umbrales_con_supuesto.toml").open("rb") as f:
            tabla = tomllib.load(f)
        self.assertTrue(tabla)
        for nombre, entrada in tabla.items():
            with self.subTest(nombre):
                for campo in ("que_decide", "supuesto", "donde_se_declara"):
                    self.assertTrue(entrada.get(campo), campo)

    def test_un_supuesto_declarado_dice_DONDE_se_declara(self):
        # «Lleva un supuesto» sin decir donde vive es la mitad del trabajo: quien lea el
        # numero dentro de un año necesita poder ir a comprobarlo.
        with (RAIZ / "data" / "umbrales_con_supuesto.toml").open("rb") as f:
            tabla = tomllib.load(f)
        for nombre, entrada in tabla.items():
            if entrada["supuesto"].lower().startswith("ninguno"):
                continue
            with self.subTest(nombre):
                self.assertNotEqual(
                    entrada["donde_se_declara"].strip(), "—",
                    "este umbral declara que SÍ depende de un supuesto y no dice dónde "
                    "está escrito ese supuesto.",
                )


if __name__ == "__main__":
    unittest.main()
