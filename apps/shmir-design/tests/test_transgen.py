"""Tests del filtro contra el transgen terapeutico (bloque 10).

Regla 5: escritos antes que el filtro.

El problema que resuelve, con el dato medido sobre el vector real: de las 744 ventanas
del CDS nativo murino, 29 quedan a 1 desapareamiento del ORF del transgen y 105 a 2. Una
guia con un solo desapareamiento silencia el transgen casi igual que la diana perfecta,
asi que un candidato del ORF puede parecer perfecto y estar apagando la propia PrP-DN
que se quiere expresar. Seria un fallo silencioso: knockdown global bonito y ningun
beneficio en el ratio.

Para los candidatos del 3'UTR pasara siempre —el casete lleva polyA heterologo y ni una
base del 3'UTR nativo— pero merece correrlo igual: tambien coge coincidencias con WPRE,
hSyn, las ITR o el array de miR-183T, que nadie ha mirado nunca.

Las secuencias de casete de este fichero son SONDAS de mecanismo. La comprobacion contra
el vector real es `test_la_guia_1018_no_toca_el_casete`, que corre solo si esta el FASTA.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.specificity import (
    SpecificityDatabase,
    Strand,
    filter_transgene,
    reverse_complement,
)

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"
RELLENO = "GGCCATACTAGCATCGGATCAG"


def _casete(*insertos: str, nombre: str = "casete_AAV") -> SpecificityDatabase:
    secuencia = RELLENO * 3 + "".join(i + RELLENO * 2 for i in insertos)
    return SpecificityDatabase(
        name="sonda de casete AAV",
        version="sonda",
        checksum="0" * 32,
        records={nombre: secuencia},
    )


def _con_desapareamientos(sequence: str, cuantos: int) -> str:
    """Cambia `cuantos` bases repartidas. No genera secuencia: permuta la que hay."""
    cambio = {"A": "C", "C": "A", "G": "T", "T": "G"}
    bases = list(sequence)
    for i in range(cuantos):
        posicion = 3 + i * 5
        bases[posicion] = cambio[bases[posicion]]
    return "".join(bases)


class TestSinBase(unittest.TestCase):

    def test_sin_casete_el_filtro_es_NOT_RUN(self):
        r = filter_transgene(GUIA_1018, None, None)
        self.assertIs(r.state, FilterState.NOT_RUN)

    def test_NOT_RUN_no_es_PASS_y_el_motivo_lo_dice(self):
        r = filter_transgene(GUIA_1018, None, None)
        self.assertIn("NOT_RUN no es PASS", r.reason)

    def test_el_motivo_dice_que_queda_sin_ejecutar(self):
        r = filter_transgene(GUIA_1018, None, None)
        self.assertIn("transgén", r.reason.lower())


class TestVeredicto(unittest.TestCase):

    def test_un_sitio_perfecto_es_FAIL(self):
        base = _casete(reverse_complement(GUIA_1018))
        self.assertIs(filter_transgene(GUIA_1018, None, base).state, FilterState.FAIL)

    def test_un_sitio_a_1_desapareamiento_es_FAIL(self):
        """Una guia con un solo desapareamiento silencia el transgen casi igual."""
        base = _casete(_con_desapareamientos(reverse_complement(GUIA_1018), 1))
        self.assertIs(filter_transgene(GUIA_1018, None, base).state, FilterState.FAIL)

    def test_un_sitio_a_2_desapareamientos_no_es_FAIL(self):
        base = _casete(_con_desapareamientos(reverse_complement(GUIA_1018), 2))
        r = filter_transgene(GUIA_1018, None, base)
        self.assertIs(r.state, FilterState.PASS)

    def test_un_sitio_a_2_desapareamientos_sale_en_la_lista_de_avisos(self):
        base = _casete(_con_desapareamientos(reverse_complement(GUIA_1018), 2))
        r = filter_transgene(GUIA_1018, None, base)
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("2 desapareamiento", r.warnings[0])

    def test_sin_ningun_sitio_es_PASS(self):
        r = filter_transgene(GUIA_1018, None, _casete())
        self.assertIs(r.state, FilterState.PASS)
        self.assertEqual(r.warnings, ())

    def test_el_motivo_del_PASS_tambien_esta_escrito(self):
        self.assertTrue(filter_transgene(GUIA_1018, None, _casete()).reason)


class TestOrientacion(unittest.TestCase):

    def test_el_sitio_que_cuenta_es_el_antisentido(self):
        base = _casete(reverse_complement(GUIA_1018))
        r = filter_transgene(GUIA_1018, None, base)
        self.assertTrue(all(h.strand is Strand.ANTISENSE for h in r.hits))

    def test_la_propia_secuencia_en_el_casete_no_es_un_off_target(self):
        """Encontrar la guia tal cual significa misma hebra: no silencia."""
        base = _casete(GUIA_1018)
        r = filter_transgene(GUIA_1018, None, base)
        self.assertIs(r.state, FilterState.PASS)
        self.assertEqual(len(r.sense_hits), 1)

    def test_los_hits_de_sentido_se_cuentan_pero_no_condenan(self):
        base = _casete(GUIA_1018)
        self.assertTrue(filter_transgene(GUIA_1018, None, base).sense_hits)


class TestGuiaYPasajeraPorSeparado(unittest.TestCase):

    PASAJERA = "GGCCGTTCCATCCAGTACTAAA"

    def test_un_sitio_de_la_pasajera_tambien_condena(self):
        base = _casete(reverse_complement(self.PASAJERA))
        r = filter_transgene(GUIA_1018, self.PASAJERA, base)
        self.assertIs(r.state, FilterState.FAIL)

    def test_el_origen_del_sitio_queda_marcado(self):
        base = _casete(reverse_complement(self.PASAJERA))
        r = filter_transgene(GUIA_1018, self.PASAJERA, base)
        self.assertEqual(r.hits[0].queries, ("pasajera",))

    def test_un_sitio_que_comparten_las_dos_se_marca_una_sola_vez(self):
        base = _casete(reverse_complement(GUIA_1018))
        r = filter_transgene(GUIA_1018, GUIA_1018, base)
        self.assertEqual(len(r.hits), 1)
        self.assertEqual(set(r.hits[0].queries), {"guia", "pasajera"})


class TestSalidaYProcedencia(unittest.TestCase):

    def test_el_filtro_se_llama_transgen(self):
        r = filter_transgene(GUIA_1018, None, _casete())
        self.assertEqual(r.as_filter().name, "transgen")

    def test_el_texto_lleva_la_procedencia_del_casete(self):
        texto = filter_transgene(GUIA_1018, None, _casete()).format_text()
        self.assertIn("sonda de casete AAV", texto)

    def test_el_texto_dice_que_el_casete_no_tiene_gen_diana_que_excluir(self):
        texto = filter_transgene(GUIA_1018, None, _casete()).format_text()
        self.assertIn("no hay gen diana", texto.lower())

    def test_los_sitios_salen_listados(self):
        base = _casete(reverse_complement(GUIA_1018))
        texto = filter_transgene(GUIA_1018, None, base).format_text()
        self.assertIn("casete_AAV", texto)


class TestLoQueAborta(unittest.TestCase):

    def test_una_guia_vacia_aborta(self):
        with self.assertRaises((ValueError, ShmirDesignError)):
            filter_transgene("", None, _casete())

    def test_una_guia_con_letras_raras_aborta(self):
        with self.assertRaises((ValueError, ShmirDesignError)):
            filter_transgene("XXXXXXXXXXXXXXXXXXXXXX", None, _casete())


class TestContraElVectorReal(unittest.TestCase):

    CASETE = Path(__file__).resolve().parent.parent / "data" / "reference" / "aav_casete.fa"

    @unittest.skipUnless(
        CASETE.is_file(),
        "falta data/reference/aav_casete.fa; el chequeo contra el vector real no corre",
    )
    def test_la_guia_1018_no_toca_el_casete(self):
        """Plausibilidad: la guia del 3'UTR no puede tocar un casete sin 3'UTR nativo.

        Si este test falla, el filtro esta mal montado — no es que la guia sea mala.
        """
        from shmir_design.specificity import load_database

        base = load_database(
            self.CASETE, name="casete AAV", version="vector real", expected_md5=None
        )
        r = filter_transgene(GUIA_1018, None, base)
        self.assertEqual(r.hits, ())
        self.assertEqual(r.sense_hits, ())
        self.assertIs(r.state, FilterState.PASS)


if __name__ == "__main__":
    unittest.main()


class TestIntegracionEnElTilado(unittest.TestCase):
    """El filtro tiene que aparecer en cada ventana, con casete o sin el."""

    SONDA = "GCGTCAGTACGATCGAATTACT" * 12

    def _tiling(self, casete=None):
        from shmir_design.tiling import tile_utr

        return tile_utr(self.SONDA, transgene_db=casete)

    def test_sin_casete_todas_las_ventanas_llevan_transgen_en_NOT_RUN(self):
        tiling = self._tiling()
        estados = {w.filter("transgen").state for w in tiling.windows}
        self.assertEqual(estados, {FilterState.NOT_RUN})

    def test_el_NOT_RUN_del_transgen_se_cuenta_en_el_informe(self):
        tiling = self._tiling()
        self.assertIn("transgen", tiling.not_run_counts())

    def test_con_casete_las_ventanas_que_pasan_lo_biofisico_se_escanean(self):
        tiling = self._tiling(_casete())
        evaluadas = [
            w for w in tiling.windows
            if w.filter("transgen").state is not FilterState.NOT_RUN
        ]
        self.assertTrue(evaluadas)

    def test_una_ventana_que_no_pasa_lo_biofisico_queda_NOT_RUN_por_coste(self):
        tiling = self._tiling(_casete())
        sin_escanear = [
            w for w in tiling.windows
            if w.filter("transgen").state is FilterState.NOT_RUN
        ]
        for w in sin_escanear:
            self.assertIn("coste", w.filter("transgen").reason)

    def test_un_casete_que_contiene_la_diana_condena_esas_ventanas(self):
        base = SpecificityDatabase(
            name="casete con la diana dentro",
            version="sonda",
            checksum="0" * 32,
            records={"casete": self.SONDA},
        )
        tiling = self._tiling(base)
        condenadas = [
            w for w in tiling.windows
            if w.filter("transgen").state is FilterState.FAIL
        ]
        self.assertTrue(condenadas)

    def test_el_informe_dice_que_el_transgen_no_corrio(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report

        tiling = self._tiling()
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        texto = text_report(
            species="sonda", tiling=tiling, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        self.assertIn("── Transgén terapeutico ──", texto)
        self.assertIn("NOT_RUN no es", texto)

    def test_el_informe_con_casete_lleva_la_procedencia(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report

        tiling = self._tiling(_casete())
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        texto = text_report(
            species="sonda", tiling=tiling, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        self.assertIn("sonda de casete AAV", texto)
