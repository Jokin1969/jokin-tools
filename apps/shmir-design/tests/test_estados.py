"""El inventario de estados de la interfaz, y su trinquete.

Regla 5: escrito antes que la tabla.

El de banderas cubre los CLI. Éste cubre la PÁGINA, que es donde vive lo que el usuario
toca — y donde estaba `_modal_blast`. El eje no son los widgets: son las combinaciones de
estado que **pintan cosas distintas**.

Lo que falla aquí NO es que falten estados por pintar —eso es un informe— sino que la
TABLA se desincronice del código, que un bloqueo se quede sin motivo, o que el trinquete
suba.
"""

import tomllib
import unittest
from pathlib import Path

from tools import auditar_estados as auditoria

RAIZ = Path(__file__).resolve().parent.parent
TABLA = tomllib.loads((RAIZ / "data" / "estados.toml").read_text(encoding="utf-8"))
DESTINOS = ("CUBRIR", "CONSTANTE", "BORRAR")


class TestElEspacioSeDERIVA(unittest.TestCase):
    """Un rol nuevo o un modal nuevo tienen que aparecer solos: si hubiera que
    acordarse de añadirlos, el inventario envejecería como cualquier lista transcrita."""

    def test_hay_un_par_de_estados_por_ROL_del_gestor(self):
        from shmir_design.species import required_files, resolve

        ejes = {e.eje for e in auditoria.espacio_de_estados()}
        for fila in required_files(resolve("raton")):
            self.assertIn(f"fichero:{fila.role}", ejes, fila.role)

    def test_y_un_par_por_cada_CORRIDA_del_registro(self):
        from shmir_design.store import RECORD_KINDS

        ejes = {e.eje for e in auditoria.espacio_de_estados()}
        for tipo in RECORD_KINDS:
            if tipo.startswith("corrida_"):
                self.assertIn(f"modal:{tipo.removeprefix('corrida_')}", ejes, tipo)

    def test_el_eje_de_la_corrida_tiene_los_TRES_valores(self):
        valores = {
            e.valor for e in auditoria.espacio_de_estados() if e.eje == "corrida"
        }
        self.assertEqual(valores, set(auditoria.CORRIDA))


class TestLaTablaCubreLoQueHAY(unittest.TestCase):

    def setUp(self):
        self.informe = auditoria.auditar()

    def test_ningun_estado_se_queda_SIN_clasificar(self):
        self.assertEqual(self.informe.sin_clasificar, [])

    def test_y_ninguna_entrada_nombra_un_estado_que_ya_no_existe(self):
        self.assertEqual(self.informe.muertos, [])

    def test_todo_destino_es_uno_de_los_TRES(self):
        for fila in self.informe.filas:
            self.assertIn(fila["destino"], DESTINOS, fila["clave"])

    def test_todo_estado_dice_QUE_PINTA(self):
        """Sin eso la lista es una columna de claves y no se puede priorizar."""
        for fila in self.informe.filas:
            self.assertTrue(fila["que_pinta"], fila["clave"])


class TestElTrinquete(unittest.TestCase):

    def setUp(self):
        self.informe = auditoria.auditar()
        self.cuantos = len(self.informe.sin_pintar)

    def test_no_SUBE_sin_que_alguien_lo_diga(self):
        self.assertLessEqual(self.cuantos, self.informe.techo)

    def test_y_un_techo_CADUCADO_tambien_falla(self):
        self.assertGreaterEqual(self.cuantos, self.informe.techo)

    def test_los_BLOQUEADOS_cuentan(self):
        """Excluirlos dejaba el número en CERO con diecinueve estados sin pintar, que es
        un informe que se lee como «pendiente» (principio nº 15). `bloqueado_por` dice
        por qué no se puede hoy; no exime de contarlo."""
        bloqueados = [f for f in self.informe.sin_pintar if f["bloqueado_por"]]
        self.assertTrue(bloqueados)


class TestLosBLOQUEOSsonTAREAS(unittest.TestCase):
    """Un bloqueo sin salida escrita es una queja. Cada uno dice qué lo cerraría."""

    def test_todo_bloqueo_dice_QUE_LO_CERRARIA(self):
        for fila in auditoria.auditar().filas:
            if fila["bloqueado_por"]:
                self.assertIn("aría", fila["bloqueado_por"], fila["clave"])

    def test_un_bloqueo_de_un_estado_YA_pintado_esta_caducado(self):
        for fila in auditoria.auditar().filas:
            if fila["nivel"] == "PINTADO":
                self.assertFalse(
                    fila["bloqueado_por"],
                    f"{fila['clave']} se pinta y sigue declarado bloqueado.",
                )


class TestLoQueELdetectorNOpuedeHacer(unittest.TestCase):
    """Se contrasta el criterio, porque este detector ya se equivocó dos veces.

    Primero comparaba los niveles con `max()` de cadenas —y `max("NADA", "CONSTRUIDO")`
    es `"NADA"`, así que TODO salía sin tocar—. Y después reconocía los estados de
    fichero por el nombre del fichero en el fuente, que aparece IGUAL en un test que lo
    pone y en uno que comprueba que falta.
    """

    def test_los_niveles_se_ordenan_por_INDICE_no_alfabeticamente(self):
        self.assertEqual(auditoria.NIVELES, ("PINTADO", "CONSTRUIDO", "NADA"))
        self.assertLess(
            auditoria.NIVELES.index("PINTADO"), auditoria.NIVELES.index("CONSTRUIDO")
        )
        # Alfabeticamente seria al reves, que es justo el fallo que hubo.
        self.assertGreater("PINTADO", "CONSTRUIDO")

    def test_el_estado_de_un_FICHERO_sale_de_su_presencia_real_y_no_de_un_marcador(self):
        de_fichero = [
            e for e in auditoria.espacio_de_estados() if e.eje.startswith("fichero:")
        ]
        self.assertTrue(de_fichero)
        for estado in de_fichero:
            self.assertEqual(estado.marcadores, ())
            self.assertIsNotNone(estado.presente)

    def test_y_para_cada_rol_EXACTAMENTE_uno_de_los_dos_estados_es_el_de_hoy(self):
        """CON y SIN son excluyentes: si los dos salieran «presentes», el detector
        estaría dando por pintados los dos lados de cada eje."""
        por_eje: dict[str, list[bool]] = {}
        for estado in auditoria.espacio_de_estados():
            if estado.eje.startswith("fichero:"):
                por_eje.setdefault(estado.eje, []).append(bool(estado.presente))
        for eje, valores in por_eje.items():
            self.assertEqual(sorted(valores), [False, True], eje)


if __name__ == "__main__":
    unittest.main()
