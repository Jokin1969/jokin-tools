"""Un «SEGUNDO SITIO» no se puede leer sin saber SOBRE QUE se busco.

Sale de la errata nº 122 y de la instruccion del responsable del proyecto (2026-09-06):

    «Un fallo de marco que marca la propia diana como SEGUNDO SITIO no se lee como error
     de formato — se lee como un hallazgo biologico, y en su dia lo interpretamos como
     cooperatividad. Que quede anotado que cualquier SEGUNDO SITIO medido antes de este
     arreglo hay que volver a mirarlo.»

Y al volver a mirarlo aparecio la OTRA mitad, que no es un fallo sino una ambiguedad:
`self_sites` barre lo que se le pase como `target`, asi que sobre el 3'UTR y sobre el
transcrito entero contesta preguntas DISTINTAS. Con el transcrito aparecen sitios en el
CDS y en el 5'UTR — reales, y de otra naturaleza: la represion por seed opera sobre todo
en el 3'UTR. Un recuento sin decir sobre que se hizo no es interpretable.
"""

import unittest
from pathlib import Path

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.coords import Frame
from shmir_design.dossier import build_dossier
from shmir_design.reference import REFERENCES, load_3utr, load_reference
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr

RAIZ = Path(__file__).resolve().parents[1]


def _ficha(sobre_el_transcrito: bool):
    ref = REFERENCES["NM_011170.3"]
    if sobre_el_transcrito:
        secuencia = load_reference(ref)
        anatomia = Anatomy.from_cds(
            cds=ref.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        informe = tile_utr(secuencia, anatomy=anatomia)
        inicio = anatomia.transcript_position(449)
    else:
        secuencia = load_3utr(ref)
        informe = tile_utr(secuencia)
        inicio = 449
    seleccion = select_from_report(informe, default_config())
    return build_dossier(
        species="raton", tiling=informe, selection=seleccion,
        start=inicio, target=secuencia,
    )


class TestElRecuentoDiceSuAlcance(unittest.TestCase):
    def test_la_ficha_del_3utr_dice_que_se_busco_en_el_3utr(self):
        ficha = _ficha(sobre_el_transcrito=False)
        self.assertIn("3utr:1-", ficha.self_sites_span)
        self.assertIn(ficha.self_sites_span, ficha.render())

    def test_la_del_transcrito_dice_que_se_busco_en_el_transcrito(self):
        ficha = _ficha(sobre_el_transcrito=True)
        self.assertIn("tx:1-", ficha.self_sites_span)
        self.assertIn(ficha.self_sites_span, ficha.render())

    def test_y_los_dos_alcances_NO_son_el_mismo_texto(self):
        """Si dijeran lo mismo, el campo no distinguiria nada — que es exactamente el
        estado del que se viene."""
        self.assertNotEqual(
            _ficha(sobre_el_transcrito=False).self_sites_span,
            _ficha(sobre_el_transcrito=True).self_sites_span,
        )


class TestElHallazgoDE_LOS_CUATRO_SIGUE_EN_PIE(unittest.TestCase):
    """LA RE-MEDIDA que pidio el responsable, con el resultado fijado.

    El hallazgo registrado —4 de los del panel con un segundo sitio en el 3'UTR de Prnp—
    se midio sobre el 3'UTR PELADO, donde el desfase es 0 y el fallo de marco es INERTE.
    Por eso NO estaba contaminado, y eso se comprueba en vez de afirmarse.
    """

    ESPERADO = {
        449: [(464, "7mer-m8", True), (1033, "7mer-A1", False)],
        553: [(460, "6mer", False), (568, "7mer-m8", True)],
        819: [(148, "7mer-m8", False), (834, "7mer-m8", True)],
        1018: [(464, "6mer", False), (1033, "8mer", True)],
    }

    def test_los_cuatro_dan_LO_MISMO_que_lo_registrado(self):
        from shmir_design.offtarget import self_sites

        ref = REFERENCES["NM_011170.3"]
        utr3 = load_3utr(ref)
        informe = tile_utr(utr3)
        seleccion = select_from_report(informe, default_config())
        for inicio, esperado in self.ESPERADO.items():
            eleccion = next(
                c for c in seleccion.selection.chosen if c.start == inicio
            )
            ventana = seleccion.window_of(eleccion)
            sitios = self_sites(
                ventana.evaluation.guide, target=utr3,
                window=(ventana.window.start, ventana.window.end),
                frame=Frame.UTR3,
            )
            with self.subTest(inicio):
                self.assertEqual(
                    [(s.position, s.site_class, s.own_window) for s in sitios],
                    esperado,
                )

    def test_y_ninguno_de_los_cuatro_marca_su_PROPIA_ventana_como_segundo(self):
        """El sintoma del fallo de marco era justo ese. Control adversario del arreglo."""
        for esperado in self.ESPERADO.values():
            propios = [s for s in esperado if s[2]]
            self.assertEqual(len(propios), 1, esperado)


if __name__ == "__main__":
    unittest.main()
