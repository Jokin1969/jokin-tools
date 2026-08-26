"""Las tres plazas del bloque «solo de fuente externa» se reasignan a COBERTURA.

Regla 5: escritos antes.

El bloque desaparece por vacio: contra los 90 sitios elegibles no hay ni un sitio
exclusivo de la fuente externa que supere nuestros filtros duros (ver
tests/test_convergencia.py). Esas plazas no se pierden ni se reparten por asimetria —
que es lo que las daria a la region que mas candidatos buenos tenga— sino que compran
lo unico que sigue comprando independencia entre apuestas cuando la prediccion esta
saturada: SEPARACION.

Dos cuotas nuevas, y las dos son minimos duros:

- `min_per_tercio`: al menos N candidatos por tercio del 3'UTR.
- `apa_immune_quota` sobre `apa_immune_before`: al menos N candidatos que empiecen POR
  DELANTE del corte de la señal proximal, o sea inmunes al truncamiento. Con 60, 143 y
  221 ya son tres; la cuota pide cinco.

Justificacion, que va escrita en el informe: las causas de fallo son REGIONALES, no
puntuales. Cinco candidatos en el mismo tramo comparten modo de fallo aunque tengan
asimetrias distintas.

Datos reales: el 3'UTR verificado de NM_011170.3.
"""

import unittest
from pathlib import Path

from shmir_design.polya import Tercio
from shmir_design.selection import SelectionConfig, select_from_report

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"

#: Las dos definiciones de «inmune», y no dan lo mismo. El AATAAA de 3utr:288 termina
#: en 293 y su corte cae entre +10 y +30:
#:   ESTRICTA  — por delante del corte mas TEMPRANO (303): la ventana se conserva en las
#:               dos isoformas pase lo que pase. Es la que vale como inmune.
#:   LAXA      — por delante del corte mas TARDIO (323): admite ventanas de DENTRO de la
#:               banda de 20 nt, que `polya_risk` clasifica PENALIZADO, no NO_APLICA.
#: Llamar inmune a una de la banda seria inventarse una precision que no hay.
CORTE_ESTRICTO = 303
CORTE_LAXO = 323
CORTE = CORTE_ESTRICTO


def _tiling():
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence
    from shmir_design.tiling import tile_utr

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return tile_utr(normalize_sequence(bruta, name="NM_011170.3")[949:])


class TestLaConfiguracionSeValida(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling = _tiling()

    def test_una_cuota_de_inmunes_sin_corte_se_DERIVA_del_informe(self):
        # Antes esto abortaba al construir la config. Ahora `None` significa «sacalo del
        # informe», que es mejor que teclearlo: un corte escrito a mano no se entera de
        # que un sitio de corte MEDIDO adelante la frontera de la inmunidad.
        from shmir_design.selection import derive_immune_cut

        config = SelectionConfig(n_candidates=6, apa_immune_quota=2)
        self.assertIsNone(config.apa_immune_before)
        self.assertEqual(derive_immune_cut(self.tiling), 303)

    def test_pero_elegir_sin_resolverlo_SIGUE_abortando(self):
        from shmir_design.selection import choose, eligible_choices, group_choices

        sitios = group_choices(eligible_choices(self.tiling))
        with self.assertRaises(ValueError) as ctx:
            choose(sitios, SelectionConfig(n_candidates=6, apa_immune_quota=2))
        self.assertIn("inmunes A QUE", str(ctx.exception))

    def test_una_cuota_de_inmunes_mayor_que_el_panel_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(
                n_candidates=4, apa_immune_quota=5, apa_immune_before=CORTE
            )

    def test_min_per_tercio_negativo_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(n_candidates=10, min_per_tercio=-1)

    def test_min_per_tercio_que_no_cabe_aborta(self):
        # 3 tercios x 4 = 12 > 10: la cuota no cabe y no se recorta en silencio.
        with self.assertRaises(ValueError):
            SelectionConfig(n_candidates=10, min_per_tercio=4)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElPanelDeDiez(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling = _tiling()
        cls.seleccion = select_from_report(
            cls.tiling,
            SelectionConfig(
                n_candidates=10,
                min_per_tercio=2,
                apa_immune_quota=5,
                apa_immune_before=CORTE,
            ),
        )
        cls.inicios = sorted(c.start for c in cls.seleccion.selection.chosen)

    def test_salen_diez(self):
        self.assertEqual(len(self.inicios), 10)

    def test_con_el_criterio_ESTRICTO_solo_caben_CUATRO_inmunes(self):
        # HALLAZGO geometrico, no una limitacion del codigo: los sitios elegibles por
        # delante de 3utr:303 son 20, pero con 50 nt de espaciado el maximo es 4 —
        # 3utr:10, 60, 143 y 221 o 200. Pedir cinco no se puede cumplir sin bajar el
        # espaciado o sin aceptar una ventana de la banda de corte.
        sitios = sorted(
            s.best.start for s in self.seleccion.selection.sites
            if s.best.start <= CORTE_ESTRICTO
        )
        maximo, ultimo = 0, None
        for p in sitios:            # voraz por posicion: optimo para maximo con hueco fijo
            if ultimo is None or p - ultimo >= 50:
                maximo += 1
                ultimo = p
        self.assertEqual(maximo, 4)
        inmunes = [p for p in self.inicios if p <= CORTE_ESTRICTO]
        self.assertEqual(len(inmunes), 4)

    def test_y_la_quinta_plaza_se_DECLARA_sin_llenar(self):
        # No se rellena con un candidato de mas abajo: seria otro riesgo, no el que la
        # cuota compra. Y se dice.
        avisos = " ".join(self.seleccion.selection.quota_unfilled)
        self.assertIn("inmunes al corte", avisos)
        self.assertIn("5", avisos)
        self.assertIn("4", avisos)

    def test_con_el_criterio_LAXO_si_salen_cinco_pero_una_es_de_la_BANDA(self):
        laxa = select_from_report(
            self.tiling,
            SelectionConfig(
                n_candidates=10, min_per_tercio=2,
                apa_immune_quota=5, apa_immune_before=CORTE_LAXO,
            ),
        )
        inicios = sorted(c.start for c in laxa.selection.chosen)
        self.assertEqual(len([p for p in inicios if p <= CORTE_LAXO]), 5)
        # La quinta cae DENTRO de la banda de corte: no es inmune, es incierta.
        quinta = [p for p in inicios if CORTE_ESTRICTO < p <= CORTE_LAXO]
        self.assertEqual(quinta, [309])

    def test_los_tres_inmunes_conocidos_siguen_dentro(self):
        for posicion in (60, 143, 221):
            with self.subTest(posicion):
                self.assertIn(posicion, self.inicios)

    def test_cada_tercio_tiene_al_menos_dos(self):
        from collections import Counter

        cuenta = Counter(
            self.seleccion.window_of(c).tercio
            for c in self.seleccion.selection.chosen
        )
        for tercio in (Tercio.PROXIMAL, Tercio.MEDIO, Tercio.DISTAL):
            with self.subTest(tercio):
                self.assertGreaterEqual(cuenta[tercio], 2)

    def test_se_respeta_el_espaciado(self):
        # El espaciado es el minimo EXIGIDO: exactamente 50 lo cumple.
        for a, b in zip(self.inicios, self.inicios[1:]):
            with self.subTest((a, b)):
                self.assertGreaterEqual(b - a, 50)

    def test_sin_la_cuota_no_saldrian_cinco_inmunes(self):
        # Si la cuota no cambiara nada seria decoracion. Esta es la prueba de que hace
        # algo: por asimetria sola, el panel de 10 no llega a cinco inmunes.
        sin_cuota = select_from_report(
            self.tiling, SelectionConfig(n_candidates=10)
        )
        inmunes = [c.start for c in sin_cuota.selection.chosen if c.start <= CORTE]
        self.assertLess(len(inmunes), 5)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLoQueDiceElInforme(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD

        tiling = _tiling()
        seleccion = select_from_report(
            tiling,
            SelectionConfig(
                n_candidates=10,
                min_per_tercio=2,
                apa_immune_quota=5,
                apa_immune_before=CORTE,
            ),
        )
        cls.texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )

    def test_declara_las_dos_cuotas_con_sus_cifras(self):
        self.assertIn("2 por tercio", self.texto)
        self.assertIn("5 inmune", self.texto)

    def test_escribe_la_justificacion(self):
        bajo = self.texto.lower()
        self.assertIn("regionales, no puntuales", bajo)
        self.assertIn("independencia entre apuestas", bajo)
        self.assertIn("saturad", bajo)

    def test_dice_de_donde_salen_esas_plazas(self):
        bajo = self.texto.lower()
        self.assertIn("solo de fuente externa", bajo)
        self.assertIn("vacio", bajo)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaQuintaPlazaVaAlTercioMEDIO(unittest.TestCase):
    """La plaza que la cuota de inmunes no puede llenar se reasigna al tercio medio.

    Razon, que va escrita en el informe: si el APA resulta funcional se pierde un
    candidato; si no, se gana cobertura donde el panel queda mas flojo.

    El espaciado NO se baja para meter un quinto inmune: el espaciado compra
    INDEPENDENCIA entre apuestas, no numero de apuestas. Dos candidatos a 30 nt fallan
    juntos, asi que un quinto inmune pegado a otro no compra nada.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.polya import Tercio

        cls.tiling = _tiling()
        cls.seleccion = select_from_report(
            cls.tiling,
            SelectionConfig(
                n_candidates=10,
                apa_immune_quota=4,
                apa_immune_before=CORTE_ESTRICTO,
                tercio_quota=((Tercio.PROXIMAL, 4), (Tercio.MEDIO, 3), (Tercio.DISTAL, 2)),
            ),
        )
        cls.tercios = [
            cls.seleccion.window_of(c).tercio for c in cls.seleccion.selection.chosen
        ]

    def test_el_espaciado_sigue_intacto(self):
        inicios = sorted(c.start for c in self.seleccion.selection.chosen)
        for a, b in zip(inicios, inicios[1:]):
            with self.subTest((a, b)):
                self.assertGreaterEqual(b - a, 50)

    def test_cuatro_inmunes_ni_uno_mas(self):
        inicios = [c.start for c in self.seleccion.selection.chosen]
        self.assertEqual(
            sorted(p for p in inicios if p <= CORTE_ESTRICTO), [10, 60, 143, 221]
        )

    def test_el_medio_se_lleva_tres(self):
        from shmir_design.polya import Tercio

        self.assertGreaterEqual(self.tercios.count(Tercio.MEDIO), 3)

    def test_una_cuota_por_tercio_que_no_suma_no_se_acepta_a_ciegas(self):
        from shmir_design.polya import Tercio

        with self.assertRaises(ValueError):
            SelectionConfig(
                n_candidates=10,
                tercio_quota=((Tercio.MEDIO, 8), (Tercio.DISTAL, 8)),
            )

    def test_una_cuota_que_repite_tercio_aborta(self):
        from shmir_design.polya import Tercio

        with self.assertRaises(ValueError):
            SelectionConfig(
                n_candidates=10,
                tercio_quota=((Tercio.MEDIO, 2), (Tercio.MEDIO, 3)),
            )

    def test_el_informe_escribe_la_razon_de_la_reasignacion(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD

        texto = text_report(
            species="raton", tiling=self.tiling, selection=self.seleccion,
            scaffold=SGEP_SCAFFOLD,
        ).lower()
        self.assertIn("tercio medio", texto)
        self.assertIn("si el apa resulta funcional se pierde un candidato", texto)
        self.assertIn("se gana cobertura", texto)
