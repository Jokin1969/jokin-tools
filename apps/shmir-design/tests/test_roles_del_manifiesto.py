"""Todo rol del manifiesto tiene decidido qué hace el CLI con él. En las dos direcciones.

Regla 5: escrito antes del arreglo.

**El fallo.** `manifest.ROLES` ganó el rol `polyadb` cuando la tabla de PolyA_DB se mudó
del código al gestor, y `tools/design.py` no se enteró: su diccionario `DESTINOS` —el que
dice a qué bandera va cada rol— se quedó sin esa entrada. Resultado:

    python3 tools/design.py --usar-manifiesto ...  →  KeyError: 'polyadb'

O sea que **«la forma normal de correr» estaba rota** contra el manifiesto de verdad.

**Por qué ningún test lo vio.** Los de `--usar-manifiesto` montan un manifiesto PARCIAL
en un directorio temporal, con los roles que ese test necesita. Ninguno incluía
`polyadb`, así que la bandera salía como recorrida de punta a punta — y lo estaba, sobre
un manifiesto que no se parece al de producción. Es el principio nº 17 con la variante
del principio nº 18: el camino se recorre, pero con una entrada que ningún usuario tiene.

**Lo que se fija aquí** no es que `polyadb` esté: es que las dos listas no puedan
volver a separarse.
"""

import unittest

from shmir_design.manifest import ROLES
from tools.design import DESTINOS


class TestLasDosListasNoPuedenSepararse(unittest.TestCase):

    def test_todo_rol_del_manifiesto_tiene_entrada_en_DESTINOS(self):
        faltan = sorted({r.role for r in ROLES} - set(DESTINOS))
        self.assertEqual(
            faltan, [],
            f"{faltan} está(n) en `manifest.ROLES` y no en `DESTINOS`: "
            f"`--usar-manifiesto` abortará con un KeyError en cuanto el manifiesto "
            f"traiga ese fichero.",
        )

    def test_y_ninguna_entrada_de_DESTINOS_nombra_un_rol_que_ya_no_existe(self):
        """Un diccionario con entradas muertas deja de leerse."""
        sobran = sorted(set(DESTINOS) - {r.role for r in ROLES})
        self.assertEqual(sobran, [])

    def test_un_rol_que_NO_se_conecta_aqui_se_declara_con_None(self):
        """`None` es una decisión escrita, no un hueco: la tabla de PolyA_DB la resuelve
        `tile_utr` por su cuenta y no hay bandera que rellenar."""
        self.assertIsNone(DESTINOS["polyadb"])

    def test_los_demas_declaran_su_TRIO_de_banderas(self):
        for rol, conexion in DESTINOS.items():
            if conexion is None:
                continue
            self.assertEqual(len(conexion), 3, rol)
            self.assertTrue(conexion[0], rol)


class TestLaFormaNORMALdeCorrerNOaborta(unittest.TestCase):
    """La regresión de verdad: contra el manifiesto REAL, no contra uno de temporal."""

    def test_usar_manifiesto_con_el_manifiesto_del_repositorio(self):
        import tempfile
        from pathlib import Path

        from shmir_design.reference import REFERENCES, fixture_available
        from tools.design import main

        if not fixture_available(REFERENCES["NM_011170.3"]):
            self.skipTest("falta data/reference/NM_011170.3.fa")
        raiz = Path(__file__).resolve().parent.parent
        datos = raiz / "data" / "reference"
        with tempfile.TemporaryDirectory() as tmp:
            codigo = main([
                "--fasta", str(datos / "NM_011170.3.fa"),
                "--genbank", str(datos / "NM_011170.3.gb"),
                "--name", "raton",
                "--usar-manifiesto",
                "--out", tmp,
            ])
        self.assertEqual(codigo, 0)


if __name__ == "__main__":
    unittest.main()


class TestElLIMITEdeLasDosEspeciesSEDICEANTES(unittest.TestCase):
    """Que la combinación no sea viable es correcto; que sólo se sepa al abortar, no.

    El manifiesto conecta `rmsk_mouse.out` **por su rol**, sin mirar qué se está
    diseñando, así que con `--fasta-b` la máscara murina acaba delante del transcrito
    humano y `RepeatMask.query_length` la rechaza —«se corrió sobre 2191 nt y se le está
    dando una de 2435»—. El guardia hace exactamente lo que debe. Lo que faltaba es que
    lo dijera **antes de que alguien lo intente**, y el sitio donde se mira antes de
    intentar nada es la ayuda de la bandera.
    """

    def test_la_ayuda_de_la_bandera_dice_UNA_SOLA_ESPECIE(self):
        import io
        from contextlib import redirect_stdout

        from tools.design import main

        salida = io.StringIO()
        with redirect_stdout(salida), self.assertRaises(SystemExit):
            main(["--help"])
        texto = salida.getvalue()
        self.assertIn("--usar-manifiesto", texto)
        self.assertIn("UNA SOLA ESPECIE", texto)
        self.assertIn("--fasta-b", texto)

    def test_y_dice_POR_QUE_no_solo_que_no(self):
        """«No se puede» sin causa manda a probar cosas al azar. La causa es el rol."""
        import io
        from contextlib import redirect_stdout

        from tools.design import main

        salida = io.StringIO()
        with redirect_stdout(salida), self.assertRaises(SystemExit):
            main(["--help"])
        self.assertIn("POR SU ROL", salida.getvalue())
