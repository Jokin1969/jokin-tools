"""El `.out` declara la especie de la BIBLIOTECA, y hay que comprobarla.

Regla 5: escritos antes.

Fallo real del 2026-08-26: se corrio el transcrito HUMANO contra la biblioteca MURINA.
El informe salio con formato correcto, cifras plausibles y **Alu 0 %** — que en humano es
imposible— y lo unico que lo delataba era una linea del resumen:

    The query species was assumed to be mus musculus

Un «Alu: 0 %» obtenido SIN BUSCAR Alu no puede pasar como veredicto. Es el mismo patron
que la errata nº 5 del 3'UTR fabricado: salida bien formada, cifras razonables, y la
unica pista en una linea que nadie lee.

Contramedida: `expected_species` es OBLIGATORIO. El parser lee la especie declarada y
aborta si no coincide — y aborta tambien si el fichero no la declara, porque entonces la
comprobacion no se puede hacer y «no se ha podido comprobar» no es «coincide».
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.masking import parse_rmsk_out

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
CORRIDA_MALA = DIR / "rmsk_humano_contra_biblioteca_murina.out"

CABECERA = """\
   SW   perc perc perc  query     position in query           matching repeat
score   div. del. ins.  sequence  begin end   (left)   repeat  class/family

  256   12.3  0.0  0.0  NM_011170    120   240  (1951) +  B1_Mus1  SINE/Alu

The query species was assumed to be mus musculus
"""

SIN_ESPECIE = """\
   SW   perc perc perc  query     position in query           matching repeat
score   div. del. ins.  sequence  begin end   (left)   repeat  class/family

  256   12.3  0.0  0.0  NM_011170    120   240  (1951) +  B1_Mus1  SINE/Alu
"""


def _leer(texto, especie):
    return parse_rmsk_out(
        texto, source="sonda", version="v", checksum="0" * 32,
        expected_species=especie,
    )


class TestLaEspecieSeComprueba(unittest.TestCase):

    def test_con_la_especie_correcta_lee_normal(self):
        mask = _leer(CABECERA, "mus musculus")
        self.assertEqual(len(mask.elements), 1)

    def test_la_especie_declarada_queda_guardada(self):
        self.assertEqual(_leer(CABECERA, "mus musculus").species, "mus musculus")

    def test_da_igual_mayusculas_y_espacios(self):
        self.assertEqual(_leer(CABECERA, "  Mus Musculus ").species, "mus musculus")

    def test_si_no_coincide_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            _leer(CABECERA, "homo sapiens")
        mensaje = str(ctx.exception)
        self.assertIn("mus musculus", mensaje)
        self.assertIn("homo sapiens", mensaje)

    def test_y_el_mensaje_explica_QUE_pasa_si_no_se_comprueba(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            _leer(CABECERA, "homo sapiens")
        mensaje = str(ctx.exception).lower()
        self.assertIn("alu", mensaje)
        self.assertIn("sin buscar", mensaje)

    def test_si_el_fichero_no_declara_especie_tambien_aborta(self):
        # No haber podido comprobar no es «coincide».
        with self.assertRaises(ShmirDesignError) as ctx:
            _leer(SIN_ESPECIE, "mus musculus")
        # La linea de la especie vive en el RESUMEN, no en el .out: los tres
        # .out reales del 2026-08-26 no la traen. Sin resumen no hay nada que
        # comprobar, y eso no es «coincide».
        motivo = str(ctx.exception).lower()
        self.assertIn("no hay forma de saber", motivo)
        self.assertIn("resumen", motivo)

    def test_expected_species_es_OBLIGATORIO(self):
        with self.assertRaises(TypeError):
            parse_rmsk_out(
                CABECERA, source="s", version="v", checksum="0" * 32
            )

    def test_una_especie_esperada_vacia_aborta(self):
        with self.assertRaises(ValueError):
            _leer(CABECERA, "")


@unittest.skipUnless(
    CORRIDA_MALA.is_file(),
    "NOT_RUN: falta data/reference/rmsk_humano_contra_biblioteca_murina.out — el "
    "fixture NEGATIVO de la corrida equivocada. Sin el, este test no puede reproducir "
    "la errata y NO se fabrica un .out de mentira (regla 5).",
)
class TestElFixtureNegativo(unittest.TestCase):
    """La corrida equivocada se ARCHIVA, no se destruye: sin un test que la reproduzca,
    una errata se olvida. Igual que el 3'UTR fabricado de 1246 nt."""

    def test_el_parser_la_RECHAZA_cuando_se_espera_humano(self):
        with self.assertRaises(ShmirDesignError):
            parse_rmsk_out(
                CORRIDA_MALA.read_text(encoding="utf-8"),
                source=str(CORRIDA_MALA), version="fixture negativo",
                checksum="0" * 32, expected_species="homo sapiens",
            )

    def test_y_declara_la_biblioteca_murina(self):
        mask = parse_rmsk_out(
            CORRIDA_MALA.read_text(encoding="utf-8"),
            source=str(CORRIDA_MALA), version="fixture negativo",
            checksum="0" * 32, expected_species="mus musculus",
        )
        self.assertEqual(mask.species, "mus musculus")

    def test_el_Alu_sale_a_cero_que_es_la_pista_que_NO_se_puede_leer_sola(self):
        # En un transcrito humano, Alu 0 % es imposible. Pero la cifra por si sola no
        # dice nada: hay que mirar la especie de la biblioteca.
        mask = parse_rmsk_out(
            CORRIDA_MALA.read_text(encoding="utf-8"),
            source=str(CORRIDA_MALA), version="fixture negativo",
            checksum="0" * 32, expected_species="mus musculus",
        )
        alu = [e for e in mask.elements if "Alu" in e.family]
        self.assertEqual(alu, [])


class TestUnCeroSinResumenNoEsUnResultado(unittest.TestCase):
    """Un `.out` sin filas no distingue «no habia repetitivos» de «no llego a correr».

    Esa diferencia es exactamente la de PASS contra NOT_RUN, asi que el `.out` vacio
    solo vale acompañado del RESUMEN con los ceros explicitos por familia.
    """

    VACIO = """\
   SW   perc perc perc  query     position in query           matching repeat
score   div. del. ins.  sequence  begin end   (left)   repeat  class/family

The query species was assumed to be mus musculus
"""

    RESUMEN = """\
sequences:             1
total length:       2191 bp
==================================================
SINEs:                 0          0 bp    0.00 %
      B1/Alu           0          0 bp    0.00 %
      B2-B4            0          0 bp    0.00 %
LINEs:                 0          0 bp    0.00 %
LTR elements:          0          0 bp    0.00 %
Simple repeats:        1         45 bp    2.05 %
"""

    def _leer(self, texto, resumen=None):
        return parse_rmsk_out(
            texto, source="sonda", version="v", checksum="0" * 32,
            expected_species="mus musculus", summary=resumen,
        )

    def test_sin_filas_y_sin_resumen_ABORTA(self):
        # Mas fuerte que devolver una mascara no concluyente: sin el resumen el fichero
        # no se puede usar para nada, y el filtro de repetitivos se queda en NOT_RUN
        # porque no hay mascara que pasarle.
        with self.assertRaises(ShmirDesignError) as ctx:
            self._leer(self.VACIO)
        mensaje = str(ctx.exception)
        self.assertIn("NO vino el resumen", mensaje)
        self.assertIn("PASS contra NOT_RUN", mensaje)

    def test_sin_filas_pero_CON_resumen_si_lo_es(self):
        self.assertTrue(self._leer(self.VACIO, self.RESUMEN).conclusive)

    def test_con_filas_lo_es_aunque_no_haya_resumen(self):
        self.assertTrue(self._leer(CABECERA).conclusive)

    def test_el_resumen_se_guarda_entero(self):
        mask = self._leer(self.VACIO, self.RESUMEN)
        self.assertIn("B1/Alu", mask.summary)
        self.assertIn("Simple repeats", mask.summary)

    def test_la_biblioteca_se_registra_aparte_de_la_version(self):
        mask = parse_rmsk_out(
            CABECERA, source="s", version="RepeatMasker open-4.0.9",
            checksum="0" * 32, expected_species="mus musculus",
            library="Dfam_3.0",
        )
        self.assertEqual(mask.library, "Dfam_3.0")
        self.assertIn("Dfam_3.0", mask.provenance)
        self.assertIn("4.0.9", mask.provenance)
