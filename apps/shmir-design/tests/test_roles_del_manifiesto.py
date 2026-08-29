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
