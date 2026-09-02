"""La RT-PCR de empalme NO distingue fallo de empalme de transcritos NACIENTES.

**Corrección aportada por el responsable del proyecto (2026-09-02)**, y es una corrección
de fondo sobre un ensayo que ya estaba especificado y escrito:

> El pre-mRNA sin empalmar existe SIEMPRE —el splicing es cotranscripcional pero no
> instantáneo— así que la banda larga aparece aunque el empalme sea perfecto. **Presencia
> de banda larga no es evidencia de retención.**

Y lo que estaba escrito era exactamente eso: «Banda CORTA = empalmado, banda LARGA =
retenido». Falso, y sobre el ÚNICO frente binario del proyecto — el que decide si hay
proteína o no la hay.

Cuatro cosas entran en la ficha, y ninguna es opcional:

  1. **RNA citoplásmico**, no total. El pre-mRNA sin empalmar es NUCLEAR; lo que sí es
     fallo es encontrarlo retenido en el citoplasma.
  2. **Selección por polyA**, que excluye la mayor parte del naciente.
  3. **DNasa y control sin retrotranscriptasa.** El genoma del AAV LLEVA el intrón, así
     que una traza de ADN da una banda larga indistinguible de la retención.
  4. **La lectura es la PROPORCIÓN corta/larga, no la presencia**, y necesita DOS
     referencias en la misma tanda: el control sin intrón (100 % corta) y el terapéutico.

Regla 5: escrito antes.
"""

import unittest

from shmir_design import splicing


def _rtpcr():
    lecturas = splicing.splicing_readouts(None)
    return next(l for l in lecturas if l.name == "rtpcr_empalme")


class TestLaFRASEfalsaYANOsEAFIRMA(unittest.TestCase):
    """Principio nº 11: la prosa que se quedó atrás es la que alguien va a leer."""

    FICHA = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "data" / "obtencion" / "empalme_intron.toml"
    ).read_text(encoding="utf-8")

    def test_el_requisito_NO_dice_que_banda_larga_sea_retencion(self):
        texto = _rtpcr().requirement
        self.assertNotIn("LARGA = retenido", texto)
        self.assertNotIn("larga = retenido", texto)

    def test_la_ficha_tampoco_lo_AFIRMA(self):
        # Puede CITARSE como lo que fue —el registro no se borra— pero no afirmarse.
        for linea in self.FICHA.splitlines():
            if "= retenido" in linea and "«" not in linea:
                self.fail(f"la ficha sigue afirmándolo: {linea.strip()[:90]}")

    def test_y_se_dice_POR_QUE_es_falso_con_esas_palabras(self):
        texto = _rtpcr().requirement.lower()
        self.assertIn("naciente", texto)
        self.assertIn("cotranscripcional", texto)
        self.assertIn("no es evidencia", texto)


class TestLasCUATROcondicionesEstanEnLosDOSsitios(unittest.TestCase):
    """El requisito que emite el código y la ficha que lee el usuario dicen lo mismo."""

    FICHA = TestLaFRASEfalsaYANOsEAFIRMA.FICHA

    CLAVES = {
        "citoplasmico": ("citoplásmic", "citoplasmic"),
        "polya": ("polyA", "poli-A", "poliA"),
        "dnasa": ("DNasa", "DNAsa"),
        "sin_rt": ("sin retrotranscriptasa", "sin RT", "−RT", "-RT"),
        "proporcion": ("proporción", "proporcion"),
    }

    def _tiene(self, texto, alternativas):
        # Sin distinguir mayusculas: la ficha grita las condiciones —«RNA CITOPLÁSMICO»—
        # y el requisito del codigo las escribe en prosa. Lo que se comprueba es que la
        # condicion ESTE en los dos sitios, no como se escribe.
        bajo = texto.lower()
        return any(a.lower() in bajo for a in alternativas)

    def test_el_requisito_del_codigo_las_lleva_las_cuatro(self):
        texto = _rtpcr().requirement
        for nombre, alternativas in self.CLAVES.items():
            with self.subTest(nombre):
                self.assertTrue(self._tiene(texto, alternativas))

    def test_la_ficha_las_lleva_las_cuatro(self):
        for nombre, alternativas in self.CLAVES.items():
            with self.subTest(nombre):
                self.assertTrue(self._tiene(self.FICHA, alternativas))

    def test_la_ficha_dice_por_que_el_ADN_del_AAV_es_el_problema(self):
        self.assertIn("genoma del AAV", self.FICHA)


class TestLasDOSreferenciasDeLaMismaTanda(unittest.TestCase):
    """La proporción no se lee sola: hace falta contra qué compararla."""

    def test_el_requisito_NOMBRA_las_dos(self):
        texto = _rtpcr().requirement
        self.assertIn("sin intrón", texto)
        self.assertIn("misma tanda", texto.lower())

    def test_el_control_sin_intron_es_el_100_por_cien_corta(self):
        self.assertIn("100 %", _rtpcr().requirement)

    def test_siguen_siendo_CUATRO_lecturas_y_ninguna_se_ha_perdido(self):
        nombres = {l.name for l in splicing.splicing_readouts(None)}
        self.assertEqual(
            nombres,
            {
                "rtpcr_empalme", "western_L42_por_vg",
                "secuencia_union_exon_exon", "parental_sin_intron",
            },
        )

    def test_todas_siguen_en_NOT_RUN(self):
        from shmir_design.filters import FilterState

        for lectura in splicing.splicing_readouts(None):
            with self.subTest(lectura.name):
                self.assertIs(lectura.state, FilterState.NOT_RUN)


if __name__ == "__main__":
    unittest.main()
