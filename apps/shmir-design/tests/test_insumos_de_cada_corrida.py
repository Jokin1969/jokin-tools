"""Cada corrida guarda el md5 de TODOS los ficheros que consumió, no sólo del principal.

Regla 5: escrito antes.

`SeedScan` guardaba `source`, que es la PROSA de procedencia del fichero de maduros —el
md5 está dentro, en medio de una frase—. BLAST guarda `database.md5` y off-target
`provenance.md5`, los dos como CAMPO. La diferencia importa porque OBSOLETO se deriva
comparando md5, y un md5 dentro de una frase no se compara: se lee.

Y off-target consume DOS ficheros —el catálogo de 3'UTR y el de maduros— y sólo tenía
el md5 del primero. Así que no era «un campo que falta en uno de cuatro»: faltaba en
dos, y en el segundo lo tapaba que el primero sí estuviera.

Se cierra con UNA TABLA, `insumos.CONSUMIDOS`, que declara qué consume cada tipo de
corrida y en qué campo del registro vive su md5. El test recorre la tabla; añadir un
quinto modal sin declarar sus insumos falla aquí.

ACTUALIZADO (2026-09-02, errata nº 47): el insumo declara su ROL y el NOMBRE lo pone
`species.required_files`. Aquí ningún nombre de fichero se escribe a mano — antes se
escribían, y por eso estos tests preguntaban por la clave que ellos mismos habían
puesto y no podían discrepar del depósito nunca.
"""

import re
import unittest

from shmir_design import insumos

ESPECIE = "mouse"

HEX32 = re.compile(r"^[0-9a-f]{32}$")


class TestLaTablaCubreLosCuatroTipos(unittest.TestCase):
    def test_estan_los_cuatro_y_solo_los_cuatro(self):
        self.assertEqual(
            set(insumos.CONSUMIDOS),
            {"corrida_blast", "corrida_seed", "corrida_offtarget", "corrida_empalme"},
        )

    def test_ningun_save_del_almacen_se_queda_fuera_de_la_tabla(self):
        from shmir_design import store

        tipos = set()
        for nombre in dir(store):
            if not nombre.startswith("save_") or nombre == "save_selection":
                continue
            fuente = getattr(store, nombre).__code__.co_consts
            tipos.update(
                c for c in fuente if isinstance(c, str) and c.startswith("corrida_")
            )
        self.assertEqual(tipos - set(insumos.CONSUMIDOS), set())

    def test_cada_insumo_dice_POR_QUE_se_registra(self):
        for tipo, lista in insumos.CONSUMIDOS.items():
            for ins in lista:
                with self.subTest(f"{tipo}/{ins.rol}"):
                    self.assertTrue(ins.porque.strip())

    def test_el_de_maduros_esta_en_las_DOS_corridas_que_lo_consumen(self):
        con_maduros = {
            tipo for tipo, lista in insumos.CONSUMIDOS.items()
            if any(i.rol == "mirbase" for i in lista)
        }
        self.assertEqual(con_maduros, {"corrida_seed", "corrida_offtarget"})


class TestNavegarLaRuta(unittest.TestCase):
    def test_saca_el_md5_del_registro(self):
        ins = insumos.Insumo(rol="x", ruta=("a", "b"), porque="prueba")
        self.assertEqual(insumos.md5_de({"a": {"b": "abc"}}, ins), "abc")

    def test_una_ruta_que_no_esta_da_None_y_no_revienta(self):
        ins = insumos.Insumo(rol="x", ruta=("a", "z"), porque="prueba")
        self.assertIsNone(insumos.md5_de({"a": {"b": "abc"}}, ins))

    def test_un_tipo_desconocido_ABORTA_en_vez_de_dar_lista_vacia(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            insumos.insumos_de("corrida_inventada")


class TestObsoleto(unittest.TestCase):
    """La derivación que pedía OBSOLETO, y que el md5 en prosa no permitía."""

    PAYLOAD = {
        "database": {"md5": "d" * 32},
        "query_md5": "q" * 32,
        "result_md5": "r" * 32,
    }

    @property
    def BASE(self):
        """El nombre del fichero, PEDIDO al gestor. Nunca escrito aquí."""
        return insumos.fichero_de(insumos.insumos_de("corrida_blast")[0], ESPECIE)

    def test_si_los_md5_coinciden_NO_es_obsoleta(self):
        self.assertEqual(
            insumos.obsoleta(
                "corrida_blast", self.PAYLOAD,
                actuales={self.BASE: "d" * 32}, especie=ESPECIE,
            ),
            (),
        )

    def test_si_uno_cambio_lo_NOMBRA(self):
        cambiados = insumos.obsoleta(
            "corrida_blast", self.PAYLOAD,
            actuales={self.BASE: "e" * 32}, especie=ESPECIE,
        )
        self.assertEqual(len(cambiados), 1)
        self.assertIn(self.BASE, cambiados[0])

    def test_lo_que_la_app_GENERA_no_es_un_insumo(self):
        # `query_md5` y `result_md5` siguen en el registro, pero no marcan obsoleta a
        # nadie: no son ficheros que alguien pueda reemplazar por el gestor.
        roles = {i.rol for l in insumos.CONSUMIDOS.values() for i in l}
        self.assertNotIn("consulta", roles)

    def test_un_fichero_del_que_no_se_sabe_el_md5_de_hoy_NO_se_da_por_vigente(self):
        # Sin md5 actual no se puede comparar. Eso NO es «sigue valiendo»: es que no se
        # sabe, y se dice — la misma distincion que NOT_RUN frente a PASS.
        cambiados = insumos.obsoleta(
            "corrida_blast", self.PAYLOAD, actuales={}, especie=ESPECIE,
        )
        self.assertTrue(any("no se ha podido comprobar" in c for c in cambiados))


class TestLasCorridasDeVerdadLosGuardan(unittest.TestCase):
    """No basta con que la tabla lo declare: el registro tiene que traerlo."""

    def test_seed_guarda_el_md5_de_los_maduros_como_CAMPO(self):
        from shmir_design.seed_scan import SeedScan

        self.assertIn("mature_md5", SeedScan.__dataclass_fields__)

    def test_offtarget_tambien(self):
        from shmir_design.offtarget import OfftargetScan

        self.assertIn("mature_md5", OfftargetScan.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
