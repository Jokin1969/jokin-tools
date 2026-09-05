"""El almacen de corridas de BLAST: inmutable, validado y sin sobrescribir.

Regla 5: escritos antes.

CRITERIOS DE ACEPTACION, uno por clase:

  1. Un resultado subido con parametros distintos a los estandar NO puede presentarse
     como veredicto estandar.
  2. Un resultado cuyo md5 de consulta no coincida SE RECHAZA.
  3. Un `-remote` NO puede cerrar el frente.
  4. La ficha de un candidato sin corrida sigue diciendo `NOT_RUN`, visible.
"""

import unittest

from shmir_design import blast
from shmir_design.blast_store import (
    BlastDatabase, BlastRun, BlastStore, validate_upload,
)
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState

from shmir_design.presentation import query_name

# EL NOMBRE DE UNA CONSULTA SE PIDE, NO SE ESCRIBE. Estos tests transcribian
# `raton_pos200_guia`, que es un formato que la app YA NO PRODUCE —el slug de la especie
# es `mouse`, no `raton`—: coincidian consigo mismos, asi que el desfase no se veia. Es
# la mitad que dejo pasar la errata nº 44. Ver `data/claves_derivadas.toml`.
def Q(inicio, hebra="guia", especie="mouse"):
    return query_name(especie, inicio, hebra)


CRUDO = (
    f"{Q(200)}\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191\t1e-05\t44.1\n"
    f"{Q(200, 'pasajera')}\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191\t1e-05\t44.1\n"
)

LOCAL = BlastDatabase(
    name="refseq_rna", version="2026-08-26", md5="a" * 32, remote=False
)
REMOTA = BlastDatabase(name="refseq_rna", version="", md5=None, remote=True)


def _consulta():
    return blast.QueryFasta.from_records(
        (
            (Q(200), "TTATATTCTTATTGGCCCGGTG"),
            (Q(200, "pasajera"), "CACCGGGCCAATAAGAATATAA"),
        )
    )


def _corrida(**cambios):
    consulta = cambios.pop("consulta", None) or _consulta()
    base = dict(
        run_id="r1", date="2026-08-26", uploaded_by="responsable del proyecto",
        params=blast.DEFAULTS, database=LOCAL, query=consulta, raw=CRUDO,
    )
    base.update(cambios)
    return BlastRun.create(**base)


class TestLaBaseDeDatos(unittest.TestCase):

    def test_una_LOCAL_necesita_version_y_md5(self):
        with self.assertRaises(ValueError):
            BlastDatabase(name="refseq_rna", version="", md5=None, remote=False)

    def test_una_local_con_md5_es_REPRODUCIBLE(self):
        self.assertTrue(LOCAL.reproducible)

    def test_una_REMOTA_no_lo_es_y_lo_dice_con_esas_palabras(self):
        self.assertFalse(REMOTA.reproducible)
        self.assertIn("no reproducible", REMOTA.describe().lower())

    def test_y_dice_por_que(self):
        self.assertIn("cambia entre corridas", REMOTA.describe().lower())


class TestElRegistroEsINMUTABLE(unittest.TestCase):

    def setUp(self):
        self.corrida = _corrida()

    def test_trae_TODO_lo_que_hay_que_guardar(self):
        c = self.corrida
        self.assertEqual(c.run_id, "r1")
        self.assertEqual(c.date, "2026-08-26")
        self.assertTrue(c.uploaded_by)
        self.assertEqual(len(c.query_md5), 32)
        self.assertEqual(len(c.result_md5), 32)
        self.assertIs(c.params, blast.DEFAULTS)
        self.assertIs(c.database, LOCAL)

    def test_guarda_el_CRUDO_sin_tocar_ademas_del_parseado(self):
        self.assertEqual(self.corrida.raw, CRUDO)
        self.assertEqual(len(self.corrida.hits), 2)

    def test_los_parametros_van_COMPLETOS_no_solo_los_cambiados(self):
        texto = "\n".join(self.corrida.describe())
        for trozo in ("task=", "word_size=", "evalue=", "dust=", "db="):
            self.assertIn(trozo, texto)

    def test_no_se_puede_modificar(self):
        from dataclasses import FrozenInstanceError

        with self.assertRaises(FrozenInstanceError):
            self.corrida.run_id = "otro"

    def test_sin_quien_la_subio_ABORTA(self):
        with self.assertRaises(ValueError):
            _corrida(uploaded_by="")


class TestCriterio1_ParametrosNoEstandar(unittest.TestCase):
    """Un resultado con parametros cambiados no puede presentarse como estandar."""

    def setUp(self):
        self.raro = _corrida(params=blast.DEFAULTS.with_changes(word_size=11))

    def test_la_corrida_NO_da_veredicto(self):
        self.assertFalse(self.raro.gives_verdict)

    def test_su_veredicto_es_NO_CIERRA_no_PASS(self):
        """CAMBIO DE DECISION (2026-09-01), no una regresion.

        Este test exigia `NOT_RUN`. Ahora exige `NO_CIERRA`, que es un estado PROPIO: la
        corrida existe y se puede leer, y lo que pasa es que no defiende un veredicto.
        La diferencia es accionable — «se corrio y no vale» se arregla REPITIENDO BIEN y
        «no se ha corrido» hay que EMPEZARLO, y detras de una corrida de BLAST hay una
        descarga de decenas de GB. Lo que NO cambia es que ninguno de los dos aprueba.
        """
        self.assertIs(self.raro.verdict().state, FilterState.NO_CIERRA)

    def test_y_el_motivo_NOMBRA_el_ajuste_cambiado(self):
        self.assertIn("word_size", self.raro.verdict().reason)

    def test_la_estandar_SI_da_veredicto(self):
        self.assertTrue(_corrida().gives_verdict)

    def test_los_ajustes_VIAJAN_con_el_resultado(self):
        # No se puede leer la corrida sin ver que se toco algo.
        self.assertIn("MODIFICADOS", "\n".join(self.raro.describe()))


class TestCriterio2_ElMd5DeConsulta(unittest.TestCase):
    """Un resultado cuyo md5 de consulta no coincida se rechaza."""

    def test_el_bueno_pasa(self):
        consulta = _consulta()
        validate_upload(
            raw=CRUDO, query=consulta, declared_query_md5=consulta.md5,
            panel_names=consulta.names,
        )

    def test_un_md5_distinto_SE_RECHAZA(self):
        consulta = _consulta()
        with self.assertRaises(ShmirDesignError) as ctx:
            validate_upload(
                raw=CRUDO, query=consulta, declared_query_md5="b" * 32,
                panel_names=consulta.names,
            )
        self.assertIn("md5", str(ctx.exception).lower())

    def test_y_el_motivo_dice_que_es_de_OTRA_corrida(self):
        consulta = _consulta()
        with self.assertRaises(ShmirDesignError) as ctx:
            validate_upload(
                raw=CRUDO, query=consulta, declared_query_md5="b" * 32,
                panel_names=consulta.names,
            )
        self.assertIn("otra corrida", str(ctx.exception).lower())

    def test_una_guia_del_resultado_que_NO_esta_en_el_panel_se_rechaza(self):
        consulta = _consulta()
        ajeno = CRUDO + (
            f"{Q(999, especie='human')}\tNM_000311.5\t100.000\t22\t0\t0\t1\t22\t1\t22\t1e-05\t44.1\n"
        )
        with self.assertRaises(ShmirDesignError) as ctx:
            validate_upload(
                raw=ajeno, query=consulta, declared_query_md5=consulta.md5,
                panel_names=consulta.names,
            )
        self.assertIn(Q(999, especie="human"), str(ctx.exception))

    def test_es_el_fallo_del_CSV_de_miRarchitect_y_lo_dice(self):
        consulta = _consulta()
        with self.assertRaises(ShmirDesignError) as ctx:
            validate_upload(
                raw=CRUDO, query=consulta, declared_query_md5="b" * 32,
                panel_names=consulta.names,
            )
        self.assertIn("miRarchitect", str(ctx.exception))


class TestCriterio3_RemoteNoCierraElFrente(unittest.TestCase):

    def setUp(self):
        self.remota = _corrida(
            params=blast.DEFAULTS.with_changes(remote=True), database=REMOTA
        )

    def test_no_da_veredicto(self):
        self.assertFalse(self.remota.gives_verdict)

    def test_su_veredicto_es_NO_CIERRA(self):
        """CAMBIO DE DECISION (2026-09-01), no una regresion.

        Este test exigia `NOT_RUN`. Ahora exige `NO_CIERRA`, que es un estado PROPIO: la
        corrida existe y se puede leer, y lo que pasa es que no defiende un veredicto.
        La diferencia es accionable — «se corrio y no vale» se arregla REPITIENDO BIEN y
        «no se ha corrido» hay que EMPEZARLO, y detras de una corrida de BLAST hay una
        descarga de decenas de GB. Lo que NO cambia es que ninguno de los dos aprueba.
        """
        self.assertIs(self.remota.verdict().state, FilterState.NO_CIERRA)

    def test_el_motivo_dice_EXPLORACION(self):
        self.assertIn("exploracion", self.remota.verdict().reason.lower())

    def test_una_base_remota_con_parametros_estandar_TAMPOCO(self):
        # Aunque no se toque ningun ajuste mas: la base es la que no es reproducible.
        solo_remote = _corrida(
            params=blast.DEFAULTS.with_changes(remote=True), database=REMOTA
        )
        self.assertFalse(solo_remote.gives_verdict)

    def test_una_base_declarada_local_con_params_remote_ABORTA(self):
        # Incoherencia entre lo declarado y lo hecho: no se elige por nuestra cuenta.
        with self.assertRaises(ValueError):
            _corrida(params=blast.DEFAULTS.with_changes(remote=True), database=LOCAL)


class TestNadaSeSOBRESCRIBE(unittest.TestCase):

    def setUp(self):
        self.almacen = BlastStore()

    def test_dos_corridas_del_mismo_candidato_se_SUMAN(self):
        self.almacen.add(_corrida(run_id="r1"))
        self.almacen.add(_corrida(run_id="r2", date="2026-08-27"))
        self.assertEqual(len(self.almacen.history(Q(200))), 2)

    def test_la_ficha_muestra_la_ULTIMA(self):
        self.almacen.add(_corrida(run_id="r1", date="2026-08-26"))
        self.almacen.add(_corrida(run_id="r2", date="2026-08-27"))
        self.assertEqual(self.almacen.latest(Q(200)).run_id, "r2")

    def test_repetir_un_run_id_ABORTA(self):
        self.almacen.add(_corrida(run_id="r1"))
        with self.assertRaises(ShmirDesignError):
            self.almacen.add(_corrida(run_id="r1"))

    def test_el_historial_va_en_orden(self):
        self.almacen.add(_corrida(run_id="r2", date="2026-08-27"))
        self.almacen.add(_corrida(run_id="r1", date="2026-08-26"))
        self.assertEqual(
            [c.run_id for c in self.almacen.history(Q(200))], ["r1", "r2"]
        )


class TestCriterio4_SinCorridaSigueEnNOT_RUN(unittest.TestCase):

    def setUp(self):
        self.almacen = BlastStore()

    def test_un_candidato_sin_corrida_es_NOT_RUN(self):
        resultado = self.almacen.verdict_for(Q(999))
        self.assertIs(resultado.state, FilterState.NOT_RUN)

    def test_y_es_VISIBLE_no_una_ausencia(self):
        motivo = self.almacen.verdict_for(Q(999)).reason
        self.assertIn("ninguna corrida", motivo.lower())
        self.assertIn("NOT_RUN no es PASS", motivo)

    def test_el_almacen_NO_relaja_la_disciplina(self):
        # Meter una corrida de OTRO candidato no cambia el de este.
        self.almacen.add(_corrida())
        self.assertIs(
            self.almacen.verdict_for(Q(999)).state, FilterState.NOT_RUN
        )

    def test_con_corrida_estandar_local_SI_hay_veredicto(self):
        self.almacen.add(_corrida())
        self.assertIsNot(
            self.almacen.verdict_for(Q(200)).state, FilterState.NOT_RUN
        )

    def test_con_corrida_remota_pasa_a_NO_CIERRA(self):
        """Y NO se queda en NOT_RUN, que es el cambio de decision de 2026-09-01.

        Aqui esta la mitad que importa del estado nuevo: quien ve esta celda ya sabe que
        hay una corrida hecha y que el arreglo es repetirla en local, no empezar de cero
        bajandose la base otra vez.
        """
        self.almacen.add(
            _corrida(params=blast.DEFAULTS.with_changes(remote=True), database=REMOTA)
        )
        resultado = self.almacen.verdict_for(Q(200))
        self.assertIs(resultado.state, FilterState.NO_CIERRA)
        self.assertIn("REPITIENDO", resultado.reason)


if __name__ == "__main__":
    unittest.main()
