"""Tests de la resolucion de anatomia, ahora en el nucleo.

Regla 5: escritos antes de mover nada.

Vivia dentro de `tools/design.py`, asi que la interfaz no podia usarla — y acabo
teniendo su propia version, con el `else: todo es 3'UTR` que el CLI habia cerrado. Un
mismo mRNA daba una anatomia por consola y otra por navegador. Por eso baja al nucleo:
para que solo haya una.

Las secuencias son SONDAS de mecanismo, no datos biologicos. La cabecera de GenBank es
la REAL de NM_011170.3 (2191 nt, CDS 185..949) y no lleva bloque ORIGIN: las coordenadas
son metadatos, la secuencia sigue viniendo del FASTA.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.anatomy import RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.resolve import SIN_ANATOMIA, resolve_anatomy

UTR5 = "GCGTCAGTACGATCGAATTACT" * 2            # 44 nt   -> 1..44
CDS = "ATG" + "GCTAACGGGACT" * 8 + "TAA"        # 102 nt  -> 45..146
UTR3 = "GCGTCAGTACGATCGAATTACT" * 20            # 440 nt  -> 147..586
SONDA = UTR5 + CDS + UTR3                       # 586 nt

GENBANK = """\
LOCUS       SONDA                    586 bp    mRNA    linear   ROD 25-MAY-2024
DEFINITION  Sonda de mecanismo, no es un registro real.
ACCESSION   SONDA
VERSION     SONDA.1
FEATURES             Location/Qualifiers
     source          1..586
     CDS             45..146
                     /codon_start=1
//
"""


def _gb(directorio: Path) -> Path:
    ruta = directorio / "sonda.gb"
    ruta.write_text(GENBANK, encoding="utf-8")
    return ruta


class TestLasTresVias(unittest.TestCase):

    def test_el_genbank_resuelve_y_deja_su_procedencia(self):
        with TemporaryDirectory() as tmp:
            anatomia = resolve_anatomy(
                name="sonda", sequence=SONDA, genbank=_gb(Path(tmp))
            )
        self.assertEqual(anatomia.source, RegionSource.ANOTACION_GENBANK)
        self.assertEqual(anatomia.cds, (45, 146))

    def test_las_coordenadas_a_mano_resuelven(self):
        anatomia = resolve_anatomy(name="sonda", sequence=SONDA, cds=(45, 146))
        self.assertEqual(anatomia.source, RegionSource.CDS_DECLARADA)

    def test_declarar_que_ya_es_3utr_resuelve(self):
        anatomia = resolve_anatomy(name="sonda", sequence=UTR3, whole_is_utr3=True)
        self.assertEqual(anatomia.source, RegionSource.TODO_3UTR_DECLARADO)

    def test_un_fixture_verificado_resuelve(self):
        anatomia = resolve_anatomy(name="sonda", sequence=UTR3, from_fixture=True)
        self.assertEqual(anatomia.source, RegionSource.FIXTURE_VERIFICADO)


class TestNoHayCaminoSilencioso(unittest.TestCase):

    def test_sin_ninguna_via_aborta(self):
        # El agujero que se cerro en el CLI y que la interfaz habia reabierto.
        with self.assertRaises(ShmirDesignError) as caja:
            resolve_anatomy(name="sonda", sequence=SONDA)
        self.assertIn(SIN_ANATOMIA.split(",")[0], str(caja.exception))

    def test_el_error_nombra_las_tres_vias(self):
        with self.assertRaises(ShmirDesignError) as caja:
            resolve_anatomy(name="sonda", sequence=SONDA)
        texto = str(caja.exception).lower()
        for via in ("genbank", "cds", "3'utr"):
            with self.subTest(via):
                self.assertIn(via, texto)

    def test_el_error_dice_de_quien_es_la_secuencia(self):
        with self.assertRaises(ShmirDesignError) as caja:
            resolve_anatomy(name="raton", sequence=SONDA)
        self.assertIn("raton", str(caja.exception))

    def test_cada_frontal_puede_añadir_como_se_resuelve_en_el(self):
        with self.assertRaises(ShmirDesignError) as caja:
            resolve_anatomy(name="sonda", sequence=SONDA, hint="  usa --cds INICIO FIN")
        self.assertIn("--cds INICIO FIN", str(caja.exception))


class TestPrioridades(unittest.TestCase):

    def test_el_genbank_manda_sobre_las_coordenadas_a_mano(self):
        with TemporaryDirectory() as tmp:
            anatomia = resolve_anatomy(
                name="sonda", sequence=SONDA, genbank=_gb(Path(tmp)), cds=(1, 3)
            )
        self.assertEqual(anatomia.cds, (45, 146))

    def test_un_genbank_de_otra_longitud_aborta(self):
        # El chequeo que pilla el fichero equivocado: 586 nt declarados contra una
        # secuencia mas corta.
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ShmirDesignError):
                resolve_anatomy(name="sonda", sequence=UTR3, genbank=_gb(Path(tmp)))

    def test_el_md5_del_genbank_se_comprueba_si_se_pide(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ShmirDesignError):
                resolve_anatomy(
                    name="sonda", sequence=SONDA, genbank=_gb(Path(tmp)),
                    genbank_md5="0" * 32,
                )


class TestFronteras(unittest.TestCase):

    def test_un_cds_sin_codon_de_parada_aborta(self):
        from shmir_design.resolve import check_boundaries

        anatomia = resolve_anatomy(name="sonda", sequence=SONDA, cds=(44, 145))
        with self.assertRaises(ShmirDesignError) as caja:
            check_boundaries(SONDA, anatomia)
        self.assertIn("codon de parada", str(caja.exception))

    def test_se_puede_permitir_a_proposito(self):
        from shmir_design.resolve import check_boundaries

        anatomia = resolve_anatomy(name="sonda", sequence=SONDA, cds=(44, 145))
        avisos = check_boundaries(SONDA, anatomia, allow_no_stop=True)
        self.assertTrue(any("codon de parada" in a for a in avisos))

    def test_un_cds_correcto_no_aborta(self):
        from shmir_design.resolve import check_boundaries

        anatomia = resolve_anatomy(name="sonda", sequence=SONDA, cds=(45, 146))
        check_boundaries(SONDA, anatomia)


if __name__ == "__main__":
    unittest.main()
