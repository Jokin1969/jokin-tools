"""Tests del lector de RepeatMasker (bloque 2).

Regla 5: escritos antes de implementarlo.

En raton el riesgo son los SINE B1/B2. Una guia derivada de un elemento repetitivo tiene
miles de sitios perfectos: no es un off-target, es inservible. Por eso el nombre de la
familia tiene que llegar hasta el motivo del FAIL, no solo el intervalo.

El enmascarado va ANTES de tilar y se RETILA — eso ya estaba, y hay un test que lo fija.

Coordenadas: los ficheros que se aceptan estan en coordenadas de la secuencia consultada
(RepeatMasker corrido sobre el propio FASTA del transcrito). Un fichero en coordenadas
genomicas tiene numeros enormes y se detecta al aplicar la mascara: se aborta en vez de
enmascarar el tramo equivocado.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.errors import ChecksumMismatchError, ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.masking import (
    RepeatElement,
    RepeatMask,
    apply_mask,
    filter_repeats,
    load_rmsk,
    parse_rmsk_out,
    parse_rmsk_table,
)

#: Salida de RepeatMasker (.out) sobre un transcrito. Coordenadas de la consulta.
RMSK_OUT = """\
   SW   perc perc perc  query     position in query           matching repeat
score   div. del. ins.  sequence  begin end   (left)   repeat  class/family

  256   12.3  0.0  0.0  NM_011170    120   240  (1951) +  B1_Mus1  SINE/Alu
  198   18.1  1.2  0.4  NM_011170    900   1010  (1181) C  B2_Mm1a  SINE/B2

The query species was assumed to be mus musculus
"""

#: Tabla rmsk de UCSC: genoStart es 0-based y genoEnd exclusivo.
RMSK_TABLE = """\
#bin\tswScore\tmilliDiv\tmilliDel\tmilliIns\tgenoName\tgenoStart\tgenoEnd\tgenoLeft\tstrand\trepName\trepClass\trepFamily\trepStart\trepEnd\trepLeft\tid
585\t256\t123\t0\t0\tNM_011170\t119\t240\t-1951\t+\tB1_Mus1\tSINE\tAlu\t1\t121\t0\t1
586\t198\t181\t12\t4\tNM_011170\t899\t1010\t-1181\t-\tB2_Mm1a\tSINE\tB2\t1\t111\t0\t2
"""


class TestLecturaDelOut(unittest.TestCase):

    def test_saca_los_dos_elementos(self):
        mask = parse_rmsk_out(
            RMSK_OUT, source="sonda", version="v", checksum="0" * 32,
            expected_species="mus musculus",
        )
        self.assertEqual(len(mask.elements), 2)

    def test_las_coordenadas_son_1_based_inclusivas(self):
        mask = parse_rmsk_out(
            RMSK_OUT, source="sonda", version="v", checksum="0" * 32,
            expected_species="mus musculus",
        )
        self.assertEqual(mask.intervals[0], (120, 240))

    def test_guarda_el_nombre_y_la_familia(self):
        mask = parse_rmsk_out(
            RMSK_OUT, source="sonda", version="v", checksum="0" * 32,
            expected_species="mus musculus",
        )
        self.assertEqual(mask.elements[0].name, "B1_Mus1")
        self.assertEqual(mask.elements[1].family, "SINE/B2")

    def test_reconoce_los_SINE_de_raton(self):
        mask = parse_rmsk_out(
            RMSK_OUT, source="sonda", version="v", checksum="0" * 32,
            expected_species="mus musculus",
        )
        self.assertTrue(all(e.is_sine for e in mask.elements))

    def test_ignora_la_cabecera_y_las_lineas_vacias(self):
        mask = parse_rmsk_out(
            RMSK_OUT, source="sonda", version="v", checksum="0" * 32,
            expected_species="mus musculus",
        )
        self.assertEqual(len(mask.intervals), 2)

    def test_una_linea_con_pocos_campos_aborta(self):
        malo = RMSK_OUT + "  100  1.0\n"
        with self.assertRaises(ShmirDesignError):
            parse_rmsk_out(
                malo, source="sonda", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            )

    def test_un_fichero_sin_ningun_elemento_aborta(self):
        # Con la linea de especie: si no, aborta antes y por otra razon (la especie se
        # comprueba primero). Lo que este test fija es el cero SIN resumen.
        solo_cabecera = (
            "\n".join(RMSK_OUT.splitlines()[:2])
            + "\n\nThe query species was assumed to be mus musculus\n"
        )
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_rmsk_out(
                solo_cabecera, source="sonda", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            )
        self.assertIn("ningún", str(ctx.exception).lower())


class TestLecturaDeLaTablaUCSC(unittest.TestCase):

    def test_convierte_de_0_based_a_1_based(self):
        """genoStart 119 (0-based) -> 120 (1-based)."""
        mask = parse_rmsk_table(RMSK_TABLE, source="sonda", version="v", checksum="0" * 32)
        self.assertEqual(mask.intervals[0], (120, 240))

    def test_las_dos_lecturas_dan_lo_mismo(self):
        a = parse_rmsk_out(
                RMSK_OUT, source="s", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            )
        b = parse_rmsk_table(RMSK_TABLE, source="s", version="v", checksum="0" * 32)
        self.assertEqual(a.intervals, b.intervals)

    def test_junta_clase_y_familia(self):
        mask = parse_rmsk_table(RMSK_TABLE, source="s", version="v", checksum="0" * 32)
        self.assertEqual(mask.elements[1].family, "SINE/B2")


class TestProcedencia(unittest.TestCase):

    def test_la_version_y_el_checksum_son_obligatorios(self):
        for campo in ("version", "checksum"):
            kwargs = dict(
                source="s", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            )
            kwargs[campo] = ""
            with self.assertRaises(ValueError):
                parse_rmsk_out(RMSK_OUT, **kwargs)

    def test_la_procedencia_sale_en_el_texto(self):
        mask = parse_rmsk_out(
            RMSK_OUT, source="rmsk mm39", version="2026-01", checksum="0" * 32,
            expected_species="mus musculus", library="Dfam_3.0",
        )
        self.assertIn("mm39", mask.provenance)
        self.assertIn("2026-01", mask.provenance)
        # La BIBLIOTECA va pegada a la version: el veredicto depende de las dos.
        self.assertIn("Dfam_3.0", mask.provenance)


class TestCoordenadasQueNoCuadran(unittest.TestCase):

    def test_una_mascara_que_se_sale_de_la_secuencia_aborta(self):
        mask = parse_rmsk_out(
                RMSK_OUT, source="s", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            )
        with self.assertRaises(ShmirDesignError) as ctx:
            apply_mask("A" * 500, mask)
        self.assertIn("500", str(ctx.exception))

    def test_el_error_sugiere_que_el_fichero_es_genomico(self):
        mask = parse_rmsk_out(
                RMSK_OUT, source="s", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            )
        with self.assertRaises(ShmirDesignError) as ctx:
            apply_mask("A" * 500, mask)
        self.assertIn("genomic", str(ctx.exception).lower())

    def test_una_mascara_que_cabe_enmascara(self):
        enmascarada = apply_mask(
            "A" * 1200,
            parse_rmsk_out(
                RMSK_OUT, source="s", version="v", checksum="0" * 32,
                expected_species="mus musculus",
            ),
        )
        self.assertEqual(enmascarada[119], "N")
        self.assertEqual(enmascarada[118], "A")


class TestElMotivoDelFAIL(unittest.TestCase):

    MASK = parse_rmsk_out(
        RMSK_OUT, source="rmsk", version="v", checksum="0" * 32,
        expected_species="mus musculus",
    )

    def test_el_FAIL_nombra_la_familia(self):
        r = filter_repeats(125, 146, self.MASK)
        self.assertIs(r.state, FilterState.FAIL)
        self.assertIn("SINE/Alu", r.reason)

    def test_el_FAIL_nombra_el_elemento(self):
        self.assertIn("B1_Mus1", filter_repeats(125, 146, self.MASK).reason)

    def test_el_FAIL_explica_que_no_es_un_off_target_sino_inservible(self):
        self.assertIn("inservible", filter_repeats(125, 146, self.MASK).reason)

    def test_fuera_de_los_elementos_es_PASS(self):
        self.assertIs(filter_repeats(300, 321, self.MASK).state, FilterState.PASS)

    def test_sin_mascara_sigue_siendo_NOT_RUN(self):
        self.assertIs(filter_repeats(300, 321, None).state, FilterState.NOT_RUN)


class TestCargaDesdeDisco(unittest.TestCase):

    def test_detecta_el_formato_out(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "raton.out"
            p.write_text(RMSK_OUT, encoding="utf-8")
            self.assertEqual(load_rmsk(p, version="v", expected_species="mus musculus").intervals[0], (120, 240))

    def test_detecta_la_tabla_de_UCSC(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "rmsk.txt"
            p.write_text(RMSK_TABLE, encoding="utf-8")
            self.assertEqual(load_rmsk(p, version="v", expected_species="mus musculus").intervals[0], (120, 240))

    def test_un_md5_que_no_cuadra_aborta(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "raton.out"
            p.write_text(RMSK_OUT, encoding="utf-8")
            with self.assertRaises(ChecksumMismatchError):
                load_rmsk(
                    p, version="v", expected_species="mus musculus",
                    expected_md5="0" * 32,
                )

    def test_un_fichero_ausente_aborta_diciendo_cual(self):
        with self.assertRaises((ShmirDesignError, OSError)) as ctx:
            load_rmsk(
                Path("/no/existe/raton.out"), version="v",
                expected_species="mus musculus",
            )
        self.assertIn("raton.out", str(ctx.exception))


class TestPlausibilidad(unittest.TestCase):
    """La guia 1018 da un unico hit en raton por BLAST: no puede ser repetitiva."""

    DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
    RMSK = DIR / "rmsk_mouse.out"
    TBL = DIR / "rmsk_mouse.tbl"

    @unittest.skipUnless(
        RMSK.is_file() and TBL.is_file(),
        "faltan data/reference/rmsk_mouse.{out,tbl}; el chequeo no corre",
    )
    def test_la_ventana_1018_no_cae_en_un_repetitivo(self):
        """Si este test falla, el filtro esta mal montado, no la guia."""
        mask = load_rmsk(
            self.RMSK, version="4.0.9", expected_species="mus musculus",
            library="Dfam_3.0", summary_path=self.TBL,
        )
        self.assertIs(filter_repeats(1018, 1039, mask).state, FilterState.PASS)

    @unittest.skipUnless(
        RMSK.is_file() and TBL.is_file(), "faltan los ficheros rmsk_mouse"
    )
    def test_la_UNICA_repeticion_murina_esta_en_el_CDS_y_no_toca_el_3UTR(self):
        # Con la corrida real: (CTC)n en tx:892-936, dentro del CDS (185-949). El 3'UTR
        # empieza en 950, asi que NINGUNA ventana del barrido cae en un repetitivo.
        mask = load_rmsk(
            self.RMSK, version="4.0.9", expected_species="mus musculus",
            library="Dfam_3.0", summary_path=self.TBL,
        )
        self.assertEqual([(e.start, e.end) for e in mask.elements], [(892, 936)])
        self.assertIs(filter_repeats(950, 2191, mask).state, FilterState.PASS)


if __name__ == "__main__":
    unittest.main()
