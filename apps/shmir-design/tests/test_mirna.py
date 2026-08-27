"""Tests de la colision de seed con miARN endogeno (bloque 1a).

Regla 5: escritos antes que `shmir_design/mirna.py`.

Por que dos niveles y no uno: el espacio de 7-meros son 16.384 combinaciones y hay unos
2.000 maduros murinos anotados, asi que por azar cerca del 10 % de las guias colisionaran
con alguno. "Cualquier colision = FAIL" tiraria uno de cada diez candidatos, casi todos
por chocar con miARN que no se expresan en cerebro.

  FAIL  colision con un miARN abundante en cerebro (lista curada, con procedencia)
  WARN  colision con cualquier otro anotado en miRBase

Sin fichero de abundancia el nivel FAIL queda NOT_RUN y el WARN corre igual. No hay
ninguna lista por defecto escrita en el codigo, ni de abundancia ni de maduros.

Regla 1: en este fichero no se fabrica ninguna secuencia de miARN con nombre real. Las
entradas de prueba se llaman `mmu-sonda-*` y son sondas de mecanismo. Las seeds que se
usan si son reales: salen de la lista de arranque que ya vive en `seeds.py`.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.errors import ChecksumMismatchError, ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.mirna import (
    AbundanceList,
    MatureSet,
    filter_seed_collision,
    load_abundance_list,
    load_mature_fa,
    parse_abundance_list,
    parse_mature_fa,
)

#: Seeds reales, tomadas de la lista de arranque de `seeds.py`.
SEED_124 = "AAGGCAC"      # miR-124-3p
SEED_9 = "CTTTGGT"        # miR-9-5p
SEED_137 = "GGAATGT"      # miR-137

#: Guias de prueba: 22 nt cuyas posiciones 2-8 son la seed que interesa.
def _guia(seed: str) -> str:
    return "T" + seed + "G" * 14


MADUROS = """\
>mmu-sonda-124 sonda de mecanismo, no es un maduro real
UAAGGCACGCGGGGGGGGGGGG
>mmu-sonda-9 sonda de mecanismo, no es un maduro real
UCUUUGGUGCGGGGGGGGGGGG
>hsa-sonda-137 sonda de mecanismo, no es un maduro real
UGGAATGTGCGGGGGGGGGGGG
>dme-sonda-otra sonda de mecanismo de otra especie
UAAAAAAAGCGGGGGGGGGGGG
"""


def _maduros(prefixes=("mmu-", "hsa-")) -> MatureSet:
    return parse_mature_fa(
        MADUROS, source="sonda", version="sonda", checksum="0" * 32, prefixes=prefixes
    )


class TestLecturaDeMaduros(unittest.TestCase):

    def test_saca_la_seed_de_cada_maduro(self):
        maduros = _maduros()
        self.assertIn(SEED_124, maduros.seeds)

    def test_la_seed_va_en_ADN_no_en_ARN(self):
        for seed in _maduros().seeds:
            self.assertNotIn("U", seed)

    def test_la_seed_son_las_posiciones_2_a_8(self):
        """UAAGGCACGC... -> posiciones 2-8 = AAGGCAC."""
        self.assertIn(SEED_124, _maduros().seeds)

    def test_filtra_por_prefijo_de_especie(self):
        maduros = _maduros(prefixes=("mmu-",))
        self.assertIn(SEED_124, maduros.seeds)
        self.assertNotIn(SEED_137, maduros.seeds)

    def test_deja_fuera_las_especies_que_no_se_piden(self):
        nombres = [n for nombres in _maduros().seeds.values() for n in nombres]
        self.assertFalse([n for n in nombres if n.startswith("dme-")])

    def test_varios_maduros_pueden_compartir_seed(self):
        texto = MADUROS + ">mmu-sonda-124b sonda\nUAAGGCACGCTTTTTTTTTTTT\n"
        maduros = parse_mature_fa(
            texto, source="sonda", version="sonda", checksum="0" * 32
        )
        self.assertEqual(len(maduros.seeds[SEED_124]), 2)

    def test_la_procedencia_es_obligatoria(self):
        for campo in ("source", "version", "checksum"):
            kwargs = dict(source="s", version="v", checksum="0" * 32)
            kwargs[campo] = ""
            with self.assertRaises(ValueError):
                parse_mature_fa(MADUROS, **kwargs)

    def test_un_fichero_vacio_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_mature_fa("", source="s", version="v", checksum="0" * 32)

    def test_un_maduro_mas_corto_que_la_seed_aborta(self):
        texto = ">mmu-sonda-corta sonda\nUAAG\n"
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_mature_fa(texto, source="s", version="v", checksum="0" * 32)
        self.assertIn("mmu-sonda-corta", str(ctx.exception))

    def test_ninguna_entrada_de_las_especies_pedidas_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_mature_fa(
                MADUROS, source="s", version="v", checksum="0" * 32,
                prefixes=("xxx-",),
            )


class TestListaDeAbundancia(unittest.TestCase):

    #: La capa AMPLIADA necesita referencia y umbral en la cabecera desde el
    #: 2026-08-26: sin ellos no se usa (ver tests/test_abundancia_dos_capas.py).
    LISTA = """\
# MirGeneDB, miARN abundantes en cerebro de raton
# referencia: dataset publicado de small RNA-seq de cerebro murino
# umbral: 100 RPM
mmu-sonda-124
mmu-sonda-9
"""

    def test_lee_los_nombres(self):
        lista = parse_abundance_list(
            self.LISTA, source="sonda", version="sonda", checksum="0" * 32
        )
        self.assertEqual(lista.names, frozenset({"mmu-sonda-124", "mmu-sonda-9"}))

    def test_ignora_comentarios_y_lineas_vacias(self):
        lista = parse_abundance_list(
            "# referencia: r\n# umbral: 100 RPM\n\nmmu-sonda-124\n\n",
            source="s", version="v", checksum="0" * 32
        )
        self.assertEqual(len(lista.names), 1)

    def test_una_lista_vacia_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_abundance_list(
                "# referencia: r\n# umbral: 100 RPM\n# y nada más\n",
                source="s", version="v", checksum="0" * 32,
            )

    def test_la_procedencia_es_obligatoria(self):
        with self.assertRaises(ValueError):
            parse_abundance_list(self.LISTA, source="", version="v", checksum="0" * 32)

    def test_la_UNICA_lista_en_codigo_es_el_nucleo_autorizado(self):
        """REVERTIDO el 2026-08-26, y por eso este test cambio de forma.

        La regla era «no hay ninguna lista de miARN escrita en el codigo». El
        responsable del proyecto autorizo el NUCLEO —diez familias, consenso del campo,
        sin cita— para que el nivel FAIL no dependa de un fichero que no existe. La
        reversion es ACOTADA: la capa ampliada sigue viniendo de fichero con referencia
        y umbral, y ninguna SECUENCIA entra en el codigo.
        """
        import inspect

        import shmir_design.mirna as modulo
        from shmir_design.mirna import CORE_ABUNDANT, CORE_AUTHORIZATION

        fuente = inspect.getsource(modulo)
        # Los nombres del nucleo SI estan, y su autorizacion tambien.
        self.assertIn("miR-124-3p", fuente)
        # Fragmento contiguo: la constante va partida en varias lineas en el fuente.
        self.assertIn("autorizado por el responsable del proyecto ", fuente)
        self.assertIn("2026-08-26", CORE_AUTHORIZATION)
        self.assertEqual(len(CORE_ABUNDANT), 10)
        # Lo que sigue sin haber es una SECUENCIA: la seed de cada uno sale de
        # `mature.fa`, no de aqui. Rastro tipico de una seed escrita a mano.
        for palabra in fuente.split():
            limpia = palabra.strip('"\',.()[]')
            if len(limpia) >= 7 and set(limpia) <= set("ACGTU"):
                self.fail(f"parece una secuencia escrita en el código: {limpia!r}")


class TestDosNiveles(unittest.TestCase):

    ABUNDANTES = AbundanceList(
        names=frozenset({"mmu-sonda-124"}),
        source="sonda de MirGeneDB",
        version="sonda",
        checksum="0" * 32,
        reference="dataset de sonda",
        threshold="100 RPM",
    )

    def test_sin_maduros_todo_el_filtro_es_NOT_RUN(self):
        r = filter_seed_collision(_guia(SEED_124), None, self.ABUNDANTES)
        self.assertIs(r.state, FilterState.NOT_RUN)

    def test_colision_con_un_abundante_es_FAIL(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), self.ABUNDANTES)
        self.assertIs(r.state, FilterState.FAIL)

    def test_el_FAIL_dice_con_quien_colisiona(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), self.ABUNDANTES)
        self.assertIn("mmu-sonda-124", r.reason)

    def test_el_FAIL_explica_que_se_reprime_una_red_entera(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), self.ABUNDANTES)
        self.assertIn("red", r.reason.lower())

    def test_colision_con_uno_no_abundante_es_solo_aviso(self):
        r = filter_seed_collision(_guia(SEED_9), _maduros(), self.ABUNDANTES)
        self.assertIs(r.state, FilterState.PASS)
        self.assertTrue(r.warnings)

    def test_el_aviso_nombra_al_miARN(self):
        r = filter_seed_collision(_guia(SEED_9), _maduros(), self.ABUNDANTES)
        self.assertIn("mmu-sonda-9", " ".join(r.warnings))

    def test_sin_colision_ninguna_es_PASS_limpio(self):
        r = filter_seed_collision(_guia("CCCCCCC"), _maduros(), self.ABUNDANTES)
        self.assertIs(r.state, FilterState.PASS)
        self.assertEqual(r.warnings, ())

    def test_sin_lista_de_abundancia_el_nivel_FAIL_queda_NOT_RUN(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), None)
        self.assertIs(r.state, FilterState.NOT_RUN)

    def test_sin_lista_de_abundancia_el_WARN_corre_igual(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), None)
        self.assertTrue(r.warnings)
        self.assertIn("mmu-sonda-124", " ".join(r.warnings))

    def test_sin_lista_de_abundancia_el_motivo_dice_que_falta(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), None)
        self.assertIn("abundancia", r.reason.lower())
        self.assertIn("NOT_RUN no es PASS", r.reason)

    def test_una_seed_con_N_no_se_puede_comparar(self):
        r = filter_seed_collision("TAAGGNACGGGGGGGGGGGGG", _maduros(), self.ABUNDANTES)
        self.assertIs(r.state, FilterState.NOT_RUN)

    def test_el_filtro_se_llama_seed_colision(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), self.ABUNDANTES)
        self.assertEqual(r.as_filter().name, "seed_colision")

    def test_el_texto_lleva_la_procedencia_de_las_dos_fuentes(self):
        texto = filter_seed_collision(
            _guia(SEED_124), _maduros(), self.ABUNDANTES
        ).format_text()
        self.assertIn("sonda de MirGeneDB", texto)


class TestCargaDesdeDisco(unittest.TestCase):

    def test_un_md5_que_no_cuadra_aborta(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "mature.fa"
            p.write_text(MADUROS, encoding="utf-8")
            with self.assertRaises(ChecksumMismatchError):
                load_mature_fa(p, version="sonda", expected_md5="0" * 32)

    def test_un_fichero_ausente_aborta_diciendo_cual(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            load_mature_fa(Path("/no/existe/mature.fa"), version="x")
        self.assertIn("mature.fa", str(ctx.exception))

    def test_la_lista_de_abundancia_tambien_comprueba_md5(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "abundantes.txt"
            p.write_text("mmu-sonda-124\n", encoding="utf-8")
            with self.assertRaises(ChecksumMismatchError):
                load_abundance_list(p, version="sonda", expected_md5="0" * 32)


if __name__ == "__main__":
    unittest.main()


class TestPasajeraPorSeparado(unittest.TestCase):
    """La pasajera se mira con la misma vara: si escapa, su seed reprime igual."""

    ABUNDANTES = AbundanceList(
        names=frozenset({"mmu-sonda-124"}),
        source="sonda de MirGeneDB",
        version="sonda",
        checksum="0" * 32,
    )

    def test_una_colision_solo_de_la_pasajera_tambien_condena(self):
        r = filter_seed_collision(
            _guia("CCCCCCC"), _maduros(), self.ABUNDANTES, passenger=_guia(SEED_124)
        )
        self.assertIs(r.state, FilterState.FAIL)

    def test_el_origen_de_la_colision_queda_marcado(self):
        r = filter_seed_collision(
            _guia("CCCCCCC"), _maduros(), self.ABUNDANTES, passenger=_guia(SEED_124)
        )
        self.assertIn("pasajera", r.reason)

    def test_una_colision_de_las_dos_se_marca_una_vez_con_los_dos_origenes(self):
        r = filter_seed_collision(
            _guia(SEED_124), _maduros(), self.ABUNDANTES, passenger=_guia(SEED_124)
        )
        self.assertEqual(len(r.abundant_hits), 1)
        self.assertIn("guia/pasajera", r.reason)

    def test_una_pasajera_con_N_en_la_seed_deja_el_filtro_en_NOT_RUN(self):
        r = filter_seed_collision(
            _guia(SEED_124), _maduros(), self.ABUNDANTES,
            passenger="TAAGGNACGGGGGGGGGGGGG",
        )
        self.assertIs(r.state, FilterState.NOT_RUN)
        self.assertIn("pasajera", r.reason)

    def test_sin_pasajera_el_filtro_sigue_funcionando(self):
        r = filter_seed_collision(_guia(SEED_124), _maduros(), self.ABUNDANTES)
        self.assertIs(r.state, FilterState.FAIL)
