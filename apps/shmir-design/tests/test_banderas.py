"""El inventario de banderas de los CLI, y el trinquete que lo obliga a bajar.

Regla 5: escrito antes que la tabla.

**De dónde sale.** De la errata nº 31. `tools/design.py` pasaba `thresholds=umbrales`,
una variable que no existe, así que TODA corrida con `--rmsk` moría con un `NameError` —
y con ella el bloque del triple motivo, **que se había cableado precisamente porque
«existía sólo porque alguien lo corría a mano»**. Se cableó, y el cable no conducía.

**Ninguna de las dos herramientas del proyecto podía verlo**: la alcanzabilidad busca
símbolos sin llamador y aquí había una llamada escrita; el golden lee la salida por
defecto y se genera SIN máscara. Entre las dos hay un hueco, y ahí vive el código llamado
desde caminos que nadie recorre. Es el principio nº 17.

Lo que falla aquí NO es que falten banderas por cubrir —eso es un informe, y cubrirlas
todas de golpe no hace falta—: falla que la TABLA se desincronice del código, o que el
trinquete suba.
"""

import tomllib
import unittest
from pathlib import Path

from tools import auditar_banderas as auditoria

RAIZ = Path(__file__).resolve().parent.parent
TABLA = tomllib.loads((RAIZ / "data" / "banderas.toml").read_text(encoding="utf-8"))


class TestLaTablaCubreLoQueHAY(unittest.TestCase):
    """En las dos direcciones, como `alcanzabilidad.toml` y `guardias.toml`."""

    def setUp(self):
        self.informe = auditoria.auditar()

    def test_ninguna_bandera_del_codigo_se_queda_SIN_clasificar(self):
        self.assertEqual(self.informe.sin_clasificar, [])

    def test_y_ninguna_entrada_nombra_una_bandera_que_ya_no_existe(self):
        """Una tabla con entradas muertas deja de leerse, y el siguiente hallazgo se
        pierde dentro."""
        self.assertEqual(self.informe.muertas, [])

    def test_toda_consecuencia_es_una_de_las_CUATRO_declaradas(self):
        for fila in self.informe.filas:
            self.assertIn(fila["consecuencia"], auditoria.CONSECUENCIAS, fila["clave"])

    def test_toda_bandera_dice_QUE_HACE(self):
        """Sin eso la lista es una columna de nombres y no se puede priorizar."""
        for fila in self.informe.filas:
            self.assertTrue(fila["que_hace"], fila["clave"])


class TestElTrinquete(unittest.TestCase):
    """Una lista larga se lee como «pendiente» y no obliga a nada (principio nº 15).

    El número declarado es lo que la convierte en algo que hay que tocar. Falla en las
    DOS direcciones, y por eso sólo puede ir hacia abajo.
    """

    def setUp(self):
        self.informe = auditoria.auditar()
        self.cuantas = len(self.informe.por_consecuencia("VEREDICTO"))

    def test_no_SUBE_sin_que_alguien_lo_diga(self):
        self.assertLessEqual(
            self.cuantas,
            self.informe.techo,
            "hay una bandera que decide un veredicto y nadie la recorre de punta a "
            "punta. O se cubre, o se sube el techo en data/banderas.toml a propósito.",
        )

    def test_y_un_techo_CADUCADO_tambien_falla(self):
        self.assertGreaterEqual(
            self.cuantas,
            self.informe.techo,
            "se han cubierto banderas y el techo se quedó alto: bájalo en "
            "data/banderas.toml. Un techo caducado deja de apretar.",
        )


class TestLasExENCIONESsonDECLARADAS(unittest.TestCase):
    """No recorrer algo a propósito es legítimo; no decirlo, no."""

    def setUp(self):
        self.informe = auditoria.auditar()

    def test_toda_exenta_trae_su_MOTIVO(self):
        for fila in self.informe.exentas:
            self.assertTrue(fila["exento"], fila["clave"])

    def test_una_exenta_que_YA_se_recorre_esta_caducada(self):
        """Igual que las excepciones de alcanzabilidad: si alguien la cubrió, la
        exención sobra y hay que quitarla."""
        for fila in self.informe.exentas:
            self.assertFalse(
                fila["probada"],
                f"{fila['clave']} está exenta y además se recorre: quita la exención.",
            )


class TestLasCombinacionesNombranBanderasQueEXISTEN(unittest.TestCase):

    def test_cada_bandera_de_cada_combinacion_esta_declarada(self):
        vivas = {b.clave for b in auditoria.banderas_declaradas()}
        for combinacion in TABLA.get("combinacion", []):
            for bandera in combinacion["banderas"]:
                clave = f"{combinacion['cli']}:{bandera}"
                self.assertIn(clave, vivas, clave)


class TestElDetectorNOseEquivocaHaciaElSILENCIO(unittest.TestCase):
    """Un análisis que se equivoca hacia el silencio es peor que no tenerlo: no avisa y
    además tranquiliza. La primera versión de este detector falló en LAS DOS direcciones
    y por eso el criterio se contrasta aquí.
    """

    def setUp(self):
        self.ejercitadas = auditoria.banderas_ejercitadas()

    def test_resuelve_el_CLI_por_fichero_y_no_por_una_tabla_de_alias(self):
        """`import_scores` también importa su main como `main`. Con una tabla global,
        sus banderas se contaban como recorridas por `design`."""
        self.assertNotIn("--andamio", self.ejercitadas.get("design", set()))
        self.assertIn("--andamio", self.ejercitadas.get("import_scores", set()))

    def test_sigue_UN_nivel_de_ayudante(self):
        """`test_usar_manifiesto.py` llama por `self._correr([...])`, no a `main`
        directamente. Sin seguirlo, `--usar-manifiesto` salía como no recorrida."""
        self.assertIn("--usar-manifiesto", self.ejercitadas.get("design", set()))

    def test_una_corrida_que_se_espera_que_ABORTE_no_cuenta_como_recorrido(self):
        """`assertEqual(main([...]), 2)` comprueba que una entrada mala se rechaza. Es
        útil y NO atraviesa el camino — que es justo donde vivía la errata nº 31."""
        arbol = __import__("ast").parse(
            "self.assertEqual(main(['--scaffold', '/no/hay.toml']), 2)"
        )
        fuera = auditoria._llamadas_que_esperan_aborto(arbol)
        self.assertEqual(len(fuera), 1)

    def test_y_una_que_se_espera_que_TERMINE_BIEN_si_cuenta(self):
        arbol = __import__("ast").parse("self.assertEqual(main(['--estimar']), 0)")
        self.assertEqual(auditoria._llamadas_que_esperan_aborto(arbol), set())


if __name__ == "__main__":
    unittest.main()


# ─────── y bajar el trinquete: la primera que se cubre, de punta a punta ───────


class TestMirbaseSeRecorreENTERA(unittest.TestCase):
    """`--mirbase` conecta `mature.fa`, y con él el FAIL duro del núcleo de abundancia.

    Es la bandera VEREDICTO más consecuente de las que se podían cubrir HOY: su fichero
    está en el repositorio. Las otras urgentes esperan a un dato que no tenemos
    —`--apa-medido` necesita el 3'-end seq— o a una dependencia opcional
    —`--accesibilidad` necesita ViennaRNA—.

    No basta con que un test la NOMBRE: la errata nº 31 tenía llamador. Se corre
    `main()`, se comprueba que termina en 0 y se LEE la salida.
    """

    @classmethod
    def setUpClass(cls):
        import tempfile

        from shmir_design.reference import REFERENCES, fixture_available
        from tools.design import main

        cls.hay = fixture_available(REFERENCES["NM_011170.3"])
        if not cls.hay:
            return
        datos = RAIZ / "data" / "reference"
        cls.salida = Path(tempfile.mkdtemp())
        cls.codigo = main([
            "--fasta", str(datos / "NM_011170.3.fa"),
            "--genbank", str(datos / "NM_011170.3.gb"),
            "--name", "raton",
            "--mirbase", str(datos / "mature.fa"),
            "--mirbase-version", "22.1",
            "--mirbase-md5", "320a5a535c75bff442dbdc7bbccfff4c",
            "--out", str(cls.salida),
        ])
        informes = sorted(cls.salida.rglob("*informe*.txt"))
        cls.texto = informes[0].read_text(encoding="utf-8") if informes else ""

    def setUp(self):
        if not self.hay:
            self.skipTest("falta data/reference/NM_011170.3.fa")

    def test_la_corrida_termina_bien(self):
        self.assertEqual(self.codigo, 0)
        self.assertTrue(self.texto)

    def test_y_la_colision_de_seed_DEJA_de_estar_en_NOT_RUN(self):
        """Que es lo que la bandera existe para conseguir. Sin leer esto, la corrida
        podría terminar en 0 con el fichero conectado a nada."""
        plano = " ".join(self.texto.split())
        self.assertNotIn("no hay tabla de maduros de miRBase cargada", plano)
        self.assertIn("mature.fa", plano)

    def test_y_la_procedencia_del_fichero_VIAJA_al_informe(self):
        plano = " ".join(self.texto.split())
        self.assertIn("22.1", plano)

    def test_un_md5_QUE_NO_CUADRA_aborta(self):
        """La otra mitad: la bandera de md5 existe para PARAR, y ese camino también se
        recorre — con un `2` esperado, que aquí sí es el resultado correcto."""
        import tempfile

        from tools.design import main

        datos = RAIZ / "data" / "reference"
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                main([
                    "--fasta", str(datos / "NM_011170.3.fa"),
                    "--genbank", str(datos / "NM_011170.3.gb"),
                    "--name", "raton",
                    "--mirbase", str(datos / "mature.fa"),
                    "--mirbase-version", "22.1",
                    "--mirbase-md5", "0" * 32,
                    "--out", tmp,
                ]),
                2,
            )
