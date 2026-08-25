"""Regresion de `passenger_from_guide` sobre las 24 guias conocidas (fixture).

Regla 5: escritos antes que el cargador.

El fixture es `data/reference/guias_pasajera.fa`, con el valor esperado en la cabecera de
cada entrada: `bases_ok` (las bases que reproducen la estructura de SGEP) y `elegida` (la
que la regla debe devolver).

Mientras el fichero no este, estos tests se SALTAN de forma visible. No se sustituyen por
guias inventadas: son datos reales y el valor esperado es biologia, no formato.

El md5 del fichero esta registrado EN CODIGO (`guide_fixture.EXPECTED_MD5`), no solo en
el manifiesto: un checksum que solo vive en un fichero de datos se puede editar para que
un fichero malo pase (invariante 4 del proyecto).
"""

import unittest
from pathlib import Path

from shmir_design.folding import VIENNA_AVAILABLE, dot_bracket, reference_structure
from shmir_design.guide_fixture import (
    EXPECTED_MD5,
    FIXTURE_NAME,
    fixture_path,
    load_guide_fixture,
    parse_guide_fasta,
)
from shmir_design.scaffold import (
    MISMATCH_PREFERENCE,
    REFERENCE_HAIRPIN,
    build_hairpin,
    passenger_from_guide,
)

DISPONIBLE = fixture_path().is_file()
SALTAR = f"falta {FIXTURE_NAME}; la regresion de las 24 guias no corre"

#: Sonda de FORMATO, no de biologia: la guia y los valores son los de SGEP, que ya
#: estan en el repositorio. Sirve para probar el parseo de la cabecera.
SONDA = """\
>sgep_shRen713 bases_ok=C,A,G elegida=C
TAGATAAGCATTATAATTCCTA
"""


class TestFormatoDeLaCabecera(unittest.TestCase):

    def test_lee_la_guia(self):
        entradas = parse_guide_fasta(SONDA, source="sonda")
        self.assertEqual(entradas[0].guide, "TAGATAAGCATTATAATTCCTA")

    def test_lee_la_base_elegida(self):
        self.assertEqual(parse_guide_fasta(SONDA, source="s")[0].chosen, "C")

    def test_lee_las_bases_que_valen(self):
        self.assertEqual(parse_guide_fasta(SONDA, source="s")[0].ok, ("C", "A", "G"))

    def test_guarda_el_nombre(self):
        self.assertEqual(parse_guide_fasta(SONDA, source="s")[0].name, "sgep_shRen713")

    def test_una_cabecera_sin_elegida_aborta(self):
        from shmir_design.errors import ShmirDesignError

        malo = SONDA.replace(" elegida=C", "")
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_guide_fasta(malo, source="s")
        self.assertIn("elegida", str(ctx.exception))

    def test_una_cabecera_sin_bases_ok_aborta(self):
        from shmir_design.errors import ShmirDesignError

        malo = SONDA.replace("bases_ok=C,A,G ", "")
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_guide_fasta(malo, source="s")
        self.assertIn("bases_ok", str(ctx.exception))

    def test_una_elegida_que_no_esta_en_bases_ok_aborta(self):
        from shmir_design.errors import ShmirDesignError

        malo = SONDA.replace("elegida=C", "elegida=T")
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_guide_fasta(malo, source="s")
        self.assertIn("T", str(ctx.exception))

    def test_una_base_que_no_es_ACGT_aborta(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            parse_guide_fasta(SONDA.replace("elegida=C", "elegida=X"), source="s")

    def test_una_guia_repetida_aborta(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            parse_guide_fasta(SONDA + SONDA, source="s")

    def test_un_fichero_vacio_aborta(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            parse_guide_fasta("", source="s")

    def test_una_guia_de_longitud_rara_aborta(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError) as ctx:
            parse_guide_fasta(SONDA.replace("TAGATAAGCATTATAATTCCTA", "ACGT"), source="s")
        self.assertIn("22", str(ctx.exception))


class TestElChecksumEstaEnCodigo(unittest.TestCase):
    """Invariante 4: el md5 manda en el codigo, no solo en el manifiesto."""

    def test_esta_declarado(self):
        self.assertEqual(EXPECTED_MD5, "6281e37478453f03a34ad0856d8c83f7")

    def test_es_un_md5_hexadecimal(self):
        self.assertEqual(len(EXPECTED_MD5), 32)
        int(EXPECTED_MD5, 16)

    def test_el_manifiesto_declara_el_mismo(self):
        from shmir_design.manifest import load_manifest
        from shmir_design.manifest import MANIFEST_NAME

        manifiesto = load_manifest(fixture_path().parent / MANIFEST_NAME)
        self.assertEqual(manifiesto.entry(FIXTURE_NAME).md5, EXPECTED_MD5)


@unittest.skipUnless(DISPONIBLE, SALTAR)
class TestElFixture(unittest.TestCase):

    def test_el_md5_cuadra(self):
        load_guide_fixture()  # aborta si no

    def test_hay_20_guias(self):
        self.assertEqual(len(load_guide_fixture()), 20)

    def test_ninguna_es_de_las_que_ya_estaban(self):
        """Las 4 del repositorio ya tienen su test; estas son las que faltaban."""
        ya_estaban = {
            "TTTAGTACTGGATGGAACGGCC",
            "TAGATAAGCATTATAATTCCTA",
            "TAATTGAAAGAGCTACAGGTGG",
            "TAAAGGAATGCCACATATAGGG",
        }
        nuevas = {e.guide for e in load_guide_fixture()}
        self.assertEqual(nuevas & ya_estaban, set())


@unittest.skipUnless(DISPONIBLE, SALTAR)
@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no esta instalado")
class TestRegresionDeLaPasajera(unittest.TestCase):
    """Lo que pide el encargo: la base elegida tiene que ser la anotada."""

    def test_la_primera_base_de_la_pasajera_es_la_anotada(self):
        for entrada in load_guide_fixture():
            with self.subTest(guia=entrada.name):
                pasajera = passenger_from_guide(entrada.guide)
                self.assertEqual(pasajera.sequence[0], entrada.chosen)

    def test_y_coincide_con_chosen_base(self):
        for entrada in load_guide_fixture():
            with self.subTest(guia=entrada.name):
                pasajera = passenger_from_guide(entrada.guide)
                self.assertEqual(pasajera.chosen_base, entrada.chosen)

    def test_las_bases_que_valen_son_las_anotadas(self):
        """`bases_ok` de la cabecera contra `candidates` del criterio estructural."""
        for entrada in load_guide_fixture():
            with self.subTest(guia=entrada.name):
                self.assertEqual(
                    set(passenger_from_guide(entrada.guide).candidates),
                    set(entrada.ok),
                )

    def test_la_elegida_es_la_primera_de_la_preferencia_entre_las_que_valen(self):
        for entrada in load_guide_fixture():
            with self.subTest(guia=entrada.name):
                esperada = next(b for b in MISMATCH_PREFERENCE if b in entrada.ok)
                self.assertEqual(entrada.chosen, esperada)

    def test_las_20_horquillas_pliegan_como_la_referencia(self):
        referencia = reference_structure(REFERENCE_HAIRPIN)
        for entrada in load_guide_fixture():
            with self.subTest(guia=entrada.name):
                horquilla = build_hairpin(entrada.guide)
                self.assertEqual(dot_bracket(horquilla.sequence)[0], referencia)

    def test_ninguna_guia_acabada_en_G_elige_A(self):
        """La errata que motivo el criterio estructural, fijada sobre las 20."""
        for entrada in load_guide_fixture():
            if entrada.guide.endswith("G"):
                with self.subTest(guia=entrada.name):
                    self.assertNotEqual(entrada.chosen, "A")
                    self.assertEqual(
                        passenger_from_guide(entrada.guide).chosen_base, entrada.chosen
                    )


if __name__ == "__main__":
    unittest.main()


class TestElCargadorFuncionaDeExtremoAExtremo(unittest.TestCase):
    """El camino entero probado sobre un fichero de FORMATO, para que cuando llegue el
    de verdad lo unico nuevo sea el contenido."""

    def _fichero(self, texto=SONDA):
        import hashlib
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name) / FIXTURE_NAME
        ruta.write_text(texto, encoding="utf-8")
        md5 = hashlib.md5(ruta.read_bytes(), usedforsecurity=False).hexdigest()
        return Path(tmp.name), md5

    def test_carga_con_el_md5_correcto(self):
        directorio, md5 = self._fichero()
        entradas = load_guide_fixture(directorio, expected_md5=md5)
        self.assertEqual(entradas[0].chosen, "C")

    def test_un_md5_que_no_cuadra_aborta(self):
        from shmir_design.errors import ChecksumMismatchError

        directorio, _ = self._fichero()
        with self.assertRaises(ChecksumMismatchError):
            load_guide_fixture(directorio, expected_md5="0" * 32)

    def test_un_fichero_ausente_aborta_diciendo_cual(self):
        from shmir_design.errors import ShmirDesignError

        import tempfile

        with tempfile.TemporaryDirectory() as vacio:
            with self.assertRaises(ShmirDesignError) as ctx:
                load_guide_fixture(vacio)
            self.assertIn(FIXTURE_NAME, str(ctx.exception))

    @unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no esta instalado")
    def test_la_sonda_de_formato_pasa_la_regresion_de_verdad(self):
        """Con la guia de SGEP, que es real: el camino completo da el valor anotado."""
        directorio, md5 = self._fichero()
        entrada = load_guide_fixture(directorio, expected_md5=md5)[0]
        pasajera = passenger_from_guide(entrada.guide)
        self.assertEqual(pasajera.sequence[0], entrada.chosen)
        self.assertEqual(set(pasajera.candidates), set(entrada.ok))
