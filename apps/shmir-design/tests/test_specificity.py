"""Tests del filtro de especificidad (paso 12).

Regla 5: escritos antes que `shmir_design/specificity.py`.

Dato real: la guia 1018 `TTTAGTACTGGATGGAACGGCC` casa con 0 desapareamientos en
NM_011170.3, posiciones 1967-1988, en orientacion ANTISENTIDO. De ahi se deduce que ese
tramo del mRNA es el complementario reverso de la guia, `GGCCGTTCCATCCAGTACTAAA`, y esa
es la unica secuencia real que aparece aqui. Comprobado ademas contra cuatro datos
independientes que ya estaban en el proyecto: la seed TTAGTAC, su sitio complementario
GTACTAA, el ACTAAA en 1983 y los 203 nt al extremo 3'.

El resto son andamios de N: la N nunca casa, asi que solo casa lo que se coloca a
proposito.
"""

import unittest

from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.specificity import (
    MAX_MISMATCHES,
    SpecificityDatabase,
    Strand,
    filter_specificity,
    reverse_complement,
    scan_database,
)

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"
SITIO_1018 = "GGCCGTTCCATCCAGTACTAAA"          # revcomp: el tramo real del mRNA
DIANA = "NM_011170.3"


def transcrito(secuencia_por_posicion: dict[int, str], longitud: int = 2191) -> str:
    """Andamio de N con tramos reales colocados en su posicion (1-based)."""
    bases = ["N"] * longitud
    for inicio, tramo in secuencia_por_posicion.items():
        for offset, base in enumerate(tramo):
            bases[inicio - 1 + offset] = base
    return "".join(bases)


def base_de_datos(registros: dict[str, str], **kwargs) -> SpecificityDatabase:
    datos = dict(
        name="RefSeq RNA de prueba",
        version="2026-08-25",
        checksum="0" * 32,
        records=registros,
    )
    datos.update(kwargs)
    return SpecificityDatabase(**datos)


class TestRegresionGuia1018(unittest.TestCase):
    """Si esto falla, el motor esta mal configurado."""

    def base(self):
        return base_de_datos({DIANA: transcrito({1967: SITIO_1018})})

    def test_exactamente_un_sitio_de_0_desapareamientos(self):
        hits = scan_database(GUIA_1018, self.base())
        ceros = [h for h in hits if h.mismatches == 0]
        self.assertEqual(len(ceros), 1)

    def test_en_las_coordenadas_declaradas(self):
        hit = next(h for h in scan_database(GUIA_1018, self.base()) if h.mismatches == 0)
        self.assertEqual(hit.transcript, DIANA)
        self.assertEqual((hit.start, hit.end), (1967, 1988))

    def test_en_orientacion_antisentido(self):
        hit = next(h for h in scan_database(GUIA_1018, self.base()) if h.mismatches == 0)
        self.assertIs(hit.strand, Strand.ANTISENSE)


class TestOrientacion(unittest.TestCase):
    """Un mRNA solo es diana si contiene el COMPLEMENTO INVERSO de la guia."""

    def test_el_complemento_inverso_es_el_sitio(self):
        self.assertEqual(reverse_complement(GUIA_1018), SITIO_1018)

    def test_un_hit_en_la_misma_orientacion_no_es_off_target(self):
        base = base_de_datos({"otro": transcrito({100: GUIA_1018}, longitud=500)})
        hits = scan_database(GUIA_1018, base)
        self.assertTrue(all(h.strand is Strand.SENSE for h in hits))

    def test_los_hits_sentido_no_cuentan_para_el_veredicto(self):
        base = base_de_datos({"otro": transcrito({100: GUIA_1018}, longitud=500)})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIs(resultado.state, FilterState.PASS)
        self.assertIn("sentido", resultado.reason.lower())

    def test_la_salida_dice_cuantos_se_han_descartado_por_orientacion(self):
        base = base_de_datos({"otro": transcrito({100: GUIA_1018}, longitud=500)})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIn("1", resultado.reason)


class TestDesapareamientos(unittest.TestCase):

    def sitio_con_cambios(self, posiciones):
        bases = list(SITIO_1018)
        for indice in posiciones:
            bases[indice] = "A" if bases[indice] != "A" else "C"
        return "".join(bases)

    def test_encuentra_un_sitio_con_1_desapareamiento(self):
        base = base_de_datos({"otro": transcrito({50: self.sitio_con_cambios([10])}, 200)})
        hits = [h for h in scan_database(GUIA_1018, base) if h.strand is Strand.ANTISENSE]
        self.assertEqual([h.mismatches for h in hits], [1])

    def test_encuentra_un_sitio_con_2_desapareamientos(self):
        base = base_de_datos({"otro": transcrito({50: self.sitio_con_cambios([3, 15])}, 200)})
        hits = [h for h in scan_database(GUIA_1018, base) if h.strand is Strand.ANTISENSE]
        self.assertEqual([h.mismatches for h in hits], [2])

    def test_con_3_desapareamientos_ya_no_es_hit(self):
        base = base_de_datos({"otro": transcrito({50: self.sitio_con_cambios([3, 10, 15])}, 200)})
        self.assertEqual(scan_database(GUIA_1018, base), [])

    def test_el_maximo_declarado_es_2(self):
        self.assertEqual(MAX_MISMATCHES, 2)

    def test_la_N_nunca_casa(self):
        base = base_de_datos({"todoN": "N" * 500})
        self.assertEqual(scan_database(GUIA_1018, base), [])


class TestVeredicto(unittest.TestCase):

    def test_solo_el_gen_diana_pasa(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIs(resultado.state, FilterState.PASS)

    def test_un_sitio_de_0_fuera_de_la_diana_es_FAIL(self):
        base = base_de_datos({
            DIANA: transcrito({1967: SITIO_1018}),
            "NM_otro.1": transcrito({100: SITIO_1018}, 500),
        })
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("NM_otro.1", resultado.reason)

    def test_un_sitio_de_1_fuera_de_la_diana_tambien_es_FAIL(self):
        sitio = "A" + SITIO_1018[1:]
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018}),
                              "NM_otro.1": transcrito({100: sitio}, 500)})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIs(resultado.state, FilterState.FAIL)

    def test_un_sitio_de_2_es_aviso_pero_no_FAIL(self):
        bases = list(SITIO_1018)
        bases[3], bases[15] = "A", "A"
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018}),
                              "NM_otro.1": transcrito({100: "".join(bases)}, 500)})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIs(resultado.state, FilterState.PASS)
        self.assertIn("2 desapareamientos", resultado.reason)
        self.assertIn("NM_otro.1", resultado.reason)

    def test_sin_base_de_datos_es_NOT_RUN(self):
        resultado = filter_specificity(GUIA_1018, None, None, target=DIANA)
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("NOT_RUN no es PASS", resultado.reason)

    def test_sin_gen_diana_declarado_aborta(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        with self.assertRaises(ValueError):
            filter_specificity(GUIA_1018, None, base, target="")


class TestGuiaYPasajeraPorSeparado(unittest.TestCase):
    """Dos especies distintas con off-targets distintos; se deduplica y se marca."""

    def test_cada_hit_dice_de_donde_viene(self):
        pasajera = "C" + reverse_complement(GUIA_1018)[1:]
        base = base_de_datos({
            DIANA: transcrito({1967: SITIO_1018}),
            "NM_otro.1": transcrito({100: reverse_complement(pasajera)}, 500),
        })
        resultado = filter_specificity(GUIA_1018, pasajera, base, target=DIANA)
        origenes = {origen for hit in resultado.hits for origen in hit.queries}
        self.assertIn("pasajera", origenes)

    def test_los_hits_compartidos_salen_una_sola_vez(self):
        pasajera = "C" + reverse_complement(GUIA_1018)[1:]
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        resultado = filter_specificity(GUIA_1018, pasajera, base, target=DIANA)
        posiciones = [(h.transcript, h.start, h.strand) for h in resultado.hits]
        self.assertEqual(len(posiciones), len(set(posiciones)))

    def test_sin_pasajera_solo_se_evalua_la_guia(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertTrue(all(hit.queries == ("guia",) for hit in resultado.hits))


class TestProcedencia(unittest.TestCase):

    def test_la_base_exige_nombre_version_y_checksum(self):
        for falta in ("name", "version", "checksum"):
            with self.subTest(falta):
                with self.assertRaises(ValueError):
                    base_de_datos({DIANA: "ACGT"}, **{falta: ""})

    def test_la_procedencia_sale_en_el_motivo(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        resultado = filter_specificity(GUIA_1018, None, base, target=DIANA)
        self.assertIn("RefSeq RNA de prueba", resultado.reason)
        self.assertIn("2026-08-25", resultado.reason)

    def test_los_parametros_exactos_salen_en_el_informe(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        texto = filter_specificity(GUIA_1018, None, base, target=DIANA).format_text()
        self.assertIn("22 nt", texto)
        self.assertIn("2 desapareamientos", texto)
        self.assertIn("0" * 32, texto)

    def test_una_base_vacia_aborta(self):
        with self.assertRaises(ShmirDesignError):
            base_de_datos({})


class TestLoQueEsteFiltroNoResuelve(unittest.TestCase):
    """El hueco importante: los off-targets mediados por seed."""

    def test_el_informe_lo_dice(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        texto = filter_specificity(GUIA_1018, None, base, target=DIANA).format_text()
        self.assertIn("seed", texto.lower())
        self.assertIn("7mer", texto)

    def test_y_dice_que_ningun_alineador_los_devuelve(self):
        base = base_de_datos({DIANA: transcrito({1967: SITIO_1018})})
        texto = filter_specificity(GUIA_1018, None, base, target=DIANA).format_text()
        self.assertIn("alineador", texto.lower())


if __name__ == "__main__":
    unittest.main()
