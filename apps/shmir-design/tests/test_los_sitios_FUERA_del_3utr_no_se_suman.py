"""Un 6mer en el CDS y uno en el 3'UTR no son comparables, y el conteo los suma.

Del responsable del proyecto (2026-09-06), cerrando la errata nº 122:

    «Los sitios en CDS y 5'UTR son reales pero de otra naturaleza — la represión por seed
     opera sobre todo en 3'UTR, así que un 6mer en el CDS no es comparable con uno en el
     3'UTR aunque el conteo los sume. Que la ficha lo diga, o alguien comparará dos
     números que no miden lo mismo.»

Es `WHY_NOT_SUMMED` por un eje nuevo: allí no se suman las CLASES porque la represión
esperada de un 8mer y la de un 6mer no se parecen; aquí no se pueden mezclar las REGIONES
por la misma razón. Y aquí es peor de leer, porque la region no sale en el numero: dos
fichas con «2 sitios» pueden ser 2 en el 3'UTR o 1 y 1, y solo una de las dos lecturas
dice algo del knockdown.
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.dossier import build_dossier
from shmir_design.reference import REFERENCES, load_3utr, load_reference
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr


def _ficha_del_transcrito(utr3_start: int):
    ref = REFERENCES["NM_011170.3"]
    secuencia = load_reference(ref)
    anatomia = Anatomy.from_cds(
        cds=ref.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )
    informe = tile_utr(secuencia, anatomy=anatomia)
    seleccion = select_from_report(informe, default_config())
    return build_dossier(
        species="raton", tiling=informe, selection=seleccion,
        start=anatomia.transcript_position(utr3_start), target=secuencia,
    )


def _ficha_del_3utr(utr3_start: int):
    ref = REFERENCES["NM_011170.3"]
    utr3 = load_3utr(ref)
    informe = tile_utr(utr3)
    seleccion = select_from_report(informe, default_config())
    return build_dossier(
        species="raton", tiling=informe, selection=seleccion,
        start=utr3_start, target=utr3,
    )


class TestLaRegionDeCadaSitio(unittest.TestCase):
    """`3utr:143` es el caso medido: sobre el transcrito gana un 6mer FUERA del 3'UTR
    que en la lectura del 3'UTR no existe."""

    def test_el_caso_existe_y_es_el_medido(self):
        """Control adversario del dato: sin un sitio fuera del 3'UTR, este test no
        probaria nada — «ninguno se mezcla» y «no hay ninguno» darian el mismo verde."""
        del_tx = _ficha_del_transcrito(143)
        del_utr = _ficha_del_3utr(143)
        self.assertGreater(len(del_tx.self_sites), len(del_utr.self_sites))

    def test_cada_sitio_DICE_su_region(self):
        for sitio in _ficha_del_transcrito(143).self_sites:
            self.assertTrue(sitio.region, sitio)

    def test_y_los_de_fuera_del_3utr_salen_marcados(self):
        regiones = {s.region for s in _ficha_del_transcrito(143).self_sites}
        self.assertIn("3'UTR", regiones)
        self.assertTrue(regiones - {"3'UTR"}, "ninguno sale fuera del 3'UTR")

    def test_la_ficha_AVISA_de_que_no_son_comparables(self):
        from shmir_design.offtarget import SITES_OUTSIDE_UTR3

        texto = _ficha_del_transcrito(143).render()
        self.assertIn(" ".join(SITES_OUTSIDE_UTR3.split())[:60], " ".join(texto.split()))

    def test_y_NO_avisa_cuando_todos_estan_en_el_3utr(self):
        """Un aviso que sale siempre deja de leerse. Sobre el 3'UTR pelado no hay nada
        que distinguir, asi que no se dice nada."""
        from shmir_design.offtarget import SITES_OUTSIDE_UTR3

        texto = _ficha_del_3utr(143).render()
        self.assertNotIn(" ".join(SITES_OUTSIDE_UTR3.split())[:60], " ".join(texto.split()))


if __name__ == "__main__":
    unittest.main()
