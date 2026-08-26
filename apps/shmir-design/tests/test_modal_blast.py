"""El modal de especificidad: toda la LOGICA aqui, ninguna en la pagina.

Regla 5: escritos antes. Regla 6: la interfaz Streamlit no contiene logica — lo que
decide algo vive en `presentation.py` y tiene tests. Si la pagina empieza a decidir
—ordenar, marcar en rojo, elegir un estado— eso se arregla moviendolo aqui.
"""

import unittest

from shmir_design import blast, presentation
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]


def _seleccion():
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    informe = tile_utr(load_3utr(RATON))
    return select_from_report(informe, SelectionConfig(n_candidates=10))


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaSeleccionDeCandidatos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.seleccion = _seleccion()
        cls.filas = presentation.blast_candidate_rows(cls.seleccion, species="raton")

    def test_hay_una_fila_por_candidato(self):
        self.assertEqual(len(self.filas), len(self.seleccion.selection.chosen))

    def test_cada_fila_trae_los_DOS_nombres_de_consulta(self):
        for fila in self.filas:
            self.assertTrue(fila["guia_id"].endswith("_guia"))
            self.assertTrue(fila["pasajera_id"].endswith("_pasajera"))

    def test_guia_y_pasajera_son_DOS_consultas_y_se_dice(self):
        self.assertIn("dos consultas", presentation.BLAST_MODAL_NOTE.lower())

    def test_todas_son_del_panel_en_esta_corrida(self):
        self.assertTrue(all(f["panel"] for f in self.filas))

    def test_las_filas_traen_lo_que_hace_falta_para_decidir(self):
        fila = self.filas[0]
        for clave in ("start", "guia", "pasajera", "asimetria", "veredicto"):
            self.assertIn(clave, fila)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaConsultaQueSeConstruye(unittest.TestCase):

    def setUp(self):
        self.seleccion = _seleccion()

    def test_guia_y_pasajera_son_registros_SEPARADOS(self):
        consulta = presentation.blast_query(
            self.seleccion, species="raton", starts=(10,), guides=True, passengers=True
        )
        self.assertEqual(len(consulta.records), 2)

    def test_solo_guias_da_UN_registro(self):
        consulta = presentation.blast_query(
            self.seleccion, species="raton", starts=(10,), guides=True, passengers=False
        )
        self.assertEqual(len(consulta.records), 1)
        self.assertTrue(consulta.names[0].endswith("_guia"))

    def test_sin_guias_ni_pasajeras_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            presentation.blast_query(
                self.seleccion, species="raton", starts=(10,),
                guides=False, passengers=False,
            )

    def test_sin_candidatos_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            presentation.blast_query(
                self.seleccion, species="raton", starts=(),
                guides=True, passengers=True,
            )

    def test_un_start_que_no_esta_en_el_panel_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            presentation.blast_query(
                self.seleccion, species="raton", starts=(99999,),
                guides=True, passengers=True,
            )
        self.assertIn("99999", str(ctx.exception))

    def test_las_guias_van_en_ADN(self):
        consulta = presentation.blast_query(
            self.seleccion, species="raton", starts=(10,), guides=True, passengers=False
        )
        self.assertNotIn("U", consulta.records[0][1])

    def test_el_md5_se_muestra_para_pegarlo_al_subir(self):
        consulta = presentation.blast_query(
            self.seleccion, species="raton", starts=(10,), guides=True, passengers=True
        )
        self.assertIn(consulta.md5, consulta.describe())


class TestLosAjustesYElROJO(unittest.TestCase):

    def test_por_defecto_ninguna_fila_va_marcada(self):
        filas = presentation.blast_setting_rows(blast.DEFAULTS)
        self.assertTrue(all(not f["modificado"] for f in filas))

    def test_cambiar_uno_marca_SOLO_ese(self):
        filas = presentation.blast_setting_rows(
            blast.DEFAULTS.with_changes(word_size=11)
        )
        marcadas = [f["ajuste"] for f in filas if f["modificado"]]
        self.assertEqual(marcadas, ["word_size"])

    def test_cada_fila_trae_el_valor_y_el_POR_DEFECTO(self):
        fila = next(
            f for f in presentation.blast_setting_rows(
                blast.DEFAULTS.with_changes(word_size=11)
            ) if f["ajuste"] == "word_size"
        )
        self.assertEqual(fila["valor"], "11")
        self.assertEqual(fila["por_defecto"], "7")

    def test_estan_TODOS_los_ajustes_no_solo_los_cambiados(self):
        filas = presentation.blast_setting_rows(blast.DEFAULTS)
        nombres = {f["ajuste"] for f in filas}
        for esperado in (
            "task", "word_size", "evalue", "dust", "outfmt", "db", "entrez_query",
            "include_predicted", "remote",
        ):
            self.assertIn(esperado, nombres)


class TestLosAvisosDelModal(unittest.TestCase):

    def test_con_los_valores_por_defecto_NO_hay_aviso_bloqueante(self):
        avisos = presentation.blast_warnings(blast.DEFAULTS)
        self.assertEqual([a for a in avisos if a["bloquea"]], [])

    def test_remote_da_aviso_que_BLOQUEA(self):
        avisos = presentation.blast_warnings(blast.DEFAULTS.with_changes(remote=True))
        bloqueantes = [a for a in avisos if a["bloquea"]]
        self.assertTrue(bloqueantes)
        self.assertIn("exploracion", bloqueantes[0]["texto"].lower())

    def test_un_ajuste_cambiado_tambien(self):
        avisos = presentation.blast_warnings(
            blast.DEFAULTS.with_changes(word_size=11)
        )
        self.assertTrue([a for a in avisos if a["bloquea"]])

    def test_el_aviso_del_seed_sale_SIEMPRE_y_no_bloquea_este_modal(self):
        avisos = presentation.blast_warnings(blast.DEFAULTS)
        seed = [a for a in avisos if "seed" in a["texto"].lower()]
        self.assertTrue(seed)
        self.assertIn("7 nt", seed[0]["texto"])

    def test_ese_aviso_dice_que_es_OTRO_frente(self):
        avisos = presentation.blast_warnings(blast.DEFAULTS)
        seed = next(a for a in avisos if "seed" in a["texto"].lower())
        self.assertIn("offtarget_seed", seed["texto"])


class TestLaOrdenQueSeCopia(unittest.TestCase):

    def test_lleva_la_ruta_del_FASTA_que_genera_el_modal(self):
        orden = presentation.blast_command_text(
            blast.DEFAULTS, query_path="raton_consulta.fasta"
        )
        self.assertIn("raton_consulta.fasta", orden)

    def test_y_el_fichero_de_salida_sugerido(self):
        orden = presentation.blast_command_text(
            blast.DEFAULTS, query_path="q.fasta", out_path="r.tsv"
        )
        self.assertIn("-out r.tsv", orden)

    def test_el_ejecutor_de_hoy_sale_nombrado_con_su_motivo(self):
        texto = presentation.blast_executor_text()
        self.assertIn("deshabilitado", texto)
        self.assertIn("CORS", texto)


if __name__ == "__main__":
    unittest.main()


class TestLaPaginaNoCONVIERTE_nada(unittest.TestCase):
    """Convertir «SI» a booleano es una decision, y las decisiones tienen test."""

    BASE = {
        "task": "blastn-short", "word_size": "7", "evalue": "1000", "dust": "no",
        "outfmt": "6", "db": "refseq_rna", "entrez_query": "txid10090",
        "include_predicted": "SI", "remote": "no",
    }

    def test_los_valores_por_defecto_dan_los_DEFAULTS(self):
        self.assertEqual(presentation.blast_params_from_form(dict(self.BASE)), blast.DEFAULTS)

    def test_si_en_minusculas_TAMBIEN_es_si(self):
        datos = dict(self.BASE, remote="si")
        self.assertTrue(presentation.blast_params_from_form(datos).remote)

    def test_una_palabra_que_no_entiende_ABORTA_y_no_cae_a_no(self):
        # El fallo silencioso: leerlo como «no» por descarte y perder el aviso de que
        # la corrida era remota.
        datos = dict(self.BASE, remote="quizas")
        with self.assertRaises(ShmirDesignError) as ctx:
            presentation.blast_params_from_form(datos)
        self.assertIn("remote", str(ctx.exception))

    def test_un_numero_ilegible_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            presentation.blast_params_from_form(dict(self.BASE, word_size="siete"))

    def test_y_la_validacion_de_rango_la_sigue_haciendo_el_dataclass(self):
        with self.assertRaises(ValueError):
            presentation.blast_params_from_form(dict(self.BASE, word_size="0"))


class TestLaPaginaNoTieneLOGICA(unittest.TestCase):
    """Regla 6: lo que decide algo vive en `presentation.py`, no en la pagina."""

    def test_el_modal_de_la_pagina_no_convierte_ni_compara_datos(self):
        import inspect
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        inicio = fuente.index("def _modal_blast(")
        modal = fuente[inicio:]
        for prohibido in ("int(", "float(", ".upper()", ".lower()", "sorted("):
            self.assertNotIn(prohibido, modal, prohibido)
