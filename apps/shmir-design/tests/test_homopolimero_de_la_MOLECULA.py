"""El homopolímero se mide sobre lo que se SINTETIZA: guía y pasajera.

Regla 5: escrito antes del arreglo.

**El fallo.** El filtro biofísico medía la VENTANA DIANA, y lo que se manda a sintetizar
no es la ventana: es la guía —con una U forzada en la posición 1 (paso 6)— y la pasajera
—con la posición 1 desapareada—. Entre una cosa y la otra hay **dos sustituciones de la
posición 1** que el filtro nunca veía, y las dos pueden crear un tramo de 4.

Salió en la hoja de pedido del panel murino (2026-09-07): cuatro de los once con
`check:homopolimeros` en FAIL y su ventana en PASS.

| candidato | ventana | dónde sale el 4 | quién lo crea |
|---|---|---|---|
| `3utr:143` | `GCCCTGGGAAATGTACAGTAGA`, tramo 3 | pasajera 1-4 `CCCC` | mismatch de la pasajera |
| `3utr:652` | `GAGGGATGGTTAAGGTACAAAG`, tramo 3 | guía 1-4 `TTTT` | U forzada en la posición 1 |
| `3utr:735` | `GCCCTATGTTTCTGTACTTCTA`, tramo 3 | pasajera 1-4 `CCCC` | mismatch de la pasajera |
| `3utr:819` | `GCTCCATTCCAAAGTGGGAAAG`, tramo 3 | guía 1-4 `TTTT` | U forzada en la posición 1 |

**Lo que se fija aquí NO es que los cuatro caigan** —eso es la consecuencia—, sino que
las DOS medidas existan y digan cosas distintas: la de la ventana sigue en PASS y la de
la molécula en FAIL. Borrar la primera perdería la comparación, que es justo lo que hace
visible que el filtro estaba midiendo un sustituto (decisión del responsable del
proyecto, 2026-09-07).
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.filters import BIOPHYSICAL_FILTERS, FilterState
from shmir_design.hard_filters import MAX_HOMOPOLYMER, longest_homopolymer
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.scaffold import (
    MOLECULE_HOMOPOLYMER,
    filter_molecule_homopolymer,
    passenger_from_guide,
)
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: Los cuatro del panel, en el marco de lo TILADO (transcrito) y en el del 3'UTR.
#: Se dan los dos porque una posición sin marco es válida en dos sitios (errata nº 133).
LOS_CUATRO = {
    1092: {"utr3": 143, "base": "C", "largo": 4, "donde": "pasajera"},
    1601: {"utr3": 652, "base": "T", "largo": 4, "donde": "guía"},
    1684: {"utr3": 735, "base": "C", "largo": 4, "donde": "pasajera"},
    1768: {"utr3": 819, "base": "T", "largo": 4, "donde": "guía"},
}


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLasDosMedidasSonDistintas(unittest.TestCase):
    """La de la ventana y la de la molécula. Ninguna sustituye a la otra."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.informe = tile_utr(secuencia, anatomy=anatomia, species="raton")
        cls.por_inicio = {w.window.start: w for w in cls.informe.windows}

    def test_los_cuatro_fallan_en_la_MOLECULA(self):
        for inicio, esperado in LOS_CUATRO.items():
            with self.subTest(inicio=inicio):
                ventana = self.por_inicio[inicio]
                resultado = ventana.filter(MOLECULE_HOMOPOLYMER)
                self.assertIs(resultado.state, FilterState.FAIL)
                # El motivo dice CUANTO, DE QUE BASE y DONDE. Un «falla» a secas mandaría
                # a mirar la ventana, que es justo la que está bien (principio nº 3).
                self.assertIn(f"{esperado['largo']} {esperado['base']}", resultado.reason)
                self.assertIn(esperado["donde"], resultado.reason)

    def test_y_su_VENTANA_sigue_en_PASS(self):
        """Que la ventana pase NO es un descuido: es el hallazgo."""
        for inicio in LOS_CUATRO:
            with self.subTest(inicio=inicio):
                ventana = self.por_inicio[inicio]
                self.assertIs(ventana.filter("homopolimero").state, FilterState.PASS)
                base, largo = longest_homopolymer(ventana.evaluation.sequence)
                self.assertLessEqual(largo, MAX_HOMOPOLYMER, f"tramo {largo}{base}")

    def test_el_VECINO_corrido_UN_nucleotido_si_pasa(self):
        """El 4 lo crea la posición 1, así que correr la ventana 1 nt lo deshace.

        Es lo que hace que los sustitutos del panel sean los de al lado, y por eso se
        fija: si algún día dejara de ser cierto, el arreglo de este fallo cambiaría de
        forma sin que nadie se enterara.
        """
        for inicio, vecino in ((1092, 1093), (1601, 1600), (1684, 1685), (1768, 1767)):
            with self.subTest(inicio=inicio):
                self.assertIs(
                    self.por_inicio[vecino].filter(MOLECULE_HOMOPOLYMER).state,
                    FilterState.PASS,
                )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElAtajoDaLoMISMOQuePlegarSiempre(unittest.TestCase):
    """Principio nº 5: dos implementaciones del mismo número se CRUZAN.

    El camino rápido decide sin plegar salvo cuando la base de la posición 1 puede
    cambiar la respuesta. La referencia pliega SIEMPRE. Tienen que coincidir en las
    2170 ventanas reales, no en un ejemplo de juguete: si divergen, el atajo se lleva
    por delante candidatos sin que nadie lo vea.
    """

    def test_coinciden_en_TODAS_las_ventanas_del_raton(self):
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        informe = tile_utr(secuencia, anatomy=anatomia, species="raton")
        mirados = 0
        for ventana in informe.windows:
            guia = ventana.evaluation.guide
            rapido = filter_molecule_homopolymer(guia)
            # La referencia: montar la pasajera SIEMPRE y medir las dos cadenas.
            pasajera = passenger_from_guide(guia).sequence
            peor = max(
                longest_homopolymer(guia.replace("U", "T"))[1],
                longest_homopolymer(pasajera)[1],
            )
            esperado = (
                FilterState.FAIL if peor > MAX_HOMOPOLYMER else FilterState.PASS
            )
            self.assertIs(rapido.state, esperado, ventana.window.name)
            mirados += 1
        # Control de que el barrido ha mirado algo (principio nº 51): un bucle sobre una
        # lista vacía pasa sin comprobar nada.
        self.assertGreater(mirados, 2000, "el barrido no recorrió las ventanas")


class TestElFiltroNuevoNoSeCuelaEnLosBIOFISICOS(unittest.TestCase):
    """No depende SOLO de la secuencia: depende del andamio y de ViennaRNA.

    Meterlo en `BIOPHYSICAL_FILTERS` movería el contador de referencia del proyecto —el
    que se puede comprobar sin miRBase, sin gnomAD y sin red— y lo haría depender de una
    dependencia opcional.
    """

    def test_no_esta_entre_los_biofisicos(self):
        self.assertNotIn(MOLECULE_HOMOPOLYMER, BIOPHYSICAL_FILTERS)


class TestElUmbralSeDERIVAYNoSeTranscribe(unittest.TestCase):
    """Principio nº 13. Estaba escrito `= 3` en cuatro módulos distintos."""

    def test_blocks_usa_el_umbral_de_hard_filters(self):
        from shmir_design import blocks

        self.assertIs(blocks.MAX_HOMOPOLYMER, MAX_HOMOPOLYMER)

    def test_gblock_usa_el_umbral_de_hard_filters(self):
        from shmir_design import gblock

        self.assertIs(gblock.MAX_HOMOPOLYMER, MAX_HOMOPOLYMER)

    def test_spacers_usa_el_umbral_de_hard_filters(self):
        from shmir_design import spacers

        self.assertIs(spacers.MAX_HOMOPOLYMER, MAX_HOMOPOLYMER)


class TestSinViennaRNANoSeInventaLaPasajera(unittest.TestCase):
    """Sin plegado la posición 1 se elegiría con la regla que el proyecto DESCARTÓ.

    La guía no necesita plegado, así que un fallo suyo sigue siendo FAIL. Lo que no se
    puede afirmar es la pasajera: eso es NOT_RUN con el motivo, nunca PASS.
    """

    def test_la_guia_falla_igual_sin_plegado(self):
        # `3utr:652`: el TTTT está en la guía, y la guía se conoce sin plegar nada.
        guia = "UUUUGUACCUUAACCAUCCCUC"
        resultado = filter_molecule_homopolymer(guia, available=False)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("guía", resultado.reason)

    def test_pero_la_pasajera_queda_en_NOT_RUN_y_lo_dice(self):
        # `3utr:143`: la guía está limpia y el CCCC lo crea la posición 1 de la pasajera.
        guia = "UCUACUGUACAUUUCCCAGGGC"
        resultado = filter_molecule_homopolymer(guia, available=False)
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("ViennaRNA", resultado.reason)
        # La fórmula del proyecto, entera: un NOT_RUN que no lo diga se lee como un
        # PASS silencioso.
        self.assertIn("NOT_RUN no es PASS", resultado.reason)
