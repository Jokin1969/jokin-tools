"""La corrida que hace la PAGINA, entera y contra un golden.

Regla 5: escritos antes.

**Por que existe este fichero.** La suite tenia 2.767 tests en verde y la primera
ejecucion real de la pagina —`NM_011170.3.gb`, Mus musculus, sin subir nada— dio tres
fallos seguidos: un aborto de marco en el mapa, una aritmetica imposible entre la
estimacion y el resultado, y un recuento que decia una causa que no habia comprobado.
Ninguno de los tres es sutil. Lo que fallaba no era la cobertura de las funciones: era
que **nadie corria el camino de la pagina de punta a punta y miraba la salida entera**.

Es exactamente la leccion del golden del informe, aplicada un piso mas arriba: los tests
de presencia miran lo que cada uno se espera y no ven lo que falta. Y es la leccion del
test de humo de `/shmir`: un cliente que no se parece al real no prueba nada. Aqui el
"cliente real" es el camino que recorre la pagina con lo que el usuario sube.

El golden (`tests/golden/pagina_raton.txt`) fija ese camino ENTERO. Se regenera a mano
con `python3 tools/regenerar_golden.py` y el diff entra en la revision.
"""

import unittest

from shmir_design import coords, presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_reference

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _entrada():
    """Lo mismo que le llega a la pagina: el mRNA ENTERO y su anatomia verificada."""
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    return secuencia, anatomia


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElMapaRECIBEelMarco(unittest.TestCase):
    """Fallo real: `3utr:1856` sobre un 3'UTR de 1242 nt.

    Es la CUARTA vez que aparece la misma familia —`3utr:1784`, `3utr:1185`,
    `3utr:1398`— y ahora en el modulo del mapa. La contramedida de `coords` hizo su
    trabajo: aborto en vez de una posicion inventada. Lo que faltaba es que el mapa
    sacara el marco de la anatomia en vez de suponerlo.
    """

    @classmethod
    def setUpClass(cls):
        cls.secuencia, cls.anatomia = _entrada()
        cls.corrida = presentation.page_run(
            species="raton", sequence=cls.secuencia, anatomy=cls.anatomia
        )

    def test_lo_tilado_es_el_TRANSCRITO_y_su_marco_es_tx(self):
        # Si esto deja de ser `tx`, el resto de esta clase no prueba nada.
        self.assertIs(coords.frame_of(self.anatomia), coords.Frame.TX)

    def test_el_mapa_ya_no_ABORTA(self):
        svg = presentation.map_svg(self.corrida.tiling, self.corrida.selection)
        self.assertIn("<svg", svg)

    def test_y_las_posiciones_del_mapa_van_ETIQUETADAS_en_su_marco(self):
        svg = presentation.map_svg(self.corrida.tiling, self.corrida.selection)
        self.assertIn("tx:", svg)
        self.assertNotIn("3utr:1856", svg)

    def test_el_mapa_dibuja_el_3UTR_no_el_transcrito_entero(self):
        # El titulo dice «Mapa del 3'UTR». Si el eje mide 2191 nt, lo que se esta
        # pintando es el transcrito con otro nombre, y los tercios —que cuelgan de la
        # frontera del 3'UTR— caen donde no es.
        svg = presentation.map_svg(self.corrida.tiling, self.corrida.selection)
        self.assertIn("3'UTR de 1242 nt", svg)
        self.assertNotIn("3'UTR de 2191 nt", svg)

    def test_un_mapa_SIN_anatomia_aborta_en_vez_de_suponer_el_marco(self):
        sin = presentation.page_run(
            species="raton",
            sequence=self.secuencia[RATON.cds[1] :],
            anatomy=Anatomy.whole_is_utr3(
                len(self.secuencia) - RATON.cds[1],
                source=RegionSource.TODO_3UTR_DECLARADO,
            ),
        )
        # Ese si es 3'UTR entero: el marco es `3utr` y el mapa lo dice.
        svg = presentation.map_svg(sin.tiling, sin.selection)
        self.assertIn("3utr:", svg)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaEstimacionYLaCorridaCuentanLO_MISMO(unittest.TestCase):
    """Aritmetica imposible: «ventanas a tilar: 1221» y luego 1773 descartadas.

    No puede haber mas descartadas que totales. Salian de dos conjuntos distintos con
    el mismo nombre: la estimacion tilaba el 3'UTR (1242 nt) y la corrida el transcrito
    entero (2191 nt).
    """

    @classmethod
    def setUpClass(cls):
        cls.secuencia, cls.anatomia = _entrada()
        cls.corrida = presentation.page_run(
            species="raton", sequence=cls.secuencia, anatomy=cls.anatomia
        )

    def test_la_estimacion_recibe_LA_MISMA_secuencia_y_anatomia(self):
        texto = presentation.cost_text(self.secuencia, anatomy=self.anatomia)
        ventanas = len(self.corrida.tiling.windows)
        self.assertIn(f"ventanas a tilar:        {ventanas}", texto)

    def test_estimar_SIN_anatomia_aborta(self):
        # Es la regla de `resolve.py`: sin anatomia no se adivina el marco. Antes la
        # estimacion se la fabricaba con `whole_is_utr3`, y por eso contaba otra cosa.
        with self.assertRaises(ShmirDesignError):
            presentation.cost_text(self.secuencia, anatomy=None)

    def test_ninguna_cuenta_de_la_pagina_supera_al_TOTAL(self):
        total = len(self.corrida.tiling.windows)
        luz = presentation.status_light(self.corrida.selection)
        self.assertLessEqual(luz.not_eligible, total)
        self.assertLessEqual(luz.ran, luz.total)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElRecuentoNoDIAGNOSTICA(unittest.TestCase):
    """«1773 ventanas no evaluables (bases desconocidas o enmascaradas)» era falso.

    Ninguna de esas ventanas tenia una N ni estaba enmascarada: fallaban GC y
    homopolimero. El texto nombraba una causa que no se habia comprobado — la misma
    familia que el «comprueba que Streamlit esta instalado» y que el «Alu 0 %» obtenido
    sin buscar Alu. Un diagnostico equivocado cuesta mas que ninguno.
    """

    @classmethod
    def setUpClass(cls):
        secuencia, anatomia = _entrada()
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia
        )
        cls.luz = presentation.status_light(cls.corrida.selection)

    def test_el_numero_dice_DE_QUE_CONJUNTO_sale(self):
        # La descomposición va ENTERA: total, las que caen fuera del 3'UTR y las que
        # pasan los biofísicos, con su reparto. Un descartado sin total no se puede leer,
        # y un total sin reparto deja «¿de dónde sale ese número?» sin contestar — que es
        # exactamente lo que se preguntó al ver «1221» arriba y «1773» abajo.
        total = len(self.corrida.tiling.windows)
        fuera = sum(
            1 for w in self.corrida.selection.windows.values()
            if w.inicio_3utr is None
        )
        self.assertIn(f"{total} ventanas tiladas", self.luz.detail)
        self.assertIn(f"{fuera} caen FUERA del 3'UTR", self.luz.detail)
        self.assertIn(f"{total - fuera} dentro", self.luz.detail)
        self.assertEqual(self.luz.tiled, total)

    def test_y_NO_afirma_una_causa_que_no_ha_comprobado(self):
        self.assertNotIn("bases desconocidas", self.luz.detail)

    def test_sin_mascara_cargada_NO_se_menciona_el_enmascarado(self):
        self.assertIsNone(self.corrida.tiling.mask)
        self.assertNotIn("enmascarad", self.luz.detail)

    def test_la_cuenta_es_la_de_los_biofisicos_y_cuadra(self):
        elegibles = self.corrida.tiling.biofisicos_ok()
        self.assertEqual(
            self.luz.not_eligible, len(self.corrida.tiling.windows) - elegibles
        )


class TestElCOMPAÑERO_obligatorio_SE_VE(unittest.TestCase):
    """El `.tbl` era obligatorio y no aparecia en la lista de conectados.

    `rmsk_mouse.out` a solas NO cierra el frente —hay test— pero la lista de ficheros
    conectados solo nombraba el `.out`, asi que la pantalla se leia como «un frente
    cerrado con un .out a solas», que es justo lo que este proyecto promete no hacer.
    """

    def test_la_lista_de_conectados_nombra_el_compañero(self):
        from shmir_design.resources import describe_connected

        texto = describe_connected(("rmsk_mouse.out",), companions={
            "rmsk_mouse.out": ("rmsk_mouse.tbl",)
        })
        self.assertIn("rmsk_mouse.tbl", texto)

    def test_y_dice_PARA_QUE_hace_falta(self):
        from shmir_design.masking import INDISTINGUISHABLE_OUTS
        from shmir_design.resources import COMPANION_NOTE

        self.assertTrue(COMPANION_NOTE)
        self.assertIn("resumen", COMPANION_NOTE.lower())
        self.assertTrue(INDISTINGUISHABLE_OUTS)


class TestFrentesYFiltrosNoSonLO_MISMO(unittest.TestCase):
    """«2 de 7 frentes» y «8 de 12 filtros» en la misma pantalla.

    Son dos cuentas distintas y ninguna de las dos lo decia: los 7 son los frentes que
    cierra un FICHERO de referencia, los 12 son los filtros que se le corren a UN
    candidato — cinco de ellos biofisicos, que no necesitan fichero ninguno.
    """

    def test_el_paso_3_dice_que_cuenta_ficheros(self):
        from shmir_design.presentation import FRONTS_VS_FILTERS

        self.assertIn("fichero", FRONTS_VS_FILTERS.lower())
        self.assertIn("candidato", FRONTS_VS_FILTERS.lower())

    def test_los_dos_recuentos_van_ETIQUETADOS_distinto(self):
        from shmir_design.presentation import FILTER_COUNT_NAME, FRONT_COUNT_NAME

        self.assertNotEqual(FRONT_COUNT_NAME, FILTER_COUNT_NAME)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElGoldenDeLaPagina(unittest.TestCase):
    """La salida ENTERA de la pagina, comparada entera.

    Los tests de arriba miran cada uno lo suyo. Este mira lo que falta.
    """

    def test_la_instantanea_cuadra_con_el_golden(self):
        from pathlib import Path

        # La instantánea se pide al MISMO generador que escribe el golden. Pedirla aquí
        # por separado ya se dio: el test usaba la configuración por defecto y el
        # generador `n_candidates=10`, así que el golden decía 10 candidatos y el test
        # veía 6 — un fallo que no era del código sino de tener la corrida definida dos
        # veces. Es la misma lección que `resolve.py`: una definición, no dos.
        from tools.regenerar_golden import generar_pagina

        golden = Path(__file__).resolve().parent / "golden" / "pagina_raton.txt"
        if not golden.is_file():
            self.fail(
                f"No hay golden en {golden}. Se genera con "
                f"`python3 tools/regenerar_golden.py` y su diff entra en la revisión."
            )
        self.assertEqual(
            generar_pagina(),
            golden.read_text(encoding="utf-8"),
            "La salida de la página ha cambiado. Si es a propósito, regenera el golden "
            "con `python3 tools/regenerar_golden.py` y que el diff entre en la "
            "revisión; leerlo es para lo que existe.",
        )


if __name__ == "__main__":
    unittest.main()
