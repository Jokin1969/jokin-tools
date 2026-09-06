"""El bloque exportable etiquetaba `3utr:` coordenadas del TRANSCRITO, y el propio
fichero se contradecía.

Reportado el 2026-09-06 con la corrida entera pegada. La tabla de hebras decía

    3utr:1398   guia   TTAGTAA  8mer=1800 …

y doce líneas más abajo, el autoconteo de ESA MISMA guía decía que su sitio propio está
en `3utr:464`. Si 1398 fuera una coordenada de 3'UTR, su propio sitio no podría estar en
464: **el fichero se delata solo**. Y no es casual que las dos mitades discrepen — las del
autoconteo salen de `self_sites` con el marco DERIVADO (errata nº 122) y las de la tabla
de un `f"3utr:{start}"` escrito a mano en `LoadResult.describe()`.

Séptima vez de la familia del marco, y en el peor sitio: este bloque es «material para
defender la selección», el que se lee SIN la app delante y se pega en un documento.

Y LA SEGUNDA MITAD, que es un fallo mío de la tanda anterior: el aviso de la pasajera no
graduaba por CLASE. El de la guía sí lo hace —«un 8mer o un 7mer-m8 de más dan
cooperatividad real; un 6mer es marginal»— y el de la pasajera decía «MERECE MIRARSE»
igual para dos 7mer-A1 que para un 6mer suelto. Separé el VALOR ESPERADO por hebra y dejé
el CRITERIO DE LECTURA de la clase sin separar: el corolario del responsable del proyecto
—«separar la medida no basta si el criterio de lectura sigue siendo uno»— aplicándose una
segunda vez, un nivel más abajo.
"""

import unittest

from shmir_design.coords import Frame
from shmir_design.offtarget import (
    Counts,
    LoadResult,
    SelfCount,
    SelfSite,
    SITE_CLASSES,
    site_patterns,
)

GUIA = "TTTAGTAAAGAAAGAATTCCAC"   # la de `3utr:449`, o sea `tx:1398`


def _fila(marco):
    patrones = site_patterns(GUIA)
    return LoadResult(
        # La clave NO se transcribe: `describe()` no la imprime, así que aquí
        # cualquier etiqueta vale — y escribir el formato de `query_name` sería
        # justo lo que el auditor de claves prohíbe (principio nº 25).
        start=1398, strand="guia", query="consulta", sequence=GUIA,
        patterns=patrones,
        counts=Counts(
            sites={c: 0 for c in SITE_CLASSES},
            transcripts={c: 0 for c in SITE_CLASSES},
        ),
        percentiles={c: 0.0 for c in SITE_CLASSES},
        frame=marco,
    )


class TestLaTablaLlevaSuMarco(unittest.TestCase):
    def test_con_marco_de_transcrito_dice_tx(self):
        self.assertIn("tx:1398", _fila(Frame.TX).describe())

    def test_y_NO_dice_3utr(self):
        self.assertNotIn("3utr:1398", _fila(Frame.TX).describe())

    def test_con_marco_de_3utr_dice_3utr(self):
        texto = _fila(Frame.UTR3).describe()
        self.assertIn("3utr:1398", texto)
        self.assertNotIn("tx:", texto)


class TestElAvisoDeLaPasajeraGRADUA(unittest.TestCase):
    """Un 6mer suelto y dos 7mer-A1 no se leen igual, y decían lo mismo."""

    def _conteo(self, clases):
        return SelfCount(
            query="p", target_label="d", occurrences=len(clases), sites={},
            expected=0,
            detail=tuple(
                SelfSite(position=100 + i, site_class=c, own_window=False)
                for i, c in enumerate(clases)
            ),
        )

    def test_solo_6mer_se_dice_MARGINAL(self):
        texto = self._conteo(["6mer"]).describe()
        self.assertIn("es MARGINAL", texto)

    def test_un_7mer_m8_dice_que_NO_lo_es(self):
        # Se comprueba la frase entera, no la palabra: «NO es marginal» la contiene.
        texto = self._conteo(["7mer-m8"]).describe()
        self.assertIn("NO es marginal", texto)
        self.assertNotIn("es MARGINAL", texto)

    def test_y_las_dos_lecturas_son_DISTINTAS(self):
        """Si dijeran lo mismo, graduar no distinguiría nada — que es el estado del que
        se viene."""
        self.assertNotEqual(
            self._conteo(["6mer"]).describe(),
            self._conteo(["7mer-A1", "7mer-A1"]).describe(),
        )

    def test_el_motivo_de_por_que_importa_sigue_estando_en_las_dos(self):
        for clases in (["6mer"], ["7mer-m8"]):
            with self.subTest(clases):
                self.assertIn("SENTIDO", self._conteo(clases).describe())


if __name__ == "__main__":
    unittest.main()
