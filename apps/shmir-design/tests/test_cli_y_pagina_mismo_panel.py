"""El CLI y la página tienen que dar EL MISMO panel. Es la sexta divergencia.

Regla 5: escrito antes del arreglo.

**El fallo.** `tools/design.py` construía un `SelectionConfig(...)` pelado con
`apa_immune_quota=args.inmunes`, y `--inmunes` vale **0** por defecto. La decisión del
proyecto es **4** (`DEFAULT_IMMUNE_QUOTA`), y vive en `selection.default_config()`, que
es lo que llama `presentation.page_run`.

Resultado: los dos frontales daban paneles DISTINTOS sobre la misma secuencia.

    página  →  3utr: 10, 60, 143, **200**, 449, 553, 652, 735, 819, 1018, 1071
    CLI     →  3utr: 10, 60, 143, **359**, 449, 553, 652, 735, 819, 1018, 1071

`3utr:359` (+4,82) desplaza a `3utr:200` (+3,80) por asimetría, así que el panel del CLI
se quedaba con **TRES inmunes en vez de cuatro** — y no lo decía nadie, porque los dos
son del tercio proximal y la cuota de tercios se cumple igual. Es literalmente el fallo
que `default_config()` existe para cerrar, arreglado en la página y no en el CLI.

**Cómo apareció.** Del inventario de banderas: `--inmunes` salió como VEREDICTO sin
recorrido de punta a punta, y al mirar POR QUÉ nadie la pasaba se vio que su defecto
contradice la constante del proyecto. Nadie la pasa nunca, así que el CLI corre siempre
con la cuota apagada.

**Y esto es lo que se fija aquí**: no que `--inmunes` funcione, sino que los dos
frontales no puedan volver a separarse. Una bandera con un defecto distinto del de la
constante es una divergencia esperando a que alguien la lea.
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.selection import (
    DEFAULT_CANDIDATES,
    DEFAULT_IMMUNE_QUOTA,
    default_config,
    select_from_report,
)
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: El panel CONFIRMADO: coincide con el del responsable y está fijado en
#: `tests/test_promocion_por_defecto.py`. Si algo lo mueve, lo mueve a propósito.
# ONCE desde el 2026-09-06: la plaza once es el segundo distal, `3utr:1071`, y
# entra por `tercio_quota_by_start` — no por asimetria, que seria coincidencia.
PANEL = (10, 60, 143, 200, 449, 553, 652, 735, 819, 1018, 1071)


def _sitios(seleccion) -> tuple[int, ...]:
    """Los inicios en 3'UTR. Lo tilado es el transcrito, así que hay que convertir."""
    inicio_utr3 = RATON.cds[1] + 1
    return tuple(
        sorted(
            int(str(c.start).split(":")[-1]) - (inicio_utr3 - 1)
            for c in seleccion.selection.chosen
        )
    )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLosDosFrontalesDanElMismoPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.secuencia = load_reference(RATON)
        cls.anatomia = Anatomy.from_cds(
            cds=RATON.cds,
            length=len(cls.secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.informe = tile_utr(
            cls.secuencia, anatomy=cls.anatomia, species="raton"
        )

    def test_la_pagina_da_el_panel_CONFIRMADO(self):
        corrida = presentation.page_run(
            species="raton", sequence=self.secuencia, anatomy=self.anatomia
        )
        self.assertEqual(_sitios(corrida.selection), PANEL)

    def test_y_la_configuracion_que_monta_el_CLI_da_EL_MISMO(self):
        """La comprobación de verdad: se pide al CLI su configuración y se compara.

        Si alguien vuelve a construir un `SelectionConfig` pelado ahí, esto falla.
        """
        from tools.design import config_de_seleccion

        cli = select_from_report(self.informe, config_de_seleccion(_ArgsPorDefecto()))
        self.assertEqual(_sitios(cli), PANEL)

    def test_y_lleva_los_CUATRO_inmunes_que_son_la_unica_reserva(self):
        from tools.design import config_de_seleccion

        config = config_de_seleccion(_ArgsPorDefecto())
        self.assertEqual(config.apa_immune_quota, DEFAULT_IMMUNE_QUOTA)
        self.assertEqual(config.n_candidates, DEFAULT_CANDIDATES)

    def test_la_frontera_de_la_inmunidad_se_DERIVA_y_no_llega_tecleada(self):
        """Un corte escrito a mano no se entera de que un sitio medido lo adelante: pasó
        de `3utr:303` a `3utr:251` y la cifra tecleada siguió ahí sin dar ningún error."""
        from tools.design import config_de_seleccion

        self.assertIsNone(config_de_seleccion(_ArgsPorDefecto()).apa_immune_before)

    def test_y_el_defecto_del_CLI_es_el_MISMO_objeto_que_el_de_la_pagina(self):
        from tools.design import config_de_seleccion

        self.assertEqual(config_de_seleccion(_ArgsPorDefecto()), default_config())


class _ArgsPorDefecto:
    """Lo que argparse deja cuando no se pasa ninguna bandera de selección."""

    candidates = DEFAULT_CANDIDATES
    min_spacing = 50
    cuota_region = None
    reparto_rango = False


class TestLasBanderasRetiradasNoVuelven(unittest.TestCase):
    """Regresión de las que dejan de ser bandera porque ya son una decisión.

    Una bandera cuyo defecto contradice la constante del proyecto es una divergencia
    esperando: `--inmunes` valía 0 y la decisión son 4.
    """

    def test_no_hay_bandera_para_la_cuota_de_inmunes_ni_para_su_frontera(self):
        fuente = _fuente_del_cli()
        for retirada in ("--inmunes", "--inmunes-antes"):
            self.assertNotIn(f'"{retirada}"', fuente, retirada)

    def test_ni_para_la_cuota_por_tercio(self):
        self.assertNotIn('"--min-por-tercio"', _fuente_del_cli())

    def test_ni_una_puerta_de_atras_al_prefijo_de_miRBase(self):
        """Filtrar con el prefijo equivocado da CERO colisiones, que parece una buena
        noticia. El prefijo sale de `species.resolve()`."""
        self.assertNotIn('"--mirbase-especies"', _fuente_del_cli())

    def test_ni_un_modo_de_polyA_que_el_informe_ya_emite_bajo_las_dos_reglas(self):
        self.assertNotIn('"--polyA-modo"', _fuente_del_cli())

    def test_ni_una_mascara_por_intervalos_SIN_procedencia(self):
        """`--repeats` acepta intervalos pelados: sin especie, sin resumen y sin md5.
        La sustituyó `--rmsk`, que valida la corrida entera."""
        self.assertNotIn('"--repeats"', _fuente_del_cli())

    def test_ni_una_tabla_de_seeds_suelta(self):
        self.assertNotIn('"--seeds"', _fuente_del_cli())


def _fuente_del_cli() -> str:
    from pathlib import Path

    import tools.design as design

    return Path(design.__file__).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()


class TestLaCuotaPEDIDAyLaCuotaPORDEFECTOnoSonLoMismo(unittest.TestCase):
    """Salió al arreglar la divergencia, y es una decisión que hubo que tomar.

    Con `default_config()` en el CLI, la cuota de cuatro inmunes se aplica SIEMPRE — y
    `select_from_report` abortaba cuando el informe no tiene ninguna señal `APA_POSIBLE`:
    «no hay corte al que ser inmune». Sobre el ratón nunca pasa; sobre una secuencia
    cualquiera, siempre. Toda corrida del CLI con una entrada sin APA moría.

    La distinción es la misma que `default_config` ya aplicaba al tamaño del panel
    —«abortar por un defecto que quien llama no ha pedido sería peor que no tenerlo»—, y
    aquí faltaba el otro lado:

      - cuota PEDIDA + sin corte  → ABORTA. Pediste inmunes a algo que no existe.
      - cuota POR DEFECTO + sin corte → NO_APLICA, **y se dice**. No hay pregunta de
        inmunidad que contestar, así que no hay nada que abortar; pero una cuota que
        desaparece en silencio es lo mismo que no haberla tenido nunca.
    """

    def setUp(self):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.tiling import tile_utr

        # Una sonda sin ninguna señal de poliadenilación: no es un dato biológico y no
        # pretende serlo — lo que se prueba es qué hace la cuota cuando no hay corte.
        sonda = "GCGTCAGTACGATCGAATTACT" * 30
        self.informe = tile_utr(
            sonda,
            anatomy=Anatomy.whole_is_utr3(
                len(sonda), source=RegionSource.TODO_3UTR_DECLARADO
            ),
        )
        self.assertEqual(
            [s for s in self.informe.signals if s.classification.name == "APA_POSSIBLE"],
            [],
            "la sonda tiene señal de APA: este test no prueba lo que dice",
        )

    def test_la_cuota_PEDIDA_sigue_abortando(self):
        from shmir_design.selection import SelectionConfig

        with self.assertRaises(ValueError) as capturado:
            select_from_report(self.informe, SelectionConfig(apa_immune_quota=4))
        self.assertIn("no hay corte al que ser inmune", str(capturado.exception))

    def test_la_cuota_POR_DEFECTO_no_aborta(self):
        seleccion = select_from_report(self.informe, default_config())
        self.assertTrue(seleccion.selection.chosen)

    def test_pero_lo_DICE_en_las_notas_de_la_seleccion(self):
        """Y con las palabras del proyecto: NO_APLICA, no un hueco."""
        seleccion = select_from_report(self.informe, default_config())
        notas = " ".join(seleccion.selection.notes)
        self.assertIn("NO_APLICA", notas)
        self.assertIn("no hay corte al que ser inmune", notas)

    def test_y_distingue_las_dos_causas_del_panel_sin_reserva(self):
        """«No lleva reserva porque aquí no hay truncamiento que temer» y «no lleva
        reserva porque se renunció a ella» son cosas distintas, y la nota lo separa."""
        seleccion = select_from_report(self.informe, default_config())
        notas = " ".join(seleccion.selection.notes)
        self.assertIn("no porque se haya renunciado", notas)

    def test_sobre_el_RATON_la_cuota_SI_aplica_y_no_sale_ninguna_nota(self):
        if not HAY:
            self.skipTest("falta data/reference/NM_011170.3.fa")
        secuencia = load_reference(RATON)
        informe = tile_utr(
            secuencia,
            anatomy=Anatomy.from_cds(
                cds=RATON.cds,
                length=len(secuencia),
                source=RegionSource.FIXTURE_VERIFICADO,
            ),
            species="raton",
        )
        seleccion = select_from_report(informe, default_config())
        self.assertNotIn("NO_APLICA", " ".join(seleccion.selection.notes))
        self.assertEqual(_sitios(seleccion), PANEL)
