"""Un nombre no puede denotar dos cantidades distintas sin decirlo.

**Principio nº 27**, pedido por el responsable del proyecto (2026-09-02) como
generalizacion de los cuatro pares duplicados:

> No es codigo repetido, es peor — es una cantidad que se mueve de contexto sin el
> supuesto que la sostenia. Alli todos los hits son de longitud completa por
> construccion, asi que la condicion de longitud no hacia falta escribirla; al mover el
> criterio, el supuesto se quedo atras.

EL CONTROL ADVERSARIO ES LA MITAD DEL TEST, como en `auditar_umbrales`: salir a cero
sobre la tabla ya rellenada no demuestra que el detector muerda.
"""

import tomllib
import unittest
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

from auditar_homonimos import (  # noqa: E402
    RELACIONES, auditar, homonimos_de_fuentes,
)

#: El par que abre la categoria, reducido a lo que lo hace un homonimo. Es el fuente de
#: verdad, no un fixture inventado: las dos clases existen y siguen existiendo.
EL_PAR = {
    "blast": '''
class BlastHit:
    @property
    def antisense(self):
        return self.send < self.sstart
''',
    "specificity": '''
class Hit:
    @property
    def antisense(self):
        return self.strand is Strand.ANTISENSE
''',
}


class TestElGuardiaMUERDE(unittest.TestCase):

    def test_ve_el_par_que_abrio_la_categoria(self):
        encontrados = homonimos_de_fuentes(EL_PAR)
        self.assertIn("antisense", encontrados)
        self.assertEqual(
            encontrados["antisense"], ["blast.BlastHit", "specificity.Hit"]
        )

    def test_y_NO_señala_una_derivacion_de_UN_solo_modulo(self):
        # El recorte es lo que lo hace aplicable: el barrido ancho de «cualquier nombre
        # en mas de un modulo» da 207 y son casi todas etiquetas.
        uno = {"blast": EL_PAR["blast"]}
        self.assertEqual(homonimos_de_fuentes(uno), {})

    def test_y_NO_señala_un_CAMPO_repetido(self):
        # Un campo guardado es una etiqueta; una derivacion lleva supuestos dentro. Con
        # los campos dentro salian 207 filas y el auditor se apagaria.
        campos = {
            "a": "class Uno:\n    name: str\n",
            "b": "class Dos:\n    name: str\n",
        }
        self.assertEqual(homonimos_de_fuentes(campos), {})


class TestLaTablaDEL_repositorio(unittest.TestCase):

    def test_ninguna_magnitud_compartida_se_queda_SIN_DECLARAR(self):
        self.assertEqual(auditar()["sin_declarar"], [])

    def test_ninguna_declaracion_se_queda_CADUCADA(self):
        # Ya cazo dos al estrenarse: `end`, que dejo de ser homonimo al renombrar
        # `Site.end`, y `transcript`, que es propiedad en un lado y campo en el otro.
        self.assertEqual(auditar()["muertos"], [])

    def test_y_ninguna_declara_unas_clases_QUE_YA_NO_SON(self):
        # Mover la derivacion a otra clase sin tocar la tabla dejaria la justificacion
        # viva leyendose como vigente sobre algo que ya no existe.
        self.assertEqual(auditar()["movidos"], {})

    def test_cada_entrada_dice_QUE_ES_y_de_QUE_TIPO(self):
        with (RAIZ / "data" / "homonimos.toml").open("rb") as f:
            tabla = tomllib.load(f)
        self.assertTrue(tabla)
        for nombre, entrada in tabla.items():
            with self.subTest(nombre):
                self.assertIn(entrada["relacion"], RELACIONES)
                self.assertTrue(entrada["que_es"].strip())
                self.assertTrue(entrada["donde"])

    def test_una_DISTINTA_escribe_QUE_es_CADA_UNA(self):
        # «Son distintas» sin decir qué es cada una no sirve de nada: lo que hace falta
        # es poder leerlo sin abrir los dos módulos.
        with (RAIZ / "data" / "homonimos.toml").open("rb") as f:
            tabla = tomllib.load(f)
        for nombre, entrada in tabla.items():
            if entrada["relacion"] != "DISTINTA":
                continue
            with self.subTest(nombre):
                for clase in entrada["donde"]:
                    corto = clase.split(".")[-1]
                    self.assertIn(
                        corto, entrada["que_es"],
                        f"{nombre}: se declara DISTINTA y su explicación no nombra "
                        f"{clase}, así que no dice qué es esa.",
                    )

    def test_ANTISENSE_sigue_declarada_como_DISTINTA(self):
        # Regresion de la errata nº 57: si alguien las unifica, esta entrada tiene que
        # cambiar a la vez — y este test es el que obliga a mirarla.
        self.assertIn("antisense", auditar()["distintas"])


if __name__ == "__main__":
    unittest.main()
