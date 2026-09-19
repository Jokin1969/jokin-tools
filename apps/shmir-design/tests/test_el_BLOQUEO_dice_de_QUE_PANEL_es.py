"""Un bloqueo por corrida repetida dice de QUE PANEL es la corrida que bloquea.

**Reportado (2026-09-11).** Con el panel humano activo, la app bloqueo el guardado de una
corrida de `seed_colision` por `result_md5` repetido y dijo ademas que lo registrado cubre
**0 de 11** candidatos del panel. De ahi se dedujo una colision de md5 entre paneles
distintos.

**ESA COLISION NO PUEDE DARSE, y se midio antes de tocar nada** (ver
`TestDosPanelesNoPuedenColisionar`): cada linea del crudo empieza por
`query_name(especie, inicio, hebra)` —`human_pos825_guia` frente a `mouse_pos60_guia`—,
asi que el contexto del panel YA esta dentro del identificador, no como un campo aparte
sino porque el id se DERIVA de un crudo en el que cada linea identifica su consulta.

**Lo que si faltaba es que el bloqueo lo DIJERA.** Decia cuantos cubre y no de que panel
es, asi que de que panel venia la corrida que bloquea habia que deducirlo — y deducir de
que panel es un registro es exactamente lo que este proyecto no deja hacer con nada mas.
Principio nº 47: la salida va donde esta el bloqueo.

Regla 5: escritos antes. Python 3.11+, solo biblioteca estandar (regla 6).
"""

import unittest

from shmir_design import presentation as P


class TestLaInversaDeQueryName(unittest.TestCase):
    """`query_panel` lee de vuelta lo que `query_name` escribe."""

    def test_ida_y_VUELTA_para_todas_las_especies_declaradas(self):
        from shmir_design.species import SPECIES, resolve

        for nombre in SPECIES:
            for hebra in P.STRANDS:
                with self.subTest(nombre, hebra=hebra):
                    clave = P.query_name(nombre, 825, hebra)
                    self.assertEqual(P.query_panel(clave), resolve(nombre).slug)

    def test_un_ALIAS_viejo_se_NORMALIZA(self):
        """Antes de la errata nº 42 la clave llevaba el nombre que se pinta.

        Un log de entonces puede traer `raton_pos200_guia`, y `raton` es un ALIAS. Sin
        normalizar, una corrida de entonces se leería como de otro panel y el aviso que
        esto añade sería un falso positivo — un guardia con falsos positivos se apaga.
        """
        self.assertEqual(P.query_panel("raton_pos200_guia"), "mouse")

    def test_lo_que_NO_tiene_la_forma_devuelve_VACIO_y_no_adivina(self):
        for nombre in ("Mus_pos1_guia", "basura", "", "_pos1_guia", None):
            with self.subTest(nombre):
                self.assertEqual(P.query_panel(nombre), "")


class TestDosPanelesNoPuedenColisionar(unittest.TestCase):
    """La premisa del reporte, medida: el panel YA está dentro del md5.

    Se construye el PEOR caso posible —mismo eje declarado, mismo heptámero, mismo nivel
    y los mismos nombres de miARN, o sea suponiendo que todo lo biológico coincide— y aun
    así los dos crudos dan md5 distintos, porque lo que va delante de cada línea no.
    """

    #: Los dos paneles reales, en sus marcos. No se recalculan aquí: se declaran una vez
    #: en `panel_confirmado` y se leen (principio nº 13).
    def _crudo(self, especie, inicios):
        from shmir_design.species import resolve

        lineas = ["# organismo\tmouse\tmmu-"]
        for inicio in inicios:
            for hebra in P.STRANDS:
                lineas.append(
                    f"{P.query_name(resolve(especie), inicio, hebra)}"
                    f"\tAAAAAAA\tLIMPIO\t"
                )
        return "\n".join(lineas) + "\n"

    def test_el_mismo_resultado_en_DOS_PANELES_da_md5_DISTINTO(self):
        from shmir_design.identidad import result_fingerprint

        humano = self._crudo("human", [825, 939, 1019])
        raton = self._crudo("mouse", [60, 144, 200])
        self.assertNotEqual(result_fingerprint(humano), result_fingerprint(raton))

    def test_y_NI_SIQUIERA_con_las_MISMAS_POSICIONES(self):
        """El caso extremo: dos paneles que coincidieran posición a posición.

        Sin la especie dentro, éstos SÍ colisionarían — y es lo que el reporte describía.
        """
        from shmir_design.identidad import result_fingerprint

        mismas = [825, 939, 1019]
        self.assertNotEqual(
            result_fingerprint(self._crudo("human", mismas)),
            result_fingerprint(self._crudo("mouse", mismas)),
        )



class TestElControlAdversario(unittest.TestCase):
    """Sin la especie delante, los dos crudos SÍ colisionan.

    Es la mitad que explica por qué el arreglo no hace falta: si `query_name` no llevara
    el slug, la colisión del reporte sería real. Sin este caso, «no colisionan» y «el
    test no compara nada» dan el mismo verde.
    """

    def test_sin_el_slug_delante_DOS_PANELES_SI_colisionarian(self):
        from shmir_design.identidad import result_fingerprint

        def crudo(especie, inicios):
            """El mismo generador, pero IGNORANDO la especie: así era el fallo."""
            del especie  # ← justo lo que `query_name` no hace
            lineas = ["# organismo\tmouse\tmmu-"]
            for inicio in inicios:
                for hebra in P.STRANDS:
                    lineas.append(f"pos{inicio}_{hebra}\tAAAAAAA\tLIMPIO\t")
            return "\n".join(lineas) + "\n"

        # DOS paneles distintos que compartieran posiciones. Con el slug delante dan md5
        # distintos (el test de arriba); sin él, el mismo — que es la colisión reportada.
        mismas = [825, 939, 1019]
        self.assertEqual(
            result_fingerprint(crudo("human", mismas)),
            result_fingerprint(crudo("mouse", mismas)),
            "sin la especie delante los dos paneles darían el mismo md5: es lo que el "
            "slug de `query_name` compra, y por eso la colisión reportada no puede darse.",
        )


class TestElAvisoDeOtroPanel(unittest.TestCase):
    """Lo que sí faltaba: que el bloqueo diga de qué panel es lo registrado."""

    class _CorridaFalsa:
        def __init__(self, nombres):
            self.query_names = tuple(nombres)

    class _AlmacenFalso:
        def __init__(self, corridas):
            self.runs = list(corridas)

    def _stores(self, nombres):
        return {"seed": self._AlmacenFalso([self._CorridaFalsa(nombres)])}

    def test_los_paneles_registrados_se_DERIVAN_de_las_consultas(self):
        stores = self._stores(["mouse_pos60_guia", "mouse_pos60_pasajera"])
        self.assertEqual(P.registered_panels(stores, "seed_colision"), ("mouse",))

    def test_un_frente_SIN_ALMACEN_no_inventa_nada(self):
        self.assertEqual(P.registered_panels({}, "seed_colision"), ())
        self.assertEqual(P.registered_panels(None, "seed_colision"), ())

    def test_y_un_frente_que_no_tiene_almacen_tampoco(self):
        self.assertEqual(P.registered_panels(self._stores([]), "repeticiones"), ())

    def test_el_aviso_SALE_cuando_lo_registrado_es_de_otro_panel(self):
        texto = P._otro_panel(
            self._stores(["mouse_pos60_guia"]), "seed_colision", "human"
        )
        self.assertIn("mouse", texto)
        self.assertIn("human", texto)
        self.assertIn("NO del de hoy", texto)

    def test_y_NO_SALE_cuando_es_del_MISMO(self):
        """La otra mitad: un aviso que saliera siempre dejaría de leerse."""
        self.assertEqual(
            P._otro_panel(self._stores(["human_pos825_guia"]), "seed_colision", "human"),
            "",
        )

    def test_NI_con_un_alias_viejo_del_mismo_panel(self):
        # `raton_pos200_guia` en un log viejo ES el panel murino: sobre un diseño murino
        # no puede salir el aviso.
        self.assertEqual(
            P._otro_panel(self._stores(["raton_pos200_guia"]), "seed_colision", "mouse"),
            "",
        )

    def test_una_consulta_SIN_FORMA_no_dispara_el_aviso(self):
        # Vacío significa «no se ha podido leer», y eso no es «es de otro panel».
        self.assertEqual(
            P._otro_panel(self._stores(["basura"]), "seed_colision", "human"), ""
        )


@unittest.skipUnless(
    __import__("shmir_design.reference", fromlist=["x"]).fixture_available(
        __import__("shmir_design.reference", fromlist=["x"]).REFERENCES["NM_000311.5"]
    ),
    "NOT_RUN: falta data/reference/NM_000311.5.fa",
)
class TestSOBRE_EL_PANEL_DE_VERDAD(unittest.TestCase):
    """El caso reportado, entero: panel humano y una corrida murina registrada.

    Se comprueba sobre `pending_after_duplicate` —lo que la página pinta— y no sólo
    sobre `_otro_panel`: la cabecera puede estar perfecta y no llegar al texto.
    """

    class _Corrida:
        query_names = ("mouse_pos60_guia", "mouse_pos60_pasajera")

    class _Almacen:
        def __init__(self, corridas):
            self.runs = list(corridas)

        def history(self, consulta):
            return ()

        def latest(self, consulta, **kwargs):
            return None

        def verdict_for(self, consulta, **kwargs):
            return None

    @classmethod
    def setUpClass(cls):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.reference import REFERENCES, load_reference

        humano = REFERENCES["NM_000311.5"]
        secuencia = load_reference(humano)
        anatomia = Anatomy.from_cds(
            cds=humano.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = P.page_run(
            species="human", sequence=secuencia, anatomy=anatomia
        )

    def _pendiente(self, corridas):
        return P.pending_after_duplicate(
            self.corrida.tiling, self.corrida.selection, species="human",
            front="seed_colision", stores={"seed": self._Almacen(corridas)},
        )

    def test_el_texto_NOMBRA_el_panel_de_lo_registrado(self):
        texto = self._pendiente([self._Corrida()])["texto"]
        self.assertIn("es del panel mouse", texto)
        self.assertIn("NO del de hoy (human)", texto)
        # Y SIGUE diciendo lo de antes: la cabecera se añade, no sustituye.
        self.assertIn("0 de 11", texto)

    def test_y_la_cabecera_va_DELANTE(self):
        """Cambia lo que hay que hacer, así que no puede ir al final."""
        texto = self._pendiente([self._Corrida()])["texto"]
        self.assertLess(texto.index("es del panel mouse"), texto.index("0 de 11"))

    def test_SIN_corridas_registradas_no_dice_nada_de_ningun_panel(self):
        # Prueba de vida: sin corridas, la cabecera tiene que callarse — si saliera
        # igual, estaría saliendo siempre y dejaría de leerse.
        self.assertNotIn("es del panel", self._pendiente([])["texto"])


if __name__ == "__main__":
    unittest.main()
