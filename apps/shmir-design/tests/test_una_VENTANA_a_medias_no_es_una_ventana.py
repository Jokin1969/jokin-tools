"""Un intervalo con un extremo desconocido NO es una ventana, y no marca ningun sitio.

**Reportado (2026-09-11), errata nº 162.** El modal de off-targets del panel humano moria
en la primera consulta:

    TypeError: '<=' not supported between instances of 'NoneType' and 'int'
    offtarget.py:970  propio = bool(window) and window[0] <= posicion <= window[1]

**`window` NO llegaba `None`. Llegaba `(None, 17)`** — y esa es la distincion entera: una
TUPLA NO VACIA ES VERDADERA aunque lleve un `None` dentro, asi que `bool(window)` pasaba y
reventaba en el indice. Es la errata nº 19: *la pregunta era por el CONTENIDO y la
comprobacion miro el CONTINENTE*.

**El caso es UNO y es real: `tx:825`.** `NM_000311.5` tiene el CDS en 68..829, asi que el
3'UTR empieza en `tx:830` y la ventana `tx:825-846` cae A CABALLO — 5 nt de CDS y 17 de
3'UTR. Su `region` sale `3'UTR` porque se decide por el PUNTO MEDIO (835) y su
`inicio_3utr` sale `None` porque se decide por el INICIO (825): dos definiciones que este
proyecto ya tenia registradas, chocando justo en esa frontera. Y como `825` es el menor
del panel, la corrida entera moria en la primera de sus 22 consultas.

**Y el proyecto ya se lo habia topado CUATRO veces**, resolviendolo cada vez en su sitio:
`tiling` lo ancla a 1 para el APA, `outputs` se niega expresamente a hacer
`inicio_3utr or window.start`, `selection` filtra los `None` y `presentation` los cuenta.
Este era el quinto. Principio nº 31: un comentario protege su linea, un mecanismo protege
al siguiente — asi que lo que entra no es un `if` mas, es `complete_window`.

**LA DECISION (2026-09-11)**, del responsable del proyecto: *«si `inicio_3utr` es `None`,
no se marca ningun sitio como suyo y se dice. Sin inventar coordenadas con solo
`fin_3utr`. El autoconteo de `tx:825` sale con su sitio propio SIN IDENTIFICAR, no con uno
inventado»*. De ahi el tercer estado de `own_window`: `None` no es `False`.

Regla 5: escritos antes.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.coords import Frame
from shmir_design.offtarget import (
    WINDOW_WITHOUT_UTR3_START, complete_window, self_count, self_sites,
)
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design import presentation as P

HUMANO = REFERENCES["NM_000311.5"]

#: La hebra y la diana del caso, minimas: lo que se prueba es el GUARDIA, no el conteo.
HEBRA = "ACGTACGTACGTACGTACGTAC"


class TestUnaTuplaConUnNoneNoEsUnaVentana(unittest.TestCase):
    """La mecanica, sin panel de por medio."""

    def test_complete_window_pide_los_DOS_extremos(self):
        for entrada in (None, (), (None, 17), (5, None), (None, None)):
            with self.subTest(entrada=entrada):
                self.assertIsNone(complete_window(entrada))
        self.assertEqual(complete_window((5, 17)), (5, 17))

    def test_y_LA_TUPLA_A_MEDIAS_ES_VERDADERA(self):
        """El control que explica el fallo: `bool` no sirve para esta pregunta.

        Sin este caso, «`complete_window` devuelve `None`» y «el guardia de antes ya
        valia» se leerian igual.
        """
        self.assertTrue(bool((None, 17)), "si esto fuera falso no habria habido errata")

    def test_con_la_ventana_a_medias_NO_revienta_y_NO_marca_ninguno(self):
        diana = "A" * 20 + HEBRA + "A" * 20
        sitios = self_sites(
            HEBRA, target=diana, frame=Frame.UTR3, window=(None, 17),
        )
        self.assertTrue(sitios, "el barrido no ha encontrado nada que marcar")
        for sitio in sitios:
            with self.subTest(sitio.position):
                self.assertIsNone(
                    sitio.own_window,
                    "una ventana a medias no puede decir cuál es el suyo, y `False` "
                    "diría «SEGUNDO SITIO» del que probablemente ES el suyo.",
                )
                self.assertIn("sin identificar", sitio.describe())

    def test_con_la_ventana_ENTERA_sigue_marcando_el_suyo(self):
        """La otra mitad: sin esto, «no marca ninguno» y «no marca nunca» dan igual."""
        diana = "A" * 20 + HEBRA + "A" * 20
        sitios = self_sites(HEBRA, target=diana, frame=Frame.UTR3, window=(1, 60))
        self.assertTrue(any(s.own_window is True for s in sitios))

    def test_y_SIN_VENTANA_sigue_siendo_False_y_no_None(self):
        """No haber pasado ventana y haberla pasado a medias son DOS causas.

        La primera la explica el docstring de `self_sites` —nadie la pasó— y la segunda
        es la frontera. Colapsarlas haría que un alcance sin ventanas se leyera como un
        candidato a caballo del CDS.
        """
        diana = "A" * 20 + HEBRA + "A" * 20
        sitios = self_sites(HEBRA, target=diana, frame=Frame.UTR3, window=None)
        self.assertTrue(sitios)
        self.assertTrue(all(s.own_window is False for s in sitios))


class TestElMotivoVIAJAconElAutoconteo(unittest.TestCase):
    """No basta con no reventar: hay que decir POR QUE no se identifica ninguno."""

    def _cuenta(self, window):
        diana = "A" * 20 + HEBRA + "A" * 20
        return self_count(
            HEBRA, target=diana, target_label="3'UTR de prueba", frame=Frame.UTR3,
            window=window, strand_name="guia",
        )

    def test_con_la_ventana_a_medias_el_motivo_esta(self):
        cuenta = self._cuenta((None, 17))
        self.assertFalse(cuenta.own_site_known)
        self.assertEqual(cuenta.own_window_reason, WINDOW_WITHOUT_UTR3_START)
        # Y va PEGADO a la lectura, que es la línea que se copia y se descarga: sin él,
        # «sin identificar» se lee como que el candidato no tiene su propio sitio.
        self.assertIn("CRUZA la frontera", cuenta.describe())

    def test_y_con_la_ventana_entera_NO_sale(self):
        cuenta = self._cuenta((1, 60))
        self.assertTrue(cuenta.own_site_known)
        self.assertEqual(cuenta.own_window_reason, "")
        self.assertNotIn("CRUZA la frontera", cuenta.describe())

    def test_sin_ventana_tampoco_sale_ese_motivo(self):
        # Es otra causa: nadie pasó ventana. Decir «cruza la frontera» ahí sería un
        # diagnóstico equivocado, que cuesta más que ninguno (principio nº 3).
        self.assertEqual(self._cuenta(None).own_window_reason, "")


@unittest.skipUnless(
    fixture_available(HUMANO), "NOT_RUN: falta data/reference/NM_000311.5.fa"
)
class TestElCasoREAL_tx825(unittest.TestCase):
    """Sobre el panel humano de verdad, que es donde vive el fallo."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(HUMANO)
        anatomia = Anatomy.from_cds(
            cds=HUMANO.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = P.page_run(
            species="human", sequence=secuencia, anatomy=anatomia,
        )
        cls.sel = cls.corrida.selection
        cls.ventanas = {c.start: cls.sel.window_of(c) for c in cls.sel.selection.chosen}

    def test_EL_PANEL_TRAE_una_ventana_a_caballo_y_SOLO_una(self):
        # Prueba de vida: si el panel dejara de traerla, todo lo de abajo pasaría sin
        # comprobar nada y habría que mirar por qué (principio nº 51).
        a_medias = [
            inicio for inicio, w in self.ventanas.items() if w.inicio_3utr is None
        ]
        self.assertEqual(
            a_medias, [825],
            "el panel humano ya no trae `tx:825`, que es el caso que esto cubre.",
        )

    def test_y_su_ventana_CRUZA_la_frontera(self):
        ventana = self.ventanas[825]
        self.assertTrue(ventana.cruza_frontera)
        self.assertEqual(ventana.region.value, "3'UTR")
        self.assertIsNone(ventana.inicio_3utr)
        self.assertIsNotNone(ventana.fin_3utr)

    def test_LA_FICHA_de_tx825_lo_deja_ESCRITO(self):
        """La segunda decisión: el informe de `tx:825` lo dice, como DATO de diseño.

        No basta con que `boundary_note` devuelva el texto — ya pasó once veces en este
        proyecto que algo se calculara y no llegara a ninguna salida. Se mira la ficha
        RENDERIZADA, que es lo que se descarga y lo que se lee sin la app delante.
        """
        from shmir_design.dossier import build_dossier
        from shmir_design.tiling import CROSSES_BOUNDARY_HEADING

        ficha = build_dossier(
            species="human", tiling=self.corrida.tiling, selection=self.sel, start=825,
        )
        texto = ficha.render()
        self.assertIn("Anatomía de la ventana", texto)
        self.assertIn(CROSSES_BOUNDARY_HEADING, texto)
        # Las dos cifras, DERIVADAS de la ventana y no transcritas (principio nº 13).
        ventana = self.ventanas[825]
        dentro = ventana.fin_3utr
        largo = ventana.window.length
        self.assertIn(f"{largo} nt", texto)
        self.assertIn(f"{largo - dentro} caen", texto)
        # Y es un DATO, no una advertencia de fallo: lo dice con esas palabras. Se mira
        # sobre el campo y no sobre lo renderizado porque el ajuste de línea parte la
        # frase — un test anclado al texto ya ajustado se rompe al cambiar el ancho.
        self.assertIn("NO es un fallo ni una advertencia", ficha.boundary_note)

    def test_y_LA_DE_OTRO_CANDIDATO_no_la_lleva(self):
        """La otra mitad: una nota que saliera siempre dejaría de leerse."""
        from shmir_design.dossier import build_dossier

        otro = next(c for c in self.sel.selection.chosen if c.start != 825)
        texto = build_dossier(
            species="human", tiling=self.corrida.tiling, selection=self.sel,
            start=otro.start,
        ).render()
        self.assertNotIn("Anatomía de la ventana", texto)

    def test_el_intervalo_que_reventaba_se_monta_igual(self):
        # No se cambia lo que `run_scan` construye —el intervalo sigue siendo
        # `(inicio_3utr, fin_3utr)`— porque el dato es correcto: lo que estaba mal era
        # la pregunta que se le hacía.
        ventana = self.ventanas[825]
        intervalo = (ventana.inicio_3utr, ventana.fin_3utr)
        self.assertTrue(bool(intervalo))
        self.assertIsNone(complete_window(intervalo))


if __name__ == "__main__":
    unittest.main()
