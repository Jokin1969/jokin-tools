"""Cuánto quita la máscara de repetitivos, y que ESO salga en el informe.

Regla 5: escritos antes.

**Por qué es información y no un detalle de test.** Al medir qué cambia cada fichero de
referencia salió que la máscara del ratón quita **0** ventanas elegibles y la del humano
**5**. Eso no es una propiedad del pipeline: es una propiedad de los TRANSCRITOS. El
3'UTR murino de Prnp no tiene ni un elemento repetitivo —su único hallazgo, el `(CTC)n`
de `tx:892-936`, está entero dentro del CDS— y el humano sí, un `(TA)n` en
`3utr:1268-1301`.

Un filtro que corre y no quita nada, y otro que corre y quita cinco, tienen que
distinguirse en la salida. Si no se dice, un `0` se lee como «el filtro no hizo nada» o,
peor, como que no llegó a correr — y no haber quitado nada NO es lo mismo que no haber
mirado. Es la misma familia que el «Alu 0 %» obtenido sin buscar Alu.

**Y los dos números se DERIVAN aquí**, de los ficheros de verdad, en vez de estar
escritos: la frase del informe cita las dos cifras y este test las recalcula. Principio
nº 13 aplicado a una prosa que compara dos especies.
"""

import unittest

from shmir_design import masking
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(RATON) and fixture_available(HUMANO)


def _mordida(referencia, rmsk: str, tbl: str):
    """Las ventanas elegibles que la máscara se lleva por delante en ese transcrito.

    Se tila SIN máscara a propósito: con ella puesta el paso 15 retila y esas ventanas
    ya no están en la piscina, así que la cuenta saldría VACÍA — que no es lo mismo que
    limpia. Misma condición que `triple_motive_rows`.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "data" / "reference"
    secuencia = load_reference(referencia)
    anatomia = Anatomy.from_cds(
        cds=referencia.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    mascara = masking.load_rmsk(
        raiz / rmsk,
        version="test",
        expected_species=referencia.organism,
        summary_path=raiz / tbl,
    )
    sin_mascara = tile_utr(secuencia, anatomy=anatomia)
    return masking.mask_bite(
        sin_mascara, mascara, mask_offset=0, label_offset=anatomia.utr3[0] - 1
    )


@unittest.skipUnless(HAY, "faltan los fixtures de las dos especies")
class TestLaMordidaSeMide(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raton = _mordida(RATON, "rmsk_mouse.out", "rmsk_mouse.tbl")
        cls.humano = _mordida(HUMANO, "rmsk_human.out", "rmsk_human.tbl")

    def test_en_el_RATON_la_mascara_no_se_lleva_NINGUNA(self):
        self.assertEqual(self.raton.windows, 0)

    def test_y_el_motivo_es_que_su_unico_repetitivo_esta_en_el_CDS(self):
        """Cero elementos DENTRO del 3'UTR, no cero elementos: la máscara sí encontró
        algo, y está en el CDS. Las dos cifras dicen cosas distintas."""
        self.assertEqual(self.raton.in_utr3, 0)
        self.assertGreater(self.raton.elements, 0)

    def test_en_el_HUMANO_la_MISMA_maquinaria_se_lleva_CINCO(self):
        self.assertEqual(self.humano.windows, 5)
        self.assertEqual(self.humano.in_utr3, 1)

    def test_las_ventanas_del_humano_salen_ETIQUETADAS_en_3utr(self):
        for etiqueta in self.humano.labels:
            self.assertTrue(str(etiqueta).startswith("3utr:"), etiqueta)

    def test_un_cero_NO_puede_ser_indistinguible_de_no_haber_corrido(self):
        """Las dos mitades de la lectura, y hacen falta las dos."""
        texto = self.raton.describe()
        self.assertIn("corrió", texto)
        self.assertIn("resultado medido", texto)
        self.assertIn("no un filtro que no corrió", texto)


@unittest.skipUnless(HAY, "faltan los fixtures de las dos especies")
class TestLaFraseDelInformeCITAlasDosCifras(unittest.TestCase):
    """La comparación entre especies va escrita, y este test la RECALCULA.

    Una frase que dice «0 en el ratón y 5 en el humano» es un dato transcrito: envejece
    sola y en silencio. Aquí se deriva de los ficheros y se exige que la prosa cuadre.
    """

    def test_la_frase_nombra_los_dos_numeros_que_salen_de_los_ficheros(self):
        raton = _mordida(RATON, "rmsk_mouse.out", "rmsk_mouse.tbl")
        humano = _mordida(HUMANO, "rmsk_human.out", "rmsk_human.tbl")
        texto = masking.WHY_THE_BITE_IS_A_PROPERTY
        self.assertIn(f"{raton.windows}", texto)
        self.assertIn(f"{humano.windows}", texto)
        self.assertIn("Mus musculus", texto)
        self.assertIn("Homo sapiens", texto)

    def test_y_dice_que_es_propiedad_del_TRANSCRITO_no_del_pipeline(self):
        texto = masking.WHY_THE_BITE_IS_A_PROPERTY.lower()
        self.assertIn("transcrito", texto)
        self.assertIn("pipeline", texto)


@unittest.skipUnless(HAY, "faltan los fixtures de las dos especies")
class TestSaleEnElInformeDEVERDAD(unittest.TestCase):
    """Calculado y no emitido es el patrón de siempre, y aquí NO vale mirar el fuente.

    El golden del informe se genera SIN máscara, así que este bloque no entra en él: si
    la comprobación fuera un `grep` sobre `outputs.py`, pasaría igual con la línea nunca
    llegando a ninguna pantalla — que es exactamente el fallo que este proyecto lleva
    cuatro veces cometiendo. Así que se corre el CLI DE VERDAD con la máscara puesta y se
    lee el informe que escribe.
    """

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path

        from tools.design import main

        raiz = Path(__file__).resolve().parent.parent
        datos = raiz / "data" / "reference"
        cls.salida = Path(tempfile.mkdtemp())
        codigo = main([
            "--fasta", str(datos / "NM_011170.3.fa"),
            "--genbank", str(datos / "NM_011170.3.gb"),
            "--name", "raton",
            "--rmsk", str(datos / "rmsk_mouse.out"),
            "--rmsk-especie", "Mus musculus",
            "--rmsk-version", "open-4.0.9",
            "--rmsk-resumen", str(datos / "rmsk_mouse.tbl"),
            "--out", str(cls.salida),
        ])
        cls.codigo = codigo
        informes = sorted(cls.salida.rglob("*informe*.txt"))
        cls.texto = informes[0].read_text(encoding="utf-8") if informes else ""
        # El informe va ENVUELTO a 85 columnas, asi que una frase puede partirse por
        # cualquier espacio. Se compara sobre el texto con los espacios colapsados: lo
        # que se comprueba es que la frase SE EMITE, no donde cae el salto de linea.
        cls.plano = " ".join(cls.texto.split())

    def test_la_corrida_termina_bien(self):
        """REGRESIÓN: el CLI con `--rmsk` abortaba con un `NameError`.

        `tools/design.py` pasaba `thresholds=umbrales` y esa variable NO EXISTE en el
        módulo — se llama `thresholds`. O sea que TODA corrida con máscara moría, y con
        ella el bloque del triple motivo, que se escribió justo porque «existía sólo
        porque alguien lo corría a mano». Ningún test lo veía porque ninguno corría el
        CLI con máscara: los del triple motivo llaman a `triple_motive_rows` ellos
        mismos. Es la ceguera que describe la alcanzabilidad, un piso más arriba.
        """
        self.assertEqual(self.codigo, 0)
        self.assertTrue(self.texto, f"no salió informe en {self.salida}")

    def test_y_el_TRIPLE_MOTIVO_tambien_sale_ahora_que_el_CLI_no_aborta(self):
        """Era el bloque que el `NameError` se llevaba por delante."""
        self.assertIn("Triple motivo", self.plano)

    def test_el_informe_DICE_que_la_mascara_corrio_y_no_se_llevo_ninguna(self):
        self.assertIn("La máscara corrió y NO se lleva ninguna ventana", self.plano)

    def test_y_lleva_la_comparacion_entre_especies_pegada(self):
        """Las dos cifras juntas, que es lo que hace legible el cero."""
        self.assertIn("0 ventanas elegibles en Mus musculus", self.plano)
        self.assertIn("5 en Homo sapiens", self.plano)

    def test_y_dice_que_es_del_TRANSCRITO_y_no_del_pipeline(self):
        self.assertIn("propiedad del TRANSCRITO, no del pipeline", self.plano)

    def test_un_cero_medido_no_se_confunde_con_un_filtro_que_no_corrio(self):
        self.assertIn("resultado medido, no un filtro que no corrió", self.plano)
        # Y la linea del NOT_RUN, que es la otra rama, NO puede salir a la vez.
        self.assertNotIn("no hay máscara de repeticiones cargada", self.plano)


if __name__ == "__main__":
    unittest.main()


# ─────────── la dirección esperada de la discrepancia, escrita y emitida ───────────


class TestLaDireccionEsperadaDeLaDiscrepancia(unittest.TestCase):
    """Si los dos techos discrepan, no es un fallo a reconciliar: es el dato.

    PolyA_DB promedia TODOS los tejidos y las neuronas ALARGAN los 3'UTR, así que lo
    esperable es que el techo de cerebro sea MAYOR que 0,86. Una discrepancia en esa
    dirección CONFIRMA el modelo; en la contraria, hay que PARAR.

    Sin la dirección escrita, alguien tratará la discrepancia como un error y promediará
    los dos números — que es perder la única información que la discrepancia lleva
    dentro.
    """

    def test_la_direccion_va_ESCRITA_y_con_las_dos_ramas(self):
        from shmir_design import apa

        texto = apa.EXPECTED_DIRECTION
        self.assertIn("MAYOR", texto)
        self.assertIn("0,86", texto)
        self.assertIn("CONFIRMA", texto)
        self.assertIn("PARAR", texto)

    def test_dice_POR_QUE_esa_es_la_direccion_esperada(self):
        from shmir_design import apa

        texto = apa.EXPECTED_DIRECTION.lower()
        self.assertIn("todos los tejidos", texto)
        self.assertIn("alargan", texto)

    def test_y_prohibe_expresamente_promediarlos(self):
        from shmir_design import apa

        self.assertIn("No se promedian", apa.EXPECTED_DIRECTION)

    def test_viaja_dentro_de_APA_ARE_TWO_FILES(self):
        from shmir_design import apa

        self.assertIn(apa.EXPECTED_DIRECTION, apa.APA_ARE_TWO_FILES)

    def test_y_LLEGA_A_UNA_PANTALLA_no_se_queda_en_el_codigo(self):
        """Escrito y no emitido es el patrón de siempre. Sale en el informe."""
        from pathlib import Path

        from shmir_design import outputs, presentation

        fuentes = "".join(
            Path(m.__file__).read_text(encoding="utf-8")
            for m in (outputs, presentation)
        )
        self.assertIn("APA_ARE_TWO_FILES", fuentes)
