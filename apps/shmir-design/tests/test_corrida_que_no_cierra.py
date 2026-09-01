"""Una corrida que se hizo y NO CIERRA el frente tiene estado propio.

**El criterio, decidido por el responsable del proyecto (2026-09-01).** Una corrida cierra
el frente si y solo si:

  - base LOCAL con md5 registrado — `-remote` no cierra nunca, porque la base de NCBI
    cambia entre corridas y no hay nada que anotar;
  - parametros ESTANDAR — cualquiera cambiado la degrada;
  - md5 del FASTA de consulta cuadrando con el que emitio la app.

**Y las que no cumplan NO son `NOT_RUN`.** «Se corrio y no vale para cerrar» y «no se ha
corrido» son dos situaciones distintas y piden dos cosas distintas: la primera se arregla
REPITIENDO BIEN, la segunda hay que EMPEZARLA. Colapsarlas manda al usuario a buscar de
cero un trabajo que ya hizo.

Es el mismo criterio de `OBSOLETO` y por la misma razon: hay resultado, se puede leer, y
no defiende un veredicto.
"""

import unittest

from shmir_design import blast
from shmir_design.blast_store import BlastDatabase, BlastRun, BlastStore
from shmir_design.filters import FilterState, Verdict, overall_verdict
from shmir_design.presentation import query_name

CONSULTA = query_name("raton", 200, "guia")
GUIA = "TTATATTCTTATTGGCCCGGTG"
CRUDO = (
    f"{CONSULTA}\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191\t1e-05\t44.1\n"
)


def _corrida(*, params=None, remota=False, run_id="r1"):
    fasta = blast.QueryFasta.from_records(((CONSULTA, GUIA),))
    return BlastRun.create(
        run_id=run_id, date="2026-09-01", uploaded_by="responsable",
        params=params or blast.BlastParams.for_species("raton"),
        database=BlastDatabase(
            name="refseq_mouse", version="2026-09-01", md5="a" * 32, remote=remota,
        ),
        query=fasta, raw=CRUDO,
    )


class TestElESTADOnuevoEXISTE(unittest.TestCase):

    def test_hay_un_estado_propio_y_NO_es_NOT_RUN(self):
        self.assertIsNot(FilterState.NO_CIERRA, FilterState.NOT_RUN)

    def test_y_tampoco_es_PASS(self):
        self.assertIsNot(FilterState.NO_CIERRA, FilterState.PASS)

    def test_NO_CIERRA_impide_aprobar_igual_que_NOT_RUN(self):
        from shmir_design.filters import FilterResult

        veredicto = overall_verdict([
            # Con motivo: la regla 3 lo exige TAMBIEN en PASS, y este test se
            # escribio sin el — lo caza `FilterResult.__post_init__`, que hace su
            # trabajo.
            FilterResult(name="x", state=FilterState.PASS, reason="limpio"),
            FilterResult(name="y", state=FilterState.NO_CIERRA, reason="no vale"),
        ])
        self.assertIs(veredicto, Verdict.INCOMPLETE)


class TestLasTRESconDICIONES(unittest.TestCase):
    """Las tres, por separado, cada una degradando por su cuenta."""

    def test_una_corrida_ESTANDAR_y_LOCAL_cierra(self):
        self.assertIs(_corrida().verdict(CONSULTA).state, FilterState.PASS)

    def test_REMOTA_no_cierra_NUNCA(self):
        resultado = _corrida(
            params=blast.BlastParams.for_species("raton", remote=True), remota=True,
        ).verdict(CONSULTA)
        self.assertIs(resultado.state, FilterState.NO_CIERRA)
        self.assertIn("remote", resultado.reason)

    def test_un_parametro_CAMBIADO_la_degrada(self):
        resultado = _corrida(
            params=blast.BlastParams.for_species("raton", word_size=11)
        ).verdict(CONSULTA)
        self.assertIs(resultado.state, FilterState.NO_CIERRA)
        self.assertIn("word_size", resultado.reason)

    def test_y_el_MOTIVO_va_en_el_veredicto_no_en_una_nota(self):
        motivo = _corrida(
            params=blast.BlastParams.for_species("raton", remote=True), remota=True,
        ).verdict(CONSULTA).reason
        # Que se hizo, y por que no vale: las dos cosas, en el propio veredicto.
        self.assertIn("r1", motivo)
        self.assertIn("NO CIERRA", motivo)


class TestSINcorridaSIGUEsiendoNOT_RUN(unittest.TestCase):
    """El control adversario: si todo saliera NO_CIERRA, el estado no distinguiria nada."""

    def test_un_candidato_sin_corrida_es_NOT_RUN(self):
        resultado = BlastStore().verdict_for(CONSULTA)
        self.assertIs(resultado.state, FilterState.NOT_RUN)

    def test_y_los_dos_motivos_dicen_COSAS_DISTINTAS(self):
        sin = BlastStore().verdict_for(CONSULTA).reason
        almacen = BlastStore()
        almacen.add(_corrida(
            params=blast.BlastParams.for_species("raton", remote=True), remota=True,
        ))
        no_vale = almacen.verdict_for(CONSULTA).reason
        self.assertNotEqual(sin, no_vale)
        # Uno manda a EMPEZAR y el otro a REPETIR: es toda la diferencia.
        self.assertIn("No hay ninguna corrida", sin)
        self.assertIn("NO CIERRA", no_vale)


if __name__ == "__main__":
    unittest.main()
