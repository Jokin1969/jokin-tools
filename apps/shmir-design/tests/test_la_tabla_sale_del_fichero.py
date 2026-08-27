"""La promoción sale del FICHERO, no de una constante. Sin fichero, NOT_RUN.

Regla 5: escrito antes.

Es la mitad que cierra el objetivo del responsable, dicho por él en una frase:

> Subo los ficheros, le doy a diseñar, y la app hace todo el análisis y muestra
> resultados. Sin banderas, sin recordar nada, sin tocar el código.

La regla —promover un hexámero con uso medido— ya entraba sola desde la tanda anterior.
Lo que faltaba es que los VALORES salieran del gestor: hasta hoy `tile_utr` leía
`apa.TABLA`, una constante, así que en otra especie no había forma de meterlos.

Los tres estados, y ninguno sobra:

  · **hay fichero y habla de esta secuencia** → la promoción se aplica sola;
  · **hay fichero y NO habla de esta secuencia** (otro md5 de 3'UTR) → no se promueve
    nada, y eso NO es un fallo: es la tabla diciendo que no es suya;
  · **no hay fichero** → el frente queda NOT_RUN. No es lo mismo que lo anterior, y el
    informe no puede decir lo mismo de los dos.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.polya import SignalClass
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(RATON)
DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestConElFicheroLaPromocionSeAplicaSOLA(unittest.TestCase):

    def test_el_AATATA_de_236_sube_a_APA_POSIBLE(self):
        informe = tile_utr(load_3utr(RATON))
        señal = next(s for s in informe.signals if s.position == 236)
        self.assertIs(señal.classification, SignalClass.APA_POSSIBLE)
        self.assertEqual(señal.evidence, "medida")

    def test_y_la_procedencia_dice_de_QUE_FICHERO_sale(self):
        informe = tile_utr(load_3utr(RATON))
        self.assertIsNotNone(informe.measured_apa)
        self.assertIn("PolyA_DB", informe.measured_apa.source)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestSinFicheroElFrenteQuedaNOT_RUN(unittest.TestCase):
    """Y NO es lo mismo que «la tabla no habla de esta secuencia»."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_sin_fichero_no_hay_medida(self):
        informe = tile_utr(load_3utr(RATON), reference_dir=self.tmp.name)
        self.assertIsNone(informe.measured_apa)

    def test_y_el_AATATA_vuelve_a_ser_OTRA(self):
        informe = tile_utr(load_3utr(RATON), reference_dir=self.tmp.name)
        señal = next(s for s in informe.signals if s.position == 236)
        self.assertIsNot(señal.classification, SignalClass.APA_POSSIBLE)

    def test_el_motivo_dice_que_FALTA_EL_FICHERO(self):
        informe = tile_utr(load_3utr(RATON), reference_dir=self.tmp.name)
        self.assertIn("polya_db", informe.apa_missing_reason)

    def test_y_NO_dice_que_la_tabla_no_hable_de_esta_secuencia(self):
        # Los dos estados dan `measured_apa=None` y NO son lo mismo. Si el informe
        # dijera lo mismo de los dos, nadie sabria si hay que subir un fichero o si el
        # que hay es de otro gen.
        informe = tile_utr(load_3utr(RATON), reference_dir=self.tmp.name)
        self.assertNotIn("md5", informe.apa_missing_reason.lower())


@unittest.skipUnless(
    HAY and fixture_available(HUMANO), "NOT_RUN: faltan los dos fixtures"
)
class TestConFicheroQueNOHablaDeEstaSecuencia(unittest.TestCase):

    def test_el_humano_no_promueve_nada(self):
        informe = tile_utr(load_3utr(HUMANO))
        self.assertIsNone(informe.measured_apa)

    def test_pero_el_motivo_es_OTRO(self):
        informe = tile_utr(load_3utr(HUMANO))
        self.assertIn("md5", informe.apa_missing_reason.lower())

    def test_y_los_dos_motivos_NO_son_el_mismo_texto(self):
        with TemporaryDirectory() as tmp:
            sin = tile_utr(load_3utr(RATON), reference_dir=tmp).apa_missing_reason
        otra = tile_utr(load_3utr(HUMANO)).apa_missing_reason
        self.assertNotEqual(sin, otra)


class TestLaConstanteYaNoDECIDE(unittest.TestCase):
    """El dato sale del fichero; la constante se queda sólo como referencia histórica."""

    def test_tile_utr_no_USA_la_constante(self):
        # Sobre codigo, no sobre comentarios: el comentario que dice «hasta 2026-08-27
        # esto leia la constante» tiene que poder nombrarla.
        ruta = Path(__file__).resolve().parents[1] / "shmir_design" / "tiling.py"
        culpables = [
            f"tiling.py:{n}  {l.strip()}"
            for n, l in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
            if "TABLA" in l and not l.lstrip().startswith("#")
        ]
        self.assertEqual(culpables, [], "\n".join(culpables))


if __name__ == "__main__":
    unittest.main()
